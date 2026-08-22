"""Endpoint별 정상·오류·빈 결과 Mock JSON을 outputs/mock_api/에 생성한다.

Schema가 바뀌면 이 스크립트를 다시 돌려서 Mock JSON을 갱신한다(A 지시서 §3: "Schema 변경이
필요하면 B와 C에게 변경 내용과 새로운 Mock JSON을 동시에 제공한다").

2026-08-22 리뷰 반영: 이 스크립트는 로컬 `.env`에 `ENABLE_LLM_QUESTION_GENERATION=true`·
`LANGSMITH_TRACING=true`가 켜져 있어도 항상 결정론적 Mock/Fallback 경로만 탄다 — 실제
LLM·LangSmith 네트워크 호출을 절대 하지 않는다(실행할 때마다 과금되거나, 실행마다 결과가
달라지는 문제를 막는다). `_llm_client`/`_tracer`를 강제로 비활성화하고, session_id·
생성 시각도 고정값으로 주입해서 재실행해도 의미 없는 Diff(session_id, generated_at)가
안 생기게 한다 — 실제 계산 결과가 바뀌었을 때만 git diff가 발생해야 리뷰하기 쉽다.

실행: PYTHONPATH=. ./.venv/bin/python scripts/generate_mock_json.py
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.agents.assessment.profile_generator as profile_generator_module
import src.api.main as main_module
import src.api.mock_data as mock_data_module
from src.api.main import app
from src.tracing.tracer import Tracer

OUT_DIR = Path(__file__).resolve().parent.parent / "outputs" / "mock_api"

# 실행마다 값이 바뀌지 않도록 고정한다 — 실제 API 응답 필드 이름·타입·계산 결과는 이
# 값과 무관하다(session_id 자체는 어떤 계산에도 입력으로 쓰이지 않는다).
_FIXED_SESSION_ID = "sess_00000000000000000000000000000000"
_FIXED_GENERATED_AT = datetime(2026, 8, 22, 0, 0, 0)


def _write(name: str, payload: dict) -> None:
    path = OUT_DIR / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {path.relative_to(OUT_DIR.parent.parent)}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with (
        # 로컬 .env 설정과 무관하게 강제로 끈다 — Mock 생성은 항상 Mock/Fallback 경로다.
        patch.object(main_module, "_llm_client", None),
        patch.object(main_module, "_tracer", Tracer(client=None)),
        patch.object(main_module, "generate_session_id", lambda: _FIXED_SESSION_ID),
        patch.object(profile_generator_module, "datetime") as mock_datetime,
        patch.object(mock_data_module, "datetime") as mock_data_datetime,
    ):
        mock_datetime.now.return_value = _FIXED_GENERATED_AT
        mock_data_datetime.now.return_value = _FIXED_GENERATED_AT
        client = TestClient(app)
        _run(client)


def _run(client: TestClient) -> None:
    # 프론트엔드가 실제 API와 같은 계약을 기준으로 개발할 수 있도록
    # Mock 응답과 함께 현재 FastAPI 앱의 OpenAPI 명세도 항상 갱신한다.
    _write("openapi", app.openapi())

    # --- 정상 흐름 ---
    r = client.post("/assessment/session")
    _write("session_create_normal", r.json())
    session_id = r.json()["session_id"]
    assert session_id == _FIXED_SESSION_ID  # 고정 주입이 실제로 먹혔는지 방어적 확인

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
    # _llm_client가 강제로 None이라 질문 생성은 항상 결정론적 Mock 경로를 타지만, Evidence·
    # Trait·Matching 계산 자체는 실제 로직이라 B 환경에서 그대로 재현 가능하다.
    #
    # 매번 같은 선택지(항상 options[0])만 고르면 Evidence가 2~3개 Trait에만 몰려서
    # §16 minimum_traits_per_vector_group(그룹당 최소 2개)를 못 채우는 그룹이 많아지고
    # majors_normal도 결국 insufficient로 끝난다 — 여러 선택지를 골고루 골라야
    # "실제로 순위가 매겨진" 예시가 나온다. (turn*2)%5는 난수가 아니라 turn의 결정론적
    # 함수라 재실행해도 항상 같은 순서로 선택지를 고른다.
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

    majors_response = client.get(f"/majors/{session_id}").json()
    _write("profile_normal", client.get(f"/profile/{session_id}").json())
    _write("majors_normal", majors_response)
    _write("departments_normal", client.get("/departments/media_communication").json())
    # 2026-08-24 14차 리뷰: selected_major_id는 이 세션이 실제로 추천받은 전공이어야
    # 한다(§5 검증 규칙) — majors_normal 응답의 1위 전공을 그대로 재사용한다.
    selected_major_id = majors_response["relevant_majors"][0]["major_id"]
    _write(
        "subjects_normal",
        client.get(f"/subjects/{session_id}", params={"selected_major_id": selected_major_id}).json(),
    )

    # 2026-08-26 16차 리뷰: 실제 Parser로 연결된 뒤로는 텍스트를 추출할 수 없는 가짜
    # PDF("%PDF-1.4 fake content")를 올리면 이제 성공(200)이 아니라 PARSE_FAILED(422)가
    # 정직한 결과다 — Mock 예시도 실제 시연 Fixture(demo_school_offerings.xlsx)를 올려서
    # 진짜 성공 사례를 보여준다.
    fixture_path = (
        Path(__file__).resolve().parent.parent
        / "data" / "fixtures" / "course_offerings" / "demo_school_offerings.xlsx"
    )
    with open(fixture_path, "rb") as f:
        fixture_bytes = f.read()
    r = client.post(
        "/course/upload",
        data={"session_id": session_id, "selected_major_id": selected_major_id},
        files={
            "file": (
                "demo_school_offerings.xlsx", fixture_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    _write("course_upload_normal", r.json())
    matched_subject_ids = sorted(
        {c["matched_subject_id"] for c in r.json()["parsed_candidates"] if c["matched_subject_id"]}
    )

    r = client.post(
        "/course/upload",
        data={"session_id": session_id, "selected_major_id": selected_major_id},
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    _write("course_upload_error_invalid_file_type", r.json()["detail"])

    # 2026-08-26 16차 리뷰: 확정 응답이 accepted=True만 반환하던 Mock에서 실제
    # POST_OFFERING CourseProfile을 함께 담는 형태로 바뀌었다 — B가 참고할 실제 예시.
    r = client.post(
        "/course/confirm",
        json={"session_id": session_id, "confirmed_subject_ids": matched_subject_ids},
    )
    _write("course_confirm_normal", r.json())
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
