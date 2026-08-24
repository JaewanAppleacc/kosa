"""배치별 Shared Probe 검수 화면 — 2026-08-24 지시서
(a/shared-probe-batch-review-ui).

기존 `tests/test_review_ui_context_pack_tab.py`와 같은 2계층 전략을 쓴다.

1. `StaticSourceTest` — index.html/review.js 원문 구조 검증. 여기에 예외적으로
   `HashParserExecutionTest`를 추가한다: `parseLocationHash()`(순수 함수, DOM 의존
   없음)는 정규식이 아니라 실제 Node로 그 함수 원문을 그대로 추출·실행해서
   검증한다 — 재구현이 아니라 배포되는 그 코드 자체를 실행한다.
2. `SharedProbeBatchApiShapeTest`/`SaveBehaviorTest` — 실제 서비스 함수
   (`context_pack_review_service`)를 호출해 배치 정보·저장 동작을 검증한다.
   전부 `tempfile.TemporaryDirectory()`만 쓰고 실제 `data/reviews/`는 절대
   건드리지 않는다(SHA-256으로 매 테스트마다 증명)."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from src.data.context_packs._example_pack_builder import build_example_context_pack
from src.data.contexts.context_activation_batches import CONTEXT_ACTIVATION_BATCHES
from src.data.contexts.context_definitions import CONTEXT_IDS
from src.data.questions.context_pack_shared_probe_blueprints import CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS
from src.review_ui import context_pack_review_service as cprs
from src.schemas.context_pack_shared_probe_review import SharedProbeContextReview
from src.services.context_pack_registry import ContextPackRegistry
from src.services.context_pack_shared_probe_review_store import load_shared_probe_review_entries
from src.services.trait_ontology_v2 import load_trait_ontology_v2

_STATIC_DIR = Path(__file__).resolve().parents[1] / "src" / "review_ui" / "static"
_HTML = (_STATIC_DIR / "index.html").read_text(encoding="utf-8")
_JS = (_STATIC_DIR / "review.js").read_text(encoding="utf-8")


def _js_function_body(name: str) -> str:
    start = _JS.index(f"function {name}(")
    rest = _JS[start:]
    m = re.search(r"\n(async function |function )", rest[1:])
    return rest[: m.start() + 1] if m else rest


class StaticSourceTest(unittest.TestCase):
    """index.html/review.js 원문 구조 검증."""

    # 2. Batch 필터 UI 존재(1차/2차/3차/전체) + 3. 진행 현황 표시 영역.
    def test_batch_selector_and_dashboard_elements_exist(self) -> None:
        self.assertIn('id="shared-probe-batch-selector"', _HTML)
        self.assertIn('id="shared-probe-progress-dashboard"', _HTML)
        self.assertIn("function renderSharedProbeBatchSelector(", _JS)
        self.assertIn("function renderSharedProbeProgressDashboard(", _JS)

    # 6. 상태 필터 8종 + 기본값 "미판정 Anchor 있음".
    def test_status_filter_options_and_default(self) -> None:
        for value in ("all", "TBD", "APPROVE", "REVISE", "HOLD", "anchor_undetermined", "runtime_usable", "runtime_unusable"):
            self.assertIn(f'name="shared-probe-status-filter" value="{value}"', _HTML)
        m = re.search(r'name="shared-probe-status-filter" value="anchor_undetermined"[^>]*checked', _HTML)
        self.assertIsNotNone(m, "기본값(미판정 Anchor 있음)에 checked가 없다")
        # 다른 옵션에는 checked가 없어야 진짜 기본값이다.
        for value in ("all", "TBD", "APPROVE", "REVISE", "HOLD", "runtime_usable", "runtime_unusable"):
            other = re.search(rf'name="shared-probe-status-filter" value="{value}"[^>]*checked', _HTML)
            self.assertIsNone(other, f"{value}에 checked가 있다 — 기본값이 두 개다")

    def test_default_batch_state_is_1(self) -> None:
        self.assertIn("sharedProbeBatch: 1,", _JS)

    # 7. Anchor 상호배타 — 승인 체크 시 제외 해제, 반대도 동일. 저장 시 방어적으로도
    #    한 번 더 배타 처리한다.
    def test_anchor_mutual_exclusion_handlers_present(self) -> None:
        card_src = _js_function_body("renderSharedProbeAnchorCard")
        self.assertIn("if (approveBox.checked) excludeBox.checked = false;", card_src)
        self.assertIn("if (excludeBox.checked) approveBox.checked = false;", card_src)
        self.assertIn("const approved = approveBox.checked && !excludeBox.checked;", card_src)
        self.assertIn("const excluded = excludeBox.checked && !approveBox.checked;", card_src)

    # 8. 저장 버튼 분리 — Anchor 저장은 status/comment 미전송, Context 저장은
    #    approved/excluded_anchor_ids에 명시적 null.
    def test_anchor_save_payload_excludes_status_and_comment(self) -> None:
        card_src = _js_function_body("renderSharedProbeAnchorCard")
        m = re.search(r"saveSharedProbeContextReview\(\s*probe\.blueprint_id, contextRow\.context_id,\s*(\{[^}]*\})", card_src)
        self.assertIsNotNone(m, "Anchor 저장 payload를 찾지 못했다")
        payload_src = m.group(1)
        self.assertIn("approved_anchor_ids", payload_src)
        self.assertIn("excluded_anchor_ids", payload_src)
        self.assertNotIn("status", payload_src)
        self.assertNotIn("comment", payload_src)

    def test_context_save_payload_sends_explicit_null_anchor_lists(self) -> None:
        row_src = _js_function_body("renderSharedProbeContextRow")
        m = re.search(r"saveSharedProbeContextReview\(\s*probe\.blueprint_id, contextRow\.context_id,\s*(\{[^}]*\})", row_src)
        self.assertIsNotNone(m, "Context 저장 payload를 찾지 못했다")
        payload_src = m.group(1)
        self.assertIn("status:", payload_src)
        self.assertIn("comment:", payload_src)
        self.assertIn("approved_anchor_ids: null", payload_src)
        self.assertIn("excluded_anchor_ids: null", payload_src)

    # 10. 자동 판정 금지 — 저장 함수가 실패해도 목록을 성공한 것처럼 새로고침하지 않는다.
    def test_save_failure_does_not_reload_list(self) -> None:
        save_src = _js_function_body("saveSharedProbeContextReview")
        try_start = save_src.index("try {")
        catch_start = save_src.index("} catch (err) {")
        finally_start = save_src.index("} finally {")
        try_block = save_src[try_start:catch_start]
        catch_block = save_src[catch_start:finally_start]
        self.assertIn("await loadSharedProbesAll();", try_block)
        self.assertNotIn("await loadSharedProbesAll();", catch_block)
        # 422/409 구분 표시.
        self.assertIn('err.status === 422', catch_block)
        self.assertIn('err.status === 409', catch_block)

    # 15/16. 기존 ContextPack 탭·Legacy 탭 회귀 없음.
    def test_context_pack_tab_untouched(self) -> None:
        self.assertIn('id="tab-context-packs-btn"', _HTML)
        self.assertIn("function renderContextPackAll(", _JS)
        self.assertIn("function loadContextPacksAll(", _JS)

    def test_legacy_tabs_untouched(self) -> None:
        for tab_id in (
            "tab-direct-probe-btn", "tab-routing-btn", "tab-seed-anchor-btn",
            "tab-backup-btn", "tab-anchor-backup-btn",
        ):
            self.assertIn(f'id="{tab_id}"', _HTML)

    # 배치 표를 프론트에 복제하지 않는다(§2 "Context ID→Batch를 프론트 JavaScript에
    # 별도 하드코딩하지 마세요") — science/sports 같은 context_id 문자열이 review.js
    # 어디에도 하드코딩돼 있지 않아야 한다(§4의 batch selector 라벨 등에서만 배치
    # "번호"를 다루지, context_id 목록을 다루지 않는다).
    def test_batch_membership_not_duplicated_in_frontend(self) -> None:
        self.assertNotIn('"science"', _JS)
        self.assertNotIn('"sports"', _JS)
        self.assertIn("row.activation_batch", _JS)
        # CONTEXT_ACTIVATION_BATCHES는 주석(서버가 그 정본에서 계산한다는 설명)에만
        # 등장해야 한다 — JS 객체/배열로 정의되거나 대입되면 프론트가 배치 표를
        # 복제하고 있다는 뜻이다.
        self.assertNotRegex(_JS, r"CONTEXT_ACTIVATION_BATCHES\s*[=:\[]")


@unittest.skipUnless(shutil.which("node"), "node 실행 파일이 없어 실제 hash 파서 실행 테스트를 건너뛴다")
class HashParserExecutionTest(unittest.TestCase):
    """4. Deep Link — 정규식이 아니라 실제 배포되는 parseLocationHash() 함수 원문을
    Node로 그대로 실행해서 검증한다(재구현이 아니라 그 코드 자체를 실행)."""

    @classmethod
    def setUpClass(cls) -> None:
        start = _JS.index("const CONTEXTPACK_TAB_HASH = {")
        end = _JS.index("function tabFromLocationHash()")
        cls._parser_src = _JS[start:end]

    def _parse(self, hash_value: str) -> dict:
        script = (
            f"globalThis.location = {{ hash: {json.dumps(hash_value)} }};\n"
            f"{self._parser_src}\n"
            "console.log(JSON.stringify(parseLocationHash()));"
        )
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout.strip())

    def test_shared_probes_batch_1(self) -> None:
        self.assertEqual(self._parse("#shared-probes?batch=1"), {"tab": "shared_probes", "batch": 1})

    def test_shared_probes_batch_2_and_3(self) -> None:
        self.assertEqual(self._parse("#shared-probes?batch=2"), {"tab": "shared_probes", "batch": 2})
        self.assertEqual(self._parse("#shared-probes?batch=3"), {"tab": "shared_probes", "batch": 3})

    def test_unknown_batch_number_falls_back_to_null(self) -> None:
        self.assertEqual(self._parse("#shared-probes?batch=9"), {"tab": "shared_probes", "batch": None})
        self.assertEqual(self._parse("#shared-probes?batch=abc"), {"tab": "shared_probes", "batch": None})

    def test_shared_probes_without_batch_query_has_null_batch(self) -> None:
        self.assertEqual(self._parse("#shared-probes"), {"tab": "shared_probes", "batch": None})

    def test_context_packs_hash_unaffected_by_batch_feature(self) -> None:
        self.assertEqual(self._parse("#context-packs"), {"tab": "context_packs", "batch": None})

    def test_unknown_tab_hash_returns_null_tab(self) -> None:
        self.assertEqual(self._parse("#no-such-tab"), {"tab": None, "batch": None})

    def test_empty_hash_returns_null_tab(self) -> None:
        self.assertEqual(self._parse(""), {"tab": None, "batch": None})


class SharedProbeBatchApiShapeTest(unittest.TestCase):
    """2/3 — activation_batch가 정본과 실제로 일치하고, 1차/2차/3차 Context 집합이
    정확한지 실제 서비스 함수로 확인한다."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.registry = ContextPackRegistry(
            known_context_ids=frozenset(CONTEXT_IDS), review_status_dir=Path(self.tmpdir.name),
        )
        self.trait_definitions = {t.trait_id: t for t in load_trait_ontology_v2()}
        self.response = cprs.build_shared_probe_list(
            self.registry, list(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS), self.trait_definitions,
        )

    def _context_ids_in_batch(self, batch_no: int) -> set[str]:
        ids: set[str] = set()
        for probe in self.response.probes:
            for row in probe.contexts:
                if row.activation_batch == batch_no:
                    ids.add(row.context_id)
        return ids

    def test_activation_batch_matches_real_batch_constant_for_every_row(self) -> None:
        expected = {
            context_id: batch_no for batch_no, ids in CONTEXT_ACTIVATION_BATCHES.items() for context_id in ids
        }
        for probe in self.response.probes:
            for row in probe.contexts:
                self.assertEqual(row.activation_batch, expected.get(row.context_id), f"{probe.blueprint_id}/{row.context_id}")

    def test_batch_1_contains_only_business_science_sports(self) -> None:
        self.assertEqual(self._context_ids_in_batch(1), {"business", "science", "sports"})

    def test_batch_2_contains_making_volunteer_writing_travel(self) -> None:
        self.assertEqual(self._context_ids_in_batch(2), {"making", "volunteer", "writing", "travel"})

    def test_batch_3_contains_five_lifestyle_contexts(self) -> None:
        self.assertEqual(
            self._context_ids_in_batch(3),
            {"art_design", "cooking", "fashion_beauty", "history_humanities", "law_politics"},
        )

    def test_14_probes_times_3_batch1_contexts_present(self) -> None:
        self.assertEqual(len(self.response.probes), 14)
        for probe in self.response.probes:
            batch1_rows = [r for r in probe.contexts if r.activation_batch == 1]
            self.assertEqual(len(batch1_rows), 3, probe.blueprint_id)
            for row in batch1_rows:
                self.assertEqual(len(row.anchors), 5, f"{probe.blueprint_id}/{row.context_id}")


class _SaveTestBase(unittest.TestCase):
    """`_ServiceTestBase`(test_shared_probe_review_validation.py)와 같은 패턴 —
    tempdir만 쓰고, 실제 data/reviews는 setUp/tearDown에서 SHA-256으로 무변경을
    증명한다."""

    _REAL_REVIEW_DIR = Path(__file__).resolve().parents[1] / "data" / "reviews" / "context_packs"
    _REAL_SHARED_PROBE_PATH = (
        Path(__file__).resolve().parents[1] / "data" / "reviews" / "context_pack_shared_probes_review_status.json"
    )

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.review_dir = Path(self.tmpdir.name)
        self.shared_path = self.review_dir / "shared.json"
        self.pack = build_example_context_pack("business")
        self.anchor_ids = [a.anchor_id for a in self.pack.anchor_presentations]
        self.registry = ContextPackRegistry(
            known_context_ids=frozenset({"business"}),
            known_trait_ids=frozenset({"causal_analysis", "pattern_finding"}),
            review_status_dir=self.review_dir,
            shared_probe_review_status_path=self.shared_path,
            _discovered=({"business": self.pack}, {}),
        )
        self.blueprint = CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS[0]
        self.assertIn("business", self.blueprint.allowed_context_ids)
        self._before_real = self._snapshot_real_files()
        self.addCleanup(self._assert_real_files_untouched)

    def _snapshot_real_files(self) -> dict[str, str]:
        snapshot = {}
        if self._REAL_REVIEW_DIR.exists():
            for p in sorted(self._REAL_REVIEW_DIR.glob("*.json")):
                snapshot[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
        if self._REAL_SHARED_PROBE_PATH.exists():
            snapshot["__shared__"] = hashlib.sha256(self._REAL_SHARED_PROBE_PATH.read_bytes()).hexdigest()
        return snapshot

    def _assert_real_files_untouched(self) -> None:
        self.assertEqual(self._before_real, self._snapshot_real_files(), "실제 검수 JSON이 테스트 중 바뀌었다 — 절대 금지 위반")

    def _entries_by_key(self) -> dict[str, SharedProbeContextReview]:
        return {e.key: e for e in load_shared_probe_review_entries(self.shared_path)}


class SaveBehaviorTest(_SaveTestBase):
    """9/10 — Anchor 저장과 Context 저장이 서로의 영역을 침범하지 않는지, 특히
    "Context APPROVE로 Anchor 자동 승인 안 됨"을 명시적으로 확인한다(기존 파일은
    반대 방향인 "Anchor 저장이 Context를 자동 승인하지 않음"만 다뤘다)."""

    def test_context_approve_does_not_auto_approve_any_anchor(self) -> None:
        from src.review_ui.context_pack_review_service import update_shared_probe_review

        update_shared_probe_review(
            self.registry, list(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS), self.blueprint.blueprint_id, "business",
            status="APPROVE", comment="Context 승인", approved_anchor_ids=None, excluded_anchor_ids=None,
            resolution_note=None,
        )
        entry = self._entries_by_key().get(f"{self.blueprint.blueprint_id}::business")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.reviewer_1_status, "APPROVE")
        self.assertEqual(entry.approved_anchor_ids, [])  # Anchor는 하나도 자동 승인되지 않는다.
        self.assertEqual(entry.excluded_anchor_ids, [])

    def test_context_approve_after_partial_anchor_approval_does_not_change_anchor_list(self) -> None:
        from src.review_ui.context_pack_review_service import update_shared_probe_review

        update_shared_probe_review(
            self.registry, list(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS), self.blueprint.blueprint_id, "business",
            status=None, comment=None, approved_anchor_ids=[self.anchor_ids[0]], excluded_anchor_ids=[self.anchor_ids[1]],
            resolution_note=None,
        )
        update_shared_probe_review(
            self.registry, list(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS), self.blueprint.blueprint_id, "business",
            status="APPROVE", comment="Context만 승인", approved_anchor_ids=None, excluded_anchor_ids=None,
            resolution_note=None,
        )
        entry = self._entries_by_key()[f"{self.blueprint.blueprint_id}::business"]
        self.assertEqual(entry.reviewer_1_status, "APPROVE")
        self.assertEqual(entry.approved_anchor_ids, [self.anchor_ids[0]])
        self.assertEqual(entry.excluded_anchor_ids, [self.anchor_ids[1]])
        self.assertNotIn(self.anchor_ids[2], entry.approved_anchor_ids)
        self.assertNotIn(self.anchor_ids[3], entry.approved_anchor_ids)
        self.assertNotIn(self.anchor_ids[4], entry.approved_anchor_ids)

    def test_overlap_between_approved_and_excluded_still_rejected(self) -> None:
        """§7 — 서버 Schema의 교집합 거부 규칙이 여전히 살아있는지(UI가 상호배타를
        강제해도 서버가 마지막 방어선으로 남아야 한다)."""

        from src.review_ui.context_pack_review_service import SharedProbeAnchorListValidationError, update_shared_probe_review

        with self.assertRaises(SharedProbeAnchorListValidationError):
            update_shared_probe_review(
                self.registry, list(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS), self.blueprint.blueprint_id, "business",
                status=None, comment=None,
                approved_anchor_ids=[self.anchor_ids[0]], excluded_anchor_ids=[self.anchor_ids[0]],
                resolution_note=None,
            )
        self.assertEqual(self._entries_by_key(), {})

    def test_no_review_file_means_all_tbd_and_no_anchor_predetermined(self) -> None:
        """13 — 자동 승인 없음. tempdir이 비어 있으면(사람이 아직 아무것도 안 함)
        모든 Anchor가 미판정이어야 한다."""

        trait_definitions = {t.trait_id: t for t in load_trait_ontology_v2()}
        resp = cprs.build_shared_probe_list(self.registry, list(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS), trait_definitions)
        probe = next(p for p in resp.probes if p.blueprint_id == self.blueprint.blueprint_id)
        row = next(r for r in probe.contexts if r.context_id == "business")
        self.assertEqual(row.review.reviewer_1_status, "TBD")
        for anchor in row.anchors:
            self.assertFalse(anchor.is_approved, anchor.anchor_id)
            self.assertFalse(anchor.is_excluded, anchor.anchor_id)


if __name__ == "__main__":
    unittest.main()
