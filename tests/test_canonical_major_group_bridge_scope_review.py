"""Canonical Major Group Bridge Scope 검수 탭 테스트 — 2026-08-24 지시서
(a/bridge-scope-final-review-ui).

기존 Mapping 검수(`test_canonical_major_group_bridge_review.py`)와 완전히 독립된
두 번째 검수 축(Scope: FULL_GROUP/INCLUDED_SMALL_SERIES_ONLY/
DEPARTMENT_REVIEW_REQUIRED/EXCLUDED_RECOMMENDATION)이 화면에 표시되고, 별도 파일
(`data/reviews/canonical_major_group_bridge_scope_review_status.jsonl`)에만 저장되며,
Mapping 검수와 서로 자동으로 영향을 주지 않는지 검증한다. 같은 2계층 전략
(`StaticSourceTest` + Service/Api Layer)을 따른다."""

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
from src.schemas.canonical_major_group_bridge_scope_review import (
    CanonicalMajorGroupBridgeScopeReview,
    bridge_review_key,
)
from src.services.canonical_major_group_bridge_loader import DEFAULT_BRIDGE_DRAFT_PATH
from src.services.canonical_major_group_bridge_scope_review_store import (
    DuplicateBridgeScopeReviewKeyError,
    load_bridge_scope_review_entries_by_key,
    save_bridge_scope_review_entries,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_STATIC_DIR = _REPO_ROOT / "src" / "review_ui" / "static"
_HTML = (_STATIC_DIR / "index.html").read_text(encoding="utf-8")
_JS = (_STATIC_DIR / "review.js").read_text(encoding="utf-8")

_PRIORITY_KEYS = {
    ("business", "business_administration"),
    ("education", "education"),
    ("industrial_engineering", "industrial_engineering"),
    ("mechanical_transport", "mechanical_engineering"),
    ("computer_science", "hci_ux"),
    ("bio_medical_engineering", "life_science"),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _js_function_body(name: str) -> str:
    start = _JS.index(f"function {name}(")
    rest = _JS[start:]
    m = re.search(r"\n(async function |function )", rest[1:])
    return rest[: m.start() + 1] if m else rest


class StaticSourceTest(unittest.TestCase):
    def test_scope_filters_present(self) -> None:
        for value in (
            "all", "FULL_GROUP", "INCLUDED_SMALL_SERIES_ONLY", "DEPARTMENT_REVIEW_REQUIRED",
            "EXCLUDED_RECOMMENDATION", "none",
        ):
            self.assertIn(f'name="bridge-scope-type-filter" value="{value}"', _HTML)
        for value in ("all", "unreviewed", "reviewed"):
            self.assertIn(f'name="bridge-scope-review-filter" value="{value}"', _HTML)
        self.assertIn('id="bridge-filter-department-review"', _HTML)

    def test_existing_mapping_filters_still_present(self) -> None:
        """새 Scope 필터를 추가하면서 기존 Mapping 필터(대표 전공·경계 사례 포함)를
        지우지 않았는지 — 필수 통합 §7의 "대표 서비스 전공"·"경계 사례만"은 기존
        필터를 재사용하는 게 맞다."""

        self.assertIn('name="bridge-major-filter" value="media_communication"', _HTML)
        self.assertIn('id="bridge-filter-boundary"', _HTML)

    def test_scope_save_only_triggered_by_button_click(self) -> None:
        """안전 규칙 "저장 버튼을 눌렀을 때만 상태·코멘트 저장" — Scope PATCH
        (.../scope Endpoint)는 Scope 저장 버튼의 click 핸들러 안에만 있어야 하고,
        새 Scope 필터 변경 핸들러 안에는 전혀 없어야 한다."""

        card_src = _js_function_body("renderBridgeRowCard")
        self.assertIn('scopeSaveBtn.addEventListener("click", async () => {', card_src)
        click_handler_start = card_src.index('scopeSaveBtn.addEventListener("click"')
        click_handler_snippet = card_src[click_handler_start : click_handler_start + 600]
        self.assertIn("/scope", click_handler_snippet)
        self.assertIn("apiPatch(", click_handler_snippet)

        for filter_fn_marker in (
            'name="bridge-scope-type-filter"', 'name="bridge-scope-review-filter"',
            "bridge-filter-department-review",
        ):
            idx = _JS.index(filter_fn_marker)
            snippet = _JS[idx : idx + 400]
            self.assertNotIn("apiPatch(", snippet)

    def test_scope_and_mapping_save_hit_different_endpoints(self) -> None:
        """Mapping 저장 버튼과 Scope 저장 버튼이 서로 다른 URL을 부르는지 원문으로
        확인한다 — 이름이 비슷해서 실수로 같은 Endpoint를 두 번 부르면 두 축이
        하나로 합쳐진다."""

        card_src = _js_function_body("renderBridgeRowCard")
        mapping_click_idx = card_src.index('saveBtn.addEventListener("click"')
        scope_click_idx = card_src.index('scopeSaveBtn.addEventListener("click"')
        mapping_snippet = card_src[mapping_click_idx : mapping_click_idx + 400]
        scope_snippet = card_src[scope_click_idx : scope_click_idx + 400]
        self.assertNotIn("/scope", mapping_snippet)
        self.assertIn("/scope", scope_snippet)

    def test_priority_badge_rendering_logic_present(self) -> None:
        card_src = _js_function_body("renderBridgeRowCard")
        self.assertIn("is_priority_scope_review", card_src)
        self.assertIn("priority-badge", card_src)

    def test_official_small_series_names_rendered_alongside_codes(self) -> None:
        card_src = _js_function_body("renderBridgeRowCard")
        self.assertIn("included_small_series_names", card_src)
        self.assertIn("excluded_small_series_names", card_src)

    def test_no_hardcoded_scope_summary_numbers_in_html(self) -> None:
        summary_fn = _js_function_body("renderBridgeSummary")
        self.assertIn("state.bridgeSummary", summary_fn)
        self.assertNotIn(" 6", summary_fn.split("priority_scope_review_count")[0][-20:])

    def test_hash_deep_link_still_registered(self) -> None:
        self.assertIn('bridge: "bridge"', _JS)


class _BridgeScopeTestBase(unittest.TestCase):
    """Mapping 검수 테스트와 같은 tempdir 격리 + 실제 파일 SHA-256 무변경 증명
    전략을 그대로 따른다. 실제 Scope 검수 파일(`.jsonl`)이 이번 작업 전에 존재하지
    않았다면, 테스트가 끝난 뒤에도 여전히 존재하지 않아야 한다(자동 생성 금지)."""

    _REAL_BRIDGE_DRAFT_PATH = DEFAULT_BRIDGE_DRAFT_PATH
    _REAL_REVIEW_PATHS = sorted((_REPO_ROOT / "data" / "reviews").rglob("*.json")) + sorted(
        (_REPO_ROOT / "data" / "reviews").rglob("*.jsonl")
    )

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.mapping_review_path = Path(self.tmpdir.name) / "canonical_major_group_bridge_review_status.json"
        self.scope_review_path = Path(self.tmpdir.name) / "canonical_major_group_bridge_scope_review_status.jsonl"

        self._before_snapshot = self._snapshot_real_files()
        self.addCleanup(self._assert_real_files_untouched)

    def _snapshot_real_files(self) -> dict[str, object]:
        snapshot: dict[str, object] = {"__bridge_draft__": _sha256(self._REAL_BRIDGE_DRAFT_PATH)}
        for p in self._REAL_REVIEW_PATHS:
            snapshot[str(p)] = _sha256(p)
        real_scope_path = (
            _REPO_ROOT / "data" / "reviews" / "canonical_major_group_bridge_scope_review_status.jsonl"
        )
        snapshot["__real_scope_review_exists__"] = real_scope_path.exists()
        return snapshot

    def _assert_real_files_untouched(self) -> None:
        self.assertEqual(self._before_snapshot, self._snapshot_real_files(), "실제 파일이 테스트 중 바뀌었다 — 절대 금지 위반")


class ServiceLayerTest(_BridgeScopeTestBase):
    def _list(self):
        return cmgbrs.build_bridge_review_list(
            review_status_path=self.mapping_review_path, scope_review_status_path=self.scope_review_path,
        )

    def test_all_44_rows_carry_scope_info(self) -> None:
        resp = self._list()
        self.assertEqual(len(resp.rows), 44)
        for row in resp.rows:
            self.assertIsNotNone(row.scope_review)

    def test_scope_type_none_only_for_unmapped(self) -> None:
        resp = self._list()
        for row in resp.rows:
            if row.mapping_status == "UNMAPPED":
                self.assertIsNone(row.scope_type)
            else:
                self.assertIsNotNone(row.scope_type)

    def test_included_and_excluded_codes_paired_with_official_names(self) -> None:
        resp = self._list()
        business_row = next(
            r for r in resp.rows if r.canonical_major_group_id == "business" and r.canonical_major_id == "business_administration"
        )
        self.assertEqual(business_row.scope_type, "INCLUDED_SMALL_SERIES_ONLY")
        self.assertEqual(business_row.included_small_series_codes, ["033"])
        self.assertEqual(business_row.included_small_series_names, ["경영학"])
        self.assertEqual(len(business_row.excluded_small_series_codes), len(business_row.excluded_small_series_names))
        self.assertGreater(len(business_row.excluded_small_series_codes), 0)

    def test_priority_scope_review_flag_matches_exactly_the_6_named_rows(self) -> None:
        resp = self._list()
        flagged = {
            (r.canonical_major_group_id, r.canonical_major_id) for r in resp.rows if r.is_priority_scope_review
        }
        self.assertEqual(flagged, _PRIORITY_KEYS)
        self.assertEqual(resp.summary.priority_scope_review_count, 6)

    def test_computer_science_to_computer_science_is_full_group(self) -> None:
        resp = self._list()
        row = next(
            r for r in resp.rows if r.canonical_major_group_id == "computer_science" and r.canonical_major_id == "computer_science"
        )
        self.assertEqual(row.scope_type, "FULL_GROUP")
        self.assertFalse(row.is_priority_scope_review)

    def test_computer_science_to_hci_ux_is_department_review_required(self) -> None:
        resp = self._list()
        row = next(
            r for r in resp.rows if r.canonical_major_group_id == "computer_science" and r.canonical_major_id == "hci_ux"
        )
        self.assertEqual(row.scope_type, "DEPARTMENT_REVIEW_REQUIRED")

    def test_bio_medical_engineering_to_life_science_is_department_review_required(self) -> None:
        resp = self._list()
        row = next(
            r for r in resp.rows
            if r.canonical_major_group_id == "bio_medical_engineering" and r.canonical_major_id == "life_science"
        )
        self.assertEqual(row.scope_type, "DEPARTMENT_REVIEW_REQUIRED")

    def test_no_scope_review_is_pre_approved(self) -> None:
        """자동 승인 절대 금지 — 저장 파일이 없는 상태에서는 44행 전부
        scope_review.reviewer_1_status가 TBD여야 한다."""

        resp = self._list()
        statuses = {r.scope_review.reviewer_1_status for r in resp.rows}
        self.assertEqual(statuses, {"TBD"})
        self.assertEqual(resp.summary.scope_reviewer_approve_count, 0)
        self.assertEqual(resp.summary.scope_unreviewed_count, 44)

    def test_mapping_approve_does_not_auto_approve_scope(self) -> None:
        """Mapping APPROVE가 Scope 자동 APPROVE를 발생시키면 안 됨(지시서 §2)."""

        resp = self._list()
        evidenced_row = next(r for r in resp.rows if r.mapping_status == "EVIDENCED")
        cmgbrs.update_bridge_review(
            evidenced_row.review_key, status="APPROVE", comment="Mapping 승인",
            resolution_note=None, review_status_path=self.mapping_review_path,
        )
        resp2 = self._list()
        row2 = next(r for r in resp2.rows if r.review_key == evidenced_row.review_key)
        self.assertEqual(row2.review.reviewer_1_status, "APPROVE")
        self.assertEqual(row2.scope_review.reviewer_1_status, "TBD", "Mapping APPROVE가 Scope를 자동 승인시켰다")

    def test_scope_approve_does_not_change_mapping(self) -> None:
        """Scope APPROVE가 Mapping 상태를 바꾸면 안 됨(지시서 §2)."""

        resp = self._list()
        key = resp.rows[0].review_key
        before_mapping_status = resp.rows[0].review.reviewer_1_status
        cmgbrs.update_bridge_scope_review(
            key, status="APPROVE", comment="범위 확인함", resolution_note=None,
            scope_review_status_path=self.scope_review_path,
        )
        resp2 = self._list()
        row2 = next(r for r in resp2.rows if r.review_key == key)
        self.assertEqual(row2.scope_review.reviewer_1_status, "APPROVE")
        self.assertEqual(row2.review.reviewer_1_status, before_mapping_status, "Scope APPROVE가 Mapping 상태를 바꿨다")

    def test_get_style_load_never_writes_scope_review_file(self) -> None:
        self._list()
        self._list()
        self.assertFalse(self.scope_review_path.exists(), "목록 조회만으로 Scope 검수 상태 파일이 생성/기록되면 안 된다")

    def test_get_never_writes_mapping_review_file_either(self) -> None:
        self._list()
        self.assertFalse(self.mapping_review_path.exists())

    def test_save_and_reload_round_trip_touches_only_target_row(self) -> None:
        resp = self._list()
        key = resp.rows[3].review_key
        out = cmgbrs.update_bridge_scope_review(
            key, status="REVISE", comment="소계열 재검토 필요", resolution_note=None,
            scope_review_status_path=self.scope_review_path,
        )
        self.assertTrue(out.ok)
        self.assertEqual(out.final_status, "REVIEW_REQUIRED")

        resp2 = self._list()
        row = next(r for r in resp2.rows if r.review_key == key)
        self.assertEqual(row.scope_review.reviewer_1_status, "REVISE")
        self.assertEqual(row.scope_review.reviewer_1_comment, "소계열 재검토 필요")

        others = [r for r in resp2.rows if r.review_key != key]
        self.assertTrue(all(r.scope_review.reviewer_1_status == "TBD" for r in others))

    def test_partial_save_none_means_unchanged(self) -> None:
        resp = self._list()
        key = resp.rows[0].review_key
        cmgbrs.update_bridge_scope_review(
            key, status="HOLD", comment="1차 코멘트", resolution_note=None,
            scope_review_status_path=self.scope_review_path,
        )
        cmgbrs.update_bridge_scope_review(
            key, status=None, comment="수정된 코멘트", resolution_note=None,
            scope_review_status_path=self.scope_review_path,
        )
        row = next(r for r in self._list().rows if r.review_key == key)
        self.assertEqual(row.scope_review.reviewer_1_status, "HOLD")
        self.assertEqual(row.scope_review.reviewer_1_comment, "수정된 코멘트")

    def test_unknown_review_key_rejected(self) -> None:
        with self.assertRaises(cmgbrs.UnknownBridgeReviewKeyError):
            cmgbrs.update_bridge_scope_review(
                "does_not_exist::UNMAPPED", status="APPROVE", comment=None, resolution_note=None,
                scope_review_status_path=self.scope_review_path,
            )
        self.assertFalse(self.scope_review_path.exists())

    def test_duplicate_key_rejected_on_save(self) -> None:
        dup = [
            CanonicalMajorGroupBridgeScopeReview(canonical_major_group_id="computer_science", canonical_major_id="computer_science"),
            CanonicalMajorGroupBridgeScopeReview(canonical_major_group_id="computer_science", canonical_major_id="computer_science"),
        ]
        with self.assertRaises(DuplicateBridgeScopeReviewKeyError):
            save_bridge_scope_review_entries(dup, self.scope_review_path)
        self.assertFalse(self.scope_review_path.exists(), "중복 Key 저장 시도가 부분적으로라도 파일을 남기면 안 된다")

    def test_duplicate_key_rejected_on_manual_load(self) -> None:
        self.scope_review_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            json.dumps({"canonical_major_group_id": "computer_science", "canonical_major_id": "computer_science"}),
            json.dumps({"canonical_major_group_id": "computer_science", "canonical_major_id": "computer_science"}),
        ]
        self.scope_review_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with self.assertRaises(DuplicateBridgeScopeReviewKeyError):
            load_bridge_scope_review_entries_by_key(self.scope_review_path)

    def test_key_matches_mapping_review_key_convention(self) -> None:
        """같은 (group_id, major_id)라면 Mapping 검수 Key와 Scope 검수 Key가 항상
        동일한 문자열이어야 한다(두 파일을 나란히 조인할 수 있어야 하므로)."""

        self.assertEqual(bridge_review_key("business", "business_administration"), "business::business_administration")
        self.assertEqual(bridge_review_key("music", None), "music::UNMAPPED")


class ApiLayerTest(_BridgeScopeTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.client = TestClient(app)
        mapping_patcher = patch(
            "src.review_ui.canonical_major_group_bridge_review_service.BRIDGE_REVIEW_STATUS_PATH",
            self.mapping_review_path,
        )
        scope_patcher = patch(
            "src.review_ui.canonical_major_group_bridge_review_service.BRIDGE_SCOPE_REVIEW_STATUS_PATH",
            self.scope_review_path,
        )
        mapping_patcher.start()
        scope_patcher.start()
        self.addCleanup(mapping_patcher.stop)
        self.addCleanup(scope_patcher.stop)

    def test_get_includes_scope_fields_and_summary(self) -> None:
        r = self.client.get("/internal/review/v2/canonical-major-group-bridge")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["summary"]["priority_scope_review_count"], 6)
        self.assertEqual(body["summary"]["scope_unreviewed_count"], 44)
        row = next(row for row in body["rows"] if row["canonical_major_group_id"] == "education")
        self.assertEqual(row["scope_type"], "INCLUDED_SMALL_SERIES_ONLY")
        self.assertEqual(row["included_small_series_codes"], ["042"])
        self.assertEqual(row["included_small_series_names"], ["교육학"])
        self.assertEqual(row["scope_review"]["reviewer_1_status"], "TBD")

    def test_patch_scope_endpoint_saves_only_scope_file(self) -> None:
        rows = self.client.get("/internal/review/v2/canonical-major-group-bridge").json()["rows"]
        key = next(r["review_key"] for r in rows if r["mapping_status"] == "EVIDENCED")

        r = self.client.patch(
            f"/internal/review/v2/canonical-major-group-bridge/{key}/scope",
            json={"status": "APPROVE", "comment": "범위 근거 충분"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["final_status"], "APPROVED")

        self.assertTrue(self.scope_review_path.exists())
        self.assertFalse(self.mapping_review_path.exists(), "Scope PATCH가 Mapping 검수 파일을 만들면 안 된다")

        rows2 = self.client.get("/internal/review/v2/canonical-major-group-bridge").json()["rows"]
        row2 = next(r for r in rows2 if r["review_key"] == key)
        self.assertEqual(row2["scope_review"]["reviewer_1_status"], "APPROVE")
        self.assertEqual(row2["scope_review"]["reviewer_1_comment"], "범위 근거 충분")
        self.assertEqual(row2["review"]["reviewer_1_status"], "TBD", "Scope PATCH가 Mapping 상태를 바꿨다")

    def test_patch_mapping_endpoint_does_not_touch_scope_file(self) -> None:
        rows = self.client.get("/internal/review/v2/canonical-major-group-bridge").json()["rows"]
        key = next(r["review_key"] for r in rows if r["mapping_status"] == "EVIDENCED")

        r = self.client.patch(
            f"/internal/review/v2/canonical-major-group-bridge/{key}",
            json={"status": "APPROVE", "comment": "Mapping 근거 충분"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self.mapping_review_path.exists())
        self.assertFalse(self.scope_review_path.exists(), "Mapping PATCH가 Scope 검수 파일을 만들면 안 된다")

    def test_patch_scope_unknown_key_returns_422(self) -> None:
        r = self.client.patch(
            "/internal/review/v2/canonical-major-group-bridge/does_not_exist::UNMAPPED/scope",
            json={"status": "APPROVE"},
        )
        self.assertEqual(r.status_code, 422)

    def test_get_alone_never_creates_either_review_file(self) -> None:
        for _ in range(3):
            self.client.get("/internal/review/v2/canonical-major-group-bridge")
        self.assertFalse(self.mapping_review_path.exists())
        self.assertFalse(self.scope_review_path.exists())


class ExistingMappingReviewPreservedTest(unittest.TestCase):
    """§9 "기존 44행 Mapping 상태 38/6 보존" — 이번 Scope 검수 탭 작업이 실제
    Mapping 검수 파일(사용자가 이미 완료한 검수 결과)의 값을 조금도 바꾸지
    않았는지, 진짜 파일을 읽어 직접 확인한다."""

    def test_real_mapping_review_file_still_38_approve_6_revise(self) -> None:
        from src.services.canonical_major_group_bridge_review_store import load_bridge_review_entries_by_key

        entries = load_bridge_review_entries_by_key()
        statuses = [e.reviewer_1_status for e in entries.values()]
        self.assertEqual(statuses.count("APPROVE"), 38)
        self.assertEqual(statuses.count("REVISE"), 6)
        self.assertEqual(len(entries), 44)


class InvalidScopeCodeStillFailsFastThroughThisUiTest(unittest.TestCase):
    """이 Review UI도 결국 `load_canonical_major_group_bridge()`(A-1 정본 Loader)를
    그대로 재사용하므로, 잘못된 소계열 코드가 섞인 Draft를 읽으면 이 UI의 서비스
    함수도 그대로 예외를 던져야 한다(별도의, 더 관대한 검증 경로를 만들지
    않았다는 증거)."""

    def test_build_bridge_review_list_raises_on_unknown_small_series_code(self) -> None:
        """실제 44행 전부를 로드한 뒤, 그중 한 행의 코드만 존재하지 않는 값으로
        바꿔서 이 UI의 서비스 함수(`build_bridge_review_list`)가 여전히
        Fail-Fast로 죽는지 확인한다(완결성 검사를 지나 Scope 교차 검증까지
        실제로 도달해야 하므로, 44행 전체가 채워진 파일이 필요하다)."""

        from src.services.canonical_major_group_bridge_loader import (
            BridgeScopeValidationError,
            DEFAULT_BRIDGE_DRAFT_PATH,
        )

        real_rows = [
            json.loads(line) for line in DEFAULT_BRIDGE_DRAFT_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        for row in real_rows:
            if row["canonical_major_group_id"] == "business" and row["canonical_major_id"] == "business_administration":
                row["included_small_series_codes"] = ["999_not_a_real_official_code"]
                break

        with tempfile.TemporaryDirectory() as tmp:
            bad_path = Path(tmp) / "bad_bridge.jsonl"
            bad_path.write_text("\n".join(json.dumps(r) for r in real_rows) + "\n", encoding="utf-8")
            with self.assertRaises(BridgeScopeValidationError):
                cmgbrs.build_bridge_review_list(
                    bridge_path=bad_path,
                    review_status_path=Path(tmp) / "mapping.json",
                    scope_review_status_path=Path(tmp) / "scope.jsonl",
                )


if __name__ == "__main__":
    unittest.main()
