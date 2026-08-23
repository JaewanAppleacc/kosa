"""V2 Direct Probe 검수 UI 내부 API Schema — 2026-08-23 Trait Ontology v2(2.4단계) §2/§10,
2.5.5단계(단일 검토자 정책 전환).

`src/api/main.py`가 노출하는 공개 API Schema(`src/schemas/api.py`)와 이름이 겹치더라도
완전히 별개다 — 이 파일의 모델은 오직 `src/review_ui/app.py`(127.0.0.1 전용 내부 App)
에서만 쓰인다. 학생 답변이나 개인정보는 어디에도 담지 않는다 — 검수 대상은 고정
Blueprint와 Mapping, 그리고 검토자의 판단(TBD/APPROVE/REVISE/HOLD)뿐이다.

2.5.5단계: 이 프로젝트는 2차 검토를 쓰지 않는다 — `final_status`는 reviewer_1만으로
계산한다([[v2_direct_probe_review.ReviewEntry]] 참고). `ReviewerSlot`은 과거 데이터
호환을 위해 `reviewer_2`를 계속 허용하지만(기존 JSON에 남은 값을 깨뜨리지 않는다),
UI는 검토자 1 선택만 제공한다."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ReviewerSlot = Literal["reviewer_1", "reviewer_2"]
ReviewerStatus = Literal["APPROVE", "REVISE", "HOLD", "TBD"]
FinalReviewStatus = Literal["DRAFT", "REVIEW_REQUIRED", "APPROVED"]


class OptionReviewView(BaseModel):
    reviewer_1_status: ReviewerStatus
    reviewer_1_comment: str
    reviewer_2_status: ReviewerStatus
    reviewer_2_comment: str
    final_status: FinalReviewStatus
    resolution_note: str


class QuestionReviewView(BaseModel):
    reviewer_1_status: ReviewerStatus
    reviewer_1_comment: str
    reviewer_2_status: ReviewerStatus
    reviewer_2_comment: str
    final_status: FinalReviewStatus
    resolution_note: str


class MappingSignalView(BaseModel):
    """`TraitSignal` 하나를 그대로 옮긴 것 — RELATED Signal이 실제로 존재할 경우를
    대비해 구조를 그대로 유지한다(현재 14개 Blueprint는 전부 PRIMARY 1개뿐이지만,
    검수 페이지가 그 사실을 스스로 판단하지 않고 있는 그대로 보여준다)."""

    trait_id: str
    signal_role: Literal["PRIMARY", "RELATED"]
    weight: float


class OptionItem(BaseModel):
    role_id: str
    # 학생 화면 모드 — 실제 학생에게 보이는 정보만.
    text: str
    length: int
    display_order: int

    # Mapping 검수 모드 전용 — 학생 화면 모드에서는 프론트엔드가 이 필드들을 숨긴다
    # (서버 응답 자체에는 포함된다 — 로컬 전용 App이라 별도 응답을 만들 필요가 없고,
    # 프론트엔드의 토글이 화면 표시 여부만 담당한다).
    mapping_type: Literal["TRAIT_SIGNAL", "NO_SIGNAL"]
    is_target: bool
    signals: list[MappingSignalView]
    no_signal_reason: str | None
    quality_flags: list[str]
    length_outlier: bool
    length_review_before: str | None
    length_review_after: str | None
    length_review_reason: str | None

    review: OptionReviewView


class QuestionItem(BaseModel):
    blueprint_id: str
    context_id: str
    context_label: str
    frame_id: str
    question_text: str

    trait_id: str
    trait_label: str
    trait_definition: str
    neighboring_trait_ids: list[str]
    distinction_notes: str

    question_quality_flags: list[str]
    has_no_signal_option: bool
    has_length_review_history: bool

    options: list[OptionItem]
    review: QuestionReviewView


class QuestionListResponse(BaseModel):
    questions: list[QuestionItem]
    question_review_revision: str
    option_review_revision: str


class SummaryResponse(BaseModel):
    question_total: int
    question_reviewed_final: int  # final_status != DRAFT (즉, 최소 한쪽이라도 의견이 있음)
    question_status_counts: dict[str, int]
    option_total: int
    option_reviewed_final: int
    option_status_counts: dict[str, int]
    approved_eligible_blueprint_ids: list[str]
    question_review_revision: str
    option_review_revision: str


class RoutingOptionItem(BaseModel):
    """2.5단계 §10 — Context Routing 선택지 검수 항목. Trait Mapping 필드가 아예 없다
    (Trait Signal이 구조적으로 0이라 보여줄 Mapping 자체가 없다) — 대신 어느
    하위 Context(Anchor)로 연결되는지만 보여준다."""

    role_id: str
    text: str
    display_order: int
    context_anchor: str
    anchor_label: str
    review: OptionReviewView


class RoutingQuestionItem(BaseModel):
    """2.5단계 §10 — Context Routing 질문 검수 항목. `trait_id`/`trait_label` 같은 필드가
    없다 — Routing 질문은 애초에 어떤 Trait도 측정하지 않는다. 대신 구조적으로 이미
    보장된 사실(trait_signal_free, distinct_anchor_count)을 참고 정보로 보여주고, 나머지
    (학생 배제 여부, 선택지 의미 중복 여부)는 사람이 직접 판단하도록 체크리스트로만
    남긴다."""

    blueprint_id: str
    context_id: str
    context_label: str
    question_text: str

    trait_signal_free: bool
    distinct_anchor_count: int
    total_anchor_count: int

    options: list[RoutingOptionItem]
    review: QuestionReviewView


class RoutingQuestionListResponse(BaseModel):
    questions: list[RoutingQuestionItem]
    question_review_revision: str
    option_review_revision: str


class AnchorPreviewOptionView(BaseModel):
    role_id: str
    text: str
    primary_trait_delta: dict[str, int]


class AnchorPreviewResponse(BaseModel):
    """2026-08-23 Trait Ontology v2(2.5.1단계) §11 — Routing 질문에서 Anchor 하나를
    고르면 실제로 나오는 첫 후속 질문(Seed Anchor Variant)을 그대로 보여준다.
    `preview_question_text`/`preview_options`는 UI 전용 가짜 데이터가 아니라
    `src.api.mock_data.seed_question_as_finalized()`(실제 Runtime이 Seed를 낼 때 쓰는
    바로 그 함수)를 그대로 호출한 결과다."""

    context_id: str
    anchor_id: str
    anchor_label: str
    preferred_scenarios: list[str]
    forbidden_assumptions: list[str]
    preview_question_text: str
    preview_options: list[AnchorPreviewOptionView]


class SeedAnchorOptionItem(BaseModel):
    """2.5.2단계 §12 — Seed Anchor Variant 선택지 검수 항목."""

    role_id: str
    text: str
    neutral_text: str
    primary_trait_delta: dict[str, int]
    trait_id: str
    trait_label: str
    trait_definition: str
    mapping_rationale_draft: str
    review: OptionReviewView


class SeedAnchorQuestionItem(BaseModel):
    """2.5.2단계 §12 — Seed Anchor Variant 질문 검수 항목."""

    context_id: str
    context_label: str
    anchor_id: str
    anchor_label: str
    question_text: str
    neutral_question_text: str
    options: list[SeedAnchorOptionItem]
    review: QuestionReviewView


class SeedAnchorQuestionListResponse(BaseModel):
    questions: list[SeedAnchorQuestionItem]
    question_review_revision: str
    option_review_revision: str


class BackupOptionItem(BaseModel):
    """2.5.3단계 §11, 2.5.4단계 §5 — Backup 선택지 검수 항목. `trait_id=None`이면
    NO_SIGNAL이다(2.5.3단계의 기존 6개는 NO_SIGNAL이 없어 항상 값이 있었다)."""

    role_id: str
    text: str
    primary_trait_delta: dict[str, int]
    trait_id: str | None
    trait_label: str
    trait_definition: str
    mapping_rationale_draft: str
    review: OptionReviewView


class BackupQuestionItem(BaseModel):
    """2.5.3단계 §11 — Backup 질문 검수 항목. `anchor_gate_results`는 이 Context의 각
    Anchor(및 "neutral" = Anchor 없음)에 대해 실제 Backup 적합성 검사 함수
    (`check_backup_candidate`)를 그대로 호출한 통과 여부다 — UI 전용 가짜 판정이
    아니다."""

    question_id: str
    context_id: str
    context_label: str
    question_text: str
    options: list[BackupOptionItem]
    allowed_anchor_ids: list[str] | None
    excluded_anchor_ids: list[str]
    applicability_reason_draft: str
    anchor_gate_results: dict[str, bool]
    review: QuestionReviewView
    # 2.5.4단계 §2/§7 — "이전 REVISE Backup과의 관계". 기존(2.5.3단계) Backup은 항상
    # []. Anchor Backup은 자신이 대체하는 그 Context의 기존 REVISE Backup question_id
    # 목록을 담는다(예: game_backup_01/02) — 사람이 검수 페이지에서 "왜 이 Anchor
    # Backup이 새로 생겼는지" 맥락을 바로 볼 수 있게 한다.
    superseded_question_ids: list[str] = []


class BackupQuestionListResponse(BaseModel):
    questions: list[BackupQuestionItem]
    question_review_revision: str
    option_review_revision: str


class BackupAnchorPreviewResponse(BaseModel):
    """2.5.3단계 §11/§14 — Backup Anchor Preview. `check_backup_candidate()`를 그대로
    호출한 결과만 담는다."""

    question_id: str
    anchor_id: str | None
    passed: bool
    failures: list[str]


class UpdateQuestionReviewRequest(BaseModel):
    reviewer: ReviewerSlot
    status: ReviewerStatus
    comment: str = ""
    resolution_note: str | None = None
    expected_revision: str = Field(..., description="GET 응답의 question_review_revision을 그대로 보내야 한다")


class UpdateOptionReviewRequest(BaseModel):
    reviewer: ReviewerSlot
    status: ReviewerStatus
    comment: str = ""
    resolution_note: str | None = None
    expected_revision: str = Field(..., description="GET 응답의 option_review_revision을 그대로 보내야 한다")


class UpdateReviewResponse(BaseModel):
    ok: bool
    final_status: FinalReviewStatus
    new_revision: str


class ContextPackReviewOptionView(BaseModel):
    """2026-08-23 Trait Ontology v2(2.8단계) §9 — Seed/Backup은 `FinalizedOption.
    primary_trait_delta`(비어있으면 NO_SIGNAL) 기반, Direct Probe는
    `V2ProbeOptionMapping`(PRIMARY/RELATED/NO_SIGNAL 명시) 기반이다 — 어느 쪽이든
    같은 View로 평평하게 담는다."""

    role_id: str
    text: str
    mapping_type: Literal["TRAIT_SIGNAL", "NO_SIGNAL"]
    trait_id: str | None
    trait_label: str | None
    mapping_rationale_draft: str | None


class ContextPackReviewQuestionView(BaseModel):
    key: str  # ContextPackRegistry.required_review_keys()와 동일한 검수 상태 Key.
    kind: Literal["routing", "seed", "anchor_backup", "direct_probe"]
    anchor_id: str | None
    question_text: str
    trait_signal_free: bool  # Routing 질문이면 True(Trait 미반영 구조 확인용).
    options: list[ContextPackReviewOptionView]
    review: QuestionReviewView


class ContextPackAnchorView(BaseModel):
    anchor_id: str
    label: str
    situation_terms: list[str]
    preferred_scenarios: list[str]
    forbidden_assumptions: list[str]


class ContextPackCoverageView(BaseModel):
    primary_trait_ids: list[str]
    related_trait_ids: list[str]
    direct_probe_trait_ids: list[str]
    anchor_count: int
    seed_question_count: int
    backup_question_count: int
    uncovered_trait_ids: list[str]


class ContextPackReviewItem(BaseModel):
    context_id: str
    label: str
    description: str
    pack_version: str
    forbidden_assumptions: list[str]
    review_artifact_paths: list[str]
    anchors: list[ContextPackAnchorView]
    questions: list[ContextPackReviewQuestionView]
    coverage: ContextPackCoverageView
    is_active: bool  # 지금 ENABLE_CONTEXT_PACK_RUNTIME=true라면 실제 서빙 대상인가.
    registry_errors: list[str] = Field(default_factory=list)


class ContextPackListResponse(BaseModel):
    packs: list[ContextPackReviewItem]
    discovery_errors: dict[str, str]
    ontology_errors: dict[str, str]


class UpdateContextPackReviewRequest(BaseModel):
    status: ReviewerStatus
    comment: str = ""
    resolution_note: str | None = None
