"""ContextPack Adaptive Tail Planner — 2026-08-23 Trait Ontology v2(2.9단계) §4/§7.

Seed 다음에 나오는 Adaptive Tail 질문의 Target Trait·Blueprint를 순수 함수로 고른다
(LangGraph Node가 아니다 — CLAUDE.md "계산 함수는 순수 함수로, LLM·DB 호출과 분리"를
그대로 따른다, `src/engines/v2_direct_probe_selector.py`와 동일 원칙).

`evidence_engine.decide_stop_or_continue()`/`has_coverage_gap()`은 이미 "최소 4개·
최대 6개, Coverage Gap 있으면 계속" 정책을 순수 함수로 구현하고 있다(Legacy Tail이
그대로 쓴다) — 여기서 다시 만들지 않고 그대로 재사용한다(`src/api/main.py`가 호출).
이 파일은 그 정책이 필요로 하는 "이 Context 전용 trait_summaries"와 "다음 Target
Trait+Blueprint 선택"만 담당한다."""

from __future__ import annotations

from pydantic import BaseModel

from src.engines.v2_direct_probe_selector import select_blueprint_for_trait
from src.schemas.evidence import EvidenceOrigin, EvidenceRecord, TraitEvidenceSummary
from src.schemas.v2_direct_probe import V2DirectProbeBlueprint

# Pack Context의 Seed는 PRIMARY_BLUEPRINT, Adaptive Tail Direct Probe는 V2_DIRECT_PROBE로
# 기록된다(`main.py::_submit_pack_context_probe_answer`) — 둘 다 "이 Context에서 실제로
# 관찰된 1차 Evidence"이므로 둘 다 센다. `evidence_engine.summarize_trait_evidence()`는
# PRIMARY_BLUEPRINT만 세는데, 그건 Legacy 12-Trait 집계가 SECONDARY_HYPOTHESIS/
# CONFLICT_RESOLUTION을 섞지 않기 위한 것이라(그 Origin들은 Pack Context에 애초에
# 나타나지 않는다) 여기 그대로 재사용하면 V2_DIRECT_PROBE Evidence가 전부 빠져 Gap
# 판정이 사실상 항상 True가 된다 — 그래서 이 파일은 같은 계산을 넓은 Origin 집합으로
# 직접 한다(evidence_engine.py는 건드리지 않는다, Legacy 계산에 영향 없음).
_PACK_CONTEXT_PRIMARY_ORIGINS = frozenset({EvidenceOrigin.PRIMARY_BLUEPRINT, EvidenceOrigin.V2_DIRECT_PROBE})


class PackAdaptiveTargetDecision(BaseModel):
    trait_id: str
    blueprint: V2DirectProbeBlueprint


def compute_pack_context_trait_summaries(
    evidence_ledger: list[EvidenceRecord],
    offered_trait_ids_by_question: dict[str, list[str]],
    *,
    context_id: str,
    trait_ids: set[str],
) -> dict[str, TraitEvidenceSummary]:
    """§7 "Context 전체 Coverage 개선" — 세션 전체가 아니라 이 Context에서 실제로
    제시된 질문(evidence.context == context_id)만으로 Trait별 요약을 계산한다. 다른
    Context에서 이미 STRONG으로 확인된 Trait라도 이 Context의 예산(최소 4·최대 6)을
    건너뛰지 않는다 — `decide_stop_or_continue()`가 처음 4개는 무조건 CONTINUE로
    강제하므로, 이 함수는 4~6번째 질문에서의 Gap 판단에만 영향을 준다."""

    context_records = [
        r for r in evidence_ledger if r.context == context_id and r.evidence_origin in _PACK_CONTEXT_PRIMARY_ORIGINS
    ]
    context_question_ids = {r.question_id for r in context_records}
    all_offered_sets = [set(offered_trait_ids_by_question.get(qid, [])) for qid in context_question_ids]

    summaries: dict[str, TraitEvidenceSummary] = {}
    for trait_id in trait_ids:
        support_count = sum(1 for r in context_records if trait_id in r.applied_primary_trait_delta)
        opportunity_count = sum(1 for offered in all_offered_sets if trait_id in offered)
        contexts = {r.context for r in context_records if trait_id in r.applied_primary_trait_delta}
        frames = {r.question_frame_id for r in context_records if trait_id in r.applied_primary_trait_delta}
        summaries[trait_id] = TraitEvidenceSummary(
            trait_id=trait_id, support_count=support_count, opportunity_count=opportunity_count,
            context_count=len(contexts), distinct_frame_count=len(frames),
        )
    return summaries


def _is_evidence_gap(trait_id: str, trait_summaries: dict[str, TraitEvidenceSummary]) -> bool:
    summary = trait_summaries.get(trait_id)
    if summary is None:
        return True
    return summary.opportunity_count == 0 or summary.support_count < 2


def select_pack_adaptive_target(
    *,
    candidate_pool: list[V2DirectProbeBlueprint],
    trait_summaries: dict[str, TraitEvidenceSummary],
    already_used_blueprint_ids: set[str],
    recent_target_trait_id: str | None,
    used_frame_ids: set[str],
    final_contexts: list[str],
) -> PackAdaptiveTargetDecision | None:
    """§7 우선순위를 그대로 코드로 옮긴다:

    1. 이 Context에서 관찰 가능한 PRIMARY Trait(candidate_pool에 실제 Blueprint가
       있는 Trait만 애초에 후보다 — §7 마지막 규칙 "가능한 Blueprint가 실제로 존재하고
       검수된 Trait"만).
    2/5. Evidence가 부족한 Trait 우선(opportunity_count==0 또는 support_count<2).
    3. 최근 목표 Trait와 다른 Trait를 우선(완전히 배제하지는 않는다 — 그 Trait밖에
       남지 않았으면 그래도 물어봐야 한다).
    4. 아직 사용하지 않은 Frame(select_blueprint_for_trait가 이미 이 기준으로
       내부 정렬한다) — 여기서는 blueprint_id 재사용 금지만 별도로 강제한다.
    6. blueprint_id 오름차순(최종 결정론적 Tie-break, select_blueprint_for_trait 내부).

    맞는 Blueprint가 없으면 None — 호출부(main.py)가 억지로 새 Trait를 만들지 않고
    Anchor Backup이나 Context 종료로 넘어간다(§7 마지막 규칙)."""

    candidate_trait_ids = sorted({bp.trait_id for bp in candidate_pool})

    def sort_key(trait_id: str) -> tuple[bool, bool, str]:
        gap = _is_evidence_gap(trait_id, trait_summaries)
        same_as_recent = trait_id == recent_target_trait_id
        return (not gap, same_as_recent, trait_id)  # gap=True(부족)가 앞으로

    for trait_id in sorted(candidate_trait_ids, key=sort_key):
        pool_for_trait = [
            bp for bp in candidate_pool
            if bp.trait_id == trait_id and bp.blueprint_id not in already_used_blueprint_ids
        ]
        if not pool_for_trait:
            continue
        blueprint = select_blueprint_for_trait(
            trait_id, related_context_ids=set(), preferred_context_ids=[],
            final_contexts=final_contexts, used_v2_probe_frame_ids=used_frame_ids,
            candidate_pool=pool_for_trait,
        )
        if blueprint is not None:
            return PackAdaptiveTargetDecision(trait_id=trait_id, blueprint=blueprint)
    return None
