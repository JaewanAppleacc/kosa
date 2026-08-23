"""cooking Context Pack — context-pack-lifestyle 작업 배정(2026-08-23).

작업 지시문 "cooking 주의"를 그대로 지킨다:
- 실제 요리 경험을 전제하지 않는다 — 모든 질문을 "~한다면/~해야 한다면" 가정형으로
  묻거나, 레시피를 보기만 하는 상황(직접 조리 없이도 답 가능)으로 구성한다.
- 음식 선택·레시피 이해·재료 대체·과정 계획·맛 조정 다섯 상황을 Anchor로 그대로
  분리해서 쓴다(작업 지시문이 예시로 든 다섯 축).
- 가정환경·조리도구 보유를 전제하지 않는다 — "집에 ~가 있다"처럼 자원 접근성을
  요구하는 표현을 쓰지 않는다."""

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

CONTEXT_ID = "cooking"

ANCHORS = [
    AnchorSpec(
        anchor_id="food_choice", label="음식 선택",
        situation_terms=["메뉴 선택", "취향 반영", "정보 탐색"],
        preferred_scenarios=["먹을 음식이나 만들 요리를 고르는 상황", "여럿이 같이 먹을 음식을 정하는 상황"],
        forbidden_assumptions=["외식이나 배달 등 특정 소비 여건을 전제하지 않는다"],
    ),
    AnchorSpec(
        anchor_id="recipe_understanding", label="레시피 이해",
        situation_terms=["과정 이해", "순서 파악", "세부 확인"],
        preferred_scenarios=["레시피나 요리 방법을 보게 되는 상황", "요리 영상이나 레시피 글을 보는 상황"],
        forbidden_assumptions=["요리책이나 레시피 앱 등 특정 매체 이용 경험을 전제하지 않는다"],
    ),
    AnchorSpec(
        anchor_id="ingredient_substitution", label="재료 대체",
        situation_terms=["대체 재료 탐색", "즉흥 대응", "재료 비교"],
        preferred_scenarios=["레시피에 있는 재료가 없는 상황", "필요한 재료가 마침 떨어진 상황"],
        forbidden_assumptions=["실제로 재료를 사서 요리해본 경험을 전제하지 않는다"],
    ),
    AnchorSpec(
        anchor_id="process_planning", label="과정 계획",
        situation_terms=["순서 계획", "시간 배분", "유연한 대응"],
        preferred_scenarios=["여러 음식을 한 번에 준비해야 하는 상황", "정해진 시간 안에 요리를 끝내야 하는 상황"],
        forbidden_assumptions=["여러 명 분의 식사를 준비해본 경험을 전제하지 않는다"],
    ),
    AnchorSpec(
        anchor_id="taste_adjustment", label="맛 조정",
        situation_terms=["간 맞추기", "세밀한 조절", "의견 반영"],
        preferred_scenarios=["요리를 하다가 맛을 조절해야 하는 상황", "맛이 부족하다고 느껴지는 상황"],
        forbidden_assumptions=["요리를 직접 맛보며 조절해본 경험을 전제하지 않는다"],
    ),
]

ROUTING = build_routing_blueprint(
    context_id=CONTEXT_ID, blueprint_id="cooking_routing_blueprint", question_id="cooking_routing_question",
    question_text="요리나 음식과 관련해 네가 더 흥미를 느끼는 상황은?",
    options=[
        RoutingOptionSpec("route_choice", "먹을 음식이나 메뉴를 고르는 것", "food_choice", "음식 선택"),
        RoutingOptionSpec("route_recipe", "레시피나 요리 방법을 이해하는 것", "recipe_understanding", "레시피 이해"),
        RoutingOptionSpec("route_substitution", "재료가 없을 때 다른 걸로 대체해보는 것", "ingredient_substitution", "재료 대체"),
        RoutingOptionSpec("route_process", "여러 음식을 준비할 순서나 계획을 세우는 것", "process_planning", "과정 계획"),
        RoutingOptionSpec("route_taste", "맛을 보고 간을 조절하는 것", "taste_adjustment", "맛 조정"),
    ],
)

_SPECS: dict[str, dict[str, object]] = {
    "food_choice": {
        "seed": (
            "cooking_seed_food_choice", "choice_seed",
            "먹을 음식이나 만들 요리를 고를 때, 너에게 가까운 모습은?",
            [
                OptionSpec("try_unfamiliar_combo", "새로운 음식이나 안 먹어본 조합을 시도해보고 싶다", "novelty_seeking",
                           "안 먹어본 조합을 시도해보려는 행동이 직접 드러나 novelty_seeking 후보로 연결된다"),
                OptionSpec("search_and_compare_before_choosing", "정보를 찾아보고 비교해서 고른다", "information_comparison",
                           "정보를 찾아 비교해서 고르는 행동이 직접 드러나 information_comparison 후보로 연결된다"),
                OptionSpec("prioritize_what_i_like", "내가 좋아하는 걸 우선으로 고른다", "personal_goal_priority",
                           "자신이 좋아하는 것을 우선 기준으로 삼는 행동이 직접 드러나 personal_goal_priority 후보로 연결된다"),
                OptionSpec("ask_others_and_match", "다른 사람들 의견을 물어보고 맞춘다", "collaboration_preference",
                           "다른 사람 의견을 물어 함께 맞추는 행동이 직접 드러나 collaboration_preference 후보로 연결된다"),
                OptionSpec("pick_whatever_feels_right", "그때그때 끌리는 대로 고른다", None,
                           "특별한 기준 없이 끌리는 대로 고르는 것은 특정 성향의 직접 근거로 보기 어렵다"),
            ],
        ),
        "backup": (
            "cooking_backup_food_choice", "backup",
            "여럿이 같이 먹을 음식을 정해야 한다면, 너에게 가까운 모습은?",
            [
                OptionSpec("suggest_untried_menu", "안 먹어본 메뉴를 제안해보고 싶다", "novelty_seeking",
                           "안 먹어본 메뉴를 제안해보려는 행동이 직접 드러나 novelty_seeking 후보로 연결된다"),
                OptionSpec("search_reviews_to_compare", "메뉴들을 검색하거나 후기를 찾아 비교한다", "information_comparison",
                           "후기를 찾아 비교하는 행동이 직접 드러나 information_comparison 후보로 연결된다"),
                OptionSpec("say_what_i_want_first", "내가 먹고 싶은 걸 우선 얘기한다", "personal_goal_priority",
                           "자신이 원하는 것을 우선 말하는 행동이 직접 드러나 personal_goal_priority 후보로 연결된다"),
                OptionSpec("listen_and_match_others", "다른 사람들 의견을 들어보고 맞춘다", "collaboration_preference",
                           "다른 사람 의견을 듣고 맞추는 행동이 직접 드러나 collaboration_preference 후보로 연결된다"),
                OptionSpec("anything_is_fine", "아무거나 상관없다고 생각한다", None,
                           "아무거나 상관없다는 것은 특정 성향의 직접 근거가 되지 않는다"),
            ],
        ),
    },
    "recipe_understanding": {
        "seed": (
            "cooking_seed_recipe_understanding", "recipe_seed",
            "레시피나 요리 방법을 보게 될 때, 너에게 가까운 모습은?",
            [
                OptionSpec("think_why_this_order", "왜 이 순서로 해야 하는지 이유를 생각해본다", "causal_analysis",
                           "순서의 이유를 스스로 생각해보는 행동이 직접 드러나 causal_analysis 후보로 연결된다"),
                OptionSpec("organize_steps_in_order", "단계를 순서대로 정리해서 이해하려 한다", "planning",
                           "단계를 순서대로 정리해서 이해하려는 행동이 직접 드러나 planning 후보로 연결된다"),
                OptionSpec("see_whole_process_structure", "레시피의 전체 과정이 어떻게 연결되는지 구조적으로 본다", "systems_thinking",
                           "전체 과정의 연결 구조를 파악하는 행동이 직접 드러나 systems_thinking 후보로 연결된다"),
                OptionSpec("check_measure_and_time_carefully", "세세한 계량이나 시간까지 신경 써서 본다", "detail_orientation",
                           "계량·시간 같은 세부까지 신경 써서 보는 행동이 직접 드러나 detail_orientation 후보로 연결된다"),
                OptionSpec("dont_look_closely", "레시피를 자세히 들여다보진 않는다", None,
                           "자세히 들여다보지 않는 것은 특정 성향의 직접 근거로 보기 어렵다"),
            ],
        ),
        "backup": (
            "cooking_backup_recipe_understanding", "backup",
            "요리 영상이나 레시피 글을 보게 된다면, 너에게 가까운 모습은?",
            [
                OptionSpec("question_why_this_step_needed", "이 과정이 왜 필요한지 이유를 따져본다", "causal_analysis",
                           "과정이 필요한 이유를 따져보는 행동이 직접 드러나 causal_analysis 후보로 연결된다"),
                OptionSpec("organize_order_mentally", "순서를 머릿속으로 정리하며 따라간다", "planning",
                           "순서를 정리하며 따라가는 행동이 직접 드러나 planning 후보로 연결된다"),
                OptionSpec("grasp_process_connection", "전체 과정이 어떻게 이어지는지 구조를 파악한다", "systems_thinking",
                           "전체 과정의 연결 구조를 파악하는 행동이 직접 드러나 systems_thinking 후보로 연결된다"),
                OptionSpec("check_detail_carefully", "계량이나 시간 같은 세부 정보를 꼼꼼히 본다", "detail_orientation",
                           "세부 정보를 꼼꼼히 확인하는 행동이 직접 드러나 detail_orientation 후보로 연결된다"),
                OptionSpec("skim_and_move_on", "대충 훑어보고 넘어간다", None,
                           "대충 훑어보고 넘어가는 것은 특정 성향의 직접 근거로 보기 어렵다"),
            ],
        ),
    },
    "ingredient_substitution": {
        "seed": (
            "cooking_seed_ingredient_substitution", "substitution_seed",
            "레시피에 있는 재료가 없다면, 너에게 가까운 모습은?",
            [
                OptionSpec("think_of_alternative_myself", "대신 쓸 수 있는 다른 재료를 스스로 생각해본다", "creative_ideation",
                           "대체 재료를 스스로 떠올리는 행동이 직접 드러나 creative_ideation 후보로 연결된다"),
                OptionSpec("compare_similar_ingredients", "비슷한 재료들을 비교해서 뭐가 나을지 따져본다", "information_comparison",
                           "비슷한 재료를 비교해서 따져보는 행동이 직접 드러나 information_comparison 후보로 연결된다"),
                OptionSpec("try_substitute_despite_unsure", "확실하지 않아도 일단 대체해서 시도해본다", "uncertainty_tolerance",
                           "확실하지 않아도 일단 대체해서 시도하는 행동이 직접 드러나 uncertainty_tolerance 후보로 연결된다"),
                OptionSpec("switch_to_another_way", "없으면 없는 대로 다른 방법을 찾는다", "change_adaptation",
                           "상황에 맞춰 다른 방법을 찾는 행동이 직접 드러나 change_adaptation 후보로 연결된다"),
                OptionSpec("just_skip_making_it", "재료가 없으면 그냥 안 만든다", None,
                           "그냥 만들지 않는다는 것은 특정 성향의 직접 근거가 되지 않는다"),
            ],
        ),
        "backup": (
            "cooking_backup_ingredient_substitution", "backup",
            "필요한 재료가 마침 다 떨어졌다면, 너에게 가까운 모습은?",
            [
                OptionSpec("come_up_with_substitute", "대체할 만한 다른 재료를 스스로 떠올려본다", "creative_ideation",
                           "대체 재료를 스스로 떠올리는 행동이 직접 드러나 creative_ideation 후보로 연결된다"),
                OptionSpec("compare_which_is_better", "어떤 재료가 더 나을지 비교해본다", "information_comparison",
                           "어떤 재료가 나을지 비교하는 행동이 직접 드러나 information_comparison 후보로 연결된다"),
                OptionSpec("try_even_if_unsure_result", "잘 될지 몰라도 일단 다른 걸로 시도해본다", "uncertainty_tolerance",
                           "결과가 불확실해도 시도해보는 행동이 직접 드러나 uncertainty_tolerance 후보로 연결된다"),
                OptionSpec("change_method_or_menu", "다른 방법이나 메뉴로 바꾼다", "change_adaptation",
                           "상황에 맞춰 방법·메뉴를 바꾸는 행동이 직접 드러나 change_adaptation 후보로 연결된다"),
                OptionSpec("just_give_up", "그냥 포기한다", None,
                           "그냥 포기하는 것은 특정 성향의 직접 근거가 되지 않는다"),
            ],
        ),
    },
    "process_planning": {
        "seed": (
            "cooking_seed_process_planning", "process_seed",
            "여러 음식을 한 번에 준비해야 한다면, 너에게 가까운 모습은?",
            [
                OptionSpec("decide_order_in_advance", "무엇을 먼저 할지 순서를 미리 정한다", "planning",
                           "무엇을 먼저 할지 순서를 미리 정하는 행동이 직접 드러나 planning 후보로 연결된다"),
                OptionSpec("keep_pushing_to_finish_in_time", "시간 안에 끝내려고 계속 신경 쓴다", "persistence_completion",
                           "시간 안에 끝내려고 계속 신경 쓰는 행동이 직접 드러나 persistence_completion 후보로 연결된다"),
                OptionSpec("adjust_order_flexibly", "상황에 따라 순서를 바꿔가며 유연하게 대응한다", "change_adaptation",
                           "상황에 따라 순서를 유연하게 바꾸는 행동이 직접 드러나 change_adaptation 후보로 연결된다"),
                OptionSpec("feel_burdened_just_thinking", "생각만 해도 부담스러워서 피하고 싶다", None,
                           "부담을 느껴 피하고 싶다는 감정은 특정 성향의 직접 근거로 보기 어렵다"),
                OptionSpec("rarely_such_situation", "그런 상황은 별로 없었다", None,
                           "그런 상황이 없었다는 것은 특정 성향의 직접 근거가 되지 않는다"),
            ],
        ),
        "backup": (
            "cooking_backup_process_planning", "backup",
            "정해진 시간 안에 요리를 끝내야 한다면, 너에게 가까운 모습은?",
            [
                OptionSpec("plan_task_order_ahead", "할 일의 순서를 미리 정해둔다", "planning",
                           "할 일의 순서를 미리 정해두는 행동이 직접 드러나 planning 후보로 연결된다"),
                OptionSpec("finish_despite_lack_of_time", "시간이 부족해도 끝까지 마치려 한다", "persistence_completion",
                           "시간이 부족해도 끝까지 마치려는 행동이 직접 드러나 persistence_completion 후보로 연결된다"),
                OptionSpec("adapt_order_to_situation", "상황에 맞춰 순서를 바꿔가며 대응한다", "change_adaptation",
                           "상황에 맞춰 순서를 바꿔 대응하는 행동이 직접 드러나 change_adaptation 후보로 연결된다"),
                OptionSpec("feel_burdened_by_time_limit", "그런 상황이면 부담스럽게 느껴진다", None,
                           "부담스럽게 느껴진다는 감정은 특정 성향의 직접 근거로 보기 어렵다"),
                OptionSpec("dont_care_much", "별로 신경 쓰지 않는다", None,
                           "신경 쓰지 않는다는 것은 특정 성향의 직접 근거가 되지 않는다"),
            ],
        ),
    },
    "taste_adjustment": {
        "seed": (
            "cooking_seed_taste_adjustment", "taste_seed",
            "요리를 하다가 간을 보고 맛을 조절해야 한다면, 너에게 가까운 모습은?",
            [
                OptionSpec("adjust_taste_bit_by_bit", "조금씩 맛을 보면서 세밀하게 조절한다", "detail_orientation",
                           "조금씩 맛보며 세밀하게 조절하는 행동이 직접 드러나 detail_orientation 후보로 연결된다"),
                OptionSpec("judge_by_my_own_taste", "내 입맛을 기준으로 판단해서 조절한다", "independent_judgment",
                           "자신의 입맛을 기준으로 스스로 판단하는 행동이 직접 드러나 independent_judgment 후보로 연결된다"),
                OptionSpec("ask_others_taste_too", "다른 사람 입맛도 물어보고 맞추려 한다", "opinion_mediation",
                           "다른 사람 입맛을 물어보고 맞추는 행동이 직접 드러나 opinion_mediation 후보로 연결된다"),
                OptionSpec("roughly_match_by_feel", "감으로 대충 맞춰서 넘어간다", None,
                           "감으로 대충 맞추는 것은 특정 성향의 직접 근거로 보기 어렵다"),
                OptionSpec("dont_care_about_taste_much", "맛 조절에 크게 신경 쓰지 않는다", None,
                           "맛 조절에 신경 쓰지 않는다는 것은 특정 성향의 직접 근거가 되지 않는다"),
            ],
        ),
        "backup": (
            "cooking_backup_taste_adjustment", "backup",
            "맛이 뭔가 부족하다고 느껴질 때, 너에게 가까운 모습은?",
            [
                OptionSpec("add_little_by_little", "조금씩 더해가며 세밀하게 맞춘다", "detail_orientation",
                           "조금씩 더해가며 세밀하게 맞추는 행동이 직접 드러나 detail_orientation 후보로 연결된다"),
                OptionSpec("judge_by_my_own_sense", "내가 느끼는 맛을 기준으로 판단한다", "independent_judgment",
                           "자신이 느끼는 맛을 기준으로 판단하는 행동이 직접 드러나 independent_judgment 후보로 연결된다"),
                OptionSpec("ask_how_others_feel", "다른 사람은 어떻게 느끼는지 물어본다", "opinion_mediation",
                           "다른 사람이 어떻게 느끼는지 물어보는 행동이 직접 드러나 opinion_mediation 후보로 연결된다"),
                OptionSpec("leave_it_as_good_enough", "그 정도면 됐다고 넘어간다", None,
                           "그 정도면 됐다고 넘기는 것은 특정 성향의 직접 근거로 보기 어렵다"),
                OptionSpec("focus_on_other_things", "맛보다는 다른 부분에 더 신경 쓴다", None,
                           "맛보다 다른 부분에 신경 쓴다는 것은 맛 조정 행동을 보여주지 않아 근거로 보기 약하다"),
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
            "실제로 요리를 해본 경험을 전제하지 않는다",
            "가정에서 조리도구나 재료를 자유롭게 쓸 수 있는 환경을 전제하지 않는다",
            "특정 가사 역할이나 성별에 따른 요리 참여를 기대하지 않는다",
        ],
        review_artifact_paths=["data/reviews/context_packs/cooking_review_status.json"],
        pack_version="lifestyle_v1.0-draft",
    )


CONTEXT_PACK: ContextPack = _build_pack()
