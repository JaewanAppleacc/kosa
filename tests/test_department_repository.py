"""JsonlDepartmentRepository 계약 테스트 — 2026-08-24
national-department-readiness 정합성 수정 지시서 §6.

중복 department_id를 조용히 마지막 값으로 덮어쓰던 결함을 고친 뒤(Fail-Fast로
전환), 그 수정이 실제로 강제되는지 확인한다."""

from __future__ import annotations

import unittest

from src.repositories.department_repository import (
    DuplicateDepartmentIdError,
    JsonlDepartmentRepository,
)
from src.schemas.major import Department


def _dept(department_id: str, *, department_name: str = "테스트학과", university_name: str = "테스트대학교") -> Department:
    return Department(
        department_id=department_id,
        university_name=university_name,
        campus=None,
        region="서울",
        department_name=department_name,
        college_name="테스트대학",
        admission_unit=None,
        department_status="EXISTING",
        source_svy_year=2025,
        source_url="https://example.test/dept",
        canonical_major_id="computer_science",
    )


class NormalLoadTest(unittest.TestCase):
    def test_real_master_5595_departments_load_normally(self) -> None:
        """2026-08-25 전국 학과 1,072건 Production Master 전환 — 옛 데모 35건은
        `data/archive/departments_legacy_demo_35.jsonl`로 보존됐고, 이제 실제
        Repository 기준값은 1,072다.

        2026-08-25 지시서(c/national-departments-38-majors) 후속 정정 — 8개
        Major·1,072건을 38개 Major·5,595건으로 다시 교체했다(옛 1,072건은
        `data/archive/departments_legacy_1072_8majors.jsonl`로 보존)."""
        repo = JsonlDepartmentRepository()
        self.assertEqual(len(repo), 5595)
        self.assertEqual(len(repo.all()), 5595)

    def test_no_duplicate_ids_in_real_master(self) -> None:
        repo = JsonlDepartmentRepository()
        ids = [d.department_id for d in repo.all()]
        self.assertEqual(len(ids), len(set(ids)))


class DuplicateDepartmentIdFailFastTest(unittest.TestCase):
    """§6 "중복 ID 2개 즉시 차단"·"중복이 마지막 값으로 덮어써지지 않음"·
    "예외 메시지 민감정보 미포함"·"Repository가 부분 초기화된 상태로 남지 않음"."""

    def _duplicate_pair(self) -> list[Department]:
        return [
            _dept("dup_id_001", department_name="가나다학과", university_name="가나다대학교"),
            _dept("dup_id_001", department_name="라마바학과", university_name="라마바대학교"),
        ]

    def test_duplicate_id_raises_immediately(self) -> None:
        with self.assertRaises(DuplicateDepartmentIdError):
            JsonlDepartmentRepository(departments=self._duplicate_pair())

    def test_exception_message_contains_only_department_id(self) -> None:
        try:
            JsonlDepartmentRepository(departments=self._duplicate_pair())
            self.fail("DuplicateDepartmentIdError가 발생하지 않았다")
        except DuplicateDepartmentIdError as exc:
            message = str(exc)
            self.assertEqual(message, "dup_id_001")
            for forbidden in ("가나다학과", "라마바학과", "가나다대학교", "라마바대학교", "example.test"):
                self.assertNotIn(forbidden, message)

    def test_last_row_does_not_silently_win(self) -> None:
        """예전 버그: `{d.department_id: d for d in ...}`는 마지막 행으로 조용히
        덮어썼다 — 지금은 그 마지막 행이 "이겼는지" 확인할 방법 자체가 없어야
        한다(예외가 나서 Repository가 아예 만들어지지 않으므로)."""

        with self.assertRaises(DuplicateDepartmentIdError):
            repo = JsonlDepartmentRepository(departments=self._duplicate_pair())
            repo.get("dup_id_001")  # 여기 도달하면(예외가 안 났다면) 테스트 자체가 실패해야 한다.

    def test_no_partially_constructed_repository_escapes(self) -> None:
        """생성자가 예외를 던지면 그 인스턴스 참조 자체가 호출자에게 전달되지
        않는다(Python 언어 보장) — 여기서는 그 상태에서 어떤 부분 완성 객체도
        남지 않았음을, 예외 처리 스코프 밖에서 이름이 바인딩되지 않은 사실로
        직접 확인한다."""

        repo = None
        try:
            repo = JsonlDepartmentRepository(departments=self._duplicate_pair())
        except DuplicateDepartmentIdError:
            pass
        self.assertIsNone(repo)

    def test_three_duplicates_of_same_id_still_fails_on_first_repeat(self) -> None:
        rows = [_dept("dup_triple") for _ in range(3)]
        with self.assertRaises(DuplicateDepartmentIdError) as ctx:
            JsonlDepartmentRepository(departments=rows)
        self.assertEqual(str(ctx.exception), "dup_triple")

    def test_get_search_all_stay_consistent_when_no_duplicates(self) -> None:
        """중복이 없을 때는 기존과 동일하게 .get()/.search()/.all()이 서로
        일관된 데이터 집합을 본다."""

        rows = [_dept("a1"), _dept("a2"), _dept("a3")]
        repo = JsonlDepartmentRepository(departments=rows)
        self.assertEqual(len(repo.all()), 3)
        self.assertIsNotNone(repo.get("a1"))
        self.assertIsNotNone(repo.get("a2"))
        self.assertIsNotNone(repo.get("a3"))
        self.assertIsNone(repo.get("does_not_exist"))


if __name__ == "__main__":
    unittest.main()
