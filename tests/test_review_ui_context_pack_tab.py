"""신규 ContextPack(business/science/sports 등 12개) 검수 탭 — 2026-08-24 지시서.

이 프로젝트의 유일한 테스트 러너는 `./.venv/bin/python -m unittest discover -s tests`
뿐이고, `src/review_ui/static/`은 번들러도 JS 테스트 러너도 없는 순수 정적 파일이다
(frontend/의 Vitest와 무관 — README_B §0 "Review UI는 frontend/와 별개"). 그래서 이
파일은 두 계층으로 나눠 검증한다.

1. `StaticSourceTest` — index.html/review.js 원문에 대한 구조적 문자열 검증. 실제
   브라우저 DOM 실행 없이도 "탭 버튼이 있는가", "reviewer_2를 그리는 코드가 없는가",
   "저장 실패 시 성공 처리로 넘어가지 않는가" 같은 것을 소스 자체에서 확인한다.
2. `BehaviorTest` 계열 — 실제 서비스 함수(`context_pack_review_service`)와
   `ContextPackRegistry`를 호출해 데이터 계약(12개 Pack, 질문 11개, 배치 매핑,
   저장이 그 Key만 바꾸는지, 자동 APPROVE가 없는지)을 검증한다. 전부
   `tempfile.TemporaryDirectory()`로 만든 임시 검수 디렉터리만 쓴다 — 실제
   `data/reviews/context_packs/`는 어떤 테스트에서도 건드리지 않는다(§17).

이 파일을 준비하며 `update_context_pack_review()`/`build_context_pack_list()`가
`registry`에 주입한 tempdir을 무시하고 항상 진짜 `data/reviews/context_packs/`를
읽고 쓰던 버그를 발견해 함께 고쳤다(`trait_signal_review_gate.py`에서 이미 한 번
고쳤던 것과 같은 종류 — base_dir 인자를 빠뜨린 채 store 함수를 호출하는 버그)."""

from __future__ import annotations

import hashlib
import re
import tempfile
import unittest
from pathlib import Path

from src.data.contexts.context_activation_batches import ALL_BATCH_CONTEXT_IDS, CONTEXT_ACTIVATION_BATCHES
from src.data.contexts.context_definitions import CONTEXT_IDS
from src.review_ui import context_pack_review_service as cprs
from src.services.context_pack_registry import ContextPackRegistry
from src.services.context_pack_review_store import load_context_pack_review_entries
from src.services.trait_ontology_v2 import load_trait_ontology_v2

_STATIC_DIR = Path(__file__).resolve().parents[1] / "src" / "review_ui" / "static"
_HTML = (_STATIC_DIR / "index.html").read_text(encoding="utf-8")
_JS = (_STATIC_DIR / "review.js").read_text(encoding="utf-8")


def _js_function_body(name: str) -> str:
    """`function <name>(...) { ... }` 블록 원문을 대략적으로 잘라낸다 — 다음
    top-level `function`/`async function` 선언 직전까지. 이 파일 안의 함수는 전부
    top-level(중첩 함수 정의 없음)이라 이 방식으로 충분하다."""

    start = _JS.index(f"function {name}(")
    rest = _JS[start:]
    m = re.search(r"\n(async function |function )", rest[1:])
    return rest[: m.start() + 1] if m else rest


class StaticSourceTest(unittest.TestCase):
    """index.html/review.js 원문 구조 검증(§1/§2/§7/§8/§10/§14/§15/§16/§19/§20)."""

    # 1. 신규 ContextPack (12) 탭 존재.
    def test_new_tab_button_exists_in_html(self) -> None:
        self.assertIn('data-tab="context_packs"', _HTML)
        self.assertIn("신규 ContextPack (12)", _HTML)
        self.assertIn('id="tab-context-packs-btn"', _HTML)

    # 15. 기존 legacy 검수 탭 회귀 없음 — 버튼도, 로딩/렌더 함수도 그대로 남아있다.
    def test_all_existing_legacy_tabs_still_present(self) -> None:
        for tab_id in (
            "tab-direct-probe-btn", "tab-routing-btn", "tab-seed-anchor-btn",
            "tab-backup-btn", "tab-anchor-backup-btn", "tab-shared-probes-btn",
        ):
            self.assertIn(f'id="{tab_id}"', _HTML)
        for fn in (
            "function loadAll(", "function loadRoutingAll(", "function loadSeedAnchorAll(",
            "function loadBackupAll(", "function loadAnchorBackupAll(",
        ):
            self.assertIn(fn, _JS)

    # 16. Shared Probe 탭 회귀 없음.
    def test_shared_probe_tab_untouched(self) -> None:
        self.assertIn('id="shared-probe-container"', _HTML)
        self.assertIn('id="shared-probe-nav-list"', _HTML)
        self.assertIn("function loadSharedProbesAll(", _JS)
        self.assertIn("function renderCurrentSharedProbe(", _JS)
        self.assertIn("/context-packs/shared-probes/${blueprintId}/${contextId}", _JS)

    # 2 / 20. #context-packs Deep Link + 새로고침 시 유지.
    def test_hash_deep_link_mapping_and_bootstrap_reads_hash_first(self) -> None:
        self.assertIn('context_packs: "context-packs"', _JS)
        self.assertIn("function tabFromLocationHash(", _JS)
        self.assertIn("window.addEventListener(\"hashchange\"", _JS)
        bootstrap_body = _js_function_body("bootstrap")
        hash_pos = bootstrap_body.index("tabFromLocationHash()")
        load_pos = bootstrap_body.index("loadOrRenderTab(initialTab)")
        self.assertLess(hash_pos, load_pos, "bootstrap()이 hash보다 기본 tab을 먼저 로드한다")

    def test_unknown_hash_falls_back_to_direct_probe(self) -> None:
        # 두 곳 모두(부트스트랩, hashchange) "알 수 없으면 direct_probe" 안전 기본값을 쓴다.
        self.assertIn('tabFromLocationHash() || "direct_probe"', _JS)

    # 7. Trait Signal / NO_SIGNAL 시각적 구분(기존 탭의 모드 토글에 종속되지 않는
    #    전용 클래스를 쓰는지) + CSS 규칙 존재.
    def test_trait_signal_vs_no_signal_has_dedicated_visual_class(self) -> None:
        self.assertIn('classes.push("context-pack-nosignal")', _JS)
        css = (_STATIC_DIR / "review.css").read_text(encoding="utf-8")
        self.assertIn(".option-card.context-pack-nosignal", css)
        self.assertIn("trait-signal-free-banner", _JS)
        self.assertIn("trait-signal-present-warning", _JS)

    # 8. reviewer_2 UI 미표시 — 신규 탭의 저장 패널 함수 안에 reviewer_2 문자열이
    #    전혀 없어야 한다(기존 탭의 renderReviewerSlotBlock과 달리 이 탭은 그 함수를
    #    아예 재사용하지 않는다).
    def test_review_panel_never_renders_reviewer_2(self) -> None:
        panel_src = _js_function_body("renderContextPackReviewPanel")
        self.assertNotIn("reviewer_2", panel_src)
        self.assertIn("reviewer_1", panel_src)
        self.assertIn("검토자 1", panel_src)
        self.assertNotIn("검토자 2", panel_src)

    # 10. 저장 API 호출부가 reviewer 필드 없이 status/comment/resolution_note만
    #     보낸다(단일 검토자 계약과 PATCH Schema에 정확히 맞음).
    def test_save_payload_has_no_reviewer_field(self) -> None:
        panel_src = _js_function_body("renderContextPackReviewPanel")
        m = re.search(r"apiPatch\(path, (\{[^}]*\})\)", panel_src)
        self.assertIsNotNone(m, "apiPatch(path, {...}) 호출을 찾지 못했다")
        payload_src = m.group(1)
        self.assertIn("status:", payload_src)
        self.assertIn("comment:", payload_src)
        self.assertIn("resolution_note:", payload_src)
        self.assertNotIn("reviewer:", payload_src)
        self.assertNotIn("expected_revision", payload_src)  # 이 Endpoint는 Revision 동시성 계약이 없다.

    # 14. 저장 실패 시 성공 상태로 표시하지 않음 — catch 블록 안에서 목록을
    #     새로고침하거나 dirty를 지우지 않는다(그건 try 블록 성공 경로에만 있다).
    def test_save_failure_does_not_refresh_or_clear_dirty(self) -> None:
        panel_src = _js_function_body("renderContextPackReviewPanel")
        try_start = panel_src.index("try {")
        catch_start = panel_src.index("} catch (err) {")
        finally_start = panel_src.index("} finally {")
        try_block = panel_src[try_start:catch_start]
        catch_block = panel_src[catch_start:finally_start]
        self.assertIn("await refreshContextPacksAfterSave(", try_block)
        self.assertIn("state.dirty = false;", try_block)
        # catch 블록에는 "왜 안 부르는지" 설명하는 주석에만 함수 이름이 등장해야 한다
        # (실제 호출 `refreshContextPacksAfterSave(`은 없어야 한다).
        self.assertNotIn("refreshContextPacksAfterSave(", catch_block)
        self.assertNotIn("state.dirty = false;", catch_block)

    # 19. discovery_errors/ontology_errors 상단 표시.
    def test_error_banner_reads_discovery_and_ontology_errors(self) -> None:
        banner_src = _js_function_body("renderContextPackErrorBanner")
        self.assertIn("state.contextPackDiscoveryErrors", banner_src)
        self.assertIn("state.contextPackOntologyErrors", banner_src)

    # 6. Routing → Seed → Anchor Backup → (있으면) Native Direct Probe 순서.
    def test_kind_order_constant_matches_required_sequence(self) -> None:
        self.assertIn(
            "CONTEXTPACK_KIND_ORDER = { routing: 0, seed: 1, anchor_backup: 2, direct_probe: 3 }", _JS,
        )

    # 4. 배치 표를 프론트에서 복제하지 않고 서버 응답(activation_batch)을 그대로 쓴다
    #    (지시서 "UI에 불가피하게 표시용 그룹을 둘 경우..." 조건 자체가 발생하지 않게
    #    설계했다는 것을 소스로 증명 — 배치 숫자를 하드코딩한 매핑 표가 없다).
    def test_batch_grouping_is_not_duplicated_in_frontend(self) -> None:
        # "business"는 §4 "기본 선택: 1차 배치 → business" Fallback 한 곳에서만 쓰고,
        # 그 외에는 어떤 context_id도 review.js에 배치 표로 하드코딩돼 있지 않다 —
        # science/sports 같은 다른 1차 배치 Context는 review.js 어디에도 없어야 한다
        # (있다면 배치 표를 통째로 복제하고 있다는 뜻이다).
        self.assertNotIn('"science"', _JS)
        self.assertNotIn('"sports"', _JS)
        self.assertIn("p.activation_batch", _JS)
        self.assertNotIn("CONTEXT_ACTIVATION_BATCHES", _JS)  # 그런 상수를 JS가 따로 두지 않는다.


class ApiListShapeTest(unittest.TestCase):
    """§3/§4/§5/§18 — 실제 서비스 함수가 반환하는 데이터 계약. tempdir만 쓴다."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.registry = ContextPackRegistry(
            known_context_ids=frozenset(CONTEXT_IDS), review_status_dir=Path(self.tmpdir.name),
        )
        self.trait_definitions = {t.trait_id: t for t in load_trait_ontology_v2()}
        self.response = cprs.build_context_pack_list(self.registry, self.trait_definitions)

    # 3. API에서 12개 Pack 로드.
    def test_exactly_12_packs_loaded(self) -> None:
        self.assertEqual(len(self.response.packs), 12)
        self.assertEqual({p.context_id for p in self.response.packs}, set(ALL_BATCH_CONTEXT_IDS))

    # 4. 1차 배치 business/science/sports가 activation_batch=1로 노출된다(하드코딩이
    #    아니라 CONTEXT_ACTIVATION_BATCHES 정본과 실제로 일치하는지까지 검증).
    def test_activation_batch_matches_real_batch_constant_for_every_pack(self) -> None:
        expected = {
            context_id: batch_no
            for batch_no, ids in CONTEXT_ACTIVATION_BATCHES.items()
            for context_id in ids
        }
        for pack in self.response.packs:
            self.assertEqual(pack.activation_batch, expected[pack.context_id], pack.context_id)
        batch1 = {p.context_id for p in self.response.packs if p.activation_batch == 1}
        self.assertEqual(batch1, {"business", "science", "sports"})

    # 5 / 6. Pack당 질문 11개, Routing 1 + Seed 5 + Anchor Backup 5(이번 배치엔
    #        Native Direct Probe가 없다는 사실까지 함께 확인).
    def test_every_pack_has_exactly_11_questions_1_5_5_split(self) -> None:
        for pack in self.response.packs:
            self.assertEqual(len(pack.questions), 11, pack.context_id)
            kinds = [q.kind for q in pack.questions]
            self.assertEqual(kinds.count("routing"), 1, pack.context_id)
            self.assertEqual(kinds.count("seed"), 5, pack.context_id)
            self.assertEqual(kinds.count("anchor_backup"), 5, pack.context_id)
            self.assertEqual(kinds.count("direct_probe"), 0, pack.context_id)

    # 7. 데이터 쪽에서도 TRAIT_SIGNAL과 NO_SIGNAL이 실제로 섞여 있는지(그려줄 대상이
    #    존재하는지) 확인 — 최소 하나의 Pack에서 두 mapping_type이 모두 나타난다.
    def test_options_include_both_trait_signal_and_no_signal_somewhere(self) -> None:
        mapping_types = {o.mapping_type for pack in self.response.packs for q in pack.questions for o in q.options}
        self.assertEqual(mapping_types, {"TRAIT_SIGNAL", "NO_SIGNAL"})

    # 18. business/science/making/law_politics는 두 Artifact 경로를 모두 노출한다.
    def test_dual_artifact_business_science_making_law_politics(self) -> None:
        by_id = {p.context_id: p for p in self.response.packs}
        for context_id in ("business", "science", "making", "law_politics"):
            paths = by_id[context_id].review_artifact_paths
            self.assertIn(f"data/reviews/context_packs/{context_id}_review_status.json", paths)
            self.assertIn(f"outputs/context_packs/{context_id}_mapping_audit.md", paths)

    # 13. 자동 APPROVE 없음 — 검수 파일이 아예 없는 tempdir이므로 전부 TBD/미승인.
    def test_no_auto_approve_when_no_review_file_exists(self) -> None:
        for pack in self.response.packs:
            self.assertFalse(pack.is_active, pack.context_id)
            for q in pack.questions:
                self.assertEqual(q.review.reviewer_1_status, "TBD", f"{pack.context_id}/{q.key}")
                self.assertEqual(q.review.final_status, "DRAFT", f"{pack.context_id}/{q.key}")

    # 9. 저장 전에는 JSON 무변경 — GET(build_context_pack_list) 호출 자체가 파일을
    #    만들지 않는다.
    def test_get_does_not_create_any_review_file(self) -> None:
        for context_id in ("business", "science", "sports"):
            self.assertFalse((Path(self.tmpdir.name) / f"{context_id}_review_status.json").exists())


class SaveBehaviorTest(unittest.TestCase):
    """§9/§10/§11/§12/§13/§17 — 실제 저장(update_context_pack_review) 동작.
    tempdir에만 쓴다 — 실제 data/reviews/context_packs/는 setUp에서 스냅샷을 떠서
    이 클래스의 어떤 테스트도 그 파일을 건드리지 않았음을 tearDown에서 증명한다."""

    _REAL_REVIEW_DIR = Path(__file__).resolve().parents[1] / "data" / "reviews" / "context_packs"

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.review_dir = Path(self.tmpdir.name)
        self.registry = ContextPackRegistry(known_context_ids=frozenset(CONTEXT_IDS), review_status_dir=self.review_dir)
        self.trait_definitions = {t.trait_id: t for t in load_trait_ontology_v2()}
        self._before_real_files = self._snapshot_real_files()
        self.addCleanup(self._assert_real_files_untouched)

    def _snapshot_real_files(self) -> dict[str, str]:
        if not self._REAL_REVIEW_DIR.exists():
            return {}
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(self._REAL_REVIEW_DIR.glob("*.json"))}

    def _assert_real_files_untouched(self) -> None:
        self.assertEqual(self._before_real_files, self._snapshot_real_files(), "실제 검수 JSON이 테스트 중 바뀌었다 — 절대 금지 위반")

    def _pack_for(self, context_id: str):
        response = cprs.build_context_pack_list(self.registry, self.trait_definitions)
        return next(p for p in response.packs if p.context_id == context_id)

    # 10. APPROVE 저장 시 해당 Key만 변경 — 같은 Context의 다른 10개 질문은 그대로 TBD.
    def test_approve_save_changes_only_the_target_key(self) -> None:
        pack = self._pack_for("business")
        target_key = next(q.key for q in pack.questions if q.kind == "seed")
        other_keys = [q.key for q in pack.questions if q.key != target_key]

        cprs.update_context_pack_review(
            self.registry, "business", target_key, status="APPROVE", comment="근거 명확", resolution_note=None,
        )

        after = self._pack_for("business")
        by_key = {q.key: q for q in after.questions}
        self.assertEqual(by_key[target_key].review.reviewer_1_status, "APPROVE")
        self.assertEqual(by_key[target_key].review.reviewer_1_comment, "근거 명확")
        for k in other_keys:
            self.assertEqual(by_key[k].review.reviewer_1_status, "TBD", k)

    # 11. REVISE/HOLD/TBD 저장.
    def test_revise_hold_tbd_all_save_correctly(self) -> None:
        pack = self._pack_for("science")
        routing_key = next(q.key for q in pack.questions if q.kind == "routing")
        for status, expected_final in (("REVISE", "REVIEW_REQUIRED"), ("HOLD", "REVIEW_REQUIRED"), ("TBD", "DRAFT")):
            result = cprs.update_context_pack_review(
                self.registry, "science", routing_key, status=status, comment=f"상태={status}", resolution_note=None,
            )
            self.assertEqual(result.final_status, expected_final)
            after = self._pack_for("science")
            saved = next(q for q in after.questions if q.key == routing_key)
            self.assertEqual(saved.review.reviewer_1_status, status)

    # 12. 사용자 comment·해소 메모(resolution_note) 저장 → 재조회 시 그대로 보인다.
    def test_comment_and_resolution_note_persist_across_reload(self) -> None:
        pack = self._pack_for("sports")
        key = next(q.key for q in pack.questions if q.kind == "anchor_backup")
        cprs.update_context_pack_review(
            self.registry, "sports", key, status="REVISE",
            comment="선택지 3번이 다른 선택지를 포괄한다", resolution_note="문구 수정 후 재검토 요청",
        )
        reloaded = self._pack_for("sports")
        saved = next(q for q in reloaded.questions if q.key == key)
        self.assertEqual(saved.review.reviewer_1_comment, "선택지 3번이 다른 선택지를 포괄한다")
        self.assertEqual(saved.review.resolution_note, "문구 수정 후 재검토 요청")

    # 17. 이 테스트 파일 전체가 실제 data/reviews를 쓰지 않는지 저장소 파일 레벨에서도
    #     한 번 더 증명한다 — save 직후 tempdir에는 파일이 생기고, 진짜 디렉터리에는
    #     안 생긴다.
    def test_save_writes_only_to_injected_tempdir_not_real_directory(self) -> None:
        pack = self._pack_for("business")
        key = next(q.key for q in pack.questions if q.kind == "seed")
        cprs.update_context_pack_review(self.registry, "business", key, status="APPROVE", comment="", resolution_note=None)
        self.assertTrue((self.review_dir / "business_review_status.json").exists())
        entries = load_context_pack_review_entries("business", self.review_dir)
        self.assertTrue(any(e.blueprint_id == key and e.reviewer_1_status == "APPROVE" for e in entries))

    def test_unknown_key_rejected_without_writing(self) -> None:
        with self.assertRaises(cprs.UnknownReviewKeyError):
            cprs.update_context_pack_review(
                self.registry, "business", "business::seed::not_a_real_anchor",
                status="APPROVE", comment="", resolution_note=None,
            )
        self.assertFalse((self.review_dir / "business_review_status.json").exists())


if __name__ == "__main__":
    unittest.main()
