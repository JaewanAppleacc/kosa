"""API 요청·응답 Envelope — A 지시서 §3 "결측값, 오류 응답, 정성 관련도 Label의 표현 형식을
확정한다"의 구현. 여기 정의된 상태값·오류 코드가 B 화면의 Loading/Fallback/재시도 UI가
참조하는 정본이다.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, StrictInt

from src.schemas.course import CourseProfile, ParsedSubjectCandidate
from src.schemas.graph import SubgraphEdge, SubgraphNode
from src.schemas.major import Department, MajorRelevance
from src.schemas.profile import CareerProfile
from src.schemas.question import FinalizedQuestion


# --- 공통 상태 코드 (§11 Fallback 흐름을 그대로 표현) ---


class QuestionDeliveryStatus(str, Enum):
    GENERATED = "GENERATED"  # 정상 실시간 생성
    REGENERATING = "REGENERATING"  # 1회 재생성 중
    CACHE_USED = "CACHE_USED"  # 사전 캐시 사용
    BACKUP_USED = "BACKUP_USED"  # Backup Question 사용
    CONTEXT_EARLY_TERMINATED = "CONTEXT_EARLY_TERMINATED"  # Backup 소진, 해당 Context 조기 종료


class APIErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    LANGSMITH_UNAVAILABLE = "LANGSMITH_UNAVAILABLE"  # fail-open이라 세션은 안 막힘, 참고용 코드
    INTERNAL_ERROR = "INTERNAL_ERROR"
    # 2026-08-21 리뷰: 답변이 아직 하나도 없어 Profile을 만들 Evidence 자체가 없는 상태.
    # CareerProfile.highlights는 5~8개를 강제하는 Schema라 "빈 Profile"을 표현할 방법이
    # 없다 — Majors처럼 200 + 빈 목록이 아니라 이 오류 코드로 명시적으로 알린다.
    EVIDENCE_NOT_READY = "EVIDENCE_NOT_READY"
    # 2026-08-24 14차 리뷰: GET /subjects/{session_id}?selected_major_id=...가
    # selected_major_id를 세 가지 이유로 거부할 수 있다 — (1) Vertical Slice 대표 전공
    # 3개(또는 design 등 추천 제외 전공)에 없는 미등록 전공, (2) 이 세션의 실제 전공
    # 추천 결과(관련성 높음/함께 탐색해볼 분야)에 없는 전공. 셋 다 "이 세션에서 이
    # 전공으로 과목 추천을 받을 수 없다"는 같은 성격의 거부라 코드 하나로 묶는다.
    MAJOR_NOT_SELECTABLE = "MAJOR_NOT_SELECTABLE"


class APIError(BaseModel):
    error_code: APIErrorCode
    message: str


# --- /assessment/session ---


class CreateSessionResponse(BaseModel):
    session_id: str
    user_id: str


# --- /assessment/interest-rating ---


class InterestRatingRequest(BaseModel):
    session_id: str
    # 2026-08-22 4차 리뷰: 예전엔 dict[str, int]라 Pydantic이 "4"(문자열)·4.0(실수)·
    # true/false(bool은 파이썬에서 int의 하위형이라 1/0으로 통과)까지 전부 int로 조용히
    # 변환해 받아들였다. StrictInt는 그 자동 변환(coercion)을 막고 JSON 정수만 통과시킨다
    # (범위 1~5 검사는 값 검증이라 여기서 하지 않고, 기존과 동일하게 핸들러의
    # validate_interest_ratings()가 한다 — 타입 문제와 값 범위 문제를 같은 곳에서 섞지
    # 않기 위함).
    ratings: dict[str, StrictInt]


class InterestRatingResponse(BaseModel):
    session_id: str
    accepted: bool


# --- /assessment/context-select ---


class ContextSelectRequest(BaseModel):
    session_id: str
    selected_preferred_context_ids: list[str]  # 학생이 직접 고른 4개(Vertical Slice는 규모가 다를 수 있음)


class ContextSelectResponse(BaseModel):
    session_id: str
    contrast_context_id: str
    contrast_reason: str
    coverage_replacement_offered: list[str] = []  # 최대 2개


# --- /assessment/context-confirm (HITL) ---


class ContextConfirmRequest(BaseModel):
    session_id: str
    final_context_ids: list[str]


class ContextConfirmResponse(BaseModel):
    session_id: str
    final_context_ids: list[str]
    processing_order: list[str]


# --- /assessment/next-question ---


class NextQuestionResponse(BaseModel):
    session_id: str
    status: QuestionDeliveryStatus
    question: FinalizedQuestion | None  # CONTEXT_EARLY_TERMINATED면 None일 수 있다
    current_context_id: str | None
    questions_asked_in_current_context: int
    assessment_complete: bool = False


# --- /assessment/answer ---


class AnswerRequest(BaseModel):
    session_id: str
    question_id: str
    selected_option_id: str


class AnswerResponse(BaseModel):
    session_id: str
    accepted: bool
    next_action: Literal["NEXT_QUESTION", "CONTEXT_COMPLETE", "ASSESSMENT_COMPLETE"]


# --- GET /profile/{session_id} ---

ProfileResponse = CareerProfile


# --- GET /majors/{session_id} ---


class MajorsResponse(BaseModel):
    session_id: str
    relevant_majors: list[MajorRelevance]
    explore_together_majors: list[MajorRelevance]
    # §16 matching_policy 미충족 시("minimum_usable_traits"/"minimum_usable_vector_groups"
    # 못 채움) 순위를 만들지 않고 이 메시지만 채운다. 정상 계산됐으면 None.
    insufficient_evidence_message: str | None = None


# --- GET /departments/{major_id} ---


class DepartmentsResponse(BaseModel):
    major_id: str
    departments: list[Department]


# --- GET /subjects/{session_id} ---

SubjectsResponse = CourseProfile


# --- POST /course/upload, /course/confirm ---


class CourseUploadResponse(BaseModel):
    session_id: str
    parsed_candidates: list[ParsedSubjectCandidate]


class CourseConfirmRequest(BaseModel):
    session_id: str
    confirmed_subject_ids: list[str]


class CourseConfirmResponse(BaseModel):
    session_id: str
    accepted: bool


# --- GET /subgraph/{session_id} ---


class SubgraphResponse(BaseModel):
    session_id: str
    nodes: list[SubgraphNode]
    edges: list[SubgraphEdge]


# --- GET /session/{session_id} (Session 복원) ---


class SessionRestoreResponse(BaseModel):
    session_id: str
    user_id: str
    phase: str
    has_previous_completed_profile: bool
