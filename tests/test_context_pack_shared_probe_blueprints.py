"""ContextPack 공용 Adaptive Probe Blueprint 구조 테스트 — 2026-08-23 Trait Ontology
v2(2.9단계) §5/§13."""

from __future__ import annotations

import unittest

from src.data.contexts.context_activation_batches import ALL_BATCH_CONTEXT_IDS
from src.data.questions.context_pack_shared_probe_blueprints import CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS
from src.data.questions.trait_v2_direct_probe_blueprints import V2_DIRECT_PROBE_BLUEPRINTS


class SharedProbePoolStructureTest(unittest.TestCase):
    def test_at_least_six_distinct_blueprints(self) -> None:
        self.assertGreaterEqual(len(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS), 6)

    def test_all_start_as_draft_review_status(self) -> None:
        for bp in CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS:
            self.assertEqual(bp.review_status, "draft")

    def test_allowed_context_ids_are_all_batch_contexts_only(self) -> None:
        for bp in CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS:
            self.assertEqual(set(bp.allowed_context_ids), set(ALL_BATCH_CONTEXT_IDS))

    def test_role_id_and_trait_signal_identical_to_original_blueprint(self) -> None:
        """§5 "Option role_id·Trait Signal은 원본 Blueprint와 동일" — 공용 Adaptive
        Probe는 원본 14개의 role_id→Trait Signal Mapping을 그대로 재사용한다(문구·id만
        새로 만든다)."""

        originals_by_trait = {bp.trait_id: bp for bp in V2_DIRECT_PROBE_BLUEPRINTS}
        seen_trait_ids = set()
        for shared_bp in CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS:
            original = next(
                (b for b in V2_DIRECT_PROBE_BLUEPRINTS if shared_bp.blueprint_id == f"pack_shared_{b.blueprint_id}"),
                None,
            )
            self.assertIsNotNone(original, f"{shared_bp.blueprint_id}의 원본을 찾을 수 없다")
            self.assertEqual(shared_bp.trait_id, original.trait_id)
            for shared_mapping, original_mapping in zip(shared_bp.option_mappings, original.option_mappings):
                self.assertEqual(shared_mapping.role_id, original_mapping.role_id)
                self.assertEqual(shared_mapping.mapping_type, original_mapping.mapping_type)
                self.assertEqual(shared_mapping.trait_signals, original_mapping.trait_signals)
            seen_trait_ids.add(shared_bp.trait_id)
        self.assertEqual(seen_trait_ids, set(originals_by_trait))

    def test_no_id_collision_with_original_14(self) -> None:
        shared_ids = {b.blueprint_id for b in CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS}
        original_ids = {b.blueprint_id for b in V2_DIRECT_PROBE_BLUEPRINTS}
        self.assertEqual(shared_ids & original_ids, set())

    def test_all_blueprints_individually_valid(self) -> None:
        # 생성 시점에 이미 Pydantic Cross-field Validator를 통과했다(import 시 예외 없음) —
        # 여기서는 그 사실을 명시적으로 재확인한다(Option 5개, Target 정확히 1개 등).
        for bp in CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS:
            self.assertEqual(len(bp.option_mappings), 5)
            self.assertEqual(bp.base_question.context in bp.allowed_context_ids, True)


if __name__ == "__main__":
    unittest.main()
