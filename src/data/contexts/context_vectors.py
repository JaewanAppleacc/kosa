"""15개 Context의 활동 축 Vector — 설계안 §6-5, 1차 초안(DRAFT, 2인 교차검토 전).

Contrast Context Selector(§5-1)의 context_distance 계산에 쓴다. 단어 임베딩이 아니라
각 Context의 `description`/`example_activities`(context_definitions.py)를 근거로 판단한
값이다. 6개 축은 전부 0.0(왼쪽 극)~1.0(오른쪽 극) — 정확한 심리측정 척도가 아니라 "이
Context가 그 축에서 어느 쪽에 더 가까운가"를 사람이 판단한 순서형 근사치다.
"""

from __future__ import annotations

from src.schemas.context import ContextVector

CONTEXT_VECTORS: dict[str, ContextVector] = {
    "game": ContextVector(
        individual_vs_team=0.5, digital_vs_physical=0.1, people_vs_system=0.7,
        appreciation_vs_creation=0.3, expression_vs_analysis=0.7, exploration_vs_goal=0.7,
    ),
    # 2026-08-23 2.5단계 §3: media 재정의(제작 중심 → 감상·해석 중심)를 반영해
    # appreciation_vs_creation을 0.5(중립)에서 0.2(감상 쪽)로 낮췄다 — 다른 5개 축은
    # 재정의 전후로 근거(description/example_activities)가 크게 안 바뀌어 그대로 뒀다.
    "media": ContextVector(
        individual_vs_team=0.3, digital_vs_physical=0.1, people_vs_system=0.3,
        appreciation_vs_creation=0.2, expression_vs_analysis=0.3, exploration_vs_goal=0.3,
    ),
    # 2.5단계 §3: school_life 재정의(조별활동 중심 → 학업/과제/과목·진로/친구관계 중심)를
    # 반영해 individual_vs_team을 0.7(팀 쪽)에서 0.4(개인 쪽에 더 가깝게)로 낮췄다 —
    # 새 정의의 상당 부분(공부·과제·과목 선택)이 개인 활동이기 때문이다.
    "school_life": ContextVector(
        individual_vs_team=0.4, digital_vs_physical=0.7, people_vs_system=0.2,
        appreciation_vs_creation=0.6, expression_vs_analysis=0.5, exploration_vs_goal=0.7,
    ),
    "business": ContextVector(
        individual_vs_team=0.6, digital_vs_physical=0.4, people_vs_system=0.5,
        appreciation_vs_creation=0.8, expression_vs_analysis=0.6, exploration_vs_goal=0.8,
    ),
    "making": ContextVector(
        individual_vs_team=0.4, digital_vs_physical=0.5, people_vs_system=0.8,
        appreciation_vs_creation=0.9, expression_vs_analysis=0.7, exploration_vs_goal=0.6,
    ),
    "volunteer": ContextVector(
        individual_vs_team=0.7, digital_vs_physical=0.8, people_vs_system=0.1,
        appreciation_vs_creation=0.6, expression_vs_analysis=0.2, exploration_vs_goal=0.5,
    ),
    "sports": ContextVector(
        individual_vs_team=0.5, digital_vs_physical=0.9, people_vs_system=0.5,
        appreciation_vs_creation=0.7, expression_vs_analysis=0.6, exploration_vs_goal=0.8,
    ),
    "science": ContextVector(
        individual_vs_team=0.3, digital_vs_physical=0.6, people_vs_system=0.9,
        appreciation_vs_creation=0.5, expression_vs_analysis=0.9, exploration_vs_goal=0.3,
    ),
    "writing": ContextVector(
        individual_vs_team=0.15, digital_vs_physical=0.3, people_vs_system=0.3,
        appreciation_vs_creation=0.5, expression_vs_analysis=0.2, exploration_vs_goal=0.2,
    ),
    "art_design": ContextVector(
        individual_vs_team=0.2, digital_vs_physical=0.4, people_vs_system=0.4,
        appreciation_vs_creation=0.85, expression_vs_analysis=0.15, exploration_vs_goal=0.25,
    ),
    "travel": ContextVector(
        individual_vs_team=0.5, digital_vs_physical=0.85, people_vs_system=0.25,
        appreciation_vs_creation=0.25, expression_vs_analysis=0.5, exploration_vs_goal=0.2,
    ),
    "cooking": ContextVector(
        individual_vs_team=0.25, digital_vs_physical=0.9, people_vs_system=0.6,
        appreciation_vs_creation=0.85, expression_vs_analysis=0.55, exploration_vs_goal=0.4,
    ),
    "fashion_beauty": ContextVector(
        individual_vs_team=0.2, digital_vs_physical=0.7, people_vs_system=0.2,
        appreciation_vs_creation=0.7, expression_vs_analysis=0.1, exploration_vs_goal=0.3,
    ),
    "history_humanities": ContextVector(
        individual_vs_team=0.15, digital_vs_physical=0.3, people_vs_system=0.25,
        appreciation_vs_creation=0.2, expression_vs_analysis=0.75, exploration_vs_goal=0.25,
    ),
    "law_politics": ContextVector(
        individual_vs_team=0.5, digital_vs_physical=0.35, people_vs_system=0.7,
        appreciation_vs_creation=0.3, expression_vs_analysis=0.85, exploration_vs_goal=0.6,
    ),
}
