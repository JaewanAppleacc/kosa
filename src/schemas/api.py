"""API 요청·응답 Envelope — A 지시서 §3 "결측값, 오류 응답, 정성 관련도 Label의 표현 형식을
확정한다"의 구현. 여기 정의된 상태값·오류 코드가 B 화면의 Loading/Fallback/재시도 UI가
참조하는 정본이다.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, StrictInt

from src.schemas.course import CourseParseWarning, CourseProfile, ParsedSubjectCandidate
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
    # 2026-08-26 16차 리뷰: POST /course/upload가 문서를 읽긴 했지만 본문에서 과목명
    # 후보를 하나도 뽑아내지 못한 상태(이미지 스캔 PDF, .xls 미지원, 손상된 xlsx 등).
    # "개설과목이 0개"(빈 목록, 200)와 "문서를 못 읽었다"(파싱 실패, 422)는 서로 다른
    # 사실이라 반드시 구분한다 — 전자를 후자로 표현하면 "이 학교는 개설과목이 없다"는
    # 거짓 정보가 된다.
    PARSE_FAILED = "PARSE_FAILED"
    # POST /course/confirm이 호출됐는데 이 session_id로 먼저 POST /course/upload를
    # 거친 적이 없을 때(CoursePlanningSessionState 자체가 없음) — 순서가 잘못된
    # 호출이라는 뜻이라 SESSION_NOT_FOUND(Assessment 세션 자체가 없음)와는 다른
    # 코드로 구분한다.
    COURSE_UPLOAD_NOT_FOUND = "COURSE_UPLOAD_NOT_FOUND"


class APIError(BaseModel):
    error_code: APIErrorCode
    message: str


# --- GET /contexts ---


class ContextCatalogItem(BaseModel):
    """2026-08-30 20차 리뷰: B가 `src/data/contexts/context_definitions.py`(15개)를
    프론트엔드 상수로 복제하지 않도록, 서버가 검증하는 것과 동일한 Context 목록·순서를
    그대로 API로 내려준다. 필드는 `ContextDefinition`(`src/schemas/context.py`)과
    `assessment_supported`(계산값) 하나를 더한 것뿐이다 — 새 정본 데이터를 만들지 않는다."""

    context_id: str
    label: str
    description: str
    example_activities: list[str]
    interest_rating_prompt: str
    is_core: bool
    # 실제 심층 질문 흐름(Seed·Option Blueprint)이 이 Context를 지원하는지 — 현재는
    # VERTICAL_SLICE_CONTEXT_IDS(game/media/school_life) 3개만 true다. 관심도 평가
    # (`/assessment/interest-rating`)는 15개 전부 받지만, `/assessment/context-select`로
    # 선택할 수 있는 건 이 값이 true인 Context뿐이다.
    assessment_supported: bool


class ContextSelectionPolicyResponse(BaseModel):
    """B가 선택 개수 제한을 하드코딩하지 않도록 서버가 실제로 검증하는 값을 그대로
    내려준다 — `src/engines/contrast_context_selector.py`의 상수와 항상 같은 값이다."""

    preferred_context_min_count: int
    preferred_context_max_count: int
    contrast_context_count: int
    final_context_min_count: int
    final_context_max_count: int
    coverage_replacement_enabled: bool


class ContextCatalogResponse(BaseModel):
    contexts: list[ContextCatalogItem]
    selection_policy: ContextSelectionPolicyResponse


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
    # 2026-08-26 16차 리뷰: PRE_SURVEY(GET /subjects)와 동일한 규칙으로 검증된
    # selected_major_id를 그대로 응답에도 담아 화면이 다시 물어보지 않아도 되게 한다.
    selected_major_id: str
    parsed_candidates: list[ParsedSubjectCandidate]
    parse_warnings: list[CourseParseWarning] = []


class CourseConfirmRequest(BaseModel):
    session_id: str
    confirmed_subject_ids: list[str]


class CourseConfirmResponse(BaseModel):
    session_id: str
    accepted: bool
    # 2026-08-26 16차 리뷰: 예전엔 accepted=True만 돌려주고 끝났다 — 화면이 확정 직후
    # 바로 최종 추천을 보여주려면 별도로 GET /subjects를 다시 호출해야 했다. 이제
    # 확정과 동시에 POST_OFFERING CourseProfile을 함께 반환한다.
    course_profile: CourseProfile


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
