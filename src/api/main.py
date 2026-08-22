"""FastAPI 앱 — B에게 줄 API 계약의 실행 가능한 형태.

2026-08-22 리뷰 이후 상태(오래된 설명 갱신): Session 생성부터 Context 확정(Contrast Context
Selector 포함, §5-1/§6-5), Evidence·Trait 계산, Explicit Conflict 판정(§12-1), Career
Profile(§14), 전공 Matching(§16), LangSmith Trace(§24, `LANGSMITH_TRACING=true`일 때만)
까지 전부 실제 경로다. "학생 답변 → Evidence Update → Stop/Continue → Target Planner"와
"Question Generator → Quality Gate → 재생성/Backup" 두 구간은 실제 LangGraph StateGraph로
연결돼 있다(src/agents/assessment/graph/). 2026-08-22 리뷰 8항목: 정확히 이 두 구간만
LangGraph이고, Context 이동·Career Profile 생성·전공 Matching 호출은 여전히 이
FastAPI 파일의 일반 함수 orchestration이다 — "LangGraph로 Adaptive 답변 처리와 질문
생성·재생성·Fallback Workflow를 구현했다"까지만 정확한 표현이고, "전체 진로·학업설계
서비스가 하나의 LangGraph로 구성됐다"는 과장이다(발표·문서에서 쓰지 않는다). 질문
생성(§10) 자체는 `.env`의
`ENABLE_LLM_QUESTION_GENERATION` + API Key 여부에 따라 실제 LLM 또는 Mock 문구로 갈리고,
그 외 계산은 LLM 연동 여부와 무관하게 항상 실제로 동작한다 — Evidence가 전혀 없는 세션에서
Profile을 물으면 Mock으로 얼버무리지 않고 `EVIDENCE_NOT_READY`를 반환한다. Postgres Profile
Store·C 소유 데이터(학과 Repository·RAG·MCP·과목 문서 파싱)는 아직 없다(각 함수 docstring에
개별 표시). Major Exploration·Course Planning은 §5-2가 아니라 별개 Workflow(§4)라 이번
LangGraph 연결 범위 밖이다.

실행: ./.venv/bin/uvicorn src.api.main:app --reload
OpenAPI 문서: http://127.0.0.1:8000/docs (자동 생성, B에게 줄 명세 그 자체)
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# 로컬 개발 편의용 — 이미 설정된 실제 배포 환경변수는 덮어쓰지 않는다(override=False가 기본값).
load_dotenv()

from src.agents.assessment.answer_processor import submit_answer as process_answer_submission
from src.agents.assessment.profile_generator import generate_career_profile
from src.agents.assessment.graph.question_generation_graph import classify_generation_failure
from src.agents.assessment.question_generator import generate_tail_question
from src.api import mock_data
from src.data.conflicts.vertical_slice_contrast_definitions import VERTICAL_SLICE_CONTRAST_DEFINITIONS
from src.data.conflicts.vertical_slice_conflict_resolution_questions import (
    VERTICAL_SLICE_RESOLUTION_QUESTION_BUILDERS,
    VERTICAL_SLICE_RESOLUTION_SPECS,
)
from src.data.contexts.context_definitions import CONTEXT_DEFINITIONS, CONTEXT_IDS, VERTICAL_SLICE_CONTEXT_IDS
from src.data.contexts.context_trait_coverage import CONTEXT_TRAIT_COVERAGE
from src.data.contexts.context_vectors import CONTEXT_VECTORS
from src.data.majors.vertical_slice_major_profiles import VERTICAL_SLICE_MAJOR_PROFILES
from src.data.question_frames.frame_role_map import QUESTION_FRAME_TEXT
from src.data.questions.vertical_slice_backup_questions import VERTICAL_SLICE_BACKUP_QUESTIONS
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAIT_IDS, VERTICAL_SLICE_TRAITS
from src.engines.contrast_context_selector import (
    MINIMUM_PREFERRED_CONTEXT_COUNT_VERTICAL_SLICE,
    ContextSelectionError,
    select_contrast_context,
    validate_context_id_list,
    validate_interest_ratings,
)
from src.engines.matching_engine import (
    compute_major_match,
    compute_student_trait_states,
    rank_major_relevance,
)
from src.ids import generate_question_id, generate_session_id
from src.llm.openai_client import OpenAIChatClient
from src.llm.protocols import ChatLLMClient
from src.llm.settings import LLMSettingsError, llm_generation_enabled, load_chat_llm_settings
from src.agents.course.course_document_parser import SubjectAliasIndex
from src.memory.course_planning_store import InMemoryCoursePlanningStore
from src.memory.session_store import InMemorySessionStore
from src.repositories.department_repository import JsonlDepartmentRepository
from src.repositories.subject_repository import JsonlSubjectRepository
from src.services.course_document_parsing_service import (
    MAX_UPLOAD_SIZE_BYTES,
    CourseConfirmValidationError,
    CourseDocumentParsingService,
    CourseParsingFailedError,
    CourseUploadNotFoundError,
    EmptyFileError,
    FileTooLargeError,
    UnsupportedFileTypeError,
    read_upload_with_limit,
)
from src.services.course_planning_service import (
    CourseEvidenceNotReadyError,
    CoursePlanningService,
    MajorNotSelectableError,
)
from src.services.department_recommendation_scope import JsonlDepartmentRecommendationScopePolicy
from src.services.knowledge_subgraph_service import (
    KnowledgeSubgraphService,
    SubgraphEvidenceNotReadyError,
)
from src.services.major_exploration_service import MajorExplorationService
from src.services.major_trait_mapping_evidence import load_major_trait_mapping_evidence
from src.services.subject_trait_mapping_evidence import load_subject_trait_mapping_evidence
from src.tracing.langsmith_client import LangSmithTraceClient
from src.tracing.protocols import TraceClient
from src.tracing.settings import TracingSettingsError, load_tracing_settings, tracing_enabled
from src.tracing.tracer import Tracer
from src.schemas.api import (
    AnswerRequest,
    AnswerResponse,
    APIError,
    APIErrorCode,
    ContextConfirmRequest,
    ContextConfirmResponse,
    ContextSelectRequest,
    ContextSelectResponse,
    CourseConfirmRequest,
    CourseConfirmResponse,
    CourseUploadResponse,
    CreateSessionResponse,
    DepartmentsResponse,
    InterestRatingRequest,
    InterestRatingResponse,
    MajorsResponse,
    NextQuestionResponse,
    ProfileResponse,
    QuestionDeliveryStatus,
    SessionRestoreResponse,
    SubgraphResponse,
    SubjectsResponse,
)
from src.schemas.assessment_state import AssessmentPhase, AssessmentState

app = FastAPI(
    title="AI 진로·학업설계 Agent API",
    version="0.1.0-vertical-slice",
    description=(
        "Vertical Slice API. Evidence·Trait 판정·Explicit Conflict 판정·Career Profile·"
        "전공 Matching은 실제 계산 경로다(LLM 미연동이어도 무관한 Mock으로 대체하지 않음). "
        "LangSmith Trace도 LANGSMITH_TRACING=true일 때 실제로 기록된다. Assessment 답변·질문 "
        "생성 루프는 LangGraph StateGraph로 연결돼 있다. Major Exploration·Course Planning "
        "Workflow는 범위 밖이다."
    ),
)


@app.exception_handler(RequestValidationError)
async def _handle_request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """2026-08-22 4차 리뷰: StrictInt 등 Pydantic 자체 타입 검증이 걸리면 FastAPI 기본
    핸들러가 `{"detail": [{"loc": ..., "msg": ..., "type": ...}]}` 형태로 응답한다 —
    이 서비스의 모든 다른 검증 오류(§3, ContextSelectionError 등)는 항상
    `{"detail": {"error_code": "VALIDATION_ERROR", "message": ...}}` 형태다. B가 오류를
    한 가지 방식으로만 처리할 수 있도록, Pydantic 검증 실패도 같은 형태로 맞춘다.

    원본 요청 값(exc.errors()[i]["input"])은 절대 message에 담지 않는다 — 어떤 필드가
    문제인지(JSON 경로)만 알려준다. 자유서술 답변 같은 민감한 원문이 여기로 들어올 일은
    없지만("body -> ratings -> game" 같은 구조적 위치만 다루므로), 그래도 원칙을 지킨다."""

    locations = [".".join(str(part) for part in err["loc"]) for err in exc.errors()]
    return JSONResponse(
        status_code=422,
        content={
            "detail": APIError(
                error_code=APIErrorCode.VALIDATION_ERROR,
                message=f"요청 형식이 올바르지 않습니다: {locations}",
            ).model_dump()
        },
    )


_store = InMemorySessionStore()

# 설계안 §1: 공모전 프로토타입은 로그인 없이 demo_user_01 단일 사용자만 지원한다.
# 2026-08-20 보안 리뷰 반영: 이전에는 create_session이 클라이언트가 보낸 user_id를
# 그대로 받아 저장했다 — 인증 없이 아무 문자열이나 자기 자신이라고 주장할 수 있는
# Identity Spoofing이었다. 지금은 서버가 유일하게 지원하는 사용자로 고정해서 막는다.
#
# 이것과 별개로, session_id만 알면 그 세션의 Profile·전공·과목·Subgraph를 전부 조회할 수
# 있다는 Broken Access Control 문제는 여전히 구조적으로 남아 있다. 지금은 사용자가
# demo_user_01 하나뿐이라 "다른 사람 데이터 유출"이 실제로 발생하진 않지만, §1 후속 확장
# (회원가입과 실제 다중 사용자 운영)을 구현할 때는 모든 session_id 기반 Endpoint에
# "인증된 호출자가 이 세션의 소유자인가"를 검사하는 로직을 반드시 추가해야 한다.
DEMO_USER_ID = "demo_user_01"

TRAIT_DEFINITIONS_BY_ID = {t.trait_id: t for t in VERTICAL_SLICE_TRAITS}
ALL_TRAIT_LABELS = {tid: t.label for tid, t in TRAIT_DEFINITIONS_BY_ID.items()}
CONTEXT_DEFINITIONS_BY_ID = {c.context_id: c for c in CONTEXT_DEFINITIONS}

# §10/§11 실시간 LLM 질문 생성 — 명시적으로 켜져 있고(.env ENABLE_LLM_QUESTION_GENERATION)
# 설정이 완전할 때만 활성화한다. 꺼져 있거나 Key가 없으면 조용히 Mock 경로로 돌아간다
# (CLAUDE.md "외부 API 실패를 성공 응답으로 위장하지 않는다" — 이건 실패 위장이 아니라
# 애초에 기능이 꺼진 상태이므로 문제 없다).
_llm_client: ChatLLMClient | None = None
if llm_generation_enabled():
    try:
        _llm_client = OpenAIChatClient(load_chat_llm_settings())
    except LLMSettingsError as exc:
        print(f"[warn] ENABLE_LLM_QUESTION_GENERATION=true이지만 설정이 불완전합니다: {exc}")

# §24 LangSmith Observability — LLM 연동과 동일한 패턴: 명시적으로 켜져 있고 설정이
# 완전할 때만 실제 Client를 만든다. 꺼져 있거나 설정이 없으면 Tracer가 client=None으로
# 항상 조용히 아무것도 안 한다(fail-open) — 세션 진행에는 영향이 없다.
_trace_client: TraceClient | None = None
if tracing_enabled():
    try:
        _trace_client = LangSmithTraceClient(load_tracing_settings())
    except TracingSettingsError as exc:
        print(f"[warn] LANGSMITH_TRACING=true이지만 설정이 불완전합니다: {exc}")
_tracer = Tracer(_trace_client)

# 2026-08-22 7차: 학과 탐색 1단계 통합 — C의 JsonlDepartmentRepository를 앱 시작 시점에
# 한 번만 읽는다(요청마다 파일을 다시 열지 않는다). 파일 누락·형식 오류를 조용히 Mock
# 데이터로 대체하지 않는다 — JsonlDepartmentRepository()가 형식 오류는 그대로 예외로
# 던지고(원인 은폐 금지), 파일이 아예 없으면 빈 목록으로 초기화되므로 그 경우만 여기서
# 명시적으로 경고한다(LLM/LangSmith와 같은 "설정 없음은 조용히 넘어간다" 패턴과 달리,
# 학과 데이터는 이 서비스의 핵심 기능이라 비어 있으면 원인을 바로 알 수 있어야 한다).
_department_repository = JsonlDepartmentRepository()
if len(_department_repository) == 0:
    print(
        "[warn] JsonlDepartmentRepository가 비어 있습니다 — "
        "data/master/departments.jsonl 경로·형식을 확인하세요."
    )
# 2026-08-22 10차: 실제로 추천 가능한 대표 전공(VERTICAL_SLICE_MAJOR_PROFILES에서 그대로
# 읽는다 — 별도로 하드코딩하지 않는다)에는 학과 단위 추천 적격성 정책을 Fail-Closed로
# 적용한다. 정책 데이터도 Repository와 동일하게 앱 시작 시 한 번만 읽는다.
_department_recommendation_scope_policy = JsonlDepartmentRecommendationScopePolicy()
_major_exploration_service = MajorExplorationService(
    _department_repository,
    recommendation_scope_policy=_department_recommendation_scope_policy,
    fail_closed_major_ids=frozenset(m.major_id for m in VERTICAL_SLICE_MAJOR_PROFILES),
)

# 2026-08-24 14차 리뷰: GET /subjects/{session_id}?selected_major_id=... — 과목 데이터도
# 학과 Repository와 같은 패턴으로 앱 시작 시 한 번만 읽는다.
_subject_repository = JsonlSubjectRepository()
if len(_subject_repository) == 0:
    print(
        "[warn] JsonlSubjectRepository가 비어 있습니다 — "
        "data/master/subjects.jsonl 경로·형식을 확인하세요."
    )
_course_planning_store = InMemoryCoursePlanningStore()
_course_planning_service = CoursePlanningService(
    _subject_repository,
    major_profiles=VERTICAL_SLICE_MAJOR_PROFILES,
    trait_definitions=TRAIT_DEFINITIONS_BY_ID,
    course_planning_store=_course_planning_store,
)

# 2026-08-26 16차 리뷰: POST /course/upload — 실제 Parser를 연결한다. Alias 표도 학과·
# 과목 Repository와 같은 패턴으로 앱 시작 시 한 번만 읽는다.
_subject_alias_index = SubjectAliasIndex.load(
    Path(__file__).resolve().parents[2] / "data" / "master" / "subject_aliases.jsonl"
)
_course_document_parsing_service = CourseDocumentParsingService(
    _subject_alias_index,
    _subject_repository,
    _course_planning_service,
    _course_planning_store,
)

# 2026-08-28 19차 리뷰: GET /subgraph/{session_id} — 실제 Knowledge Subgraph. Major/
# Subject-Trait Mapping Evidence도 학과·과목 Repository와 같은 패턴으로 앱 시작 시 한 번만
# 읽는다(파일이 없으면 빈 리스트 — build 스크립트가 아니라 런타임이므로 여기선 경고만
# 남기지 않는다, MajorProfile Vector 자체가 이미 이 파일로 만들어졌으므로 있는 게 정상).
_knowledge_subgraph_service = KnowledgeSubgraphService(
    major_profiles=VERTICAL_SLICE_MAJOR_PROFILES,
    trait_definitions=TRAIT_DEFINITIONS_BY_ID,
    major_trait_records=load_major_trait_mapping_evidence(),
    subject_trait_records=load_subject_trait_mapping_evidence(),
    major_exploration_service=_major_exploration_service,
    course_planning_service=_course_planning_service,
    course_planning_store=_course_planning_store,
    subject_repository=_subject_repository,
)


def _advance_to_next_context_or_complete(state: AssessmentState) -> bool:
    """§11 Fallback: Backup Question까지 소진되면 해당 Context를 조기 종료한다.
    다음 Context가 있으면 이동 후 True, 없으면 세션을 완료 처리하고 False를 반환한다."""

    if state.current_context_index + 1 < len(state.context_processing_order):
        state.current_context_index += 1
        state.questions_asked_in_current_context = 0
        state.used_frame_ids_in_current_context = []
        state.generated_question_texts_in_current_context = []
        state.pending_target_traits = []
        state.pending_question_frame = None
        state.pending_purpose = None
        state.pending_next_probe = None
        state.pending_previous_question_text = None
        state.pending_previous_answer_text = None
        state.pending_option_blueprint_id = None
        state.current_context_seed_trait_id = None
        state.resolution_questions_asked_in_current_context = 0
        state.pending_resolution_contrast_id = None
        return True
    state.phase = AssessmentPhase.PROFILE_GENERATION
    return False


def _get_state_or_404(session_id: str) -> AssessmentState:
    state = _store.load(session_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail=APIError(
                error_code=APIErrorCode.SESSION_NOT_FOUND,
                message=f"session_id {session_id!r}를 찾을 수 없습니다.",
            ).model_dump(),
        )
    return state


@app.post("/assessment/session", response_model=CreateSessionResponse)
def create_session() -> CreateSessionResponse:
    session_id = generate_session_id()
    _store.save(AssessmentState(session_id=session_id, user_id=DEMO_USER_ID))
    return CreateSessionResponse(session_id=session_id, user_id=DEMO_USER_ID)


@app.post("/assessment/interest-rating", response_model=InterestRatingResponse)
def submit_interest_rating(payload: InterestRatingRequest) -> InterestRatingResponse:
    state = _get_state_or_404(payload.session_id)
    try:
        # 2026-08-22 3차 리뷰: 이 값이 그대로 Context Selector(§5-1/§6-5) 입력으로 쓰이므로
        # 범위 밖 점수·미등록 Context id·빈 입력을 여기서 구조적으로 막는다. 최소 개수는
        # 지금 유일하게 지원하는 Vertical Slice 모드 기준(§5-1 선호 Context 최소 개수와
        # 동일한 상수를 재사용 — Full Mode 전환 시 이 값만 바꾸면 된다).
        validate_interest_ratings(
            payload.ratings, CONTEXT_IDS, minimum_count=MINIMUM_PREFERRED_CONTEXT_COUNT_VERTICAL_SLICE
        )
    except ContextSelectionError as exc:
        raise HTTPException(
            status_code=422,
            detail=APIError(error_code=APIErrorCode.VALIDATION_ERROR, message=str(exc)).model_dump(),
        ) from exc

    state.interest_ratings = payload.ratings
    state.phase = AssessmentPhase.CONTEXT_SELECTION
    _store.save(state)
    return InterestRatingResponse(session_id=state.session_id, accepted=True)


@app.post("/assessment/context-select", response_model=ContextSelectResponse)
def select_contexts(payload: ContextSelectRequest) -> ContextSelectResponse:
    state = _get_state_or_404(payload.session_id)
    try:
        validate_context_id_list(
            payload.selected_preferred_context_ids,
            CONTEXT_IDS,
            minimum_count=MINIMUM_PREFERRED_CONTEXT_COUNT_VERTICAL_SLICE,
            label="선호 Context",
        )
    except ContextSelectionError as exc:
        raise HTTPException(
            status_code=422,
            detail=APIError(error_code=APIErrorCode.VALIDATION_ERROR, message=str(exc)).model_dump(),
        ) from exc

    state.selected_preferred_contexts = payload.selected_preferred_context_ids
    state.phase = AssessmentPhase.CONTRAST_PROPOSAL
    # §5-1/§6-5: 실제 계산 — 관심도 평가와 사전 정의된 Context Vector·Coverage Matrix만
    # 사용한다(학생의 Trait 점수나 전공 순위는 절대 참조하지 않는다, CLAUDE.md).
    selection = select_contrast_context(
        preferred_context_ids=state.selected_preferred_contexts,
        interest_ratings=state.interest_ratings,
        all_context_ids=CONTEXT_IDS,
        context_vectors=CONTEXT_VECTORS,
        coverage_matrix=CONTEXT_TRAIT_COVERAGE,
        all_trait_ids=VERTICAL_SLICE_TRAIT_IDS,
        trait_labels=ALL_TRAIT_LABELS,
    )
    # 2026-08-22 리뷰: 계산 결과를 State에 저장한다 — 이전에는 응답으로만 나가고 저장되지
    # 않아서, 이후 조회·복원 시 이번에 실제로 뭘 제안했는지 알 수 없었다.
    state.contrast_context_id = selection.contrast_context_id
    _store.save(state)
    _tracer.record_stage(
        trace_id=state.trace_id,
        stage_name="Context Selector",
        attributes={"graph_node": "context_selector", "context_id": selection.contrast_context_id},
    )
    return ContextSelectResponse(
        session_id=state.session_id,
        contrast_context_id=selection.contrast_context_id,
        contrast_reason=selection.contrast_reason,
        coverage_replacement_offered=[],
    )


@app.post("/assessment/context-confirm", response_model=ContextConfirmResponse)
def confirm_contexts(payload: ContextConfirmRequest) -> ContextConfirmResponse:
    state = _get_state_or_404(payload.session_id)
    try:
        # 구조적 검증(빈 목록·중복·미지의 Context id) — "제안한 후보만 허용"으로 강제하지
        # 않는다. 학생이 다른 Context로 교체할 수 있어야 한다(§5-1).
        validate_context_id_list(
            payload.final_context_ids, CONTEXT_IDS, minimum_count=1, label="최종 Context"
        )
        # Vertical Slice 운영 제약: 실제 질문 흐름(Seed·Option Blueprint)이 아직
        # game/media/school_life 3개만 지원한다 — 다른 유효한 Context를 확정하면
        # /assessment/next-question에서야 뒤늦게 실패하므로 여기서 먼저 막는다.
        unsupported = sorted(set(payload.final_context_ids) - set(VERTICAL_SLICE_CONTEXT_IDS))
        if unsupported:
            raise ContextSelectionError(
                f"Vertical Slice는 아직 다음 Context의 실제 질문 흐름을 지원하지 않습니다: "
                f"{unsupported} (지원: {VERTICAL_SLICE_CONTEXT_IDS})"
            )
    except ContextSelectionError as exc:
        raise HTTPException(
            status_code=422,
            detail=APIError(error_code=APIErrorCode.VALIDATION_ERROR, message=str(exc)).model_dump(),
        ) from exc

    state.final_contexts = payload.final_context_ids
    state.context_processing_order = payload.final_context_ids
    state.phase = AssessmentPhase.QUESTION_LOOP
    _store.save(state)
    return ContextConfirmResponse(
        session_id=state.session_id,
        final_context_ids=state.final_contexts,
        processing_order=state.context_processing_order,
    )


@app.post("/assessment/next-question", response_model=NextQuestionResponse)
def next_question(session_id: str) -> NextQuestionResponse:
    state = _get_state_or_404(session_id)
    current_context = state.current_context_id
    if current_context is None:
        raise HTTPException(
            status_code=422,
            detail=APIError(
                error_code=APIErrorCode.VALIDATION_ERROR,
                message="Context가 아직 확정되지 않았습니다. /assessment/context-confirm을 먼저 호출하세요.",
            ).model_dump(),
        )

    status = QuestionDeliveryStatus.GENERATED

    if state.pending_resolution_contrast_id is not None:
        # 2026-08-22 §12-1 확장: Explicit Conflict 확인 질문은 LLM/Mock이 아니라 사람이
        # 미리 검토한 고정 문항을 그대로 낸다(Backup Question과 같은 신뢰도 이유).
        builder = VERTICAL_SLICE_RESOLUTION_QUESTION_BUILDERS.get(state.pending_resolution_contrast_id)
        if builder is not None:
            question = builder(current_context)
            state.current_question = question
            _store.save(state)
            return NextQuestionResponse(
                session_id=session_id,
                status=QuestionDeliveryStatus.GENERATED,
                question=question,
                current_context_id=current_context,
                questions_asked_in_current_context=state.questions_asked_in_current_context,
                assessment_complete=False,
            )

    if state.questions_asked_in_current_context == 0:
        # Context의 첫 질문 — 실제 확정된 Seed Question(§7-1)을 그대로 반환한다.
        question = mock_data.next_mock_question(current_context, 0)
    elif _llm_client is not None and state.pending_target_traits and state.pending_option_blueprint_id:
        question_id = generate_question_id(
            current_context, "tail", state.questions_asked_in_current_context
        )
        frame_id = state.pending_question_frame or "problem_check"
        outcome = generate_tail_question(
            question_id=question_id,
            context_definition=CONTEXT_DEFINITIONS_BY_ID[current_context],
            trait_definition=TRAIT_DEFINITIONS_BY_ID[state.pending_target_traits[0]],
            all_trait_labels=ALL_TRAIT_LABELS,
            option_blueprint_id=state.pending_option_blueprint_id,
            frame_id=frame_id,
            frame_text=QUESTION_FRAME_TEXT.get(frame_id, "다음 상황에서 어떻게 하나요?"),
            llm_client=_llm_client,
            purpose=state.pending_purpose,
            previous_question_texts=state.generated_question_texts_in_current_context,
            previous_answer_text=state.pending_previous_answer_text,
            previous_next_probe=state.pending_next_probe,
            backup_questions=VERTICAL_SLICE_BACKUP_QUESTIONS.get(current_context, []),
            used_backup_question_ids=set(state.used_backup_question_ids),
        )
        _tracer.record_stage(
            trace_id=state.trace_id,
            stage_name="Question Generator",
            attributes={
                "graph_node": "question_generator",
                "context_id": current_context,
                "frame_id": frame_id,
                "blueprint_id": state.pending_option_blueprint_id,
                "trait_ids": state.pending_target_traits,
                "source": outcome.source,
                # 2026-08-22 리뷰: 예외/실패 메시지 원문 대신 고정된 error_type만 보낸다.
                "error_type": classify_generation_failure(outcome.failure_reason),
            },
        )
        if outcome.source in {"backup", "exhausted"}:
            _tracer.record_stage(
                trace_id=state.trace_id,
                stage_name="재생성 또는 Fallback",
                attributes={
                    "graph_node": "regeneration_or_fallback",
                    "context_id": current_context,
                    "cache_or_fallback_status": outcome.source,
                    "fallback_source": outcome.source,
                    "error_type": classify_generation_failure(outcome.failure_reason),
                },
            )
        if outcome.question is None:
            # §11 Fallback 소진 — Context 조기 종료. 남은 재생성·Backup 경로를 다 썼다는
            # 뜻이라 조용히 넘기지 않고 상태를 남긴다.
            has_next_context = _advance_to_next_context_or_complete(state)
            state.current_question = None
            _store.save(state)
            return NextQuestionResponse(
                session_id=session_id,
                status=QuestionDeliveryStatus.CONTEXT_EARLY_TERMINATED,
                question=None,
                current_context_id=state.current_context_id,
                questions_asked_in_current_context=state.questions_asked_in_current_context,
                assessment_complete=not has_next_context,
            )
        question = outcome.question
        state.generated_question_texts_in_current_context.append(question.question_text)
        if outcome.source == "backup":
            state.used_backup_question_ids.append(question.question_id)
            status = QuestionDeliveryStatus.BACKUP_USED
        elif outcome.source == "cache":
            status = QuestionDeliveryStatus.CACHE_USED
        else:
            status = QuestionDeliveryStatus.GENERATED
    else:
        # LLM 미연동(.env ENABLE_LLM_QUESTION_GENERATION 미설정) 상태의 기존 Mock 경로.
        question_id = generate_question_id(
            current_context, "tail", state.questions_asked_in_current_context
        )
        question = mock_data.tail_question_from_planner_decision(
            question_id,
            current_context,
            state.pending_target_traits,
            state.pending_question_frame or "problem_check",
        )

    state.current_question = question
    _store.save(state)
    return NextQuestionResponse(
        session_id=session_id,
        status=status,
        question=question,
        current_context_id=current_context,
        questions_asked_in_current_context=state.questions_asked_in_current_context,
        assessment_complete=False,
    )


@app.post("/assessment/answer", response_model=AnswerResponse)
def submit_answer(payload: AnswerRequest) -> AnswerResponse:
    """실제 답변 처리 파이프라인(§5-2): Option 검증 → EvidenceRecord → Trait Summary →
    Stop/Continue(§5-3) → (CONTINUE면) Target Planner(§8). LLM 질문 생성만 아직 Mock이다."""

    state = _get_state_or_404(payload.session_id)

    if state.current_question is None or state.current_question.question_id != payload.question_id:
        raise HTTPException(
            status_code=422,
            detail=APIError(
                error_code=APIErrorCode.VALIDATION_ERROR,
                message="현재 세션에 제시된 질문과 question_id가 다릅니다. 먼저 /assessment/next-question을 호출하세요.",
            ).model_dump(),
        )

    is_first_context_in_session = state.current_context_index == 0
    result = process_answer_submission(
        state,
        state.current_question,
        payload.selected_option_id,
        VERTICAL_SLICE_TRAIT_IDS,
        is_first_context_in_session,
        VERTICAL_SLICE_CONTRAST_DEFINITIONS,
        VERTICAL_SLICE_RESOLUTION_SPECS,
    )

    if not result.accepted:
        raise HTTPException(
            status_code=422,
            detail=APIError(
                error_code=APIErrorCode.VALIDATION_ERROR,
                message=result.rejection_reason or "답변이 거부됐습니다.",
            ).model_dump(),
        )

    latest_evidence = state.evidence_ledger[-1] if state.evidence_ledger else None
    _tracer.record_stage(
        trace_id=state.trace_id,
        stage_name="Evidence Update",
        attributes={
            "graph_node": "evidence_update",
            "context_id": latest_evidence.context if latest_evidence else None,
            "role_id": latest_evidence.option_role_id if latest_evidence else None,
            "trait_ids": list(latest_evidence.applied_primary_trait_delta) if latest_evidence else [],
        },
    )
    _tracer.record_stage(
        trace_id=state.trace_id,
        stage_name="Stop / Continue Decision",
        attributes={"graph_node": "stop_continue_decision", "stop_reason": result.stop_decision},
    )

    if result.stop_decision == "STOP":
        has_next_context = _advance_to_next_context_or_complete(state)
        next_action = "CONTEXT_COMPLETE" if has_next_context else "ASSESSMENT_COMPLETE"
    else:
        decision = result.next_planner_decision
        state.pending_target_traits = decision.target_traits if decision else []
        state.pending_question_frame = decision.question_frame if decision else None
        state.pending_purpose = decision.purpose if decision else None
        state.pending_option_blueprint_id = decision.option_blueprint_id if decision else None
        next_action = "NEXT_QUESTION"
        _tracer.record_stage(
            trace_id=state.trace_id,
            stage_name="Target Planner",
            attributes={
                "graph_node": "target_planner",
                "trait_ids": decision.target_traits if decision else [],
                "frame_id": decision.question_frame if decision else None,
                "blueprint_id": decision.option_blueprint_id if decision else None,
                "planner_decision_reason": decision.purpose if decision else None,
            },
        )

    _store.save(state)
    return AnswerResponse(session_id=state.session_id, accepted=True, next_action=next_action)


@app.get("/profile/{session_id}", response_model=ProfileResponse)
def get_profile(session_id: str) -> ProfileResponse:
    """2026-08-21 리뷰 반영: 예전엔 `_llm_client is None`이면 실제 Evidence가 있어도
    무관한 고정 Mock Profile을 반환했다 — 다른 학생 결과를 보여주는 꼴이라 제거했다.
    Trait Evidence가 하나라도 있으면(=Seed 이상 답변) LLM 연동 여부와 무관하게 항상
    이 세션의 실제 계산 결과를 반환한다(LLM 없으면 `_fallback_profile()`류 결정론적
    문장으로 자동 전환 — generate_career_profile 내부에서 처리). 답변이 전혀 없으면
    Profile을 꾸며내지 않고 EVIDENCE_NOT_READY를 반환한다."""

    state = _get_state_or_404(session_id)
    if not state.trait_summaries:
        raise HTTPException(
            status_code=422,
            detail=APIError(
                error_code=APIErrorCode.EVIDENCE_NOT_READY,
                message="아직 답변이 없어 Profile을 생성할 Evidence가 없습니다. "
                "먼저 /assessment/next-question과 /assessment/answer로 최소 1개 이상 "
                "답변한 뒤 다시 호출하세요.",
            ).model_dump(),
        )
    profile = generate_career_profile(
        session_id=state.session_id,
        user_id=state.user_id,
        trait_summaries=state.trait_summaries,
        all_trait_definitions=TRAIT_DEFINITIONS_BY_ID,
        evidence_ledger=state.evidence_ledger,
        # 2026-08-21 3단계: /assessment/answer가 매 답변마다 evidence_ledger 전체로 다시
        # 판정해서 저장해둔 값을 그대로 쓴다(이 GET 시점에 다시 계산하지 않음 — evidence_ledger는
        # 이후 안 바뀌므로 같은 결과가 나온다).
        unresolved_conflict_trait_ids=state.unresolved_conflict_trait_ids,
        llm_client=_llm_client,  # None이어도 generate_career_profile이 알아서 Fallback으로 처리
        # 2026-08-22 2차 리뷰: 확인 질문 답변(선호/비선호/상황 의존)을 highlight 우선순위·
        # 문장에 정성적으로 반영한다.
        resolutions=state.contrast_resolutions,
    )
    # §24: highlight 개수·LLM 사용 여부 같은 메타데이터만 남기고, title·highlight 문장
    # 원문은 "상세 Career Profile 문장" 금지 목록에 해당하므로 절대 넘기지 않는다.
    _tracer.record_stage(
        trace_id=state.trace_id,
        stage_name="Profile Summary Generator",
        attributes={
            "graph_node": "profile_summary_generator",
            "used_llm": _llm_client is not None,
            "highlight_count": len(profile.highlights),
        },
    )
    return profile


@app.get("/majors/{session_id}", response_model=MajorsResponse)
def get_majors(session_id: str) -> MajorsResponse:
    """§16은 LLM을 전혀 쓰지 않는 순수 계산이라 예전부터 LLM 연동 여부와 무관하게 항상
    실제 경로를 썼다. 2026-08-21 리뷰 반영: `state.trait_summaries`가 비어 있을 때도
    Mock 전공 목록으로 대체하지 않는다 — compute_major_match()가 Evidence 부족을 이미
    "insufficient" 상태로 정확히 처리하므로, 빈 trait_summaries를 넣어도 자연스럽게
    빈 목록 + insufficient_evidence_message가 나온다. 그래서 별도 분기가 필요 없다."""

    state = _get_state_or_404(session_id)
    student_states = compute_student_trait_states(
        state.trait_summaries,
        TRAIT_DEFINITIONS_BY_ID,
        unresolved_conflict_trait_ids=state.unresolved_conflict_trait_ids,
        # 2026-08-22 2차 리뷰: 확인 질문에서 상대적으로 덜 우선으로 밝혀진 Trait는 여기서
        # normalized_value가 완화된다(0으로 만들지 않음) — Matching에도 해소 결과가 반영된다.
        resolutions=state.contrast_resolutions,
    )
    results = [compute_major_match(student_states, major) for major in VERTICAL_SLICE_MAJOR_PROFILES]
    labels_by_major_id = {m.major_id: m.label for m in VERTICAL_SLICE_MAJOR_PROFILES}
    relevant, explore_together, insufficient_message = rank_major_relevance(results, labels_by_major_id)
    return MajorsResponse(
        session_id=session_id,
        relevant_majors=relevant,
        explore_together_majors=explore_together,
        insufficient_evidence_message=insufficient_message,
    )


@app.get("/departments/{major_id}", response_model=DepartmentsResponse)
def get_departments(major_id: str) -> DepartmentsResponse:
    """2026-08-22 7차: 학과 탐색 1단계 통합 — 더 이상 mock_data.mock_departments()를
    쓰지 않는다. FastAPI는 요청·응답 변환만 하고, 어떤 학과를 어떤 순서로 보여줄지는
    MajorExplorationService(노출 정책)가, 실제 데이터 조회는 JsonlDepartmentRepository
    (C 소유)가 담당한다. 매칭되는 학과가 없거나 major_id가 미등록이면 기존 UX 계약대로
    오류가 아니라 200 + 빈 목록을 반환한다(list_departments_for_major가 이미 그렇게
    동작한다 — 여기서 별도 분기가 필요 없다)."""

    departments = _major_exploration_service.list_departments_for_major(major_id)
    return DepartmentsResponse(major_id=major_id, departments=departments)


@app.get("/subjects/{session_id}", response_model=SubjectsResponse)
def get_subjects(
    session_id: str,
    selected_major_id: str = Query(
        ...,
        description=(
            "학생이 전공 추천 화면에서 선택한 대표 전공(Vertical Slice 3개 중 하나). "
            "예: /subjects/{session_id}?selected_major_id=industrial_engineering"
        ),
    ),
) -> SubjectsResponse:
    """2026-08-24 14차 리뷰: 더 이상 `mock_data.mock_course_profile()`을 쓰지 않는다.
    2026-08-26 16차 리뷰: 이 세션·selected_major_id 조합에 실제로 확정
    (`upload_status == "CONFIRMED"`)된 개설과목이 있으면 POST_OFFERING 최종 추천을,
    없으면 기존과 동일한 PRE_SURVEY 희망과목 추천을 반환한다(§10 —
    `CoursePlanningService.get_course_profile`이 이 분기를 담당한다). `selected_major_id`
    는 여기서만 쓰고 AssessmentState에는 저장하지 않는다(§5, CLAUDE.md "Assessment
    단계에서 전공 추천 결과나 성적을 Planner 입력으로 사용하지 않는다"의 반대 방향도
    지킨다)."""

    state = _get_state_or_404(session_id)
    try:
        return _course_planning_service.get_course_profile(state, selected_major_id)
    except CourseEvidenceNotReadyError as exc:
        raise HTTPException(
            status_code=422,
            detail=APIError(error_code=APIErrorCode.EVIDENCE_NOT_READY, message=str(exc)).model_dump(),
        ) from exc
    except MajorNotSelectableError as exc:
        raise HTTPException(
            status_code=422,
            detail=APIError(error_code=APIErrorCode.MAJOR_NOT_SELECTABLE, message=str(exc)).model_dump(),
        ) from exc


@app.post("/course/upload", response_model=CourseUploadResponse)
async def upload_course_document(
    session_id: str = Form(...),
    selected_major_id: str = Form(
        ..., description="PRE_SURVEY와 동일한 규칙으로 검증되는, 이 업로드가 속할 대표 전공"
    ),
    file: UploadFile = File(...),
) -> CourseUploadResponse:
    """2026-08-26 16차 리뷰: 더 이상 형식만 확인하고 고정 Mock 후보를 돌려주지 않는다.
    `CourseDocumentParsingService`가 실제 Parser(`course_document_parser.py`)·Alias
    표(`data/master/subject_aliases.jsonl`)로 연결한다. 이 Handler는 요청·응답 변환과
    `UploadFile`에서 원본 bytes를 읽는 것까지만 한다 — 과목명 유사도 계산이나 파일
    경로 조립은 전부 Service 쪽에서 한다(Path Traversal 방지: 사용자가 보낸 filename을
    로컬 경로로 직접 쓰지 않는다).

    2026-08-27 17차 리뷰 §3: `await file.read()`로 전체를 한 번에 메모리에 올린 뒤
    크기를 검사하지 않는다 — `read_upload_with_limit`이 chunk 단위로 읽으면서 10MB를
    넘는 순간 그 자리에서 멈춘다(초과분을 이미 메모리에 올려버린 뒤 뒤늦게 거부하지
    않는다)."""

    state = _get_state_or_404(session_id)

    try:
        content = await read_upload_with_limit(file, MAX_UPLOAD_SIZE_BYTES)
    except FileTooLargeError as exc:
        raise HTTPException(
            status_code=422,
            detail=APIError(error_code=APIErrorCode.VALIDATION_ERROR, message=str(exc)).model_dump(),
        ) from exc

    try:
        candidates, warnings = _course_document_parsing_service.parse_upload(
            state, selected_major_id, content, file.filename or "", file.content_type
        )
    except CourseEvidenceNotReadyError as exc:
        raise HTTPException(
            status_code=422,
            detail=APIError(error_code=APIErrorCode.EVIDENCE_NOT_READY, message=str(exc)).model_dump(),
        ) from exc
    except MajorNotSelectableError as exc:
        raise HTTPException(
            status_code=422,
            detail=APIError(error_code=APIErrorCode.MAJOR_NOT_SELECTABLE, message=str(exc)).model_dump(),
        ) from exc
    except (UnsupportedFileTypeError, EmptyFileError, FileTooLargeError) as exc:
        raise HTTPException(
            status_code=422,
            detail=APIError(error_code=APIErrorCode.VALIDATION_ERROR, message=str(exc)).model_dump(),
        ) from exc
    except CourseParsingFailedError as exc:
        raise HTTPException(
            status_code=422,
            detail=APIError(error_code=APIErrorCode.PARSE_FAILED, message=str(exc)).model_dump(),
        ) from exc

    return CourseUploadResponse(
        session_id=session_id,
        selected_major_id=selected_major_id,
        parsed_candidates=candidates,
        parse_warnings=warnings,
    )


@app.post("/course/confirm", response_model=CourseConfirmResponse)
def confirm_course_selection(payload: CourseConfirmRequest) -> CourseConfirmResponse:
    """2026-08-26 16차 리뷰: 더 이상 어떤 ID든 받아 accepted=True만 돌려주는 Mock이
    아니다. `CourseDocumentParsingService.confirm()`이 §6의 모든 검증(정본 존재·이번
    업로드 후보에서 나온 값인지 등)을 통과시킨 뒤, 확정된 실제 개설과목 집합으로
    POST_OFFERING CourseProfile을 함께 계산해 반환한다.

    2026-08-27 17차 리뷰 §2: 검증·추천 계산·Policy Guard가 전부 성공해야만 Store가
    `CONFIRMED`로 갱신된다(원자성) — 그 판단은 전부 `CourseDocumentParsingService.
    confirm()` 내부에서 이뤄지므로, 이 Handler는 더 이상 "confirm 저장 → 별도로
    추천 계산" 두 단계로 나눠 호출하지 않는다(예전에는 그 사이에 계산이 실패하면
    Store에 이미 CONFIRMED만 남는 비원자적 상태가 될 수 있었다)."""

    state = _get_state_or_404(payload.session_id)

    try:
        course_profile = _course_document_parsing_service.confirm(
            state, payload.confirmed_subject_ids
        )
    except CourseUploadNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=APIError(error_code=APIErrorCode.COURSE_UPLOAD_NOT_FOUND, message=str(exc)).model_dump(),
        ) from exc
    except CourseConfirmValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=APIError(error_code=APIErrorCode.VALIDATION_ERROR, message=str(exc)).model_dump(),
        ) from exc
    except CourseEvidenceNotReadyError as exc:
        raise HTTPException(
            status_code=422,
            detail=APIError(error_code=APIErrorCode.EVIDENCE_NOT_READY, message=str(exc)).model_dump(),
        ) from exc
    except MajorNotSelectableError as exc:
        raise HTTPException(
            status_code=422,
            detail=APIError(error_code=APIErrorCode.MAJOR_NOT_SELECTABLE, message=str(exc)).model_dump(),
        ) from exc

    return CourseConfirmResponse(
        session_id=payload.session_id, accepted=True, course_profile=course_profile
    )


@app.get("/subgraph/{session_id}", response_model=SubgraphResponse)
def get_subgraph(session_id: str) -> SubgraphResponse:
    """2026-08-28 19차 리뷰: 더 이상 `mock_data.mock_subgraph()`의 고정 5개 Node가 아니다.
    `KnowledgeSubgraphService`가 이 세션의 실제 Trait·대표 전공·학과·(확정됐다면) 추천
    과목으로 Node·Edge를 계산한다 — 이 Handler는 세션 조회·Service 호출·응답 변환·오류
    코드 매핑만 한다. 성공하면 §10의 Sanitizer를 거친 LangSmith Trace를 남긴다(node_count
    등 개수 요약만 — session_id·학생 답변 원문은 Allowlist에 아예 없어 샐 수 없다)."""

    state = _get_state_or_404(session_id)
    try:
        nodes, edges = _knowledge_subgraph_service.build(state)
    except SubgraphEvidenceNotReadyError as exc:
        raise HTTPException(
            status_code=422,
            detail=APIError(error_code=APIErrorCode.EVIDENCE_NOT_READY, message=str(exc)).model_dump(),
        ) from exc

    # 2026-08-29 19차 후속 보완: "has_confirmed_course_profile"은 원래 "과목 Node가
    # 하나라도 있는가"로 계산했는데, 이건 실제로 다른 질문이다 — CoursePlanningStore가
    # upload_status="CONFIRMED"인데 confirmed_subject_ids=[]라서 HighSchoolSubject
    # Node가 0개인 상태도 있을 수 있다("확정은 했다"와 "확정된 과목이 있다"는 다른
    # 사실). 이 둘을 각각 정확한 이름으로 나눈다. Store 조회는 순수 읽기다 — 추천을
    # 다시 계산하거나 상태를 바꾸지 않는다(KnowledgeSubgraphService.build()가 이미
    # 내부에서 필요하면 조회했다 — 여기서는 Trace 메타데이터만 위해 한 번 더 읽는다).
    planning_state = _course_planning_store.load(session_id)
    has_confirmed_course_profile = planning_state is not None and planning_state.upload_status == "CONFIRMED"
    has_subject_nodes = any(n.node_type == "HighSchoolSubject" for n in nodes)

    _tracer.record_stage(
        trace_id=state.trace_id,
        stage_name="Knowledge Subgraph Extractor",
        attributes={
            "graph_node": "knowledge_subgraph_extractor",
            "node_count": len(nodes),
            "edge_count": len(edges),
            "trait_node_count": sum(1 for n in nodes if n.node_type == "Trait"),
            "major_node_count": sum(1 for n in nodes if n.node_type == "CanonicalMajor"),
            "department_node_count": sum(1 for n in nodes if n.node_type == "Department"),
            "subject_node_count": sum(1 for n in nodes if n.node_type == "HighSchoolSubject"),
            "has_confirmed_course_profile": has_confirmed_course_profile,
            "has_subject_nodes": has_subject_nodes,
        },
    )
    return SubgraphResponse(session_id=session_id, nodes=nodes, edges=edges)


@app.get("/session/{session_id}", response_model=SessionRestoreResponse)
def restore_session(session_id: str) -> SessionRestoreResponse:
    state = _get_state_or_404(session_id)
    return SessionRestoreResponse(
        session_id=state.session_id,
        user_id=state.user_id,
        phase=state.phase.value,
        has_previous_completed_profile=False,  # 실제 Profile Store 연결 전까지는 항상 False
    )
