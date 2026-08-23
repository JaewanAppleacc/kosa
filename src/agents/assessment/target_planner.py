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
  명시한 값이라 구현하지 않았다.

2026-08-21 리뷰 반영:
- §8: "꼬리질문 1~4 → 해당 위치의 테마와 호환되는 Trait만 후보로 삼는다"를 구현하지 않고
  있었다 — DEEPEN 테마(위치 1, 또는 첫 Context의 위치 3 대체)는 이제 Seed에서 선택된
  Trait이 속한 Option Blueprint(§9) 안의 형제 Trait로만 후보를 제한한다. §8이 명시적으로
  금지하는 "선택 Trait 그대로 강제 반복"은 아니다 — 같은 Blueprint 안에서도 반복 금지·
  교차확인 우선순위는 그대로 적용된다. (BEHAVIOR/CROSS_CONTEXT/ALTERNATIVE 테마의 후보
  제한은 설계상 근거가 더 필요해 이번엔 다루지 않는다.)
- 동률 tie-break를 trait_id 알파벳 순 대신 "이번 세션에서 이 Trait를 이미 목표로 삼은
  횟수가 적은 순"으로 바꿨다 — 알파벳이 빠른 Trait(audience_response_prediction 등)가
  구조적으로 계속 이기는 편향을 줄인다. 그래도 완전히 동률이면 trait_id로 결정론적 마무리.
- 위치 5~6 Gap 보완에도 반복 금지 규칙을 적용한다(이전에는 빠져 있었다).
- 출력에 §8 원본 JSON 예시에 있던 `option_blueprint_id`를 추가한다 — Question Generator가
  target_trait만으로 Blueprint를 다시 찾을 때 생기는 모호함(같은 Trait가 여러 Blueprint에
  걸쳐 있을 수 있음)을 없앤다.
"""

from __future__ import annotations

from pydantic import BaseModel

from src.data.question_frames.frame_role_map import PositionTheme, frame_for_theme, position_to_theme
from src.data.questions.tail_option_blueprints import blueprint_for_target_trait
from src.schemas.evidence import TraitEvidenceSummary


class PlannerDecision(BaseModel):
    target_traits: list[str]
    question_frame: str
    context: str
    purpose: str
    option_blueprint_id: str
    # 2026-08-22 §12-1 확장: 값이 있으면 이 결정은 특정 Trait가 아니라 Explicit Conflict
    # 확인 질문(고정 문항)을 가리킨다 — 하위 호환 Optional, 기존 호출자는 신경 쓸 필요 없다.
    contrast_resolution_id: str | None = None


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
    restricted_candidate_pool: set[str] | None = None,
) -> str:
    """§8 우선순위 ①②③: 후보 중 교차확인이 필요한 Trait를 우선하고, 반복 금지 Trait는
    제외한다. 동률이면 이번 세션에서 덜 목표로 삼힌 Trait를 우선하고, 그래도 동률이면
    trait_id 알파벳 순으로 결정론적으로 고른다(순수 알파벳 tie-break는 특정 Trait가
    구조적으로 계속 이기는 편향이 있었다 — 2026-08-21 리뷰).

    `restricted_candidate_pool`이 주어지면 그 안에서만 고른다(§8: "해당 위치의 테마와
    호환되는 Trait만 후보로 삼는다") — 비어 있으면 안전하게 전체 풀로 되돌아간다.
    """

    pool = all_trait_ids if restricted_candidate_pool is None else (restricted_candidate_pool & all_trait_ids)
    if not pool:
        pool = all_trait_ids

    candidates = [
        trait_id
        for trait_id in sorted(pool)
        if not _violates_repetition_rule(trait_id, recent_target_trait_ids)
    ]
    if not candidates:
        # 모든 후보가 반복 금지에 걸리는 극단적 상황 — 그래도 진행은 해야 하므로 규칙을 푼다.
        candidates = sorted(pool)

    def sort_key(trait_id: str) -> tuple[bool, int, str]:
        summary = trait_summaries.get(trait_id)
        needs_cross_context = _needs_cross_context_confirmation(summary) if summary else True
        times_targeted = recent_target_trait_ids.count(trait_id)
        return (not needs_cross_context, times_targeted, trait_id)  # False(=필요함)가 앞으로

    candidates.sort(key=sort_key)
    return candidates[0]


def _select_gap_filling_candidate(
    all_trait_ids: set[str],
    trait_summaries: dict[str, TraitEvidenceSummary],
    unresolved_conflict_trait_ids: set[str],
    recent_target_trait_ids: list[str],
) -> tuple[str, str]:
    """§8 위치 5-6 우선순위 1·2단계: Conflict가 남은 Trait 우선, 그다음 Evidence가 부족한 핵심
    Trait. 반환값은 (trait_id, purpose 설명). 자기확증 방지(연속 3회 금지)는 이 구간에도
    적용한다(2026-08-21 리뷰 — 이전에는 빠져 있었다)."""

    non_repeating = {
        trait_id
        for trait_id in all_trait_ids
        if not _violates_repetition_rule(trait_id, recent_target_trait_ids)
    }
    pool = non_repeating or all_trait_ids  # 전부 반복 금지에 걸리면 규칙을 풀어서라도 진행

    conflict_candidates = sorted(unresolved_conflict_trait_ids & pool)
    if conflict_candidates:
        return conflict_candidates[0], "해결되지 않은 Explicit Conflict 보완"

    def is_evidence_gap(trait_id: str) -> bool:
        summary = trait_summaries.get(trait_id)
        if summary is None:
            return True  # 아예 관찰 이력이 없으면 명백한 Gap
        return summary.opportunity_count == 0 or summary.support_count < 2

    gap_traits = sorted(t for t in pool if is_evidence_gap(t))
    if gap_traits:
        return gap_traits[0], "Evidence가 부족한 핵심 Trait 보완"

    # Gap도 없으면(모두 충분히 관찰됨) 그래도 질문은 나가야 하므로 임의로 첫 Trait를 쓴다.
    return sorted(pool)[0], "추가 확인(특정 Gap 없음)"


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
    deepen_anchor_trait_id: str | None = None,
    contrast_ids_needing_resolution_question: set[str] | None = None,
) -> PlannerDecision:
    """position은 1-based 꼬리질문 순번(1~6)이다. Seed Question은 이 함수를 거치지 않는다.

    §5-1/§7-2: 세션에서 처리 순서상 가장 먼저 오는 Context는 비교할 다른 Context Evidence가
    없으므로, 꼬리질문 3번(교차확인 테마)을 관심 심화(DEEPEN)로 대체한다.

    `deepen_anchor_trait_id`는 이 Context의 Seed에서 학생이 실제로 선택한 Trait이다.
    DEEPEN 테마(위치 1, 또는 첫 Context의 위치 3 대체)에서는 이 Trait이 속한 Option
    Blueprint 안의 형제 Trait로만 후보를 제한한다 — §7-2 "Seed 답변의 관심 지점 심화"를
    Blueprint 단위로 구현한다. 완전히 같은 Trait를 강제하지는 않는다(§8 자기확증 방지).

    2026-08-22 §12-1 확장: `contrast_ids_needing_resolution_question`이 있으면 위치·테마와
    무관하게 최우선으로 Explicit Conflict 확인 질문을 낸다 — Mask된 Trait를 최대한 빨리
    풀어야 나머지 질문 예산을 낭비하지 않는다. 여러 개면 contrast_id 알파벳 순으로
    결정론적으로 하나씩 처리한다.
    """

    contrast_ids_needing_resolution_question = contrast_ids_needing_resolution_question or set()
    if contrast_ids_needing_resolution_question:
        contrast_id = sorted(contrast_ids_needing_resolution_question)[0]
        frame_id = frame_for_theme(PositionTheme.BEHAVIOR, used_frame_ids_in_context)
        return PlannerDecision(
            target_traits=[],
            question_frame=frame_id,
            context=context_id,
            purpose="Explicit Conflict 확인 질문",
            option_blueprint_id="",
            contrast_resolution_id=contrast_id,
        )

    theme = position_to_theme(position)

    if theme is None:
        # 위치 5~6: 테마가 없다. Conflict → Coverage Gap 순서로 목표 Trait를 정한다.
        trait_id, purpose = _select_gap_filling_candidate(
            all_trait_ids, trait_summaries, unresolved_conflict_trait_ids, recent_target_trait_ids
        )
        frame_id = frame_for_theme(PositionTheme.BEHAVIOR, used_frame_ids_in_context)
        return PlannerDecision(
            target_traits=[trait_id],
            question_frame=frame_id,
            context=context_id,
            purpose=purpose,
            option_blueprint_id=blueprint_for_target_trait(trait_id).blueprint_id,
        )

    if theme is PositionTheme.CROSS_CONTEXT and is_first_context_in_session:
        theme = PositionTheme.DEEPEN  # §7-2 예외

    restricted_pool: set[str] | None = None
    anchor_blueprint = None
    if theme is PositionTheme.DEEPEN and deepen_anchor_trait_id is not None:
        try:
            anchor_blueprint = blueprint_for_target_trait(deepen_anchor_trait_id)
        except KeyError:
            anchor_blueprint = None
        if anchor_blueprint is not None:
            restricted_pool = {
                trait_id for role in anchor_blueprint.roles for trait_id in role.primary_trait_delta
            }

    trait_id = _select_theme_candidate(
        theme, all_trait_ids, trait_summaries, recent_target_trait_ids, restricted_pool
    )
    frame_id = frame_for_theme(theme, used_frame_ids_in_context)

    # anchor_blueprint를 썼다면 그 Blueprint를 그대로 쓴다 — trait_id가 다른 Blueprint에도
    # 걸쳐 있어서 blueprint_for_target_trait(trait_id)가 다른 Blueprint를 돌려주면
    # anchor_blueprint로 제한한 의미가 없어지기 때문이다.
    resolved_blueprint = (
        anchor_blueprint if anchor_blueprint is not None else blueprint_for_target_trait(trait_id)
    )

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
        option_blueprint_id=resolved_blueprint.blueprint_id,
    )
