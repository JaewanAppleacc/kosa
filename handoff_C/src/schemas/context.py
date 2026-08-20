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
