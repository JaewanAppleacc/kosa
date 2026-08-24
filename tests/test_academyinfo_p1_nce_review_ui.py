"""대학알리미 P1 분류 REVIEW(374건)·N.C.E 중계열(24개 클러스터·584건) 검수 탭
테스트 — 2026-08-24 지시서(a/academyinfo-review-ui-p1-nce).

Bridge Mapping/Scope 검수와 같은 2계층 전략(정적 소스 검증 + 실제 서비스/API
호출)을 따른다. 모든 저장 테스트는 `tempfile.TemporaryDirectory()`만 쓰고
실제 data/reviews/·data/academyinfo_work/ 파일은 절대 건드리지 않는다 — 매
테스트가 실제 파일들의 SHA-256을 스냅샷하고 종료 시 재확인한다."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.review_ui import academyinfo_nce_middle_series_review_service as nces
from src.review_ui import academyinfo_p1_classification_review_service as p1s
from src.review_ui import canonical_major_group_bridge_review_service as cmgbrs
from src.review_ui.app import app
from src.schemas.academyinfo_nce_middle_series_cluster_review import AcademyInfoNceMiddleSeriesReview
from src.schemas.academyinfo_p1_classification_candidate_review import AcademyInfoP1ClassificationReview
from src.services.academyinfo_nce_middle_series_cluster_loader import (
    DEFAULT_NCE_CLUSTER_PATH,
    load_nce_middle_series_clusters,
)
from src.services.academyinfo_nce_middle_series_review_store import (
    DuplicateNceReviewKeyError,
    load_nce_review_entries_by_key,
    save_nce_review_entries,
)
from src.services.academyinfo_p1_classification_loader import (
    DEFAULT_P1_PACKET_PATH,
    load_p1_classification_packet,
)
from src.services.academyinfo_p1_classification_review_store import (
    DuplicateP1ReviewKeyError,
    load_p1_review_entries_by_key,
    save_p1_review_entries,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_STATIC_DIR = _REPO_ROOT / "src" / "review_ui" / "static"
_HTML = (_STATIC_DIR / "index.html").read_text(encoding="utf-8")
_JS = (_STATIC_DIR / "review.js").read_text(encoding="utf-8")

_NCE_TRIAGE_QUEUE_PATH = _REPO_ROOT / "data" / "academyinfo_work" / "2025" / "packets" / "nce_triage_queue.jsonl"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _js_function_body(name: str) -> str:
    start = _JS.index(f"function {name}(")
    rest = _JS[start:]
    m = re.search(r"\n(async function |function )", rest[1:])
    return rest[: m.start() + 1] if m else rest


class StaticSourceTest(unittest.TestCase):
    def test_tab_buttons_and_containers_exist(self) -> None:
        self.assertIn('id="tab-p1-classification-btn"', _HTML)
        self.assertIn('id="p1-container"', _HTML)
        self.assertIn('id="p1-summary-box"', _HTML)
        self.assertIn('id="tab-nce-reexaminable-btn"', _HTML)
        self.assertIn('id="nce-container"', _HTML)
        self.assertIn('id="nce-summary-box"', _HTML)

    def test_p1_filters_present(self) -> None:
        for value in ("all", "CONTENT_MEDIA", "DESIGN_HCI_UX"):
            self.assertIn(f'name="p1-cluster-filter" value="{value}"', _HTML)
        for value in (
            "all", "MEDIA_COMMUNICATION_CANDIDATE", "HCI_UX_CANDIDATE", "DESIGN_ARTS_EXCLUDED",
            "NEEDS_OFFICIAL_CURRICULUM", "UNMAPPED",
        ):
            self.assertIn(f'name="p1-judgment-filter" value="{value}"', _HTML)
        for value in ("all", "sufficient", "insufficient"):
            self.assertIn(f'name="p1-evidence-filter" value="{value}"', _HTML)
        for value in ("all", "POSSIBLE_NEEDS_CHECK", "UNLIKELY"):
            self.assertIn(f'name="p1-arts-sports-filter" value="{value}"', _HTML)
        self.assertIn('name="p1-decision-filter" value="TBD"', _HTML)
        self.assertIn('id="p1-filter-unreviewed"', _HTML)

    def test_nce_filters_present(self) -> None:
        for value in ("all", "single", "multiple"):
            self.assertIn(f'name="nce-candidate-count-filter" value="{value}"', _HTML)
        self.assertIn('id="nce-filter-middle-series"', _HTML)
        self.assertIn('name="nce-decision-filter" value="TBD"', _HTML)
        self.assertIn('id="nce-filter-min-department-count"', _HTML)
        self.assertIn('id="nce-filter-department-review"', _HTML)

    def test_p1_save_only_triggered_by_button_click(self) -> None:
        card_src = _js_function_body("renderP1RowCard")
        self.assertIn('saveBtn.addEventListener("click", async () => {', card_src)
        click_start = card_src.index('saveBtn.addEventListener("click"')
        self.assertIn("apiPatch(", card_src[click_start:])
        self.assertIn("expected_revision", card_src[click_start:])

        for marker in (
            'name="p1-cluster-filter"', 'name="p1-judgment-filter"', 'name="p1-evidence-filter"',
            'name="p1-arts-sports-filter"', 'name="p1-decision-filter"', "p1-filter-unreviewed",
        ):
            idx = _JS.index(marker)
            self.assertNotIn("apiPatch(", _JS[idx : idx + 400])

    def test_nce_save_only_triggered_by_button_click(self) -> None:
        card_src = _js_function_body("renderNceClusterCard")
        self.assertIn('saveBtn.addEventListener("click", async () => {', card_src)
        click_start = card_src.index('saveBtn.addEventListener("click"')
        self.assertIn("apiPatch(", card_src[click_start:])
        self.assertIn("expected_revision", card_src[click_start:])

        for marker in (
            'name="nce-candidate-count-filter"', "nce-filter-middle-series",
            'name="nce-decision-filter"', "nce-filter-min-department-count", "nce-filter-department-review",
        ):
            idx = _JS.index(marker)
            self.assertNotIn("apiPatch(", _JS[idx : idx + 400])

    def test_nce_accept_does_not_promote_departments_disclaimer_shown(self) -> None:
        card_src = _js_function_body("renderNceClusterCard")
        self.assertIn("자동 승인하지 않습니다", card_src)

    def test_no_bulk_approve_all_function_exists(self) -> None:
        """§4 "'모두 승인' 기능 금지" — 그런 이름의 함수/버튼이 아예 없어야 한다."""

        for forbidden in ("approveAll", "모두 승인", "일괄 승인", "bulkApprove"):
            self.assertNotIn(forbidden, _JS)

    def test_hash_deep_link_registered_for_both_tabs(self) -> None:
        self.assertIn('p1_classification: "p1-classification"', _JS)
        self.assertIn('nce_reexaminable: "nce-reexaminable"', _JS)


class _PreservationTestBase(unittest.TestCase):
    """§5 "기존 데이터 보존" — 지시서가 명시한 파일들의 SHA-256을 테스트 전후로
    직접 대조한다."""

    _PROTECTED_PATHS = [
        _REPO_ROOT / "data" / "reviews" / "canonical_major_group_bridge_review_status.json",
        _REPO_ROOT / "data" / "academyinfo_work" / "2025" / "packets" / "p1_classification_review.jsonl",
        _NCE_TRIAGE_QUEUE_PATH,
        _REPO_ROOT / "data" / "academyinfo_work" / "2025" / "packets" / "nce_reexaminable_middle_series_clusters.jsonl",
        _REPO_ROOT / "data" / "master" / "departments.jsonl",
    ]
    _OPTIONAL_SCOPE_REVIEW_PATH = (
        _REPO_ROOT / "data" / "reviews" / "canonical_major_group_bridge_scope_review_status.jsonl"
    )
    _P1_REVIEW_REAL_PATH = _REPO_ROOT / "data" / "reviews" / "academyinfo_p1_classification_review_status.jsonl"
    _NCE_REVIEW_REAL_PATH = _REPO_ROOT / "data" / "reviews" / "academyinfo_nce_middle_series_review_status.jsonl"

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.p1_review_path = Path(self.tmpdir.name) / "academyinfo_p1_classification_review_status.jsonl"
        self.nce_review_path = Path(self.tmpdir.name) / "academyinfo_nce_middle_series_review_status.jsonl"

        self._before = self._snapshot()
        self.addCleanup(self._assert_unchanged)

    def _snapshot(self) -> dict[str, object]:
        snap: dict[str, object] = {str(p): _sha256(p) for p in self._PROTECTED_PATHS}
        snap["__scope_exists__"] = self._OPTIONAL_SCOPE_REVIEW_PATH.exists()
        if self._OPTIONAL_SCOPE_REVIEW_PATH.exists():
            snap["__scope_sha__"] = _sha256(self._OPTIONAL_SCOPE_REVIEW_PATH)
        snap["__p1_review_exists__"] = self._P1_REVIEW_REAL_PATH.exists()
        snap["__nce_review_exists__"] = self._NCE_REVIEW_REAL_PATH.exists()
        return snap

    def _assert_unchanged(self) -> None:
        self.assertEqual(self._before, self._snapshot(), "실제 파일이 테스트 중 바뀌었다 — 절대 금지 위반")


class P1ServiceLayerTest(_PreservationTestBase):
    def _list(self):
        return p1s.build_p1_classification_list(review_status_path=self.p1_review_path)

    def test_374_rows_275_content_media_99_design_hci_ux(self) -> None:
        resp = self._list()
        self.assertEqual(resp.summary.total, 374)
        self.assertEqual(resp.summary.content_media_count, 275)
        self.assertEqual(resp.summary.design_hci_ux_count, 99)
        self.assertEqual(len(resp.rows), 374)

    def test_evidence_sufficient_97_insufficient_277(self) -> None:
        resp = self._list()
        self.assertEqual(resp.summary.evidence_sufficient_count, 97)
        self.assertEqual(resp.summary.evidence_insufficient_count, 277)
        self.assertEqual(resp.summary.evidence_sufficient_count + resp.summary.evidence_insufficient_count, 374)

    def test_judgment_candidate_counts_match_real_manifest(self) -> None:
        resp = self._list()
        expected = {
            "MEDIA_COMMUNICATION_CANDIDATE": 96, "UNMAPPED": 68, "NEEDS_OFFICIAL_CURRICULUM": 207,
            "DESIGN_ARTS_EXCLUDED": 1, "HCI_UX_CANDIDATE": 2,
        }
        self.assertEqual(resp.summary.judgment_candidate_counts, expected)

    def test_no_row_is_pre_approved(self) -> None:
        resp = self._list()
        self.assertEqual({r.review.decision for r in resp.rows}, {"TBD"})
        self.assertEqual(resp.summary.reviewed_count, 0)
        self.assertEqual(resp.summary.unreviewed_count, 374)
        self.assertEqual(resp.summary.decision_counts, {"TBD": 374})

    def test_get_style_load_never_writes_review_file(self) -> None:
        self._list()
        self._list()
        self.assertFalse(self.p1_review_path.exists())

    def test_approve_eligible_excludes_group_id_and_insufficient_evidence(self) -> None:
        """DESIGN_ARTS_EXCLUDED 행(candidate_canonical_major_ids=['fine_arts_design'],
        evidence_sufficient=True)은 fine_arts_design이 42개 Group ID이지 10개
        서비스 Major ID가 아니므로 승인 불가여야 한다. HCI_UX_CANDIDATE
        (evidence_sufficient=False)도 승인 불가."""

        resp = self._list()
        design_row = next(r for r in resp.rows if r.judgment_candidate == "DESIGN_ARTS_EXCLUDED")
        self.assertFalse(design_row.approve_eligible)
        for r in resp.rows:
            if r.judgment_candidate == "HCI_UX_CANDIDATE":
                self.assertFalse(r.approve_eligible)
        eligible_count = sum(1 for r in resp.rows if r.approve_eligible)
        self.assertEqual(eligible_count, 96, "MEDIA_COMMUNICATION_CANDIDATE 96건만 승인 가능해야 한다")

    def test_approve_on_ineligible_row_is_fail_closed(self) -> None:
        resp = self._list()
        ineligible = next(r for r in resp.rows if not r.approve_eligible)
        with self.assertRaises(p1s.P1ApproveNotEligibleError):
            p1s.update_p1_classification_review(
                ineligible.candidate_id, decision="APPROVE_PROPOSED_CANDIDATE", comment=None, resolution_note=None,
                expected_revision=0, review_status_path=self.p1_review_path,
            )
        self.assertFalse(self.p1_review_path.exists())

    def test_approve_on_eligible_row_succeeds(self) -> None:
        resp = self._list()
        eligible = next(r for r in resp.rows if r.approve_eligible)
        out = p1s.update_p1_classification_review(
            eligible.candidate_id, decision="APPROVE_PROPOSED_CANDIDATE", comment="근거 확인",
            resolution_note=None, expected_revision=0, review_status_path=self.p1_review_path,
        )
        self.assertTrue(out.ok)
        self.assertEqual(out.decision, "APPROVE_PROPOSED_CANDIDATE")
        self.assertEqual(out.new_revision, 1)

    def test_save_touches_only_target_row(self) -> None:
        resp = self._list()
        target = resp.rows[10]
        p1s.update_p1_classification_review(
            target.candidate_id, decision="HOLD", comment="검토 보류", resolution_note=None,
            expected_revision=0, review_status_path=self.p1_review_path,
        )
        resp2 = self._list()
        row = next(r for r in resp2.rows if r.candidate_id == target.candidate_id)
        self.assertEqual(row.review.decision, "HOLD")
        others = [r for r in resp2.rows if r.candidate_id != target.candidate_id]
        self.assertTrue(all(r.review.decision == "TBD" for r in others))

    def test_partial_save_none_means_unchanged(self) -> None:
        resp = self._list()
        target = resp.rows[0]
        p1s.update_p1_classification_review(
            target.candidate_id, decision="HOLD", comment="1차", resolution_note=None,
            expected_revision=0, review_status_path=self.p1_review_path,
        )
        p1s.update_p1_classification_review(
            target.candidate_id, decision=None, comment="수정", resolution_note=None,
            expected_revision=1, review_status_path=self.p1_review_path,
        )
        row = next(r for r in self._list().rows if r.candidate_id == target.candidate_id)
        self.assertEqual(row.review.decision, "HOLD")
        self.assertEqual(row.review.reviewer_comment, "수정")

    def test_stale_revision_rejected(self) -> None:
        resp = self._list()
        target = resp.rows[0]
        p1s.update_p1_classification_review(
            target.candidate_id, decision="HOLD", comment=None, resolution_note=None,
            expected_revision=0, review_status_path=self.p1_review_path,
        )
        with self.assertRaises(p1s.P1StaleRevisionError):
            p1s.update_p1_classification_review(
                target.candidate_id, decision="KEEP_UNMAPPED", comment=None, resolution_note=None,
                expected_revision=0, review_status_path=self.p1_review_path,
            )

    def test_unknown_candidate_rejected(self) -> None:
        with self.assertRaises(p1s.UnknownP1CandidateError):
            p1s.update_p1_classification_review(
                "does_not_exist", decision="HOLD", comment=None, resolution_note=None,
                expected_revision=0, review_status_path=self.p1_review_path,
            )
        self.assertFalse(self.p1_review_path.exists())

    def test_duplicate_key_rejected_on_save(self) -> None:
        dup = [
            AcademyInfoP1ClassificationReview(candidate_id="dup1"),
            AcademyInfoP1ClassificationReview(candidate_id="dup1"),
        ]
        with self.assertRaises(DuplicateP1ReviewKeyError):
            save_p1_review_entries(dup, self.p1_review_path)
        self.assertFalse(self.p1_review_path.exists())

    def test_duplicate_key_rejected_on_manual_load(self) -> None:
        self.p1_review_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps({"candidate_id": "dup1"}), json.dumps({"candidate_id": "dup1"})]
        self.p1_review_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with self.assertRaises(DuplicateP1ReviewKeyError):
            load_p1_review_entries_by_key(self.p1_review_path)

    def test_packet_loader_reusable_standalone(self) -> None:
        entries = load_p1_classification_packet()
        self.assertEqual(len(entries), 374)


class NceServiceLayerTest(_PreservationTestBase):
    def _list(self):
        return nces.build_nce_middle_series_list(review_status_path=self.nce_review_path)

    def test_24_clusters_584_departments(self) -> None:
        resp = self._list()
        self.assertEqual(resp.summary.cluster_total, 24)
        self.assertEqual(resp.summary.department_total, 584)
        self.assertEqual(len(resp.clusters), 24)

    def test_proposed_15_208_department_required_9_376(self) -> None:
        resp = self._list()
        self.assertEqual(resp.summary.proposed_group_candidate_cluster_count, 15)
        self.assertEqual(resp.summary.proposed_group_candidate_department_count, 208)
        self.assertEqual(resp.summary.department_level_review_required_cluster_count, 9)
        self.assertEqual(resp.summary.department_level_review_required_department_count, 376)

    def test_no_cluster_is_pre_approved(self) -> None:
        resp = self._list()
        self.assertEqual({c.review.decision for c in resp.clusters}, {"TBD"})
        self.assertEqual(resp.summary.reviewed_count, 0)
        self.assertEqual(resp.summary.unreviewed_count, 24)

    def test_get_style_load_never_writes_review_file(self) -> None:
        self._list()
        self._list()
        self.assertFalse(self.nce_review_path.exists())

    def test_all_members_and_sample_members_consistent(self) -> None:
        resp = self._list()
        for c in resp.clusters:
            self.assertEqual(len(c.all_members), c.row_count)
            self.assertLessEqual(len(c.sample_members), 5)
            self.assertLessEqual(len(c.sample_members), len(c.all_members))

    def test_is_single_candidate_flag_correct(self) -> None:
        resp = self._list()
        for c in resp.clusters:
            self.assertEqual(c.is_single_candidate, len(c.candidate_canonical_major_groups) == 1)

    def test_save_touches_only_target_cluster(self) -> None:
        resp = self._list()
        target = resp.clusters[0]
        nces.update_nce_middle_series_review(
            target.official_middle_series_code, decision="ACCEPT_GROUP_AS_REVIEW_CANDIDATE", comment="검토 후보로 인정",
            resolution_note=None, expected_revision=0, review_status_path=self.nce_review_path,
        )
        resp2 = self._list()
        row = next(c for c in resp2.clusters if c.official_middle_series_code == target.official_middle_series_code)
        self.assertEqual(row.review.decision, "ACCEPT_GROUP_AS_REVIEW_CANDIDATE")
        others = [c for c in resp2.clusters if c.official_middle_series_code != target.official_middle_series_code]
        self.assertTrue(all(c.review.decision == "TBD" for c in others))

    def test_accept_as_review_candidate_does_not_change_row_count_or_members(self) -> None:
        """§2 "ACCEPT_GROUP_AS_REVIEW_CANDIDATE는 584개 학과 자동 승인이 아님" —
        저장 전후로 그 클러스터의 row_count·학과 목록이 정확히 그대로여야 한다
        (이 저장이 어떤 학과 데이터도 건드리지 않는다는 직접 증거)."""

        resp = self._list()
        target = resp.clusters[0]
        before_members = [m.candidate_id for m in target.all_members]
        before_count = target.row_count
        nces.update_nce_middle_series_review(
            target.official_middle_series_code, decision="ACCEPT_GROUP_AS_REVIEW_CANDIDATE", comment=None,
            resolution_note=None, expected_revision=0, review_status_path=self.nce_review_path,
        )
        resp2 = self._list()
        row = next(c for c in resp2.clusters if c.official_middle_series_code == target.official_middle_series_code)
        self.assertEqual(row.row_count, before_count)
        self.assertEqual([m.candidate_id for m in row.all_members], before_members)

    def test_stale_revision_rejected(self) -> None:
        resp = self._list()
        target = resp.clusters[0]
        nces.update_nce_middle_series_review(
            target.official_middle_series_code, decision="HOLD", comment=None, resolution_note=None,
            expected_revision=0, review_status_path=self.nce_review_path,
        )
        with self.assertRaises(nces.NceStaleRevisionError):
            nces.update_nce_middle_series_review(
                target.official_middle_series_code, decision="REQUIRE_DEPARTMENT_LEVEL_REVIEW", comment=None,
                resolution_note=None, expected_revision=0, review_status_path=self.nce_review_path,
            )

    def test_unknown_code_rejected(self) -> None:
        with self.assertRaises(nces.UnknownNceMiddleSeriesCodeError):
            nces.update_nce_middle_series_review(
                "does_not_exist", decision="HOLD", comment=None, resolution_note=None,
                expected_revision=0, review_status_path=self.nce_review_path,
            )
        self.assertFalse(self.nce_review_path.exists())

    def test_duplicate_key_rejected_on_save(self) -> None:
        dup = [
            AcademyInfoNceMiddleSeriesReview(official_middle_series_code="99"),
            AcademyInfoNceMiddleSeriesReview(official_middle_series_code="99"),
        ]
        with self.assertRaises(DuplicateNceReviewKeyError):
            save_nce_review_entries(dup, self.nce_review_path)
        self.assertFalse(self.nce_review_path.exists())

    def test_duplicate_key_rejected_on_manual_load(self) -> None:
        self.nce_review_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            json.dumps({"official_middle_series_code": "99"}),
            json.dumps({"official_middle_series_code": "99"}),
        ]
        self.nce_review_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with self.assertRaises(DuplicateNceReviewKeyError):
            load_nce_review_entries_by_key(self.nce_review_path)

    def test_row_count_mismatch_detected_by_loader(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad_path = Path(tmp) / "bad_nce.jsonl"
            row = {
                "cluster_id": "x", "official_middle_series_code": "99", "official_middle_series_name": "테스트",
                "official_middle_series_code_source": "test", "group_linkage_status": "PROPOSED_GROUP_CANDIDATE",
                "candidate_canonical_major_groups": [{"canonical_major_id": "psychology", "label": "심리학"}],
                "candidate_canonical_major_group_basis": "test",
                "members": [], "row_count": 3,
            }
            bad_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            from src.services.academyinfo_nce_middle_series_cluster_loader import NceClusterValidationError

            with self.assertRaises(NceClusterValidationError):
                load_nce_middle_series_clusters(bad_path)


class StoreIndependenceTest(_PreservationTestBase):
    """§4 "Mapping·Scope·P1·N.C.E Store를 물리적으로 분리" — 한 Store를 갱신해도
    다른 세 Store가 전혀 건드려지지 않는지 직접 증명한다."""

    def setUp(self) -> None:
        super().setUp()
        self.bridge_review_path = Path(self.tmpdir.name) / "bridge_mapping.json"
        self.bridge_scope_path = Path(self.tmpdir.name) / "bridge_scope.jsonl"

    def test_p1_save_does_not_touch_nce_or_bridge_paths(self) -> None:
        resp = p1s.build_p1_classification_list(review_status_path=self.p1_review_path)
        p1s.update_p1_classification_review(
            resp.rows[0].candidate_id, decision="HOLD", comment=None, resolution_note=None,
            expected_revision=0, review_status_path=self.p1_review_path,
        )
        self.assertTrue(self.p1_review_path.exists())
        self.assertFalse(self.nce_review_path.exists())
        self.assertFalse(self.bridge_review_path.exists())
        self.assertFalse(self.bridge_scope_path.exists())

    def test_nce_save_does_not_touch_p1_or_bridge_paths(self) -> None:
        resp = nces.build_nce_middle_series_list(review_status_path=self.nce_review_path)
        nces.update_nce_middle_series_review(
            resp.clusters[0].official_middle_series_code, decision="HOLD", comment=None, resolution_note=None,
            expected_revision=0, review_status_path=self.nce_review_path,
        )
        self.assertTrue(self.nce_review_path.exists())
        self.assertFalse(self.p1_review_path.exists())
        self.assertFalse(self.bridge_review_path.exists())
        self.assertFalse(self.bridge_scope_path.exists())

    def test_bridge_save_does_not_touch_p1_or_nce_paths(self) -> None:
        resp = cmgbrs.build_bridge_review_list(
            review_status_path=self.bridge_review_path, scope_review_status_path=self.bridge_scope_path,
        )
        cmgbrs.update_bridge_review(
            resp.rows[0].review_key, status="APPROVE", comment=None, resolution_note=None,
            review_status_path=self.bridge_review_path,
        )
        self.assertTrue(self.bridge_review_path.exists())
        self.assertFalse(self.bridge_scope_path.exists())
        self.assertFalse(self.p1_review_path.exists())
        self.assertFalse(self.nce_review_path.exists())

    def test_module_source_never_imports_the_other_domains_store(self) -> None:
        p1_src = (_REPO_ROOT / "src" / "services" / "academyinfo_p1_classification_review_store.py").read_text(
            encoding="utf-8"
        )
        nce_src = (_REPO_ROOT / "src" / "services" / "academyinfo_nce_middle_series_review_store.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("nce_middle_series_review_store", p1_src)
        self.assertNotIn("canonical_major_group_bridge", p1_src)
        self.assertNotIn("p1_classification_review_store", nce_src)
        self.assertNotIn("canonical_major_group_bridge", nce_src)


class ApiLayerTest(_PreservationTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.client = TestClient(app)
        p1_patcher = patch(
            "src.review_ui.academyinfo_p1_classification_review_service.P1_REVIEW_STATUS_PATH", self.p1_review_path,
        )
        nce_patcher = patch(
            "src.review_ui.academyinfo_nce_middle_series_review_service.NCE_REVIEW_STATUS_PATH", self.nce_review_path,
        )
        p1_patcher.start()
        nce_patcher.start()
        self.addCleanup(p1_patcher.stop)
        self.addCleanup(nce_patcher.stop)

    def test_p1_get_returns_374(self) -> None:
        r = self.client.get("/internal/review/v2/academyinfo/p1-classification")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["summary"]["total"], 374)
        self.assertEqual(len(body["rows"]), 374)

    def test_p1_patch_saves_and_requires_expected_revision(self) -> None:
        rows = self.client.get("/internal/review/v2/academyinfo/p1-classification").json()["rows"]
        candidate_id = next(r["candidate_id"] for r in rows if r["approve_eligible"])
        r = self.client.patch(
            f"/internal/review/v2/academyinfo/p1-classification/{candidate_id}",
            json={"decision": "APPROVE_PROPOSED_CANDIDATE", "comment": "확인", "expected_revision": 0},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["new_revision"], 1)

        # 낡은 revision으로 다시 저장 시도 -> 409.
        r2 = self.client.patch(
            f"/internal/review/v2/academyinfo/p1-classification/{candidate_id}",
            json={"decision": "HOLD", "expected_revision": 0},
        )
        self.assertEqual(r2.status_code, 409)

    def test_p1_patch_ineligible_approve_returns_422(self) -> None:
        rows = self.client.get("/internal/review/v2/academyinfo/p1-classification").json()["rows"]
        candidate_id = next(r["candidate_id"] for r in rows if not r["approve_eligible"])
        r = self.client.patch(
            f"/internal/review/v2/academyinfo/p1-classification/{candidate_id}",
            json={"decision": "APPROVE_PROPOSED_CANDIDATE", "expected_revision": 0},
        )
        self.assertEqual(r.status_code, 422)
        self.assertFalse(self.p1_review_path.exists())

    def test_p1_patch_unknown_candidate_returns_422(self) -> None:
        r = self.client.patch(
            "/internal/review/v2/academyinfo/p1-classification/does_not_exist",
            json={"decision": "HOLD", "expected_revision": 0},
        )
        self.assertEqual(r.status_code, 422)

    def test_p1_get_alone_never_creates_file(self) -> None:
        for _ in range(3):
            self.client.get("/internal/review/v2/academyinfo/p1-classification")
        self.assertFalse(self.p1_review_path.exists())

    def test_nce_get_returns_24_584(self) -> None:
        r = self.client.get("/internal/review/v2/academyinfo/nce-reexaminable")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["summary"]["cluster_total"], 24)
        self.assertEqual(body["summary"]["department_total"], 584)

    def test_nce_patch_saves_and_requires_expected_revision(self) -> None:
        clusters = self.client.get("/internal/review/v2/academyinfo/nce-reexaminable").json()["clusters"]
        code = clusters[0]["official_middle_series_code"]
        r = self.client.patch(
            f"/internal/review/v2/academyinfo/nce-reexaminable/{code}",
            json={"decision": "ACCEPT_GROUP_AS_REVIEW_CANDIDATE", "expected_revision": 0},
        )
        self.assertEqual(r.status_code, 200)
        r2 = self.client.patch(
            f"/internal/review/v2/academyinfo/nce-reexaminable/{code}",
            json={"decision": "HOLD", "expected_revision": 0},
        )
        self.assertEqual(r2.status_code, 409)

    def test_nce_patch_unknown_code_returns_422(self) -> None:
        r = self.client.patch(
            "/internal/review/v2/academyinfo/nce-reexaminable/does_not_exist",
            json={"decision": "HOLD", "expected_revision": 0},
        )
        self.assertEqual(r.status_code, 422)

    def test_nce_get_alone_never_creates_file(self) -> None:
        for _ in range(3):
            self.client.get("/internal/review/v2/academyinfo/nce-reexaminable")
        self.assertFalse(self.nce_review_path.exists())

    def test_other_endpoints_unaffected(self) -> None:
        r = self.client.get("/internal/review/v2/canonical-major-group-bridge")
        self.assertEqual(r.status_code, 200)
        r2 = self.client.get("/internal/review/v2/questions")
        self.assertEqual(r2.status_code, 200)


class NotWiredIntoRuntimeOrPromotionTest(unittest.TestCase):
    """§ 안전 규칙 — 학생 공개 API에 이 신규 모듈에 대한 어떤 참조도 없어야 하고,
    N.C.E ACCEPT_GROUP_AS_REVIEW_CANDIDATE가 Department 승격 로직을 호출하는
    코드가 어디에도 없어야 한다."""

    def test_public_api_module_does_not_import_new_review_modules(self) -> None:
        main_src = (_REPO_ROOT / "src" / "api" / "main.py").read_text(encoding="utf-8")
        self.assertNotIn("academyinfo_p1_classification_review", main_src)
        self.assertNotIn("academyinfo_nce_middle_series_review", main_src)

    def test_nce_service_never_calls_department_repository_or_promotion(self) -> None:
        nce_service_src = (
            _REPO_ROOT / "src" / "review_ui" / "academyinfo_nce_middle_series_review_service.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "JsonlDepartmentRepository", "department_repository", "MajorExplorationService",
            "departments.jsonl", "promote",
        ):
            self.assertNotIn(forbidden, nce_service_src)

    def test_review_app_is_not_the_public_app(self) -> None:
        from src.api.main import app as public_app

        self.assertIsNot(app, public_app)
        public_paths = {getattr(route, "path", "") for route in public_app.routes}
        self.assertNotIn("/internal/review/v2/academyinfo/p1-classification", public_paths)
        self.assertNotIn("/internal/review/v2/academyinfo/nce-reexaminable", public_paths)


if __name__ == "__main__":
    unittest.main()
