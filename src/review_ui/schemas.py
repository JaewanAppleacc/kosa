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
    # 2026-08-24 신규 ContextPack 검수 탭 — 기존 Seed Anchor/Backup 탭(SeedAnchorOptionItem
    # 등)과 동일하게 Trait Ontology 정의 문장을 각 Option 응답에 직접 담는다(프론트가
    # 별도 Trait 조회 API 없이 Mapping 근거를 바로 검토할 수 있게).
    trait_definition: str | None = None
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
    # 2026-08-24 신규 ContextPack 검수 탭 §4 — 표시용 그룹을 프론트에서 따로 만들지
    # 않기 위해 실제 정본(src/data/contexts/context_activation_batches.py의
    # CONTEXT_ACTIVATION_BATCHES)에서 그대로 계산해 내려준다. 그 배치 목록에 없는
    # Pack(예: 향후 4차 배치 이전 실험용 Pack)이면 None이다.
    activation_batch: int | None = None


class ContextPackListResponse(BaseModel):
    packs: list[ContextPackReviewItem]
    discovery_errors: dict[str, str]
    ontology_errors: dict[str, str]


class UpdateContextPackReviewRequest(BaseModel):
    status: ReviewerStatus
    comment: str = ""
    resolution_note: str | None = None


class SharedProbeOptionView(BaseModel):
    """2026-08-23 Trait Ontology v2(2.9단계) §5/§11 — ContextPack 공용 Adaptive Probe
    Blueprint(`context_pack_shared_probe_blueprints.py`)의 선택지 하나. `weight`는
    PRIMARY(1.0)만 노출한다 — 이 Blueprint는 원본 14개를 그대로 복사한 것이라
    RELATED Signal이 없다(원본 자체가 그렇다)."""

    role_id: str
    text: str
    mapping_type: Literal["TRAIT_SIGNAL", "NO_SIGNAL"]
    trait_id: str | None
    trait_label: str | None
    weight: float | None


class SharedProbeAnchorPreviewView(BaseModel):
    """2026-08-23 Trait Ontology v2(2.9.1단계) §5 — 이 Context의 실제 Anchor 5개 각각에
    대한 Preview. `forbidden_assumption_failures`는 UI 전용 가짜 판정이 아니라 실제
    `question_quality_gate.run_quality_gate()`를 그 Anchor의 `forbidden_assumptions`로
    돌린 결과다. `is_approved`/`is_excluded`는 지금 저장된 검수 상태를 그대로 보여줄
    뿐 이 화면이 계산해서 만든 값이 아니다."""

    anchor_id: str
    label: str
    situation_terms: list[str]
    preferred_scenarios: list[str]
    forbidden_assumptions: list[str]
    forbidden_assumption_failures: list[str]
    is_approved: bool
    is_excluded: bool


class SharedProbeContextRow(BaseModel):
    context_id: str
    context_label: str
    review: QuestionReviewView
    anchors: list[SharedProbeAnchorPreviewView]
    is_runtime_usable: bool  # 이 Context에서 실제로 이 Blueprint가 최소 1개 Anchor에 쓰일 수 있는가.
    # 2026-08-24 배치별 Shared Probe 검수 화면 — ContextPackReviewItem.activation_batch와
    # 동일한 이유로 정본(CONTEXT_ACTIVATION_BATCHES)에서 그대로 계산해 내려준다. 프론트가
    # Context ID→Batch 표를 별도로 복제하지 않는다.
    activation_batch: int | None = None


class SharedProbeReviewItem(BaseModel):
    blueprint_id: str
    trait_id: str
    trait_label: str
    trait_definition: str
    purpose: str  # Mapping Rationale에 해당 — Blueprint 자체가 이미 갖고 있는 값을 그대로 노출한다.
    question_text: str
    options: list[SharedProbeOptionView]
    contexts: list[SharedProbeContextRow]  # 신규 12개 Context 각각의 검수 상태 + Anchor Preview.


class SharedProbeListResponse(BaseModel):
    probes: list[SharedProbeReviewItem]


class UpdateSharedProbeReviewRequest(BaseModel):
    # 2026-08-24 2.9.1단계 §1-3: status/comment도 None이면 기존 값을 그대로 둔다 —
    # "이 Anchor 판정 저장" 버튼은 Context의 reviewer_1_status를 절대 암묵적으로
    # 바꾸면 안 되므로 둘 다 아예 안 보낼 수 있어야 한다(이전에는 status가 필수라
    # 화면이 TBD를 APPROVE로 승격시켜 보낼 수밖에 없었다 — 그 버그의 근본 수정).
    status: ReviewerStatus | None = None
    comment: str | None = None
    # None이면 기존 목록을 그대로 유지한다 — 전달하면 그 목록으로 완전히 교체한다
    # (부분 추가/삭제가 아니라 매 저장마다 검토자가 다시 확정한 전체 목록).
    approved_anchor_ids: list[str] | None = None
    excluded_anchor_ids: list[str] | None = None


class BridgeReviewRowView(BaseModel):
    """2026-08-24 지시서(a/canonical-major-bridge-review-ui, 이후
    a/bridge-scope-final-review-ui로 Scope 필드 추가) — 44개 Bridge Draft 행 하나 +
    그 행에 대한 Mapping 검수 상태 + Scope 정보 + 그 Scope에 대한 **독립적인** 검수
    상태. `canonical_major_group_bridge.draft.jsonl`(Master Draft, Read-Only)과
    두 종류의 별도 검수 상태 파일을 조인한 View일 뿐, 이 응답 자체가 Master Draft나
    두 검수 파일 중 어느 것도 바꾸지 않는다(GET은 항상 읽기 전용).

    `review`(Mapping 검수)와 `scope_review`(Scope 검수)는 서로 다른 파일에서 온
    완전히 독립된 상태다 — 한쪽이 APPROVE라고 다른 쪽이 자동으로 APPROVE되지
    않는다(둘 다 이 View 안에서 나란히 보일 뿐, 서버가 서로 영향을 주도록 계산한
    적이 없다)."""

    review_key: str
    canonical_major_group_id: str
    canonical_major_group_label: str
    canonical_major_id: str | None
    canonical_major_label: str | None
    mapping_status: Literal["EVIDENCED", "REVIEW_REQUIRED", "UNMAPPED", "EXCLUDED_RECOMMENDATION"]
    evidence: list[str]
    decision_reason: str
    boundary_notes: str
    is_boundary_case: bool  # boundary_notes가 비어있지 않은 행("경계 사례만" 필터 기준).
    national_department_candidate_count: int | None  # 조인 실패 시(있을 수 없지만) None.
    review: QuestionReviewView

    # ── Scope(2026-08-24 a/canonical-major-bridge-scope 지시서가 만든 시스템 초안 +
    # a/bridge-scope-final-review-ui가 추가한 사람 검수 상태) ──
    # None은 UNMAPPED 전용(연결 대상이 없어 범위 판단 자체가 성립하지 않는다).
    scope_type: Literal[
        "FULL_GROUP", "INCLUDED_SMALL_SERIES_ONLY", "DEPARTMENT_REVIEW_REQUIRED", "EXCLUDED_RECOMMENDATION",
    ] | None
    included_small_series_codes: list[str]
    # 코드와 같은 순서로 병렬 대응하는 대학알리미 공식 소계열 명칭
    # (`getCodeBySmallSeries` 158개 코드표에서 조인). 코드표에 없는 코드는 이미
    # Loader가 Fail-Fast로 걸렀으므로 여기서는 항상 채워진다.
    included_small_series_names: list[str]
    excluded_small_series_codes: list[str]
    excluded_small_series_names: list[str]
    scope_decision_reason: str
    # scope_type이 Group 전체를 그대로 쓰지 않고 좁힌 행("사람이 REVISE로 요구한
    # 범위 제한 결과") — 우선 검토 카드 판정 기준. 하드코딩한 6개 목록이 아니라
    # scope_type 값에서 구조적으로 계산한다(같은 이유로 좁혀진 행이 나중에 더
    # 늘어나도 이 판정이 자동으로 따라간다).
    is_priority_scope_review: bool
    scope_review: QuestionReviewView


class BridgeReviewSummary(BaseModel):
    """§4 — 화면 상단 요약 개수. 전부 서버가 실제 44행 데이터에서 집계한 값이고,
    HTML/JS에 하드코딩된 숫자는 없다(`build_bridge_review_list()`가 매 요청마다
    다시 센다)."""

    total: int
    evidenced_count: int
    review_required_count: int
    excluded_recommendation_count: int
    unmapped_count: int
    reviewer_tbd_count: int
    reviewer_approve_count: int
    reviewer_revise_count: int
    reviewer_hold_count: int
    reviewed_count: int  # reviewer_1_status != "TBD"
    unreviewed_count: int  # reviewer_1_status == "TBD"

    # ── Scope 검수 요약(2026-08-24 a/bridge-scope-final-review-ui, 위 Mapping
    # 검토자 상태 집계와 완전히 별개 축 — 다른 파일에서 센 값이다) ──
    priority_scope_review_count: int  # is_priority_scope_review == True인 행 수.
    scope_reviewer_tbd_count: int
    scope_reviewer_approve_count: int
    scope_reviewer_revise_count: int
    scope_reviewer_hold_count: int
    scope_reviewed_count: int
    scope_unreviewed_count: int


class BridgeReviewListResponse(BaseModel):
    rows: list[BridgeReviewRowView]
    summary: BridgeReviewSummary


class UpdateBridgeReviewRequest(BaseModel):
    # "필터 변경만으로 저장 요청을 보내지 않음" — 이 계약은 status/comment를 필수로
    # 받아도 지켜진다(필터는 애초에 이 Endpoint를 호출하지 않는다, JS 쪽에서 보장).
    # 그래도 UpdateSharedProbeReviewRequest와 동일하게 None="변경 없음" 규칙을 따라서,
    # 코멘트만 저장하거나 상태만 저장하는 부분 저장을 허용한다.
    status: ReviewerStatus | None = None
    comment: str | None = None
    resolution_note: str | None = None


class UpdateBridgeScopeReviewRequest(BaseModel):
    """2026-08-24 지시서(a/bridge-scope-final-review-ui) — Mapping 검수
    (`UpdateBridgeReviewRequest`)와 완전히 별도의 요청 Schema다. 이 요청을 처리하는
    Endpoint는 Mapping 검수 파일을 절대 열지 않는다 — 이름이 비슷해도 물리적으로
    다른 파일에 쓰인다."""

    status: ReviewerStatus | None = None
    comment: str | None = None
    resolution_note: str | None = None
