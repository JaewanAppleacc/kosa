"""ID 2층 분리·Lineage·검토 대기열 테스트 — A 지시 §5·§10."""

from __future__ import annotations

import unittest

from src.data_sources.academyinfo_identity import (
    build_lineage,
    build_resolution_review_queue,
    generate_source_record_id,
    retention_stats,
)


def dept(dept_id: str, mjr_id: str, **over) -> dict:
    base = {
        "department_id": dept_id,
        "source_schl_mjr_id": mjr_id,
        "source_record_id": generate_source_record_id("0000149", mjr_id, 2025),
        "university_name": "테스트대학교",
        "department_name": "컴퓨터공학과",
        "college_name": "공과대학",
        "department_status": "EXISTING",
        "enrolled_count": 0,
        "graduate_count": 0,
        "lesson_term_name": "4년",
    }
    base.update(over)
    return base


class SourceRecordIdTest(unittest.TestCase):
    def test_is_deterministic(self) -> None:
        a = generate_source_record_id("0000149", "0012796", 2025)
        b = generate_source_record_id("0000149", "0012796", 2025)
        self.assertEqual(a, b)

    def test_year_changes_the_id(self) -> None:
        """원본 행 식별자에는 연도가 들어간다 — 연도마다 새로 생기는 것이 정상이다."""
        self.assertNotEqual(
            generate_source_record_id("0000149", "0012796", 2025),
            generate_source_record_id("0000149", "0012796", 2024),
        )

    def test_different_department_differs(self) -> None:
        self.assertNotEqual(
            generate_source_record_id("0000149", "0012796", 2025),
            generate_source_record_id("0000149", "0012797", 2025),
        )

    def test_whitespace_is_normalized(self) -> None:
        self.assertEqual(
            generate_source_record_id(" 0000149 ", " 0012796 ", " 2025 "),
            generate_source_record_id("0000149", "0012796", "2025"),
        )


class LineageTest(unittest.TestCase):
    def test_stable_when_both_ids_match(self) -> None:
        cur = [dept("d1", "m1")]
        prev = [dept("d1", "m1")]
        self.assertEqual(build_lineage(cur, prev)[0]["status"], "STABLE")

    def test_schl_mjr_id_change_is_detected(self) -> None:
        """같은 학과인데 원본 행 id가 바뀐 경우 — schlMjrId를 department_id로 쓰면 안 되는 이유."""
        rows = build_lineage([dept("d1", "m2")], [dept("d1", "m1")])
        self.assertEqual(rows[0]["status"], "SCHL_MJR_ID_CHANGED")
        self.assertEqual(rows[0]["previous_schl_mjr_ids"], ["m1"])

    def test_new_department_marked(self) -> None:
        self.assertEqual(build_lineage([dept("d2", "m9")], [dept("d1", "m1")])[0]["status"], "NEW_IN_LATEST")

    def test_disappeared_department_is_not_dropped(self) -> None:
        """직전 연도에만 있던 학과가 조용히 사라지면 폐지·개칭을 추적할 수 없다."""
        rows = build_lineage([dept("d1", "m1")], [dept("d1", "m1"), dept("dGone", "mG")])
        gone = [r for r in rows if r["department_id"] == "dGone"]
        self.assertEqual(len(gone), 1)
        self.assertEqual(gone[0]["status"], "MISSING_IN_LATEST")
        self.assertIsNone(gone[0]["latest_schl_mjr_id"])


class RetentionTest(unittest.TestCase):
    def test_retention_rate_over_matched_only(self) -> None:
        lineage = build_lineage(
            [dept("d1", "m1"), dept("d2", "m2b"), dept("d3", "mNew")],
            [dept("d1", "m1"), dept("d2", "m2a")],
        )
        s = retention_stats(lineage)
        self.assertEqual((s["stable"], s["schl_mjr_id_changed"], s["new_in_latest"]), (1, 1, 1))
        self.assertEqual(s["schl_mjr_id_retention_rate"], 0.5, "신설 학과는 유지율 분모에서 뺀다")

    def test_no_match_gives_none_not_zero(self) -> None:
        s = retention_stats(build_lineage([dept("d1", "m1")], []))
        self.assertIsNone(s["schl_mjr_id_retention_rate"], "0%와 '계산 불가'는 다르다")


class ReviewQueueTest(unittest.TestCase):
    def test_single_row_is_not_queued(self) -> None:
        self.assertEqual(build_resolution_review_queue([dept("d1", "m1")]), [])

    def test_duplicates_are_all_kept(self) -> None:
        """자동으로 한 행만 남기지 않는다 — 후보 전부를 보여주고 사람이 고른다."""
        q = build_resolution_review_queue(
            [dept("d1", "m1", enrolled_count=85), dept("d1", "m2"), dept("d1", "m3", department_status="ABOLISHED")]
        )
        self.assertEqual(len(q), 1)
        self.assertEqual(q[0]["candidate_count"], 3)
        self.assertEqual(len(q[0]["candidates"]), 3)
        self.assertEqual(q[0]["review_status"], "REVIEW_REQUIRED")

    def test_new_department_with_zero_students_is_preserved(self) -> None:
        """재학생 0명이라고 버리면 신설 학과가 사라진다."""
        q = build_resolution_review_queue(
            [dept("d1", "m1", enrolled_count=85), dept("d1", "m2", department_status="NEW", enrolled_count=0)]
        )
        counts = [c["enrolled_count"] for c in q[0]["candidates"]]
        self.assertIn(0, counts)


if __name__ == "__main__":
    unittest.main()
