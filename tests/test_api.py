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

        # 7. Profile / Majors / Departments / Subgraph 전부 끊기지 않고 응답하는지
        for path in [
            f"/profile/{session_id}",
            f"/majors/{session_id}",
            f"/subgraph/{session_id}",
        ]:
            r = client.get(path)
            self.assertEqual(r.status_code, 200, f"{path} failed: {r.text}")

        r = client.get("/departments/media_communication")
        self.assertEqual(r.status_code, 200)

        # 7-0. 2026-08-24 14차 리뷰: /subjects/{session_id}는 이제 selected_major_id
        # Query Parameter가 필수다 — 없으면 FastAPI가 이 핸들러에 도달하기 전에 422를
        # 낸다("끊기지 않고 응답"의 의미가 200이 아니라 "정직한 422"로 바뀐 지점).
        r = client.get(f"/subjects/{session_id}")
        self.assertEqual(r.status_code, 422)

        # 7-1. 2026-08-26 16차 리뷰: 과목 문서 업로드도 이제 selected_major_id를 같은
        # 규칙으로 검증한다 — 이 시점의 세션은 답변이 1개뿐이라 Evidence가 부족해서
        # /subjects와 마찬가지로 정직한 422가 나오는 게 맞다(끊기지 않고 응답한다는
        # 뜻이 200이 아니라 "정직한 422"로 바뀐 지점, 위 7-0과 같은 이유).
        r = client.post(
            "/course/upload",
            data={"session_id": session_id, "selected_major_id": "media_communication"},
            files={"file": ("curriculum.pdf", b"%PDF-1.4 fake content", "application/pdf")},
        )
        self.assertEqual(r.status_code, 422, r.text)
        self.assertIn(
            r.json()["detail"]["error_code"], ("EVIDENCE_NOT_READY", "MAJOR_NOT_SELECTABLE")
        )

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
            data={"session_id": session_id, "selected_major_id": "media_communication"},
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["error_code"], "VALIDATION_ERROR")

    def test_course_upload_without_file_is_rejected(self) -> None:
        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        r = client.post(
            "/course/upload",
            data={"session_id": session_id, "selected_major_id": "media_communication"},
        )
        self.assertEqual(r.status_code, 422)

    def test_course_upload_over_10mb_is_rejected_without_parsing(self) -> None:
        """2026-08-27 17차 리뷰 §3: 실제 HTTP 경로에서도 10MB 초과 파일이 chunk 읽기
        단계에서 거부되는지 확인한다(파일 형식과 무관하게 크기부터 걸린다)."""

        from src.services.course_document_parsing_service import MAX_UPLOAD_SIZE_BYTES

        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]

        oversized = b"0" * (MAX_UPLOAD_SIZE_BYTES + 1)
        r = client.post(
            "/course/upload",
            data={"session_id": session_id, "selected_major_id": "media_communication"},
            files={
                "file": (
                    "big.xlsx", oversized,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["error_code"], "VALIDATION_ERROR")
        detail_text = str(r.json()["detail"])
        self.assertNotIn("/tmp/", detail_text)
        self.assertNotIn("Traceback", detail_text)

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

    def test_majors_response_includes_canonical_description_for_every_major(self) -> None:
        """A3 지시서(2026-08-24) §10 — `/majors/{session_id}`의 relevant_majors·
        explore_together_majors 양쪽 모두 description이 채워지고, 그 값이
        canonical_majors.jsonl 정본과 정확히 일치해야 한다(Runtime이 즉흥 생성하지
        않는다는 증거)."""

        from src.data.majors.canonical_major_descriptions import CANONICAL_MAJOR_DESCRIPTIONS_BY_ID

        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game", "media", "school_life"]},
        )
        # 3개 Context 전부(Seed + Adaptive Tail 4~6개씩)를 완주해야 "관련도 계산 가능"
        # 기준(MINIMUM_USABLE_TRAITS/MINIMUM_USABLE_VECTOR_GROUPS)을 채운다 — 6턴으로는
        # 부족하다(다른 majors 테스트들이 6턴만 쓰는 건 애초에 빈 목록도 허용하기 때문).
        for _ in range(30):
            r = client.post("/assessment/next-question", params={"session_id": session_id})
            body = r.json()
            if body["status"] == "CONTEXT_EARLY_TERMINATED":
                if body["assessment_complete"]:
                    break
                continue
            question = body["question"]
            option_id = question["options"][0]["option_id"]
            ar = client.post(
                "/assessment/answer",
                json={"session_id": session_id, "question_id": question["question_id"], "selected_option_id": option_id},
            )
            if ar.json()["next_action"] == "ASSESSMENT_COMPLETE":
                break

        r = client.get(f"/majors/{session_id}")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        all_items = body["relevant_majors"] + body["explore_together_majors"]
        self.assertTrue(all_items, "이 테스트는 실제로 추천 결과가 나온 상태를 검증해야 한다")
        for item in all_items:
            self.assertIn("description", item)
            self.assertTrue(item["description"].strip())
            self.assertEqual(item["description"], CANONICAL_MAJOR_DESCRIPTIONS_BY_ID[item["major_id"]])
            # keywords를 이어붙인 것이 아니라 실제 문장이어야 한다(쉼표로 나열된 형태 금지).
            self.assertNotRegex(item["description"], r"^[가-힣A-Za-z0-9]+(,\s*[가-힣A-Za-z0-9]+){2,}$")

    def test_openapi_schema_is_generated(self) -> None:
        r = client.get("/openapi.json")
        self.assertEqual(r.status_code, 200)
        spec = r.json()
        self.assertIn("/assessment/next-question", spec["paths"])
        self.assertIn("NextQuestionResponse", str(spec["components"]["schemas"].keys()))


class ContextCatalogEndpointTest(unittest.TestCase):
    """2026-08-30 20차 리뷰: GET /contexts — B가 Context 목록·선택 정책을 프론트엔드
    상수로 복제하지 않도록 서버가 검증하는 것과 동일한 값을 내려준다."""

    def test_returns_200(self) -> None:
        r = client.get("/contexts")
        self.assertEqual(r.status_code, 200)

    def test_exactly_15_contexts(self) -> None:
        r = client.get("/contexts")
        self.assertEqual(len(r.json()["contexts"]), 15)

    def test_no_duplicate_context_ids(self) -> None:
        r = client.get("/contexts")
        ids = [c["context_id"] for c in r.json()["contexts"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_order_matches_context_definitions(self) -> None:
        from src.data.contexts.context_definitions import CONTEXT_DEFINITIONS

        r = client.get("/contexts")
        ids = [c["context_id"] for c in r.json()["contexts"]]
        self.assertEqual(ids, [c.context_id for c in CONTEXT_DEFINITIONS])

    def test_fields_match_context_definitions(self) -> None:
        from src.data.contexts.context_definitions import CONTEXT_DEFINITIONS

        r = client.get("/contexts")
        by_id = {c["context_id"]: c for c in r.json()["contexts"]}
        for definition in CONTEXT_DEFINITIONS:
            item = by_id[definition.context_id]
            self.assertEqual(item["label"], definition.label)
            self.assertEqual(item["description"], definition.description)
            self.assertEqual(item["example_activities"], definition.example_activities)
            self.assertEqual(item["interest_rating_prompt"], definition.interest_rating_prompt)
            self.assertEqual(item["is_core"], definition.is_core)

    def test_exactly_three_assessment_supported(self) -> None:
        r = client.get("/contexts")
        supported = [c for c in r.json()["contexts"] if c["assessment_supported"]]
        self.assertEqual(len(supported), 3)

    def test_supported_contexts_are_exactly_game_media_school_life(self) -> None:
        r = client.get("/contexts")
        supported_ids = {c["context_id"] for c in r.json()["contexts"] if c["assessment_supported"]}
        self.assertEqual(supported_ids, {"game", "media", "school_life"})

    def test_selection_policy_values(self) -> None:
        r = client.get("/contexts")
        self.assertEqual(
            r.json()["selection_policy"],
            {
                "preferred_context_min_count": 2,
                "preferred_context_max_count": 2,
                "contrast_context_count": 1,
                "final_context_min_count": 2,
                "final_context_max_count": 3,
                "coverage_replacement_enabled": False,
            },
        )

    def test_no_internal_context_vector_or_coverage_score_exposed(self) -> None:
        r = client.get("/contexts")
        body_text = r.text
        for forbidden_field in (
            "individual_vs_team", "digital_vs_physical", "people_vs_system",
            "appreciation_vs_creation", "expression_vs_analysis", "exploration_vs_goal",
        ):
            self.assertNotIn(forbidden_field, body_text)


class ContextSelectionValidationTest(unittest.TestCase):
    """2026-08-22 6항목: Contrast Context State 저장 + Context 선택·확정 입력 검증."""

    def setUp(self) -> None:
        patcher = patch.object(main_module, "_llm_client", None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _new_session(self) -> str:
        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 5, "media": 5, "school_life": 4}},
        )
        return session_id

    def test_contrast_context_id_is_persisted_and_survives_reload(self) -> None:
        session_id = self._new_session()
        r = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "media"]},
        )
        self.assertEqual(r.status_code, 200)
        proposed = r.json()["contrast_context_id"]

        state = main_module._store.load(session_id)
        self.assertEqual(state.contrast_context_id, proposed)

        # "복원" — 저장소에서 다시 읽어도(같은 InMemory 저장소지만 별도 조회) 같은 값이다.
        reloaded = main_module._store.load(session_id)
        self.assertEqual(reloaded.contrast_context_id, proposed)

    def test_empty_preferred_contexts_rejected(self) -> None:
        session_id = self._new_session()
        r = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": []},
        )
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["error_code"], "VALIDATION_ERROR")

    def test_duplicate_preferred_contexts_rejected(self) -> None:
        session_id = self._new_session()
        r = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "game"]},
        )
        self.assertEqual(r.status_code, 422)

    def test_unknown_preferred_context_rejected(self) -> None:
        session_id = self._new_session()
        r = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "not_a_real_context"]},
        )
        self.assertEqual(r.status_code, 422)

    def test_empty_final_contexts_rejected(self) -> None:
        session_id = self._new_session()
        r = client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": []},
        )
        self.assertEqual(r.status_code, 422)

    def test_duplicate_final_contexts_rejected(self) -> None:
        session_id = self._new_session()
        r = client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game", "game", "media"]},
        )
        self.assertEqual(r.status_code, 422)

    def test_final_context_not_yet_supported_by_vertical_slice_rejected(self) -> None:
        """알려진(15개 중 하나) Context라도, Vertical Slice가 실제 질문 흐름을 아직
        지원하지 않는 Context면 나중에 next-question에서 조용히 실패하지 않도록 여기서
        먼저 막는다."""

        session_id = self._new_session()
        r = client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game", "media", "business"]},
        )
        self.assertEqual(r.status_code, 422)

    def test_user_can_replace_with_a_context_never_originally_selected(self) -> None:
        """§5-1: "학생은 기존 선택 유지, 추천 수용, 다른 Context 선택 중 하나를 고른다" —
        확정 단계가 "선호 4개 ∪ 제안된 Contrast"로만 강제되지 않는다. 처음에 game을
        선호로 골랐어도, 최종 확정에서는 game을 아예 빼고 다른 조합으로 바꿀 수 있다."""

        session_id = self._new_session()
        select_response = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "media"]},
        )
        self.assertEqual(select_response.status_code, 200)

        # 처음에 선호로 고르지 않았던 조합(game 제외, school_life 포함)으로 최종 확정 —
        # "제안받은 것만 가능"으로 강제하지 않으므로 여전히 허용돼야 한다.
        r = client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["media", "school_life"]},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["final_context_ids"], ["media", "school_life"])

    def test_interest_rating_one_candidate_is_not_silently_auto_finalized(self) -> None:
        """관심도 1점 후보가 제안되더라도(마지막 방어선 tier), 학생이 /assessment/
        context-confirm을 직접 호출하기 전까지는 최종 Context에 절대 포함되지 않는다
        (HITL 확인을 거쳐야만 최종 반영됨)."""

        session_id = self._new_session()
        # game/media만 5점, 나머지는 전부 1점(관심도 낮음) → 마지막 방어선 tier로 제안됨.
        client.post(
            "/assessment/interest-rating",
            json={
                "session_id": session_id,
                "ratings": {"game": 5, "media": 5, "school_life": 1, "business": 1, "making": 1},
            },
        )
        r = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "media"]},
        )
        self.assertEqual(r.status_code, 200)
        state = main_module._store.load(session_id)
        # 제안은 저장됐지만(state.contrast_context_id) 최종 Context에는 아직 전혀 반영 안 됨.
        self.assertIsNotNone(state.contrast_context_id)
        self.assertEqual(state.final_contexts, [])

    # --- 2026-08-30 20차 리뷰: 선호 Context "정확히 2개", 지원 Context 제한 ---

    def test_one_preferred_context_rejected(self) -> None:
        session_id = self._new_session()
        r = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game"]},
        )
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["error_code"], "VALIDATION_ERROR")

    def test_three_preferred_contexts_rejected(self) -> None:
        session_id = self._new_session()
        r = client.post(
            "/assessment/context-select",
            json={
                "session_id": session_id,
                "selected_preferred_context_ids": ["game", "media", "school_life"],
            },
        )
        self.assertEqual(r.status_code, 422)

    def test_registered_but_unsupported_preferred_context_rejected(self) -> None:
        """art_design은 등록된 15개 중 하나지만 실제 질문 흐름을 지원하지 않는다 —
        "미등록"과는 다른 사유로 거부돼야 한다(둘 다 422 VALIDATION_ERROR지만, 이 값이
        나중에 next-question에서야 뒤늦게 실패하면 안 된다는 게 핵심)."""

        session_id = self._new_session()
        r = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "art_design"]},
        )
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["error_code"], "VALIDATION_ERROR")
        self.assertIn("art_design", r.json()["detail"]["message"])

    def test_preferred_context_without_interest_rating_rejected(self) -> None:
        """관심도 평가를 아예 안 한 Context는 선호 Context로 직접 제출할 수 없다."""

        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 5, "media": 3}},
        )
        r = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "school_life"]},
        )
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["error_code"], "VALIDATION_ERROR")
        self.assertIn("school_life", r.json()["detail"]["message"])

    def test_contrast_candidate_is_always_a_supported_context(self) -> None:
        """선호 2개(지원 3개 중 2개)를 고르면, 남는 지원 Context 1개가 결정론적으로
        Contrast 후보가 된다 — 미지원 12개 Context 중 하나가 나오면 안 된다."""

        cases = [
            (["game", "media"], "school_life"),
            (["game", "school_life"], "media"),
            (["media", "school_life"], "game"),
        ]
        for preferred, expected_contrast in cases:
            with self.subTest(preferred=preferred):
                r = client.post("/assessment/session")
                session_id = r.json()["session_id"]
                client.post(
                    "/assessment/interest-rating",
                    json={
                        "session_id": session_id,
                        "ratings": {"game": 5, "media": 5, "school_life": 5, "business": 3, "making": 3},
                    },
                )
                r = client.post(
                    "/assessment/context-select",
                    json={"session_id": session_id, "selected_preferred_context_ids": preferred},
                )
                self.assertEqual(r.status_code, 200, r.text)
                self.assertEqual(r.json()["contrast_context_id"], expected_contrast)

    def test_contrast_candidate_never_duplicates_a_preferred_context(self) -> None:
        session_id = self._new_session()
        r = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "media"]},
        )
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(r.json()["contrast_context_id"], ["game", "media"])

    def test_contrast_context_id_saved_in_state(self) -> None:
        session_id = self._new_session()
        r = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "media"]},
        )
        self.assertEqual(r.status_code, 200)
        state = main_module._store.load(session_id)
        self.assertEqual(state.contrast_context_id, r.json()["contrast_context_id"])

    # --- 2026-08-30 20차 리뷰: 최종 Context 2~3개(정확히 3개 강제 아님) ---

    def test_final_context_two_supported_accepted(self) -> None:
        session_id = self._new_session()
        r = client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game", "media"]},
        )
        self.assertEqual(r.status_code, 200, r.text)

    def test_final_context_three_supported_accepted(self) -> None:
        session_id = self._new_session()
        r = client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game", "media", "school_life"]},
        )
        self.assertEqual(r.status_code, 200, r.text)

    def test_final_context_one_rejected(self) -> None:
        session_id = self._new_session()
        r = client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game"]},
        )
        self.assertEqual(r.status_code, 422)

    def test_final_context_with_unsupported_rejected(self) -> None:
        session_id = self._new_session()
        r = client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game", "media", "business"]},
        )
        self.assertEqual(r.status_code, 422)

    def test_final_context_duplicate_rejected(self) -> None:
        session_id = self._new_session()
        r = client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game", "game"]},
        )
        self.assertEqual(r.status_code, 422)

    def test_final_context_can_replace_with_supported_context_never_selected(self) -> None:
        """§5-1: Contrast를 수용하지 않고, 처음 고르지 않았던 지원 Context로 교체 가능."""

        session_id = self._new_session()
        client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "media"]},
        )
        r = client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["media", "school_life"]},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["final_context_ids"], ["media", "school_life"])

    def test_final_context_does_not_force_accepting_contrast(self) -> None:
        """선호 2개만으로 확정할 수 있다 — Contrast Context 수용을 강제하지 않는다."""

        session_id = self._new_session()
        select_response = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "media"]},
        )
        contrast_id = select_response.json()["contrast_context_id"]
        r = client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game", "media"]},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertNotIn(contrast_id, r.json()["final_context_ids"])


class InterestRatingValidationTest(unittest.TestCase):
    """2026-08-22 3차 리뷰 항목 3: `/assessment/interest-rating` 입력 검증."""

    def setUp(self) -> None:
        patcher = patch.object(main_module, "_llm_client", None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _new_session(self) -> str:
        r = client.post("/assessment/session")
        return r.json()["session_id"]

    def test_scores_one_and_five_are_accepted(self) -> None:
        session_id = self._new_session()
        r = client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 1, "media": 5}},
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["accepted"])

    def test_out_of_range_integer_scores_rejected(self) -> None:
        """2026-08-22 4차 리뷰 항목 1: 0/6/-1은 타입은 맞지만(strict int) 범위(1~5) 밖 —
        이건 여전히 핸들러의 validate_interest_ratings()가 APIError로 거부한다."""

        session_id = self._new_session()
        for bad_score in (0, 6, -1):
            r = client.post(
                "/assessment/interest-rating",
                json={"session_id": session_id, "ratings": {"game": bad_score, "media": 4}},
            )
            self.assertEqual(r.status_code, 422, f"score={bad_score!r}이 거부되지 않았습니다.")
            self.assertEqual(r.json()["detail"]["error_code"], "VALIDATION_ERROR")

    def test_numeric_string_score_rejected(self) -> None:
        """2026-08-22 4차 리뷰 항목 1: "4"(문자열)는 예전엔 Pydantic이 조용히 int로
        변환해 받아줬다 — StrictInt 도입 후 거부돼야 하고, 응답 형식도 다른 검증 오류와
        동일한 APIError(VALIDATION_ERROR) 형태를 유지해야 한다(RequestValidationError
        핸들러로 정규화)."""

        session_id = self._new_session()
        r = client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": "4", "media": 4}},
        )
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["error_code"], "VALIDATION_ERROR")

    def test_non_numeric_string_score_rejected(self) -> None:
        session_id = self._new_session()
        r = client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": "high", "media": 4}},
        )
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["error_code"], "VALIDATION_ERROR")

    def test_float_score_rejected(self) -> None:
        """2026-08-22 4차 리뷰 항목 1: 4.0(실수)도 예전엔 int로 조용히 잘렸다 — StrictInt는
        실수를 거부한다."""

        session_id = self._new_session()
        r = client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 4.0, "media": 4}},
        )
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["error_code"], "VALIDATION_ERROR")

    def test_boolean_score_rejected(self) -> None:
        """2026-08-22 4차 리뷰 항목 1: 파이썬에서 bool은 int의 하위형이라(True==1) 예전
        dict[str, int]는 true/false를 1/0으로 조용히 받아들였다 — StrictInt는 bool을
        명시적으로 거부한다."""

        session_id = self._new_session()
        for bad_score in (True, False):
            r = client.post(
                "/assessment/interest-rating",
                json={"session_id": session_id, "ratings": {"game": bad_score, "media": 4}},
            )
            self.assertEqual(r.status_code, 422, f"score={bad_score!r}이 거부되지 않았습니다.")
            self.assertEqual(r.json()["detail"]["error_code"], "VALIDATION_ERROR")

    def test_unknown_context_id_rejected(self) -> None:
        session_id = self._new_session()
        r = client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 5, "not_a_real_context": 4}},
        )
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["error_code"], "VALIDATION_ERROR")

    def test_empty_ratings_rejected(self) -> None:
        session_id = self._new_session()
        r = client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {}},
        )
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["error_code"], "VALIDATION_ERROR")

    def test_valid_request_result_unchanged(self) -> None:
        """검증 추가 이전과 동일하게, 유효한 입력은 그대로 저장되고 정상 응답이 나와야 한다."""

        session_id = self._new_session()
        r = client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 5, "media": 5, "school_life": 4}},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"session_id": session_id, "accepted": True})
        state = main_module._store.load(session_id)
        self.assertEqual(state.interest_ratings, {"game": 5, "media": 5, "school_life": 4})


class DepartmentsEndpointTest(unittest.TestCase):
    """2026-08-22 7차: 학과 탐색 1단계 통합 — GET /departments/{major_id}가 더 이상
    mock_data.mock_departments()가 아니라 실제 MajorExplorationService·
    JsonlDepartmentRepository·data/master/departments.jsonl 경로를 탄다."""

    def test_returns_real_repository_departments_for_a_mapped_major(self) -> None:
        r = client.get("/departments/computer_science")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["major_id"], "computer_science")
        # data/master/departments.jsonl 실측: computer_science에 매핑된 학과 10개.
        self.assertEqual(len(body["departments"]), 10)
        for dept in body["departments"]:
            self.assertEqual(dept["canonical_major_id"], "computer_science")

    def test_response_contains_no_mock_department_id(self) -> None:
        r = client.get("/departments/media_communication")
        body_text = r.text
        self.assertNotIn("dept_mock", body_text)

    def test_response_contains_no_mock_university_name(self) -> None:
        r = client.get("/departments/media_communication")
        self.assertNotIn("예시대학교", r.text)

    def test_response_contains_no_mock_source_url(self) -> None:
        r = client.get("/departments/media_communication")
        self.assertNotIn("example.ac.kr", r.text)

    def test_unmapped_major_id_returns_200_with_empty_list(self) -> None:
        r = client.get("/departments/no_such_major_id_at_all")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"major_id": "no_such_major_id_at_all", "departments": []})

    def test_response_schema_matches_existing_departments_response_contract(self) -> None:
        r = client.get("/departments/computer_science")
        body = r.json()
        self.assertEqual(set(body.keys()), {"major_id", "departments"})
        dept = body["departments"][0]
        self.assertEqual(
            set(dept.keys()),
            {
                "department_id", "university_name", "campus", "region", "department_name",
                "college_name", "admission_unit", "department_status", "source_svy_year",
                "source_url", "canonical_major_id",
            },
        )

    def test_other_endpoints_in_the_same_session_are_unaffected(self) -> None:
        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        r = client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 5, "media": 5, "school_life": 4}},
        )
        self.assertEqual(r.status_code, 200)
        r = client.get(f"/majors/{session_id}")
        self.assertEqual(r.status_code, 200)
        r = client.get(f"/profile/{session_id}")
        self.assertIn(r.status_code, (200, 422))  # EVIDENCE_NOT_READY도 정상 계약이다.

        # 이 요청들 사이에 실제 학과 조회를 끼워 넣어도 나머지 흐름에 영향이 없어야 한다.
        r = client.get("/departments/computer_science")
        self.assertEqual(r.status_code, 200)

    def test_departments_endpoint_does_not_touch_llm_langsmith_or_embedding_clients(self) -> None:
        """이 Endpoint는 JsonlDepartmentRepository(순수 JSONL 읽기)만 거친다 — LLM·
        LangSmith·Embedding Client가 전부 비활성(None)이어도(로컬 .env에 실제 API Key가
        있더라도 테스트에서는 이 값들을 명시적으로 꺼서) 정상 동작해야 한다."""

        with patch.object(main_module, "_llm_client", None), patch.object(
            main_module, "_trace_client", None
        ), patch.object(main_module, "_tracer", main_module.Tracer(client=None)):
            r = client.get("/departments/computer_science")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(len(r.json()["departments"]), 10)


def _drive_to_industrial_engineering_upload(test_case: unittest.TestCase) -> tuple[str, list[str]]:
    """2026-08-28 19차 리뷰: `tests/test_post_offering_full_flow_e2e.py`(17차)가 이미
    검증해 둔, industrial_engineering으로 결정론적으로 수렴하는 관심도·Context·옵션 선택
    패턴을 그대로 재사용해 학교 편제표 업로드까지 끌고 간다 — Confirm 여부는 호출부가
    직접 결정한다(트레이스 메타데이터 시나리오마다 confirmed_subject_ids가 달라야 하므로
    이 함수에서 확정까지 하지 않는다). `(session_id, matched_ids)`를 반환한다."""

    from pathlib import Path

    fixture_path = (
        Path(__file__).resolve().parent.parent
        / "data" / "fixtures" / "course_offerings" / "demo_school_offerings.xlsx"
    )

    r = client.post("/assessment/session")
    session_id = r.json()["session_id"]
    client.post(
        "/assessment/interest-rating",
        json={
            "session_id": session_id,
            "ratings": {"game": 3, "media": 3, "school_life": 5, "business": 2, "making": 2},
        },
    )
    client.post(
        "/assessment/context-select",
        json={"session_id": session_id, "selected_preferred_context_ids": ["school_life", "game"]},
    )
    client.post(
        "/assessment/context-confirm",
        json={"session_id": session_id, "final_context_ids": ["school_life", "game", "media"]},
    )
    for _ in range(30):
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        body = r.json()
        if body["status"] == "CONTEXT_EARLY_TERMINATED":
            if body["assessment_complete"]:
                break
            continue
        question = body["question"]
        option = question["options"][0]
        ar = client.post(
            "/assessment/answer",
            json={
                "session_id": session_id,
                "question_id": question["question_id"],
                "selected_option_id": option["option_id"],
            },
        )
        if ar.json()["next_action"] == "ASSESSMENT_COMPLETE":
            break

    selected_major_id = "industrial_engineering"
    with open(fixture_path, "rb") as f:
        file_bytes = f.read()
    r = client.post(
        "/course/upload",
        data={"session_id": session_id, "selected_major_id": selected_major_id},
        files={
            "file": (
                "demo_school_offerings.xlsx", file_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    test_case.assertEqual(r.status_code, 200, r.text)
    matched_ids = sorted({c["matched_subject_id"] for c in r.json()["parsed_candidates"] if c["matched_subject_id"]})
    return session_id, matched_ids


def _drive_to_confirmed_industrial_engineering_subgraph(test_case: unittest.TestCase) -> tuple[str, dict]:
    """업로드에 이어 실제 confirmed_subject_ids로 확정까지 마치고 GET /subgraph가 전체
    Graph(과목 Node 포함)를 반환하는 지점까지 끌고 간다 — 여기서는 API 계약(§9)만
    확인하고, 근거 그래프의 세부 내용은 별도 `tests/test_subgraph_full_flow_e2e.py`가
    깊게 검증한다."""

    session_id, matched_ids = _drive_to_industrial_engineering_upload(test_case)
    r = client.post("/course/confirm", json={"session_id": session_id, "confirmed_subject_ids": matched_ids})
    test_case.assertEqual(r.status_code, 200, r.text)

    r = client.get(f"/subgraph/{session_id}")
    test_case.assertEqual(r.status_code, 200, r.text)
    return session_id, r.json()


class SubgraphEndpointTest(unittest.TestCase):
    """2026-08-28 19차 리뷰: GET /subgraph/{session_id}가 더 이상 mock_data.mock_subgraph()
    의 고정 5개 Node가 아니라 KnowledgeSubgraphService의 실제 계산 결과다(지시서 §9/§12
    "API 테스트")."""

    def setUp(self) -> None:
        # SessionLifecycleTest.setUp과 같은 이유: 로컬 .env가 실제 LLM/LangSmith 설정을
        # 갖고 있어도(ENABLE_LLM_QUESTION_GENERATION=true 등) 이 계약 테스트는 항상
        # Mock/Fallback 경로로 고정한다 — 실제 네트워크 호출로 멈추면 안 된다.
        for patch_target in (
            patch.object(main_module, "_llm_client", None),
            patch.object(main_module, "_tracer", main_module.Tracer(client=None)),
        ):
            patch_target.start()
            self.addCleanup(patch_target.stop)

    def test_unknown_session_returns_404(self) -> None:
        r = client.get("/subgraph/sess_does_not_exist_at_all")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["detail"]["error_code"], "SESSION_NOT_FOUND")

    def test_no_evidence_at_all_returns_evidence_not_ready(self) -> None:
        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        r = client.get(f"/subgraph/{session_id}")
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["error_code"], "EVIDENCE_NOT_READY")

    def test_some_evidence_but_no_confirmed_course_returns_partial_graph(self) -> None:
        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 5, "media": 5, "school_life": 4}},
        )
        client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "media"]},
        )
        client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game", "media", "school_life"]},
        )
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

        r = client.get(f"/subgraph/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        node_types = {n["node_type"] for n in body["nodes"]}
        self.assertIn("Student", node_types)
        self.assertNotIn("HighSchoolSubject", node_types)  # 아직 업로드·확정 전이다.

    def test_confirmed_course_profile_yields_full_graph_with_subject_nodes(self) -> None:
        _session_id, body = _drive_to_confirmed_industrial_engineering_subgraph(self)
        node_types = {n["node_type"] for n in body["nodes"]}
        self.assertEqual(
            node_types, {"Student", "Trait", "CanonicalMajor", "Department", "University", "HighSchoolSubject"}
        )

    def test_response_schema_matches_existing_contract(self) -> None:
        _session_id, body = _drive_to_confirmed_industrial_engineering_subgraph(self)
        self.assertEqual(set(body.keys()), {"session_id", "nodes", "edges"})
        for node in body["nodes"]:
            self.assertEqual(set(node.keys()), {"node_id", "node_type", "label"})
        for edge in body["edges"]:
            self.assertEqual(
                set(edge.keys()),
                {
                    "source_node_id", "target_node_id", "relation_type", "relevance_level",
                    "evidence_ids", "source_ids", "mapping_version", "created_at",
                },
            )

    def test_no_mock_strings_leak_into_response(self) -> None:
        _session_id, body = _drive_to_confirmed_industrial_engineering_subgraph(self)
        body_text = str(body)
        self.assertNotIn("예시대학교", body_text)
        self.assertNotIn("dept_mock", body_text)
        self.assertNotIn("교과(군)", body_text)
        self.assertNotIn("정체불명 과목ABC", body_text)

    def test_no_internal_float_score_is_exposed(self) -> None:
        _session_id, body = _drive_to_confirmed_industrial_engineering_subgraph(self)

        def _assert_no_float(node) -> None:
            if isinstance(node, float):
                self.fail(f"float 값이 노출됨: {node}")
            elif isinstance(node, dict):
                for value in node.values():
                    _assert_no_float(value)
            elif isinstance(node, list):
                for value in node:
                    _assert_no_float(value)

        _assert_no_float(body)

    def test_no_raw_student_answer_text_is_exposed(self) -> None:
        """session_id는 응답 최상위 필드(`session_id`)로 정상적으로 echo되는 계약이라
        제외하고, Node label·Edge 값 안에는 학생이 실제로 고른 선택지 원문이 그대로
        들어오면 안 된다는 것만 확인한다."""

        import re

        session_id, body = _drive_to_confirmed_industrial_engineering_subgraph(self)
        nodes_and_edges_text = str(body["nodes"]) + str(body["edges"])
        self.assertNotIn(session_id, nodes_and_edges_text)
        for node in body["nodes"]:
            self.assertNotIn(" ", node["node_id"])  # node_id는 답변 문장이 아니라 식별자다.
        # HAS_TRAIT의 evidence_ids는 항상 opaque한 "ev_<hex>" 식별자다 — 선택지 원문
        # 문장이 아니다(RELATED_TO는 Mapping 식별자라 형식이 다르므로 검사 대상이 아니다).
        for edge in body["edges"]:
            if edge["relation_type"] != "HAS_TRAIT":
                continue
            for evidence_id in edge["evidence_ids"]:
                self.assertRegex(evidence_id, r"^ev_[0-9a-f]{32}$")


class SubgraphTraceMetadataTest(unittest.TestCase):
    """2026-08-29 19차 후속 보완: `has_confirmed_course_profile`(CoursePlanningStore의
    실제 Confirm 상태)과 `has_subject_nodes`(실제 생성된 HighSchoolSubject Node 존재
    여부)가 서로 다른 사실을 정확히 반영하는지 확인한다 — 빈 `confirmed_subject_ids=[]`
    로도 CONFIRMED가 될 수 있어(§2), Node 개수만으로 Confirm 여부를 추론하면 틀린다."""

    def setUp(self) -> None:
        for patch_target in (
            patch.object(main_module, "_llm_client", None),
        ):
            patch_target.start()
            self.addCleanup(patch_target.stop)

    def test_confirmed_with_subject_nodes(self) -> None:
        session_id, matched_ids = _drive_to_industrial_engineering_upload(self)
        r = client.post(
            "/course/confirm", json={"session_id": session_id, "confirmed_subject_ids": matched_ids}
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(matched_ids, "이 Fixture는 최소 1개 이상 매칭 후보가 있어야 한다")

        with patch.object(main_module, "_tracer") as mock_tracer:
            r = client.get(f"/subgraph/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        attributes = mock_tracer.record_stage.call_args.kwargs["attributes"]
        self.assertIs(attributes["has_confirmed_course_profile"], True)
        self.assertIs(attributes["has_subject_nodes"], True)

    def test_confirmed_with_empty_subject_list_has_no_subject_nodes(self) -> None:
        """upload_status=='CONFIRMED'인데 confirmed_subject_ids=[]라 HighSchoolSubject
        Node가 0개인 경우 — has_confirmed_course_profile은 True, has_subject_nodes는
        False여야 한다(둘을 혼동하면 이 경우가 (False, False)로 잘못 나온다)."""

        session_id, _matched_ids = _drive_to_industrial_engineering_upload(self)
        r = client.post("/course/confirm", json={"session_id": session_id, "confirmed_subject_ids": []})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["course_profile"]["recommendations"], [])

        with patch.object(main_module, "_tracer") as mock_tracer:
            r = client.get(f"/subgraph/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        node_types = {n["node_type"] for n in r.json()["nodes"]}
        self.assertNotIn("HighSchoolSubject", node_types)
        attributes = mock_tracer.record_stage.call_args.kwargs["attributes"]
        self.assertIs(attributes["has_confirmed_course_profile"], True)
        self.assertIs(attributes["has_subject_nodes"], False)

    def test_not_yet_confirmed_has_neither(self) -> None:
        session_id, _matched_ids = _drive_to_industrial_engineering_upload(self)
        # /course/confirm을 아예 호출하지 않는다 — planning_state.upload_status는
        # PARSED 또는 CONFIRMATION_REQUIRED로 남아 있다.

        with patch.object(main_module, "_tracer") as mock_tracer:
            r = client.get(f"/subgraph/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        node_types = {n["node_type"] for n in r.json()["nodes"]}
        self.assertNotIn("HighSchoolSubject", node_types)
        attributes = mock_tracer.record_stage.call_args.kwargs["attributes"]
        self.assertIs(attributes["has_confirmed_course_profile"], False)
        self.assertIs(attributes["has_subject_nodes"], False)

    def test_no_upload_at_all_has_neither(self) -> None:
        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 5, "media": 5, "school_life": 4}},
        )
        client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "media"]},
        )
        client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game", "media", "school_life"]},
        )
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

        with patch.object(main_module, "_tracer") as mock_tracer:
            r = client.get(f"/subgraph/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        attributes = mock_tracer.record_stage.call_args.kwargs["attributes"]
        self.assertIs(attributes["has_confirmed_course_profile"], False)
        self.assertIs(attributes["has_subject_nodes"], False)

    def test_langsmith_failure_does_not_break_the_subgraph_response(self) -> None:
        """§24 fail-open을 /subgraph에서도 그대로 확인한다 — Trace 기록이 실패해도
        200 응답과 실제 계산 결과는 그대로 나와야 한다(has_confirmed_course_profile
        계산은 Store 조회일 뿐이라 Trace 실패와 무관하게 항상 먼저 끝난다)."""

        from src.tracing.protocols import TraceError
        from src.tracing.tracer import Tracer

        class _AlwaysFailingTraceClient:
            def record_run(self, *, trace_id, name, run_type, attributes) -> None:
                raise TraceError("모의 LangSmith 장애")

        session_id, matched_ids = _drive_to_industrial_engineering_upload(self)
        client.post("/course/confirm", json={"session_id": session_id, "confirmed_subject_ids": matched_ids})

        with patch.object(main_module, "_tracer", Tracer(client=_AlwaysFailingTraceClient())):
            r = client.get(f"/subgraph/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["nodes"])


class TracingFailOpenIntegrationTest(unittest.TestCase):
    """§24: "LangSmith 장애는 로컬 로그만 남기고 사용자 Session을 중단하지 않는다"를
    API 레벨에서 확인한다 — Trace 기록이 매번 실패해도 전체 흐름이 그대로 끝까지 돈다."""

    def setUp(self) -> None:
        from src.tracing.protocols import TraceError
        from src.tracing.tracer import Tracer

        class _AlwaysFailingTraceClient:
            def record_run(self, *, trace_id, name, run_type, attributes) -> None:
                raise TraceError("모의 LangSmith 장애 — 이 예외는 세션 밖으로 나가면 안 된다")

        llm_patcher = patch.object(main_module, "_llm_client", None)
        tracer_patcher = patch.object(main_module, "_tracer", Tracer(client=_AlwaysFailingTraceClient()))
        llm_patcher.start()
        tracer_patcher.start()
        self.addCleanup(llm_patcher.stop)
        self.addCleanup(tracer_patcher.stop)

    def test_flow_completes_despite_every_trace_call_failing(self) -> None:
        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]

        r = client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 5, "media": 5, "school_life": 4}},
        )
        self.assertEqual(r.status_code, 200)

        # Context Selector 계측 지점을 통과한다.
        r = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "media"]},
        )
        self.assertEqual(r.status_code, 200)

        r = client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game", "media", "school_life"]},
        )
        self.assertEqual(r.status_code, 200)

        # Question Generator 계측 지점을 통과한다(Mock 경로여도 Tracer는 호출됨).
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        self.assertEqual(r.status_code, 200)
        question_body = r.json()["question"]

        # Evidence Update·Stop/Continue·Target Planner 계측 지점을 통과한다.
        r = client.post(
            "/assessment/answer",
            json={
                "session_id": session_id,
                "question_id": question_body["question_id"],
                "selected_option_id": question_body["options"][0]["option_id"],
            },
        )
        self.assertEqual(r.status_code, 200)

        # Profile Summary Generator 계측 지점을 통과한다.
        r = client.get(f"/profile/{session_id}")
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()
