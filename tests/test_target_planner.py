"""Question Target Planner — §8 결정 로직 테스트. 손으로 먼저 기대값을 적고 코드와 비교한다."""

from __future__ import annotations

import unittest

from src.agents.assessment.target_planner import decide_next_target
from src.schemas.evidence import TraitEvidenceSummary

ALL_TRAITS = {"causal_analysis", "pattern_finding", "planning", "collaboration_preference"}


def _summary(trait_id: str, context_count: int, opportunity: int = 2, support: int = 2) -> TraitEvidenceSummary:
    return TraitEvidenceSummary(
        trait_id=trait_id,
        support_count=support,
        opportunity_count=opportunity,
        context_count=context_count,
        distinct_frame_count=1,
    )


class PositionThemeTest(unittest.TestCase):
    def test_position_1_uses_deepen_theme_frame(self) -> None:
        decision = decide_next_target(
            context_id="media",
            position=1,
            all_trait_ids=ALL_TRAITS,
            trait_summaries={},
            unresolved_conflict_trait_ids=set(),
            recent_target_trait_ids=[],
            used_frame_ids_in_context=set(),
            is_first_context_in_session=False,
        )
        self.assertEqual(decision.question_frame, "longest_focus")  # DEEPEN 테마 1순위 후보
        self.assertEqual(decision.purpose, "관심 지점 심화 확인")

    def test_position_2_uses_behavior_theme_frame(self) -> None:
        decision = decide_next_target(
            context_id="media",
            position=2,
            all_trait_ids=ALL_TRAITS,
            trait_summaries={},
            unresolved_conflict_trait_ids=set(),
            recent_target_trait_ids=[],
            used_frame_ids_in_context=set(),
            is_first_context_in_session=False,
        )
        self.assertEqual(decision.question_frame, "problem_check")

    def test_position_3_uses_cross_context_theme_when_not_first_context(self) -> None:
        decision = decide_next_target(
            context_id="school_life",
            position=3,
            all_trait_ids=ALL_TRAITS,
            trait_summaries={},
            unresolved_conflict_trait_ids=set(),
            recent_target_trait_ids=[],
            used_frame_ids_in_context=set(),
            is_first_context_in_session=False,
        )
        self.assertEqual(decision.purpose, "다른 Context Evidence와 교차 확인")

    def test_position_3_falls_back_to_deepen_when_first_context(self) -> None:
        """§7-2 예외: 세션의 첫 Context는 비교할 다른 Context Evidence가 없어 심화로 대체."""

        decision = decide_next_target(
            context_id="game",
            position=3,
            all_trait_ids=ALL_TRAITS,
            trait_summaries={},
            unresolved_conflict_trait_ids=set(),
            recent_target_trait_ids=[],
            used_frame_ids_in_context=set(),
            is_first_context_in_session=True,
        )
        self.assertEqual(decision.purpose, "관심 지점 심화 확인")
        self.assertEqual(decision.question_frame, "longest_focus")

    def test_position_4_uses_alternative_theme_frame(self) -> None:
        decision = decide_next_target(
            context_id="media",
            position=4,
            all_trait_ids=ALL_TRAITS,
            trait_summaries={},
            unresolved_conflict_trait_ids=set(),
            recent_target_trait_ids=[],
            used_frame_ids_in_context=set(),
            is_first_context_in_session=False,
        )
        self.assertEqual(decision.question_frame, "unexpected_result")


class CrossContextPriorityTest(unittest.TestCase):
    def test_trait_needing_cross_context_confirmation_is_prioritized(self) -> None:
        """손계산: causal_analysis는 이미 2개 Context에서 확인됨(교차확인 불필요),
        pattern_finding은 1개 Context에서만 확인됨(교차확인 필요) → pattern_finding이 선택돼야 함."""

        summaries = {
            "causal_analysis": _summary("causal_analysis", context_count=2),
            "pattern_finding": _summary("pattern_finding", context_count=1),
        }
        decision = decide_next_target(
            context_id="media",
            position=1,
            all_trait_ids={"causal_analysis", "pattern_finding"},
            trait_summaries=summaries,
            unresolved_conflict_trait_ids=set(),
            recent_target_trait_ids=[],
            used_frame_ids_in_context=set(),
            is_first_context_in_session=False,
        )
        self.assertEqual(decision.target_traits, ["pattern_finding"])

    def test_ties_broken_alphabetically(self) -> None:
        summaries = {
            "causal_analysis": _summary("causal_analysis", context_count=1),
            "pattern_finding": _summary("pattern_finding", context_count=1),
        }
        decision = decide_next_target(
            context_id="media",
            position=1,
            all_trait_ids={"causal_analysis", "pattern_finding"},
            trait_summaries=summaries,
            unresolved_conflict_trait_ids=set(),
            recent_target_trait_ids=[],
            used_frame_ids_in_context=set(),
            is_first_context_in_session=False,
        )
        self.assertEqual(decision.target_traits, ["causal_analysis"])  # 알파벳 순으로 먼저


class RepetitionGuardTest(unittest.TestCase):
    def test_trait_targeted_twice_in_a_row_is_excluded(self) -> None:
        """§8 자기확증 방지: 연속 3회 금지. causal_analysis가 최근 2번 연속 목표였다면
        이번엔 다른 Trait가 선택돼야 한다(둘 다 교차확인 불필요 상태로 동률이라도)."""

        summaries = {
            "causal_analysis": _summary("causal_analysis", context_count=2),
            "pattern_finding": _summary("pattern_finding", context_count=2),
        }
        decision = decide_next_target(
            context_id="media",
            position=2,
            all_trait_ids={"causal_analysis", "pattern_finding"},
            trait_summaries=summaries,
            unresolved_conflict_trait_ids=set(),
            recent_target_trait_ids=["causal_analysis", "causal_analysis"],
            used_frame_ids_in_context=set(),
            is_first_context_in_session=False,
        )
        self.assertEqual(decision.target_traits, ["pattern_finding"])


class PositionFiveSixTest(unittest.TestCase):
    def test_unresolved_conflict_takes_priority_over_coverage_gap(self) -> None:
        summaries = {
            "planning": _summary("planning", context_count=0, opportunity=0, support=0),  # gap
        }
        decision = decide_next_target(
            context_id="media",
            position=5,
            all_trait_ids=ALL_TRAITS,
            trait_summaries=summaries,
            unresolved_conflict_trait_ids={"collaboration_preference"},
            recent_target_trait_ids=[],
            used_frame_ids_in_context=set(),
            is_first_context_in_session=False,
        )
        self.assertEqual(decision.target_traits, ["collaboration_preference"])
        self.assertEqual(decision.purpose, "해결되지 않은 Explicit Conflict 보완")

    def test_coverage_gap_used_when_no_conflict(self) -> None:
        """손계산: planning은 opportunity=0(전혀 안 물어봄)이라 명백한 Gap. 나머지는 충분히 관찰됨.
        → planning이 선택돼야 한다."""

        summaries = {
            "causal_analysis": _summary("causal_analysis", context_count=2, opportunity=3, support=3),
            "pattern_finding": _summary("pattern_finding", context_count=2, opportunity=3, support=3),
            "collaboration_preference": _summary(
                "collaboration_preference", context_count=2, opportunity=3, support=3
            ),
            # planning은 trait_summaries에 아예 없음 → opportunity_count=0과 동일하게 취급
        }
        decision = decide_next_target(
            context_id="media",
            position=6,
            all_trait_ids=ALL_TRAITS,
            trait_summaries=summaries,
            unresolved_conflict_trait_ids=set(),
            recent_target_trait_ids=[],
            used_frame_ids_in_context=set(),
            is_first_context_in_session=False,
        )
        self.assertEqual(decision.target_traits, ["planning"])
        self.assertEqual(decision.purpose, "Evidence가 부족한 핵심 Trait 보완")


if __name__ == "__main__":
    unittest.main()
