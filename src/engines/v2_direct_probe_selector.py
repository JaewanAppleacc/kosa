"""V2 Direct Probe 후보 선택 — 2026-08-23 Trait Ontology v2(2단계 §11, 2.1단계 §2/§4/§5,
2.2단계 §1/§2).

LangGraph Node가 아니라 순수 함수다(CLAUDE.md: "계산 함수는 가능한 한 순수 함수로 만들고
LLM·DB·네트워크 호출과 분리한다"). LLM은 다음 Trait·Context·Blueprint를 선택하지 않는다
— 여기서 전부 결정론적으로 정해진다.

2.1단계 §1 버그 수정: 2단계의 `_tier()`는 RELATED Evidence가 0개인 Hypothesis 기반
Trait도 "우선순위 3"(탐색과 같은 급)으로 취급해 사실상 항상 후보에 남게 했다 — 실제로는
탐색 Trait(creative_ideation/independent_judgment) 2개만 "Evidence 없이도 후보"이고,
나머지 5개(systems_thinking/detail_orientation/persistence_completion/
uncertainty_tolerance/opinion_expression)는 RELATED Evidence가 최소 1개 있어야만
후보 "자격"이 있다. 이번 버전은 "자격이 있는가"(`_is_eligible`)와 "그중 어떤 순서로
물을 것인가"(`_sort_key`)를 완전히 분리한다.

2.2단계 §1/§2 버그 수정: 탐색 Trait 둘 다 RELATED Evidence가 보통 0개라 기존 정렬 기준
(2~5번, 전부 RELATED 기반)이 항상 0으로 동률이 나서 최종적으로 trait_id 오름차순
(`creative_ideation` < `independent_judgment`)으로만 갈렸다 — 실사용 세션에서
`independent_judgment`가 사실상 선택될 수 없었다. 탐색 Trait끼리는 이제 학생이 실제로
선택한 관심 Context(`EXPLORATION_CONTEXT_AFFINITY`)를 기준으로 정렬한다(무작위·Hash·
LLM 위임 없이 결정론적으로)."""

from __future__ import annotations

from src.data.questions.trait_v2_direct_probe_blueprints import (
    V2_DIRECT_PROBE_BLUEPRINTS_BY_TRAIT,
    V2_DIRECT_PROBE_TARGET_TRAIT_IDS,
)
from src.schemas.trait_vector_snapshot import TraitVectorEntry
from src.schemas.v2_direct_probe import V2DirectProbeBlueprint

# §2: RELATED Evidence가 있어야만 후보가 되는 Trait(Hypothesis 기반) — 2단계 §5에서
# Blueprint를 만든 7개 중 탐색 Trait 2개를 뺀 나머지.
HYPOTHESIS_BASED_TRAIT_IDS: frozenset[str] = frozenset(V2_DIRECT_PROBE_TARGET_TRAIT_IDS) - frozenset(
    {"creative_ideation", "independent_judgment"}
)
# §2: RELATED Evidence 없이도 후보가 될 수 있는 탐색 Trait. 한 학생에게 최대 1개만 제시한다.
EXPLORATION_TRAIT_IDS: frozenset[str] = frozenset({"creative_ideation", "independent_judgment"})

# 2.2단계 §2: 탐색 Trait가 어떤 Context와 자연스럽게 연결되는지 나타내는 고정 표
# (점수가 클수록 그 Trait와 더 강하게 연결된다는 뜻 — Evidence나 학생 답변에서 유도한
# 값이 아니라 사람이 미리 정의한 우선순위다). media는 콘텐츠를 스스로 새로 기획하는
# 행동(creative_ideation)과, school_life는 지시가 모호할 때 스스로 기준을 정하는 행동
# (independent_judgment)과 가장 자연스럽게 엮인다고 보고, game은 둘 다에 약하게
# 연결된다(두 Trait의 game Blueprint가 모두 존재하므로).
EXPLORATION_CONTEXT_AFFINITY: dict[str, dict[str, int]] = {
    "creative_ideation": {"media": 2, "game": 1},
    "independent_judgment": {"school_life": 2, "game": 1},
}

_ALREADY_SUFFICIENT_STATUSES = frozenset({"MODERATE", "STRONG"})


def _exploration_best_preferred_context(
    trait_id: str, preferred_context_ids: list[str]
) -> tuple[str, int] | None:
    """이 탐색 Trait의 Affinity Context 중 학생의 Preferred Context와 겹치는 것 중
    Affinity가 가장 높은 (context_id, affinity_score)를 고른다. 여러 개가 동점이면
    Preferred Context 목록에서 더 앞선(학생이 먼저 고른) Context를 택한다. 전혀 안
    겹치면 None(이 Trait는 학생의 관심 Context와 직접 연결되지 않는다는 뜻)."""

    affinity_map = EXPLORATION_CONTEXT_AFFINITY.get(trait_id, {})
    candidates = [(ctx, score) for ctx, score in affinity_map.items() if ctx in preferred_context_ids]
    if not candidates:
        return None
    max_score = max(score for _, score in candidates)
    best = [ctx for ctx, score in candidates if score == max_score]
    best.sort(key=lambda ctx: preferred_context_ids.index(ctx))
    return best[0], max_score


def _exploration_sort_key(
    trait_id: str,
    *,
    preferred_context_ids: list[str],
    interest_ratings: dict[str, int],
    used_v2_probe_frame_ids: set[str],
) -> tuple:
    """2.2단계 §2 — 탐색 Trait 둘 사이의 우선순위. 순서대로:

    1. Preferred Context와 직접 연결되는가(연결되는 쪽이 먼저)
    2. 그 Context의 interest_rating(높을수록 먼저)
    3. Context Affinity 점수(높을수록 먼저)
    4. Preferred Context에서 먼저 선택한 순서(앞설수록 먼저)
    5. 아직 사용하지 않은 Frame이 있는가(있는 쪽이 먼저)
    6. trait_id 오름차순(최종 결정론적 Tie-break)

    무작위·session_id Hash·LLM 위임을 쓰지 않는다 — 전부 이미 알려진 값만으로 계산한다."""

    linked = _exploration_best_preferred_context(trait_id, preferred_context_ids)
    has_no_preferred_link = linked is None
    if linked is not None:
        context_id, affinity_score = linked
        interest_rating = interest_ratings.get(context_id, 0)
        preferred_order_index = preferred_context_ids.index(context_id)
    else:
        interest_rating = 0
        affinity_score = 0
        preferred_order_index = len(preferred_context_ids)

    frame_ids_for_trait = {
        bp.question_frame_id for bp in V2_DIRECT_PROBE_BLUEPRINTS_BY_TRAIT.get(trait_id, [])
    }
    all_frames_used = bool(frame_ids_for_trait) and frame_ids_for_trait <= used_v2_probe_frame_ids

    return (
        has_no_preferred_link, -interest_rating, -affinity_score,
        preferred_order_index, all_frames_used, trait_id,
    )


def _is_eligible(
    trait_id: str,
    entry: TraitVectorEntry | None,
    *,
    already_probed_trait_ids: set[str],
    final_contexts: list[str],
    used_v2_probe_frame_ids: set[str],
) -> bool:
    """§2 후보 자격 조건. Tier·정렬과 완전히 분리된 별도 단계 — 여기서 걸러진 Trait는
    정렬 순서와 무관하게 아예 후보 목록에 들어가지 않는다."""

    if trait_id in already_probed_trait_ids:
        return False  # 이미 이 Trait를 Target으로 Direct Probe했다(§2/§4 "재질문 금지").
    if entry is not None:
        if entry.status in _ALREADY_SUFFICIENT_STATUSES:
            return False  # 이미 MODERATE/STRONG — "충분히 확인됨".
        if entry.status == "CONFLICTING":
            return False
    if trait_id in HYPOTHESIS_BASED_TRAIT_IDS:
        if entry is None or entry.related_evidence_count < 1:
            return False  # RELATED Evidence 0개 — Tier로 보내지 않고 여기서 완전히 제외.
    elif trait_id in EXPLORATION_TRAIT_IDS:
        # §2: "한 학생에게 Exploration Trait는 최대 1개만 제시하세요"는 세션 전체에 걸친
        # 제약이다 — 후보 목록은 답변마다 새로 계산되므로(already_probed_trait_ids만
        # 커진다), 이미 probe한 탐색 Trait가 있으면 "아직 안 물어본 다른 탐색 Trait"가
        # 다음 라운드에 슬쩍 다시 후보로 살아나지 않게 여기서 명시적으로 막는다.
        if EXPLORATION_TRAIT_IDS & already_probed_trait_ids:
            return False
    else:
        return False  # Direct Probe Blueprint가 아예 없는 Trait.

    if select_blueprint_for_trait(
        trait_id, related_context_ids=set(), preferred_context_ids=[],
        final_contexts=final_contexts, used_v2_probe_frame_ids=used_v2_probe_frame_ids,
    ) is None:
        return False  # 학생의 최종 Context 안에서 쓸 수 있는 Blueprint가 없다.
    return True


def _tier(trait_id: str) -> int:
    """자격을 이미 통과한 Trait만 여기 들어온다 — Tier는 이제 "Hypothesis 기반(1) vs
    탐색(2)" 두 단계뿐이다(2단계의 "RELATED 2회 이상 vs 1회" 세분화는 폐기 — §4가 그
    구분을 정렬 기준 2번(related_question_count)으로 대체했다)."""

    return 1 if trait_id in HYPOTHESIS_BASED_TRAIT_IDS else 2


def select_v2_probe_candidates(
    v2_snapshot: dict[str, TraitVectorEntry],
    already_probed_trait_ids: set[str],
    *,
    final_contexts: list[str] | None = None,
    used_v2_probe_frame_ids: set[str] | None = None,
    preferred_context_ids: list[str] | None = None,
    interest_ratings: dict[str, int] | None = None,
) -> list[str]:
    """§2/§4 — 자격이 있는 Trait만 후보로 남기고, 아래 순서로 정렬한다:

    1. Tier(Hypothesis 기반 1, 탐색 2)
    2-6. Tier 내부 정렬:
       - Hypothesis 기반: 서로 다른 RELATED question_id 수(내림차순) → RELATED Context
         다양성(내림차순) → RELATED Frame 다양성(내림차순) → RELATED Signal 합(내림차순)
         → trait_id(오름차순).
       - 탐색(2.2단계 §2): `_exploration_sort_key()` — Preferred Context 연결 여부 →
         interest_rating → Context Affinity → Preferred 순서 → 미사용 Frame → trait_id.

    `final_contexts`/`used_v2_probe_frame_ids`/`preferred_context_ids`/`interest_ratings`를
    생략하면(과거 호출 호환) 각각 안전한 기본값으로 대체한다 — 실제 서빙 경로(main.py)는
    항상 전부 넘긴다."""

    final_contexts = final_contexts if final_contexts is not None else ["game", "media", "school_life"]
    used_v2_probe_frame_ids = used_v2_probe_frame_ids if used_v2_probe_frame_ids is not None else set()
    preferred_context_ids = preferred_context_ids if preferred_context_ids is not None else []
    interest_ratings = interest_ratings if interest_ratings is not None else {}

    candidates = [
        trait_id for trait_id in V2_DIRECT_PROBE_TARGET_TRAIT_IDS
        if _is_eligible(
            trait_id, v2_snapshot.get(trait_id),
            already_probed_trait_ids=already_probed_trait_ids,
            final_contexts=final_contexts, used_v2_probe_frame_ids=used_v2_probe_frame_ids,
        )
    ]

    def sort_key(trait_id: str) -> tuple:
        if trait_id in EXPLORATION_TRAIT_IDS:
            return (
                _tier(trait_id),
                *_exploration_sort_key(
                    trait_id, preferred_context_ids=preferred_context_ids,
                    interest_ratings=interest_ratings, used_v2_probe_frame_ids=used_v2_probe_frame_ids,
                ),
            )
        entry = v2_snapshot.get(trait_id)
        related_question_count = entry.related_question_count if entry else 0
        related_context_count = entry.related_context_count if entry else 0
        related_frame_count = entry.related_frame_count if entry else 0
        related_signal_sum = entry.related_signal_sum if entry else 0.0
        return (
            _tier(trait_id), -related_question_count, -related_context_count,
            -related_frame_count, -related_signal_sum, trait_id,
        )

    candidates.sort(key=sort_key)

    # §2: 탐색 Trait는 최대 1개만 최종 목록에 남긴다.
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
    trait_id: str,
    *,
    related_context_ids: set[str],
    preferred_context_ids: list[str],
    final_contexts: list[str],
    used_v2_probe_frame_ids: set[str],
    candidate_pool: list[V2DirectProbeBlueprint] | None = None,
) -> V2DirectProbeBlueprint | None:
    """§5 — 다음 우선순위로 Blueprint를 고른다:

    1. 이 Trait의 RELATED Evidence가 실제 관찰된 Context
    2. 학생이 선택한 Preferred Context
    3. 학생의 Final Context(이미 Blueprint 후보 필터링 단계에서 보장됨)
    4. 아직 사용하지 않은 Frame
    5. blueprint_id 오름차순

    맞는 Blueprint가 없으면 None(호출자가 다음 후보 Trait로 넘어간다).

    2026-08-23 Trait Ontology v2(2.8단계) §7: `candidate_pool`이 주어지면 전역
    `V2_DIRECT_PROBE_BLUEPRINTS_BY_TRAIT`(Legacy 3-Context) 대신 그 목록에서만
    고른다 — ContextPack Runtime이 신규 Context 하나의 Direct Probe 후보만 넘길 때
    쓴다. 기본값 None이면 기존 동작과 100% 동일하다(하위 호환)."""

    source = candidate_pool if candidate_pool is not None else V2_DIRECT_PROBE_BLUEPRINTS_BY_TRAIT.get(trait_id, [])
    candidates = [
        bp for bp in source
        if bp.trait_id == trait_id and set(bp.allowed_context_ids) & set(final_contexts)
    ]
    if not candidates:
        return None

    def sort_key(bp: V2DirectProbeBlueprint) -> tuple:
        matched_context = next(c for c in bp.allowed_context_ids if c in final_contexts)
        no_related_evidence_here = matched_context not in related_context_ids
        not_preferred = matched_context not in preferred_context_ids
        frame_already_used = bp.question_frame_id in used_v2_probe_frame_ids
        return (no_related_evidence_here, not_preferred, frame_already_used, bp.blueprint_id)

    candidates.sort(key=sort_key)
    return candidates[0]
