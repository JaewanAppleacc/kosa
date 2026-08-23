"""v2 Career Profile 후보 선정 — 2026-08-23 Trait Ontology v2(2.6단계) §4/§5.

`src/engines/profile_engine.py`(Legacy)와 같은 원칙(순수 계산, LLM·DB 호출 없음, "어떤
Trait를 highlight로 쓸지"는 여기서 결정론적으로 정하고 "그걸 어떤 문장으로 표현할지"만
LLM에 맡긴다)을 그대로 따르되, 입력이 `TraitEvidenceSummary`(Legacy 12-Trait)가 아니라
`TraitVectorEntry`(v2 24-Trait, `dict[str, TraitVectorEntry]` — Fail-Closed 게이트를
이미 통과한 evidence_ledger로 계산된 값)라는 점이 다르다.

CLAUDE.md/§4 규칙을 그대로 지킨다:
- 관련 없는 Trait는 0점이 아니라 미관찰(NOT_PROBED/HYPOTHESIS, tendency_score=None).
- CONFLICTING(미해소 Explicit Conflict)은 backfill 후보에서 제외한다(Legacy와 동일 —
  "부족한 걸 솔직히 보여준다"와 "상충 Trait를 확정 강점처럼 노출한다"는 다르다).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from src.schemas.evidence import ContrastResolutionRecord, EvidenceOrigin, EvidenceRecord
from src.schemas.profile import DimensionEvidenceItem
from src.schemas.trait import TraitDefinition
from src.schemas.trait_vector_snapshot import TraitVectorEntry

MIN_HIGHLIGHTS = 5
MAX_HIGHLIGHTS = 8

ResolutionRoleV2 = Literal["preferred", "deprioritized", "context_dependent"]

# status 우선순위 — 작을수록 먼저 선택된다. HYPOTHESIS/NOT_PROBED는 "확정 강점"이 아니라
# "추가 탐색이 필요한 Trait"로만 backfill에 쓰인다(§5 "추가 탐색이 필요한 Trait" 항목).
_STATUS_PRIORITY: dict[str, int] = {
    "STRONG": 0, "MODERATE": 1, "LIMITED": 2, "HYPOTHESIS": 3, "NOT_PROBED": 4,
}


class HighlightCandidateV2(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    trait_definition: TraitDefinition
    entry: TraitVectorEntry
    resolution_role: ResolutionRoleV2 | None = None


def _resolution_role_for_trait(
    trait_id: str, resolutions: dict[str, ContrastResolutionRecord]
) -> ResolutionRoleV2 | None:
    for record in resolutions.values():
        if record.preferred_trait_id == trait_id:
            return "preferred"
        if record.opposite_trait_id == trait_id:
            return "deprioritized"
        if trait_id in record.context_dependent_trait_ids:
            return "context_dependent"
    return None


def select_profile_highlight_traits_v2(
    snapshot_entries: dict[str, TraitVectorEntry],
    all_trait_definitions: dict[str, TraitDefinition],
    resolutions: dict[str, ContrastResolutionRecord] | None = None,
) -> list[HighlightCandidateV2]:
    """§4/§5 — Evidence가 충분한 상위 Trait 5~8개를 고른다. STRONG 먼저(evidence_count
    내림차순), 그다음 MODERATE. 그래도 5개가 안 되면 LIMITED → HYPOTHESIS → NOT_PROBED
    순으로 채운다(§5 "추가 탐색이 필요한 Trait"를 정직하게 함께 보여준다). CONFLICTING은
    Legacy와 동일하게 backfill에서 제외한다."""

    resolutions = resolutions or {}
    candidates: list[HighlightCandidateV2] = []
    for trait_id, trait_def in all_trait_definitions.items():
        entry = snapshot_entries.get(trait_id) or TraitVectorEntry(
            trait_id=trait_id, primary_signal_sum=0.0, related_signal_sum=0.0,
            confirmed_related_signal_sum=0.0, primary_evidence_count=0, related_evidence_count=0,
            context_count=0, frame_count=0, question_count=0, tendency_score=None,
            evidence_confidence="no_evidence", status="NOT_PROBED",
        )
        candidates.append(
            HighlightCandidateV2(
                trait_definition=trait_def, entry=entry,
                resolution_role=_resolution_role_for_trait(trait_id, resolutions),
            )
        )

    def strength_key(c: HighlightCandidateV2) -> tuple[bool, int, int, str]:
        is_deprioritized = c.resolution_role == "deprioritized"
        return (
            is_deprioritized,
            _STATUS_PRIORITY.get(c.entry.status, 9),
            -c.entry.evidence_count,
            c.trait_definition.trait_id,
        )

    strong = sorted((c for c in candidates if c.entry.status == "STRONG"), key=strength_key)
    moderate = sorted((c for c in candidates if c.entry.status == "MODERATE"), key=strength_key)
    remaining = sorted(
        (c for c in candidates if c.entry.status in ("LIMITED", "HYPOTHESIS", "NOT_PROBED")),
        key=strength_key,
    )

    selected = (strong + moderate)[:MAX_HIGHLIGHTS]
    if len(selected) < MIN_HIGHLIGHTS:
        selected += remaining[: MIN_HIGHLIGHTS - len(selected)]

    return selected


def build_detailed_evidence_by_dimension_v2(
    highlight_candidates: list[HighlightCandidateV2],
    evidence_ledger: list[EvidenceRecord],
) -> dict[str, list[DimensionEvidenceItem]]:
    """§5 "실제 답변 근거" — highlight로 뽑힌 Trait들의 실제 선택 문장을 parent_dimension
    → Context 순으로 묶는다. `evidence_ledger`는 호출하는 쪽(v2 Primary 파이프라인)이
    이미 Fail-Closed 게이트를 통과시킨 목록이어야 한다 — 이 함수 자체는 검수 상태를
    판정하지 않는다(단일 책임)."""

    highlighted_trait_ids = {c.trait_definition.trait_id for c in highlight_candidates}
    dimension_by_trait_id = {
        c.trait_definition.trait_id: c.trait_definition.parent_dimension for c in highlight_candidates
    }

    result: dict[str, list[DimensionEvidenceItem]] = {}
    seen: set[tuple[str, str, str]] = set()

    for record in evidence_ledger:
        if record.evidence_origin not in (EvidenceOrigin.PRIMARY_BLUEPRINT, EvidenceOrigin.V2_DIRECT_PROBE):
            continue
        for signal in record.applied_trait_signals_v2:
            if signal.signal_role != "PRIMARY" or signal.trait_id not in highlighted_trait_ids:
                continue
            dimension = dimension_by_trait_id[signal.trait_id]
            key = (dimension, record.context, record.option_text)
            if key in seen:
                continue
            seen.add(key)
            result.setdefault(dimension, []).append(
                DimensionEvidenceItem(context_id=record.context, description=record.option_text)
            )

    return result
