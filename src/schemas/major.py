"""Major / Department / Canonical Mapping Schema — 설계안 §15, §17, §18 구현.

Department/AdmissionReference는 C가 구현할 department_repository.py/admission_repository.py의
반환 타입 계약이다. A는 이 파일만 소유하고, C는 이 Schema를 import해서 채우기만 한다
(CLAUDE.md: "A는 위 모듈들의 입출력 계약을 정의하고 호출하지만 내부 구현을 대신 작성하지 않는다").
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import parse_qsl, urlparse

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


# A2 지시서(2026-08-24) §1: department_url에는 대학알리미 OpenAPI 호출 URL이나 API
# Key/Service Key가 든 URL을 넣지 않는다 — 학과 공식 홈페이지만 허용한다. 쿼리
# 파라미터 이름 기준으로 판정한다(값 자체를 흉내내는 우연한 문자열 매칭을 피하기
# 위해 urlparse로 실제 쿼리 파라미터만 본다).
_FORBIDDEN_DEPARTMENT_URL_QUERY_PARAMS = frozenset(
    {"servicekey", "service_key", "apikey", "api_key", "key", "authkey", "auth_key", "token"}
)
# A2 후속 보완(2026-08-24) §2-1: 학과 홈페이지는 웹 페이지여야 한다 — `file`/`javascript`/
# `ftp` 등은 브라우저에서 새 탭으로 열었을 때 안전하지 않거나(로컬 파일 접근, 스크립트
# 실행) 애초에 "홈페이지"가 아니다.
_ALLOWED_DEPARTMENT_URL_SCHEMES = frozenset({"http", "https"})


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
    # A2 지시서(2026-08-24) §1: 학과 공식 홈페이지 URL. 데이터 출처 표시용인
    # `source_url`(대학알리미 공식 URL)과 역할이 다르다 — B는 이 값이 있을 때만 "학과
    # 홈페이지" 버튼을 보여주고, `source_url`을 그 버튼에 쓰면 안 된다(README_B §2 참고).
    # 검증되지 않은 URL은 아직 None이다 — C의 검증된 URL 데이터는 이후 별도 라운드에서
    # 채운다(이번 라운드는 Schema·None 처리 경로만 완성한다).
    department_url: str | None = None

    @field_validator("department_name", "university_name")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("빈 값은 허용하지 않는다")
        return value

    @field_validator("department_url")
    @classmethod
    def _validate_department_url(cls, value: str | None) -> str | None:
        """A2 후속 보완(2026-08-24) §2 — 오류 메시지에는 절대 원본 URL을 그대로
        담지 않는다(§2-3). Query 값이 비어 있어도(`?serviceKey=`) 차단해야 하므로
        `parse_qsl(keep_blank_values=True)`로 실제 쿼리 파라미터 "이름"만 본다(값은
        아예 비교하지 않는다 — 이름만으로 판정하면 로그에도 Secret 값이 남지 않는다).
        Query 이름 비교는 대소문자를 무시한다."""

        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None  # 빈 문자열·공백만 있는 값은 "없음"으로 정규화한다.

        parsed = urlparse(stripped)
        if parsed.scheme.lower() not in _ALLOWED_DEPARTMENT_URL_SCHEMES or not parsed.netloc:
            raise ValueError("department_url은 http 또는 https 절대 URL이어야 한다")

        query_param_names = {name.lower() for name, _value in parse_qsl(parsed.query, keep_blank_values=True)}
        forbidden = query_param_names & _FORBIDDEN_DEPARTMENT_URL_QUERY_PARAMS
        if forbidden:
            raise ValueError(
                "department_url에 인증·API Key로 보이는 쿼리 파라미터를 포함할 수 없다 "
                f"(파라미터 이름: {sorted(forbidden)}) — 학과 공식 홈페이지 URL만 허용한다"
            )

        # 대학알리미(academyinfo.go.kr) OpenAPI 호출 경로를 학과 홈페이지로 위장하지
        # 않는다 — source_url(출처 표시용 포털 URL)과 구분한다.
        host = parsed.netloc.lower()
        if "academyinfo.go.kr" in host and "openapi" in stripped.lower():
            raise ValueError(
                "department_url에 대학알리미 OpenAPI 호출 URL을 넣을 수 없다 — "
                "학과 공식 홈페이지 URL만 허용한다"
            )

        return stripped


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
    """§16 사용자 노출용. 내부 유사도 점수는 절대 포함하지 않는다(CLAUDE.md 금지 사항).

    A3 지시서(2026-08-24) §6: `description`은 이 전공이 무엇을 배우는 분야인지
    설명하는 필수 필드다 — 관련도 근거 문장도, 학생 Trait 분석 문장도 아니다(전공
    이름 아래 고정적으로 붙는 정본 소개 문구, `CanonicalMajorEntry.description`을
    그대로 옮긴 값). Optional이 아니다 — 추천 가능한 Canonical Major라면 검토된
    설명이 반드시 있어야 하고, 없으면 major_id/label로 대체하지 않고 그 자리에서
    예외를 낸다(`matching_engine.py`/`matching_engine_v2.py`)."""

    major_id: str
    label: str
    description: str
    relevance_label: RelevanceLabel
    evidence_sufficiency: EvidenceSufficiencyLabel
    repeated_context_count: int

    @field_validator("description")
    @classmethod
    def _description_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("MajorRelevance.description은 빈 문자열이나 공백만 있는 값을 허용하지 않는다")
        return value
