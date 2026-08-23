"""Context Anchor Presentation 정본 — 2026-08-23 Trait Ontology v2(2.5.1단계) §3/§7/§8/§9.

game/media/school_life 각 5개 Anchor(2.5단계 Context Routing에서 이미 확정한 Anchor
ID)에 대해, 학생에게 보여줄 상황 표현만 정의한다. 여기 적힌 `forbidden_assumptions`는
결정론적 Seed Anchor Variant(`src/data/questions/seed_anchor_variants.py`)를 검토할 때,
그리고 LLM Prompt에 전달해 재생성 판정에 쓸 때 똑같이 참조하는 단일 정본이다."""

from __future__ import annotations

from src.data.contexts.context_definitions import CONTEXT_DEFINITIONS
from src.data.questions.context_routing_blueprints import CONTEXT_ROUTING_BLUEPRINTS_BY_CONTEXT
from src.schemas.context_anchor_presentation import ContextAnchorPresentation, ContextAnchorPresentationError

_KNOWN_CONTEXT_IDS = {c.context_id for c in CONTEXT_DEFINITIONS}

# 2.5.1단계 §7 — game 5개 Anchor. cooperative_role에서만 팀원·역할 분담을 기본 상황으로
# 쓸 수 있다(§7 "중요" 절) — 나머지 4개는 팀원을 forbidden_assumptions에 명시한다.
GAME_ANCHOR_PRESENTATIONS: list[ContextAnchorPresentation] = [
    ContextAnchorPresentation(
        context_id="game", anchor_id="story_exploration", label="이야기·탐험",
        situation_terms=["이야기", "세계", "탐험", "선택"],
        preferred_scenarios=["이야기의 진행", "새로운 지역 탐색", "선택에 따라 달라지는 전개"],
        forbidden_assumptions=["팀원", "경기 순위", "협동 역할"],
    ),
    ContextAnchorPresentation(
        context_id="game", anchor_id="strategy_puzzle", label="전략·퍼즐",
        situation_terms=["전략", "문제 해결", "자원", "순서"],
        preferred_scenarios=["자원 배분 계획", "퍼즐의 해법 찾기", "제한된 조건 안에서 최적의 수 찾기"],
        forbidden_assumptions=["팀원", "실시간 경쟁 순위"],
    ),
    ContextAnchorPresentation(
        context_id="game", anchor_id="competition_mastery", label="경쟁·실력 향상",
        situation_terms=["기록", "도전", "실력 향상", "연습"],
        preferred_scenarios=["기록 경신 도전", "반복 연습으로 실력 올리기", "상대와의 실력 대결"],
        forbidden_assumptions=["팀원", "협동 역할 분담"],
    ),
    ContextAnchorPresentation(
        context_id="game", anchor_id="cooperative_role", label="협동·역할 수행",
        situation_terms=["역할 분담", "협력", "팀 상황", "합"],
        preferred_scenarios=["팀원과 역할을 나눠 진행", "함께 목표를 이루기 위한 협력"],
        # 여기서만 팀 상황을 기본 전제로 쓸 수 있다 — forbidden_assumptions는 비워 둔다.
        forbidden_assumptions=[],
    ),
    ContextAnchorPresentation(
        context_id="game", anchor_id="building_creation", label="건축·창작",
        situation_terms=["만들기", "꾸미기", "조합", "창작"],
        preferred_scenarios=["원하는 대로 무언가를 만들고 꾸미기", "여러 요소를 조합해 새로운 것을 시도"],
        forbidden_assumptions=["팀원", "승패", "경쟁 순위"],
    ),
]

# 2.5.1단계 §8 — media 5개 Anchor. 감상자 관점을 유지한다(2.5단계 §7과 동일 원칙).
MEDIA_ANCHOR_PRESENTATIONS: list[ContextAnchorPresentation] = [
    ContextAnchorPresentation(
        context_id="media", anchor_id="film_drama", label="영화·드라마",
        situation_terms=["장면", "인물", "이야기", "결말"],
        preferred_scenarios=["인물의 선택과 결말 해석", "장면 구성과 전개 방식 감상"],
        forbidden_assumptions=["편집", "촬영", "제출"],
    ),
    ContextAnchorPresentation(
        context_id="media", anchor_id="online_video", label="온라인 영상",
        situation_terms=["영상", "진행 흐름", "전달 방식"],
        preferred_scenarios=["영상의 진행 흐름을 따라가며 감상", "정보나 이야기가 전달되는 방식에 반응"],
        forbidden_assumptions=["직접 제작", "편집", "촬영"],
    ),
    ContextAnchorPresentation(
        context_id="media", anchor_id="animation_webcontent", label="애니메이션·웹콘텐츠",
        situation_terms=["장면", "그림", "연출", "세계관"],
        preferred_scenarios=["세계관과 설정 이해", "그림체·연출 감상"],
        forbidden_assumptions=["직접 작화", "편집"],
    ),
    ContextAnchorPresentation(
        context_id="media", anchor_id="stage_performance", label="공연·뮤지컬",
        situation_terms=["무대", "배우", "음악", "조명", "연기"],
        preferred_scenarios=["무대 연출과 배우의 연기 감상", "음악·조명이 만드는 분위기 감상"],
        # §8 금지: stage_performance 선택자에게 영상 편집을 전제하지 않는다.
        forbidden_assumptions=["영상 편집", "촬영본 편집"],
    ),
    ContextAnchorPresentation(
        context_id="media", anchor_id="documentary", label="다큐멘터리",
        situation_terms=["내용", "근거", "사례", "설명 방식"],
        preferred_scenarios=["제시된 근거와 사례 검토", "설명 방식과 구성 이해"],
        # §8 금지: documentary 선택자에게 허구적 결말 변경을 기본 전제로 하지 않는다.
        forbidden_assumptions=["결말을 바꿔본다면", "허구적 결말"],
    ),
]

# 2.5.1단계 §9 — school_life 5개 Anchor.
SCHOOL_LIFE_ANCHOR_PRESENTATIONS: list[ContextAnchorPresentation] = [
    ContextAnchorPresentation(
        context_id="school_life", anchor_id="academic_study", label="학업·공부",
        situation_terms=["시험 범위", "공부 방법", "시간 배분"],
        preferred_scenarios=["시험공부 계획 조정", "공부 방법과 시간 배분 결정"],
        forbidden_assumptions=["조별", "팀원"],
    ),
    ContextAnchorPresentation(
        context_id="school_life", anchor_id="assignment_evaluation", label="과제·수행평가",
        situation_terms=["수행평가 조건", "주제", "제출 기한"],
        preferred_scenarios=["수행평가 주제 선정", "제출 기한 임박 상황"],
        forbidden_assumptions=["조별", "팀원"],
    ),
    ContextAnchorPresentation(
        context_id="school_life", anchor_id="course_career", label="과목·진로선택",
        situation_terms=["선택과목", "학과 정보", "진로 결정"],
        preferred_scenarios=["선택과목 신청", "진로·학과 정보 탐색"],
        forbidden_assumptions=["조별", "팀원"],
    ),
    ContextAnchorPresentation(
        context_id="school_life", anchor_id="friendship", label="친구 관계",
        situation_terms=["생각 차이", "오해", "관계 조정"],
        preferred_scenarios=["친구와의 생각 차이 조율", "오해 해소"],
        forbidden_assumptions=["조별 과제", "팀 프로젝트"],
    ),
    ContextAnchorPresentation(
        context_id="school_life", anchor_id="club_activity", label="동아리·학교 활동",
        situation_terms=["동아리 선택", "역할", "활동 일정"],
        preferred_scenarios=["동아리 선택과 역할 정하기", "활동 일정 조율"],
        forbidden_assumptions=[],
    ),
]

CONTEXT_ANCHOR_PRESENTATIONS: list[ContextAnchorPresentation] = [
    *GAME_ANCHOR_PRESENTATIONS, *MEDIA_ANCHOR_PRESENTATIONS, *SCHOOL_LIFE_ANCHOR_PRESENTATIONS,
]

CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY: dict[tuple[str, str], ContextAnchorPresentation] = {
    (p.context_id, p.anchor_id): p for p in CONTEXT_ANCHOR_PRESENTATIONS
}


def _validate() -> None:
    keys = [(p.context_id, p.anchor_id) for p in CONTEXT_ANCHOR_PRESENTATIONS]
    if len(keys) != len(set(keys)):
        raise ContextAnchorPresentationError(f"(context_id, anchor_id) 중복이 있다: {keys}")

    unknown_contexts = {p.context_id for p in CONTEXT_ANCHOR_PRESENTATIONS} - _KNOWN_CONTEXT_IDS
    if unknown_contexts:
        raise ContextAnchorPresentationError(f"CONTEXT_DEFINITIONS에 없는 context_id: {unknown_contexts}")

    # §3: Routing Blueprint와의 불일치를 Fail-Fast로 검증 — 이 Presentation 정본이 실제
    # Context Routing Blueprint(2.5단계)가 만들어내는 Anchor 집합과 정확히 같아야 한다.
    for context_id, routing_bp in CONTEXT_ROUTING_BLUEPRINTS_BY_CONTEXT.items():
        expected_anchors = {m.context_anchor for m in routing_bp.option_mappings}
        actual_anchors = {p.anchor_id for p in CONTEXT_ANCHOR_PRESENTATIONS if p.context_id == context_id}
        if actual_anchors != expected_anchors:
            missing = expected_anchors - actual_anchors
            extra = actual_anchors - expected_anchors
            raise ContextAnchorPresentationError(
                f"{context_id}: Presentation Anchor 집합이 Routing Blueprint와 다르다"
                f"(빠짐: {sorted(missing)}, 불필요: {sorted(extra)})"
            )


_validate()
