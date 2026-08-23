"""ContextPack 검수 UI 통합 테스트 — 2026-08-23 Trait Ontology v2(2.8단계) §9.

T·S·L이 Pack 파일을 추가하기만 하면(Context마다 UI 코드를 새로 만들지 않아도) 자동으로
검수 목록에 나타나는지를, 실제 `src/data/context_packs/` 디렉터리에 임시 Pack 파일을
하나 놓아 검증한다(`test_context_pack_registry.py::RealDirectoryAutoDiscoveryTest`와
같은 패턴). 검수 상태 파일은 임시 디렉터리에만 쓴다 — 공유 `data/reviews/context_packs/`
디렉터리는 절대 건드리지 않는다."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from src.data.contexts.context_definitions import CONTEXT_IDS
from src.review_ui import context_pack_review_service as cprs
from src.services.context_pack_registry import ContextPackRegistry
from src.services.trait_ontology_v2 import load_trait_ontology_v2


class BuildContextPackListTest(unittest.TestCase):
    """실제 `src/data/context_packs/`를 그대로 스캔한다 — T·S·L의 실제 Pack이 있으면
    자동으로 잡히고, 없어도(구조 검증만 통과하면) 실패하지 않는다."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.registry = ContextPackRegistry(
            known_context_ids=frozenset(CONTEXT_IDS), review_status_dir=Path(self.tmpdir.name),
        )
        self.trait_definitions = {t.trait_id: t for t in load_trait_ontology_v2()}

    def test_returns_response_without_error_regardless_of_pack_count(self) -> None:
        response = cprs.build_context_pack_list(self.registry, self.trait_definitions)
        self.assertEqual(response.discovery_errors, {})
        context_ids = [p.context_id for p in response.packs]
        self.assertEqual(context_ids, sorted(context_ids))

    def test_unapproved_pack_shows_up_but_not_active(self) -> None:
        # 검수 상태 파일을 아예 안 만들었으므로(임시 디렉터리가 비어 있다) 실제 Pack이
        # 있다면 전부 is_active=False로 나와야 한다(Claude가 자동 APPROVE하지 않는다).
        response = cprs.build_context_pack_list(self.registry, self.trait_definitions)
        for item in response.packs:
            self.assertFalse(item.is_active)

    def test_each_pack_exposes_minimum_required_fields(self) -> None:
        response = cprs.build_context_pack_list(self.registry, self.trait_definitions)
        for item in response.packs:
            self.assertEqual(len(item.anchors), 5)
            kinds = {q.kind for q in item.questions}
            self.assertIn("routing", kinds)
            self.assertIn("seed", kinds)
            self.assertIn("anchor_backup", kinds)
            for question in item.questions:
                for option in question.options:
                    self.assertIn(option.mapping_type, ("TRAIT_SIGNAL", "NO_SIGNAL"))
            self.assertIsInstance(item.coverage.uncovered_trait_ids, list)


class SyntheticPackAutoDiscoveryTest(unittest.TestCase):
    """실제 디렉터리에 합성 Pack 파일을 하나 임시로 놓아, review_ui 쪽 코드를 전혀
    고치지 않고도 새 Pack이 검수 목록에 나타나는지 끝까지 확인한다."""

    def setUp(self) -> None:
        import src.data.context_packs as package

        self.package_dir = Path(package.__file__).resolve().parent
        self.pack_file = self.package_dir / "zz_test_review_ui_temp_pack.py"
        self.module_name = "src.data.context_packs.zz_test_review_ui_temp_pack"
        self.addCleanup(self._cleanup)
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

    def _cleanup(self) -> None:
        if self.pack_file.exists():
            self.pack_file.unlink()
        sys.modules.pop(self.module_name, None)
        cache_dir = self.package_dir / "__pycache__"
        if cache_dir.exists():
            for f in cache_dir.glob("zz_test_review_ui_temp_pack*"):
                f.unlink()

    def test_new_pack_file_appears_in_review_list_without_ui_code_changes(self) -> None:
        self.pack_file.write_text(
            "from src.data.context_packs._example_pack_builder import build_example_context_pack\n"
            "CONTEXT_PACK = build_example_context_pack()\n",
            encoding="utf-8",
        )
        registry = ContextPackRegistry(
            known_context_ids=frozenset({"example_context"}),
            known_trait_ids=frozenset({"causal_analysis", "pattern_finding"}),
            review_status_dir=Path(self.tmpdir.name),
        )
        trait_definitions = {t.trait_id: t for t in load_trait_ontology_v2()}
        response = cprs.build_context_pack_list(registry, trait_definitions)
        self.assertIn("example_context", [p.context_id for p in response.packs])


class ReviewAppEndpointTest(unittest.TestCase):
    """실제 review_ui FastAPI App(`src.review_ui.app`)의 HTTP Endpoint 자체를 확인한다.
    공유 검수 디렉터리를 건드리지 않도록 읽기(GET)만 검증한다 — PATCH는 공유 파일에
    쓰므로 여기서는 별도 Registry/Store를 직접 주입하는 `BuildContextPackListTest`/
    `update_context_pack_review` 단위 테스트로 이미 검증했다."""

    def test_get_context_packs_endpoint_returns_200(self) -> None:
        from src.review_ui.app import app

        client = TestClient(app)
        response = client.get("/internal/review/v2/context-packs")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("packs", body)
        self.assertIn("discovery_errors", body)
        self.assertIn("ontology_errors", body)


if __name__ == "__main__":
    unittest.main()
