"""Seed Anchor Variant 정본 — 2026-08-23 Trait Ontology v2(2.5.1단계) §4/§5/§7/§8/§9.

game/media/school_life 각 5개 Anchor에 대해 Seed Question의 문구만 다시 쓴 Variant다.
각 Variant는 원본 Seed Question(`VERTICAL_SLICE_SEED_QUESTIONS`)과 정확히 같은 5개
role_id를 쓴다 — role_id별 `primary_trait_delta`는 원본 SeedQuestion이 그대로 소유하고,
여기서는 절대 다시 정의하지 않는다(§2). 즉 같은 "행동의 의미"를 Anchor의 상황
어휘(situation_terms)로 다시 표현했을 뿐이다.

`_validate()`가 가져오는 시점에 다음을 Fail-Fast로 검증한다.
- (context_id, anchor_id)가 `CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY`에 실제로 등록돼 있다.
- Context마다 정확히 5개 Anchor(Presentation 레지스트리와 동일 집합)의 Variant가 있다.
- `option_text_by_role_id`의 Key 집합이 그 Context의 실제 Seed Question role_id 집합과
  정확히 같다.
- 이 Anchor의 `forbidden_assumptions` 문구가 Variant 문구 어디에도 들어있지 않다."""

from __future__ import annotations

from src.data.contexts.context_anchor_presentations import CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY
from src.data.questions.vertical_slice_seed_questions import VERTICAL_SLICE_SEED_QUESTIONS
from src.schemas.seed_anchor_variant import SeedAnchorVariant, SeedAnchorVariantError

_GAME_VARIANTS = [
    SeedAnchorVariant(
        context_id="game", anchor_id="story_exploration",
        question_text="이야기를 따라가며 게임을 진행할 때 가장 몰입된다고 느끼는 순간은 언제인가요?",
        option_text_by_role_id={
            "strategy_analysis": "이 전개가 왜 이렇게 흘러갔는지 이유를 알아가는 순간",
            "quick_execution": "여러 선택지를 직접 골라보면서 이야기가 어떻게 바뀌는지 확인하는 순간",
            "team_coordination": "다른 사람과 함께 이야기를 만들어가며 진행하는 순간",
            "pattern_recognition": "이야기 속에 숨겨진 단서나 복선을 알아채는 순간",
            "tool_mastery": "이야기 속에서 새로 얻은 능력이나 아이템을 활용해보는 순간",
        },
    ),
    SeedAnchorVariant(
        context_id="game", anchor_id="strategy_puzzle",
        question_text="전략을 짜거나 퍼즐을 풀 때 가장 몰입된다고 느끼는 순간은 언제인가요?",
        option_text_by_role_id={
            "strategy_analysis": "왜 이 전략이 통하는지 원리를 알아가는 순간",
            "quick_execution": "여러 방법을 직접 시도해보며 최적의 수를 찾는 순간",
            "team_coordination": "다른 사람과 의견을 맞춰가며 전략을 함께 짜는 순간",
            "pattern_recognition": "문제 속에 반복되는 규칙이나 패턴을 발견하는 순간",
            "tool_mastery": "새로운 도구나 기능을 활용해 더 나은 수를 찾아내는 순간",
        },
    ),
    SeedAnchorVariant(
        context_id="game", anchor_id="competition_mastery",
        question_text="실력을 겨루거나 기록에 도전할 때 가장 몰입된다고 느끼는 순간은 언제인가요?",
        option_text_by_role_id={
            "strategy_analysis": "왜 이번엔 잘 안 됐는지 원인을 분석하는 순간",
            "quick_execution": "여러 방법을 직접 시도하며 실력을 끌어올리는 순간",
            "team_coordination": "다른 사람과 함께 연습하며 서로 도움을 주고받는 순간",
            "pattern_recognition": "상대의 습관이나 반복되는 패턴을 알아채는 순간",
            "tool_mastery": "새로운 기술이나 조작법을 익혀 활용하는 순간",
        },
    ),
    SeedAnchorVariant(
        context_id="game", anchor_id="cooperative_role",
        question_text="팀원과 역할을 나눠 함께 게임을 진행할 때 가장 몰입된다고 느끼는 순간은 언제인가요?",
        option_text_by_role_id={
            "strategy_analysis": "이번 판이 왜 이렇게 풀렸는지 팀원과 함께 이유를 짚어보는 순간",
            "quick_execution": "맡은 역할을 직접 여러 방식으로 시도해보는 순간",
            "team_coordination": "팀원과 역할을 나누고 손발을 맞춰가는 순간",
            "pattern_recognition": "상대 팀의 움직임에서 반복되는 패턴을 찾아내는 순간",
            "tool_mastery": "맡은 역할에 맞는 장비나 기능을 새롭게 활용하는 순간",
        },
    ),
    SeedAnchorVariant(
        context_id="game", anchor_id="building_creation",
        question_text="무언가를 만들거나 꾸밀 때 가장 몰입된다고 느끼는 순간은 언제인가요?",
        option_text_by_role_id={
            "strategy_analysis": "왜 이 구조나 조합이 잘 어울리는지 이유를 알아가는 순간",
            "quick_execution": "여러 재료나 방식을 직접 시도해보며 만들어가는 순간",
            "team_coordination": "다른 사람과 아이디어를 나누며 함께 만들어가는 순간",
            "pattern_recognition": "잘 어울리는 조합이나 구조의 규칙을 발견하는 순간",
            "tool_mastery": "새로운 도구나 재료를 활용하는 방법을 알아가는 순간",
        },
    ),
]

_MEDIA_VARIANTS = [
    SeedAnchorVariant(
        context_id="media", anchor_id="film_drama",
        question_text="영화나 드라마를 볼 때 가장 흥미를 느끼는 부분은 무엇인가요?",
        option_text_by_role_id={
            "structure_analysis": "이야기나 장면이 왜 그렇게 전개됐는지 이유를 생각하는 것",
            "creative_making": "장면의 색감, 구도, 연출 방식을 살펴보는 것",
            "audience_reaction": "사람들이 이 장면을 어떻게 받아들일지 생각해보는 것",
            "character_empathy": "인물이 그 순간 어떤 감정을 느꼈을지 이해해보는 것",
            "trend_research": "비슷한 작품과 어떤 점이 다른지 찾아 비교하는 것",
        },
    ),
    SeedAnchorVariant(
        context_id="media", anchor_id="online_video",
        question_text="유튜브 같은 온라인 영상을 볼 때 가장 흥미를 느끼는 부분은 무엇인가요?",
        option_text_by_role_id={
            "structure_analysis": "영상이 왜 이런 순서로 진행되는지 이유를 생각하는 것",
            "creative_making": "화면 구성이나 자막·색감 같은 표현 방식을 살펴보는 것",
            "audience_reaction": "이 영상에 사람들이 어떻게 반응할지 생각해보는 것",
            "character_empathy": "진행자나 출연자가 어떤 감정으로 말하고 있는지 이해해보는 것",
            "trend_research": "비슷한 주제의 다른 영상과 비교해보는 것",
        },
    ),
    SeedAnchorVariant(
        context_id="media", anchor_id="animation_webcontent",
        question_text="애니메이션이나 웹툰·웹소설 같은 콘텐츠를 볼 때 가장 흥미를 느끼는 부분은 무엇인가요?",
        option_text_by_role_id={
            "structure_analysis": "이야기나 세계관이 왜 이렇게 짜였는지 이유를 생각하는 것",
            "creative_making": "그림체나 장면 연출 방식을 살펴보는 것",
            "audience_reaction": "이 장면에 사람들이 어떻게 반응할지 생각해보는 것",
            "character_empathy": "등장인물이 그 순간 느꼈을 감정을 이해해보는 것",
            "trend_research": "비슷한 세계관의 다른 작품과 비교해보는 것",
        },
    ),
    SeedAnchorVariant(
        context_id="media", anchor_id="stage_performance",
        question_text="공연이나 뮤지컬을 볼 때 가장 흥미를 느끼는 부분은 무엇인가요?",
        option_text_by_role_id={
            "structure_analysis": "이야기나 장면이 왜 그렇게 구성됐는지 이유를 생각하는 것",
            "creative_making": "무대·조명·음악이 만들어내는 분위기를 살펴보는 것",
            "audience_reaction": "관객들이 이 장면에 어떻게 반응할지 생각해보는 것",
            "character_empathy": "배우가 그 순간 표현하려 한 감정을 이해해보는 것",
            "trend_research": "비슷한 공연과 연출이 어떻게 다른지 비교해보는 것",
        },
    ),
    SeedAnchorVariant(
        context_id="media", anchor_id="documentary",
        question_text="다큐멘터리를 볼 때 가장 흥미를 느끼는 부분은 무엇인가요?",
        option_text_by_role_id={
            "structure_analysis": "설명이 왜 이런 순서로 짜였는지 이유를 생각하는 것",
            "creative_making": "화면 구성이나 자료를 보여주는 방식을 살펴보는 것",
            "audience_reaction": "이 내용에 사람들이 어떻게 반응할지 생각해보는 것",
            "character_empathy": "등장인물이나 인터뷰이가 그 순간 느꼈을 감정을 이해해보는 것",
            "trend_research": "비슷한 주제를 다룬 다른 자료와 비교해보는 것",
        },
    ),
]

_SCHOOL_LIFE_VARIANTS = [
    SeedAnchorVariant(
        context_id="school_life", anchor_id="academic_study",
        question_text="시험공부를 하거나 공부 계획을 세울 때 가장 흥미를 느끼는 부분은 무엇인가요?",
        option_text_by_role_id={
            "task_planning": "무엇을 언제 공부할지 미리 계획하고 정리하는 것",
            "team_project": "같이 공부하는 사람과 진도를 맞추고 역할을 나누는 것",
            "conflict_mediation": "공부 방법에 대해 의견이 다를 때 기준을 세우고 맞춰가는 것",
            "peer_understanding": "함께 공부하는 친구가 힘들어하는 부분을 알아채는 것",
            "adapting_change": "계획과 다른 상황이 생겼을 때 방법을 바꾸어 해결하는 것",
        },
    ),
    SeedAnchorVariant(
        context_id="school_life", anchor_id="assignment_evaluation",
        question_text="수행평가나 과제를 준비할 때 가장 흥미를 느끼는 부분은 무엇인가요?",
        option_text_by_role_id={
            "task_planning": "과제를 어떻게 진행할지 미리 계획하고 정리하는 것",
            "team_project": "과제를 함께 준비하는 사람과 역할을 나누는 것",
            "conflict_mediation": "과제 방향에 대해 의견이 다를 때 기준을 세우고 맞춰가는 것",
            "peer_understanding": "함께 준비하는 친구의 상황이나 생각을 이해하는 것",
            "adapting_change": "조건이나 기한이 바뀌었을 때 방법을 바꾸어 대응하는 것",
        },
    ),
    SeedAnchorVariant(
        context_id="school_life", anchor_id="course_career",
        question_text="선택과목이나 진로를 고민할 때 가장 흥미를 느끼는 부분은 무엇인가요?",
        option_text_by_role_id={
            "task_planning": "필요한 정보를 어떤 순서로 찾아볼지 미리 계획하는 것",
            "team_project": "같은 고민을 하는 친구와 정보를 나누고 함께 알아보는 것",
            "conflict_mediation": "주변 의견이 서로 다를 때 내 기준을 세우고 정리하는 것",
            "peer_understanding": "비슷한 고민을 하는 친구의 상황을 이해하는 것",
            "adapting_change": "생각이 바뀌었을 때 계획을 다시 조정하는 것",
        },
    ),
    SeedAnchorVariant(
        context_id="school_life", anchor_id="friendship",
        question_text="친구 관계에서 생각이 다르거나 오해가 생겼을 때 가장 신경 쓰는 부분은 무엇인가요?",
        option_text_by_role_id={
            "task_planning": "어떻게 이야기를 풀어갈지 미리 정리해보는 것",
            "team_project": "친구와 함께 시간을 보내며 관계를 맞춰가는 것",
            "conflict_mediation": "서로 다른 생각 사이에서 기준을 세우고 방향을 맞추는 것",
            "peer_understanding": "친구의 생각이나 감정을 먼저 이해해보는 것",
            "adapting_change": "상황이 달라지면 내 태도도 거기에 맞춰 바꾸는 것",
        },
    ),
    SeedAnchorVariant(
        context_id="school_life", anchor_id="club_activity",
        question_text="동아리 활동을 할 때 가장 흥미를 느끼는 부분은 무엇인가요?",
        option_text_by_role_id={
            "task_planning": "활동 일정과 순서를 미리 계획하고 정리하는 것",
            "team_project": "동아리 부원과 역할을 나누고 함께 만들어가는 것",
            "conflict_mediation": "의견이 다를 때 기준을 세우고 방향을 맞추는 것",
            "peer_understanding": "동아리 부원의 생각이나 상황을 이해하는 것",
            "adapting_change": "계획과 다른 상황이 생겼을 때 방법을 바꾸어 해결하는 것",
        },
    ),
]

SEED_ANCHOR_VARIANTS: list[SeedAnchorVariant] = [*_GAME_VARIANTS, *_MEDIA_VARIANTS, *_SCHOOL_LIFE_VARIANTS]

SEED_ANCHOR_VARIANTS_BY_KEY: dict[tuple[str, str], SeedAnchorVariant] = {
    (v.context_id, v.anchor_id): v for v in SEED_ANCHOR_VARIANTS
}


def _validate() -> None:
    keys = [(v.context_id, v.anchor_id) for v in SEED_ANCHOR_VARIANTS]
    if len(keys) != len(set(keys)):
        raise SeedAnchorVariantError(f"(context_id, anchor_id) 중복이 있다: {keys}")

    expected_keys = set(CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY.keys())
    if set(keys) != expected_keys:
        missing = expected_keys - set(keys)
        extra = set(keys) - expected_keys
        raise SeedAnchorVariantError(
            f"Seed Anchor Variant 집합이 Anchor Presentation 레지스트리와 다르다"
            f"(빠짐: {sorted(missing)}, 불필요: {sorted(extra)})"
        )

    for variant in SEED_ANCHOR_VARIANTS:
        seed = VERTICAL_SLICE_SEED_QUESTIONS[variant.context_id]
        expected_role_ids = {o.role_id for o in seed.options}
        actual_role_ids = set(variant.option_text_by_role_id.keys())
        if actual_role_ids != expected_role_ids:
            missing = expected_role_ids - actual_role_ids
            extra = actual_role_ids - expected_role_ids
            raise SeedAnchorVariantError(
                f"{variant.context_id}/{variant.anchor_id}: role_id 집합이 원본 Seed Question과 다르다"
                f"(빠짐: {sorted(missing)}, 불필요: {sorted(extra)})"
            )

        presentation = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[(variant.context_id, variant.anchor_id)]
        all_text = variant.question_text + " " + " ".join(variant.option_text_by_role_id.values())
        for phrase in presentation.forbidden_assumptions:
            if phrase in all_text:
                raise SeedAnchorVariantError(
                    f"{variant.context_id}/{variant.anchor_id}: 금지 전제 표현 {phrase!r}이 Variant 문구에 남아 있다"
                )


_validate()
