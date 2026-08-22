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


def _subject(subject_id: str, trait_vector: dict[str, float], related_major_ids: list[str]) -> SubjectProfile:
    return SubjectProfile(
        subject_id=subject_id, label=subject_id, trait_vector=trait_vector,
        related_major_ids=related_major_ids, source_id="https://example.moe.go.kr/",
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


if __name__ == "__main__":
    unittest.main()
