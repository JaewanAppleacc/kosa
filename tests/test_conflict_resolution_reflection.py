"""2026-08-22 3차 리뷰 반영 테스트.

## 항목 1 — Stop/Continue보다 Conflict Resolution 질문이 우선순위를 가져야 한다(§5-3 버그 수정)
꼬리질문 개수 상한(6개)에 도달한 시점에 Explicit Conflict가 처음 감지되더라도, 확인
질문을 한 번은 반드시 물어봐야 한다. answer_graph._stop_or_continue의 우선순위 오버라이드를
end-to-end(submit_answer)로 검증한다.

## 항목 2 — Conflict Resolution 결과가 Profile·Matching에 반영돼야 한다
§12-1 확인 질문 답변(RESOLVED_POSITIVE/RESOLVED_OPPOSITE/RESOLVED_CONTEXT_DEPENDENT/
UNRESOLVED)이 Evidence를 지우거나 고치지 않으면서도 Profile 문장 선정(profile_engine)과
Matching 정규화 값(matching_engine)에 정성적으로만 반영되는지 확인한다.

## 2026-08-22 4차 리뷰 — Resolution 답변과 일반 Trait Evidence 분리
확인 질문 답변이 EvidenceOrigin.CONFLICT_RESOLUTION으로 따로 표시돼, 일반 Trait 집계
(support_count/opportunity_count/context_count/distinct_frame_count)와 일반 Explicit
Conflict 재탐지에서 제외되는지 확인한다. Ledger·답변 이력에는 그대로 남아야 한다
(ResolutionEvidenceSeparationTest).

## 2026-08-22 5차 리뷰 — Resolution 답변이 일반 Adaptive 상태를 오염시키지 않아야 한다
일반 Seed·꼬리질문 답변은 다음 Adaptive 질문 생성을 위한 상태(pending_next_probe,
pending_previous_question_text, pending_previous_answer_text, recent_target_trait_ids,
used_frame_ids_in_current_context, offered_trait_ids_by_question,
questions_asked_in_current_context, current_context_seed_trait_id)를 갱신하지만,
Conflict Resolution 답변은 답변 이력과 Resolution 해석 정보만 갱신하고 이 상태들은
"마지막 일반 질문" 기준 그대로 유지해야 한다(AdaptiveStateNotPollutedByResolutionTest,
ResolutionRecordKeptTest, SubsequentQuestionFlowTest).
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
from src.engines.conflict_engine import detect_explicit_conflicts
from src.schemas.assessment_state import AssessmentState
from src.schemas.evidence import ContrastResolutionStatus, EvidenceOrigin

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


class ResolutionEvidenceSeparationTest(unittest.TestCase):
    """2026-08-22 4차 리뷰 항목 2: 확인 질문 답변은 EvidenceOrigin.CONFLICT_RESOLUTION으로
    구분되고, 일반 Trait 집계·재탐지에서 제외되지만 Ledger·답변 이력에는 남아야 한다."""

    def test_resolution_answer_is_kept_in_evidence_ledger_and_answer_history(self) -> None:
        state = _fresh_state()
        _drive_conflict_to_detection(state)
        evidence_count_before = len(state.evidence_ledger)
        answers_count_before = len(state.answers)

        _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        # Ledger에도, 별도 답변 이력(state.answers)에도 새 항목이 남는다 — 삭제하지 않는다.
        self.assertEqual(len(state.evidence_ledger), evidence_count_before + 1)
        self.assertEqual(len(state.answers), answers_count_before + 1)
        resolution_record = state.evidence_ledger[-1]
        resolution_question = build_planning_vs_execution_resolution_question("game")
        self.assertEqual(resolution_record.question_id, resolution_question.question_id)
        self.assertEqual(resolution_record.option_text, resolution_question.options[0].text)

    def test_resolution_answer_evidence_origin_is_distinct_from_ordinary_answers(self) -> None:
        state = _fresh_state()
        _drive_conflict_to_detection(state)
        # 해소 전 5개(Seed 1 + Conflict 꼬리 4)는 전부 일반 질문 Evidence다.
        for record in state.evidence_ledger:
            self.assertEqual(record.evidence_origin, EvidenceOrigin.PRIMARY_BLUEPRINT)

        _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        self.assertEqual(state.evidence_ledger[-1].evidence_origin, EvidenceOrigin.CONFLICT_RESOLUTION)
        # 과거 5개는 여전히 PRIMARY_BLUEPRINT 그대로다.
        for record in state.evidence_ledger[:-1]:
            self.assertEqual(record.evidence_origin, EvidenceOrigin.PRIMARY_BLUEPRINT)

    def test_existing_primary_evidence_records_unchanged_by_resolution(self) -> None:
        state = _fresh_state()
        _drive_conflict_to_detection(state)
        evidence_before = list(state.evidence_ledger)

        _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        for before, after in zip(evidence_before, state.evidence_ledger[: len(evidence_before)]):
            self.assertEqual(before, after)

    def test_resolution_answer_does_not_increase_support_count(self) -> None:
        state = _fresh_state()
        _drive_conflict_to_detection(state)
        support_before = state.trait_summaries["planning"].support_count

        # RESOLVED_POSITIVE로 답하면(선호 Trait=planning) 일반 Evidence였다면 planning의
        # support_count가 +1 됐을 것이다 — CONFLICT_RESOLUTION으로 분리됐으므로 안 늘어야 한다.
        _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        self.assertEqual(state.trait_summaries["planning"].support_count, support_before)

    def test_resolution_answer_does_not_increase_opportunity_count(self) -> None:
        state = _fresh_state()
        _drive_conflict_to_detection(state)
        # 확인 질문 선택지 5개 중엔 collaboration_preference/information_comparison도
        # 포함된다(filler_ask_others/filler_research_first) — 이 Trait들의
        # opportunity_count도 늘면 안 된다.
        opportunity_before = {
            trait_id: state.trait_summaries[trait_id].opportunity_count
            for trait_id in ("planning", "immediate_execution", "collaboration_preference", "information_comparison")
        }

        _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        for trait_id, before in opportunity_before.items():
            self.assertEqual(
                state.trait_summaries[trait_id].opportunity_count, before,
                f"{trait_id}의 opportunity_count가 확인 질문 답변으로 바뀌면 안 됩니다.",
            )

    def test_resolution_answer_does_not_change_context_or_frame_diversity(self) -> None:
        state = _fresh_state()
        _drive_conflict_to_detection(state)
        before = {
            trait_id: (
                state.trait_summaries[trait_id].context_count,
                state.trait_summaries[trait_id].distinct_frame_count,
            )
            for trait_id in ("planning", "immediate_execution")
        }

        _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        for trait_id, (context_count, frame_count) in before.items():
            self.assertEqual(state.trait_summaries[trait_id].context_count, context_count)
            self.assertEqual(state.trait_summaries[trait_id].distinct_frame_count, frame_count)

    def test_resolution_answer_does_not_create_new_explicit_conflict(self) -> None:
        """확인 질문 자체의 role_id(consistent_planning 등)는 어떤 ContrastDefinition의
        positive_role_ids/opposite_role_ids에도 없고, 이제는 evidence_origin도 달라
        detect_explicit_conflicts가 아예 보지 않는다 — 확인 질문 답변 자체가 새로운
        Explicit Conflict를 만들지 않아야 한다."""

        state = _fresh_state()
        _drive_conflict_to_detection(state)
        _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        # 해소 직후 재탐지 — 이미 RESOLVED_POSITIVE라 "resolved" 처리되지만, 그 판정이
        # 확인 질문 자신의 Evidence 때문이 아니라 저장된 ContrastResolutionRecord 때문임을
        # 확인하기 위해, 이 Contrast를 완전히 새 이름으로 다시 붙여 evidence만으로 재탐지한다.
        from src.schemas.evidence import ContrastDefinition

        probe_definition = ContrastDefinition(
            contrast_id="probe_only_resolution_role_ids",
            construct_id="probe",
            positive_role_ids=["consistent_planning"],
            opposite_role_ids=["consistent_execution"],
            comparable_frame_ids=["new_tool"],
            condition_scope="probe",
            minimum_evidence_each_side=1,
            description="확인 질문 role_id만으로 만든 진단용 Contrast — 실제 데이터에는 없다.",
        )
        result = detect_explicit_conflicts(state.evidence_ledger, [probe_definition], {})
        self.assertEqual(
            result.pair_results[0].status, "insufficient_evidence",
            "확인 질문 답변(CONFLICT_RESOLUTION)이 detect_explicit_conflicts의 Evidence로 잡히면 안 됩니다.",
        )

    def test_resolved_positive_still_reflected_in_profile_and_matching(self) -> None:
        state, _, _ = self._run_to_resolution(ContrastResolutionStatus.RESOLVED_POSITIVE)
        self.assertEqual(state.contrast_resolutions["planning_vs_execution"].preferred_trait_id, "planning")
        matching_states = compute_student_trait_states(
            state.trait_summaries, TRAIT_DEFINITIONS_BY_ID, state.unresolved_conflict_trait_ids,
            state.contrast_resolutions,
        )
        self.assertIsNotNone(matching_states["planning"].normalized_value)

    def test_resolved_opposite_still_reflected_in_profile_and_matching(self) -> None:
        state, _, _ = self._run_to_resolution(ContrastResolutionStatus.RESOLVED_OPPOSITE)
        self.assertEqual(state.contrast_resolutions["planning_vs_execution"].preferred_trait_id, "immediate_execution")
        matching_states = compute_student_trait_states(
            state.trait_summaries, TRAIT_DEFINITIONS_BY_ID, state.unresolved_conflict_trait_ids,
            state.contrast_resolutions,
        )
        self.assertIsNotNone(matching_states["immediate_execution"].normalized_value)

    def test_resolved_context_dependent_still_expressed_qualitatively(self) -> None:
        state, _, _ = self._run_to_resolution(ContrastResolutionStatus.RESOLVED_CONTEXT_DEPENDENT)
        record = state.contrast_resolutions["planning_vs_execution"]
        self.assertEqual(set(record.context_dependent_trait_ids), {"planning", "immediate_execution"})
        self.assertEqual(
            _resolution_role_for_trait("planning", state.contrast_resolutions), "context_dependent"
        )

    def test_unresolved_still_masks_and_is_not_reasked(self) -> None:
        state, _, _ = self._run_to_resolution(ContrastResolutionStatus.UNRESOLVED)
        self.assertEqual(state.unresolved_conflict_trait_ids, {"planning", "immediate_execution"})
        self.assertIsNone(state.pending_resolution_contrast_id)

        follow_up = _tail("follow_up_03", "some_other_role", "collaboration_preference", "other_frame")
        result = submit_answer(
            state, follow_up, "follow_up_03_o1", VERTICAL_SLICE_TRAIT_IDS, False,
            VERTICAL_SLICE_CONTRAST_DEFINITIONS, VERTICAL_SLICE_RESOLUTION_SPECS,
        )
        self.assertIsNone(result.next_planner_decision.contrast_resolution_id)

    def test_ordinary_seed_and_tail_evidence_calculation_unaffected(self) -> None:
        """Resolution 답변이 아예 없는 일반 흐름(Seed + 꼬리 4개)의 Trait Summary 계산
        결과가 이번 변경 전후로 동일해야 한다 — origin 필터링은 CONFLICT_RESOLUTION에만
        새로 영향을 주고, 기존 PRIMARY_BLUEPRINT 경로는 손대지 않았음을 확인한다."""

        state = _fresh_state()
        submit_answer(
            state, GAME_SEED_01_FINALIZED, "game_seed_01_o1", VERTICAL_SLICE_TRAIT_IDS, True,
        )
        for i, option in enumerate(GAME_SEED_01_FINALIZED.options[1:], start=2):
            fake_tail = GAME_SEED_01_FINALIZED.model_copy(
                update={
                    "question_id": f"ordinary_tail_{i:02d}",
                    "frame_id": f"frame_{i}",
                    "target_traits": list(option.primary_trait_delta.keys()),
                    "options": [
                        o.model_copy(update={"option_id": f"ordinary_tail_{i:02d}_o{j}"})
                        for j, o in enumerate(GAME_SEED_01_FINALIZED.options, start=1)
                    ],
                }
            )
            selected_option_id = f"ordinary_tail_{i:02d}_o{i}"
            submit_answer(state, fake_tail, selected_option_id, VERTICAL_SLICE_TRAIT_IDS, False)

        self.assertEqual(state.questions_asked_in_current_context, 5)  # seed 1 + tail 4
        self.assertEqual(state.trait_summaries["causal_analysis"].support_count, 1)
        self.assertEqual(state.trait_summaries["visual_expression"].opportunity_count, 0)
        for record in state.evidence_ledger:
            self.assertEqual(record.evidence_origin, EvidenceOrigin.PRIMARY_BLUEPRINT)

    def _run_to_resolution(self, status: ContrastResolutionStatus):
        state = _fresh_state()
        _drive_conflict_to_detection(state)
        evidence_before = list(state.evidence_ledger)
        result = _resolve_with(state, status)
        return state, evidence_before, result


class AdaptiveStateNotPollutedByResolutionTest(unittest.TestCase):
    """2026-08-22 5차 리뷰 — "Adaptive 상태 보존" 필수 테스트 1~9."""

    def test_pending_next_probe_unchanged_by_resolution(self) -> None:
        state = _fresh_state()
        _drive_conflict_to_detection(state)
        before = state.pending_next_probe
        self.assertIsNotNone(before)

        _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        self.assertEqual(state.pending_next_probe, before)

    def test_pending_previous_question_text_stays_at_last_ordinary_question(self) -> None:
        state = _fresh_state()
        _drive_conflict_to_detection(state)
        before = state.pending_previous_question_text
        self.assertEqual(before, GAME_SEED_01_FINALIZED.question_text)

        _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        # 확인 질문의 question_text("새로운 과제나 도구를 접했을 때...")로 덮이면 안 된다.
        self.assertEqual(state.pending_previous_question_text, before)
        resolution_question = build_planning_vs_execution_resolution_question("game")
        self.assertNotEqual(state.pending_previous_question_text, resolution_question.question_text)

    def test_pending_previous_answer_text_stays_at_last_ordinary_answer(self) -> None:
        state = _fresh_state()
        _drive_conflict_to_detection(state)
        before = state.pending_previous_answer_text
        self.assertIsNotNone(before)

        _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        self.assertEqual(state.pending_previous_answer_text, before)

    def test_recent_target_trait_ids_unchanged_by_resolution(self) -> None:
        state = _fresh_state()
        _drive_conflict_to_detection(state)
        before = list(state.recent_target_trait_ids)

        _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        self.assertEqual(state.recent_target_trait_ids, before)

    def test_used_frame_ids_does_not_include_resolution_frame(self) -> None:
        state = _fresh_state()
        _drive_conflict_to_detection(state)
        before = list(state.used_frame_ids_in_current_context)

        _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        resolution_question = build_planning_vs_execution_resolution_question("game")
        self.assertEqual(state.used_frame_ids_in_current_context, before)
        self.assertNotIn(resolution_question.frame_id, [
            f for f in state.used_frame_ids_in_current_context if f not in before
        ])

    def test_offered_trait_ids_by_question_excludes_resolution_question(self) -> None:
        state = _fresh_state()
        _drive_conflict_to_detection(state)
        before_keys = set(state.offered_trait_ids_by_question)

        _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        resolution_question = build_planning_vs_execution_resolution_question("game")
        self.assertEqual(set(state.offered_trait_ids_by_question), before_keys)
        self.assertNotIn(resolution_question.question_id, state.offered_trait_ids_by_question)

    def test_ordinary_question_counter_unchanged_by_resolution(self) -> None:
        state = _fresh_state()
        _drive_conflict_to_detection(state)
        before = state.questions_asked_in_current_context
        self.assertEqual(before, 5)  # seed 1 + conflict 꼬리 4

        _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        self.assertEqual(state.questions_asked_in_current_context, before)

    def test_resolution_counter_increments_by_exactly_one(self) -> None:
        state = _fresh_state()
        _drive_conflict_to_detection(state)
        self.assertEqual(state.resolution_questions_asked_in_current_context, 0)

        _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        self.assertEqual(state.resolution_questions_asked_in_current_context, 1)

    def test_current_context_seed_trait_id_unchanged_by_resolution(self) -> None:
        state = _fresh_state()
        _drive_conflict_to_detection(state)
        before = state.current_context_seed_trait_id
        self.assertIsNotNone(before)

        _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        self.assertEqual(state.current_context_seed_trait_id, before)


class ResolutionRecordKeptTest(unittest.TestCase):
    """2026-08-22 5차 리뷰 — "Resolution 기록 유지" 필수 테스트 10~16."""

    def test_resolution_answer_recorded_in_answers_history(self) -> None:
        state = _fresh_state()
        _drive_conflict_to_detection(state)
        answers_before = len(state.answers)
        resolution_question = build_planning_vs_execution_resolution_question("game")

        _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        self.assertEqual(len(state.answers), answers_before + 1)
        self.assertEqual(state.answers[-1].question_id, resolution_question.question_id)

    def test_resolution_evidence_kept_in_ledger(self) -> None:
        state = _fresh_state()
        _drive_conflict_to_detection(state)
        evidence_before = len(state.evidence_ledger)

        _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        self.assertEqual(len(state.evidence_ledger), evidence_before + 1)

    def test_resolution_evidence_origin_is_conflict_resolution(self) -> None:
        state = _fresh_state()
        _drive_conflict_to_detection(state)
        _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        self.assertEqual(state.evidence_ledger[-1].evidence_origin, EvidenceOrigin.CONFLICT_RESOLUTION)

    def test_resolution_evidence_source_type_is_conflict_resolution_question(self) -> None:
        state = _fresh_state()
        _drive_conflict_to_detection(state)
        _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        self.assertEqual(state.evidence_ledger[-1].source_type, "conflict_resolution_question")
        # 일반 질문(Seed·꼬리)의 source_type은 그대로 유지된다.
        self.assertEqual(state.evidence_ledger[0].source_type, "seed_question")
        self.assertEqual(state.evidence_ledger[1].source_type, "generated_question")

    def test_contrast_resolution_record_created(self) -> None:
        state = _fresh_state()
        _drive_conflict_to_detection(state)
        _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        self.assertIn("planning_vs_execution", state.contrast_resolutions)
        self.assertEqual(
            state.contrast_resolutions["planning_vs_execution"].status,
            ContrastResolutionStatus.RESOLVED_POSITIVE,
        )

    def test_resolved_at_answer_id_matches_resolution_evidence_answer_id(self) -> None:
        state = _fresh_state()
        _drive_conflict_to_detection(state)
        _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        record = state.contrast_resolutions["planning_vs_execution"]
        self.assertEqual(record.resolved_at_answer_id, state.evidence_ledger[-1].answer_id)

    def test_reason_option_id_matches_selected_option(self) -> None:
        state = _fresh_state()
        _drive_conflict_to_detection(state)
        resolution_question = build_planning_vs_execution_resolution_question("game")
        selected_option_id = f"{resolution_question.question_id}_o1"

        _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        record = state.contrast_resolutions["planning_vs_execution"]
        self.assertEqual(record.reason_option_id, selected_option_id)


class SubsequentQuestionFlowTest(unittest.TestCase):
    """2026-08-22 5차 리뷰 — "후속 질문 흐름" 필수 테스트 17~21."""

    def test_resolving_before_max_ordinary_questions_plans_next_ordinary_question(self) -> None:
        """일반 문항 수(5개: seed 1 + 꼬리 4)가 강제 STOP 경계(6개)에 못 미친 상태에서
        Conflict를 해소하면, 세션이 끝나지 않고 다음 일반 질문 계획이 나와야 한다."""

        state = _fresh_state()
        _drive_conflict_to_detection(state)  # 여기서 5개(< 6) — 아직 강제 STOP 아님
        result = _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        self.assertEqual(result.stop_decision, "CONTINUE")
        self.assertIsNotNone(result.next_planner_decision)
        self.assertIsNone(result.next_planner_decision.contrast_resolution_id)

    def test_planner_recent_trait_frame_history_matches_pre_resolution_state(self) -> None:
        """Target Planner가 참고하는 recent_target_trait_ids/used_frame_ids는 확인 질문
        답변 이전과 동일해야 한다(target_planner.decide_next_target 호출 시점 값 검증)."""

        state = _fresh_state()
        _drive_conflict_to_detection(state)
        recent_traits_before = list(state.recent_target_trait_ids)
        used_frames_before = list(state.used_frame_ids_in_current_context)

        _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        self.assertEqual(state.recent_target_trait_ids, recent_traits_before)
        self.assertEqual(state.used_frame_ids_in_current_context, used_frames_before)

    def test_next_llm_question_generation_inputs_use_last_ordinary_question(self) -> None:
        """main.py의 /assessment/next-question이 generate_tail_question에 그대로 넘기는
        세 값(previous_question_text/previous_answer_text/previous_next_probe)이 확인
        질문이 아니라 마지막 일반 질문·답변 기준이어야 한다."""

        state = _fresh_state()
        _drive_conflict_to_detection(state)
        expected_previous_question_text = state.pending_previous_question_text
        expected_previous_answer_text = state.pending_previous_answer_text
        expected_previous_next_probe = state.pending_next_probe

        _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        self.assertEqual(state.pending_previous_question_text, expected_previous_question_text)
        self.assertEqual(state.pending_previous_answer_text, expected_previous_answer_text)
        self.assertEqual(state.pending_next_probe, expected_previous_next_probe)

    def test_reaching_max_ordinary_questions_then_resolving_ends_session(self) -> None:
        """§5-3: 강제 STOP은 "꼬리질문 6개"(tail_questions_asked = questions_asked_in_
        current_context - 1, Seed 제외) 기준이다. 필러 꼬리 2개를 더 넣어 Seed(1) + 필러
        꼬리(2) + Conflict 꼬리(4) = 7개(꼬리 6개, 강제 STOP 경계)에서 Conflict가 감지되게
        만든 뒤, 해소하면 확인 질문 답변으로 일반 질문 카운터가 추가로 늘지 않았으므로
        여전히 꼬리 6개 경계에 있어 추가 일반 질문 없이 세션이 정상 종료(STOP)돼야 한다."""

        state = _fresh_state()
        _drive_conflict_to_detection(state, filler_tail_count=2)  # 7개(꼬리 6개, 강제 STOP 경계)에서 감지
        self.assertEqual(state.questions_asked_in_current_context, 7)

        result = _resolve_with(state, ContrastResolutionStatus.RESOLVED_POSITIVE)

        self.assertEqual(result.stop_decision, "STOP")
        self.assertIsNone(result.next_planner_decision)
        # 해소 이후에도 일반 질문 카운터는 7에 머문다 — 확인 질문 답변으로 추가 증가 없음.
        self.assertEqual(state.questions_asked_in_current_context, 7)

    def test_unresolved_masks_and_is_not_reasked(self) -> None:
        state = _fresh_state()
        _drive_conflict_to_detection(state)
        _resolve_with(state, ContrastResolutionStatus.UNRESOLVED)

        self.assertEqual(state.unresolved_conflict_trait_ids, {"planning", "immediate_execution"})
        self.assertIsNone(state.pending_resolution_contrast_id)

        follow_up = _tail("follow_up_04", "some_other_role", "collaboration_preference", "other_frame")
        result = submit_answer(
            state, follow_up, "follow_up_04_o1", VERTICAL_SLICE_TRAIT_IDS, False,
            VERTICAL_SLICE_CONTRAST_DEFINITIONS, VERTICAL_SLICE_RESOLUTION_SPECS,
        )
        self.assertIsNone(result.next_planner_decision.contrast_resolution_id)


class OrdinaryAnswerStillUpdatesAdaptiveStateRegressionTest(unittest.TestCase):
    """2026-08-22 5차 리뷰 — "회귀 확인" 22~23: is_resolution_answer 분기가 일반 질문
    경로에서 여전히 Adaptive 상태를 정상적으로 갱신하는지(음성 테스트만으론 이걸
    증명 못 한다 — 양성 테스트로 직접 확인한다)."""

    def test_ordinary_seed_answer_updates_adaptive_state(self) -> None:
        state = _fresh_state()
        submit_answer(
            state, GAME_SEED_01_FINALIZED, "game_seed_01_o1", VERTICAL_SLICE_TRAIT_IDS, True,
        )

        self.assertEqual(state.pending_previous_question_text, GAME_SEED_01_FINALIZED.question_text)
        self.assertEqual(state.pending_previous_answer_text, GAME_SEED_01_FINALIZED.options[0].text)
        self.assertEqual(state.pending_next_probe, GAME_SEED_01_FINALIZED.options[0].next_probe)
        self.assertEqual(state.questions_asked_in_current_context, 1)
        self.assertIsNotNone(state.current_context_seed_trait_id)
        self.assertIn(GAME_SEED_01_FINALIZED.question_id, state.offered_trait_ids_by_question)

    def test_ordinary_tail_answer_updates_adaptive_state(self) -> None:
        state = _fresh_state()
        submit_answer(
            state, GAME_SEED_01_FINALIZED, "game_seed_01_o1", VERTICAL_SLICE_TRAIT_IDS, True,
        )
        tail = _tail("ordinary_tail_check_01", "advance_planning", "planning", "new_tool")
        submit_answer(
            state, tail, "ordinary_tail_check_01_o1", VERTICAL_SLICE_TRAIT_IDS, False,
        )

        self.assertEqual(state.pending_previous_question_text, tail.question_text)
        self.assertEqual(state.questions_asked_in_current_context, 2)
        self.assertIn(tail.question_id, state.offered_trait_ids_by_question)
        self.assertIn(tail.frame_id, state.used_frame_ids_in_current_context)
        self.assertIn("planning", state.recent_target_trait_ids)


if __name__ == "__main__":
    unittest.main()
