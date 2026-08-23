"""Trait Vector Snapshot Engine 테스트 — 지시서 §15 "Evidence"/(Snapshot 계산 관련)."""

from __future__ import annotations

import unittest

from src.engines.matching_engine import StudentTraitState
from src.engines.trait_vector_snapshot_engine import (
    compute_trait_vector_snapshot,
    compute_trait_vector_snapshot_all,
)
from src.schemas.evidence import AppliedTraitSignal, EvidenceOrigin, EvidenceRecord, TraitState


def _evidence(
    evidence_id: str, question_id: str, frame_id: str, context: str,
    trait_id: str, signal_role: str, weight: float,
    origin: EvidenceOrigin = EvidenceOrigin.PRIMARY_BLUEPRINT,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id, answer_id=f"ans_{evidence_id}", question_id=question_id,
        question_frame_id=frame_id, option_role_id="role", option_text="답변 예시",
        applied_primary_trait_delta={}, evidence_origin=origin, context=context,
        source_type="seed_question", generator_version="v1", quality_gate_status="passed",
        applied_trait_signals_v2=[
            AppliedTraitSignal(trait_id=trait_id, signal_role=signal_role, weight=weight)
        ],
    )


_INSUFFICIENT = StudentTraitState(
    trait_id="systems_thinking", state=TraitState.INSUFFICIENT, normalized_value=None,
    context_count=0, primary_vector_group="cognitive",
)
_STRONG = StudentTraitState(
    trait_id="causal_analysis", state=TraitState.STRONG, normalized_value=1.0,
    context_count=2, primary_vector_group="cognitive",
)


class NoEvidenceTest(unittest.TestCase):
    def test_no_evidence_is_not_probed(self) -> None:
        snap = compute_trait_vector_snapshot("systems_thinking", [], _INSUFFICIENT, set())
        self.assertEqual(snap.status, "NOT_PROBED")
        self.assertIsNone(snap.tendency_score)
        self.assertEqual(snap.evidence_confidence, "no_evidence")


class SingleRelatedIsHypothesisTest(unittest.TestCase):
    def test_single_related_signal_stays_hypothesis(self) -> None:
        """§9: "확인되지 않은 RELATED는 Hypothesis로만 보존" — 1회만으로는 승격 안 됨."""

        ledger = [_evidence("e1", "q1", "f1", "game", "systems_thinking", "RELATED", 0.33)]
        snap = compute_trait_vector_snapshot("systems_thinking", ledger, _INSUFFICIENT, set())
        self.assertEqual(snap.status, "HYPOTHESIS")
        self.assertIsNone(snap.tendency_score)
        self.assertEqual(snap.related_evidence_count, 1)
        self.assertEqual(snap.confirmed_related_signal_sum, 0.0)


class PromotionByDiversityTest(unittest.TestCase):
    def test_two_different_questions_and_contexts_promotes_to_limited(self) -> None:
        ledger = [
            _evidence("e1", "q1", "f1", "game", "systems_thinking", "RELATED", 0.33),
            _evidence("e2", "q2", "f1", "media", "systems_thinking", "RELATED", 0.33),
        ]
        snap = compute_trait_vector_snapshot("systems_thinking", ledger, _INSUFFICIENT, set())
        self.assertEqual(snap.status, "LIMITED")
        self.assertEqual(snap.tendency_score, 0.33)
        self.assertEqual(snap.evidence_confidence, "promoted_related_signal")
        self.assertAlmostEqual(snap.confirmed_related_signal_sum, 0.66)

    def test_same_question_id_repeated_does_not_promote(self) -> None:
        """같은 질문을 표현만 바꿔 반복해도(question_id가 실제로 같다면) 독립 Evidence로
        중복 계산하지 않는다 — question_id 기준 set이라 자동으로 방지된다."""

        ledger = [
            _evidence("e1", "q1", "f1", "game", "systems_thinking", "RELATED", 0.33),
            _evidence("e2", "q1", "f2", "media", "systems_thinking", "RELATED", 0.33),
        ]
        snap = compute_trait_vector_snapshot("systems_thinking", ledger, _INSUFFICIENT, set())
        self.assertEqual(snap.status, "HYPOTHESIS")  # question_id 다양성 1개뿐이라 승격 안 됨

    def test_two_different_frames_same_context_promotes(self) -> None:
        ledger = [
            _evidence("e1", "q1", "f1", "game", "systems_thinking", "RELATED", 0.33),
            _evidence("e2", "q2", "f2", "game", "systems_thinking", "RELATED", 0.33),
        ]
        snap = compute_trait_vector_snapshot("systems_thinking", ledger, _INSUFFICIENT, set())
        self.assertEqual(snap.status, "LIMITED")


class PromotionByPrimaryElsewhereTest(unittest.TestCase):
    def test_related_plus_primary_elsewhere_promotes_even_with_single_related(self) -> None:
        """2026-08-23 2단계 §15 반영: legacy_state가 없는(신규) Trait에 실제 PRIMARY
        Evidence가 하나라도 있으면 이제 `_direct_probe_status()`가 먼저 판정한다 — 이
        사례(PRIMARY 1개, RELATED 1개, 둘 다 같은 Context·Frame)는 다양성 조건을
        만족하지 못해 여전히 LIMITED이지만, "실제 PRIMARY Evidence가 있다"는 사실을
        더 정확히 반영해 evidence_confidence가 `primary_evidence`로 나온다(상태 자체는
        1.5단계와 동일하게 LIMITED — Matching에 미치는 영향 없음, 사유 문구만 더
        정확해졌다)."""

        legacy_insufficient_with_some_primary = StudentTraitState(
            trait_id="systems_thinking", state=TraitState.INSUFFICIENT, normalized_value=None,
            context_count=0, primary_vector_group="cognitive",
        )
        ledger = [
            _evidence("e1", "q1", "f1", "game", "systems_thinking", "PRIMARY", 1.0),
            _evidence("e2", "q2", "f1", "game", "systems_thinking", "RELATED", 0.33),
        ]
        snap = compute_trait_vector_snapshot(
            "systems_thinking", ledger, legacy_insufficient_with_some_primary, set()
        )
        self.assertEqual(snap.status, "LIMITED")
        self.assertEqual(snap.evidence_confidence, "primary_evidence")

    def test_related_from_different_context_with_single_primary_reaches_moderate(self) -> None:
        """PRIMARY 1개 + 다른 질문·다른 Context에서 관찰된 RELATED는 §15 MODERATE
        규칙("PRIMARY 1개 + 다른 질문에서 같은 Trait의 RELATED, Context 또는 Frame이
        다름")을 만족해야 한다."""

        legacy_insufficient = StudentTraitState(
            trait_id="systems_thinking", state=TraitState.INSUFFICIENT, normalized_value=None,
            context_count=0, primary_vector_group="cognitive",
        )
        ledger = [
            _evidence("e1", "q1", "f1", "game", "systems_thinking", "PRIMARY", 1.0),
            _evidence("e2", "q2", "f1", "media", "systems_thinking", "RELATED", 0.33),
        ]
        snap = compute_trait_vector_snapshot("systems_thinking", ledger, legacy_insufficient, set())
        self.assertEqual(snap.status, "MODERATE")
        self.assertEqual(snap.tendency_score, 0.67)
        self.assertEqual(snap.evidence_confidence, "primary_evidence")


class LegacyPrimaryTakesPriorityTest(unittest.TestCase):
    def test_legacy_strong_state_is_preserved_regardless_of_related(self) -> None:
        """§10: "PRIMARY Evidence가 기존 STRONG/MODERATE/LIMITED 조건을 만족하면 기존
        판정을 우선 유지" — RELATED가 아무리 많아도 STRONG을 흔들지 않는다."""

        ledger = [
            _evidence("e1", "q1", "f1", "game", "causal_analysis", "RELATED", 0.33),
            _evidence("e2", "q2", "f1", "media", "causal_analysis", "RELATED", 0.33),
        ]
        snap = compute_trait_vector_snapshot("causal_analysis", ledger, _STRONG, set())
        self.assertEqual(snap.status, "STRONG")
        self.assertEqual(snap.tendency_score, 1.0)
        self.assertEqual(snap.evidence_confidence, "primary_evidence")

    def test_one_answer_never_creates_a_strong_trait_from_related_alone(self) -> None:
        """한 번의 답변으로 강한 Trait가 되면 안 된다."""

        ledger = [_evidence("e1", "q1", "f1", "game", "systems_thinking", "RELATED", 0.33)]
        snap = compute_trait_vector_snapshot("systems_thinking", ledger, _INSUFFICIENT, set())
        self.assertNotIn(snap.status, ("STRONG", "MODERATE"))


class ExplicitConflictTest(unittest.TestCase):
    def test_unresolved_conflict_trait_is_masked(self) -> None:
        ledger = [_evidence("e1", "q1", "f1", "game", "systems_thinking", "RELATED", 0.33)]
        snap = compute_trait_vector_snapshot(
            "systems_thinking", ledger, _INSUFFICIENT, {"systems_thinking"}
        )
        self.assertEqual(snap.status, "CONFLICTING")
        self.assertIsNone(snap.tendency_score)


class ConflictResolutionOriginExclusionTest(unittest.TestCase):
    def test_conflict_resolution_origin_evidence_is_ignored(self) -> None:
        """Conflict Resolution 답변의 Evidence는 (있다 하더라도) 일반 Trait Evidence에
        포함되면 안 된다 — evidence_origin 필터로 이미 제외된다."""

        ledger = [
            _evidence(
                "e1", "q1", "f1", "game", "systems_thinking", "RELATED", 0.33,
                origin=EvidenceOrigin.CONFLICT_RESOLUTION,
            )
        ]
        snap = compute_trait_vector_snapshot("systems_thinking", ledger, _INSUFFICIENT, set())
        self.assertEqual(snap.status, "NOT_PROBED")
        self.assertEqual(snap.related_evidence_count, 0)


class ComputeAllTest(unittest.TestCase):
    def test_computes_entry_for_every_core_trait_id(self) -> None:
        core_ids = {"causal_analysis", "systems_thinking", "novelty_seeking"}
        legacy_states = {"causal_analysis": _STRONG}
        result = compute_trait_vector_snapshot_all([], legacy_states, set(), core_ids)
        self.assertEqual(set(result.keys()), core_ids)
        self.assertEqual(result["causal_analysis"].status, "STRONG")
        self.assertEqual(result["systems_thinking"].status, "NOT_PROBED")


class DirectProbeStatusRulesTest(unittest.TestCase):
    """2026-08-23 2단계 §15 — 신규 Trait Snapshot 판정 규칙. V2_DIRECT_PROBE Origin도
    v2 Signal의 정당한 출처로 포함되는지(§9 필터 확장)까지 함께 확인한다."""

    def test_v2_direct_probe_origin_evidence_is_included_in_v2_calculation(self) -> None:
        ledger = [
            _evidence(
                "e1", "q1", "f1", "game", "systems_thinking", "PRIMARY", 1.0,
                origin=EvidenceOrigin.V2_DIRECT_PROBE,
            )
        ]
        snap = compute_trait_vector_snapshot("systems_thinking", ledger, _INSUFFICIENT, set())
        self.assertEqual(snap.primary_evidence_count, 1)
        self.assertEqual(snap.status, "LIMITED")

    def test_single_direct_probe_primary_alone_is_limited_never_strong(self) -> None:
        """§15 금지: "Direct Probe 한 번만으로 STRONG" — 1개 PRIMARY, 다양성 없음."""

        ledger = [
            _evidence(
                "e1", "q1", "f1", "game", "creative_ideation", "PRIMARY", 1.0,
                origin=EvidenceOrigin.V2_DIRECT_PROBE,
            )
        ]
        snap = compute_trait_vector_snapshot("creative_ideation", ledger, _INSUFFICIENT, set())
        self.assertEqual(snap.status, "LIMITED")
        self.assertEqual(snap.tendency_score, 0.33)
        self.assertNotEqual(snap.status, "STRONG")

    def test_two_diverse_primary_records_reach_moderate(self) -> None:
        """§15 MODERATE 규칙 2: PRIMARY 2개가 서로 다른 질문·Context에서 존재."""

        ledger = [
            _evidence(
                "e1", "q1", "f1", "game", "independent_judgment", "PRIMARY", 1.0,
                origin=EvidenceOrigin.V2_DIRECT_PROBE,
            ),
            _evidence(
                "e2", "q2", "f1", "school_life", "independent_judgment", "PRIMARY", 1.0,
                origin=EvidenceOrigin.V2_DIRECT_PROBE,
            ),
        ]
        snap = compute_trait_vector_snapshot("independent_judgment", ledger, _INSUFFICIENT, set())
        self.assertEqual(snap.status, "MODERATE")
        self.assertEqual(snap.tendency_score, 0.67)

    def test_three_diverse_primary_records_reach_strong(self) -> None:
        """§15 STRONG 규칙: 실제로는 Trait당 Direct Probe 1개 제한 때문에 이 라운드에서
        도달 불가능하지만, 규칙 자체가 정확히 존재하는지는 독립적으로 검증한다."""

        ledger = [
            _evidence(
                "e1", "q1", "f1", "game", "systems_thinking", "PRIMARY", 1.0,
                origin=EvidenceOrigin.V2_DIRECT_PROBE,
            ),
            _evidence(
                "e2", "q2", "f2", "media", "systems_thinking", "PRIMARY", 1.0,
                origin=EvidenceOrigin.V2_DIRECT_PROBE,
            ),
            _evidence(
                "e3", "q3", "f1", "school_life", "systems_thinking", "PRIMARY", 1.0,
                origin=EvidenceOrigin.V2_DIRECT_PROBE,
            ),
        ]
        snap = compute_trait_vector_snapshot("systems_thinking", ledger, _INSUFFICIENT, set())
        self.assertEqual(snap.status, "STRONG")
        self.assertEqual(snap.tendency_score, 1.00)


class DirectProbeOpportunityCountTest(unittest.TestCase):
    def test_opportunity_counts_are_zero_by_default(self) -> None:
        snap = compute_trait_vector_snapshot("systems_thinking", [], _INSUFFICIENT, set())
        self.assertEqual(snap.direct_probe_opportunity_count, 0)
        self.assertEqual(snap.direct_probe_primary_evidence_count, 0)

    def test_opportunity_count_reflects_presented_not_selected(self) -> None:
        """target_signal_selected=False도 "질문은 받았다"는 사실로 opportunity_count에는
        들어가되, primary_evidence_count에는 들어가지 않는다(부정 Evidence 아님)."""

        from src.schemas.evidence import V2ProbeOpportunity

        opportunities = [
            V2ProbeOpportunity(
                question_id="q1", blueprint_id="systems_thinking_game_v1", target_trait_id="systems_thinking",
                context_id="game", frame_id="new_tool", selected_option_id="q1_o2", target_signal_selected=False,
            )
        ]
        snap = compute_trait_vector_snapshot(
            "systems_thinking", [], _INSUFFICIENT, set(), v2_probe_opportunities=opportunities
        )
        self.assertEqual(snap.direct_probe_opportunity_count, 1)
        self.assertEqual(snap.direct_probe_primary_evidence_count, 0)
        self.assertEqual(snap.status, "NOT_PROBED")  # 비선택은 Evidence가 아니다 — 상태에 영향 없음


if __name__ == "__main__":
    unittest.main()
