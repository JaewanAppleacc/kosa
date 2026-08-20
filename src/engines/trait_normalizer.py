"""trait_normalizer.py — 설계안 §15, §16, §20 / A 지시서 §3 "Student·Major·Course에
동일한 정규화 정책을 적용한다"의 실제 구현.

등급(0~3)을 0 / 0.33 / 0.67 / 1.00으로 변환한다. Major/Subject Profile과 Student
Trait 상태 모두 이 함수 하나로 정규화해서, 세 곳에서 각자 다른 스케일을 쓰는 사고를 막는다.
"""

from __future__ import annotations

from src.schemas.evidence import TraitState

_GRADE_TO_VALUE: dict[int, float] = {0: 0.00, 1: 0.33, 2: 0.67, 3: 1.00}

_STATE_TO_VALUE: dict[TraitState, float | None] = {
    TraitState.STRONG: 1.00,
    TraitState.MODERATE: 0.67,
    TraitState.LIMITED: 0.33,
    TraitState.INSUFFICIENT: None,  # Mask
    TraitState.CONFLICTING: None,  # Mask
}


def normalize_grade(grade: int) -> float:
    """Major/Subject Profile 작성 시 0~3 등급을 0/.33/.67/1.00으로 변환한다 (§15, §20)."""
    if grade not in _GRADE_TO_VALUE:
        raise ValueError(f"grade must be 0~3, got {grade}")
    return _GRADE_TO_VALUE[grade]


def normalize_trait_state(state: TraitState) -> float | None:
    """Student Trait 상태를 매칭용 내부 값으로 변환한다 (§13). None은 Mask(분모 제외)를 뜻한다."""
    return _STATE_TO_VALUE[state]
