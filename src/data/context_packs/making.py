"""making(만들기·코딩) Context Pack — context-pack-technical 브랜치 초안.

담당 범위: 질문 콘텐츠와 Trait Mapping Draft만(`outputs/context_packs/
context_pack_development_guide.md` §1/§2). 구조는 `business.py`와 동일한
패턴이다 — Anchor 5개, Anchor당 Seed 1개·Backup 1개, 총 10개 질문·50개 Option을
이 파일 안에서 자기 완결적으로 정의한다.

작업 지시 준수 사항:
- 코딩 경험을 필수로 전제하지 않는다 — 질문 문구는 "도구·프로그램"처럼 소프트웨어
  뿐 아니라 물리적 만들기(조립·장비)에도 적용 가능한 표현을 썼고, "코딩"이라는
  단어 자체를 질문·선택지에 쓰지 않았다.
- 코딩을 좋아하면 분석적이라는 자동 연결을 하지 않는다 — 5개 Anchor에 걸쳐
  causal_analysis 외에도 visual_expression·audience_response_prediction·
  novelty_seeking 등 다양한 Trait를 배분했다(아래 참고).
- 조립·도구·오류·개선·사용자 관점의 5개 Anchor로 구성했다.

Trait는 24개 Ontology 밖의 것을 쓰지 않는다. 질문·선택지 검수 상태는 전부 TBD로
시작한다(`data/reviews/context_packs/making_review_status.json`).

Direct Probe 후보: 이번 초안에서는 만들지 않았다(0개). `tool_utilization`을
오류 해결(error_fixing) Anchor에서 더 직접적으로 관찰할 Direct Probe 후보가
있으면 좋겠다는 메모를 `outputs/context_packs/making_mapping_audit.md`에
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

CONTEXT_ID = "making"

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
        context_id=CONTEXT_ID, anchor_id="assembling", label="조립·구성",
        situation_terms=["조립", "구성", "재료"],
        preferred_scenarios=["여러 부품을 맞춰 완성하는 상황", "구조를 짜 맞추는 상황"],
        forbidden_assumptions=["코딩 경험", "전자기기 조립 경험"],
    ),
    ContextAnchorPresentation(
        context_id=CONTEXT_ID, anchor_id="tool_using", label="도구 다루기",
        situation_terms=["도구", "사용법", "기능"],
        preferred_scenarios=["새로운 도구의 기능을 익히는 상황", "도구로 원하는 결과를 만들어보는 상황"],
        forbidden_assumptions=["특정 프로그래밍 언어 경험"],
    ),
    ContextAnchorPresentation(
        context_id=CONTEXT_ID, anchor_id="error_fixing", label="오류 해결",
        situation_terms=["오류", "원인", "고치기"],
        preferred_scenarios=["예상과 다르게 작동할 때 원인을 찾는 상황", "오류를 하나씩 점검하는 상황"],
        forbidden_assumptions=["프로그래밍 디버깅 경험", "전문적인 오류 해결 능력"],
    ),
    ContextAnchorPresentation(
        context_id=CONTEXT_ID, anchor_id="improving", label="개선하기",
        situation_terms=["개선", "수정", "다듬기"],
        preferred_scenarios=["완성한 것을 다시 살펴보고 고치는 상황", "더 나은 방법을 찾는 상황"],
        forbidden_assumptions=["완벽주의 성향을 기본으로 전제"],
    ),
    ContextAnchorPresentation(
        context_id=CONTEXT_ID, anchor_id="user_perspective", label="사용자 관점",
        situation_terms=["사용자", "편의", "반응"],
        preferred_scenarios=["다른 사람이 사용하는 모습을 상상해보는 상황", "사용자 의견을 반영하는 상황"],
        forbidden_assumptions=["실제 사용자 테스트 경험"],
    ),
]

# ============================== Routing 질문 1개 ==============================

_ROUTING_QUESTION_ID = "making_routing_question"
_ROUTING_ROWS: list[tuple[str, str, str, str]] = [
    ("mk_assemble", "부품이나 재료를 맞춰가며 완성해갈 때", "assembling", "조립·구성"),
    ("mk_tool", "새로운 도구나 프로그램의 기능을 익힐 때", "tool_using", "도구 다루기"),
    ("mk_error", "뜻대로 되지 않는 부분의 원인을 찾을 때", "error_fixing", "오류 해결"),
    ("mk_improve", "한 번 만든 것을 더 낫게 고칠 때", "improving", "개선하기"),
    ("mk_user", "다른 사람이 쓰는 모습을 상상하며 만들 때", "user_perspective", "사용자 관점"),
]
ROUTING_BLUEPRINT = ContextRoutingBlueprint(
    context_id=CONTEXT_ID, blueprint_id="making_context_router_v1",
    option_mappings=[
        ContextRoutingOptionMapping(role_id=role_id, context_anchor=anchor_id, anchor_label=label)
        for role_id, _text, anchor_id, label in _ROUTING_ROWS
    ],
    base_question=FinalizedQuestion(
        question_id=_ROUTING_QUESTION_ID, context=CONTEXT_ID, target_traits=[], frame_id="context_routing",
        question_text="직접 도구나 코드로 무언가를 만들어볼 때, 어떤 순간에 가장 몰입하나요?",
        options=[
            FinalizedOption(option_id=f"{_ROUTING_QUESTION_ID}_o{i}", role_id=role_id, text=text, primary_trait_delta={})
            for i, (role_id, text, _anchor_id, _label) in enumerate(_ROUTING_ROWS, start=1)
        ],
    ),
)

# ============================== Seed / Backup ==============================

_SEED_OPTIONS: dict[str, list[_OptionSpec]] = {
    "assembling": [
        ("plan_order", "어떤 순서로 맞출지 먼저 계획을 세운다", "planning",
         "시작 전에 조립 순서를 스스로 계획하는 행동이 드러나 planning 후보로 연결된다"),
        ("try_hands_on", "일단 손으로 이것저것 맞춰보며 진행한다", "immediate_execution",
         "계획보다 먼저 직접 시도해보는 행동이 드러나 immediate_execution 후보로 연결된다"),
        ("check_detail", "각 부분이 딱 맞는지 꼼꼼히 확인한다", "detail_orientation",
         "세부 부분까지 꼼꼼히 확인하는 행동이 드러나 detail_orientation 후보로 연결된다"),
        ("follow_guide", "설명서나 정해진 방법을 그대로 따른다", None,
         "정해진 절차를 그대로 따르는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("change_method", "안 맞으면 다른 방법을 시도해본다", "change_adaptation",
         "예상과 다를 때 방법을 바꿔 대응하는 행동이 드러나 change_adaptation 후보로 연결된다"),
    ],
    "tool_using": [
        ("explore_freely", "이것저것 눌러보며 기능을 직접 익힌다", "immediate_execution",
         "설명 없이도 직접 시도하며 기능을 익히는 행동이 드러나 immediate_execution 후보로 연결된다"),
        ("read_first", "사용법을 먼저 찾아보고 시작한다", "information_comparison",
         "시작 전에 정보를 찾아 확인하는 행동이 드러나 information_comparison 후보로 연결된다"),
        ("find_new_use", "원래 용도 말고 다르게 써볼 방법을 찾아본다", "novelty_seeking",
         "정해진 용도를 벗어나 새로운 활용을 찾는 행동이 드러나 novelty_seeking 후보로 연결된다"),
        ("ask_experienced", "써본 사람에게 물어본다", "collaboration_preference",
         "경험이 있는 사람에게 직접 물어보는 행동이 드러나 collaboration_preference 후보로 연결된다"),
        ("use_minimum", "필요한 기능만 최소한으로 쓴다", None,
         "필요한 만큼만 최소한으로 쓰는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
    ],
    "error_fixing": [
        ("trace_cause", "어느 단계에서 문제가 생겼는지 하나씩 짚어본다", "causal_analysis",
         "문제가 생긴 지점을 단계별로 짚어보는 행동이 드러나 causal_analysis 후보로 연결된다"),
        ("guess_pattern", "이전에 비슷한 문제가 있었는지 떠올려본다", "pattern_finding",
         "과거 사례에서 반복되는 규칙을 떠올리는 행동이 드러나 pattern_finding 후보로 연결된다"),
        ("try_random_fix", "일단 이것저것 바꿔보며 확인한다", "immediate_execution",
         "생각보다 먼저 직접 바꿔보며 확인하는 행동이 드러나 immediate_execution 후보로 연결된다"),
        ("stay_calm", "당황하지 않고 잠시 지켜본다", None,
         "단순히 지켜보는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("search_reference", "비슷한 사례나 자료를 찾아본다", "information_comparison",
         "해결을 위해 참고 자료를 찾아 비교하는 행동이 드러나 information_comparison 후보로 연결된다"),
    ],
    "improving": [
        ("find_better_way", "더 나은 방법이 없을지 계속 고민한다", "persistence_completion",
         "만족하지 않고 계속 더 나은 방법을 찾는 행동이 드러나 persistence_completion 후보로 연결된다"),
        ("simplify_structure", "복잡한 부분을 더 단순한 구조로 정리한다", "systems_thinking",
         "전체 구조를 단순하게 재구성하는 행동이 드러나 systems_thinking 후보로 연결된다"),
        ("change_look", "겉모습이나 디자인을 다르게 바꿔본다", "visual_expression",
         "시각적으로 다르게 표현해보는 행동이 드러나 visual_expression 후보로 연결된다"),
        ("leave_it", "지금 상태로 충분하다고 생각하고 둔다", None,
         "현재 상태에 만족하고 그대로 두는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("ask_opinion", "다른 사람에게 의견을 물어본다", "collaboration_preference",
         "개선을 위해 다른 사람 의견을 구하는 행동이 드러나 collaboration_preference 후보로 연결된다"),
    ],
    "user_perspective": [
        ("imagine_use", "그 사람이 어떻게 쓸지 미리 상상해본다", "audience_response_prediction",
         "실제 사용 전에 사용자의 행동을 미리 예상해보는 행동이 드러나 audience_response_prediction 후보로 연결된다"),
        ("ask_directly", "실제로 써보고 어떤지 물어본다", "collaboration_preference",
         "사용자에게 직접 사용해보게 하고 의견을 구하는 행동이 드러나 collaboration_preference 후보로 연결된다"),
        ("simplify_use", "더 쉽게 쓸 수 있도록 단순하게 만든다", "systems_thinking",
         "사용 과정을 단순한 구조로 재구성하는 행동이 드러나 systems_thinking 후보로 연결된다"),
        ("not_consider", "그 부분은 크게 신경 쓰지 않는다", None,
         "신경 쓰지 않는 태도만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("add_new_feature", "새로운 기능을 더 추가해본다", "creative_ideation",
         "스스로 새로운 기능을 구상해 더하는 행동이 드러나 creative_ideation 후보로 연결된다"),
    ],
}

_SEED_QUESTION_TEXT: dict[str, str] = {
    "assembling": "여러 부품이나 재료를 맞춰서 무언가를 완성할 때, 나에게 가장 가까운 모습은 무엇인가요?",
    "tool_using": "새로운 도구나 프로그램을 처음 써볼 때, 나에게 가장 가까운 모습은 무엇인가요?",
    "error_fixing": "만든 것이 생각대로 작동하지 않을 때, 나에게 가장 가까운 모습은 무엇인가요?",
    "improving": "한 번 완성한 것을 다시 살펴볼 때, 나에게 가장 가까운 모습은 무엇인가요?",
    "user_perspective": "다른 사람이 내가 만든 것을 쓴다고 생각할 때, 나에게 가장 가까운 모습은 무엇인가요?",
}

_BACKUP_OPTIONS: dict[str, list[_OptionSpec]] = {
    "assembling": [
        ("recheck_steps", "처음부터 순서를 다시 확인한다", "detail_orientation",
         "문제 발생 시 처음부터 세부 순서를 다시 확인하는 행동이 드러나 detail_orientation 후보로 연결된다"),
        ("guess_cause", "왜 안 맞는지 이유를 생각해본다", "causal_analysis",
         "맞지 않는 원인을 스스로 생각해보는 행동이 드러나 causal_analysis 후보로 연결된다"),
        ("ask_someone", "아는 사람에게 물어본다", "collaboration_preference",
         "막혔을 때 다른 사람에게 도움을 구하는 행동이 드러나 collaboration_preference 후보로 연결된다"),
        ("leave_as_is", "일단 그대로 두고 넘어간다", None,
         "단순 방치는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("try_fit_again", "다른 방식으로 다시 맞춰본다", "persistence_completion",
         "포기하지 않고 다른 방식으로 다시 시도하는 행동이 드러나 persistence_completion 후보로 연결된다"),
    ],
    "tool_using": [
        ("try_new_feature", "바로 새 기능을 써본다", "novelty_seeking",
         "새로운 기능을 망설임 없이 시도하는 행동이 드러나 novelty_seeking 후보로 연결된다"),
        ("compare_before", "이전 방식과 무엇이 다른지 비교해본다", "information_comparison",
         "이전과 새로운 방식을 비교해보는 행동이 드러나 information_comparison 후보로 연결된다"),
        ("ignore_for_now", "당장은 그냥 쓰던 대로 쓴다", None,
         "기존 방식을 그대로 유지하는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("find_use_case", "이 기능을 어디에 쓰면 좋을지 생각해본다", "creative_ideation",
         "새 기능의 활용 방법을 스스로 구상하는 행동이 드러나 creative_ideation 후보로 연결된다"),
        ("master_it", "잘 쓸 수 있을 때까지 연습한다", "persistence_completion",
         "숙달될 때까지 연습을 지속하는 행동이 드러나 persistence_completion 후보로 연결된다"),
    ],
    "error_fixing": [
        ("keep_trying", "포기하지 않고 계속 시도한다", "persistence_completion",
         "오래 걸려도 포기하지 않고 계속 시도하는 행동이 드러나 persistence_completion 후보로 연결된다"),
        ("set_aside", "잠시 미뤄두고 다른 일을 한다", None,
         "잠시 미뤄두는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("ask_help", "다른 사람에게 도움을 요청한다", "collaboration_preference",
         "해결이 어려울 때 다른 사람에게 도움을 요청하는 행동이 드러나 collaboration_preference 후보로 연결된다"),
        ("rebuild_part", "그 부분을 처음부터 다시 만들어본다", "uncertainty_tolerance",
         "결과가 불확실해도 처음부터 다시 시도하는 행동이 드러나 uncertainty_tolerance 후보로 연결된다"),
        ("narrow_down", "문제를 작은 단위로 나눠서 하나씩 확인한다", "systems_thinking",
         "문제를 구조적으로 나누어 확인하는 행동이 드러나 systems_thinking 후보로 연결된다"),
    ],
    "improving": [
        ("list_issues", "아쉬운 부분들을 하나씩 정리해본다", "detail_orientation",
         "아쉬운 부분을 세부적으로 정리하는 행동이 드러나 detail_orientation 후보로 연결된다"),
        ("redo_soon", "바로 고치기 시작한다", "immediate_execution",
         "발견하자마자 바로 수정에 들어가는 행동이 드러나 immediate_execution 후보로 연결된다"),
        ("think_why_missed", "왜 처음엔 못 봤는지 생각해본다", "causal_analysis",
         "놓쳤던 이유를 스스로 되짚어보는 행동이 드러나 causal_analysis 후보로 연결된다"),
        ("accept_result", "이번엔 여기까지로 마무리한다", None,
         "결과를 그대로 수용하는 것만으로는 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("plan_next_version", "다음에 다시 만든다면 어떻게 할지 계획해본다", "planning",
         "다음 시도를 위한 계획을 미리 세우는 행동이 드러나 planning 후보로 연결된다"),
    ],
    "user_perspective": [
        ("ask_what_wrong", "어디가 불편했는지 물어본다", "collaboration_preference",
         "불편함의 원인을 직접 물어 확인하는 행동이 드러나 collaboration_preference 후보로 연결된다"),
        ("observe_more", "더 지켜보며 어떤 부분에서 막히는지 살펴본다", "pattern_finding",
         "반복해서 막히는 지점을 살펴 규칙을 찾는 행동이 드러나 pattern_finding 후보로 연결된다"),
        ("fix_right_away", "바로 그 부분을 고쳐본다", "immediate_execution",
         "문제를 발견하자마자 바로 고치는 행동이 드러나 immediate_execution 후보로 연결된다"),
        ("explain_how", "사용법을 설명해준다", None,
         "단순 사용법 설명은 특정 Trait 근거로 보기 어렵다(NO_SIGNAL)"),
        ("redesign_flow", "쓰는 순서 자체를 다시 구성해본다", "systems_thinking",
         "사용 흐름 전체를 다시 구조화하는 행동이 드러나 systems_thinking 후보로 연결된다"),
    ],
}

_BACKUP_QUESTION_TEXT: dict[str, str] = {
    "assembling": "조립하다가 부품이 남거나 맞지 않는 걸 발견했을 때 가장 먼저 하는 행동은 무엇인가요?",
    "tool_using": "쓰던 도구에 새로운 기능이 추가됐다는 걸 알게 됐을 때 가장 먼저 하는 행동은 무엇인가요?",
    "error_fixing": "며칠 동안 원인을 못 찾은 오류가 있을 때 가장 먼저 하는 행동은 무엇인가요?",
    "improving": "다 만든 뒤 아쉬운 부분이 눈에 띄었을 때 가장 먼저 하는 행동은 무엇인가요?",
    "user_perspective": "다른 사람이 내가 만든 것을 쓰다가 불편해하는 모습을 봤을 때 가장 먼저 하는 행동은 무엇인가요?",
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
        "학생이 코딩·프로그래밍 경험이 있다는 전제",
        "코딩을 좋아하면 분석적 성향이라는 자동 연결",
        "학생이 전자기기·장비를 자유롭게 쓸 수 있다는 전제",
    ],
    review_artifact_paths=[
        "data/reviews/context_packs/making_review_status.json",
        "outputs/context_packs/making_mapping_audit.md",
    ],
    pack_version="context_pack_technical_draft_v0.1",
)
