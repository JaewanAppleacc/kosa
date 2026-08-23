"""V2 Direct Probe 후보 선택 — 2026-08-24 Trait Ontology v2(2단계) §11.

LangGraph Node가 아니라 순수 함수다(CLAUDE.md: "계산 함수는 가능한 한 순수 함수로 만들고
LLM·DB·네트워크 호출과 분리한다"). LLM은 다음 Trait을 선택하지 않는다 — 여기서 전부
결정론적으로 정해진다.
"""

from __future__ import annotations

from src.data.questions.trait_v2_direct_probe_blueprints import (
    V2_DIRECT_PROBE_BLUEPRINTS_BY_TRAIT,
    V2_DIRECT_PROBE_TARGET_TRAIT_IDS,
)
from src.schemas.trait_vector_snapshot import TraitVectorEntry
from src.schemas.v2_direct_probe import V2DirectProbeBlueprint

# §11 우선순위 3: 현재 Signal이 없는 탐색 Trait. 한 학생에게 최대 1개만 제시한다.
EXPLORATION_TRAIT_IDS: frozenset[str] = frozenset({"creative_ideation", "independent_judgment"})


def _tier(trait_id: str, entry: TraitVectorEntry | None) -> int:
    if trait_id in EXPLORATION_TRAIT_IDS:
        return 3
    if entry is None:
        return 3
    # 우선순위 1: RELATED Hypothesis가 있고 아직 PRIMARY로 확인되지 않은 Trait 중,
    # 승격 조건(§9)을 이미 만족했거나 RELATED가 2회 이상 관찰된 쪽을 더 급하게 본다.
    if entry.related_evidence_count >= 2 or entry.evidence_confidence == "promoted_related_signal":
        return 1
    # 우선순위 2: RELATED는 있지만 한 번만 관찰된 Trait.
    if entry.related_evidence_count == 1:
        return 2
    return 3


def select_v2_probe_candidates(
    v2_snapshot: dict[str, TraitVectorEntry],
    already_probed_trait_ids: set[str],
) -> list[str]:
    """§11 우선순위대로 정렬된 후보 Trait id 목록을 반환한다. 이미 이 세션에서 Direct
    Probe로 질문한 Trait는 제외한다(§4 "동일 Trait를 두 번 묻지 마세요"). 탐색 Trait
    (creative_ideation/independent_judgment)는 최대 1개만 목록에 남는다."""

    candidates = [
        trait_id for trait_id in V2_DIRECT_PROBE_TARGET_TRAIT_IDS
        if trait_id not in already_probed_trait_ids
    ]

    def sort_key(trait_id: str) -> tuple:
        entry = v2_snapshot.get(trait_id)
        tier = _tier(trait_id, entry)
        question_count = entry.question_count if entry else 0
        context_count = entry.context_count if entry else 0
        frame_count = entry.frame_count if entry else 0
        related_sum = entry.related_signal_sum if entry else 0.0
        # 정렬 기준(§11): 서로 다른 질문 수 → Context 다양성 → Frame 다양성 →
        # Related Signal 합 → 고정 Trait ID 순서. 전부 내림차순이라 음수로 뒤집는다.
        return (tier, -question_count, -context_count, -frame_count, -related_sum, trait_id)

    candidates.sort(key=sort_key)

    result: list[str] = []
    exploration_used = False
    for trait_id in candidates:
        if trait_id in EXPLORATION_TRAIT_IDS:
            if exploration_used:
                continue
            exploration_used = True
        result.append(trait_id)
    return result


def select_blueprint_for_trait(
    trait_id: str, final_contexts: list[str], used_v2_probe_frame_ids: set[str]
) -> V2DirectProbeBlueprint | None:
    """§7/§11: 학생이 선택한 Context에서 자연스러운 Blueprint만 후보로 삼고, 이미 쓴
    Frame과 중복되지 않는 쪽을 우선한다. 맞는 Blueprint가 없으면 None(호출자가 다음
    후보 Trait로 넘어간다)."""

    candidates = [
        bp for bp in V2_DIRECT_PROBE_BLUEPRINTS_BY_TRAIT.get(trait_id, [])
        if set(bp.allowed_context_ids) & set(final_contexts)
    ]
    if not candidates:
        return None

    def sort_key(bp: V2DirectProbeBlueprint) -> tuple:
        frame_already_used = bp.question_frame_id in used_v2_probe_frame_ids
        return (frame_already_used, bp.blueprint.blueprint_id)

    candidates.sort(key=sort_key)
    return candidates[0]
