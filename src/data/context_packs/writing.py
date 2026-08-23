"""writing(글쓰기·독서) Context Pack — 2026-08-23 Trait Ontology v2(2.7단계 2차 배치) §2.

context-pack-social 작업 배정(담당: volunteer/travel/writing/history_humanities) 초안이다.
검수 상태는 전부 TBD이며 `data/reviews/context_packs/writing_review_status.json`에서
사람이 직접 채운다(§1 "Claude가 Context 질문을 자동 APPROVE하지 않는다").

설계 원칙(작업 지시문 그대로):
- 독서량·국어 성적·글쓰기 실력을 평가하지 않는다 — 모든 질문이 "안 써봤어도 상상해보면
  답할 수 있는" 가상 상황이고, "글을 잘 쓴다"는 자기평가를 묻는 선택지가 없다.
- 이야기 해석·정보 정리·표현 방식·독자 반응·자료 비교 상황을 다뤘다(Routing 5개 Anchor).
- "별다른 생각 없이 계속 읽는다", "이전 형식을 그대로 따른다", "일단 다 쓰고 끝낸다"처럼
  무난한 기본 행동은 NO_SIGNAL로 두어 "잘 쓰는 사람 같은 답"이 정답처럼 보이지 않게 했다."""

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

_CONTEXT_ID = "writing"


def _rationales_for(question: FinalizedQuestion, source: str, texts: dict[str, str]) -> list[OptionMappingRationale]:
    rationales = []
    for option in question.options:
        trait_id = next(iter(option.primary_trait_delta), None)
        rationales.append(
            OptionMappingRationale(
                source=source, question_id=question.question_id, role_id=option.role_id,
                trait_id=trait_id, mapping_rationale_draft=texts[option.role_id],
            )
        )
    return rationales


# ============================== Routing ==============================

_ROUTING_ROWS = [
    ("wr_story", "이야기를 읽으며 해석해보는 상황", "story_interpretation", "이야기 해석"),
    ("wr_info", "여러 정보를 정리해서 표현하는 상황", "information_organizing", "정보 정리"),
    ("wr_style", "같은 내용을 어떻게 표현할지 고민하는 상황", "expression_style", "표현 방식 고민"),
    ("wr_reader", "글을 읽을 사람이 어떻게 받아들일지 생각하는 상황", "reader_reaction", "독자 반응 고려"),
    ("wr_source", "여러 자료를 비교하며 확인하는 상황", "source_comparison", "자료 비교"),
]

_ROUTING_QUESTION_ID = "writing_context_router_v1_base"
_ROUTING_BLUEPRINT = ContextRoutingBlueprint(
    context_id=_CONTEXT_ID,
    blueprint_id="writing_context_router_v1",
    option_mappings=[
        ContextRoutingOptionMapping(role_id=role_id, context_anchor=anchor, anchor_label=label)
        for role_id, _text, anchor, label in _ROUTING_ROWS
    ],
    base_question=FinalizedQuestion(
        question_id=_ROUTING_QUESTION_ID, context=_CONTEXT_ID, target_traits=[], frame_id="context_routing",
        question_text="글을 읽거나 쓰는 상황을 상상해볼 때, 가장 관심이 가는 상황은 무엇인가요?",
        options=[
            FinalizedOption(
                option_id=f"{_ROUTING_QUESTION_ID}_o{i}", role_id=role_id, text=text, primary_trait_delta={},
            )
            for i, (role_id, text, _anchor, _label) in enumerate(_ROUTING_ROWS, start=1)
        ],
    ),
)

# ============================== Anchor Presentations ==============================

ANCHOR_PRESENTATIONS = [
    ContextAnchorPresentation(
        context_id=_CONTEXT_ID, anchor_id="story_interpretation", label="이야기 해석",
        situation_terms=["이야기", "인물", "해석"],
        preferred_scenarios=["이야기 속 인물의 선택이나 결말을 해석하는 상황"],
        forbidden_assumptions=["독서량", "국어 성적"],
    ),
    ContextAnchorPresentation(
        context_id=_CONTEXT_ID, anchor_id="information_organizing", label="정보 정리",
        situation_terms=["정보 정리", "구조", "요약"],
        preferred_scenarios=["여러 정보를 정리해서 전달해야 하는 상황"],
        forbidden_assumptions=["글쓰기 실력", "국어 성적"],
    ),
    ContextAnchorPresentation(
        context_id=_CONTEXT_ID, anchor_id="expression_style", label="표현 방식 고민",
        situation_terms=["표현 방식", "전달 방법", "형식"],
        preferred_scenarios=["같은 내용을 어떤 방식으로 표현할지 고민하는 상황"],
        forbidden_assumptions=["글쓰기 실력", "작문 대회"],
    ),
    ContextAnchorPresentation(
        context_id=_CONTEXT_ID, anchor_id="reader_reaction", label="독자 반응 고려",
        situation_terms=["독자 반응", "전달", "이해"],
        preferred_scenarios=["이 글을 읽을 사람이 어떻게 받아들일지 고려하는 상황"],
        forbidden_assumptions=["글쓰기 실력", "독서량"],
    ),
    ContextAnchorPresentation(
        context_id=_CONTEXT_ID, anchor_id="source_comparison", label="자료 비교",
        situation_terms=["자료 비교", "출처", "신뢰성"],
        preferred_scenarios=["여러 자료를 놓고 비교해 확인하는 상황"],
        forbidden_assumptions=["독서량", "국어 성적"],
    ),
]

# ============================== Seed Anchor Questions ==============================

_SEED_STORY_INTERPRETATION = FinalizedQuestion(
    question_id="writing_seed_story_interpretation_v1", context=_CONTEXT_ID, target_traits=[], frame_id="seed_anchor",
    question_text="이야기를 읽다가 등장인물이 예상 밖의 선택을 하는 장면을 봤다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="writing_seed_story_interpretation_v1_o1", role_id="trace_why_chose",
            text="그 인물이 왜 그런 선택을 했는지 이유를 짚어본다", primary_trait_delta={"causal_analysis": 1}),
        FinalizedOption(option_id="writing_seed_story_interpretation_v1_o2", role_id="feel_the_character",
            text="그 순간 인물이 어떤 감정이었을지 헤아려본다", primary_trait_delta={"emotional_interpretation": 1}),
        FinalizedOption(option_id="writing_seed_story_interpretation_v1_o3", role_id="imagine_alt_ending",
            text="다른 선택을 했다면 이야기가 어떻게 달라졌을지 상상해본다", primary_trait_delta={"creative_ideation": 1}),
        FinalizedOption(option_id="writing_seed_story_interpretation_v1_o4", role_id="find_similar_scene",
            text="비슷한 전개가 다른 이야기에도 있었는지 떠올려본다", primary_trait_delta={"pattern_finding": 1}),
        FinalizedOption(option_id="writing_seed_story_interpretation_v1_o5", role_id="keep_reading",
            text="별다른 생각 없이 계속 읽는다", primary_trait_delta={}),
    ],
)
_SEED_STORY_INTERPRETATION_RATIONALE = {
    "trace_why_chose": "인물의 선택 이유를 능동적으로 짚어보는 행동이 드러나 causal_analysis 후보로 연결된다",
    "feel_the_character": "인물의 감정을 헤아려보는 행동이 드러나 emotional_interpretation 후보로 연결된다",
    "imagine_alt_ending": "다른 전개를 스스로 상상해보는 행동이 드러나 creative_ideation 후보로 연결된다",
    "find_similar_scene": "반복되는 전개 패턴을 스스로 찾아내는 행동이 드러나 pattern_finding 후보로 연결된다",
    "keep_reading": "별다른 생각 없이 계속 읽는 것은 감상의 기본 행동이라 특정 성향의 근거가 되기 어렵다",
}

_SEED_INFORMATION_ORGANIZING = FinalizedQuestion(
    question_id="writing_seed_information_organizing_v1", context=_CONTEXT_ID, target_traits=[], frame_id="seed_anchor",
    question_text="여러 정보를 정리해서 다른 사람에게 전달해야 한다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="writing_seed_information_organizing_v1_o1", role_id="structure_first",
            text="전체 순서와 구조를 먼저 짜본다", primary_trait_delta={"planning": 1}),
        FinalizedOption(option_id="writing_seed_information_organizing_v1_o2", role_id="start_writing_now",
            text="일단 떠오르는 대로 먼저 써 내려간다", primary_trait_delta={"immediate_execution": 1}),
        FinalizedOption(option_id="writing_seed_information_organizing_v1_o3", role_id="find_the_pattern",
            text="정보들 사이에 공통된 흐름이나 규칙을 찾아본다", primary_trait_delta={"pattern_finding": 1}),
        FinalizedOption(option_id="writing_seed_information_organizing_v1_o4", role_id="check_details",
            text="각 정보가 정확한지 세부적으로 다시 확인한다", primary_trait_delta={"detail_orientation": 1}),
        FinalizedOption(option_id="writing_seed_information_organizing_v1_o5", role_id="copy_the_format",
            text="이전에 봤던 형식을 그대로 따라 쓴다", primary_trait_delta={}),
    ],
)
_SEED_INFORMATION_ORGANIZING_RATIONALE = {
    "structure_first": "쓰기 전에 전체 순서와 구조부터 짜는 행동이 드러나 planning 후보로 연결된다",
    "start_writing_now": "구조를 먼저 짜기보다 떠오르는 대로 바로 써보는 행동이 드러나 immediate_execution 후보로 연결된다",
    "find_the_pattern": "정보들 사이의 공통된 규칙을 스스로 찾는 행동이 드러나 pattern_finding 후보로 연결된다",
    "check_details": "각 정보를 세부까지 다시 확인하는 행동이 드러나 detail_orientation 후보로 연결된다",
    "copy_the_format": "이전 형식을 그대로 따르는 것은 관행을 따르는 것이라 특정 성향의 직접 근거로 보기는 약하다",
}

_SEED_EXPRESSION_STYLE = FinalizedQuestion(
    question_id="writing_seed_expression_style_v1", context=_CONTEXT_ID, target_traits=[], frame_id="seed_anchor",
    question_text="같은 내용을 어떤 방식으로 표현할지 고민하게 됐다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="writing_seed_expression_style_v1_o1", role_id="try_new_way",
            text="지금까지 안 써본 새로운 표현 방식을 시도해본다", primary_trait_delta={"novelty_seeking": 1}),
        FinalizedOption(option_id="writing_seed_expression_style_v1_o2", role_id="write_it_out",
            text="생각을 글로 정리해서 표현해본다", primary_trait_delta={"verbal_expression": 1}),
        FinalizedOption(option_id="writing_seed_expression_style_v1_o3", role_id="make_it_visual",
            text="이미지나 그림으로 표현하는 방법을 떠올려본다", primary_trait_delta={"visual_expression": 1}),
        FinalizedOption(option_id="writing_seed_expression_style_v1_o4", role_id="consider_word_choice",
            text="어떤 단어나 표현이 더 어울릴지 세밀하게 따져본다", primary_trait_delta={"aesthetic_sensitivity": 1}),
        FinalizedOption(option_id="writing_seed_expression_style_v1_o5", role_id="use_familiar_way",
            text="익숙하게 써오던 방식대로 표현한다", primary_trait_delta={}),
    ],
)
_SEED_EXPRESSION_STYLE_RATIONALE = {
    "try_new_way": "익숙한 방식 대신 새로운 표현을 스스로 시도하는 행동이 드러나 novelty_seeking 후보로 연결된다",
    "write_it_out": "생각을 말이나 글로 정리해 표현하려는 행동이 드러나 verbal_expression 후보로 연결된다",
    "make_it_visual": "글이 아닌 이미지로 표현하는 방법을 떠올리는 행동이 드러나 visual_expression 후보로 연결된다",
    "consider_word_choice": "단어와 표현의 미묘한 차이를 세밀하게 따지는 행동이 드러나 aesthetic_sensitivity 후보로 연결된다",
    "use_familiar_way": "익숙한 방식을 그대로 쓰는 것은 기본값에 가까워 특정 성향의 직접 근거로 보기 어렵다",
}

_SEED_READER_REACTION = FinalizedQuestion(
    question_id="writing_seed_reader_reaction_v1", context=_CONTEXT_ID, target_traits=[], frame_id="seed_anchor",
    question_text="쓴 글을 누군가 읽게 될 거라고 상상해보세요. 무엇을 가장 먼저 신경 쓰나요?",
    options=[
        FinalizedOption(option_id="writing_seed_reader_reaction_v1_o1", role_id="predict_reaction",
            text="읽는 사람이 이 글을 어떻게 받아들일지 예상해본다", primary_trait_delta={"audience_response_prediction": 1}),
        FinalizedOption(option_id="writing_seed_reader_reaction_v1_o2", role_id="state_my_point_clearly",
            text="내가 하고 싶은 말을 분명하게 드러낸다", primary_trait_delta={"opinion_expression": 1}),
        FinalizedOption(option_id="writing_seed_reader_reaction_v1_o3", role_id="check_if_clear",
            text="오해 없이 전달되는지 표현을 세밀하게 다시 본다", primary_trait_delta={"detail_orientation": 1}),
        FinalizedOption(option_id="writing_seed_reader_reaction_v1_o4", role_id="imagine_their_feeling",
            text="글을 읽고 어떤 감정을 느낄지 상상해본다", primary_trait_delta={"emotional_interpretation": 1}),
        FinalizedOption(option_id="writing_seed_reader_reaction_v1_o5", role_id="just_finish_it",
            text="일단 다 쓰고 끝낸다", primary_trait_delta={}),
    ],
)
_SEED_READER_REACTION_RATIONALE = {
    "predict_reaction": "읽는 사람의 반응을 미리 예상해보는 행동이 직접 드러나 audience_response_prediction 후보로 연결된다",
    "state_my_point_clearly": "하고 싶은 말을 분명하게 드러내는 행동이 드러나 opinion_expression 후보로 연결된다",
    "check_if_clear": "오해 없이 전달되는지 세밀하게 다시 확인하는 행동이 드러나 detail_orientation 후보로 연결된다",
    "imagine_their_feeling": "독자가 느낄 감정을 상상해보는 행동이 드러나 emotional_interpretation 후보로 연결된다",
    "just_finish_it": "일단 다 쓰고 끝내는 것은 마무리 자체일 뿐, 특정 성향의 직접 근거로 보기는 약하다",
}

_SEED_SOURCE_COMPARISON = FinalizedQuestion(
    question_id="writing_seed_source_comparison_v1", context=_CONTEXT_ID, target_traits=[], frame_id="seed_anchor",
    question_text="같은 주제를 다룬 자료 여러 개를 놓고 봐야 한다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="writing_seed_source_comparison_v1_o1", role_id="compare_content",
            text="자료들 사이에 내용이 어떻게 다른지 비교해본다", primary_trait_delta={"information_comparison": 1}),
        FinalizedOption(option_id="writing_seed_source_comparison_v1_o2", role_id="trace_why_differ",
            text="왜 자료마다 다르게 설명하는지 이유를 따져본다", primary_trait_delta={"causal_analysis": 1}),
        FinalizedOption(option_id="writing_seed_source_comparison_v1_o3", role_id="see_the_whole_picture",
            text="이 자료들이 큰 주제 안에서 어떻게 연결되는지 살펴본다", primary_trait_delta={"systems_thinking": 1}),
        FinalizedOption(option_id="writing_seed_source_comparison_v1_o4", role_id="decide_with_one",
            text="일단 가장 먼저 본 자료를 기준으로 삼는다", primary_trait_delta={}),
        FinalizedOption(option_id="writing_seed_source_comparison_v1_o5", role_id="proceed_without_full_certainty",
            text="완전히 확실하지 않아도 종합해서 결론을 낸다", primary_trait_delta={"uncertainty_tolerance": 1}),
    ],
)
_SEED_SOURCE_COMPARISON_RATIONALE = {
    "compare_content": "자료들 사이의 내용 차이를 비교하는 행동이 드러나 information_comparison 후보로 연결된다",
    "trace_why_differ": "자료마다 다른 이유를 능동적으로 따져보는 행동이 드러나 causal_analysis 후보로 연결된다",
    "see_the_whole_picture": "자료들이 큰 주제와 어떻게 연결되는지 구조로 살피는 행동이 드러나 systems_thinking 후보로 연결된다",
    "decide_with_one": "먼저 본 자료를 그대로 기준 삼는 것은 특정 성향의 직접 근거로 보기 어렵다",
    "proceed_without_full_certainty": "완전한 확신이 없어도 종합해 결론을 내리는 행동이 드러나 uncertainty_tolerance 후보로 연결된다",
}

SEED_ANCHOR_VARIANTS = [
    ContextPackSeedAnchorQuestion(anchor_id="story_interpretation", question=_SEED_STORY_INTERPRETATION),
    ContextPackSeedAnchorQuestion(anchor_id="information_organizing", question=_SEED_INFORMATION_ORGANIZING),
    ContextPackSeedAnchorQuestion(anchor_id="expression_style", question=_SEED_EXPRESSION_STYLE),
    ContextPackSeedAnchorQuestion(anchor_id="reader_reaction", question=_SEED_READER_REACTION),
    ContextPackSeedAnchorQuestion(anchor_id="source_comparison", question=_SEED_SOURCE_COMPARISON),
]

# ============================== Anchor Backup Questions ==============================

_BACKUP_STORY_INTERPRETATION = FinalizedQuestion(
    question_id="writing_backup_story_interpretation_v1", context=_CONTEXT_ID, target_traits=[], frame_id="backup",
    question_text="이야기의 결말이 뚜렷하게 설명되지 않고 끝났다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="writing_backup_story_interpretation_v1_o1", role_id="guess_the_meaning",
            text="작가가 어떤 의도로 이렇게 끝냈는지 짚어본다", primary_trait_delta={"causal_analysis": 1}),
        FinalizedOption(option_id="writing_backup_story_interpretation_v1_o2", role_id="make_my_own_ending",
            text="내 나름대로 결말을 상상해서 채워본다", primary_trait_delta={"creative_ideation": 1}),
        FinalizedOption(option_id="writing_backup_story_interpretation_v1_o3", role_id="compare_other_interpretations",
            text="다른 사람들은 이 결말을 어떻게 해석하는지 찾아본다", primary_trait_delta={"information_comparison": 1}),
        FinalizedOption(option_id="writing_backup_story_interpretation_v1_o4", role_id="decide_my_own_interpretation",
            text="다른 해석과 상관없이 내가 느낀 대로 결론짓는다", primary_trait_delta={"independent_judgment": 1}),
        FinalizedOption(option_id="writing_backup_story_interpretation_v1_o5", role_id="leave_it_open",
            text="특별히 정리하지 않고 그대로 둔다", primary_trait_delta={}),
    ],
)
_BACKUP_STORY_INTERPRETATION_RATIONALE = {
    "guess_the_meaning": "작가의 의도를 능동적으로 짚어보는 행동이 드러나 causal_analysis 후보로 연결된다",
    "make_my_own_ending": "결말을 스스로 상상해 채우는 행동이 드러나 creative_ideation 후보로 연결된다",
    "compare_other_interpretations": "다른 사람의 해석을 찾아 비교하는 행동이 드러나 information_comparison 후보로 연결된다",
    "decide_my_own_interpretation": "다른 해석과 무관하게 스스로 판단해 결론짓는 행동이 드러나 independent_judgment 후보로 연결된다",
    "leave_it_open": "그대로 두는 것은 판단을 유보하는 것이라 특정 성향의 직접 근거로 보기 어렵다",
}

_BACKUP_INFORMATION_ORGANIZING = FinalizedQuestion(
    question_id="writing_backup_information_organizing_v1", context=_CONTEXT_ID, target_traits=[], frame_id="backup",
    question_text="정리하던 정보의 양이 생각보다 많다는 걸 알게 됐다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="writing_backup_information_organizing_v1_o1", role_id="reorganize_structure",
            text="구조를 다시 짜서 순서를 조정한다", primary_trait_delta={"planning": 1}),
        FinalizedOption(option_id="writing_backup_information_organizing_v1_o2", role_id="push_through_all",
            text="많아도 전부 끝까지 정리한다", primary_trait_delta={"persistence_completion": 1}),
        FinalizedOption(option_id="writing_backup_information_organizing_v1_o3", role_id="simplify_it",
            text="덜 중요한 부분은 줄이는 방식으로 바꾼다", primary_trait_delta={"change_adaptation": 1}),
        FinalizedOption(option_id="writing_backup_information_organizing_v1_o4", role_id="recheck_each_item",
            text="빠진 게 없는지 항목을 하나하나 다시 확인한다", primary_trait_delta={"detail_orientation": 1}),
        FinalizedOption(option_id="writing_backup_information_organizing_v1_o5", role_id="take_a_break_first",
            text="잠깐 쉬었다가 다시 본다", primary_trait_delta={}),
    ],
)
_BACKUP_INFORMATION_ORGANIZING_RATIONALE = {
    "reorganize_structure": "구조를 다시 짜서 순서를 조정하는 행동이 드러나 planning 후보로 연결된다",
    "push_through_all": "양이 많아도 포기하지 않고 끝까지 정리하는 행동이 드러나 persistence_completion 후보로 연결된다",
    "simplify_it": "방식을 바꿔 덜 중요한 부분을 줄이는 행동이 드러나 change_adaptation 후보로 연결된다",
    "recheck_each_item": "빠진 부분이 없는지 하나하나 다시 확인하는 행동이 드러나 detail_orientation 후보로 연결된다",
    "take_a_break_first": "잠깐 쉬는 것은 일반적인 컨디션 관리 행동일 뿐, 특정 성향의 직접 근거는 아니다",
}

_BACKUP_EXPRESSION_STYLE = FinalizedQuestion(
    question_id="writing_backup_expression_style_v1", context=_CONTEXT_ID, target_traits=[], frame_id="backup",
    question_text="정해진 형식대로 쓰는 게 이 내용에는 잘 안 어울린다는 생각이 들었다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="writing_backup_expression_style_v1_o1", role_id="try_different_format",
            text="다른 형식을 새로 시도해본다", primary_trait_delta={"novelty_seeking": 1}),
        FinalizedOption(option_id="writing_backup_expression_style_v1_o2", role_id="keep_original_format",
            text="정해진 형식을 그대로 따른다", primary_trait_delta={}),
        FinalizedOption(option_id="writing_backup_expression_style_v1_o3", role_id="combine_formats",
            text="몇 가지 형식을 섞어서 새로운 방식을 만들어본다", primary_trait_delta={"creative_ideation": 1}),
        FinalizedOption(option_id="writing_backup_expression_style_v1_o4", role_id="refine_word_by_word",
            text="표현 하나하나를 더 어울리게 다듬는다", primary_trait_delta={"aesthetic_sensitivity": 1}),
        FinalizedOption(option_id="writing_backup_expression_style_v1_o5", role_id="explain_in_words_more",
            text="이미지보다 말이나 글로 더 풀어서 설명한다", primary_trait_delta={"verbal_expression": 1}),
    ],
)
_BACKUP_EXPRESSION_STYLE_RATIONALE = {
    "try_different_format": "정해진 형식 대신 다른 형식을 스스로 시도하는 행동이 드러나 novelty_seeking 후보로 연결된다",
    "keep_original_format": "정해진 형식을 그대로 따르는 것은 기본값에 가까워 특정 성향의 직접 근거로 보기 어렵다",
    "combine_formats": "여러 형식을 섞어 새로운 방식을 만드는 행동이 드러나 creative_ideation 후보로 연결된다",
    "refine_word_by_word": "표현을 하나하나 더 어울리게 다듬는 행동이 드러나 aesthetic_sensitivity 후보로 연결된다",
    "explain_in_words_more": "말이나 글로 더 풀어서 설명하려는 행동이 드러나 verbal_expression 후보로 연결된다",
}

_BACKUP_READER_REACTION = FinalizedQuestion(
    question_id="writing_backup_reader_reaction_v1", context=_CONTEXT_ID, target_traits=[], frame_id="backup",
    question_text="쓴 글에 대해 누군가 이해가 안 된다는 반응을 보였다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="writing_backup_reader_reaction_v1_o1", role_id="guess_why_confusing",
            text="어느 부분이 왜 헷갈렸을지 원인을 짚어본다", primary_trait_delta={"causal_analysis": 1}),
        FinalizedOption(option_id="writing_backup_reader_reaction_v1_o2", role_id="rewrite_for_clarity",
            text="표현을 다시 다듬어 고쳐 쓴다", primary_trait_delta={"change_adaptation": 1}),
        FinalizedOption(option_id="writing_backup_reader_reaction_v1_o3", role_id="ask_their_feeling",
            text="상대가 어떤 부분에서 헷갈렸는지 먼저 물어본다", primary_trait_delta={}),
        FinalizedOption(option_id="writing_backup_reader_reaction_v1_o4", role_id="predict_future_readers",
            text="다음에 읽을 사람도 비슷하게 느낄지 미리 예상해본다", primary_trait_delta={"audience_response_prediction": 1}),
        FinalizedOption(option_id="writing_backup_reader_reaction_v1_o5", role_id="leave_it_as_is",
            text="원래 쓴 그대로 둔다", primary_trait_delta={"persistence_completion": 1}),
    ],
)
_BACKUP_READER_REACTION_RATIONALE = {
    "guess_why_confusing": "헷갈린 이유를 능동적으로 짚어보는 행동이 드러나 causal_analysis 후보로 연결된다",
    "rewrite_for_clarity": "표현을 다시 다듬어 고치는 행동이 드러나 change_adaptation 후보로 연결된다",
    "ask_their_feeling": "직접 물어보는 것은 일반적인 확인 행동일 뿐, 특정 성향의 직접 근거로 보기는 약하다",
    "predict_future_readers": "다른 독자도 비슷하게 느낄지 미리 예상하는 행동이 드러나 audience_response_prediction 후보로 연결된다",
    "leave_it_as_is": "고치지 않고 그대로 두는 것은 원래 쓴 것을 끝까지 유지하는 행동이 드러나 persistence_completion 후보로 연결된다",
}

_BACKUP_SOURCE_COMPARISON = FinalizedQuestion(
    question_id="writing_backup_source_comparison_v1", context=_CONTEXT_ID, target_traits=[], frame_id="backup",
    question_text="찾아본 자료 중 하나가 다른 자료들과 결이 다르다는 걸 알게 됐다고 상상해보세요. 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(option_id="writing_backup_source_comparison_v1_o1", role_id="dig_into_difference",
            text="왜 이 자료만 다른지 원인을 파고든다", primary_trait_delta={"causal_analysis": 1}),
        FinalizedOption(option_id="writing_backup_source_comparison_v1_o2", role_id="search_for_more",
            text="더 많은 자료를 찾아서 비교해본다", primary_trait_delta={"information_comparison": 1}),
        FinalizedOption(option_id="writing_backup_source_comparison_v1_o3", role_id="exclude_it",
            text="이 자료는 빼고 나머지만 사용한다", primary_trait_delta={}),
        FinalizedOption(option_id="writing_backup_source_comparison_v1_o4", role_id="see_broader_context",
            text="이 차이가 전체 맥락에서 어떤 의미인지 살펴본다", primary_trait_delta={"systems_thinking": 1}),
        FinalizedOption(option_id="writing_backup_source_comparison_v1_o5", role_id="decide_despite_gap",
            text="차이가 남아 있어도 종합해서 결론을 낸다", primary_trait_delta={"uncertainty_tolerance": 1}),
    ],
)
_BACKUP_SOURCE_COMPARISON_RATIONALE = {
    "dig_into_difference": "다른 이유를 능동적으로 파고드는 행동이 드러나 causal_analysis 후보로 연결된다",
    "search_for_more": "더 많은 자료를 찾아 비교하는 행동이 드러나 information_comparison 후보로 연결된다",
    "exclude_it": "다른 자료를 그냥 배제하는 것은 단순 처리에 가까워 특정 성향의 직접 근거로 보기 어렵다",
    "see_broader_context": "차이를 전체 맥락과 연결해 구조로 살피는 행동이 드러나 systems_thinking 후보로 연결된다",
    "decide_despite_gap": "차이가 남아 있어도 종합해서 결론 내리는 행동이 드러나 uncertainty_tolerance 후보로 연결된다",
}

ANCHOR_BACKUP_QUESTIONS = [
    ContextPackAnchorBackupQuestion(anchor_id="story_interpretation", question=_BACKUP_STORY_INTERPRETATION),
    ContextPackAnchorBackupQuestion(anchor_id="information_organizing", question=_BACKUP_INFORMATION_ORGANIZING),
    ContextPackAnchorBackupQuestion(anchor_id="expression_style", question=_BACKUP_EXPRESSION_STYLE),
    ContextPackAnchorBackupQuestion(anchor_id="reader_reaction", question=_BACKUP_READER_REACTION),
    ContextPackAnchorBackupQuestion(anchor_id="source_comparison", question=_BACKUP_SOURCE_COMPARISON),
]

# ============================== Mapping Rationale ==============================

OPTION_MAPPING_RATIONALES = [
    *_rationales_for(_SEED_STORY_INTERPRETATION, "seed_anchor", _SEED_STORY_INTERPRETATION_RATIONALE),
    *_rationales_for(_SEED_INFORMATION_ORGANIZING, "seed_anchor", _SEED_INFORMATION_ORGANIZING_RATIONALE),
    *_rationales_for(_SEED_EXPRESSION_STYLE, "seed_anchor", _SEED_EXPRESSION_STYLE_RATIONALE),
    *_rationales_for(_SEED_READER_REACTION, "seed_anchor", _SEED_READER_REACTION_RATIONALE),
    *_rationales_for(_SEED_SOURCE_COMPARISON, "seed_anchor", _SEED_SOURCE_COMPARISON_RATIONALE),
    *_rationales_for(_BACKUP_STORY_INTERPRETATION, "anchor_backup", _BACKUP_STORY_INTERPRETATION_RATIONALE),
    *_rationales_for(_BACKUP_INFORMATION_ORGANIZING, "anchor_backup", _BACKUP_INFORMATION_ORGANIZING_RATIONALE),
    *_rationales_for(_BACKUP_EXPRESSION_STYLE, "anchor_backup", _BACKUP_EXPRESSION_STYLE_RATIONALE),
    *_rationales_for(_BACKUP_READER_REACTION, "anchor_backup", _BACKUP_READER_REACTION_RATIONALE),
    *_rationales_for(_BACKUP_SOURCE_COMPARISON, "anchor_backup", _BACKUP_SOURCE_COMPARISON_RATIONALE),
]

# ============================== Pack ==============================

CONTEXT_PACK = ContextPack(
    context_id=_CONTEXT_ID,
    routing_blueprint=_ROUTING_BLUEPRINT,
    anchor_presentations=ANCHOR_PRESENTATIONS,
    seed_anchor_variants=SEED_ANCHOR_VARIANTS,
    anchor_backup_questions=ANCHOR_BACKUP_QUESTIONS,
    option_mapping_rationales=OPTION_MAPPING_RATIONALES,
    direct_probe_candidates=[],
    forbidden_assumptions=[
        "독서량이나 국어 성적으로 평가하지 않는다",
        "글을 잘 쓴다는 자기평가를 묻지 않는다",
        "글쓰기 실력 자체를 측정하지 않는다",
    ],
    review_artifact_paths=["data/reviews/context_packs/writing_review_status.json"],
    pack_version="v1.0",
)
