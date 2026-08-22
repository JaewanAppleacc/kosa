"""Repository/Retriever Protocol — A가 정의하고 C가 구현한다.

CLAUDE.md: "A는 Protocol, Pydantic 입출력, 오류 형식과 Timeout 정책을 정의한다. C의 구현
파일을 직접 수정하지 않는다." 실제 구현(`department_repository.py`, `admission_repository.py`,
RAG retriever)은 C 소유이며 이 Protocol을 만족하기만 하면 된다 — A는 이 인터페이스만으로
LangGraph Node를 짜고, C의 실제 구현체로 교체돼도 코드가 안 바뀐다.

`profile_repository.py`는 A 소유라 여기 Protocol이 아니라 직접 구현한다.
"""

from __future__ import annotations

from typing import Protocol

from src.schemas.course import SubjectProfile
from src.schemas.major import AdmissionReference, Department
from src.schemas.mcp_contracts import AdmissionSearchCriteria, DepartmentSearchCriteria
from src.schemas.retrieval import RetrievedDocument


class DepartmentRepository(Protocol):
    def search(self, criteria: DepartmentSearchCriteria, limit: int = 30) -> list[Department]: ...

    def get(self, department_id: str) -> Department | None: ...


class SubjectRepository(Protocol):
    """2026-08-24 14차 리뷰 — `CoursePlanningService`가 참조하는 과목 조회 인터페이스.
    `DepartmentRepository`와 같은 이유로 Protocol로 둔다: 테스트에서 Fake Repository를
    주입할 수 있어야 하고, 저장소가 JSONL에서 다른 구현으로 바뀌어도 이 인터페이스만
    지키면 Service·FastAPI 코드는 안 바뀐다."""

    def all(self) -> list[SubjectProfile]: ...

    def related_to_major(self, major_id: str) -> list[SubjectProfile]: ...

    def get(self, subject_id: str) -> SubjectProfile | None: ...


class AdmissionRepository(Protocol):
    def find_comparable(self, criteria: AdmissionSearchCriteria) -> list[AdmissionReference]:
        """criteria.data_comparability_group이 없으면, 비교 가능한 자료끼리만 묶어서
        여러 그룹을 반환한다 — 서로 다른 그룹을 하나의 리스트로 섞어서 반환하지 않는다."""
        ...


class DocumentRetriever(Protocol):
    def search(
        self, query: str, filters: dict[str, str] | None = None, top_k: int = 5
    ) -> list[RetrievedDocument]: ...
