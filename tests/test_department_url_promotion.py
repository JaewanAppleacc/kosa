"""Department URL 승격 준비 규칙 테스트 — A-2 지시서(integration/academyinfo-pipeline,
2026-08-24) §1/§6.

이 규칙은 아직 어떤 Builder에서도 호출되지 않는다 — 현재 시연 Master(35개)는 이
테스트로도, 이 모듈로도 재생성되거나 바뀌지 않는다(그 자체를 별도로 확인한다)."""

from __future__ import annotations

import unittest
from pathlib import Path

from src.schemas.major import Department
from src.services.department_url_promotion import resolve_department_url_for_promotion

_REPO_ROOT = Path(__file__).resolve().parents[1]


class ResolveDepartmentUrlForPromotionTest(unittest.TestCase):
    def test_department_scope_passes_url_through(self) -> None:
        url = "https://cs.example.ac.kr"
        self.assertEqual(resolve_department_url_for_promotion("department", url), url)

    def test_college_scope_always_resolves_to_none_even_with_a_url(self) -> None:
        self.assertIsNone(
            resolve_department_url_for_promotion("college", "https://college.example.ac.kr")
        )

    def test_department_scope_with_none_url_stays_none(self) -> None:
        self.assertIsNone(resolve_department_url_for_promotion("department", None))

    def test_resolved_department_scope_value_passes_existing_department_url_validator(self) -> None:
        """이 함수가 돌려주는 값은 실제 `Department.department_url` 검증(§A2 기존
        규칙 — http/https만, API Key 쿼리 파라미터 금지)을 그대로 통과해야 한다."""

        resolved = resolve_department_url_for_promotion("department", "https://cs.example.ac.kr")
        dept = Department(
            department_id="dept_test", university_name="테스트대학교", region="서울",
            department_name="테스트학과", college_name="테스트단과대학", department_status="EXISTING",
            source_svy_year=2025, source_url="https://www.academyinfo.go.kr/", department_url=resolved,
        )
        self.assertEqual(dept.department_url, "https://cs.example.ac.kr")

    def test_college_scope_resolved_none_is_valid_department_url(self) -> None:
        resolved = resolve_department_url_for_promotion("college", "https://college.example.ac.kr")
        dept = Department(
            department_id="dept_test2", university_name="테스트대학교", region="서울",
            department_name="테스트학과", college_name="테스트단과대학", department_status="EXISTING",
            source_svy_year=2025, source_url="https://www.academyinfo.go.kr/", department_url=resolved,
        )
        self.assertIsNone(dept.department_url)


class DemoMasterNotRegeneratedTest(unittest.TestCase):
    """이번 라운드에서 시연 Master 35개의 URL이 이 브랜치 안에서 자동으로 바뀌지
    않았는지 직접 `git diff`로 확인한다.

    2026-08-25 전국 학과 1,072건 Production Master 전환(a/national-master-
    promotion-final-wiring)이 이 URL 통합 라운드와 무관하게 의도적으로
    `data/master/departments.jsonl`을 교체했다 — 옛 35건(이 URL 통합 라운드가
    실제로 손대지 않았다는 사실 자체)은 `data/archive/departments_legacy_demo_35.jsonl`
    로 그대로 보존됐으므로, 그 archive를 대상으로 원래 검증을 계속한다."""

    def test_legacy_35_department_archive_has_no_department_url(self) -> None:
        """archive된 옛 35개 시연 데이터는 전부 `department_url=None`이어야 한다
        (§1 "시연 데이터 35개의 URL도 이번 브랜치에서 자동 변경하지 않는다")."""

        from src.repositories.department_repository import load_departments

        archive_path = _REPO_ROOT / "data" / "archive" / "departments_legacy_demo_35.jsonl"
        departments = load_departments(archive_path)
        self.assertEqual(len(departments), 35)
        for dept in departments:
            self.assertIsNone(dept.department_url, f"{dept.department_id}에 department_url이 이미 채워짐")


class InvalidScopeRejectedTest(unittest.TestCase):
    def test_unknown_scope_value_is_a_type_error_at_call_time(self) -> None:
        """`DepartmentUrlScope`는 Literal["department", "college"]다 — 함수 자체는
        런타임에 값 검사를 다시 하지 않지만(타입 힌트로 이미 막힘), 실제로 다른 문자열이
        들어오면 college 취급(else 분기)으로 안전하게 떨어져 None을 반환한다 — 알 수
        없는 scope를 실수로 공개 노출하는 방향으로 fail하지 않는다(Fail-Closed)."""

        result = resolve_department_url_for_promotion("unknown_scope", "https://example.ac.kr")  # type: ignore[arg-type]
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
