"""분류 REVIEW P1(추천 노출 직접 영향) 검수 패킷 테스트 — 2026-08-24 지시서
(c/academyinfo-classification-p1-review).

핵심은 하나다 — **Claude가 자동 승인하지 않았음을 기계적으로 증명한다.** 입력
(`classification_review_queue.jsonl`)은 항상 커밋돼 있으므로(`.gitignore`
whitelist), 이 파일의 검증은 전국 원본 데이터 없이도 clean clone에서 전부
돈다 — `has_inputs()` Skip 게이트가 필요 없다."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "data" / "academyinfo_work" / "2025"
PACKETS = WORK / "packets"
QUEUE_PATH = WORK / "classification_review_queue.jsonl"

JSONL_PATH = PACKETS / "p1_classification_review.jsonl"
HTML_PATH = PACKETS / "p1_classification_review_packet.html"
MANIFEST_PATH = PACKETS / "p1_classification_review_manifest.json"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


import sys as _sys  # noqa: E402
_sys.path.insert(0, str(ROOT))
from scripts.career_build_academyinfo_p1_classification_review import (  # noqa: E402
    DESIGN_ARTS_EXCLUDED,
    HCI_UX_CANDIDATE,
    MEDIA_COMMUNICATION_CANDIDATE,
    NEEDS_OFFICIAL_CURRICULUM,
    PERFORMING_MEDIA_ARTS_EXCLUDED,
    UNMAPPED,
    build_p1_rows,
)
from scripts.career_build_academyinfo_review_packets import cluster_of  # noqa: E402

SOURCE_QUEUE = read_jsonl(QUEUE_PATH)
SOURCE_P1_IDS = {
    r["source_record_id"] for r in SOURCE_QUEUE if cluster_of(r)[0] in ("CONTENT_MEDIA", "DESIGN_HCI_UX")
}
ROWS = read_jsonl(JSONL_PATH)
MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

ALL_JUDGMENT_CANDIDATES = {
    MEDIA_COMMUNICATION_CANDIDATE, HCI_UX_CANDIDATE, DESIGN_ARTS_EXCLUDED,
    PERFORMING_MEDIA_ARTS_EXCLUDED, NEEDS_OFFICIAL_CURRICULUM, UNMAPPED,
}
# 공식 후보 전공군(candidate_canonical_major_ids) 하나만으로 확정적으로 매길 수 있는 버킷.
OFFICIALLY_GROUNDED_CANDIDATES = {
    MEDIA_COMMUNICATION_CANDIDATE, DESIGN_ARTS_EXCLUDED, PERFORMING_MEDIA_ARTS_EXCLUDED,
}


class CommittedInputAlwaysCheckedTest(unittest.TestCase):
    """입력·산출물이 커밋돼 있고 clean clone에서 항상 검증 가능한지."""

    def test_source_queue_committed(self) -> None:
        self.assertTrue(QUEUE_PATH.exists())
        self.assertEqual(len(SOURCE_QUEUE), 1936)

    def test_packet_outputs_committed(self) -> None:
        for p in (JSONL_PATH, HTML_PATH, MANIFEST_PATH):
            self.assertTrue(p.exists(), f"{p.name}이 커밋돼 있지 않다")


class ExactCountTest(unittest.TestCase):
    def test_exactly_374_rows(self) -> None:
        self.assertEqual(len(ROWS), 374)

    def test_content_media_275_design_hci_ux_99(self) -> None:
        from collections import Counter

        counts = Counter(r["p1_cluster"] for r in ROWS)
        self.assertEqual(counts["CONTENT_MEDIA"], 275)
        self.assertEqual(counts["DESIGN_HCI_UX"], 99)
        self.assertEqual(counts["CONTENT_MEDIA"] + counts["DESIGN_HCI_UX"], 374)

    def test_manifest_counts_match(self) -> None:
        self.assertEqual(MANIFEST["p1_total"], 374)
        self.assertEqual(MANIFEST["source_queue_total"], 1936)
        self.assertEqual(MANIFEST["p1_cluster_breakdown"]["CONTENT_MEDIA"], 275)
        self.assertEqual(MANIFEST["p1_cluster_breakdown"]["DESIGN_HCI_UX"], 99)


class IdMappingTest(unittest.TestCase):
    """원본 Queue와 1:1 대응 + 중복 없음."""

    def test_source_record_ids_are_unique(self) -> None:
        ids = [r["source_record_id"] for r in ROWS]
        self.assertEqual(len(ids), len(set(ids)), "source_record_id 중복이 있다")

    def test_department_ids_are_unique(self) -> None:
        ids = [r["department_id"] for r in ROWS]
        self.assertEqual(len(ids), len(set(ids)), "department_id 중복이 있다")

    def test_candidate_ids_are_unique(self) -> None:
        ids = [r["candidate_id"] for r in ROWS]
        self.assertEqual(len(ids), len(set(ids)), "candidate_id 중복이 있다")

    def test_row_set_exactly_matches_source_p1_selection(self) -> None:
        """P1 패킷의 source_record_id 집합이 원본 Queue를 cluster_of()로 직접 걸러낸
        결과와 정확히 같다 — 1:1 대응."""

        packet_ids = {r["source_record_id"] for r in ROWS}
        self.assertEqual(packet_ids, SOURCE_P1_IDS)

    def test_every_row_traces_back_to_a_real_source_row_with_matching_official_fields(self) -> None:
        by_source_id = {r["source_record_id"]: r for r in SOURCE_QUEUE}
        for row in ROWS:
            source = by_source_id[row["source_record_id"]]
            self.assertEqual(row["department_id"], source["department_id"])
            self.assertEqual(row["university_name"], source["university_name"])
            self.assertEqual(row["department_name"], source["department_name"])
            self.assertEqual(row["college_name"], source["college_name"])
            self.assertEqual(row["official_large_series_name"], source["official_large_series_name"])
            self.assertEqual(row["official_middle_series_name"], source["official_middle_series_name"])
            self.assertEqual(row["official_small_series_name"], source["official_small_series_name"])
            self.assertEqual(row["candidate_canonical_major_ids"], source["candidate_canonical_major_ids"])
            self.assertEqual(row["arts_sports_possibility"], source["arts_sports_possibility"])


class RequiredFieldsTest(unittest.TestCase):
    """§2 — 각 행에 요구된 필드가 전부 있는지."""

    _REQUIRED = (
        "source_record_id", "department_id", "university_name", "department_name", "college_name",
        "official_large_series_name", "official_middle_series_name", "official_small_series_name",
        "candidate_canonical_major_ids", "arts_sports_possibility", "official_curriculum_summary",
        "official_evidence_needed", "reviewer_1_status", "resolution_status", "reviewer_comment",
    )

    def test_every_row_has_required_fields(self) -> None:
        for row in ROWS:
            for field in self._REQUIRED:
                self.assertIn(field, row, f"{row['source_record_id']}에 {field}가 없다")


class NoAutoApprovalTest(unittest.TestCase):
    """§ 안전 규칙 — 자동 승인 금지."""

    def test_every_row_is_tbd_and_pending(self) -> None:
        for row in ROWS:
            self.assertEqual(row["reviewer_1_status"], "TBD", row["source_record_id"])
            self.assertEqual(row["resolution_status"], "PENDING", row["source_record_id"])
            self.assertIsNone(row["reviewer_comment"], row["source_record_id"])

    def test_manifest_declares_zero_auto_approved(self) -> None:
        self.assertEqual(MANIFEST["auto_approved_rows"], 0)

    def test_no_approval_string_in_reviewer_status(self) -> None:
        forbidden_status = {"APPROVE", "APPROVED", "CONFIRMED", "EVIDENCED"}
        forbidden_resolution = {"RESOLVED", "APPROVED", "CONFIRMED"}
        for row in ROWS:
            self.assertNotIn(row["reviewer_1_status"], forbidden_status)
            self.assertNotIn(row["resolution_status"], forbidden_resolution)

    def test_no_approval_string_anywhere_in_jsonl_blob(self) -> None:
        blob = JSONL_PATH.read_text(encoding="utf-8")
        for token in ('"reviewer_1_status": "APPROVE"', '"reviewer_1_status": "APPROVED"',
                      '"resolution_status": "RESOLVED"', '"resolution_status": "APPROVED"'):
            self.assertNotIn(token, blob)

    def test_judgment_candidate_is_never_written_into_committed_master(self) -> None:
        # 이 패킷이 35건 시연 Master나 canonical_majors.jsonl 어디에도 반영되지 않았다.
        master_text = (ROOT / "data" / "master" / "departments.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("judgment_candidate", master_text)
        majors_text = (ROOT / "data" / "master" / "canonical_majors.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("judgment_candidate", majors_text)


class JudgmentCandidateTest(unittest.TestCase):
    def test_only_6_known_values_used(self) -> None:
        used = {r["judgment_candidate"] for r in ROWS}
        self.assertTrue(used.issubset(ALL_JUDGMENT_CANDIDATES), used - ALL_JUDGMENT_CANDIDATES)

    def test_every_row_has_a_reason_citing_official_fields(self) -> None:
        for row in ROWS:
            self.assertTrue(row["judgment_candidate_reason"].strip(), row["source_record_id"])

    def test_design_arts_excluded_rows_have_fine_arts_design_official_candidate(self) -> None:
        for row in ROWS:
            if row["judgment_candidate"] == DESIGN_ARTS_EXCLUDED:
                self.assertIn("fine_arts_design", row["candidate_canonical_major_ids"])

    def test_performing_media_arts_excluded_rows_have_matching_official_candidate(self) -> None:
        arts_groups = {"music", "performing_media_arts", "sports_dance"}
        for row in ROWS:
            if row["judgment_candidate"] == PERFORMING_MEDIA_ARTS_EXCLUDED:
                self.assertTrue(set(row["candidate_canonical_major_ids"]) & arts_groups)

    def test_media_communication_candidate_rows_have_matching_official_candidate(self) -> None:
        for row in ROWS:
            if row["judgment_candidate"] == MEDIA_COMMUNICATION_CANDIDATE:
                self.assertIn("media_communication", row["candidate_canonical_major_ids"])

    def test_no_row_is_confirmed_by_department_name_text_alone(self) -> None:
        """DESIGN_ARTS_EXCLUDED/PERFORMING_MEDIA_ARTS_EXCLUDED/MEDIA_COMMUNICATION_CANDIDATE
        (공식 근거로 확정된 3개 버킷)는 전부 candidate_canonical_major_ids(공식 소계열
        코드로 이미 계산된 값)에 근거해야 한다 — 학과명 문자열이 그 자체로 판단 근거가
        아니다."""

        for row in ROWS:
            if row["judgment_candidate"] in OFFICIALLY_GROUNDED_CANDIDATES:
                self.assertTrue(row["judgment_evidence_sufficient"])
                self.assertTrue(row["candidate_canonical_major_ids"], row["source_record_id"])

    def test_never_labels_arts_group_as_media_or_hci_ux_candidate(self) -> None:
        """예체능을 HCI·UX나 미디어 전공으로 자동 연결하지 않음."""

        arts_groups = {"fine_arts_design", "music", "performing_media_arts", "sports_dance"}
        for row in ROWS:
            if set(row["candidate_canonical_major_ids"]) & arts_groups:
                self.assertNotIn(
                    row["judgment_candidate"], (MEDIA_COMMUNICATION_CANDIDATE, HCI_UX_CANDIDATE),
                    row["source_record_id"],
                )


class FailClosedOfficialEvidenceTest(unittest.TestCase):
    """§4 — 공식 교육목표·교육과정 근거가 없는 행은 추측하지 말고
    NEEDS_OFFICIAL_CURRICULUM으로 유지한다(Fail-Closed)."""

    def test_curriculum_summary_is_never_fabricated(self) -> None:
        for row in ROWS:
            self.assertIsNone(row["official_curriculum_summary"], row["source_record_id"])
            self.assertFalse(row["official_curriculum_available"], row["source_record_id"])

    def test_evidence_insufficient_rows_are_never_officially_grounded_buckets(self) -> None:
        for row in ROWS:
            if not row["judgment_evidence_sufficient"]:
                self.assertNotIn(row["judgment_candidate"], OFFICIALLY_GROUNDED_CANDIDATES, row["source_record_id"])

    def test_hci_ux_candidate_is_always_marked_insufficient(self) -> None:
        """HCI·UX는 대학알리미 158개 공식 소계열에 정확히 대응하는 코드가 없다 —
        키워드로 후보 표시는 하되 근거 충분으로 절대 표시하지 않는다."""

        for row in ROWS:
            if row["judgment_candidate"] == HCI_UX_CANDIDATE:
                self.assertFalse(row["judgment_evidence_sufficient"])

    def test_rows_with_no_official_candidate_group_and_no_keyword_hit_are_unmapped_or_needs_curriculum(self) -> None:
        for row in ROWS:
            if not row["candidate_canonical_major_ids"]:
                self.assertIn(row["judgment_candidate"], (UNMAPPED, HCI_UX_CANDIDATE), row["source_record_id"])

    def test_manifest_sufficient_plus_insufficient_equals_total(self) -> None:
        self.assertEqual(
            MANIFEST["official_evidence_sufficient_count"] + MANIFEST["official_evidence_insufficient_count"],
            MANIFEST["p1_total"],
        )
        actual_sufficient = sum(1 for r in ROWS if r["judgment_evidence_sufficient"])
        self.assertEqual(MANIFEST["official_evidence_sufficient_count"], actual_sufficient)


class StatsTest(unittest.TestCase):
    """§6 결과 통계."""

    def test_all_required_manifest_stats_present(self) -> None:
        for key in (
            "p1_total", "p1_cluster_breakdown", "judgment_candidate_breakdown",
            "official_evidence_sufficient_count", "official_evidence_insufficient_count",
            "arts_sports_possibility_breakdown", "auto_approved_rows",
        ):
            self.assertIn(key, MANIFEST, key)

    def test_judgment_breakdown_sums_to_total(self) -> None:
        self.assertEqual(sum(MANIFEST["judgment_candidate_breakdown"].values()), MANIFEST["p1_total"])

    def test_arts_breakdown_sums_to_total(self) -> None:
        self.assertEqual(sum(MANIFEST["arts_sports_possibility_breakdown"].values()), MANIFEST["p1_total"])


class HtmlPacketTest(unittest.TestCase):
    """§3 — 콘텐츠·미디어와 디자인/HCI/UX를 별도 필터로 볼 수 있어야 한다."""

    def setUp(self) -> None:
        self.html = HTML_PATH.read_text(encoding="utf-8")

    def test_has_cluster_filter_for_content_media_and_design_hci_ux(self) -> None:
        self.assertIn("콘텐츠·미디어", self.html)
        self.assertIn("디자인/HCI/UX", self.html)
        self.assertIn('data-kind="cluster"', self.html)

    def test_has_judgment_candidate_filter(self) -> None:
        self.assertIn('data-kind="judgment"', self.html)
        for code in ALL_JUDGMENT_CANDIDATES:
            self.assertIn(code, self.html)

    def test_card_count_matches_374(self) -> None:
        self.assertEqual(self.html.count('<div class="card" data-cluster='), 374)

    def test_card_cluster_counts_match_manifest(self) -> None:
        self.assertEqual(self.html.count('data-cluster="CONTENT_MEDIA"'), 275)
        self.assertEqual(self.html.count('data-cluster="DESIGN_HCI_UX"'), 99)

    def test_warns_that_judgment_is_not_final(self) -> None:
        self.assertIn("확정이 아닙니다", self.html)
        self.assertIn("학과명 문자열만으로", self.html)
        self.assertIn("예체능을", self.html)


class PacketHygieneTest(unittest.TestCase):
    def test_no_secret_pattern(self) -> None:
        for path in (JSONL_PATH, HTML_PATH, MANIFEST_PATH):
            blob = path.read_text(encoding="utf-8")
            for token in ("serviceKey", "DATA_GO_KR_SERVICE_KEY", "apikey", "access_token", "sk-", "Bearer "):
                self.assertNotIn(token, blob, f"{path.name}에 {token!r}")

    def test_no_output_file_exceeds_5mb(self) -> None:
        for path in (JSONL_PATH, HTML_PATH, MANIFEST_PATH):
            size = path.stat().st_size
            self.assertLess(size, 5 * 1024 * 1024, f"{path.name}이 {size / 1024 / 1024:.2f}MB다")

    def test_manifest_has_no_timestamp(self) -> None:
        blob = MANIFEST_PATH.read_text(encoding="utf-8")
        for token in ("generated_at", "created_at", "timestamp", "collected_at"):
            self.assertNotIn(token, blob)

    def test_manifest_hashes_match_actual_files(self) -> None:
        self.assertEqual(MANIFEST["input_hashes"]["classification_review_queue.jsonl"], sha256(QUEUE_PATH))
        self.assertEqual(MANIFEST["output_hashes"][JSONL_PATH.name], sha256(JSONL_PATH))
        self.assertEqual(MANIFEST["output_hashes"][HTML_PATH.name], sha256(HTML_PATH))


class DeterminismTest(unittest.TestCase):
    """§5 — 같은 입력에서 2회 byte-identical. 입력이 항상 커밋돼 있으므로 Skip 없이 돈다."""

    def _run(self, data_dir: Path) -> dict[str, bytes]:
        work = data_dir / "academyinfo_work" / "2025"
        work.mkdir(parents=True, exist_ok=True)
        (work / "classification_review_queue.jsonl").write_bytes(QUEUE_PATH.read_bytes())

        proc = subprocess.run(
            [sys.executable, "scripts/career_build_academyinfo_p1_classification_review.py",
             "--survey-year", "2025", "--data-dir", str(data_dir)],
            cwd=ROOT, capture_output=True, timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace")[:800])
        out = work / "packets"
        return {p.name: p.read_bytes() for p in sorted(out.iterdir())}

    def test_two_runs_are_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            first, second = self._run(Path(a)), self._run(Path(b))
            self.assertEqual(first.keys(), second.keys())
            for name in first:
                self.assertEqual(first[name], second[name], f"{name}이 재실행마다 다르다")

    def test_isolated_run_matches_committed_output(self) -> None:
        """임시 디렉터리 실행 결과가 커밋된 실제 산출물과 정확히 같다(재생성 증명)."""

        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(Path(tmp))
        self.assertEqual(result[JSONL_PATH.name], JSONL_PATH.read_bytes())
        self.assertEqual(result[HTML_PATH.name], HTML_PATH.read_bytes())

    def test_isolated_run_does_not_touch_repository_packets(self) -> None:
        before = {n: sha256(p) for n, p in ((JSONL_PATH.name, JSONL_PATH), (HTML_PATH.name, HTML_PATH))}
        with tempfile.TemporaryDirectory() as tmp:
            self._run(Path(tmp))
        for name, path in ((JSONL_PATH.name, JSONL_PATH), (HTML_PATH.name, HTML_PATH)):
            self.assertEqual(before[name], sha256(path))


class CleanCloneTest(unittest.TestCase):
    """§7 — clean clone(전국 원본 데이터 없이 커밋된 Queue만 있는 환경)에서도 재생성된다."""

    def test_script_runs_with_only_committed_queue_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            work = data_dir / "academyinfo_work" / "2025"
            work.mkdir(parents=True)
            (work / "classification_review_queue.jsonl").write_bytes(QUEUE_PATH.read_bytes())
            proc = subprocess.run(
                [sys.executable, "scripts/career_build_academyinfo_p1_classification_review.py",
                 "--survey-year", "2025", "--data-dir", str(data_dir)],
                cwd=ROOT, capture_output=True, timeout=120,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace")[:800])
            self.assertTrue((work / "packets" / "p1_classification_review.jsonl").exists())

    def test_missing_input_fails_closed_without_partial_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            (data_dir / "academyinfo_work" / "2025").mkdir(parents=True)
            proc = subprocess.run(
                [sys.executable, "scripts/career_build_academyinfo_p1_classification_review.py",
                 "--survey-year", "2025", "--data-dir", str(data_dir)],
                cwd=ROOT, capture_output=True, timeout=120,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertFalse((data_dir / "academyinfo_work" / "2025" / "packets").exists())


class UnitLogicTest(unittest.TestCase):
    """`build_p1_rows()`를 작은 Fixture로 직접 검증 — 전국 데이터 없이도 판단 로직
    자체가 맞는지 확인한다."""

    def _row(self, **overrides) -> dict:
        row = {
            "source_record_id": "src_1", "department_id": "dept_1",
            "university_name": "픽스처대학교", "department_name": "일반학과",
            "college_name": "공과대학", "official_large_series_name": "공학계열",
            "official_middle_series_name": "전기·전자·컴퓨터", "official_small_series_name": "전산학·컴퓨터공학",
            "candidate_canonical_major_ids": ["computer_science"], "arts_sports_possibility": "UNLIKELY",
            "official_evidence_needed": ["공식 교육과정"], "review_cause": "CONVERGENCE",
        }
        row.update(overrides)
        return row

    def test_fine_arts_design_candidate_excluded(self) -> None:
        rows = build_p1_rows([self._row(
            department_name="디자인학과", candidate_canonical_major_ids=["fine_arts_design"],
        )])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["judgment_candidate"], DESIGN_ARTS_EXCLUDED)
        self.assertTrue(rows[0]["judgment_evidence_sufficient"])

    def test_media_communication_candidate(self) -> None:
        rows = build_p1_rows([self._row(
            department_name="미디어학과", candidate_canonical_major_ids=["media_communication"],
        )])
        self.assertEqual(rows[0]["judgment_candidate"], MEDIA_COMMUNICATION_CANDIDATE)
        self.assertTrue(rows[0]["judgment_evidence_sufficient"])

    def test_hci_ux_keyword_without_official_group_stays_insufficient(self) -> None:
        rows = build_p1_rows([self._row(
            department_name="UX디자인학과", candidate_canonical_major_ids=[],
        )])
        self.assertEqual(rows[0]["judgment_candidate"], HCI_UX_CANDIDATE)
        self.assertFalse(rows[0]["judgment_evidence_sufficient"])

    def test_no_official_candidate_and_no_keyword_is_unmapped(self) -> None:
        # "콘텐츠"가 있어 CONTENT_MEDIA 군집(P1)에는 들어오지만, 공식 후보 전공군도
        # HCI/UX 키워드도 없다.
        rows = build_p1_rows([self._row(
            department_name="콘텐츠제작학과", candidate_canonical_major_ids=[],
        )])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["judgment_candidate"], UNMAPPED)

    def test_official_candidate_without_confident_keyword_needs_curriculum(self) -> None:
        # "미디어"가 있어 CONTENT_MEDIA 군집(P1)에는 들어오지만, 공식 후보 전공군이
        # media_communication/예체능 4개 중 어디에도 속하지 않는다.
        rows = build_p1_rows([self._row(
            department_name="미디어공학과", candidate_canonical_major_ids=["computer_science"],
        )])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["judgment_candidate"], NEEDS_OFFICIAL_CURRICULUM)
        self.assertFalse(rows[0]["judgment_evidence_sufficient"])

    def test_rows_outside_p1_clusters_are_dropped(self) -> None:
        # cluster_of()가 CONTENT_MEDIA/DESIGN_HCI_UX로 분류하지 않는 행(예: 순수
        # BUSINESS_FINANCE 키워드만 있는 행)은 P1 패킷에 나타나지 않는다.
        rows = build_p1_rows([self._row(department_name="경영정보학과", college_name="경영대학")])
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
