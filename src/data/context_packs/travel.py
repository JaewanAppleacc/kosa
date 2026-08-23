"""travel(여행·문화탐방) Context Pack — 2026-08-23 Trait Ontology v2(2.7단계 2차 배치) §2.

context-pack-social 작업 배정(담당: volunteer/travel/writing/history_humanities) 초안이다.
검수 상태는 전부 TBD이며 `data/reviews/context_packs/travel_review_status.json`에서
사람이 직접 채운다(§1 "Claude가 Context 질문을 자동 APPROVE하지 않는다").

설계 원칙(작업 지시문 그대로):
- 해외여행 경험·경제력을 전제하지 않는다 — "여행"이 국내 답사·현장체험도 포괄하도록
  일부러 "해외"를 한 번도 쓰지 않았고, forbidden_assumptions에도 명시했다.
- 낯선 장소·문화 정보·계획 변경·동행 의견 차이를 가상 상황으로 구성했다(5번째 Anchor로
  "다음 행선지 정하기" — 정보 비교·의사결정 상황을 추가해 Routing 5개를 채웠다).
- "모험적이다"라는 Trait을 자동으로 붙이지 않았다 — 같은 상황에서도
  planning/detail_orientation/uncertainty_tolerance/novelty_seeking처럼 서로 다른 축으로
  갈라 놓았다.
- "사람들을 따라간다", "먼저 물어본다", "함께 있는 사람이 정하게 둔다"처럼 무난하고
  사회적으로 자연스러워 보이는 선택지는 NO_SIGNAL로 두었다."""

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

_CONTEXT_ID = "travel"


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
    ("tr_place", "낯선 장소에 처음 도착했을 때", "unfamiliar_place", "낯선 장소 도착"),
    ("tr_culture", "다른 문화나 낯선 정보를 접했을 때", "culture_info", "낯선 문화·정보 접하기"),
    ("tr_plan", "계획이 갑자기 바뀌었을 때", "plan_change", "계획 변경 대응"),
    ("tr_companion", "함께 다니는 사람과 의견이 다를 때", "companion_opinion", "동행 의견 차이"),
    ("tr_route", "다음에 어디로 갈지 정할 때", "route_decision", "다음 행선지 정하기"),
]

_ROUTING_QUESTION_ID = "travel_context_router_v1_base"
_ROUTING_BLUEPRINT = ContextRoutingBlueprint(
    context_id=_CONTEXT_ID,
    blueprint_id="travel_context_router_v1",
    option_mappings=[
        ContextRoutingOptionMapping(role_id=role_id, context_anchor=anchor, anchor_label=label)
        for role_id, _text, anchor, label in _ROUTING_ROWS
    ],
    base_question=FinalizedQuestion(
        question_id=_ROUTING_QUESTION_ID, context=_CONTEXT_ID, target_traits=[], frame_id="context_routing",
        question_text="여행이나 낯선 곳을 탐방하는 상황을 상상해볼 때, 가장 관심이 가는 상황은 무엇인가요?",
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
        context_id=_CONTEXT_ID, anchor_id="unfamiliar_place", label="낯선 장소 도착",
        situation_terms=["낯선 장소", "도착", "방향"],
        preferred_scenarios=["낯선 장소에 처음 도착했을 때 무엇을 먼저 하는지"],
        forbidden_assumptions=["해외여행 경험", "여행 경비"],
    ),
    ContextAnchorPresentation(
        context_id=_CONTEXT_ID, anchor_id="culture_info", label="낯선 문화·정보 접하기",
        situation_terms=["다른 문화", "낯선 정보", "설명"],
        preferred_scenarios=["낯선 문화 정보나 설명을 접했을 때"],
        forbidden_assumptions=["해외여행 경험", "외국어 능력"],
    ),
    ContextAnchorPresentation(
        context_id=_CONTEXT_ID, anchor_id="plan_change", label="계획 변경 대응",
        situation_terms=["계획 변경", "일정 조정", "돌발 상황"],
        preferred_scenarios=["세워둔 일정이 갑자기 바뀌었을 때"],
        forbidden_assumptions=["해외여행 경험", "여행 경비"],
    ),
    ContextAnchorPresentation(
        context_id=_CONTEXT_ID, anchor_id="companion_opinion", label="동행 의견 차이",
        situation_terms=["동행", "의견 차이", "조율"],
        preferred_scenarios=["함께 다니는 사람과 하고 싶은 것이 다를 때"],
        forbidden_assumptions=["해외여행 경험", "친구와만 여행"],
    ),
    ContextAnchorPresentation(
        context_id=_CONTEXT_ID, anchor_id="route_decision", label="다음 행선지 정하기",
        situation_terms=["행선지", "정보 비교", "결정"],
        preferred_scenarios=["다음 행선지나 일정을 정해야 하는 상황"],
        forbidden_assumptions=["해외여행 경험", "여행 경비"],
    ),
]

# ============================== Seed Anchor Questions ==============================

_SEED_UNFAMILIAR_PLACE = FinalizedQuestion(
    question_id="travel_seed_unfamiliar_place_v1", context=_CONTEXT_ID, target_traits=[], frame_id="seed_anchor",
    question_text="낯선 장소에 처음 도착했다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="travel_seed_unfamiliar_place_v1_o1", role_id="explore_by_walking",
            text="일단 걸어 다니며 주변을 직접 살펴본다", primary_trait_delta={"immediate_execution": 1}),
        FinalizedOption(option_id="travel_seed_unfamiliar_place_v1_o2", role_id="check_map_first",
            text="지도나 안내 정보를 먼저 확인한다", primary_trait_delta={"planning": 1}),
        FinalizedOption(option_id="travel_seed_unfamiliar_place_v1_o3", role_id="notice_details",
            text="간판이나 표지판의 세세한 정보를 눈여겨본다", primary_trait_delta={"detail_orientation": 1}),
        FinalizedOption(option_id="travel_seed_unfamiliar_place_v1_o4", role_id="look_for_something_new",
            text="이곳에서만 볼 수 있는 낯선 것을 적극적으로 찾아본다", primary_trait_delta={"novelty_seeking": 1}),
        FinalizedOption(option_id="travel_seed_unfamiliar_place_v1_o5", role_id="follow_the_crowd",
            text="사람들이 많이 가는 쪽을 따라간다", primary_trait_delta={}),
    ],
)
_SEED_UNFAMILIAR_PLACE_RATIONALE = {
    "explore_by_walking": "미리 알아보기보다 직접 걸으며 살펴보는 행동이 드러나 immediate_execution 후보로 연결된다",
    "check_map_first": "움직이기 전에 지도와 정보를 먼저 확인하는 행동이 드러나 planning 후보로 연결된다",
    "notice_details": "작은 표지 정보까지 세세하게 눈여겨보는 행동이 드러나 detail_orientation 후보로 연결된다",
    "look_for_something_new": "익숙한 것보다 낯선 것을 스스로 찾아 나서는 행동이 드러나 novelty_seeking 후보로 연결된다",
    "follow_the_crowd": "사람들을 따라가는 것은 일반적인 안전한 선택이라 특정 성향의 직접 근거로 보기는 약하다",
}

_SEED_CULTURE_INFO = FinalizedQuestion(
    question_id="travel_seed_culture_info_v1", context=_CONTEXT_ID, target_traits=[], frame_id="seed_anchor",
    question_text="낯선 지역의 문화나 관습에 대한 설명을 듣게 됐다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="travel_seed_culture_info_v1_o1", role_id="compare_with_known",
            text="내가 아는 문화와 어떤 점이 다른지 비교해본다", primary_trait_delta={"information_comparison": 1}),
        FinalizedOption(option_id="travel_seed_culture_info_v1_o2", role_id="trace_why_it_formed",
            text="왜 이런 문화가 생겼는지 배경을 따져본다", primary_trait_delta={"causal_analysis": 1}),
        FinalizedOption(option_id="travel_seed_culture_info_v1_o3", role_id="connect_to_bigger_picture",
            text="이 관습이 그 지역의 다른 부분과 어떻게 얽혀 있는지 생각해본다", primary_trait_delta={"systems_thinking": 1}),
        FinalizedOption(option_id="travel_seed_culture_info_v1_o4", role_id="imagine_living_there",
            text="그 문화 속에서 사는 사람은 어떤 마음일지 상상해본다", primary_trait_delta={"emotional_interpretation": 1}),
        FinalizedOption(option_id="travel_seed_culture_info_v1_o5", role_id="just_follow_manners",
            text="실수하지 않게 그대로 따라 한다", primary_trait_delta={}),
    ],
)
_SEED_CULTURE_INFO_RATIONALE = {
    "compare_with_known": "아는 문화와 어떻게 다른지 비교하는 행동이 드러나 information_comparison 후보로 연결된다",
    "trace_why_it_formed": "그런 문화가 생긴 배경을 능동적으로 따져보는 행동이 드러나 causal_analysis 후보로 연결된다",
    "connect_to_bigger_picture": "관습이 다른 부분과 어떻게 얽혀 있는지 구조로 살피는 행동이 드러나 systems_thinking 후보로 연결된다",
    "imagine_living_there": "그 문화 속 사람의 마음을 상상해보는 행동이 드러나 emotional_interpretation 후보로 연결된다",
    "just_follow_manners": "그대로 따라 하는 것은 실수를 피하려는 일반적 태도라 특정 성향의 직접 근거로 보기는 약하다",
}

_SEED_PLAN_CHANGE = FinalizedQuestion(
    question_id="travel_seed_plan_change_v1", context=_CONTEXT_ID, target_traits=[], frame_id="seed_anchor",
    question_text="세워둔 여행 일정이 갑자기 바뀌게 됐다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="travel_seed_plan_change_v1_o1", role_id="make_new_plan_fast",
            text="남은 일정을 바로 새로 짜본다", primary_trait_delta={"change_adaptation": 1}),
        FinalizedOption(option_id="travel_seed_plan_change_v1_o2", role_id="keep_original_goal",
            text="원래 하려던 것은 최대한 그대로 지키려 한다", primary_trait_delta={"persistence_completion": 1}),
        FinalizedOption(option_id="travel_seed_plan_change_v1_o3", role_id="see_it_as_chance",
            text="예정에 없던 것을 해볼 기회로 삼는다", primary_trait_delta={"novelty_seeking": 1}),
        FinalizedOption(option_id="travel_seed_plan_change_v1_o4", role_id="proceed_without_certainty",
            text="확실하지 않아도 일단 움직이면서 정한다", primary_trait_delta={"uncertainty_tolerance": 1}),
        FinalizedOption(option_id="travel_seed_plan_change_v1_o5", role_id="ask_companion_first",
            text="함께 있는 사람에게 어떻게 할지 먼저 물어본다", primary_trait_delta={}),
    ],
)
_SEED_PLAN_CHANGE_RATIONALE = {
    "make_new_plan_fast": "바뀐 상황에 맞춰 계획을 바로 다시 짜는 행동이 드러나 change_adaptation 후보로 연결된다",
    "keep_original_goal": "상황이 바뀌어도 원래 목표를 지키려는 행동이 드러나 persistence_completion 후보로 연결된다",
    "see_it_as_chance": "예정에 없던 상황을 새로움을 시도할 기회로 삼는 행동이 드러나 novelty_seeking 후보로 연결된다",
    "proceed_without_certainty": "확실하지 않은 상태에서도 불안해하지 않고 움직이는 행동이 드러나 uncertainty_tolerance 후보로 연결된다",
    "ask_companion_first": "먼저 물어보는 것은 일반적인 확인 절차라 특정 성향의 직접 근거로 보기는 약하다",
}

_SEED_COMPANION_OPINION = FinalizedQuestion(
    question_id="travel_seed_companion_opinion_v1", context=_CONTEXT_ID, target_traits=[], frame_id="seed_anchor",
    question_text="함께 다니는 사람과 하고 싶은 것이 다르다는 걸 알게 됐다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="travel_seed_companion_opinion_v1_o1", role_id="say_my_preference",
            text="내가 하고 싶은 것을 분명하게 말한다", primary_trait_delta={"opinion_expression": 1}),
        FinalizedOption(option_id="travel_seed_companion_opinion_v1_o2", role_id="find_middle_ground",
            text="둘 다 만족할 수 있는 방법을 찾아본다", primary_trait_delta={"opinion_mediation": 1}),
        FinalizedOption(option_id="travel_seed_companion_opinion_v1_o3", role_id="understand_their_reason",
            text="상대가 왜 그걸 하고 싶어하는지 먼저 이해해본다", primary_trait_delta={"emotional_interpretation": 1}),
        FinalizedOption(option_id="travel_seed_companion_opinion_v1_o4", role_id="go_with_my_plan",
            text="내가 원래 계획한 대로 진행한다", primary_trait_delta={"personal_goal_priority": 1}),
        FinalizedOption(option_id="travel_seed_companion_opinion_v1_o5", role_id="let_them_choose",
            text="상대가 하고 싶은 대로 따른다", primary_trait_delta={}),
    ],
)
_SEED_COMPANION_OPINION_RATIONALE = {
    "say_my_preference": "내가 원하는 것을 분명히 말하는 행동이 드러나 opinion_expression 후보로 연결된다",
    "find_middle_ground": "둘 다 만족할 수 있는 지점을 찾는 행동이 드러나 opinion_mediation 후보로 연결된다",
    "understand_their_reason": "상대가 그렇게 원하는 이유를 먼저 헤아려보는 행동이 드러나 emotional_interpretation 후보로 연결된다",
    "go_with_my_plan": "공동 조율보다 자신의 계획을 우선하는 행동이 드러나 personal_goal_priority 후보로 연결된다",
    "let_them_choose": "그대로 따르는 것은 수동적 동조에 가까워 특정 성향의 적극적 근거로 보기 어렵다",
}

_SEED_ROUTE_DECISION = FinalizedQuestion(
    question_id="travel_seed_route_decision_v1", context=_CONTEXT_ID, target_traits=[], frame_id="seed_anchor",
    question_text="다음 행선지를 정해야 하는데 후보가 여러 곳이라고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="travel_seed_route_decision_v1_o1", role_id="compare_candidates",
            text="후보들의 정보를 찾아 하나하나 비교한다", primary_trait_delta={"information_comparison": 1}),
        FinalizedOption(option_id="travel_seed_route_decision_v1_o2", role_id="pick_the_new_one",
            text="가보지 않은 낯선 곳을 고른다", primary_trait_delta={"novelty_seeking": 1}),
        FinalizedOption(option_id="travel_seed_route_decision_v1_o3", role_id="pick_the_challenging_one",
            text="더 어렵거나 힘들 것 같은 곳에 끌린다", primary_trait_delta={"challenge_seeking": 1}),
        FinalizedOption(option_id="travel_seed_route_decision_v1_o4", role_id="decide_fast",
            text="오래 고민하지 않고 끌리는 곳을 바로 정한다", primary_trait_delta={"immediate_execution": 1}),
        FinalizedOption(option_id="travel_seed_route_decision_v1_o5", role_id="ask_others_recommendation",
            text="다른 사람들은 어디를 추천하는지 물어본다", primary_trait_delta={}),
    ],
)
_SEED_ROUTE_DECISION_RATIONALE = {
    "compare_candidates": "후보 정보를 찾아 하나하나 비교하는 행동이 드러나 information_comparison 후보로 연결된다",
    "pick_the_new_one": "익숙한 곳보다 가보지 않은 낯선 곳을 스스로 찾는 행동이 드러나 novelty_seeking 후보로 연결된다",
    "pick_the_challenging_one": "쉬운 곳보다 더 어려운 곳에 끌리는 행동이 드러나 challenge_seeking 후보로 연결된다",
    "decide_fast": "따져보기보다 먼저 끌리는 곳을 바로 정하는 행동이 드러나 immediate_execution 후보로 연결된다",
    "ask_others_recommendation": "다른 사람 추천을 묻는 것은 정보 확인 행동일 뿐, 특정 성향의 직접 근거로 보기는 약하다",
}

SEED_ANCHOR_VARIANTS = [
    ContextPackSeedAnchorQuestion(anchor_id="unfamiliar_place", question=_SEED_UNFAMILIAR_PLACE),
    ContextPackSeedAnchorQuestion(anchor_id="culture_info", question=_SEED_CULTURE_INFO),
    ContextPackSeedAnchorQuestion(anchor_id="plan_change", question=_SEED_PLAN_CHANGE),
    ContextPackSeedAnchorQuestion(anchor_id="companion_opinion", question=_SEED_COMPANION_OPINION),
    ContextPackSeedAnchorQuestion(anchor_id="route_decision", question=_SEED_ROUTE_DECISION),
]

# ============================== Anchor Backup Questions ==============================

_BACKUP_UNFAMILIAR_PLACE = FinalizedQuestion(
    question_id="travel_backup_unfamiliar_place_v1", context=_CONTEXT_ID, target_traits=[], frame_id="backup",
    question_text="낯선 장소에서 길을 잘못 들어섰다는 걸 알게 됐다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="travel_backup_unfamiliar_place_v1_o1", role_id="retrace_and_check",
            text="지나온 길을 하나하나 다시 확인한다", primary_trait_delta={"detail_orientation": 1}),
        FinalizedOption(option_id="travel_backup_unfamiliar_place_v1_o2", role_id="try_new_direction",
            text="이 참에 다른 방향으로도 가본다", primary_trait_delta={"novelty_seeking": 1}),
        FinalizedOption(option_id="travel_backup_unfamiliar_place_v1_o3", role_id="figure_out_where_wrong",
            text="어디서부터 잘못됐는지 원인을 짚어본다", primary_trait_delta={"causal_analysis": 1}),
        FinalizedOption(option_id="travel_backup_unfamiliar_place_v1_o4", role_id="stay_calm_and_continue",
            text="불안해하지 않고 일단 걸으며 방향을 찾는다", primary_trait_delta={"uncertainty_tolerance": 1}),
        FinalizedOption(option_id="travel_backup_unfamiliar_place_v1_o5", role_id="ask_someone_nearby",
            text="주변 사람에게 길을 물어본다", primary_trait_delta={}),
    ],
)
_BACKUP_UNFAMILIAR_PLACE_RATIONALE = {
    "retrace_and_check": "지나온 길을 하나하나 다시 확인하는 행동이 드러나 detail_orientation 후보로 연결된다",
    "try_new_direction": "이 상황을 새로운 방향을 시도할 기회로 삼는 행동이 드러나 novelty_seeking 후보로 연결된다",
    "figure_out_where_wrong": "잘못된 지점의 원인을 능동적으로 짚어보는 행동이 드러나 causal_analysis 후보로 연결된다",
    "stay_calm_and_continue": "확실하지 않은 상태에서도 불안해하지 않고 계속 움직이는 행동이 드러나 uncertainty_tolerance 후보로 연결된다",
    "ask_someone_nearby": "주변에 길을 묻는 것은 일반적인 확인 행동이라 특정 성향의 직접 근거로 보기는 약하다",
}

_BACKUP_CULTURE_INFO = FinalizedQuestion(
    question_id="travel_backup_culture_info_v1", context=_CONTEXT_ID, target_traits=[], frame_id="backup",
    question_text="안내판이나 설명이 내가 알던 내용과 다르다는 걸 알게 됐다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="travel_backup_culture_info_v1_o1", role_id="search_more_sources",
            text="다른 자료를 더 찾아서 확인해본다", primary_trait_delta={"information_comparison": 1}),
        FinalizedOption(option_id="travel_backup_culture_info_v1_o2", role_id="question_why_different",
            text="왜 다르게 알려져 있는지 이유를 생각해본다", primary_trait_delta={"causal_analysis": 1}),
        FinalizedOption(option_id="travel_backup_culture_info_v1_o3", role_id="connect_to_context",
            text="이 설명이 그 지역의 다른 배경과 어떻게 이어지는지 살펴본다", primary_trait_delta={"systems_thinking": 1}),
        FinalizedOption(option_id="travel_backup_culture_info_v1_o4", role_id="accept_new_info",
            text="새로 알게 된 내용을 그대로 받아들인다", primary_trait_delta={"uncertainty_tolerance": 1}),
        FinalizedOption(option_id="travel_backup_culture_info_v1_o5", role_id="move_on",
            text="크게 신경 쓰지 않고 넘어간다", primary_trait_delta={}),
    ],
)
_BACKUP_CULTURE_INFO_RATIONALE = {
    "search_more_sources": "다른 자료를 더 찾아 확인하는 행동이 드러나 information_comparison 후보로 연결된다",
    "question_why_different": "왜 다르게 알려졌는지 이유를 생각해보는 행동이 드러나 causal_analysis 후보로 연결된다",
    "connect_to_context": "설명을 다른 배경과 연결해 구조로 살피는 행동이 드러나 systems_thinking 후보로 연결된다",
    "accept_new_info": "확실히 검증되지 않은 새 정보도 열어두고 받아들이는 행동이 드러나 uncertainty_tolerance 후보로 연결된다",
    "move_on": "신경 쓰지 않고 넘어가는 것은 특정 성향의 적극적 근거로 보기 어렵다",
}

_BACKUP_PLAN_CHANGE = FinalizedQuestion(
    question_id="travel_backup_plan_change_v1", context=_CONTEXT_ID, target_traits=[], frame_id="backup",
    question_text="예약해둔 것이 취소돼서 일정을 다시 짜야 한다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="travel_backup_plan_change_v1_o1", role_id="replan_whole_schedule",
            text="남은 일정 전체를 다시 계획한다", primary_trait_delta={"planning": 1}),
        FinalizedOption(option_id="travel_backup_plan_change_v1_o2", role_id="try_something_unplanned",
            text="원래 계획에 없던 것을 해본다", primary_trait_delta={"novelty_seeking": 1}),
        FinalizedOption(option_id="travel_backup_plan_change_v1_o3", role_id="push_for_original",
            text="원래 예약했던 것과 최대한 비슷한 대안을 끝까지 찾는다", primary_trait_delta={"persistence_completion": 1}),
        FinalizedOption(option_id="travel_backup_plan_change_v1_o4", role_id="let_companion_decide",
            text="함께 있는 사람이 정하게 둔다", primary_trait_delta={}),
        FinalizedOption(option_id="travel_backup_plan_change_v1_o5", role_id="combine_options",
            text="몇 가지 대안을 조합해 새로운 일정을 만들어본다", primary_trait_delta={"creative_ideation": 1}),
    ],
)
_BACKUP_PLAN_CHANGE_RATIONALE = {
    "replan_whole_schedule": "남은 일정 전체를 다시 계획하는 행동이 드러나 planning 후보로 연결된다",
    "try_something_unplanned": "이 상황을 계획에 없던 것을 시도할 기회로 삼는 행동이 드러나 novelty_seeking 후보로 연결된다",
    "push_for_original": "원래 목표와 비슷한 대안을 포기하지 않고 끝까지 찾는 행동이 드러나 persistence_completion 후보로 연결된다",
    "let_companion_decide": "다른 사람이 정하게 두는 것은 수동적 위임이라 특정 성향의 직접 근거로 보기 어렵다",
    "combine_options": "여러 대안을 조합해 새로운 방법을 만드는 행동이 드러나 creative_ideation 후보로 연결된다",
}

_BACKUP_COMPANION_OPINION = FinalizedQuestion(
    question_id="travel_backup_companion_opinion_v1", context=_CONTEXT_ID, target_traits=[], frame_id="backup",
    question_text="동행이 내가 세운 일정에 대해 걱정을 표현했다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="travel_backup_companion_opinion_v1_o1", role_id="explain_my_reasoning",
            text="이 일정을 짠 이유를 설명한다", primary_trait_delta={"opinion_expression": 1}),
        FinalizedOption(option_id="travel_backup_companion_opinion_v1_o2", role_id="listen_to_concern",
            text="상대가 왜 걱정하는지 먼저 들어본다", primary_trait_delta={"emotional_interpretation": 1}),
        FinalizedOption(option_id="travel_backup_companion_opinion_v1_o3", role_id="adjust_the_plan",
            text="걱정하는 부분을 반영해 일정을 조정한다", primary_trait_delta={"change_adaptation": 1}),
        FinalizedOption(option_id="travel_backup_companion_opinion_v1_o4", role_id="keep_my_plan",
            text="내가 세운 계획이 맞다고 보고 그대로 진행한다", primary_trait_delta={"independent_judgment": 1}),
        FinalizedOption(option_id="travel_backup_companion_opinion_v1_o5", role_id="downplay_it",
            text="별일 아니라며 넘어간다", primary_trait_delta={}),
    ],
)
_BACKUP_COMPANION_OPINION_RATIONALE = {
    "explain_my_reasoning": "자신의 계획 이유를 분명히 설명하는 행동이 드러나 opinion_expression 후보로 연결된다",
    "listen_to_concern": "상대의 걱정을 먼저 들어보고 이해하려는 행동이 드러나 emotional_interpretation 후보로 연결된다",
    "adjust_the_plan": "걱정하는 부분을 반영해 계획을 바꾸는 행동이 드러나 change_adaptation 후보로 연결된다",
    "keep_my_plan": "다른 의견과 무관하게 스스로 판단한 계획을 유지하는 행동이 드러나 independent_judgment 후보로 연결된다",
    "downplay_it": "넘어가는 것은 상황을 가볍게 다루는 것이라 특정 성향의 직접 근거로 보기 어렵다",
}

_BACKUP_ROUTE_DECISION = FinalizedQuestion(
    question_id="travel_backup_route_decision_v1", context=_CONTEXT_ID, target_traits=[], frame_id="backup",
    question_text="정보를 아무리 찾아봐도 후보 중 어디가 더 나을지 확신이 서지 않는다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="travel_backup_route_decision_v1_o1", role_id="decide_with_current_info",
            text="지금까지 찾은 정보만으로 일단 정한다", primary_trait_delta={"uncertainty_tolerance": 1}),
        FinalizedOption(option_id="travel_backup_route_decision_v1_o2", role_id="keep_searching",
            text="확신이 설 때까지 정보를 계속 더 찾는다", primary_trait_delta={"information_comparison": 1}),
        FinalizedOption(option_id="travel_backup_route_decision_v1_o3", role_id="pick_harder_option",
            text="더 어렵고 도전적인 쪽을 선택한다", primary_trait_delta={"challenge_seeking": 1}),
        FinalizedOption(option_id="travel_backup_route_decision_v1_o4", role_id="make_new_combo_plan",
            text="두 후보의 장점을 섞은 새로운 일정을 만들어본다", primary_trait_delta={"creative_ideation": 1}),
        FinalizedOption(option_id="travel_backup_route_decision_v1_o5", role_id="flip_a_coin",
            text="그냥 아무거나 골라본다", primary_trait_delta={}),
    ],
)
_BACKUP_ROUTE_DECISION_RATIONALE = {
    "decide_with_current_info": "확신이 없어도 지금까지의 정보만으로 결정하는 행동이 드러나 uncertainty_tolerance 후보로 연결된다",
    "keep_searching": "확신이 설 때까지 정보를 계속 찾는 행동이 드러나 information_comparison 후보로 연결된다",
    "pick_harder_option": "더 어려운 쪽을 스스로 선택하는 행동이 드러나 challenge_seeking 후보로 연결된다",
    "make_new_combo_plan": "두 후보의 장점을 섞어 새로운 방안을 만드는 행동이 드러나 creative_ideation 후보로 연결된다",
    "flip_a_coin": "아무거나 고르는 것은 무작위 선택이라 특정 성향의 근거가 되지 않는다",
}

ANCHOR_BACKUP_QUESTIONS = [
    ContextPackAnchorBackupQuestion(anchor_id="unfamiliar_place", question=_BACKUP_UNFAMILIAR_PLACE),
    ContextPackAnchorBackupQuestion(anchor_id="culture_info", question=_BACKUP_CULTURE_INFO),
    ContextPackAnchorBackupQuestion(anchor_id="plan_change", question=_BACKUP_PLAN_CHANGE),
    ContextPackAnchorBackupQuestion(anchor_id="companion_opinion", question=_BACKUP_COMPANION_OPINION),
    ContextPackAnchorBackupQuestion(anchor_id="route_decision", question=_BACKUP_ROUTE_DECISION),
]

# ============================== Mapping Rationale ==============================

OPTION_MAPPING_RATIONALES = [
    *_rationales_for(_SEED_UNFAMILIAR_PLACE, "seed_anchor", _SEED_UNFAMILIAR_PLACE_RATIONALE),
    *_rationales_for(_SEED_CULTURE_INFO, "seed_anchor", _SEED_CULTURE_INFO_RATIONALE),
    *_rationales_for(_SEED_PLAN_CHANGE, "seed_anchor", _SEED_PLAN_CHANGE_RATIONALE),
    *_rationales_for(_SEED_COMPANION_OPINION, "seed_anchor", _SEED_COMPANION_OPINION_RATIONALE),
    *_rationales_for(_SEED_ROUTE_DECISION, "seed_anchor", _SEED_ROUTE_DECISION_RATIONALE),
    *_rationales_for(_BACKUP_UNFAMILIAR_PLACE, "anchor_backup", _BACKUP_UNFAMILIAR_PLACE_RATIONALE),
    *_rationales_for(_BACKUP_CULTURE_INFO, "anchor_backup", _BACKUP_CULTURE_INFO_RATIONALE),
    *_rationales_for(_BACKUP_PLAN_CHANGE, "anchor_backup", _BACKUP_PLAN_CHANGE_RATIONALE),
    *_rationales_for(_BACKUP_COMPANION_OPINION, "anchor_backup", _BACKUP_COMPANION_OPINION_RATIONALE),
    *_rationales_for(_BACKUP_ROUTE_DECISION, "anchor_backup", _BACKUP_ROUTE_DECISION_RATIONALE),
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
        "해외여행 경험이나 경제적 여유를 전제하지 않는다",
        "여행을 좋아하면 모험적이라고 자동으로 연결하지 않는다",
        "친구와만 여행한다고 전제하지 않는다",
    ],
    review_artifact_paths=["data/reviews/context_packs/travel_review_status.json"],
    pack_version="v1.0",
)
