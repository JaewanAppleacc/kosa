"""FastAPI 앱 — B에게 줄 API 계약의 실행 가능한 형태.

2026-08-22 리뷰 이후 상태(오래된 설명 갱신): Session 생성부터 Context 확정(Contrast Context
Selector 포함, §5-1/§6-5), Evidence·Trait 계산, Explicit Conflict 판정(§12-1), Career
Profile(§14), 전공 Matching(§16), LangSmith Trace(§24, `LANGSMITH_TRACING=true`일 때만)
까지 전부 실제 경로다. "학생 답변 → Evidence Update → Stop/Continue → Target Planner"와
"Question Generator → Quality Gate → 재생성/Backup" 두 구간은 실제 LangGraph StateGraph로
연결돼 있다(src/agents/assessment/graph/). 질문 생성(§10) 자체는 `.env`의
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

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile

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
from src.data.contexts.context_definitions import CONTEXT_DEFINITIONS, CONTEXT_IDS
from src.data.contexts.context_trait_coverage import CONTEXT_TRAIT_COVERAGE
from src.data.contexts.context_vectors import CONTEXT_VECTORS
from src.data.majors.vertical_slice_major_profiles import VERTICAL_SLICE_MAJOR_PROFILES
from src.data.question_frames.frame_role_map import QUESTION_FRAME_TEXT
from src.data.questions.vertical_slice_backup_questions import VERTICAL_SLICE_BACKUP_QUESTIONS
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAIT_IDS, VERTICAL_SLICE_TRAITS
from src.engines.contrast_context_selector import select_contrast_context
from src.engines.matching_engine import (
    compute_major_match,
    compute_student_trait_states,
    rank_major_relevance,
)
from src.ids import generate_question_id, generate_session_id
from src.llm.openai_client import OpenAIChatClient
from src.llm.protocols import ChatLLMClient
from src.llm.settings import LLMSettingsError, llm_generation_enabled, load_chat_llm_settings
from src.memory.session_store import InMemorySessionStore
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
RESOLUTION_ROLE_MAPS_BY_CONTRAST_ID = {
    cid: spec.role_resolution_map for cid, spec in VERTICAL_SLICE_RESOLUTION_SPECS.items()
}

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
        RESOLUTION_ROLE_MAPS_BY_CONTRAST_ID,
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
        state.trait_summaries, TRAIT_DEFINITIONS_BY_ID, unresolved_conflict_trait_ids=state.unresolved_conflict_trait_ids
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
