"""FastAPI 앱 — B에게 줄 API 계약의 실행 가능한 형태.

Session 생성·Context 선택·확정은 실제 AssessmentState를 저장·조회한다(InMemorySessionStore —
DB 아님, 재시작하면 날아감). next-question 이후 단계(질문 생성, Evidence 계산, Profile,
Matching)는 아직 실제 로직이 없어 고정 Mock을 반환한다 — A 지시서 §3 "B가 실제 구현을
기다리지 않고 작업할 수 있도록 Mock 응답을 먼저 제공한다"에 따른 의도적 설계다.

실행: ./.venv/bin/uvicorn src.api.main:app --reload
OpenAPI 문서: http://127.0.0.1:8000/docs (자동 생성, B에게 줄 명세 그 자체)
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from src.api import mock_data
from src.ids import generate_session_id
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
def create_session(user_id: str = "demo_user_01") -> CreateSessionResponse:
    session_id = generate_session_id()
    _store.save(AssessmentState(session_id=session_id, user_id=user_id))
    return CreateSessionResponse(session_id=session_id, user_id=user_id)


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
    current_context = state.current_context_id or "media"
    # 실제 Seed/Adaptive 질문 생성(§7, §10)은 미구현 — Mock 고정 질문 반환
    question = mock_data.mock_finalized_question(
        current_context, state.questions_asked_in_current_context + 1
    )
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
    state = _get_state_or_404(payload.session_id)
    state.questions_asked_in_current_context += 1
    _store.save(state)
    # 실제 Stop/Continue 판단(§5-3)은 미구현 — 5개까지는 계속 진행하는 걸로 Mock 처리
    next_action = "NEXT_QUESTION" if state.questions_asked_in_current_context < 5 else "CONTEXT_COMPLETE"
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


@app.post("/course/upload", response_model=CourseUploadResponse)
def upload_course_document(session_id: str) -> CourseUploadResponse:
    _get_state_or_404(session_id)
    # 실제 파싱(course_document_parser.py)은 C 소유, 미구현 — Mock 후보 반환
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
