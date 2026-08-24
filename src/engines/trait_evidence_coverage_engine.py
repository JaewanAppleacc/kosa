"""Trait Evidence Coverage Policy Engine (Shadow Mode) — a/trait-evidence-coverage-shadow.

CLAUDE.md "계산 함수는 가능한 한 순수 함수로 만들고 LLM·DB·네트워크 호출과 분리한다"를
그대로 따른다 — 이 파일은 LLM·DB·네트워크를 전혀 참조하지 않는다. 입력은 실제
`EvidenceRecord` 리스트(§12 Evidence Ledger, `src/schemas/evidence.py`)와 승인된
evidence_id 집합(`src/services/trait_signal_review_gate.py`가 이미 계산한 결과를 그대로
받는다 — 이 파일이 검수 상태를 다시 조회하지 않는다), 출력은
`TraitCoverageResult`(`src/schemas/trait_evidence_coverage.py`)다.

**이 파일이 하지 않는 것(진단 전용, Shadow Mode):**
- Runtime Stop Condition을 바꾸지 않는다(`evidence_engine.decide_stop_or_continue`는
  그대로다).
- Matching 점수를 바꾸지 않는다.
- 기존 `TraitState`(STRONG/MODERATE/LIMITED/CONFLICTING/INSUFFICIENT)나 `TraitVectorEntry`
  판정을 대체하지 않는다 — 이 Coverage Policy는 "이 Trait가 높다/낮다"가 아니라 "판단할
  근거가 충분한가"만 답하는 완전히 별도의 다섯 상태(UNOBSERVED/LIMITED/SUPPORTED/
  SUFFICIENT/CONFLICTED)다.

**가중치 정책(과제 §2)은 실제 v2 Signal Registry의 저장 weight(PRIMARY=1.0,
RELATED=0.33/0.67, `src/schemas/trait_signal.py`)를 재사용하지 않는다** — 이 Coverage
Policy 전용으로 별도 고정 상수(PRIMARY=1.0, 검수 승인된 RELATED=0.5, NO_SIGNAL=0)를
쓴다. 의도적인 단순화다: "LLM이 임의 점수를 만들지 않게 한다"는 목표에는 Registry의
0.33/0.67 세분화보다 이 Policy만의 고정 2단 상수가 더 명확하고 감사하기 쉽다. Registry의
weight 값은 여기서 전혀 읽지 않는다 — `signal_role`(PRIMARY/RELATED)만 본다."""

from __future__ import annotations

from collections import defaultdict

from src.schemas.evidence import ContrastDefinition, EvidenceOrigin, EvidenceRecord
from src.schemas.trait_evidence_coverage import CoverageStatus, TraitCoverageResult

# ── §2 기본 Evidence 가중치 ──────────────────────────────────────────────
PRIMARY_WEIGHT = 1.0
RELATED_WEIGHT = 0.5
NO_SIGNAL_WEIGHT = 0.0

# ── §3 SUFFICIENT 기본 기준 ──────────────────────────────────────────────
SUFFICIENT_MIN_PRIMARY_COUNT = 2
SUFFICIENT_MIN_EFFECTIVE_WEIGHT = 3.0
SUFFICIENT_MIN_CONTEXT_COUNT = 2
SUFFICIENT_MIN_FRAME_COUNT = 2
SUFFICIENT_MIN_DIRECTIONAL_CONSISTENCY = 0.7

# ── §4 SUPPORTED 기준(전체 미달이지만 이 정도는 넘음) ──────────────────────
SUPPORTED_MIN_PRIMARY_COUNT = 2
SUPPORTED_MIN_FRAME_COUNT = 2

# v2 Signal의 정당한 출처만 본다 — trait_vector_snapshot_engine.py의
# `_V2_ELIGIBLE_ORIGINS`와 동일 필터(CONFLICT_RESOLUTION/SECONDARY_HYPOTHESIS 제외).
_ELIGIBLE_ORIGINS = frozenset({EvidenceOrigin.PRIMARY_BLUEPRINT, EvidenceOrigin.V2_DIRECT_PROBE})


def evidence_dedup_key(record: EvidenceRecord) -> tuple[str, str]:
    """§2 "동일 blueprint_id+frame_id의 반복 Evidence는 최대 1회만 인정" / §6 중복 방지.

    실제 Evidence Ledger 감사 결과(`src/schemas/evidence.py::EvidenceRecord`) —
    `source_blueprint_id`는 2.6단계부터 생긴 필드라 그 이전 기록이나 LLM 생성 Adaptive
    Tail Blueprint 일부 경로에서는 None일 수 있다. blueprint_id가 없으면 그 질문은
    애초에 "고정 콘텐츠 재사용" 개념이 없는 생성 질문이므로, question_id로 대체해
    동일 질문(=같은 question_id) 재요청만 중복으로 잡고 서로 다른 생성 질문끼리는
    같은 frame이라는 이유로 뭉치지 않게 한다."""

    blueprint_key = record.source_blueprint_id or f"__no_blueprint__:{record.question_id}"
    return (blueprint_key, record.question_frame_id)


def deduplicate_evidence(
    evidence_ledger: list[EvidenceRecord], approved_evidence_ids: set[str]
) -> list[EvidenceRecord]:
    """§2/§6 — 승인된 Signal의 정당한 출처(PRIMARY_BLUEPRINT/V2_DIRECT_PROBE)만 남기고,
    동일 (blueprint_id, frame_id) 반복은 Ledger 등장 순서상 첫 번째만 남긴다. 이 결과를
    모든 Trait 계산이 공유한다 — Trait마다 다른 중복 판정을 쓰면 "어떤 Evidence가 실제로
    셈에 들어갔는가"가 Trait별로 달라져 감사할 수 없다."""

    seen: set[tuple[str, str]] = set()
    kept: list[EvidenceRecord] = []
    for record in evidence_ledger:
        if record.evidence_origin not in _ELIGIBLE_ORIGINS:
            continue
        if record.evidence_id not in approved_evidence_ids:
            continue
        key = evidence_dedup_key(record)
        if key in seen:
            continue
        seen.add(key)
        kept.append(record)
    return kept


def _directional_consistency_and_conflict(
    trait_id: str,
    contributing_records: list[EvidenceRecord],
    deduped_pool: list[EvidenceRecord],
    contrast_definitions: list[ContrastDefinition],
) -> tuple[float, int]:
    """§3/§4 "동일 방향 Evidence 비율"/"상반 방향 Evidence". 이 Trait 자신의 Evidence는
    등록된 Contrast Pair 한쪽 role_id에서만 나온다(role_id 하나는 항상 한 Trait의
    PRIMARY만 만든다) — 그래서 "반대 방향"은 이 Trait의 Evidence가 아니라 같은 Contrast의
    **반대쪽 role_id를 가진 다른 Trait의 Evidence**다. 이 Trait이 등록된 Contrast Pair
    어디에도 관여하지 않으면(현재 24개 중 22개) 1.0/0을 그대로 반환한다 — "측정해봤더니
    100% 일치"가 아니라 "애초에 반대 방향이라는 개념이 없다"는 뜻이다."""

    for contrast in contrast_definitions:
        own_roles: list[str] | None = None
        other_roles: list[str] | None = None
        if any(r.option_role_id in contrast.positive_role_ids for r in contributing_records):
            own_roles, other_roles = contrast.positive_role_ids, contrast.opposite_role_ids
        elif any(r.option_role_id in contrast.opposite_role_ids for r in contributing_records):
            own_roles, other_roles = contrast.opposite_role_ids, contrast.positive_role_ids
        else:
            continue

        comparable = set(contrast.comparable_frame_ids)
        own_weight = sum(
            PRIMARY_WEIGHT
            for r in contributing_records
            if r.question_frame_id in comparable and r.option_role_id in own_roles
        )
        other_weight = sum(
            PRIMARY_WEIGHT
            for r in deduped_pool
            if r.question_frame_id in comparable and r.option_role_id in other_roles
        )
        total = own_weight + other_weight
        if total <= 0 or other_weight <= 0:
            continue  # 이 Contrast에서는 반대쪽 근거가 없다 — 다음 Contrast를 본다.

        consistency = own_weight / total
        is_unresolved_conflict = (
            own_weight >= contrast.minimum_evidence_each_side
            and other_weight >= contrast.minimum_evidence_each_side
        )
        return consistency, (1 if is_unresolved_conflict else 0)

    return 1.0, 0


def compute_trait_coverage(
    trait_id: str,
    deduped_pool: list[EvidenceRecord],
    *,
    contrast_definitions: list[ContrastDefinition] | None = None,
) -> TraitCoverageResult:
    """§4 상태 판정. `deduped_pool`은 `deduplicate_evidence()`가 이미 승인·중복 제거를
    끝낸 결과를 그대로 받는다(이 함수가 다시 계산하지 않는다 — 24개 Trait 전부가 같은
    중복 판정을 공유해야 하므로 호출자가 한 번만 만들어 재사용한다,
    `compute_all_trait_coverage()` 참고)."""

    contrasts = contrast_definitions or []

    primary_records: list[EvidenceRecord] = []
    related_records: list[EvidenceRecord] = []
    for record in deduped_pool:
        for signal in record.applied_trait_signals_v2:
            if signal.trait_id != trait_id:
                continue
            if signal.signal_role == "PRIMARY":
                primary_records.append(record)
            elif signal.signal_role == "RELATED":
                related_records.append(record)
            break  # §2 검증(validate_role_signals)상 한 Record에 같은 Trait가 두 번 못 나온다.

    contributing = primary_records + related_records
    primary_count = len(primary_records)
    related_count = len(related_records)
    effective_weight = primary_count * PRIMARY_WEIGHT + related_count * RELATED_WEIGHT
    distinct_context_count = len({r.context for r in contributing})
    distinct_frame_count = len({r.question_frame_id for r in contributing})
    contributing_evidence_ids = list(dict.fromkeys(r.evidence_id for r in contributing))

    directional_consistency, unresolved_conflict_count = _directional_consistency_and_conflict(
        trait_id, contributing, deduped_pool, contrasts
    )

    has_conflict = unresolved_conflict_count > 0 or directional_consistency < SUFFICIENT_MIN_DIRECTIONAL_CONSISTENCY

    meets_sufficient = (
        primary_count >= SUFFICIENT_MIN_PRIMARY_COUNT
        and effective_weight >= SUFFICIENT_MIN_EFFECTIVE_WEIGHT
        and distinct_context_count >= SUFFICIENT_MIN_CONTEXT_COUNT
        and distinct_frame_count >= SUFFICIENT_MIN_FRAME_COUNT
        and directional_consistency >= SUFFICIENT_MIN_DIRECTIONAL_CONSISTENCY
        and unresolved_conflict_count == 0
    )

    status: CoverageStatus
    if primary_count == 0 and related_count == 0:
        status = "UNOBSERVED"
    elif has_conflict:
        status = "CONFLICTED"
    elif meets_sufficient:
        status = "SUFFICIENT"
    elif primary_count >= SUPPORTED_MIN_PRIMARY_COUNT and distinct_frame_count >= SUPPORTED_MIN_FRAME_COUNT:
        status = "SUPPORTED"
    else:
        status = "LIMITED"

    missing_requirements: list[str] = []
    if status != "SUFFICIENT":
        if primary_count < SUFFICIENT_MIN_PRIMARY_COUNT:
            missing_requirements.append(
                f"primary_evidence_count>={SUFFICIENT_MIN_PRIMARY_COUNT} 미충족(현재 {primary_count})"
            )
        if effective_weight < SUFFICIENT_MIN_EFFECTIVE_WEIGHT:
            missing_requirements.append(
                f"effective_evidence_weight>={SUFFICIENT_MIN_EFFECTIVE_WEIGHT} 미충족(현재 {effective_weight})"
            )
        if distinct_context_count < SUFFICIENT_MIN_CONTEXT_COUNT:
            missing_requirements.append(
                f"distinct_context_count>={SUFFICIENT_MIN_CONTEXT_COUNT} 미충족(현재 {distinct_context_count})"
            )
        if distinct_frame_count < SUFFICIENT_MIN_FRAME_COUNT:
            missing_requirements.append(
                f"distinct_frame_count>={SUFFICIENT_MIN_FRAME_COUNT} 미충족(현재 {distinct_frame_count})"
            )
        if directional_consistency < SUFFICIENT_MIN_DIRECTIONAL_CONSISTENCY:
            missing_requirements.append(
                f"directional_consistency>={SUFFICIENT_MIN_DIRECTIONAL_CONSISTENCY} 미충족"
                f"(현재 {directional_consistency:.3f})"
            )
        if unresolved_conflict_count > 0:
            missing_requirements.append("unresolved_conflict_count==0 미충족(미해결 Conflict 존재)")

    return TraitCoverageResult(
        trait_id=trait_id,
        coverage_status=status,
        effective_evidence_weight=effective_weight,
        primary_evidence_count=primary_count,
        related_evidence_count=related_count,
        distinct_context_count=distinct_context_count,
        distinct_frame_count=distinct_frame_count,
        directional_consistency=directional_consistency,
        unresolved_conflict_count=unresolved_conflict_count,
        missing_requirements=missing_requirements,
        contributing_evidence_ids=contributing_evidence_ids,
    )


def compute_all_trait_coverage(
    trait_ids: set[str],
    evidence_ledger: list[EvidenceRecord],
    approved_evidence_ids: set[str],
    *,
    contrast_definitions: list[ContrastDefinition] | None = None,
) -> dict[str, TraitCoverageResult]:
    """24개 Trait 전체를 한 번에 계산한다(`compute_trait_vector_snapshot_all()`과 같은
    "중복 제거는 한 번만" 패턴) — Trait마다 다시 필터링하면 O(trait × ledger)로 느려지고,
    무엇보다 중복 판정이 Trait마다 갈릴 위험이 생긴다."""

    deduped = deduplicate_evidence(evidence_ledger, approved_evidence_ids)
    return {
        trait_id: compute_trait_coverage(trait_id, deduped, contrast_definitions=contrast_definitions)
        for trait_id in trait_ids
    }


def coverage_status_breakdown(results: dict[str, TraitCoverageResult]) -> dict[str, int]:
    """보고서용 — 상태별 Trait 개수. 5개 상태 전부 0건이어도 Key로 남긴다(다른 진단
    스크립트의 "0건이어도 표에 남긴다" 관례와 동일)."""

    breakdown: dict[str, int] = defaultdict(int)
    for status in ("UNOBSERVED", "LIMITED", "SUPPORTED", "SUFFICIENT", "CONFLICTED"):
        breakdown[status] = 0
    for result in results.values():
        breakdown[result.coverage_status] += 1
    return dict(breakdown)
