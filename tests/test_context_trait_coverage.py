"""Context–Trait Coverage Matrix 계약 테스트 — 2026-08-23 Trait Ontology v2(2.8단계) §6."""

from __future__ import annotations

import unittest

from src.data.context_packs._example_pack_builder import (
    EXAMPLE_TRAIT_IDS,
    build_example_context_pack,
)
from src.schemas.question import FinalizedOption, FinalizedQuestion
from src.schemas.trait_signal import TraitSignal
from src.schemas.v2_direct_probe import V2DirectProbeBlueprint, V2ProbeOptionMapping
from src.services.context_trait_coverage import (
    ContextTraitCoverageError,
    compute_context_trait_coverage,
)

_KNOWN = frozenset(EXAMPLE_TRAIT_IDS) | frozenset({"planning", "persistence_completion"})


class BasicCoverageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.pack = build_example_context_pack()

    def test_seed_and_backup_counts_match_pack_structure(self) -> None:
        coverage = compute_context_trait_coverage(self.pack, _KNOWN)
        self.assertEqual(coverage.context_id, "example_context")
        self.assertEqual(coverage.anchor_count, 5)
        self.assertEqual(coverage.seed_question_count, 5)
        self.assertEqual(coverage.backup_question_count, 5)

    def test_primary_trait_ids_come_from_seed_and_backup_deltas(self) -> None:
        # _example_pack_builder는 causal_analysis/pattern_finding 두 Trait만 쓴다
        # (각 Anchor의 Seed/Backup Option 1이 target_trait_id를 PRIMARY로 delta에 담는다).
        coverage = compute_context_trait_coverage(self.pack, _KNOWN)
        self.assertEqual(coverage.primary_trait_ids, set(EXAMPLE_TRAIT_IDS))

    def test_no_signal_options_excluded_from_primary(self) -> None:
        # Option 2는 항상 primary_trait_delta={}(NO_SIGNAL) — 이 Trait가 잘못
        # primary_trait_ids에 섞여 들어가지 않는지는 위 test로 이미 간접 확인되지만,
        # 여기서는 "Trait 후보가 딱 2개"라는 상한으로 NO_SIGNAL이 안 새는지 명시한다.
        coverage = compute_context_trait_coverage(self.pack, _KNOWN)
        self.assertEqual(len(coverage.primary_trait_ids), 2)

    def test_uncovered_trait_ids_is_known_minus_referenced(self) -> None:
        coverage = compute_context_trait_coverage(self.pack, _KNOWN)
        self.assertEqual(coverage.uncovered_trait_ids, _KNOWN - set(EXAMPLE_TRAIT_IDS))

    def test_unknown_trait_id_raises_fail_closed_error(self) -> None:
        with self.assertRaises(ContextTraitCoverageError):
            compute_context_trait_coverage(self.pack, frozenset())

    def test_dedup_same_trait_across_multiple_options_and_questions(self) -> None:
        # causal_analysis는 5개 Anchor 중 여러 개(0, 2, 4번째 anchor)의 Seed/Backup에서
        # 반복 등장한다 — set 기반이라 중복 계산 없이 1개로 합쳐져야 한다.
        coverage = compute_context_trait_coverage(self.pack, _KNOWN)
        self.assertIn("causal_analysis", coverage.primary_trait_ids)
        self.assertEqual(sum(1 for t in coverage.primary_trait_ids if t == "causal_analysis"), 1)


def _probe_with_related_signal(context_id: str, trait_id: str, related_trait_id: str) -> V2DirectProbeBlueprint:
    role_ids = [f"probe_role_{i}" for i in range(1, 6)]
    options = []
    mappings = []
    for i, role_id in enumerate(role_ids, start=1):
        if i == 1:
            delta = {trait_id: 1}
            mapping = V2ProbeOptionMapping(
                role_id=role_id, mapping_type="TRAIT_SIGNAL",
                trait_signals=[
                    TraitSignal(trait_id=trait_id, signal_role="PRIMARY", weight=1.0),
                    TraitSignal(trait_id=related_trait_id, signal_role="RELATED", weight=0.33),
                ],
            )
        else:
            delta = {}
            mapping = V2ProbeOptionMapping(role_id=role_id, mapping_type="NO_SIGNAL", no_signal_reason="예제")
        options.append(FinalizedOption(option_id=f"probe_q_o{i}", role_id=role_id, text=f"옵션 {i}", primary_trait_delta=delta))
        mappings.append(mapping)

    base_question = FinalizedQuestion(
        question_id="probe_q", context=context_id, target_traits=[], frame_id="direct_probe",
        question_text="Direct Probe 예제 질문", options=options,
    )
    return V2DirectProbeBlueprint(
        trait_id=trait_id, blueprint_id="probe_bp_1", option_mappings=mappings,
        allowed_context_ids=[context_id], question_frame_id="direct_probe", purpose="예제",
        base_question=base_question,
    )


class DirectProbeCoverageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.pack = build_example_context_pack()
        probe = _probe_with_related_signal(self.pack.context_id, "planning", "persistence_completion")
        self.pack_with_probe = self.pack.model_copy(update={"direct_probe_candidates": [probe]})

    def test_direct_probe_primary_and_related_are_distinguished(self) -> None:
        coverage = compute_context_trait_coverage(self.pack_with_probe, _KNOWN)
        self.assertIn("planning", coverage.primary_trait_ids)
        self.assertIn("planning", coverage.direct_probe_trait_ids)
        self.assertIn("persistence_completion", coverage.related_trait_ids)

    def test_related_only_trait_not_counted_as_primary(self) -> None:
        coverage = compute_context_trait_coverage(self.pack_with_probe, _KNOWN)
        self.assertNotIn("persistence_completion", coverage.primary_trait_ids)

    def test_related_trait_removed_from_uncovered(self) -> None:
        coverage = compute_context_trait_coverage(self.pack_with_probe, _KNOWN)
        self.assertNotIn("persistence_completion", coverage.uncovered_trait_ids)
        self.assertNotIn("planning", coverage.uncovered_trait_ids)


if __name__ == "__main__":
    unittest.main()
