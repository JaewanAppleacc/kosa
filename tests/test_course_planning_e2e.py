"""GET /subjects/{session_id}?selected_major_id=... 최소 E2E Fixture — 2026-08-24 14차 리뷰 §9.

실제 FastAPI TestClient로 세션을 만들고, 고정 Persona의 Trait Evidence를 세션 상태에
직접 채운 뒤(질문 20턴을 반복하는 대신 결정론적으로 구성 — tests/test_vertical_slice_
major_department_alignment.py의 FixedPersonaEndToEndTest와 같은 전략), 실제 HTTP
엔드포인트를 호출해 CoursePlanningService·SubjectMatchingEngine·JsonlSubjectRepository가
전부 연결돼 동작하는지 확인한다.

여기서 쓰는 Persona 3개(analytical/visual_user_facing/media)는 tests/test_matching_
engine.py::FixedPersonaVerticalSliceMatchingTest, tests/test_vertical_slice_major_
department_alignment.py::FixedPersonaEndToEndTest, eval/major_matching_persona_
diagnostics.py에서 이미 각 대표 전공을 1위(또는 관련성 높음)로 만든다고 검증된 조합을
그대로 재사용한다 — 이 테스트를 위해 새로 만든 조합이 아니다(매칭 결과를 원하는
순서로 만들려고 임의 조정하지 않는다는 원칙을 그대로 따른다).
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import src.api.main as main_module
from src.api.main import app
from src.repositories.subject_repository import load_subjects
from src.schemas.evidence import TraitEvidenceSummary

ROOT = Path(__file__).resolve().parents[1]
client = TestClient(app)

_ALL_SUBJECT_IDS = {s.subject_id for s in load_subjects()}


def _strong(trait_id: str) -> TraitEvidenceSummary:
    return TraitEvidenceSummary(
        trait_id=trait_id, support_count=3, opportunity_count=3, context_count=2, distinct_frame_count=2
    )


def _limited(trait_id: str) -> TraitEvidenceSummary:
    return TraitEvidenceSummary(
        trait_id=trait_id, support_count=2, opportunity_count=2, context_count=1, distinct_frame_count=1
    )


def _not_probed(trait_id: str) -> TraitEvidenceSummary:
    return TraitEvidenceSummary(trait_id=trait_id, support_count=0, opportunity_count=0)


# Persona 정의 — 근거는 파일 docstring 참고.
_ANALYTICAL_STRONG = {"causal_analysis", "pattern_finding", "information_comparison", "planning"}
_ANALYTICAL_LIMITED = {"visual_expression", "audience_response_prediction", "tool_utilization"}

_VISUAL_USER_FACING_STRONG = {"visual_expression", "audience_response_prediction", "tool_utilization"}

_MEDIA_STRONG = {
    "visual_expression", "audience_response_prediction", "collaboration_preference",
    "planning", "causal_analysis", "pattern_finding", "information_comparison",
}
_MEDIA_LIMITED = {"tool_utilization"}

# eval/major_matching_persona_diagnostics.py의 "tool_only" Persona와 동일 — Trait 1개만
# 강하게 관찰되면 세 대표 전공 모두 usable_trait_count 미달로 insufficient가 된다(§13
# 12차 리뷰 진단 리포트에서 확인됨). "이 세션은 어떤 전공도 실제로 추천받지 않았다"를
# 재현하는 데 쓴다.
_TOOL_ONLY_STRONG = {"tool_utilization"}


def _seed_session_with_persona(strong: set[str], limited: set[str]) -> str:
    """세션을 만들고, main_module._store에 직접 trait_summaries를 채운다 — 20턴 답변
    루프를 반복하지 않고 고정 Persona를 결정론적으로 구성하기 위함(질문 생성 자체는
    이번 라운드 범위가 아니다)."""

    r = client.post("/assessment/session")
    session_id = r.json()["session_id"]
    state = main_module._store.load(session_id)

    from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAITS

    trait_ids = [t.trait_id for t in VERTICAL_SLICE_TRAITS]
    summaries = {}
    for trait_id in trait_ids:
        if trait_id in strong:
            summaries[trait_id] = _strong(trait_id)
        elif trait_id in limited:
            summaries[trait_id] = _limited(trait_id)
        else:
            summaries[trait_id] = _not_probed(trait_id)
    state.trait_summaries = summaries
    main_module._store.save(state)
    return session_id


def _assert_no_float(node, path: str, test_case: unittest.TestCase) -> None:
    if isinstance(node, float):
        test_case.fail(f"{path}에 float 값이 노출됨: {node}")
    elif isinstance(node, dict):
        for key, value in node.items():
            _assert_no_float(value, f"{path}.{key}", test_case)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            _assert_no_float(value, f"{path}[{i}]", test_case)


class CoursePlanningThreePersonaPathTest(unittest.TestCase):
    """§9 최소 3개 경로: 분석형→industrial_engineering, 시각·사용자 관점형→hci_ux,
    미디어형→media_communication."""

    def _assert_valid_course_profile(self, session_id: str, major_id: str, major_label: str) -> dict:
        r = client.get(f"/subjects/{session_id}", params={"selected_major_id": major_id})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["session_id"], session_id)
        self.assertEqual(body["source"], "PRE_SURVEY")
        self.assertGreater(len(body["recommendations"]), 0, "관련 희망과목이 반환되지 않았다")

        subject_ids_returned = [item["subject_id"] for item in body["recommendations"]]
        # 다른 학생 Mock 과목(예전 mock_data.mock_course_profile()의 고정값)이 섞이지 않는다.
        self.assertNotIn("subj_mock0000000000000001", subject_ids_returned)
        for item in body["recommendations"]:
            self.assertIn(item["subject_id"], _ALL_SUBJECT_IDS, "subjects.jsonl에 없는 subject_id")
            self.assertIn(item["category"], ("core", "explore"))
            self.assertIsNone(item["is_actually_offered"], "PRE_SURVEY는 개설 여부가 아직 미확정이어야 한다")
            self.assertIn(major_label, item["reason"], "reason에 선택한 전공과의 연결 이유가 없다")

        _assert_no_float(body, "subjects_response", self)
        return body

    def test_analytical_persona_selecting_industrial_engineering(self) -> None:
        session_id = _seed_session_with_persona(_ANALYTICAL_STRONG, _ANALYTICAL_LIMITED)
        self._assert_valid_course_profile(session_id, "industrial_engineering", "산업공학")

    def test_visual_user_facing_persona_selecting_hci_ux(self) -> None:
        session_id = _seed_session_with_persona(_VISUAL_USER_FACING_STRONG, set())
        self._assert_valid_course_profile(session_id, "hci_ux", "HCI·UX")

    def test_media_persona_selecting_media_communication(self) -> None:
        session_id = _seed_session_with_persona(_MEDIA_STRONG, _MEDIA_LIMITED)
        self._assert_valid_course_profile(session_id, "media_communication", "미디어·커뮤니케이션")

    def test_same_input_yields_the_same_order(self) -> None:
        session_id = _seed_session_with_persona(_ANALYTICAL_STRONG, _ANALYTICAL_LIMITED)
        first = client.get(
            f"/subjects/{session_id}", params={"selected_major_id": "industrial_engineering"}
        ).json()
        second = client.get(
            f"/subjects/{session_id}", params={"selected_major_id": "industrial_engineering"}
        ).json()
        first_ids = [item["subject_id"] for item in first["recommendations"]]
        second_ids = [item["subject_id"] for item in second["recommendations"]]
        self.assertEqual(first_ids, second_ids)
        self.assertEqual(first, second)


class CoursePlanningValidationTest(unittest.TestCase):
    """§9 추가 검증: Evidence 부족, 존재하지 않는 전공, design 전공 선택 차단."""

    def test_insufficient_evidence_is_rejected(self) -> None:
        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        r = client.get(f"/subjects/{session_id}", params={"selected_major_id": "industrial_engineering"})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["error_code"], "EVIDENCE_NOT_READY")

    def test_unregistered_major_is_rejected(self) -> None:
        session_id = _seed_session_with_persona(_ANALYTICAL_STRONG, _ANALYTICAL_LIMITED)
        r = client.get(f"/subjects/{session_id}", params={"selected_major_id": "underwater_basket_weaving"})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["error_code"], "MAJOR_NOT_SELECTABLE")

    def test_design_major_is_rejected(self) -> None:
        """design은 예체능 계열로 추천 대상에서 제외된 전공이다(9차 리뷰) — Vertical
        Slice 대표 전공 3개에 없으므로 selected_major_id로도 거부돼야 한다."""

        session_id = _seed_session_with_persona(_ANALYTICAL_STRONG, _ANALYTICAL_LIMITED)
        r = client.get(f"/subjects/{session_id}", params={"selected_major_id": "design"})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["error_code"], "MAJOR_NOT_SELECTABLE")

    def test_major_not_recommended_for_this_session_is_rejected(self) -> None:
        """selected_major_id 자체는 유효한 대표 전공이어도, 이 세션의 실제 추천 결과에
        없으면 거부해야 한다 — Trait 1개만 강하게 관찰된 학생은 세 대표 전공 모두
        usable_trait_count 미달로 insufficient가 되어(§13 12차 리뷰 진단 리포트의
        'tool_only' Persona) 어떤 전공도 추천 결과에 없다."""

        session_id = _seed_session_with_persona(_TOOL_ONLY_STRONG, set())
        r = client.get(f"/subjects/{session_id}", params={"selected_major_id": "industrial_engineering"})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["error_code"], "MAJOR_NOT_SELECTABLE")

    def test_missing_query_parameter_is_rejected(self) -> None:
        session_id = _seed_session_with_persona(_ANALYTICAL_STRONG, _ANALYTICAL_LIMITED)
        r = client.get(f"/subjects/{session_id}")
        self.assertEqual(r.status_code, 422)

    def test_unknown_session_returns_404(self) -> None:
        r = client.get(
            "/subjects/sess_does_not_exist", params={"selected_major_id": "industrial_engineering"}
        )
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
