"""MajorExplorationService(§18) 테스트 — 학과 탐색 1단계 통합.

검사 답변 → Career Profile → 대표 전공 추천 → 실제 DepartmentRepository 조회 →
그 대표 전공과 연결된 학과 목록, 이라는 Vertical Slice 중 마지막 두 단계를 다룬다.
Repository는 Fake로 대체해 실제 JSONL 파일이나 네트워크에 의존하지 않는다.
"""

from __future__ import annotations

import unittest

from src.schemas.major import Department
from src.schemas.mcp_contracts import DepartmentSearchCriteria
from src.services.major_exploration_service import (
    DEFAULT_DEPARTMENT_LIMIT,
    MajorExplorationService,
    VISIBLE_DEPARTMENT_STATUSES,
)


def _dept(
    department_id: str,
    *,
    university_name: str = "테스트대학교",
    campus: str | None = None,
    region: str = "서울",
    department_name: str = "테스트학과",
    department_status: str = "EXISTING",
    canonical_major_id: str | None = "computer_science",
) -> Department:
    return Department(
        department_id=department_id,
        university_name=university_name,
        campus=campus,
        region=region,
        department_name=department_name,
        college_name="테스트대학",
        admission_unit=None,
        department_status=department_status,
        source_svy_year=2025,
        source_url="https://example.test/dept",
        canonical_major_id=canonical_major_id,
    )


class _FakeDepartmentRepository:
    """DepartmentRepository Protocol을 만족하는 테스트용 대역 — 실제 JSONL을 읽지 않는다.
    실제 JsonlDepartmentRepository와 동일하게, canonical_major_id 필터가 주어지면
    정확히 일치하는 것만 통과시킨다(None인 학과는 항상 걸러진다)."""

    def __init__(self, departments: list[Department]) -> None:
        self._departments = departments

    def search(self, criteria: DepartmentSearchCriteria, limit: int = 30) -> list[Department]:
        matched = [
            d for d in self._departments
            if not criteria.canonical_major_id or d.canonical_major_id == criteria.canonical_major_id
        ]
        return matched[:limit]

    def get(self, department_id: str) -> Department | None:
        return next((d for d in self._departments if d.department_id == department_id), None)


class MajorExplorationServiceTest(unittest.TestCase):
    def test_returns_only_departments_linked_to_the_requested_major(self) -> None:
        repo = _FakeDepartmentRepository(
            [
                _dept("d1", canonical_major_id="computer_science"),
                _dept("d2", canonical_major_id="psychology"),
                _dept("d3", canonical_major_id="computer_science"),
            ]
        )
        service = MajorExplorationService(repo)
        result = service.list_departments_for_major("computer_science")
        self.assertEqual({d.department_id for d in result}, {"d1", "d3"})

    def test_all_returned_canonical_major_id_match_requested_major_id(self) -> None:
        repo = _FakeDepartmentRepository(
            [
                _dept("d1", canonical_major_id="computer_science"),
                _dept("d2", canonical_major_id="psychology"),
            ]
        )
        service = MajorExplorationService(repo)
        result = service.list_departments_for_major("computer_science")
        for d in result:
            self.assertEqual(d.canonical_major_id, "computer_science")

    def test_departments_with_no_canonical_major_id_are_excluded(self) -> None:
        repo = _FakeDepartmentRepository(
            [
                _dept("d1", canonical_major_id="computer_science"),
                _dept("d2", canonical_major_id=None),  # REVIEW_REQUIRED — 아직 미확정 Mapping
            ]
        )
        service = MajorExplorationService(repo)
        result = service.list_departments_for_major("computer_science")
        self.assertEqual({d.department_id for d in result}, {"d1"})

    def test_abolished_merged_split_are_excluded(self) -> None:
        repo = _FakeDepartmentRepository(
            [
                _dept("d1", department_status="EXISTING"),
                _dept("d2", department_status="NEW"),
                _dept("d3", department_status="ABOLISHED"),
                _dept("d4", department_status="MERGED"),
                _dept("d5", department_status="SPLIT"),
            ]
        )
        service = MajorExplorationService(repo)
        result = service.list_departments_for_major("computer_science")
        self.assertEqual({d.department_id for d in result}, {"d1", "d2"})
        for d in result:
            self.assertIn(d.department_status, VISIBLE_DEPARTMENT_STATUSES)

    def test_result_is_capped_at_limit(self) -> None:
        repo = _FakeDepartmentRepository(
            [_dept(f"d{i}", department_name=f"학과{i:02d}") for i in range(50)]
        )
        service = MajorExplorationService(repo)
        result = service.list_departments_for_major("computer_science")
        self.assertEqual(len(result), DEFAULT_DEPARTMENT_LIMIT)

        result_custom_limit = service.list_departments_for_major("computer_science", limit=5)
        self.assertEqual(len(result_custom_limit), 5)

    def test_sort_order_is_deterministic_region_then_university_then_campus_then_department(
        self,
    ) -> None:
        repo = _FakeDepartmentRepository(
            [
                _dept("d1", region="부산", university_name="B대", department_name="가"),
                _dept("d2", region="서울", university_name="Z대", department_name="가"),
                _dept("d3", region="서울", university_name="A대", campus="분교", department_name="나"),
                _dept("d4", region="서울", university_name="A대", campus="본교", department_name="가"),
                _dept("d5", region="서울", university_name="A대", campus="본교", department_name="다"),
            ]
        )
        service = MajorExplorationService(repo)
        result_ids = [d.department_id for d in service.list_departments_for_major("computer_science")]
        # region 오름차순("부산" < "서울") 먼저, 그다음 서울 안에서 university_name
        # ("A대" < "Z대"), A대 안에서 campus("본교" < "분교"), 본교 안에서 department_name
        # ("가" < "다").
        self.assertEqual(result_ids, ["d1", "d4", "d5", "d3", "d2"])

        # 같은 요청은 항상 같은 순서를 반환한다(무작위 요소 없음).
        result_ids_again = [
            d.department_id for d in service.list_departments_for_major("computer_science")
        ]
        self.assertEqual(result_ids, result_ids_again)

    def test_empty_result_for_unmapped_major_is_an_empty_list(self) -> None:
        repo = _FakeDepartmentRepository([_dept("d1", canonical_major_id="computer_science")])
        service = MajorExplorationService(repo)
        result = service.list_departments_for_major("no_such_major")
        self.assertEqual(result, [])

    def test_empty_major_id_returns_empty_list_without_leaking_unrelated_departments(self) -> None:
        """빈 문자열은 Repository 쪽 필터에서 "필터 없음"으로 해석될 수 있으므로, Service가
        먼저 막아 무관한 학과가 새어나가지 않게 해야 한다."""

        repo = _FakeDepartmentRepository(
            [_dept("d1", canonical_major_id="computer_science"), _dept("d2", canonical_major_id="psychology")]
        )
        service = MajorExplorationService(repo)
        self.assertEqual(service.list_departments_for_major(""), [])

    def test_fake_repository_can_be_injected(self) -> None:
        """DI 확인: MajorExplorationService는 DepartmentRepository Protocol만 참조하므로
        실제 JsonlDepartmentRepository 없이도 완전히 동작해야 한다."""

        repo = _FakeDepartmentRepository([_dept("d1")])
        service = MajorExplorationService(repo)
        self.assertEqual(len(service.list_departments_for_major("computer_science")), 1)


if __name__ == "__main__":
    unittest.main()
