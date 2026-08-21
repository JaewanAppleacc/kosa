"""답변 처리 파이프라인(§5-2) + Stop Condition(§5-3) 테스트."""

from __future__ import annotations

import unittest

from src.agents.assessment.answer_processor import submit_answer
from src.api.mock_data import seed_question_as_finalized
from src.data.questions.vertical_slice_seed_questions import GAME_SEED_01
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAIT_IDS
from src.engines.evidence_engine import decide_stop_or_continue
from src.schemas.assessment_state import AssessmentState
from src.schemas.evidence import TraitEvidenceSummary

# submit_answer는 FinalizedQuestion을 받는다(실제 API가 학생에게 보여주는 형태) — Seed는
# mock_data.seed_question_as_finalized()로 변환한 것을 쓴다.
GAME_SEED_01_FINALIZED = seed_question_as_finalized(GAME_SEED_01)


class StopConditionTest(unittest.TestCase):
    """§5-3 손계산: 각 케이스를 표 그대로 옮긴다."""

    def test_under_four_always_continues(self) -> None:
        self.assertEqual(decide_stop_or_continue(0, {}, set(), set()), "CONTINUE")
        self.assertEqual(decide_stop_or_continue(3, {}, set(), set()), "CONTINUE")

    def test_six_or_more_always_stops(self) -> None:
        # Gap과 Conflict가 남아있어도 6개 완료면 무조건 강제 STOP.
        self.assertEqual(
            decide_stop_or_continue(6, {}, {"causal_analysis"}, {"causal_analysis"}), "STOP"
        )

    def test_four_with_no_gap_and_no_conflict_stops(self) -> None:
        summaries = {
            "causal_analysis": TraitEvidenceSummary(
                trait_id="causal_analysis",
                support_count=3,
                opportunity_count=3,
                context_count=2,
                distinct_frame_count=2,
            )
        }
        result = decide_stop_or_continue(4, summaries, {"causal_analysis"}, set())
        self.assertEqual(result, "STOP")

    def test_four_with_coverage_gap_continues(self) -> None:
        # opportunity_count=0인 Trait가 하나라도 있으면 아직 STOP하면 안 된다.
        summaries = {
            "causal_analysis": TraitEvidenceSummary(
                trait_id="causal_analysis",
                support_count=0,
                opportunity_count=0,
                context_count=0,
                distinct_frame_count=0,
            )
        }
        result = decide_stop_or_continue(4, summaries, {"causal_analysis"}, set())
        self.assertEqual(result, "CONTINUE")

    def test_four_with_unresolved_conflict_continues(self) -> None:
        summaries = {
            "causal_analysis": TraitEvidenceSummary(
                trait_id="causal_analysis",
                support_count=3,
                opportunity_count=3,
                context_count=2,
                distinct_frame_count=2,
            )
        }
        result = decide_stop_or_continue(4, summaries, {"causal_analysis"}, {"causal_analysis"})
        self.assertEqual(result, "CONTINUE")

    def test_five_same_as_four_rules(self) -> None:
        summaries = {
            "causal_analysis": TraitEvidenceSummary(
                trait_id="causal_analysis",
                support_count=3,
                opportunity_count=3,
                context_count=2,
                distinct_frame_count=2,
            )
        }
        self.assertEqual(decide_stop_or_continue(5, summaries, {"causal_analysis"}, set()), "STOP")
        self.assertEqual(
            decide_stop_or_continue(5, summaries, {"causal_analysis"}, {"causal_analysis"}),
            "CONTINUE",
        )


class SubmitAnswerTest(unittest.TestCase):
    def _fresh_state(self) -> AssessmentState:
        return AssessmentState(session_id="sess_test", user_id="demo_user_01")

    def test_rejects_option_not_belonging_to_question(self) -> None:
        state = self._fresh_state()
        result = submit_answer(
            state, GAME_SEED_01_FINALIZED, "not_a_real_option_id", VERTICAL_SLICE_TRAIT_IDS, True
        )
        self.assertFalse(result.accepted)
        self.assertIsNotNone(result.rejection_reason)
        self.assertEqual(len(state.evidence_ledger), 0)  # 거부되면 State가 바뀌면 안 된다

    def test_seed_answer_always_continues_and_targets_position_one(self) -> None:
        state = self._fresh_state()
        result = submit_answer(
            state, GAME_SEED_01_FINALIZED, "game_seed_01_o1", VERTICAL_SLICE_TRAIT_IDS, True
        )
        self.assertTrue(result.accepted)
        self.assertEqual(result.stop_decision, "CONTINUE")
        self.assertIsNotNone(result.next_planner_decision)
        self.assertEqual(result.next_planner_decision.purpose, "관심 지점 심화 확인")  # 위치 1 = DEEPEN

        # State가 실제로 갱신됐는지 확인
        self.assertEqual(len(state.evidence_ledger), 1)
        self.assertEqual(state.evidence_ledger[0].applied_primary_trait_delta, {"causal_analysis": 1})
        self.assertEqual(state.questions_asked_in_current_context, 1)
        self.assertEqual(state.trait_summaries["causal_analysis"].support_count, 1)
        self.assertEqual(state.trait_summaries["causal_analysis"].opportunity_count, 1)
        # game_seed_01에 없는 Trait(예: planning)는 opportunity도 0이어야 한다
        self.assertEqual(state.trait_summaries["planning"].opportunity_count, 0)

    def test_context_continues_while_coverage_gap_remains(self) -> None:
        """손계산: Seed 1개 + 꼬리질문 4개를 넣어도, 이 5개 질문이 game_seed_01의 5개
        Trait(causal_analysis/immediate_execution/collaboration_preference/pattern_finding/
        tool_utilization)만 계속 다루기 때문에 나머지 7개 Trait는 opportunity=0인 채로
        남는다. 그래서 4번째 꼬리질문(전체 5번째 답변) 시점에도 Gap이 남아 STOP이 아니라
        CONTINUE가 나와야 한다."""

        state = self._fresh_state()
        result = submit_answer(
            state, GAME_SEED_01_FINALIZED, "game_seed_01_o1", VERTICAL_SLICE_TRAIT_IDS, True
        )

        for i, option in enumerate(GAME_SEED_01_FINALIZED.options[1:], start=2):
            fake_tail = GAME_SEED_01_FINALIZED.model_copy(
                update={
                    "question_id": f"game_tail_{i:02d}",
                    "frame_id": f"frame_{i}",
                    "target_traits": list(option.primary_trait_delta.keys()),
                    "options": [
                        o.model_copy(update={"option_id": f"game_tail_{i:02d}_o{j}"})
                        for j, o in enumerate(GAME_SEED_01_FINALIZED.options, start=1)
                    ],
                }
            )
            selected_option_id = f"game_tail_{i:02d}_o{i}"  # option[i-1] == 원래 game_seed_01의 i번째 옵션
            result = submit_answer(state, fake_tail, selected_option_id, VERTICAL_SLICE_TRAIT_IDS, False)

        self.assertEqual(state.questions_asked_in_current_context, 5)  # seed 1 + tail 4
        self.assertEqual(result.stop_decision, "CONTINUE")  # Gap이 남아 STOP 못 함
        # 한 번도 제시 안 된 Trait는 여전히 opportunity=0이어야 한다.
        self.assertEqual(state.trait_summaries["visual_expression"].opportunity_count, 0)


if __name__ == "__main__":
    unittest.main()
