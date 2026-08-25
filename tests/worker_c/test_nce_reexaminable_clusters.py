"""N.C.E REEXAMINABLE_BY_OFFICIAL_EVIDENCE 584건 중계열 군집화 테스트 —
브랜치 c/academyinfo-nce-reexaminable.

핵심 불변식 두 가지를 기계적으로 증명한다.
    1. `nce_triage_queue.jsonl`(1,901건, worker-c 산출물)을 한 바이트도 바꾸지 않았다.
    2. 어떤 군집도 자동으로 승인되지 않았다 — PROPOSED_GROUP_CANDIDATE도 제안일 뿐이다.
"""

from __future__ import annotations

import gzip
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "data" / "academyinfo_work" / "2025"
PACKETS = WORK / "packets"
SCRIPT = ROOT / "scripts" / "career_build_nce_reexaminable_clusters.py"

STATUS_PROPOSED = "PROPOSED_GROUP_CANDIDATE"
STATUS_DEPT_REVIEW = "DEPARTMENT_LEVEL_REVIEW_REQUIRED"
STATUS_INSUFFICIENT = "INSUFFICIENT_OFFICIAL_EVIDENCE"
ALLOWED_STATUSES = {STATUS_PROPOSED, STATUS_DEPT_REVIEW, STATUS_INSUFFICIENT}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


NCE_ALL = read_jsonl(PACKETS / "nce_triage_queue.jsonl")
REEXAMINABLE = [r for r in NCE_ALL if r["triage_group"] == "REEXAMINABLE_BY_OFFICIAL_EVIDENCE"]
CLUSTERS = read_jsonl(PACKETS / "nce_reexaminable_middle_series_clusters.jsonl")
MANIFEST = json.loads((PACKETS / "nce_reexaminable_manifest.json").read_text(encoding="utf-8"))
OFFICIAL_MIDDLE_SERIES_TABLE = {
    row["cdnm"]: row["cdid"]
    for row in (
        json.loads(l)
        for l in gzip.open(
            ROOT / "data" / "academyinfo_raw" / "2025" / "codes" / "getCodeByMiddleSeries.jsonl.gz",
            "rt", encoding="utf-8",
        )
        if l.strip()
    )
}
CANONICAL_GROUPS = read_jsonl(ROOT / "data" / "canonical_major_groups.draft.jsonl")
CANONICAL_GROUP_IDS = {g["canonical_major_id"] for g in CANONICAL_GROUPS}


class InputCountTest(unittest.TestCase):
    def test_source_queue_has_584_reexaminable_rows(self) -> None:
        """원본 nce_triage_queue.jsonl 자체에서 584건을 확인한다(내 산출물이 아니라 입력)."""
        self.assertEqual(len(REEXAMINABLE), 584)

    def test_source_queue_total_unchanged_at_1901(self) -> None:
        self.assertEqual(len(NCE_ALL), 1901)

    def test_other_1317_rows_are_the_two_untouched_groups(self) -> None:
        others = [r for r in NCE_ALL if r["triage_group"] != "REEXAMINABLE_BY_OFFICIAL_EVIDENCE"]
        self.assertEqual(len(others), 1317)
        self.assertEqual(
            {r["triage_group"] for r in others},
            {"NAME_ALONE_INSUFFICIENT", "NEEDS_CANONICAL_GROUP_EXPANSION"},
        )


class ClusterCoverageTest(unittest.TestCase):
    """584건 정확히, ID 일치, 다른 1,317건 무변경."""

    def test_cluster_row_total_is_exactly_584(self) -> None:
        self.assertEqual(sum(c["row_count"] for c in CLUSTERS), 584)

    def test_member_candidate_ids_match_source_queue_exactly(self) -> None:
        clustered_ids = {m["candidate_id"] for c in CLUSTERS for m in c["members"]}
        source_ids = {r["candidate_id"] for r in REEXAMINABLE}
        self.assertEqual(clustered_ids, source_ids)
        self.assertEqual(len(clustered_ids), 584)

    def test_no_candidate_id_appears_in_two_clusters(self) -> None:
        all_ids = [m["candidate_id"] for c in CLUSTERS for m in c["members"]]
        self.assertEqual(len(all_ids), len(set(all_ids)))

    def test_source_queue_file_untouched_on_disk(self) -> None:
        """git이 아니라 내용 자체로 재확인 — 1,901건 전부 그대로인지."""
        reloaded = read_jsonl(PACKETS / "nce_triage_queue.jsonl")
        self.assertEqual(reloaded, NCE_ALL)

    def test_script_never_writes_nce_triage_queue(self) -> None:
        """`nce_triage_queue.jsonl`은 오직 read_jsonl로만 읽히고, write_jsonl 호출 어디에도
        그 경로가 인자로 나타나지 않아야 한다(정적 검사)."""
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('inputs["nce_triage_queue.jsonl"]', src, "읽기 경로가 있어야 한다")
        for line in src.splitlines():
            if "write_jsonl(" in line:
                self.assertNotIn("nce_triage_queue", line, line)


class OfficialMiddleSeriesCodeTest(unittest.TestCase):
    """§ 공식 중계열 코드가 대학알리미 코드표에 존재."""

    def test_code_table_loaded(self) -> None:
        self.assertGreaterEqual(len(OFFICIAL_MIDDLE_SERIES_TABLE), 24)

    def test_every_cluster_code_and_name_matches_official_table(self) -> None:
        for c in CLUSTERS:
            name = c["official_middle_series_name"]
            code = c["official_middle_series_code"]
            self.assertIn(name, OFFICIAL_MIDDLE_SERIES_TABLE, f"{name}이 공식 코드표에 없다")
            self.assertEqual(OFFICIAL_MIDDLE_SERIES_TABLE[name], code, f"{name}의 코드 불일치")

    def test_no_cluster_uses_the_nce_sentinel_code(self) -> None:
        """584건은 전부 중계열이 살아있는 행이다 — 99(N.C.E)가 섞이면 안 된다."""
        codes = {c["official_middle_series_code"] for c in CLUSTERS}
        self.assertNotIn("99", codes)

    def test_every_row_middle_series_name_traces_back_to_a_cluster(self) -> None:
        clustered_names = {(c["official_middle_series_code"], c["official_middle_series_name"]) for c in CLUSTERS}
        for r in REEXAMINABLE:
            name = r["official_middle_series_name"]
            code = OFFICIAL_MIDDLE_SERIES_TABLE[name]
            self.assertIn((code, name), clustered_names)


class GroupLinkageDecisionTest(unittest.TestCase):
    """§ 1:1도 자동 승인 금지 / 1:다 → DEPARTMENT_LEVEL_REVIEW_REQUIRED /
    근거 부족 → INSUFFICIENT_OFFICIAL_EVIDENCE."""

    def test_status_values_are_only_the_three_allowed(self) -> None:
        for c in CLUSTERS:
            self.assertIn(c["group_linkage_status"], ALLOWED_STATUSES)

    def test_single_candidate_is_proposed_not_confirmed(self) -> None:
        for c in CLUSTERS:
            if len(c["candidate_canonical_major_groups"]) == 1:
                self.assertEqual(c["group_linkage_status"], STATUS_PROPOSED)

    def test_multiple_candidates_require_department_level_review(self) -> None:
        for c in CLUSTERS:
            if len(c["candidate_canonical_major_groups"]) >= 2:
                self.assertEqual(c["group_linkage_status"], STATUS_DEPT_REVIEW)

    def test_zero_candidates_are_insufficient_evidence(self) -> None:
        for c in CLUSTERS:
            if len(c["candidate_canonical_major_groups"]) == 0:
                self.assertEqual(c["group_linkage_status"], STATUS_INSUFFICIENT)

    def test_candidate_canonical_major_ids_exist_in_the_42_groups(self) -> None:
        """42개를 임의로 늘리지 않았다는 것을 후보 id로도 재확인한다."""
        for c in CLUSTERS:
            for g in c["candidate_canonical_major_groups"]:
                self.assertIn(g["canonical_major_id"], CANONICAL_GROUP_IDS)

    def test_canonical_major_group_count_still_42(self) -> None:
        self.assertEqual(len(CANONICAL_GROUPS), 42)

    def test_every_cluster_has_the_required_fields(self) -> None:
        required = (
            "official_middle_series_code", "official_middle_series_name", "row_count",
            "candidate_canonical_major_groups", "unlinkable_or_too_broad_reason",
            "additional_official_evidence_needed", "decision_status", "reviewer_1_status",
        )
        for c in CLUSTERS:
            for field in required:
                self.assertIn(field, c, f"{field}가 없다")
            self.assertTrue(c["unlinkable_or_too_broad_reason"])
            self.assertTrue(c["additional_official_evidence_needed"])


class NoAutoApprovalTest(unittest.TestCase):
    def test_manifest_declares_zero_auto_approved(self) -> None:
        self.assertEqual(MANIFEST["auto_approved_clusters"], 0)

    def test_every_cluster_is_pending_and_tbd(self) -> None:
        for c in CLUSTERS:
            self.assertEqual(c["decision_status"], "PENDING")
            self.assertEqual(c["reviewer_1_status"], "TBD")
            self.assertEqual(c["reviewer_1_comment"], "")

    def test_no_approved_string_anywhere(self) -> None:
        blob = json.dumps(CLUSTERS, ensure_ascii=False)
        for token in ("APPROVED", "EVIDENCED", "CONFIRMED"):
            self.assertNotIn(f'"{token}"', blob)

    def test_proposed_group_candidate_status_is_not_an_approval_value(self) -> None:
        """PROPOSED_GROUP_CANDIDATE 문자열 자체가 reviewer_1_status에 나타나면 안 된다."""
        for c in CLUSTERS:
            self.assertNotEqual(c["reviewer_1_status"], c["group_linkage_status"])


class DeterminismTest(unittest.TestCase):
    """동일 입력 2회 byte-identical — 커밋된 입력만으로 재현되므로(clean clone과 동일
    조건) skip하지 않는다."""

    def _run(self, data_dir: Path) -> dict[str, bytes]:
        work = data_dir / "academyinfo_work" / "2025"
        (work / "packets").mkdir(parents=True, exist_ok=True)
        (work / "packets" / "nce_triage_queue.jsonl").write_bytes(
            (PACKETS / "nce_triage_queue.jsonl").read_bytes()
        )
        (data_dir / "canonical_major_groups.draft.jsonl").write_bytes(
            (ROOT / "data" / "canonical_major_groups.draft.jsonl").read_bytes()
        )
        codes_dir = data_dir / "academyinfo_raw" / "2025" / "codes"
        codes_dir.mkdir(parents=True, exist_ok=True)
        (codes_dir / "getCodeByMiddleSeries.jsonl.gz").write_bytes(
            (ROOT / "data" / "academyinfo_raw" / "2025" / "codes" / "getCodeByMiddleSeries.jsonl.gz").read_bytes()
        )
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--data-dir", str(data_dir)],
            cwd=ROOT, capture_output=True, timeout=300,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace")[:1000])
        out = work / "packets"
        return {
            p.name: p.read_bytes() for p in sorted(out.iterdir())
            if p.name.startswith("nce_reexaminable_")
        }

    def test_two_runs_from_committed_inputs_only_are_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            first, second = self._run(Path(a)), self._run(Path(b))
            self.assertEqual(first.keys(), second.keys())
            self.assertEqual(len(first), 4, sorted(first))
            for name in first:
                self.assertEqual(first[name], second[name], f"{name}이 재실행마다 다르다")

    def test_isolated_run_does_not_touch_repository_outputs(self) -> None:
        import hashlib

        names = (
            "nce_reexaminable_middle_series_clusters.jsonl",
            "nce_reexaminable_review_packet.md",
            "nce_reexaminable_review_packet.html",
            "nce_reexaminable_manifest.json",
        )
        before = {n: hashlib.sha256((PACKETS / n).read_bytes()).hexdigest() for n in names}
        with tempfile.TemporaryDirectory() as tmp:
            self._run(Path(tmp))
        for name in names:
            self.assertEqual(before[name], hashlib.sha256((PACKETS / name).read_bytes()).hexdigest())


class MissingInputSafetyTest(unittest.TestCase):
    def test_missing_input_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            (data_dir / "academyinfo_work" / "2025").mkdir(parents=True)
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--data-dir", str(data_dir)],
                cwd=ROOT, capture_output=True, timeout=120,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertFalse((data_dir / "academyinfo_work" / "2025" / "packets").exists())


class PacketHygieneTest(unittest.TestCase):
    NAMES = (
        "nce_reexaminable_middle_series_clusters.jsonl",
        "nce_reexaminable_review_packet.md",
        "nce_reexaminable_review_packet.html",
        "nce_reexaminable_manifest.json",
    )

    def test_all_files_exist(self) -> None:
        for name in self.NAMES:
            self.assertTrue((PACKETS / name).exists(), name)

    def test_no_secret_pattern(self) -> None:
        for name in self.NAMES:
            blob = (PACKETS / name).read_text(encoding="utf-8")
            for token in ("serviceKey", "DATA_GO_KR_SERVICE_KEY", "apikey", "access_token"):
                self.assertNotIn(token, blob)

    def test_no_file_exceeds_5mb(self) -> None:
        for name in self.NAMES:
            size = (PACKETS / name).stat().st_size
            self.assertLess(size, 5 * 1024 * 1024, f"{name}이 {size / 1024 / 1024:.1f}MB다")

    def test_manifest_has_no_timestamp(self) -> None:
        blob = json.dumps(MANIFEST, ensure_ascii=False)
        for token in ("generated_at", "created_at", "timestamp", "collected_at"):
            self.assertNotIn(token, blob)

    def test_manifest_hashes_match_committed_files(self) -> None:
        import hashlib

        for name, expected in MANIFEST["output_hashes"].items():
            self.assertEqual(hashlib.sha256((PACKETS / name).read_bytes()).hexdigest(), expected, name)


class UnrelatedFilesUntouchedTest(unittest.TestCase):
    """Master/API/Mock/Bridge 무변경 — origin/trait-vector-v2 대비 diff가 비어야 한다."""

    def _diff_paths(self, *paths: str) -> str:
        proc = subprocess.run(
            ["git", "diff", "--name-only", "origin/trait-vector-v2...HEAD", "--", *paths],
            cwd=ROOT, capture_output=True, text=True, timeout=60,
        )
        return proc.stdout.strip()

    def test_master_unchanged(self) -> None:
        # 2026-08-25 전국 학과 1,072건 Production Master 전환(a/national-master-
        # promotion-final-wiring)이 이 N.C.E 재검토 작업과 무관하게 data/master/
        # departments.jsonl·department_recommendation_scope.jsonl을 의도적으로
        # 바꾸고 departments_promotion_manifest.json을 새로 추가했다(옛 값은
        # data/archive/에 보존) — 이 세 파일만 diff 대상에서 뺀다.
        # 2026-08-25 Service Canonical Major v2(a/service-major-catalog-v2)도
        # 이 N.C.E 재검토 작업과 무관하게 새 파일 2개를 추가했다 — 같은 이유로 뺀다.
        # 2026-08-25 39개 Major 최종 통합(a/final-39-major-integration)이 이 N.C.E
        # 재검토 작업과 무관한 4개 upstream 브랜치(Profile v2·Subject Mapping v2·
        # 전국 학과 38개 재분류)를 병합하며 추가·재분류한 파일들도 같은 이유로 뺀다 —
        # major_profiles_v2.jsonl(a/major-profiles-v2-38), subject_profiles_v2.jsonl·
        # subject_major_link_evidence_v2.jsonl·subject_trait_mapping_evidence_v2.jsonl
        # (a/subject-mapping-38-majors), departments_promotion_manifest_38majors.json
        # (c/national-departments-38-majors — departments.jsonl/department_recommendation_
        # scope.jsonl는 이미 위에서 빠져 있다).
        self.assertEqual(
            self._diff_paths(
                "data/master/",
                ":(exclude)data/master/departments.jsonl",
                ":(exclude)data/master/department_recommendation_scope.jsonl",
                ":(exclude)data/master/departments_promotion_manifest.json",
                ":(exclude)data/master/service_canonical_majors_v2.jsonl",
                ":(exclude)data/master/canonical_major_group_to_service_major_v2.jsonl",
                ":(exclude)data/master/departments_promotion_manifest_38majors.json",
                ":(exclude)data/master/major_profiles_v2.jsonl",
                ":(exclude)data/master/subject_profiles_v2.jsonl",
                ":(exclude)data/master/subject_major_link_evidence_v2.jsonl",
                ":(exclude)data/master/subject_trait_mapping_evidence_v2.jsonl",
            ),
            "",
        )

    def test_api_and_mock_unchanged(self) -> None:
        # 위와 같은 이유로 src/api/main.py(fail_closed_major_ids 10개 통일)와
        # outputs/mock_api/departments_normal.json·subgraph_normal.json(새 Master
        # 기준 재생성)을 diff 대상에서 뺀다.
        self.assertEqual(
            self._diff_paths(
                "src/api/", "outputs/mock_api/",
                ":(exclude)src/api/main.py",
                ":(exclude)outputs/mock_api/departments_normal.json",
                ":(exclude)outputs/mock_api/subgraph_normal.json",
            ),
            "",
        )

    def test_bridge_files_unchanged(self) -> None:
        self.assertEqual(self._diff_paths(
            "data/master/canonical_major_group_bridge.draft.jsonl",
            "src/schemas/canonical_major_group_bridge.py",
            "src/schemas/canonical_major_group_bridge_review.py",
            "src/services/canonical_major_group_bridge_loader.py",
            "src/services/canonical_major_group_bridge_review_store.py",
        ), "")

    def test_canonical_major_groups_draft_unchanged(self) -> None:
        """42개 전공군 정의 자체를 건드리지 않았다."""
        self.assertEqual(self._diff_paths("data/canonical_major_groups.draft.jsonl"), "")

    def test_nce_triage_queue_unchanged(self) -> None:
        self.assertEqual(
            self._diff_paths("data/academyinfo_work/2025/packets/nce_triage_queue.jsonl"), ""
        )


if __name__ == "__main__":
    unittest.main()
