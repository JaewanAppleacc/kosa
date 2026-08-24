"""career_build_national_master_promotion_candidates.py 테스트 —
a/final-integration-master-promotion §6."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.career_build_national_master_promotion_candidates import (  # noqa: E402
    build_candidate_row,
    build_report,
    main,
)

_SCRIPT = ROOT / "scripts" / "career_build_national_master_promotion_candidates.py"


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def _dry_run_row(
    offering_id: str, *, university_name: str = "테스트대학교", canonical_major_id: str = "computer_science",
    old_department_id: str = "dept_old_1",
) -> dict:
    return {
        "offering_id": offering_id, "display_group_id": f"dgrp_{offering_id}", "old_department_id": old_department_id,
        "university_name": university_name, "department_name": "컴퓨터공학과", "college_name": "공과대학",
        "department_status": "EXISTING", "survey_year": 2025, "resolved_canonical_major_id": canonical_major_id,
        "resolved_department_url": None, "status": "READY_FOR_PROMOTION", "blocked_reasons": [],
    }


class BuildCandidateRowTest(unittest.TestCase):
    def test_row_shape_matches_department_like_fields(self) -> None:
        row = build_candidate_row(_dry_run_row("off_1"))
        self.assertEqual(row["offering_id"], "off_1")
        self.assertEqual(row["canonical_major_id"], "computer_science")
        self.assertNotIn("status", row)
        self.assertNotIn("blocked_reasons", row)


class BuildReportTest(unittest.TestCase):
    def test_report_counts_and_no_duplicate(self) -> None:
        candidates = [build_candidate_row(_dry_run_row(f"off_{i}")) for i in range(3)]
        report = build_report(
            candidates=candidates, existing_master=[{"department_id": "dept_old_99"}],
            dry_run_summary={"blocked_reason_counts": {}}, survey_year=2025,
        )
        self.assertEqual(report["new_candidate_row_count"], 3)
        self.assertEqual(report["existing_master_row_count"], 1)
        self.assertEqual(report["duplicate_offering_id_count"], 0)
        self.assertEqual(report["candidates_sharing_existing_master_display_group_count"], 0)

    def test_report_flags_duplicate_offering_ids(self) -> None:
        candidates = [build_candidate_row(_dry_run_row("off_1")), build_candidate_row(_dry_run_row("off_1"))]
        report = build_report(
            candidates=candidates, existing_master=[], dry_run_summary={"blocked_reason_counts": {}}, survey_year=2025,
        )
        self.assertEqual(report["duplicate_offering_id_count"], 1)
        self.assertEqual(report["duplicate_offering_ids"], ["off_1"])

    def test_report_flags_shared_display_group_with_existing_master_for_audit_only(self) -> None:
        candidates = [build_candidate_row(_dry_run_row("off_1", old_department_id="dept_shared"))]
        report = build_report(
            candidates=candidates, existing_master=[{"department_id": "dept_shared"}],
            dry_run_summary={"blocked_reason_counts": {}}, survey_year=2025,
        )
        self.assertEqual(report["candidates_sharing_existing_master_display_group_count"], 1)
        self.assertEqual(report["candidates_sharing_existing_master_display_group"], ["off_1"])


class NeverTouchesRealMasterTest(unittest.TestCase):
    def test_main_never_writes_to_real_master_path(self) -> None:
        """`data/master/departments.jsonl`을 읽기만 하고 절대 쓰지 않는다 — tmp
        data-dir로 실행해도 이 스크립트 코드 어디에도 그 경로에 대한 쓰기 호출이
        없다는 사실을 실제 실행으로 확인한다(간접 검증: tmp master 파일의 mtime/
        내용이 실행 전후로 완전히 같다)."""

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            master_path = root / "master" / "departments.jsonl"
            _write_jsonl(master_path, [{"department_id": "dept_x", "university_name": "X"}])
            before = master_path.read_bytes()

            dry_run_dir = root / "academyinfo_work" / "2025" / "promotion_dry_run"
            _write_jsonl(dry_run_dir / "promotion_candidates.jsonl", [_dry_run_row("off_1")])
            (dry_run_dir / "promotion_summary.json").write_text(
                json.dumps({"ready_for_promotion_count": 1, "blocked_reason_counts": {}}), encoding="utf-8",
            )

            code = main(["--survey-year", "2025", "--data-dir", str(root)])
            self.assertEqual(code, 0)
            after = master_path.read_bytes()
            self.assertEqual(before, after, "실제(tmp) Master 파일이 변경됐다")

    def test_zero_ready_exits_2_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_jsonl(root / "master" / "departments.jsonl", [])
            dry_run_dir = root / "academyinfo_work" / "2025" / "promotion_dry_run"
            _write_jsonl(dry_run_dir / "promotion_candidates.jsonl", [])
            (dry_run_dir / "promotion_summary.json").write_text(
                json.dumps({"ready_for_promotion_count": 0, "blocked_reason_counts": {}}), encoding="utf-8",
            )
            code = main(["--survey-year", "2025", "--data-dir", str(root)])
            self.assertEqual(code, 2)
            self.assertFalse((dry_run_dir / "national_master_promotion_candidates.jsonl").exists())


class DeterminismTest(unittest.TestCase):
    def test_two_runs_produce_identical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_jsonl(root / "master" / "departments.jsonl", [{"department_id": "dept_old_1"}])
            dry_run_dir = root / "academyinfo_work" / "2025" / "promotion_dry_run"
            _write_jsonl(
                dry_run_dir / "promotion_candidates.jsonl",
                [_dry_run_row("off_1"), _dry_run_row("off_2", university_name="다른대학교")],
            )
            (dry_run_dir / "promotion_summary.json").write_text(
                json.dumps({"ready_for_promotion_count": 2, "blocked_reason_counts": {"BLOCKED_ARTS_RECOMMENDATION": 1}}),
                encoding="utf-8",
            )

            def _run(output_dir: Path) -> None:
                result = subprocess.run(
                    [
                        sys.executable, str(_SCRIPT), "--survey-year", "2025", "--data-dir", str(root),
                        "--output-dir", str(output_dir),
                    ],
                    cwd=ROOT, capture_output=True, text=True, timeout=60,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            out1, out2 = root / "run1", root / "run2"
            _run(out1)
            _run(out2)
            for name in (
                "national_master_promotion_candidates.jsonl", "national_master_promotion_report.json",
                "national_master_promotion_report.md",
            ):
                self.assertEqual((out1 / name).read_bytes(), (out2 / name).read_bytes(), name)


if __name__ == "__main__":
    unittest.main()
