"""Trait Vector Snapshot Engine — 2026-08-31 Trait Ontology v2(1단계) §9/§10. LLM·DB
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
from src.schemas.evidence import EvidenceOrigin, EvidenceRecord
from src.schemas.trait_vector_snapshot import TraitVectorEntry


def _records_with_signal(
    evidence_ledger: list[EvidenceRecord], trait_id: str, signal_role: str
) -> list[EvidenceRecord]:
    """§8과 동일한 필터 — PRIMARY_BLUEPRINT Origin만 본다(Conflict Resolution 답변은
    이미 답변 처리 시점에 applied_trait_signals_v2를 비워두지만, 여기서도 한 번 더
    방어적으로 막는다)."""

    return [
        r for r in evidence_ledger
        if r.evidence_origin == EvidenceOrigin.PRIMARY_BLUEPRINT
        and any(s.trait_id == trait_id and s.signal_role == signal_role for s in r.applied_trait_signals_v2)
    ]


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
) -> TraitVectorEntry:
    """트레잇 하나의 v2 Snapshot을 계산한다. `legacy_state`는 기존
    `compute_student_trait_states()`가 이미 계산해 둔 결과를 그대로 받는다 — 이 함수가
    §13 판정을 다시 하지 않는다(중복 계산 금지, matching_engine.py를 신뢰한다)."""

    primary_records = _records_with_signal(evidence_ledger, trait_id, "PRIMARY")
    related_records = _records_with_signal(evidence_ledger, trait_id, "RELATED")

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
    )


def compute_trait_vector_snapshot_all(
    evidence_ledger: list[EvidenceRecord],
    legacy_states: dict[str, StudentTraitState],
    unresolved_conflict_trait_ids: set[str],
    core_trait_ids: set[str],
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
            trait_id, evidence_ledger, legacy_state, unresolved_conflict_trait_ids
        )
    return result
