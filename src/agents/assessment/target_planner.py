"""Question Target Planner — 설계안 §8 구현.

LangGraph Node가 아니라 순수 함수다(CLAUDE.md: "계산 함수는 가능한 한 순수 함수로 만들고
LLM·DB·네트워크 호출과 분리한다"). 질문 "문장"은 만들지 않고, 다음 질문이 어떤 Trait를
노려야 하는지와 어떤 Frame을 쓸지만 정한다. 실제 문장 생성은 Question Generator(LLM)가
별도로 담당한다(§10, 미구현).

의도적으로 미구현/단순화한 부분 (§8 전체를 한 번에 만들지 않기 위한 축소):
- "필수 질문 역할 미충족" 우선순위(§8 위치 5-6 순서 3번)는 Context별 역할 이력을 추적하는
  구조가 아직 없어서 뺐다. 지금은 Conflict → Coverage Gap 두 단계만 구현한다.
- "다른 Context에서 확인 가능한 미확인 Secondary Hypothesis"(§8 위치 5-6 순서 4번)도
  SecondaryTraitHypothesis 상태 전이 로직이 아직 없어서 뺐다.
- 사전 Trait 판별력(static_trait_discrimination) tie-break는 설계안도 "선택적"이라고
  명시한 값이라 구현하지 않았다 — 동률이면 trait_id 알파벳 순으로 결정론적으로 고른다.
"""

from __future__ import annotations

from pydantic import BaseModel

from src.data.question_frames.frame_role_map import PositionTheme, frame_for_theme, position_to_theme
from src.schemas.evidence import TraitEvidenceSummary


class PlannerDecision(BaseModel):
    target_traits: list[str]
    question_frame: str
    context: str
    purpose: str


def _violates_repetition_rule(trait_id: str, recent_target_trait_ids: list[str]) -> bool:
    """§8 자기확증 방지: 동일 Trait를 연속 3회 이상 묻지 않는다.

    recent_target_trait_ids는 최근 순서대로(오래된 것 → 최신) 정렬돼 있다고 가정한다.
    """

    if len(recent_target_trait_ids) < 2:
        return False
    return recent_target_trait_ids[-1] == trait_id and recent_target_trait_ids[-2] == trait_id


def _needs_cross_context_confirmation(summary: TraitEvidenceSummary) -> bool:
    """context_count<=1이면 아직 한 Context에서만 관찰된 것이므로 교차 확인이 필요하다."""

    return summary.context_count <= 1


def _select_theme_candidate(
    theme: PositionTheme,
    all_trait_ids: set[str],
    trait_summaries: dict[str, TraitEvidenceSummary],
    recent_target_trait_ids: list[str],
) -> str:
    """§8 우선순위 ①②③: 후보 중 교차확인이 필요한 Trait를 우선하고, 반복 금지 Trait는
    제외하며, 동률이면 trait_id 알파벳 순으로 결정론적으로 고른다."""

    candidates = [
        trait_id
        for trait_id in sorted(all_trait_ids)
        if not _violates_repetition_rule(trait_id, recent_target_trait_ids)
    ]
    if not candidates:
        # 모든 후보가 반복 금지에 걸리는 극단적 상황 — 그래도 진행은 해야 하므로 규칙을 푼다.
        candidates = sorted(all_trait_ids)

    def sort_key(trait_id: str) -> tuple[bool, str]:
        summary = trait_summaries.get(trait_id)
        needs_cross_context = _needs_cross_context_confirmation(summary) if summary else True
        return (not needs_cross_context, trait_id)  # False(=필요함)가 앞으로 오도록 not 사용

    candidates.sort(key=sort_key)
    return candidates[0]


def _select_gap_filling_candidate(
    all_trait_ids: set[str],
    trait_summaries: dict[str, TraitEvidenceSummary],
    unresolved_conflict_trait_ids: set[str],
) -> tuple[str, str]:
    """§8 위치 5-6 우선순위 1·2단계: Conflict가 남은 Trait 우선, 그다음 Evidence가 부족한 핵심
    Trait. 반환값은 (trait_id, purpose 설명)."""

    conflict_candidates = sorted(unresolved_conflict_trait_ids & all_trait_ids)
    if conflict_candidates:
        return conflict_candidates[0], "해결되지 않은 Explicit Conflict 보완"

    def is_evidence_gap(trait_id: str) -> bool:
        summary = trait_summaries.get(trait_id)
        if summary is None:
            return True  # 아예 관찰 이력이 없으면 명백한 Gap
        return summary.opportunity_count == 0 or summary.support_count < 2

    gap_traits = sorted(t for t in all_trait_ids if is_evidence_gap(t))
    if gap_traits:
        return gap_traits[0], "Evidence가 부족한 핵심 Trait 보완"

    # Gap도 없으면(모두 충분히 관찰됨) 그래도 질문은 나가야 하므로 임의로 첫 Trait를 쓴다.
    return sorted(all_trait_ids)[0], "추가 확인(특정 Gap 없음)"


def decide_next_target(
    *,
    context_id: str,
    position: int,
    all_trait_ids: set[str],
    trait_summaries: dict[str, TraitEvidenceSummary],
    unresolved_conflict_trait_ids: set[str],
    recent_target_trait_ids: list[str],
    used_frame_ids_in_context: set[str],
    is_first_context_in_session: bool,
) -> PlannerDecision:
    """position은 1-based 꼬리질문 순번(1~6)이다. Seed Question은 이 함수를 거치지 않는다.

    §5-1/§7-2: 세션에서 처리 순서상 가장 먼저 오는 Context는 비교할 다른 Context Evidence가
    없으므로, 꼬리질문 3번(교차확인 테마)을 관심 심화(DEEPEN)로 대체한다.
    """

    theme = position_to_theme(position)

    if theme is None:
        # 위치 5~6: 테마가 없다. Conflict → Coverage Gap 순서로 목표 Trait를 정한다.
        trait_id, purpose = _select_gap_filling_candidate(
            all_trait_ids, trait_summaries, unresolved_conflict_trait_ids
        )
        frame_id = frame_for_theme(PositionTheme.BEHAVIOR, used_frame_ids_in_context)
        return PlannerDecision(
            target_traits=[trait_id],
            question_frame=frame_id,
            context=context_id,
            purpose=purpose,
        )

    if theme is PositionTheme.CROSS_CONTEXT and is_first_context_in_session:
        theme = PositionTheme.DEEPEN  # §7-2 예외

    trait_id = _select_theme_candidate(
        theme, all_trait_ids, trait_summaries, recent_target_trait_ids
    )
    frame_id = frame_for_theme(theme, used_frame_ids_in_context)

    purpose_by_theme = {
        PositionTheme.DEEPEN: "관심 지점 심화 확인",
        PositionTheme.BEHAVIOR: "실제 행동·문제 해결 방식 확인",
        PositionTheme.CROSS_CONTEXT: "다른 Context Evidence와 교차 확인",
        PositionTheme.ALTERNATIVE: "반대·대안 상황에서의 선택 확인",
    }

    return PlannerDecision(
        target_traits=[trait_id],
        question_frame=frame_id,
        context=context_id,
        purpose=purpose_by_theme[theme],
    )
