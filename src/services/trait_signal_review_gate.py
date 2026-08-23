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

from src.data.contexts.context_activation_batches import ALL_BATCH_CONTEXT_IDS
from src.schemas.evidence import EvidenceOrigin, EvidenceRecord
from src.services.anchor_backup_review_store import load_anchor_backup_question_review_entries
from src.services.backup_question_review_store import load_backup_question_review_entries
from src.services.context_pack_registry import ContextPackRegistry
from src.services.context_pack_review_store import load_context_pack_review_entries
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


def _load_pack_review_entries(context_id: str, registry: ContextPackRegistry) -> dict[str, object]:
    """`context_id`의 검수 파일을 Key(`blueprint_id` 필드)로 인덱싱해서 돌려준다.
    `registry.review_status_path_for()`로 이 Registry가 실제로 쓰는 검수 디렉터리를
    그대로 따라간다 — base_dir 없이 호출하면 항상 실제(운영) 디렉터리로 새서, 테스트
    전용 Registry(review_status_dir로 임시 디렉터리를 주입한)와 결과가 어긋난다."""

    return {
        e.blueprint_id: e
        for e in load_context_pack_review_entries(context_id, registry.review_status_path_for(context_id).parent)
    }


def _pack_question_approved_by_anchor(
    context_id: str, anchor_id: str, kind: str, registry: ContextPackRegistry,
) -> bool:
    """2026-08-23 Trait Ontology v2(2.9.1단계) §2 — ContextPack 자신의 Seed/Anchor
    Backup Evidence 판정(`kind` in {"seed", "anchor_backup"}). 이 두 Family는
    Anchor 하나당 정확히 1개 질문이라 검수 Key도 Anchor 기준
    (`context_id::kind::anchor_id`, `ContextPackRegistry.required_review_keys()`와
    같은 형식)이다 — Native Direct Probe(아래 `_pack_native_direct_probe_approved`)와
    reference_id 의미가 다르므로 한 함수에 섞지 않는다(2.9.1단계 §1-1 감사 반영).

    AND 조건: (1) Context Pack 자체가 reviewer_1 APPROVED(`registry.
    is_pack_review_approved`, 모든 필수 Key 포함) AND (2) 이 질문 하나의 Key가 그
    검수 파일 안에서 그 자체로도 APPROVED. 두 조건이 사실상 겹치더라도(전체가
    APPROVED면 개별 Key도 APPROVED다) 나중에 `is_pack_review_approved`의 정의가
    느슨해지는 경우를 대비해 이중으로 확인한다."""

    if not registry.is_pack_review_approved(context_id):
        return False
    entries = _load_pack_review_entries(context_id, registry)
    key = f"{context_id}::{kind}::{anchor_id}"
    entry = entries.get(key)
    return entry is not None and entry.final_status == "APPROVED"


def _pack_native_direct_probe_approved(
    context_id: str, blueprint_id: str, registry: ContextPackRegistry,
) -> bool:
    """2026-08-23 Trait Ontology v2(2.9.1단계) §1-1 수정 — Pack 자신의
    `direct_probe_candidates`에서 온 Native Direct Probe 전용 판정. 이 Family는
    Anchor 하나에 여러 Native Probe가 있을 수 있어(향후 확장) Key가 Anchor 기준이
    아니라 Blueprint 기준(`context_id::direct_probe::blueprint_id`)이다 —
    `ContextPackRegistry.required_review_keys()`가 실제로 쓰는 정본 Key와 정확히
    같은 형식이어야 한다.

    2.9.1단계 이전에는 이 판정이 `_pack_question_approved(context_id, anchor_id,
    "direct_probe", registry)`처럼 실수로 anchor_id를 Key에 썼다 — 검수 파일은
    처음부터 blueprint_id로 저장되므로(`required_review_keys()` 참고), 사람이 올바른
    Key로 APPROVE해도 이 게이트가 영원히 그 Key를 못 찾아 Fail-Closed로 막히는 조용한
    버그였다(안전한 방향의 실패였지만 근거가 틀렸다 — 정상 승인된 콘텐츠까지 막았다).
    `tests/test_context_pack_review_gate_e2e.py::NativeDirectProbeReviewKeyTest`가
    합성 Pack Fixture로 이 버그를 재현하고 고정한다."""

    if not registry.is_pack_review_approved(context_id):
        return False
    entries = _load_pack_review_entries(context_id, registry)
    key = f"{context_id}::direct_probe::{blueprint_id}"
    entry = entries.get(key)
    return entry is not None and entry.final_status == "APPROVED"


def _pack_direct_probe_approved(
    context_id: str, anchor_id: str, blueprint_id: str, registry: ContextPackRegistry,
) -> bool:
    """2026-08-23 Trait Ontology v2(2.9.1단계) §2/§3 — pack_direct_probe Evidence
    판정. Pack 자신의 `direct_probe_candidates`에서 온 것이면 Native 전용 판정
    (`_pack_native_direct_probe_approved`, blueprint_id 기준)으로, 공용 Adaptive
    Probe Pool에서 온 것이면 Context+Anchor 단위 검수(`ContextPackRegistry.
    is_shared_probe_approved_for_anchor`, §3)로 판정한다 — 두 경로가 서로 다른
    reference_id 의미(blueprint_id vs anchor_id)를 쓰므로 호출 지점에서부터
    명시적으로 분리한다."""

    pack = registry.get_pack(context_id)
    if pack is None:
        return False
    if any(p.blueprint_id == blueprint_id for p in pack.direct_probe_candidates):
        return _pack_native_direct_probe_approved(context_id, blueprint_id, registry)
    return registry.is_shared_probe_approved_for_anchor(blueprint_id, context_id, anchor_id)


def is_evidence_signal_approved(
    evidence: EvidenceRecord, context_anchor_choices: dict[str, str], registry: ContextPackRegistry | None = None,
) -> bool:
    """이 Evidence를 만든 질문이 reviewer_1 기준 APPROVED인가. Fail-Closed —
    검수 상태를 알 수 없는 family/blueprint_id는 승인된 것으로 가정하지 않는다.

    2026-08-23 Trait Ontology v2(2.9.1단계) §2: `registry`는 신규 ContextPack Evidence
    (family가 "seed"이면서 `evidence.context`가 배치 Context인 경우, "pack_backup",
    "pack_direct_probe")를 판정할 때만 쓴다 — Legacy game/media/school_life 판정
    경로는 기존과 동일하게 `registry` 없이도 정확히 동작한다(하위 호환, 기존 테스트
    17개가 `registry`를 넘기지 않고 그대로 통과한다). `main.py`는 항상 이미 만들어
    둔 `_context_pack_registry` 싱글턴을 넘긴다(요청마다 새로 스캔하지 않는다) — 이
    함수가 자체적으로 새 Registry를 만들지는 않는다(넘기지 않으면 신규 Pack 판정은
    Fail-Closed로 거부된다, 아래 참고)."""

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
        if evidence.context in ALL_BATCH_CONTEXT_IDS:
            # 2.9.1단계 §1/§2: 신규 ContextPack Seed(2.9단계에는 이 분기가 아예 없어
            # Legacy Seed Anchor Store에서 항상 못 찾고 조용히 거부됐다 — 결과는
            # 우연히 Fail-Closed였지만 근거가 틀렸다). Registry가 없으면 판정 불가 —
            # Fail-Closed.
            if registry is None:
                return False
            return _pack_question_approved_by_anchor(evidence.context, anchor_id, "seed", registry)
        status = _seed_anchor_review_status(evidence.context, anchor_id)
        return status == "APPROVED"

    if family == "pack_backup":
        anchor_id = context_anchor_choices.get(evidence.context)
        if anchor_id is None or registry is None:
            return False
        return _pack_question_approved_by_anchor(evidence.context, anchor_id, "anchor_backup", registry)

    if family == "pack_direct_probe":
        anchor_id = context_anchor_choices.get(evidence.context)
        if anchor_id is None or registry is None:
            return False
        return _pack_direct_probe_approved(evidence.context, anchor_id, blueprint_id or "", registry)

    # 알 수 없는 family — Fail-Closed: 승인된 것으로 가정하지 않는다.
    return False


def gate_primary_eligible_evidence(
    evidence_ledger: list[EvidenceRecord], context_anchor_choices: dict[str, str],
    registry: ContextPackRegistry | None = None,
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
        if is_evidence_signal_approved(record, context_anchor_choices, registry):
            approved.add(record.evidence_id)
        else:
            excluded.add(record.evidence_id)
    return SignalReviewGateResult(approved_evidence_ids=approved, excluded_evidence_ids=excluded)


def filter_primary_eligible_evidence(
    evidence_ledger: list[EvidenceRecord], context_anchor_choices: dict[str, str],
    registry: ContextPackRegistry | None = None,
) -> list[EvidenceRecord]:
    """§3 — DRAFT/REVIEW_REQUIRED 질문에서 나온 Signal을 제외한 evidence_ledger를
    돌려준다. 원본 Ledger는 건드리지 않는다(§4 "기존 Evidence Ledger를 변경하거나
    삭제하지 않는다") — 이 함수는 새 list를 만들어 반환할 뿐이다.

    Shadow 계산(`main.py::_compute_and_store_trait_vector_shadow_snapshot`)은 이 함수를
    쓰지 않는다 — DRAFT Signal도 Shadow 분석에는 그대로 남겨야 한다(§3 "DRAFT Signal은
    Shadow 분석에는 남길 수 있으나 Primary 계산에서는 제외")."""

    gate = gate_primary_eligible_evidence(evidence_ledger, context_anchor_choices, registry)
    return [e for e in evidence_ledger if e.evidence_id not in gate.excluded_evidence_ids]
