"""Context Pack Registry 계약 테스트 — 2026-08-23 Trait Ontology v2(2.7단계) §1/§2/§6/§7."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from src.data.context_packs._example_pack_builder import build_example_context_pack
from src.data.contexts.context_definitions import CONTEXT_IDS
from src.services.context_pack_registry import (
    CONTEXT_ACTIVATION_BATCHES,
    ContextPackRegistry,
    discover_context_packs,
)


class EmptyRegistryBaselineTest(unittest.TestCase):
    """2026-08-23 2.8단계: Context 확장 에이전트들이 실제 Pack을 병렬로 추가하면서
    이 클래스 이름이 더 이상 문자 그대로는 맞지 않는다 — 그래도 검증 대상 불변식은
    그대로다: 실제 Pack이 몇 개든 검수(reviewer_1 APPROVE) 전에는 기존 3개 Context
    지원 목록이 절대 바뀌면 안 된다(§9)."""

    def test_discovered_real_packs_have_no_structural_errors(self) -> None:
        """실제 Pack이 있든 없든, 발견된 Pack은 전부 구조적으로 올바라야 한다(Fail-Fast
        가 이미 각 Pack 모듈 import 시점에 강제한다 — 여기서는 discover_context_packs()
        가 그 결과를 조용히 삼기지 않는지만 확인한다)."""

        packs, errors = discover_context_packs()
        self.assertEqual(errors, {})
        for context_id, pack in packs.items():
            self.assertEqual(pack.context_id, context_id)

    def test_assessment_supported_context_ids_unchanged_with_no_packs(self) -> None:
        registry = ContextPackRegistry(known_context_ids=frozenset(CONTEXT_IDS))
        result = registry.assessment_supported_context_ids(["game", "media", "school_life"])
        self.assertEqual(result, ["game", "media", "school_life"])

    def test_example_builder_is_not_auto_discovered(self) -> None:
        """`_example_pack_builder.py`는 `CONTEXT_PACK` 상수를 노출하지 않으므로 자동
        발견 대상이 아니다(파일명이 `_`로 시작해 애초에 스캔에서도 제외된다)."""

        packs, _errors = discover_context_packs()
        self.assertNotIn("example_context", packs)


class OntologyValidationTest(unittest.TestCase):
    def test_unknown_trait_id_excludes_pack_with_ontology_error(self) -> None:
        pack = build_example_context_pack()
        registry = ContextPackRegistry(
            known_context_ids=frozenset({pack.context_id}),
            known_trait_ids=frozenset(),  # 이 Pack이 쓰는 causal_analysis/pattern_finding 둘 다 없음
            _discovered=({pack.context_id: pack}, {}),
        )
        self.assertIsNone(registry.get_pack(pack.context_id))
        self.assertIn(pack.context_id, registry.ontology_errors())
        self.assertIn("Trait", registry.ontology_errors()[pack.context_id])

    def test_known_trait_ids_pack_registers_successfully(self) -> None:
        pack = build_example_context_pack()
        registry = ContextPackRegistry(
            known_context_ids=frozenset({pack.context_id}),
            known_trait_ids=frozenset({"causal_analysis", "pattern_finding"}),
            _discovered=({pack.context_id: pack}, {}),
        )
        self.assertIsNotNone(registry.get_pack(pack.context_id))
        self.assertEqual(registry.ontology_errors(), {})

    def test_unregistered_context_id_excludes_pack(self) -> None:
        pack = build_example_context_pack()
        registry = ContextPackRegistry(
            known_context_ids=frozenset(),  # example_context가 known 집합에 없음
            known_trait_ids=frozenset({"causal_analysis", "pattern_finding"}),
            _discovered=({pack.context_id: pack}, {}),
        )
        self.assertIsNone(registry.get_pack(pack.context_id))
        self.assertIn(pack.context_id, registry.ontology_errors())

    def test_discovery_errors_preserved_not_silently_dropped(self) -> None:
        registry = ContextPackRegistry(
            known_context_ids=frozenset(CONTEXT_IDS),
            _discovered=({}, {"broken_pack_module": "ValidationError: something wrong"}),
        )
        self.assertEqual(registry.discovery_errors(), {"broken_pack_module": "ValidationError: something wrong"})


class ReviewApprovalGateTest(unittest.TestCase):
    """§1/§6 "Pack 미검수 시 지원 Context로 활성화되지 않음" — Fail-Closed."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.review_dir = Path(self.tmpdir.name)
        self.pack = build_example_context_pack("business")  # 실제 배치-1 Context ID 재사용
        self.registry = ContextPackRegistry(
            known_context_ids=frozenset({"business"}),
            known_trait_ids=frozenset({"causal_analysis", "pattern_finding"}),
            review_status_dir=self.review_dir,
            _discovered=({"business": self.pack}, {}),
        )

    def _write_review_status(self, entries: list[dict]) -> None:
        path = self.review_dir / "business_review_status.json"
        path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")

    def test_missing_review_status_file_is_not_approved(self) -> None:
        self.assertFalse(self.registry.is_pack_review_approved("business"))

    def test_all_tbd_review_status_is_not_approved(self) -> None:
        required = sorted(self.registry.required_review_keys(self.pack))
        self._write_review_status([{"blueprint_id": k, "reviewer_1_status": "TBD"} for k in required])
        self.assertFalse(self.registry.is_pack_review_approved("business"))

    def test_partial_approval_is_not_approved(self) -> None:
        required = sorted(self.registry.required_review_keys(self.pack))
        entries = [{"blueprint_id": k, "reviewer_1_status": "APPROVE"} for k in required]
        entries[0]["reviewer_1_status"] = "TBD"  # 하나만 미승인
        self._write_review_status(entries)
        self.assertFalse(self.registry.is_pack_review_approved("business"))

    def test_all_approved_is_approved(self) -> None:
        required = sorted(self.registry.required_review_keys(self.pack))
        self._write_review_status([{"blueprint_id": k, "reviewer_1_status": "APPROVE"} for k in required])
        self.assertTrue(self.registry.is_pack_review_approved("business"))

    def test_activation_batch_excludes_unapproved_business(self) -> None:
        result = self.registry.assessment_supported_context_ids(["game", "media", "school_life"])
        self.assertNotIn("business", result)

    def test_activation_batch_includes_approved_business(self) -> None:
        required = sorted(self.registry.required_review_keys(self.pack))
        self._write_review_status([{"blueprint_id": k, "reviewer_1_status": "APPROVE"} for k in required])
        result = self.registry.assessment_supported_context_ids(["game", "media", "school_life"])
        self.assertIn("business", result)
        self.assertEqual(result[:3], ["game", "media", "school_life"])

    def test_corrupted_review_status_file_fails_closed_not_crash(self) -> None:
        path = self.review_dir / "business_review_status.json"
        path.write_text("이건 JSON이 아니다", encoding="utf-8")
        self.assertFalse(self.registry.is_pack_review_approved("business"))


class ActivationBatchDefinitionTest(unittest.TestCase):
    def test_batches_match_task_specification(self) -> None:
        self.assertEqual(CONTEXT_ACTIVATION_BATCHES[1], frozenset({"business", "science", "sports"}))
        self.assertEqual(
            CONTEXT_ACTIVATION_BATCHES[2], frozenset({"making", "volunteer", "writing", "travel"})
        )
        self.assertEqual(
            CONTEXT_ACTIVATION_BATCHES[3],
            frozenset({"art_design", "cooking", "fashion_beauty", "history_humanities", "law_politics"}),
        )

    def test_all_batch_context_ids_are_known_context_definitions(self) -> None:
        all_batch_ids = {c for batch in CONTEXT_ACTIVATION_BATCHES.values() for c in batch}
        self.assertTrue(all_batch_ids.issubset(CONTEXT_IDS))


class RealDirectoryAutoDiscoveryTest(unittest.TestCase):
    """실제 `src/data/context_packs/` 디렉터리에 파일 하나를 임시로 놓아, Context 제작
    에이전트가 실제로 겪을 경로(새 파일만 추가 → 자동 발견)가 동작하는지 확인한다.
    테스트 종료 시 파일과 모듈 캐시를 반드시 정리한다."""

    def setUp(self) -> None:
        import src.data.context_packs as package

        self.package_dir = Path(package.__file__).resolve().parent
        self.pack_file = self.package_dir / "zz_test_registry_temp_pack.py"
        self.module_name = "src.data.context_packs.zz_test_registry_temp_pack"
        self.addCleanup(self._cleanup)

    def _cleanup(self) -> None:
        if self.pack_file.exists():
            self.pack_file.unlink()
        sys.modules.pop(self.module_name, None)
        cache_dir = self.package_dir / "__pycache__"
        if cache_dir.exists():
            for f in cache_dir.glob("zz_test_registry_temp_pack*"):
                f.unlink()

    def test_new_pack_file_is_auto_discovered_without_touching_registry(self) -> None:
        # 2026-08-23 2.8단계: 실제 배치 Context id(business 등)는 다른 작업자가 동시에
        # 실제 Pack을 만들고 있어 충돌할 수 있다 — 이 테스트는 발견 메커니즘 자체만
        # 검증하면 되므로, 실제 배치와 무관한 합성 context_id를 쓴다(기본값 그대로).
        self.pack_file.write_text(
            "from src.data.context_packs._example_pack_builder import build_example_context_pack\n"
            "CONTEXT_PACK = build_example_context_pack()\n",
            encoding="utf-8",
        )
        packs, errors = discover_context_packs()
        self.assertEqual(errors, {})
        self.assertIn("example_context", packs)
        self.assertEqual(packs["example_context"].context_id, "example_context")


if __name__ == "__main__":
    unittest.main()
