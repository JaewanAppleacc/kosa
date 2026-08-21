"""FastAPI 앱 — B에게 줄 API 계약의 실행 가능한 형태.

Session 생성·Context 선택·확정은 실제 AssessmentState를 저장·조회한다(InMemorySessionStore —
DB 아님, 재시작하면 날아감). next-question 이후 단계(질문 생성, Evidence 계산, Profile,
Matching)는 아직 실제 로직이 없어 고정 Mock을 반환한다 — A 지시서 §3 "B가 실제 구현을
기다리지 않고 작업할 수 있도록 Mock 응답을 먼저 제공한다"에 따른 의도적 설계다.

실행: ./.venv/bin/uvicorn src.api.main:app --reload
OpenAPI 문서: http://127.0.0.1:8000/docs (자동 생성, B에게 줄 명세 그 자체)
"""

from __future__ import annotations

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from src.agents.assessment.answer_processor import submit_answer as process_answer_submission
from src.api import mock_data
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAIT_IDS
from src.ids import generate_question_id, generate_session_id
from src.memory.session_store import InMemorySessionStore
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
        "단계 0 계약 확정용 API. next-question 이후 응답은 고정 Mock이며, "
        "실제 LangGraph/LLM/Matching 로직이 붙기 전까지는 화면 데이터 구조 검증 용도로만 쓴다."
    ),
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
    state.interest_ratings = payload.ratings
    state.phase = AssessmentPhase.CONTEXT_SELECTION
    _store.save(state)
    return InterestRatingResponse(session_id=state.session_id, accepted=True)


@app.post("/assessment/context-select", response_model=ContextSelectResponse)
def select_contexts(payload: ContextSelectRequest) -> ContextSelectResponse:
    state = _get_state_or_404(payload.session_id)
    state.selected_preferred_contexts = payload.selected_preferred_context_ids
    state.phase = AssessmentPhase.CONTRAST_PROPOSAL
    _store.save(state)
    # Contrast Context 계산(§6-5)은 아직 미구현 — Mock으로 고정 응답
    return ContextSelectResponse(
        session_id=state.session_id,
        contrast_context_id="business",
        contrast_reason="선택한 4개와 활동 방식 거리가 멀고, 부족한 Shared Trait를 보완합니다(Mock).",
        coverage_replacement_offered=[],
    )


@app.post("/assessment/context-confirm", response_model=ContextConfirmResponse)
def confirm_contexts(payload: ContextConfirmRequest) -> ContextConfirmResponse:
    state = _get_state_or_404(payload.session_id)
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

    if state.questions_asked_in_current_context == 0:
        # Context의 첫 질문 — 실제 확정된 Seed Question(§7-1)을 그대로 반환한다.
        question = mock_data.next_mock_question(current_context, 0)
    else:
        # 꼬리질문: Target Planner(§8)가 직전 답변 처리에서 정한 목표 Trait·Frame을 실제로
        # 반영한다. 선택지 문장 자체는 아직 LLM 연동(§10) 전이라 Mock이다.
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
        status=QuestionDeliveryStatus.GENERATED,
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
    )

    if not result.accepted:
        raise HTTPException(
            status_code=422,
            detail=APIError(
                error_code=APIErrorCode.VALIDATION_ERROR,
                message=result.rejection_reason or "답변이 거부됐습니다.",
            ).model_dump(),
        )

    if result.stop_decision == "STOP":
        if state.current_context_index + 1 < len(state.context_processing_order):
            state.current_context_index += 1
            state.questions_asked_in_current_context = 0
            state.used_frame_ids_in_current_context = []
            state.pending_target_traits = []
            state.pending_question_frame = None
            next_action = "CONTEXT_COMPLETE"
        else:
            state.phase = AssessmentPhase.PROFILE_GENERATION
            next_action = "ASSESSMENT_COMPLETE"
    else:
        decision = result.next_planner_decision
        state.pending_target_traits = decision.target_traits if decision else []
        state.pending_question_frame = decision.question_frame if decision else None
        next_action = "NEXT_QUESTION"

    _store.save(state)
    return AnswerResponse(session_id=state.session_id, accepted=True, next_action=next_action)


@app.get("/profile/{session_id}", response_model=ProfileResponse)
def get_profile(session_id: str) -> ProfileResponse:
    _get_state_or_404(session_id)
    return mock_data.mock_career_profile(session_id)


@app.get("/majors/{session_id}", response_model=MajorsResponse)
def get_majors(session_id: str) -> MajorsResponse:
    _get_state_or_404(session_id)
    relevant, explore_together = mock_data.mock_majors_relevance()
    return MajorsResponse(
        session_id=session_id, relevant_majors=relevant, explore_together_majors=explore_together
    )


@app.get("/departments/{major_id}", response_model=DepartmentsResponse)
def get_departments(major_id: str) -> DepartmentsResponse:
    return DepartmentsResponse(major_id=major_id, departments=mock_data.mock_departments(major_id))


@app.get("/subjects/{session_id}", response_model=SubjectsResponse)
def get_subjects(session_id: str) -> SubjectsResponse:
    _get_state_or_404(session_id)
    return mock_data.mock_course_profile(session_id)


_ALLOWED_COURSE_UPLOAD_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "application/vnd.ms-excel",  # .xls
}


@app.post("/course/upload", response_model=CourseUploadResponse)
async def upload_course_document(
    session_id: str = Form(...), file: UploadFile = File(...)
) -> CourseUploadResponse:
    """2026-08-21 리뷰 반영: 이전에는 session_id만 받고 실제 파일을 받지 않았다 —
    B README가 약속한 "PDF·Excel 업로드"와 실제 계약이 어긋나 있었다. 지금은
    multipart/form-data로 진짜 파일을 받는다. 파싱 자체(course_document_parser.py)는
    여전히 C 소유·미구현이라 형식만 검증하고 Mock 후보를 반환한다.
    """

    _get_state_or_404(session_id)

    if file.content_type not in _ALLOWED_COURSE_UPLOAD_CONTENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=APIError(
                error_code=APIErrorCode.VALIDATION_ERROR,
                message=f"PDF 또는 Excel 파일만 허용합니다. 받은 형식: {file.content_type}",
            ).model_dump(),
        )

    from src.schemas.course import ParsedSubjectCandidate

    return CourseUploadResponse(
        session_id=session_id,
        parsed_candidates=[
            ParsedSubjectCandidate(
                raw_text="데이터과학탐구",
                matched_subject_id=None,
                confidence="low",
                requires_user_confirmation=True,
            )
        ],
    )


@app.post("/course/confirm", response_model=CourseConfirmResponse)
def confirm_course_selection(payload: CourseConfirmRequest) -> CourseConfirmResponse:
    _get_state_or_404(payload.session_id)
    return CourseConfirmResponse(session_id=payload.session_id, accepted=True)


@app.get("/subgraph/{session_id}", response_model=SubgraphResponse)
def get_subgraph(session_id: str) -> SubgraphResponse:
    _get_state_or_404(session_id)
    nodes, edges = mock_data.mock_subgraph(session_id)
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
