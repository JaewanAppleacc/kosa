"""DepartmentRepository 구현 (작업자 C 소유) — 설계안 §18.

A가 `src/repositories/protocols.py`에 정의한 `DepartmentRepository` Protocol을 만족한다.
A는 이 Protocol만 보고 LangGraph Node를 짜고, 저장소가 JSONL에서 PostgreSQL로 바뀌어도
이 클래스만 교체된다.

저장소를 지금 JSONL로 두는 이유:
- `DATA_GO_KR_SERVICE_KEY`(대학알리미 B340014)가 아직 발급되지 않아 전국 수집이 막혀 있다.
- DB 도입은 A의 인프라 결정 사항이라 C가 앞서 정하지 않는다.
읽기 인터페이스가 같으므로 수집이 풀리면 `data/master/departments.jsonl`만 커지고
`load_departments()`의 입력 경로만 바뀐다.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.engines.canonical_mapper import normalize_department_name
from src.schemas.major import Department
from src.schemas.mcp_contracts import DepartmentSearchCriteria

DEFAULT_MASTER_PATH = Path(__file__).resolve().parents[2] / "data" / "master" / "departments.jsonl"


def load_departments(path: Path | None = None) -> list[Department]:
    source = path or DEFAULT_MASTER_PATH
    if not source.exists():
        return []
    return [
        Department.model_validate(json.loads(line))
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _contains(haystack: str, needle: str) -> bool:
    """공백·괄호 표기 차이를 무시한 부분 문자열 비교.

    사용자는 "중앙대", "중앙대학교", "중앙 대학교"를 섞어 입력한다. 표기 정규화를 거친
    뒤 비교해야 셋이 같은 결과를 낸다.
    """

    return normalize_department_name(needle).replace(" ", "") in normalize_department_name(
        haystack
    ).replace(" ", "")


class JsonlDepartmentRepository:
    """`data/master/departments.jsonl`을 읽는 DepartmentRepository."""

    def __init__(self, departments: list[Department] | None = None, path: Path | None = None):
        self._departments = departments if departments is not None else load_departments(path)
        self._by_id = {d.department_id: d for d in self._departments}

    def __len__(self) -> int:
        return len(self._departments)

    def all(self) -> list[Department]:
        return list(self._departments)

    def search(self, criteria: DepartmentSearchCriteria, limit: int = 30) -> list[Department]:
        if limit <= 0:
            raise ValueError("limit must be > 0")

        matched = [d for d in self._departments if self._matches(d, criteria)]
        # 정렬을 고정한다 — 같은 질의에 매번 같은 순서가 나와야 §26 "동일 답변 재실행
        # 일관성"을 데이터 계층에서 깨지 않는다.
        matched.sort(key=lambda d: (d.university_name, d.department_name, d.department_id))
        return matched[:limit]

    def get(self, department_id: str) -> Department | None:
        return self._by_id.get(department_id)

    @staticmethod
    def _matches(department: Department, criteria: DepartmentSearchCriteria) -> bool:
        if criteria.university_name and not _contains(
            department.university_name, criteria.university_name
        ):
            return False
        if criteria.region and department.region != criteria.region.strip():
            return False
        if criteria.department_name_query and not _contains(
            department.department_name, criteria.department_name_query
        ):
            return False
        if criteria.canonical_major_id:
            # canonical_major_id가 None인 학과는 Mapping이 REVIEW_REQUIRED로 남아 있다는
            # 뜻이다. 미확정 Mapping을 확정된 것처럼 검색 결과에 포함시키지 않는다 (§17).
            if department.canonical_major_id != criteria.canonical_major_id:
                return False
        return True


def departments_missing_canonical_major(repository: JsonlDepartmentRepository) -> list[Department]:
    """Canonical Mapping이 아직 확정되지 않은 학과 — A에게 넘길 검토 대상 (지시서 §5)."""

    return [d for d in repository.all() if d.canonical_major_id is None]
