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
    option_text: str
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


ContrastPairStatus = Literal["explicit_conflict", "context_dependent", "insufficient_evidence"]


class ContrastPairResult(BaseModel):
    """§12-1 한 ContrastDefinition에 대한 판정 결과.

    - explicit_conflict: 양쪽 모두 comparable_frame_ids 안에서 minimum_evidence_each_side
      이상 확보 — 두 Trait 모두 Mask 대상이다.
    - context_dependent: 양쪽 다 Evidence는 있지만 비교 가능한 Frame 조건을 못 채움 —
      "상황 차이로 설명 가능"하므로 Mask하지 않는다.
    - insufficient_evidence: 한쪽이라도 Evidence가 아예 없어 판정 자체가 불가능.
    """

    contrast_id: str
    status: ContrastPairStatus
    trait_ids: set[str]  # 이 판정에 관련된 Trait id(들) — explicit_conflict일 때만 Mask 대상


class ConflictDetectionResult(BaseModel):
    """detect_explicit_conflicts()의 반환값 — AssessmentState.unresolved_conflict_trait_ids와
    TraitEvidenceSummary.explicit_conflict_count/context_dependency_flag를 채우는 데 쓴다."""

    pair_results: list[ContrastPairResult]
    unresolved_conflict_trait_ids: set[str]
    explicit_conflict_count_by_trait: dict[str, int]
    context_dependency_flag_by_trait: dict[str, bool]


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
    # 2026-08-21 3단계: §12-1 "상황 차이로 설명 가능한 반대 Evidence → context_dependency_flag
    # = true"의 실제 구현. explicit_conflict_count와 달리 이건 CONFLICTING으로 Mask하지
    # 않는다 — "이 Trait는 Context에 따라 다르게 나타날 수 있다"는 참고 정보일 뿐이다.
    context_dependency_flag: bool = False

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
