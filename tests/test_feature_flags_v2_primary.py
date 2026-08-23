"""ENABLE_TRAIT_VECTOR_V2_PRIMARY Flag 테스트 — 2026-08-23 Trait Ontology v2(2.6단계) §2."""

from __future__ import annotations

import unittest

from src.services.feature_flags import trait_vector_v2_direct_probes_enabled, trait_vector_v2_primary_enabled


class TraitVectorV2PrimaryFlagTest(unittest.TestCase):
    def test_default_off(self) -> None:
        self.assertFalse(trait_vector_v2_primary_enabled(env={}))

    def test_explicit_true_variants_enable(self) -> None:
        for value in ("1", "true", "True", "yes", "YES"):
            with self.subTest(value=value):
                self.assertTrue(trait_vector_v2_primary_enabled(env={"ENABLE_TRAIT_VECTOR_V2_PRIMARY": value}))

    def test_garbage_disables(self) -> None:
        self.assertFalse(trait_vector_v2_primary_enabled(env={"ENABLE_TRAIT_VECTOR_V2_PRIMARY": "banana"}))

    def test_independent_from_direct_probes_flag(self) -> None:
        """§2 — 두 Flag는 서로를 함의하지 않는다."""

        env_primary_only = {"ENABLE_TRAIT_VECTOR_V2_PRIMARY": "true"}
        self.assertTrue(trait_vector_v2_primary_enabled(env=env_primary_only))
        self.assertFalse(trait_vector_v2_direct_probes_enabled(env=env_primary_only))

        env_direct_probes_only = {"ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES": "true"}
        self.assertTrue(trait_vector_v2_direct_probes_enabled(env=env_direct_probes_only))
        self.assertFalse(trait_vector_v2_primary_enabled(env=env_direct_probes_only))

        env_both = {"ENABLE_TRAIT_VECTOR_V2_PRIMARY": "true", "ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES": "true"}
        self.assertTrue(trait_vector_v2_primary_enabled(env=env_both))
        self.assertTrue(trait_vector_v2_direct_probes_enabled(env=env_both))


if __name__ == "__main__":
    unittest.main()
