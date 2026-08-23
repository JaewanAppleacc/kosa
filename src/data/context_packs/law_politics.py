"""law_politics(법·정치·시사) Context Pack — context-pack-technical 브랜치 초안.

담당 범위: 질문 콘텐츠와 Trait Mapping Draft만(`outputs/context_packs/
context_pack_development_guide.md` §1/§2). 구조는 다른 3개 Pack과 동일한
패턴이다 — Anchor 5개, Anchor당 Seed 1개·Backup 1개, 총 10개 질문·50개 Option을
이 파일 안에서 자기 완결적으로 정의한다.

작업 지시 준수 사항(가장 주의가 필요한 Context):
- 정치 성향·이념·정당 선호를 추론하지 않는다 — 질문·선택지 어디에도 특정 정당,
  진보/보수 같은 이념 축, 실제 정치 이슈(예: 특정 법안·정책 찬반)를 언급하지
  않는다. 전부 "규칙", "자료", "주장", "결정"처럼 일반화된 상황만 다룬다.
  실제 정치 성향 데이터를 다루지 않으므로, 정치 성향 Trait 자체도 Ontology에
  존재하지 않는다(causal_analysis·opinion_mediation 등 일반 사고·의사소통
  Trait만 관찰한다).
- 도덕적으로 옳은 답을 만들지 않는다 — 선택지 사이에 "이게 정답"으로 보일 만한
  위계를 두지 않았다(전부 실제로 있을 법한 행동이고 Rationale도 우열을 매기지
  않는다).
- 규칙 충돌·자료 해석·서로 다른 주장·공공 의사결정·규칙 만들기라는 5개 Anchor로
  구성했다.

Trait는 24개 Ontology 밖의 것을 쓰지 않는다. 질문·선택지 검수 상태는 전부 TBD로
시작한다(`data/reviews/context_packs/law_politics_review_status.json`).

Direct Probe 후보: 이번 초안에서는 만들지 않았다(0개). `emotional_interpretation`을
공공 의사결정(public_decision) Anchor에서 더 직접적으로 관찰할 Direct Probe
후보가 있으면 좋겠다는 메모를 `outputs/context_packs/
law_politics_mapping_audit.md`에 남겼다."""

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

CONTEXT_ID = "law_politics"

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
        context_id=CONTEXT_ID, anchor_id="rule_conflict", label="규칙 충돌",
        situation_terms=["규칙", "기준", "충돌"],
        preferred_scenarios=["서로 다른 규칙이나 기준이 부딪히는 상황"],
        forbidden_assumptions=["특정 정당·이념 판단", "정치적 올바름의 정답 전제"],
    ),
    ContextAnchorPresentation(
        context_id=CONTEXT_ID, anchor_id="source_reading", label="자료 해석",
        situation_terms=["뉴스", "자료", "해석"],
        preferred_scenarios=["뉴스나 자료를 읽고 의미를 해석하는 상황"],
        forbidden_assumptions=["특정 언론사·정치 성향 판단"],
    ),
    ContextAnchorPresentation(
        context_id=CONTEXT_ID, anchor_id="differing_claims", label="다른 주장 다루기",
        situation_terms=["주장", "의견", "토론"],
        preferred_scenarios=["의견이 다른 여러 주장을 접하는 상황"],
        forbidden_assumptions=["특정 입장이 도덕적으로 옳다는 전제"],
    ),
    ContextAnchorPresentation(
        context_id=CONTEXT_ID, anchor_id="public_decision", label="공공 의사결정 참여",
        situation_terms=["결정", "학급·모의국회", "영향"],
        preferred_scenarios=["여러 사람에게 영향을 주는 결정에 참여하는 상황(예: 학급 규칙, 모의국회)"],
        forbidden_assumptions=["실제 선거·정당 활동 경험"],
    ),
    ContextAnchorPresentation(
        context_id=CONTEXT_ID, anchor_id="rule_making", label="규칙 만들기",
        situation_terms=["규칙", "기준", "제정"],
        preferred_scenarios=["새로운 규칙이나 기준을 정해야 하는 상황"],
        forbidden_assumptions=["법률 제정 실무 경험"],
    ),
]

# ============================== Routing 질문 1개 ==============================

_ROUTING_QUESTION_ID = "law_politics_routing_question"
_ROUTING_ROWS: list[tuple[str, str, str, str]] = [
    ("lp_conflict", "서로 다른 규칙이나 기준이 부딪힐 때", "rule_conflict", "규칙 충돌"),
    ("lp_source", "뉴스나 자료를 읽고 의미를 해석할 때", "source_reading", "자료 해석"),
    ("lp_claims", "의견이 다른 여러 주장을 접할 때", "differing_claims", "다른 주장 다루기"),
    ("lp_public", "여러 사람에게 영향을 주는 결정에 참여할 때", "public_decision", "공공 의사결정 참여"),
    ("lp_rule", "새로운 규칙이나 기준을 정할 때", "rule_making", "규칙 만들기"),
]
ROUTING_BLUEPRINT = ContextRoutingBlueprint(
    context_id=CONTEXT_ID, blueprint_id="law_politics_context_router_v1",
    option_mappings=[
        ContextRoutingOptionMapping(role_id=role_id, context_anchor=anchor_id, anchor_label=label)
        for role_id, _text, anchor_id, label in _ROUTING_ROWS
    ],
    base_question=FinalizedQuestion(
        question_id=_ROUTING_QUESTION_ID, context=CONTEXT_ID, target_traits=[], frame_id="context_routing",
        question_text="사회 이슈나 규칙·제도에 대해 생각해볼 때, 어떤 순간에 가장 몰입하나요?",
        options=[
            FinalizedOption(option_id=f"{_ROUTING_QUESTION_ID}_o{i}", role_id=role_id, text=text, primary_trait_delta={})
            for i, (role_id, text, _anchor_id, _label) in enumerate(_ROUTING_ROWS, start=1)
        ],
    ),
)

# ============================== Seed / Backup ==============================

_SEED_OPTIONS: dict[str, list[_OptionSpec]] = {
    "rule_conflict": [
        ("compare_rules", "각 규칙이 왜 만들어졌는지 이유를 비교해본다", "causal_analysis",
         "서로 다른 규칙이 생긴 이유를 비교해보는 행동이 드러나 causal_analysis 후보로 연결된다"),
        ("find_middle_ground", "양쪽이 받아들일 수 있는 지점을 찾아본다", "opinion_mediation",
         "충돌하는 두 규칙 사이에서 접점을 찾는 행동이 드러나 opinion_mediation 후보로 연결된다"),
        ("pick_one_clearly", "내 기준으로 어느 쪽이 맞는지 정한다", "independent_judgment",
         "스스로의 기준으로 하나를 정하는 행동이 드러나 independent_judgment 후보로 연결된다"),
        ("just_follow_stronger", "더 힘 있는 규칙을 그냥 따른다", None,
         "힘이 센 쪽을 그냥 따르는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("explain_both_sides", "양쪽 입장을 각각 정리해서 설명해본다", "verbal_expression",
         "양쪽 입장을 말로 정리해 설명하는 행동이 드러나 verbal_expression 후보로 연결된다"),
    ],
    "source_reading": [
        ("check_source_reliability", "이 정보가 어디서 나왔는지 확인해본다", "information_comparison",
         "정보를 받아들이기 전에 출처를 확인·비교하는 행동이 드러나 information_comparison 후보로 연결된다"),
        ("recall_similar_case", "비슷한 사건이 이전에도 있었는지 떠올려본다", "pattern_finding",
         "지금 사건을 이전 사례와 연결해보는 행동이 드러나 pattern_finding 후보로 연결된다"),
        ("form_own_view", "읽은 내용을 바탕으로 내 생각을 정리한다", "independent_judgment",
         "읽은 내용을 바탕으로 스스로 생각을 정리하는 행동이 드러나 independent_judgment 후보로 연결된다"),
        ("just_skim", "제목 위주로 훑어본다", None,
         "제목만 훑어보는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("share_with_friend", "읽은 내용을 친구에게 이야기해본다", "verbal_expression",
         "읽은 내용을 말로 풀어 다른 사람에게 전달하는 행동이 드러나 verbal_expression 후보로 연결된다"),
    ],
    "differing_claims": [
        ("list_each_reason", "각 주장의 근거를 하나씩 정리해본다", "information_comparison",
         "여러 주장의 근거를 정리해서 비교하는 행동이 드러나 information_comparison 후보로 연결된다"),
        ("find_common_ground", "공통된 부분이 있는지 찾아본다", "opinion_mediation",
         "다른 주장들 사이의 공통점을 찾는 행동이 드러나 opinion_mediation 후보로 연결된다"),
        ("decide_my_position", "내 입장을 스스로 정리해본다", "independent_judgment",
         "여러 주장을 접한 뒤 스스로 입장을 정리하는 행동이 드러나 independent_judgment 후보로 연결된다"),
        ("stay_neutral", "특별히 입장을 정하지 않는다", None,
         "입장을 정하지 않는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("voice_opinion", "내 생각을 다른 사람에게 말해본다", "opinion_expression",
         "정리한 생각을 다른 사람에게 적극적으로 말하는 행동이 드러나 opinion_expression 후보로 연결된다"),
    ],
    "public_decision": [
        ("consider_all_affected", "이 결정이 누구에게 어떤 영향을 줄지 생각해본다", "systems_thinking",
         "결정이 여러 사람에게 미치는 영향을 구조적으로 생각해보는 행동이 드러나 systems_thinking 후보로 연결된다"),
        ("propose_idea", "내 생각을 먼저 제안해본다", "opinion_expression",
         "결정 과정에서 생각을 먼저 적극적으로 제안하는 행동이 드러나 opinion_expression 후보로 연결된다"),
        ("gather_others_view", "다른 사람들의 의견을 먼저 모아본다", "collaboration_preference",
         "결정 전에 다른 사람들의 의견을 모으는 행동이 드러나 collaboration_preference 후보로 연결된다"),
        ("just_vote", "제시된 것 중에 하나를 고른다", None,
         "제시된 선택지 중 고르기만 하는 것은 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("mediate_disagreement", "의견이 갈릴 때 조율을 시도한다", "opinion_mediation",
         "의견이 갈리는 상황에서 조율을 시도하는 행동이 드러나 opinion_mediation 후보로 연결된다"),
    ],
    "rule_making": [
        ("think_purpose_first", "이 규칙이 왜 필요한지부터 정리한다", "causal_analysis",
         "규칙을 만들기 전에 필요한 이유를 먼저 정리하는 행동이 드러나 causal_analysis 후보로 연결된다"),
        ("draft_clear_rule", "누구나 이해할 수 있게 구체적으로 정한다", "detail_orientation",
         "규칙을 구체적이고 명확하게 정리하는 행동이 드러나 detail_orientation 후보로 연결된다"),
        ("consider_exceptions", "예외가 생길 상황까지 미리 생각해본다", "systems_thinking",
         "규칙이 적용될 다양한 상황과 예외를 구조적으로 살펴보는 행동이 드러나 systems_thinking 후보로 연결된다"),
        ("copy_existing", "이미 있는 규칙을 그대로 가져온다", None,
         "기존 규칙을 그대로 가져오는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("ask_input", "다른 사람 의견을 먼저 물어본다", "collaboration_preference",
         "규칙을 만들기 전에 다른 사람 의견을 구하는 행동이 드러나 collaboration_preference 후보로 연결된다"),
    ],
}

_SEED_QUESTION_TEXT: dict[str, str] = {
    "rule_conflict": "서로 다른 규칙이나 기준이 부딪히는 상황을 봤을 때, 나에게 가장 가까운 모습은 무엇인가요?",
    "source_reading": "뉴스나 기사 자료를 읽을 때, 나에게 가장 가까운 모습은 무엇인가요?",
    "differing_claims": "의견이 서로 다른 여러 주장을 접했을 때, 나에게 가장 가까운 모습은 무엇인가요?",
    "public_decision": "여러 사람에게 영향을 주는 결정(예: 학급 규칙, 모의국회)에 참여할 때, 나에게 가장 가까운 모습은 무엇인가요?",
    "rule_making": "새로운 규칙이나 기준을 정해야 할 때, 나에게 가장 가까운 모습은 무엇인가요?",
}

_BACKUP_OPTIONS: dict[str, list[_OptionSpec]] = {
    "rule_conflict": [
        ("question_rule", "왜 이 규칙이 필요한지 다시 생각해본다", "causal_analysis",
         "지금 안 맞는 규칙이 왜 필요한지 다시 생각해보는 행동이 드러나 causal_analysis 후보로 연결된다"),
        ("suggest_change", "바꿔야 할 부분을 이야기해본다", "opinion_expression",
         "바뀌어야 할 부분을 적극적으로 이야기하는 행동이 드러나 opinion_expression 후보로 연결된다"),
        ("follow_anyway", "일단 정해진 대로 따른다", None,
         "규칙을 그대로 따르는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("find_exception_case", "예외가 인정될 수 있는 경우인지 살펴본다", "systems_thinking",
         "규칙 적용의 예외 가능성을 구조적으로 살펴보는 행동이 드러나 systems_thinking 후보로 연결된다"),
        ("ask_others_think", "다른 사람들은 어떻게 생각하는지 물어본다", "collaboration_preference",
         "판단이 어려운 상황에서 다른 사람 생각을 구하는 행동이 드러나 collaboration_preference 후보로 연결된다"),
    ],
    "source_reading": [
        ("find_diff_detail", "구체적으로 어떤 부분이 다른지 짚어본다", "detail_orientation",
         "자료 간 차이를 세부적으로 짚어보는 행동이 드러나 detail_orientation 후보로 연결된다"),
        ("guess_why_diff", "왜 다르게 전달됐는지 이유를 생각해본다", "causal_analysis",
         "자료마다 내용이 다른 이유를 생각해보는 행동이 드러나 causal_analysis 후보로 연결된다"),
        ("trust_familiar", "평소 자주 보던 자료를 믿는다", None,
         "익숙한 자료를 그대로 신뢰하는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("look_for_more", "다른 자료를 더 찾아본다", "information_comparison",
         "판단을 위해 추가 자료를 찾아 비교하는 행동이 드러나 information_comparison 후보로 연결된다"),
        ("hold_off_judging", "판단을 미루고 더 지켜본다", "uncertainty_tolerance",
         "결론이 불확실한 상태를 견디며 더 지켜보는 행동이 드러나 uncertainty_tolerance 후보로 연결된다"),
    ],
    "differing_claims": [
        ("reconsider_position", "내 입장을 다시 생각해본다", "change_adaptation",
         "더 설득력 있는 주장을 접하고 입장을 다시 생각하는 행동이 드러나 change_adaptation 후보로 연결된다"),
        ("ask_more_evidence", "그 주장의 근거를 더 물어본다", "information_comparison",
         "주장을 받아들이기 전에 근거를 더 확인하는 행동이 드러나 information_comparison 후보로 연결된다"),
        ("keep_my_position", "그래도 원래 생각을 유지한다", "persistence_completion",
         "다른 의견을 접해도 원래 입장을 유지하는 행동이 드러나 persistence_completion 후보로 연결된다"),
        ("say_nothing", "별다른 반응 없이 듣기만 한다", None,
         "반응 없이 듣기만 하는 것은 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("find_middle_view", "두 입장을 절충할 수 있는지 생각해본다", "opinion_mediation",
         "서로 다른 두 입장의 절충점을 찾는 행동이 드러나 opinion_mediation 후보로 연결된다"),
    ],
    "public_decision": [
        ("listen_complaint", "불만이 어디서 오는지 들어본다", "emotional_interpretation",
         "불만을 가진 사람의 마음을 헤아려 들어보는 행동이 드러나 emotional_interpretation 후보로 연결된다"),
        ("explain_reason", "왜 그렇게 결정했는지 설명한다", "opinion_expression",
         "결정의 이유를 적극적으로 설명하는 행동이 드러나 opinion_expression 후보로 연결된다"),
        ("adjust_decision", "필요하면 결정을 조정한다", "change_adaptation",
         "불만을 반영해 결정을 조정하는 행동이 드러나 change_adaptation 후보로 연결된다"),
        ("let_it_be", "시간이 지나면 괜찮아질 거라 생각한다", None,
         "상황을 그대로 두는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("find_compromise", "절충안을 찾아본다", "opinion_mediation",
         "불만을 가진 쪽과 절충안을 찾는 행동이 드러나 opinion_mediation 후보로 연결된다"),
    ],
    "rule_making": [
        ("find_gap", "규칙의 어느 부분이 문제인지 찾아본다", "causal_analysis",
         "문제가 생긴 규칙의 원인 부분을 찾아보는 행동이 드러나 causal_analysis 후보로 연결된다"),
        ("revise_rule", "문제된 부분을 고쳐본다", "change_adaptation",
         "드러난 문제에 맞춰 규칙을 고치는 행동이 드러나 change_adaptation 후보로 연결된다"),
        ("keep_rule", "일단 정해진 대로 유지한다", "persistence_completion",
         "문제가 생겨도 정해진 규칙을 유지하려는 행동이 드러나 persistence_completion 후보로 연결된다"),
        ("ignore_issue", "큰 문제가 아니면 넘어간다", None,
         "사소한 문제를 넘기는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("discuss_fix", "다른 사람과 함께 개선 방법을 논의한다", "collaboration_preference",
         "규칙 개선 방법을 다른 사람과 함께 논의하는 행동이 드러나 collaboration_preference 후보로 연결된다"),
    ],
}

_BACKUP_QUESTION_TEXT: dict[str, str] = {
    "rule_conflict": "정해진 규칙이 지금 상황에는 안 맞는다고 느껴질 때 가장 먼저 하는 행동은 무엇인가요?",
    "source_reading": "같은 사건을 다룬 기사인데 내용이 자료마다 다를 때 가장 먼저 하는 행동은 무엇인가요?",
    "differing_claims": "토론 중 내 생각과 다른 주장이 더 설득력 있게 느껴질 때 가장 먼저 하는 행동은 무엇인가요?",
    "public_decision": "내가 참여한 결정이 일부 사람들에게 불만을 샀을 때 가장 먼저 하는 행동은 무엇인가요?",
    "rule_making": "만든 규칙이 실제로 적용됐을 때 문제가 생긴 걸 알게 되면 가장 먼저 하는 행동은 무엇인가요?",
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
        "특정 정당·정치 성향·이념 축을 전제하거나 추론하는 것",
        "특정 입장이 도덕적으로 옳다고 전제하는 것",
        "실제 선거·정당 활동 경험을 전제하는 것",
    ],
    review_artifact_paths=[
        "data/reviews/context_packs/law_politics_review_status.json",
        "outputs/context_packs/law_politics_mapping_audit.md",
    ],
    pack_version="context_pack_technical_draft_v0.1",
)
