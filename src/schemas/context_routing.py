"""Context Routing Question Schema — 2026-08-23 Trait Ontology v2(2.5단계) §4/§5.

Context 선택·하위 관심 선택은 "학생이 이해하기 쉬운 질문 배경을 결정"할 뿐 Trait
점수에 직접 반영하지 않는다(§2 아키텍처 불변식) — 그래서 Routing Question의 5개
선택지는 전부 `primary_trait_delta={}`로 강제한다(공개 `FinalizedQuestion`/
`FinalizedOption` 타입을 그대로 재사용해 B가 기존과 동일하게 렌더링할 수 있게 하되,
Trait Signal은 애초에 만들 수 없는 구조로 만든다). 각 선택지는 대신 `context_anchor`
(예: "strategy_puzzle")만 가리킨다 — 이후 같은 Context의 Direct Probe/Tail 질문
문구를 조절하는 재료로만 쓴다(§6/§7)."""

from __future__ import annotations

from pydantic import BaseModel, model_validator

from src.schemas.question import FinalizedQuestion


class ContextRoutingBlueprintValidationError(ValueError):
    """Routing Blueprint 자체의 Cross-field 정합성이 깨졌을 때."""


class ContextRoutingOptionMapping(BaseModel):
    role_id: str
    context_anchor: str
    anchor_label: str


class ContextRoutingBlueprint(BaseModel):
    context_id: str
    blueprint_id: str
    option_mappings: list[ContextRoutingOptionMapping]
    base_question: FinalizedQuestion

    def anchor_for_role(self, role_id: str) -> str:
        for mapping in self.option_mappings:
            if mapping.role_id == role_id:
                return mapping.context_anchor
        raise KeyError(f"role_id {role_id!r} not found in routing blueprint {self.blueprint_id!r}")

    @model_validator(mode="after")
    def _cross_field_consistency(self) -> "ContextRoutingBlueprint":
        if len(self.option_mappings) != 5:
            raise ContextRoutingBlueprintValidationError(
                f"{self.blueprint_id}: option_mappings는 정확히 5개여야 한다(got {len(self.option_mappings)})"
            )
        mapping_role_ids = [m.role_id for m in self.option_mappings]
        if len(set(mapping_role_ids)) != len(mapping_role_ids):
            raise ContextRoutingBlueprintValidationError(f"{self.blueprint_id}: role_id가 서로 달라야 한다")

        anchors = [m.context_anchor for m in self.option_mappings]
        if len(set(anchors)) != len(anchors):
            raise ContextRoutingBlueprintValidationError(f"{self.blueprint_id}: context_anchor가 서로 달라야 한다")

        if self.base_question.context != self.context_id:
            raise ContextRoutingBlueprintValidationError(
                f"{self.blueprint_id}: base_question.context {self.base_question.context!r} != "
                f"context_id {self.context_id!r}"
            )
        option_role_ids = [o.role_id for o in self.base_question.options]
        if mapping_role_ids != option_role_ids:
            raise ContextRoutingBlueprintValidationError(
                f"{self.blueprint_id}: option_mappings 순서 {mapping_role_ids} != "
                f"base_question Option 순서 {option_role_ids}"
            )
        # §2 핵심 불변식: Routing Option은 어떤 Trait에도 점수를 주지 않는다.
        for option in self.base_question.options:
            if option.primary_trait_delta:
                raise ContextRoutingBlueprintValidationError(
                    f"{self.blueprint_id}/{option.role_id}: Routing Option의 primary_trait_delta는 "
                    f"항상 빈 dict여야 한다(got {option.primary_trait_delta}) — Context Routing은 "
                    "Trait 점수에 반영되지 않는다"
                )
        if self.base_question.target_traits:
            raise ContextRoutingBlueprintValidationError(
                f"{self.blueprint_id}: base_question.target_traits는 비어 있어야 한다"
            )
        return self
