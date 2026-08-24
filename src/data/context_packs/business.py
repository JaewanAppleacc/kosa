"""business(창업·비즈니스) Context Pack — context-pack-technical 브랜치 초안.

담당 범위: 질문 콘텐츠와 Trait Mapping Draft만(`outputs/context_packs/
context_pack_development_guide.md` §1/§2). Anchor 5개, Anchor당 Seed 1개·Backup
1개, 총 10개 질문·50개 Option을 이 파일 안에서 자기 완결적으로 정의한다(§2 —
`primary_trait_delta`를 이 Pack이 직접 소유, 기존 3개 Vertical Slice Context처럼
외부 Legacy Seed Question을 참조하지 않는다).

작업 지시 준수 사항(사용자 지시문 그대로):
- 창업 관심 자체를 리더십·모험성 등 특정 Trait로 자동 연결하지 않는다 — Anchor
  5개 각각의 Seed/Backup Option Trait는 실제 서술된 행동(아이디어 만들기·반응
  확인·자원 배분·방향 결정·역할 나누기)에서만 도출했다.
  role_id는 질문 내부에서만 고유하면 되고(Schema 요구), Pack 전체에서 재사용해도
  된다.
- 실제 창업 경험을 전제하지 않는다(투자 유치·매출·법인 등록 등 언급 없음) —
  동아리·팀 활동·수행평가 수준의 상황만 쓴다.
- "돈을 많이 벌고 싶은지"를 묻지 않는다 — 이 파일 어디에도 금전적 목표를 묻는
  문항이 없다.
- 아이디어·고객 반응·자원 배분·의사결정 상황을 Anchor로 삼았다(아래 5개).

Trait는 24개 Ontology(`data/master/trait_ontology_v2.jsonl`) 밖의 것을 쓰지
않는다. 질문·선택지 검수 상태는 전부 TBD로 시작한다(`_review_status_dir` JSON,
같은 커밋에 `data/reviews/context_packs/business_review_status.json`으로 동봉) —
Claude가 자동 APPROVE하지 않는다(개발 가이드 §1 4번, CLAUDE.md).

Direct Probe 후보: 이번 초안에서는 만들지 않았다(0개, Schema상 허용). 자원 배분
Anchor에서 `personal_goal_priority`(개인 목표 우선)를 더 직접적으로 관찰할
Direct Probe 후보가 있으면 좋겠다는 메모를 `outputs/context_packs/
business_mapping_audit.md`에 남겼다 — 실제 Blueprint 작성은 이번 범위 밖이다."""

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

CONTEXT_ID = "business"

# (role_id, option 문구, trait_id 또는 None(NO_SIGNAL), Mapping Rationale Draft)
_OptionSpec = tuple[str, str, str | None, str]


def _question(question_id: str, frame_id: str, question_text: str, options: list[_OptionSpec]) -> FinalizedQuestion:
    if len(options) != 5:
        raise ValueError(f"{question_id}: option은 정확히 5개여야 한다(got {len(options)})")
    finalized = [
        FinalizedOption(
            option_id=f"{question_id}_o{i}", role_id=role_id, text=text,
            primary_trait_delta=({trait_id: 1} if trait_id else {}),
        )
        for i, (role_id, text, trait_id, _rationale) in enumerate(options, start=1)
    ]
    return FinalizedQuestion(
        question_id=question_id, context=CONTEXT_ID, target_traits=[], frame_id=frame_id,
        question_text=question_text, options=finalized,
    )


def _rationales(question_id: str, source: str, options: list[_OptionSpec]) -> list[OptionMappingRationale]:
    return [
        OptionMappingRationale(
            source=source, question_id=question_id, role_id=role_id, trait_id=trait_id,
            mapping_rationale_draft=rationale,
        )
        for role_id, _text, trait_id, rationale in options
    ]


# ============================== Anchor 5개 ==============================

ANCHOR_PRESENTATIONS: list[ContextAnchorPresentation] = [
    ContextAnchorPresentation(
        context_id=CONTEXT_ID, anchor_id="idea_shaping", label="아이디어 구상",
        situation_terms=["아이디어", "구상", "다듬기"],
        preferred_scenarios=["새로운 아이디어를 떠올리는 상황", "떠올린 아이디어를 구체화하는 상황"],
        forbidden_assumptions=["실제 창업 경험", "투자 유치 경험"],
    ),
    ContextAnchorPresentation(
        context_id=CONTEXT_ID, anchor_id="feedback_reading", label="반응·피드백 확인",
        situation_terms=["반응", "피드백", "의견"],
        preferred_scenarios=["사람들의 반응을 확인하는 상황", "예상과 다른 반응을 접하는 상황"],
        forbidden_assumptions=["실제 판매·거래 경험", "투자자 앞 발표"],
    ),
    ContextAnchorPresentation(
        context_id=CONTEXT_ID, anchor_id="resource_budgeting", label="자원·예산 배분",
        situation_terms=["제한된 자원", "배분", "우선순위"],
        preferred_scenarios=["정해진 예산 안에서 쓸 곳을 정하는 상황", "시간이 부족한 상황에서 순서를 정하는 상황"],
        forbidden_assumptions=["실제 자금 운용 경험", "큰 규모의 예산"],
    ),
    ContextAnchorPresentation(
        context_id=CONTEXT_ID, anchor_id="plan_decision", label="방향 결정",
        situation_terms=["선택지", "결정", "방향"],
        preferred_scenarios=["여러 대안 중 하나를 고르는 상황", "예상과 다르게 흘러갔을 때 방향을 다시 정하는 상황"],
        forbidden_assumptions=["정답이 정해진 결정"],
    ),
    ContextAnchorPresentation(
        context_id=CONTEXT_ID, anchor_id="team_role_share", label="팀 역할 나누기",
        situation_terms=["역할", "분담", "팀"],
        preferred_scenarios=["팀에서 역할을 나누는 상황", "의견이 다른 팀원과 조율하는 상황"],
        forbidden_assumptions=["리더 역할을 기본으로 맡는 것", "이미 완성된 팀 구성"],
    ),
]

# ============================== Routing 질문 1개 ==============================

_ROUTING_QUESTION_ID = "business_routing_question"
_ROUTING_ROWS: list[tuple[str, str, str, str]] = [  # role_id, 문구, anchor_id, anchor_label
    ("br_idea", "새로운 아이디어를 떠올리고 다듬는 순간", "idea_shaping", "아이디어 구상"),
    ("br_feedback", "사람들의 반응이나 피드백을 확인하는 순간", "feedback_reading", "반응·피드백 확인"),
    ("br_resource", "정해진 시간이나 예산 안에서 무엇을 우선할지 정하는 순간", "resource_budgeting", "자원·예산 배분"),
    ("br_decision", "아이디어를 어떤 방식으로 실제 진행할지 결정하는 순간", "plan_decision", "방향 결정"),
    ("br_team", "팀에서 역할을 나누는 순간", "team_role_share", "팀 역할 나누기"),
]
ROUTING_BLUEPRINT = ContextRoutingBlueprint(
    context_id=CONTEXT_ID, blueprint_id="business_context_router_v1",
    option_mappings=[
        ContextRoutingOptionMapping(role_id=role_id, context_anchor=anchor_id, anchor_label=label)
        for role_id, _text, anchor_id, label in _ROUTING_ROWS
    ],
    base_question=FinalizedQuestion(
        question_id=_ROUTING_QUESTION_ID, context=CONTEXT_ID, target_traits=[], frame_id="context_routing",
        question_text="동아리 활동이나 수행평가에서 아이디어·사업 관련 활동을 한다면, 어떤 순간에 가장 마음이 쓰일 것 같나요?",
        options=[
            FinalizedOption(option_id=f"{_ROUTING_QUESTION_ID}_o{i}", role_id=role_id, text=text, primary_trait_delta={})
            for i, (role_id, text, _anchor_id, _label) in enumerate(_ROUTING_ROWS, start=1)
        ],
    ),
)

# ============================== Seed / Backup ==============================

_SEED_OPTIONS: dict[str, list[_OptionSpec]] = {
    "idea_shaping": [
        ("try_new_way", "이미 있는 것과는 다른 새로운 방식을 시도해보려 한다", "novelty_seeking",
         "익숙한 방식 대신 낯선 방식을 시도하려는 행동이 드러나 novelty_seeking 후보로 연결된다"),
        ("free_brainstorm", "머릿속에 떠오르는 대로 여러 아이디어를 자유롭게 만들어본다", "creative_ideation",
         "형식에 얽매이지 않고 스스로 아이디어를 만들어내는 행동이 드러나 creative_ideation 후보로 연결된다"),
        ("predict_reaction", "사람들이 이 아이디어를 어떻게 받아들일지 미리 그려본다", "audience_response_prediction",
         "실행 전에 다른 사람의 반응을 예상해보는 행동이 드러나 audience_response_prediction 후보로 연결된다"),
        ("set_direction", "여러 아이디어 중 무엇부터 다뤄볼지 순서를 정해본다", "planning",
         "여러 후보 중 처리 순서를 스스로 정하는 행동이 드러나 planning 후보로 연결된다"),
        ("talk_casually", "일단 흥미가 가는 것부터 편하게 이야기해본다", None,
         "단순히 흥미 위주로 편하게 이야기하는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
    ],
    "feedback_reading": [
        ("guess_before_ask", "물어보기 전에 사람들이 어떻게 반응할지 먼저 예상해본다", "audience_response_prediction",
         "확인하기 전에 반응을 미리 예상해보는 행동이 드러나 audience_response_prediction 후보로 연결된다"),
        ("find_why_negative", "반응이 예상과 다르면 그 이유를 파고든다", "causal_analysis",
         "예상과 다른 결과의 원인을 능동적으로 짚어보는 행동이 드러나 causal_analysis 후보로 연결된다"),
        ("compare_opinions", "여러 사람의 의견을 비교해서 공통점을 찾는다", "information_comparison",
         "여러 의견을 나란히 놓고 비교·정리하는 행동이 드러나 information_comparison 후보로 연결된다"),
        ("just_check_count", "얼마나 많은 사람이 좋아했는지부터 확인한다", None,
         "단순 수치 확인만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("explain_my_view", "내가 왜 이렇게 만들었는지 사람들에게 설명한다", "opinion_expression",
         "자신의 생각과 의도를 적극적으로 드러내는 행동이 드러나 opinion_expression 후보로 연결된다"),
    ],
    "resource_budgeting": [
        ("list_priority", "무엇을 먼저 해야 할지 순서를 정리한다", "planning",
         "제한된 자원 안에서 처리 순서를 정리하는 행동이 드러나 planning 후보로 연결된다"),
        ("cut_least_needed", "가장 덜 중요한 것부터 내 기준으로 줄이거나 뺀다", "independent_judgment",
         "스스로 세운 기준으로 우선순위를 정해 결정하는 행동이 드러나 independent_judgment 후보로 연결된다"),
        ("research_cost", "각 항목에 얼마나 필요한지 미리 알아본다", "information_comparison",
         "결정 전에 여러 항목의 정보를 찾아 비교하는 행동이 드러나 information_comparison 후보로 연결된다"),
        ("start_first", "일단 손이 가는 것부터 바로 시작한다", "immediate_execution",
         "계획보다 먼저 행동으로 옮기는 모습이 드러나 immediate_execution 후보로 연결된다"),
        ("follow_example", "예전에 하던 방식을 그대로 따른다", None,
         "기존 방식을 그대로 따르는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
    ],
    "plan_decision": [
        ("weigh_options", "각 방향의 장단점을 비교해본다", "information_comparison",
         "선택 전에 여러 방향의 장단점을 비교하는 행동이 드러나 information_comparison 후보로 연결된다"),
        ("decide_by_self", "다른 사람 의견보다 내 판단을 우선한다", "independent_judgment",
         "외부 의견보다 스스로의 판단을 우선하는 행동이 드러나 independent_judgment 후보로 연결된다"),
        ("pick_uncertain", "결과가 확실하지 않아도 일단 하나를 선택해본다", "uncertainty_tolerance",
         "결과가 불확실한 상태에서도 선택을 진행하는 행동이 드러나 uncertainty_tolerance 후보로 연결된다"),
        ("talk_to_others", "다른 사람들 생각을 먼저 들어본다", "collaboration_preference",
         "결정 전에 다른 사람과 의견을 맞춰보는 행동이 드러나 collaboration_preference 후보로 연결된다"),
        ("go_with_flow", "정해진 흐름을 따라간다", None,
         "단순히 정해진 흐름을 따르는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
    ],
    "team_role_share": [
        ("suggest_split", "각자 잘할 수 있는 역할을 먼저 제안해본다", "opinion_expression",
         "역할 분담에 대한 생각을 먼저 적극적으로 제안하는 행동이 드러나 opinion_expression 후보로 연결된다"),
        ("adjust_conflict", "역할이 겹칠 때 의견을 조율해서 맞춘다", "opinion_mediation",
         "서로 다른 의견 사이에서 공통점을 찾아 조율하는 행동이 드러나 opinion_mediation 후보로 연결된다"),
        ("take_needed_role", "부족한 역할이 있으면 그 역할을 맡는다", "collaboration_preference",
         "팀에 필요한 부분을 채우며 협력하는 행동이 드러나 collaboration_preference 후보로 연결된다"),
        ("set_process", "역할을 정하는 순서나 기준을 먼저 세운다", "planning",
         "역할 배분의 순서·기준을 미리 세우는 행동이 드러나 planning 후보로 연결된다"),
        ("wait_assignment", "정해질 때까지 기다린다", None,
         "수동적으로 기다리는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
    ],
}

_SEED_QUESTION_TEXT: dict[str, str] = {
    "idea_shaping": "여러 사업 아이디어를 떠올릴 때, 다음 중 나에게 가장 가까운 모습은 무엇인가요?",
    "feedback_reading": "만든 결과물이나 아이디어에 대해 사람들의 반응을 확인할 때, 나에게 가장 가까운 모습은 무엇인가요?",
    "resource_budgeting": "정해진 시간이나 예산 안에서 무언가를 준비해야 할 때, 나에게 가장 가까운 모습은 무엇인가요?",
    "plan_decision": "여러 방향 중 하나를 선택해야 할 때, 나에게 가장 가까운 모습은 무엇인가요?",
    "team_role_share": "동아리나 팀 활동에서 역할을 나눠야 할 때, 나에게 가장 가까운 모습은 무엇인가요?",
}

_BACKUP_OPTIONS: dict[str, list[_OptionSpec]] = {
    "idea_shaping": [
        ("change_angle", "질문을 바꿔서 다른 각도로 다시 생각해본다", "change_adaptation",
         "막힌 상황에서 접근 방식을 스스로 바꿔보는 행동이 드러나 change_adaptation 후보로 연결된다"),
        ("ask_others_first", "다른 사람 의견을 먼저 들어본다", "collaboration_preference",
         "막혔을 때 다른 사람과 함께 풀어가려는 행동이 드러나 collaboration_preference 후보로 연결된다"),
        ("research_examples", "비슷한 사례를 찾아보며 힌트를 얻는다", "information_comparison",
         "참고할 사례를 찾아 비교해보는 행동이 드러나 information_comparison 후보로 연결된다"),
        ("wait_quietly", "잠시 조용히 생각할 시간을 갖는다", None,
         "단순히 생각할 시간을 갖는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("say_rough_idea", "완성되지 않았어도 떠오르는 대로 말해본다", "creative_ideation",
         "완결되지 않은 상태에서도 아이디어를 적극적으로 꺼내는 행동이 드러나 creative_ideation 후보로 연결된다"),
    ],
    "feedback_reading": [
        ("ask_reason", "왜 그렇게 생각했는지 이유를 물어본다", "causal_analysis",
         "예상과 다른 반응의 이유를 직접 물어 파고드는 행동이 드러나 causal_analysis 후보로 연결된다"),
        ("defend_view", "내 생각을 조금 더 자세히 설명해본다", "opinion_expression",
         "자신의 생각을 다시 한번 적극적으로 설명하는 행동이 드러나 opinion_expression 후보로 연결된다"),
        ("adjust_idea", "그 반응을 반영해서 아이디어를 조정해본다", "change_adaptation",
         "받은 반응에 맞춰 아이디어를 바꿔보는 행동이 드러나 change_adaptation 후보로 연결된다"),
        ("move_on", "크게 신경 쓰지 않고 넘어간다", None,
         "별다른 대응 없이 넘어가는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("ask_more_people", "다른 사람들 생각도 더 들어본다", "information_comparison",
         "여러 사람의 의견을 더 모아 비교하는 행동이 드러나 information_comparison 후보로 연결된다"),
    ],
    "resource_budgeting": [
        ("recalculate", "남은 자원으로 다시 계획을 짜본다", "planning",
         "변화한 조건에 맞춰 계획을 다시 세우는 행동이 드러나 planning 후보로 연결된다"),
        ("decide_alone", "내 기준으로 무엇을 포기할지 정한다", "independent_judgment",
         "스스로의 기준으로 포기할 항목을 정하는 행동이 드러나 independent_judgment 후보로 연결된다"),
        ("ask_team", "팀원들과 상의해서 정한다", "collaboration_preference",
         "결정을 팀원과 함께 상의해서 내리는 행동이 드러나 collaboration_preference 후보로 연결된다"),
        ("keep_going", "일단 하던 대로 계속 진행한다", None,
         "별다른 판단 없이 진행을 유지하는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("try_alternative", "결과가 어떻게 될지 몰라도 일단 다른 방법을 시도해본다", "uncertainty_tolerance",
         "결과가 불확실한 상태에서도 대안을 시도하는 행동이 드러나 uncertainty_tolerance 후보로 연결된다"),
    ],
    "plan_decision": [
        ("find_cause", "어디서부터 어긋났는지 원인을 짚어본다", "causal_analysis",
         "계획이 틀어진 지점의 원인을 짚어보는 행동이 드러나 causal_analysis 후보로 연결된다"),
        ("change_direction", "상황에 맞게 방향을 바꿔본다", "change_adaptation",
         "달라진 상황에 맞춰 방향을 바꾸는 행동이 드러나 change_adaptation 후보로 연결된다"),
        ("keep_original", "원래 방향을 그대로 유지한다", "persistence_completion",
         "어려움에도 원래 방향을 끝까지 유지하려는 행동이 드러나 persistence_completion 후보로 연결된다"),
        ("ask_around", "주변에 어떻게 하면 좋을지 물어본다", "collaboration_preference",
         "판단이 어려운 상황에서 주변과 상의하는 행동이 드러나 collaboration_preference 후보로 연결된다"),
        ("note_and_pause", "일단 상황을 기록해두고 지켜본다", None,
         "기록하고 지켜보는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
    ],
    "team_role_share": [
        ("say_mismatch", "팀에게 상황이 다르다고 이야기한다", "opinion_expression",
         "실제 상황과 다르다는 생각을 적극적으로 이야기하는 행동이 드러나 opinion_expression 후보로 연결된다"),
        ("adjust_role", "필요한 역할에 맞게 내 역할을 조정한다", "change_adaptation",
         "달라진 필요에 맞게 스스로 역할을 조정하는 행동이 드러나 change_adaptation 후보로 연결된다"),
        ("finish_original", "맡은 역할은 그대로 끝까지 해낸다", "persistence_completion",
         "상황이 달라져도 맡은 몫을 끝까지 해내려는 행동이 드러나 persistence_completion 후보로 연결된다"),
        ("find_middle", "다른 팀원과 역할을 어떻게 나눌지 조율한다", "opinion_mediation",
         "역할 재배분을 놓고 팀원과 조율하는 행동이 드러나 opinion_mediation 후보로 연결된다"),
        ("do_nothing_special", "특별히 다르게 하지 않고 넘어간다", None,
         "별다른 대응 없이 넘어가는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
    ],
}

_BACKUP_QUESTION_TEXT: dict[str, str] = {
    "idea_shaping": "친구들과 아이디어 회의를 하다가 갑자기 아무 말도 떠오르지 않을 때, 무엇을 가장 먼저 하나요?",
    "feedback_reading": "친구가 내 아이디어에 대해 예상과 다른 반응을 보였을 때 가장 먼저 하는 행동은 무엇인가요?",
    "resource_budgeting": "준비하던 중 예산이나 시간이 예상보다 부족하다는 걸 알게 되면 가장 먼저 하는 행동은 무엇인가요?",
    "plan_decision": "정했던 방향이 생각과 다르게 흘러갈 때 가장 먼저 하는 행동은 무엇인가요?",
    "team_role_share": "맡은 역할과 실제로 필요한 일이 다르다는 걸 알게 됐을 때 가장 먼저 하는 행동은 무엇인가요?",
}

_ANCHOR_IDS = [a.anchor_id for a in ANCHOR_PRESENTATIONS]

SEED_ANCHOR_VARIANTS: list[ContextPackSeedAnchorQuestion] = [
    ContextPackSeedAnchorQuestion(
        anchor_id=anchor_id,
        question=_question(f"{CONTEXT_ID}_seed_{anchor_id}", "seed_anchor", _SEED_QUESTION_TEXT[anchor_id], _SEED_OPTIONS[anchor_id]),
    )
    for anchor_id in _ANCHOR_IDS
]

ANCHOR_BACKUP_QUESTIONS: list[ContextPackAnchorBackupQuestion] = [
    ContextPackAnchorBackupQuestion(
        anchor_id=anchor_id,
        question=_question(f"{CONTEXT_ID}_backup_{anchor_id}", "anchor_backup", _BACKUP_QUESTION_TEXT[anchor_id], _BACKUP_OPTIONS[anchor_id]),
    )
    for anchor_id in _ANCHOR_IDS
]

OPTION_MAPPING_RATIONALES: list[OptionMappingRationale] = []
for _anchor_id in _ANCHOR_IDS:
    OPTION_MAPPING_RATIONALES.extend(
        _rationales(f"{CONTEXT_ID}_seed_{_anchor_id}", "seed_anchor", _SEED_OPTIONS[_anchor_id])
    )
    OPTION_MAPPING_RATIONALES.extend(
        _rationales(f"{CONTEXT_ID}_backup_{_anchor_id}", "anchor_backup", _BACKUP_OPTIONS[_anchor_id])
    )

CONTEXT_PACK = ContextPack(
    context_id=CONTEXT_ID,
    routing_blueprint=ROUTING_BLUEPRINT,
    anchor_presentations=ANCHOR_PRESENTATIONS,
    seed_anchor_variants=SEED_ANCHOR_VARIANTS,
    anchor_backup_questions=ANCHOR_BACKUP_QUESTIONS,
    option_mapping_rationales=OPTION_MAPPING_RATIONALES,
    direct_probe_candidates=[],
    forbidden_assumptions=[
        "학생이 실제 창업·사업 운영 경험이 있다는 전제",
        "학생이 많은 돈을 벌고 싶어한다는 전제",
        "학생이 이미 팀의 리더 역할을 맡고 있다는 전제",
    ],
    review_artifact_paths=[
        "data/reviews/context_packs/business_review_status.json",
        "outputs/context_packs/business_mapping_audit.md",
    ],
    pack_version="context_pack_technical_draft_v0.1",
)
