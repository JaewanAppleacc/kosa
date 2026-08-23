"""science(과학탐구) Context Pack — context-pack-technical 브랜치 초안.

담당 범위: 질문 콘텐츠와 Trait Mapping Draft만(`outputs/context_packs/
context_pack_development_guide.md` §1/§2). 구조는 `business.py`/`making.py`와
동일한 패턴이다 — Anchor 5개, Anchor당 Seed 1개·Backup 1개, 총 10개 질문·50개
Option을 이 파일 안에서 자기 완결적으로 정의한다.

작업 지시 준수 사항:
- 과학 지식 정답 문제를 만들지 않았다 — 모든 질문은 "왜/어떻게 반응하는가"를
  묻고, "무엇이 맞는가"를 묻지 않는다(정답이 있는 선택지가 없다).
- 실험 경험을 필수로 전제하지 않는다 — "실험", "실험 장비" 대신 "현상", "결과",
  "자료"처럼 일상적으로도 접할 수 있는 표현을 썼다.
- 원인 탐색·자료 비교·가설·관찰·불확실한 결과라는 5개 Anchor로 구성했다.

Trait는 24개 Ontology 밖의 것을 쓰지 않는다. 질문·선택지 검수 상태는 전부 TBD로
시작한다(`data/reviews/context_packs/science_review_status.json`).

Direct Probe 후보: 이번 초안에서는 만들지 않았다(0개). `uncertainty_tolerance`를
불확실한 결과(uncertain_result) Anchor에서 더 직접적으로 관찰할 Direct Probe
후보가 있으면 좋겠다는 메모를 `outputs/context_packs/science_mapping_audit.md`에
남겼다."""

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

CONTEXT_ID = "science"

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
        context_id=CONTEXT_ID, anchor_id="cause_exploring", label="원인 탐색",
        situation_terms=["원인", "이유", "탐색"],
        preferred_scenarios=["어떤 현상이 왜 일어나는지 궁금해하는 상황", "궁금한 이유를 찾아보는 상황"],
        forbidden_assumptions=["실험 장비 접근 경험", "정해진 정답을 안다는 전제"],
    ),
    ContextAnchorPresentation(
        context_id=CONTEXT_ID, anchor_id="data_comparing", label="자료 비교",
        situation_terms=["자료", "비교", "결과"],
        preferred_scenarios=["여러 자료나 결과를 비교해서 판단하는 상황"],
        forbidden_assumptions=["전문적인 통계 지식", "실험 데이터 분석 경험"],
    ),
    ContextAnchorPresentation(
        context_id=CONTEXT_ID, anchor_id="hypothesis_testing", label="가설 확인",
        situation_terms=["예상", "가설", "확인"],
        preferred_scenarios=["예상을 세우고 맞는지 확인해보는 상황"],
        forbidden_assumptions=["정식 실험 설계 경험"],
    ),
    ContextAnchorPresentation(
        context_id=CONTEXT_ID, anchor_id="observing", label="관찰·기록",
        situation_terms=["관찰", "기록", "변화"],
        preferred_scenarios=["현상을 꾸준히 지켜보고 기록하는 상황"],
        forbidden_assumptions=["실험 장비를 이용한 정밀 관찰 경험"],
    ),
    ContextAnchorPresentation(
        context_id=CONTEXT_ID, anchor_id="uncertain_result", label="불확실한 결과 다루기",
        situation_terms=["불확실", "애매한 결과", "판단"],
        preferred_scenarios=["실험이나 관찰 결과가 예상과 다르거나 애매한 상황"],
        forbidden_assumptions=["결과가 항상 명확하다는 전제"],
    ),
]

# ============================== Routing 질문 1개 ==============================

_ROUTING_QUESTION_ID = "science_routing_question"
_ROUTING_ROWS: list[tuple[str, str, str, str]] = [
    ("sc_cause", "어떤 현상이 왜 일어나는지 궁금해질 때", "cause_exploring", "원인 탐색"),
    ("sc_data", "여러 자료나 결과를 비교해볼 때", "data_comparing", "자료 비교"),
    ("sc_hypo", "예상을 세우고 맞는지 확인해볼 때", "hypothesis_testing", "가설 확인"),
    ("sc_observe", "현상을 꾸준히 지켜보고 기록할 때", "observing", "관찰·기록"),
    ("sc_uncertain", "결과가 예상과 다르거나 애매하게 나올 때", "uncertain_result", "불확실한 결과 다루기"),
]
ROUTING_BLUEPRINT = ContextRoutingBlueprint(
    context_id=CONTEXT_ID, blueprint_id="science_context_router_v1",
    option_mappings=[
        ContextRoutingOptionMapping(role_id=role_id, context_anchor=anchor_id, anchor_label=label)
        for role_id, _text, anchor_id, label in _ROUTING_ROWS
    ],
    base_question=FinalizedQuestion(
        question_id=_ROUTING_QUESTION_ID, context=CONTEXT_ID, target_traits=[], frame_id="context_routing",
        question_text="과학적으로 궁금한 것을 탐구할 때, 어떤 순간에 가장 몰입하나요?",
        options=[
            FinalizedOption(option_id=f"{_ROUTING_QUESTION_ID}_o{i}", role_id=role_id, text=text, primary_trait_delta={})
            for i, (role_id, text, _anchor_id, _label) in enumerate(_ROUTING_ROWS, start=1)
        ],
    ),
)

# ============================== Seed / Backup ==============================

_SEED_OPTIONS: dict[str, list[_OptionSpec]] = {
    "cause_exploring": [
        ("list_possible_causes", "가능한 이유들을 여러 개 떠올려본다", "causal_analysis",
         "결과의 가능한 원인을 스스로 여러 개 떠올려보는 행동이 드러나 causal_analysis 후보로 연결된다"),
        ("search_similar_case", "비슷한 경우가 있었는지 찾아본다", "information_comparison",
         "판단을 위해 비슷한 사례를 찾아 비교하는 행동이 드러나 information_comparison 후보로 연결된다"),
        ("ask_someone_know", "잘 아는 사람에게 물어본다", "collaboration_preference",
         "궁금증을 해결하려 다른 사람에게 묻는 행동이 드러나 collaboration_preference 후보로 연결된다"),
        ("just_curious", "궁금해하는 것으로 그친다", None,
         "궁금해하는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("find_common_thread", "여러 사례에서 공통점을 찾아본다", "pattern_finding",
         "여러 사례에서 반복되는 공통점을 찾는 행동이 드러나 pattern_finding 후보로 연결된다"),
    ],
    "data_comparing": [
        ("list_differences", "각 자료의 차이점을 정리해본다", "information_comparison",
         "여러 자료의 차이를 정리해서 비교하는 행동이 드러나 information_comparison 후보로 연결된다"),
        ("find_pattern_across", "여러 자료에서 반복되는 흐름을 찾아본다", "pattern_finding",
         "여러 자료를 관통하는 규칙을 찾는 행동이 드러나 pattern_finding 후보로 연결된다"),
        ("pick_most_reliable", "어떤 자료가 더 믿을만한지 스스로 판단한다", "independent_judgment",
         "스스로의 기준으로 자료의 신뢰도를 판단하는 행동이 드러나 independent_judgment 후보로 연결된다"),
        ("just_read_through", "일단 순서대로 읽어본다", None,
         "단순히 순서대로 읽는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("organize_visually", "표나 그림으로 정리해본다", "visual_expression",
         "정보를 시각적인 형태로 정리해 표현하는 행동이 드러나 visual_expression 후보로 연결된다"),
    ],
    "hypothesis_testing": [
        ("make_guess_first", "먼저 내 예상을 정해본다", "independent_judgment",
         "확인하기 전에 스스로의 기준으로 예상을 세우는 행동이 드러나 independent_judgment 후보로 연결된다"),
        ("think_why_guess", "왜 그렇게 될 거라 생각하는지 이유를 정리한다", "causal_analysis",
         "예상의 근거가 되는 이유를 정리하는 행동이 드러나 causal_analysis 후보로 연결된다"),
        ("test_right_away", "예상이 맞는지 바로 확인해본다", "immediate_execution",
         "생각한 예상을 바로 확인해보는 행동이 드러나 immediate_execution 후보로 연결된다"),
        ("no_guess", "예상하지 않고 결과만 지켜본다", None,
         "예상 없이 지켜보기만 하는 것은 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("compare_with_others_guess", "다른 사람의 예상과 비교해본다", "information_comparison",
         "내 예상을 다른 사람의 예상과 비교해보는 행동이 드러나 information_comparison 후보로 연결된다"),
    ],
    "observing": [
        ("record_carefully", "작은 변화도 놓치지 않고 꼼꼼히 기록한다", "detail_orientation",
         "작은 변화까지 놓치지 않고 기록하는 행동이 드러나 detail_orientation 후보로 연결된다"),
        ("note_pattern_over_time", "시간에 따라 어떻게 달라지는지 흐름을 살펴본다", "pattern_finding",
         "시간에 따른 변화의 흐름을 살펴보는 행동이 드러나 pattern_finding 후보로 연결된다"),
        ("record_minimum", "필요한 만큼만 간단히 기록한다", None,
         "최소한의 기록만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("plan_schedule", "언제 무엇을 확인할지 미리 계획한다", "planning",
         "관찰 시점과 순서를 미리 계획하는 행동이 드러나 planning 후보로 연결된다"),
        ("stick_to_end", "지루해도 끝까지 지켜본다", "persistence_completion",
         "지루함에도 끝까지 관찰을 지속하는 행동이 드러나 persistence_completion 후보로 연결된다"),
    ],
    "uncertain_result": [
        ("repeat_check", "다시 한번 확인해서 결과를 명확히 하려 한다", "detail_orientation",
         "결과를 명확히 하려 다시 세밀하게 확인하는 행동이 드러나 detail_orientation 후보로 연결된다"),
        ("accept_uncertain", "확실하지 않은 채로도 다음 단계로 넘어간다", "uncertainty_tolerance",
         "결과가 불확실한 채로도 다음 단계를 진행하는 행동이 드러나 uncertainty_tolerance 후보로 연결된다"),
        ("find_other_reason", "다른 원인이 있을 가능성을 생각해본다", "causal_analysis",
         "예상과 다른 결과의 다른 원인을 생각해보는 행동이 드러나 causal_analysis 후보로 연결된다"),
        ("just_report_as_is", "있는 그대로 결과만 전달한다", None,
         "결과를 그대로 전달하는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("discuss_with_others", "다른 사람과 이야기하며 의미를 찾아본다", "opinion_mediation",
         "애매한 결과의 의미를 다른 사람과 조율하며 찾는 행동이 드러나 opinion_mediation 후보로 연결된다"),
    ],
}

_SEED_QUESTION_TEXT: dict[str, str] = {
    "cause_exploring": "어떤 현상을 보고 '왜 이럴까?'라는 생각이 들 때, 나에게 가장 가까운 모습은 무엇인가요?",
    "data_comparing": "여러 자료나 결과를 놓고 비교할 때, 나에게 가장 가까운 모습은 무엇인가요?",
    "hypothesis_testing": "어떤 결과가 나올지 예상을 세워볼 때, 나에게 가장 가까운 모습은 무엇인가요?",
    "observing": "현상을 꾸준히 지켜보고 기록해야 할 때, 나에게 가장 가까운 모습은 무엇인가요?",
    "uncertain_result": "결과가 애매하거나 예상과 다를 때, 나에게 가장 가까운 모습은 무엇인가요?",
}

_BACKUP_OPTIONS: dict[str, list[_OptionSpec]] = {
    "cause_exploring": [
        ("accept_new_reason", "새로운 이유를 그대로 받아들인다", "change_adaptation",
         "내 생각과 다른 새로운 이유를 받아들이는 행동이 드러나 change_adaptation 후보로 연결된다"),
        ("double_check", "정말 맞는지 다시 확인해본다", "detail_orientation",
         "새로 알게 된 이유를 다시 세밀히 확인하는 행동이 드러나 detail_orientation 후보로 연결된다"),
        ("compare_with_mine", "내가 생각했던 이유와 비교해본다", "information_comparison",
         "새 이유와 원래 생각을 비교해보는 행동이 드러나 information_comparison 후보로 연결된다"),
        ("move_on_quick", "빠르게 다음으로 넘어간다", None,
         "빠르게 넘어가는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("explain_to_others", "왜 그런지 다른 사람에게 설명해본다", "verbal_expression",
         "알게 된 이유를 말로 풀어 설명하는 행동이 드러나 verbal_expression 후보로 연결된다"),
    ],
    "data_comparing": [
        ("find_why_different", "왜 결과가 다른지 이유를 생각해본다", "causal_analysis",
         "자료 간 차이가 생긴 이유를 생각해보는 행동이 드러나 causal_analysis 후보로 연결된다"),
        ("trust_majority", "더 많은 자료가 가리키는 쪽을 따른다", None,
         "단순히 다수를 따르는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("recheck_source", "자료의 출처를 다시 살펴본다", "detail_orientation",
         "자료 출처를 세밀히 다시 확인하는 행동이 드러나 detail_orientation 후보로 연결된다"),
        ("ask_others_view", "다른 사람은 어떻게 판단하는지 물어본다", "collaboration_preference",
         "판단이 어려운 상황에서 다른 사람 생각을 구하는 행동이 드러나 collaboration_preference 후보로 연결된다"),
        ("hold_judgment", "판단을 서두르지 않고 더 찾아본다", "uncertainty_tolerance",
         "결론이 불확실한 상태를 견디며 더 확인하는 행동이 드러나 uncertainty_tolerance 후보로 연결된다"),
    ],
    "hypothesis_testing": [
        ("figure_out_wrong_part", "어느 부분에서 예상이 어긋났는지 찾아본다", "causal_analysis",
         "예상이 틀린 지점을 짚어보는 행동이 드러나 causal_analysis 후보로 연결된다"),
        ("make_new_guess", "새로운 예상을 다시 세워본다", "change_adaptation",
         "틀린 예상을 반영해 새로운 예상을 세우는 행동이 드러나 change_adaptation 후보로 연결된다"),
        ("accept_quietly", "그냥 그런가보다 하고 넘어간다", None,
         "별다른 반응 없이 넘어가는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("keep_testing", "될 때까지 다시 확인해본다", "persistence_completion",
         "결과를 확인할 때까지 반복해서 시도하는 행동이 드러나 persistence_completion 후보로 연결된다"),
        ("note_result", "결과를 기록해둔다", "detail_orientation",
         "결과를 세밀하게 기록해두는 행동이 드러나 detail_orientation 후보로 연결된다"),
    ],
    "observing": [
        ("record_change_detail", "그 변화를 자세히 기록해둔다", "detail_orientation",
         "예상 못한 변화를 자세히 기록하는 행동이 드러나 detail_orientation 후보로 연결된다"),
        ("guess_cause_change", "왜 그런 변화가 생겼는지 생각해본다", "causal_analysis",
         "변화의 원인을 스스로 생각해보는 행동이 드러나 causal_analysis 후보로 연결된다"),
        ("keep_watching", "계속 지켜보며 어떻게 되는지 확인한다", "uncertainty_tolerance",
         "결과가 불확실한 상태에서도 계속 지켜보는 행동이 드러나 uncertainty_tolerance 후보로 연결된다"),
        ("ignore_change", "큰 변화가 아니면 넘어간다", None,
         "사소한 변화를 넘기는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("tell_someone", "이 사실을 다른 사람에게 알린다", "verbal_expression",
         "관찰한 내용을 다른 사람에게 말로 전달하는 행동이 드러나 verbal_expression 후보로 연결된다"),
    ],
    "uncertain_result": [
        ("state_limitation", "확실하지 않은 부분을 그대로 밝히고 말한다", "opinion_expression",
         "불확실한 부분을 숨기지 않고 밝혀 말하는 행동이 드러나 opinion_expression 후보로 연결된다"),
        ("find_more_evidence", "조금이라도 더 근거를 찾아본다", "information_comparison",
         "판단을 위해 추가 근거를 찾아 비교하는 행동이 드러나 information_comparison 후보로 연결된다"),
        ("just_finish", "일단 정해진 대로 마무리한다", None,
         "정해진 대로 마무리하는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("proceed_despite_unsure", "불확실해도 일단 진행한다", "uncertainty_tolerance",
         "불확실함을 감수하고 진행하는 행동이 드러나 uncertainty_tolerance 후보로 연결된다"),
        ("organize_logically", "알고 있는 것들을 논리적으로 정리한다", "systems_thinking",
         "가진 정보를 논리적 구조로 정리하는 행동이 드러나 systems_thinking 후보로 연결된다"),
    ],
}

_BACKUP_QUESTION_TEXT: dict[str, str] = {
    "cause_exploring": "궁금했던 이유를 찾았는데 내 생각과 달랐을 때 가장 먼저 하는 행동은 무엇인가요?",
    "data_comparing": "자료들이 서로 다른 결과를 보여줄 때 가장 먼저 하는 행동은 무엇인가요?",
    "hypothesis_testing": "세운 예상이 틀렸다는 걸 확인했을 때 가장 먼저 하는 행동은 무엇인가요?",
    "observing": "지켜보던 중 예상 못한 변화가 생겼을 때 가장 먼저 하는 행동은 무엇인가요?",
    "uncertain_result": "결과가 확실하지 않은 상태로 발표나 정리를 해야 할 때 가장 먼저 하는 행동은 무엇인가요?",
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
        "정답이 정해진 과학 지식 문제로 만드는 것",
        "학생이 실험 장비를 다뤄본 경험이 있다는 전제",
        "결과가 항상 명확하게 나온다는 전제",
    ],
    review_artifact_paths=[
        "data/reviews/context_packs/science_review_status.json",
        "outputs/context_packs/science_mapping_audit.md",
    ],
    pack_version="context_pack_technical_draft_v0.1",
)
