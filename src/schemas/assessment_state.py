"""AssessmentState — LangGraph Checkpointer가 들고 다니는 상태 (설계안 §5-1, §5-2, §22).

CLAUDE.md 아키텍처 불변식: "Assessment 단계에서 전공 추천 결과나 성적을 Planner 입력으로
사용하지 않는다." 이 State에는 그래서 major/전공 관련 필드를 의도적으로 넣지 않는다 —
정책 위반을 코드 리뷰로 잡는 대신 애초에 State에 그 필드 자체가 존재하지 않게 한다.
(tests/test_policy_guard.py에서 이 불변식을 구조적으로 검증한다.)
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from src.ids import generate_trace_id
from src.schemas.evidence import ContrastResolutionRecord, EvidenceRecord, TraitEvidenceSummary, V2ProbeOpportunity
from src.schemas.question import FinalizedQuestion


class AssessmentPhase(str, Enum):
    INTEREST_RATING = "INTEREST_RATING"
    CONTEXT_SELECTION = "CONTEXT_SELECTION"
    CONTRAST_PROPOSAL = "CONTRAST_PROPOSAL"
    COVERAGE_CHECK = "COVERAGE_CHECK"
    QUESTION_LOOP = "QUESTION_LOOP"
    PROFILE_GENERATION = "PROFILE_GENERATION"
    DONE = "DONE"


# 2026-08-23 Trait Ontology v2(2단계) §3 — 기존 `AssessmentPhase`(위 Enum, Legacy §5-1~
# §5-3 전체 흐름을 가리킴)와 이름이 겹치지 않도록 별도 타입으로 둔다. Legacy 질문 흐름은
# 여전히 `AssessmentPhase.QUESTION_LOOP` 하나로 표현되고, 이 값은 그 QUESTION_LOOP
# "내부"에서 Legacy 검사가 끝난 뒤 v2 Direct Probe로 넘어갈지를 가리키는 서버 내부 전용
# 하위 상태다 — 공개 API에는 절대 노출하지 않는다(§3/§19).
V2ProbeSubPhase = Literal["LEGACY_ASSESSMENT", "V2_DIRECT_PROBE", "COMPLETE"]


class AnsweredQuestion(BaseModel):
    question_id: str
    selected_option_id: str
    selected_role_id: str


class RoutingAnsweredQuestion(BaseModel):
    """2026-08-23 Trait Ontology v2(2.5단계) §5 — Context Routing 답변 기록. Legacy
    `answers`(질문 수 집계에 쓰임)와 완전히 분리된 별도 목록에만 남긴다 — Routing
    답변은 "Legacy 질문 수"에 포함되면 안 된다."""

    context_id: str
    question_id: str
    selected_option_id: str
    selected_role_id: str
    context_anchor: str


class AssessmentState(BaseModel):
    session_id: str
    user_id: str
    # §24 LangSmith Observability: session_id와 분리된 익명 식별자. LangSmith에는 이
    # 값만 보내고 session_id 원문은 보내지 않는다.
    trace_id: str = Field(default_factory=generate_trace_id)
    phase: AssessmentPhase = AssessmentPhase.INTEREST_RATING

    # §5-1 Context 선택 흐름
    interest_ratings: dict[str, int] = {}  # context_id -> 1~5
    selected_preferred_contexts: list[str] = []  # 학생이 직접 고른 4개
    contrast_context_id: str | None = None
    coverage_replacement_offered: list[str] = []  # 최대 2개
    final_contexts: list[str] = []  # 확정된 심층 Context (Vertical Slice에서는 3개)
    context_processing_order: list[str] = []  # 선호 4개 → Contrast 마지막

    # §5-2 질문 진행
    current_context_index: int = 0
    current_question: FinalizedQuestion | None = None
    questions_asked_in_current_context: int = 0
    answers: list[AnsweredQuestion] = []

    # §12/§13 Evidence·Trait 상태
    evidence_ledger: list[EvidenceRecord] = []
    trait_summaries: dict[str, TraitEvidenceSummary] = {}
    # §12-1: 매 답변마다 evidence_ledger 전체로 다시 판정한다(conflict_engine.
    # detect_explicit_conflicts). 2026-08-22 리뷰로 수정: Evidence는 계속 누적되기만
    # 하므로 "추가 Evidence로 자동 해소"는 실제로 일어나지 않는다 — 아래
    # contrast_resolutions에 확인 질문 답변이 기록돼야만 빠진다.
    unresolved_conflict_trait_ids: set[str] = set()
    # contrast_id -> 확인 질문 답변 결과. Evidence Ledger는 건드리지 않고 이 Record만으로
    # "지금 이 Contrast가 해소됐는지"를 판단한다(과거 Evidence 보존).
    contrast_resolutions: dict[str, ContrastResolutionRecord] = {}
    # DETECTED 또는 UNRESOLVED 상태라 아직 최종적으로 정리되지 않은 Contrast id 집합
    # (Trait 단위인 unresolved_conflict_trait_ids와 별개로 Contrast 단위 추적용).
    unresolved_contrast_ids: set[str] = set()
    # Target Planner가 "다음 질문은 이 Contrast의 확인 질문이어야 한다"고 정했을 때만 채워진다.
    # /assessment/next-question이 이 값을 보고 LLM/Mock 대신 고정 확인 질문을 낸다.
    pending_resolution_contrast_id: str | None = None
    # 2026-08-22 2차 리뷰: 일반 꼬리질문 수(questions_asked_in_current_context)와 별도로
    # 센다 — Conflict 확인 질문은 §5-3의 4~6개 상한과 무관한 별도 문항이라, 이 카운터가
    # 올라가도 일반 문항 수는 그대로다(그래서 확인 질문을 하나 끼워 넣어도 다음 질문의
    # §7-2 위치·테마 계산이 밀리지 않는다).
    resolution_questions_asked_in_current_context: int = 0
    # summarize_trait_evidence()의 opportunity_count 계산 입력. 질문 하나가 제시한 5개
    # Option(=5개 Trait)을 question_id별로 기록해둔다 — 나중에 "이 Trait가 몇 번 제시됐는지"를
    # 다시 계산하려면 어떤 질문이 어떤 Trait를 다뤘는지가 남아있어야 한다.
    offered_trait_ids_by_question: dict[str, list[str]] = {}
    # 최근 목표 Trait 이력(오래된 것 → 최신). Planner의 자기확증 방지 규칙(§8, 연속 3회 금지)
    # 입력으로 쓴다.
    recent_target_trait_ids: list[str] = []
    used_frame_ids_in_current_context: list[str] = []
    # §10 생성 원칙("앞선 질문을 표현만 바꿔 반복하지 않는다") 검사용 — Context가 바뀌면
    # 초기화한다. §11 Fallback에서 같은 세션 안에 Backup Question을 재사용하지 않기 위한
    # 목록은 Context가 바뀌어도 유지한다(question_id 자체가 Context를 포함해 유일하다).
    generated_question_texts_in_current_context: list[str] = []
    used_backup_question_ids: list[str] = []
    # §7-2 DEEPEN 테마 Blueprint 제한용 — 이 Context의 Seed에서 학생이 실제로 선택한 Trait.
    # Context가 바뀌면 그 Context의 새 Seed 선택으로 다시 채워진다(2026-08-21 리뷰).
    current_context_seed_trait_id: str | None = None

    # §24 LLM 호출 예산
    llm_call_count: int = 0
    regeneration_count_current_question: int = 0

    # §5-3 Stop Condition
    stop_reason: str | None = None

    # 직전 답변 처리에서 Target Planner가 정한 다음 질문 목표. schemas/는 agents/를 import하지
    # 않는 게 계층 원칙이라 PlannerDecision 객체 대신 필드만 그대로 옮겨 담는다.
    pending_target_traits: list[str] = []
    pending_question_frame: str | None = None
    pending_purpose: str | None = None
    # §7-3/§8: 방금 선택된 Option의 next_probe. 목표 Trait 자체는 바꾸지 않고(§8 "우선순위
    # 조건이 아니라") 다음 질문 "문구"를 자연스럽게 잇는 재료로만 쓴다.
    pending_next_probe: str | None = None
    # 2026-08-21 리뷰: LLM 프롬프트에 next_probe 메모 한 줄만 주지 않고, 직전 질문 전문과
    # 학생이 실제로 고른 선택지 문장도 함께 준다(문장 자체에 노출은 안 하고 참고 재료로만).
    pending_previous_question_text: str | None = None
    pending_previous_answer_text: str | None = None
    # §8 원본 출력 스키마의 option_blueprint_id. Question Generator가 target_trait만으로
    # Blueprint를 다시 찾을 때 생기는 모호함(같은 Trait가 여러 Blueprint에 걸칠 수 있음)을
    # 없애기 위해 Planner가 고른 Blueprint를 그대로 넘긴다.
    pending_option_blueprint_id: str | None = None

    # 2026-08-23 Trait Ontology v2(1.5단계) §3 — "지금 학생에게 나가 있는 current_question이
    # v2 Signal Registry를 조회할 때 어떤 (질문 계열, Blueprint)에서 왔는지"를 가리키는
    # 서버 내부 전용 식별자. FinalizedQuestion 자체에 필드를 추가해 API 응답에서
    # exclude=True로 숨기는 방식 대신 이 State 필드를 골랐다 — 이유는 완료 보고에 설명한다
    # (핵심은: FinalizedQuestion은 NextQuestionResponse 등 여러 Response Model에 직접
    # 중첩되므로 매 경로·매 직렬화 지점마다 노출 여부를 새로 검증해야 하는데, AssessmentState는
    # 이미 어떤 Response Model에도 직접 노출되지 않는다는 게 기존 구조로 보장돼 있다 —
    # pending_option_blueprint_id·pending_resolution_contrast_id와 같은 기존 패턴을 그대로
    # 따른다). Seed·LLM·Backup 질문 모두 next_question() Handler가 이 두 필드를 채운다.
    current_question_family_id: str | None = None
    current_question_blueprint_id: str | None = None
    # 2.2단계 §11 — 아직 답하지 않은 `current_question`을 위해 `/assessment/next-question`
    # 응답을 그대로 복원하는 데 필요한 최소 정보. `status`/`current_context_id`는 최초
    # 서빙 당시 계산된 값을 그대로 재사용해야 한다(재요청마다 다시 계산하면 LLM을 다시
    # 부르거나 문구가 바뀔 수 있다) — `questions_asked_in_current_context`는 기존 필드를
    # 그대로 재사용한다(답변 전까지 바뀌지 않으므로 새 필드가 필요 없다). 공개 API에는
    # 새 필드를 추가하지 않는다 — `QuestionDeliveryStatus`의 문자열 값만 그대로 담는다.
    current_question_delivery_status: str | None = None
    current_question_served_context_id: str | None = None

    # 2026-08-23 Trait Ontology v2(2단계) §3/§4 — Feature Flag가 꺼져 있으면 이 필드들은
    # 전부 기본값 그대로 남고, 기존 세션 흐름·Fixture·복원에 어떤 영향도 주지 않는다.
    v2_probe_phase: V2ProbeSubPhase = "LEGACY_ASSESSMENT"
    # 후보 Trait 우선순위 큐 — V2_DIRECT_PROBE 진입 시 한 번 계산해서 채우고,
    # 질문을 하나 낼 때마다 그 Trait를 꺼내 쓴다(§11 우선순위 공식은
    # src/engines/v2_direct_probe_selector.py가 순수 함수로 계산한다).
    # 2.3단계 §1: v2가 추가한 list 필드는 default_factory로 통일한다(Pydantic v2가
    # 이미 인스턴스마다 독립적으로 복사하므로 실제 공유 버그는 없었지만, 관례를 맞춘다).
    pending_v2_probe_trait_ids: list[str] = Field(default_factory=list)
    v2_probe_questions_asked: int = 0
    v2_probed_trait_ids: list[str] = Field(default_factory=list)
    current_v2_probe_target_trait_id: str | None = None
    current_v2_probe_blueprint_id: str | None = None
    # §10 — Target Signal을 선택하지 않았어도 "질문은 제시했다"는 사실 자체를 남긴다
    # (Counter Evidence로 쓰지 않는다, 사용자 화면에 노출하지 않는다).
    v2_probe_opportunities: list[V2ProbeOpportunity] = Field(default_factory=list)

    # 2026-08-23 Trait Ontology v2(2.5단계) §2/§4/§5 — Context 선택·하위 관심 선택은
    # "학생이 이해하기 쉬운 질문 배경을 결정"할 뿐 Trait 점수에 직접 반영하지 않는다.
    # context_id -> context_anchor(예: "strategy_puzzle"). v2 기능 Flag와 무관하게
    # 항상 채워진다(Context 재정의 자체는 실험적 v2 기능이 아니라 기본 경험 개선이다).
    context_anchor_choices: dict[str, str] = Field(default_factory=dict)
    # Legacy `answers`/v2 `v2_probe_opportunities`와 완전히 분리된 감사용 기록.
    routing_answer_history: list[RoutingAnsweredQuestion] = Field(default_factory=list)

    @property
    def current_context_id(self) -> str | None:
        if 0 <= self.current_context_index < len(self.context_processing_order):
            return self.context_processing_order[self.current_context_index]
        return None
