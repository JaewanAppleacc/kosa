"""Context–Trait Coverage Matrix — 설계안 §6-5, 1차 초안(DRAFT, 2인 교차검토 전).

15개 Context × Vertical Slice 12개 Trait의 관찰 가능 등급(0~3). game/media/school_life
3개는 outputs/trait_ontology_draft.md §4 "3-Context 예비 관찰 가능성 체크"에서 이미
팀이 채운 값을 그대로 옮겼다(새로 판단하지 않음 — 기존 문서와 불일치가 생기지 않게).
나머지 12개 Context는 이번에 Context 설명(context_definitions.py)을 근거로 새로 채웠다.

Contrast Context Selector(§5-1)의 coverage_gain 계산에 쓴다. Trait를 확장(12→20~30개)할
때 이 Matrix도 함께 확장해야 한다.
"""

from __future__ import annotations

# 열 순서: causal_analysis, pattern_finding, planning, immediate_execution,
# change_adaptation, collaboration_preference, opinion_mediation, emotional_interpretation,
# audience_response_prediction, visual_expression, information_comparison, tool_utilization
_TRAIT_ORDER: list[str] = [
    "causal_analysis", "pattern_finding", "planning", "immediate_execution",
    "change_adaptation", "collaboration_preference", "opinion_mediation",
    "emotional_interpretation", "audience_response_prediction", "visual_expression",
    "information_comparison", "tool_utilization",
]

_RAW_GRADES: dict[str, list[int]] = {
    #                          원인 패턴 계획 즉시 변화 협업 의견 감정 반응 시각 정보 도구
    "game":               [3, 3, 2, 3, 3, 2, 2, 1, 1, 1, 3, 2],
    "media":              [2, 2, 2, 2, 2, 1, 1, 3, 3, 3, 2, 2],
    "school_life":        [3, 2, 3, 1, 2, 3, 3, 2, 2, 1, 2, 1],
    "business":           [3, 2, 3, 2, 2, 2, 2, 1, 3, 1, 3, 1],
    "making":             [3, 2, 2, 3, 2, 1, 0, 0, 1, 1, 2, 3],
    "volunteer":          [1, 0, 2, 1, 1, 3, 2, 3, 2, 0, 1, 0],
    "sports":             [2, 2, 2, 2, 2, 2, 1, 1, 0, 0, 1, 2],
    "science":            [3, 3, 2, 1, 1, 1, 0, 0, 0, 0, 2, 2],
    "writing":            [1, 1, 1, 0, 0, 1, 1, 2, 2, 0, 1, 0],
    "art_design":         [0, 1, 1, 1, 1, 0, 0, 1, 2, 3, 1, 2],
    "travel":             [0, 0, 3, 1, 2, 1, 0, 1, 0, 0, 3, 0],
    "cooking":            [2, 1, 2, 2, 2, 0, 0, 0, 1, 1, 2, 2],
    "fashion_beauty":     [0, 1, 1, 1, 1, 0, 0, 0, 2, 3, 2, 1],
    "history_humanities": [3, 2, 0, 0, 0, 0, 1, 2, 0, 0, 2, 0],
    "law_politics":       [3, 1, 1, 0, 1, 1, 3, 1, 2, 0, 3, 0],
}

CONTEXT_TRAIT_COVERAGE: dict[str, dict[str, int]] = {
    context_id: dict(zip(_TRAIT_ORDER, grades, strict=True))
    for context_id, grades in _RAW_GRADES.items()
}
