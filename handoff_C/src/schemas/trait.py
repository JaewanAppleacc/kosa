"""Trait Definition — 설계안 §6-3 TraitDefinition 스키마 그대로 구현."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator

from src.ids import is_valid_slug

TraitScope = Literal["shared", "domain_specific"]
VectorGroup = Literal["interest", "cognitive", "work_style", "environment"]


class TraitDefinition(BaseModel):
    trait_id: str
    label: str
    parent_dimension: str
    definition: str
    positive_indicators: list[str]
    conflicting_indicators: list[str]
    aliases: list[str] = []
    source_references: list[str]
    trait_scope: TraitScope
    minimum_context_count: int
    primary_vector_group: VectorGroup

    @field_validator("trait_id")
    @classmethod
    def _validate_trait_id(cls, value: str) -> str:
        if not is_valid_slug(value):
            raise ValueError(f"trait_id must be snake_case slug, got: {value!r}")
        return value

    @field_validator("minimum_context_count")
    @classmethod
    def _validate_min_context(cls, value: int) -> int:
        if value < 1:
            raise ValueError("minimum_context_count must be >= 1")
        return value

    @field_validator("source_references")
    @classmethod
    def _validate_source_references(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError(
                "source_references must not be empty — 근거가 없으면 "
                "'팀 정의 — O*NET/Holland 대응 항목 없음' 처럼 명시적으로 적는다"
            )
        return value
