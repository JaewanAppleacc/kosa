"""신규 Trait Direct Probe Blueprint 14개 — 2026-08-24 Trait Ontology v2(2단계) §5/§6/§7.

7개 신규 Trait(systems_thinking/detail_orientation/persistence_completion/
uncertainty_tolerance/opinion_expression/creative_ideation/independent_judgment) ×
서로 다른 Frame·Context의 Blueprint 2개 = 14개. 학생 한 명에게는 최대
`MAX_V2_DIRECT_PROBE_QUESTIONS`(4)개만 제시한다(선택 로직은
`src/engines/v2_direct_probe_selector.py`).

질문 설계 원칙(§6): Trait Label을 문장에 직접 노출하지 않는다("구조적으로 사고하는
편인가요?" 같은 자기평가 문항 금지). 5개 선택지 중 하나만 Target Trait를 PRIMARY로
가리키고, 나머지 4개는 그 상황에서 실제로 나올 법한 다른 Core Trait 행동이다 — 근거
없이 Target Trait를 여러 선택지에 넣지 않는다(§8). 모든 Blueprint는 아직
`review_status="draft"`다(2인 교차검토 전).
"""

from __future__ import annotations

from src.schemas.question import FinalizedOption, FinalizedQuestion, OptionBlueprint, OptionRole
from src.schemas.v2_direct_probe import V2DirectProbeBlueprint


def _bp(blueprint_id: str, roles: list[tuple[str, str]]) -> OptionBlueprint:
    """roles: [(role_id, trait_id), ...] 5개. 전부 primary_trait_delta={trait_id: 1}."""

    return OptionBlueprint(
        blueprint_id=blueprint_id,
        roles=[OptionRole(role_id=role_id, primary_trait_delta={trait_id: 1}) for role_id, trait_id in roles],
    )


def _finalized(question_id: str, context: str, frame_id: str, question_text: str, options: list[tuple[str, str, str]]) -> FinalizedQuestion:
    """options: [(role_id, trait_id, text), ...] 5개."""

    return FinalizedQuestion(
        question_id=question_id,
        context=context,
        target_traits=[],
        frame_id=frame_id,
        question_text=question_text,
        options=[
            FinalizedOption(
                option_id=f"{question_id}_o{i}", role_id=role_id, text=text,
                primary_trait_delta={trait_id: 1},
            )
            for i, (role_id, trait_id, text) in enumerate(options, start=1)
        ],
    )


# --- 1. systems_thinking ---

SYSTEMS_THINKING_GAME_V1 = V2DirectProbeBlueprint(
    trait_id="systems_thinking",
    blueprint=_bp(
        "systems_thinking_game_v1",
        [
            ("st_ripple_check", "systems_thinking"), ("st_reason_first", "causal_analysis"),
            ("st_try_it", "immediate_execution"), ("st_compare_items", "information_comparison"),
            ("st_ask_team", "collaboration_preference"),
        ],
    ),
    allowed_context_ids=["game"],
    question_frame_id="new_tool",
    purpose="systems_thinking Direct Probe(요소 간 상호작용 관찰)",
    base_question=_finalized(
        "systems_thinking_game_v1_base", "game", "new_tool",
        "게임에 새로운 아이템이나 규칙이 추가되면 가장 먼저 무엇을 하나요?",
        [
            ("st_ripple_check", "systems_thinking", "이게 다른 아이템이나 전략에 어떤 영향을 주는지 같이 살펴본다"),
            ("st_reason_first", "causal_analysis", "왜 이게 추가됐는지 이유부터 생각해본다"),
            ("st_try_it", "immediate_execution", "일단 직접 써보면서 익힌다"),
            ("st_compare_items", "information_comparison", "기존 아이템들과 비교해본다"),
            ("st_ask_team", "collaboration_preference", "팀원들에게 어떻게 쓸지 물어본다"),
        ],
    ),
)

SYSTEMS_THINKING_SCHOOL_LIFE_V1 = V2DirectProbeBlueprint(
    trait_id="systems_thinking",
    blueprint=_bp(
        "systems_thinking_school_life_v1",
        [
            ("st_map_impact", "systems_thinking"), ("st_replan", "planning"),
            ("st_adapt_now", "change_adaptation"), ("st_check_mood", "emotional_interpretation"),
            ("st_state_view", "opinion_expression"),
        ],
    ),
    allowed_context_ids=["school_life"],
    question_frame_id="unexpected_result",
    purpose="systems_thinking Direct Probe(요소 간 상호작용 관찰)",
    base_question=_finalized(
        "systems_thinking_school_life_v1_base", "school_life", "unexpected_result",
        "조별 프로젝트에서 한 사람의 역할이나 일정이 갑자기 바뀌면 무엇을 가장 먼저 생각하나요?",
        [
            ("st_map_impact", "systems_thinking", "이 변화가 다른 역할이나 전체 일정에 어떻게 이어질지 짚어본다"),
            ("st_replan", "planning", "전체 일정을 다시 짠다"),
            ("st_adapt_now", "change_adaptation", "일단 상황에 맞게 바로 대응한다"),
            ("st_check_mood", "emotional_interpretation", "역할이 바뀐 친구의 기분을 먼저 살핀다"),
            ("st_state_view", "opinion_expression", "내 생각을 팀에 분명하게 말한다"),
        ],
    ),
)

# --- 2. detail_orientation ---

DETAIL_ORIENTATION_MEDIA_V1 = V2DirectProbeBlueprint(
    trait_id="detail_orientation",
    blueprint=_bp(
        "detail_orientation_media_v1",
        [
            ("do_scan_errors", "detail_orientation"), ("do_overall_flow", "pattern_finding"),
            ("do_ask_feedback", "collaboration_preference"), ("do_visual_check", "visual_expression"),
            ("do_compare_ref", "information_comparison"),
        ],
    ),
    allowed_context_ids=["media"],
    question_frame_id="problem_check",
    purpose="detail_orientation Direct Probe(세부 정확성 관찰)",
    base_question=_finalized(
        "detail_orientation_media_v1_base", "media", "problem_check",
        "영상이나 자료를 편집해서 제출하기 전에 무엇부터 확인하나요?",
        [
            ("do_scan_errors", "detail_orientation", "작은 오탈자나 어긋난 부분까지 하나하나 짚어본다"),
            ("do_overall_flow", "pattern_finding", "전체 흐름이 자연스러운지 훑어본다"),
            ("do_ask_feedback", "collaboration_preference", "친구에게 먼저 보여주고 의견을 듣는다"),
            ("do_visual_check", "visual_expression", "화면 구성과 배치를 다시 살펴본다"),
            ("do_compare_ref", "information_comparison", "참고했던 자료와 다시 비교해본다"),
        ],
    ),
)

DETAIL_ORIENTATION_SCHOOL_LIFE_V1 = V2DirectProbeBlueprint(
    trait_id="detail_orientation",
    blueprint=_bp(
        "detail_orientation_school_life_v1",
        [
            ("do_check_conditions", "detail_orientation"), ("do_finish_first", "persistence_completion"),
            ("do_priority_pick", "planning"), ("do_quick_submit", "immediate_execution"),
            ("do_ask_help", "collaboration_preference"),
        ],
    ),
    allowed_context_ids=["school_life"],
    question_frame_id="limited_time_priority",
    purpose="detail_orientation Direct Probe(세부 정확성 관찰)",
    base_question=_finalized(
        "detail_orientation_school_life_v1_base", "school_life", "limited_time_priority",
        "과제를 제출하기 직전, 시간이 얼마 없을 때 무엇을 우선 확인하나요?",
        [
            ("do_check_conditions", "detail_orientation", "제출 조건을 하나하나 놓치지 않았는지 세세히 확인한다"),
            ("do_finish_first", "persistence_completion", "일단 끝까지 마무리부터 한다"),
            ("do_priority_pick", "planning", "가장 중요한 부분부터 순서를 정한다"),
            ("do_quick_submit", "immediate_execution", "지금 상태로 바로 제출한다"),
            ("do_ask_help", "collaboration_preference", "선생님이나 친구에게 확인을 부탁한다"),
        ],
    ),
)

# --- 3. persistence_completion ---

PERSISTENCE_COMPLETION_GAME_V1 = V2DirectProbeBlueprint(
    trait_id="persistence_completion",
    blueprint=_bp(
        "persistence_completion_game_v1",
        [
            ("pc_keep_going", "persistence_completion"), ("pc_analyze_fail", "causal_analysis"),
            ("pc_take_break", "change_adaptation"), ("pc_watch_others", "information_comparison"),
            ("pc_ask_help", "collaboration_preference"),
        ],
    ),
    allowed_context_ids=["game"],
    question_frame_id="unexpected_result",
    purpose="persistence_completion Direct Probe(어려움 이후 지속 관찰)",
    base_question=_finalized(
        "persistence_completion_game_v1_base", "game", "unexpected_result",
        "어려운 스테이지나 목표에서 계속 실패할 때 무엇을 하나요?",
        [
            ("pc_keep_going", "persistence_completion", "포기하지 않고 방법을 바꿔가며 계속 도전한다"),
            ("pc_analyze_fail", "causal_analysis", "왜 계속 실패하는지 원인을 분석한다"),
            ("pc_take_break", "change_adaptation", "잠깐 다른 걸 하다가 다시 돌아온다"),
            ("pc_watch_others", "information_comparison", "다른 사람들은 어떻게 하는지 찾아본다"),
            ("pc_ask_help", "collaboration_preference", "같이 하는 친구에게 도움을 요청한다"),
        ],
    ),
)

PERSISTENCE_COMPLETION_SCHOOL_LIFE_V1 = V2DirectProbeBlueprint(
    trait_id="persistence_completion",
    blueprint=_bp(
        "persistence_completion_school_life_v1",
        [
            ("pc_finish_through", "persistence_completion"), ("pc_plan_stage", "planning"),
            ("pc_detail_stage", "detail_orientation"), ("pc_creative_stage", "visual_expression"),
            ("pc_team_stage", "collaboration_preference"),
        ],
    ),
    allowed_context_ids=["school_life"],
    question_frame_id="longest_focus",
    purpose="persistence_completion Direct Probe(어려움 이후 지속 관찰)",
    base_question=_finalized(
        "persistence_completion_school_life_v1_base", "school_life", "longest_focus",
        "길고 지루한 과제를 할 때 어떤 부분에 가장 오래 매달리나요?",
        [
            ("pc_finish_through", "persistence_completion", "지루해도 끝까지 마무리하는 데 가장 오래 매달린다"),
            ("pc_plan_stage", "planning", "처음 계획을 세우는 데 가장 오래 매달린다"),
            ("pc_detail_stage", "detail_orientation", "세부 내용을 확인하는 데 가장 오래 매달린다"),
            ("pc_creative_stage", "visual_expression", "결과물을 보기 좋게 꾸미는 데 가장 오래 매달린다"),
            ("pc_team_stage", "collaboration_preference", "팀원과 맞추는 데 가장 오래 매달린다"),
        ],
    ),
)

# --- 4. uncertainty_tolerance ---

UNCERTAINTY_TOLERANCE_GAME_V1 = V2DirectProbeBlueprint(
    trait_id="uncertainty_tolerance",
    blueprint=_bp(
        "uncertainty_tolerance_game_v1",
        [
            ("ut_proceed_calm", "uncertainty_tolerance"), ("ut_try_now", "immediate_execution"),
            ("ut_research_first", "information_comparison"), ("ut_ask_others", "collaboration_preference"),
            ("ut_plan_ahead", "planning"),
        ],
    ),
    allowed_context_ids=["game"],
    question_frame_id="new_tool",
    purpose="uncertainty_tolerance Direct Probe(결과 불확실 상태에서의 진행 관찰)",
    base_question=_finalized(
        "uncertainty_tolerance_game_v1_base", "game", "new_tool",
        "결과를 전혀 예측할 수 없는 새로운 선택지가 주어지면 어떻게 하나요?",
        [
            ("ut_proceed_calm", "uncertainty_tolerance", "결과를 몰라도 크게 신경 쓰지 않고 진행한다"),
            ("ut_try_now", "immediate_execution", "일단 빠르게 시도해본다"),
            ("ut_research_first", "information_comparison", "먼저 관련 정보를 찾아본다"),
            ("ut_ask_others", "collaboration_preference", "다른 사람 의견을 먼저 들어본다"),
            ("ut_plan_ahead", "planning", "결과를 예상할 수 있는 익숙한 방법을 미리 계획해서 고른다"),
        ],
    ),
)

UNCERTAINTY_TOLERANCE_SCHOOL_LIFE_V1 = V2DirectProbeBlueprint(
    trait_id="uncertainty_tolerance",
    blueprint=_bp(
        "uncertainty_tolerance_school_life_v1",
        [
            ("ut_decide_now", "uncertainty_tolerance"), ("ut_wait_more", "planning"),
            ("ut_ask_teacher", "collaboration_preference"), ("ut_pick_safe", "information_comparison"),
            ("ut_voice_concern", "opinion_expression"),
        ],
    ),
    allowed_context_ids=["school_life"],
    question_frame_id="conflicting_opinions",
    purpose="uncertainty_tolerance Direct Probe(결과 불확실 상태에서의 진행 관찰)",
    base_question=_finalized(
        "uncertainty_tolerance_school_life_v1_base", "school_life", "conflicting_opinions",
        "필요한 정보가 다 모이지 않은 상태에서 결정을 내려야 할 때 어떻게 하나요?",
        [
            ("ut_decide_now", "uncertainty_tolerance", "확실하지 않아도 불안해하지 않고 일단 결정하고 진행한다"),
            ("ut_wait_more", "planning", "정보가 더 모일 때까지 결정을 미룬다"),
            ("ut_ask_teacher", "collaboration_preference", "선생님이나 친구에게 먼저 물어본다"),
            ("ut_pick_safe", "information_comparison", "그나마 확실한 정보를 비교해서 고른다"),
            ("ut_voice_concern", "opinion_expression", "불확실하다는 내 생각을 팀에 말한다"),
        ],
    ),
)

# --- 5. opinion_expression ---

OPINION_EXPRESSION_MEDIA_V1 = V2DirectProbeBlueprint(
    trait_id="opinion_expression",
    blueprint=_bp(
        "opinion_expression_media_v1",
        [
            ("oe_state_view", "opinion_expression"), ("oe_mediate", "opinion_mediation"),
            ("oe_gather_data", "information_comparison"), ("oe_follow_majority", "collaboration_preference"),
            ("oe_read_mood", "emotional_interpretation"),
        ],
    ),
    allowed_context_ids=["media"],
    question_frame_id="conflicting_opinions",
    purpose="opinion_expression Direct Probe(의견 표명 여부 관찰)",
    base_question=_finalized(
        "opinion_expression_media_v1_base", "media", "conflicting_opinions",
        "콘텐츠 방향에 대해 사람들 의견이 갈리면 어떻게 하나요?",
        [
            ("oe_state_view", "opinion_expression", "내 생각을 먼저 분명하게 말한다"),
            ("oe_mediate", "opinion_mediation", "서로 다른 의견을 절충할 지점을 찾는다"),
            ("oe_gather_data", "information_comparison", "관련 사례를 더 찾아서 비교해본다"),
            ("oe_follow_majority", "collaboration_preference", "다수가 원하는 방향을 따른다"),
            ("oe_read_mood", "emotional_interpretation", "사람들이 왜 그렇게 느끼는지 먼저 살핀다"),
        ],
    ),
)

OPINION_EXPRESSION_SCHOOL_LIFE_V1 = V2DirectProbeBlueprint(
    trait_id="opinion_expression",
    blueprint=_bp(
        "opinion_expression_school_life_v1",
        [
            ("oe_speak_role", "opinion_expression"), ("oe_listen_role", "emotional_interpretation"),
            ("oe_organize_role", "planning"), ("oe_bridge_role", "opinion_mediation"),
            ("oe_support_role", "collaboration_preference"),
        ],
    ),
    allowed_context_ids=["school_life"],
    question_frame_id="team_role",
    purpose="opinion_expression Direct Probe(의견 표명 여부 관찰)",
    base_question=_finalized(
        "opinion_expression_school_life_v1_base", "school_life", "team_role",
        "팀 활동에서 내 생각이 다른 사람들과 다르면 어떤 역할을 맡고 싶나요?",
        [
            ("oe_speak_role", "opinion_expression", "생각이 있으면 먼저 나서서 말하는 역할을 맡는다"),
            ("oe_listen_role", "emotional_interpretation", "다른 사람 의견을 듣고 이해하는 역할을 맡는다"),
            ("oe_organize_role", "planning", "전체 진행을 정리하는 역할을 맡는다"),
            ("oe_bridge_role", "opinion_mediation", "의견을 조율하는 역할을 맡는다"),
            ("oe_support_role", "collaboration_preference", "정해진 방향에 맞춰 지원하는 역할을 맡는다"),
        ],
    ),
)

# --- 6. creative_ideation ---

CREATIVE_IDEATION_MEDIA_V1 = V2DirectProbeBlueprint(
    trait_id="creative_ideation",
    blueprint=_bp(
        "creative_ideation_media_v1",
        [
            ("ci_new_format", "creative_ideation"), ("ci_visual_first", "visual_expression"),
            ("ci_research_trend", "information_comparison"), ("ci_plan_steps", "planning"),
            ("ci_ask_team", "collaboration_preference"),
        ],
    ),
    allowed_context_ids=["media"],
    question_frame_id="first_action",
    purpose="creative_ideation Direct Probe(매체 무관 발상 관찰)",
    base_question=_finalized(
        "creative_ideation_media_v1_base", "media", "first_action",
        "새로운 콘텐츠를 기획할 때 가장 먼저 무엇을 하고 싶나요?",
        [
            ("ci_new_format", "creative_ideation", "기존에 없던 새로운 구성이나 방식을 스스로 떠올려본다"),
            ("ci_visual_first", "visual_expression", "화면이나 이미지를 어떻게 꾸밀지부터 생각한다"),
            ("ci_research_trend", "information_comparison", "요즘 인기 있는 콘텐츠를 찾아본다"),
            ("ci_plan_steps", "planning", "전체 제작 순서를 미리 계획한다"),
            ("ci_ask_team", "collaboration_preference", "팀원들과 아이디어를 같이 나눈다"),
        ],
    ),
)

CREATIVE_IDEATION_GAME_V1 = V2DirectProbeBlueprint(
    trait_id="creative_ideation",
    blueprint=_bp(
        "creative_ideation_game_v1",
        [
            ("ci_invent_rule", "creative_ideation"), ("ci_improve_existing", "pattern_finding"),
            ("ci_test_it", "immediate_execution"), ("ci_visual_design", "visual_expression"),
            ("ci_get_feedback", "collaboration_preference"),
        ],
    ),
    allowed_context_ids=["game"],
    question_frame_id="new_tool",
    purpose="creative_ideation Direct Probe(매체 무관 발상 관찰)",
    base_question=_finalized(
        "creative_ideation_game_v1_base", "game", "new_tool",
        "새로운 게임 규칙이나 콘텐츠를 직접 만들 수 있다면 무엇을 하고 싶나요?",
        [
            ("ci_invent_rule", "creative_ideation", "아직 아무도 안 써본 새로운 규칙을 스스로 떠올려본다"),
            ("ci_improve_existing", "pattern_finding", "기존 규칙 중 반복되는 부분을 찾아 다듬는다"),
            ("ci_test_it", "immediate_execution", "일단 만들어서 바로 실험해본다"),
            ("ci_visual_design", "visual_expression", "어떻게 보여줄지 화면 디자인부터 생각한다"),
            ("ci_get_feedback", "collaboration_preference", "친구들에게 아이디어를 먼저 물어본다"),
        ],
    ),
)

# --- 7. independent_judgment ---

INDEPENDENT_JUDGMENT_GAME_V1 = V2DirectProbeBlueprint(
    trait_id="independent_judgment",
    blueprint=_bp(
        "independent_judgment_game_v1",
        [
            ("ij_own_call", "independent_judgment"), ("ij_follow_guide", "information_comparison"),
            ("ij_ask_more", "collaboration_preference"), ("ij_say_thoughts", "opinion_expression"),
            ("ij_stay_calm", "uncertainty_tolerance"),
        ],
    ),
    allowed_context_ids=["game"],
    question_frame_id="others_reaction",
    purpose="independent_judgment Direct Probe(판단 주체 관찰)",
    base_question=_finalized(
        "independent_judgment_game_v1_base", "game", "others_reaction",
        "게임 공략이나 다른 사람의 조언과 내 생각이 다를 때 어떻게 하나요?",
        [
            ("ij_own_call", "independent_judgment", "다른 사람 의견과 달라도 내가 판단한 방식대로 한다"),
            ("ij_follow_guide", "information_comparison", "공략을 참고해서 비교한 뒤 따른다"),
            ("ij_ask_more", "collaboration_preference", "다른 사람들에게 더 물어본다"),
            ("ij_say_thoughts", "opinion_expression", "내 생각이 다르다고 먼저 말한다"),
            ("ij_stay_calm", "uncertainty_tolerance", "결과가 확실하지 않아도 크게 신경 쓰지 않고 진행한다"),
        ],
    ),
)

INDEPENDENT_JUDGMENT_SCHOOL_LIFE_V1 = V2DirectProbeBlueprint(
    trait_id="independent_judgment",
    blueprint=_bp(
        "independent_judgment_school_life_v1",
        [
            ("ij_set_own_standard", "independent_judgment"), ("ij_ask_clarify", "collaboration_preference"),
            ("ij_plan_role", "planning"), ("ij_speak_role", "opinion_expression"),
            ("ij_adapt_role", "change_adaptation"),
        ],
    ),
    allowed_context_ids=["school_life"],
    question_frame_id="team_role",
    purpose="independent_judgment Direct Probe(판단 주체 관찰)",
    base_question=_finalized(
        "independent_judgment_school_life_v1_base", "school_life", "team_role",
        "지시가 명확하지 않은 활동을 맡았을 때 어떤 역할을 맡고 싶나요?",
        [
            ("ij_set_own_standard", "independent_judgment", "스스로 기준을 세워서 판단하고 진행하는 역할을 맡는다"),
            ("ij_ask_clarify", "collaboration_preference", "먼저 다른 사람에게 물어보고 맞추는 역할을 맡는다"),
            ("ij_plan_role", "planning", "전체 순서를 계획하는 역할을 맡는다"),
            ("ij_speak_role", "opinion_expression", "내 생각을 적극적으로 말하는 역할을 맡는다"),
            ("ij_adapt_role", "change_adaptation", "상황이 바뀌면 바로 맞춰서 조정하는 역할을 맡는다"),
        ],
    ),
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
    b.blueprint.blueprint_id: b for b in V2_DIRECT_PROBE_BLUEPRINTS
}

V2_DIRECT_PROBE_BLUEPRINTS_BY_TRAIT: dict[str, list[V2DirectProbeBlueprint]] = {}
for _b in V2_DIRECT_PROBE_BLUEPRINTS:
    V2_DIRECT_PROBE_BLUEPRINTS_BY_TRAIT.setdefault(_b.trait_id, []).append(_b)

V2_DIRECT_PROBE_TARGET_TRAIT_IDS: frozenset[str] = frozenset(V2_DIRECT_PROBE_BLUEPRINTS_BY_TRAIT)
