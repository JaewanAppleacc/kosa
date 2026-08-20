"""Evidence Ledger / Explicit Conflict Schema — 설계안 §12, §12-1, §13 구현."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel


class EvidenceOrigin(str, Enum):
    PRIMARY_BLUEPRINT = "primary_blueprint"
    SECONDARY_HYPOTHESIS = "secondary_hypothesis"


class EvidenceRecord(BaseModel):
    """§12 Evidence Ledger의 한 행. FinalizedOption 선택 시 생성된다."""

    evidence_id: str
    answer_id: str
    question_id: str
    question_frame_id: str
    option_role_id: str
    applied_primary_trait_delta: dict[str, int]
    evidence_origin: EvidenceOrigin
    secondary_hypotheses: list[str] = []
    context: str
    source_type: str
    generator_version: str
    quality_gate_status: str
    cross_context_group: str | None = None


class ContrastDefinition(BaseModel):
    """§12-1 — 사전 정의된 반대 관계만 Explicit Conflict로 판정하기 위한 근거 테이블."""

    contrast_id: str
    construct_id: str
    positive_role_ids: list[str]
    opposite_role_ids: list[str]
    comparable_frame_ids: list[str]
    condition_scope: str
    minimum_evidence_each_side: int
    description: str


class TraitState(str, Enum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    LIMITED = "LIMITED"
    CONFLICTING = "CONFLICTING"
    INSUFFICIENT = "INSUFFICIENT"


InsufficientReason = Literal["NOT_PROBED", "NO_POSITIVE_EVIDENCE", "EVIDENCE_LIMITED"]


class TraitEvidenceSummary(BaseModel):
    """§12 하단에 나열된 Trait별 집계 지표. Evidence Engine이 EvidenceRecord들로부터 계산한다."""

    trait_id: str
    support_count: int = 0
    opportunity_count: int = 0
    context_count: int = 0
    distinct_frame_count: int = 0
    cross_context_repeat_count: int = 0
    explicit_conflict_count: int = 0

    @property
    def support_ratio(self) -> float | None:
        """§12: support_ratio는 보조 지표일 뿐, Trait 강도 점수로 사용하지 않는다."""
        if self.opportunity_count == 0:
            return None
        return self.support_count / self.opportunity_count


class TraitStateJudgment(BaseModel):
    """judge_trait_state()의 반환값. state만으로는 INSUFFICIENT 세부 사유가 사라지므로
    (§14 상세 근거 화면, §26 Evaluation 분포 집계에 필요) 이유를 함께 들고 다닌다.
    Matching 계산(§16)에서는 state만 쓰고 insufficient_reason은 무시한다 — 세 사유 모두
    동일하게 Mask 처리하는 게 원래 규칙이다."""

    state: TraitState
    insufficient_reason: InsufficientReason | None = None
