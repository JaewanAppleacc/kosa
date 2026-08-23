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
# 2026-08-23 Trait Ontology v2(2.5.1단계) §10-A: 시청각 연출에 대한 관심·감상은 보여주지만,
# 학생이 직접 시각적으로 "표현"했다는 Evidence는 아니다(visual_expression은 산출 행동을
# 요구하는 Trait다). 새 Trait를 즉시 만들지 않고, 더 정직하게 NO_SIGNAL로 되돌렸다.
_VISUAL_APPRECIATION_REASON = "시각·음향 연출에 대한 관심이나 감상을 보여줄 뿐, 학생이 직접 시각적으로 표현하거나 만들었다는 근거는 아니다"

# --- 1. systems_thinking ---

SYSTEMS_THINKING_GAME_V1 = _build(
    blueprint_id="systems_thinking_game_v1",
    trait_id="systems_thinking",
    allowed_context_ids=["game"],
    question_frame_id="new_tool",
    purpose="systems_thinking Direct Probe(요소 간 상호작용 관찰)",
    context="game",
    # 2.5단계 §6: "아이템이나 규칙 추가"는 RPG·라이브 서비스 게임 전제라 이야기 탐험·
    # 퍼즐 등 다른 장르 학생에게 안 맞을 수 있어 "예상하지 못한 새로운 상황이나 요소"로
    # 넓혔다(사용자 검수 피드백: "장르가 다양해서 한 질문이 모든 장르를 포괄하긴
    # 어려운것같아").
    question_text="게임을 하다가 예상하지 못한 새로운 상황이나 요소를 마주치면 가장 먼저 무엇을 하나요?",
    rows=[
        ("st_ripple_check", "그 요소가 다른 부분과 어떻게 연결되어 영향을 주는지 살펴본다", "systems_thinking", None),
        ("st_reason_first", "왜 이런 상황이 생겼는지 이유부터 생각해본다", "causal_analysis", None),
        ("st_try_it", "일단 직접 부딪혀보면서 알아간다", "immediate_execution", None),
        # 사용자 검수 피드백(st_compare_items): "기존 아이템들과 비교해보는건 개인의
        # 특성에 따라 갈리는 영역이 아닌 당연한 영역이야" — 단순 비교를
        # "정보를 찾아서 비교"로 구체화하고, pattern_finding 자리를 대신 information_
        # comparison에 남긴다(과거 회차와 role_id는 그대로 유지).
        ("st_compare_items", "다른 공략이나 정보를 찾아서 비교해본다", "information_comparison", None),
        # 사용자 검수 피드백(st_ask_team): "팀원들끼리 같이 하는 게임이 아닌 혼자 하는
        # 게임일 수 도 있어" — 팀 전제를 완전히 제거하고 혼자·함께 플레이하는 학생
        # 모두에게 적용되는 NO_SIGNAL 선택지로 바꿨다.
        (
            "st_ask_team", "당장은 넘어가고 나중에 다시 생각해본다", None,
            "지금 판단을 미루는 행동일 뿐 특정 Core Trait를 직접 확인할 만큼 근거가 명확하지 않다",
        ),
    ],
)

SYSTEMS_THINKING_SCHOOL_LIFE_V1 = _build(
    blueprint_id="systems_thinking_school_life_v1",
    trait_id="systems_thinking",
    allowed_context_ids=["school_life"],
    question_frame_id="unexpected_result",
    purpose="systems_thinking Direct Probe(요소 간 상호작용 관찰)",
    context="school_life",
    # 2.5단계 §8: 조별 프로젝트 편중을 줄이고 학업·공부 영역으로 옮겼다(학교생활 6개
    # 중 조별·그룹활동은 opinion_expression_school_life_v1 하나로 제한). 사용자 검수
    # 피드백을 반영해 st_replan/st_adapt_now도 다시 썼다.
    question_text="이번 주 시험공부 계획을 세워뒀는데 한 과목의 시험 범위가 갑자기 바뀌면 가장 먼저 어떻게 하나요?",
    rows=[
        ("st_map_impact", "이 변화가 다른 과목 공부 계획에 어떻게 영향을 주는지 살펴본다", "systems_thinking", None),
        # 사용자 검수 피드백: "남은 일정과 순서를 처음부터 다시 짜는건 무조건적으로
        # 1번 선택지인 이 변화가 어떤 영향을 주는지 짚어본 후에야 나올 수 있는
        # 생각인것같아" — st_map_impact 없이도 바로 선택할 수 있는 독립적 행동으로
        # 다시 썼다(범위가 바뀌었다는 사실 자체에 바로 반응해 계획을 다시 짜는 것도
        # 가능한 선택이다).
        ("st_replan", "남은 공부 시간과 순서를 처음부터 다시 짠다", "planning", None),
        # 사용자 검수 피드백: "상황에 맞게 바로 대응한다는 모든 답변을 포괄하는
        # 답변이라 애매한것같아" — change_adaptation을 "원래 계획을 미뤄두고 바뀐
        # 부분부터 바로 처리한다"는 구체적 행동으로 좁혔다.
        ("st_adapt_now", "원래 하려던 계획은 미뤄두고 바뀐 범위부터 바로 공부한다", "change_adaptation", None),
        ("st_check_mood", "바뀐 범위에서 무엇이 정확히 달라졌는지 하나하나 확인한다", "detail_orientation", None),
        ("st_state_view", "범위가 너무 갑자기 바뀌었다는 내 생각을 선생님께 직접 말씀드린다", "opinion_expression", None),
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
    # 2.5단계 §7 전면 재작성: 사용자 검수 피드백(질문 메모) — "내가 말한 미디어는
    # 이런 편집이나 제출의 느낌보다는 영화,드라마,유튜브,뮤지컬,공연 등의 문화생활을
    # 말한거였어" — 제작·편집 전제를 완전히 걷어내고 감상자 관점으로 다시 썼다.
    question_text="영화·드라마·공연 같은 작품을 보고 난 뒤 다시 떠올려보는 부분은 무엇인가요?",
    rows=[
        ("do_scan_errors", "대사나 장면 속 작은 단서·복선을 다시 짚어본다", "detail_orientation", None),
        (
            "do_overall_flow",
            "이 감독이나 작가의 다른 작품에서도 비슷하게 반복되는 연출이 있었는지 떠올려본다",
            "pattern_finding", None,
        ),
        ("do_ask_feedback", "같이 본 사람과 어떤 장면이 좋았는지 이야기를 나눈다", None, _ASK_FEEDBACK_REASON),
        (
            "do_visual_check", "화면 구도나 무대·음악 연출이 인상 깊었던 순간을 떠올린다",
            None, _VISUAL_APPRECIATION_REASON,
        ),
        ("do_compare_ref", "비슷한 장르의 다른 작품과 어떤 점이 다른지 비교해본다", "information_comparison", None),
    ],
)

DETAIL_ORIENTATION_SCHOOL_LIFE_V1 = _build(
    blueprint_id="detail_orientation_school_life_v1",
    trait_id="detail_orientation",
    allowed_context_ids=["school_life"],
    question_frame_id="limited_time_priority",
    purpose="detail_orientation Direct Probe(세부 정확성 관찰)",
    context="school_life",
    # 2.5단계 §8: "과제·수행평가" 영역으로 명확히 고정한다(학교생활 분포 기준).
    question_text="수행평가 결과물을 제출하기 직전인데 시간이 얼마 없다면 무엇을 우선 확인하나요?",
    rows=[
        (
            "do_check_conditions",
            "촉박해도 조건을 하나하나 놓치지 않는지 확인한다",
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
    # 2.5단계 §6: "스테이지"는 레벨 기반 장르 전제라 장르 중립 표현으로 바꿨다.
    question_text="어려운 목표나 도전에서 계속 뜻대로 안 될 때 무엇을 하나요?",
    rows=[
        (
            "pc_keep_going",
            "잘 안 나와도 다른 목표로 넘어가지 않고 끝까지 이어간다",
            "persistence_completion", None,
        ),
        ("pc_analyze_fail", "왜 잘 안 풀리는지 원인을 분석한다", "causal_analysis", None),
        (
            "pc_take_break", "그 목표 대신 지금 상황에 맞는 다른 목표로 바꾼다", None,
            "목표를 다른 것으로 바꾸는 행동으로, 상황에 맞춰 방식을 능동적으로 바꾸는 change_adaptation의 직접 "
            "근거로 보기엔 단순한 목표 포기·교체에 가깝다",
        ),
        ("pc_watch_others", "다른 사람들은 어떻게 하는지 찾아본다", "information_comparison", None),
        # 사용자 검수 원칙(§6): 팀 플레이를 선택하지 않은 학생에게 팀원 상황을 쓰지
        # 않는다 — "같이 하는 친구"를 요구하지 않는 표현으로 바꿨다.
        ("pc_ask_help", "온라인이나 주변에 도움을 요청한다", None, _ASK_INFO_REASON),
    ],
)

PERSISTENCE_COMPLETION_SCHOOL_LIFE_V1 = _build(
    blueprint_id="persistence_completion_school_life_v1",
    trait_id="persistence_completion",
    allowed_context_ids=["school_life"],
    question_frame_id="longest_focus",
    purpose="persistence_completion Direct Probe(어려움 이후 지속 관찰)",
    context="school_life",
    # 2.5단계 §8: "학업·공부" 영역(학교생활 분포 기준 2번째)으로 옮겼다.
    question_text="시험공부처럼 길고 지루한 학업 활동을 할 때 어떤 부분에 가장 오래 매달리나요?",
    rows=[
        (
            "pc_finish_through",
            "시간이 걸려도 끝까지 마무리하는 데 가장 오래 매달린다",
            "persistence_completion", None,
        ),
        ("pc_plan_stage", "처음 계획을 세우는 데 가장 오래 매달린다", "planning", None),
        ("pc_detail_stage", "세부 내용을 확인하는 데 가장 오래 매달린다", "detail_orientation", None),
        ("pc_creative_stage", "정리한 내용을 보기 좋게 꾸미는 데 가장 오래 매달린다", "visual_expression", None),
        # §6/§9 적용 가능성 원칙: 이미 스터디 그룹이 있다고 전제하지 않고, "함께할
        # 사람을 구하는" 능동적 행동으로 바꿨다.
        ("pc_team_stage", "함께 공부할 사람을 구하고 진도를 맞추는 데 가장 오래 매달린다", "collaboration_preference", None),
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
        # §6: 팀 전제를 없애고 "다른 사람들의 의견·후기"로 넓혀 혼자 플레이하는
        # 학생도 적용할 수 있게 했다.
        ("ut_ask_others", "다른 사람들의 의견이나 후기를 먼저 찾아본다", None, _ASK_FEEDBACK_REASON),
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
    # 2.5단계 §8: 사용자가 지적한 추상적 표현("필요한 정보가 다 모이지 않은 상태에서
    # 결정을 내려야 할 때")을 실제 고등학생 상황(선택과목·진로 결정)으로 바꿨다 —
    # "과목·진로 선택" 영역.
    question_text=(
        "다음 학기 선택과목 신청 마감이 다가왔는데, 관심 학과와 과목에 대한 정보를 "
        "아직 충분히 찾지 못했다면 어떻게 하나요?"
    ),
    rows=[
        # 2.5.1단계 §10-B: 기존 문구("확실한 정보가 없어도 불안해하지 않고 지금 아는
        # 것만으로 신청한다")는 감정 상태("불안해하지 않고")와 행동(신청한다)을 한
        # 문장에 묶고 있었고, "불안해하지 않고"가 사회적으로 바람직해 보이는 표현이라
        # 이 선택지만 유독 성숙한 답처럼 읽힐 위험이 있었다. 감정 어휘를 빼고
        # "확인된 정보를 기준으로 선택한다"는 행동 하나만 남겼다.
        (
            "ut_decide_now", "확인하지 못한 부분이 남아 있어도 지금까지 확인된 정보만으로 신청한다",
            "uncertainty_tolerance", None,
        ),
        (
            "ut_wait_more", "신청 기한을 최대한 늦추면서 정보를 더 찾아본다", None,
            "기한을 늦추는 행동일 뿐 일정을 짜거나 순서를 정하는 것 같은 실제 계획 행동이 드러나지 않아 "
            "planning의 직접 근거로 보기 어렵다",
        ),
        ("ut_ask_teacher", "진로 선생님이나 선배에게 먼저 물어본다", None, _ASK_INFO_REASON),
        ("ut_pick_safe", "그나마 확실하게 알려진 과목·학과 정보를 비교해서 고른다", "information_comparison", None),
        ("ut_voice_concern", "정보가 부족해서 걱정된다는 내 생각을 선생님께 말씀드린다", "opinion_expression", None),
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
    # 2.5단계 §7 전면 재작성: 감상자 관점 — 같은 작품을 본 친구와 해석이 갈리는 상황.
    question_text="같은 작품을 본 친구와 인물의 선택이나 결말에 대한 생각이 다를 때 어떻게 하나요?",
    rows=[
        (
            "oe_state_view", "분위기가 어색해져도 내 생각을 먼저 분명하게 말한다",
            "opinion_expression", None,
        ),
        ("oe_mediate", "서로 다른 해석을 절충할 지점을 찾아본다", "opinion_mediation", None),
        ("oe_gather_data", "다른 사람들은 어떻게 해석했는지 리뷰나 반응을 찾아본다", "information_comparison", None),
        (
            "oe_follow_majority", "다수가 동의하는 해석을 따른다", None,
            "다수 해석을 따르는 행동으로, 협업 선호인지 단순한 순응·갈등 회피인지 문맥만으로 구분하기 어렵다",
        ),
        ("oe_read_mood", "친구가 왜 그렇게 생각하는지 먼저 이해해보려 한다", "emotional_interpretation", None),
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
    # 2.5단계 §7 전면 재작성: 감상자 관점 — 제작 경험이 없어도 답할 수 있는 "결말을
    # 바꿔본다면" 가정 질문으로 바꿨다.
    question_text="인상 깊게 본 작품의 한 장면이나 결말을 바꿔볼 수 있다면 무엇부터 생각하나요?",
    rows=[
        ("ci_new_format", "그 장면을 완전히 다른 전개로 새롭게 상상해본다", "creative_ideation", None),
        ("ci_visual_first", "화면이나 무대를 어떻게 다르게 연출할지부터 생각한다", "visual_expression", None),
        ("ci_research_trend", "비슷하게 결말을 바꾼 다른 작품들을 찾아본다", "information_comparison", None),
        ("ci_plan_steps", "바뀐 이야기가 앞뒤로 자연스럽게 이어지도록 순서를 정리한다", "planning", None),
        ("ci_ask_team", "친구와 이야기를 나누며 같이 아이디어를 발전시킨다", "collaboration_preference", None),
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
            "ci_invent_rule", "여러 요소를 새롭게 엮어서 다른 방식을 스스로 만들어본다",
            "creative_ideation", None,
        ),
        ("ci_improve_existing", "기존 규칙 중 반복되는 부분을 찾아 다듬는다", "pattern_finding", None),
        ("ci_test_it", "일단 만들어서 바로 실험해본다", "immediate_execution", None),
        ("ci_visual_design", "어떻게 보여줄지 화면 디자인부터 생각한다", "visual_expression", None),
        # §6: "친구들"(팀 전제)을 "다른 사람들"로 넓혀 혼자 플레이하는 학생도 답할 수
        # 있게 했다.
        ("ci_get_feedback", "다른 사람들에게 아이디어를 먼저 이야기해본다", None, _ASK_FEEDBACK_REASON),
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
    # 2.5단계 §8: 조별·그룹 편중을 줄이려고 "팀의 지시" 전제를 없애고 "친구 관계"
    # 영역(학교생활 분포 기준)으로 옮겼다 — 조별·그룹활동은 opinion_expression_
    # school_life_v1 하나로 제한한다.
    #
    # 2.5.1단계 §10-C: "친한 친구의 말이나 행동이 평소와 달라졌는데 이유를 확실히 알
    # 수 없다면"은 독립적 판단이 마치 무심하거나 성급한 행동처럼 읽힐 위험이 있었다
    # (사용자 지적). 더 중립적인 현실 상황(선택과목·동아리를 친구 추천과 다르게
    # 정하는 것)으로 바꿨다 — 이 상황에서는 "친구에게 묻는다"가 도덕적 정답처럼
    # 보이지 않고, 5개 선택지가 전부 같은 결정 시점(신청 전)에 동시에 존재하며,
    # 독립적 판단·정보 비교·의견 표현·다수 추종을 서로 다른 role로 구분한다(ij_plan_role은
    # planning에서 information_comparison으로, ij_adapt_role은 change_adaptation에서
    # "다수 추종" NO_SIGNAL로 Trait를 바꿨다 — role_id는 유지해 기존 검수 Key를
    # 보존한다).
    question_text=(
        "친구들이 추천하는 선택과목이나 동아리가 내가 원래 관심 있던 것과 다를 때, "
        "무엇을 기준으로 결정하나요?"
    ),
    rows=[
        (
            "ij_set_own_standard", "친구들의 추천과 상관없이, 원래 내가 관심 있던 기준대로 정한다",
            "independent_judgment", None,
        ),
        (
            "ij_ask_clarify", "친구들이 왜 그 과목·동아리를 추천하는지 이유를 물어본다", None,
            "추천 이유를 확인하는 행동일 뿐, 그 자체로 독립적 판단인지 다수 추종인지는 구분되지 않는다",
        ),
        (
            "ij_plan_role", "내 관심사와 친구들의 추천을 각각 장단점으로 정리해서 비교해본다",
            "information_comparison", None,
        ),
        ("ij_speak_role", "원래 어떤 과목·동아리에 관심 있었는지 친구들에게 솔직하게 말한다", "opinion_expression", None),
        (
            "ij_adapt_role", "친구들 대부분이 추천하는 쪽으로 따라간다", None,
            "친구들 다수의 의견을 그대로 따르는 행동으로, 독립적 판단과 구분되는 다수 추종 행동이다",
        ),
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
