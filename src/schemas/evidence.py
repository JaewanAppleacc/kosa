"""Evidence Ledger / Explicit Conflict Schema — 설계안 §12, §12-1, §13 구현."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from src.schemas.trait_signal import MappingSource, SignalRole


class AppliedTraitSignal(BaseModel):
    """2026-08-23 Trait Ontology v2(1단계) §8 — 답변 하나가 실제로 적용한 v2 Trait
    Signal 하나. `TraitSignal`(정본 Registry 값)과 필드는 같지만, 이건 "이 답변이 실제로
    적용받은 값"을 Evidence Ledger에 그대로 굳혀 기록하는 별도 타입이다 — 나중에
    Registry 내용이 바뀌어도 과거 Evidence 기록은 그때 실제로 적용된 값 그대로 남아야
    감사 가능성(auditability)이 유지된다."""

    trait_id: str
    signal_role: SignalRole
    weight: float
    # 1.5단계 §6: mutable default([])는 클래스 정의 시 한 번만 만들어지는 공유 객체라,
    # 실수로 여러 인스턴스가 같은 list를 공유하게 될 위험이 있다 — default_factory로
    # 인스턴스마다 새 list를 만든다.
    related_concept_ids: list[str] = Field(default_factory=list)


class EvidenceOrigin(str, Enum):
    PRIMARY_BLUEPRINT = "primary_blueprint"
    SECONDARY_HYPOTHESIS = "secondary_hypothesis"
    # 2026-08-22 4차 리뷰: Explicit Conflict 확인 질문(§12-1) 답변은 일반 상황형 질문
    # 답변과 다른 종류의 정보다 — "이 Trait가 실제로 얼마나 자주 나타나는가"가 아니라
    # "상충하는 기존 Evidence를 어떻게 해석할지"를 알려주는 답이다. PRIMARY_BLUEPRINT로
    # 기록하면 support_count/opportunity_count/context_count/distinct_frame_count 같은
    # 일반 Trait 집계에 그대로 섞여 들어가는데(evidence_engine.summarize_trait_evidence는
    # PRIMARY_BLUEPRINT만 집계), 이러면 확인 질문 한 번이 "일반 Evidence +1"과
    # "Matching damping(×0.67, matching_engine.py)"을 동시에 유발해 정책보다 과하게
    # 반영된다. 이 값으로 따로 표시하면 기존의 "PRIMARY_BLUEPRINT만 계산에 쓴다"는
    # 필터를 그대로 재사용하는 것만으로 자동으로 제외된다(evidence_engine.py,
    # conflict_engine.py, profile_engine.py 세 곳 모두 이미 `== PRIMARY_BLUEPRINT`로
    # 걸러쓰고 있었다). Evidence Ledger에서 삭제하지 않고 그대로 남긴다 — 역추적용.
    CONFLICT_RESOLUTION = "conflict_resolution"
    # 2026-08-24 Trait Ontology v2(2단계) §9 — 신규 Trait Direct Probe 질문(Feature Flag
    # ON일 때만 서빙)에 대한 답변. CONFLICT_RESOLUTION과 똑같은 이유로 별도 Origin이
    # 필요하다: Legacy summarize_trait_evidence/Explicit Conflict 탐지/Adaptive
    # Target Planner 상태·opportunity_count는 전부 `== PRIMARY_BLUEPRINT` 필터를 이미
    # 쓰고 있으므로, 이 값으로 분리하면 자동으로 제외된다(코드를 새로 고칠 필요 없음).
    # v2 Trait Vector Snapshot 계산(Shadow 전용)에서는 반대로 PRIMARY_BLUEPRINT와
    # 함께 "v2 Signal의 정당한 출처"로 포함한다(trait_vector_snapshot_engine.py).
    V2_DIRECT_PROBE = "v2_direct_probe"


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
    # 2026-08-23 Trait Ontology v2(1단계) §8: 기존 `applied_primary_trait_delta`는
    # 즉시 제거하지 않고 하위 호환·Legacy 계산을 위해 그대로 유지한다 — 이 필드는
    # 그 옆에 병행으로 추가하는 v2 Signal 기록이다(기본값 빈 리스트라 기존 EvidenceRecord
    # 생성 코드는 하나도 안 고쳐도 된다). Conflict Resolution 확인 질문에서만 빈 리스트로
    # 남는다 — 그 외 정상 질문은 1.5단계부터 항상 최소 1개(EXACT_BLUEPRINT 또는
    # LEGACY_PRIMARY_ADAPTER)를 갖는다.
    applied_trait_signals_v2: list[AppliedTraitSignal] = Field(default_factory=list)
    # 1.5단계 §1/§6 신규: 이 Evidence의 v2 Signal이 어디서 왔는지(사람이 검토한 Registry
    # 값인지, 아직 Registry에 없어 legacy delta를 그대로 옮긴 것인지, Conflict Resolution
    # 이라 아예 없는지) 감사·Coverage 측정용으로 남긴다. None은 이 필드가 생기기 전
    # 과거(1단계) 기록과의 하위 호환용이다 — API 응답에는 노출하지 않는다.
    trait_signal_mapping_source_v2: MappingSource | None = None


class V2ProbeOpportunity(BaseModel):
    """2026-08-24 Trait Ontology v2(2단계) §10 — 신규 Trait Direct Probe 질문이 학생에게
    제시됐다는 사실 자체를 기록한다. `target_signal_selected=False`는 "이 Trait가
    낮다"는 부정 Evidence가 절대 아니다 — "직접 질문했지만 이번 답변에서는 Target
    Signal이 선택되지 않았다"는 사실만 담는다(Counter Evidence로 계산에 쓰지 않는다,
    사용자 화면에도 노출하지 않는다)."""

    question_id: str
    blueprint_id: str
    target_trait_id: str
    context_id: str
    frame_id: str
    selected_option_id: str
    target_signal_selected: bool


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


ContrastPairStatus = Literal[
    "explicit_conflict", "context_dependent", "insufficient_evidence", "resolved"
]


class ContrastPairResult(BaseModel):
    """§12-1 한 ContrastDefinition에 대한 판정 결과.

    - explicit_conflict: 양쪽 모두 comparable_frame_ids 안에서 minimum_evidence_each_side
      이상 확보했고 아직 해소되지 않음 — 두 Trait 모두 Mask 대상이다.
    - context_dependent: 양쪽 다 Evidence는 있지만 비교 가능한 Frame 조건을 못 채움(또는
      확인 질문에서 "상황에 따라 다르다"로 명시적으로 답함) — Mask하지 않는다.
    - insufficient_evidence: 한쪽이라도 Evidence가 아예 없어 판정 자체가 불가능.
    - resolved: 확인 질문에 답해 한쪽으로 정리됨(RESOLVED_POSITIVE/RESOLVED_OPPOSITE) —
      더 이상 Mask하지 않는다.
    """

    contrast_id: str
    status: ContrastPairStatus
    trait_ids: set[str]  # 이 판정에 관련된 Trait id(들) — explicit_conflict일 때만 Mask 대상


class ContrastResolutionStatus(str, Enum):
    """2026-08-22 리뷰 반영: Evidence는 계속 누적되기만 하므로, "양쪽 다
    minimum_evidence_each_side 이상"이라는 조건은 한 번 충족하면 이후 답변이 아무리
    쌓여도 저절로 빠질 수 없다(Evidence를 지우지 않는 한 항상 참). 그래서 탐지(감지)와
    해소(확인 질문에 대한 답)를 분리한다 — 해소는 오직 이 상태 전이로만 이뤄진다."""

    DETECTED = "DETECTED"  # 조건 충족, 아직 확인 질문을 물어보지 않음
    RESOLVED_POSITIVE = "RESOLVED_POSITIVE"  # 확인 질문에서 positive_role_ids 쪽으로 답함
    RESOLVED_OPPOSITE = "RESOLVED_OPPOSITE"  # 확인 질문에서 opposite_role_ids 쪽으로 답함
    RESOLVED_CONTEXT_DEPENDENT = "RESOLVED_CONTEXT_DEPENDENT"  # "상황에 따라 다르다"로 답함
    UNRESOLVED = "UNRESOLVED"  # 확인 질문에 답했지만 판정 불가(무관한 선택지)


class ContrastResolutionRecord(BaseModel):
    """학생이 Explicit Conflict 확인 질문에 답한 결과. 과거 Evidence를 지우거나 고치지
    않는다 — Evidence Ledger는 그대로 두고 이 Record를 별도로 저장해서 "현재 Conflict
    상태 계산"에만 반영한다.

    2026-08-22 2차 리뷰 반영: "Evidence는 관찰된 답변 기록이고, Conflict Resolution은
    상충 Evidence의 해석 정보다. Resolution은 Evidence를 삭제하지 않으며, Profile 설명과
    Matching 우선순위에 제한적으로 반영한다." 이 정책을 실제로 구현하려면 "어느 Trait가
    우선인지"를 구조적으로 들고 있어야 해서 preferred_trait_id/opposite_trait_id/
    context_dependent_trait_ids를 추가했다:

    - RESOLVED_POSITIVE/RESOLVED_OPPOSITE: preferred_trait_id = 학생이 실제로 답변에서
      우선한 쪽, opposite_trait_id = 상대적으로 덜 우선한 쪽(0으로 만들지 않고 완화만 함,
      §16 damping). status만 보고 매번 다시 계산하지 않도록 이미 "어느 쪽이 우선인지"
      해석까지 끝낸 값을 들고 다닌다.
    - RESOLVED_CONTEXT_DEPENDENT: 어느 한쪽도 우선하지 않으므로 preferred/opposite는
      비우고 context_dependent_trait_ids에 둘 다 담는다 — Profile이 "상황에 따라
      다르게 나타나요"처럼 정성적으로 표현할 때 쓴다.
    - UNRESOLVED: 셋 다 비운다 — 이미 unresolved_conflict_trait_ids로 Mask되므로
      Profile/Matching에서 아예 제외된다(확정적 추천 근거로 쓰지 않음)."""

    contrast_id: str
    status: ContrastResolutionStatus
    resolved_at_answer_id: str
    # 하위 호환을 위해 기본값을 둔다(2026-08-22 1차 리뷰 때 만든 기존 테스트 Fixture가
    # 이 필드들 없이 생성자를 호출한다).
    context_id: str = ""
    reason_option_id: str = ""
    preferred_trait_id: str | None = None
    opposite_trait_id: str | None = None
    context_dependent_trait_ids: list[str] = []


class ContrastResolutionQuestionSpec(BaseModel):
    """§12-1 확장 — 어떤 Contrast의 확인 질문에서, 어떤 Role을 고르면 어떤
    ContrastResolutionStatus로 해석되는지, 그리고 그 Contrast의 두 Trait이 뭔지를
    담는다. 실제 질문 문구·선택지는 src/data/conflicts/에 있고, 이 Spec은 그 데이터가
    Vertical Slice 밖(answer_graph.py 등 범용 Node)에서도 타입으로 참조될 수 있게 여기
    schemas/에 둔다(ContrastDefinition과 동일한 배치 원칙)."""

    contrast_id: str
    positive_trait_id: str
    opposite_trait_id: str
    role_resolution_map: dict[str, ContrastResolutionStatus]


class ConflictDetectionResult(BaseModel):
    """detect_explicit_conflicts()의 반환값 — AssessmentState.unresolved_conflict_trait_ids와
    TraitEvidenceSummary.explicit_conflict_count/context_dependency_flag를 채우는 데 쓴다."""

    pair_results: list[ContrastPairResult]
    unresolved_conflict_trait_ids: set[str]
    explicit_conflict_count_by_trait: dict[str, int]
    context_dependency_flag_by_trait: dict[str, bool]
    # DETECTED 상태(방금 조건을 충족했고 아직 확인 질문을 받은 적 없는) Contrast id.
    # Target Planner가 이걸 보고 다음 질문을 Conflict 확인 질문으로 할지 정한다 — 이미
    # 확인 질문을 한 번 물어봤다면(UNRESOLVED 포함) 여기 다시 나타나지 않는다(무한 반복 방지).
    contrast_ids_needing_resolution_question: set[str] = set()


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
