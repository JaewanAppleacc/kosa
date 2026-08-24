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
    source_url: str = "https://example.test/dept",
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
        source_url=source_url,
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
        # 2026-08-25 §5: DEFAULT_DEPARTMENT_LIMIT이 30→500으로 올라갔다(전국 학과
        # 1,072건 전환 이후 Major당 최대 271건까지 나온다) — Fixture 크기도 그
        # 한도보다 커야 실제로 잘리는지 확인할 수 있다.
        repo = _FakeDepartmentRepository(
            [_dept(f"d{i}", department_name=f"학과{i:04d}") for i in range(DEFAULT_DEPARTMENT_LIMIT + 50)]
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


class _MisbehavingDepartmentRepository:
    """DepartmentRepository Protocol을 만족하지만, 진짜 JsonlDepartmentRepository와 달리
    검색 조건(criteria)을 완전히 무시하고 가진 것을 전부 돌려준다 — "Repository 구현이
    교체되거나 버그가 있으면"을 재현하는 대역. `search()`가 이 상태를 흉내내면, Service의
    마지막 노출 필터가 실제로 방어막 역할을 하는지 검증할 수 있다(정상 Fake는 이미
    criteria를 지켜서 필터가 있으나 없으나 결과가 같아 보호막을 검증 못 한다)."""

    def __init__(self, departments: list[Department]) -> None:
        self._departments = departments

    def search(self, criteria: DepartmentSearchCriteria, limit: int = 30) -> list[Department]:
        return list(self._departments)[:limit]

    def get(self, department_id: str) -> Department | None:
        return next((d for d in self._departments if d.department_id == department_id), None)


class MajorExplorationServiceDefendsAgainstMisbehavingRepositoryTest(unittest.TestCase):
    """2026-08-22 8차 리뷰: Service가 Repository의 canonical_major_id 필터링을 무조건
    신뢰하지 않고, 노출 직전에 다시 검증하는지 확인한다. 검색 조건을 지키는 정상 Fake
    Repository로는 이 방어 로직 자체를 테스트할 수 없으므로, 일부러 조건을 무시하는
    _MisbehavingDepartmentRepository를 쓴다."""

    def test_wrong_major_department_mixed_in_by_repository_is_excluded(self) -> None:
        repo = _MisbehavingDepartmentRepository(
            [
                _dept("d1", canonical_major_id="computer_science"),
                _dept("d2", canonical_major_id="psychology"),  # Repository가 잘못 섞어 보낸 것
            ]
        )
        service = MajorExplorationService(repo)
        result = service.list_departments_for_major("computer_science")
        self.assertEqual({d.department_id for d in result}, {"d1"})

    def test_canonical_major_id_none_is_excluded_even_if_repository_returns_it(self) -> None:
        repo = _MisbehavingDepartmentRepository(
            [
                _dept("d1", canonical_major_id="computer_science"),
                _dept("d2", canonical_major_id=None),
            ]
        )
        service = MajorExplorationService(repo)
        result = service.list_departments_for_major("computer_science")
        self.assertEqual({d.department_id for d in result}, {"d1"})

    def test_empty_source_url_is_excluded(self) -> None:
        repo = _MisbehavingDepartmentRepository(
            [
                _dept("d1", canonical_major_id="computer_science", source_url="https://real.example/dept"),
                _dept("d2", canonical_major_id="computer_science", source_url=""),
            ]
        )
        service = MajorExplorationService(repo)
        result = service.list_departments_for_major("computer_science")
        self.assertEqual({d.department_id for d in result}, {"d1"})

    def test_whitespace_only_source_url_is_excluded(self) -> None:
        repo = _MisbehavingDepartmentRepository(
            [
                _dept("d1", canonical_major_id="computer_science", source_url="https://real.example/dept"),
                _dept("d2", canonical_major_id="computer_science", source_url="   "),
            ]
        )
        service = MajorExplorationService(repo)
        result = service.list_departments_for_major("computer_science")
        self.assertEqual({d.department_id for d in result}, {"d1"})

    def test_valid_department_with_correct_major_and_source_is_still_returned(self) -> None:
        """방어 필터가 과잉 차단하지 않는지 확인 — 정상 조건을 모두 만족하는 학과는
        Repository가 조건을 지키든 안 지키든 그대로 나와야 한다."""

        repo = _MisbehavingDepartmentRepository(
            [_dept("d1", canonical_major_id="computer_science", source_url="https://real.example/dept")]
        )
        service = MajorExplorationService(repo)
        result = service.list_departments_for_major("computer_science")
        self.assertEqual([d.department_id for d in result], ["d1"])

    def test_status_filter_and_deterministic_sort_still_hold_against_misbehaving_repository(
        self,
    ) -> None:
        repo = _MisbehavingDepartmentRepository(
            [
                _dept("d1", canonical_major_id="computer_science", department_status="ABOLISHED"),
                _dept(
                    "d2", canonical_major_id="computer_science", region="부산", university_name="B대",
                ),
                _dept(
                    "d3", canonical_major_id="computer_science", region="서울", university_name="A대",
                ),
                _dept("d4", canonical_major_id="psychology"),
            ]
        )
        service = MajorExplorationService(repo)
        result = service.list_departments_for_major("computer_science")
        self.assertEqual([d.department_id for d in result], ["d2", "d3"])
        for d in result:
            self.assertIn(d.department_status, VISIBLE_DEPARTMENT_STATUSES)


class AllowedServiceMajorIdFailClosedTest(unittest.TestCase):
    """2026-08-24 national-department-readiness 정합성 수정 §6 — "서비스 Major ID
    허용"·"Group ID 차단"·"design 차단"·"미등록 ID 차단"·"Repository 오작동 시
    Service 방어(Allowlist 방향)". `EXCLUDED_RECOMMENDATION_MAJOR_IDS`(알려진
    나쁜 것만 막기) 하나만으로는 42개 Canonical Major Group ID 같은 "허용 목록에
    없는 새 ID"를 못 막았다 — `allowed_major_ids` Allowlist가 이를 막는지 확인한다."""

    def test_default_service_major_ids_matches_canonical_majors_jsonl(self) -> None:
        from src.data.majors.canonical_major_descriptions import CANONICAL_MAJOR_DESCRIPTIONS_BY_ID
        from src.services.major_exploration_service import DEFAULT_SERVICE_MAJOR_IDS

        self.assertEqual(DEFAULT_SERVICE_MAJOR_IDS, frozenset(CANONICAL_MAJOR_DESCRIPTIONS_BY_ID))
        self.assertEqual(len(DEFAULT_SERVICE_MAJOR_IDS), 10)

    def test_real_service_major_id_allowed(self) -> None:
        repo = _FakeDepartmentRepository([_dept("d1", canonical_major_id="business_administration")])
        service = MajorExplorationService(repo)
        result = service.list_departments_for_major("business_administration")
        self.assertEqual([d.department_id for d in result], ["d1"])

    def test_42_group_id_blocked_even_with_matching_department_data(self) -> None:
        # 실제로 이 Group ID로 Mapping된 학과가 있어도(Repository 데이터 자체는
        # 그대로 두고) 42개 Canonical Major Group ID로는 조회할 수 없다.
        for group_id in ("fine_arts_design", "music", "performing_media_arts", "sports_dance", "korean_literature"):
            repo = _FakeDepartmentRepository([_dept("d1", canonical_major_id=group_id)])
            service = MajorExplorationService(repo)
            self.assertEqual(service.list_departments_for_major(group_id), [], group_id)

    def test_design_still_blocked_even_though_it_is_a_real_service_major_id(self) -> None:
        # design은 DEFAULT_SERVICE_MAJOR_IDS에는 있지만(canonical_majors.jsonl의
        # 실제 10개 중 하나) EXCLUDED_RECOMMENDATION_MAJOR_IDS가 그보다 먼저 막는다.
        from src.services.major_exploration_service import DEFAULT_SERVICE_MAJOR_IDS

        self.assertIn("design", DEFAULT_SERVICE_MAJOR_IDS)
        repo = _FakeDepartmentRepository([_dept("d1", canonical_major_id="design")])
        service = MajorExplorationService(repo)
        self.assertEqual(service.list_departments_for_major("design"), [])

    def test_unregistered_arbitrary_id_blocked(self) -> None:
        repo = _FakeDepartmentRepository([_dept("d1", canonical_major_id="totally_made_up_major_id")])
        service = MajorExplorationService(repo)
        self.assertEqual(service.list_departments_for_major("totally_made_up_major_id"), [])

    def test_misbehaving_repository_cannot_leak_group_id_departments(self) -> None:
        # Repository가 criteria를 완전히 무시해도(_MisbehavingDepartmentRepository),
        # Service의 마지막 노출 필터가 여전히 허용 집합 밖 major_id를 막는다.
        repo = _MisbehavingDepartmentRepository([_dept("d1", canonical_major_id="fine_arts_design")])
        service = MajorExplorationService(repo)
        self.assertEqual(service.list_departments_for_major("fine_arts_design"), [])

    def test_custom_allowed_major_ids_overrides_default(self) -> None:
        repo = _FakeDepartmentRepository([_dept("d1", canonical_major_id="fine_arts_design")])
        service = MajorExplorationService(repo, allowed_major_ids=frozenset({"fine_arts_design"}))
        result = service.list_departments_for_major("fine_arts_design")
        self.assertEqual([d.department_id for d in result], ["d1"])

    def test_existing_national_results_unchanged_with_real_data(self) -> None:
        """실제 Repository·실제 canonical_majors.jsonl 기반 기본 Allowlist로,
        전국 학과 1,072건 전환(2026-08-25) 이후 실제 기준값이 그대로인지 End-to-End로
        확인한다 — 옛 데모 4/3/1/0은 archive로 옮겨졌다. `fail_closed_major_ids`를
        지정하지 않아 학과 단위 Scope 정책은 적용되지 않는다(상태·출처 필터만)."""

        from src.repositories.department_repository import JsonlDepartmentRepository

        repo = JsonlDepartmentRepository()
        service = MajorExplorationService(repo)
        self.assertEqual(len(service.list_departments_for_major("media_communication")), 133)
        self.assertEqual(len(service.list_departments_for_major("industrial_engineering")), 53)
        self.assertEqual(len(service.list_departments_for_major("hci_ux")), 0)
        self.assertEqual(len(service.list_departments_for_major("design")), 0)


if __name__ == "__main__":
    unittest.main()
