"""§8 Feature Flag 최종 검증 실제 E2E — 2026-08-25 지시서(a/final-integration-master-
promotion) §8. 3개 Flag를 모두 실제 환경변수로 켠 채(모듈 import 시점에 이미 반영돼야
하므로 별도 프로세스로 실행한다) 실제 12개 승인 ContextPack + 3개 Vertical Slice =
15개 Context, 4+1 선택 정책, 실제 질문 흐름, Profile/Major/Subject/Subgraph까지
전부 실제 API로 검증한다. LLM/LangSmith는 `test_course_planning_full_flow_e2e.py`와
같은 패턴으로 강제로 끈다(Cache/Backup 경로만 탄다) — Trait Summary를 직접 주입하지
않는다.

`tests/`의 `unittest discover` 대상이 아니라 `scripts/`에 독립 스크립트로 둔다 — 세
Feature Flag는 `src.api.main` 모듈 import 시점에 이미 반영돼 있어야 하는데(앱 시작
검사·Registry 구성이 import 시 1회만 실행), 전체 테스트 스위트를 한 프로세스에서 돌리면
다른 테스트가 먼저 Flag OFF 상태로 그 모듈을 import해버려 이 파일에서 다시 켜도 반영되지
않는다. 그래서 독립 프로세스로 실행한다:

    PYTHONPATH=. ./.venv/bin/python scripts/verify_section8_feature_flag_e2e.py
"""

from __future__ import annotations

import os

os.environ["ENABLE_CONTEXT_PACK_RUNTIME"] = "true"
os.environ["ENABLE_CONTEXT_SELECTION_4_PLUS_1"] = "true"
os.environ["ENABLE_TRAIT_VECTOR_V2_PRIMARY"] = "true"

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

import src.api.main as main_module  # noqa: E402
from src.api.main import app  # noqa: E402
from src.tracing.tracer import Tracer  # noqa: E402

main_module._llm_client = None
main_module._tracer = Tracer(client=None)

client = TestClient(app)
_MAX_TURNS = 40


def _fail(label: str, detail: str) -> None:
    print(f"FAIL[{label}]: {detail}")
    raise SystemExit(1)


def main() -> None:
    r = client.get("/contexts")
    if r.status_code != 200:
        _fail("GET /contexts", r.text)
    catalog = r.json()
    contexts = catalog["contexts"]
    if len(contexts) != 15:
        _fail("catalog count", f"expected 15, got {len(contexts)}: {sorted(c['context_id'] for c in contexts)}")
    supported = [c["context_id"] for c in contexts if c.get("assessment_supported")]
    if len(supported) != 15:
        _fail("assessment_supported count", f"expected 15, got {len(supported)}: {sorted(supported)}")
    policy = catalog["selection_policy"]
    if (policy["preferred_context_min_count"], policy["preferred_context_max_count"], policy["contrast_context_count"]) != (4, 4, 1):
        _fail("selection_policy", str(policy))
    print(f"OK: /contexts -> 15 total, 15 assessment_supported, policy={policy}")

    r = client.post("/assessment/session")
    if r.status_code != 200:
        _fail("POST /assessment/session", r.text)
    session_id = r.json()["session_id"]
    print(f"OK: session {session_id}")

    preferred = ["business", "science", "sports", "art_design"]
    ratings = {cid: 5 for cid in preferred}
    r = client.post("/assessment/interest-rating", json={"session_id": session_id, "ratings": ratings})
    if r.status_code != 200:
        _fail("POST /assessment/interest-rating", r.text)
    print("OK: interest-rating")

    r = client.post(
        "/assessment/context-select",
        json={"session_id": session_id, "selected_preferred_context_ids": preferred},
    )
    if r.status_code != 200:
        _fail("POST /assessment/context-select", r.text)
    contrast_id = r.json()["contrast_context_id"]
    print(f"OK: context-select -> contrast={contrast_id}")

    final_ids = preferred + [contrast_id]
    r = client.post(
        "/assessment/context-confirm",
        json={"session_id": session_id, "final_context_ids": final_ids},
    )
    if r.status_code != 200:
        _fail("POST /assessment/context-confirm", r.text)
    print(f"OK: context-confirm -> final={r.json()['final_context_ids']}")

    for turn in range(_MAX_TURNS):
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        if r.status_code != 200:
            _fail(f"next-question turn={turn}", r.text)
        body = r.json()
        if body["status"] == "CONTEXT_EARLY_TERMINATED":
            if body["assessment_complete"]:
                break
            continue
        if body["status"] == "ASSESSMENT_COMPLETE" or body.get("question") is None:
            break
        question = body["question"]
        if len(question["options"]) != 5:
            _fail(f"question options turn={turn}", f"expected 5, got {len(question['options'])}")
        option = question["options"][(turn * 2) % 5]
        ar = client.post(
            "/assessment/answer",
            json={
                "session_id": session_id, "question_id": question["question_id"],
                "selected_option_id": option["option_id"],
            },
        )
        if ar.status_code != 200:
            _fail(f"answer turn={turn}", ar.text)
        if ar.json()["next_action"] == "ASSESSMENT_COMPLETE":
            break
    else:
        _fail("turn loop", f"did not complete within {_MAX_TURNS} turns")
    print(f"OK: question/answer loop completed in <= {turn + 1} turns")

    r = client.get(f"/profile/{session_id}")
    if r.status_code != 200:
        _fail("GET /profile", r.text)
    profile = r.json()
    dimensions = profile.get("detailed_evidence_by_dimension") or {}
    for label in ("84%", "81점"):
        for h in profile.get("highlights", []):
            if label in str(h):
                _fail("profile fake accuracy", f"{label} found in highlights: {h}")
    print(f"OK: /profile -> {len(dimensions)} trait dimensions, keys={list(profile.keys())}")

    r = client.get(f"/majors/{session_id}")
    if r.status_code != 200:
        _fail("GET /majors", r.text)
    majors_body = r.json()
    recommended = majors_body["relevant_majors"] + majors_body["explore_together_majors"]
    if len(recommended) == 0:
        _fail("majors", "0개 computed 대표 전공 — Trait Summary를 직접 주입해 억지로 통과시키지 않는다")
    has_description = all("description" in m and m["description"] for m in recommended)
    print(f"OK: /majors -> {len(recommended)} recommended, description_present={has_description}")
    print(f"  sample major keys: {list(recommended[0].keys())}")

    selected_major_id = recommended[0]["major_id"]
    r = client.get(f"/departments/{selected_major_id}")
    if r.status_code != 200:
        _fail("GET /departments", r.text)
    departments_body = r.json()
    depts = departments_body["departments"]
    print(f"OK: /departments/{selected_major_id} -> {len(depts)} national departments")
    if depts:
        sample = depts[0]
        print(f"  sample department keys: {list(sample.keys())}")
        source_url = sample.get("source_url")
        department_url = sample.get("department_url")
        print(f"  sample source_url={source_url!r} department_url={department_url!r}")

    r = client.get(f"/subjects/{session_id}", params={"selected_major_id": selected_major_id})
    if r.status_code != 200:
        _fail("GET /subjects", r.text)
    subjects_body = r.json()
    print(f"OK: /subjects -> keys={list(subjects_body.keys())}")

    r = client.get(f"/subgraph/{session_id}")
    if r.status_code != 200:
        _fail("GET /subgraph", r.text)
    subgraph_body = r.json()
    print(
        f"OK: /subgraph -> nodes={len(subgraph_body.get('nodes', []))}, "
        f"edges={len(subgraph_body.get('edges', []))}"
    )

    print("\n=== §8 실제 E2E 전체 통과 ===")


if __name__ == "__main__":
    main()
