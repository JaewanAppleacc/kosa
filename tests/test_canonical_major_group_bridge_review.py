"""Canonical Major Group Bridge 검수 탭 테스트 — 2026-08-24 지시서
(a/canonical-major-bridge-review-ui).

44개 Canonical Major Group Bridge Draft(`data/master/canonical_major_group_bridge.
draft.jsonl`, Read-Only)를 사람이 검수할 수 있는 별도 탭·API·저장 파일
(`data/reviews/canonical_major_group_bridge_review_status.json`)을 검증한다.
기존 `tests/test_review_ui_shared_probe_batch.py`와 같은 2계층 전략을 그대로
따른다.

1. `StaticSourceTest` — index.html/review.js 원문 구조 검증(탭 버튼, 필터, 저장이
   필터 변경과 분리돼 있는지).
2. `ServiceLayerTest`/`ApiLayerTest`/`ImmutabilityTest` — 실제 서비스 함수와 FastAPI
   TestClient를 호출해 44행 로드, 복합 Key, 중복 Key 차단, 저장/재조회, 자동 승인
   없음, Master Draft·기존 검수 JSON 무변경(SHA-256)을 확인한다. 전부
   `tempfile.TemporaryDirectory()`만 쓰고 실제 `data/reviews/`, `data/master/`는
   절대 건드리지 않는다."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.review_ui import canonical_major_group_bridge_review_service as cmgbrs
from src.review_ui.app import app
from src.schemas.canonical_major_group_bridge import CanonicalMajorGroupBridgeEntry
from src.schemas.canonical_major_group_bridge_review import CanonicalMajorGroupBridgeReview, bridge_review_key
from src.services.canonical_major_group_bridge_loader import DEFAULT_BRIDGE_DRAFT_PATH, load_canonical_major_group_bridge
from src.services.canonical_major_group_bridge_review_store import (
    DuplicateBridgeReviewKeyError,
    load_bridge_review_entries_by_key,
    save_bridge_review_entries,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_STATIC_DIR = _REPO_ROOT / "src" / "review_ui" / "static"
_HTML = (_STATIC_DIR / "index.html").read_text(encoding="utf-8")
_JS = (_STATIC_DIR / "review.js").read_text(encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _js_function_body(name: str) -> str:
    start = _JS.index(f"function {name}(")
    rest = _JS[start:]
    m = re.search(r"\n(async function |function )", rest[1:])
    return rest[: m.start() + 1] if m else rest


class StaticSourceTest(unittest.TestCase):
    def test_tab_button_and_container_exist(self) -> None:
        self.assertIn('id="tab-bridge-btn"', _HTML)
        self.assertIn('id="bridge-container"', _HTML)
        self.assertIn('id="bridge-summary-box"', _HTML)

    def test_status_filters_present(self) -> None:
        for value in ("all", "EVIDENCED", "REVIEW_REQUIRED", "UNMAPPED", "EXCLUDED_RECOMMENDATION"):
            self.assertIn(f'name="bridge-mapping-filter" value="{value}"', _HTML)
        for value in ("all", "unreviewed", "reviewed"):
            self.assertIn(f'name="bridge-review-filter" value="{value}"', _HTML)
        self.assertIn('id="bridge-filter-boundary"', _HTML)

    def test_representative_major_filter_present(self) -> None:
        for value in ("all", "media_communication", "industrial_engineering", "hci_ux", "other"):
            self.assertIn(f'name="bridge-major-filter" value="{value}"', _HTML)

    def test_other_tabs_untouched(self) -> None:
        for tab_id in (
            "tab-direct-probe-btn", "tab-routing-btn", "tab-seed-anchor-btn", "tab-backup-btn",
            "tab-anchor-backup-btn", "tab-shared-probes-btn", "tab-context-packs-btn",
        ):
            self.assertIn(f'id="{tab_id}"', _HTML)

    def test_save_only_triggered_by_button_click(self) -> None:
        """안전 규칙 "저장 버튼을 눌렀을 때만 상태·코멘트 저장" — apiPatch 호출은
        저장 버튼의 click 핸들러 안에만 있어야 하고, 필터 변경 핸들러 안에는 전혀
        없어야 한다."""

        card_src = _js_function_body("renderBridgeRowCard")
        self.assertIn("saveBtn.addEventListener(\"click\", async () => {", card_src)
        click_handler_start = card_src.index('saveBtn.addEventListener("click"')
        self.assertIn("apiPatch(", card_src[click_handler_start:])

        for filter_fn_marker in (
            'name="bridge-mapping-filter"', 'name="bridge-review-filter"',
            "bridge-filter-boundary", 'name="bridge-major-filter"',
        ):
            idx = _JS.index(filter_fn_marker)
            # 필터 이벤트 리스너 등록부 주변 400자 안에 apiPatch 호출이 없어야 한다
            # (필터 변경 → renderBridgeContainer()만 호출, 저장 요청 없음).
            snippet = _JS[idx : idx + 400]
            self.assertNotIn("apiPatch(", snippet)

    def test_no_hardcoded_summary_numbers_in_html(self) -> None:
        """§4 — 요약 숫자(44/8/2/5/29)를 HTML에 하드코딩하지 않는다. review.js도
        renderBridgeSummary()가 state.bridgeSummary(서버 응답)에서만 값을 읽는다."""

        self.assertNotIn(">44<", _HTML)
        self.assertNotIn(">29<", _HTML)
        summary_fn = _js_function_body("renderBridgeSummary")
        self.assertIn("state.bridgeSummary", summary_fn)
        self.assertNotIn(" 44", summary_fn)
        self.assertNotIn(" 29", summary_fn)

    def test_filters_are_client_side_only(self) -> None:
        """필터 change 리스너는 API를 호출하지 않고 이미 불러온 state.bridgeRows를
        다시 그리기만 한다(loadBridgeAll을 다시 호출하지 않는다 = 서버 재조회조차
        하지 않는 순수 필터)."""

        idx = _JS.index('name="bridge-mapping-filter"')
        snippet = _JS[idx : idx + 300]
        self.assertIn("renderBridgeContainer()", snippet)
        self.assertNotIn("loadBridgeAll()", snippet)

    def test_hash_deep_link_registered(self) -> None:
        self.assertIn('bridge: "bridge"', _JS)


class _BridgeTestBase(unittest.TestCase):
    """모든 저장·서비스 테스트가 공유하는 tempdir 격리 + 실제 파일 SHA-256 무변경
    증명. `data/master/canonical_major_group_bridge.draft.jsonl`(Master Draft)과
    기존 5개 검수 JSON 전부를 대상으로 한다."""

    _REAL_BRIDGE_DRAFT_PATH = DEFAULT_BRIDGE_DRAFT_PATH
    _REAL_REVIEW_JSON_PATHS = sorted((_REPO_ROOT / "data" / "reviews").rglob("*.json"))

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.review_path = Path(self.tmpdir.name) / "canonical_major_group_bridge_review_status.json"

        self._before_hashes = self._snapshot_real_files()
        self.addCleanup(self._assert_real_files_untouched)

    def _snapshot_real_files(self) -> dict[str, str]:
        snapshot = {"__bridge_draft__": _sha256(self._REAL_BRIDGE_DRAFT_PATH)}
        for p in self._REAL_REVIEW_JSON_PATHS:
            snapshot[str(p)] = _sha256(p)
        return snapshot

    def _assert_real_files_untouched(self) -> None:
        self.assertEqual(self._before_hashes, self._snapshot_real_files(), "실제 파일이 테스트 중 바뀌었다 — 절대 금지 위반")


class ServiceLayerTest(_BridgeTestBase):
    def test_loads_all_44_rows(self) -> None:
        resp = cmgbrs.build_bridge_review_list(review_status_path=self.review_path)
        self.assertEqual(len(resp.rows), 44)
        self.assertEqual(resp.summary.total, 44)

    def test_summary_matches_exact_distribution(self) -> None:
        resp = cmgbrs.build_bridge_review_list(review_status_path=self.review_path)
        self.assertEqual(resp.summary.evidenced_count, 8)
        self.assertEqual(resp.summary.review_required_count, 2)
        self.assertEqual(resp.summary.excluded_recommendation_count, 5)
        self.assertEqual(resp.summary.unmapped_count, 29)
        self.assertEqual(
            resp.summary.evidenced_count + resp.summary.review_required_count
            + resp.summary.excluded_recommendation_count + resp.summary.unmapped_count,
            44,
        )

    def test_composite_key_is_stable_and_unique(self) -> None:
        resp = cmgbrs.build_bridge_review_list(review_status_path=self.review_path)
        keys = [r.review_key for r in resp.rows]
        self.assertEqual(len(keys), len(set(keys)), "복합 Key가 44행 전체에서 유일하지 않다")
        # computer_science Group은 실제로 두 Major 후보(computer_science/hci_ux)를
        # 가진다 — group_id 하나만으로는 Key가 유일하지 않다는 사실 자체를 검증한다.
        group_ids = [r.canonical_major_group_id for r in resp.rows]
        self.assertGreater(len(group_ids), len(set(group_ids)), "group_id만으로 Key를 만들면 유일하지 않아야 하는데 유일하다")

    def test_unmapped_sentinel_used_when_major_id_is_none(self) -> None:
        resp = cmgbrs.build_bridge_review_list(review_status_path=self.review_path)
        unmapped_row = next(r for r in resp.rows if r.canonical_major_id is None)
        self.assertTrue(unmapped_row.review_key.endswith("::UNMAPPED"))
        self.assertEqual(
            unmapped_row.review_key, bridge_review_key(unmapped_row.canonical_major_group_id, None),
        )

    def test_unmapped_sentinel_never_collides_with_a_real_major_id(self) -> None:
        """"UNMAPPED"이라는 센티널이 실제 10개 서비스 Major ID와 절대 겹치지
        않는지 실제 파일로 확인한다(가정이 아니라 사실)."""

        from src.engines.canonical_mapper import load_canonical_majors
        from src.services.canonical_major_group_bridge_loader import DEFAULT_CANONICAL_MAJORS_PATH

        real_major_ids = {m.major_id for m in load_canonical_majors(DEFAULT_CANONICAL_MAJORS_PATH)}
        self.assertNotIn("UNMAPPED", real_major_ids)

    def test_row_fields_include_labels_and_national_department_count(self) -> None:
        resp = cmgbrs.build_bridge_review_list(review_status_path=self.review_path)
        evidenced = next(r for r in resp.rows if r.mapping_status == "EVIDENCED")
        self.assertTrue(evidenced.canonical_major_group_label)
        self.assertTrue(evidenced.canonical_major_label)
        self.assertIsNotNone(evidenced.national_department_candidate_count)
        self.assertGreater(evidenced.national_department_candidate_count, 0)

    def test_no_item_is_pre_approved(self) -> None:
        """안전 규칙 "어떤 항목도 자동 APPROVE하지 않음" — 저장 파일이 없는 상태(사람이
        아직 아무것도 안 함)에서는 44행 전부 reviewer_1_status가 TBD여야 한다."""

        resp = cmgbrs.build_bridge_review_list(review_status_path=self.review_path)
        statuses = {r.review.reviewer_1_status for r in resp.rows}
        self.assertEqual(statuses, {"TBD"})
        self.assertEqual(resp.summary.reviewer_approve_count, 0)
        self.assertEqual(resp.summary.unreviewed_count, 44)

    def test_get_style_load_never_writes_review_file(self) -> None:
        cmgbrs.build_bridge_review_list(review_status_path=self.review_path)
        cmgbrs.build_bridge_review_list(review_status_path=self.review_path)
        self.assertFalse(self.review_path.exists(), "목록 조회만으로 검수 상태 파일이 생성/기록되면 안 된다")

    def test_save_and_reload_round_trip(self) -> None:
        resp = cmgbrs.build_bridge_review_list(review_status_path=self.review_path)
        key = resp.rows[0].review_key
        out = cmgbrs.update_bridge_review(
            key, status="REVISE", comment="재검토 필요 — 근거 부족", resolution_note=None,
            review_status_path=self.review_path,
        )
        self.assertTrue(out.ok)
        self.assertEqual(out.final_status, "REVIEW_REQUIRED")

        resp2 = cmgbrs.build_bridge_review_list(review_status_path=self.review_path)
        row = next(r for r in resp2.rows if r.review_key == key)
        self.assertEqual(row.review.reviewer_1_status, "REVISE")
        self.assertEqual(row.review.reviewer_1_comment, "재검토 필요 — 근거 부족")

        # 다른 43행은 여전히 TBD여야 한다(한 행 저장이 다른 행으로 새지 않는다).
        others = [r for r in resp2.rows if r.review_key != key]
        self.assertTrue(all(r.review.reviewer_1_status == "TBD" for r in others))

    def test_partial_save_none_means_unchanged(self) -> None:
        resp = cmgbrs.build_bridge_review_list(review_status_path=self.review_path)
        key = resp.rows[0].review_key
        cmgbrs.update_bridge_review(
            key, status="HOLD", comment="1차 코멘트", resolution_note=None, review_status_path=self.review_path,
        )
        # comment만 다시 저장(status=None) — 기존 HOLD가 유지돼야 한다.
        cmgbrs.update_bridge_review(
            key, status=None, comment="수정된 코멘트", resolution_note=None, review_status_path=self.review_path,
        )
        row = next(
            r for r in cmgbrs.build_bridge_review_list(review_status_path=self.review_path).rows
            if r.review_key == key
        )
        self.assertEqual(row.review.reviewer_1_status, "HOLD")
        self.assertEqual(row.review.reviewer_1_comment, "수정된 코멘트")

    def test_unknown_review_key_rejected(self) -> None:
        with self.assertRaises(cmgbrs.UnknownBridgeReviewKeyError):
            cmgbrs.update_bridge_review(
                "does_not_exist::UNMAPPED", status="APPROVE", comment=None, resolution_note=None,
                review_status_path=self.review_path,
            )
        self.assertFalse(self.review_path.exists())

    def test_duplicate_key_rejected_on_save(self) -> None:
        dup = [
            CanonicalMajorGroupBridgeReview(canonical_major_group_id="computer_science", canonical_major_id="computer_science"),
            CanonicalMajorGroupBridgeReview(canonical_major_group_id="computer_science", canonical_major_id="computer_science"),
        ]
        with self.assertRaises(DuplicateBridgeReviewKeyError):
            save_bridge_review_entries(dup, self.review_path)
        self.assertFalse(self.review_path.exists(), "중복 Key 저장 시도가 부분적으로라도 파일을 남기면 안 된다")

    def test_duplicate_key_rejected_on_manual_load(self) -> None:
        """파일이 외부에서 손상돼(같은 Key 두 번) 있으면 조용히 마지막 값으로
        덮어쓰지 않고 즉시 예외를 던진다."""

        self.review_path.parent.mkdir(parents=True, exist_ok=True)
        self.review_path.write_text(
            json.dumps(
                [
                    {"canonical_major_group_id": "computer_science", "canonical_major_id": "computer_science"},
                    {"canonical_major_group_id": "computer_science", "canonical_major_id": "computer_science"},
                ]
            ),
            encoding="utf-8",
        )
        with self.assertRaises(DuplicateBridgeReviewKeyError):
            load_bridge_review_entries_by_key(self.review_path)

    def test_bridge_draft_entries_still_load_via_shared_loader(self) -> None:
        """A-1이 만든 정본 Loader(`load_canonical_major_group_bridge`)를 그대로
        재사용하고 있는지 — 별도 경쟁 Loader/Schema를 만들지 않았다는 사실 자체를
        타입으로 확인한다."""

        report = load_canonical_major_group_bridge()
        self.assertEqual(len(report.entries), 44)
        self.assertIsInstance(report.entries[0], CanonicalMajorGroupBridgeEntry)


class ApiLayerTest(_BridgeTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.client = TestClient(app)
        patcher = patch(
            "src.review_ui.canonical_major_group_bridge_review_service.BRIDGE_REVIEW_STATUS_PATH", self.review_path,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_get_returns_44_rows_and_summary(self) -> None:
        r = self.client.get("/internal/review/v2/canonical-major-group-bridge")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(len(body["rows"]), 44)
        self.assertEqual(body["summary"]["total"], 44)
        self.assertEqual(body["summary"]["reviewer_tbd_count"], 44)

    def test_patch_saves_status_and_comment(self) -> None:
        rows = self.client.get("/internal/review/v2/canonical-major-group-bridge").json()["rows"]
        key = next(r["review_key"] for r in rows if r["mapping_status"] == "EVIDENCED")
        r = self.client.patch(
            f"/internal/review/v2/canonical-major-group-bridge/{key}",
            json={"status": "APPROVE", "comment": "근거 충분"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["final_status"], "APPROVED")

        rows2 = self.client.get("/internal/review/v2/canonical-major-group-bridge").json()["rows"]
        row = next(r for r in rows2 if r["review_key"] == key)
        self.assertEqual(row["review"]["reviewer_1_status"], "APPROVE")
        self.assertEqual(row["review"]["reviewer_1_comment"], "근거 충분")

    def test_patch_unknown_key_returns_422(self) -> None:
        r = self.client.patch(
            "/internal/review/v2/canonical-major-group-bridge/does_not_exist::UNMAPPED",
            json={"status": "APPROVE"},
        )
        self.assertEqual(r.status_code, 422)

    def test_key_with_colons_round_trips_through_url_path(self) -> None:
        """복합 Key 자체에 "::"가 포함돼 있다 — URL 인코딩 후에도 서버가 정확히 같은
        행을 찾아야 한다."""

        from urllib.parse import quote

        rows = self.client.get("/internal/review/v2/canonical-major-group-bridge").json()["rows"]
        key = rows[0]["review_key"]
        self.assertIn("::", key)
        r = self.client.patch(f"/internal/review/v2/canonical-major-group-bridge/{quote(key, safe='')}", json={"status": "HOLD"})
        self.assertEqual(r.status_code, 200)

    def test_get_alone_never_creates_review_file(self) -> None:
        self.client.get("/internal/review/v2/canonical-major-group-bridge")
        self.assertFalse(self.review_path.exists())

    def test_repeated_get_calls_are_stable_no_auto_write(self) -> None:
        """필터를 바꾸는 흐름과 동일한 성격 — GET을 여러 번 호출해도(화면을 새로
        그리는 것과 같다) 검수 상태 파일이 전혀 생성되지 않는다."""

        for _ in range(5):
            r = self.client.get("/internal/review/v2/canonical-major-group-bridge")
            self.assertEqual(r.status_code, 200)
        self.assertFalse(self.review_path.exists())

    def test_bridge_route_not_shadowed_by_other_review_routes(self) -> None:
        r = self.client.get("/internal/review/v2/canonical-major-group-bridge")
        self.assertEqual(r.status_code, 200)
        # 기존 다른 탭 Endpoint도 여전히 정상 동작해야 한다(회귀 없음).
        r2 = self.client.get("/internal/review/v2/questions")
        self.assertEqual(r2.status_code, 200)


class NotWiredIntoRuntimeTest(unittest.TestCase):
    """§ 안전 규칙 "Runtime Matching과 Department 조회에 연결 금지" — 학생 공개 API
    소스에 이 신규 모듈에 대한 어떤 참조도 없어야 한다."""

    def test_public_api_module_does_not_import_bridge_review_modules(self) -> None:
        main_src = (_REPO_ROOT / "src" / "api" / "main.py").read_text(encoding="utf-8")
        self.assertNotIn("canonical_major_group_bridge_review", main_src)
        self.assertNotIn("review_ui", main_src)

    def test_review_app_is_not_the_public_app(self) -> None:
        from src.api.main import app as public_app

        self.assertIsNot(app, public_app)
        public_paths = {getattr(route, "path", "") for route in public_app.routes}
        self.assertNotIn("/internal/review/v2/canonical-major-group-bridge", public_paths)


class MasterDraftUntouchedByLoadTest(_BridgeTestBase):
    def test_repeated_loads_never_modify_master_draft(self) -> None:
        for _ in range(3):
            load_canonical_major_group_bridge()
        self.assertEqual(_sha256(self._REAL_BRIDGE_DRAFT_PATH), self._before_hashes["__bridge_draft__"])


if __name__ == "__main__":
    unittest.main()
