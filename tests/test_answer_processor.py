"""답변 처리 파이프라인(§5-2) + Stop Condition(§5-3) 테스트."""

from __future__ import annotations

import unittest

from src.agents.assessment.answer_processor import submit_answer
from src.api.mock_data import seed_question_as_finalized
from src.data.conflicts.vertical_slice_conflict_resolution_questions import (
    VERTICAL_SLICE_RESOLUTION_SPECS,
    build_planning_vs_execution_resolution_question,
)
from src.data.conflicts.vertical_slice_contrast_definitions import VERTICAL_SLICE_CONTRAST_DEFINITIONS
from src.data.questions.vertical_slice_seed_questions import GAME_SEED_01
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAIT_IDS
from src.engines.evidence_engine import decide_stop_or_continue
from src.schemas.assessment_state import AssessmentState
from src.schemas.evidence import ContrastResolutionStatus, TraitEvidenceSummary

_RESOLUTION_ROLE_MAPS = {
    cid: spec.role_resolution_map for cid, spec in VERTICAL_SLICE_RESOLUTION_SPECS.items()
}

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

    def test_seed_answer_sets_context_seed_trait_and_restricts_deepen_blueprint(self) -> None:
        """2026-08-21 리뷰: Seed에서 causal_analysis(problem_response_v1)를 선택하면,
        state.current_context_seed_trait_id가 그 Trait로 채워지고, 위치 1(DEEPEN)의
        option_blueprint_id도 problem_response_v1로 제한돼야 한다."""

        state = self._fresh_state()
        result = submit_answer(
            state, GAME_SEED_01_FINALIZED, "game_seed_01_o1", VERTICAL_SLICE_TRAIT_IDS, True
        )
        self.assertEqual(state.current_context_seed_trait_id, "causal_analysis")
        self.assertEqual(result.next_planner_decision.option_blueprint_id, "problem_response_v1")

    def test_previous_question_and_answer_text_are_carried_into_state(self) -> None:
        state = self._fresh_state()
        selected = GAME_SEED_01_FINALIZED.options[0]
        submit_answer(
            state, GAME_SEED_01_FINALIZED, selected.option_id, VERTICAL_SLICE_TRAIT_IDS, True
        )
        self.assertEqual(state.pending_previous_question_text, GAME_SEED_01_FINALIZED.question_text)
        self.assertEqual(state.pending_previous_answer_text, selected.text)

    def test_selected_option_next_probe_is_carried_into_state(self) -> None:
        """§7-3/§8: 선택된 Option의 next_probe는 목표 Trait을 바꾸지 않고 다음 질문
        "문구"를 잇는 재료로만 state.pending_next_probe에 남아야 한다."""

        state = self._fresh_state()
        selected = GAME_SEED_01_FINALIZED.options[0]
        self.assertIsNotNone(selected.next_probe)  # Fixture 전제 확인
        submit_answer(
            state, GAME_SEED_01_FINALIZED, selected.option_id, VERTICAL_SLICE_TRAIT_IDS, True
        )
        self.assertEqual(state.pending_next_probe, selected.next_probe)

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


class ExplicitConflictIntegrationTest(unittest.TestCase):
    """§12-1 3단계: 실제 VERTICAL_SLICE_CONTRAST_DEFINITIONS(planning_vs_execution)를
    submit_answer에 넘겨 evidence_ledger만으로 Conflict가 실제로 잡히는지 확인한다."""

    def _fresh_state(self) -> AssessmentState:
        return AssessmentState(session_id="sess_test", user_id="demo_user_01")

    def _tail(self, question_id: str, role_id: str, trait_id: str, frame_id: str):
        target_option = GAME_SEED_01_FINALIZED.options[0].model_copy(
            update={"option_id": f"{question_id}_o1", "role_id": role_id, "primary_trait_delta": {trait_id: 1}}
        )
        filler_options = [
            o.model_copy(update={"option_id": f"{question_id}_o{i}"})
            for i, o in enumerate(GAME_SEED_01_FINALIZED.options[1:], start=2)
        ]
        return GAME_SEED_01_FINALIZED.model_copy(
            update={
                "question_id": question_id,
                "frame_id": frame_id,
                "target_traits": [trait_id],
                "options": [target_option] + filler_options,
            }
        )

    def test_explicit_conflict_masks_both_traits_and_blocks_stop(self) -> None:
        state = self._fresh_state()
        submit_answer(
            state, GAME_SEED_01_FINALIZED, "game_seed_01_o1", VERTICAL_SLICE_TRAIT_IDS, True,
            VERTICAL_SLICE_CONTRAST_DEFINITIONS,
        )

        result = None
        for i, (role_id, trait_id) in enumerate(
            [
                ("advance_planning", "planning"),
                ("quick_execution", "immediate_execution"),
                ("advance_planning", "planning"),
                ("quick_execution", "immediate_execution"),
            ],
            start=2,
        ):
            question = self._tail(f"game_tail_{i:02d}", role_id, trait_id, "new_tool")
            result = submit_answer(
                state, question, f"game_tail_{i:02d}_o1", VERTICAL_SLICE_TRAIT_IDS, False,
                VERTICAL_SLICE_CONTRAST_DEFINITIONS,
            )

        self.assertEqual(state.unresolved_conflict_trait_ids, {"planning", "immediate_execution"})
        self.assertEqual(state.trait_summaries["planning"].explicit_conflict_count, 1)
        self.assertEqual(state.trait_summaries["immediate_execution"].explicit_conflict_count, 1)
        # §5-3: 4개 완료 시점이어도 Conflict가 남아있으면 STOP할 수 없다.
        self.assertEqual(result.stop_decision, "CONTINUE")
        # 2026-08-22 리뷰 반영: 위치·테마와 무관하게 최우선으로 Explicit Conflict 확인
        # 질문(고정 문항)을 낸다 — 특정 Trait를 타깃하는 일반 질문이 아니다.
        self.assertEqual(result.next_planner_decision.contrast_resolution_id, "planning_vs_execution")
        self.assertEqual(result.next_planner_decision.purpose, "Explicit Conflict 확인 질문")
        self.assertEqual(state.pending_resolution_contrast_id, "planning_vs_execution")
        self.assertEqual(state.unresolved_contrast_ids, {"planning_vs_execution"})

    def test_evidence_outside_comparable_frame_does_not_mask_traits(self) -> None:
        """같은 두 Trait라도 "new_tool" Frame 밖(예: 시간 제약 상황)에서만 반대로
        나오면 Explicit Conflict가 아니다 — Mask되지 않고 정상적으로 STRONG까지 갈 수 있다."""

        state = self._fresh_state()
        submit_answer(
            state, GAME_SEED_01_FINALIZED, "game_seed_01_o1", VERTICAL_SLICE_TRAIT_IDS, True,
            VERTICAL_SLICE_CONTRAST_DEFINITIONS,
        )
        for i, (role_id, trait_id) in enumerate(
            [
                ("advance_planning", "planning"),
                ("quick_execution", "immediate_execution"),
            ],
            start=2,
        ):
            question = self._tail(f"game_tail_{i:02d}", role_id, trait_id, "limited_time_priority")
            submit_answer(
                state, question, f"game_tail_{i:02d}_o1", VERTICAL_SLICE_TRAIT_IDS, False,
                VERTICAL_SLICE_CONTRAST_DEFINITIONS,
            )

        self.assertEqual(state.unresolved_conflict_trait_ids, set())
        self.assertTrue(state.trait_summaries["planning"].context_dependency_flag)
        self.assertTrue(state.trait_summaries["immediate_execution"].context_dependency_flag)

    def test_answering_the_resolution_question_unmasks_traits_end_to_end(self) -> None:
        """2026-08-22 리뷰 반영 전체 흐름: 탐지 → 확인 질문이 다음 질문으로 배정됨 →
        학생이 "계획을 우선한다" 쪽으로 답함 → RESOLVED_POSITIVE로 해소 → 더 이상 Mask 안 됨.
        과거 Evidence(4개)는 그대로 남는다."""

        state = self._fresh_state()
        submit_answer(
            state, GAME_SEED_01_FINALIZED, "game_seed_01_o1", VERTICAL_SLICE_TRAIT_IDS, True,
            VERTICAL_SLICE_CONTRAST_DEFINITIONS, _RESOLUTION_ROLE_MAPS,
        )
        result = None
        for i, (role_id, trait_id) in enumerate(
            [
                ("advance_planning", "planning"),
                ("quick_execution", "immediate_execution"),
                ("advance_planning", "planning"),
                ("quick_execution", "immediate_execution"),
            ],
            start=2,
        ):
            question = self._tail(f"game_tail_{i:02d}", role_id, trait_id, "new_tool")
            result = submit_answer(
                state, question, f"game_tail_{i:02d}_o1", VERTICAL_SLICE_TRAIT_IDS, False,
                VERTICAL_SLICE_CONTRAST_DEFINITIONS, _RESOLUTION_ROLE_MAPS,
            )

        self.assertEqual(state.pending_resolution_contrast_id, "planning_vs_execution")
        evidence_count_before_resolution = len(state.evidence_ledger)

        # 다음 질문으로 확인 질문이 나온다(main.py의 /assessment/next-question이 하는 일과
        # 동일하게, 이 테스트에서는 직접 만든다).
        resolution_question = build_planning_vs_execution_resolution_question("game")
        result = submit_answer(
            state, resolution_question, f"{resolution_question.question_id}_o1", VERTICAL_SLICE_TRAIT_IDS, False,
            VERTICAL_SLICE_CONTRAST_DEFINITIONS, _RESOLUTION_ROLE_MAPS,
        )

        self.assertEqual(
            state.contrast_resolutions["planning_vs_execution"].status,
            ContrastResolutionStatus.RESOLVED_POSITIVE,
        )
        self.assertEqual(state.unresolved_conflict_trait_ids, set())
        self.assertEqual(state.unresolved_contrast_ids, set())
        self.assertIsNone(state.pending_resolution_contrast_id)
        # 과거 Evidence 보존 + 확인 질문 자체도 새 Evidence로 추가됨.
        self.assertEqual(len(state.evidence_ledger), evidence_count_before_resolution + 1)
        # 다음 질문 결정도 더 이상 확인 질문을 다시 요구하지 않는다.
        self.assertIsNone(result.next_planner_decision.contrast_resolution_id)


if __name__ == "__main__":
    unittest.main()
