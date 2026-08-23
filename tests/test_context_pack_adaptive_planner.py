"""ContextPack Adaptive Tail Planner 계약 테스트 — 2026-08-23 Trait Ontology v2(2.9단계) §7/§13."""

from __future__ import annotations

import unittest

from src.engines.context_pack_adaptive_planner import (
    compute_pack_context_trait_summaries,
    select_pack_adaptive_target,
)
from src.engines.evidence_engine import decide_stop_or_continue
from src.schemas.evidence import AppliedTraitSignal, EvidenceOrigin, EvidenceRecord
from src.schemas.question import FinalizedOption, FinalizedQuestion
from src.schemas.trait_signal import TraitSignal
from src.schemas.v2_direct_probe import V2DirectProbeBlueprint, V2ProbeOptionMapping


def _blueprint(blueprint_id: str, trait_id: str, *, frame_id: str = "direct_probe", context: str = "business") -> V2DirectProbeBlueprint:
    role_ids = [f"{blueprint_id}_r{i}" for i in range(1, 6)]
    options = []
    mappings = []
    for i, role_id in enumerate(role_ids, start=1):
        if i == 1:
            options.append(FinalizedOption(option_id=f"{blueprint_id}_o{i}", role_id=role_id, text=f"옵션{i}", primary_trait_delta={trait_id: 1}))
            mappings.append(V2ProbeOptionMapping(role_id=role_id, mapping_type="TRAIT_SIGNAL", trait_signals=[TraitSignal(trait_id=trait_id, signal_role="PRIMARY", weight=1.0)]))
        else:
            options.append(FinalizedOption(option_id=f"{blueprint_id}_o{i}", role_id=role_id, text=f"옵션{i}", primary_trait_delta={}))
            mappings.append(V2ProbeOptionMapping(role_id=role_id, mapping_type="NO_SIGNAL", no_signal_reason="예제"))
    base_question = FinalizedQuestion(
        question_id=f"{blueprint_id}_base", context=context, target_traits=[], frame_id=frame_id,
        question_text="예제 질문", options=options,
    )
    return V2DirectProbeBlueprint(
        trait_id=trait_id, blueprint_id=blueprint_id, option_mappings=mappings,
        allowed_context_ids=[context], question_frame_id=frame_id, purpose="예제", base_question=base_question,
    )


def _evidence(context: str, question_id: str, trait_id: str, frame_id: str, blueprint_id: str, family: str = "pack_direct_probe") -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=f"ev_{question_id}", answer_id=f"ans_{question_id}", question_id=question_id,
        question_frame_id=frame_id, option_role_id="r1", option_text="답",
        applied_primary_trait_delta={trait_id: 1},
        applied_trait_signals_v2=[AppliedTraitSignal(trait_id=trait_id, signal_role="PRIMARY", weight=1.0)],
        trait_signal_mapping_source_v2="EXACT_BLUEPRINT", evidence_origin=EvidenceOrigin.V2_DIRECT_PROBE,
        context=context, source_type="pack_context_direct_probe_question", generator_version="v1",
        quality_gate_status="passed", source_question_family_id=family, source_blueprint_id=blueprint_id,
    )


class ComputeTraitSummariesTest(unittest.TestCase):
    def test_only_this_context_counted(self) -> None:
        ledger = [
            _evidence("business", "business_q1", "planning", "f1", "bp1"),
            _evidence("science", "science_q1", "planning", "f1", "bp_other"),
        ]
        offered = {"business_q1": ["planning"], "science_q1": ["planning"]}
        summaries = compute_pack_context_trait_summaries(ledger, offered, context_id="business", trait_ids={"planning"})
        self.assertEqual(summaries["planning"].support_count, 1)
        self.assertEqual(summaries["planning"].opportunity_count, 1)


class SelectAdaptiveTargetTest(unittest.TestCase):
    def setUp(self) -> None:
        self.bp_planning = _blueprint("bp_planning", "planning")
        self.bp_causal = _blueprint("bp_causal", "causal_analysis")
        self.pool = [self.bp_planning, self.bp_causal]

    def test_prefers_evidence_gap_trait(self) -> None:
        # planning은 이미 support_count>=2(충분), causal_analysis는 아예 관찰 이력 없음(Gap).
        summaries = {
            "planning": _dummy_summary(support=2, opportunity=2),
            "causal_analysis": _dummy_summary(support=0, opportunity=0),
        }
        decision = select_pack_adaptive_target(
            candidate_pool=self.pool, trait_summaries=summaries, already_used_blueprint_ids=set(),
            recent_target_trait_id=None, used_frame_ids=set(), final_contexts=["business"],
        )
        self.assertIsNotNone(decision)
        self.assertEqual(decision.trait_id, "causal_analysis")

    def test_avoids_immediately_repeating_recent_trait_when_alternative_exists(self) -> None:
        summaries = {"planning": _dummy_summary(0, 0), "causal_analysis": _dummy_summary(0, 0)}
        decision = select_pack_adaptive_target(
            candidate_pool=self.pool, trait_summaries=summaries, already_used_blueprint_ids=set(),
            recent_target_trait_id="planning", used_frame_ids=set(), final_contexts=["business"],
        )
        self.assertIsNotNone(decision)
        self.assertEqual(decision.trait_id, "causal_analysis")

    def test_used_blueprint_id_is_never_reused(self) -> None:
        summaries = {"planning": _dummy_summary(0, 0)}
        decision = select_pack_adaptive_target(
            candidate_pool=[self.bp_planning], trait_summaries=summaries,
            already_used_blueprint_ids={"bp_planning"}, recent_target_trait_id=None,
            used_frame_ids=set(), final_contexts=["business"],
        )
        self.assertIsNone(decision)

    def test_returns_none_when_candidates_exhausted(self) -> None:
        decision = select_pack_adaptive_target(
            candidate_pool=[], trait_summaries={}, already_used_blueprint_ids=set(),
            recent_target_trait_id=None, used_frame_ids=set(), final_contexts=["business"],
        )
        self.assertIsNone(decision)

    def test_blueprint_outside_final_contexts_is_not_selected(self) -> None:
        bp_other_context = _blueprint("bp_other_ctx", "planning", context="science")
        decision = select_pack_adaptive_target(
            candidate_pool=[bp_other_context], trait_summaries={"planning": _dummy_summary(0, 0)},
            already_used_blueprint_ids=set(), recent_target_trait_id=None, used_frame_ids=set(),
            final_contexts=["business"],
        )
        self.assertIsNone(decision)


def _dummy_summary(support: int, opportunity: int):
    from src.schemas.evidence import TraitEvidenceSummary

    return TraitEvidenceSummary(
        trait_id="x", support_count=support, opportunity_count=opportunity, context_count=1, distinct_frame_count=1,
    )


class MinMaxPolicyReuseTest(unittest.TestCase):
    """§4 최소 4개·최대 6개 정책은 evidence_engine.decide_stop_or_continue를 그대로
    재사용한다 — 여기서는 그 재사용이 실제로 Pack Context에도 그대로 적용되는지만
    확인한다(정책 자체의 세부 재검증은 기존 evidence_engine 테스트가 이미 한다)."""

    def test_below_minimum_always_continues_regardless_of_summaries(self) -> None:
        self.assertEqual(decide_stop_or_continue(0, {}, set(), set()), "CONTINUE")
        self.assertEqual(decide_stop_or_continue(3, {}, set(), set()), "CONTINUE")

    def test_at_maximum_always_stops(self) -> None:
        self.assertEqual(decide_stop_or_continue(6, {}, {"planning"}, set()), "STOP")


if __name__ == "__main__":
    unittest.main()
