"""v2 Career Profile 후보 선정 테스트 — 2026-08-23 Trait Ontology v2(2.6단계) §4/§5."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from src.engines.profile_engine_v2 import select_profile_highlight_traits_v2
from src.schemas.evidence import ContrastResolutionRecord, ContrastResolutionStatus
from src.schemas.trait import TraitDefinition
from src.schemas.trait_vector_snapshot import TraitVectorEntry


def _trait(trait_id: str) -> TraitDefinition:
    return TraitDefinition(
        trait_id=trait_id, label=trait_id, parent_dimension="테스트 차원", definition=f"{trait_id} 정의",
        positive_indicators=["a"], conflicting_indicators=["b"], source_references=["c"],
        trait_scope="shared", minimum_context_count=1, primary_vector_group="cognitive",
    )


def _entry(trait_id: str, status: str, tendency: float | None) -> TraitVectorEntry:
    return TraitVectorEntry(
        trait_id=trait_id, primary_signal_sum=1.0, related_signal_sum=0.0,
        confirmed_related_signal_sum=0.0, primary_evidence_count=3, related_evidence_count=0,
        context_count=2, frame_count=2, question_count=3, tendency_score=tendency,
        evidence_confidence="primary_evidence", status=status,
    )


class HighlightSelectionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.trait_ids = [f"t{i:02d}" for i in range(10)]
        self.definitions = {tid: _trait(tid) for tid in self.trait_ids}

    def test_strong_traits_prioritized(self) -> None:
        entries = {tid: _entry(tid, "STRONG", 1.0) for tid in self.trait_ids[:6]}
        entries.update({tid: _entry(tid, "NOT_PROBED", None) for tid in self.trait_ids[6:]})
        selected = select_profile_highlight_traits_v2(entries, self.definitions)
        self.assertGreaterEqual(len(selected), 5)
        self.assertLessEqual(len(selected), 8)
        # STRONG 6개가 전부 우선 선택돼야 한다.
        selected_ids = {c.trait_definition.trait_id for c in selected[:6]}
        self.assertEqual(selected_ids, set(self.trait_ids[:6]))

    def test_backfills_with_not_probed_when_too_few_strong(self) -> None:
        entries = {tid: _entry(tid, "NOT_PROBED", None) for tid in self.trait_ids}
        selected = select_profile_highlight_traits_v2(entries, self.definitions)
        self.assertEqual(len(selected), 5)  # MIN_HIGHLIGHTS
        for c in selected:
            self.assertEqual(c.entry.status, "NOT_PROBED")

    def test_conflicting_excluded_from_backfill(self) -> None:
        """CLAUDE.md — Missing/Insufficient/Conflicting을 정상 점수처럼 취급하지 않는다.
        상충 Trait를 확정 강점 후보처럼 backfill에 넣지 않는다."""

        entries = {tid: _entry(tid, "CONFLICTING", None) for tid in self.trait_ids[:3]}
        entries.update({tid: _entry(tid, "NOT_PROBED", None) for tid in self.trait_ids[3:]})
        selected = select_profile_highlight_traits_v2(entries, self.definitions)
        selected_ids = {c.trait_definition.trait_id for c in selected}
        self.assertTrue(selected_ids.isdisjoint(set(self.trait_ids[:3])))

    def test_missing_entry_treated_as_not_probed_not_zero(self) -> None:
        """snapshot_entries에 아예 없는 Trait(=완전 미관찰)는 0점이 아니라 NOT_PROBED로
        취급돼야 한다."""

        entries: dict[str, TraitVectorEntry] = {}
        selected = select_profile_highlight_traits_v2(entries, self.definitions)
        for c in selected:
            self.assertEqual(c.entry.status, "NOT_PROBED")
            self.assertIsNone(c.entry.tendency_score)

    def test_deprioritized_trait_pushed_to_end_of_its_tier(self) -> None:
        entries = {tid: _entry(tid, "STRONG", 1.0) for tid in self.trait_ids[:3]}
        resolutions = {
            "c1": ContrastResolutionRecord(
                contrast_id="c1", status=ContrastResolutionStatus.RESOLVED_OPPOSITE,
                resolved_at_answer_id="ans_1", opposite_trait_id=self.trait_ids[0],
            )
        }
        selected = select_profile_highlight_traits_v2(entries, self.definitions, resolutions)
        strong_selected = [c for c in selected if c.entry.status == "STRONG"]
        self.assertEqual(strong_selected[-1].trait_definition.trait_id, self.trait_ids[0])


if __name__ == "__main__":
    unittest.main()
