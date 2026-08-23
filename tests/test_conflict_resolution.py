"""2026-08-22 리뷰 반영: Explicit Conflict "탐지"와 "해소"를 분리한 로직(§12-1 확장)
테스트. Evidence가 계속 쌓여도 저절로 해소되지 않는다는 버그 수정과, 확인 질문 답변으로만
해소된다는 새 계약을 손계산으로 검증한다.
"""

from __future__ import annotations

import unittest

from src.engines.conflict_engine import detect_explicit_conflicts
from src.schemas.evidence import (
    ContrastDefinition,
    ContrastResolutionRecord,
    ContrastResolutionStatus,
    EvidenceRecord,
    EvidenceOrigin,
)


def _evidence(evidence_id: str, role_id: str, frame_id: str, trait_delta: dict[str, int]) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        answer_id=f"ans_{evidence_id}",
        question_id=f"q_{evidence_id}",
        question_frame_id=frame_id,
        option_role_id=role_id,
        option_text="테스트 선택지",
        applied_primary_trait_delta=trait_delta,
        evidence_origin=EvidenceOrigin.PRIMARY_BLUEPRINT,
        context="game",
        source_type="generated_question",
        generator_version="v1",
        quality_gate_status="passed",
    )


CONTRAST = ContrastDefinition(
    contrast_id="planning_vs_execution",
    construct_id="approach_timing",
    positive_role_ids=["task_planning", "advance_planning"],
    opposite_role_ids=["quick_execution", "direct_trial"],
    comparable_frame_ids=["new_tool"],
    condition_scope="테스트",
    minimum_evidence_each_side=2,
    description="테스트용",
)

_CONFLICT_LEDGER = [
    _evidence("e1", "task_planning", "new_tool", {"planning": 1}),
    _evidence("e2", "advance_planning", "new_tool", {"planning": 1}),
    _evidence("e3", "quick_execution", "new_tool", {"immediate_execution": 1}),
    _evidence("e4", "direct_trial", "new_tool", {"immediate_execution": 1}),
]


class ConflictDoesNotAutoResolveWithMoreEvidenceTest(unittest.TestCase):
    """2026-08-22 리뷰의 핵심 버그 재현: Evidence가 계속 쌓여도(해소 질문 답변 없이는)
    Explicit Conflict는 절대 저절로 빠지지 않는다."""

    def test_conflict_stays_detected_after_many_more_ordinary_answers(self) -> None:
        ledger = list(_CONFLICT_LEDGER)
        first = detect_explicit_conflicts(ledger, [CONTRAST])
        self.assertEqual(first.pair_results[0].status, "explicit_conflict")
        self.assertEqual(first.contrast_ids_needing_resolution_question, {"planning_vs_execution"})

        # 관련 없는 일반 답변을 10개 더 쌓아도 여전히 explicit_conflict여야 한다(버그였다면
        # 이것도 아무 영향 없었겠지만, 수정된 로직에서도 "일반 질문만으로는 해소 안 됨"이
        # 유지되는지 명시적으로 확인한다).
        for i in range(10):
            ledger.append(_evidence(f"filler_{i}", "cause_analysis", "problem_check", {"causal_analysis": 1}))
        later = detect_explicit_conflicts(ledger, [CONTRAST])
        self.assertEqual(later.pair_results[0].status, "explicit_conflict")
        self.assertEqual(later.unresolved_conflict_trait_ids, {"planning", "immediate_execution"})
        # 이미 한 번 DETECTED였다는 사실 자체는 resolutions가 없으면 매번 다시 계산되므로
        # 여전히 "확인 질문이 필요함" 목록에 남는다 — 이게 바로 Planner가 계속 우선순위로
        # 잡아야 하는 이유다(고쳐지지 않은 채로 두면 무한 반복 원인이 된다).
        self.assertEqual(later.contrast_ids_needing_resolution_question, {"planning_vs_execution"})


class ConflictResolutionRecordSettlesTheConflictTest(unittest.TestCase):
    def test_resolved_positive_unmasks_both_traits_and_stops_asking_again(self) -> None:
        resolutions = {
            "planning_vs_execution": ContrastResolutionRecord(
                contrast_id="planning_vs_execution",
                status=ContrastResolutionStatus.RESOLVED_POSITIVE,
                resolved_at_answer_id="ans_resolution_01",
            )
        }
        result = detect_explicit_conflicts(_CONFLICT_LEDGER, [CONTRAST], resolutions)
        self.assertEqual(result.pair_results[0].status, "resolved")
        self.assertEqual(result.unresolved_conflict_trait_ids, set())  # 더 이상 Mask 안 됨
        self.assertEqual(result.contrast_ids_needing_resolution_question, set())  # 다시 안 물어봄

    def test_resolved_opposite_also_unmasks_both_traits(self) -> None:
        resolutions = {
            "planning_vs_execution": ContrastResolutionRecord(
                contrast_id="planning_vs_execution",
                status=ContrastResolutionStatus.RESOLVED_OPPOSITE,
                resolved_at_answer_id="ans_resolution_01",
            )
        }
        result = detect_explicit_conflicts(_CONFLICT_LEDGER, [CONTRAST], resolutions)
        self.assertEqual(result.pair_results[0].status, "resolved")
        self.assertEqual(result.unresolved_conflict_trait_ids, set())

    def test_resolved_context_dependent_unmasks_but_flags_both_traits(self) -> None:
        """§12-1: "상황 차이로 설명 가능"하면 결함처럼 표현하거나 영구 Mask하지 않는다 —
        Mask는 풀리되 context_dependency_flag로 참고 정보만 남긴다."""

        resolutions = {
            "planning_vs_execution": ContrastResolutionRecord(
                contrast_id="planning_vs_execution",
                status=ContrastResolutionStatus.RESOLVED_CONTEXT_DEPENDENT,
                resolved_at_answer_id="ans_resolution_01",
            )
        }
        result = detect_explicit_conflicts(_CONFLICT_LEDGER, [CONTRAST], resolutions)
        self.assertEqual(result.pair_results[0].status, "context_dependent")
        self.assertEqual(result.unresolved_conflict_trait_ids, set())
        self.assertTrue(result.context_dependency_flag_by_trait.get("planning"))
        self.assertTrue(result.context_dependency_flag_by_trait.get("immediate_execution"))

    def test_unresolved_keeps_masking_but_never_asks_again(self) -> None:
        """확인 질문에 답은 했지만(무관한 선택지) 판정 불가 — 계속 Mask하되, 최대 질문
        수 도달 시 무한 반복을 막기 위해 다시 확인 질문을 요구하지는 않는다."""

        resolutions = {
            "planning_vs_execution": ContrastResolutionRecord(
                contrast_id="planning_vs_execution",
                status=ContrastResolutionStatus.UNRESOLVED,
                resolved_at_answer_id="ans_resolution_01",
            )
        }
        result = detect_explicit_conflicts(_CONFLICT_LEDGER, [CONTRAST], resolutions)
        self.assertEqual(result.pair_results[0].status, "explicit_conflict")
        self.assertEqual(result.unresolved_conflict_trait_ids, {"planning", "immediate_execution"})
        self.assertEqual(result.contrast_ids_needing_resolution_question, set())  # 재요청 없음

    def test_past_evidence_is_never_deleted_by_resolution(self) -> None:
        ledger = list(_CONFLICT_LEDGER)
        original_length = len(ledger)
        resolutions = {
            "planning_vs_execution": ContrastResolutionRecord(
                contrast_id="planning_vs_execution",
                status=ContrastResolutionStatus.RESOLVED_POSITIVE,
                resolved_at_answer_id="ans_resolution_01",
            )
        }
        detect_explicit_conflicts(ledger, [CONTRAST], resolutions)
        self.assertEqual(len(ledger), original_length)  # 함수가 Ledger를 건드리지 않음


if __name__ == "__main__":
    unittest.main()
