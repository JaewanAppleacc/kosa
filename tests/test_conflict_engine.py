"""Explicit Conflict / Context Dependency 판정(§12-1) 테스트 — 손계산 기반."""

from __future__ import annotations

import unittest

from src.engines.conflict_engine import detect_explicit_conflicts
from src.schemas.evidence import ContrastDefinition, EvidenceOrigin, EvidenceRecord


def _evidence(
    evidence_id: str,
    role_id: str,
    frame_id: str,
    trait_delta: dict[str, int],
    *,
    origin: EvidenceOrigin = EvidenceOrigin.PRIMARY_BLUEPRINT,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        answer_id=f"ans_{evidence_id}",
        question_id=f"q_{evidence_id}",
        question_frame_id=frame_id,
        option_role_id=role_id,
        option_text="테스트 선택지",
        applied_primary_trait_delta=trait_delta,
        evidence_origin=origin,
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
    condition_scope="새로운 도구·과제가 주어진 상황",
    minimum_evidence_each_side=2,
    description="테스트용",
)


class DetectExplicitConflictsTest(unittest.TestCase):
    def test_both_sides_meet_minimum_in_comparable_frame_is_explicit_conflict(self) -> None:
        ledger = [
            _evidence("e1", "task_planning", "new_tool", {"planning": 1}),
            _evidence("e2", "advance_planning", "new_tool", {"planning": 1}),
            _evidence("e3", "quick_execution", "new_tool", {"immediate_execution": 1}),
            _evidence("e4", "direct_trial", "new_tool", {"immediate_execution": 1}),
        ]
        result = detect_explicit_conflicts(ledger, [CONTRAST])
        self.assertEqual(result.pair_results[0].status, "explicit_conflict")
        self.assertEqual(result.unresolved_conflict_trait_ids, {"planning", "immediate_execution"})

    def test_one_side_missing_is_insufficient_evidence_not_conflict(self) -> None:
        ledger = [
            _evidence("e1", "task_planning", "new_tool", {"planning": 1}),
            _evidence("e2", "advance_planning", "new_tool", {"planning": 1}),
        ]
        result = detect_explicit_conflicts(ledger, [CONTRAST])
        self.assertEqual(result.pair_results[0].status, "insufficient_evidence")
        self.assertEqual(result.unresolved_conflict_trait_ids, set())

    def test_no_evidence_at_all_is_insufficient_evidence(self) -> None:
        result = detect_explicit_conflicts([], [CONTRAST])
        self.assertEqual(result.pair_results[0].status, "insufficient_evidence")
        self.assertEqual(result.unresolved_conflict_trait_ids, set())

    def test_evidence_outside_comparable_frame_is_context_dependent_not_conflict(self) -> None:
        """CLAUDE.md: "단순 Context 차이를 Conflict로 판정하지 않는다" — 양쪽 다 Evidence는
        있지만 "새로운 도구" 상황에서 직접 대조된 게 아니라 서로 다른 상황(예: 시간 제약)에서
        나온 반대 선택이면, 상황 차이로 설명 가능하므로 Conflict가 아니라 Context Dependency다."""

        ledger = [
            _evidence("e1", "task_planning", "limited_time_priority", {"planning": 1}),
            _evidence("e2", "quick_execution", "unexpected_result", {"immediate_execution": 1}),
        ]
        result = detect_explicit_conflicts(ledger, [CONTRAST])
        self.assertEqual(result.pair_results[0].status, "context_dependent")
        self.assertEqual(result.unresolved_conflict_trait_ids, set())
        self.assertTrue(result.context_dependency_flag_by_trait.get("planning"))
        self.assertTrue(result.context_dependency_flag_by_trait.get("immediate_execution"))

    def test_below_minimum_evidence_each_side_is_context_dependent(self) -> None:
        """comparable frame 안에 있어도 한쪽이 minimum_evidence_each_side(2)에 못 미치면
        아직 EXPLICIT_CONFLICT로 확정하지 않는다."""

        ledger = [
            _evidence("e1", "task_planning", "new_tool", {"planning": 1}),
            _evidence("e2", "advance_planning", "new_tool", {"planning": 1}),
            _evidence("e3", "quick_execution", "new_tool", {"immediate_execution": 1}),  # 반대쪽 1개뿐
        ]
        result = detect_explicit_conflicts(ledger, [CONTRAST])
        self.assertEqual(result.pair_results[0].status, "context_dependent")

    def test_secondary_hypothesis_evidence_is_excluded(self) -> None:
        """CLAUDE.md: Secondary Hypothesis는 확정 전까지 계산에 넣지 않는다."""

        ledger = [
            _evidence("e1", "task_planning", "new_tool", {"planning": 1}),
            _evidence("e2", "advance_planning", "new_tool", {"planning": 1}),
            _evidence("e3", "quick_execution", "new_tool", {"immediate_execution": 1}, origin=EvidenceOrigin.SECONDARY_HYPOTHESIS),
            _evidence("e4", "direct_trial", "new_tool", {"immediate_execution": 1}, origin=EvidenceOrigin.SECONDARY_HYPOTHESIS),
        ]
        result = detect_explicit_conflicts(ledger, [CONTRAST])
        # opposite 쪽이 전부 Secondary라 사실상 0개 취급 → insufficient_evidence.
        self.assertEqual(result.pair_results[0].status, "insufficient_evidence")

    def test_explicit_conflict_count_and_context_dependency_flag_are_mutually_exclusive_per_trait(self) -> None:
        conflict_ledger = [
            _evidence("e1", "task_planning", "new_tool", {"planning": 1}),
            _evidence("e2", "advance_planning", "new_tool", {"planning": 1}),
            _evidence("e3", "quick_execution", "new_tool", {"immediate_execution": 1}),
            _evidence("e4", "direct_trial", "new_tool", {"immediate_execution": 1}),
        ]
        result = detect_explicit_conflicts(conflict_ledger, [CONTRAST])
        self.assertEqual(result.explicit_conflict_count_by_trait.get("planning"), 1)
        self.assertEqual(result.context_dependency_flag_by_trait.get("planning"), None)

    def test_unrelated_evidence_does_not_affect_unrelated_trait(self) -> None:
        ledger = [
            _evidence("e1", "task_planning", "new_tool", {"planning": 1}),
            _evidence("e2", "advance_planning", "new_tool", {"planning": 1}),
            _evidence("e3", "quick_execution", "new_tool", {"immediate_execution": 1}),
            _evidence("e4", "direct_trial", "new_tool", {"immediate_execution": 1}),
            _evidence("e5", "cause_analysis", "problem_check", {"causal_analysis": 1}),
        ]
        result = detect_explicit_conflicts(ledger, [CONTRAST])
        self.assertNotIn("causal_analysis", result.unresolved_conflict_trait_ids)


if __name__ == "__main__":
    unittest.main()
