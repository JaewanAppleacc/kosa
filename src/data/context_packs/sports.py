"""sports Context Pack — context-pack-lifestyle 작업 배정(2026-08-23).

`context_pack_development_guide.md` §1/§2 계약을 따른다. Anchor 5개는 작업 지시문이
지정한 분리 기준을 그대로 따른다 — 관람·기록 향상·전략·개인 운동·팀 상황. 아래 원칙을
지킨다(작업 지시문 "sports 주의"):
- 스포츠 관심을 경쟁성·협동성으로 자동 연결하지 않는다 — `team_situation`의
  collaboration_preference/opinion_mediation은 "관심이 있다"가 아니라 팀 상황에서
  실제로 어떻게 행동하겠다고 답했는지에서만 나온다.
- 선수 경험·팀 스포츠 경험을 전제하지 않는다 — 모든 질문이 "~한다면"처럼 가정형으로
  묻거나, 직접 경험 없이도 답할 수 있는 상황(관람·개인 연습·정보 탐색)으로 구성한다.
- 체력이나 운동 능력을 평가하지 않는다 — Trait Mapping은 전부 준비 방식·판단 방식·
  태도에 대한 것이고, 기록의 절대적 수준을 묻지 않는다."""

from __future__ import annotations

from src.data.context_packs._lifestyle_pack_shared import (
    AnchorSpec,
    OptionSpec,
    RoutingOptionSpec,
    build_anchor_presentation,
    build_question,
    build_rationales,
    build_routing_blueprint,
)
from src.schemas.context_pack import ContextPack, ContextPackAnchorBackupQuestion, ContextPackSeedAnchorQuestion

CONTEXT_ID = "sports"

ANCHORS = [
    AnchorSpec(
        anchor_id="spectating_analysis", label="관람·분석",
        situation_terms=["경기 관람", "기록·데이터 확인", "장면 복기"],
        preferred_scenarios=["중계를 보다가 흥미로운 장면이 나온 상황", "결과가 예상과 다르게 나온 상황"],
        forbidden_assumptions=["경기장에 직접 가본 경험을 전제하지 않는다", "특정 종목을 꾸준히 관람한 경험을 전제하지 않는다"],
    ),
    AnchorSpec(
        anchor_id="record_improvement", label="개인 기록 향상",
        situation_terms=["개인 목표 설정", "기록 관리", "꾸준한 연습"],
        preferred_scenarios=["스스로 정한 목표(시간·횟수 등)를 향해 나아가는 상황", "체력 검정이나 개인 기록 측정을 앞둔 상황"],
        forbidden_assumptions=["신체 능력 수준이나 실제 기록 자체를 평가하지 않는다", "특정 종목 숙련도를 전제하지 않는다"],
    ),
    AnchorSpec(
        anchor_id="strategy_tactics", label="전략 분석",
        situation_terms=["작전 이해", "전략 판단", "상황 대응"],
        preferred_scenarios=["경기의 작전·전략을 이야기하는 상황", "경기를 보며 다음 수를 예상해보는 상황"],
        forbidden_assumptions=["선수·감독 경험을 전제하지 않는다"],
    ),
    AnchorSpec(
        anchor_id="individual_training", label="개인 운동",
        situation_terms=["혼자 하는 운동", "루틴 구성", "운동 도구·앱 활용"],
        preferred_scenarios=["혼자 운동 방식을 정하는 상황", "운동 루틴을 스스로 짜야 하는 상황"],
        forbidden_assumptions=["특정 운동 기구나 시설 접근성을 전제하지 않는다", "운동 능력 수준을 평가하지 않는다"],
    ),
    AnchorSpec(
        anchor_id="team_situation", label="팀 상황",
        situation_terms=["팀 활동", "의견 조율", "역할 분담"],
        preferred_scenarios=["팀으로 경기를 하게 된다면 벌어질 수 있는 상황(가정형)", "체육 시간에 팀을 나눠 활동하는 상황"],
        forbidden_assumptions=["실제 팀 스포츠 소속 경험을 전제하지 않는다", "성별에 따라 다른 팀 스포츠 참여를 기대하지 않는다"],
    ),
]

ROUTING = build_routing_blueprint(
    context_id=CONTEXT_ID, blueprint_id="sports_routing_blueprint", question_id="sports_routing_question",
    question_text="스포츠와 관련해 네가 가장 흥미를 느끼는 상황은?",
    options=[
        RoutingOptionSpec("route_spectate", "경기를 보면서 분석하거나 데이터를 찾아보는 것", "spectating_analysis", "관람·분석"),
        RoutingOptionSpec("route_record", "내 기록이나 실력을 발전시켜 나가는 것", "record_improvement", "개인 기록 향상"),
        RoutingOptionSpec("route_strategy", "전략이나 작전을 생각해보는 것", "strategy_tactics", "전략 분석"),
        RoutingOptionSpec("route_individual", "혼자 운동하며 나만의 방식을 찾는 것", "individual_training", "개인 운동"),
        RoutingOptionSpec("route_team", "팀으로 함께 경기하는 상황", "team_situation", "팀 상황"),
    ],
)

_SPECS: dict[str, dict[str, object]] = {
    "spectating_analysis": {
        "seed": (
            "sports_seed_spectating_analysis", "spectating_seed",
            "경기를 보다가 흥미로운 장면이 나왔을 때, 너는 주로 무엇을 하게 되니?",
            [
                OptionSpec("recall_flow_order", "경기 흐름이 어떻게 바뀌었는지 순서대로 다시 떠올려본다", "pattern_finding",
                           "장면을 순서대로 되짚어 흐름 규칙을 찾는 행동이 직접 드러나 pattern_finding 후보로 연결된다"),
                OptionSpec("trace_cause", "왜 그 상황이 벌어졌는지 원인을 짚어본다", "causal_analysis",
                           "결과가 나온 원인을 능동적으로 짚어보는 행동이 직접 드러나 causal_analysis 후보로 연결된다"),
                OptionSpec("compare_records", "선수나 팀의 기록·데이터를 찾아 비교해본다", "information_comparison",
                           "선수·팀 기록을 찾아 비교하는 행동이 직접 드러나 information_comparison 후보로 연결된다"),
                OptionSpec("want_to_share", "친구에게 그 장면 얘기를 하고 싶어진다", None,
                           "이야기하고 싶어지는 감정은 있지만 무엇을 분석·비교했는지는 드러나지 않아 특정 성향의 직접 근거로 보기 약하다"),
                OptionSpec("just_watch", "특별히 하는 건 없고 그냥 본다", None,
                           "특별한 행동 없이 지켜보는 것은 관심 표현일 뿐, 특정 성향의 직접 근거로 보기 어렵다"),
            ],
        ),
        "backup": (
            "sports_backup_spectating_analysis", "backup",
            "경기 결과가 예상과 다르게 나왔을 때, 너의 반응에 가장 가까운 건?",
            [
                OptionSpec("retrace_sequence", "결과가 나오기까지 흐름을 다시 순서대로 짚어본다", "pattern_finding",
                           "결과에 이르기까지 흐름을 순서대로 되짚는 행동이 직접 드러나 pattern_finding 후보로 연결된다"),
                OptionSpec("find_decisive_cause", "무엇이 결정적 원인이었는지 따져본다", "causal_analysis",
                           "결정적 원인을 따져보는 행동이 직접 드러나 causal_analysis 후보로 연결된다"),
                OptionSpec("check_related_stats", "관련 기록이나 통계를 찾아본다", "information_comparison",
                           "관련 기록·통계를 찾아보는 행동이 직접 드러나 information_comparison 후보로 연결된다"),
                OptionSpec("guess_next_time", "다음엔 어떻게 될지 예상해본다", None,
                           "다음 결과를 막연히 예상해보는 것은 특정 성향을 직접 보여주는 근거로 보기 약하다"),
                OptionSpec("let_it_go", "별다른 생각 없이 넘어간다", None,
                           "별다른 반응 없이 넘어가는 것은 특정 성향의 직접 근거가 되지 않는다"),
            ],
        ),
    },
    "record_improvement": {
        "seed": (
            "sports_seed_record_improvement", "record_seed",
            "운동이나 신체 활동에서 스스로 정한 목표(예: 시간 줄이기, 개수 늘리기)를 향해 갈 때, 너에게 가까운 모습은?",
            [
                OptionSpec("plan_stepwise", "구체적인 계획을 세우고 단계별로 접근한다", "planning",
                           "목표를 향한 단계를 미리 계획해서 접근하는 행동이 직접 드러나 planning 후보로 연결된다"),
                OptionSpec("keep_going_despite_tired", "쉬고 싶어도 꾸준히 이어가려 한다", "persistence_completion",
                           "힘들어도 정해둔 만큼 꾸준히 이어가는 행동이 직접 드러나 persistence_completion 후보로 연결된다"),
                OptionSpec("focus_on_own_record", "내 기록에 집중하고 남과 비교하지 않는다", "personal_goal_priority",
                           "타인과 비교하지 않고 자신의 목표 기준을 우선하는 행동이 직접 드러나 personal_goal_priority 후보로 연결된다"),
                OptionSpec("adjust_fine_details", "자세나 방법의 세부적인 부분을 계속 조정한다", "detail_orientation",
                           "자세나 방법의 세부를 계속 조정하는 행동이 직접 드러나 detail_orientation 후보로 연결된다"),
                OptionSpec("no_particular_care", "특별히 신경 쓰지 않고 그때그때 한다", None,
                           "특별한 접근 없이 그때그때 하는 것은 특정 성향의 직접 근거로 보기 어렵다"),
            ],
        ),
        "backup": (
            "sports_backup_record_improvement", "backup",
            "체력 검정이나 개인 기록 측정을 앞두고 있다면, 너의 준비 방식에 가까운 건?",
            [
                OptionSpec("plan_order_ahead", "언제까지 어떤 순서로 준비할지 계획을 세운다", "planning",
                           "준비 순서와 시점을 미리 계획하는 행동이 직접 드러나 planning 후보로 연결된다"),
                OptionSpec("finish_what_i_set", "힘들어도 정해둔 만큼은 끝까지 한다", "persistence_completion",
                           "정해둔 만큼 끝까지 해내려는 행동이 직접 드러나 persistence_completion 후보로 연결된다"),
                OptionSpec("compare_to_past_self", "다른 사람 기록보다 내 이전 기록과 비교한다", "personal_goal_priority",
                           "타인 기록이 아닌 자신의 이전 기록을 기준으로 삼는 행동이 직접 드러나 personal_goal_priority 후보로 연결된다"),
                OptionSpec("check_motion_detail", "동작 하나하나를 세밀하게 점검한다", "detail_orientation",
                           "동작을 하나하나 세밀히 점검하는 행동이 직접 드러나 detail_orientation 후보로 연결된다"),
                OptionSpec("prepare_when_it_comes", "닥치면 그때 한다", None,
                           "닥쳐서야 준비하는 것은 특정 성향의 직접 근거로 보기 어렵다"),
            ],
        ),
    },
    "strategy_tactics": {
        "seed": (
            "sports_seed_strategy_tactics", "strategy_seed",
            "스포츠 경기의 작전이나 전략을 이야기할 때, 너에게 가까운 태도는?",
            [
                OptionSpec("break_into_structure", "여러 상황을 구조적으로 나눠서 이해하려 한다", "systems_thinking",
                           "여러 상황을 구조적으로 나눠 이해하려는 행동이 직접 드러나 systems_thinking 후보로 연결된다"),
                OptionSpec("switch_approach_fast", "정해진 전략이 안 통하면 다른 방법을 빠르게 생각해본다", "change_adaptation",
                           "안 통하는 전략을 빠르게 다른 방법으로 바꾸는 행동이 직접 드러나 change_adaptation 후보로 연결된다"),
                OptionSpec("decide_despite_uncertainty", "확실하지 않은 상황에서도 판단을 내려본다", "uncertainty_tolerance",
                           "확실하지 않아도 판단을 내려보는 행동이 직접 드러나 uncertainty_tolerance 후보로 연결된다"),
                OptionSpec("judge_my_own_way", "내 나름의 관점으로 전략을 판단한다(다른 사람 의견과 달라도)", "independent_judgment",
                           "다른 의견과 달라도 자기 관점으로 판단하는 행동이 직접 드러나 independent_judgment 후보로 연결된다"),
                OptionSpec("not_much_interest", "전략 얘기는 잘 모르겠고 관심이 적다", None,
                           "관심이 적다는 것은 특정 성향의 직접 근거가 되지 않는다"),
            ],
        ),
        "backup": (
            "sports_backup_strategy_tactics", "backup",
            "경기를 보다가 '이럴 땐 이렇게 해야지'라는 생각이 들 때, 너에게 가까운 모습은?",
            [
                OptionSpec("examine_situation_piece_by_piece", "상황을 나눠서 하나씩 짚어보며 이해한다", "systems_thinking",
                           "상황을 나눠 하나씩 짚어보며 이해하는 행동이 직접 드러나 systems_thinking 후보로 연결된다"),
                OptionSpec("switch_idea_quickly", "생각한 방법이 안 맞으면 바로 다른 방법을 떠올린다", "change_adaptation",
                           "맞지 않는 방법을 바로 다른 방법으로 바꾸는 행동이 직접 드러나 change_adaptation 후보로 연결된다"),
                OptionSpec("commit_despite_unsure", "정답이 확실치 않아도 내 판단을 내려본다", "uncertainty_tolerance",
                           "확실치 않아도 판단을 내리는 행동이 직접 드러나 uncertainty_tolerance 후보로 연결된다"),
                OptionSpec("trust_own_view", "다른 사람 의견과 다르더라도 내 생각대로 판단한다", "independent_judgment",
                           "다른 의견과 달라도 자신의 판단을 따르는 행동이 직접 드러나 independent_judgment 후보로 연결된다"),
                OptionSpec("rarely_think_that_far", "그런 생각까지는 잘 안 하게 된다", None,
                           "그런 생각을 잘 하지 않는 것은 특정 성향의 직접 근거가 되지 않는다"),
            ],
        ),
    },
    "individual_training": {
        "seed": (
            "sports_seed_individual_training", "training_seed",
            "혼자 운동을 한다면, 너에게 더 가까운 모습은?",
            [
                OptionSpec("try_new_method", "새로운 운동 방법이나 종목을 시도해보고 싶다", "novelty_seeking",
                           "새로운 운동 방법이나 종목을 시도해보려는 행동이 직접 드러나 novelty_seeking 후보로 연결된다"),
                OptionSpec("decide_my_own_way", "다른 사람 방식보다 내가 편한 방식을 스스로 정한다", "independent_judgment",
                           "다른 방식보다 자신에게 맞는 방식을 스스로 정하는 행동이 직접 드러나 independent_judgment 후보로 연결된다"),
                OptionSpec("use_tracking_app", "운동 앱이나 기록 도구를 활용해서 관리한다", "tool_utilization",
                           "앱이나 기록 도구를 실제로 활용하는 행동이 직접 드러나 tool_utilization 후보로 연결된다"),
                OptionSpec("adjust_to_conditions", "상황(날씨, 시간)에 따라 운동 방식을 바꾼다", "change_adaptation",
                           "날씨·시간 같은 상황에 맞춰 운동 방식을 바꾸는 행동이 직접 드러나 change_adaptation 후보로 연결된다"),
                OptionSpec("not_drawn_to_solo", "혼자 운동하는 건 별로 안 끌린다", None,
                           "혼자 운동에 끌리지 않는다는 것은 특정 성향의 직접 근거가 되지 않는다"),
            ],
        ),
        "backup": (
            "sports_backup_individual_training", "backup",
            "운동 루틴을 스스로 짜야 한다면, 너에게 가까운 모습은?",
            [
                OptionSpec("add_untried_style", "안 해본 방식이나 종목을 넣어보고 싶다", "novelty_seeking",
                           "안 해본 방식을 루틴에 넣어보려는 행동이 직접 드러나 novelty_seeking 후보로 연결된다"),
                OptionSpec("pick_what_fits_me", "남들이 추천하는 것보다 내게 맞는 방식을 스스로 고른다", "independent_judgment",
                           "추천보다 자신에게 맞는 방식을 스스로 고르는 행동이 직접 드러나 independent_judgment 후보로 연결된다"),
                OptionSpec("use_app_or_video", "기록 앱이나 영상 같은 도구를 활용해 점검한다", "tool_utilization",
                           "앱이나 영상 도구를 활용해 점검하는 행동이 직접 드러나 tool_utilization 후보로 연결된다"),
                OptionSpec("adjust_to_condition", "그날 컨디션이나 상황에 맞춰 루틴을 바꾼다", "change_adaptation",
                           "컨디션이나 상황에 맞춰 루틴을 바꾸는 행동이 직접 드러나 change_adaptation 후보로 연결된다"),
                OptionSpec("rarely_plan_myself", "루틴을 직접 짜는 건 잘 안 하게 된다", None,
                           "직접 루틴을 짜지 않는 것은 특정 성향의 직접 근거가 되지 않는다"),
            ],
        ),
    },
    "team_situation": {
        "seed": (
            "sports_seed_team_situation", "team_seed",
            "팀으로 경기를 하게 된다면, 의견이 갈릴 때 너에게 가까운 모습은?",
            [
                OptionSpec("mediate_opinions", "여러 의견을 조율해서 하나로 모으려 한다", "opinion_mediation",
                           "여러 의견을 조율해서 모으려는 행동이 직접 드러나 opinion_mediation 후보로 연결된다"),
                OptionSpec("state_my_view_clearly", "내 생각을 분명하게 이야기하는 편이다", "opinion_expression",
                           "자기 생각을 분명하게 말하는 행동이 직접 드러나 opinion_expression 후보로 연결된다"),
                OptionSpec("prefer_working_with_roles", "팀원들과 역할을 나눠 함께 움직이는 게 편하다", "collaboration_preference",
                           "역할을 나눠 함께 움직이는 방식을 선호하는 행동이 직접 드러나 collaboration_preference 후보로 연결된다"),
                OptionSpec("read_teammates_mood", "팀원의 표정이나 반응을 보고 분위기를 파악한다", "emotional_interpretation",
                           "표정이나 반응을 보고 분위기를 파악하는 행동이 직접 드러나 emotional_interpretation 후보로 연결된다"),
                OptionSpec("not_fond_of_team_games", "팀 경기 자체를 별로 안 좋아한다", None,
                           "팀 경기를 좋아하지 않는다는 것은 특정 성향의 직접 근거가 되지 않는다"),
            ],
        ),
        "backup": (
            "sports_backup_team_situation", "backup",
            "체육 시간에 팀을 나눠서 활동하게 된다면, 너에게 가까운 태도는?",
            [
                OptionSpec("gather_opinions_and_decide", "다양한 의견을 들어보고 정리해서 결정한다", "opinion_mediation",
                           "여러 의견을 들어 정리한 뒤 결정하는 행동이 직접 드러나 opinion_mediation 후보로 연결된다"),
                OptionSpec("speak_my_opinion_first", "내 의견을 먼저 말하는 편이다", "opinion_expression",
                           "의견을 먼저 말하는 행동이 직접 드러나 opinion_expression 후보로 연결된다"),
                OptionSpec("prefer_shared_roles", "역할을 나눠서 같이 하는 방식이 편하다", "collaboration_preference",
                           "역할을 나눠 함께 하는 방식을 선호하는 행동이 직접 드러나 collaboration_preference 후보로 연결된다"),
                OptionSpec("watch_teammates_reaction", "팀원들 반응을 살피며 맞춰간다", "emotional_interpretation",
                           "팀원 반응을 살피며 맞춰가는 행동이 직접 드러나 emotional_interpretation 후보로 연결된다"),
                OptionSpec("find_team_activity_burdensome", "팀으로 하는 활동 자체가 부담스럽다", None,
                           "팀 활동을 부담스러워하는 것은 특정 성향의 직접 근거가 되지 않는다"),
            ],
        ),
    },
}


def _build_pack() -> ContextPack:
    seed_variants: list[ContextPackSeedAnchorQuestion] = []
    backup_questions: list[ContextPackAnchorBackupQuestion] = []
    rationales = []

    for anchor_id, spec in _SPECS.items():
        seed_question_id, seed_frame, seed_text, seed_options = spec["seed"]
        seed_question = build_question(
            question_id=seed_question_id, context_id=CONTEXT_ID, frame_id=seed_frame,
            question_text=seed_text, options=seed_options,
        )
        seed_variants.append(ContextPackSeedAnchorQuestion(anchor_id=anchor_id, question=seed_question))
        rationales.extend(build_rationales(seed_question, "seed_anchor", seed_options))

        backup_question_id, backup_frame, backup_text, backup_options = spec["backup"]
        backup_question = build_question(
            question_id=backup_question_id, context_id=CONTEXT_ID, frame_id=backup_frame,
            question_text=backup_text, options=backup_options,
        )
        backup_questions.append(ContextPackAnchorBackupQuestion(anchor_id=anchor_id, question=backup_question))
        rationales.extend(build_rationales(backup_question, "anchor_backup", backup_options))

    return ContextPack(
        context_id=CONTEXT_ID,
        routing_blueprint=ROUTING,
        anchor_presentations=[build_anchor_presentation(CONTEXT_ID, spec) for spec in ANCHORS],
        seed_anchor_variants=seed_variants,
        anchor_backup_questions=backup_questions,
        option_mapping_rationales=rationales,
        direct_probe_candidates=[],
        forbidden_assumptions=[
            "선수 경험이나 팀 스포츠 소속 경험을 전제하지 않는다",
            "체력·운동 능력 수준을 평가하거나 추론하지 않는다",
            "스포츠에 대한 관심을 경쟁성이나 협동성으로 자동 연결하지 않는다",
        ],
        review_artifact_paths=["data/reviews/context_packs/sports_review_status.json"],
        pack_version="lifestyle_v1.0-draft",
    )


CONTEXT_PACK: ContextPack = _build_pack()
