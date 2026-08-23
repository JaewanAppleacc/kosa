"""신규 Trait Direct Probe Blueprint 14개 — 2026-08-23 Trait Ontology v2(2단계 §5/§6/§7,
2.1단계 §7/§8/§9, 2.2단계 §7/§8/§9).

7개 신규 Trait(systems_thinking/detail_orientation/persistence_completion/
uncertainty_tolerance/opinion_expression/creative_ideation/independent_judgment) ×
서로 다른 Frame·Context의 Blueprint 2개 = 14개. 학생 한 명에게는 최대
`MAX_V2_DIRECT_PROBE_QUESTIONS`(4)개만 제시한다(선택 로직은
`src/engines/v2_direct_probe_selector.py`).

질문 설계 원칙(§6): Trait Label을 문장에 직접 노출하지 않는다("구조적으로 사고하는
편인가요?" 같은 자기평가 문항 금지). 5개 선택지 중 하나만 Target Trait를 PRIMARY로
가리키고, 나머지는 그 상황에서 실제로 나올 법한 다른 Core Trait 행동이거나(TRAIT_SIGNAL),
근거가 약해 특정 Trait로 단정하지 않는 NO_SIGNAL이다 — 근거 없이 Target Trait를 여러
선택지에 넣지 않는다(§8). 모든 Blueprint는 아직 `review_status="draft"`다(2인 교차검토 전).

2.2단계 §7/§8 재검토: 70개 Option을 전수 재검토해 "정보만 물어보는" 패턴(예: "팀원에게
물어본다", "친구에게 의견을 듣는다")을 collaboration_preference로 억지로 매핑하던 14개
Option을 NO_SIGNAL로 바꿨다(협업 선호는 "역할을 나눠 함께 해결"처럼 근거가 강할 때만
유지한다 — 예: persistence_completion_school_life_v1의 pc_team_stage). 근거 없는 목표
교체(persistence_completion_game_v1의 pc_take_break)와 단순 결정 유보
(uncertainty_tolerance_school_life_v1의 ut_wait_more)도 같은 이유로 NO_SIGNAL로
바꿨다. uncertainty_tolerance_game_v1의 ut_plan_ahead는 "예측 가능한 익숙한 방법"이라는
불확실성 회피 프레이밍을 지우고 순수 계획 행동으로 다시 썼다(NO_SIGNAL이 아니라
planning으로 유지). §9: persistence_completion·detail_orientation·opinion_expression의
Target Option에 현실적인 Trade-off 문구를 추가해 "무조건 좋은 답"처럼 보이지 않게 했다."""

from __future__ import annotations

from src.schemas.question import FinalizedOption, FinalizedQuestion
from src.schemas.trait_signal import TraitSignal
from src.schemas.v2_direct_probe import V2DirectProbeBlueprint, V2ProbeOptionMapping

# rows 한 행 = (role_id, option_text, mapped_trait_id 또는 None, no_signal_reason 또는 None).
# mapped_trait_id가 있으면 TRAIT_SIGNAL(PRIMARY 1개), 없으면 NO_SIGNAL이다(그 경우
# no_signal_reason은 필수). Target Role은 정확히 1개만 trait_id=blueprint의 trait_id다.
_Row = tuple[str, str, str | None, str | None]


def _build(
    *, blueprint_id: str, trait_id: str, allowed_context_ids: list[str], question_frame_id: str,
    purpose: str, context: str, question_text: str, rows: list[_Row],
) -> V2DirectProbeBlueprint:
    if len(rows) != 5:
        raise ValueError(f"{blueprint_id}: rows는 정확히 5개여야 한다(got {len(rows)})")

    question_id = f"{blueprint_id}_base"
    mappings: list[V2ProbeOptionMapping] = []
    options: list[FinalizedOption] = []
    for i, (role_id, text, mapped_trait_id, no_signal_reason) in enumerate(rows, start=1):
        if mapped_trait_id is not None:
            mappings.append(
                V2ProbeOptionMapping(
                    role_id=role_id, mapping_type="TRAIT_SIGNAL",
                    trait_signals=[TraitSignal(trait_id=mapped_trait_id, signal_role="PRIMARY", weight=1.0)],
                )
            )
            delta = {mapped_trait_id: 1}
        else:
            mappings.append(
                V2ProbeOptionMapping(role_id=role_id, mapping_type="NO_SIGNAL", no_signal_reason=no_signal_reason)
            )
            delta = {}
        options.append(
            FinalizedOption(option_id=f"{question_id}_o{i}", role_id=role_id, text=text, primary_trait_delta=delta)
        )

    return V2DirectProbeBlueprint(
        trait_id=trait_id,
        blueprint_id=blueprint_id,
        option_mappings=mappings,
        allowed_context_ids=allowed_context_ids,
        question_frame_id=question_frame_id,
        purpose=purpose,
        base_question=FinalizedQuestion(
            question_id=question_id, context=context, target_traits=[], frame_id=question_frame_id,
            question_text=question_text, options=options,
        ),
    )


_ASK_INFO_REASON = "정보를 묻거나 확인하는 행동일 뿐, 역할을 나눠 함께 해결하는 협업 행동이라는 근거가 약하다"
_ASK_FEEDBACK_REASON = "의견이나 반응을 구하는 행동으로, 협업 선호인지 단순한 반응 확인인지 문맥만으로 구분하기 어렵다"

# --- 1. systems_thinking ---

SYSTEMS_THINKING_GAME_V1 = _build(
    blueprint_id="systems_thinking_game_v1",
    trait_id="systems_thinking",
    allowed_context_ids=["game"],
    question_frame_id="new_tool",
    purpose="systems_thinking Direct Probe(요소 간 상호작용 관찰)",
    context="game",
    question_text="게임에 새로운 아이템이나 규칙이 추가되면 가장 먼저 무엇을 하나요?",
    rows=[
        ("st_ripple_check", "이게 다른 아이템이나 전략에 어떤 영향을 주는지 같이 살펴본다", "systems_thinking", None),
        ("st_reason_first", "왜 이게 추가됐는지 이유부터 생각해본다", "causal_analysis", None),
        ("st_try_it", "일단 직접 써보면서 익힌다", "immediate_execution", None),
        ("st_compare_items", "기존 아이템들과 비교해본다", "information_comparison", None),
        ("st_ask_team", "팀원들에게 어떻게 쓸지 물어본다", None, _ASK_INFO_REASON),
    ],
)

SYSTEMS_THINKING_SCHOOL_LIFE_V1 = _build(
    blueprint_id="systems_thinking_school_life_v1",
    trait_id="systems_thinking",
    allowed_context_ids=["school_life"],
    question_frame_id="unexpected_result",
    purpose="systems_thinking Direct Probe(요소 간 상호작용 관찰)",
    context="school_life",
    question_text="조별 프로젝트에서 한 사람의 역할이나 일정이 갑자기 바뀌면 무엇을 가장 먼저 생각하나요?",
    rows=[
        ("st_map_impact", "이 변화가 다른 사람의 역할과 어떻게 서로 얽혀 영향을 주는지 짚어본다", "systems_thinking", None),
        ("st_replan", "남은 일정과 순서를 처음부터 다시 짠다", "planning", None),
        ("st_adapt_now", "일단 상황에 맞게 바로 대응한다", "change_adaptation", None),
        ("st_check_mood", "역할이 바뀐 친구의 기분을 먼저 살핀다", "emotional_interpretation", None),
        ("st_state_view", "내 생각을 팀에 분명하게 말한다", "opinion_expression", None),
    ],
)

# --- 2. detail_orientation ---

DETAIL_ORIENTATION_MEDIA_V1 = _build(
    blueprint_id="detail_orientation_media_v1",
    trait_id="detail_orientation",
    allowed_context_ids=["media"],
    question_frame_id="problem_check",
    purpose="detail_orientation Direct Probe(세부 정확성 관찰)",
    context="media",
    question_text="영상이나 자료를 편집해서 제출하기 전에 무엇부터 확인하나요?",
    rows=[
        (
            "do_scan_errors",
            "시간이 더 들더라도 작은 오탈자나 어긋난 부분까지 하나하나 짚어본다",
            "detail_orientation", None,
        ),
        (
            "do_overall_flow",
            "예전에 만들었던 것과 비슷하게 반복되는 편집 패턴이 있는지 확인한다",
            "pattern_finding", None,
        ),
        ("do_ask_feedback", "친구에게 먼저 보여주고 의견을 듣는다", None, _ASK_FEEDBACK_REASON),
        (
            "do_visual_check", "화면 구성과 배치를 다시 살펴본다", None,
            "다시 확인하는 행동일 뿐, 새로운 시각 요소를 만들어내는 창작·표현 행동이라는 근거가 약하다",
        ),
        ("do_compare_ref", "참고했던 자료와 다시 비교해본다", "information_comparison", None),
    ],
)

DETAIL_ORIENTATION_SCHOOL_LIFE_V1 = _build(
    blueprint_id="detail_orientation_school_life_v1",
    trait_id="detail_orientation",
    allowed_context_ids=["school_life"],
    question_frame_id="limited_time_priority",
    purpose="detail_orientation Direct Probe(세부 정확성 관찰)",
    context="school_life",
    question_text="과제를 제출하기 직전, 시간이 얼마 없을 때 무엇을 우선 확인하나요?",
    rows=[
        (
            "do_check_conditions",
            "시간이 촉박해도 제출 조건을 하나하나 놓치지 않았는지 세세히 확인한다",
            "detail_orientation", None,
        ),
        ("do_finish_first", "일단 끝까지 마무리부터 한다", "persistence_completion", None),
        ("do_priority_pick", "가장 중요한 부분부터 순서를 정한다", "planning", None),
        ("do_quick_submit", "지금 상태로 바로 제출한다", "immediate_execution", None),
        ("do_ask_help", "선생님이나 친구에게 확인을 부탁한다", None, _ASK_INFO_REASON),
    ],
)

# --- 3. persistence_completion ---

PERSISTENCE_COMPLETION_GAME_V1 = _build(
    blueprint_id="persistence_completion_game_v1",
    trait_id="persistence_completion",
    allowed_context_ids=["game"],
    question_frame_id="unexpected_result",
    purpose="persistence_completion Direct Probe(어려움 이후 지속 관찰)",
    context="game",
    question_text="어려운 스테이지나 목표에서 계속 실패할 때 무엇을 하나요?",
    rows=[
        (
            "pc_keep_going",
            "결과가 잘 안 나오고 다른 목표를 시작할 시간이 늦어져도, 지금 목표는 그대로 두고 끝까지 시도를 이어간다",
            "persistence_completion", None,
        ),
        ("pc_analyze_fail", "왜 계속 실패하는지 원인을 분석한다", "causal_analysis", None),
        (
            "pc_take_break", "그 목표 대신 지금 상황에 맞는 다른 목표로 바꾼다", None,
            "목표를 다른 것으로 바꾸는 행동으로, 상황에 맞춰 방식을 능동적으로 바꾸는 change_adaptation의 직접 "
            "근거로 보기엔 단순한 목표 포기·교체에 가깝다",
        ),
        ("pc_watch_others", "다른 사람들은 어떻게 하는지 찾아본다", "information_comparison", None),
        ("pc_ask_help", "같이 하는 친구에게 도움을 요청한다", None, _ASK_INFO_REASON),
    ],
)

PERSISTENCE_COMPLETION_SCHOOL_LIFE_V1 = _build(
    blueprint_id="persistence_completion_school_life_v1",
    trait_id="persistence_completion",
    allowed_context_ids=["school_life"],
    question_frame_id="longest_focus",
    purpose="persistence_completion Direct Probe(어려움 이후 지속 관찰)",
    context="school_life",
    question_text="길고 지루한 과제를 할 때 어떤 부분에 가장 오래 매달리나요?",
    rows=[
        (
            "pc_finish_through",
            "다른 일에 쓸 시간이 줄어들어도, 지루한 과제를 끝까지 마무리하는 데 가장 오래 매달린다",
            "persistence_completion", None,
        ),
        ("pc_plan_stage", "처음 계획을 세우는 데 가장 오래 매달린다", "planning", None),
        ("pc_detail_stage", "세부 내용을 확인하는 데 가장 오래 매달린다", "detail_orientation", None),
        ("pc_creative_stage", "결과물을 보기 좋게 꾸미는 데 가장 오래 매달린다", "visual_expression", None),
        ("pc_team_stage", "팀원과 역할을 맞추는 데 가장 오래 매달린다", "collaboration_preference", None),
    ],
)

# --- 4. uncertainty_tolerance ---

UNCERTAINTY_TOLERANCE_GAME_V1 = _build(
    blueprint_id="uncertainty_tolerance_game_v1",
    trait_id="uncertainty_tolerance",
    allowed_context_ids=["game"],
    question_frame_id="new_tool",
    purpose="uncertainty_tolerance Direct Probe(결과 불확실 상태에서의 진행 관찰)",
    context="game",
    question_text="결과를 전혀 예측할 수 없는 새로운 선택지가 주어지면 어떻게 하나요?",
    rows=[
        (
            "ut_proceed_calm",
            "결과가 어떻게 나올지 몰라도 그 상태를 그대로 받아들이고 계속 진행한다",
            "uncertainty_tolerance", None,
        ),
        ("ut_try_now", "정보가 충분히 모이기 전이라도 일단 지금 바로 움직인다", "immediate_execution", None),
        ("ut_research_first", "먼저 관련 정보를 찾아본다", "information_comparison", None),
        ("ut_ask_others", "다른 사람 의견을 먼저 들어본다", None, _ASK_FEEDBACK_REASON),
        (
            "ut_plan_ahead", "선택하기 전에 여러 경우를 미리 따져보고 계획을 세운다",
            "planning", None,
        ),
    ],
)

UNCERTAINTY_TOLERANCE_SCHOOL_LIFE_V1 = _build(
    blueprint_id="uncertainty_tolerance_school_life_v1",
    trait_id="uncertainty_tolerance",
    allowed_context_ids=["school_life"],
    question_frame_id="conflicting_opinions",
    purpose="uncertainty_tolerance Direct Probe(결과 불확실 상태에서의 진행 관찰)",
    context="school_life",
    question_text="필요한 정보가 다 모이지 않은 상태에서 결정을 내려야 할 때 어떻게 하나요?",
    rows=[
        (
            "ut_decide_now", "확실하지 않아도 불안해하지 않고 일단 결정하고 진행한다",
            "uncertainty_tolerance", None,
        ),
        (
            "ut_wait_more", "정보가 더 모일 때까지 결정을 미룬다", None,
            "결정을 미루는 행동일 뿐 일정을 짜거나 순서를 정하는 것 같은 실제 계획 행동이 드러나지 않아 "
            "planning의 직접 근거로 보기 어렵다",
        ),
        ("ut_ask_teacher", "선생님이나 친구에게 먼저 물어본다", None, _ASK_INFO_REASON),
        ("ut_pick_safe", "그나마 확실한 정보를 비교해서 고른다", "information_comparison", None),
        ("ut_voice_concern", "불확실하다는 내 생각을 팀에 말한다", "opinion_expression", None),
    ],
)

# --- 5. opinion_expression ---

OPINION_EXPRESSION_MEDIA_V1 = _build(
    blueprint_id="opinion_expression_media_v1",
    trait_id="opinion_expression",
    allowed_context_ids=["media"],
    question_frame_id="conflicting_opinions",
    purpose="opinion_expression Direct Probe(의견 표명 여부 관찰)",
    context="media",
    question_text="콘텐츠 방향에 대해 사람들 의견이 갈리면 어떻게 하나요?",
    rows=[
        (
            "oe_state_view", "분위기가 어색해질 수 있어도 내 생각을 먼저 분명하게 말한다",
            "opinion_expression", None,
        ),
        ("oe_mediate", "서로 다른 의견을 절충할 지점을 찾는다", "opinion_mediation", None),
        ("oe_gather_data", "관련 사례를 더 찾아서 비교해본다", "information_comparison", None),
        (
            "oe_follow_majority", "다수가 원하는 방향을 따른다", None,
            "다수 의견을 따르는 행동으로, 협업 선호인지 단순한 순응·갈등 회피인지 문맥만으로 구분하기 어렵다",
        ),
        ("oe_read_mood", "사람들이 왜 그렇게 느끼는지 먼저 살핀다", "emotional_interpretation", None),
    ],
)

OPINION_EXPRESSION_SCHOOL_LIFE_V1 = _build(
    blueprint_id="opinion_expression_school_life_v1",
    trait_id="opinion_expression",
    allowed_context_ids=["school_life"],
    question_frame_id="others_reaction",
    purpose="opinion_expression Direct Probe(의견 표명 여부 관찰)",
    context="school_life",
    question_text="조별 활동에서 내 생각이 다른 사람들과 다르면 실제로 어떻게 하나요?",
    rows=[
        (
            "oe_speak_role", "다른 사람들 반응이 걱정되더라도 내 생각을 먼저 분명하게 말한다",
            "opinion_expression", None,
        ),
        ("oe_listen_role", "다른 사람이 왜 그렇게 생각하는지 먼저 들어본다", "emotional_interpretation", None),
        ("oe_organize_role", "전체 의견을 정리해서 다음 단계를 계획한다", "planning", None),
        ("oe_bridge_role", "서로 다른 의견을 절충할 지점을 찾는다", "opinion_mediation", None),
        (
            "oe_support_role", "일단 다수가 정한 방향에 맞춘다", None,
            "다수가 정한 방향에 맞추는 행동으로, 협업 선호인지 단순한 순응인지 문맥만으로 구분하기 어렵다",
        ),
    ],
)

# --- 6. creative_ideation ---

CREATIVE_IDEATION_MEDIA_V1 = _build(
    blueprint_id="creative_ideation_media_v1",
    trait_id="creative_ideation",
    allowed_context_ids=["media"],
    question_frame_id="first_action",
    purpose="creative_ideation Direct Probe(매체 무관 발상 관찰)",
    context="media",
    question_text="새로운 콘텐츠를 기획할 때 가장 먼저 무엇을 하고 싶나요?",
    rows=[
        ("ci_new_format", "기존에 없던 새로운 구성이나 방식을 스스로 떠올려본다", "creative_ideation", None),
        ("ci_visual_first", "화면이나 이미지를 어떻게 꾸밀지부터 생각한다", "visual_expression", None),
        ("ci_research_trend", "요즘 인기 있는 콘텐츠를 찾아본다", "information_comparison", None),
        ("ci_plan_steps", "전체 제작 순서를 미리 계획한다", "planning", None),
        ("ci_ask_team", "팀원들과 아이디어를 같이 나눈다", "collaboration_preference", None),
    ],
)

CREATIVE_IDEATION_GAME_V1 = _build(
    blueprint_id="creative_ideation_game_v1",
    trait_id="creative_ideation",
    allowed_context_ids=["game"],
    question_frame_id="new_tool",
    purpose="creative_ideation Direct Probe(매체 무관 발상 관찰)",
    context="game",
    question_text="새로운 게임 규칙이나 콘텐츠를 직접 만들 수 있다면 무엇을 하고 싶나요?",
    rows=[
        (
            "ci_invent_rule", "여러 요소를 새롭게 엮어서 지금까지와 다른 방식을 스스로 만들어본다",
            "creative_ideation", None,
        ),
        ("ci_improve_existing", "기존 규칙 중 반복되는 부분을 찾아 다듬는다", "pattern_finding", None),
        ("ci_test_it", "일단 만들어서 바로 실험해본다", "immediate_execution", None),
        ("ci_visual_design", "어떻게 보여줄지 화면 디자인부터 생각한다", "visual_expression", None),
        ("ci_get_feedback", "친구들에게 아이디어를 먼저 물어본다", None, _ASK_FEEDBACK_REASON),
    ],
)

# --- 7. independent_judgment ---

INDEPENDENT_JUDGMENT_GAME_V1 = _build(
    blueprint_id="independent_judgment_game_v1",
    trait_id="independent_judgment",
    allowed_context_ids=["game"],
    question_frame_id="others_reaction",
    purpose="independent_judgment Direct Probe(판단 주체 관찰)",
    context="game",
    question_text="게임 공략이나 다른 사람의 조언과 내 생각이 다를 때 어떻게 하나요?",
    rows=[
        ("ij_own_call", "다른 사람 의견과 달라도 내가 판단한 방식대로 한다", "independent_judgment", None),
        ("ij_follow_guide", "공략을 참고해서 비교한 뒤 따른다", "information_comparison", None),
        ("ij_ask_more", "다른 사람들에게 더 물어본다", None, _ASK_INFO_REASON),
        ("ij_say_thoughts", "내 생각이 다르다고 먼저 말한다", "opinion_expression", None),
        ("ij_stay_calm", "결과가 확실하지 않아도 크게 신경 쓰지 않고 진행한다", "uncertainty_tolerance", None),
    ],
)

INDEPENDENT_JUDGMENT_SCHOOL_LIFE_V1 = _build(
    blueprint_id="independent_judgment_school_life_v1",
    trait_id="independent_judgment",
    allowed_context_ids=["school_life"],
    question_frame_id="problem_check",
    purpose="independent_judgment Direct Probe(판단 주체 관찰)",
    context="school_life",
    question_text="선생님이나 팀의 지시가 명확하지 않을 때, 다음 행동의 기준을 어떻게 정하나요?",
    rows=[
        ("ij_set_own_standard", "스스로 판단한 기준으로 다음 행동을 정한다", "independent_judgment", None),
        (
            "ij_ask_clarify", "다른 사람에게 먼저 물어보고 기준을 맞춘다", None,
            "먼저 물어보고 기준을 맞추는 행동으로, 협업 선호가 직접 드러난다고 보기보다는 단순한 확인 행동에 "
            "가깝다",
        ),
        ("ij_plan_role", "전체 일정과 순서부터 다시 계획한다", "planning", None),
        ("ij_speak_role", "내가 생각한 기준을 다른 사람들에게 먼저 말한다", "opinion_expression", None),
        ("ij_adapt_role", "상황이 바뀌면 그때그때 기준을 바꾼다", "change_adaptation", None),
    ],
)


V2_DIRECT_PROBE_BLUEPRINTS: list[V2DirectProbeBlueprint] = [
    SYSTEMS_THINKING_GAME_V1, SYSTEMS_THINKING_SCHOOL_LIFE_V1,
    DETAIL_ORIENTATION_MEDIA_V1, DETAIL_ORIENTATION_SCHOOL_LIFE_V1,
    PERSISTENCE_COMPLETION_GAME_V1, PERSISTENCE_COMPLETION_SCHOOL_LIFE_V1,
    UNCERTAINTY_TOLERANCE_GAME_V1, UNCERTAINTY_TOLERANCE_SCHOOL_LIFE_V1,
    OPINION_EXPRESSION_MEDIA_V1, OPINION_EXPRESSION_SCHOOL_LIFE_V1,
    CREATIVE_IDEATION_MEDIA_V1, CREATIVE_IDEATION_GAME_V1,
    INDEPENDENT_JUDGMENT_GAME_V1, INDEPENDENT_JUDGMENT_SCHOOL_LIFE_V1,
]

V2_DIRECT_PROBE_BLUEPRINTS_BY_ID: dict[str, V2DirectProbeBlueprint] = {
    b.blueprint_id: b for b in V2_DIRECT_PROBE_BLUEPRINTS
}

V2_DIRECT_PROBE_BLUEPRINTS_BY_TRAIT: dict[str, list[V2DirectProbeBlueprint]] = {}
for _b in V2_DIRECT_PROBE_BLUEPRINTS:
    V2_DIRECT_PROBE_BLUEPRINTS_BY_TRAIT.setdefault(_b.trait_id, []).append(_b)

V2_DIRECT_PROBE_TARGET_TRAIT_IDS: frozenset[str] = frozenset(V2_DIRECT_PROBE_BLUEPRINTS_BY_TRAIT)


def _validate_cross_blueprint_uniqueness_and_ontology() -> None:
    """2.1단계 §6 — 개별 Blueprint 자체 정합성은 `V2DirectProbeBlueprint`의
    model_validator가 이미 검사한다(Import 시 Pydantic이 즉시 Fail-Fast). 여기서는
    Blueprint "여러 개 사이"의 정합성(전역 ID 중복)과 외부 Ontology 존재 여부만
    추가로 검사한다 — Schema 계층이 서비스 계층(trait_ontology_v2)을 몰라도 되게
    분리했다."""

    blueprint_ids = [b.blueprint_id for b in V2_DIRECT_PROBE_BLUEPRINTS]
    if len(blueprint_ids) != len(set(blueprint_ids)):
        raise ValueError(f"V2 Direct Probe blueprint_id 중복: {blueprint_ids}")

    question_ids = [b.base_question.question_id for b in V2_DIRECT_PROBE_BLUEPRINTS]
    if len(question_ids) != len(set(question_ids)):
        raise ValueError(f"V2 Direct Probe base_question.question_id 중복: {question_ids}")

    from src.services.trait_ontology_v2 import load_trait_ontology_v2

    known_trait_ids = {t.trait_id for t in load_trait_ontology_v2()}
    for b in V2_DIRECT_PROBE_BLUEPRINTS:
        if b.trait_id not in known_trait_ids:
            raise ValueError(f"{b.blueprint_id}: trait_id {b.trait_id!r}가 Core Trait Ontology에 없다")
        for mapping in b.option_mappings:
            if mapping.mapping_type != "TRAIT_SIGNAL":
                continue
            unknown = [s.trait_id for s in mapping.trait_signals if s.trait_id not in known_trait_ids]
            if unknown:
                raise ValueError(f"{b.blueprint_id}/{mapping.role_id}: 등록되지 않은 Trait id: {unknown}")


_validate_cross_blueprint_uniqueness_and_ontology()
