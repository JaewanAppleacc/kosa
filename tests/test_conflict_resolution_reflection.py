"""2026-08-22 3차 리뷰 반영 테스트.

## 항목 1 — Stop/Continue보다 Conflict Resolution 질문이 우선순위를 가져야 한다(§5-3 버그 수정)
꼬리질문 개수 상한(6개)에 도달한 시점에 Explicit Conflict가 처음 감지되더라도, 확인
질문을 한 번은 반드시 물어봐야 한다. answer_graph._stop_or_continue의 우선순위 오버라이드를
end-to-end(submit_answer)로 검증한다.

## 항목 2 — Conflict Resolution 결과가 Profile·Matching에 반영돼야 한다
§12-1 확인 질문 답변(RESOLVED_POSITIVE/RESOLVED_OPPOSITE/RESOLVED_CONTEXT_DEPENDENT/
UNRESOLVED)이 Evidence를 지우거나 고치지 않으면서도 Profile 문장 선정(profile_engine)과
Matching 정규화 값(matching_engine)에 정성적으로만 반영되는지 확인한다.
"""

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
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAIT_IDS, VERTICAL_SLICE_TRAITS
from src.engines.matching_engine import compute_student_trait_states
from src.engines.profile_engine import _resolution_role_for_trait, select_profile_highlight_traits
from src.schemas.assessment_state import AssessmentState
from src.schemas.evidence import ContrastResolutionStatus

GAME_SEED_01_FINALIZED = seed_question_as_finalized(GAME_SEED_01)
TRAIT_DEFINITIONS_BY_ID = {t.trait_id: t for t in VERTICAL_SLICE_TRAITS}

# 확인 질문 선택지 role_id -> 그 role을 고르면 나오는 ContrastResolutionStatus
# (build_planning_vs_execution_resolution_question 참고)
_OPTION_INDEX_BY_STATUS = {
    ContrastResolutionStatus.RESOLVED_POSITIVE: 1,
    ContrastResolutionStatus.RESOLVED_CONTEXT_DEPENDENT: 2,
    ContrastResolutionStatus.RESOLVED_OPPOSITE: 3,
    ContrastResolutionStatus.UNRESOLVED: 4,
}


def _fresh_state() -> AssessmentState:
    return AssessmentState(session_id="sess_test", user_id="demo_user_01")


def _tail(question_id: str, role_id: str, trait_id: str, frame_id: str):
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


def _drive_conflict_to_detection(state: AssessmentState, *, filler_tail_count: int = 0) -> None:
    """Seed 답변 + (옵션) 무관한 필러 꼬리질문 + planning/immediate_execution이 상충하는
    4개 꼬리질문(new_tool Frame)을 순서대로 답변시켜, 정확히 마지막 답변에서 Explicit
    Conflict가 감지되게 만든다."""

    submit_answer(
        state, GAME_SEED_01_FINALIZED, "game_seed_01_o1", VERTICAL_SLICE_TRAIT_IDS, True,
        VERTICAL_SLICE_CONTRAST_DEFINITIONS, VERTICAL_SLICE_RESOLUTION_SPECS,
    )
    for i in range(filler_tail_count):
        qid = f"filler_{i:02d}"
        question = _tail(qid, "some_other_role", "collaboration_preference", "other_frame")
        submit_answer(
            state, question, f"{qid}_o1", VERTICAL_SLICE_TRAIT_IDS, False,
            VERTICAL_SLICE_CONTRAST_DEFINITIONS, VERTICAL_SLICE_RESOLUTION_SPECS,
        )

    result = None
    for i, (role_id, trait_id) in enumerate(
        [
            ("advance_planning", "planning"),
            ("quick_execution", "immediate_execution"),
            ("advance_planning", "planning"),
            ("quick_execution", "immediate_execution"),
        ],
        start=1,
    ):
        qid = f"conflict_tail_{i:02d}"
        question = _tail(qid, role_id, trait_id, "new_tool")
        result = submit_answer(
            state, question, f"{qid}_o1", VERTICAL_SLICE_TRAIT_IDS, False,
            VERTICAL_SLICE_CONTRAST_DEFINITIONS, VERTICAL_SLICE_RESOLUTION_SPECS,
        )
    return result


def _resolve_with(state: AssessmentState, status: ContrastResolutionStatus):
    """확인 질문에 답해서 준 status로 해소시키고, 그 submit_answer 결과를 반환한다."""

    resolution_question = build_planning_vs_execution_resolution_question("game")
    option_index = _OPTION_INDEX_BY_STATUS[status]
    return submit_answer(
        state, resolution_question, f"{resolution_question.question_id}_o{option_index}",
        VERTICAL_SLICE_TRAIT_IDS, False,
        VERTICAL_SLICE_CONTRAST_DEFINITIONS, VERTICAL_SLICE_RESOLUTION_SPECS,
    )


class StopConditionYieldsToResolutionQuestionTest(unittest.TestCase):
    """항목 1: 5개 required test."""

    def test_conflict_first_detected_on_sixth_question_still_returns_resolution_question(self) -> None:
        """Seed(1) + 필러 꼬리(1) + Conflict 꼬리 4개 = 6번째 답변에서 처음 감지돼도
        (§5-3 강제 STOP 경계인 6개에 도달한 시점) 세션이 바로 끝나지 않고 확인 질문이
        나와야 한다."""

        state = _fresh_state()
        result = _drive_conflict_to_detection(state, filler_tail_count=1)

        self.assertEqual(state.questions_asked_in_current_context, 6)
        self.assertEqual(result.stop_decision, "CONTINUE")
        self.assertEqual(result.next_planner_decision.contrast_resolution_id, "planning_vs_execution")
        self.assertEqual(state.pending_resolution_contrast_id, "planning_vs_execution")

    def test_answering_resolution_question_reenables_ordinary_stop_decision(self) -> None:
        """확인 질문에 답해 해소되고 나면, 더 이상 Conflict가 Stop/Continue를 강제로
        CONTINUE시키지 않고 원래의 §5-3 조건(개수+Gap)이 다시 적용돼야 한다. 검증을 위해
        all_trait_ids를 이 Contrast의 두 Trait만으로 좁혀서, 해소 후에는 Gap도 Conflict도
        없어 STOP이 나오는 걸 확인한다(해소 전이었다면 무조건 CONTINUE였을 상황)."""

        state = _fresh_state()
        narrow_trait_ids = {"planning", "immediate_execution"}
        submit_answer(
            state, GAME_SEED_01_FINALIZED, "game_seed_01_o1", narrow_trait_ids, True,
            VERTICAL_SLICE_CONTRAST_DEFINITIONS, VERTICAL_SLICE_RESOLUTION_SPECS,
        )
        for i, (role_id, trait_id) in enumerate(
            [
                ("advance_planning", "planning"),
                ("quick_execution", "immediate_execution"),
                ("advance_planning", "planning"),
                ("quick_execution", "immediate_execution"),
            ],
            start=1,
        ):
            qid = f"conflict_tail_{i:02d}"
            question = _tail(qid, role_id, trait_id, "new_tool")
            submit_answer(
                state, question, f"{qid}_o1", narrow_trait_ids, False,
                VERTICAL_SLICE_CONTRAST_DEFINITIONS, VERTICAL_SLICE_RESOLUTION_SPECS,
            )

        resolution_question = build_planning_vs_execution_resolution_question("game")
        result = submit_answer(
            state, resolution_question, f"{resolution_question.question_id}_o1", narrow_trait_ids, False,
            VERTICAL_SLICE_CONTRAST_DEFINITIONS, VERTICAL_SLICE_RESOLUTION_SPECS,
        )

        self.assertEqual(result.stop_decision, "STOP")

    def test_unresolved_resolution_answer_is_never_reasked(self) -> None:
        state = _fresh_state()
        _drive_conflict_to_detection(state)
        _resolve_with(state, ContrastResolutionStatus.UNRESOLVED)

        self.assertEqual(
            state.contrast_resolutions["planning_vs_execution"].status, ContrastResolutionStatus.UNRESOLVED
        )
        self.assertIsNone(state.pending_resolution_contrast_id)

        # 그 다음 일반 꼬리질문에서도 확인 질문이 다시 나오면 안 된다(무한 반복 방지) —
        # UNRESOLVED는 여전히 두 Trait를 Mask하지만, "다시 물어봄"과는 별개다.
        follow_up = _tail("follow_up_01", "some_other_role", "collaboration_preference", "other_frame")
        result = submit_answer(
            state, follow_up, "follow_up_01_o1", VERTICAL_SLICE_TRAIT_IDS, False,
            VERTICAL_SLICE_CONTRAST_DEFINITIONS, VERTICAL_SLICE_RESOLUTION_SPECS,
        )
        self.assertIsNone(result.next_planner_decision.contrast_resolution_id)
        self.assertEqual(state.unresolved_conflict_trait_ids, {"planning", "immediate_execution"})

    def test_no_conflict_stop_condition_unchanged(self) -> None:
        """Contrast가 전혀 감지되지 않는 세션에서는 기존 4~6개 Stop Condition이 그대로여야
        한다 — narrow all_trait_ids로 4개 꼬리질문 뒤 Gap도 Conflict도 없으면 STOP."""

        state = _fresh_state()
        narrow_trait_ids = {"causal_analysis"}
        submit_answer(
            state, GAME_SEED_01_FINALIZED, "game_seed_01_o1", narrow_trait_ids, True,
            VERTICAL_SLICE_CONTRAST_DEFINITIONS, VERTICAL_SLICE_RESOLUTION_SPECS,
        )
        result = None
        for i in range(2, 6):
            qid = f"causal_tail_{i:02d}"
            question = _tail(qid, "some_role", "causal_analysis", "other_frame")
            result = submit_answer(
                state, question, f"{qid}_o1", narrow_trait_ids, False,
                VERTICAL_SLICE_CONTRAST_DEFINITIONS, VERTICAL_SLICE_RESOLUTION_SPECS,
            )

        self.assertEqual(state.questions_asked_in_current_context, 5)  # seed 1 + tail 4
        self.assertEqual(result.stop_decision, "STOP")

    def test_already_resolved_conflict_is_never_reasked(self) -> None:
        state = _fresh_state()
        _drive_conflict_to_detection(state)
        _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        # 해소 이후 같은 role로 답변이 더 들어와도(같은 Contrast 조건을 다시 충족해도)
        # 확인 질문이 다시 나오면 안 된다.
        follow_up = _tail("follow_up_02", "advance_planning", "planning", "new_tool")
        result = submit_answer(
            state, follow_up, "follow_up_02_o1", VERTICAL_SLICE_TRAIT_IDS, False,
            VERTICAL_SLICE_CONTRAST_DEFINITIONS, VERTICAL_SLICE_RESOLUTION_SPECS,
        )
        self.assertIsNone(result.next_planner_decision.contrast_resolution_id)
        self.assertIsNone(state.pending_resolution_contrast_id)


class ResolutionReflectedInProfileAndMatchingTest(unittest.TestCase):
    """항목 2: 6개 required test. Evidence Ledger를 보존한 채 Profile/Matching에
    정성적으로만 반영되는지 확인한다."""

    def _run_to_resolution(self, status: ContrastResolutionStatus) -> tuple[AssessmentState, object]:
        state = _fresh_state()
        _drive_conflict_to_detection(state)
        evidence_before = list(state.evidence_ledger)
        result = _resolve_with(state, status)
        return state, evidence_before, result

    def test_resolved_positive_prioritizes_positive_trait(self) -> None:
        state, _, _ = self._run_to_resolution(ContrastResolutionStatus.RESOLVED_POSITIVE)
        record = state.contrast_resolutions["planning_vs_execution"]
        self.assertEqual(record.preferred_trait_id, "planning")
        self.assertEqual(record.opposite_trait_id, "immediate_execution")

        # 해소 여부와 무관한 "원래(damping 전)" 정규화 값 — 두 Trait는 같은 개수·같은
        # Context의 Evidence를 쌓았으므로 damping이 없다면 값이 같아야 한다.
        baseline_states = compute_student_trait_states(
            state.trait_summaries, TRAIT_DEFINITIONS_BY_ID, state.unresolved_conflict_trait_ids,
        )
        baseline_value = baseline_states["planning"].normalized_value
        self.assertEqual(baseline_value, baseline_states["immediate_execution"].normalized_value)

        matching_states = compute_student_trait_states(
            state.trait_summaries, TRAIT_DEFINITIONS_BY_ID, state.unresolved_conflict_trait_ids,
            state.contrast_resolutions,
        )
        # preferred 쪽은 damping 없이 원래 값 그대로, deprioritized 쪽만 완화된다(0으로
        # 만들지 않는다는 정책 그대로 — 값이 남아있되 baseline보다는 작다).
        self.assertEqual(matching_states["planning"].normalized_value, baseline_value)
        self.assertLess(matching_states["immediate_execution"].normalized_value, baseline_value)
        self.assertGreater(matching_states["immediate_execution"].normalized_value, 0)

        # 문장 선정(select_profile_highlight_traits)이 어떤 Trait를 top-N으로 뽑든, "이
        # Trait가 이 Resolution에서 어떤 역할인지" 자체는 항상 정확해야 한다.
        self.assertEqual(_resolution_role_for_trait("planning", state.contrast_resolutions), "preferred")
        self.assertEqual(
            _resolution_role_for_trait("immediate_execution", state.contrast_resolutions), "deprioritized"
        )

    def test_resolved_opposite_prioritizes_opposite_trait(self) -> None:
        state, _, _ = self._run_to_resolution(ContrastResolutionStatus.RESOLVED_OPPOSITE)
        record = state.contrast_resolutions["planning_vs_execution"]
        self.assertEqual(record.preferred_trait_id, "immediate_execution")
        self.assertEqual(record.opposite_trait_id, "planning")

        baseline_states = compute_student_trait_states(
            state.trait_summaries, TRAIT_DEFINITIONS_BY_ID, state.unresolved_conflict_trait_ids,
        )
        baseline_value = baseline_states["immediate_execution"].normalized_value

        matching_states = compute_student_trait_states(
            state.trait_summaries, TRAIT_DEFINITIONS_BY_ID, state.unresolved_conflict_trait_ids,
            state.contrast_resolutions,
        )
        self.assertEqual(matching_states["immediate_execution"].normalized_value, baseline_value)
        self.assertLess(matching_states["planning"].normalized_value, baseline_value)
        self.assertGreater(matching_states["planning"].normalized_value, 0)

        self.assertEqual(
            _resolution_role_for_trait("immediate_execution", state.contrast_resolutions), "preferred"
        )
        self.assertEqual(_resolution_role_for_trait("planning", state.contrast_resolutions), "deprioritized")

    def test_resolved_context_dependent_expresses_both_as_context_dependent(self) -> None:
        state, _, _ = self._run_to_resolution(ContrastResolutionStatus.RESOLVED_CONTEXT_DEPENDENT)
        record = state.contrast_resolutions["planning_vs_execution"]
        self.assertIsNone(record.preferred_trait_id)
        self.assertIsNone(record.opposite_trait_id)
        self.assertEqual(set(record.context_dependent_trait_ids), {"planning", "immediate_execution"})

        # Context-dependent는 Matching에서 어느 쪽도 완화(damping)되지 않는다 — 둘 다
        # 존재하는 성향으로 취급한다.
        baseline_states = compute_student_trait_states(
            state.trait_summaries, TRAIT_DEFINITIONS_BY_ID, state.unresolved_conflict_trait_ids,
        )
        matching_states = compute_student_trait_states(
            state.trait_summaries, TRAIT_DEFINITIONS_BY_ID, state.unresolved_conflict_trait_ids,
            state.contrast_resolutions,
        )
        self.assertEqual(
            matching_states["planning"].normalized_value, baseline_states["planning"].normalized_value
        )
        self.assertEqual(
            matching_states["immediate_execution"].normalized_value,
            baseline_states["immediate_execution"].normalized_value,
        )

        candidates = select_profile_highlight_traits(
            state.trait_summaries, TRAIT_DEFINITIONS_BY_ID, state.unresolved_conflict_trait_ids,
            state.contrast_resolutions,
        )
        by_id = {c.trait_definition.trait_id: c for c in candidates}
        self.assertEqual(by_id["planning"].resolution_role, "context_dependent")
        self.assertEqual(by_id["immediate_execution"].resolution_role, "context_dependent")

    def test_unresolved_uses_neither_trait_as_confirmed_basis(self) -> None:
        state, _, _ = self._run_to_resolution(ContrastResolutionStatus.UNRESOLVED)
        record = state.contrast_resolutions["planning_vs_execution"]
        self.assertIsNone(record.preferred_trait_id)
        self.assertIsNone(record.opposite_trait_id)
        self.assertEqual(record.context_dependent_trait_ids, [])

        # UNRESOLVED는 §12-1 그대로 unresolved_conflict_trait_ids에 남아 계속 Mask된다 —
        # Matching에서 normalized_value가 None(확정 근거로 안 씀).
        self.assertEqual(state.unresolved_conflict_trait_ids, {"planning", "immediate_execution"})
        matching_states = compute_student_trait_states(
            state.trait_summaries, TRAIT_DEFINITIONS_BY_ID, state.unresolved_conflict_trait_ids,
            state.contrast_resolutions,
        )
        self.assertIsNone(matching_states["planning"].normalized_value)
        self.assertIsNone(matching_states["immediate_execution"].normalized_value)

    def test_existing_evidence_records_are_not_deleted_or_altered(self) -> None:
        state, evidence_before, _ = self._run_to_resolution(ContrastResolutionStatus.RESOLVED_POSITIVE)

        # 해소 전 4개(Seed 제외 Conflict 관련 4개 + Seed 1개 = 5개)는 그대로 남아있어야 하고,
        # 값도 변형되지 않아야 한다. 확인 질문 자체가 새 Evidence로 1개 추가된다.
        self.assertEqual(len(state.evidence_ledger), len(evidence_before) + 1)
        for before, after in zip(evidence_before, state.evidence_ledger[: len(evidence_before)]):
            self.assertEqual(before, after)

    def test_session_without_any_resolution_is_unaffected(self) -> None:
        """Contrast가 아예 없는(또는 아직 해소되지 않은) 세션은 resolutions=None을 넘기던
        예전 호출과 동일한 결과를 내야 한다(하위 호환)."""

        state = _fresh_state()
        submit_answer(
            state, GAME_SEED_01_FINALIZED, "game_seed_01_o1", VERTICAL_SLICE_TRAIT_IDS, True,
        )

        states_without_resolutions_arg = compute_student_trait_states(
            state.trait_summaries, TRAIT_DEFINITIONS_BY_ID, state.unresolved_conflict_trait_ids,
        )
        states_with_empty_resolutions = compute_student_trait_states(
            state.trait_summaries, TRAIT_DEFINITIONS_BY_ID, state.unresolved_conflict_trait_ids,
            state.contrast_resolutions,
        )
        self.assertEqual(states_without_resolutions_arg, states_with_empty_resolutions)

        candidates_without = select_profile_highlight_traits(
            state.trait_summaries, TRAIT_DEFINITIONS_BY_ID, state.unresolved_conflict_trait_ids,
        )
        candidates_with_empty = select_profile_highlight_traits(
            state.trait_summaries, TRAIT_DEFINITIONS_BY_ID, state.unresolved_conflict_trait_ids,
            state.contrast_resolutions,
        )
        self.assertEqual(candidates_without, candidates_with_empty)


if __name__ == "__main__":
    unittest.main()
