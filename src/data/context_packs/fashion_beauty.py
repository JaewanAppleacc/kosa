"""fashion_beauty Context Pack — context-pack-lifestyle 작업 배정(2026-08-23).

작업 지시문 "fashion_beauty 주의"를 그대로 지킨다:
- 성별·외모·체형 고정관념을 두지 않는다 — 질문·선택지 어디에도 성별을 전제하거나
  체형·외모를 언급하지 않는다.
- 고가 제품 구매 경험을 전제하지 않는다 — "산다/구매한다"가 아니라 "고른다/찾아본다/
  조합한다"처럼 경제력과 무관하게 답할 수 있는 행동으로만 묻는다.
- 스타일 조합·정보 비교·상황 적합성·표현 선택 네 상황을 Anchor로 활용한다(작업
  지시문이 예시로 든 네 축) — 다섯 번째 Anchor로 유행 변화 대응을 추가해 5개를
  채운다.
- 외모 자신감이나 인기 여부를 Trait로 추론하지 않는다 — Trait Mapping은 전부 "어떻게
  판단·표현·비교하는가"에 대한 것이고, 자신감·인기 같은 사회적 평가를 묻지 않는다."""

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

CONTEXT_ID = "fashion_beauty"

ANCHORS = [
    AnchorSpec(
        anchor_id="style_combination", label="스타일 조합",
        situation_terms=["코디 조합", "새 조합 시도", "세부 조정"],
        preferred_scenarios=["옷차림이나 스타일을 조합하는 상황", "가진 아이템으로 새로운 조합을 만들어보는 상황"],
        forbidden_assumptions=["특정 브랜드나 고가 아이템 소유를 전제하지 않는다"],
    ),
    AnchorSpec(
        anchor_id="info_comparison", label="정보 비교·트렌드 탐색",
        situation_terms=["후기 비교", "유행 탐색", "이유 궁금증"],
        preferred_scenarios=["옷·뷰티 관련 정보를 찾아보는 상황", "새로운 뷰티·패션 정보를 접하는 상황"],
        forbidden_assumptions=["SNS나 특정 플랫폼 이용 경험을 전제하지 않는다"],
    ),
    AnchorSpec(
        anchor_id="situational_fit", label="상황 적합성",
        situation_terms=["상황별 스타일링", "유연한 조정", "판단 기준"],
        preferred_scenarios=["학교 행사·면접·모임 등 상황에 맞춰 옷차림을 정하는 상황", "평소와 다른 자리를 준비하는 상황"],
        forbidden_assumptions=["특정 행사·모임 참석 경험을 전제하지 않는다"],
    ),
    AnchorSpec(
        anchor_id="expression_choice", label="표현 선택",
        situation_terms=["느낌 표현", "의도 설명", "반응 조정"],
        preferred_scenarios=["기분이나 느낌을 스타일로 표현해야 하는 상황", "특별한 날 나만의 느낌을 나타내고 싶은 상황"],
        forbidden_assumptions=["메이크업 등 특정 뷰티 행위를 해본 경험을 전제하지 않는다", "성별에 따라 다른 표현 방식을 기대하지 않는다"],
    ),
    AnchorSpec(
        anchor_id="trend_adaptation", label="유행 변화 대응",
        situation_terms=["유행 변화", "취향 유지", "변화 이유 탐색"],
        preferred_scenarios=["유행이나 스타일이 계속 바뀌는 상황", "주변에서 유행이 바뀌었다고 느껴지는 상황"],
        forbidden_assumptions=["유행을 따라갈 경제적 여유를 전제하지 않는다"],
    ),
]

ROUTING = build_routing_blueprint(
    context_id=CONTEXT_ID, blueprint_id="fashion_beauty_routing_blueprint", question_id="fashion_beauty_routing_question",
    question_text="패션이나 뷰티와 관련해 네가 더 끌리는 상황은?",
    options=[
        RoutingOptionSpec("route_combination", "스타일을 조합해보는 것", "style_combination", "스타일 조합"),
        RoutingOptionSpec("route_info", "관련 정보나 유행을 찾아보고 비교하는 것", "info_comparison", "정보 비교·트렌드 탐색"),
        RoutingOptionSpec("route_fit", "상황에 맞는 스타일을 고르는 것", "situational_fit", "상황 적합성"),
        RoutingOptionSpec("route_expression", "나만의 느낌을 스타일로 표현하는 것", "expression_choice", "표현 선택"),
        RoutingOptionSpec("route_trend", "유행 변화에 따라 스타일을 바꿔가는 것", "trend_adaptation", "유행 변화 대응"),
    ],
)

_SPECS: dict[str, dict[str, object]] = {
    "style_combination": {
        "seed": (
            "fashion_beauty_seed_style_combination", "combination_seed",
            "옷차림이나 스타일을 조합할 때, 너에게 가까운 모습은?",
            [
                OptionSpec("try_untried_combo", "안 써본 조합을 새롭게 시도해보고 싶다", "novelty_seeking",
                           "안 써본 조합을 새롭게 시도해보려는 행동이 직접 드러나 novelty_seeking 후보로 연결된다"),
                OptionSpec("imagine_new_combos", "여러 조합을 떠올려보고 새로운 방식을 만들어본다", "creative_ideation",
                           "여러 조합을 떠올려 새로운 방식을 만드는 행동이 직접 드러나 creative_ideation 후보로 연결된다"),
                OptionSpec("match_overall_feel_carefully", "전체적인 느낌이 서로 잘 어울리는지 세밀하게 맞춘다", "detail_orientation",
                           "전체적인 어울림을 세밀하게 맞추는 행동이 직접 드러나 detail_orientation 후보로 연결된다"),
                OptionSpec("decide_my_own_style", "남들이 뭐라 하든 내 스타일대로 정한다", "independent_judgment",
                           "다른 사람 시선과 무관하게 스스로 정하는 행동이 직접 드러나 independent_judgment 후보로 연결된다"),
                OptionSpec("dont_care_much_about_combo", "스타일 조합에는 크게 신경 쓰지 않는다", None,
                           "조합에 신경 쓰지 않는다는 것은 특정 성향의 직접 근거가 되지 않는다"),
            ],
        ),
        "backup": (
            "fashion_beauty_backup_style_combination", "backup",
            "가진 옷이나 아이템으로 새로운 조합을 만들어야 한다면, 너에게 가까운 모습은?",
            [
                OptionSpec("try_new_combo_again", "안 해본 조합을 새롭게 시도해본다", "novelty_seeking",
                           "안 해본 조합을 새롭게 시도하는 행동이 직접 드러나 novelty_seeking 후보로 연결된다"),
                OptionSpec("think_up_new_ways", "여러 조합을 떠올리며 새로운 방식을 생각해본다", "creative_ideation",
                           "여러 조합을 떠올리며 새로운 방식을 생각하는 행동이 직접 드러나 creative_ideation 후보로 연결된다"),
                OptionSpec("check_fit_carefully", "어울리는지 세밀하게 확인하고 맞춘다", "detail_orientation",
                           "어울림을 세밀하게 확인하고 맞추는 행동이 직접 드러나 detail_orientation 후보로 연결된다"),
                OptionSpec("decide_by_my_own_judgment", "남 시선보다 내 판단대로 정한다", "independent_judgment",
                           "타인 시선보다 자신의 판단을 따르는 행동이 직접 드러나 independent_judgment 후보로 연결된다"),
                OptionSpec("dont_care_about_combo", "조합은 별로 신경 안 쓴다", None,
                           "조합에 신경 쓰지 않는다는 것은 특정 성향의 직접 근거가 되지 않는다"),
            ],
        ),
    },
    "info_comparison": {
        "seed": (
            "fashion_beauty_seed_info_comparison", "info_seed",
            "옷이나 뷰티 관련 정보를 찾아볼 때, 너에게 가까운 모습은?",
            [
                OptionSpec("compare_reviews_before_judging", "여러 후기나 정보를 비교해서 판단한다", "information_comparison",
                           "여러 후기·정보를 비교해서 판단하는 행동이 직접 드러나 information_comparison 후보로 연결된다"),
                OptionSpec("enjoy_finding_new_trend", "새로 나온 유행이나 스타일을 찾아보는 게 재밌다", "novelty_seeking",
                           "새로 나온 유행·스타일을 찾아보는 행동이 직접 드러나 novelty_seeking 후보로 연결된다"),
                OptionSpec("wonder_why_trending", "정보를 보다가 왜 그 스타일이 유행하는지 궁금해진다", "causal_analysis",
                           "유행하는 이유를 궁금해하며 따져보는 행동이 직접 드러나 causal_analysis 후보로 연결된다"),
                OptionSpec("dont_search_specifically", "특별히 찾아보진 않는다", None,
                           "특별히 찾아보지 않는다는 것은 특정 성향의 직접 근거가 되지 않는다"),
                OptionSpec("refer_to_others_opinion", "다른 사람 의견을 참고해서 정한다", None,
                           "다른 사람 의견을 참고만 하는 것은 스스로 비교·판단한 행동이 드러나지 않아 근거로 보기 약하다"),
            ],
        ),
        "backup": (
            "fashion_beauty_backup_info_comparison", "backup",
            "새로운 뷰티·패션 정보를 접하게 된다면, 너에게 가까운 모습은?",
            [
                OptionSpec("compare_info_before_judging", "여러 정보를 비교해서 판단해본다", "information_comparison",
                           "여러 정보를 비교해서 판단하는 행동이 직접 드러나 information_comparison 후보로 연결된다"),
                OptionSpec("find_interesting_new_thing", "새로 나온 걸 찾아보는 게 흥미롭다", "novelty_seeking",
                           "새로 나온 것을 찾아보는 행동이 직접 드러나 novelty_seeking 후보로 연결된다"),
                OptionSpec("curious_why_trending_now", "왜 그게 유행하는지 궁금해진다", "causal_analysis",
                           "유행하는 이유를 궁금해하는 행동이 직접 드러나 causal_analysis 후보로 연결된다"),
                OptionSpec("dont_look_it_up", "따로 찾아보지는 않는다", None,
                           "따로 찾아보지 않는다는 것은 특정 성향의 직접 근거가 되지 않는다"),
                OptionSpec("listen_to_people_around", "주변 사람 얘기를 듣고 참고한다", None,
                           "주변 얘기를 참고만 하는 것은 스스로 비교·판단한 행동이 드러나지 않아 근거로 보기 약하다"),
            ],
        ),
    },
    "situational_fit": {
        "seed": (
            "fashion_beauty_seed_situational_fit", "fit_seed",
            "상황(학교 행사, 면접, 모임 등)에 맞춰 옷차림을 정해야 한다면, 너에게 가까운 모습은?",
            [
                OptionSpec("weigh_what_fits_situation", "그 상황에 어떤 게 어울릴지 이것저것 따져본다", "planning",
                           "상황에 맞는 것을 따져보며 준비하는 행동이 직접 드러나 planning 후보로 연결된다"),
                OptionSpec("flexibly_change_by_situation", "상황이 바뀌면 스타일도 유연하게 바꾼다", "change_adaptation",
                           "상황에 따라 스타일을 유연하게 바꾸는 행동이 직접 드러나 change_adaptation 후보로 연결된다"),
                OptionSpec("judge_without_fixed_standard", "정해진 기준이 없어도 내 나름대로 판단한다", "uncertainty_tolerance",
                           "정해진 기준 없이도 스스로 판단하는 행동이 직접 드러나 uncertainty_tolerance 후보로 연결된다"),
                OptionSpec("refer_to_how_others_dress", "다른 사람들은 어떻게 입는지 참고한다", None,
                           "다른 사람 사례를 참고만 하는 것은 스스로의 판단 과정이 드러나지 않아 근거로 보기 약하다"),
                OptionSpec("dont_care_much_by_situation", "상황에 따라 크게 다르게 신경 쓰지 않는다", None,
                           "상황별로 신경 쓰지 않는다는 것은 특정 성향의 직접 근거가 되지 않는다"),
            ],
        ),
        "backup": (
            "fashion_beauty_backup_situational_fit", "backup",
            "평소와 다른 자리(면접, 발표, 행사 등)에 갈 준비를 한다면, 너에게 가까운 모습은?",
            [
                OptionSpec("figure_out_fitting_style_ahead", "어떤 스타일이 맞을지 미리 따져본다", "planning",
                           "어울리는 스타일을 미리 따져보는 행동이 직접 드러나 planning 후보로 연결된다"),
                OptionSpec("flexibly_change_by_occasion", "자리에 따라 스타일을 유연하게 바꾼다", "change_adaptation",
                           "자리에 따라 스타일을 유연하게 바꾸는 행동이 직접 드러나 change_adaptation 후보로 연결된다"),
                OptionSpec("judge_my_own_way_without_standard", "정해진 기준이 없어도 내 나름대로 판단한다", "uncertainty_tolerance",
                           "정해진 기준 없이도 스스로 판단하는 행동이 직접 드러나 uncertainty_tolerance 후보로 연결된다"),
                OptionSpec("refer_to_other_cases", "다른 사람들 사례를 참고한다", None,
                           "다른 사례를 참고만 하는 것은 스스로의 판단 과정이 드러나지 않아 근거로 보기 약하다"),
                OptionSpec("keep_usual_style", "크게 신경 쓰지 않고 평소대로 한다", None,
                           "평소대로 한다는 것은 특정 성향의 직접 근거가 되지 않는다"),
            ],
        ),
    },
    "expression_choice": {
        "seed": (
            "fashion_beauty_seed_expression_choice", "expression_seed",
            "스타일이나 화장으로 그날의 느낌을 표현해야 한다면, 너에게 가까운 모습은?",
            [
                OptionSpec("choose_and_express_the_feeling", "그 느낌에 맞게 조합이나 색을 직접 골라 표현해본다", "visual_expression",
                           "느낌에 맞는 조합·색을 직접 골라 표현하는 행동이 직접 드러나 visual_expression 후보로 연결된다"),
                OptionSpec("want_to_explain_the_choice", "왜 이렇게 골랐는지 이유를 설명하고 싶어진다", "opinion_expression",
                           "고른 이유를 설명하고 싶어하는 행동이 직접 드러나 opinion_expression 후보로 연결된다"),
                OptionSpec("adjust_by_watching_reaction", "다른 사람 반응을 살피며 조정한다", "emotional_interpretation",
                           "반응을 살피며 조정하는 행동이 직접 드러나 emotional_interpretation 후보로 연결된다"),
                OptionSpec("no_particular_feeling_to_express", "특별히 표현하고 싶은 느낌은 딱히 없다", None,
                           "표현하고 싶은 느낌이 없다는 것은 특정 성향의 직접 근거가 되지 않는다"),
                OptionSpec("rarely_such_occasion", "그런 상황 자체가 별로 없다", None,
                           "그런 상황이 없다는 것은 특정 성향의 직접 근거가 되지 않는다"),
            ],
        ),
        "backup": (
            "fashion_beauty_backup_expression_choice", "backup",
            "특별한 날 나만의 느낌을 스타일로 나타내고 싶다면, 너에게 가까운 모습은?",
            [
                OptionSpec("pick_and_express_directly", "원하는 느낌에 맞게 직접 골라서 표현한다", "visual_expression",
                           "원하는 느낌에 맞게 직접 골라 표현하는 행동이 직접 드러나 visual_expression 후보로 연결된다"),
                OptionSpec("want_to_talk_about_reason", "그렇게 고른 이유를 이야기하고 싶어진다", "opinion_expression",
                           "고른 이유를 이야기하고 싶어하는 행동이 직접 드러나 opinion_expression 후보로 연결된다"),
                OptionSpec("adjust_watching_others_reaction", "주변 반응을 보고 조금씩 조정한다", "emotional_interpretation",
                           "주변 반응을 보고 조정하는 행동이 직접 드러나 emotional_interpretation 후보로 연결된다"),
                OptionSpec("no_particular_feeling_wanted", "딱히 표현하고 싶은 느낌이 없다", None,
                           "표현하고 싶은 느낌이 없다는 것은 특정 성향의 직접 근거가 되지 않는다"),
                OptionSpec("rarely_have_such_day", "그런 날이 거의 없다", None,
                           "그런 날이 거의 없다는 것은 특정 성향의 직접 근거가 되지 않는다"),
            ],
        ),
    },
    "trend_adaptation": {
        "seed": (
            "fashion_beauty_seed_trend_adaptation", "trend_seed",
            "유행이나 스타일이 계속 바뀔 때, 너에게 가까운 모습은?",
            [
                OptionSpec("try_new_trend_first", "새로운 유행을 먼저 시도해보고 싶다", "novelty_seeking",
                           "새로운 유행을 먼저 시도해보려는 행동이 직접 드러나 novelty_seeking 후보로 연결된다"),
                OptionSpec("keep_my_style_regardless", "유행과 상관없이 내 스타일을 유지한다", "personal_goal_priority",
                           "유행과 무관하게 자신의 스타일을 유지하는 행동이 직접 드러나 personal_goal_priority 후보로 연결된다"),
                OptionSpec("curious_why_trend_changed", "유행이 왜 바뀌는지 궁금해서 찾아본다", "causal_analysis",
                           "유행이 바뀌는 이유를 찾아보는 행동이 직접 드러나 causal_analysis 후보로 연결된다"),
                OptionSpec("gradually_follow_trend", "유행에 맞춰 조금씩 바꿔간다", "change_adaptation",
                           "유행에 맞춰 조금씩 바꿔가는 행동이 직접 드러나 change_adaptation 후보로 연결된다"),
                OptionSpec("not_interested_in_trend", "유행에는 크게 관심이 없다", None,
                           "유행에 관심이 없다는 것은 특정 성향의 직접 근거가 되지 않는다"),
            ],
        ),
        "backup": (
            "fashion_beauty_backup_trend_adaptation", "backup",
            "주변에서 유행이 바뀌었다고 느껴질 때, 너에게 가까운 모습은?",
            [
                OptionSpec("want_to_try_it_first", "먼저 시도해보고 싶어진다", "novelty_seeking",
                           "먼저 시도해보고 싶어지는 행동이 직접 드러나 novelty_seeking 후보로 연결된다"),
                OptionSpec("keep_my_own_way", "유행과 상관없이 내 방식대로 한다", "personal_goal_priority",
                           "유행과 무관하게 자신의 방식을 유지하는 행동이 직접 드러나 personal_goal_priority 후보로 연결된다"),
                OptionSpec("look_up_why_it_changed", "왜 바뀌었는지 궁금해서 찾아본다", "causal_analysis",
                           "바뀐 이유를 찾아보는 행동이 직접 드러나 causal_analysis 후보로 연결된다"),
                OptionSpec("adjust_little_by_little", "조금씩 맞춰서 바꿔본다", "change_adaptation",
                           "조금씩 맞춰 바꾸는 행동이 직접 드러나 change_adaptation 후보로 연결된다"),
                OptionSpec("dont_care_much", "특별히 신경 쓰지 않는다", None,
                           "특별히 신경 쓰지 않는다는 것은 특정 성향의 직접 근거가 되지 않는다"),
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
            "성별에 따라 다른 스타일 관심을 기대하지 않는다",
            "특정 체형이나 외모를 전제하거나 평가하지 않는다",
            "고가 브랜드나 제품 구매 경험을 전제하지 않는다",
            "외모 자신감이나 인기 여부를 Trait로 추론하지 않는다",
        ],
        review_artifact_paths=["data/reviews/context_packs/fashion_beauty_review_status.json"],
        pack_version="lifestyle_v1.0-draft",
    )


CONTEXT_PACK: ContextPack = _build_pack()
