"""Trait Probe Coverage 테스트 — 1.5단계 지시서 §14 "Coverage"."""

from __future__ import annotations

import unittest

from src.data.trait_ontology.trait_probe_capabilities_v2 import (
    CORE_TRAIT_IDS,
    DIRECTLY_MEASURABLE_TRAIT_IDS,
    LEGACY_RUNTIME_ACTIVE_TRAIT_IDS,
    NOT_PROBED_TRAIT_IDS,
    OBSERVABLE_TRAIT_IDS,
    RELATED_ONLY_TRAIT_IDS,
    TRAIT_PROBE_CAPABILITIES,
)
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAIT_IDS


class LegacyRuntimeActiveIsolationTest(unittest.TestCase):
    def test_legacy_runtime_active_equals_existing_12_traits(self) -> None:
        """Adaptive Target Planner·Stop Condition이 실제로 참조하는 유일한 집합은
        기존 12개와 정확히 같아야 한다 — v2 계산이 뭐라 하든 이 값은 절대 안 바뀐다."""

        self.assertEqual(LEGACY_RUNTIME_ACTIVE_TRAIT_IDS, set(VERTICAL_SLICE_TRAIT_IDS))
        self.assertEqual(len(LEGACY_RUNTIME_ACTIVE_TRAIT_IDS), 12)


class CoverageClassificationTest(unittest.TestCase):
    def test_core_trait_count_is_24(self) -> None:
        self.assertEqual(len(CORE_TRAIT_IDS), 24)

    def test_classification_partitions_core_trait_ids(self) -> None:
        """DIRECTLY_MEASURABLE/RELATED_ONLY/NOT_PROBED는 서로 겹치지 않고, 합치면
        CORE_TRAIT_IDS 전체가 돼야 한다."""

        self.assertEqual(DIRECTLY_MEASURABLE_TRAIT_IDS & RELATED_ONLY_TRAIT_IDS, set())
        self.assertEqual(DIRECTLY_MEASURABLE_TRAIT_IDS & NOT_PROBED_TRAIT_IDS, set())
        self.assertEqual(RELATED_ONLY_TRAIT_IDS & NOT_PROBED_TRAIT_IDS, set())
        self.assertEqual(
            DIRECTLY_MEASURABLE_TRAIT_IDS | RELATED_ONLY_TRAIT_IDS | NOT_PROBED_TRAIT_IDS,
            CORE_TRAIT_IDS,
        )

    def test_observable_is_directly_measurable_union_related_only(self) -> None:
        self.assertEqual(OBSERVABLE_TRAIT_IDS, DIRECTLY_MEASURABLE_TRAIT_IDS | RELATED_ONLY_TRAIT_IDS)

    def test_all_12_legacy_traits_are_directly_measurable(self) -> None:
        self.assertTrue(VERTICAL_SLICE_TRAIT_IDS <= DIRECTLY_MEASURABLE_TRAIT_IDS)

    def test_no_new_trait_is_directly_measurable_this_round(self) -> None:
        """1.5단계는 신규 Trait용 실제 PRIMARY 질문을 서빙하지 않으므로(§12, Gap 문서만
        작성), 신규 12개 중 DIRECTLY_MEASURABLE은 0개여야 한다 — Registry에 PRIMARY로
        등록된 신규 Trait이 하나라도 있으면 §16 금지("신규 Trait 질문 Runtime 등록")를
        어긴 것이다."""

        new_trait_ids = CORE_TRAIT_IDS - VERTICAL_SLICE_TRAIT_IDS
        self.assertEqual(new_trait_ids & DIRECTLY_MEASURABLE_TRAIT_IDS, set())

    def test_related_only_traits_are_not_mislabeled_as_active(self) -> None:
        """§7 핵심 요구사항: RELATED만 있는 신규 Trait를 Active(=DIRECTLY_MEASURABLE)로
        잘못 분류하지 않는다."""

        for trait_id in RELATED_ONLY_TRAIT_IDS:
            with self.subTest(trait_id=trait_id):
                self.assertGreater(TRAIT_PROBE_CAPABILITIES[trait_id].related_probe_count, 0)
                self.assertNotIn(trait_id, DIRECTLY_MEASURABLE_TRAIT_IDS)

    def test_role_id_count_alone_does_not_imply_measurability(self) -> None:
        """1단계의 "role_id 2개 ≈ Frame/Context 2개" 가정이 깨졌음을 구조적으로 확인한다:
        RELATED_ONLY Trait 중 하나를 골라 실제로는 PRIMARY가 전혀 없는데도 여러 Blueprint에
        걸쳐 RELATED만 존재한다는 걸 보여준다(role_id/Blueprint 다양성이 있어도
        DIRECTLY_MEASURABLE이 되지 않는다)."""

        self.assertIn("systems_thinking", RELATED_ONLY_TRAIT_IDS)
        cap = TRAIT_PROBE_CAPABILITIES["systems_thinking"]
        self.assertEqual(cap.primary_probe_count, 0)
        self.assertGreaterEqual(len(cap.blueprint_ids), 2)
        self.assertNotIn("systems_thinking", DIRECTLY_MEASURABLE_TRAIT_IDS)


class TraitProbeCapabilityFieldsTest(unittest.TestCase):
    def test_seed_only_trait_reaches_single_context_and_seed_frame(self) -> None:
        """PRIMARY가 Seed 한 곳에만 등록된 게 아니라 여러 Context/Blueprint에 걸친 Trait는
        이미 legacy 12개뿐이라(전부 DIRECTLY_MEASURABLE), Context/Frame이 구조적으로
        모두 3개/9개(Tail Blueprint 포함)로 넓다는 걸 확인한다."""

        cap = TRAIT_PROBE_CAPABILITIES["causal_analysis"]
        self.assertGreaterEqual(len(cap.blueprint_ids), 2)
        self.assertGreaterEqual(len(cap.context_ids), 2)

    def test_seed_and_backup_only_context_reachability_is_narrow(self) -> None:
        """Tail Blueprint에 전혀 등장하지 않는 Trait는 없지만(현재 12개 legacy trait는
        모두 Tail Blueprint에도 등록돼 있다), Seed/Backup만의 Context 도달 범위가 Trait별로
        1개(Seed/Backup 자신의 Context)로 좁게 계산되는지 개별 Registry Key 단위로
        확인한다."""

        from src.data.trait_ontology.trait_probe_capabilities_v2 import _reachable_context_and_frame_ids

        contexts, frames = _reachable_context_and_frame_ids("seed", "game_seed_01_blueprint")
        self.assertEqual(contexts, {"game"})
        self.assertEqual(frames, {"seed_frame"})

        contexts, frames = _reachable_context_and_frame_ids("backup", "game_backup_01")
        self.assertEqual(contexts, {"game"})
        self.assertEqual(frames, {"backup"})

    def test_tail_blueprint_reaches_all_contexts_and_frames(self) -> None:
        from src.data.contexts.context_definitions import VERTICAL_SLICE_CONTEXT_IDS
        from src.data.question_frames.frame_role_map import QUESTION_FRAME_TEXT
        from src.data.trait_ontology.trait_probe_capabilities_v2 import _reachable_context_and_frame_ids

        contexts, frames = _reachable_context_and_frame_ids("tail_blueprint", "problem_response_v1")
        self.assertEqual(contexts, set(VERTICAL_SLICE_CONTEXT_IDS))
        self.assertEqual(frames, set(QUESTION_FRAME_TEXT.keys()))


if __name__ == "__main__":
    unittest.main()
