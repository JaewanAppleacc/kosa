"""department_repository / admission_repository / admission_filter 계약 테스트."""

from __future__ import annotations

import unittest

from src.engines.admission_filter import (
    ComparabilityViolation,
    assert_single_group,
    comparability_group_of,
    derive_comparability_group,
    group_by_comparability,
    select_group,
    sort_within_group,
    validate_group_field,
    verified_only,
)
from src.repositories.admission_repository import JsonlAdmissionRepository
from src.repositories.department_repository import (
    JsonlDepartmentRepository,
    departments_missing_canonical_major,
)
from src.schemas.mcp_contracts import AdmissionSearchCriteria, DepartmentSearchCriteria
from tests.worker_c.fixtures import admission_reference, department


class DepartmentRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = JsonlDepartmentRepository(
            [
                department("dept_a", "서울대학교", "컴퓨터공학부", "공과대학", canonical_major_id="computer_science"),
                department("dept_b", "연세대학교", "컴퓨터과학과", "공과대학", canonical_major_id="computer_science"),
                department("dept_c", "부산대학교", "교육학과", "사범대학", region="부산", canonical_major_id="education"),
                department("dept_d", "충남대학교", "자유전공학부", "자유전공학부", region="대전"),
            ]
        )

    def test_get_returns_none_for_unknown_id(self) -> None:
        self.assertIsNone(self.repository.get("dept_없음"))
        self.assertIsNotNone(self.repository.get("dept_a"))

    def test_search_by_university_ignores_spacing(self) -> None:
        found = self.repository.search(DepartmentSearchCriteria(university_name="서울 대학교"))
        self.assertEqual([d.department_id for d in found], ["dept_a"])

    def test_search_by_partial_department_name(self) -> None:
        found = self.repository.search(DepartmentSearchCriteria(department_name_query="컴퓨터"))
        self.assertEqual({d.department_id for d in found}, {"dept_a", "dept_b"})

    def test_search_by_region_is_exact(self) -> None:
        self.assertEqual(
            [d.department_id for d in self.repository.search(DepartmentSearchCriteria(region="부산"))],
            ["dept_c"],
        )
        self.assertEqual(self.repository.search(DepartmentSearchCriteria(region="부")), [])

    def test_unmapped_department_never_matches_canonical_major_filter(self) -> None:
        """canonical_major_id가 없는 학과(=Mapping 미확정)는 어떤 전공 필터에도 걸리면 안 된다."""

        for major_id in ("computer_science", "education", "design"):
            found = self.repository.search(DepartmentSearchCriteria(canonical_major_id=major_id))
            self.assertNotIn("dept_d", [d.department_id for d in found])

    def test_search_order_is_stable(self) -> None:
        first = self.repository.search(DepartmentSearchCriteria())
        second = self.repository.search(DepartmentSearchCriteria())
        self.assertEqual([d.department_id for d in first], [d.department_id for d in second])

    def test_limit_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            self.repository.search(DepartmentSearchCriteria(), limit=0)

    def test_missing_canonical_major_list(self) -> None:
        self.assertEqual(
            [d.department_id for d in departments_missing_canonical_major(self.repository)],
            ["dept_d"],
        )


class AdmissionFilterTest(unittest.TestCase):
    def test_group_is_derived_from_four_axes(self) -> None:
        self.assertEqual(
            derive_comparability_group(2025, "정시", "나군", "백분위 70%컷"),
            "2025|정시|나군|백분위 70%컷",
        )

    def test_blank_axis_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            derive_comparability_group(2025, "정시", "  ", "백분위 70%컷")

    def test_validate_group_field_catches_typo(self) -> None:
        reference = admission_reference().model_copy(update={"data_comparability_group": "2025|정시"})
        problems = validate_group_field([reference])
        self.assertEqual(len(problems), 1)
        self.assertIn("파생값", problems[0])

    def test_assert_single_group_rejects_mixed(self) -> None:
        mixed = [admission_reference(), admission_reference(admission_year=2024)]
        with self.assertRaises(ComparabilityViolation):
            assert_single_group(mixed)

    def test_select_group_prefers_latest_year(self) -> None:
        rows = [
            admission_reference(admission_year=2024),
            admission_reference(department_id="dept_x", admission_year=2024),
            admission_reference(admission_year=2025),
        ]
        name, selected = select_group(rows)
        self.assertTrue(name.startswith("2025"))
        self.assertEqual(len(selected), 1)
        assert_single_group(selected)

    def test_select_group_honours_explicit_group(self) -> None:
        rows = [admission_reference(), admission_reference(admission_year=2024)]
        wanted = comparability_group_of(rows[1])
        name, selected = select_group(rows, preferred_group=wanted)
        self.assertEqual(name, wanted)
        self.assertEqual([r.admission_year for r in selected], [2024])

    def test_group_by_comparability_splits(self) -> None:
        rows = [admission_reference(), admission_reference(admission_type="수시")]
        self.assertEqual(len(group_by_comparability(rows)), 2)

    def test_sort_within_group_refuses_mixed_and_puts_none_last(self) -> None:
        with self.assertRaises(ComparabilityViolation):
            sort_within_group([admission_reference(), admission_reference(admission_year=2024)])

        rows = [
            admission_reference(department_id="d1", score_70_cut=None),
            admission_reference(department_id="d2", score_70_cut=90.0),
            admission_reference(department_id="d3", score_70_cut=97.0),
        ]
        ordered = sort_within_group(rows)
        self.assertEqual([r.department_id for r in ordered], ["d3", "d2", "d1"])

    def test_verified_only_drops_draft(self) -> None:
        rows = [admission_reference(), admission_reference(department_id="d2", review_status="draft")]
        self.assertEqual([r.department_id for r in verified_only(rows)], ["dept_test_001"])


class AdmissionRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = JsonlAdmissionRepository(
            [
                admission_reference(department_id="dept_a", admission_year=2025),
                admission_reference(department_id="dept_a", admission_year=2024),
                admission_reference(department_id="dept_a", admission_type="수시", admission_track="교과"),
                admission_reference(department_id="dept_b", admission_year=2025),
            ]
        )

    def test_find_comparable_returns_single_group_only(self) -> None:
        rows = self.repository.find_comparable(AdmissionSearchCriteria(department_id="dept_a"))
        self.assertTrue(rows)
        assert_single_group(rows)

    def test_find_comparable_groups_keeps_groups_separate(self) -> None:
        grouped = self.repository.find_comparable_groups(
            AdmissionSearchCriteria(department_id="dept_a")
        )
        self.assertEqual(len(grouped), 3)
        for rows in grouped.values():
            assert_single_group(rows)

    def test_year_filter(self) -> None:
        rows = self.repository.find_comparable(
            AdmissionSearchCriteria(department_id="dept_a", admission_year=2024)
        )
        self.assertEqual([r.admission_year for r in rows], [2024])

    def test_unknown_department_is_distinguishable_from_empty(self) -> None:
        self.assertFalse(self.repository.has_department("dept_없음"))
        self.assertTrue(self.repository.has_department("dept_a"))
        self.assertEqual(
            self.repository.find_comparable(AdmissionSearchCriteria(department_id="dept_없음")), []
        )

    def test_available_groups_is_sorted(self) -> None:
        groups = self.repository.available_groups("dept_a")
        self.assertEqual(groups, sorted(groups))
        self.assertEqual(len(groups), 3)


if __name__ == "__main__":
    unittest.main()
