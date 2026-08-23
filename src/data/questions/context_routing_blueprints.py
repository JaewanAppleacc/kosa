"""Context Routing Blueprint 3개(game/media/school_life) — 2026-08-23 Trait Ontology
v2(2.5단계) §4.

각 Context에 실제로 진입하기 전, 학생이 어떤 방식으로 그 Context를 즐기는지(Anchor)를
먼저 확인한다 — 사용자 검수 피드백(질문 메모: "게임 중에서도 협동형 게임이 있고,
혼자 플레이하는 게임이 있고 장르가 다양해서 한 질문이 모든 장르를 포괄하긴
어려운것같아")을 반영한다. 이 질문의 답은 Trait 점수·Evidence·Opportunity Count
어디에도 반영되지 않는다(§2) — `context_anchor_choices`에만 저장되고, 이후 같은
Context의 Direct Probe/Tail 질문 문구를 조절하는 참고 재료로만 쓴다."""

from __future__ import annotations

from src.schemas.question import FinalizedOption, FinalizedQuestion
from src.schemas.context_routing import ContextRoutingBlueprint, ContextRoutingOptionMapping

_Row = tuple[str, str, str, str]  # (role_id, option_text, context_anchor, anchor_label)


def _build_routing(*, context_id: str, blueprint_id: str, question_text: str, rows: list[_Row]) -> ContextRoutingBlueprint:
    if len(rows) != 5:
        raise ValueError(f"{blueprint_id}: rows는 정확히 5개여야 한다(got {len(rows)})")

    question_id = f"{blueprint_id}_base"
    mappings = [
        ContextRoutingOptionMapping(role_id=role_id, context_anchor=anchor, anchor_label=label)
        for role_id, _text, anchor, label in rows
    ]
    options = [
        FinalizedOption(option_id=f"{question_id}_o{i}", role_id=role_id, text=text, primary_trait_delta={})
        for i, (role_id, text, _anchor, _label) in enumerate(rows, start=1)
    ]
    return ContextRoutingBlueprint(
        context_id=context_id,
        blueprint_id=blueprint_id,
        option_mappings=mappings,
        base_question=FinalizedQuestion(
            question_id=question_id, context=context_id, target_traits=[], frame_id="context_routing",
            question_text=question_text, options=options,
        ),
    )


# --- game ---
GAME_CONTEXT_ROUTER_V1 = _build_routing(
    context_id="game",
    blueprint_id="game_context_router_v1",
    question_text="최근 게임을 즐길 때 가장 자주 재미를 느낀 방식은 무엇인가요?",
    rows=[
        ("gr_story", "이야기나 세계를 탐험하며 진행할 때", "story_exploration", "이야기·탐험"),
        ("gr_strategy", "전략을 세우거나 문제를 해결할 때", "strategy_puzzle", "전략·퍼즐"),
        ("gr_competition", "기록이나 실력을 겨루며 도전할 때", "competition_mastery", "경쟁·기록"),
        ("gr_coop", "다른 사람과 역할을 나눠 협력할 때", "cooperative_role", "협동·역할 수행"),
        ("gr_creation", "원하는 것을 만들거나 꾸밀 때", "building_creation", "건축·꾸미기·창작"),
    ],
)

# --- media ---
MEDIA_CONTEXT_ROUTER_V1 = _build_routing(
    context_id="media",
    blueprint_id="media_context_router_v1",
    question_text="최근 가장 자주 즐긴 문화 콘텐츠는 어떤 종류인가요?",
    rows=[
        ("mr_film", "영화·드라마", "film_drama", "영화·드라마"),
        ("mr_youtube", "유튜브·온라인 영상", "online_video", "유튜브·온라인 영상"),
        ("mr_animation", "애니메이션·웹 기반 이야기 콘텐츠", "animation_webcontent", "애니메이션·웹 콘텐츠"),
        ("mr_stage", "뮤지컬·연극·공연", "stage_performance", "뮤지컬·연극·공연"),
        ("mr_documentary", "다큐멘터리·교양 콘텐츠", "documentary", "다큐멘터리·교양"),
    ],
)

# --- school_life ---
SCHOOL_LIFE_CONTEXT_ROUTER_V1 = _build_routing(
    context_id="school_life",
    blueprint_id="school_life_context_router_v1",
    question_text="요즘 학교생활에서 가장 자주 고민하는 부분은 무엇인가요?",
    rows=[
        ("sr_study", "시험과 공부 방법", "academic_study", "학업·공부"),
        ("sr_assignment", "과제·수행평가", "assignment_evaluation", "과제·수행평가"),
        ("sr_course", "선택과목·진로 결정", "course_career", "과목·진로 선택"),
        ("sr_friend", "친구 관계", "friendship", "친구 관계"),
        ("sr_club", "동아리·학교 활동", "club_activity", "동아리·학교 활동"),
    ],
)

CONTEXT_ROUTING_BLUEPRINTS: list[ContextRoutingBlueprint] = [
    GAME_CONTEXT_ROUTER_V1, MEDIA_CONTEXT_ROUTER_V1, SCHOOL_LIFE_CONTEXT_ROUTER_V1,
]

CONTEXT_ROUTING_BLUEPRINTS_BY_CONTEXT: dict[str, ContextRoutingBlueprint] = {
    b.context_id: b for b in CONTEXT_ROUTING_BLUEPRINTS
}

CONTEXT_ROUTING_BLUEPRINTS_BY_ID: dict[str, ContextRoutingBlueprint] = {
    b.blueprint_id: b for b in CONTEXT_ROUTING_BLUEPRINTS
}


def _validate_uniqueness() -> None:
    blueprint_ids = [b.blueprint_id for b in CONTEXT_ROUTING_BLUEPRINTS]
    if len(blueprint_ids) != len(set(blueprint_ids)):
        raise ValueError(f"Context Routing blueprint_id 중복: {blueprint_ids}")
    context_ids = [b.context_id for b in CONTEXT_ROUTING_BLUEPRINTS]
    if len(context_ids) != len(set(context_ids)):
        raise ValueError(f"Context Routing context_id 중복: {context_ids}")
    question_ids = [b.base_question.question_id for b in CONTEXT_ROUTING_BLUEPRINTS]
    if len(question_ids) != len(set(question_ids)):
        raise ValueError(f"Context Routing base_question.question_id 중복: {question_ids}")


_validate_uniqueness()
