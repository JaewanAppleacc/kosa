"""Trait Signal Review Gate — Fail-Closed 검수 게이트, 2026-08-23 Trait Ontology
v2(2.6단계) §3.

`ENABLE_TRAIT_VECTOR_V2_PRIMARY=true`일 때 Career Profile·전공·과목 추천의 실제 입력이
되는 Signal은 그 Signal을 만든 질문·선택지가 reviewer_1 기준 APPROVED여야 한다(§3).
이 파일은 그 판정만 한다 — 검수 상태를 대신 채우거나 승격시키지 않는다(다른 review_store
모듈들과 같은 원칙).

대상은 2.5.x단계에서 도입된, 사람이 사후에 APPROVE/REVISE/HOLD로 판정하는 고정 콘텐츠
질문(V2 Direct Probe·Seed Anchor Variant·Backup·Anchor Backup)뿐이다. Legacy LLM
생성 질문(`tail_blueprint`)과 Mock Placeholder는 Question Quality Gate가 이미 게이트
역할을 하고 있고 애초에 이 reviewer_1/reviewer_2 검수 UI의 대상이 아니므로, 이 게이트가
막지 않는다(§3은 "검수 UI가 다루는 질문"에 한정된 규칙이다).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.schemas.evidence import EvidenceOrigin, EvidenceRecord
from src.services.anchor_backup_review_store import load_anchor_backup_question_review_entries
from src.services.backup_question_review_store import load_backup_question_review_entries
from src.services.seed_anchor_review_store import load_seed_anchor_question_review_entries
from src.services.v2_direct_probe_review_store import (
    load_question_review_entries as load_direct_probe_question_review_entries,
)

# reviewer_1/reviewer_2 검수 UI 대상이 아닌 family — 항상 허용한다(위 docstring 참고).
_ALWAYS_APPROVED_FAMILIES = frozenset({"tail_blueprint", "mock_placeholder", "conflict_resolution"})


class SignalReviewGateResult(BaseModel):
    """§3 "어떤 Signal이 검수 미완료로 제외됐는지 Trace와 진단 결과에서 확인 가능하게
    함"을 만족하기 위한 값 — 학생 화면(공개 API)에는 절대 노출하지 않는다. LangSmith
    메타데이터·내부 진단 전용."""

    approved_evidence_ids: set[str] = Field(default_factory=set)
    excluded_evidence_ids: set[str] = Field(default_factory=set)


def _direct_probe_review_status(blueprint_id: str) -> str | None:
    entries = {e.blueprint_id: e.final_status for e in load_direct_probe_question_review_entries()}
    return entries.get(blueprint_id)


def _backup_family_review_status(blueprint_id: str) -> str | None:
    # Anchor Backup(신규 15개)이 있으면 그것을 우선 조회하고, 없으면 기존 Backup(6개)
    # 목록에서 찾는다 — 두 목록의 blueprint_id 공간은 서로 겹치지 않는다(2.5.4단계 §3).
    anchor_ids = {e.blueprint_id: e.final_status for e in load_anchor_backup_question_review_entries()}
    if blueprint_id in anchor_ids:
        return anchor_ids[blueprint_id]
    old_ids = {e.blueprint_id: e.final_status for e in load_backup_question_review_entries()}
    return old_ids.get(blueprint_id)


def _seed_anchor_review_status(context_id: str, anchor_id: str) -> str | None:
    entries = {(e.context_id, e.anchor_id): e.final_status for e in load_seed_anchor_question_review_entries()}
    return entries.get((context_id, anchor_id))


def is_evidence_signal_approved(evidence: EvidenceRecord, context_anchor_choices: dict[str, str]) -> bool:
    """이 Evidence를 만든 질문이 reviewer_1 기준 APPROVED인가. Fail-Closed —
    검수 상태를 알 수 없는 family/blueprint_id는 승인된 것으로 가정하지 않는다."""

    family = evidence.source_question_family_id
    blueprint_id = evidence.source_blueprint_id

    if family is None or family in _ALWAYS_APPROVED_FAMILIES:
        return True

    if family == "context_routing":
        # Routing 질문은 구조적으로 Trait Signal이 없다(trait_signal_free) — 이 함수를
        # 호출하는 쪽은 애초에 Signal이 있는 Evidence만 넘기므로 도달할 일이 없지만,
        # 방어적으로 명시한다.
        return True

    if family == "v2_direct_probe":
        status = _direct_probe_review_status(blueprint_id or "")
        return status == "APPROVED"

    if family == "backup":
        status = _backup_family_review_status(blueprint_id or "")
        return status == "APPROVED"

    if family == "seed":
        anchor_id = context_anchor_choices.get(evidence.context)
        if anchor_id is None:
            # Anchor 없는 Legacy Seed — 이 검수 시스템 대상이 아니다. CLAUDE.md
            # "Context마다 검토된 Seed Question 1개를 사용한다" — 설계 시점에 이미
            # 검토된 고정 문항으로 취급한다(2.5.x단계 사후 검수 UI는 Anchor Variant만
            # 새로 다룬다).
            return True
        status = _seed_anchor_review_status(evidence.context, anchor_id)
        return status == "APPROVED"

    # 알 수 없는 family — Fail-Closed: 승인된 것으로 가정하지 않는다.
    return False


def gate_primary_eligible_evidence(
    evidence_ledger: list[EvidenceRecord], context_anchor_choices: dict[str, str]
) -> SignalReviewGateResult:
    """v2 Signal의 정당한 출처(PRIMARY_BLUEPRINT/V2_DIRECT_PROBE)만 검수 상태를
    판정한다 — CONFLICT_RESOLUTION 등 다른 origin은 애초에 v2 계산에 안 쓰이므로
    이 판정 대상이 아니다(trait_vector_snapshot_engine.py의 `_V2_ELIGIBLE_ORIGINS`와
    같은 필터를 여기서도 적용한다)."""

    approved: set[str] = set()
    excluded: set[str] = set()
    for record in evidence_ledger:
        if record.evidence_origin not in (EvidenceOrigin.PRIMARY_BLUEPRINT, EvidenceOrigin.V2_DIRECT_PROBE):
            continue
        if is_evidence_signal_approved(record, context_anchor_choices):
            approved.add(record.evidence_id)
        else:
            excluded.add(record.evidence_id)
    return SignalReviewGateResult(approved_evidence_ids=approved, excluded_evidence_ids=excluded)


def filter_primary_eligible_evidence(
    evidence_ledger: list[EvidenceRecord], context_anchor_choices: dict[str, str]
) -> list[EvidenceRecord]:
    """§3 — DRAFT/REVIEW_REQUIRED 질문에서 나온 Signal을 제외한 evidence_ledger를
    돌려준다. 원본 Ledger는 건드리지 않는다(§4 "기존 Evidence Ledger를 변경하거나
    삭제하지 않는다") — 이 함수는 새 list를 만들어 반환할 뿐이다.

    Shadow 계산(`main.py::_compute_and_store_trait_vector_shadow_snapshot`)은 이 함수를
    쓰지 않는다 — DRAFT Signal도 Shadow 분석에는 그대로 남겨야 한다(§3 "DRAFT Signal은
    Shadow 분석에는 남길 수 있으나 Primary 계산에서는 제외")."""

    gate = gate_primary_eligible_evidence(evidence_ledger, context_anchor_choices)
    return [e for e in evidence_ledger if e.evidence_id not in gate.excluded_evidence_ids]
