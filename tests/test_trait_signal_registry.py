"""Sparse Trait Signal 테스트 — 지시서 §15 "Sparse Signal"."""

from __future__ import annotations

import unittest

from src.schemas.trait_signal import TraitSignal
from src.services.related_concept_registry import load_related_concepts_v2
from src.services.trait_ontology_v2 import load_trait_ontology_v2
from src.services.trait_signal_registry import (
    ROLE_ID_TO_TRAIT_SIGNALS,
    TraitSignalRegistryError,
    signals_for_role,
    validate_full_registry,
    validate_role_signals,
)

_KNOWN_TRAIT_IDS = {t.trait_id for t in load_trait_ontology_v2()}
_KNOWN_CONCEPT_IDS = {c.concept_id for c in load_related_concepts_v2()}


class TraitSignalWeightValidationTest(unittest.TestCase):
    def test_primary_must_be_1_0(self) -> None:
        with self.assertRaises(ValueError):
            TraitSignal(trait_id="causal_analysis", signal_role="PRIMARY", weight=0.9)

    def test_related_must_be_033_or_067(self) -> None:
        with self.assertRaises(ValueError):
            TraitSignal(trait_id="causal_analysis", signal_role="RELATED", weight=0.5)
        TraitSignal(trait_id="causal_analysis", signal_role="RELATED", weight=0.33)
        TraitSignal(trait_id="causal_analysis", signal_role="RELATED", weight=0.67)

    def test_related_rejects_arbitrary_precision(self) -> None:
        """LLM이나 임의 계산이 만들 법한 가짜 정밀도 값(예: 0.4123)을 거부한다."""

        with self.assertRaises(ValueError):
            TraitSignal(trait_id="causal_analysis", signal_role="RELATED", weight=0.4123)


class RegistryStructureTest(unittest.TestCase):
    def test_registry_is_not_empty(self) -> None:
        self.assertTrue(ROLE_ID_TO_TRAIT_SIGNALS)

    def test_full_registry_passes_validation(self) -> None:
        validate_full_registry(_KNOWN_TRAIT_IDS, _KNOWN_CONCEPT_IDS)  # 예외 없으면 통과

    def test_primary_count_between_1_and_2(self) -> None:
        for role_id, signals in ROLE_ID_TO_TRAIT_SIGNALS.items():
            with self.subTest(role_id=role_id):
                primary_count = sum(1 for s in signals if s.signal_role == "PRIMARY")
                self.assertGreaterEqual(primary_count, 1)
                self.assertLessEqual(primary_count, 2)

    def test_related_count_at_most_3(self) -> None:
        for role_id, signals in ROLE_ID_TO_TRAIT_SIGNALS.items():
            with self.subTest(role_id=role_id):
                related_count = sum(1 for s in signals if s.signal_role == "RELATED")
                self.assertLessEqual(related_count, 3)

    def test_total_signals_at_most_5(self) -> None:
        for role_id, signals in ROLE_ID_TO_TRAIT_SIGNALS.items():
            with self.subTest(role_id=role_id):
                self.assertLessEqual(len(signals), 5)

    def test_no_duplicate_trait_id_within_a_role(self) -> None:
        for role_id, signals in ROLE_ID_TO_TRAIT_SIGNALS.items():
            with self.subTest(role_id=role_id):
                trait_ids = [s.trait_id for s in signals]
                self.assertEqual(len(trait_ids), len(set(trait_ids)))

    def test_duplicated_team_coordination_role_id_has_identical_signals(self) -> None:
        """game seed와 planning blueprint 둘 다 role_id='team_coordination'을 쓴다 —
        Registry가 role_id로 조회되므로 두 곳 모두 collaboration_preference PRIMARY만
        받는 것이 일관돼야 한다(둘 다 실제로 같은 legacy Trait에 매핑돼 있다)."""

        signals = signals_for_role("team_coordination")
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].trait_id, "collaboration_preference")
        self.assertEqual(signals[0].signal_role, "PRIMARY")


class ValidateRoleSignalsRejectionTest(unittest.TestCase):
    def test_rejects_zero_primary(self) -> None:
        with self.assertRaises(TraitSignalRegistryError):
            validate_role_signals(
                "r", [TraitSignal(trait_id="causal_analysis", signal_role="RELATED", weight=0.33)],
                known_trait_ids=_KNOWN_TRAIT_IDS, known_concept_ids=_KNOWN_CONCEPT_IDS,
            )

    def test_rejects_more_than_2_primary(self) -> None:
        with self.assertRaises(TraitSignalRegistryError):
            validate_role_signals(
                "r",
                [
                    TraitSignal(trait_id="causal_analysis", signal_role="PRIMARY", weight=1.0),
                    TraitSignal(trait_id="pattern_finding", signal_role="PRIMARY", weight=1.0),
                    TraitSignal(trait_id="planning", signal_role="PRIMARY", weight=1.0),
                ],
                known_trait_ids=_KNOWN_TRAIT_IDS, known_concept_ids=_KNOWN_CONCEPT_IDS,
            )

    def test_rejects_more_than_3_related(self) -> None:
        primary = TraitSignal(trait_id="causal_analysis", signal_role="PRIMARY", weight=1.0)
        related = [
            TraitSignal(trait_id=t, signal_role="RELATED", weight=0.33)
            for t in ("pattern_finding", "planning", "tool_utilization", "visual_expression")
        ]
        with self.assertRaises(TraitSignalRegistryError):
            validate_role_signals(
                "r", [primary, *related],
                known_trait_ids=_KNOWN_TRAIT_IDS, known_concept_ids=_KNOWN_CONCEPT_IDS,
            )

    def test_rejects_more_than_5_total(self) -> None:
        primary = [
            TraitSignal(trait_id=t, signal_role="PRIMARY", weight=1.0)
            for t in ("causal_analysis", "pattern_finding")
        ]
        related = [
            TraitSignal(trait_id=t, signal_role="RELATED", weight=0.33)
            for t in ("planning", "tool_utilization", "visual_expression", "collaboration_preference")
        ]
        with self.assertRaises(TraitSignalRegistryError):
            validate_role_signals(
                "r", [*primary, *related],
                known_trait_ids=_KNOWN_TRAIT_IDS, known_concept_ids=_KNOWN_CONCEPT_IDS,
            )

    def test_rejects_duplicate_trait_id_across_signals(self) -> None:
        with self.assertRaises(TraitSignalRegistryError):
            validate_role_signals(
                "r",
                [
                    TraitSignal(trait_id="causal_analysis", signal_role="PRIMARY", weight=1.0),
                    TraitSignal(trait_id="causal_analysis", signal_role="RELATED", weight=0.33),
                ],
                known_trait_ids=_KNOWN_TRAIT_IDS, known_concept_ids=_KNOWN_CONCEPT_IDS,
            )

    def test_rejects_unknown_trait_id(self) -> None:
        with self.assertRaises(TraitSignalRegistryError):
            validate_role_signals(
                "r", [TraitSignal(trait_id="not_a_real_trait", signal_role="PRIMARY", weight=1.0)],
                known_trait_ids=_KNOWN_TRAIT_IDS, known_concept_ids=_KNOWN_CONCEPT_IDS,
            )

    def test_rejects_unknown_concept_id(self) -> None:
        with self.assertRaises(TraitSignalRegistryError):
            validate_role_signals(
                "r",
                [
                    TraitSignal(trait_id="causal_analysis", signal_role="PRIMARY", weight=1.0),
                    TraitSignal(
                        trait_id="systems_thinking", signal_role="RELATED", weight=0.33,
                        related_concept_ids=["not_a_real_concept"],
                    ),
                ],
                known_trait_ids=_KNOWN_TRAIT_IDS, known_concept_ids=_KNOWN_CONCEPT_IDS,
            )

    def test_dense_24_dimension_signal_list_is_rejected(self) -> None:
        """§4 "Dense 24차원 Signal 생성 차단" — 억지로 24개 Trait 전부에 Signal을 만들면
        전체 5개 상한에서 이미 걸린다."""

        all_traits = sorted(_KNOWN_TRAIT_IDS)[:24]
        signals = [TraitSignal(trait_id=all_traits[0], signal_role="PRIMARY", weight=1.0)] + [
            TraitSignal(trait_id=t, signal_role="RELATED", weight=0.33) for t in all_traits[1:]
        ]
        with self.assertRaises(TraitSignalRegistryError):
            validate_role_signals(
                "r", signals, known_trait_ids=_KNOWN_TRAIT_IDS, known_concept_ids=_KNOWN_CONCEPT_IDS,
            )


class SignalsForRoleTest(unittest.TestCase):
    def test_unknown_role_id_returns_empty_list_not_error(self) -> None:
        """등록 안 된 role_id(예: Conflict Resolution 확인 질문)는 조용히 빈 목록."""

        self.assertEqual(signals_for_role("no_such_role_at_all"), [])

    def test_known_role_returns_signals(self) -> None:
        signals = signals_for_role("cause_analysis")
        self.assertTrue(signals)
        self.assertEqual(signals[0].trait_id, "causal_analysis")
        self.assertEqual(signals[0].signal_role, "PRIMARY")


if __name__ == "__main__":
    unittest.main()
