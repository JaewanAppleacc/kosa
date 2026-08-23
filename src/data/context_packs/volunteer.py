"""volunteer(봉사·사회참여) Context Pack — 2026-08-23 Trait Ontology v2(2.7단계 2차 배치) §2.

context-pack-social 작업 배정(담당: volunteer/travel/writing/history_humanities) 초안이다.
검수 상태는 전부 TBD이며 `data/reviews/context_packs/volunteer_review_status.json`에서
사람이 직접 채운다(§1 "Claude가 Context 질문을 자동 APPROVE하지 않는다").

설계 원칙(작업 지시문 그대로):
- 봉사를 좋아하면 이타적·협동적이라는 자동 연결을 하지 않는다 — "도움을 받는 사람이
  어떤 마음일지 헤아려본다"(emotional_interpretation), "왜 이런 어려움이 생겼는지
  파고든다"(causal_analysis)처럼 서로 다른 축의 행동으로 갈라 놓았다.
- 봉사 경험을 전제하지 않는다 — 모든 질문을 "~라고 상상해보세요"로 시작해 경험이 없는
  학생도 답할 수 있게 했다.
- 도움 방식·자원 배분·현장 변화·의견 차이 상황을 다뤘다(5번째 Anchor로 "어떤 문제에
  참여할지" 선택 상황을 추가했다 — Routing 5개 Anchor를 채우기 위한 자연스러운 확장).
- "물어본다", "고르게 나눠본다", "책임자 지시를 기다린다"처럼 사회적으로 무난하고
  바람직해 보이는 선택지는 의도적으로 NO_SIGNAL로 두어, 그 선택이 특정 Trait의 정답처럼
  보이지 않게 했다."""

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

_CONTEXT_ID = "volunteer"


def _rationales_for(question: FinalizedQuestion, source: str, texts: dict[str, str]) -> list[OptionMappingRationale]:
    """옵션의 실제 `primary_trait_delta`에서 trait_id를 그대로 파생시켜, 문구(texts)와
    trait_id가 어긋날 여지를 구조적으로 없앤다(예제 빌더의 `_rationales_for`와 동일 패턴)."""

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
    ("vr_method", "어떤 도움을 어떤 방식으로 줄지 정하는 상황", "help_method", "도움 방식 정하기"),
    ("vr_resource", "제한된 시간이나 물품을 여러 곳에 나눠야 하는 상황", "resource_allocation", "자원 배분"),
    ("vr_field", "현장에서 계획과 다르게 상황이 바뀌는 상황", "field_change", "현장 변화 대응"),
    ("vr_opinion", "함께 참여하는 사람들과 방법에 대한 생각이 다른 상황", "opinion_difference", "의견 차이 조율"),
    ("vr_cause", "여러 사회 문제 중 어디에 참여할지 정하는 상황", "cause_selection", "참여 대상 선택"),
]

_ROUTING_QUESTION_ID = "volunteer_context_router_v1_base"
_ROUTING_BLUEPRINT = ContextRoutingBlueprint(
    context_id=_CONTEXT_ID,
    blueprint_id="volunteer_context_router_v1",
    option_mappings=[
        ContextRoutingOptionMapping(role_id=role_id, context_anchor=anchor, anchor_label=label)
        for role_id, _text, anchor, label in _ROUTING_ROWS
    ],
    base_question=FinalizedQuestion(
        question_id=_ROUTING_QUESTION_ID, context=_CONTEXT_ID, target_traits=[], frame_id="context_routing",
        question_text="봉사나 사회 참여를 상상해볼 때, 가장 관심이 가는 상황은 무엇인가요?",
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
        context_id=_CONTEXT_ID, anchor_id="help_method", label="도움 방식 정하기",
        situation_terms=["도움 방식", "직접 행동", "정보 제공"],
        preferred_scenarios=[
            "어떤 방식으로 도울지 정하는 상황",
            "직접 나서는 것과 정보를 알려주는 것 사이에서 고르는 상황",
        ],
        forbidden_assumptions=["봉사 경험", "실제로 해 본 적"],
    ),
    ContextAnchorPresentation(
        context_id=_CONTEXT_ID, anchor_id="resource_allocation", label="자원 배분",
        situation_terms=["자원 배분", "우선순위", "제한된 시간"],
        preferred_scenarios=["한정된 물품이나 시간을 여러 대상에게 나누는 상황"],
        forbidden_assumptions=["봉사 경험", "동아리 가입"],
    ),
    ContextAnchorPresentation(
        context_id=_CONTEXT_ID, anchor_id="field_change", label="현장 변화 대응",
        situation_terms=["현장 변화", "예상과 다른 상황", "대응"],
        preferred_scenarios=["계획한 것과 다른 상황이 현장에서 생겼을 때"],
        forbidden_assumptions=["봉사 경험", "해외 봉사"],
    ),
    ContextAnchorPresentation(
        context_id=_CONTEXT_ID, anchor_id="opinion_difference", label="의견 차이 조율",
        situation_terms=["의견 차이", "조율", "방법 차이"],
        preferred_scenarios=["함께하는 사람들과 방법에 대해 생각이 다를 때"],
        forbidden_assumptions=["봉사 경험", "조별 과제"],
    ),
    ContextAnchorPresentation(
        context_id=_CONTEXT_ID, anchor_id="cause_selection", label="참여 대상 선택",
        situation_terms=["사회 문제", "참여 기준", "선택"],
        preferred_scenarios=["여러 사회 문제 중 어디에 힘을 쏟을지 고르는 상황"],
        forbidden_assumptions=["봉사 경험", "특정 정치 성향"],
    ),
]

# ============================== Seed Anchor Questions ==============================

_SEED_HELP_METHOD = FinalizedQuestion(
    question_id="volunteer_seed_help_method_v1", context=_CONTEXT_ID, target_traits=[], frame_id="seed_anchor",
    question_text="누군가를 도와야 하는 상황이 생겼다고 상상해보세요. 어떤 도움을 줄지 정할 때 가장 먼저 하는 생각은 무엇인가요?",
    options=[
        FinalizedOption(option_id="volunteer_seed_help_method_v1_o1", role_id="find_root_cause",
            text="왜 이런 어려움이 생겼는지 이유부터 파고들어본다", primary_trait_delta={"causal_analysis": 1}),
        FinalizedOption(option_id="volunteer_seed_help_method_v1_o2", role_id="act_now",
            text="일단 당장 할 수 있는 일부터 바로 나서서 해본다", primary_trait_delta={"immediate_execution": 1}),
        FinalizedOption(option_id="volunteer_seed_help_method_v1_o3", role_id="compare_other_ways",
            text="다른 사람들은 어떤 방식으로 도왔는지 찾아보고 비교한다", primary_trait_delta={"information_comparison": 1}),
        FinalizedOption(option_id="volunteer_seed_help_method_v1_o4", role_id="sense_their_feeling",
            text="도움을 받는 사람이 지금 어떤 마음일지 헤아려본다", primary_trait_delta={"emotional_interpretation": 1}),
        FinalizedOption(option_id="volunteer_seed_help_method_v1_o5", role_id="ask_what_needed",
            text="일단 무엇이 필요한지 물어본다", primary_trait_delta={}),
    ],
)
_SEED_HELP_METHOD_RATIONALE = {
    "find_root_cause": "어려움의 원인을 능동적으로 파고드는 행동이 드러나 causal_analysis 후보로 연결된다",
    "act_now": "생각보다 먼저 할 수 있는 일을 바로 시작하는 행동이 드러나 immediate_execution 후보로 연결된다",
    "compare_other_ways": "다른 사례를 찾아 비교하는 행동이 드러나 information_comparison 후보로 연결된다",
    "sense_their_feeling": "상대의 감정을 직접 헤아려보는 행동이 드러나 emotional_interpretation 후보로 연결된다",
    "ask_what_needed": "필요를 묻는 것은 도움을 주는 일반적인 절차일 뿐, 특정 성향의 직접 근거로 보기는 약하다",
}

_SEED_RESOURCE_ALLOCATION = FinalizedQuestion(
    question_id="volunteer_seed_resource_allocation_v1", context=_CONTEXT_ID, target_traits=[], frame_id="seed_anchor",
    question_text="한정된 시간이나 물품을 여러 곳에 나눠야 하는 상황이라고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="volunteer_seed_resource_allocation_v1_o1", role_id="set_priority_order",
            text="어디에 먼저 쓸지 기준을 세워 순서를 정한다", primary_trait_delta={"planning": 1}),
        FinalizedOption(option_id="volunteer_seed_resource_allocation_v1_o2", role_id="split_evenly",
            text="일단 최대한 고르게 나눠본다", primary_trait_delta={}),
        FinalizedOption(option_id="volunteer_seed_resource_allocation_v1_o3", role_id="research_similar_cases",
            text="비슷한 상황에서는 보통 어떻게 나눴는지 찾아본다", primary_trait_delta={"information_comparison": 1}),
        FinalizedOption(option_id="volunteer_seed_resource_allocation_v1_o4", role_id="ask_involved_people",
            text="이 상황과 관련된 사람들 의견을 모아 기준을 정한다", primary_trait_delta={"opinion_mediation": 1}),
        FinalizedOption(option_id="volunteer_seed_resource_allocation_v1_o5", role_id="decide_by_own_standard",
            text="내가 중요하다고 생각하는 곳에 더 많이 배정한다", primary_trait_delta={"personal_goal_priority": 1}),
    ],
)
_SEED_RESOURCE_ALLOCATION_RATIONALE = {
    "set_priority_order": "무엇을 먼저 쓸지 기준과 순서를 세우는 행동이 드러나 planning 후보로 연결된다",
    "split_evenly": "고르게 나누는 것은 배분의 기본값에 가까워 특정 성향의 직접 근거로 보기 어렵다",
    "research_similar_cases": "비슷한 사례를 찾아 참고하는 행동이 드러나 information_comparison 후보로 연결된다",
    "ask_involved_people": "관련된 사람들의 의견을 모아 기준을 세우는 행동이 드러나 opinion_mediation 후보로 연결된다",
    "decide_by_own_standard": "공동 기준보다 자신의 판단 기준을 우선해 배정하는 행동이 드러나 personal_goal_priority 후보로 연결된다",
}

_SEED_FIELD_CHANGE = FinalizedQuestion(
    question_id="volunteer_seed_field_change_v1", context=_CONTEXT_ID, target_traits=[], frame_id="seed_anchor",
    question_text="돕기로 계획한 것과 다르게 현장 상황이 갑자기 바뀌었다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="volunteer_seed_field_change_v1_o1", role_id="change_the_plan",
            text="바뀐 상황에 맞게 방법을 바꿔서 대응한다", primary_trait_delta={"change_adaptation": 1}),
        FinalizedOption(option_id="volunteer_seed_field_change_v1_o2", role_id="stick_to_plan",
            text="원래 계획대로 끝까지 진행한다", primary_trait_delta={"persistence_completion": 1}),
        FinalizedOption(option_id="volunteer_seed_field_change_v1_o3", role_id="figure_out_why",
            text="왜 이렇게 바뀌었는지부터 파악해본다", primary_trait_delta={"causal_analysis": 1}),
        FinalizedOption(option_id="volunteer_seed_field_change_v1_o4", role_id="find_similar_situation",
            text="이전에 비슷한 상황은 없었는지 떠올려본다", primary_trait_delta={"pattern_finding": 1}),
        FinalizedOption(option_id="volunteer_seed_field_change_v1_o5", role_id="wait_for_instruction",
            text="담당자가 정해줄 때까지 기다린다", primary_trait_delta={}),
    ],
)
_SEED_FIELD_CHANGE_RATIONALE = {
    "change_the_plan": "바뀐 상황에 맞춰 대응 방식을 바꾸는 행동이 드러나 change_adaptation 후보로 연결된다",
    "stick_to_plan": "예상 밖 상황에서도 원래 계획을 포기하지 않고 끝까지 가는 행동이 드러나 persistence_completion 후보로 연결된다",
    "figure_out_why": "상황이 바뀐 이유를 능동적으로 파악하는 행동이 드러나 causal_analysis 후보로 연결된다",
    "find_similar_situation": "이전 사례와 이어지는 흐름을 스스로 찾는 행동이 드러나 pattern_finding 후보로 연결된다",
    "wait_for_instruction": "담당자의 지시를 기다리는 것은 수동적 대응이라 특정 성향의 직접 근거로 보기 어렵다",
}

_SEED_OPINION_DIFFERENCE = FinalizedQuestion(
    question_id="volunteer_seed_opinion_difference_v1", context=_CONTEXT_ID, target_traits=[], frame_id="seed_anchor",
    question_text="함께 돕기로 한 사람들과 방법에 대한 생각이 다르다는 걸 알게 됐다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="volunteer_seed_opinion_difference_v1_o1", role_id="state_my_view",
            text="내 생각을 분명하게 말한다", primary_trait_delta={"opinion_expression": 1}),
        FinalizedOption(option_id="volunteer_seed_opinion_difference_v1_o2", role_id="find_common_ground",
            text="서로 받아들일 수 있는 지점을 찾아 조율한다", primary_trait_delta={"opinion_mediation": 1}),
        FinalizedOption(option_id="volunteer_seed_opinion_difference_v1_o3", role_id="understand_their_reason",
            text="다른 사람은 왜 그렇게 생각하는지 먼저 이해해본다", primary_trait_delta={"emotional_interpretation": 1}),
        FinalizedOption(option_id="volunteer_seed_opinion_difference_v1_o4", role_id="decide_on_my_own",
            text="다른 의견과 상관없이 내가 맞다고 생각하는 방식대로 진행한다", primary_trait_delta={"independent_judgment": 1}),
        FinalizedOption(option_id="volunteer_seed_opinion_difference_v1_o5", role_id="go_along",
            text="다른 사람 의견에 맞춘다", primary_trait_delta={}),
    ],
)
_SEED_OPINION_DIFFERENCE_RATIONALE = {
    "state_my_view": "내 생각을 분명히 드러내는 행동이 직접 드러나 opinion_expression 후보로 연결된다",
    "find_common_ground": "서로 받아들일 수 있는 지점을 찾아 조율하는 행동이 직접 드러나 opinion_mediation 후보로 연결된다",
    "understand_their_reason": "다른 사람이 그렇게 생각하는 이유를 먼저 헤아려보는 행동이 드러나 emotional_interpretation 후보로 연결된다",
    "decide_on_my_own": "다른 의견과 무관하게 스스로 판단한 방식을 그대로 밀고 나가는 행동이 드러나 independent_judgment 후보로 연결된다",
    "go_along": "그대로 맞춰주는 것은 수동적 동조에 가까워 특정 성향의 적극적 근거로 보기 어렵다",
}

_SEED_CAUSE_SELECTION = FinalizedQuestion(
    question_id="volunteer_seed_cause_selection_v1", context=_CONTEXT_ID, target_traits=[], frame_id="seed_anchor",
    question_text="여러 사회 문제 중 어디에 참여할지 골라야 한다고 상상해보세요. 무엇을 기준으로 정하나요?",
    options=[
        FinalizedOption(option_id="volunteer_seed_cause_selection_v1_o1", role_id="research_each_issue",
            text="각 문제에 대한 정보를 찾아보고 비교한다", primary_trait_delta={"information_comparison": 1}),
        FinalizedOption(option_id="volunteer_seed_cause_selection_v1_o2", role_id="trace_the_structure",
            text="이 문제가 다른 문제들과 어떻게 얽혀 있는지 살펴본다", primary_trait_delta={"systems_thinking": 1}),
        FinalizedOption(option_id="volunteer_seed_cause_selection_v1_o3", role_id="pick_personally_meaningful",
            text="나에게 더 의미 있게 다가오는 문제를 고른다", primary_trait_delta={"personal_goal_priority": 1}),
        FinalizedOption(option_id="volunteer_seed_cause_selection_v1_o4", role_id="pick_most_urgent_by_feel",
            text="가장 시급해 보이는 것을 바로 고른다", primary_trait_delta={"immediate_execution": 1}),
        FinalizedOption(option_id="volunteer_seed_cause_selection_v1_o5", role_id="follow_recommendation",
            text="주변에서 추천하는 곳을 고른다", primary_trait_delta={}),
    ],
)
_SEED_CAUSE_SELECTION_RATIONALE = {
    "research_each_issue": "각 문제에 대한 정보를 찾아 비교하는 행동이 드러나 information_comparison 후보로 연결된다",
    "trace_the_structure": "문제들이 서로 어떻게 얽혀 있는지 구조로 살피는 행동이 드러나 systems_thinking 후보로 연결된다",
    "pick_personally_meaningful": "공동의 기준보다 자신에게 의미 있는 기준을 우선하는 행동이 드러나 personal_goal_priority 후보로 연결된다",
    "pick_most_urgent_by_feel": "따져보기보다 먼저 눈에 띄는 것을 바로 고르는 행동이 드러나 immediate_execution 후보로 연결된다",
    "follow_recommendation": "추천을 따르는 것은 정보를 그대로 받아들이는 것일 뿐, 특정 성향의 직접 근거로 보기는 약하다",
}

SEED_ANCHOR_VARIANTS = [
    ContextPackSeedAnchorQuestion(anchor_id="help_method", question=_SEED_HELP_METHOD),
    ContextPackSeedAnchorQuestion(anchor_id="resource_allocation", question=_SEED_RESOURCE_ALLOCATION),
    ContextPackSeedAnchorQuestion(anchor_id="field_change", question=_SEED_FIELD_CHANGE),
    ContextPackSeedAnchorQuestion(anchor_id="opinion_difference", question=_SEED_OPINION_DIFFERENCE),
    ContextPackSeedAnchorQuestion(anchor_id="cause_selection", question=_SEED_CAUSE_SELECTION),
]

# ============================== Anchor Backup Questions ==============================

_BACKUP_HELP_METHOD = FinalizedQuestion(
    question_id="volunteer_backup_help_method_v1", context=_CONTEXT_ID, target_traits=[], frame_id="backup",
    question_text="생각해 둔 도움 방법이 이 사람에게는 잘 안 맞을 수도 있겠다는 생각이 들었다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="volunteer_backup_help_method_v1_o1", role_id="switch_approach",
            text="다른 방법으로 바꿔본다", primary_trait_delta={"change_adaptation": 1}),
        FinalizedOption(option_id="volunteer_backup_help_method_v1_o2", role_id="keep_original_way",
            text="원래 하려던 방법을 그대로 진행한다", primary_trait_delta={"persistence_completion": 1}),
        FinalizedOption(option_id="volunteer_backup_help_method_v1_o3", role_id="find_precedent",
            text="비슷한 경우에 다른 사람들은 어떻게 했는지 찾아본다", primary_trait_delta={"pattern_finding": 1}),
        FinalizedOption(option_id="volunteer_backup_help_method_v1_o4", role_id="use_new_resource",
            text="필요한 도구나 자료를 새로 찾아 활용해본다", primary_trait_delta={"tool_utilization": 1}),
        FinalizedOption(option_id="volunteer_backup_help_method_v1_o5", role_id="leave_it_as_is",
            text="일단 그대로 진행하고 지켜본다", primary_trait_delta={}),
    ],
)
_BACKUP_HELP_METHOD_RATIONALE = {
    "switch_approach": "맞지 않을 수 있는 방법을 바꾸는 행동이 드러나 change_adaptation 후보로 연결된다",
    "keep_original_way": "불확실해도 원래 방법을 그대로 끝까지 진행하는 행동이 드러나 persistence_completion 후보로 연결된다",
    "find_precedent": "비슷한 사례에서 반복되는 방식을 찾아보는 행동이 드러나 pattern_finding 후보로 연결된다",
    "use_new_resource": "새로운 도구나 자료를 찾아 활용하는 행동이 드러나 tool_utilization 후보로 연결된다",
    "leave_it_as_is": "일단 지켜보는 것은 판단을 유보하는 것이라 특정 성향의 직접 근거로 보기 어렵다",
}

_BACKUP_RESOURCE_ALLOCATION = FinalizedQuestion(
    question_id="volunteer_backup_resource_allocation_v1", context=_CONTEXT_ID, target_traits=[], frame_id="backup",
    question_text="나눠주기로 한 물품이 생각보다 부족하다는 걸 알게 됐다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="volunteer_backup_resource_allocation_v1_o1", role_id="recheck_amount",
            text="남은 양과 대상을 다시 하나하나 확인한다", primary_trait_delta={"detail_orientation": 1}),
        FinalizedOption(option_id="volunteer_backup_resource_allocation_v1_o2", role_id="reprioritize",
            text="누구에게 먼저 줄지 우선순위를 다시 정한다", primary_trait_delta={"planning": 1}),
        FinalizedOption(option_id="volunteer_backup_resource_allocation_v1_o3", role_id="find_more_resource",
            text="추가로 구할 수 있는 곳이 있는지 찾아본다", primary_trait_delta={"information_comparison": 1}),
        FinalizedOption(option_id="volunteer_backup_resource_allocation_v1_o4", role_id="ask_others_opinion",
            text="함께하는 사람들 의견을 모아 정한다", primary_trait_delta={"opinion_mediation": 1}),
        FinalizedOption(option_id="volunteer_backup_resource_allocation_v1_o5", role_id="just_give_first_come",
            text="먼저 온 순서대로 나눠준다", primary_trait_delta={}),
    ],
)
_BACKUP_RESOURCE_ALLOCATION_RATIONALE = {
    "recheck_amount": "남은 양과 대상을 하나하나 다시 확인하는 행동이 드러나 detail_orientation 후보로 연결된다",
    "reprioritize": "우선순위를 다시 세우는 행동이 드러나 planning 후보로 연결된다",
    "find_more_resource": "추가로 구할 곳을 찾아보는 행동이 드러나 information_comparison 후보로 연결된다",
    "ask_others_opinion": "함께하는 사람들의 의견을 모아 기준을 정하는 행동이 드러나 opinion_mediation 후보로 연결된다",
    "just_give_first_come": "순서대로 나눠주는 것은 정해진 관행을 따르는 것이라 특정 성향의 직접 근거로 보기는 약하다",
}

_BACKUP_FIELD_CHANGE = FinalizedQuestion(
    question_id="volunteer_backup_field_change_v1", context=_CONTEXT_ID, target_traits=[], frame_id="backup",
    question_text="현장에서 예상하지 못한 문제가 갑자기 생겼다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="volunteer_backup_field_change_v1_o1", role_id="act_right_away",
            text="일단 눈앞의 문제부터 바로 처리한다", primary_trait_delta={"immediate_execution": 1}),
        FinalizedOption(option_id="volunteer_backup_field_change_v1_o2", role_id="analyze_cause_first",
            text="무엇 때문에 이런 문제가 생겼는지부터 짚어본다", primary_trait_delta={"causal_analysis": 1}),
        FinalizedOption(option_id="volunteer_backup_field_change_v1_o3", role_id="coordinate_with_others",
            text="함께 있는 사람들과 역할을 나눠 대응한다", primary_trait_delta={"collaboration_preference": 1}),
        FinalizedOption(option_id="volunteer_backup_field_change_v1_o4", role_id="stay_uncertain_but_proceed",
            text="확실하지 않아도 일단 진행하면서 조정한다", primary_trait_delta={"uncertainty_tolerance": 1}),
        FinalizedOption(option_id="volunteer_backup_field_change_v1_o5", role_id="report_and_wait",
            text="책임자에게 알리고 지시를 기다린다", primary_trait_delta={}),
    ],
)
_BACKUP_FIELD_CHANGE_RATIONALE = {
    "act_right_away": "생각보다 먼저 눈앞의 문제부터 바로 처리하는 행동이 드러나 immediate_execution 후보로 연결된다",
    "analyze_cause_first": "문제의 원인을 능동적으로 짚어보는 행동이 드러나 causal_analysis 후보로 연결된다",
    "coordinate_with_others": "함께 있는 사람과 역할을 나눠 대응하는 행동이 드러나 collaboration_preference 후보로 연결된다",
    "stay_uncertain_but_proceed": "확실하지 않은 상태에서도 불안해하지 않고 진행하는 행동이 드러나 uncertainty_tolerance 후보로 연결된다",
    "report_and_wait": "책임자에게 알리고 기다리는 것은 절차를 따르는 일반적 대응이라 특정 성향의 직접 근거로 보기는 약하다",
}

_BACKUP_OPINION_DIFFERENCE = FinalizedQuestion(
    question_id="volunteer_backup_opinion_difference_v1", context=_CONTEXT_ID, target_traits=[], frame_id="backup",
    question_text="함께하는 사람이 내가 맡은 방식에 대해 다른 의견을 냈다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="volunteer_backup_opinion_difference_v1_o1", role_id="explain_reason",
            text="내가 그 방식을 고른 이유를 설명한다", primary_trait_delta={"opinion_expression": 1}),
        FinalizedOption(option_id="volunteer_backup_opinion_difference_v1_o2", role_id="combine_ideas",
            text="두 방식에서 좋은 점을 합쳐 새로운 방법을 만들어본다", primary_trait_delta={"creative_ideation": 1}),
        FinalizedOption(option_id="volunteer_backup_opinion_difference_v1_o3", role_id="understand_first",
            text="상대가 왜 그런 의견을 냈는지 먼저 들어본다", primary_trait_delta={"emotional_interpretation": 1}),
        FinalizedOption(option_id="volunteer_backup_opinion_difference_v1_o4", role_id="keep_my_way",
            text="내 기준이 맞다고 판단해 원래 방식을 유지한다", primary_trait_delta={"independent_judgment": 1}),
        FinalizedOption(option_id="volunteer_backup_opinion_difference_v1_o5", role_id="avoid_conflict",
            text="괜히 부딪히지 않으려 대화를 피한다", primary_trait_delta={}),
    ],
)
_BACKUP_OPINION_DIFFERENCE_RATIONALE = {
    "explain_reason": "자신의 선택 이유를 분명하게 설명하는 행동이 드러나 opinion_expression 후보로 연결된다",
    "combine_ideas": "서로 다른 방식의 좋은 점을 합쳐 새로운 방법을 만드는 행동이 드러나 creative_ideation 후보로 연결된다",
    "understand_first": "상대의 의견을 먼저 들어보고 이해하려는 행동이 드러나 emotional_interpretation 후보로 연결된다",
    "keep_my_way": "다른 의견과 무관하게 스스로 판단해 유지하는 행동이 드러나 independent_judgment 후보로 연결된다",
    "avoid_conflict": "대화를 피하는 것은 갈등 회피에 가까워 특정 성향의 적극적 근거로 보기 어렵다",
}

_BACKUP_CAUSE_SELECTION = FinalizedQuestion(
    question_id="volunteer_backup_cause_selection_v1", context=_CONTEXT_ID, target_traits=[], frame_id="backup",
    question_text="관심 있던 사회 문제에 대해 알아볼수록 생각이 복잡해졌다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="volunteer_backup_cause_selection_v1_o1", role_id="dig_deeper_cause",
            text="이 문제가 왜 생겼는지 더 깊이 파고든다", primary_trait_delta={"causal_analysis": 1}),
        FinalizedOption(option_id="volunteer_backup_cause_selection_v1_o2", role_id="compare_more_sources",
            text="다른 자료나 입장을 더 찾아 비교한다", primary_trait_delta={"information_comparison": 1}),
        FinalizedOption(option_id="volunteer_backup_cause_selection_v1_o3", role_id="decide_with_current_info",
            text="지금까지 알아본 것만으로 일단 정한다", primary_trait_delta={"uncertainty_tolerance": 1}),
        FinalizedOption(option_id="volunteer_backup_cause_selection_v1_o4", role_id="connect_related_issues",
            text="이 문제와 관련된 다른 문제들과 어떻게 연결되는지 살펴본다", primary_trait_delta={"systems_thinking": 1}),
        FinalizedOption(option_id="volunteer_backup_cause_selection_v1_o5", role_id="set_aside_for_now",
            text="일단 결정을 미뤄둔다", primary_trait_delta={}),
    ],
)
_BACKUP_CAUSE_SELECTION_RATIONALE = {
    "dig_deeper_cause": "문제의 원인을 더 깊이 파고드는 행동이 드러나 causal_analysis 후보로 연결된다",
    "compare_more_sources": "다른 자료나 입장을 찾아 비교하는 행동이 드러나 information_comparison 후보로 연결된다",
    "decide_with_current_info": "확실하지 않아도 지금까지의 정보만으로 결정을 내리는 행동이 드러나 uncertainty_tolerance 후보로 연결된다",
    "connect_related_issues": "관련된 다른 문제들과 어떻게 연결되는지 구조로 살피는 행동이 드러나 systems_thinking 후보로 연결된다",
    "set_aside_for_now": "결정을 미루는 것은 회피에 가까워 특정 성향의 적극적 근거로 보기 어렵다",
}

ANCHOR_BACKUP_QUESTIONS = [
    ContextPackAnchorBackupQuestion(anchor_id="help_method", question=_BACKUP_HELP_METHOD),
    ContextPackAnchorBackupQuestion(anchor_id="resource_allocation", question=_BACKUP_RESOURCE_ALLOCATION),
    ContextPackAnchorBackupQuestion(anchor_id="field_change", question=_BACKUP_FIELD_CHANGE),
    ContextPackAnchorBackupQuestion(anchor_id="opinion_difference", question=_BACKUP_OPINION_DIFFERENCE),
    ContextPackAnchorBackupQuestion(anchor_id="cause_selection", question=_BACKUP_CAUSE_SELECTION),
]

# ============================== Mapping Rationale ==============================

OPTION_MAPPING_RATIONALES = [
    *_rationales_for(_SEED_HELP_METHOD, "seed_anchor", _SEED_HELP_METHOD_RATIONALE),
    *_rationales_for(_SEED_RESOURCE_ALLOCATION, "seed_anchor", _SEED_RESOURCE_ALLOCATION_RATIONALE),
    *_rationales_for(_SEED_FIELD_CHANGE, "seed_anchor", _SEED_FIELD_CHANGE_RATIONALE),
    *_rationales_for(_SEED_OPINION_DIFFERENCE, "seed_anchor", _SEED_OPINION_DIFFERENCE_RATIONALE),
    *_rationales_for(_SEED_CAUSE_SELECTION, "seed_anchor", _SEED_CAUSE_SELECTION_RATIONALE),
    *_rationales_for(_BACKUP_HELP_METHOD, "anchor_backup", _BACKUP_HELP_METHOD_RATIONALE),
    *_rationales_for(_BACKUP_RESOURCE_ALLOCATION, "anchor_backup", _BACKUP_RESOURCE_ALLOCATION_RATIONALE),
    *_rationales_for(_BACKUP_FIELD_CHANGE, "anchor_backup", _BACKUP_FIELD_CHANGE_RATIONALE),
    *_rationales_for(_BACKUP_OPINION_DIFFERENCE, "anchor_backup", _BACKUP_OPINION_DIFFERENCE_RATIONALE),
    *_rationales_for(_BACKUP_CAUSE_SELECTION, "anchor_backup", _BACKUP_CAUSE_SELECTION_RATIONALE),
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
        "봉사 활동을 해본 경험을 전제하지 않는다",
        "봉사를 좋아하면 이타적이거나 협동적이라고 자동으로 연결하지 않는다",
        "특정 정치 성향이나 이념을 전제하지 않는다",
    ],
    review_artifact_paths=["data/reviews/context_packs/volunteer_review_status.json"],
    pack_version="v1.0",
)
