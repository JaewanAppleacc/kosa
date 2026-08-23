"""Trait Vector Snapshot Engine — 2026-08-23 Trait Ontology v2(1단계) §9/§10. LLM·DB
호출 없는 순수 계산(matching_engine.py/evidence_engine.py와 같은 성격).

이 파일이 하지 않는 것:
- 기존 Profile·Matching 결과를 바꾸지 않는다 — Shadow Mode 병행 계산만 한다(§11).
- Related Signal 하나만으로 학생의 대표 Trait를 확정하지 않는다(§9) — RELATED만
  반복된 Trait는 최대 LIMITED 수준의 진술만 허용하고, 한 번의 답변으로 "강한 Trait"가
  되게 하지 않는다.
- 기존 PRIMARY 판정(STRONG/MODERATE/LIMITED)이 있으면 그 판정을 그대로 우선 쓴다 —
  RELATED Signal로 STRONG 조건을 완화하지 않는다.
"""

from __future__ import annotations

from src.engines.matching_engine import StudentTraitState
from src.schemas.evidence import EvidenceOrigin, EvidenceRecord, V2ProbeOpportunity
from src.schemas.trait_vector_snapshot import TraitVectorEntry

# 2026-08-23 2단계 §9: v2 Signal의 정당한 출처는 PRIMARY_BLUEPRINT(Legacy 질문)와
# V2_DIRECT_PROBE(신규 Trait Direct Probe 질문) 둘 다다 — Conflict Resolution만 제외한다.
# Legacy 계산(summarize_trait_evidence 등)은 여전히 PRIMARY_BLUEPRINT만 걸러 쓰므로
# V2_DIRECT_PROBE Evidence는 자동으로 거기서 제외된다(별도 필터가 이미 존재).
_V2_ELIGIBLE_ORIGINS = frozenset({EvidenceOrigin.PRIMARY_BLUEPRINT, EvidenceOrigin.V2_DIRECT_PROBE})


def _records_with_signal(
    evidence_ledger: list[EvidenceRecord], trait_id: str, signal_role: str
) -> list[EvidenceRecord]:
    """v2 Signal의 정당한 출처(PRIMARY_BLUEPRINT/V2_DIRECT_PROBE)만 본다(Conflict
    Resolution 답변은 이미 답변 처리 시점에 applied_trait_signals_v2를 비워두지만,
    여기서도 한 번 더 방어적으로 막는다)."""

    return [
        r for r in evidence_ledger
        if r.evidence_origin in _V2_ELIGIBLE_ORIGINS
        and any(s.trait_id == trait_id and s.signal_role == signal_role for s in r.applied_trait_signals_v2)
    ]


def _direct_probe_status(
    primary_records: list[EvidenceRecord], related_records: list[EvidenceRecord]
) -> tuple[str, float, str] | None:
    """2단계 §15 — legacy_state가 없는(=신규) Trait에 PRIMARY Evidence(대부분 Direct
    Probe에서 나온다)가 있을 때의 판정. PRIMARY가 하나도 없으면 None을 반환해 호출자가
    기존 promoted/related/not_probed 분기로 넘어가게 한다.

    - STRONG: PRIMARY 3개 이상, 서로 다른 질문, Context 2개 이상, Frame 2개 이상
      (Trait당 Direct Probe 최대 1개 정책 아래서는 사실상 도달 불가 — 그래도 규칙
      자체는 올바르게 존재해야 한다, §15 "Direct Probe 한 번만으로 STRONG 금지").
    - MODERATE: PRIMARY 2개(서로 다른 질문·Frame 또는 Context)거나, PRIMARY 1개 +
      다른 질문에서 관찰된 RELATED(그 PRIMARY와 Context 또는 Frame이 다름).
    - LIMITED: 그 외 PRIMARY 존재(다양성 부족)."""

    if not primary_records:
        return None

    distinct_questions = {r.question_id for r in primary_records}
    distinct_contexts = {r.context for r in primary_records}
    distinct_frames = {r.question_frame_id for r in primary_records}

    if len(distinct_questions) >= 3 and len(distinct_contexts) >= 2 and len(distinct_frames) >= 2:
        return "STRONG", 1.00, "primary_evidence"

    if len(distinct_questions) >= 2 and (len(distinct_contexts) >= 2 or len(distinct_frames) >= 2):
        return "MODERATE", 0.67, "primary_evidence"

    corroborating_related = [
        r for r in related_records
        if r.question_id not in distinct_questions
        and (r.context not in distinct_contexts or r.question_frame_id not in distinct_frames)
    ]
    if corroborating_related:
        return "MODERATE", 0.67, "primary_evidence"

    return "LIMITED", 0.33, "primary_evidence"


def _is_related_promoted(
    related_records: list[EvidenceRecord], primary_evidence_count: int
) -> bool:
    """§9 승격 규칙 — 둘 중 하나만 만족해도 CONFIRMED_RELATED 후보다.

    1. 서로 다른 question_id 2개 이상 + (서로 다른 frame_id 2개 이상 또는 서로 다른
       context_id 2개 이상)에서 관찰됨.
    2. RELATED Signal이 존재하고, 같은 Trait의 PRIMARY Evidence가(다른 답변에서) 이미
       하나라도 있음.

    같은 질문을 표현만 바꿔 반복한 경우는 독립 Evidence로 중복 계산하지 않는다 — 이
    함수는 애초에 question_id를 set으로 모으므로, 같은 question_id가 여러 번 나와도
    한 번으로만 센다(질문 자체가 재사용되는 일은 없지만 방어적으로 안전하다)."""

    if not related_records:
        return False
    distinct_questions = {r.question_id for r in related_records}
    distinct_frames = {r.question_frame_id for r in related_records}
    distinct_contexts = {r.context for r in related_records}
    reaches_diversity = len(distinct_questions) >= 2 and (
        len(distinct_frames) >= 2 or len(distinct_contexts) >= 2
    )
    confirmed_elsewhere = primary_evidence_count >= 1
    return reaches_diversity or confirmed_elsewhere


def compute_trait_vector_snapshot(
    trait_id: str,
    evidence_ledger: list[EvidenceRecord],
    legacy_state: StudentTraitState,
    unresolved_conflict_trait_ids: set[str],
    v2_probe_opportunities: list[V2ProbeOpportunity] | None = None,
) -> TraitVectorEntry:
    """트레잇 하나의 v2 Snapshot을 계산한다. `legacy_state`는 기존
    `compute_student_trait_states()`가 이미 계산해 둔 결과를 그대로 받는다 — 이 함수가
    §13 판정을 다시 하지 않는다(중복 계산 금지, matching_engine.py를 신뢰한다).
    `v2_probe_opportunities`는 2단계 §10 — Target Signal을 선택하지 않은 답변도
    "질문은 받았다"는 사실을 `direct_probe_opportunity_count`로 남긴다(기본값 None이면
    두 필드 모두 0 — 기존 호출자는 이 인자를 몰라도 된다)."""

    primary_records = _records_with_signal(evidence_ledger, trait_id, "PRIMARY")
    related_records = _records_with_signal(evidence_ledger, trait_id, "RELATED")
    opportunities = v2_probe_opportunities or []
    direct_probe_opportunity_count = sum(1 for o in opportunities if o.target_trait_id == trait_id)
    direct_probe_primary_evidence_count = sum(
        1 for o in opportunities if o.target_trait_id == trait_id and o.target_signal_selected
    )

    primary_signal_sum = sum(
        s.weight for r in primary_records for s in r.applied_trait_signals_v2
        if s.trait_id == trait_id and s.signal_role == "PRIMARY"
    )
    related_signal_sum = sum(
        s.weight for r in related_records for s in r.applied_trait_signals_v2
        if s.trait_id == trait_id and s.signal_role == "RELATED"
    )

    promoted = _is_related_promoted(related_records, len(primary_records))
    confirmed_related_signal_sum = related_signal_sum if promoted else 0.0

    observed_records = {r.evidence_id: r for r in (primary_records + related_records)}.values()
    context_count = len({r.context for r in observed_records})
    frame_count = len({r.question_frame_id for r in observed_records})
    question_count = len({r.question_id for r in observed_records})
    # 2.1단계 §4: 후보 우선순위 정렬은 PRIMARY와 섞이지 않은 RELATED 전용 다양성만 써야
    # 한다 — 위 context_count/frame_count/question_count(PRIMARY+RELATED 합산, 기존
    # 유지)와 별도로 다시 센다.
    related_context_ids = {r.context for r in related_records}
    related_question_count = len({r.question_id for r in related_records})
    related_frame_count = len({r.question_frame_id for r in related_records})
    v2_direct_primary_evidence_count = len(
        [r for r in primary_records if r.evidence_origin == EvidenceOrigin.V2_DIRECT_PROBE]
    )
    # 2.6단계 §4: 등장 순서를 보존한 중복 없는 evidence_id 목록(dict를 순서 보존 집합
    # 대용으로 쓴다 — set은 순서가 없어 같은 입력에도 매번 다른 순서가 나올 수 있다).
    supporting_evidence_ids = list(dict.fromkeys(r.evidence_id for r in observed_records))

    if trait_id in unresolved_conflict_trait_ids:
        status = "CONFLICTING"
        tendency_score: float | None = None
        evidence_confidence = "explicit_conflict"
    elif legacy_state.normalized_value is not None:
        # §10: "PRIMARY Evidence가 기존 STRONG/MODERATE/LIMITED 조건을 만족하면 기존
        # 판정을 우선 유지" — RELATED가 있어도 이 판정을 절대 완화·강화하지 않는다.
        status = legacy_state.state.value  # type: ignore[assignment]
        tendency_score = legacy_state.normalized_value
        evidence_confidence = "primary_evidence"
    elif (direct := _direct_probe_status(primary_records, related_records)) is not None:
        # 2단계 §15: legacy_state가 없는(신규) Trait에 PRIMARY Evidence(Direct Probe)가
        # 있는 경우의 판정 — LIMITED/MODERATE/STRONG 세 단계 전부 여기서 나온다.
        status, tendency_score, evidence_confidence = direct
    elif promoted:
        # §10: "RELATED가 승격 조건을 만족하지만 PRIMARY 없음: LIMITED, tendency_score
        # 최대 0.33" — 확인된 RELATED만으로는 STRONG/MODERATE로 올라가지 않는다.
        status = "LIMITED"
        tendency_score = 0.33
        evidence_confidence = "promoted_related_signal"
    elif related_records:
        # §9: "확인되지 않은 RELATED는 Hypothesis로만 보존" — Matching에 쓰지 않는다.
        status = "HYPOTHESIS"
        tendency_score = None
        evidence_confidence = "unconfirmed_related_signal"
    else:
        status = "NOT_PROBED"
        tendency_score = None
        evidence_confidence = "no_evidence"

    return TraitVectorEntry(
        trait_id=trait_id,
        primary_signal_sum=primary_signal_sum,
        related_signal_sum=related_signal_sum,
        confirmed_related_signal_sum=confirmed_related_signal_sum,
        primary_evidence_count=len(primary_records),
        related_evidence_count=len(related_records),
        context_count=context_count,
        frame_count=frame_count,
        question_count=question_count,
        tendency_score=tendency_score,
        evidence_confidence=evidence_confidence,
        status=status,
        direct_probe_opportunity_count=direct_probe_opportunity_count,
        direct_probe_primary_evidence_count=direct_probe_primary_evidence_count,
        related_question_count=related_question_count,
        related_context_count=len(related_context_ids),
        related_frame_count=related_frame_count,
        related_context_ids=related_context_ids,
        v2_direct_primary_evidence_count=v2_direct_primary_evidence_count,
        supporting_evidence_ids=supporting_evidence_ids,
    )


def compute_trait_vector_snapshot_all(
    evidence_ledger: list[EvidenceRecord],
    legacy_states: dict[str, StudentTraitState],
    unresolved_conflict_trait_ids: set[str],
    core_trait_ids: set[str],
    v2_probe_opportunities: list[V2ProbeOpportunity] | None = None,
) -> dict[str, TraitVectorEntry]:
    """24개 Core Trait 전체에 대해 한 번에 계산한다(`compute_student_trait_states()`와
    같은 "전체를 한 번에 계산해서 재사용" 패턴). `legacy_states`에 없는 trait_id(예: 아직
    기존 12개 목록에는 없던 신규 Trait)는 `normalized_value=None`인 빈 상태로 취급한다."""

    from src.schemas.evidence import TraitState

    result: dict[str, TraitVectorEntry] = {}
    for trait_id in core_trait_ids:
        legacy_state = legacy_states.get(trait_id) or StudentTraitState(
            trait_id=trait_id, state=TraitState.INSUFFICIENT, normalized_value=None,
            context_count=0, primary_vector_group="cognitive",
        )
        result[trait_id] = compute_trait_vector_snapshot(
            trait_id, evidence_ledger, legacy_state, unresolved_conflict_trait_ids,
            v2_probe_opportunities=v2_probe_opportunities,
        )
    return result
