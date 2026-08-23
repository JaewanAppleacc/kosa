"""Context Pack Registry 계약 테스트 — 2026-08-23 Trait Ontology v2(2.7단계) §1/§2/§6/§7."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from src.data.context_packs._example_pack_builder import build_example_context_pack
from src.data.contexts.context_definitions import CONTEXT_IDS
from src.services.context_pack_registry import (
    ALL_BATCH_CONTEXT_IDS,
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


class ReviewArtifactPathConsistencyTest(unittest.TestCase):
    """2026-08-24 사람 검수 시작 전 정합성 점검 — `review_artifact_paths`가 실제
    검수 상태 JSON을 가리키지 않으면 검수 화면에서 그 Pack의 실제 검수 파일을 찾을
    수 없다(business/science/making/law_politics 4개 Pack이 Mapping Audit 문서만
    가리키고 있던 버그). 12개 Pack 전부에 이 불변식을 강제한다."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[1]
        cls.packs, cls.discovery_errors = discover_context_packs()

    def test_all_12_batch_packs_discovered_without_errors(self) -> None:
        self.assertEqual(self.discovery_errors, {})
        self.assertEqual(set(ALL_BATCH_CONTEXT_IDS), set(self.packs) & set(ALL_BATCH_CONTEXT_IDS))
        self.assertEqual(len(ALL_BATCH_CONTEXT_IDS), 12)

    def test_every_pack_review_artifact_paths_include_own_review_status_json(self) -> None:
        for context_id in ALL_BATCH_CONTEXT_IDS:
            pack = self.packs[context_id]
            expected = f"data/reviews/context_packs/{context_id}_review_status.json"
            self.assertIn(
                expected,
                pack.review_artifact_paths,
                f"{context_id}: review_artifact_paths에 실제 검수 상태 JSON 경로가 "
                f"없다 — {pack.review_artifact_paths}",
            )

    def test_review_status_json_path_context_id_matches_pack_context_id(self) -> None:
        for context_id in ALL_BATCH_CONTEXT_IDS:
            pack = self.packs[context_id]
            for path in pack.review_artifact_paths:
                if path.startswith("data/reviews/context_packs/") and path.endswith("_review_status.json"):
                    filename = Path(path).name
                    path_context_id = filename[: -len("_review_status.json")]
                    self.assertEqual(
                        path_context_id,
                        context_id,
                        f"{context_id} Pack의 review_artifact_paths에 다른 Context "
                        f"({path_context_id})의 검수 파일 경로가 섞여 있다: {path}",
                    )

    def test_every_review_artifact_path_actually_exists_on_disk(self) -> None:
        for context_id in ALL_BATCH_CONTEXT_IDS:
            pack = self.packs[context_id]
            self.assertGreater(len(pack.review_artifact_paths), 0, f"{context_id}: review_artifact_paths가 비어있다")
            for path in pack.review_artifact_paths:
                full_path = self.repo_root / path
                self.assertTrue(full_path.is_file(), f"{context_id}: {path} 파일이 실제로 없다")

    def test_no_duplicate_review_artifact_paths_within_a_pack(self) -> None:
        for context_id in ALL_BATCH_CONTEXT_IDS:
            paths = self.packs[context_id].review_artifact_paths
            self.assertEqual(
                len(paths), len(set(paths)), f"{context_id}: review_artifact_paths에 중복 경로가 있다: {paths}"
            )

    def test_reading_review_artifact_paths_does_not_modify_real_review_json(self) -> None:
        """이 파일이 12개 Pack의 review_artifact_paths를 읽고 실제 파일 존재를
        확인하는 과정 자체가 실제 검수 상태 JSON 내용을 바이트 하나도 바꾸지 않는다는
        것을 SHA-256으로 증명한다(지시서 §4 "작업 전후 SHA-256 또는 byte 비교
        테스트를 추가하세요")."""

        review_dir = self.repo_root / "data" / "reviews" / "context_packs"
        shared_probe_path = (
            self.repo_root / "data" / "reviews" / "context_pack_shared_probes_review_status.json"
        )

        def _snapshot() -> dict[str, str]:
            snapshot = {
                str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(review_dir.glob("*.json"))
            }
            if shared_probe_path.exists():
                snapshot[str(shared_probe_path)] = hashlib.sha256(shared_probe_path.read_bytes()).hexdigest()
            return snapshot

        before = _snapshot()
        for context_id in ALL_BATCH_CONTEXT_IDS:
            for path in self.packs[context_id].review_artifact_paths:
                (self.repo_root / path).is_file()  # 존재 확인만 — 읽기 전용 접근
        after = _snapshot()
        self.assertEqual(before, after, "검수 상태 JSON 내용이 바뀌었다 — 절대 금지 위반")


if __name__ == "__main__":
    unittest.main()
