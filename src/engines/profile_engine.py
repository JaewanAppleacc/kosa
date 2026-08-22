"""Career Profile 계산 — 설계안 §13/§14 중 LLM이 아니라 Python이 결정해야 하는 부분.

CLAUDE.md: "계산 함수는 가능한 한 순수 함수로 만들고 LLM·DB·네트워크 호출과 분리한다."
"어떤 Trait를 highlight로 쓸지"와 "Context별 근거를 어떻게 묶을지"는 여기서 결정론적으로
정하고, "그걸 어떤 문장으로 표현할지"만 LLM(agents/assessment/profile_generator.py)에게
맡긴다.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from src.engines.evidence_engine import judge_trait_state
from src.schemas.evidence import (
    ContrastResolutionRecord,
    EvidenceOrigin,
    EvidenceRecord,
    TraitEvidenceSummary,
    TraitState,
    TraitStateJudgment,
)
from src.schemas.profile import DimensionEvidenceItem
from src.schemas.trait import TraitDefinition

# §14: "첫 화면에는 핵심 특징 5~8줄만 보여준다."
MIN_HIGHLIGHTS = 5
MAX_HIGHLIGHTS = 8

ResolutionRole = Literal["preferred", "deprioritized", "context_dependent"]


class HighlightCandidate(BaseModel):
    trait_definition: TraitDefinition
    judgment: TraitStateJudgment
    summary: TraitEvidenceSummary
    # 2026-08-22 2차 리뷰: §12-1 확인 질문 답변이 이 Trait에 대해 뭐라고 했는지. 텍스트
    # 생성(profile_generator.py)과 highlight 우선순위 정렬 양쪽에서 쓴다.
    resolution_role: ResolutionRole | None = None


def _resolution_role_for_trait(
    trait_id: str, resolutions: dict[str, ContrastResolutionRecord]
) -> ResolutionRole | None:
    for record in resolutions.values():
        if record.preferred_trait_id == trait_id:
            return "preferred"
        if record.opposite_trait_id == trait_id:
            return "deprioritized"
        if trait_id in record.context_dependent_trait_ids:
            return "context_dependent"
    return None


def select_profile_highlight_traits(
    trait_summaries: dict[str, TraitEvidenceSummary],
    all_trait_definitions: dict[str, TraitDefinition],
    unresolved_conflict_trait_ids: set[str],
    resolutions: dict[str, ContrastResolutionRecord] | None = None,
) -> list[HighlightCandidate]:
    """§13 상태 판정 순서대로 모든 Trait을 판정한 뒤, §14의 5~8개 제약에 맞게 고른다.

    우선순위: STRONG 먼저(강도순), 그다음 MODERATE. 그래도 5개가 안 되면 LIMITED/
    INSUFFICIENT를 채운다 — §14 화면 예시 자체가 "협업 방식은 아직 Evidence가 적어
    추가 탐색이 필요해요"처럼 부족함을 솔직히 보여주는 줄을 포함한다(CLAUDE.md
    "Missing, Insufficient, Conflicting 상태를 정상 점수처럼 취급하지 않는다"와
    같은 이유로, 숨기지 않고 정직하게 드러낸다).

    2026-08-22 2차 리뷰: `resolutions`가 주어지면 "확인 질문에서 상대적으로 덜 우선"으로
    밝혀진 Trait(resolution_role="deprioritized")를 같은 상태 구간 안에서 뒤로 민다 —
    완전히 배제하지 않지만(둘 다 STRONG이면 둘 다 후보로 남는다), 우선한 쪽이 먼저
    선택되게 한다.
    """

    resolutions = resolutions or {}
    judged: list[HighlightCandidate] = []
    for trait_id, trait_def in all_trait_definitions.items():
        summary = trait_summaries.get(trait_id) or TraitEvidenceSummary(trait_id=trait_id)
        judgment = judge_trait_state(
            summary, trait_def.minimum_context_count, trait_id in unresolved_conflict_trait_ids
        )
        judged.append(
            HighlightCandidate(
                trait_definition=trait_def,
                judgment=judgment,
                summary=summary,
                resolution_role=_resolution_role_for_trait(trait_id, resolutions),
            )
        )

    def strength_key(candidate: HighlightCandidate) -> tuple[bool, int, int, str]:
        # deprioritized면 같은 상태 구간 안에서 항상 뒤로(False < True) — 그다음 support_
        # count·context_count가 클수록 우선(내림차순), 동률이면 trait_id로 결정론적.
        is_deprioritized = candidate.resolution_role == "deprioritized"
        return (
            is_deprioritized,
            -candidate.summary.support_count,
            -candidate.summary.context_count,
            candidate.trait_definition.trait_id,
        )

    strong = sorted(
        (c for c in judged if c.judgment.state == TraitState.STRONG), key=strength_key
    )
    moderate = sorted(
        (c for c in judged if c.judgment.state == TraitState.MODERATE), key=strength_key
    )
    # 2026-08-21 3단계: CONFLICTING은 backfill 후보에서도 제외한다 — "부족한 걸 솔직히
    # 보여준다"와 "명시적으로 상충되는 Trait를 결과에 노출한다"는 다르다(CLAUDE.md
    # "Missing, Insufficient, Conflicting 상태를 정상 점수처럼 취급하지 않는다"). 게다가
    # CONFLICTING인 Trait는 대개 support_count가 이미 쌓여 있어(그래서 상충이 드러난
    # 것이므로) strength_key 정렬에서 진짜 미확인 Trait보다 앞자리를 차지해버리는 부작용도
    # 있었다.
    remaining = sorted(
        (c for c in judged if c.judgment.state in (TraitState.LIMITED, TraitState.INSUFFICIENT)),
        key=strength_key,
    )

    selected = (strong + moderate)[:MAX_HIGHLIGHTS]
    if len(selected) < MIN_HIGHLIGHTS:
        selected += remaining[: MIN_HIGHLIGHTS - len(selected)]

    return selected


def build_detailed_evidence_by_dimension(
    highlight_candidates: list[HighlightCandidate],
    evidence_ledger: list[EvidenceRecord],
) -> dict[str, list[DimensionEvidenceItem]]:
    """§14 "왜 이런 결과가 나왔나요?" — highlight로 뽑힌 Trait들의 실제 선택 문장을
    parent_dimension(Career Dimension) → Context 순으로 묶는다. Evidence 원문(선택한
    Option의 실제 문장)을 그대로 쓴다 — 다시 요약·paraphrase하지 않아 역추적 가능성을
    유지한다(CLAUDE.md "추천 근거는 Evidence와 공식 Source까지 역추적 가능해야 한다")."""

    highlighted_trait_ids = {c.trait_definition.trait_id for c in highlight_candidates}
    dimension_by_trait_id = {
        c.trait_definition.trait_id: c.trait_definition.parent_dimension for c in highlight_candidates
    }

    result: dict[str, list[DimensionEvidenceItem]] = {}
    seen: set[tuple[str, str, str]] = set()  # (dimension, context, description) 중복 방지

    for record in evidence_ledger:
        if record.evidence_origin != EvidenceOrigin.PRIMARY_BLUEPRINT:
            continue
        for trait_id in record.applied_primary_trait_delta:
            if trait_id not in highlighted_trait_ids:
                continue
            dimension = dimension_by_trait_id[trait_id]
            key = (dimension, record.context, record.option_text)
            if key in seen:
                continue
            seen.add(key)
            result.setdefault(dimension, []).append(
                DimensionEvidenceItem(context_id=record.context, description=record.option_text)
            )

    return result
