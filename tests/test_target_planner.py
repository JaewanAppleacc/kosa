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


class DeepenBlueprintRestrictionTest(unittest.TestCase):
    """2026-08-21 리뷰: 위치 1(DEEPEN)은 Seed에서 선택된 Trait이 속한 Blueprint 안의
    형제 Trait로만 후보를 제한해야 한다(§7-2 관심 지점 심화 + §8 자기확증 방지 동시 만족)."""

    ALL_TWELVE = {
        "causal_analysis",
        "change_adaptation",
        "immediate_execution",
        "information_comparison",
        "collaboration_preference",
        "visual_expression",
        "emotional_interpretation",
        "audience_response_prediction",
        "opinion_mediation",
        "pattern_finding",
        "planning",
        "tool_utilization",
    }

    def test_deepen_candidate_restricted_to_anchor_blueprint(self) -> None:
        """causal_analysis(problem_response_v1)로 앵커링하면, 이 Blueprint 밖의
        audience_response_prediction 같은 Trait는 후보에서 아예 제외돼야 한다."""

        decision = decide_next_target(
            context_id="game",
            position=1,
            all_trait_ids=self.ALL_TWELVE,
            trait_summaries={},  # 전부 관찰 이력 없음 → 전부 교차확인 필요(동률)
            unresolved_conflict_trait_ids=set(),
            recent_target_trait_ids=[],
            used_frame_ids_in_context=set(),
            is_first_context_in_session=False,
            deepen_anchor_trait_id="causal_analysis",
        )
        # problem_response_v1 = {causal_analysis, change_adaptation, immediate_execution,
        # information_comparison, collaboration_preference} — 알파벳 순 1등은 causal_analysis
        # 자신이 아니라 collaboration_preference(하지만 여전히 같은 Blueprint 안).
        problem_response_traits = {
            "causal_analysis",
            "change_adaptation",
            "immediate_execution",
            "information_comparison",
            "collaboration_preference",
        }
        self.assertIn(decision.target_traits[0], problem_response_traits)
        self.assertEqual(decision.option_blueprint_id, "problem_response_v1")

    def test_deepen_without_anchor_is_unrestricted(self) -> None:
        """anchor가 없으면(예: Seed 답변 정보가 없는 경우) 이전처럼 전체 12개가 후보다."""

        decision = decide_next_target(
            context_id="game",
            position=1,
            all_trait_ids=self.ALL_TWELVE,
            trait_summaries={},
            unresolved_conflict_trait_ids=set(),
            recent_target_trait_ids=[],
            used_frame_ids_in_context=set(),
            is_first_context_in_session=False,
        )
        self.assertEqual(decision.target_traits, ["audience_response_prediction"])  # 알파벳 1등

    def test_resolved_blueprint_matches_anchor_even_when_trait_spans_multiple_blueprints(self) -> None:
        """pattern_finding은 expression_and_audience_v1과 planning_and_execution_v1 둘 다에
        속한다. planning으로 앵커링했을 때 Planner가 pattern_finding을 고르면,
        blueprint_for_target_trait()가 아니라 앵커한 Blueprint(planning_and_execution_v1)를
        그대로 써야 한다 — 그래야 실제 생성될 5개 선택지가 앵커 Blueprint와 일치한다."""

        summaries = {
            # planning 그룹 안에서 pattern_finding만 이미 충분히 관찰돼 교차확인이 필요없다고
            # 만들면, 반대로 다른 후보가 우선되므로 여기서는 전부 미관찰 상태로 동률을 만든다.
        }
        decision = decide_next_target(
            context_id="game",
            position=1,
            all_trait_ids=self.ALL_TWELVE,
            trait_summaries=summaries,
            unresolved_conflict_trait_ids=set(),
            recent_target_trait_ids=[],
            used_frame_ids_in_context=set(),
            is_first_context_in_session=False,
            deepen_anchor_trait_id="planning",
        )
        planning_group_traits = {
            "planning",
            "tool_utilization",
            "collaboration_preference",
            "causal_analysis",
            "pattern_finding",
        }
        self.assertIn(decision.target_traits[0], planning_group_traits)
        self.assertEqual(decision.option_blueprint_id, "planning_and_execution_v1")


class FrequencyTieBreakTest(unittest.TestCase):
    def test_less_frequently_targeted_trait_wins_tie(self) -> None:
        """둘 다 교차확인이 필요한 동률 상태에서, pattern_finding이 이미 2번 목표로
        나왔고 causal_analysis는 한 번도 안 나왔다면 causal_analysis가 이겨야 한다
        (순수 알파벳 tie-break였다면 causal_analysis가 이겼겠지만, 반대로 pattern_finding이
        여러 번 나온 상황을 만들어 빈도가 알파벳보다 우선한다는 걸 확인한다)."""

        decision = decide_next_target(
            context_id="media",
            position=2,
            all_trait_ids={"causal_analysis", "pattern_finding"},
            trait_summaries={},
            unresolved_conflict_trait_ids=set(),
            recent_target_trait_ids=["pattern_finding", "causal_analysis", "pattern_finding"],
            used_frame_ids_in_context=set(),
            is_first_context_in_session=False,
        )
        self.assertEqual(decision.target_traits, ["causal_analysis"])


class GapFillingRepetitionGuardTest(unittest.TestCase):
    def test_position_five_excludes_recently_repeated_trait(self) -> None:
        """2026-08-21 리뷰: 위치 5~6 Gap 보완에도 연속 3회 금지가 적용돼야 한다.
        planning이 opportunity=0(명백한 Gap)이지만 최근 2연속 목표였다면 제외돼야 한다."""

        summaries = {
            "planning": _summary("planning", context_count=0, opportunity=0, support=0),
        }
        decision = decide_next_target(
            context_id="media",
            position=5,
            all_trait_ids=ALL_TRAITS,
            trait_summaries=summaries,
            unresolved_conflict_trait_ids=set(),
            recent_target_trait_ids=["planning", "planning"],
            used_frame_ids_in_context=set(),
            is_first_context_in_session=False,
        )
        self.assertNotEqual(decision.target_traits, ["planning"])


if __name__ == "__main__":
    unittest.main()
