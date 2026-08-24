"""Trait Evidence Coverage Policy Engine 단위 테스트 — a/trait-evidence-coverage-shadow.

필수 테스트 항목(작업 지시문 그대로): 상태 5종 경계값, Primary/Related/NO_SIGNAL
가중치, 동일 질문 중복 차단, Context·Frame 다양성, 70% 방향 일관성 경계, Conflict
처리, 미관찰과 0점 구분."""

from __future__ import annotations

import unittest

from src.engines.trait_evidence_coverage_engine import (
    PRIMARY_WEIGHT,
    RELATED_WEIGHT,
    compute_all_trait_coverage,
    compute_trait_coverage,
    deduplicate_evidence,
    evidence_dedup_key,
)
from src.ids import generate_evidence_id
from src.schemas.evidence import AppliedTraitSignal, ContrastDefinition, EvidenceOrigin, EvidenceRecord

TRAIT = "causal_analysis"
OTHER_TRAIT = "planning"


def _record(
    *,
    trait_id: str = TRAIT,
    signal_role: str = "PRIMARY",
    weight: float = 1.0,
    context: str = "game",
    frame_id: str = "problem_check",
    blueprint_id: str | None = "bp_1",
    question_id: str | None = None,
    origin: EvidenceOrigin = EvidenceOrigin.PRIMARY_BLUEPRINT,
    role_id: str = "role_1",
    signals: list[AppliedTraitSignal] | None = None,
) -> EvidenceRecord:
    qid = question_id or f"q_{generate_evidence_id()}"
    applied = signals if signals is not None else (
        [AppliedTraitSignal(trait_id=trait_id, signal_role=signal_role, weight=weight)]
        if trait_id is not None else []
    )
    return EvidenceRecord(
        evidence_id=generate_evidence_id(),
        answer_id=f"ans_{qid}",
        question_id=qid,
        question_frame_id=frame_id,
        option_role_id=role_id,
        option_text="답변 예시",
        applied_primary_trait_delta={trait_id: 1} if trait_id and signal_role == "PRIMARY" else {},
        applied_trait_signals_v2=applied,
        evidence_origin=origin,
        context=context,
        source_type="seed_question",
        generator_version="v1",
        quality_gate_status="passed",
        source_blueprint_id=blueprint_id,
    )


def _approved(records: list[EvidenceRecord]) -> set[str]:
    return {r.evidence_id for r in records}


class WeightTest(unittest.TestCase):
    def test_primary_weight_is_1_0(self) -> None:
        self.assertEqual(PRIMARY_WEIGHT, 1.0)

    def test_related_weight_is_0_5(self) -> None:
        self.assertEqual(RELATED_WEIGHT, 0.5)

    def test_primary_and_related_sum_correctly(self) -> None:
        recs = [
            _record(signal_role="PRIMARY", frame_id="f1", blueprint_id="bp1"),
            _record(signal_role="RELATED", frame_id="f2", blueprint_id="bp2"),
        ]
        pool = deduplicate_evidence(recs, _approved(recs))
        result = compute_trait_coverage(TRAIT, pool)
        self.assertEqual(result.primary_evidence_count, 1)
        self.assertEqual(result.related_evidence_count, 1)
        self.assertAlmostEqual(result.effective_evidence_weight, 1.0 + 0.5)

    def test_no_signal_option_contributes_nothing(self) -> None:
        """NO_SIGNAL Option은 applied_trait_signals_v2가 비어 있다 — 이 Trait에 어떤
        가중치도 더하지 않는다."""
        rec = _record(trait_id=None, signals=[], blueprint_id="bp1")
        pool = deduplicate_evidence([rec], _approved([rec]))
        result = compute_trait_coverage(TRAIT, pool)
        self.assertEqual(result.effective_evidence_weight, 0.0)
        self.assertEqual(result.primary_evidence_count, 0)

    def test_unapproved_signal_excluded_from_calculation(self) -> None:
        """§2 '승인되지 않은 Signal: 계산 제외' — approved_evidence_ids에 없으면
        deduplicate_evidence 단계에서부터 빠진다."""
        rec = _record(blueprint_id="bp1")
        pool = deduplicate_evidence([rec], approved_evidence_ids=set())  # 승인 안 됨
        result = compute_trait_coverage(TRAIT, pool)
        self.assertEqual(result.primary_evidence_count, 0)
        self.assertEqual(result.coverage_status, "UNOBSERVED")


class DuplicatePreventionTest(unittest.TestCase):
    def test_same_blueprint_and_frame_counted_once(self) -> None:
        """§2 '동일 blueprint_id+frame_id의 반복 Evidence는 최대 1회만 인정'."""
        recs = [
            _record(blueprint_id="bp1", frame_id="problem_check", question_id="q1"),
            _record(blueprint_id="bp1", frame_id="problem_check", question_id="q2"),  # 재요청/재표현
        ]
        pool = deduplicate_evidence(recs, _approved(recs))
        self.assertEqual(len(pool), 1, "동일 blueprint_id+frame_id는 1건만 남아야 한다")
        result = compute_trait_coverage(TRAIT, pool)
        self.assertEqual(result.primary_evidence_count, 1)

    def test_same_blueprint_different_frame_counts_separately(self) -> None:
        recs = [
            _record(blueprint_id="bp1", frame_id="problem_check", question_id="q1"),
            _record(blueprint_id="bp1", frame_id="new_tool", question_id="q2"),
        ]
        pool = deduplicate_evidence(recs, _approved(recs))
        self.assertEqual(len(pool), 2)

    def test_different_blueprint_same_frame_counts_separately(self) -> None:
        recs = [
            _record(blueprint_id="bp1", frame_id="problem_check", question_id="q1"),
            _record(blueprint_id="bp2", frame_id="problem_check", question_id="q2"),
        ]
        pool = deduplicate_evidence(recs, _approved(recs))
        self.assertEqual(len(pool), 2)

    def test_first_occurrence_wins_and_order_is_ledger_order(self) -> None:
        recs = [
            _record(blueprint_id="bp1", frame_id="f1", question_id="first"),
            _record(blueprint_id="bp1", frame_id="f1", question_id="second"),
        ]
        pool = deduplicate_evidence(recs, _approved(recs))
        self.assertEqual(pool[0].question_id, "first")

    def test_missing_blueprint_id_falls_back_to_question_id_key(self) -> None:
        """blueprint_id가 없는(Legacy 이전 기록 등) 두 서로 다른 생성 질문은, 같은
        Frame이라는 이유만으로 뭉치면 안 된다."""
        recs = [
            _record(blueprint_id=None, frame_id="problem_check", question_id="qA"),
            _record(blueprint_id=None, frame_id="problem_check", question_id="qB"),
        ]
        pool = deduplicate_evidence(recs, _approved(recs))
        self.assertEqual(len(pool), 2, "blueprint_id가 없으면 question_id로 구분해야 한다")

    def test_dedup_key_helper_matches_engine_behavior(self) -> None:
        rec = _record(blueprint_id="bp1", frame_id="f1")
        self.assertEqual(evidence_dedup_key(rec), ("bp1", "f1"))


class ContextFrameDiversityTest(unittest.TestCase):
    def test_distinct_context_and_frame_counted(self) -> None:
        recs = [
            _record(blueprint_id="bp1", frame_id="f1", context="game"),
            _record(blueprint_id="bp2", frame_id="f2", context="media"),
        ]
        pool = deduplicate_evidence(recs, _approved(recs))
        result = compute_trait_coverage(TRAIT, pool)
        self.assertEqual(result.distinct_context_count, 2)
        self.assertEqual(result.distinct_frame_count, 2)

    def test_repeated_context_and_frame_not_double_counted(self) -> None:
        recs = [
            _record(blueprint_id="bp1", frame_id="f1", context="game"),
            _record(blueprint_id="bp2", frame_id="f1", context="game"),
        ]
        pool = deduplicate_evidence(recs, _approved(recs))
        result = compute_trait_coverage(TRAIT, pool)
        self.assertEqual(result.distinct_context_count, 1)
        self.assertEqual(result.distinct_frame_count, 1)


class StateBoundaryTest(unittest.TestCase):
    """5개 상태 각각의 경계값."""

    def test_zero_evidence_is_unobserved(self) -> None:
        result = compute_trait_coverage(TRAIT, [])
        self.assertEqual(result.coverage_status, "UNOBSERVED")
        self.assertEqual(result.primary_evidence_count, 0)
        self.assertEqual(result.effective_evidence_weight, 0.0)

    def test_single_context_single_frame_focus_is_limited(self) -> None:
        """'한 Context/한 Frame에만 집중' → LIMITED. Primary 3개를 같은 Context·같은
        Frame(다른 blueprint)에서만 모아도 다양성이 없으면 LIMITED다."""
        recs = [
            _record(blueprint_id=f"bp{i}", frame_id="problem_check", context="game")
            for i in range(3)
        ]
        pool = deduplicate_evidence(recs, _approved(recs))
        result = compute_trait_coverage(TRAIT, pool)
        self.assertEqual(result.primary_evidence_count, 3)
        self.assertEqual(result.distinct_context_count, 1)
        self.assertEqual(result.distinct_frame_count, 1)
        self.assertEqual(result.coverage_status, "LIMITED")

    def test_primary_2_and_frame_2_but_overall_criteria_unmet_is_supported(self) -> None:
        """Primary 2개 + Frame 2개지만 Context가 1개뿐 → 전체 SUFFICIENT 기준 미달,
        그러나 SUPPORTED 조건(Primary>=2, Frame>=2)은 충족."""
        recs = [
            _record(blueprint_id="bp1", frame_id="f1", context="game"),
            _record(blueprint_id="bp2", frame_id="f2", context="game"),
        ]
        pool = deduplicate_evidence(recs, _approved(recs))
        result = compute_trait_coverage(TRAIT, pool)
        self.assertEqual(result.primary_evidence_count, 2)
        self.assertEqual(result.distinct_frame_count, 2)
        self.assertEqual(result.distinct_context_count, 1)
        self.assertEqual(result.coverage_status, "SUPPORTED")
        self.assertIn(
            "distinct_context_count>=2 미충족(현재 1)", result.missing_requirements
        )

    def test_all_sufficient_criteria_met(self) -> None:
        """Primary 2개 이상 + 가중치 3.0 이상 + Context 2개 + Frame 2개 + 방향 일관성
        100% + Conflict 없음 → SUFFICIENT."""
        recs = [
            _record(blueprint_id="bp1", frame_id="f1", context="game"),
            _record(blueprint_id="bp2", frame_id="f2", context="media"),
            _record(blueprint_id="bp3", frame_id="f3", context="school_life"),
        ]
        pool = deduplicate_evidence(recs, _approved(recs))
        result = compute_trait_coverage(TRAIT, pool)
        self.assertEqual(result.primary_evidence_count, 3)
        self.assertGreaterEqual(result.effective_evidence_weight, 3.0)
        self.assertEqual(result.coverage_status, "SUFFICIENT")
        self.assertEqual(result.missing_requirements, [])

    def test_sufficient_boundary_exactly_at_thresholds(self) -> None:
        """정확히 Primary=2, weight=... Context=2, Frame=2, RELATED 1개로 weight를
        3.0에 정확히 맞춘 경계 케이스."""
        recs = [
            _record(blueprint_id="bp1", frame_id="f1", context="game", signal_role="PRIMARY"),
            _record(blueprint_id="bp2", frame_id="f2", context="media", signal_role="PRIMARY"),
            _record(blueprint_id="bp3", frame_id="f2", context="media", signal_role="RELATED"),
        ]
        pool = deduplicate_evidence(recs, _approved(recs))
        result = compute_trait_coverage(TRAIT, pool)
        self.assertEqual(result.primary_evidence_count, 2)
        self.assertEqual(result.related_evidence_count, 1)
        self.assertAlmostEqual(result.effective_evidence_weight, 2.5)
        # weight 2.5 < 3.0 → SUFFICIENT 기준 미달, 그러나 Primary>=2·Frame>=2라 SUPPORTED.
        self.assertEqual(result.coverage_status, "SUPPORTED")

    def test_weight_exactly_3_0_with_diversity_is_sufficient(self) -> None:
        recs = [
            _record(blueprint_id="bp1", frame_id="f1", context="game", signal_role="PRIMARY"),
            _record(blueprint_id="bp2", frame_id="f2", context="media", signal_role="PRIMARY"),
            _record(blueprint_id="bp3", frame_id="f2", context="media", signal_role="RELATED"),
            _record(blueprint_id="bp4", frame_id="f3", context="school_life", signal_role="RELATED"),
        ]
        pool = deduplicate_evidence(recs, _approved(recs))
        result = compute_trait_coverage(TRAIT, pool)
        self.assertAlmostEqual(result.effective_evidence_weight, 3.0)
        self.assertEqual(result.coverage_status, "SUFFICIENT")


class ConflictTest(unittest.TestCase):
    """70% 방향 일관성 경계 + Conflict 처리."""

    CONTRAST = ContrastDefinition(
        contrast_id="planning_vs_execution_test",
        construct_id="approach_timing",
        positive_role_ids=["task_planning"],
        opposite_role_ids=["quick_execution"],
        comparable_frame_ids=["new_tool"],
        condition_scope="테스트",
        minimum_evidence_each_side=2,
        description="테스트용 Contrast",
    )

    def _planning_records(self, count: int) -> list[EvidenceRecord]:
        return [
            _record(
                trait_id="planning", blueprint_id=f"plan_bp{i}", frame_id="new_tool",
                role_id="task_planning",
            )
            for i in range(count)
        ]

    def _execution_records(self, count: int) -> list[EvidenceRecord]:
        return [
            _record(
                trait_id="immediate_execution", blueprint_id=f"exec_bp{i}", frame_id="new_tool",
                role_id="quick_execution",
            )
            for i in range(count)
        ]

    def test_no_opposing_evidence_defaults_to_full_consistency(self) -> None:
        recs = self._planning_records(3)
        pool = deduplicate_evidence(recs, _approved(recs))
        result = compute_trait_coverage("planning", pool, contrast_definitions=[self.CONTRAST])
        self.assertEqual(result.directional_consistency, 1.0)
        self.assertEqual(result.unresolved_conflict_count, 0)

    def test_below_70_percent_and_both_sides_meet_minimum_is_conflicted(self) -> None:
        """양쪽 다 minimum_evidence_each_side(2) 이상이고, 우세 방향이 70% 미만 →
        CONFLICTED. 여기서는 정확히 50:50(2:2)로 만들어 확실히 70% 밑으로 둔다."""
        recs = self._planning_records(2) + self._execution_records(2)
        pool = deduplicate_evidence(recs, _approved(recs))
        result = compute_trait_coverage("planning", pool, contrast_definitions=[self.CONTRAST])
        self.assertAlmostEqual(result.directional_consistency, 0.5)
        self.assertEqual(result.unresolved_conflict_count, 1)
        self.assertEqual(result.coverage_status, "CONFLICTED")

    def test_at_or_above_70_percent_is_not_conflicted_by_direction(self) -> None:
        """우세 방향이 정확히 70%(7:3) 이상이면 방향 자체는 통과 — 다만
        minimum_evidence_each_side(2)를 반대쪽이 만족하면 여전히 Conflict로 잡힐 수
        있으니, 반대쪽을 1개(미만)로 둬서 방향성만 순수하게 확인한다."""
        recs = self._planning_records(7) + self._execution_records(1)
        pool = deduplicate_evidence(recs, _approved(recs))
        result = compute_trait_coverage("planning", pool, contrast_definitions=[self.CONTRAST])
        self.assertAlmostEqual(result.directional_consistency, 0.875)
        self.assertGreaterEqual(result.directional_consistency, 0.7)
        # 반대쪽이 minimum_evidence_each_side(2) 미만이라 unresolved conflict는 아니다.
        self.assertEqual(result.unresolved_conflict_count, 0)
        self.assertNotEqual(result.coverage_status, "CONFLICTED")

    def test_conflict_below_minimum_evidence_each_side_is_not_unresolved(self) -> None:
        """양쪽 다 있어도 반대쪽이 minimum_evidence_each_side 미만이면 미해결 Conflict가
        아니다(그냥 우세 방향이 존재하는 정상 상태)."""
        recs = self._planning_records(3) + self._execution_records(1)
        pool = deduplicate_evidence(recs, _approved(recs))
        result = compute_trait_coverage("planning", pool, contrast_definitions=[self.CONTRAST])
        self.assertEqual(result.unresolved_conflict_count, 0)

    def test_evidence_outside_comparable_frame_not_treated_as_opposing(self) -> None:
        """comparable_frame_ids 밖에서 나온 반대쪽 Evidence는 직접 비교 대상이 아니다."""
        recs = self._planning_records(3)
        opposing_wrong_frame = [
            _record(
                trait_id="immediate_execution", blueprint_id=f"exec_wrong{i}",
                frame_id="limited_time_priority", role_id="quick_execution",
            )
            for i in range(3)
        ]
        pool = deduplicate_evidence(recs + opposing_wrong_frame, _approved(recs + opposing_wrong_frame))
        result = compute_trait_coverage("planning", pool, contrast_definitions=[self.CONTRAST])
        self.assertEqual(result.directional_consistency, 1.0)
        self.assertEqual(result.unresolved_conflict_count, 0)


class UnobservedVsZeroTest(unittest.TestCase):
    """미관찰(UNOBSERVED)과 '측정했더니 0'을 구분한다 — 이 Policy에는 부정 Evidence
    개념이 없으므로, Evidence가 전혀 없는 것과 있지만 부족한 것을 상태로 구분한다."""

    def test_unobserved_has_zero_weight_and_empty_contributing_ids(self) -> None:
        result = compute_trait_coverage(TRAIT, [])
        self.assertEqual(result.coverage_status, "UNOBSERVED")
        self.assertEqual(result.contributing_evidence_ids, [])
        self.assertEqual(result.missing_requirements, [
            "primary_evidence_count>=2 미충족(현재 0)",
            "effective_evidence_weight>=3.0 미충족(현재 0.0)",
            "distinct_context_count>=2 미충족(현재 0)",
            "distinct_frame_count>=2 미충족(현재 0)",
        ])

    def test_one_related_only_is_not_unobserved(self) -> None:
        """Related 1개만 있어도 '직접 근거 없음'은 아니다 — UNOBSERVED가 아니라
        LIMITED다(Primary가 없어 SUPPORTED 조건도 못 채운다)."""
        rec = _record(signal_role="RELATED", blueprint_id="bp1")
        pool = deduplicate_evidence([rec], _approved([rec]))
        result = compute_trait_coverage(TRAIT, pool)
        self.assertNotEqual(result.coverage_status, "UNOBSERVED")
        self.assertEqual(result.coverage_status, "LIMITED")


class MultiTraitTest(unittest.TestCase):
    def test_compute_all_trait_coverage_covers_every_requested_trait(self) -> None:
        recs = [_record(blueprint_id="bp1", frame_id="f1")]
        results = compute_all_trait_coverage({TRAIT, OTHER_TRAIT}, recs, _approved(recs))
        self.assertEqual(set(results.keys()), {TRAIT, OTHER_TRAIT})
        self.assertEqual(results[OTHER_TRAIT].coverage_status, "UNOBSERVED")

    def test_one_record_can_contribute_to_two_traits_at_once(self) -> None:
        """PRIMARY causal_analysis + RELATED systems_thinking을 한 답변에 함께 담아,
        두 Trait 계산이 서로 독립적으로 이 한 Record를 각자 셈에 넣는지 확인한다."""
        rec = _record(
            blueprint_id="bp1", frame_id="f1",
            signals=[
                AppliedTraitSignal(trait_id=TRAIT, signal_role="PRIMARY", weight=1.0),
                AppliedTraitSignal(trait_id="systems_thinking", signal_role="RELATED", weight=0.33),
            ],
        )
        pool = deduplicate_evidence([rec], _approved([rec]))
        primary_result = compute_trait_coverage(TRAIT, pool)
        related_result = compute_trait_coverage("systems_thinking", pool)
        self.assertEqual(primary_result.primary_evidence_count, 1)
        self.assertEqual(related_result.related_evidence_count, 1)


if __name__ == "__main__":
    unittest.main()
