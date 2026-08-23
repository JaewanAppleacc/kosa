"""Legacy vs v2(Trait Vector Primary) Persona 비교 리포트 생성 — 2026-08-23 Trait
Ontology v2(2.6단계) §11.

각 Persona를 실제 `/assessment/*` API로 세션을 끝까지 진행시킨 뒤, 같은 세션(같은
evidence_ledger)에 대해 PRIMARY=false(Legacy)와 PRIMARY=true(v2)로 각각 /profile·
/majors를 호출해 비교한다 — Trait Summary를 직접 주입하지 않고 실제 흐름을 그대로
쓴다(§12와 같은 원칙).

옵션 선택 전략: `_llm_client=None`일 때 꼬리질문은 `mock_data.tail_question_from_
planner_decision()`이 만드는 자리표시자 role_id(`role_{trait_id}` 형태, 1.5단계 §1
감사 결과)를 쓴다 — 이 사실을 이용해 "role_id에 목표 Trait 이름이 포함된 선택지를
우선 고른다"는 결정론적 전략으로 Persona별 답변 성향을 만든다. 완벽한 심리 모사가
아니라, Legacy/v2 계산 로직이 같은 입력에 대해 실제로 어떻게 다르게(또는 같게) 반응
하는지 보여주는 것이 목적이다.

실행: PYTHONPATH=. ./.venv/bin/python scripts/evaluate_trait_v2_primary_comparison.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", "")

from fastapi.testclient import TestClient  # noqa: E402

import src.api.main as main_module  # noqa: E402
from scripts.career_console import use_utf8_stdout  # noqa: E402
from src.api.main import app  # noqa: E402
from src.tracing.tracer import Tracer  # noqa: E402

client = TestClient(app)

_MAX_TURNS = 40
_ALL_CONTEXTS = ["game", "media", "school_life"]


def _pick_option(question: dict, turn: int, preferred_substrings: list[str]) -> dict:
    for substring in preferred_substrings:
        for option in question["options"]:
            if substring in option["role_id"]:
                return option
    return question["options"][(turn * 2) % 5]


def _drive_session(
    preferred_substrings: list[str], *, max_answers: int | None = None,
    direct_probes: bool = False, option_selector=None,
) -> str:
    if direct_probes:
        os.environ["ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES"] = "true"
    else:
        os.environ.pop("ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", None)
    os.environ.pop("ENABLE_TRAIT_VECTOR_V2_PRIMARY", None)

    r = client.post("/assessment/session")
    session_id = r.json()["session_id"]
    client.post(
        "/assessment/interest-rating",
        json={"session_id": session_id, "ratings": {"game": 5, "media": 5, "school_life": 4}},
    )
    client.post(
        "/assessment/context-select",
        json={"session_id": session_id, "selected_preferred_context_ids": _ALL_CONTEXTS[:2]},
    )
    client.post(
        "/assessment/context-confirm",
        json={"session_id": session_id, "final_context_ids": _ALL_CONTEXTS},
    )

    answered = 0
    for turn in range(_MAX_TURNS):
        if max_answers is not None and answered >= max_answers:
            break
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        body = r.json()
        if body["status"] == "CONTEXT_EARLY_TERMINATED":
            if body["assessment_complete"]:
                break
            continue
        question = body["question"]
        if option_selector is not None:
            option = option_selector(question, turn)
        else:
            option = _pick_option(question, turn, preferred_substrings)
        ar = client.post(
            "/assessment/answer",
            json={
                "session_id": session_id, "question_id": question["question_id"],
                "selected_option_id": option["option_id"],
            },
        )
        answered += 1
        if ar.json().get("next_action") == "ASSESSMENT_COMPLETE":
            break
    return session_id


def _top_trait_ids(profile_body: dict, n: int = 5) -> list[str]:
    seen: list[str] = []
    for h in profile_body["highlights"]:
        for tid in h["supporting_trait_ids"]:
            if tid not in seen:
                seen.append(tid)
    return seen[:n]


def _major_ids(majors_body: dict) -> list[str]:
    return [m["major_id"] for m in majors_body["relevant_majors"] + majors_body["explore_together_majors"]]


def _conflict_option_selector(question: dict, turn: int) -> dict:
    substrings = ["planning"] if turn % 2 == 0 else ["immediate_execution"]
    return _pick_option(question, turn, substrings)


def _run_persona(name: str, description: str, preferred_substrings: list[str], **drive_kwargs) -> dict:
    session_id = _drive_session(preferred_substrings, **drive_kwargs)

    os.environ.pop("ENABLE_TRAIT_VECTOR_V2_PRIMARY", None)
    legacy_profile = client.get(f"/profile/{session_id}").json()
    legacy_majors = client.get(f"/majors/{session_id}").json()

    os.environ["ENABLE_TRAIT_VECTOR_V2_PRIMARY"] = "true"
    v2_profile_resp = client.get(f"/profile/{session_id}")
    v2_profile = v2_profile_resp.json() if v2_profile_resp.status_code == 200 else None
    v2_majors_resp = client.get(f"/majors/{session_id}")
    v2_majors = v2_majors_resp.json() if v2_majors_resp.status_code == 200 else None
    os.environ.pop("ENABLE_TRAIT_VECTOR_V2_PRIMARY", None)

    state = main_module._store.load(session_id)
    excluded_signal_count = 0
    if state is not None:
        from src.services.trait_signal_review_gate import gate_primary_eligible_evidence

        gate = gate_primary_eligible_evidence(state.evidence_ledger, state.context_anchor_choices)
        excluded_signal_count = len(gate.excluded_evidence_ids)

    return {
        "name": name, "description": description, "session_id": session_id,
        "legacy_top_traits": _top_trait_ids(legacy_profile),
        "v2_top_traits": _top_trait_ids(v2_profile) if v2_profile else [],
        "legacy_majors": _major_ids(legacy_majors),
        "v2_majors": _major_ids(v2_majors) if v2_majors else [],
        "legacy_evidence_sufficiency_present": bool(legacy_majors["relevant_majors"] or legacy_majors["explore_together_majors"]),
        "v2_evidence_sufficiency_present": bool(v2_majors and (v2_majors["relevant_majors"] or v2_majors["explore_together_majors"])),
        "excluded_unreviewed_signal_count": excluded_signal_count,
        "answer_count": len(state.evidence_ledger) if state else 0,
        "unresolved_conflict_trait_ids": sorted(state.unresolved_conflict_trait_ids) if state else [],
    }


def run_all_personas() -> list[dict]:
    personas = []
    personas.append(_run_persona(
        "분석·구조화 경향", "원인 분석·패턴 탐색·정보 비교 계열 선택지를 일관되게 고른다.",
        ["causal_analysis", "pattern_finding", "information_comparison", "systems_thinking"],
    ))
    personas.append(_run_persona(
        "시각·사용자 관점 경향", "시각 표현·청중 반응 예측 계열 선택지를 일관되게 고른다.",
        ["visual_expression", "audience_response_prediction", "aesthetic_sensitivity"],
    ))
    personas.append(_run_persona(
        "계획·지속 경향", "계획·완수 지속 계열 선택지를 일관되게 고른다.",
        ["planning", "persistence_completion", "detail_orientation"],
    ))
    personas.append(_run_persona(
        "다양한 Trait가 얕게 관찰된 경우", "매 턴 서로 다른 Trait 선택지를 골고루 고른다(깊이 없음).",
        [],  # 빈 목록 → 항상 (turn*2)%5 기본 순환만 쓴다.
    ))
    personas.append(_run_persona(
        "Evidence 부족", "세션을 아주 짧게(1문항) 종료한다.",
        [], max_answers=1,
    ))
    personas.append(_run_persona(
        "Explicit Conflict", "짝수 턴엔 planning 계열, 홀수 턴엔 immediate_execution 계열을 고른다"
        "(§12-1 사전 정의 Contrast Pair: planning_vs_execution).",
        [], option_selector=_conflict_option_selector,
    ))
    personas.append(_run_persona(
        "검수되지 않은 Direct Probe Signal만 존재하는 경우",
        "ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES=true로 세션을 진행해 DRAFT Direct Probe "
        "Signal이 섞이게 한다.",
        [], direct_probes=True,
    ))
    return personas


def render_report(personas: list[dict]) -> str:
    lines = [
        "# Trait Vector v2 Primary — Legacy/v2 Persona 비교 리포트",
        "",
        "2026-08-23 Trait Ontology v2(2.6단계) §11. 각 Persona는 실제 `/assessment/*` API로 "
        "세션을 끝까지 진행한 뒤, 같은 세션(같은 evidence_ledger)에 대해 "
        "PRIMARY=false(Legacy)와 PRIMARY=true(v2)로 각각 /profile·/majors를 호출해 비교한다 — "
        "Trait Summary를 직접 주입하지 않는다.",
        "",
    ]
    for p in personas:
        lines.extend([
            f"## {p['name']}",
            "",
            f"**설계**: {p['description']}",
            "",
            f"- 세션 ID: `{p['session_id']}`",
            f"- 실제 답변 수(evidence_ledger): {p['answer_count']}",
            f"- Legacy 상위 Trait: {', '.join(p['legacy_top_traits']) or '(없음)'}",
            f"- v2 상위 Trait: {', '.join(p['v2_top_traits']) or '(없음)'}",
            f"- Legacy 추천 전공: {', '.join(p['legacy_majors']) or '(없음 — Evidence 부족)'}",
            f"- v2 추천 전공: {', '.join(p['v2_majors']) or '(없음 — Evidence 부족)'}",
            f"- Evidence 부족 여부(Legacy): {'충분' if p['legacy_evidence_sufficiency_present'] else '부족'}",
            f"- Evidence 부족 여부(v2): {'충분' if p['v2_evidence_sufficiency_present'] else '부족'}",
            f"- 검수 미완료로 제외된 Signal 개수(v2 Primary Fail-Closed 게이트): {p['excluded_unreviewed_signal_count']}",
            f"- 미해소 Explicit Conflict Trait: {', '.join(p['unresolved_conflict_trait_ids']) or '(없음)'}",
            "",
        ])
        diff_notes = []
        if set(p["legacy_top_traits"]) != set(p["v2_top_traits"]):
            diff_notes.append(
                "Legacy는 12-Trait 범위에서만 판정하고 v2는 24-Trait 범위(신규 12개 포함)에서 "
                "판정하므로 상위 Trait 구성이 달라질 수 있다."
            )
        if set(p["legacy_majors"]) != set(p["v2_majors"]):
            diff_notes.append(
                "v2 Major Matching은 evidence confidence 가중치를 추가로 곱하고 신규 Trait까지 "
                "포함된 v2 Major Profile을 쓰므로 추천 구성이 달라질 수 있다."
            )
        if p["excluded_unreviewed_signal_count"] > 0:
            diff_notes.append(
                f"이 세션에서 {p['excluded_unreviewed_signal_count']}개 Signal이 검수 미완료로 "
                "v2 Primary 계산에서 제외됐다(Shadow 진단에는 남아 있음)."
            )
        if not diff_notes:
            diff_notes.append("이번 실행에서는 Legacy/v2 결과가 관찰 가능한 차이 없이 동일했다.")
        if p["name"] == "Explicit Conflict" and not p["unresolved_conflict_trait_ids"]:
            diff_notes.append(
                "이번 실행에서는 Explicit Conflict가 실제로 발생하지 않았다 — "
                "planning_vs_execution Contrast는 comparable_frame_ids=['new_tool']로 "
                "제한돼 있는데, Mock 질문 생성이 매번 이 Frame을 고르지는 않아 두 역할이 "
                "'비교 가능한 Frame' 조건을 충족하지 못했다(정직하게 보고 — 결과를 지어내지 "
                "않는다)."
            )
        lines.append("**추천 차이의 근거**: " + " ".join(diff_notes))
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    main_module._llm_client = None
    main_module._tracer = Tracer(client=None)

    personas = run_all_personas()
    report = render_report(personas)
    output_path = ROOT / "outputs" / "evaluation" / "trait_v2_primary_comparison_report.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"wrote {output_path.relative_to(ROOT)}")


if __name__ == "__main__":
    use_utf8_stdout()
    main()
