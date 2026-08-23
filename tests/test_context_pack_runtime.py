"""ContextPack Runtime Adapter 계약 테스트 — 2026-08-23 Trait Ontology v2(2.8단계) §4."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.data.context_packs._example_pack_builder import build_example_context_pack
from src.services.context_pack_registry import ContextPackRegistry
from src.services.context_pack_runtime import ContextPackRuntime


class _FlagState:
    """테스트 안에서 Feature Flag를 켰다 껐다 하기 위한 mutable 컨테이너."""

    def __init__(self, value: bool) -> None:
        self.value = value

    def __call__(self) -> bool:
        return self.value


class ContextPackRuntimeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.review_dir = Path(self.tmpdir.name)
        # 실제 배치-1 Context ID를 재사용해 known_context_ids 검증까지 통과시킨다.
        self.pack = build_example_context_pack("business")
        self.registry = ContextPackRegistry(
            known_context_ids=frozenset({"business"}),
            known_trait_ids=frozenset({"causal_analysis", "pattern_finding"}),
            review_status_dir=self.review_dir,
            _discovered=({"business": self.pack}, {}),
        )
        self.flag_on = _FlagState(True)
        self.flag_off = _FlagState(False)

    def _approve_all(self) -> None:
        required = sorted(self.registry.required_review_keys(self.pack))
        path = self.review_dir / "business_review_status.json"
        path.write_text(
            json.dumps([{"blueprint_id": k, "reviewer_1_status": "APPROVE"} for k in required], ensure_ascii=False),
            encoding="utf-8",
        )

    def test_legacy_context_always_returns_none_regardless_of_flag(self) -> None:
        runtime = ContextPackRuntime(self.registry, self.flag_on, frozenset({"game", "media", "school_life"}))
        self.assertIsNone(runtime.get_routing_question("game"))
        self.assertIsNone(runtime.get_anchor_presentation("game", "anchor_a"))
        self.assertIsNone(runtime.get_seed_question("game", "anchor_a"))
        self.assertEqual(runtime.get_backup_candidates("game", "anchor_a"), [])
        self.assertEqual(runtime.get_direct_probe_candidates("game"), [])

    def test_flag_off_pack_context_returns_none_even_if_approved(self) -> None:
        self._approve_all()
        runtime = ContextPackRuntime(self.registry, self.flag_off, frozenset({"game", "media", "school_life"}))
        self.assertIsNone(runtime.get_routing_question("business"))
        self.assertIsNone(runtime.get_seed_question("business", "anchor_a"))
        self.assertNotIn("business", runtime.active_pack_context_ids())

    def test_flag_on_unapproved_pack_returns_none(self) -> None:
        runtime = ContextPackRuntime(self.registry, self.flag_on, frozenset({"game", "media", "school_life"}))
        self.assertIsNone(runtime.get_routing_question("business"))
        self.assertIsNone(runtime.get_seed_question("business", "anchor_a"))
        self.assertNotIn("business", runtime.active_pack_context_ids())

    def test_flag_on_approved_pack_returns_real_data(self) -> None:
        self._approve_all()
        runtime = ContextPackRuntime(self.registry, self.flag_on, frozenset({"game", "media", "school_life"}))
        self.assertIn("business", runtime.active_pack_context_ids())

        routing = runtime.get_routing_question("business")
        self.assertIsNotNone(routing)
        self.assertEqual(routing.context_id, "business")

        presentation = runtime.get_anchor_presentation("business", "anchor_a")
        self.assertIsNotNone(presentation)
        self.assertEqual(presentation.anchor_id, "anchor_a")

        seed = runtime.get_seed_question("business", "anchor_a")
        self.assertIsNotNone(seed)
        self.assertEqual(seed.question_id, "business_seed_anchor_a")

        backups = runtime.get_backup_candidates("business", "anchor_a")
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].question_id, "business_backup_anchor_a")

    def test_anchor_isolation_seed_never_leaks_across_anchors(self) -> None:
        self._approve_all()
        runtime = ContextPackRuntime(self.registry, self.flag_on, frozenset({"game", "media", "school_life"}))
        seed_a = runtime.get_seed_question("business", "anchor_a")
        seed_b = runtime.get_seed_question("business", "anchor_b")
        self.assertNotEqual(seed_a.question_id, seed_b.question_id)
        backup_a = runtime.get_backup_candidates("business", "anchor_a")[0]
        backup_b = runtime.get_backup_candidates("business", "anchor_b")[0]
        self.assertNotEqual(backup_a.question_id, backup_b.question_id)

    def test_unknown_anchor_id_returns_none(self) -> None:
        self._approve_all()
        runtime = ContextPackRuntime(self.registry, self.flag_on, frozenset({"game", "media", "school_life"}))
        self.assertIsNone(runtime.get_seed_question("business", "no_such_anchor"))
        self.assertEqual(runtime.get_backup_candidates("business", "no_such_anchor"), [])

    def test_context_outside_activation_batches_never_active(self) -> None:
        # example_context는 CONTEXT_ACTIVATION_BATCHES 어디에도 없다 — 검수돼도 활성화 안 됨.
        pack = build_example_context_pack()  # context_id="example_context"
        registry = ContextPackRegistry(
            known_context_ids=frozenset({"example_context"}),
            known_trait_ids=frozenset({"causal_analysis", "pattern_finding"}),
            review_status_dir=self.review_dir,
            _discovered=({"example_context": pack}, {}),
        )
        required = sorted(registry.required_review_keys(pack))
        (self.review_dir / "example_context_review_status.json").write_text(
            json.dumps([{"blueprint_id": k, "reviewer_1_status": "APPROVE"} for k in required], ensure_ascii=False),
            encoding="utf-8",
        )
        runtime = ContextPackRuntime(registry, self.flag_on, frozenset({"game", "media", "school_life"}))
        self.assertIsNone(runtime.get_routing_question("example_context"))
        self.assertNotIn("example_context", runtime.active_pack_context_ids())


if __name__ == "__main__":
    unittest.main()
