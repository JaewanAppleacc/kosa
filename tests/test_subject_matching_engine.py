"""SubjectMatchingEngine 단위 테스트 — 2026-08-24 14차 리뷰 §7."""

from __future__ import annotations

import unittest

from src.engines.matching_engine import StudentTraitState
from src.engines.subject_matching_engine import (
    MINIMUM_SCORE_FOR_CORE,
    MINIMUM_USABLE_TRAITS_FOR_CORE,
    MINIMUM_USABLE_TRAITS_FOR_EXPLORE,
    build_reason,
    compute_subject_recommendations,
    to_course_recommendation_items,
)
from src.schemas.course import SubjectProfile
from src.schemas.trait import TraitDefinition


def _state(trait_id: str, value: float | None, group: str = "cognitive") -> StudentTraitState:
    from src.schemas.evidence import TraitState

    state = TraitState.STRONG if value == 1.0 else TraitState.LIMITED if value is not None else TraitState.INSUFFICIENT
    return StudentTraitState(
        trait_id=trait_id, state=state, normalized_value=value, context_count=2, primary_vector_group=group
    )


def _subject(
    subject_id: str,
    trait_vector: dict[str, float],
    related_major_ids: list[str],
    label: str | None = None,
    activity_summary: str = "테스트 활동을 수행하는 활동",
) -> SubjectProfile:
    return SubjectProfile(
        subject_id=subject_id, label=label or subject_id, trait_vector=trait_vector,
        related_major_ids=related_major_ids, source_id="https://example.moe.go.kr/",
        activity_summary=activity_summary,
    )


def _trait_def(trait_id: str, label: str) -> TraitDefinition:
    return TraitDefinition(
        trait_id=trait_id, label=label, parent_dimension="테스트", definition="테스트 정의",
        positive_indicators=["테스트 지표"], conflicting_indicators=["테스트 반대 지표"],
        source_references=["팀 정의 — 테스트"], trait_scope="shared", minimum_context_count=1,
        primary_vector_group="cognitive",
    )


class ComputeSubjectRecommendationsTest(unittest.TestCase):
    def test_only_subjects_linked_to_selected_major_are_candidates(self) -> None:
        subjects = [
            _subject("subj_related", {"causal_analysis": 1.0}, ["industrial_engineering"]),
            _subject("subj_unrelated", {"causal_analysis": 1.0}, ["media_communication"]),
        ]
        states = {"causal_analysis": _state("causal_analysis", 1.0)}
        results = compute_subject_recommendations(states, "industrial_engineering", subjects)
        self.assertEqual([r.subject_id for r in results], ["subj_related"])

    def test_subject_with_no_shared_confirmed_trait_is_excluded(self) -> None:
        subjects = [_subject("subj_a", {"causal_analysis": 1.0}, ["industrial_engineering"])]
        states = {"pattern_finding": _state("pattern_finding", 1.0)}  # causal_analysis 자체가 없음
        results = compute_subject_recommendations(states, "industrial_engineering", subjects)
        self.assertEqual(results, [])

    def test_masked_trait_is_excluded_not_treated_as_zero(self) -> None:
        """UNMAPPED/미확정 Trait(normalized_value=None)는 비교에서 완전히 빠져야 한다 —
        과목에 causal_analysis 가중치가 있어도 학생이 그 Trait를 확정하지 못했으면 안 쓴다."""

        subjects = [_subject("subj_a", {"causal_analysis": 1.0, "pattern_finding": 1.0}, ["industrial_engineering"])]
        states = {
            "causal_analysis": _state("causal_analysis", None),  # Mask(INSUFFICIENT/CONFLICTING)
            "pattern_finding": _state("pattern_finding", 1.0),
        }
        results = compute_subject_recommendations(states, "industrial_engineering", subjects)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].usable_trait_count, 1)
        self.assertEqual(results[0].usable_trait_ids, ["pattern_finding"])

    def test_high_usable_count_and_score_yields_core(self) -> None:
        subjects = [_subject("subj_a", {"causal_analysis": 1.0, "pattern_finding": 1.0}, ["industrial_engineering"])]
        states = {"causal_analysis": _state("causal_analysis", 1.0), "pattern_finding": _state("pattern_finding", 1.0)}
        results = compute_subject_recommendations(states, "industrial_engineering", subjects)
        self.assertEqual(results[0].category, "core")
        self.assertGreaterEqual(results[0].usable_trait_count, MINIMUM_USABLE_TRAITS_FOR_CORE)
        self.assertGreaterEqual(results[0].score, MINIMUM_SCORE_FOR_CORE)

    def test_single_usable_trait_yields_explore_not_core(self) -> None:
        subjects = [_subject("subj_a", {"causal_analysis": 1.0}, ["industrial_engineering"])]
        states = {"causal_analysis": _state("causal_analysis", 1.0)}
        results = compute_subject_recommendations(states, "industrial_engineering", subjects)
        self.assertEqual(results[0].category, "explore")
        self.assertEqual(results[0].usable_trait_count, MINIMUM_USABLE_TRAITS_FOR_EXPLORE)

    def test_low_score_with_enough_traits_yields_explore_not_core(self) -> None:
        subjects = [_subject("subj_a", {"causal_analysis": 1.0, "pattern_finding": 1.0}, ["industrial_engineering"])]
        states = {"causal_analysis": _state("causal_analysis", 0.33), "pattern_finding": _state("pattern_finding", 0.33)}
        results = compute_subject_recommendations(states, "industrial_engineering", subjects)
        self.assertEqual(results[0].category, "explore")

    def test_deterministic_order_core_before_explore_then_score_then_subject_id(self) -> None:
        subjects = [
            _subject("subj_z_explore", {"causal_analysis": 1.0}, ["industrial_engineering"]),
            _subject("subj_a_core", {"causal_analysis": 1.0, "pattern_finding": 1.0}, ["industrial_engineering"]),
            _subject("subj_b_core", {"causal_analysis": 1.0, "pattern_finding": 1.0}, ["industrial_engineering"]),
        ]
        states = {"causal_analysis": _state("causal_analysis", 1.0), "pattern_finding": _state("pattern_finding", 1.0)}
        results = compute_subject_recommendations(states, "industrial_engineering", subjects)
        self.assertEqual(
            [r.subject_id for r in results], ["subj_a_core", "subj_b_core", "subj_z_explore"]
        )

    def test_rerunning_with_same_input_is_identical(self) -> None:
        subjects = [_subject("subj_a", {"causal_analysis": 1.0, "pattern_finding": 1.0}, ["industrial_engineering"])]
        states = {"causal_analysis": _state("causal_analysis", 1.0), "pattern_finding": _state("pattern_finding", 1.0)}
        first = compute_subject_recommendations(states, "industrial_engineering", subjects)
        second = compute_subject_recommendations(states, "industrial_engineering", subjects)
        self.assertEqual([r.model_dump() for r in first], [r.model_dump() for r in second])


class ReasonAndMappingTest(unittest.TestCase):
    def test_reason_contains_major_label_and_trait_labels_not_numbers(self) -> None:
        subjects = [_subject("subj_a", {"causal_analysis": 1.0}, ["industrial_engineering"])]
        states = {"causal_analysis": _state("causal_analysis", 1.0)}
        results = compute_subject_recommendations(states, "industrial_engineering", subjects)
        trait_defs = {"causal_analysis": _trait_def("causal_analysis", "원인 분석")}
        reason = build_reason(results[0], "산업공학", trait_defs)
        self.assertIn("산업공학", reason)
        self.assertIn("원인 분석", reason)
        for token in reason.split():
            self.assertFalse(any(ch.isdigit() for ch in token) and "." in token, f"숫자 유사도로 보이는 토큰: {token}")

    def test_to_course_recommendation_items_has_no_score_field_and_offered_is_none(self) -> None:
        subjects = [_subject("subj_a", {"causal_analysis": 1.0, "pattern_finding": 1.0}, ["industrial_engineering"])]
        states = {"causal_analysis": _state("causal_analysis", 1.0), "pattern_finding": _state("pattern_finding", 1.0)}
        results = compute_subject_recommendations(states, "industrial_engineering", subjects)
        trait_defs = {
            "causal_analysis": _trait_def("causal_analysis", "원인 분석"),
            "pattern_finding": _trait_def("pattern_finding", "패턴 탐색"),
        }
        items = to_course_recommendation_items(results, "산업공학", trait_defs)
        self.assertEqual(len(items), 1)
        self.assertNotIn("score", items[0].model_dump())
        self.assertIsNone(items[0].is_actually_offered)
        self.assertEqual(items[0].category, "core")

    def test_to_course_recommendation_items_carries_the_subject_label(self) -> None:
        """2026-08-25 15차 리뷰 §1: subject_id만으로는 B가 과목명을 못 띄웠다 — 정본
        SubjectProfile.label을 그대로 옮겨야 한다."""

        subjects = [
            _subject("subj_a", {"causal_analysis": 1.0}, ["industrial_engineering"], label="확률과 통계")
        ]
        states = {"causal_analysis": _state("causal_analysis", 1.0)}
        results = compute_subject_recommendations(states, "industrial_engineering", subjects)
        items = to_course_recommendation_items(
            results, "산업공학", {"causal_analysis": _trait_def("causal_analysis", "원인 분석")}
        )
        self.assertEqual(items[0].subject_id, "subj_a")
        self.assertEqual(items[0].label, "확률과 통계")

    def test_reason_does_not_use_banned_overclaiming_phrases(self) -> None:
        """§3: Mapping이 아직 draft(2인 검토 전)라 "검증된"/"공식적으로 연결된" 같은
        과장된 확정 표현을 쓰면 안 된다."""

        subjects = [
            _subject(
                "subj_a", {"causal_analysis": 1.0}, ["industrial_engineering"],
                label="확률과 통계", activity_summary="자료를 분석하고 결과를 비교하는 활동",
            )
        ]
        states = {"causal_analysis": _state("causal_analysis", 1.0)}
        results = compute_subject_recommendations(states, "industrial_engineering", subjects)
        reason = build_reason(
            results[0], "산업공학", {"causal_analysis": _trait_def("causal_analysis", "원인 분석")}
        )
        banned_phrases = [
            "검증된 과목", "공식 추천 과목", "반드시 들어야 하는 과목",
            "이 전공에 필수인 과목", "적합도가 입증된 과목", "공식적으로 연결된 과목",
        ]
        for phrase in banned_phrases:
            self.assertNotIn(phrase, reason, f"금지 표현이 reason에 남아 있다: {phrase!r}")

    def test_reason_includes_selected_major_observed_trait_and_concrete_activity(self) -> None:
        """§4: reason에 (1) 선택 전공, (2) 학생 답변에서 확인된 Trait, (3) 과목의 공식
        교육과정 근거에서 뽑은 구체적 활동이 실제로 들어가야 한다."""

        subjects = [
            _subject(
                "subj_a", {"causal_analysis": 1.0}, ["industrial_engineering"],
                label="확률과 통계", activity_summary="자료를 분석하고 결과를 비교하는 활동",
            )
        ]
        states = {"causal_analysis": _state("causal_analysis", 1.0)}
        results = compute_subject_recommendations(states, "industrial_engineering", subjects)
        reason = build_reason(
            results[0], "산업공학", {"causal_analysis": _trait_def("causal_analysis", "원인 분석")}
        )
        self.assertIn("산업공학", reason)
        self.assertIn("원인 분석", reason)
        self.assertIn("확률과 통계", reason)
        self.assertIn("자료를 분석하고 결과를 비교하는 활동", reason)

    def test_reason_falls_back_to_limited_wording_when_activity_summary_missing(self) -> None:
        """§4: "근거가 없으면 활동을 지어내지 말고... 제한적 이유로 표시" — activity_summary
        가 비어 있으면 구체 활동을 지어내지 않고 제한적 문구로 대체해야 한다."""

        subjects = [
            _subject(
                "subj_a", {"causal_analysis": 1.0}, ["industrial_engineering"],
                label="근거 없는 과목", activity_summary="",
            )
        ]
        states = {"causal_analysis": _state("causal_analysis", 1.0)}
        results = compute_subject_recommendations(states, "industrial_engineering", subjects)
        reason = build_reason(
            results[0], "산업공학", {"causal_analysis": _trait_def("causal_analysis", "원인 분석")}
        )
        self.assertIn("아직 정리되지 않았습니다", reason)
        self.assertNotIn("경험할 수 있으며", reason)  # 활동을 지어내는 문장 구조가 안 쓰였는지


if __name__ == "__main__":
    unittest.main()
