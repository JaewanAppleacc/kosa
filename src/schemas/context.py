"""Context Definition — 설계안 §6-6 Context Definition Table의 코드 표현."""

from __future__ import annotations

from pydantic import BaseModel, field_validator

from src.ids import is_valid_slug


class ContextDefinition(BaseModel):
    context_id: str
    label: str
    description: str
    example_activities: list[str]
    is_core: bool
    interest_rating_prompt: str

    @field_validator("context_id")
    @classmethod
    def _validate_context_id(cls, value: str) -> str:
        if not is_valid_slug(value):
            raise ValueError(f"context_id must be snake_case slug, got: {value!r}")
        return value

    @field_validator("example_activities")
    @classmethod
    def _validate_example_activities(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("example_activities must not be empty")
        return value


class ContextVector(BaseModel):
    """§6-5 "팀이 검토한 활동 축" — Contrast Context 거리 계산에 쓰는 6개 축. 각 값은
    0.0(왼쪽 극)~1.0(오른쪽 극) 사이다. 단어 임베딩이 아니라 사람이 판단한 값이라는 게
    설계안의 핵심 요구사항이다."""

    individual_vs_team: float  # 0=개인 활동, 1=팀 활동
    digital_vs_physical: float  # 0=디지털, 1=신체·현장
    people_vs_system: float  # 0=사람 중심, 1=시스템 중심
    appreciation_vs_creation: float  # 0=감상, 1=직접 제작
    expression_vs_analysis: float  # 0=표현 중심, 1=분석 중심
    exploration_vs_goal: float  # 0=자유 탐색, 1=규칙·목표 중심

    @field_validator(
        "individual_vs_team",
        "digital_vs_physical",
        "people_vs_system",
        "appreciation_vs_creation",
        "expression_vs_analysis",
        "exploration_vs_goal",
    )
    @classmethod
    def _validate_unit_range(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"Context Vector 값은 0.0~1.0 사이여야 한다, got: {value}")
        return value
