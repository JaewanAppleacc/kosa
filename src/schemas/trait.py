"""Trait Definition — 설계안 §6-3 TraitDefinition 스키마 그대로 구현."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from src.ids import is_valid_slug

TraitScope = Literal["shared", "domain_specific"]
VectorGroup = Literal["interest", "cognitive", "work_style", "environment"]
# 2026-08-22 12차 리뷰: source_references는 자유 텍스트라 "강함/보통/팀 정의"를 사람이
# 매번 다시 읽어야 했다 — grounding_type으로 기계가 검사할 수 있는 값을 따로 둔다.
# ONET_STRONG: 공식 정의문까지 직접 대조 확인. ONET_PARTIAL: 항목명은 확인했지만 정의문은
# 구버전 인용이거나 미확인. RIASEC_REFERENCE: Holland 유형 설명 수준(항목 단위 대응 아님).
# TEAM_DEFINED: O*NET/Holland 공식 대응 항목을 찾지 못해 팀이 직접 정의(발표에서 O*NET
# 근거라고 과장하지 않는다).
GroundingType = Literal["ONET_STRONG", "ONET_PARTIAL", "RIASEC_REFERENCE", "TEAM_DEFINED"]


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
    # 기본값 TEAM_DEFINED — 가장 보수적인 값("공식 근거를 확인하지 않았다면 팀 정의로
    # 취급")이라, 이 필드를 모르는 기존 테스트 Fixture(tests/test_*.py의 손으로 만든
    # TraitDefinition)가 실수로 더 강한 근거를 주장하게 되지 않는다.
    grounding_type: GroundingType = "TEAM_DEFINED"
    # 2026-08-23 Trait Ontology v2(1단계, Shadow Mode) 추가 필드 — 전부 기본값을 둬서
    # 기존 12개 Trait(VERTICAL_SLICE_TRAITS)를 만드는 코드를 하나도 안 고쳐도 된다.
    # neighboring_trait_ids/distinction_notes는 새 24개 Trait가 의미상 겹치는 이웃
    # Trait와 실제로 어떻게 다른지 명시하기 위한 것이다("두 Trait가 뭐가 다른가"를
    # 문서로 남기지 않으면 나중에 누구도 구분 못 하고 하나로 합쳐버리기 쉽다).
    # 1.5단계 §6: mutable default([]) 대신 default_factory로 인스턴스마다 새 list를 만든다.
    neighboring_trait_ids: list[str] = Field(default_factory=list)
    distinction_notes: str = ""
    # 이 Trait 정의 자체가 2인 교차검토를 거쳤는지 — Major/Subject Mapping의
    # review_status와 같은 의미(draft=아직 검토 전, team_reviewed=검토 완료).
    review_status: Literal["draft", "team_reviewed"] = "draft"

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
