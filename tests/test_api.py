"""API 계약 End-to-End 테스트 — B가 붙일 전체 흐름이 끊기지 않고 도는지 확인.

CLAUDE.md 필수 테스트 "고정 Persona End-to-End 완주"의 API 레벨 버전이다. 실제 계산 로직은
아직 Mock이지만, 최소한 "요청 → 응답 → 다음 요청" 흐름 자체가 끊기지 않아야 한다.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api import main as main_module
from src.api.main import app

client = TestClient(app)


class SessionLifecycleTest(unittest.TestCase):
    def setUp(self) -> None:
        # main._llm_client는 개발자 로컬 .env(ENABLE_LLM_QUESTION_GENERATION)에 따라
        # 실제 LLM Client일 수도 있다. 이 테스트는 "API 배선이 안 끊기는지"만 확인하는
        # 계약 테스트라 실제 네트워크 호출 여부와 무관하게 항상 Mock 경로로 고정한다
        # (아니면 개발자 로컬 설정에 따라 unittest discover가 느려지거나 비용이 든다).
        patcher = patch.object(main_module, "_llm_client", None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_full_vertical_slice_flow_does_not_break(self) -> None:
        # 1. 세션 생성
        r = client.post("/assessment/session")
        self.assertEqual(r.status_code, 200)
        session_id = r.json()["session_id"]
        self.assertTrue(session_id.startswith("sess_"))

        # 2. 관심도 평가
        r = client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 5, "media": 5, "school_life": 4}},
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["accepted"])

        # 3. 선호 Context 선택
        r = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "media"]},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("contrast_context_id", r.json())

        # 4. Context 확정 (Vertical Slice 3개)
        r = client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game", "media", "school_life"]},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["final_context_ids"], ["game", "media", "school_life"])

        # 5. 질문 받기
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        self.assertEqual(r.status_code, 200)
        question_body = r.json()
        self.assertEqual(question_body["status"], "GENERATED")
        self.assertEqual(len(question_body["question"]["options"]), 5)

        # 6. 답변 제출
        first_option_id = question_body["question"]["options"][0]["option_id"]
        r = client.post(
            "/assessment/answer",
            json={
                "session_id": session_id,
                "question_id": question_body["question"]["question_id"],
                "selected_option_id": first_option_id,
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn(r.json()["next_action"], ["NEXT_QUESTION", "CONTEXT_COMPLETE"])

        # 7. Profile / Majors / Departments / Subjects / Subgraph 전부 끊기지 않고 응답하는지
        for path in [
            f"/profile/{session_id}",
            f"/majors/{session_id}",
            f"/subjects/{session_id}",
            f"/subgraph/{session_id}",
        ]:
            r = client.get(path)
            self.assertEqual(r.status_code, 200, f"{path} failed: {r.text}")

        r = client.get("/departments/media_communication")
        self.assertEqual(r.status_code, 200)

        # 7-1. 과목 문서 업로드 (실제 multipart 파일 전송)
        r = client.post(
            "/course/upload",
            data={"session_id": session_id},
            files={"file": ("curriculum.pdf", b"%PDF-1.4 fake content", "application/pdf")},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["parsed_candidates"])

        # 8. Session 복원
        r = client.get(f"/session/{session_id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["user_id"], "demo_user_01")

    def test_create_session_ignores_client_supplied_user_id(self) -> None:
        """2026-08-20 보안 리뷰 회귀 테스트: 클라이언트가 user_id를 임의로 지정해도
        서버가 무시하고 항상 demo_user_01로 고정해야 한다(Identity Spoofing 방지)."""

        r = client.post("/assessment/session", params={"user_id": "someone_else"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["user_id"], "demo_user_01")

    def test_course_upload_rejects_non_pdf_excel_file(self) -> None:
        """2026-08-21 리뷰 반영: /course/upload는 이제 실제 multipart 파일을 받고,
        허용 안 된 형식은 명시적으로 거부해야 한다."""

        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]

        r = client.post(
            "/course/upload",
            data={"session_id": session_id},
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["error_code"], "VALIDATION_ERROR")

    def test_course_upload_without_file_is_rejected(self) -> None:
        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        r = client.post("/course/upload", data={"session_id": session_id})
        self.assertEqual(r.status_code, 422)

    def test_unknown_session_returns_404_with_structured_error(self) -> None:
        r = client.get("/profile/sess_does_not_exist")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["detail"]["error_code"], "SESSION_NOT_FOUND")

    def test_career_profile_highlight_count_is_five_to_eight_even_via_api(self) -> None:
        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game", "media", "school_life"]},
        )
        # 2026-08-21 리뷰 반영: 답변이 아예 없으면 /profile은 이제 EVIDENCE_NOT_READY를
        # 반환한다(아래 별도 테스트) — highlights 5~8개 검증은 최소 1개 답변 이후로 옮긴다.
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        question = r.json()["question"]
        client.post(
            "/assessment/answer",
            json={
                "session_id": session_id,
                "question_id": question["question_id"],
                "selected_option_id": question["options"][0]["option_id"],
            },
        )
        r = client.get(f"/profile/{session_id}")
        self.assertEqual(r.status_code, 200)
        highlights = r.json()["highlights"]
        self.assertTrue(5 <= len(highlights) <= 8)

    def test_profile_without_any_answer_returns_evidence_not_ready(self) -> None:
        """2026-08-21 리뷰: 답변이 하나도 없는 세션에 /profile을 물으면 무관한 Mock
        Profile로 얼버무리지 않고 EVIDENCE_NOT_READY를 반환해야 한다."""

        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        r = client.get(f"/profile/{session_id}")
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["error_code"], "EVIDENCE_NOT_READY")

    def test_majors_without_any_answer_returns_empty_with_insufficient_message(self) -> None:
        """2026-08-21 리뷰: 답변이 없는 세션은 전공 추천 목록이 비어 있고
        insufficient_evidence_message가 채워져야 한다 — Mock 전공을 실제처럼 보여주지 않는다."""

        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        r = client.get(f"/majors/{session_id}")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["relevant_majors"], [])
        self.assertEqual(body["explore_together_majors"], [])
        self.assertIsNotNone(body["insufficient_evidence_message"])

    def test_profile_and_majors_reflect_this_sessions_actual_answers_without_llm(self) -> None:
        """2026-08-21 리뷰 핵심 요구사항: _llm_client가 없어도(이 테스트는 setUp에서 항상
        None으로 고정) 실제 Evidence 기반 결과가 나와야 하고, 고정 Mock 문구가 아니어야
        한다."""

        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game", "media", "school_life"]},
        )
        for _ in range(6):
            r = client.post("/assessment/next-question", params={"session_id": session_id})
            body = r.json()
            if body["status"] == "CONTEXT_EARLY_TERMINATED":
                if body["assessment_complete"]:
                    break
                continue
            q = body["question"]
            ar = client.post(
                "/assessment/answer",
                json={
                    "session_id": session_id,
                    "question_id": q["question_id"],
                    "selected_option_id": q["options"][0]["option_id"],
                },
            )
            if ar.json()["next_action"] == "ASSESSMENT_COMPLETE":
                break

        profile = client.get(f"/profile/{session_id}").json()
        # 예전 고정 Mock Profile의 제목·해시태그와 달라야 한다(다른 학생 결과가 아님).
        self.assertNotEqual(profile["title"], "구조를 읽고 사람의 반응까지 생각하는 탐색형 설계자")
        self.assertNotIn("#구조화", profile["hashtags"])
        supporting_trait_ids = {tid for h in profile["highlights"] for tid in h["supporting_trait_ids"]}
        self.assertTrue(supporting_trait_ids)  # 실제 Trait 근거가 있어야 함

        majors = client.get(f"/majors/{session_id}").json()
        # 예전 고정 Mock 전공 목록(media_communication이 항상 1등)과 결과가 달라도 되고
        # 같아도 되지만, 최소한 이 세션의 실제 Evidence로 계산된 결과여야 한다 — 여기서는
        # "에러 없이 응답이 오고 관련도 Label이 실제 enum 값 중 하나인지"만 구조적으로 확인.
        for item in majors["relevant_majors"] + majors["explore_together_majors"]:
            self.assertIn(
                item["relevance_label"], ["관련성 높음", "함께 탐색해볼 분야", "비교해볼 만한 분야"]
            )

    def test_majors_response_never_exposes_raw_score_or_float(self) -> None:
        """2026-08-21 리뷰: 내부 Matching Score(§16)가 API 응답 JSON 어디에도 소수점
        숫자로 새어나가면 안 된다 — Pydantic 스키마 레벨(MajorRelevance)뿐 아니라 실제
        JSON 응답까지 확인한다."""

        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game", "media", "school_life"]},
        )
        # 실제 파이프라인(Evidence·Trait Summary)을 몇 턴 돌려 trait_summaries를 채운다.
        # LLM은 setUp에서 None으로 고정했으니 질문 문구만 Mock이고 계산 로직은 진짜다.
        for _ in range(6):
            r = client.post("/assessment/next-question", params={"session_id": session_id})
            question = r.json()["question"]
            option_id = question["options"][0]["option_id"]
            client.post(
                "/assessment/answer",
                json={
                    "session_id": session_id,
                    "question_id": question["question_id"],
                    "selected_option_id": option_id,
                },
            )

        r = client.get(f"/majors/{session_id}")
        self.assertEqual(r.status_code, 200)

        def _assert_no_float(node, path: str) -> None:
            if isinstance(node, float):
                self.fail(f"{path}에 float 값이 노출됨: {node}")
            elif isinstance(node, dict):
                for key, value in node.items():
                    _assert_no_float(value, f"{path}.{key}")
            elif isinstance(node, list):
                for i, value in enumerate(node):
                    _assert_no_float(value, f"{path}[{i}]")

        _assert_no_float(r.json(), "majors_response")

    def test_openapi_schema_is_generated(self) -> None:
        r = client.get("/openapi.json")
        self.assertEqual(r.status_code, 200)
        spec = r.json()
        self.assertIn("/assessment/next-question", spec["paths"])
        self.assertIn("NextQuestionResponse", str(spec["components"]["schemas"].keys()))


if __name__ == "__main__":
    unittest.main()
