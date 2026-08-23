"""수집기 테스트 — 지시서 §11 (Resume·중복·결정론·원본 보존).

실제 네트워크 없이 Fake transport로 전 구간을 돈다.
"""

from __future__ import annotations

import gzip
import tempfile
import unittest
from pathlib import Path
from typing import Any

from scripts.career_collect_academyinfo_departments import (
    Paths,
    collect_departments,
    load_checkpoint,
    read_jsonl_gz,
    split_bulk_text,
    write_jsonl_gz,
)
from src.data_sources.academyinfo_client import AcademyInfoClient, RetryPolicy

FAKE_KEY = "fake/key+=="


def _envelope(items_xml: str, total: int) -> str:
    return (
        "<response><header><resultCode>00</resultCode><resultMsg>OK</resultMsg></header>"
        f"<body><items>{items_xml}</items><numOfRows>100</numOfRows>"
        f"<pageNo>1</pageNo><totalCount>{total}</totalCount></body></response>"
    )


def _dept_xml(schl_id: str, mjr_id: str, curriculum: str = "과목A|과목B") -> str:
    return (
        f"<item><schlId>{schl_id}</schlId><schlMjrId>{mjr_id}</schlMjrId>"
        f"<korMjrNm>학과{mjr_id}</korMjrNm><korSchlNm>테스트대학교</korSchlNm>"
        f"<edcCrseLtrCtnt>{curriculum}</edcCrseLtrCtnt><svyYr>2025</svyYr></item>"
    )


class ScriptedTransport:
    """schlId별 응답을 미리 정해 둔다. 특정 대학만 실패시킬 수 있다."""

    def __init__(self, per_school: dict[str, str], fail_for: set[str] | None = None) -> None:
        self.per_school = per_school
        self.fail_for = fail_for or set()
        self.requested: list[str] = []

    def __call__(self, url: str, params: dict[str, Any]) -> tuple[int, str]:
        sid = str(params.get("schlId", ""))
        self.requested.append(sid)
        if sid in self.fail_for:
            return 200, "<response><header><resultCode>99</resultCode><resultMsg>UNKNOWN</resultMsg></header><body/></response>"
        return 200, self.per_school.get(sid, _envelope("", 0))


def _client(transport: Any) -> AcademyInfoClient:
    return AcademyInfoClient(
        FAKE_KEY,
        transport=transport,
        retry=RetryPolicy(max_attempts=2, base_delay_s=0),
        sleep=lambda _s: None,
    )


class BulkTextSplitTest(unittest.TestCase):
    """교과목 전문 분리 — 원본을 버리지 않고 옮긴다."""

    def test_curriculum_is_moved_out_with_hash_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "academyinfo_raw" / "2025"
            row = {"schlMjrId": "0012796", "edcCrseLtrCtnt": "과목A|과목B|과목C"}
            out = split_bulk_text(row, root / "curricula", "0012796")

            self.assertNotIn("edcCrseLtrCtnt", out, "본 레코드에서 전문이 빠져야 한다")
            self.assertEqual(out["edcCrseLtrCtnt__len"], len("과목A|과목B|과목C"))
            self.assertEqual(len(out["edcCrseLtrCtnt__sha256"]), 64)

            saved = root / "curricula" / "0012796.txt.gz"
            self.assertTrue(saved.exists(), "전문은 별도 파일로 보존돼야 한다")
            with gzip.open(saved, "rt", encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "과목A|과목B|과목C", "원문이 손실 없이 복원돼야 한다")

    def test_empty_curriculum_is_recorded_as_zero_not_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = split_bulk_text({"schlMjrId": "x"}, Path(tmp) / "curricula", "x")
            self.assertIsNone(out["edcCrseLtrCtnt__sha256"])
            self.assertEqual(out["edcCrseLtrCtnt__len"], 0)


class DeterminismTest(unittest.TestCase):
    def test_same_input_produces_identical_bytes(self) -> None:
        """§4: 같은 원본·옵션이면 재생성 결과가 Byte-identical해야 한다."""
        rows = [{"b": "2", "a": "1"}, {"a": "3", "b": "4"}]
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "a.jsonl.gz"
            second = Path(tmp) / "b.jsonl.gz"
            write_jsonl_gz(first, rows)
            write_jsonl_gz(second, rows)
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_round_trip_preserves_rows(self) -> None:
        rows = [{"schlMjrId": "1", "korMjrNm": "컴퓨터공학과"}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "r.jsonl.gz"
            write_jsonl_gz(path, rows)
            self.assertEqual(read_jsonl_gz(path), rows)


class CollectDepartmentsTest(unittest.TestCase):
    def _paths(self, tmp: str) -> Paths:
        return Paths.for_year(2025, Path(tmp))

    def test_collects_all_schools(self) -> None:
        transport = ScriptedTransport(
            {
                "S1": _envelope(_dept_xml("S1", "M1") + _dept_xml("S1", "M2"), 2),
                "S2": _envelope(_dept_xml("S2", "M3"), 1),
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._paths(tmp)
            count, failed = collect_departments(
                _client(transport), paths, 2025, ["S1", "S2"], dry_run=False, resume=False
            )
            self.assertEqual((count, failed), (3, 0))
            self.assertEqual(len(read_jsonl_gz(paths.departments)), 3)

    def test_checkpoint_written_per_school(self) -> None:
        transport = ScriptedTransport({"S1": _envelope(_dept_xml("S1", "M1"), 1)})
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._paths(tmp)
            collect_departments(_client(transport), paths, 2025, ["S1"], dry_run=False, resume=False)
            self.assertEqual(load_checkpoint(paths.checkpoint)["completed_school_ids"], ["S1"])

    def test_resume_skips_completed_schools(self) -> None:
        """중단 후 --resume이 이미 끝낸 대학을 다시 부르지 않아야 한다 (§4)."""
        first = ScriptedTransport({"S1": _envelope(_dept_xml("S1", "M1"), 1)})
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._paths(tmp)
            collect_departments(_client(first), paths, 2025, ["S1"], dry_run=False, resume=False)

            second = ScriptedTransport(
                {"S1": _envelope(_dept_xml("S1", "M1"), 1), "S2": _envelope(_dept_xml("S2", "M2"), 1)}
            )
            count, _ = collect_departments(
                _client(second), paths, 2025, ["S1", "S2"], dry_run=False, resume=True
            )
            self.assertNotIn("S1", second.requested, "완료한 대학을 다시 호출하면 한도만 태운다")
            self.assertEqual(count, 2, "이전 수집분이 유지된 채 이어져야 한다")

    def test_failed_school_is_recorded_and_does_not_stop_collection(self) -> None:
        transport = ScriptedTransport(
            {"S1": _envelope(_dept_xml("S1", "M1"), 1), "S3": _envelope(_dept_xml("S3", "M3"), 1)},
            fail_for={"S2"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._paths(tmp)
            count, failed = collect_departments(
                _client(transport), paths, 2025, ["S1", "S2", "S3"], dry_run=False, resume=False
            )
            self.assertEqual((count, failed), (2, 1))
            self.assertTrue(paths.errors.exists(), "실패 대학은 근거와 함께 남는다")
            self.assertNotIn("S2", load_checkpoint(paths.checkpoint)["completed_school_ids"])

    def test_empty_school_is_not_a_failure(self) -> None:
        """학과가 0건인 대학은 정상이다 — 오류로 세면 실패 수가 부풀려진다."""
        transport = ScriptedTransport({})
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._paths(tmp)
            count, failed = collect_departments(
                _client(transport), paths, 2025, ["S9"], dry_run=False, resume=False
            )
            self.assertEqual((count, failed), (0, 0))

    def test_dry_run_writes_nothing(self) -> None:
        transport = ScriptedTransport({"S1": _envelope(_dept_xml("S1", "M1"), 1)})
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._paths(tmp)
            collect_departments(_client(transport), paths, 2025, ["S1"], dry_run=True, resume=False)
            self.assertFalse(paths.departments.exists())
            self.assertFalse(paths.checkpoint.exists())


if __name__ == "__main__":
    unittest.main()
