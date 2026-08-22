"""eval/policy_guard_test.py 대응 — CLAUDE.md: "생략하지 않는다."

policy_guard.py의 6개 규칙 각각을 의도적으로 위반하는 입력을 넣어 실제로 막히는지 확인한다.
"""

from __future__ import annotations

import unittest

from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAIT_IDS
from src.engines.policy_guard import (
    PolicyViolation,
    guard_exactly_five_options,
    guard_llm_call_budget,
    guard_no_major_signal_in_assessment_state,
    guard_offered_status_matches_core_category,
    guard_role_ids_match_blueprint,
    guard_subject_must_be_offered,
    guard_trait_in_ontology,
)
from src.schemas.course import CourseRecommendationItem
from src.schemas.question import GeneratedOption, OptionBlueprint, OptionRole


def _blueprint() -> OptionBlueprint:
    return OptionBlueprint(
        blueprint_id="bp",
        roles=[
            OptionRole(role_id="a", primary_trait_delta={"causal_analysis": 1}),
            OptionRole(role_id="b", primary_trait_delta={"change_adaptation": 1}),
            OptionRole(role_id="c", primary_trait_delta={"immediate_execution": 1}),
            OptionRole(role_id="d", primary_trait_delta={"information_comparison": 1}),
            OptionRole(role_id="e", primary_trait_delta={"collaboration_preference": 1}),
        ],
    )


class Rule1UnmappedTraitTest(unittest.TestCase):
    """§6-3: Ontology에 없는 Trait는 UNMAPPED_TRAIT로 저장하고 계산에서 제외한다."""

    def test_known_trait_passes_through(self) -> None:
        self.assertEqual(
            guard_trait_in_ontology("causal_analysis", VERTICAL_SLICE_TRAIT_IDS),
            "causal_analysis",
        )

    def test_unknown_trait_returns_none_ie_unmapped(self) -> None:
        self.assertIsNone(guard_trait_in_ontology("made_up_trait", VERTICAL_SLICE_TRAIT_IDS))


class Rule2RoleIdMismatchTest(unittest.TestCase):
    """§11: LLM이 반환한 Role ID가 Blueprint와 다르면 거부한다."""

    def test_matching_role_ids_pass(self) -> None:
        guard_role_ids_match_blueprint([GeneratedOption(role_id="a", text="x")], _blueprint())

    def test_unknown_role_id_is_rejected(self) -> None:
        with self.assertRaises(PolicyViolation):
            guard_role_ids_match_blueprint(
                [GeneratedOption(role_id="not_in_blueprint", text="x")], _blueprint()
            )


class Rule3OptionCountTest(unittest.TestCase):
    """§11: 선택지가 정확히 5개가 아니면 거부한다."""

    def test_five_options_pass(self) -> None:
        guard_exactly_five_options([1, 2, 3, 4, 5])

    def test_four_options_rejected(self) -> None:
        with self.assertRaises(PolicyViolation):
            guard_exactly_five_options([1, 2, 3, 4])

    def test_six_options_rejected(self) -> None:
        with self.assertRaises(PolicyViolation):
            guard_exactly_five_options([1, 2, 3, 4, 5, 6])


class Rule4LlmBudgetTest(unittest.TestCase):
    """§24: 세션당 LLM 호출 예산을 초과하면 호출 자체를 차단한다."""

    def test_under_budget_passes(self) -> None:
        guard_llm_call_budget(current_call_count=10, max_calls_per_session=40)

    def test_at_budget_is_blocked(self) -> None:
        with self.assertRaises(PolicyViolation):
            guard_llm_call_budget(current_call_count=40, max_calls_per_session=40)


class Rule5NoMajorInAssessmentTest(unittest.TestCase):
    """§5-1, §8: 전공 관련도·순위를 Assessment Planner 입력으로 전달하지 않는다."""

    def test_current_assessment_state_has_no_major_field(self) -> None:
        # 지금은 통과해야 한다 — AssessmentState에 major 필드를 추가하는 순간 이 테스트가 깨져야 한다.
        guard_no_major_signal_in_assessment_state()


class Rule6UnofferedSubjectTest(unittest.TestCase):
    """§20: 학교 개설 목록에 없는 과목을 실제 개설과목처럼 추천하지 않는다."""

    def test_offered_subjects_pass(self) -> None:
        guard_subject_must_be_offered(["subj_a", "subj_b"], {"subj_a", "subj_b", "subj_c"})

    def test_unoffered_subject_is_rejected(self) -> None:
        with self.assertRaises(PolicyViolation):
            guard_subject_must_be_offered(["subj_a", "subj_x"], {"subj_a", "subj_b"})


class Rule6bOfferedStatusMatchesCoreCategoryTest(unittest.TestCase):
    """2026-08-24 14차 리뷰(2026-08-26 16차 리뷰로 규칙 강화): `is_actually_offered`가
    `bool | None`이 된 뒤, PRE_SURVEY의 core는 개설 여부 미확정("희망 우선과목")이어도
    되지만 POST_OFFERING의 recommendations(core/explore/alternative 전부)는 반드시
    실제 개설(True)이 확인돼야 한다 — 미개설 과목은 unavailable_subjects로만 표현한다."""

    def _item(
        self, category: str, is_actually_offered: bool | None, replaces_subject_id: str | None = None
    ) -> CourseRecommendationItem:
        return CourseRecommendationItem(
            subject_id="subj_a", label="테스트 과목", category=category,
            is_actually_offered=is_actually_offered, reason="테스트용",
            replaces_subject_id=replaces_subject_id,
        )

    def test_pre_survey_core_with_unconfirmed_offering_status_passes(self) -> None:
        guard_offered_status_matches_core_category(
            [self._item("core", None)], source="PRE_SURVEY"
        )

    def test_post_offering_core_requires_confirmed_true(self) -> None:
        guard_offered_status_matches_core_category(
            [self._item("core", True)], source="POST_OFFERING"
        )

    def test_post_offering_core_with_none_is_rejected(self) -> None:
        with self.assertRaises(PolicyViolation):
            guard_offered_status_matches_core_category(
                [self._item("core", None)], source="POST_OFFERING"
            )

    def test_post_offering_core_with_false_is_rejected(self) -> None:
        with self.assertRaises(PolicyViolation):
            guard_offered_status_matches_core_category(
                [self._item("core", False)], source="POST_OFFERING"
            )

    def test_post_offering_explore_with_false_is_rejected(self) -> None:
        """2026-08-26 16차 리뷰: 예전엔 explore는 검사하지 않았지만, POST_OFFERING의
        recommendations는 전부 실제 개설이 확인돼야 한다는 규칙으로 강화됐다."""

        with self.assertRaises(PolicyViolation):
            guard_offered_status_matches_core_category(
                [self._item("explore", False)], source="POST_OFFERING"
            )

    def test_post_offering_explore_with_true_passes(self) -> None:
        guard_offered_status_matches_core_category(
            [self._item("explore", True)], source="POST_OFFERING"
        )

    def test_post_offering_alternative_requires_true(self) -> None:
        """§9: alternative도 실제 개설과목이어야 한다."""

        guard_offered_status_matches_core_category(
            [self._item("alternative", True, replaces_subject_id="subj_missing")],
            source="POST_OFFERING",
        )
        with self.assertRaises(PolicyViolation):
            guard_offered_status_matches_core_category(
                [self._item("alternative", False, replaces_subject_id="subj_missing")],
                source="POST_OFFERING",
            )


if __name__ == "__main__":
    unittest.main()
