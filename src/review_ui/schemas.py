"""V2 Direct Probe 검수 UI 내부 API Schema — 2026-08-23 Trait Ontology v2(2.4단계) §2/§10.

`src/api/main.py`가 노출하는 공개 API Schema(`src/schemas/api.py`)와 이름이 겹치더라도
완전히 별개다 — 이 파일의 모델은 오직 `src/review_ui/app.py`(127.0.0.1 전용 내부 App)
에서만 쓰인다. 학생 답변이나 개인정보는 어디에도 담지 않는다 — 검수 대상은 고정
Blueprint와 Mapping, 그리고 두 검토자의 판단(TBD/APPROVE/REVISE/HOLD)뿐이다."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ReviewerSlot = Literal["reviewer_1", "reviewer_2"]
ReviewerStatus = Literal["APPROVE", "REVISE", "HOLD", "TBD"]
FinalReviewStatus = Literal["DRAFT", "REVIEW_REQUIRED", "TEAM_REVIEWED"]


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
    team_reviewed_eligible_blueprint_ids: list[str]
    question_review_revision: str
    option_review_revision: str


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
