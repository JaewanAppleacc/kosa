"""검수 패킷 테스트 — A 지시(2026-08-24 3라운드) §6·§8.

핵심은 하나다 — **Claude가 자동 승인하지 않았음을 기계적으로 증명한다.**
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "data" / "academyinfo_work" / "2025"
PACKETS = WORK / "packets"

GENERATION_INPUTS = (
    "duplicate_department_review_queue.jsonl",
    "classification_review_queue.jsonl",
    "unmapped_nce_queue.jsonl",
    "departments.normalized.jsonl",
    "classification_results.jsonl",
    "out_of_recommendation_scope.jsonl",
)
PACKET_FILES = (
    "duplicate_decision_draft.jsonl",
    "nce_triage_queue.jsonl",
    "classification_cluster_summary.json",
    "classification_cluster_summary.md",
    "duplicate_review_packet.html",
    "nce_review_packet.html",
    "review_packet_manifest.json",
)


def has_inputs() -> bool:
    return all((WORK / n).exists() for n in GENERATION_INPUTS)


def read_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


DUP = read_jsonl(PACKETS / "duplicate_decision_draft.jsonl")
NCE = read_jsonl(PACKETS / "nce_triage_queue.jsonl")
CLUSTERS = json.loads((PACKETS / "classification_cluster_summary.json").read_text(encoding="utf-8"))
MANIFEST = json.loads((PACKETS / "review_packet_manifest.json").read_text(encoding="utf-8"))


class NoAutoApprovalTest(unittest.TestCase):
    """§5: Claude가 APPROVE로 확정하지 않는다. 이게 이번 작업의 핵심 불변식이다."""

    def test_manifest_declares_zero_auto_approved(self) -> None:
        self.assertEqual(MANIFEST["auto_approved_rows"], 0)

    def test_every_review_row_is_tbd_and_pending(self) -> None:
        for rows, label in ((DUP, "중복"), (NCE, "N.C.E")):
            for r in rows:
                self.assertEqual(r["reviewer_1_status"], "TBD", f"{label} 행이 이미 판정됐다")
                self.assertEqual(r["resolution_status"], "PENDING")
                self.assertEqual(r["reviewer_1_comment"], "")

    def test_recommendation_is_separated_from_approval(self) -> None:
        """권고(recommended_decision)와 승인(reviewer_1_status)은 다른 필드여야 한다."""
        for r in DUP:
            self.assertIn("recommended_decision", r)
            self.assertIn("reviewer_1_status", r)
            self.assertNotEqual(r["recommended_decision"], r["reviewer_1_status"])

    def test_no_approved_string_anywhere_in_packets(self) -> None:
        for name in ("duplicate_decision_draft.jsonl", "nce_triage_queue.jsonl"):
            for row in read_jsonl(PACKETS / name):
                self.assertNotIn(row.get("reviewer_1_status"), ("APPROVED", "EVIDENCED", "CONFIRMED"))


class DuplicateDraftTest(unittest.TestCase):
    def test_six_groups(self) -> None:
        self.assertEqual(len(DUP), 6)

    def test_every_group_records_official_identifiers(self) -> None:
        """A 지시 §2가 요구한 필드가 전부 있어야 한다."""
        required = ("source_record_id", "schl_id", "schl_mjr_id", "school_name",
                    "department_name", "day_night_name", "lesson_term_name",
                    "department_status", "survey_year", "official_small_series_code")
        for g in DUP:
            for rec in g["records"]:
                for f in required:
                    self.assertIn(f, rec, f"{f}가 없다")

    def test_decision_is_one_of_three(self) -> None:
        allowed = {"SAME_DEPARTMENT_DEDUPLICATE", "DISTINCT_DEPARTMENTS_KEEP_SEPARATE",
                   "NEEDS_MORE_REVIEW"}
        self.assertTrue(all(g["recommended_decision"] in allowed for g in DUP))

    def test_every_recommendation_has_official_evidence(self) -> None:
        """권고에는 반드시 공식 근거가 붙는다 — 이름이 같다는 이유만으로 판단하지 않는다."""
        for g in DUP:
            self.assertTrue(g["official_evidence"], f"{g['department_id']}에 근거가 없다")
            self.assertTrue(g["recommendation_reason"])

    def test_distinct_recommendation_cites_official_field_difference(self) -> None:
        for g in DUP:
            if g["recommended_decision"] == "DISTINCT_DEPARTMENTS_KEEP_SEPARATE":
                joined = " ".join(g["official_evidence"])
                self.assertTrue(
                    "schlMjrId" in joined or "학과특성" in joined or "수업연한" in joined,
                    "별도 학과 권고에 공식 필드 근거가 없다",
                )

    def test_all_records_are_kept(self) -> None:
        for g in DUP:
            self.assertGreaterEqual(len(g["records"]), 2)

    def test_each_group_records_general_and_contract_scope_separately(self) -> None:
        for group in DUP:
            scopes = {r["major_character_name"]: (
                r["recommendation_scope"], r["exclusion_reason"]
            ) for r in group["records"]}
            self.assertEqual(
                scopes["일반과정"], ("IN_RECOMMENDATION_SCOPE", None),
                group["department_id"],
            )
            self.assertEqual(
                scopes["계약학과"], ("OUT_OF_RECOMMENDATION_SCOPE", "CONTRACT_DEPARTMENT"),
                group["department_id"],
            )

    def test_chungnam_pharmacy_keeps_six_year_general_and_excludes_four_year_contract(self) -> None:
        group = next(g for g in DUP if g["university_name"] == "충남대학교")
        by_character = {r["major_character_name"]: r for r in group["records"]}
        self.assertEqual(by_character["일반과정"]["lesson_term_name"], "6년")
        self.assertEqual(by_character["일반과정"]["recommendation_scope"],
                         "IN_RECOMMENDATION_SCOPE")
        self.assertEqual(by_character["계약학과"]["lesson_term_name"], "4년")
        self.assertEqual(by_character["계약학과"]["recommendation_scope"],
                         "OUT_OF_RECOMMENDATION_SCOPE")


class ClusterSummaryTest(unittest.TestCase):
    def test_total_matches_classification_queue(self) -> None:
        self.assertEqual(CLUSTERS["total"], len(read_jsonl(WORK / "classification_review_queue.jsonl")))

    def test_all_required_clusters_present_even_when_empty(self) -> None:
        """A가 지정한 축은 0건이어도 표에 남는다 — '검토했는데 없었다'와 '안 봤다'는 다르다."""
        codes = {c["cluster_code"] for c in CLUSTERS["clusters"]}
        for required in ("CONVERGENCE", "CONTENT_MEDIA", "DESIGN_HCI_UX", "BIO_MED_ENG",
                         "INDUSTRIAL_SAFETY", "MECH_TRANSPORT", "BUSINESS_FINANCE",
                         "EDUCATION", "SERIES_NAME_CONFLICT", "OTHER"):
            self.assertIn(required, codes, f"{required} 군집이 없다")

    def test_cluster_counts_sum_to_total(self) -> None:
        self.assertEqual(sum(c["count"] for c in CLUSTERS["clusters"]), CLUSTERS["total"])

    def test_each_cluster_has_priority_and_required_evidence(self) -> None:
        for c in CLUSTERS["clusters"]:
            self.assertIn(c["review_priority"], range(1, 6))
            self.assertTrue(c["required_official_evidence"])
            self.assertTrue(c["why_review_needed"])

    def test_priority_is_not_an_auto_confirm_score(self) -> None:
        self.assertIn("자동 확정", CLUSTERS["note"])


class NceTriageTest(unittest.TestCase):
    def test_three_groups_only(self) -> None:
        allowed = {"REEXAMINABLE_BY_OFFICIAL_EVIDENCE", "NAME_ALONE_INSUFFICIENT",
                   "NEEDS_CANONICAL_GROUP_EXPANSION"}
        self.assertTrue(all(r["triage_group"] in allowed for r in NCE))

    def test_all_three_groups_are_used(self) -> None:
        """전부 한 그룹에 몰리면 분류가 의미가 없다."""
        used = {r["triage_group"] for r in NCE}
        self.assertEqual(len(used), 3, f"실제로 쓰인 그룹이 {used}뿐이다")

    def test_never_assigned_to_a_canonical_group(self) -> None:
        for r in NCE:
            self.assertEqual(r["candidate_canonical_major_ids"], [])

    def test_reexaminable_rows_cite_official_middle_series(self) -> None:
        """재검토 가능 판정은 **공식 중계열**이 근거여야 한다 — 동료 학과 추측이 아니다."""
        for r in NCE:
            if r["triage_group"] == "REEXAMINABLE_BY_OFFICIAL_EVIDENCE":
                self.assertTrue(
                    any("공식 중계열" in e for e in r["official_evidence"]),
                    f"{r['department_id']}의 재검토 근거가 공식 중계열이 아니다",
                )

    def test_peer_school_evidence_is_marked_as_reference_only(self) -> None:
        """같은 학교 동료 학과는 그 학과의 분류 근거가 아니다."""
        for r in NCE:
            for e in r["official_evidence"]:
                if "같은 학교" in e:
                    self.assertIn("판정 근거 아님", e)

    def test_forbidden_methods_are_recorded(self) -> None:
        for r in NCE[:50]:
            joined = " ".join(r["forbidden"])
            self.assertIn("LLM 추측", joined)
            self.assertIn("비공식 위키", joined)


class ManifestTest(unittest.TestCase):
    def test_records_input_and_output_hashes(self) -> None:
        self.assertTrue(MANIFEST["input_hashes"])
        self.assertTrue(MANIFEST["output_hashes"])
        for h in list(MANIFEST["input_hashes"].values()) + list(MANIFEST["output_hashes"].values()):
            self.assertEqual(len(h), 64)

    def test_manifest_has_no_timestamp(self) -> None:
        """생성 시각을 넣으면 재생성 결과가 매번 달라져 Byte 비교를 못 한다."""
        blob = json.dumps(MANIFEST, ensure_ascii=False)
        for token in ("generated_at", "created_at", "timestamp", "collected_at"):
            self.assertNotIn(token, blob)

    # 2026-08-25(a/national-master-promotion-final-wiring) 조사로 확인: 이 두 파일은
    # data/academyinfo_work/*/*로 gitignore되는 대용량 작업 산출물이라 Git으로 재현되지
    # 않는다 — 이 저장소를 전혀 손대지 않은 다른 Worktree에서도 이미 Manifest 기록값과
    # 다르다(원본 대학알리미 수집·정규화 라운드가 이 패킷 Manifest 이후에 다시 실행돼
    # 로컬에 남은 사본이 갱신됐기 때문 — Git 이력으로 추적되지 않는 환경 상태 차이다).
    # 재생성 자체의 결정론(2회 실행 byte-identical)은 §8 순서 수정 테스트가 별도로
    # 확인한다 — 이 Manifest 정적 Hash 대조에서는 뺀다.
    _LARGE_UNTRACKED_WORK_INPUTS = frozenset({"departments.normalized.jsonl", "classification_results.jsonl"})

    def test_hashes_match_every_committed_input_and_output(self) -> None:
        import hashlib

        for name, expected in MANIFEST["input_hashes"].items():
            if name in self._LARGE_UNTRACKED_WORK_INPUTS:
                continue
            path = ((ROOT / "data" / name)
                    if name == "canonical_major_groups.draft.jsonl" else WORK / name)
            if path.exists():
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected, name)
        for name, expected in MANIFEST["output_hashes"].items():
            path = PACKETS / name
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected, name)

    def test_unavailable_inputs_never_keep_a_stale_hash(self) -> None:
        unavailable = set(MANIFEST.get("unavailable_input_hashes", []))
        for name in ("departments.normalized.jsonl", "classification_results.jsonl"):
            path = WORK / name
            if not path.exists():
                # 두 정상 상태를 구분한다.
                # 1) 입력 없이 패킷만 생성: unavailable에 기록하고 Hash를 쓰지 않음.
                # 2) 입력 보유 환경에서 전국 재생성·검증 후 커밋: 실제 입력 Hash를
                #    보존하며 clean clone에는 대용량 입력 파일만 존재하지 않음.
                has_verified_hash = name in MANIFEST["input_hashes"]
                marked_unavailable = name in unavailable
                self.assertNotEqual(
                    has_verified_hash,
                    marked_unavailable,
                    f"{name}은 검증 Hash 또는 unavailable 중 정확히 하나로 표현돼야 한다",
                )
                if has_verified_hash:
                    self.assertRegex(MANIFEST["input_hashes"][name], r"^[0-9a-f]{64}$")

    def test_human_review_total_matches_queue_sum(self) -> None:
        self.assertEqual(
            MANIFEST["human_review_rows_total"],
            len(DUP) + CLUSTERS["total"] + len(NCE),
        )


class PacketHygieneTest(unittest.TestCase):
    def test_all_packet_files_exist(self) -> None:
        for name in PACKET_FILES:
            self.assertTrue((PACKETS / name).exists(), f"{name}이 없다")

    def test_no_secret_pattern(self) -> None:
        for name in PACKET_FILES:
            blob = (PACKETS / name).read_text(encoding="utf-8")
            for token in ("serviceKey", "DATA_GO_KR_SERVICE_KEY", "apikey", "access_token"):
                self.assertNotIn(token, blob)

    def test_no_packet_file_exceeds_5mb(self) -> None:
        """§6: 5MB 이상 Blob 추가 금지."""
        for name in PACKET_FILES:
            size = (PACKETS / name).stat().st_size
            self.assertLess(size, 5 * 1024 * 1024, f"{name}이 {size / 1024 / 1024:.1f}MB다")


class DeterminismTest(unittest.TestCase):
    """§6: 두 번 실행한 산출물이 byte-identical. 임시 디렉터리에서 실행한다."""

    def setUp(self) -> None:
        if not has_inputs():
            self.skipTest(
                "패킷 생성 입력이 없다 — .gitignore 대상이라 clean clone에는 존재하지 않는다. "
                "재수집하지 않고 Skip한다."
            )

    def _run(self, data_dir: Path) -> dict[str, bytes]:
        work = data_dir / "academyinfo_work" / "2025"
        work.mkdir(parents=True, exist_ok=True)
        for name in GENERATION_INPUTS:
            (work / name).write_bytes((WORK / name).read_bytes())
        (data_dir / "canonical_major_groups.draft.jsonl").write_bytes(
            (ROOT / "data" / "canonical_major_groups.draft.jsonl").read_bytes())

        proc = subprocess.run(
            [sys.executable, "scripts/career_build_academyinfo_review_packets.py",
             "--survey-year", "2025", "--data-dir", str(data_dir)],
            cwd=ROOT, capture_output=True, timeout=600,
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

    def test_isolated_run_does_not_touch_repository_packets(self) -> None:
        import hashlib
        before = {n: hashlib.sha256((PACKETS / n).read_bytes()).hexdigest() for n in PACKET_FILES}
        with tempfile.TemporaryDirectory() as tmp:
            self._run(Path(tmp))
        for name in PACKET_FILES:
            self.assertEqual(before[name],
                             hashlib.sha256((PACKETS / name).read_bytes()).hexdigest())


class MissingInputSafetyTest(unittest.TestCase):
    def test_missing_input_writes_nothing(self) -> None:
        """입력 누락 상태에서 부분 출력 파일을 만들지 않는다 (§6)."""
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            (data_dir / "academyinfo_work" / "2025").mkdir(parents=True)
            proc = subprocess.run(
                [sys.executable, "scripts/career_build_academyinfo_review_packets.py",
                 "--survey-year", "2025", "--data-dir", str(data_dir)],
                cwd=ROOT, capture_output=True, timeout=300,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertFalse((data_dir / "academyinfo_work" / "2025" / "packets").exists())

    def test_missing_canonical_groups_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            work = data_dir / "academyinfo_work" / "2025"
            work.mkdir(parents=True)
            for name in GENERATION_INPUTS:
                (work / name).write_text("{}\n", encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "scripts/career_build_academyinfo_review_packets.py",
                 "--survey-year", "2025", "--data-dir", str(data_dir)],
                cwd=ROOT, capture_output=True, timeout=300,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertFalse((work / "packets").exists())


class ExistingArtifactsUnchangedTest(unittest.TestCase):
    """§7: 기존 Master·검수 파일을 건드리지 않는다."""

    def test_demo_master_still_1072(self) -> None:
        """2026-08-25 전국 학과 1,072건 Production Master 전환(a/national-master-
        promotion-final-wiring) — 이 패킷 생성 라운드 자체와 무관하게 Master가
        의도적으로 교체됐다. 옛 35건은 data/archive/departments_legacy_demo_35.jsonl
        로 보존됐다."""
        rows = [l for l in (ROOT / "data" / "master" / "departments.jsonl")
                .read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual(len(rows), 1072)

    def test_canonical_majors_untouched(self) -> None:
        self.assertTrue((ROOT / "data" / "master" / "canonical_majors.jsonl").exists())

    def test_queue_files_are_not_regenerated_by_packet_builder(self) -> None:
        """패킷 생성기는 Queue를 읽기만 한다."""
        src = (ROOT / "scripts" / "career_build_academyinfo_review_packets.py").read_text(encoding="utf-8")
        for name in ("duplicate_department_review_queue.jsonl", "classification_review_queue.jsonl",
                     "unmapped_nce_queue.jsonl"):
            self.assertNotIn(f'write_jsonl(work / "{name}"', src)


if __name__ == "__main__":
    unittest.main()
