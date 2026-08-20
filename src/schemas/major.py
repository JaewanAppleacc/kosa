"""Major / Department / Canonical Mapping Schema — 설계안 §15, §17, §18 구현.

Department/AdmissionReference는 C가 구현할 department_repository.py/admission_repository.py의
반환 타입 계약이다. A는 이 파일만 소유하고, C는 이 Schema를 import해서 채우기만 한다
(CLAUDE.md: "A는 위 모듈들의 입출력 계약을 정의하고 호출하지만 내부 구현을 대신 작성하지 않는다").
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator

VectorScale = dict[str, float]  # trait_id -> 0/.33/.67/1.00 (trait_normalizer.normalize_grade 결과)


class MajorProfile(BaseModel):
    """§15 Major Multi-Vector."""

    major_id: str
    label: str
    interest_vector: VectorScale = {}
    cognitive_vector: VectorScale = {}
    work_style_vector: VectorScale = {}
    environment_vector: VectorScale = {}
    source_ids: list[str] = []
    extraction_method: Literal["rule", "llm", "manual", "rule_llm_hybrid"]
    review_status: Literal["draft", "team_reviewed", "REVIEW_REQUIRED"]
    profile_version: str
    updated_at: datetime


class MappingReview(BaseModel):
    """§15: Major-Trait Mapping 등 검토가 필요한 산출물 전반에 재사용하는 검토 기록."""

    mapping_id: str
    author_id: str
    reviewer_ids: list[str]
    agreement_status: Literal["AGREED", "REVIEW_REQUIRED", "REJECTED"]
    review_notes: list[str] = []
    source_ids: list[str]
    mapping_version: str
    reviewed_at: datetime


class CanonicalMappingResult(BaseModel):
    """§17 Mapping Pipeline 결과. `confidence: 0.84` 같은 미보정 수치는 쓰지 않는다."""

    department_id: str
    mapping_status: Literal["AUTO_MAPPED", "REVIEW_REQUIRED", "CONFIRMED"]
    primary_candidate: str
    secondary_candidates: list[str] = []
    mapping_method: Literal["exact_alias", "embedding_plus_curriculum", "llm_structured"]
    evidence: list[str]
    mapping_version: str


class Department(BaseModel):
    """§18 실제 학과. department_id는 §ids.py의 generate_department_id()로 생성하며
    조사년도(svyYr)는 id 해시에 넣지 않는다 — source_svy_year로 별도 보존한다."""

    department_id: str
    university_name: str
    campus: str | None = None
    region: str
    department_name: str
    college_name: str
    admission_unit: str | None = None
    department_status: Literal["EXISTING", "NEW", "MERGED", "SPLIT", "ABOLISHED"]
    source_svy_year: int
    source_url: str
    canonical_major_id: str | None = None  # CanonicalMappingResult 확정 후 채워짐

    @field_validator("department_name", "university_name")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("빈 값은 허용하지 않는다")
        return value


class AdmissionReference(BaseModel):
    """§18. 같은 data_comparability_group끼리만 비교 가능하다 — 서로 다른 그룹을 하나의
    정렬 결과로 섞지 않는다(정책은 C의 admission_filter.py가 강제)."""

    department_id: str
    admission_year: int
    admission_type: str
    admission_track: str
    score_metric: str
    score_50_cut: float | None = None
    score_70_cut: float | None = None
    minimum_requirement: str | None = None
    source_url: str
    data_comparability_group: str
    review_status: Literal["draft", "verified"]
    verified_at: datetime


RelevanceLabel = Literal["관련성 높음", "함께 탐색해볼 분야", "비교해볼 만한 분야"]
EvidenceSufficiencyLabel = Literal["충분", "보통", "제한적"]


class MajorRelevance(BaseModel):
    """§16 사용자 노출용. 내부 유사도 점수는 절대 포함하지 않는다(CLAUDE.md 금지 사항)."""

    major_id: str
    label: str
    relevance_label: RelevanceLabel
    evidence_sufficiency: EvidenceSufficiencyLabel
    repeated_context_count: int
