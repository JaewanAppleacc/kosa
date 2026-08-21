"""Endpoint별 정상·오류·빈 결과 Mock JSON을 outputs/mock_api/에 생성한다.

Schema가 바뀌면 이 스크립트를 다시 돌려서 Mock JSON을 갱신한다(A 지시서 §3: "Schema 변경이
필요하면 B와 C에게 변경 내용과 새로운 Mock JSON을 동시에 제공한다").

실행: PYTHONPATH=. ./.venv/bin/python scripts/generate_mock_json.py
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

    # 프론트엔드가 실제 API와 같은 계약을 기준으로 개발할 수 있도록
    # Mock 응답과 함께 현재 FastAPI 앱의 OpenAPI 명세도 항상 갱신한다.
    _write("openapi", app.openapi())

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

    # profile_normal·majors_normal은 답변 1개만으로는 Evidence가 거의 없어 항상 빈
    # 결과가 나온다(§16 minimum_usable_traits 미달) — B가 "실제로 다 채워진 화면"을
    # 참고할 수 있도록, 세션을 끝까지(3개 Context) 완주시킨 뒤에 이 두 Mock을 뽑는다.
    # LLM Key 없이도(ENABLE_LLM_QUESTION_GENERATION 미설정) Mock 질문 경로로 Evidence
    # 계산 자체는 실제로 이뤄지므로 B 환경에서 그대로 재현 가능하다.
    #
    # 매번 같은 선택지(항상 options[0])만 고르면 Evidence가 2~3개 Trait에만 몰려서
    # §16 minimum_traits_per_vector_group(그룹당 최소 2개)를 못 채우는 그룹이 많아지고
    # majors_normal도 결국 insufficient로 끝난다 — 여러 선택지를 골고루 골라야
    # "실제로 순위가 매겨진" 예시가 나온다.
    for turn in range(30):
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        body = r.json()
        if body["status"] == "CONTEXT_EARLY_TERMINATED":
            if body["assessment_complete"]:
                break
            continue
        q = body["question"]
        option = q["options"][(turn * 2) % 5]
        ar = client.post(
            "/assessment/answer",
            json={
                "session_id": session_id,
                "question_id": q["question_id"],
                "selected_option_id": option["option_id"],
            },
        )
        if ar.json()["next_action"] == "ASSESSMENT_COMPLETE":
            break

    _write("profile_normal", client.get(f"/profile/{session_id}").json())
    _write("majors_normal", client.get(f"/majors/{session_id}").json())
    _write("departments_normal", client.get("/departments/media_communication").json())
    _write("subjects_normal", client.get(f"/subjects/{session_id}").json())

    r = client.post(
        "/course/upload",
        data={"session_id": session_id},
        files={"file": ("curriculum.pdf", b"%PDF-1.4 fake content", "application/pdf")},
    )
    _write("course_upload_normal", r.json())

    r = client.post(
        "/course/upload",
        data={"session_id": session_id},
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    _write("course_upload_error_invalid_file_type", r.json()["detail"])
    _write("subgraph_normal", client.get(f"/subgraph/{session_id}").json())
    _write("session_restore_normal", client.get(f"/session/{session_id}").json())

    # --- 오류: 존재하지 않는 session_id ---
    r = client.get("/profile/sess_does_not_exist")
    _write("profile_error_session_not_found", r.json())

    # --- 빈 결과: 매칭되는 학과가 없는 major_id ---
    r = client.get("/departments/no_such_major")
    _write("departments_empty", {"major_id": "no_such_major", "departments": []})

    # --- B UI가 미리 대비해야 하는 그 외 상태들 ---
    # 지금 서버는 항상 GENERATED만 반환하지만(§11 Fallback 로직 미구현), B는 이 형태를
    # 미리 알아야 화면을 짤 수 있다. 실제 HTTP 응답이 아니라 Schema로 직접 만든
    # 손으로 채운 예시다 — 파일명에 이미 "hand-crafted"라는 걸 남겨 혼동을 막는다.
    _write_hand_crafted_states(session_id, question)


def _write_hand_crafted_states(session_id: str, sample_question: dict) -> None:
    from src.schemas.api import APIError, APIErrorCode, NextQuestionResponse, QuestionDeliveryStatus
    from src.schemas.profile import CareerProfile, CareerProfileHighlight

    _write(
        "next_question_regenerating__hand_crafted",
        NextQuestionResponse(
            session_id=session_id,
            status=QuestionDeliveryStatus.REGENERATING,
            question=None,
            current_context_id="media",
            questions_asked_in_current_context=1,
        ).model_dump(mode="json"),
    )
    _write(
        "next_question_cache_used__hand_crafted",
        NextQuestionResponse(
            session_id=session_id,
            status=QuestionDeliveryStatus.CACHE_USED,
            question=sample_question,
            current_context_id="media",
            questions_asked_in_current_context=2,
        ).model_dump(mode="json"),
    )
    _write(
        "next_question_backup_used__hand_crafted",
        NextQuestionResponse(
            session_id=session_id,
            status=QuestionDeliveryStatus.BACKUP_USED,
            question=sample_question,
            current_context_id="media",
            questions_asked_in_current_context=3,
        ).model_dump(mode="json"),
    )
    _write(
        "next_question_context_early_terminated__hand_crafted",
        NextQuestionResponse(
            session_id=session_id,
            status=QuestionDeliveryStatus.CONTEXT_EARLY_TERMINATED,
            question=None,
            current_context_id="media",
            questions_asked_in_current_context=2,
            assessment_complete=False,
        ).model_dump(mode="json"),
    )
    _write(
        "error_llm_unavailable__hand_crafted",
        APIError(
            error_code=APIErrorCode.LLM_UNAVAILABLE,
            message="LLM 호출이 실패했습니다. Cache 또는 Backup으로 전환합니다.",
        ).model_dump(mode="json"),
    )
    _write(
        "error_validation__hand_crafted",
        APIError(
            error_code=APIErrorCode.VALIDATION_ERROR,
            message="selected_option_id가 현재 질문의 선택지 목록에 없습니다.",
        ).model_dump(mode="json"),
    )
    _write(
        # 2026-08-21 리뷰: /profile은 답변이 하나도 없으면 이 오류를 반환한다(422).
        # 실제 HTTP 응답이지만 "hand_crafted" 접미사를 붙여 다른 정상 흐름 예시와 구분한다.
        "error_evidence_not_ready__hand_crafted",
        APIError(
            error_code=APIErrorCode.EVIDENCE_NOT_READY,
            message="아직 답변이 없어 Profile을 생성할 Evidence가 없습니다. 먼저 "
            "/assessment/next-question과 /assessment/answer로 최소 1개 이상 답변한 뒤 "
            "다시 호출하세요.",
        ).model_dump(mode="json"),
    )
    _write(
        "profile_partial__hand_crafted",
        CareerProfile(
            session_id=session_id,
            user_id="demo_user_01",
            title="아직 답변이 많지 않아 전체적인 경향은 더 확인이 필요해요",
            highlights=[
                CareerProfileHighlight(
                    text="지금까지 답변에서는 원인을 분석하는 경향이 반복 관찰돼요.",
                    supporting_trait_ids=["causal_analysis"],
                ),
                CareerProfileHighlight(
                    text="나머지 특성은 아직 답변이 부족해 결과에 반영하지 못했어요.",
                    supporting_trait_ids=[],
                ),
                CareerProfileHighlight(
                    text="이번 답변에서는 협업 방식이 충분히 확인되지 않았어요.",
                    supporting_trait_ids=["collaboration_preference"],
                ),
                CareerProfileHighlight(
                    text="창의적 표현 관련 답변은 아직 나오지 않았어요.",
                    supporting_trait_ids=[],
                ),
                CareerProfileHighlight(
                    text="검사를 더 진행하면 더 정확한 특징이 나타날 수 있어요.",
                    supporting_trait_ids=[],
                ),
            ],
            hashtags=["#탐색중"],
            detailed_evidence_by_dimension={},
            generated_at="2026-08-21T00:00:00",
        ).model_dump(mode="json"),
    )


if __name__ == "__main__":
    main()
