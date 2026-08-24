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

import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# 로컬 개발 편의용 — 이미 설정된 실제 배포 환경변수는 덮어쓰지 않는다(override=False가 기본값).
load_dotenv()

from src.agents.assessment.answer_processor import submit_answer as process_answer_submission
from src.agents.assessment.profile_generator import generate_career_profile
from src.agents.assessment.profile_generator_v2 import generate_career_profile_v2
from src.agents.assessment.graph.question_generation_graph import classify_generation_failure
from src.agents.assessment.question_generator import generate_tail_question
from src.agents.assessment.v2_direct_probe_generator import generate_v2_direct_probe_question
from src.api import mock_data
from src.data.conflicts.vertical_slice_contrast_definitions import VERTICAL_SLICE_CONTRAST_DEFINITIONS
from src.data.conflicts.vertical_slice_conflict_resolution_questions import (
    VERTICAL_SLICE_RESOLUTION_QUESTION_BUILDERS,
    VERTICAL_SLICE_RESOLUTION_SPECS,
)
from src.data.contexts.context_anchor_presentations import CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY
from src.data.contexts.context_definitions import CONTEXT_DEFINITIONS, CONTEXT_IDS, VERTICAL_SLICE_CONTEXT_IDS
from src.data.contexts.context_trait_coverage import CONTEXT_TRAIT_COVERAGE
from src.data.contexts.context_vectors import CONTEXT_VECTORS
from src.data.majors.canonical_major_descriptions import CANONICAL_MAJOR_DESCRIPTIONS_BY_ID
from src.data.majors.vertical_slice_major_profiles import VERTICAL_SLICE_MAJOR_PROFILES
from src.data.majors.vertical_slice_major_profiles_v2 import VERTICAL_SLICE_MAJOR_PROFILES_V2
from src.data.question_frames.frame_role_map import QUESTION_FRAME_TEXT
from src.data.questions.context_routing_blueprints import (
    CONTEXT_ROUTING_BLUEPRINTS_BY_CONTEXT,
    CONTEXT_ROUTING_BLUEPRINTS_BY_ID,
)
from src.data.questions.anchor_backup_questions import ANCHOR_BACKUP_QUESTIONS_BY_KEY
from src.data.questions.vertical_slice_backup_questions import VERTICAL_SLICE_BACKUP_QUESTIONS
from src.data.trait_ontology.trait_probe_capabilities_v2 import (
    CORE_TRAIT_IDS,
    DIRECTLY_MEASURABLE_TRAIT_IDS,
    NOT_PROBED_TRAIT_IDS,
    OBSERVABLE_TRAIT_IDS,
    RELATED_ONLY_TRAIT_IDS,
)
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAIT_IDS, VERTICAL_SLICE_TRAITS
from src.engines.contrast_context_selector import (
    ContextSelectionError,
    compute_context_selection_policy,
    select_contrast_context,
    validate_context_id_list,
    validate_interest_ratings,
)
from src.engines.context_pack_adaptive_planner import (
    compute_pack_context_trait_summaries,
    select_pack_adaptive_target,
)
from src.engines.evidence_engine import decide_stop_or_continue
from src.engines.matching_engine import (
    compute_major_match,
    compute_student_trait_states,
    rank_major_relevance,
)
from src.engines.matching_engine_v2 import compute_major_match_v2, rank_major_relevance_v2
from src.engines.trait_vector_snapshot_engine import compute_trait_vector_snapshot_all
from src.engines.v2_direct_probe_selector import select_blueprint_for_trait, select_v2_probe_candidates
from src.ids import generate_evidence_id, generate_question_id, generate_session_id
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
from src.services.course_planning_service_v2 import (
    CourseEvidenceNotReadyErrorV2,
    CoursePlanningServiceV2,
    MajorNotSelectableErrorV2,
)
from src.services.context_pack_registry import ContextPackRegistry
from src.services.context_pack_runtime import ContextPackRuntime
from src.services.context_trait_coverage import compute_context_trait_coverage
from src.services.department_recommendation_scope import JsonlDepartmentRecommendationScopePolicy
from src.services.knowledge_subgraph_service import (
    KnowledgeSubgraphService,
    SubgraphEvidenceNotReadyError,
)
from src.services.major_exploration_service import DEFAULT_SERVICE_MAJOR_IDS, MajorExplorationService
from src.services.feature_flags import (
    MAX_V2_DIRECT_PROBE_QUESTIONS,
    context_pack_runtime_enabled,
    context_selection_4_plus_1_enabled,
    trait_vector_v2_direct_probes_enabled,
    trait_vector_v2_primary_enabled,
)
from src.services.major_trait_mapping_evidence import load_major_trait_mapping_evidence
from src.services.subject_trait_mapping_evidence import load_subject_trait_mapping_evidence
from src.services.trait_ontology_v2 import load_trait_ontology_v2
from src.services.trait_signal_registry import resolve_trait_signals
from src.services.trait_signal_review_gate import filter_primary_eligible_evidence, gate_primary_eligible_evidence
from src.services.trait_vector_shadow_repository import InMemoryTraitVectorShadowRepository
from src.tracing.langsmith_client import LangSmithTraceClient
from src.tracing.protocols import TraceClient
from src.tracing.settings import TracingSettingsError, load_tracing_settings, tracing_enabled
from src.tracing.tracer import Tracer
from src.schemas.api import (
    AnswerRequest,
    AnswerResponse,
    APIError,
    APIErrorCode,
    ContextCatalogItem,
    ContextCatalogResponse,
    ContextConfirmRequest,
    ContextConfirmResponse,
    ContextSelectionPolicyResponse,
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
from src.schemas.assessment_state import AnsweredQuestion, AssessmentPhase, AssessmentState, RoutingAnsweredQuestion
from src.schemas.context_routing import ContextRoutingBlueprint
from src.schemas.evidence import AppliedTraitSignal, EvidenceOrigin, EvidenceRecord, V2ProbeOpportunity
from src.schemas.trait import TraitDefinition
from src.schemas.trait_vector_snapshot import TraitVectorEntry, TraitVectorSnapshot

# 2026-08-23 Trait Ontology v2(2단계) §2 — Shadow 계산 실패는 계속 Fail-Open이지만
# 완전히 조용하지는 않는다: 예외 "종류"만(원인 파악용) 내부 로그에 남긴다. 학생 데이터
# (user_id/session_id/답변·질문·선택지 원문/Trait Vector 전체값/API Key/Trace 원본)는
# 로그 인자에 절대 넣지 않는다 — 아래 handler의 logger.warning() 호출이 예외 타입
# 이름(exc.__class__.__name__)만 %s로 넘기는지 코드 리뷰·테스트로 고정한다.
_logger = logging.getLogger(__name__)

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
# 2026-08-23 Trait Ontology v2(1.5단계) §9 — Shadow Mode 전용 저장소. Career Profile
# Store와 완전히 분리된 별도 객체다: 이 저장소가 뭘 하든(계산 실패든 값이 이상하든)
# 기존 Career Profile 응답에는 절대 영향을 줄 수 없다는 걸 타입 수준에서도 분리해 둔다.
_trait_vector_shadow_repository = InMemoryTraitVectorShadowRepository()
# 2026-08-23 Trait Ontology v2(2.6단계) §9 — Primary 계산 전용 저장소. Shadow 저장소와
# 별도 인스턴스다(같은 session_id라도 "전체 evidence_ledger로 계산한 Shadow 값"과
# "Fail-Closed 게이트를 통과한 evidence_ledger로 계산한 Primary 값"은 서로 다른
# 계산 결과이므로 하나의 저장소에서 덮어쓰면 안 된다).
_trait_vector_primary_repository = InMemoryTraitVectorShadowRepository()

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
# 2026-08-25 지시서(a/national-master-promotion-final-wiring) §4: 전국 학과 1,072건
# 승격으로 fail_closed_major_ids를 VERTICAL_SLICE_MAJOR_PROFILES(3개)로 좁혀 둘 이유가
# 사라졌다 — 1,072건 전부가 이미 Group/Bridge/P1/N.C.E 검수를 통과했고,
# department_recommendation_scope.jsonl에 그 승인 근거가 기록돼 있다. 실제 서비스가
# 추천하는 10개 Canonical Major(DEFAULT_SERVICE_MAJOR_IDS, allowed_major_ids와 같은
# 정본) 전부를 Fail-Closed로 묶는다 — Scope 기록이 없는 Major(hci_ux·design)는 계속
# 빈 목록을 반환한다(허위로 만들어내지 않는다, §4 "hci_ux 0건을 임의로 만들지 않음").
_department_recommendation_scope_policy = JsonlDepartmentRecommendationScopePolicy()
_major_exploration_service = MajorExplorationService(
    _department_repository,
    recommendation_scope_policy=_department_recommendation_scope_policy,
    fail_closed_major_ids=DEFAULT_SERVICE_MAJOR_IDS,
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

# 2026-08-23 Trait Ontology v2(2.6단계) §6/§8/§9 — PRIMARY Flag가 켜졌을 때만 쓰는 v2
# 전용 정본·서비스. Legacy 정본(major_profiles.jsonl/subjects.jsonl)과 완전히 분리된
# 별도 파일을 읽는다 — 앱 시작 시 한 번만 읽는 것도 Legacy와 같은 패턴이다.
TRAIT_DEFINITIONS_V2_BY_ID: dict[str, TraitDefinition] = {t.trait_id: t for t in load_trait_ontology_v2()}
_subject_repository_v2 = JsonlSubjectRepository(
    path=Path(__file__).resolve().parents[2] / "data" / "master" / "subject_profiles_v2.jsonl"
)
_course_planning_service_v2 = CoursePlanningServiceV2(
    _subject_repository_v2,
    major_profiles=VERTICAL_SLICE_MAJOR_PROFILES_V2,
    trait_definitions=TRAIT_DEFINITIONS_V2_BY_ID,
)

# 2026-08-23 Trait Ontology v2(2.8단계) §1/§4 — ContextPack Registry는 앱 시작 시 한 번만
# `src/data/context_packs/`를 훑는다(Department/Subject Repository와 같은 패턴). 이
# 시점에 오류가 나는 개별 Pack이 있어도 앱 전체가 죽지 않는다(discover_context_packs가
# 이미 Fail-Closed로 그 Pack만 제외하고 원인을 보존한다, context_pack_registry.py 참고).
_context_pack_registry = ContextPackRegistry(
    known_context_ids=frozenset(CONTEXT_IDS), known_trait_ids=frozenset(TRAIT_DEFINITIONS_V2_BY_ID),
)
if _context_pack_registry.discovery_errors() or _context_pack_registry.ontology_errors():
    print(
        "[warn] 일부 ContextPack이 구조·Ontology 오류로 제외됐습니다: "
        f"{ {**_context_pack_registry.discovery_errors(), **_context_pack_registry.ontology_errors()} }"
    )
# ENABLE_CONTEXT_PACK_RUNTIME이 꺼져 있으면(기본값) 이 Runtime은 어떤 context_id에도
# 절대 관여하지 않는다(항상 None/빈 목록 반환) — 기존 game/media/school_life 3개와
# 기존 API 값이 완전히 그대로 유지된다(§3-2).
_context_pack_runtime = ContextPackRuntime(
    _context_pack_registry, context_pack_runtime_enabled, frozenset(VERTICAL_SLICE_CONTEXT_IDS),
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
    course_planning_service_v2=_course_planning_service_v2,
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


def _effective_supported_context_ids() -> list[str]:
    """2026-08-23 Trait Ontology v2(2.8단계) §3-1 — `GET /contexts`·`/assessment/
    context-select`·`/assessment/context-confirm`이 전부 이 함수 하나만 호출한다(같은
    집합을 세 곳에서 각자 계산하면 불일치가 생긴다). Flag OFF면 기존 3개 그대로,
    ON이면 Registry가 Fail-Closed로 판정한 승인된 신규 Context만 추가된다."""

    if not context_pack_runtime_enabled():
        return list(VERTICAL_SLICE_CONTEXT_IDS)
    return _context_pack_registry.assessment_supported_context_ids(list(VERTICAL_SLICE_CONTEXT_IDS))


def _current_context_selection_policy():
    """`compute_context_selection_policy()`를 현재 Flag·활성 Context 수로 호출하는
    유일한 지점 — `GET /contexts`·`/assessment/context-select`·`/assessment/
    context-confirm`·앱 시작 검사가 전부 이 함수만 부른다. Flag ON인데 활성 Context가
    5개 미만이면 `ContextSelectionConfigError`가 그대로 올라간다(여기서 잡아 2+1로
    조용히 축소하지 않는다, 지시서 §2)."""

    return compute_context_selection_policy(
        flag_enabled=context_selection_4_plus_1_enabled(),
        effective_supported_context_count=len(_effective_supported_context_ids()),
    )


# 2026-08-24 지시서(a/context-selection-4-plus-1) §2 — 앱이 뜨는 순간 4+1 정책 전제조건을
# 확인한다. Flag가 꺼져 있으면(기본값) 이 호출은 즉시 Vertical Slice 정책을 반환하고
# 끝난다(부작용 없음, 기존 앱 시작 동작과 완전히 동일). Flag가 켜져 있는데 활성 Context가
# 5개 미만이면 여기서 예외가 그대로 올라가 앱 자체가 뜨지 않는다 — "학생 요청 중간에
# 뒤늦게 실패하지 않도록" 하는 지점이 바로 여기다.
_current_context_selection_policy()


def _clear_current_question(state: AssessmentState) -> None:
    """2.2단계 §12/§13 — 성공적으로 처리됐거나(답변 완료) 더 이상 유효하지 않은(Context
    조기 종료) 질문 슬롯을 비운다. 이렇게 해야 (1) 다음 `/assessment/next-question` 호출이
    "아직 답 안 한 질문이 있다"는 재요청 멱등성 분기로 잘못 빠지지 않고, (2) 같은
    question_id로 답변이 다시 오면 기존 "현재 세션에 제시된 질문과 question_id가
    다릅니다" 검증이 자연히 걸려 Evidence 중복 저장을 막는다."""

    state.current_question = None
    state.current_question_family_id = None
    state.current_question_blueprint_id = None
    state.current_question_delivery_status = None
    state.current_question_served_context_id = None


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
        state.current_question_family_id = None
        state.current_question_blueprint_id = None
        return True
    state.phase = AssessmentPhase.PROFILE_GENERATION
    return False


def _compute_v2_snapshot(state: AssessmentState) -> dict:
    """Legacy 판정(`compute_student_trait_states`)과 v2 Trait Vector Snapshot을 한 번에
    계산하는 공용 헬퍼 — `/profile`의 Shadow 기록과 V2 Direct Probe 후보 선택·종료 조건
    판단이 똑같은 계산을 중복 구현하지 않게 한다(§9 "동일 Evidence로 재계산하면 동일
    결과"를 자연히 만족한다 — 계산 로직이 한 곳뿐이므로)."""

    legacy_states = compute_student_trait_states(
        state.trait_summaries, TRAIT_DEFINITIONS_BY_ID,
        unresolved_conflict_trait_ids=state.unresolved_conflict_trait_ids,
        resolutions=state.contrast_resolutions,
    )
    return compute_trait_vector_snapshot_all(
        state.evidence_ledger, legacy_states, state.unresolved_conflict_trait_ids, CORE_TRAIT_IDS,
        v2_probe_opportunities=state.v2_probe_opportunities,
    )


def _compute_v2_primary_snapshot(
    state: AssessmentState,
) -> tuple[dict[str, TraitVectorEntry], list[EvidenceRecord]]:
    """2026-08-23 Trait Ontology v2(2.6단계) §3/§9 — PRIMARY 전용 계산. `_compute_v2_
    snapshot()`(Shadow 기록·V2 Direct Probe 후보 선택용, 검수 상태와 무관하게 항상 전체
    evidence_ledger를 쓴다)과 별도 함수다 — 질문 목표 결정 로직은 검수 상태를 몰라도
    되고 몰라야 한다(§3은 "출력 근거"만 제한한다). Fail-Closed 게이트를 통과한
    evidence_ledger로 같은 엔진을 다시 호출할 뿐, 계산 공식 자체는 전혀 바꾸지 않는다.

    반환값의 두 번째 항목(필터링된 evidence_ledger)은 Profile의 "실제 답변 근거" 절과
    Major/Subject 추천 이유 문구가 검수 미완료 질문의 선택지 문구를 인용하지 않도록
    호출하는 쪽에 그대로 넘긴다."""

    legacy_states = compute_student_trait_states(
        state.trait_summaries, TRAIT_DEFINITIONS_BY_ID,
        unresolved_conflict_trait_ids=state.unresolved_conflict_trait_ids,
        resolutions=state.contrast_resolutions,
    )
    primary_evidence = filter_primary_eligible_evidence(state.evidence_ledger, state.context_anchor_choices, _context_pack_registry)
    entries = compute_trait_vector_snapshot_all(
        primary_evidence, legacy_states, state.unresolved_conflict_trait_ids, CORE_TRAIT_IDS,
        v2_probe_opportunities=state.v2_probe_opportunities,
    )
    return entries, primary_evidence


def _v2_probe_should_continue(state: AssessmentState) -> bool:
    """2단계 §12 종료 조건: 안전 상한(MAX_V2_DIRECT_PROBE_QUESTIONS) 도달, 후보 Trait
    없음, 준비된 Blueprint 없음(Context 불일치) 중 하나라도 해당하면 종료한다. 순수하게
    현재 State에서 다시 계산한다 — 별도 캐시를 유지하지 않는다(Legacy Planner와 같은
    "매번 다시 계산" 패턴)."""

    if state.v2_probe_questions_asked >= MAX_V2_DIRECT_PROBE_QUESTIONS:
        return False
    v2_snapshot = _compute_v2_snapshot(state)
    used_frame_ids = {o.frame_id for o in state.v2_probe_opportunities}
    candidates = select_v2_probe_candidates(
        v2_snapshot, set(state.v2_probed_trait_ids),
        final_contexts=state.final_contexts, used_v2_probe_frame_ids=used_frame_ids,
        preferred_context_ids=state.selected_preferred_contexts, interest_ratings=state.interest_ratings,
    )
    return any(
        select_blueprint_for_trait(
            trait_id,
            related_context_ids=v2_snapshot[trait_id].related_context_ids if trait_id in v2_snapshot else set(),
            preferred_context_ids=state.selected_preferred_contexts,
            final_contexts=state.final_contexts, used_v2_probe_frame_ids=used_frame_ids,
        ) is not None
        for trait_id in candidates
    )


def _enter_v2_direct_probe_phase_if_applicable(state: AssessmentState) -> bool:
    """2단계 §3/§4/§6 — Legacy 검사가 방금 끝난 시점에만 호출된다. Feature Flag가
    꺼져 있으면 아무것도 건드리지 않고 즉시 False를 반환한다(기존 동작 완전 유지가
    최우선이라, State 필드 하나도 건드리지 않는 편이 "OFF에서는 기존 결과가 완전히
    유지돼야 한다"는 완료 조건을 가장 단순하게 보증한다)."""

    if not trait_vector_v2_direct_probes_enabled():
        return False
    if _v2_probe_should_continue(state):
        state.v2_probe_phase = "V2_DIRECT_PROBE"
        return True
    state.v2_probe_phase = "COMPLETE"
    return False


def _serve_next_v2_direct_probe_question(state: AssessmentState) -> "NextQuestionResponse":
    """2단계 §5/§7/§11/§13 — 다음 V2 Direct Probe 질문을 낸다. 후보·Blueprint가 더 이상
    없으면 그 자리에서 세션을 완료 처리한다(§12)."""

    v2_snapshot = _compute_v2_snapshot(state)
    used_frame_ids = {o.frame_id for o in state.v2_probe_opportunities}
    candidates = select_v2_probe_candidates(
        v2_snapshot, set(state.v2_probed_trait_ids),
        final_contexts=state.final_contexts, used_v2_probe_frame_ids=used_frame_ids,
        preferred_context_ids=state.selected_preferred_contexts, interest_ratings=state.interest_ratings,
    )
    state.pending_v2_probe_trait_ids = candidates

    chosen_trait_id: str | None = None
    chosen_blueprint = None
    if state.v2_probe_questions_asked < MAX_V2_DIRECT_PROBE_QUESTIONS:
        for trait_id in candidates:
            blueprint = select_blueprint_for_trait(
                trait_id,
                related_context_ids=v2_snapshot[trait_id].related_context_ids if trait_id in v2_snapshot else set(),
                preferred_context_ids=state.selected_preferred_contexts,
                final_contexts=state.final_contexts, used_v2_probe_frame_ids=used_frame_ids,
            )
            if blueprint is not None:
                chosen_trait_id, chosen_blueprint = trait_id, blueprint
                break

    if chosen_blueprint is None:
        # §12: 후보 Trait 없음 / 준비된 Blueprint 없음 / 안전 상한 도달 — 전부 여기로 모인다.
        state.v2_probe_phase = "COMPLETE"
        state.phase = AssessmentPhase.PROFILE_GENERATION
        _clear_current_question(state)
        _store.save(state)
        return NextQuestionResponse(
            session_id=state.session_id,
            status=QuestionDeliveryStatus.CONTEXT_EARLY_TERMINATED,
            question=None,
            current_context_id=None,
            questions_asked_in_current_context=state.questions_asked_in_current_context,
            assessment_complete=True,
        )

    question_context = next(c for c in chosen_blueprint.allowed_context_ids if c in state.final_contexts)
    question_id = generate_question_id(question_context, "v2_probe", state.v2_probe_questions_asked + 1)
    # 2.5.1단계 §6: 이 Context에서 학생이 고른 Anchor가 있으면 LLM Prompt에 전달한다.
    chosen_anchor_id = state.context_anchor_choices.get(question_context)
    anchor = (
        CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY.get((question_context, chosen_anchor_id))
        if chosen_anchor_id else None
    )
    outcome = generate_v2_direct_probe_question(
        question_id=question_id,
        context_definition=CONTEXT_DEFINITIONS_BY_ID[question_context],
        blueprint=chosen_blueprint,
        llm_client=_llm_client,
        anchor=anchor,
    )
    question = outcome.question
    status = QuestionDeliveryStatus.GENERATED if outcome.source == "llm" else QuestionDeliveryStatus.BACKUP_USED
    state.current_question = question
    state.current_question_family_id = "v2_direct_probe"
    state.current_question_blueprint_id = chosen_blueprint.blueprint_id
    state.current_question_delivery_status = status.value
    state.current_question_served_context_id = question_context
    state.current_v2_probe_target_trait_id = chosen_trait_id
    state.current_v2_probe_blueprint_id = chosen_blueprint.blueprint_id
    _store.save(state)

    _tracer.record_stage(
        trace_id=state.trace_id,
        stage_name="V2 Direct Probe Question Generator",
        attributes={
            "graph_node": "v2_direct_probe_question_generator",
            "context_id": question_context,
            "context_anchor_id": chosen_anchor_id,
            "frame_id": chosen_blueprint.question_frame_id,
            "blueprint_id": chosen_blueprint.blueprint_id,
            "source": outcome.source,
        },
    )

    return NextQuestionResponse(
        session_id=state.session_id,
        status=status,
        question=question,
        current_context_id=question_context,
        questions_asked_in_current_context=state.questions_asked_in_current_context,
        assessment_complete=False,
    )


def _submit_v2_direct_probe_answer(state: AssessmentState, selected_option_id: str) -> "AnswerResponse":
    """2단계 §9/§10 — Direct Probe 답변은 Legacy `process_answer_submission`을 절대
    거치지 않는다(Legacy Evidence·Conflict·Stop Condition·Planner 상태·Coverage 카운터
    전부 미오염, §9 금지 목록). `resolve_trait_signals()`가 항상 `EXACT_BLUEPRINT`를
    반환해야 한다 — Direct Probe Blueprint는 5개 Role 전부 Registry에 등록돼 있다
    (§13 "LEGACY_PRIMARY_ADAPTER에 의존하지 마세요")."""

    question = state.current_question
    selected = next((o for o in question.options if o.option_id == selected_option_id), None)
    if selected is None:
        raise HTTPException(
            status_code=422,
            detail=APIError(
                error_code=APIErrorCode.VALIDATION_ERROR,
                message=f"selected_option_id {selected_option_id!r}가 질문 {question.question_id!r}의 선택지 목록에 없습니다.",
            ).model_dump(),
        )

    resolution = resolve_trait_signals(
        question_family_id="v2_direct_probe",
        blueprint_id=state.current_question_blueprint_id or "",
        role_id=selected.role_id,
        legacy_primary_trait_delta=selected.primary_trait_delta,
        is_resolution_question=False,
    )
    applied_signals = [
        AppliedTraitSignal(
            trait_id=s.trait_id, signal_role=s.signal_role, weight=s.weight,
            related_concept_ids=s.related_concept_ids,
        )
        for s in resolution.signals
    ]

    evidence = EvidenceRecord(
        evidence_id=generate_evidence_id(),
        answer_id=f"ans_{question.question_id}_{len(state.answers) + 1:02d}",
        question_id=question.question_id,
        question_frame_id=question.frame_id,
        option_role_id=selected.role_id,
        option_text=selected.text,
        applied_primary_trait_delta=selected.primary_trait_delta,
        applied_trait_signals_v2=applied_signals,
        trait_signal_mapping_source_v2=resolution.mapping_source,
        evidence_origin=EvidenceOrigin.V2_DIRECT_PROBE,
        context=question.context,
        source_type="v2_direct_probe_question",
        generator_version="v1",
        quality_gate_status="passed",
        # 2.6단계 §3: Fail-Closed 검수 게이트용 — V2 Direct Probe는 항상 blueprint_id가
        # 곧 검수 상태 조회 Key다(v2_direct_probe_review_store.py).
        source_question_family_id="v2_direct_probe",
        source_blueprint_id=state.current_question_blueprint_id,
    )
    state.evidence_ledger.append(evidence)
    state.answers.append(
        AnsweredQuestion(
            question_id=question.question_id, selected_option_id=selected.option_id,
            selected_role_id=selected.role_id,
        )
    )

    target_trait_id = state.current_v2_probe_target_trait_id or ""
    target_signal_selected = any(
        s.trait_id == target_trait_id and s.signal_role == "PRIMARY" for s in resolution.signals
    )
    state.v2_probe_opportunities.append(
        V2ProbeOpportunity(
            question_id=question.question_id,
            blueprint_id=state.current_question_blueprint_id or "",
            target_trait_id=target_trait_id,
            context_id=question.context,
            frame_id=question.frame_id,
            selected_option_id=selected.option_id,
            target_signal_selected=target_signal_selected,
        )
    )
    state.v2_probe_questions_asked += 1
    if target_trait_id:
        state.v2_probed_trait_ids.append(target_trait_id)
    state.current_v2_probe_target_trait_id = None
    state.current_v2_probe_blueprint_id = None

    _tracer.record_stage(
        trace_id=state.trace_id,
        stage_name="V2 Direct Probe Evidence Update",
        attributes={
            "graph_node": "v2_direct_probe_evidence_update",
            "context_id": evidence.context,
            "role_id": evidence.option_role_id,
        },
    )

    if _v2_probe_should_continue(state):
        next_action = "NEXT_QUESTION"
    else:
        state.v2_probe_phase = "COMPLETE"
        state.phase = AssessmentPhase.PROFILE_GENERATION
        next_action = "ASSESSMENT_COMPLETE"

    # 2.2단계 §12/§13: Evidence·Opportunity·Counter가 전부 갱신된 뒤에만 current_question을
    # 정리한다 — 이렇게 해야 (1) 같은 question_id로 다시 답변을 제출하면 아래 submit_answer의
    # 기존 "현재 세션에 제시된 질문과 question_id가 다릅니다" 검사가 자연히 걸려 중복
    # Evidence를 막고, (2) 잘못된 option_id로 거부된 답변(이 지점에 도달하지 못하고 이미
    # 함수 앞부분에서 예외로 끝남)은 current_question이 그대로 남아 재시도할 수 있다.
    _clear_current_question(state)
    _store.save(state)
    return AnswerResponse(session_id=state.session_id, accepted=True, next_action=next_action)


def _pack_context_early_terminate(state: AssessmentState, stop_reason: str) -> "NextQuestionResponse":
    """이 Context에서 더 낼 질문이 없을 때(Anchor 없음/Seed 없음/정상 Stop/Backup까지
    소진) 공통으로 쓰는 조기 종료 경로. `stop_reason`은 학생 API에 노출하지 않는
    내부 진단 문자열이다(§7 Stop Reason 구분, `state.stop_reason` 재사용)."""

    state.stop_reason = stop_reason
    has_next_context = _advance_to_next_context_or_complete(state)
    _clear_current_question(state)
    assessment_complete = not has_next_context
    # Legacy Context 조기 종료와 같은 규칙(위 §11 Fallback 소진 분기와 동일) — 이
    # Pack Context가 세션의 마지막 Context였다면, 곧장 완료 처리하지 않고 v2 Direct
    # Probe 전역 단계로 넘어갈 수 있는지 먼저 확인한다.
    if not has_next_context and _enter_v2_direct_probe_phase_if_applicable(state):
        assessment_complete = False
    _store.save(state)
    return NextQuestionResponse(
        session_id=state.session_id, status=QuestionDeliveryStatus.CONTEXT_EARLY_TERMINATED, question=None,
        current_context_id=state.current_context_id, questions_asked_in_current_context=0,
        assessment_complete=assessment_complete,
    )


def _pack_context_used_blueprint_ids(state: AssessmentState, current_context: str) -> set[str]:
    return {
        e.source_blueprint_id
        for e in state.evidence_ledger
        if e.context == current_context and e.source_question_family_id == "pack_direct_probe"
        and e.source_blueprint_id is not None
    }


def _pack_context_try_backup(state: AssessmentState, current_context: str, anchor_id: str) -> "FinalizedQuestion | None":
    """이 Anchor의 미사용 Backup을 하나 돌려준다(없으면 None) — Adaptive 후보 자체가
    없을 때와, 후보는 있었지만 LLM 생성이 최종 실패했을 때 둘 다 여기로 모인다
    (2026-08-23 2.9.1단계 §4)."""

    backups = _context_pack_runtime.get_backup_candidates(current_context, anchor_id)
    unused = [b for b in backups if b.question_id not in state.used_backup_question_ids]
    return unused[0] if unused else None


def _serve_pack_context_question(state: AssessmentState, current_context: str) -> "NextQuestionResponse":
    """2026-08-23 Trait Ontology v2(2.9단계) §4/§5/§7/§9 — 신규 ContextPack Context
    전용 질문 서빙. Legacy Tail Option Blueprint(12-Trait 전용)는 전혀 쓰지 않는다 —
    ContextPack은 Seed/Backup/Direct Probe만 정의한다(개발 가이드 §2).

    흐름: Seed(위치 0, Trait 질문 Counter 1) → Adaptive Tail(공용 Adaptive Probe
    Blueprint 후보 중 Evidence가 부족한 Trait 우선 — `context_pack_adaptive_planner`)을
    최소 4개·최대 6개(`evidence_engine.decide_stop_or_continue`, Legacy Tail과 동일한
    정책·같은 순수 함수 재사용) → 후보가 바닥나고 아직 최소치 미달이면 그 Anchor의
    Backup을 "질문 생성 실패 대체"로만 사용 → 그래도 없으면 Context 종료. "게임",
    "미디어" 같은 이름을 조건문으로 나열하지 않는다 — `_context_pack_runtime` 호출
    하나로 어떤 신규 Context가 와도 동일하게 동작한다."""

    anchor_id = state.context_anchor_choices.get(current_context)
    if anchor_id is None:
        # 방어적 분기 — Routing이 이 Context의 Anchor를 항상 먼저 정하므로(위 next_question
        # 본문에서 Routing을 먼저 서빙한다) 정상 흐름에서는 도달하지 않는다.
        return _pack_context_early_terminate(state, "PACK_ANCHOR_MISSING")

    if state.questions_asked_in_current_context == 0:
        seed_question = _context_pack_runtime.get_seed_question(current_context, anchor_id)
        if seed_question is None:
            return _pack_context_early_terminate(state, "PACK_SEED_MISSING")
        question = seed_question
        question_family_id = "seed"
        question_blueprint_id = f"{question.question_id}_blueprint"
        status = QuestionDeliveryStatus.GENERATED
    else:
        tail_count = state.questions_asked_in_current_context - 1
        # 2026-08-23 2.9.1단계 §3: Anchor 단위 검수를 반영하려면 후보 조회 자체가 이
        # Anchor를 알아야 한다(Context 단위 승인만으로는 부족하다).
        pack_candidates = _context_pack_runtime.get_direct_probe_candidates(current_context, anchor_id)
        candidate_trait_ids = {bp.trait_id for bp in pack_candidates}
        trait_summaries = compute_pack_context_trait_summaries(
            state.evidence_ledger, state.offered_trait_ids_by_question,
            context_id=current_context, trait_ids=candidate_trait_ids,
        )
        # §4/§7: 최소 4개·최대 6개, Coverage Gap 있으면 계속 — Legacy Tail이 이미 쓰는
        # 그 순수 함수를 그대로 재사용한다(Explicit Conflict는 Pack Context 범위 밖).
        stop_decision = decide_stop_or_continue(tail_count, trait_summaries, candidate_trait_ids, set())

        chosen = None
        if stop_decision == "CONTINUE":
            chosen = select_pack_adaptive_target(
                candidate_pool=pack_candidates, trait_summaries=trait_summaries,
                already_used_blueprint_ids=_pack_context_used_blueprint_ids(state, current_context),
                recent_target_trait_id=(state.recent_target_trait_ids[-1] if state.recent_target_trait_ids else None),
                used_frame_ids=set(state.used_frame_ids_in_current_context), final_contexts=[current_context],
            )

        if chosen is not None:
            question_id = generate_question_id(current_context, "v2_probe", tail_count + 1)
            anchor_presentation = _context_pack_runtime.get_anchor_presentation(current_context, anchor_id)
            # 2026-08-23 2.9.1단계 §4: 공용 Adaptive Probe의 base_question은 Legacy
            # game/media/school_life 문구를 그대로 복제한 것이다 — LLM이 꺼져 있거나
            # 재생성까지 실패하면 그 원본을 신규 Context 학생에게 노출하는 대신
            # (allow_base_question_fallback=False) 이 Anchor의 검수된 Backup으로
            # 넘어간다. Legacy 3-Context 호출(main.py 위쪽 `_serve_next_v2_direct_
            # probe_question`)은 기본값 True를 그대로 써서 회귀하지 않는다.
            outcome = generate_v2_direct_probe_question(
                question_id=question_id, context_definition=CONTEXT_DEFINITIONS_BY_ID[current_context],
                blueprint=chosen.blueprint, llm_client=_llm_client, anchor=anchor_presentation,
                allow_base_question_fallback=False,
            )
            if outcome.question is not None:
                # LLM 경로는 이미 실제 current_context를 돌려주지만, 혹시 모를 불일치를
                # 방어적으로 한 번 더 맞춘다 — Evidence.context가 실제 Context와
                # 어긋나지 않아야 한다.
                question = outcome.question.model_copy(update={"context": current_context})
                status = QuestionDeliveryStatus.GENERATED if outcome.source == "llm" else QuestionDeliveryStatus.BACKUP_USED
                question_family_id = "pack_direct_probe"
                question_blueprint_id = chosen.blueprint.blueprint_id
                state.current_v2_probe_target_trait_id = chosen.trait_id
                state.current_v2_probe_blueprint_id = chosen.blueprint.blueprint_id
            else:
                backup = _pack_context_try_backup(state, current_context, anchor_id)
                if backup is None:
                    return _pack_context_early_terminate(state, f"STOP_GENERATION_EXHAUSTED tail_count={tail_count}")
                question = backup
                question_family_id, question_blueprint_id = "pack_backup", question.question_id
                status = QuestionDeliveryStatus.BACKUP_USED
        elif stop_decision == "CONTINUE" and tail_count < 4:
            # §9: 후보가 바닥났지만 아직 최소 4개도 못 채웠다 — 이때만 Anchor Backup을
            # "실패 대체"로 쓴다(정상 후보가 있는 한 Backup은 절대 선택되지 않는다).
            backup = _pack_context_try_backup(state, current_context, anchor_id)
            if backup is None:
                return _pack_context_early_terminate(state, f"STOP_CANDIDATE_EXHAUSTED tail_count={tail_count}")
            question = backup
            question_family_id, question_blueprint_id = "pack_backup", question.question_id
            status = QuestionDeliveryStatus.BACKUP_USED
        else:
            reason = "STOP_MAX_REACHED" if tail_count >= 6 else "STOP_SUFFICIENT"
            return _pack_context_early_terminate(state, f"{reason} tail_count={tail_count}")

    state.current_question = question
    state.current_question_family_id = question_family_id
    state.current_question_blueprint_id = question_blueprint_id
    state.current_question_delivery_status = status.value
    state.current_question_served_context_id = current_context
    _store.save(state)

    _tracer.record_stage(
        trace_id=state.trace_id,
        stage_name="Pack Context Question Generator",
        attributes={
            "graph_node": "pack_context_question_generator", "context_id": current_context,
            "context_anchor_id": anchor_id, "blueprint_id": question_blueprint_id,
        },
    )

    return NextQuestionResponse(
        session_id=state.session_id, status=status, question=question, current_context_id=current_context,
        questions_asked_in_current_context=state.questions_asked_in_current_context, assessment_complete=False,
    )


def _submit_pack_context_probe_answer(state: AssessmentState, selected_option_id: str) -> "AnswerResponse":
    """2026-08-23 Trait Ontology v2(2.9단계) §5/§7/§10 — Pack Context의 Adaptive Tail
    Direct Probe/Backup 답변. `_submit_v2_direct_probe_answer()`와 같은 Evidence 생성
    원칙(Legacy 12-Trait 전용 Stop/Continue·Target Planner를 건드리지 않음)을 따르되,
    이 답변 자체가 "이번 Context에서 질문 하나를 더 물었다"는 사실은 Legacy `_evidence_
    update()`와 동일하게 `questions_asked_in_current_context`/`offered_trait_ids_by_
    question`/`recent_target_trait_ids`/`used_frame_ids_in_current_context`에 반영한다
    (§10 "Seed·Adaptive·Backup 출처 구분" — 이 Counter들이 없으면 Adaptive Planner가
    몇 번째 질문인지, 어떤 Trait·Frame을 이미 썼는지 알 수 없다). 매 답변 뒤에는 항상
    다음 질문을 다시 `_serve_pack_context_question()`이 결정한다(더 낼지, 다음
    Context로 넘어갈지는 거기서 Stop/Continue로 판단 — 이 함수는 세션을 강제로 끝내지
    않는다, 2.8단계와 달리 "무조건 다음 Context로 전진"하지 않는다)."""

    question = state.current_question
    selected = next((o for o in question.options if o.option_id == selected_option_id), None)
    if selected is None:
        raise HTTPException(
            status_code=422,
            detail=APIError(
                error_code=APIErrorCode.VALIDATION_ERROR,
                message=f"selected_option_id {selected_option_id!r}가 질문 {question.question_id!r}의 선택지 목록에 없습니다.",
            ).model_dump(),
        )

    is_direct_probe = state.current_question_family_id == "pack_direct_probe"
    origin = EvidenceOrigin.V2_DIRECT_PROBE if is_direct_probe else EvidenceOrigin.PRIMARY_BLUEPRINT
    resolution = resolve_trait_signals(
        question_family_id=state.current_question_family_id or "",
        blueprint_id=state.current_question_blueprint_id or "",
        role_id=selected.role_id,
        legacy_primary_trait_delta=selected.primary_trait_delta,
        is_resolution_question=False,
    )
    applied_signals = [
        AppliedTraitSignal(
            trait_id=s.trait_id, signal_role=s.signal_role, weight=s.weight,
            related_concept_ids=s.related_concept_ids,
        )
        for s in resolution.signals
    ]

    evidence = EvidenceRecord(
        evidence_id=generate_evidence_id(),
        answer_id=f"ans_{question.question_id}_{len(state.answers) + 1:02d}",
        question_id=question.question_id, question_frame_id=question.frame_id, option_role_id=selected.role_id,
        option_text=selected.text, applied_primary_trait_delta=selected.primary_trait_delta,
        applied_trait_signals_v2=applied_signals, trait_signal_mapping_source_v2=resolution.mapping_source,
        evidence_origin=origin, context=question.context,
        source_type="pack_context_direct_probe_question" if is_direct_probe else "pack_context_backup_question",
        generator_version="v1", quality_gate_status="passed",
        source_question_family_id=state.current_question_family_id, source_blueprint_id=state.current_question_blueprint_id,
    )
    state.evidence_ledger.append(evidence)
    state.answers.append(
        AnsweredQuestion(
            question_id=question.question_id, selected_option_id=selected.option_id, selected_role_id=selected.role_id,
        )
    )

    # 2026-08-23 2.9단계 §10: Legacy `_evidence_update()`와 같은 Counter들을 여기서도
    # 채운다 — 이게 없으면 Adaptive Planner(`_serve_pack_context_question`)가 몇 번째
    # 질문인지, 이 Context에서 이미 어떤 Trait·Frame을 썼는지 알 수 없다.
    offered_traits: list[str] = []
    for option in question.options:
        offered_traits.extend(option.primary_trait_delta.keys())
    state.offered_trait_ids_by_question[question.question_id] = offered_traits
    if selected.primary_trait_delta:
        state.recent_target_trait_ids.append(next(iter(selected.primary_trait_delta)))
    state.used_frame_ids_in_current_context.append(question.frame_id)
    state.questions_asked_in_current_context += 1

    if is_direct_probe:
        target_trait_id = state.current_v2_probe_target_trait_id or ""
        target_signal_selected = any(
            s.trait_id == target_trait_id and s.signal_role == "PRIMARY" for s in resolution.signals
        )
        state.v2_probe_opportunities.append(
            V2ProbeOpportunity(
                question_id=question.question_id, blueprint_id=state.current_question_blueprint_id or "",
                target_trait_id=target_trait_id, context_id=question.context, frame_id=question.frame_id,
                selected_option_id=selected.option_id, target_signal_selected=target_signal_selected,
            )
        )
        state.v2_probe_questions_asked += 1
        if target_trait_id:
            state.v2_probed_trait_ids.append(target_trait_id)
        state.current_v2_probe_target_trait_id = None
        state.current_v2_probe_blueprint_id = None
    else:
        state.used_backup_question_ids.append(question.question_id)

    _tracer.record_stage(
        trace_id=state.trace_id,
        stage_name="Pack Context Probe Evidence Update",
        attributes={
            "graph_node": "pack_context_probe_evidence_update", "context_id": evidence.context,
            "role_id": evidence.option_role_id,
        },
    )

    # 2026-08-23 2.9단계 §4/§9: 다음이 Adaptive Tail 질문 하나 더인지, 이 Context가
    # 끝나 다음 Context로 넘어가는지, 세션이 완전히 끝나는지는 여기서 미리 판단하지
    # 않는다 — 그다음 `/assessment/next-question` 호출이 `_serve_pack_context_question()`
    # 을 다시 호출해서 그 자리에서 최신 Evidence로 다시 결정한다(Legacy가 같은
    # 질문 하나짜리 결정을 답변 시점·다음 질문 시점 두 곳에서 중복 계산하지 않도록
    # 이미 쓰는 것과 같은 "다음 next-question이 실제 상태를 다시 본다" 원칙). B는
    # 그냥 다음 next-question을 부르면 된다(§19와 동일한 원칙, CONTEXT_COMPLETE 같은
    # 별도 신호를 새로 만들지 않는다) — 실제 종료 여부는 그 응답의
    # `status`/`assessment_complete`가 알려준다.
    _clear_current_question(state)
    _store.save(state)
    return AnswerResponse(session_id=state.session_id, accepted=True, next_action="NEXT_QUESTION")


def _serve_context_routing_question(
    state: AssessmentState, routing_blueprint: "ContextRoutingBlueprint",
) -> "NextQuestionResponse":
    """2.5단계 §4 — Context Routing 질문을 낸다. 항상 고정 문구(`base_question`)를
    그대로 쓴다 — LLM을 호출하지 않는다(§4 "학생에게 특정 상업 게임명이나 장르 지식을
    요구하지 마세요"와 무관하게, Routing 자체가 Trait 점수와 무관한 고정 분류 질문이라
    실시간 생성이 필요 없다). 공개 응답은 다른 질문과 똑같은 `FinalizedQuestion`
    모양이라 B는 아무것도 바꿀 필요가 없다(§10)."""

    question_id = generate_question_id(routing_blueprint.context_id, "routing", 1)
    question = routing_blueprint.base_question.model_copy(update={"question_id": question_id})
    state.current_question = question
    state.current_question_family_id = "context_routing"
    state.current_question_blueprint_id = routing_blueprint.blueprint_id
    state.current_question_delivery_status = QuestionDeliveryStatus.GENERATED.value
    state.current_question_served_context_id = routing_blueprint.context_id
    _store.save(state)

    _tracer.record_stage(
        trace_id=state.trace_id,
        stage_name="Context Routing Question",
        attributes={
            "graph_node": "context_routing_question",
            "context_id": routing_blueprint.context_id,
            "blueprint_id": routing_blueprint.blueprint_id,
        },
    )

    return NextQuestionResponse(
        session_id=state.session_id,
        status=QuestionDeliveryStatus.GENERATED,
        question=question,
        current_context_id=routing_blueprint.context_id,
        questions_asked_in_current_context=state.questions_asked_in_current_context,
        assessment_complete=False,
    )


def _submit_context_routing_answer(state: AssessmentState, selected_option_id: str) -> "AnswerResponse":
    """2.5단계 §2/§5 — Context Routing 답변은 Legacy/v2 파이프라인을 완전히 우회한다.
    `evidence_ledger`/`applied_trait_signals_v2`/`trait_summaries`/
    `offered_trait_ids_by_question`/`v2_probe_opportunities`/Conflict 상태/Legacy
    `answers`/v2 Direct Probe 카운터 중 어느 것도 건드리지 않는다 — `context_anchor_choices`와
    별도의 `routing_answer_history`에만 기록한다."""

    question = state.current_question
    selected = next((o for o in question.options if o.option_id == selected_option_id), None)
    if selected is None:
        raise HTTPException(
            status_code=422,
            detail=APIError(
                error_code=APIErrorCode.VALIDATION_ERROR,
                message=f"selected_option_id {selected_option_id!r}가 질문 {question.question_id!r}의 선택지 목록에 없습니다.",
            ).model_dump(),
        )

    # 2026-08-23 Trait Ontology v2(2.8단계) §4: Legacy Routing Blueprint는 blueprint_id로
    # 조회하지만, 신규 ContextPack Routing Blueprint는 blueprint_id가 Pack 저작자마다
    # 다르므로 이 답변을 서빙한 Context id(`current_question_served_context_id`)로
    # 다시 조회한다 — 서빙 시점과 완전히 동일한 조회 순서(Legacy 우선)를 그대로 따른다.
    routing_blueprint = CONTEXT_ROUTING_BLUEPRINTS_BY_ID.get(state.current_question_blueprint_id)
    if routing_blueprint is None:
        routing_blueprint = _context_pack_runtime.get_routing_question(
            state.current_question_served_context_id or ""
        )
    if routing_blueprint is None:
        raise HTTPException(
            status_code=422,
            detail=APIError(
                error_code=APIErrorCode.VALIDATION_ERROR,
                message=f"blueprint_id {state.current_question_blueprint_id!r}에 해당하는 Routing Blueprint를 찾을 수 없습니다.",
            ).model_dump(),
        )
    anchor = routing_blueprint.anchor_for_role(selected.role_id)

    state.context_anchor_choices[routing_blueprint.context_id] = anchor
    state.routing_answer_history.append(
        RoutingAnsweredQuestion(
            context_id=routing_blueprint.context_id, question_id=question.question_id,
            selected_option_id=selected.option_id, selected_role_id=selected.role_id, context_anchor=anchor,
        )
    )

    _tracer.record_stage(
        trace_id=state.trace_id,
        stage_name="Context Routing Answer",
        attributes={
            "graph_node": "context_routing_answer",
            "context_id": routing_blueprint.context_id,
            "context_anchor": anchor,
        },
    )

    _clear_current_question(state)
    _store.save(state)
    return AnswerResponse(session_id=state.session_id, accepted=True, next_action="NEXT_QUESTION")


def _get_state_or_404(session_id: str) -> AssessmentState:
    """2.3단계 §2 — 예외 원자성: `InMemorySessionStore.load()`는 저장된 객체를 참조
    그대로 반환한다(방어적 복사를 하지 않는다, `src/memory/session_store.py`). 이 함수가
    항상 깊은 복사본을 돌려주면, 호출자가 답변·질문 생성 도중 이 State를 아무리
    변형해도 처리 중간에 예외가 나서 `_store.save(state)`에 끝내 도달하지 못하면 그
    변형은 이 복사본에만 남고 Store에 저장된 원본은 전혀 건드리지 않는다 — Store에
    저장된 상태는 어떤 요청이 "완전히 성공"했을 때만 `_store.save(state)` 한 번으로
    교체된다.

    이 함수를 쓰는 12개 Handler를 전부 확인했다: interest-rating/context-select/
    context-confirm/next-question/answer 5개는 매 mutating 경로 끝에서 반드시
    `_store.save(state)`를 한 번 호출하고(§2 검증), 나머지(profile/majors/subjects/
    course 관련/subgraph/session 복원)는 AssessmentState를 읽기 전용으로만 쓰고
    `_store.save()`를 아예 호출하지 않는다 — 두 경우 모두 복사본을 돌려줘도 기존 동작이
    달라지지 않는다. `src/memory/session_store.py` 자체(`InMemorySessionStore.load()`의
    의미)는 바꾸지 않았다 — 이 파일 밖에서 `_store.load()`를 직접 부르는 테스트 코드
    (예: `main_module._store.load(session_id)`로 State를 읽고 직접 mutate하는 기존
    테스트 패턴)에 영향을 주지 않기 위해서다."""

    state = _store.load(session_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail=APIError(
                error_code=APIErrorCode.SESSION_NOT_FOUND,
                message=f"session_id {session_id!r}를 찾을 수 없습니다.",
            ).model_dump(),
        )
    return state.model_copy(deep=True)


@app.get("/contexts", response_model=ContextCatalogResponse)
def get_context_catalog() -> ContextCatalogResponse:
    """2026-08-30 20차 리뷰: B가 Context 목록·선택 정책을 프론트엔드 상수로 복제하지
    않도록 한다. session_id가 필요 없다 — 이 값은 세션과 무관하게 항상 같다(정본은
    `CONTEXT_DEFINITIONS`, 이 Handler는 그걸 그대로 옮겨 담을 뿐 새 데이터를 만들지
    않는다). `assessment_supported`는 `VERTICAL_SLICE_CONTEXT_IDS`(현재 3개)에 속하는지로
    계산한다 — `/assessment/context-select`가 실제로 검증하는 것과 동일한 기준이다."""

    # 2026-08-23 Trait Ontology v2(2.8단계) §3-1: 위 docstring은 OpenAPI 공개 설명이라
    # Flag OFF에서 문구가 절대 안 바뀌게 그대로 둔다(§9 "OpenAPI byte-identical" 불변식)
    # — 실제 계산은 이제 `_effective_supported_context_ids()`(Flag OFF면 기존 3개
    # 그대로, ON이면 검수 승인된 신규 Context Pack까지 Fail-Closed로 포함)가 한다.
    supported_ids = set(_effective_supported_context_ids())
    contexts = [
        ContextCatalogItem(
            context_id=c.context_id,
            label=c.label,
            description=c.description,
            example_activities=c.example_activities,
            interest_rating_prompt=c.interest_rating_prompt,
            is_core=c.is_core,
            assessment_supported=c.context_id in supported_ids,
        )
        for c in CONTEXT_DEFINITIONS
    ]
    # 2026-08-24 지시서(a/context-selection-4-plus-1) §3: Flag OFF면 이 호출은 앱 시작
    # 검사와 완전히 같은 값(Vertical Slice 상수)을 반환한다 — 새 필드는 추가하지 않는다.
    policy = _current_context_selection_policy()
    return ContextCatalogResponse(
        contexts=contexts,
        selection_policy=ContextSelectionPolicyResponse(
            preferred_context_min_count=policy.preferred_context_min_count,
            preferred_context_max_count=policy.preferred_context_max_count,
            contrast_context_count=policy.contrast_context_count,
            final_context_min_count=policy.final_context_min_count,
            final_context_max_count=policy.final_context_max_count,
            coverage_replacement_enabled=policy.coverage_replacement_enabled,
        ),
    )


@app.post("/assessment/session", response_model=CreateSessionResponse)
def create_session() -> CreateSessionResponse:
    session_id = generate_session_id()
    _store.save(AssessmentState(session_id=session_id, user_id=DEMO_USER_ID))
    return CreateSessionResponse(session_id=session_id, user_id=DEMO_USER_ID)


@app.post("/assessment/interest-rating", response_model=InterestRatingResponse)
def submit_interest_rating(payload: InterestRatingRequest) -> InterestRatingResponse:
    state = _get_state_or_404(payload.session_id)
    policy = _current_context_selection_policy()
    try:
        # 2026-08-22 3차 리뷰: 이 값이 그대로 Context Selector(§5-1/§6-5) 입력으로 쓰이므로
        # 범위 밖 점수·미등록 Context id·빈 입력을 여기서 구조적으로 막는다. 최소 개수는
        # 선호 Context 최소 개수와 같다(Flag OFF 2개, ON 4개) — 선호를 그만큼 고르려면
        # 최소 그만큼은 미리 관심도를 매겨야 한다.
        validate_interest_ratings(
            payload.ratings, CONTEXT_IDS, minimum_count=policy.preferred_context_min_count
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
    """2026-08-30 20차 리뷰: 선호 Context는 등록된 15개가 아니라 실제 질문 흐름이 지원하는
    3개(`VERTICAL_SLICE_CONTEXT_IDS`)에서 "정확히 2개"만 선택할 수 있다 — 예전엔 등록된
    15개 중 아무거나 최소 2개만 통과시켜서, art_design 같은 Context를 골라도 이 단계는
    통과하고 나중에 `/assessment/next-question`에서야 실패했다. 오류 상황을 구분해서
    알려준다: (1) 미등록 Context, (2) 등록됐지만 미지원 Context, (3) 개수 불일치,
    (4) 관심도를 아직 안 매긴 Context."""

    state = _get_state_or_404(payload.session_id)
    effective_supported = _effective_supported_context_ids()
    policy = _current_context_selection_policy()
    try:
        validate_context_id_list(
            payload.selected_preferred_context_ids,
            CONTEXT_IDS,
            minimum_count=policy.preferred_context_min_count,
            maximum_count=policy.preferred_context_max_count,
            label="선호 Context",
        )
        unsupported = sorted(set(payload.selected_preferred_context_ids) - set(effective_supported))
        if unsupported:
            raise ContextSelectionError(
                f"등록은 됐지만 실제 질문 흐름을 아직 지원하지 않는 Context입니다: "
                f"{unsupported} (지원: {effective_supported})"
            )
        not_rated = sorted(set(payload.selected_preferred_context_ids) - set(state.interest_ratings))
        if not_rated:
            raise ContextSelectionError(
                f"관심도 평가를 아직 제출하지 않은 Context는 선호 Context로 선택할 수 없습니다: {not_rated}"
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
    # 2026-08-30 20차 리뷰: all_context_ids를 등록된 15개 전체가 아니라 실제 질문 흐름을
    # 지원하는 Context로 제한한다 — 안 그러면 Contrast 후보가 미지원 Context 중 하나로
    # 제안될 수 있었다. 2026-08-23 2.8단계 §3-1: 이 범위가 이제 `_effective_supported_
    # context_ids()`다 — Flag ON이면 검수 승인된 신규 Context까지 포함된다.
    # `CONTEXT_VECTORS`/`CONTEXT_TRAIT_COVERAGE`는 이미 15개 Context 전부를 담고 있어
    # (Legacy 12-Trait 범위) 새 Context를 넘겨도 KeyError 없이 그대로 동작한다
    # (contrast_context_selector.py가 `.get()` 기반으로 이미 방어적이다).
    selection = select_contrast_context(
        preferred_context_ids=state.selected_preferred_contexts,
        interest_ratings=state.interest_ratings,
        all_context_ids=set(effective_supported),
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
    """2026-08-30 20차 리뷰: 최종 Context는 정확히 3개로 강제하지 않는다 — 학생이
    Contrast Context를 수용하지 않고 선호 2개만으로 진행하는 기존 HITL 흐름을 유지해야
    하므로, 최소 2개·최대 3개 범위로만 검증한다(예전엔 최소 1개만 검사해 사실상 아무
    개수나 통과했다)."""

    state = _get_state_or_404(payload.session_id)
    policy = _current_context_selection_policy()
    flag_on = context_selection_4_plus_1_enabled()
    try:
        # 구조적 검증(빈 목록·중복·미지의 Context id·개수) — "제안한 후보만 허용"으로
        # 강제하지 않는다. 학생이 다른 Context로 교체할 수 있어야 한다(§5-1, Flag OFF).
        validate_context_id_list(
            payload.final_context_ids,
            CONTEXT_IDS,
            minimum_count=policy.final_context_min_count,
            maximum_count=policy.final_context_max_count,
            label="최종 Context",
        )
        # 운영 제약: 실제 질문 흐름(Seed·Backup·Routing)을 지원하는 Context만 확정할 수
        # 있다 — 다른 유효한 Context를 확정하면 /assessment/next-question에서야 뒤늦게
        # 실패하므로 여기서 먼저 막는다. 2026-08-23 2.8단계 §3-1: 기준이 이제
        # `_effective_supported_context_ids()`다(Flag ON이면 검수 승인된 신규 Context
        # 까지 포함).
        effective_supported = _effective_supported_context_ids()
        unsupported = sorted(set(payload.final_context_ids) - set(effective_supported))
        if unsupported:
            raise ContextSelectionError(
                f"다음 Context의 실제 질문 흐름을 아직 지원하지 않습니다: "
                f"{unsupported} (지원: {effective_supported})"
            )
        # 2026-08-24 지시서(a/context-selection-4-plus-1) §6: Flag ON에서는 "선호 4개
        # (그대로)" 또는 "선호 4개 + 제안된 Contrast 1개(수용)" 두 조합만 허용한다 —
        # 선호하지 않은 임의의 Context를 다섯 번째로 끼워 넣을 수 없다. Flag OFF는 기존
        # §5-1 방식(학생이 다른 Context로 교체 가능)을 그대로 유지한다 — 이 검증은 Flag
        # ON에서만 추가된다.
        if flag_on:
            preferred_set = set(state.selected_preferred_contexts)
            submitted_set = set(payload.final_context_ids)
            allowed_fifth = {state.contrast_context_id} if state.contrast_context_id else set()
            is_preferred_only = submitted_set == preferred_set
            is_preferred_plus_contrast = (
                bool(allowed_fifth)
                and submitted_set == preferred_set | allowed_fifth
                and len(payload.final_context_ids) == len(preferred_set) + 1
            )
            if not (is_preferred_only or is_preferred_plus_contrast):
                raise ContextSelectionError(
                    "4+1 정책에서는 선호 Context 4개를 그대로 확정하거나, 그 4개에 제안된 "
                    "Contrast Context 1개를 더한 5개만 확정할 수 있습니다 — 선호하지 않은 "
                    "임의의 Context를 다섯 번째로 추가할 수 없습니다. "
                    f"(선호: {sorted(preferred_set)}, 제안된 Contrast: {state.contrast_context_id}, "
                    f"제출: {sorted(submitted_set)})"
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

    # 2.2단계 §11 — 멱등성: 아직 답하지 않은 질문이 이미 나가 있으면(Legacy/Conflict
    # Resolution/V2 Direct Probe 전부 포함) 그 응답을 그대로 복원해서 돌려준다. LLM·
    # Planner·Registry를 다시 부르지 않는다 — 재요청할 때마다 LLM이 다시 호출돼 비용이
    # 중복되거나 문구가 바뀌는 문제를 없앤다. `status`/`current_context_id`는 최초
    # 서빙 당시 저장해둔 값을 그대로 쓴다(재계산하지 않는다).
    if state.current_question is not None:
        return NextQuestionResponse(
            session_id=session_id,
            status=QuestionDeliveryStatus(state.current_question_delivery_status or "GENERATED"),
            question=state.current_question,
            current_context_id=state.current_question_served_context_id,
            questions_asked_in_current_context=state.questions_asked_in_current_context,
            assessment_complete=False,
        )

    # 2026-08-23 Trait Ontology v2(2단계) §3: Legacy Context 반복이 모두 끝난 뒤에만
    # 이 Phase로 들어온다 — Feature Flag가 꺼져 있으면 이 Phase에 절대 진입하지 않으므로
    # (submit_answer의 _enter_v2_direct_probe_phase_if_applicable), 이 분기 자체가
    # OFF에서는 죽은 코드나 마찬가지다. `state.current_context_id`가 이미 범위 밖(None)
    # 이라 아래 일반 분기보다 먼저 확인해야 한다.
    if state.v2_probe_phase == "V2_DIRECT_PROBE":
        return _serve_next_v2_direct_probe_question(state)

    current_context = state.current_context_id
    if current_context is None:
        raise HTTPException(
            status_code=422,
            detail=APIError(
                error_code=APIErrorCode.VALIDATION_ERROR,
                message="Context가 아직 확정되지 않았습니다. /assessment/context-confirm을 먼저 호출하세요.",
            ).model_dump(),
        )

    # 2026-08-23 Trait Ontology v2(2.5단계) §4/§12 — 이 Context에 처음 진입했고(아직 이
    # Context의 Routing 답변이 없고) Routing Blueprint가 있으면, Seed보다 먼저 낸다.
    # v2 기능 Flag가 켜져 있을 때만 동작한다 — "Feature Flag OFF에서 Legacy Flow가
    # 완전히 그대로 유지돼야 한다"는 기존 불변식(1.5단계부터 모든 라운드에 걸쳐 지켜온
    # 규칙)을 그대로 지킨다. Context 자체(정의·질문 문구)는 이미 재정의됐지만, "Routing
    # 질문이 추가로 하나 더 나가는" 흐름 변화는 v2 실험 범위 안에서만 켠다.
    #
    # 2026-08-23 Trait Ontology v2(2.8단계) §3-1/§4: 신규 ContextPack Context는 Anchor
    # 없이는 Seed 자체를 낼 수 없으므로(Legacy처럼 "Anchor 없는 기본 Seed"가 없다),
    # Routing이 `ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES`가 아니라 별도로
    # `ContextPackRuntime.get_routing_question()`(ENABLE_CONTEXT_PACK_RUNTIME Flag +
    # 검수 승인 여부로 이미 Fail-Closed)이 있으면 항상 먼저 나간다 — Legacy 3개
    # Context의 기존 Routing Gate(위 Flag)는 전혀 건드리지 않는다.
    if current_context not in state.context_anchor_choices:
        routing_blueprint = None
        if trait_vector_v2_direct_probes_enabled():
            routing_blueprint = CONTEXT_ROUTING_BLUEPRINTS_BY_CONTEXT.get(current_context)
        if routing_blueprint is None:
            routing_blueprint = _context_pack_runtime.get_routing_question(current_context)
        if routing_blueprint is not None:
            return _serve_context_routing_question(state, routing_blueprint)

    status = QuestionDeliveryStatus.GENERATED

    if state.pending_resolution_contrast_id is not None:
        # 2026-08-22 §12-1 확장: Explicit Conflict 확인 질문은 LLM/Mock이 아니라 사람이
        # 미리 검토한 고정 문항을 그대로 낸다(Backup Question과 같은 신뢰도 이유).
        builder = VERTICAL_SLICE_RESOLUTION_QUESTION_BUILDERS.get(state.pending_resolution_contrast_id)
        if builder is not None:
            question = builder(current_context)
            state.current_question = question
            # 2026-08-23 Trait Ontology v2(1.5단계) §3: Conflict Resolution 확인 질문은
            # resolve_trait_signals()가 is_resolution_question=True로 항상 무시하지만,
            # 감사 목적으로 family/blueprint id도 의미 있는 값으로 남겨둔다.
            state.current_question_family_id = "conflict_resolution"
            state.current_question_blueprint_id = question.contrast_id or ""
            state.current_question_delivery_status = QuestionDeliveryStatus.GENERATED.value
            state.current_question_served_context_id = current_context
            _store.save(state)
            return NextQuestionResponse(
                session_id=session_id,
                status=QuestionDeliveryStatus.GENERATED,
                question=question,
                current_context_id=current_context,
                questions_asked_in_current_context=state.questions_asked_in_current_context,
                assessment_complete=False,
            )

    # 2026-08-23 Trait Ontology v2(2.8단계) §2/§4: Legacy 3개 Context가 아니면 이 시점
    # 이후로는 전부 ContextPack Runtime이 담당한다 — Legacy Seed Mock 데이터·Tail Option
    # Blueprint(12-Trait 전용)를 전혀 참조하지 않는다. Routing을 아직 안 거쳤다면(Anchor
    # 없음) `_serve_pack_context_question`이 방어적으로 Context를 조기 종료한다.
    if current_context not in VERTICAL_SLICE_CONTEXT_IDS:
        return _serve_pack_context_question(state, current_context)

    question_family_id: str
    question_blueprint_id: str

    if state.questions_asked_in_current_context == 0:
        # Context의 첫 질문 — 실제 확정된 Seed Question(§7-1)을 그대로 반환한다.
        # 2.5.1단계 §4/§5: 이 Context에서 학생이 고른 Anchor가 있으면(Routing을 이미
        # 답했으면) Seed 문구를 그 Anchor Variant로 낸다 — "최소 첫 번째 후속 질문은
        # Anchor를 반영해야 한다"는 요구를 이 지점에서 충족한다.
        question = mock_data.next_mock_question(
            current_context, 0, anchor_id=state.context_anchor_choices.get(current_context),
        )
        # 2026-08-23 Trait Ontology v2(1.5단계) §3: Seed의 Blueprint id는
        # `seed_question_to_blueprint()`와 동일한 명명 규칙("{question_id}_blueprint")을
        # 그대로 따른다 — trait_signal_registry.py가 Seed를 등록할 때 이 함수로 직접
        # 만든 blueprint_id와 정확히 같은 문자열이어야 EXACT_BLUEPRINT로 조회된다.
        question_family_id, question_blueprint_id = "seed", f"{question.question_id}_blueprint"
    elif _llm_client is not None and state.pending_target_traits and state.pending_option_blueprint_id:
        question_id = generate_question_id(
            current_context, "tail", state.questions_asked_in_current_context
        )
        frame_id = state.pending_question_frame or "problem_check"
        # 2.5.2단계 §2: 일반 Adaptive Tail 질문에도 v2 Direct Probe와 같은 방식으로
        # 이 Context의 Anchor를 넘긴다.
        tail_anchor_id = state.context_anchor_choices.get(current_context)
        tail_anchor = (
            CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY.get((current_context, tail_anchor_id))
            if tail_anchor_id else None
        )
        # 2.5.4단계 §2/§6: Anchor가 있으면(v2 Anchor Runtime) 그 Anchor 전용 Backup
        # 1개만 후보로 쓴다 — 사용자가 REVISE 판정한 기존 6개(Context 전체 공통)는
        # v2 Anchor 흐름의 후보에서 완전히 제외한다. Anchor가 없으면(Legacy Flow,
        # v2 기능 Flag가 꺼져 있거나 아직 Routing을 안 거친 세션) 기존 정책을 그대로
        # 유지한다 — 이번 단계에서 Legacy 정책 자체는 바꾸지 않는다(§6 "임의 변경하지
        # 말고 현재 동작과 위험만 보고").
        if tail_anchor is not None:
            anchor_backup = ANCHOR_BACKUP_QUESTIONS_BY_KEY.get((current_context, tail_anchor.anchor_id))
            backup_candidates = [anchor_backup] if anchor_backup is not None else []
        else:
            backup_candidates = VERTICAL_SLICE_BACKUP_QUESTIONS.get(current_context, [])
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
            backup_questions=backup_candidates,
            used_backup_question_ids=set(state.used_backup_question_ids),
            anchor=tail_anchor,
        )
        _tracer.record_stage(
            trace_id=state.trace_id,
            stage_name="Question Generator",
            attributes={
                "graph_node": "question_generator",
                "context_id": current_context,
                "context_anchor_id": tail_anchor_id,
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
                    "backup_candidates_checked": outcome.backup_candidates_checked,
                    "backup_candidates_rejected": outcome.backup_candidates_rejected,
                },
            )
        if outcome.question is None:
            # §11 Fallback 소진 — Context 조기 종료. 남은 재생성·Backup 경로를 다 썼다는
            # 뜻이라 조용히 넘기지 않고 상태를 남긴다.
            has_next_context = _advance_to_next_context_or_complete(state)
            _clear_current_question(state)
            assessment_complete = not has_next_context
            # 2026-08-23 2단계 §3: 이 Context 조기 종료가 마지막 Legacy Context였다면,
            # 일반 STOP 경로와 동일하게 v2 Direct Probe 진입 여부를 확인한다.
            if not has_next_context and _enter_v2_direct_probe_phase_if_applicable(state):
                assessment_complete = False
            _store.save(state)
            return NextQuestionResponse(
                session_id=session_id,
                status=QuestionDeliveryStatus.CONTEXT_EARLY_TERMINATED,
                question=None,
                current_context_id=state.current_context_id,
                questions_asked_in_current_context=state.questions_asked_in_current_context,
                assessment_complete=assessment_complete,
            )
        question = outcome.question
        state.generated_question_texts_in_current_context.append(question.question_text)
        if outcome.source == "backup":
            state.used_backup_question_ids.append(question.question_id)
            status = QuestionDeliveryStatus.BACKUP_USED
            # 2026-08-23 Trait Ontology v2(1.5단계) §2/§4: Backup Question은 Tail
            # Blueprint가 아니라 그 자체가 하나의 고정 Blueprint다 — question_id를
            # blueprint_id로 쓴다(trait_signal_registry.py의 Backup 등록과 동일한 규칙).
            question_family_id, question_blueprint_id = "backup", question.question_id
        elif outcome.source == "cache":
            status = QuestionDeliveryStatus.CACHE_USED
            question_family_id, question_blueprint_id = "tail_blueprint", state.pending_option_blueprint_id
        else:
            status = QuestionDeliveryStatus.GENERATED
            question_family_id, question_blueprint_id = "tail_blueprint", state.pending_option_blueprint_id
    else:
        # LLM 미연동(.env ENABLE_LLM_QUESTION_GENERATION 미설정) 상태의 기존 Mock 경로.
        # 2026-08-23 Trait Ontology v2(1.5단계) §1 감사 결과: 이 경로가 만드는 role_id는
        # 실제 Blueprint가 아니라 그때그때 만든 자리표시자(`role_{trait}`)라 v2 Registry에
        # 절대 등록될 수 없다 — family를 "mock_placeholder"로 명확히 구분해서, Registry
        # 조회가 항상 실패하고 LEGACY_PRIMARY_ADAPTER로 넘어가는 것이 설계대로임을
        # 감사 기록에 남긴다(§4 "정상 질문인데 signals=[]로 조용히 끝나는 경로를 없앨
        # 것"은 LEGACY_PRIMARY_ADAPTER가 항상 PRIMARY Signal 1개를 보장하는 것으로
        # 충족한다 — 이 Mock 경로의 role_id·offered trait 구성 자체는 바꾸지 않는다,
        # 바꾸면 기존 LLM-off 세션의 Legacy Profile/Major/Subject 결과가 달라진다).
        question_id = generate_question_id(
            current_context, "tail", state.questions_asked_in_current_context
        )
        question = mock_data.tail_question_from_planner_decision(
            question_id,
            current_context,
            state.pending_target_traits,
            state.pending_question_frame or "problem_check",
        )
        question_family_id, question_blueprint_id = "mock_placeholder", question.question_id

    state.current_question = question
    state.current_question_family_id = question_family_id
    state.current_question_blueprint_id = question_blueprint_id
    state.current_question_delivery_status = status.value
    state.current_question_served_context_id = current_context
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

    # 2026-08-23 2단계 §9: Direct Probe 질문 답변은 Legacy 파이프라인을 완전히 우회한다.
    if state.current_question_family_id == "v2_direct_probe":
        return _submit_v2_direct_probe_answer(state, payload.selected_option_id)

    # 2.5단계 §5: Context Routing 답변도 마찬가지로 Legacy/v2 파이프라인을 완전히 우회한다.
    if state.current_question_family_id == "context_routing":
        return _submit_context_routing_answer(state, payload.selected_option_id)

    # 2026-08-23 Trait Ontology v2(2.8단계) §5: 신규 ContextPack Context의 Direct
    # Probe/Backup 답변도 Legacy 12-Trait 전용 Stop/Continue·Target Planner를 완전히
    # 우회한다(그 둘 다 VERTICAL_SLICE_TRAIT_IDS 기준이라 Pack의 24-Trait 범위와 안 맞다).
    if state.current_question_family_id in ("pack_direct_probe", "pack_backup"):
        return _submit_pack_context_probe_answer(state, payload.selected_option_id)

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
        if has_next_context:
            next_action = "CONTEXT_COMPLETE"
        elif _enter_v2_direct_probe_phase_if_applicable(state):
            # 2026-08-23 2단계 §3/§4: Legacy가 방금 끝났고 Feature Flag가 켜져 있으며
            # 실제로 서빙 가능한 v2 후보가 있을 때만 여기로 온다 — B는 그냥 다음
            # next-question을 호출하면 된다(§19 "B가 v2 Phase를 알아야만 동작하는
            # 구조를 만들지 않는다").
            next_action = "NEXT_QUESTION"
        else:
            next_action = "ASSESSMENT_COMPLETE"
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

    # 2.2단계 §12/§13: Evidence·Stop/Continue·Target Planner 상태가 전부 갱신된 뒤에만
    # current_question을 정리한다(원자성 순서 — Evidence 저장 성공 → State 갱신 성공 →
    # current_question 정리 → Store 저장). 이 답변이 처리 도중 예외로 실패했다면(위에서
    # `result.accepted=False`로 이미 거부됐거나, process_answer_submission 자체가 예외를
    # 던졌다면) 이 지점에 도달하지 못하므로 current_question은 그대로 남아 학생이
    # 올바른 선택지로 다시 답할 수 있다.
    _clear_current_question(state)
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
    # 2026-08-23 Trait Ontology v2(2.6단계) §5/§9 — PRIMARY Flag가 켜졌으면 v2
    # TraitVectorSnapshot(Fail-Closed 게이트를 통과한 Evidence만)을 실제 입력으로 쓴다.
    # Legacy 결과와 절대 섞지 않는다 — v2 Evidence가 부족해도 Legacy로 조용히 대체하지
    # 않고, generate_career_profile_v2 자체가 항상 이 세션의 실제 v2 값만으로 정직한
    # highlight(부족하면 "충분히 확인되지 않았다")를 만든다(§9).
    if trait_vector_v2_primary_enabled():
        snapshot_entries, primary_evidence = _compute_v2_primary_snapshot(state)
        profile = generate_career_profile_v2(
            session_id=state.session_id,
            user_id=state.user_id,
            snapshot_entries=snapshot_entries,
            all_trait_definitions=TRAIT_DEFINITIONS_V2_BY_ID,
            evidence_ledger=primary_evidence,
            llm_client=_llm_client,
            resolutions=state.contrast_resolutions,
        )
        gate = gate_primary_eligible_evidence(state.evidence_ledger, state.context_anchor_choices, _context_pack_registry)
        _tracer.record_stage(
            trace_id=state.trace_id,
            stage_name="Profile Summary Generator",
            attributes={
                "graph_node": "profile_summary_generator",
                "used_llm": _llm_client is not None,
                "highlight_count": len(profile.highlights),
                "trait_engine_version": "trait_vector_v2",
                "primary_signal_count": len(gate.approved_evidence_ids),
                "excluded_unreviewed_signal_count": len(gate.excluded_evidence_ids),
                "usable_trait_count": sum(1 for e in snapshot_entries.values() if e.tendency_score is not None),
                "profile_generation_path": "v2_primary",
            },
        )
        _trait_vector_primary_repository.save(state.session_id, TraitVectorSnapshot(entries=snapshot_entries))
        _compute_and_store_trait_vector_shadow_snapshot(state)
        return profile

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
            "trait_engine_version": "legacy",
            "profile_generation_path": "legacy",
        },
    )
    _compute_and_store_trait_vector_shadow_snapshot(state)
    return profile


def _compute_and_store_trait_vector_shadow_snapshot(state: AssessmentState) -> None:
    """2026-08-23 Trait Ontology v2(1.5단계) §9 — `/profile` 응답이 이미 확정된 뒤에만
    호출한다(Fail-Open: 이 함수가 무엇을 하든 위에서 이미 만든 `profile` 반환값에는
    영향을 줄 수 없다). 계산이 실패해도(방어적으로 broad Exception을 잡는다 — 이 함수는
    Shadow 진단 전용이라 어떤 예외도 사용자에게 전파하면 안 된다) 그냥 이번 호출만
    건너뛴다 — 세션 진행에는 영향이 없다."""

    try:
        entries = _compute_v2_snapshot(state)
        snapshot = TraitVectorSnapshot(entries=entries)
        _trait_vector_shadow_repository.save(state.session_id, snapshot)

        # 2026-08-23 2단계 §1: "구조상 관찰 가능한가"(질문 Bank 자체의 정적 구조,
        # OBSERVABLE_TRAIT_IDS/NOT_PROBED_TRAIT_IDS — 학생과 무관하게 항상 같은 값)와
        # "이 학생 세션에서 실제로 관찰됐는가"(evidence_confidence 기준, 세션마다 다름)는
        # 서로 다른 질문이다. 1.5단계는 이 둘을 같은 값(len(observed))으로 잘못 채웠다 —
        # 네 필드로 명확히 분리한다.
        observed_in_session = [e for e in entries.values() if e.evidence_confidence != "no_evidence"]
        # mapping_source 집계는 PRIMARY_BLUEPRINT(Legacy)와 V2_DIRECT_PROBE(신규 Trait)
        # 둘 다 "일반 질문"이다 — Conflict Resolution만 제외한다.
        primary_records = [
            r for r in state.evidence_ledger
            if r.evidence_origin in (EvidenceOrigin.PRIMARY_BLUEPRINT, EvidenceOrigin.V2_DIRECT_PROBE)
        ]
        _tracer.record_stage(
            trace_id=state.trace_id,
            stage_name="Trait Vector Shadow Snapshot",
            attributes={
                "graph_node": "trait_vector_shadow_snapshot",
                "core_trait_count": len(CORE_TRAIT_IDS),
                "structurally_observable_trait_count": len(OBSERVABLE_TRAIT_IDS),
                "structurally_not_probed_trait_count": len(NOT_PROBED_TRAIT_IDS),
                "directly_measurable_count": len(DIRECTLY_MEASURABLE_TRAIT_IDS),
                "related_only_count": len(RELATED_ONLY_TRAIT_IDS),
                "observed_in_session_count": len(observed_in_session),
                "not_observed_in_session_count": len(CORE_TRAIT_IDS) - len(observed_in_session),
                "hypothesis_count": sum(1 for e in entries.values() if e.status == "HYPOTHESIS"),
                "promoted_related_count": sum(
                    1 for e in entries.values() if e.evidence_confidence == "promoted_related_signal"
                ),
                "conflict_count": sum(1 for e in entries.values() if e.status == "CONFLICTING"),
                "mapping_source_exact_count": sum(
                    1 for r in primary_records if r.trait_signal_mapping_source_v2 == "EXACT_BLUEPRINT"
                ),
                "mapping_source_legacy_adapter_count": sum(
                    1 for r in primary_records if r.trait_signal_mapping_source_v2 == "LEGACY_PRIMARY_ADAPTER"
                ),
                "mapping_missing_count": sum(
                    1 for r in primary_records if r.trait_signal_mapping_source_v2 is None
                ),
            },
        )
    except Exception as exc:
        # Fail-Open — Shadow 계산·기록 실패가 Career Profile 응답에 영향을 주면 안 된다.
        # 이미 위에서 `profile`을 계산·반환하기로 확정한 뒤에만 이 함수를 호출하므로,
        # 여기서 무엇이 실패해도 되돌릴 결과가 없다(부수 효과만 실패할 뿐이다). 다만
        # 2단계 §2: 완전히 조용히 삼키지 않는다 — 예외 "종류"만 로그로 남긴다(학생 데이터·
        # session_id·Trait Vector 값은 절대 로그 인자에 넣지 않는다).
        _logger.warning("trait vector shadow calculation failed: %s", type(exc).__name__)


@app.get("/majors/{session_id}", response_model=MajorsResponse)
def get_majors(session_id: str) -> MajorsResponse:
    """§16은 LLM을 전혀 쓰지 않는 순수 계산이라 예전부터 LLM 연동 여부와 무관하게 항상
    실제 경로를 썼다. 2026-08-21 리뷰 반영: `state.trait_summaries`가 비어 있을 때도
    Mock 전공 목록으로 대체하지 않는다 — compute_major_match()가 Evidence 부족을 이미
    "insufficient" 상태로 정확히 처리하므로, 빈 trait_summaries를 넣어도 자연스럽게
    빈 목록 + insufficient_evidence_message가 나온다. 그래서 별도 분기가 필요 없다."""

    state = _get_state_or_404(session_id)

    # 2026-08-23 Trait Ontology v2(2.6단계) §7/§9 — PRIMARY Flag가 켜졌으면 v2
    # TraitVectorSnapshot(Fail-Closed 게이트 통과분)과 v2 Major Profile(24-Trait,
    # 별도 정본)로 다시 계산한다. Legacy 결과와 절대 섞지 않는다(§9 "Profile만 v2,
    # Matching은 Legacy처럼 섞지 않는다") — Legacy compute_major_match()는 여기서
    # 아예 호출하지 않는다.
    if trait_vector_v2_primary_enabled():
        snapshot_entries, _primary_evidence = _compute_v2_primary_snapshot(state)
        results_v2 = [compute_major_match_v2(snapshot_entries, major) for major in VERTICAL_SLICE_MAJOR_PROFILES_V2]
        labels_by_major_id_v2 = {m.major_id: m.label for m in VERTICAL_SLICE_MAJOR_PROFILES_V2}
        relevant_v2, explore_together_v2, insufficient_message_v2 = rank_major_relevance_v2(
            results_v2, labels_by_major_id_v2, CANONICAL_MAJOR_DESCRIPTIONS_BY_ID
        )
        gate = gate_primary_eligible_evidence(state.evidence_ledger, state.context_anchor_choices, _context_pack_registry)
        _tracer.record_stage(
            trace_id=state.trace_id,
            stage_name="Major Matching",
            attributes={
                "graph_node": "major_matching",
                "trait_engine_version": "trait_vector_v2",
                "matching_engine_version": "matching_engine_v2",
                "primary_signal_count": len(gate.approved_evidence_ids),
                "excluded_unreviewed_signal_count": len(gate.excluded_evidence_ids),
                "usable_trait_count": sum(1 for e in snapshot_entries.values() if e.tendency_score is not None),
                "computed_major_count": sum(1 for r in results_v2 if r.status == "computed"),
            },
        )
        return MajorsResponse(
            session_id=session_id,
            relevant_majors=relevant_v2,
            explore_together_majors=explore_together_v2,
            insufficient_evidence_message=insufficient_message_v2,
        )

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
    relevant, explore_together, insufficient_message = rank_major_relevance(
        results, labels_by_major_id, CANONICAL_MAJOR_DESCRIPTIONS_BY_ID
    )
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

    # 2026-08-23 Trait Ontology v2(2.6/2.7단계) §8/§9 — PRIMARY Flag가 켜지면
    # PRE_SURVEY·POST_OFFERING 둘 다 v2 경로를 쓴다(2.7단계 §4로 POST_OFFERING도
    # 이식했다 — 더 이상 Legacy로 떨어지지 않는다). 분기 조건(CONFIRMED 상태인가)은
    # Legacy `CoursePlanningService.get_course_profile()`과 완전히 동일하게 다시
    # 계산한다.
    if trait_vector_v2_primary_enabled():
        planning_state = _course_planning_store.load(session_id)
        is_post_offering = (
            planning_state is not None
            and planning_state.selected_major_id == selected_major_id
            and planning_state.upload_status == "CONFIRMED"
        )
        try:
            snapshot_entries, _primary_evidence = _compute_v2_primary_snapshot(state)
            if is_post_offering:
                unresolved_candidates = [
                    c for c in planning_state.parsed_candidates if c.matched_subject_id is None
                ]
                course_profile = _course_planning_service_v2.build_post_offering_course_profile_v2(
                    state, selected_major_id, snapshot_entries, TRAIT_DEFINITIONS_V2_BY_ID,
                    set(planning_state.confirmed_offered_subject_ids), unresolved_candidates,
                )
            else:
                course_profile = _course_planning_service_v2.build_pre_survey_course_profile_v2(
                    state, selected_major_id, snapshot_entries, TRAIT_DEFINITIONS_V2_BY_ID,
                )
        except CourseEvidenceNotReadyErrorV2 as exc:
            raise HTTPException(
                status_code=422,
                detail=APIError(error_code=APIErrorCode.EVIDENCE_NOT_READY, message=str(exc)).model_dump(),
            ) from exc
        except MajorNotSelectableErrorV2 as exc:
            raise HTTPException(
                status_code=422,
                detail=APIError(error_code=APIErrorCode.MAJOR_NOT_SELECTABLE, message=str(exc)).model_dump(),
            ) from exc
        gate = gate_primary_eligible_evidence(state.evidence_ledger, state.context_anchor_choices, _context_pack_registry)
        _tracer.record_stage(
            trace_id=state.trace_id,
            stage_name="Subject Matching",
            attributes={
                "graph_node": "subject_matching",
                "trait_engine_version": "trait_vector_v2",
                "matching_engine_version": "subject_matching_engine_v2",
                "primary_signal_count": len(gate.approved_evidence_ids),
                "excluded_unreviewed_signal_count": len(gate.excluded_evidence_ids),
                "usable_trait_count": sum(1 for e in snapshot_entries.values() if e.tendency_score is not None),
                "recommendation_count": len(course_profile.recommendations),
            },
        )
        return course_profile

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

    # 2026-08-23 Trait Ontology v2(2.7단계) §4 — PRIMARY Flag가 켜지면 POST_OFFERING도
    # v2 TraitVectorSnapshot(Fail-Closed 게이트 통과분)으로 계산한다. v2_snapshot_entries
    # 를 넘기지 않으면(PRIMARY=false) confirm()이 이전과 100% 동일하게 동작한다.
    v2_snapshot_entries = None
    if trait_vector_v2_primary_enabled():
        v2_snapshot_entries, _primary_evidence = _compute_v2_primary_snapshot(state)

    try:
        course_profile = _course_document_parsing_service.confirm(
            state, payload.confirmed_subject_ids,
            v2_snapshot_entries=v2_snapshot_entries,
            v2_trait_definitions=TRAIT_DEFINITIONS_V2_BY_ID if v2_snapshot_entries is not None else None,
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
    except (CourseEvidenceNotReadyError, CourseEvidenceNotReadyErrorV2) as exc:
        raise HTTPException(
            status_code=422,
            detail=APIError(error_code=APIErrorCode.EVIDENCE_NOT_READY, message=str(exc)).model_dump(),
        ) from exc
    except (MajorNotSelectableError, MajorNotSelectableErrorV2) as exc:
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
