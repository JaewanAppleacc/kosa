"""Question Frame ↔ 꼬리질문 위치 매핑 — 1차 초안 (DRAFT, 2인 교차검토 전).

설계안 §7-4는 9개 Frame 문구만 제시하고, §7-2는 위치별(1~4) 테마만 정의한다.
"어떤 Frame이 어떤 위치에 쓰이는가"는 설계안에 명시적 표가 없어서, 각 Frame 문구의
의미를 보고 team이 직접 매핑해야 한다. 아래는 그 1차 초안이다.

하나의 Frame이 여러 위치에 걸쳐 있어도 된다(예: '다른 사람의 반응이 다르면 어떻게
하는가?'는 교차확인에도, 반대·대안 확인에도 쓸 수 있다) — 실제로 어떤 Trait를 노리는지는
Planner가 §8 우선순위로 정하고, Frame은 그 질문이 어떤 "말투/상황"으로 표현될지만 정한다.
"""

from __future__ import annotations

from enum import Enum


class PositionTheme(str, Enum):
    """§7-2: 꼬리질문 1~4번의 고정 테마. 5~6번은 테마가 아니라 §8의 사전식 우선순위로 정해진다."""

    DEEPEN = "deepen"  # 꼬리질문 1: Seed 답변의 관심 지점 심화
    BEHAVIOR = "behavior"  # 꼬리질문 2: 실제 행동·문제 해결 방식 확인
    CROSS_CONTEXT = "cross_context"  # 꼬리질문 3: 다른 Context Evidence와 교차 확인
    ALTERNATIVE = "alternative"  # 꼬리질문 4: 반대·대안 상황 확인


QUESTION_FRAME_TEXT: dict[str, str] = {
    "first_action": "가장 먼저 무엇을 하고 싶은가?",
    "longest_focus": "어떤 부분에 가장 오래 집중하는가?",
    "problem_check": "문제가 생기면 무엇부터 확인하는가?",
    "limited_time_priority": "제한된 시간에는 무엇을 우선하는가?",
    "unexpected_result": "결과가 예상과 다르면 어떻게 수정하는가?",
    "others_reaction": "다른 사람의 반응이 다르면 어떻게 하는가?",
    "conflicting_opinions": "여러 의견이 충돌하면 무엇을 기준으로 결정하는가?",
    "new_tool": "새로운 도구가 주어지면 어떻게 접근하는가?",
    "team_role": "팀 활동에서는 어떤 역할을 맡고 싶은가?",
}

# 테마 하나에 여러 Frame 후보를 두고, 앞에 있는 걸 우선 사용한다(결정론적 선택을 위해).
THEME_TO_FRAME_IDS: dict[PositionTheme, list[str]] = {
    PositionTheme.DEEPEN: ["longest_focus", "first_action"],
    PositionTheme.BEHAVIOR: ["problem_check", "limited_time_priority", "new_tool"],
    PositionTheme.CROSS_CONTEXT: ["conflicting_opinions", "team_role", "others_reaction"],
    PositionTheme.ALTERNATIVE: ["unexpected_result", "others_reaction"],
}

# 꼬리질문 5~6번은 테마가 없다 — Planner가 목표 Trait를 먼저 정하고, 그 Trait를 다룰 수 있는
# Frame이면 아무거나 쓴다. 이 목록은 "제약 없음" Fallback 후보다.
OPEN_FRAME_IDS: list[str] = list(QUESTION_FRAME_TEXT.keys())


def position_to_theme(position: int) -> PositionTheme | None:
    """position은 1-based(1~6). 5~6은 테마가 없으므로 None을 반환한다."""

    mapping = {
        1: PositionTheme.DEEPEN,
        2: PositionTheme.BEHAVIOR,
        3: PositionTheme.CROSS_CONTEXT,
        4: PositionTheme.ALTERNATIVE,
    }
    return mapping.get(position)


def frame_for_theme(theme: PositionTheme, excluded_frame_ids: set[str] | None = None) -> str:
    """테마의 첫 번째 후보 Frame을 반환한다. 이미 쓴 Frame은 제외하고 다음 후보로 넘어간다."""

    excluded = excluded_frame_ids or set()
    for frame_id in THEME_TO_FRAME_IDS[theme]:
        if frame_id not in excluded:
            return frame_id
    # 후보를 다 썼으면 테마 밖이라도 같은 테마의 첫 후보를 재사용한다(완전히 막히지 않도록).
    return THEME_TO_FRAME_IDS[theme][0]
