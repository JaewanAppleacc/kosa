"""Similarity Matching Engine(§16) 테스트 — 손계산 기반."""

from __future__ import annotations

import unittest
from datetime import datetime

from src.engines.matching_engine import (
    INSUFFICIENT_EVIDENCE_MESSAGE,
    compute_major_match,
    compute_student_trait_states,
    rank_major_relevance,
)
from src.schemas.evidence import TraitEvidenceSummary
from src.schemas.major import MajorProfile
from src.schemas.trait import TraitDefinition


def _trait(trait_id: str, group: str, min_context: int = 2) -> TraitDefinition:
    return TraitDefinition(
        trait_id=trait_id,
        label=trait_id,
        parent_dimension="테스트 차원",
        definition="테스트용 정의",
        positive_indicators=["테스트 긍정 지표"],
        conflicting_indicators=["테스트 상충 지표"],
        source_references=["팀 정의 — 테스트"],
        trait_scope="shared",
        minimum_context_count=min_context,
        primary_vector_group=group,
    )


def _strong(trait_id: str, context_count: int = 2) -> TraitEvidenceSummary:
    return TraitEvidenceSummary(
        trait_id=trait_id, support_count=3, opportunity_count=3, context_count=context_count, distinct_frame_count=2
    )


def _insufficient(trait_id: str) -> TraitEvidenceSummary:
    return TraitEvidenceSummary(trait_id=trait_id, support_count=0, opportunity_count=0)


DEFS = {
    "a": _trait("a", "cognitive"),
    "b": _trait("b", "cognitive"),
    "c": _trait("c", "work_style"),
    "d": _trait("d", "work_style"),
}


class ComputeMajorMatchTest(unittest.TestCase):
    def test_insufficient_when_below_minimum_usable_traits(self) -> None:
        """확정된 Trait가 2개뿐이면(최소 3개 미달) insufficient여야 한다."""

        summaries = {"a": _strong("a"), "b": _strong("b"), "c": _insufficient("c"), "d": _insufficient("d")}
        states = compute_student_trait_states(summaries, DEFS, set())
        major = MajorProfile(
            major_id="m1", label="테스트전공",
            cognitive_vector={"a": 1.00, "b": 1.00},
            extraction_method="manual", review_status="draft", profile_version="v1",
            updated_at=datetime(2026, 1, 1),
        )
        result = compute_major_match(states, major)
        self.assertEqual(result.status, "insufficient")

    def test_insufficient_when_only_one_vector_group_usable(self) -> None:
        """Trait는 3개 이상이어도 전부 같은 Vector 그룹이면(최소 2개 그룹 미달) insufficient."""

        summaries = {"a": _strong("a"), "b": _strong("b"), "c": _insufficient("c"), "d": _insufficient("d")}
        states = compute_student_trait_states(summaries, DEFS, set())
        major = MajorProfile(
            major_id="m1", label="테스트전공",
            cognitive_vector={"a": 1.00, "b": 1.00, "extra_not_in_defs": 1.00},
            extraction_method="manual", review_status="draft", profile_version="v1",
            updated_at=datetime(2026, 1, 1),
        )
        # a,b 둘 다 cognitive라 usable_trait_count=2 (3 미만) → insufficient
        result = compute_major_match(states, major)
        self.assertEqual(result.status, "insufficient")

    def test_computed_when_minimums_met(self) -> None:
        summaries = {"a": _strong("a"), "b": _strong("b"), "c": _strong("c"), "d": _insufficient("d")}
        states = compute_student_trait_states(summaries, DEFS, set())
        major = MajorProfile(
            major_id="m1", label="테스트전공",
            cognitive_vector={"a": 1.00, "b": 1.00},
            work_style_vector={"c": 1.00},
            extraction_method="manual", review_status="draft", profile_version="v1",
            updated_at=datetime(2026, 1, 1),
        )
        result = compute_major_match(states, major)
        self.assertEqual(result.status, "computed")
        self.assertEqual(result.usable_trait_count, 3)
        self.assertIsNotNone(result.score)
        self.assertGreater(result.score, 0)  # 학생 STRONG(1.00)과 전공 가중치(1.00) 방향이 같음

    def test_masked_traits_excluded_from_denominator(self) -> None:
        """CONFLICTING(Mask)된 Trait는 major 벡터에 있어도 usable에서 빠져야 한다."""

        summaries = {"a": _strong("a"), "b": _strong("b"), "c": _strong("c")}
        states = compute_student_trait_states(summaries, DEFS, unresolved_conflict_trait_ids={"c"})
        major = MajorProfile(
            major_id="m1", label="테스트전공",
            cognitive_vector={"a": 1.00, "b": 1.00},
            work_style_vector={"c": 1.00},
            extraction_method="manual", review_status="draft", profile_version="v1",
            updated_at=datetime(2026, 1, 1),
        )
        result = compute_major_match(states, major)
        # c가 Mask되면 work_style 그룹이 통째로 제외 → usable_trait_count는 a,b 둘뿐(2개, 3 미만)
        self.assertEqual(result.status, "insufficient")


class RankMajorRelevanceTest(unittest.TestCase):
    def test_all_insufficient_returns_message(self) -> None:
        from src.engines.matching_engine import MajorMatchResult

        results = [MajorMatchResult(major_id="m1", status="insufficient")]
        relevant, explore, message = rank_major_relevance(results, {"m1": "테스트전공"})
        self.assertEqual(relevant, [])
        self.assertEqual(explore, [])
        self.assertEqual(message, INSUFFICIENT_EVIDENCE_MESSAGE)

    def test_top_third_gets_relevant_label_with_three_candidates(self) -> None:
        from src.engines.matching_engine import MajorMatchResult

        results = [
            MajorMatchResult(major_id="high", status="computed", score=0.9),
            MajorMatchResult(major_id="mid", status="computed", score=0.5),
            MajorMatchResult(major_id="low", status="computed", score=0.1),
        ]
        labels = {"high": "높음전공", "mid": "중간전공", "low": "낮음전공"}
        relevant, explore, message = rank_major_relevance(results, labels)
        self.assertIsNone(message)
        self.assertEqual([r.major_id for r in relevant], ["high"])
        self.assertEqual([r.major_id for r in explore], ["mid", "low"])
        self.assertEqual(explore[0].relevance_label, "함께 탐색해볼 분야")
        self.assertEqual(explore[1].relevance_label, "비교해볼 만한 분야")

    def test_no_internal_score_leaks_into_major_relevance(self) -> None:
        from src.engines.matching_engine import MajorMatchResult

        results = [MajorMatchResult(major_id="m1", status="computed", score=0.77)]
        relevant, _, _ = rank_major_relevance(results, {"m1": "테스트전공"})
        self.assertNotIn("score", set(type(relevant[0]).model_fields.keys()))


if __name__ == "__main__":
    unittest.main()
