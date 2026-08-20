"""Education Data MCP Tool 입출력 계약 — 설계안 §21 구현.

C가 `src/mcp/education_server.py`에서 이 Tool들의 실제 데이터 조회를 구현한다. A는 이름과
입출력 타입만 정의하고 구현하지 않는다(CLAUDE.md: "Education MCP Tool의 데이터 조회 구현"은
A가 소유하지 않는 영역).

모든 Tool은 조회 결과만 반환하고 Agent의 다음 행동을 결정하지 않는다(설계안 §21, §27
policy_guard 규칙). 오류·빈 결과·출처 누락을 명시적으로 구분하기 위해 MCPToolResult로
감싼다 — 빈 리스트를 반환하는 것과 "실패해서 아무것도 못 가져왔다"를 API 레벨에서
구분하기 위함이다.
"""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel

from src.schemas.course import SubjectProfile
from src.schemas.major import AdmissionReference, Department
from src.schemas.retrieval import RetrievedDocument

T = TypeVar("T")


class MCPToolResult(BaseModel, Generic[T]):
    status: Literal["ok", "empty", "error", "source_missing"]
    data: list[T] = []
    error_message: str | None = None


class CareerNetMajorSummary(BaseModel):
    """CareerNet 학과 정보 원본 요약(§15 데이터 출처). 우리 자체 MajorProfile과는 다른 객체다 —
    이건 외부 소스 원본이고, MajorProfile은 그걸 가공해 만든 우리 내부 산출물이다."""

    career_net_major_id: str
    label: str
    summary: str
    source_url: str


class UniversitySummary(BaseModel):
    schl_id: str
    name: str
    region: str
    establishment_type: str


class DepartmentSearchCriteria(BaseModel):
    university_name: str | None = None
    region: str | None = None
    department_name_query: str | None = None
    canonical_major_id: str | None = None


class AdmissionSearchCriteria(BaseModel):
    department_id: str
    admission_year: int | None = None
    data_comparability_group: str | None = None


# --- Tool별 Input/Output ---


class SearchCareerMajorInput(BaseModel):
    query: str
    limit: int = 10


SearchCareerMajorOutput = MCPToolResult[CareerNetMajorSummary]


class GetCareerMajorInput(BaseModel):
    career_net_major_id: str


GetCareerMajorOutput = MCPToolResult[CareerNetMajorSummary]


class SearchUniversityInput(BaseModel):
    query: str
    limit: int = 20


SearchUniversityOutput = MCPToolResult[UniversitySummary]


class SearchDepartmentsInput(BaseModel):
    criteria: DepartmentSearchCriteria
    limit: int = 30


SearchDepartmentsOutput = MCPToolResult[Department]


class GetDepartmentInput(BaseModel):
    department_id: str


GetDepartmentOutput = MCPToolResult[Department]


class SearchAdmissionReferencesInput(BaseModel):
    criteria: AdmissionSearchCriteria


SearchAdmissionReferencesOutput = MCPToolResult[AdmissionReference]


class SearchDepartmentRagInput(BaseModel):
    query: str
    department_id: str | None = None
    top_k: int = 5


SearchDepartmentRagOutput = MCPToolResult[RetrievedDocument]


class SearchHighSchoolSubjectInput(BaseModel):
    query: str
    limit: int = 20


SearchHighSchoolSubjectOutput = MCPToolResult[SubjectProfile]
