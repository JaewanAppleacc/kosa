"""Endpoint별 정상·오류·빈 결과 Mock JSON을 outputs/mock_api/에 생성한다.

Schema가 바뀌면 이 스크립트를 다시 돌려서 Mock JSON을 갱신한다(A 지시서 §3: "Schema 변경이
필요하면 B와 C에게 변경 내용과 새로운 Mock JSON을 동시에 제공한다").

실행: ./.venv/bin/python scripts/generate_mock_json.py
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.main import app

OUT_DIR = Path(__file__).resolve().parent.parent / "outputs" / "mock_api"


def _write(name: str, payload: dict) -> None:
    path = OUT_DIR / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {path.relative_to(OUT_DIR.parent.parent)}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    client = TestClient(app)

    # --- 정상 흐름 ---
    r = client.post("/assessment/session")
    _write("session_create_normal", r.json())
    session_id = r.json()["session_id"]

    r = client.post(
        "/assessment/interest-rating",
        json={"session_id": session_id, "ratings": {"game": 5, "media": 5, "school_life": 4}},
    )
    _write("interest_rating_normal", r.json())

    r = client.post(
        "/assessment/context-select",
        json={"session_id": session_id, "selected_preferred_context_ids": ["game", "media"]},
    )
    _write("context_select_normal", r.json())

    r = client.post(
        "/assessment/context-confirm",
        json={"session_id": session_id, "final_context_ids": ["game", "media", "school_life"]},
    )
    _write("context_confirm_normal", r.json())

    r = client.post("/assessment/next-question", params={"session_id": session_id})
    _write("next_question_normal", r.json())
    question = r.json()["question"]

    r = client.post(
        "/assessment/answer",
        json={
            "session_id": session_id,
            "question_id": question["question_id"],
            "selected_option_id": question["options"][0]["option_id"],
        },
    )
    _write("answer_normal", r.json())

    _write("profile_normal", client.get(f"/profile/{session_id}").json())
    _write("majors_normal", client.get(f"/majors/{session_id}").json())
    _write("departments_normal", client.get("/departments/media_communication").json())
    _write("subjects_normal", client.get(f"/subjects/{session_id}").json())
    _write("subgraph_normal", client.get(f"/subgraph/{session_id}").json())
    _write("session_restore_normal", client.get(f"/session/{session_id}").json())

    # --- 오류: 존재하지 않는 session_id ---
    r = client.get("/profile/sess_does_not_exist")
    _write("profile_error_session_not_found", r.json())

    # --- 빈 결과: 매칭되는 학과가 없는 major_id ---
    r = client.get("/departments/no_such_major")
    _write("departments_empty", {"major_id": "no_such_major", "departments": []})


if __name__ == "__main__":
    main()
