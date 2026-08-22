"""Related Concept Schema — 2026-08-31 Trait Ontology v2(1단계) §3.

Core Trait(24개, `src/schemas/trait.py::TraitDefinition`)와 학생에게 보여주는 세부
표현("감독의 관점에서 보기", "장면 순서를 재구성함" 등)을 분리한다. Related Concept는
설명·질문 설계·Subgraph용이며, Major/Subject Matching의 별도 Vector 차원으로는 절대
쓰지 않는다(지시서 §3) — Matching Edge는 항상 Core Trait 기준이다.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

from src.ids import is_valid_slug

ConceptTraitRelationType = Literal["PRIMARY", "SECONDARY"]


class TraitConceptLink(BaseModel):
    """이 Concept이 어떤 Trait와 어떤 관계로 연결되는지. 하나의 Concept이 여러 Trait와
    연결될 수 있다(§3 "하나의 Concept이 여러 Trait에 연결되는 것은 허용") — 단, 같은
    답변에서 이 Concept을 통해 연결된 Trait Signal을 중복 합산하지 않는 규칙은
    `trait_signal_registry.py`가 담당한다(이 Schema는 정본 연결 정의만 표현한다)."""

    trait_id: str
    relation_type: ConceptTraitRelationType
    explanation: str

    @field_validator("explanation")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("explanation은 비어 있을 수 없다")
        return value


class RelatedConceptDefinition(BaseModel):
    """`related_concepts_v2.jsonl`의 한 행 — 하나의 정본 레코드로 관리하고 여러 Core
    Trait와 연결될 수 있다(§3). 같은 Concept을 여러 Trait 파일에 중복 정의하지 않는다 —
    이 Concept이 정본이고, 각 Trait 쪽에서는 이 concept_id를 참조만 한다."""

    concept_id: str
    label: str
    definition: str
    trait_links: list[TraitConceptLink]
    review_status: Literal["draft", "team_reviewed"] = "draft"

    @field_validator("concept_id")
    @classmethod
    def _validate_concept_id(cls, value: str) -> str:
        if not is_valid_slug(value):
            raise ValueError(f"concept_id must be snake_case slug, got: {value!r}")
        return value

    @field_validator("trait_links")
    @classmethod
    def _not_empty(cls, value: list[TraitConceptLink]) -> list[TraitConceptLink]:
        if not value:
            raise ValueError("trait_links는 비어 있을 수 없다 — 최소 1개 Trait와 연결돼야 한다")
        return value

    @model_validator(mode="after")
    def _no_duplicate_trait_links(self) -> "RelatedConceptDefinition":
        trait_ids = [link.trait_id for link in self.trait_links]
        if len(set(trait_ids)) != len(trait_ids):
            raise ValueError(f"{self.concept_id}: 같은 Trait에 여러 Link를 중복 등록할 수 없다")
        return self
