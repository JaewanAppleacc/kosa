"""Education Data MCP Server (작업자 C 소유) — 설계안 §21.

`src/schemas/mcp_contracts.py`의 8개 Tool을 전부 구현한다. 이름·입출력 타입은 A가 확정한
계약 그대로이고, C는 데이터 조회만 채운다.

## 네 가지 상태를 구분하는 규칙 (§21)

| status | 언제 |
|---|---|
| `ok` | 조회에 성공했고 결과가 하나 이상 |
| `empty` | 조회는 성공했는데 조건에 맞는 게 없음 |
| `source_missing` | 조회할 데이터 자체가 아직 없음 (수집 미완료·파일 없음) |
| `error` | 입력이 잘못됐거나 조회 중 실패 |

`empty`와 `source_missing`을 나누는 이유는 Agent가 "그런 학과는 없다"와 "아직 모아 놓은
자료가 없다"를 다르게 말해야 하기 때문이다. 둘을 같은 빈 리스트로 돌려주면 상위 계층이
"자료가 없다"를 "존재하지 않는다"로 바꿔 말하게 된다.

## Tool은 다음 행동을 정하지 않는다

반환값에 "다음 질문", "추천", "정렬해서 보여줄 것" 같은 지시를 담지 않는다(§21, §27).
정렬조차 비교 가능한 그룹 안에서만 하고, 그룹을 고르는 정책은 admission_filter가 갖는다.

## MCP 전송 계층

`requirements-lock.txt`에 MCP SDK가 없어 (의존성 추가는 A 결정) stdio/SSE 바인딩은 붙이지
않았다. `TOOL_REGISTRY`가 "Tool 이름 → (입력 모델, 처리 함수)"를 그대로 들고 있으므로,
SDK가 정해지면 이 표를 순회하며 등록하는 어댑터만 추가하면 된다. A는 지금도
`EducationDataServer`를 직접 호출해 쓸 수 있다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from src.engines.admission_filter import assert_single_group
from src.repositories.admission_repository import JsonlAdmissionRepository
from src.repositories.department_repository import JsonlDepartmentRepository
from src.rag.retrieve import RagRetriever
from src.schemas.course import SubjectProfile
from src.schemas.major import AdmissionReference, Department
from src.schemas.mcp_contracts import (
    CareerNetMajorSummary,
    GetCareerMajorInput,
    GetCareerMajorOutput,
    GetDepartmentInput,
    GetDepartmentOutput,
    MCPToolResult,
    SearchAdmissionReferencesInput,
    SearchAdmissionReferencesOutput,
    SearchCareerMajorInput,
    SearchCareerMajorOutput,
    SearchDepartmentRagInput,
    SearchDepartmentRagOutput,
    SearchDepartmentsInput,
    SearchDepartmentsOutput,
    SearchHighSchoolSubjectInput,
    SearchHighSchoolSubjectOutput,
    SearchUniversityInput,
    SearchUniversityOutput,
    UniversitySummary,
)
from src.schemas.retrieval import RetrievedDocument

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _contains(haystack: str, needle: str) -> bool:
    return needle.strip().replace(" ", "").lower() in haystack.replace(" ", "").lower()


class EducationDataServer:
    """8개 Tool의 실제 데이터 조회. 저장소를 주입할 수 있어 테스트가 파일에 묶이지 않는다."""

    def __init__(
        self,
        data_dir: Path | None = None,
        department_repository: JsonlDepartmentRepository | None = None,
        admission_repository: JsonlAdmissionRepository | None = None,
        retriever: RagRetriever | None = None,
        career_majors: list[CareerNetMajorSummary] | None = None,
        universities: list[UniversitySummary] | None = None,
        subjects: list[SubjectProfile] | None = None,
    ) -> None:
        self._data_dir = data_dir or DEFAULT_DATA_DIR
        self._departments = department_repository or JsonlDepartmentRepository(
            path=self._data_dir / "master" / "departments.jsonl"
        )
        self._admissions = admission_repository or JsonlAdmissionRepository(
            path=self._data_dir / "admissions" / "admission_references.jsonl"
        )
        self._retriever = retriever
        self._career_majors = (
            career_majors
            if career_majors is not None
            else [
                CareerNetMajorSummary.model_validate(row)
                for row in _load_jsonl(self._data_dir / "master" / "career_net_majors.jsonl")
            ]
        )
        self._universities = (
            universities
            if universities is not None
            else [
                UniversitySummary(
                    schl_id=row["schl_id"],
                    name=row["name"],
                    region=row["region"],
                    establishment_type=row["establishment_type"],
                )
                for row in _load_jsonl(self._data_dir / "master" / "universities.jsonl")
            ]
        )
        self._subjects = (
            subjects
            if subjects is not None
            else [
                SubjectProfile.model_validate(row)
                for row in _load_jsonl(self._data_dir / "master" / "subjects.jsonl")
            ]
        )

    # --- 공통 ---

    @staticmethod
    def _result(
        rows: list[Any], source_loaded: bool, source_note: str
    ) -> MCPToolResult:
        if not source_loaded:
            return MCPToolResult(status="source_missing", data=[], error_message=source_note)
        if not rows:
            return MCPToolResult(status="empty", data=[])
        return MCPToolResult(status="ok", data=rows)

    @staticmethod
    def _limit(value: int) -> int:
        if value <= 0:
            raise ValueError("limit은 1 이상이어야 한다")
        return value

    # --- Tool 1·2: CareerNet 학과 정보 ---

    def search_career_major(self, payload: SearchCareerMajorInput) -> SearchCareerMajorOutput:
        try:
            limit = self._limit(payload.limit)
        except ValueError as exc:
            return MCPToolResult(status="error", error_message=str(exc))
        if not payload.query.strip():
            return MCPToolResult(status="error", error_message="query가 비어 있다")

        rows = [
            m
            for m in self._career_majors
            if _contains(m.label, payload.query) or _contains(m.summary, payload.query)
        ][:limit]
        return self._result(
            rows,
            bool(self._career_majors),
            "커리어넷 학과 정보가 적재되지 않았다 (data/master/career_net_majors.jsonl)",
        )

    def get_career_major(self, payload: GetCareerMajorInput) -> GetCareerMajorOutput:
        rows = [m for m in self._career_majors if m.career_net_major_id == payload.career_net_major_id]
        return self._result(
            rows,
            bool(self._career_majors),
            "커리어넷 학과 정보가 적재되지 않았다 (data/master/career_net_majors.jsonl)",
        )

    # --- Tool 3: 대학 검색 ---

    def search_university(self, payload: SearchUniversityInput) -> SearchUniversityOutput:
        try:
            limit = self._limit(payload.limit)
        except ValueError as exc:
            return MCPToolResult(status="error", error_message=str(exc))

        query = payload.query.strip()
        rows = [
            u
            for u in self._universities
            if not query or _contains(u.name, query) or _contains(u.region, query)
        ][:limit]
        return self._result(
            rows,
            bool(self._universities),
            "대학 Master가 적재되지 않았다 (data/master/universities.jsonl)",
        )

    # --- Tool 4·5: 학과 ---

    def search_departments(self, payload: SearchDepartmentsInput) -> SearchDepartmentsOutput:
        try:
            limit = self._limit(payload.limit)
            rows: list[Department] = self._departments.search(payload.criteria, limit=limit)
        except ValueError as exc:
            return MCPToolResult(status="error", error_message=str(exc))
        return self._result(
            rows,
            len(self._departments) > 0,
            "학과 Master가 적재되지 않았다 (data/master/departments.jsonl)",
        )

    def get_department(self, payload: GetDepartmentInput) -> GetDepartmentOutput:
        if len(self._departments) == 0:
            return MCPToolResult(
                status="source_missing",
                error_message="학과 Master가 적재되지 않았다 (data/master/departments.jsonl)",
            )
        found = self._departments.get(payload.department_id)
        return MCPToolResult(status="ok", data=[found]) if found else MCPToolResult(status="empty")

    # --- Tool 6: 입결 ---

    def search_admission_references(
        self, payload: SearchAdmissionReferencesInput
    ) -> SearchAdmissionReferencesOutput:
        if len(self._admissions) == 0:
            return MCPToolResult(
                status="source_missing",
                error_message="입결 자료가 적재되지 않았다 (data/admissions/admission_references.jsonl)",
            )
        if not self._admissions.has_department(payload.criteria.department_id):
            # 이 학과의 자료를 아직 하나도 안 모았다 — "조건에 맞는 게 없다"와 다르다.
            return MCPToolResult(
                status="source_missing",
                error_message=(
                    f"{payload.criteria.department_id}의 입결 자료가 아직 수집되지 않았다"
                ),
            )
        try:
            rows: list[AdmissionReference] = self._admissions.find_comparable(payload.criteria)
            assert_single_group(rows)  # 나가기 직전 한 번 더 확인한다
        except Exception as exc:  # noqa: BLE001 — 실패를 빈 결과로 바꾸지 않는다
            return MCPToolResult(status="error", error_message=str(exc))
        return MCPToolResult(status="ok", data=rows) if rows else MCPToolResult(status="empty")

    # --- Tool 7: 학과 RAG ---

    def search_department_rag(
        self, payload: SearchDepartmentRagInput
    ) -> SearchDepartmentRagOutput:
        if self._retriever is None or len(self._retriever) == 0:
            return MCPToolResult(
                status="source_missing",
                error_message="RAG 색인이 비어 있다 (data/rag/sources.jsonl 수집·색인 필요)",
            )
        if not payload.query.strip():
            return MCPToolResult(status="error", error_message="query가 비어 있다")
        if payload.top_k <= 0:
            return MCPToolResult(status="error", error_message="top_k는 1 이상이어야 한다")

        filters = (
            {"related_department_id": payload.department_id} if payload.department_id else None
        )
        try:
            rows: list[RetrievedDocument] = self._retriever.search(
                payload.query, filters=filters, top_k=payload.top_k
            )
        except Exception as exc:  # noqa: BLE001
            return MCPToolResult(status="error", error_message=str(exc))

        # 출처가 빠진 결과는 내보내지 않는다 (§19).
        without_source = [r for r in rows if not r.source_url]
        if without_source:
            return MCPToolResult(
                status="source_missing",
                error_message=f"출처 URL이 없는 검색 결과 {len(without_source)}건이 있다",
            )
        return MCPToolResult(status="ok", data=rows) if rows else MCPToolResult(status="empty")

    # --- Tool 8: 고교 과목 ---

    def search_high_school_subject(
        self, payload: SearchHighSchoolSubjectInput
    ) -> SearchHighSchoolSubjectOutput:
        try:
            limit = self._limit(payload.limit)
        except ValueError as exc:
            return MCPToolResult(status="error", error_message=str(exc))

        query = payload.query.strip()
        rows = [
            s
            for s in self._subjects
            if not query
            or _contains(s.label, query)
            or any(_contains(major_id, query) for major_id in s.related_major_ids)
        ][:limit]
        return self._result(
            rows, bool(self._subjects), "고교 과목 Master가 적재되지 않았다 (data/master/subjects.jsonl)"
        )


ToolHandler = Callable[[EducationDataServer, Any], MCPToolResult]

# Tool 이름 → (입력 모델, 처리 함수). MCP SDK가 정해지면 이 표를 순회해 등록한다.
TOOL_REGISTRY: dict[str, tuple[type, ToolHandler]] = {
    "search_career_major": (SearchCareerMajorInput, EducationDataServer.search_career_major),
    "get_career_major": (GetCareerMajorInput, EducationDataServer.get_career_major),
    "search_university": (SearchUniversityInput, EducationDataServer.search_university),
    "search_departments": (SearchDepartmentsInput, EducationDataServer.search_departments),
    "get_department": (GetDepartmentInput, EducationDataServer.get_department),
    "search_admission_references": (
        SearchAdmissionReferencesInput,
        EducationDataServer.search_admission_references,
    ),
    "search_department_rag": (
        SearchDepartmentRagInput,
        EducationDataServer.search_department_rag,
    ),
    "search_high_school_subject": (
        SearchHighSchoolSubjectInput,
        EducationDataServer.search_high_school_subject,
    ),
}


def call_tool(server: EducationDataServer, tool_name: str, payload: dict) -> MCPToolResult:
    """이름과 raw dict로 Tool을 부르는 진입점. 입력 검증 실패도 `error`로 감싼다 —
    예외를 그대로 던지면 호출자가 네 가지 상태 구분을 우회하게 된다."""

    entry = TOOL_REGISTRY.get(tool_name)
    if entry is None:
        return MCPToolResult(
            status="error", error_message=f"알 수 없는 Tool 이름: {tool_name!r}"
        )
    input_model, handler = entry
    try:
        parsed = input_model.model_validate(payload)
    except Exception as exc:  # noqa: BLE001 — pydantic ValidationError 포함
        return MCPToolResult(status="error", error_message=f"입력 검증 실패: {exc}")
    return handler(server, parsed)
