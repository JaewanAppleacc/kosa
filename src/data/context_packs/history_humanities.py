"""history_humanities(역사·인문학) Context Pack — 2026-08-23 Trait Ontology v2(2.7단계 2차 배치) §2.

context-pack-social 작업 배정(담당: volunteer/travel/writing/history_humanities) 초안이다.
검수 상태는 전부 TBD이며 `data/reviews/context_packs/history_humanities_review_status.json`
에서 사람이 직접 채운다(§1 "Claude가 Context 질문을 자동 APPROVE하지 않는다").

설계 원칙(작업 지시문 그대로):
- 역사 지식 퀴즈가 아니다 — 모든 질문이 "만약 ~라면"으로 시작해, 특정 인물·사건·연도를
  안다는 전제 없이 가상의 기록·인물·시대를 두고 어떻게 접근할지만 묻는다.
- 서로 다른 기록·인물 선택·시대적 배경·가치 충돌 상황을 다뤘다(5번째 Anchor로 "사건들의
  연결 살피기" — 원인-결과 사슬을 보는 상황을 추가해 Routing 5개를 채웠다).
- 정치 성향을 추론하지 않는다 — value_conflict Anchor는 "그 시대에는 왜 그랬는지"를
  이해하는 방식(causal_analysis/opinion_expression/independent_judgment)만 다루고,
  특정 이념·정당·시사 쟁점을 전혀 언급하지 않는다.
- "더 널리 알려진 쪽을 그대로 받아들인다", "가장 잘 알려진 인물을 고른다"처럼 무난한
  기본 선택은 NO_SIGNAL로 두었다."""

from __future__ import annotations

from src.schemas.context_anchor_presentation import ContextAnchorPresentation
from src.schemas.context_pack import (
    ContextPack,
    ContextPackAnchorBackupQuestion,
    ContextPackSeedAnchorQuestion,
    OptionMappingRationale,
)
from src.schemas.context_routing import ContextRoutingBlueprint, ContextRoutingOptionMapping
from src.schemas.question import FinalizedOption, FinalizedQuestion

_CONTEXT_ID = "history_humanities"


def _rationales_for(question: FinalizedQuestion, source: str, texts: dict[str, str]) -> list[OptionMappingRationale]:
    rationales = []
    for option in question.options:
        trait_id = next(iter(option.primary_trait_delta), None)
        rationales.append(
            OptionMappingRationale(
                source=source, question_id=question.question_id, role_id=option.role_id,
                trait_id=trait_id, mapping_rationale_draft=texts[option.role_id],
            )
        )
    return rationales


# ============================== Routing ==============================

_ROUTING_ROWS = [
    ("hh_records", "같은 사건에 대해 서로 다른 기록을 마주하는 상황", "conflicting_records", "서로 다른 기록 마주하기"),
    ("hh_figure", "여러 인물 중 한 명을 골라 조명하는 상황", "figure_choice", "인물 선택"),
    ("hh_context", "사건의 시대적 배경을 이해하는 상황", "historical_context", "시대적 배경 이해"),
    ("hh_value", "과거와 지금의 가치관이 부딪히는 상황", "value_conflict", "가치 충돌"),
    ("hh_cause", "사건들이 서로 어떻게 영향을 주고받았는지 살피는 상황", "cause_effect_chain", "사건의 연결 살피기"),
]

_ROUTING_QUESTION_ID = "history_humanities_context_router_v1_base"
_ROUTING_BLUEPRINT = ContextRoutingBlueprint(
    context_id=_CONTEXT_ID,
    blueprint_id="history_humanities_context_router_v1",
    option_mappings=[
        ContextRoutingOptionMapping(role_id=role_id, context_anchor=anchor, anchor_label=label)
        for role_id, _text, anchor, label in _ROUTING_ROWS
    ],
    base_question=FinalizedQuestion(
        question_id=_ROUTING_QUESTION_ID, context=_CONTEXT_ID, target_traits=[], frame_id="context_routing",
        question_text="역사나 인문학적 주제를 탐구하는 상황을 상상해볼 때, 가장 관심이 가는 상황은 무엇인가요?",
        options=[
            FinalizedOption(
                option_id=f"{_ROUTING_QUESTION_ID}_o{i}", role_id=role_id, text=text, primary_trait_delta={},
            )
            for i, (role_id, text, _anchor, _label) in enumerate(_ROUTING_ROWS, start=1)
        ],
    ),
)

# ============================== Anchor Presentations ==============================

ANCHOR_PRESENTATIONS = [
    ContextAnchorPresentation(
        context_id=_CONTEXT_ID, anchor_id="conflicting_records", label="서로 다른 기록 마주하기",
        situation_terms=["서로 다른 기록", "자료 차이", "신뢰성"],
        preferred_scenarios=["같은 사건을 다르게 전하는 기록을 마주하는 상황"],
        forbidden_assumptions=["역사 지식", "특정 사건을 안다는 전제"],
    ),
    ContextAnchorPresentation(
        context_id=_CONTEXT_ID, anchor_id="figure_choice", label="인물 선택",
        situation_terms=["인물", "조명", "선택 기준"],
        preferred_scenarios=["여러 인물 중 한 명을 골라 더 알아보는 상황"],
        forbidden_assumptions=["역사 지식", "위인을 안다는 전제"],
    ),
    ContextAnchorPresentation(
        context_id=_CONTEXT_ID, anchor_id="historical_context", label="시대적 배경 이해",
        situation_terms=["시대적 배경", "맥락", "상황"],
        preferred_scenarios=["사건이 일어난 시대적 배경을 이해하려는 상황"],
        forbidden_assumptions=["역사 지식", "연도 암기"],
    ),
    ContextAnchorPresentation(
        context_id=_CONTEXT_ID, anchor_id="value_conflict", label="가치 충돌",
        situation_terms=["가치관 차이", "시대 변화", "판단 기준"],
        preferred_scenarios=["과거의 가치관과 지금의 가치관이 다르게 느껴지는 상황"],
        forbidden_assumptions=["정치 성향", "특정 이념"],
    ),
    ContextAnchorPresentation(
        context_id=_CONTEXT_ID, anchor_id="cause_effect_chain", label="사건의 연결 살피기",
        situation_terms=["사건의 연결", "영향", "흐름"],
        preferred_scenarios=["여러 사건이 서로 어떻게 영향을 주고받았는지 살피는 상황"],
        forbidden_assumptions=["역사 지식", "연표 암기"],
    ),
]

# ============================== Seed Anchor Questions ==============================

_SEED_CONFLICTING_RECORDS = FinalizedQuestion(
    question_id="history_humanities_seed_conflicting_records_v1", context=_CONTEXT_ID, target_traits=[],
    frame_id="seed_anchor",
    question_text="같은 사건을 서로 다르게 전하는 두 기록을 마주하게 됐다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="history_humanities_seed_conflicting_records_v1_o1", role_id="compare_the_records",
            text="두 기록의 내용을 하나하나 비교해본다", primary_trait_delta={"information_comparison": 1}),
        FinalizedOption(option_id="history_humanities_seed_conflicting_records_v1_o2", role_id="trace_why_different",
            text="왜 다르게 기록됐는지 이유를 따져본다", primary_trait_delta={"causal_analysis": 1}),
        FinalizedOption(option_id="history_humanities_seed_conflicting_records_v1_o3", role_id="imagine_each_side",
            text="각 기록을 남긴 사람의 입장이 어땠을지 헤아려본다", primary_trait_delta={"emotional_interpretation": 1}),
        FinalizedOption(option_id="history_humanities_seed_conflicting_records_v1_o4", role_id="decide_on_my_own",
            text="다른 사람 의견과 상관없이 내가 더 타당하다고 본 쪽으로 판단한다", primary_trait_delta={"independent_judgment": 1}),
        FinalizedOption(option_id="history_humanities_seed_conflicting_records_v1_o5", role_id="accept_the_common_one",
            text="더 널리 알려진 쪽을 그대로 받아들인다", primary_trait_delta={}),
    ],
)
_SEED_CONFLICTING_RECORDS_RATIONALE = {
    "compare_the_records": "두 기록의 내용을 하나하나 비교하는 행동이 드러나 information_comparison 후보로 연결된다",
    "trace_why_different": "다르게 기록된 이유를 능동적으로 따져보는 행동이 드러나 causal_analysis 후보로 연결된다",
    "imagine_each_side": "각 기록을 남긴 사람의 입장을 헤아려보는 행동이 드러나 emotional_interpretation 후보로 연결된다",
    "decide_on_my_own": "다른 의견과 무관하게 스스로 판단하는 행동이 드러나 independent_judgment 후보로 연결된다",
    "accept_the_common_one": "더 널리 알려진 쪽을 그대로 받아들이는 것은 특정 성향의 직접 근거로 보기 어렵다",
}

_SEED_FIGURE_CHOICE = FinalizedQuestion(
    question_id="history_humanities_seed_figure_choice_v1", context=_CONTEXT_ID, target_traits=[],
    frame_id="seed_anchor",
    question_text="여러 인물 중 한 명을 골라 더 깊이 알아봐야 한다고 상상해보세요. 무엇을 기준으로 고르나요?",
    options=[
        FinalizedOption(option_id="history_humanities_seed_figure_choice_v1_o1", role_id="pick_most_relatable",
            text="지금의 나와 비슷한 고민을 했을 것 같은 인물을 고른다", primary_trait_delta={"emotional_interpretation": 1}),
        FinalizedOption(option_id="history_humanities_seed_figure_choice_v1_o2", role_id="pick_most_influential_structure",
            text="다른 사건들에 가장 크게 영향을 준 인물을 고른다", primary_trait_delta={"systems_thinking": 1}),
        FinalizedOption(option_id="history_humanities_seed_figure_choice_v1_o3", role_id="pick_personally_interesting",
            text="그냥 개인적으로 끌리는 인물을 고른다", primary_trait_delta={"personal_goal_priority": 1}),
        FinalizedOption(option_id="history_humanities_seed_figure_choice_v1_o4", role_id="compare_candidates",
            text="후보들을 하나하나 비교해서 정한다", primary_trait_delta={"information_comparison": 1}),
        FinalizedOption(option_id="history_humanities_seed_figure_choice_v1_o5", role_id="pick_the_famous_one",
            text="가장 잘 알려진 인물을 고른다", primary_trait_delta={}),
    ],
)
_SEED_FIGURE_CHOICE_RATIONALE = {
    "pick_most_relatable": "그 인물의 고민을 지금의 나에 견줘 헤아려보는 행동이 드러나 emotional_interpretation 후보로 연결된다",
    "pick_most_influential_structure": "다른 사건에 미친 영향을 구조로 살피는 행동이 드러나 systems_thinking 후보로 연결된다",
    "pick_personally_interesting": "공동 기준보다 개인적으로 끌리는 것을 우선하는 행동이 드러나 personal_goal_priority 후보로 연결된다",
    "compare_candidates": "후보들을 하나하나 비교하는 행동이 드러나 information_comparison 후보로 연결된다",
    "pick_the_famous_one": "가장 잘 알려진 쪽을 고르는 것은 특정 성향의 직접 근거로 보기 어렵다",
}

_SEED_HISTORICAL_CONTEXT = FinalizedQuestion(
    question_id="history_humanities_seed_historical_context_v1", context=_CONTEXT_ID, target_traits=[],
    frame_id="seed_anchor",
    question_text="어떤 사건이 왜 그 시점에 일어났는지 이해해야 한다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="history_humanities_seed_historical_context_v1_o1", role_id="look_at_surrounding_situation",
            text="그 시대의 다른 상황들과 어떻게 연결되는지 살펴본다", primary_trait_delta={"systems_thinking": 1}),
        FinalizedOption(option_id="history_humanities_seed_historical_context_v1_o2", role_id="trace_direct_cause",
            text="이 사건을 직접 일으킨 원인을 짚어본다", primary_trait_delta={"causal_analysis": 1}),
        FinalizedOption(option_id="history_humanities_seed_historical_context_v1_o3", role_id="find_similar_pattern",
            text="비슷한 상황이 다른 시대에도 있었는지 찾아본다", primary_trait_delta={"pattern_finding": 1}),
        FinalizedOption(option_id="history_humanities_seed_historical_context_v1_o4", role_id="imagine_people_then",
            text="그 시대 사람들은 어떤 마음이었을지 상상해본다", primary_trait_delta={"emotional_interpretation": 1}),
        FinalizedOption(option_id="history_humanities_seed_historical_context_v1_o5", role_id="just_note_the_fact",
            text="일어난 사실만 확인하고 넘어간다", primary_trait_delta={}),
    ],
)
_SEED_HISTORICAL_CONTEXT_RATIONALE = {
    "look_at_surrounding_situation": "시대의 다른 상황들과 어떻게 연결되는지 구조로 살피는 행동이 드러나 systems_thinking 후보로 연결된다",
    "trace_direct_cause": "사건을 직접 일으킨 원인을 능동적으로 짚어보는 행동이 드러나 causal_analysis 후보로 연결된다",
    "find_similar_pattern": "비슷한 상황이 다른 시대에도 있었는지 스스로 찾는 행동이 드러나 pattern_finding 후보로 연결된다",
    "imagine_people_then": "그 시대 사람들의 마음을 상상해보는 행동이 드러나 emotional_interpretation 후보로 연결된다",
    "just_note_the_fact": "사실만 확인하고 넘어가는 것은 특정 성향의 직접 근거로 보기 어렵다",
}

_SEED_VALUE_CONFLICT = FinalizedQuestion(
    question_id="history_humanities_seed_value_conflict_v1", context=_CONTEXT_ID, target_traits=[],
    frame_id="seed_anchor",
    question_text="과거에는 당연하게 여겨졌지만 지금 기준으로는 다르게 보이는 가치관을 마주했다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="history_humanities_seed_value_conflict_v1_o1", role_id="understand_then_context",
            text="그 시대에는 왜 그게 당연했는지 배경을 이해해본다", primary_trait_delta={"causal_analysis": 1}),
        FinalizedOption(option_id="history_humanities_seed_value_conflict_v1_o2", role_id="state_my_view",
            text="지금 기준으로 내 생각을 분명하게 정리해본다", primary_trait_delta={"opinion_expression": 1}),
        FinalizedOption(option_id="history_humanities_seed_value_conflict_v1_o3", role_id="compare_then_and_now",
            text="그때와 지금 기준이 어떻게 다른지 비교해본다", primary_trait_delta={"information_comparison": 1}),
        FinalizedOption(option_id="history_humanities_seed_value_conflict_v1_o4", role_id="decide_independently",
            text="다른 사람들의 평가와 상관없이 내가 판단한 기준으로 본다", primary_trait_delta={"independent_judgment": 1}),
        FinalizedOption(option_id="history_humanities_seed_value_conflict_v1_o5", role_id="just_accept_it_was_different",
            text="그때는 그랬다고만 받아들이고 넘어간다", primary_trait_delta={}),
    ],
)
_SEED_VALUE_CONFLICT_RATIONALE = {
    "understand_then_context": "그 시대 가치관의 배경을 능동적으로 이해하려는 행동이 드러나 causal_analysis 후보로 연결된다",
    "state_my_view": "지금 기준의 생각을 분명하게 정리하는 행동이 드러나 opinion_expression 후보로 연결된다",
    "compare_then_and_now": "그때와 지금의 기준을 비교하는 행동이 드러나 information_comparison 후보로 연결된다",
    "decide_independently": "다른 평가와 무관하게 스스로 판단하는 행동이 드러나 independent_judgment 후보로 연결된다",
    "just_accept_it_was_different": "그랬다고만 받아들이고 넘어가는 것은 특정 성향의 직접 근거로 보기 어렵다",
}

_SEED_CAUSE_EFFECT_CHAIN = FinalizedQuestion(
    question_id="history_humanities_seed_cause_effect_chain_v1", context=_CONTEXT_ID, target_traits=[],
    frame_id="seed_anchor",
    question_text="여러 사건이 어떻게 서로 영향을 주고받았는지 살펴봐야 한다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="history_humanities_seed_cause_effect_chain_v1_o1", role_id="map_the_connections",
            text="사건들이 서로 어떻게 얽혀 있는지 전체 구조를 그려본다", primary_trait_delta={"systems_thinking": 1}),
        FinalizedOption(option_id="history_humanities_seed_cause_effect_chain_v1_o2", role_id="trace_one_chain",
            text="한 사건이 다음 사건에 미친 직접적인 영향을 짚어본다", primary_trait_delta={"causal_analysis": 1}),
        FinalizedOption(option_id="history_humanities_seed_cause_effect_chain_v1_o3", role_id="find_repeating_flow",
            text="비슷하게 반복되는 흐름이 있는지 찾아본다", primary_trait_delta={"pattern_finding": 1}),
        FinalizedOption(option_id="history_humanities_seed_cause_effect_chain_v1_o4", role_id="compare_different_accounts",
            text="사건마다 다른 설명들을 비교해본다", primary_trait_delta={"information_comparison": 1}),
        FinalizedOption(option_id="history_humanities_seed_cause_effect_chain_v1_o5", role_id="list_events_in_order",
            text="일어난 순서대로 나열만 해본다", primary_trait_delta={}),
    ],
)
_SEED_CAUSE_EFFECT_CHAIN_RATIONALE = {
    "map_the_connections": "사건들의 전체 구조를 그려보는 행동이 드러나 systems_thinking 후보로 연결된다",
    "trace_one_chain": "한 사건이 다음에 미친 직접적 영향을 능동적으로 짚어보는 행동이 드러나 causal_analysis 후보로 연결된다",
    "find_repeating_flow": "반복되는 흐름을 스스로 찾는 행동이 드러나 pattern_finding 후보로 연결된다",
    "compare_different_accounts": "사건마다 다른 설명을 비교하는 행동이 드러나 information_comparison 후보로 연결된다",
    "list_events_in_order": "순서대로 나열만 하는 것은 정리 행동일 뿐, 특정 성향의 직접 근거로 보기는 약하다",
}

SEED_ANCHOR_VARIANTS = [
    ContextPackSeedAnchorQuestion(anchor_id="conflicting_records", question=_SEED_CONFLICTING_RECORDS),
    ContextPackSeedAnchorQuestion(anchor_id="figure_choice", question=_SEED_FIGURE_CHOICE),
    ContextPackSeedAnchorQuestion(anchor_id="historical_context", question=_SEED_HISTORICAL_CONTEXT),
    ContextPackSeedAnchorQuestion(anchor_id="value_conflict", question=_SEED_VALUE_CONFLICT),
    ContextPackSeedAnchorQuestion(anchor_id="cause_effect_chain", question=_SEED_CAUSE_EFFECT_CHAIN),
]

# ============================== Anchor Backup Questions ==============================

_BACKUP_CONFLICTING_RECORDS = FinalizedQuestion(
    question_id="history_humanities_backup_conflicting_records_v1", context=_CONTEXT_ID, target_traits=[],
    frame_id="backup",
    question_text="믿을 만하다고 생각했던 기록에 오류가 있을 수도 있다는 이야기를 들었다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="history_humanities_backup_conflicting_records_v1_o1", role_id="check_other_sources",
            text="다른 자료를 찾아 다시 확인한다", primary_trait_delta={"information_comparison": 1}),
        FinalizedOption(option_id="history_humanities_backup_conflicting_records_v1_o2", role_id="question_why_error",
            text="어디서 오류가 생겼을지 원인을 따져본다", primary_trait_delta={"causal_analysis": 1}),
        FinalizedOption(option_id="history_humanities_backup_conflicting_records_v1_o3", role_id="keep_trusting_it",
            text="특별한 근거가 없다면 원래대로 신뢰한다", primary_trait_delta={"persistence_completion": 1}),
        FinalizedOption(option_id="history_humanities_backup_conflicting_records_v1_o4", role_id="decide_myself",
            text="내가 판단하기에 더 타당한 쪽으로 결론짓는다", primary_trait_delta={"independent_judgment": 1}),
        FinalizedOption(option_id="history_humanities_backup_conflicting_records_v1_o5", role_id="set_it_aside",
            text="판단을 보류하고 넘어간다", primary_trait_delta={}),
    ],
)
_BACKUP_CONFLICTING_RECORDS_RATIONALE = {
    "check_other_sources": "다른 자료를 찾아 다시 확인하는 행동이 드러나 information_comparison 후보로 연결된다",
    "question_why_error": "오류가 생긴 원인을 능동적으로 따져보는 행동이 드러나 causal_analysis 후보로 연결된다",
    "keep_trusting_it": "특별한 근거가 없으면 원래 신뢰를 그대로 유지하는 행동이 드러나 persistence_completion 후보로 연결된다",
    "decide_myself": "스스로 판단해 결론짓는 행동이 드러나 independent_judgment 후보로 연결된다",
    "set_it_aside": "판단을 보류하는 것은 특정 성향의 적극적 근거로 보기 어렵다",
}

_BACKUP_FIGURE_CHOICE = FinalizedQuestion(
    question_id="history_humanities_backup_figure_choice_v1", context=_CONTEXT_ID, target_traits=[],
    frame_id="backup",
    question_text="알아보던 인물에 대해 상반된 평가들이 있다는 걸 알게 됐다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="history_humanities_backup_figure_choice_v1_o1", role_id="compare_evaluations",
            text="상반된 평가들을 하나하나 비교해본다", primary_trait_delta={"information_comparison": 1}),
        FinalizedOption(option_id="history_humanities_backup_figure_choice_v1_o2", role_id="understand_their_situation",
            text="그 인물이 처했던 상황을 먼저 헤아려본다", primary_trait_delta={"emotional_interpretation": 1}),
        FinalizedOption(option_id="history_humanities_backup_figure_choice_v1_o3", role_id="trace_why_evaluations_differ",
            text="왜 평가가 이렇게 갈리는지 이유를 짚어본다", primary_trait_delta={"causal_analysis": 1}),
        FinalizedOption(option_id="history_humanities_backup_figure_choice_v1_o4", role_id="form_my_own_view",
            text="다른 평가와 상관없이 내가 판단한 대로 본다", primary_trait_delta={"independent_judgment": 1}),
        FinalizedOption(option_id="history_humanities_backup_figure_choice_v1_o5", role_id="follow_majority_view",
            text="더 많은 사람이 동의하는 평가를 따른다", primary_trait_delta={}),
    ],
)
_BACKUP_FIGURE_CHOICE_RATIONALE = {
    "compare_evaluations": "상반된 평가를 하나하나 비교하는 행동이 드러나 information_comparison 후보로 연결된다",
    "understand_their_situation": "인물이 처했던 상황을 먼저 헤아려보는 행동이 드러나 emotional_interpretation 후보로 연결된다",
    "trace_why_evaluations_differ": "평가가 갈리는 이유를 능동적으로 짚어보는 행동이 드러나 causal_analysis 후보로 연결된다",
    "form_my_own_view": "다른 평가와 무관하게 스스로 판단하는 행동이 드러나 independent_judgment 후보로 연결된다",
    "follow_majority_view": "더 많은 사람의 평가를 따르는 것은 특정 성향의 직접 근거로 보기 어렵다",
}

_BACKUP_HISTORICAL_CONTEXT = FinalizedQuestion(
    question_id="history_humanities_backup_historical_context_v1", context=_CONTEXT_ID, target_traits=[],
    frame_id="backup",
    question_text="설명을 들어도 그 시대 배경이 잘 와닿지 않는다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="history_humanities_backup_historical_context_v1_o1", role_id="connect_to_other_events",
            text="그 시기의 다른 사건들과 연결해서 다시 이해해본다", primary_trait_delta={"systems_thinking": 1}),
        FinalizedOption(option_id="history_humanities_backup_historical_context_v1_o2", role_id="compare_to_now",
            text="지금 상황과 비교해보며 이해해본다", primary_trait_delta={"information_comparison": 1}),
        FinalizedOption(option_id="history_humanities_backup_historical_context_v1_o3", role_id="imagine_being_there",
            text="그 시대에 있었다면 어땠을지 상상해본다", primary_trait_delta={"emotional_interpretation": 1}),
        FinalizedOption(option_id="history_humanities_backup_historical_context_v1_o4", role_id="keep_digging_alone",
            text="이해될 때까지 혼자 계속 파고든다", primary_trait_delta={"persistence_completion": 1}),
        FinalizedOption(option_id="history_humanities_backup_historical_context_v1_o5", role_id="leave_it_for_now",
            text="일단 이해가 안 되는 채로 넘어간다", primary_trait_delta={}),
    ],
)
_BACKUP_HISTORICAL_CONTEXT_RATIONALE = {
    "connect_to_other_events": "다른 사건들과 연결해 다시 이해하려는 행동이 드러나 systems_thinking 후보로 연결된다",
    "compare_to_now": "지금 상황과 비교해 이해하려는 행동이 드러나 information_comparison 후보로 연결된다",
    "imagine_being_there": "그 시대에 있었다면 어땠을지 상상해보는 행동이 드러나 emotional_interpretation 후보로 연결된다",
    "keep_digging_alone": "이해될 때까지 포기하지 않고 계속 파고드는 행동이 드러나 persistence_completion 후보로 연결된다",
    "leave_it_for_now": "이해 안 되는 채로 넘어가는 것은 특정 성향의 적극적 근거로 보기 어렵다",
}

_BACKUP_VALUE_CONFLICT = FinalizedQuestion(
    question_id="history_humanities_backup_value_conflict_v1", context=_CONTEXT_ID, target_traits=[],
    frame_id="backup",
    question_text="친구와 과거의 어떤 가치관을 두고 평가가 다르다는 걸 알게 됐다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="history_humanities_backup_value_conflict_v1_o1", role_id="explain_my_standard",
            text="내가 그렇게 판단한 기준을 설명한다", primary_trait_delta={"opinion_expression": 1}),
        FinalizedOption(option_id="history_humanities_backup_value_conflict_v1_o2", role_id="find_common_ground",
            text="서로 다른 기준 사이에서 공통점을 찾아본다", primary_trait_delta={"opinion_mediation": 1}),
        FinalizedOption(option_id="history_humanities_backup_value_conflict_v1_o3", role_id="understand_friend_view",
            text="친구는 왜 그렇게 평가하는지 먼저 들어본다", primary_trait_delta={"emotional_interpretation": 1}),
        FinalizedOption(option_id="history_humanities_backup_value_conflict_v1_o4", role_id="keep_my_evaluation",
            text="내가 판단한 평가를 그대로 유지한다", primary_trait_delta={"independent_judgment": 1}),
        FinalizedOption(option_id="history_humanities_backup_value_conflict_v1_o5", role_id="avoid_the_topic",
            text="의견 차이가 부담스러워 화제를 넘긴다", primary_trait_delta={}),
    ],
)
_BACKUP_VALUE_CONFLICT_RATIONALE = {
    "explain_my_standard": "자신이 판단한 기준을 설명하는 행동이 드러나 opinion_expression 후보로 연결된다",
    "find_common_ground": "서로 다른 기준 사이에서 공통점을 찾는 행동이 드러나 opinion_mediation 후보로 연결된다",
    "understand_friend_view": "친구의 평가 이유를 먼저 들어보는 행동이 드러나 emotional_interpretation 후보로 연결된다",
    "keep_my_evaluation": "다른 의견과 무관하게 스스로 판단을 유지하는 행동이 드러나 independent_judgment 후보로 연결된다",
    "avoid_the_topic": "화제를 넘기는 것은 회피에 가까워 특정 성향의 적극적 근거로 보기 어렵다",
}

_BACKUP_CAUSE_EFFECT_CHAIN = FinalizedQuestion(
    question_id="history_humanities_backup_cause_effect_chain_v1", context=_CONTEXT_ID, target_traits=[],
    frame_id="backup",
    question_text="사건들을 연결해 정리하다가 앞뒤가 안 맞는 부분을 발견했다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="history_humanities_backup_cause_effect_chain_v1_o1", role_id="recheck_each_link",
            text="연결 고리를 하나하나 다시 확인한다", primary_trait_delta={"detail_orientation": 1}),
        FinalizedOption(option_id="history_humanities_backup_cause_effect_chain_v1_o2", role_id="find_the_missing_cause",
            text="빠진 원인이 무엇인지 짚어본다", primary_trait_delta={"causal_analysis": 1}),
        FinalizedOption(option_id="history_humanities_backup_cause_effect_chain_v1_o3", role_id="redraw_the_structure",
            text="전체 구조를 다시 그려본다", primary_trait_delta={"systems_thinking": 1}),
        FinalizedOption(option_id="history_humanities_backup_cause_effect_chain_v1_o4", role_id="compare_other_explanations",
            text="다른 설명은 이 부분을 어떻게 다루는지 찾아본다", primary_trait_delta={"information_comparison": 1}),
        FinalizedOption(option_id="history_humanities_backup_cause_effect_chain_v1_o5", role_id="leave_the_gap",
            text="일단 그 부분은 비워두고 넘어간다", primary_trait_delta={}),
    ],
)
_BACKUP_CAUSE_EFFECT_CHAIN_RATIONALE = {
    "recheck_each_link": "연결 고리를 하나하나 다시 확인하는 행동이 드러나 detail_orientation 후보로 연결된다",
    "find_the_missing_cause": "빠진 원인을 능동적으로 짚어보는 행동이 드러나 causal_analysis 후보로 연결된다",
    "redraw_the_structure": "전체 구조를 다시 그려보는 행동이 드러나 systems_thinking 후보로 연결된다",
    "compare_other_explanations": "다른 설명을 찾아 비교하는 행동이 드러나 information_comparison 후보로 연결된다",
    "leave_the_gap": "비워두고 넘어가는 것은 특정 성향의 적극적 근거로 보기 어렵다",
}

ANCHOR_BACKUP_QUESTIONS = [
    ContextPackAnchorBackupQuestion(anchor_id="conflicting_records", question=_BACKUP_CONFLICTING_RECORDS),
    ContextPackAnchorBackupQuestion(anchor_id="figure_choice", question=_BACKUP_FIGURE_CHOICE),
    ContextPackAnchorBackupQuestion(anchor_id="historical_context", question=_BACKUP_HISTORICAL_CONTEXT),
    ContextPackAnchorBackupQuestion(anchor_id="value_conflict", question=_BACKUP_VALUE_CONFLICT),
    ContextPackAnchorBackupQuestion(anchor_id="cause_effect_chain", question=_BACKUP_CAUSE_EFFECT_CHAIN),
]

# ============================== Mapping Rationale ==============================

OPTION_MAPPING_RATIONALES = [
    *_rationales_for(_SEED_CONFLICTING_RECORDS, "seed_anchor", _SEED_CONFLICTING_RECORDS_RATIONALE),
    *_rationales_for(_SEED_FIGURE_CHOICE, "seed_anchor", _SEED_FIGURE_CHOICE_RATIONALE),
    *_rationales_for(_SEED_HISTORICAL_CONTEXT, "seed_anchor", _SEED_HISTORICAL_CONTEXT_RATIONALE),
    *_rationales_for(_SEED_VALUE_CONFLICT, "seed_anchor", _SEED_VALUE_CONFLICT_RATIONALE),
    *_rationales_for(_SEED_CAUSE_EFFECT_CHAIN, "seed_anchor", _SEED_CAUSE_EFFECT_CHAIN_RATIONALE),
    *_rationales_for(_BACKUP_CONFLICTING_RECORDS, "anchor_backup", _BACKUP_CONFLICTING_RECORDS_RATIONALE),
    *_rationales_for(_BACKUP_FIGURE_CHOICE, "anchor_backup", _BACKUP_FIGURE_CHOICE_RATIONALE),
    *_rationales_for(_BACKUP_HISTORICAL_CONTEXT, "anchor_backup", _BACKUP_HISTORICAL_CONTEXT_RATIONALE),
    *_rationales_for(_BACKUP_VALUE_CONFLICT, "anchor_backup", _BACKUP_VALUE_CONFLICT_RATIONALE),
    *_rationales_for(_BACKUP_CAUSE_EFFECT_CHAIN, "anchor_backup", _BACKUP_CAUSE_EFFECT_CHAIN_RATIONALE),
]

# ============================== Pack ==============================

CONTEXT_PACK = ContextPack(
    context_id=_CONTEXT_ID,
    routing_blueprint=_ROUTING_BLUEPRINT,
    anchor_presentations=ANCHOR_PRESENTATIONS,
    seed_anchor_variants=SEED_ANCHOR_VARIANTS,
    anchor_backup_questions=ANCHOR_BACKUP_QUESTIONS,
    option_mapping_rationales=OPTION_MAPPING_RATIONALES,
    direct_probe_candidates=[],
    forbidden_assumptions=[
        "특정 인물·사건·연도를 안다는 전제로 묻지 않는다",
        "역사 지식 퀴즈 형태로 만들지 않는다",
        "정치 성향이나 특정 이념을 추론하지 않는다",
    ],
    review_artifact_paths=["data/reviews/context_packs/history_humanities_review_status.json"],
    pack_version="v1.0",
)
