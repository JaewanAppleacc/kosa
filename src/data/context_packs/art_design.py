"""art_design Context Pack — context-pack-lifestyle 작업 배정(2026-08-23).

작업 지시문 "art_design 주의"를 그대로 지킨다:
- 작품 감상을 visual_expression으로 연결하지 않는다 — `visual_appreciation` Anchor는
  감식(aesthetic_sensitivity)·정보 비교·아이디어 발상까지만 다루고, visual_expression은
  실제로 학생이 "그려서/골라서 표현한다"는 행동이 나오는 `direct_creation`·
  `expression`류 Option에만 붙인다.
- 직접 표현·구성·수정 행동이 있을 때만 관련 Trait를 연결한다 — `revision_feedback`
  Anchor가 그 "수정" 축을 담당한다.
- 그림 실력을 평가하지 않는다 — Trait Mapping은 태도·과정(시도·수정·계획)에 대한
  것이고, 결과물의 완성도나 숙련도를 묻지 않는다.
- 예체능 학과 추천 대상에서 제외되는 정책과 이 Context 질문 자체는 무관하다 — 이
  Pack은 Assessment 질문 노출 여부만 다루고, 전공 Matching 단계의 별도 정책(A 소유,
  이 Pack 밖)과 섞지 않는다."""

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

CONTEXT_ID = "art_design"

ANCHORS = [
    AnchorSpec(
        anchor_id="visual_appreciation", label="작품 감상",
        situation_terms=["작품 감상", "스타일 비교", "감상 중 발상"],
        preferred_scenarios=["그림·디자인 작품을 볼 때의 상황", "미술관·전시·SNS에서 작품을 우연히 접한 상황"],
        forbidden_assumptions=["미술관·전시 관람 경험을 전제하지 않는다", "작품을 좋아한다는 사실만으로 시각적 표현 능력을 추론하지 않는다"],
    ),
    AnchorSpec(
        anchor_id="direct_creation", label="직접 그리기·만들기",
        situation_terms=["직접 창작", "표현 시도", "완성까지 다듬기"],
        preferred_scenarios=["직접 그림을 그리거나 디자인을 만들어야 하는 상황", "미술·디자인 수행평가나 과제를 만드는 상황"],
        forbidden_assumptions=["미술 학원이나 전공 관련 교육 경험을 전제하지 않는다", "그림 실력 수준을 평가하지 않는다"],
    ),
    AnchorSpec(
        anchor_id="revision_feedback", label="구성 수정·피드백 반영",
        situation_terms=["피드백 반영", "구성 수정", "의도 설명"],
        preferred_scenarios=["결과물에 대해 다른 사람의 피드백을 받은 상황", "친구나 선생님이 다른 의견을 낸 상황"],
        forbidden_assumptions=["공식적인 작품 발표·전시 경험을 전제하지 않는다"],
    ),
    AnchorSpec(
        anchor_id="planning_composition", label="구도·컨셉 기획",
        situation_terms=["기획", "구도 설계", "방향 설정"],
        preferred_scenarios=["무언가를 만들기 전에 구도나 컨셉을 정하는 상황", "새로운 작업을 시작하기 전 상황"],
        forbidden_assumptions=["디자인 관련 정규 교육 경험을 전제하지 않는다"],
    ),
    AnchorSpec(
        anchor_id="tool_material_choice", label="도구·재료 활용",
        situation_terms=["도구 비교", "재료 실험", "새 프로그램 시도"],
        preferred_scenarios=["작업에 쓸 도구·프로그램·재료를 고르는 상황"],
        forbidden_assumptions=["고가의 장비나 프로그램 구매 경험을 전제하지 않는다"],
    ),
]

ROUTING = build_routing_blueprint(
    context_id=CONTEXT_ID, blueprint_id="art_design_routing_blueprint", question_id="art_design_routing_question",
    question_text="미술·디자인과 관련해 네가 더 끌리는 상황은?",
    options=[
        RoutingOptionSpec("route_appreciation", "작품을 보고 살펴보는 것", "visual_appreciation", "작품 감상"),
        RoutingOptionSpec("route_creation", "직접 그리거나 만들어보는 것", "direct_creation", "직접 그리기·만들기"),
        RoutingOptionSpec("route_revision", "만든 걸 다듬고 피드백을 반영하는 것", "revision_feedback", "구성 수정·피드백 반영"),
        RoutingOptionSpec("route_planning", "구도나 컨셉을 기획하는 것", "planning_composition", "구도·컨셉 기획"),
        RoutingOptionSpec("route_tool", "도구나 재료를 고르고 다뤄보는 것", "tool_material_choice", "도구·재료 활용"),
    ],
)

_SPECS: dict[str, dict[str, object]] = {
    "visual_appreciation": {
        "seed": (
            "art_design_seed_visual_appreciation", "appreciation_seed",
            "그림이나 디자인 작품을 볼 때, 너에게 가까운 모습은?",
            [
                OptionSpec("examine_color_composition", "색이나 구도가 왜 그렇게 됐는지 뜯어보게 된다", "aesthetic_sensitivity",
                           "색·구도가 이루어진 이유를 스스로 뜯어보는 행동이 직접 드러나 aesthetic_sensitivity 후보로 연결된다"),
                OptionSpec("want_to_explain_why_good", "다른 사람에게 왜 좋은지 설명하고 싶어진다", None,
                           "설명하고 싶은 마음은 있지만 실제로 무엇을 표현·비교했는지는 드러나지 않아 특정 성향의 직접 근거로 보기 약하다"),
                OptionSpec("search_similar_styles", "비슷한 스타일의 다른 작품들을 찾아보게 된다", "information_comparison",
                           "비슷한 스타일의 작품을 찾아 비교하는 행동이 직접 드러나 information_comparison 후보로 연결된다"),
                OptionSpec("just_look_and_move_on", "그냥 눈으로 보고 넘어가는 편이다", None,
                           "특별한 행동 없이 보고 넘어가는 것은 특정 성향의 직접 근거로 보기 어렵다"),
                OptionSpec("imagine_new_combination", "작품을 보고 새로운 조합이나 스타일을 떠올려본다", "creative_ideation",
                           "작품에서 새로운 조합·스타일을 떠올리는 행동이 직접 드러나 creative_ideation 후보로 연결된다"),
            ],
        ),
        "backup": (
            "art_design_backup_visual_appreciation", "backup",
            "미술관이나 전시, SNS에서 작품을 우연히 봤을 때, 너에게 가까운 모습은?",
            [
                OptionSpec("look_into_color_layout", "색감이나 구도가 어떻게 이루어졌는지 살펴보게 된다", "aesthetic_sensitivity",
                           "색감·구도를 자세히 살펴보는 행동이 직접 드러나 aesthetic_sensitivity 후보로 연결된다"),
                OptionSpec("find_similar_artists", "비슷한 작품이나 작가를 더 찾아보게 된다", "information_comparison",
                           "비슷한 작품·작가를 더 찾아보는 행동이 직접 드러나 information_comparison 후보로 연결된다"),
                OptionSpec("get_idea_for_combination", "그 작품에서 아이디어를 얻어 다른 조합을 상상해본다", "creative_ideation",
                           "작품에서 아이디어를 얻어 다른 조합을 상상하는 행동이 직접 드러나 creative_ideation 후보로 연결된다"),
                OptionSpec("feel_but_not_examine", "느낌은 있지만 자세히 들여다보진 않는다", None,
                           "느낌만 있고 구체적으로 들여다보지 않는 것은 특정 성향의 직접 근거로 보기 약하다"),
                OptionSpec("pass_without_thought", "별생각 없이 지나간다", None,
                           "별생각 없이 지나가는 것은 특정 성향의 직접 근거가 되지 않는다"),
            ],
        ),
    },
    "direct_creation": {
        "seed": (
            "art_design_seed_direct_creation", "creation_seed",
            "직접 그림을 그리거나 디자인을 만들어야 할 때, 너에게 가까운 모습은?",
            [
                OptionSpec("draw_out_imagined_image", "머릿속 이미지를 실제로 그려서 표현해본다", "visual_expression",
                           "머릿속 이미지를 실제로 그려서 표현하는 행동이 직접 드러나 visual_expression 후보로 연결된다"),
                OptionSpec("keep_refining_until_done", "완성될 때까지 계속 다듬고 수정한다", "persistence_completion",
                           "완성될 때까지 계속 다듬는 행동이 직접 드러나 persistence_completion 후보로 연결된다"),
                OptionSpec("try_new_approaches", "이것저것 새로운 방식을 시도해본다", "novelty_seeking",
                           "새로운 방식을 이것저것 시도하는 행동이 직접 드러나 novelty_seeking 후보로 연결된다"),
                OptionSpec("match_fine_details", "세부적인 부분까지 신경 써서 맞춘다", "detail_orientation",
                           "세부적인 부분까지 신경 써서 맞추는 행동이 직접 드러나 detail_orientation 후보로 연결된다"),
                OptionSpec("rarely_draw_directly", "직접 그리는 건 별로 안 하게 된다", None,
                           "직접 그리지 않는다는 것은 특정 성향의 직접 근거가 되지 않는다"),
            ],
        ),
        "backup": (
            "art_design_backup_direct_creation", "backup",
            "미술·디자인 수행평가나 과제를 직접 만들어야 한다면, 너에게 가까운 모습은?",
            [
                OptionSpec("express_idea_by_drawing", "떠오른 이미지를 실제로 그리거나 만들어 표현한다", "visual_expression",
                           "떠오른 이미지를 실제로 그리거나 만들어 표현하는 행동이 직접 드러나 visual_expression 후보로 연결된다"),
                OptionSpec("keep_touching_until_satisfied", "마음에 들 때까지 계속 손을 본다", "persistence_completion",
                           "마음에 들 때까지 계속 손보는 행동이 직접 드러나 persistence_completion 후보로 연결된다"),
                OptionSpec("try_unexpected_way", "생각지 못한 방식을 시도해본다", "novelty_seeking",
                           "생각지 못한 방식을 시도하는 행동이 직접 드러나 novelty_seeking 후보로 연결된다"),
                OptionSpec("raise_completeness_in_detail", "작은 부분까지 맞춰가며 완성도를 높인다", "detail_orientation",
                           "작은 부분까지 맞춰가며 완성도를 높이는 행동이 직접 드러나 detail_orientation 후보로 연결된다"),
                OptionSpec("avoid_making_process", "만드는 과정은 되도록 피하고 싶다", None,
                           "만드는 과정을 피하고 싶어하는 것은 특정 성향의 직접 근거가 되지 않는다"),
            ],
        ),
    },
    "revision_feedback": {
        "seed": (
            "art_design_seed_revision_feedback", "revision_seed",
            "만든 결과물에 대해 다른 사람의 피드백을 받았을 때, 너에게 가까운 모습은?",
            [
                OptionSpec("revise_by_reflecting_feedback", "피드백을 반영해서 구성을 다시 바꿔본다", "change_adaptation",
                           "피드백을 반영해 구성을 다시 바꾸는 행동이 직접 드러나 change_adaptation 후보로 연결된다"),
                OptionSpec("explain_my_intent", "내 의도를 설명하며 왜 그렇게 만들었는지 이야기한다", "opinion_expression",
                           "자신의 의도를 설명하며 이야기하는 행동이 직접 드러나 opinion_expression 후보로 연결된다"),
                OptionSpec("fix_details_one_by_one", "세부적인 부분을 하나하나 짚어가며 고친다", "detail_orientation",
                           "세부를 하나하나 짚어가며 고치는 행동이 직접 드러나 detail_orientation 후보로 연결된다"),
                OptionSpec("decide_what_to_reflect", "여러 의견 중 어떤 걸 반영할지 스스로 판단한다", "independent_judgment",
                           "여러 의견 중 반영할 것을 스스로 판단하는 행동이 직접 드러나 independent_judgment 후보로 연결된다"),
                OptionSpec("rarely_get_feedback", "피드백을 받을 일이 별로 없다", None,
                           "피드백을 받을 일이 없다는 것은 특정 성향의 직접 근거가 되지 않는다"),
            ],
        ),
        "backup": (
            "art_design_backup_revision_feedback", "backup",
            "친구나 선생님이 내 작품에 다른 의견을 냈을 때, 너에게 가까운 모습은?",
            [
                OptionSpec("rework_by_reflecting_opinion", "그 의견을 반영해서 다시 구성을 바꿔본다", "change_adaptation",
                           "의견을 반영해 구성을 다시 바꾸는 행동이 직접 드러나 change_adaptation 후보로 연결된다"),
                OptionSpec("explain_why_made_this_way", "왜 이렇게 만들었는지 내 생각을 설명한다", "opinion_expression",
                           "왜 이렇게 만들었는지 자신의 생각을 설명하는 행동이 직접 드러나 opinion_expression 후보로 연결된다"),
                OptionSpec("fix_pointed_part_carefully", "지적된 부분을 세밀하게 고쳐나간다", "detail_orientation",
                           "지적된 부분을 세밀하게 고치는 행동이 직접 드러나 detail_orientation 후보로 연결된다"),
                OptionSpec("decide_which_opinion_to_take", "여러 의견 중 반영할 것과 아닐 것을 스스로 정한다", "independent_judgment",
                           "여러 의견 중 반영 여부를 스스로 정하는 행동이 직접 드러나 independent_judgment 후보로 연결된다"),
                OptionSpec("rarely_had_such_situation", "그런 상황이 별로 없었다", None,
                           "그런 상황이 없었다는 것은 특정 성향의 직접 근거가 되지 않는다"),
            ],
        ),
    },
    "planning_composition": {
        "seed": (
            "art_design_seed_planning_composition", "planning_seed",
            "무언가를 만들기 전에 구도나 컨셉을 정할 때, 너에게 가까운 모습은?",
            [
                OptionSpec("plan_overall_first", "전체적인 계획을 먼저 세우고 시작한다", "planning",
                           "전체 계획을 먼저 세우고 시작하는 행동이 직접 드러나 planning 후보로 연결된다"),
                OptionSpec("think_how_elements_fit", "여러 요소가 서로 어떻게 어우러질지 구조적으로 생각한다", "systems_thinking",
                           "여러 요소가 어떻게 어우러질지 구조적으로 생각하는 행동이 직접 드러나 systems_thinking 후보로 연결된다"),
                OptionSpec("set_direction_despite_unsure", "확실하지 않아도 일단 방향을 정하고 진행한다", "uncertainty_tolerance",
                           "확실치 않아도 방향을 정하고 진행하는 행동이 직접 드러나 uncertainty_tolerance 후보로 연결된다"),
                OptionSpec("try_new_composition", "새로운 방식의 구성을 시도해보고 싶다", "novelty_seeking",
                           "새로운 방식의 구성을 시도해보려는 행동이 직접 드러나 novelty_seeking 후보로 연결된다"),
                OptionSpec("no_particular_plan", "특별히 계획 없이 그때그때 만든다", None,
                           "계획 없이 그때그때 만드는 것은 특정 성향의 직접 근거로 보기 어렵다"),
            ],
        ),
        "backup": (
            "art_design_backup_planning_composition", "backup",
            "새로운 작업을 시작하기 전에, 너에게 가까운 모습은?",
            [
                OptionSpec("decide_order_beforehand", "어떤 순서로 진행할지 미리 정해둔다", "planning",
                           "진행 순서를 미리 정해두는 행동이 직접 드러나 planning 후보로 연결된다"),
                OptionSpec("sketch_structure_first", "요소들이 어떻게 맞물릴지 구조를 먼저 그려본다", "systems_thinking",
                           "요소들이 맞물릴 구조를 먼저 그려보는 행동이 직접 드러나 systems_thinking 후보로 연결된다"),
                OptionSpec("start_and_find_direction", "확실치 않아도 일단 시작하며 방향을 잡는다", "uncertainty_tolerance",
                           "확실치 않아도 시작하며 방향을 잡는 행동이 직접 드러나 uncertainty_tolerance 후보로 연결된다"),
                OptionSpec("try_different_composition", "이전과 다른 새로운 구성을 시도해보고 싶다", "novelty_seeking",
                           "이전과 다른 새로운 구성을 시도해보려는 행동이 직접 드러나 novelty_seeking 후보로 연결된다"),
                OptionSpec("decide_while_progressing", "미리 정하지 않고 진행하면서 정한다", None,
                           "미리 정하지 않는다는 것은 특정 성향의 직접 근거가 되지 않는다"),
            ],
        ),
    },
    "tool_material_choice": {
        "seed": (
            "art_design_seed_tool_material_choice", "tool_seed",
            "어떤 도구나 프로그램, 재료로 작업할지 고를 때, 너에게 가까운 모습은?",
            [
                OptionSpec("compare_tools_before_choosing", "여러 도구를 비교해보고 나에게 맞는 걸 고른다", "information_comparison",
                           "여러 도구를 비교해서 고르는 행동이 직접 드러나 information_comparison 후보로 연결된다"),
                OptionSpec("learn_new_tool", "새로운 도구나 프로그램을 익혀서 써보고 싶다", "tool_utilization",
                           "새로운 도구·프로그램을 익혀서 써보려는 행동이 직접 드러나 tool_utilization 후보로 연결된다"),
                OptionSpec("stick_to_familiar_way", "손에 익은 방식을 계속 쓰는 편이다", None,
                           "익숙한 방식을 계속 쓰는 것은 특정 성향의 직접 근거로 보기 어렵다"),
                OptionSpec("care_more_about_result", "도구보다 결과물 자체에 더 관심이 간다", None,
                           "도구보다 결과물에 관심이 간다는 것은 도구 활용 행동 자체를 보여주지 않아 근거로 보기 약하다"),
                OptionSpec("mix_materials_for_new_try", "다양한 재료를 섞어서 새로운 걸 시도해본다", "creative_ideation",
                           "다양한 재료를 섞어 새로운 시도를 하는 행동이 직접 드러나 creative_ideation 후보로 연결된다"),
            ],
        ),
        "backup": (
            "art_design_backup_tool_material_choice", "backup",
            "작업에 쓸 프로그램이나 재료를 고를 일이 생긴다면, 너에게 가까운 모습은?",
            [
                OptionSpec("compare_options_before_pick", "여러 선택지를 비교해서 고른다", "information_comparison",
                           "여러 선택지를 비교해서 고르는 행동이 직접 드러나 information_comparison 후보로 연결된다"),
                OptionSpec("try_untried_tool", "안 써본 도구나 프로그램을 배워보고 싶다", "tool_utilization",
                           "안 써본 도구·프로그램을 배워보려는 행동이 직접 드러나 tool_utilization 후보로 연결된다"),
                OptionSpec("use_familiar_way_as_is", "익숙한 방식을 그대로 쓴다", None,
                           "익숙한 방식을 그대로 쓰는 것은 특정 성향의 직접 근거로 보기 어렵다"),
                OptionSpec("result_matters_more_than_tool", "도구보다는 결과물이 더 중요하다고 생각한다", None,
                           "결과물이 더 중요하다는 생각은 실제 도구 활용 행동을 보여주지 않아 근거로 보기 약하다"),
                OptionSpec("mix_materials_for_combination", "여러 재료나 방식을 섞어서 새로운 조합을 만들어본다", "creative_ideation",
                           "여러 재료·방식을 섞어 새로운 조합을 만드는 행동이 직접 드러나 creative_ideation 후보로 연결된다"),
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
            "작품 감상 경험을 시각적 표현 능력으로 연결하지 않는다",
            "그림이나 디자인 실력 수준을 평가하지 않는다",
            "예체능 진로 추천 정책과 이 Context의 질문 노출 여부를 혼동하지 않는다 — "
            "이 Pack은 예체능 학과 Matching 정책과 무관하게 독립적으로 운영된다",
        ],
        review_artifact_paths=["data/reviews/context_packs/art_design_review_status.json"],
        pack_version="lifestyle_v1.0-draft",
    )


CONTEXT_PACK: ContextPack = _build_pack()
