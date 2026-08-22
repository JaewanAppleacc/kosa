"""Education Data MCP Server — 8개 Tool의 계약과 4가지 상태 구분."""

from __future__ import annotations

import unittest

from src.mcp.education_server import TOOL_REGISTRY, EducationDataServer, call_tool
from src.repositories.admission_repository import JsonlAdmissionRepository
from src.repositories.department_repository import JsonlDepartmentRepository
from src.schemas.course import SubjectProfile
from src.schemas.mcp_contracts import (
    AdmissionSearchCriteria,
    CareerNetMajorSummary,
    DepartmentSearchCriteria,
    GetCareerMajorInput,
    GetDepartmentInput,
    SearchAdmissionReferencesInput,
    SearchCareerMajorInput,
    SearchDepartmentRagInput,
    SearchDepartmentsInput,
    SearchHighSchoolSubjectInput,
    SearchUniversityInput,
    UniversitySummary,
)
from tests.worker_c.fixtures import admission_reference, department

CAREER_MAJORS = [
    CareerNetMajorSummary(
        career_net_major_id="cnet_cs",
        label="컴퓨터공학",
        summary="소프트웨어와 알고리즘을 다룬다.",
        source_url="https://www.career.go.kr/",
    )
]
UNIVERSITIES = [
    UniversitySummary(schl_id="u1", name="서울대학교", region="서울", establishment_type="국립"),
    UniversitySummary(schl_id="u2", name="부산대학교", region="부산", establishment_type="국립"),
]
SUBJECTS = [
    SubjectProfile(
        subject_id="subj_1",
        label="정보",
        trait_vector={"tool_utilization": 1.0},
        related_major_ids=["computer_science"],
        source_id="https://ncic.re.kr/",
    )
]


def build_server(**overrides) -> EducationDataServer:
    defaults = dict(
        department_repository=JsonlDepartmentRepository(
            [department("dept_a", "서울대학교", "컴퓨터공학부", "공과대학", canonical_major_id="computer_science")]
        ),
        admission_repository=JsonlAdmissionRepository(
            [
                admission_reference(department_id="dept_a", admission_year=2025),
                admission_reference(department_id="dept_a", admission_year=2024),
            ]
        ),
        retriever=None,
        career_majors=CAREER_MAJORS,
        universities=UNIVERSITIES,
        subjects=SUBJECTS,
    )
    defaults.update(overrides)
    return EducationDataServer(**defaults)


class ToolContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.server = build_server()

    def test_registry_covers_eight_tools(self) -> None:
        self.assertEqual(len(TOOL_REGISTRY), 8)

    def test_search_career_major_ok_and_empty(self) -> None:
        ok = self.server.search_career_major(SearchCareerMajorInput(query="컴퓨터"))
        self.assertEqual(ok.status, "ok")
        self.assertEqual(len(ok.data), 1)

        empty = self.server.search_career_major(SearchCareerMajorInput(query="해양생물"))
        self.assertEqual(empty.status, "empty")
        self.assertEqual(empty.data, [])

    def test_blank_query_is_error_not_empty(self) -> None:
        result = self.server.search_career_major(SearchCareerMajorInput(query="  "))
        self.assertEqual(result.status, "error")
        self.assertTrue(result.error_message)

    def test_source_missing_when_dataset_not_loaded(self) -> None:
        server = build_server(career_majors=[])
        result = server.get_career_major(GetCareerMajorInput(career_net_major_id="cnet_cs"))
        self.assertEqual(result.status, "source_missing")
        self.assertIn("career_net_majors", result.error_message or "")

    def test_search_university(self) -> None:
        by_region = self.server.search_university(SearchUniversityInput(query="부산"))
        self.assertEqual(by_region.status, "ok")
        self.assertEqual(by_region.data[0].schl_id, "u2")

    def test_search_departments_and_get_department(self) -> None:
        found = self.server.search_departments(
            SearchDepartmentsInput(criteria=DepartmentSearchCriteria(department_name_query="컴퓨터"))
        )
        self.assertEqual(found.status, "ok")

        one = self.server.get_department(GetDepartmentInput(department_id="dept_a"))
        self.assertEqual(one.status, "ok")

        missing = self.server.get_department(GetDepartmentInput(department_id="dept_없음"))
        self.assertEqual(missing.status, "empty")

    def test_invalid_limit_is_error(self) -> None:
        result = self.server.search_departments(
            SearchDepartmentsInput(criteria=DepartmentSearchCriteria(), limit=0)
        )
        self.assertEqual(result.status, "error")

    def test_admission_returns_one_comparability_group(self) -> None:
        result = self.server.search_admission_references(
            SearchAdmissionReferencesInput(criteria=AdmissionSearchCriteria(department_id="dept_a"))
        )
        self.assertEqual(result.status, "ok")
        self.assertEqual(len({r.data_comparability_group for r in result.data}), 1)

    def test_admission_for_uncollected_department_is_source_missing(self) -> None:
        """자료를 아직 안 모은 학과는 'empty'가 아니라 'source_missing'이다."""

        result = self.server.search_admission_references(
            SearchAdmissionReferencesInput(criteria=AdmissionSearchCriteria(department_id="dept_b"))
        )
        self.assertEqual(result.status, "source_missing")

    def test_admission_with_no_matching_year_is_empty(self) -> None:
        result = self.server.search_admission_references(
            SearchAdmissionReferencesInput(
                criteria=AdmissionSearchCriteria(department_id="dept_a", admission_year=1999)
            )
        )
        self.assertEqual(result.status, "empty")

    def test_rag_without_index_is_source_missing(self) -> None:
        result = self.server.search_department_rag(SearchDepartmentRagInput(query="졸업요건"))
        self.assertEqual(result.status, "source_missing")

    def test_high_school_subject_search(self) -> None:
        ok = self.server.search_high_school_subject(SearchHighSchoolSubjectInput(query="정보"))
        self.assertEqual(ok.status, "ok")

        by_major = self.server.search_high_school_subject(
            SearchHighSchoolSubjectInput(query="computer_science")
        )
        self.assertEqual(by_major.status, "ok")

        empty = self.server.search_high_school_subject(SearchHighSchoolSubjectInput(query="체육"))
        self.assertEqual(empty.status, "empty")


class CallToolTest(unittest.TestCase):
    def setUp(self) -> None:
        self.server = build_server()

    def test_unknown_tool_name_is_error(self) -> None:
        result = call_tool(self.server, "search_everything", {})
        self.assertEqual(result.status, "error")

    def test_input_validation_failure_is_wrapped_as_error(self) -> None:
        result = call_tool(self.server, "get_department", {"wrong_field": 1})
        self.assertEqual(result.status, "error")
        self.assertIn("입력 검증 실패", result.error_message or "")

    def test_valid_call_by_name(self) -> None:
        result = call_tool(self.server, "get_department", {"department_id": "dept_a"})
        self.assertEqual(result.status, "ok")


if __name__ == "__main__":
    unittest.main()
