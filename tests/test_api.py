"""API 계약 End-to-End 테스트 — B가 붙일 전체 흐름이 끊기지 않고 도는지 확인.

CLAUDE.md 필수 테스트 "고정 Persona End-to-End 완주"의 API 레벨 버전이다. 실제 계산 로직은
아직 Mock이지만, 최소한 "요청 → 응답 → 다음 요청" 흐름 자체가 끊기지 않아야 한다.
"""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


class SessionLifecycleTest(unittest.TestCase):
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
        r = client.get(f"/profile/{session_id}")
        highlights = r.json()["highlights"]
        self.assertTrue(5 <= len(highlights) <= 8)

    def test_openapi_schema_is_generated(self) -> None:
        r = client.get("/openapi.json")
        self.assertEqual(r.status_code, 200)
        spec = r.json()
        self.assertIn("/assessment/next-question", spec["paths"])
        self.assertIn("NextQuestionResponse", str(spec["components"]["schemas"].keys()))


if __name__ == "__main__":
    unittest.main()
