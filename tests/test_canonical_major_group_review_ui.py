"""Canonical Major Group(42개) 검수 탭 테스트 — 2026-08-24 지시서
(a/canonical-major-group-review-ui).

Bridge/P1/N.C.E 검수와 같은 2계층 전략(정적 소스 검증 + 실제 서비스/API 호출)을
따른다. 모든 저장 테스트는 `tempfile.TemporaryDirectory()`만 쓰고 실제
`data/reviews/`·`data/canonical_major_groups.draft.jsonl`·`data/academyinfo_work/`
파일은 절대 건드리지 않는다 — 매 테스트가 실제 파일들의 SHA-256을 스냅샷하고
종료 시 재확인한다."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.review_ui import canonical_major_group_review_service as cmgrs
from src.review_ui.app import app
from src.schemas.canonical_major_group_review import CanonicalMajorGroupReview
from src.services.canonical_major_group_review_store import (
    DuplicateCanonicalMajorGroupReviewKeyError,
    load_canonical_major_group_review_entries_by_key,
    save_canonical_major_group_review_entries,
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
        self.assertIn('id="tab-canonical-major-groups-btn"', _HTML)
        self.assertIn('id="cmg-container"', _HTML)
        self.assertIn('id="cmg-summary-box"', _HTML)

    def test_filters_present(self) -> None:
        for value in ("all", "TBD", "APPROVE_AS_CLASSIFICATION_GROUP", "REVISE", "HOLD", "EXCLUDE_FROM_CLASSIFICATION"):
            self.assertIn(f'name="cmg-decision-filter" value="{value}"', _HTML)
        self.assertIn('id="cmg-filter-arts"', _HTML)
        self.assertIn('id="cmg-filter-nce"', _HTML)
        for value in ("all", "linked", "unlinked"):
            self.assertIn(f'name="cmg-bridge-filter" value="{value}"', _HTML)
        self.assertIn('id="cmg-sort-key"', _HTML)
        for value in ("id", "small_series_count", "department_count"):
            self.assertIn(f'value="{value}"', _HTML)

    def test_summary_box_ids_present(self) -> None:
        self.assertIn('id="cmg-summary-box"', _HTML)

    def test_save_only_triggered_by_button_click(self) -> None:
        card_src = _js_function_body("renderCmgRowCard")
        self.assertIn('saveBtn.addEventListener("click", async () => {', card_src)
        click_start = card_src.index('saveBtn.addEventListener("click"')
        self.assertIn("apiPatch(", card_src[click_start:])
        self.assertIn("expected_revision", card_src[click_start:])

        for marker in ('name="cmg-decision-filter"', "cmg-filter-arts", "cmg-filter-nce", 'name="cmg-bridge-filter"', "cmg-sort-key"):
            idx = _JS.index(marker)
            self.assertNotIn("apiPatch(", _JS[idx : idx + 400])

    def test_no_bulk_approve_all_function_or_button_exists(self) -> None:
        """§4 "'전체 승인' 버튼은 만들지 않는다" — 그런 이름의 함수/버튼이 이 탭
        코드 어디에도 없어야 한다(전역 검사 — 다른 탭에도 없어야 한다는 사실은
        기존 테스트가 이미 고정하고 있으므로 여기서는 내 카드 함수 안에 그런 걸
        추가하지 않았는지만 다시 확인한다)."""

        card_src = _js_function_body("renderCmgRowCard")
        container_src = _js_function_body("renderCmgContainer")
        for forbidden in ("approveAll", "모두 승인", "일괄 승인", "bulkApprove", "전체 승인"):
            self.assertNotIn(forbidden, card_src)
            self.assertNotIn(forbidden, container_src)

    def test_approve_disclaimer_shown_on_card(self) -> None:
        card_src = _js_function_body("renderCmgRowCard")
        self.assertIn("42개 중간 분류 Ontology로 사용 가능", card_src)
        for phrase in ("서비스 추천 전공 승인", "전국 학과 자동 승격", "예체능 추천 허용", "Bridge Mapping/Scope 승인"):
            self.assertIn(phrase, card_src)

    def test_hash_deep_link_registered(self) -> None:
        self.assertIn('canonical_major_groups: "canonical-major-groups"', _JS)


class _PreservationTestBase(unittest.TestCase):
    """§6 "기존 검수 보존" — 지시서가 명시한 파일들의 SHA-256을 테스트 전후로
    직접 대조한다."""

    _PROTECTED_PATHS = [
        _REPO_ROOT / "data" / "canonical_major_groups.draft.jsonl",
        _REPO_ROOT / "data" / "reviews" / "canonical_major_group_bridge_review_status.json",
        _REPO_ROOT / "data" / "master" / "canonical_major_group_bridge.draft.jsonl",
        _REPO_ROOT / "data" / "academyinfo_work" / "2025" / "packets" / "p1_classification_review.jsonl",
        _REPO_ROOT / "data" / "academyinfo_work" / "2025" / "packets" / "nce_reexaminable_middle_series_clusters.jsonl",
        _REPO_ROOT / "data" / "academyinfo_work" / "2025" / "classification_dry_run.json",
    ]
    _OPTIONAL_PATHS = [
        _REPO_ROOT / "data" / "reviews" / "canonical_major_group_bridge_scope_review_status.jsonl",
        _REPO_ROOT / "data" / "reviews" / "academyinfo_p1_classification_review_status.jsonl",
        _REPO_ROOT / "data" / "reviews" / "academyinfo_nce_middle_series_review_status.jsonl",
    ]
    _NEW_REVIEW_REAL_PATH = _REPO_ROOT / "data" / "reviews" / "canonical_major_group_review_status.jsonl"

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.review_path = Path(self.tmpdir.name) / "canonical_major_group_review_status.jsonl"

        self._before = self._snapshot()
        self.addCleanup(self._assert_unchanged)

    def _snapshot(self) -> dict[str, object]:
        snap: dict[str, object] = {str(p): _sha256(p) for p in self._PROTECTED_PATHS}
        for p in self._OPTIONAL_PATHS:
            snap[f"__exists__{p}"] = p.exists()
            if p.exists():
                snap[f"__sha__{p}"] = _sha256(p)
        # §6이 요구하는 "신규 Group Review 파일은 사용자가 실제 저장하기 전까지
        # 생성하지 않는다" — 이 테스트 스위트 전체가 실제 경로가 아니라
        # self.review_path(tempdir)만 쓰므로, 실제 경로는 테스트 시작 전 상태
        # 그대로(존재하면 존재, 없으면 없음) 남아야 한다.
        snap["__new_review_exists__"] = self._NEW_REVIEW_REAL_PATH.exists()
        return snap

    def _assert_unchanged(self) -> None:
        self.assertEqual(self._before, self._snapshot(), "실제 파일이 테스트 중 바뀌었다 — 절대 금지 위반")


class ServiceLayerTest(_PreservationTestBase):
    def _list(self):
        return cmgrs.build_canonical_major_group_review_list(review_status_path=self.review_path)

    def test_exactly_42_groups(self) -> None:
        resp = self._list()
        self.assertEqual(resp.summary.total, 42)
        self.assertEqual(len(resp.rows), 42)

    def test_no_duplicate_ids(self) -> None:
        resp = self._list()
        ids = [r.canonical_major_group_id for r in resp.rows]
        self.assertEqual(len(ids), len(set(ids)), "42개 Group ID 중 중복이 있다")

    def test_draft_and_ui_rows_one_to_one(self) -> None:
        from src.services.canonical_major_group_draft_loader import load_canonical_major_groups_draft

        draft_ids = {g.canonical_major_id for g in load_canonical_major_groups_draft()}
        resp = self._list()
        ui_ids = {r.canonical_major_group_id for r in resp.rows}
        self.assertEqual(draft_ids, ui_ids)

    def test_official_codes_present_and_series_joined(self) -> None:
        resp = self._list()
        for r in resp.rows:
            self.assertGreater(len(r.included_official_small_series_codes), 0)
            self.assertEqual(len(r.official_series.included_small_series_names), len(r.included_official_small_series_codes))
            self.assertGreater(len(r.official_series.large_series_codes), 0, r.canonical_major_group_id)
            self.assertGreater(len(r.official_series.middle_series_codes), 0, r.canonical_major_group_id)
            self.assertEqual(len(r.official_series.large_series_codes), len(r.official_series.large_series_names))
            self.assertEqual(len(r.official_series.middle_series_codes), len(r.official_series.middle_series_names))

    def test_all_initially_tbd(self) -> None:
        resp = self._list()
        self.assertEqual({r.review.decision for r in resp.rows}, {"TBD"})
        self.assertEqual(resp.summary.tbd_count, 42)
        self.assertEqual(resp.summary.unreviewed_count, 42)
        self.assertEqual(resp.summary.reviewed_count, 0)

    def test_get_style_load_never_writes_review_file(self) -> None:
        self._list()
        self._list()
        self.assertFalse(self.review_path.exists())

    def test_four_arts_or_sports_groups(self) -> None:
        """§ "예체능 4개" — 42개 안에 보이지만, 이 Flag 자체가 추천 승인을 의미하지
        않는다는 사실은 Schema 문서와 UI 문구(StaticSourceTest)에서 강제한다."""

        resp = self._list()
        arts = {r.canonical_major_group_id for r in resp.rows if r.is_arts_or_sports_group}
        self.assertEqual(arts, {"fine_arts_design", "music", "performing_media_arts", "sports_dance"})
        self.assertEqual(resp.summary.arts_or_sports_count, 4)

    def test_bridge_and_nce_linkage_flags_are_booleans_and_summary_consistent(self) -> None:
        resp = self._list()
        linked = sum(1 for r in resp.rows if r.is_bridge_linked)
        unlinked = sum(1 for r in resp.rows if not r.is_bridge_linked)
        self.assertEqual(linked, resp.summary.bridge_linked_count)
        self.assertEqual(unlinked, resp.summary.bridge_unlinked_count)
        self.assertEqual(linked + unlinked, 42)
        nce_related = sum(1 for r in resp.rows if r.is_nce_related)
        self.assertEqual(nce_related, resp.summary.nce_related_count)

    def test_save_touches_only_target_row(self) -> None:
        resp = self._list()
        target = resp.rows[10]
        cmgrs.update_canonical_major_group_review(
            target.canonical_major_group_id, decision="HOLD", comment="검토 보류", resolution_note=None,
            expected_revision=0, review_status_path=self.review_path,
        )
        resp2 = self._list()
        row = next(r for r in resp2.rows if r.canonical_major_group_id == target.canonical_major_group_id)
        self.assertEqual(row.review.decision, "HOLD")
        others = [r for r in resp2.rows if r.canonical_major_group_id != target.canonical_major_group_id]
        self.assertTrue(all(r.review.decision == "TBD" for r in others))

    def test_partial_save_none_means_unchanged(self) -> None:
        resp = self._list()
        target = resp.rows[0]
        cmgrs.update_canonical_major_group_review(
            target.canonical_major_group_id, decision="HOLD", comment="1차", resolution_note=None,
            expected_revision=0, review_status_path=self.review_path,
        )
        cmgrs.update_canonical_major_group_review(
            target.canonical_major_group_id, decision=None, comment="수정", resolution_note=None,
            expected_revision=1, review_status_path=self.review_path,
        )
        row = next(r for r in self._list().rows if r.canonical_major_group_id == target.canonical_major_group_id)
        self.assertEqual(row.review.decision, "HOLD")
        self.assertEqual(row.review.reviewer_1_comment, "수정")

    def test_stale_revision_rejected(self) -> None:
        resp = self._list()
        target = resp.rows[0]
        cmgrs.update_canonical_major_group_review(
            target.canonical_major_group_id, decision="HOLD", comment=None, resolution_note=None,
            expected_revision=0, review_status_path=self.review_path,
        )
        with self.assertRaises(cmgrs.CanonicalMajorGroupStaleRevisionError):
            cmgrs.update_canonical_major_group_review(
                target.canonical_major_group_id, decision="REVISE_GROUP_DEFINITION", comment=None, resolution_note=None,
                expected_revision=0, review_status_path=self.review_path,
            )

    def test_unknown_group_rejected(self) -> None:
        with self.assertRaises(cmgrs.UnknownCanonicalMajorGroupIdError):
            cmgrs.update_canonical_major_group_review(
                "does_not_exist", decision="HOLD", comment=None, resolution_note=None,
                expected_revision=0, review_status_path=self.review_path,
            )
        self.assertFalse(self.review_path.exists())

    def test_no_call_auto_approves(self) -> None:
        """§5 "Draft의 review_status를 자동 변경하지 않음" — decision=None(부분
        저장)으로만 호출해도 값이 APPROVE로 바뀌지 않는다."""

        resp = self._list()
        target = resp.rows[0]
        cmgrs.update_canonical_major_group_review(
            target.canonical_major_group_id, decision=None, comment="코멘트만", resolution_note=None,
            expected_revision=0, review_status_path=self.review_path,
        )
        row = next(r for r in self._list().rows if r.canonical_major_group_id == target.canonical_major_group_id)
        self.assertEqual(row.review.decision, "TBD")

    def test_final_status_computed_from_decision(self) -> None:
        entry = CanonicalMajorGroupReview(canonical_major_group_id="x")
        self.assertEqual(entry.final_status, "DRAFT")
        entry2 = CanonicalMajorGroupReview(
            canonical_major_group_id="x", decision="APPROVE_AS_CLASSIFICATION_GROUP", reviewer_1_status="APPROVE",
        )
        self.assertEqual(entry2.final_status, "APPROVED")
        for d in ("REVISE_GROUP_DEFINITION", "SPLIT_GROUP", "MERGE_WITH_OTHER_GROUP", "EXCLUDE_FROM_CLASSIFICATION"):
            entry3 = CanonicalMajorGroupReview(canonical_major_group_id="x", decision=d, reviewer_1_status="REVISE")
            self.assertEqual(entry3.final_status, "REVIEW_REQUIRED", d)
        entry4 = CanonicalMajorGroupReview(canonical_major_group_id="x", decision="HOLD", reviewer_1_status="HOLD")
        self.assertEqual(entry4.final_status, "REVIEW_REQUIRED")

    def test_reviewer_1_status_decision_contradiction_rejected(self) -> None:
        """§3 Group Review 불변식 — decision과 reviewer_1_status가 서로 다른
        판단을 나타내는 조합은 어떤 경로로도 저장할 수 없어야 한다."""

        from src.schemas.canonical_major_group_review import expected_reviewer_1_status_for_decision

        contradictory_pairs = [
            ("APPROVE_AS_CLASSIFICATION_GROUP", "TBD"),  # §3 "APPROVE인데 미검수로 표시되지 않음"
            ("APPROVE_AS_CLASSIFICATION_GROUP", "REVISE"),
            ("APPROVE_AS_CLASSIFICATION_GROUP", "HOLD"),
            ("TBD", "APPROVE"),  # §3 "TBD인데 검수 완료로 표시되지 않음"
            ("TBD", "REVISE"),
            ("TBD", "HOLD"),
            ("HOLD", "TBD"),
            ("HOLD", "APPROVE"),
            ("REVISE_GROUP_DEFINITION", "TBD"),
            ("REVISE_GROUP_DEFINITION", "APPROVE"),
            ("SPLIT_GROUP", "TBD"),
            ("EXCLUDE_FROM_CLASSIFICATION", "APPROVE"),
        ]
        for decision, reviewer_1_status in contradictory_pairs:
            with self.assertRaises(Exception, msg=f"{decision=} {reviewer_1_status=}"):
                CanonicalMajorGroupReview(
                    canonical_major_group_id="x", decision=decision, reviewer_1_status=reviewer_1_status,
                )

        # 대응하는 값이면 전부 허용돼야 한다(거부 규칙이 지나치게 넓지 않은지 확인).
        for decision in (
            "TBD", "APPROVE_AS_CLASSIFICATION_GROUP", "REVISE_GROUP_DEFINITION", "SPLIT_GROUP",
            "MERGE_WITH_OTHER_GROUP", "EXCLUDE_FROM_CLASSIFICATION", "HOLD",
        ):
            allowed_status = expected_reviewer_1_status_for_decision(decision)
            entry = CanonicalMajorGroupReview(
                canonical_major_group_id="x", decision=decision, reviewer_1_status=allowed_status,
            )
            self.assertEqual(entry.reviewer_1_status, allowed_status)

    def test_reviewer_2_status_not_required_and_not_validated(self) -> None:
        """§3 "reviewer_2 기본값은 기존대로 유지하되 2차 검토를 요구하지 않음" —
        reviewer_2_status가 TBD로 남아 있어도(2차 검토 없음) 저장·검증에 전혀
        영향을 주지 않는다. reviewer_2_status에 임의 값을 넣어도(그 자체로는
        모순 검사 대상이 아니므로) 거부되지 않는다."""

        entry = CanonicalMajorGroupReview(
            canonical_major_group_id="x", decision="APPROVE_AS_CLASSIFICATION_GROUP", reviewer_1_status="APPROVE",
        )
        self.assertEqual(entry.reviewer_2_status, "TBD")
        self.assertEqual(entry.reviewer_2_comment, "")

        for reviewer_2_status in ("TBD", "APPROVE", "REVISE", "HOLD"):
            entry2 = CanonicalMajorGroupReview(
                canonical_major_group_id="x", decision="APPROVE_AS_CLASSIFICATION_GROUP", reviewer_1_status="APPROVE",
                reviewer_2_status=reviewer_2_status,
            )
            self.assertEqual(entry2.final_status, "APPROVED", reviewer_2_status)

    def test_save_always_syncs_reviewer_1_status_to_decision(self) -> None:
        """저장 경로(`update_canonical_major_group_review`)를 거치면 decision이
        바뀔 때마다 reviewer_1_status도 항상 함께 동기화된다 — 화면(review View)·
        Store(JSONL)·API 응답 세 곳 모두 같은 값을 본다."""

        from src.schemas.canonical_major_group_review import expected_reviewer_1_status_for_decision
        from src.services.canonical_major_group_review_store import load_canonical_major_group_review_entries_by_key

        for i, decision in enumerate((
            "APPROVE_AS_CLASSIFICATION_GROUP", "REVISE_GROUP_DEFINITION", "SPLIT_GROUP",
            "MERGE_WITH_OTHER_GROUP", "EXCLUDE_FROM_CLASSIFICATION", "HOLD", "TBD",
        )):
            out = cmgrs.update_canonical_major_group_review(
                "agriculture_fisheries", decision=decision, comment=None, resolution_note=None,
                expected_revision=i, review_status_path=self.review_path,
            )
            self.assertEqual(out.decision, decision)

            row = next(r for r in self._list().rows if r.canonical_major_group_id == "agriculture_fisheries")
            expected_status = expected_reviewer_1_status_for_decision(decision)
            self.assertEqual(row.review.decision, decision)
            self.assertEqual(row.review.reviewer_1_status, expected_status, decision)

            stored = load_canonical_major_group_review_entries_by_key(self.review_path)["agriculture_fisheries"]
            self.assertEqual(stored.decision, decision)
            self.assertEqual(stored.reviewer_1_status, expected_status, decision)

    def test_duplicate_key_rejected_on_save(self) -> None:
        dup = [
            CanonicalMajorGroupReview(canonical_major_group_id="dup1"),
            CanonicalMajorGroupReview(canonical_major_group_id="dup1"),
        ]
        with self.assertRaises(DuplicateCanonicalMajorGroupReviewKeyError):
            save_canonical_major_group_review_entries(dup, self.review_path)
        self.assertFalse(self.review_path.exists())

    def test_duplicate_key_rejected_on_manual_load(self) -> None:
        self.review_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps({"canonical_major_group_id": "dup1"}), json.dumps({"canonical_major_group_id": "dup1"})]
        self.review_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with self.assertRaises(DuplicateCanonicalMajorGroupReviewKeyError):
            load_canonical_major_group_review_entries_by_key(self.review_path)

    def test_small_series_to_middle_large_lookup_has_no_duplicate_parents(self) -> None:
        """`_load_small_to_parent_series`가 전제하는 "소계열 코드 하나 = 정확히
        하나의 (중계열, 대계열)" 사실을 직접 고정한다 — 이 전제가 깨지면 조인
        결과가 조용히 마지막 값으로 덮어써지므로, 실제 원본 코드표로 다시
        확인한다."""

        import gzip

        with gzip.open(cmgrs.DEFAULT_SERIES_SYSTEM_TABLE_PATH, "rt", encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]
        by_small: dict[str, set[tuple[str, str]]] = {}
        for row in rows:
            if row["srsSclftCd"] == "999":
                continue
            by_small.setdefault(row["srsSclftCd"], set()).add((row["srsMclftCd"], row["srsLclftCd"]))
        multi = {k: v for k, v in by_small.items() if len(v) > 1}
        self.assertEqual(multi, {})


class ApiLayerTest(_PreservationTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.client = TestClient(app)
        patcher = patch("src.review_ui.canonical_major_group_review_service.REVIEW_STATUS_PATH", self.review_path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_get_returns_42(self) -> None:
        r = self.client.get("/internal/review/v2/canonical-major-groups")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["summary"]["total"], 42)
        self.assertEqual(len(body["rows"]), 42)

    def test_patch_saves_and_requires_expected_revision(self) -> None:
        rows = self.client.get("/internal/review/v2/canonical-major-groups").json()["rows"]
        group_id = rows[0]["canonical_major_group_id"]
        r = self.client.patch(
            f"/internal/review/v2/canonical-major-groups/{group_id}",
            json={"decision": "APPROVE_AS_CLASSIFICATION_GROUP", "comment": "확인", "expected_revision": 0},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["new_revision"], 1)

        r2 = self.client.patch(
            f"/internal/review/v2/canonical-major-groups/{group_id}",
            json={"decision": "HOLD", "expected_revision": 0},
        )
        self.assertEqual(r2.status_code, 409, "revision 충돌은 409여야 한다")

    def test_patch_unknown_group_returns_422(self) -> None:
        r = self.client.patch(
            "/internal/review/v2/canonical-major-groups/does_not_exist",
            json={"decision": "HOLD", "expected_revision": 0},
        )
        self.assertEqual(r.status_code, 422, "미등록 Group은 422여야 한다")

    def test_get_alone_never_creates_file(self) -> None:
        for _ in range(3):
            self.client.get("/internal/review/v2/canonical-major-groups")
        self.assertFalse(self.review_path.exists())

    def test_filter_query_alone_never_patches(self) -> None:
        """GET에는 필터 Query Parameter 자체가 없다 — 서버는 42개를 그대로 돌려주고
        필터링은 전부 클라이언트에서 한다(§3 "GET·필터로 파일 생성 금지"). 그래도
        아무 파라미터가 붙어도 PATCH가 되지 않는지(=GET Method 자체가 저장을
        일으키지 않는지) 직접 확인한다."""

        for _ in range(3):
            self.client.get("/internal/review/v2/canonical-major-groups", params={"decision": "APPROVE_AS_CLASSIFICATION_GROUP"})
        self.assertFalse(self.review_path.exists())

    def test_one_save_changes_exactly_one_row(self) -> None:
        rows = self.client.get("/internal/review/v2/canonical-major-groups").json()["rows"]
        target_id = rows[5]["canonical_major_group_id"]
        self.client.patch(
            f"/internal/review/v2/canonical-major-groups/{target_id}",
            json={"decision": "SPLIT_GROUP", "expected_revision": 0},
        )
        rows2 = self.client.get("/internal/review/v2/canonical-major-groups").json()["rows"]
        changed = [r for r in rows2 if r["review"]["decision"] != "TBD"]
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0]["canonical_major_group_id"], target_id)

    def test_other_review_endpoints_still_200(self) -> None:
        for path in (
            "/internal/review/v2/questions",
            "/internal/review/v2/summary",
            "/internal/review/v2/canonical-major-group-bridge",
            "/internal/review/v2/academyinfo/p1-classification",
            "/internal/review/v2/academyinfo/nce-reexaminable",
        ):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200, path)


class NotWiredIntoRuntimeOrDryRunTest(unittest.TestCase):
    """§ "이번 작업에서는 Dry Run Gate에 연결하지 않는다" / A가 소유하지 않는
    파일 수정 금지 — 학생 공개 API·전국 Dry Run·Department 승격 경로 어디에도
    이 신규 모듈에 대한 참조가 없어야 한다."""

    def test_public_api_module_does_not_import_new_review_module(self) -> None:
        main_src = (_REPO_ROOT / "src" / "api" / "main.py").read_text(encoding="utf-8")
        self.assertNotIn("canonical_major_group_review_service", main_src)
        self.assertNotIn("canonical_major_group_review_store", main_src)

    def test_service_never_calls_department_repository_or_promotion(self) -> None:
        service_src = (_REPO_ROOT / "src" / "review_ui" / "canonical_major_group_review_service.py").read_text(encoding="utf-8")
        for forbidden in ("JsonlDepartmentRepository", "department_repository", "MajorExplorationService", "departments.jsonl", "promote"):
            self.assertNotIn(forbidden, service_src)

    def test_review_app_is_not_the_public_app(self) -> None:
        from src.api.main import app as public_app

        self.assertIsNot(app, public_app)
        public_paths = {getattr(route, "path", "") for route in public_app.routes}
        self.assertNotIn("/internal/review/v2/canonical-major-groups", public_paths)

    def test_review_store_never_imports_other_review_stores(self) -> None:
        """다른 검수 축(Bridge/Scope/P1/N.C.E)의 검수 상태 파일을 실수로 같이
        쓰는 경로 자체가 없다는 사실을 import 목록으로 확인한다."""

        store_src = (_REPO_ROOT / "src" / "services" / "canonical_major_group_review_store.py").read_text(encoding="utf-8")
        for forbidden in (
            "canonical_major_group_bridge_review_store", "canonical_major_group_bridge_scope_review_store",
            "academyinfo_p1_classification_review_store", "academyinfo_nce_middle_series_review_store",
        ):
            self.assertNotIn(forbidden, store_src)


if __name__ == "__main__":
    unittest.main()
