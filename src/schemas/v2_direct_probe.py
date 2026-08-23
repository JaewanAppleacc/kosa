"""V2 Direct Probe Blueprint Schema — 2026-08-23 Trait Ontology v2(2단계 §5, 2.1단계 §6).

신규 Trait를 직접 관찰하기 위한 Blueprint다. 기존 `OptionBlueprint`/`OptionRole`
(Tail Blueprint와 동일한 타입)를 그대로 재사용한다 — 새 Question/Option 타입을 만들지
않고, `FinalizedQuestion`/`finalize_question()` 등 기존 §9/§10 파이프라인을 그대로
탄다(공개 API Schema를 바꾸지 않기 위한 선택이기도 하다, §19). `base_question`은 사람이
직접 검토한 완성된 `FinalizedQuestion`이며, LLM이 꺼져 있거나 재생성이 전부 실패했을 때
그대로 쓰는 Fallback이기도 하다(Legacy Seed Question과 같은 역할 — "구조도 실제, 문구도
실제"인 항상 동작하는 기준값).

2.1단계 §6: Blueprint와 고정(base) 질문 사이의 Mapping 불일치를 Import 시점에
Fail-Fast로 잡는다(조용한 덮어쓰기 금지) — `model_validator`가 여기서 다루는 항목은
이 Blueprint 하나만으로 검증 가능한 것들이다. Core Trait Ontology 존재 여부·전역
blueprint_id/question_id 중복은 다른 Blueprint·외부 Ontology와 비교해야 하므로
`src/data/questions/trait_v2_direct_probe_blueprints.py` 모듈 로드 시점에 별도로
검사한다(Schema 계층이 서비스 계층을 참조하지 않는다는 기존 원칙을 지키기 위해)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

from src.schemas.question import FinalizedQuestion, OptionBlueprint


class V2DirectProbeBlueprintValidationError(ValueError):
    """Blueprint 자체의 Cross-field 정합성이 깨졌을 때."""


class V2DirectProbeBlueprint(BaseModel):
    trait_id: str
    blueprint: OptionBlueprint
    allowed_context_ids: list[str]
    question_frame_id: str
    purpose: str
    base_question: FinalizedQuestion
    review_status: Literal["draft", "team_reviewed"] = "draft"

    @field_validator("allowed_context_ids")
    @classmethod
    def _not_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("allowed_context_ids must not be empty")
        return value

    @model_validator(mode="after")
    def _cross_field_consistency(self) -> "V2DirectProbeBlueprint":
        # base_question.context가 allowed_context_ids에 포함돼야 한다.
        if self.base_question.context not in self.allowed_context_ids:
            raise V2DirectProbeBlueprintValidationError(
                f"{self.blueprint.blueprint_id}: base_question.context "
                f"{self.base_question.context!r}가 allowed_context_ids {self.allowed_context_ids}에 없다"
            )
        # base_question.frame_id == question_frame_id.
        if self.base_question.frame_id != self.question_frame_id:
            raise V2DirectProbeBlueprintValidationError(
                f"{self.blueprint.blueprint_id}: base_question.frame_id "
                f"{self.base_question.frame_id!r} != question_frame_id {self.question_frame_id!r}"
            )

        blueprint_role_ids = [r.role_id for r in self.blueprint.roles]
        option_role_ids = [o.role_id for o in self.base_question.options]
        # Role ID 집합과 순서가 정확히 일치해야 한다.
        if blueprint_role_ids != option_role_ids:
            raise V2DirectProbeBlueprintValidationError(
                f"{self.blueprint.blueprint_id}: Blueprint Role 순서 {blueprint_role_ids} != "
                f"Base Question Option 순서 {option_role_ids}"
            )
        # 각 Role의 primary_trait_delta가 대응하는 Base Question Option과 정확히 일치해야 한다.
        options_by_role = {o.role_id: o for o in self.base_question.options}
        for role in self.blueprint.roles:
            option = options_by_role[role.role_id]
            if role.primary_trait_delta != option.primary_trait_delta:
                raise V2DirectProbeBlueprintValidationError(
                    f"{self.blueprint.blueprint_id}/{role.role_id}: Blueprint primary_trait_delta "
                    f"{role.primary_trait_delta} != Base Question Option primary_trait_delta "
                    f"{option.primary_trait_delta}"
                )

        # Target Trait를 PRIMARY로 갖는 Option이 정확히 1개여야 한다.
        target_roles = [r for r in self.blueprint.roles if self.trait_id in r.primary_trait_delta]
        if len(target_roles) != 1:
            raise V2DirectProbeBlueprintValidationError(
                f"{self.blueprint.blueprint_id}: Target Trait {self.trait_id!r}를 PRIMARY로 갖는 "
                f"Option이 {len(target_roles)}개다(정확히 1개여야 함)"
            )

        # base_question.target_traits는 공개 응답에서 이 Blueprint의 정체를 드러내는 데
        # 쓰이면 안 된다 — Direct Probe 질문은 항상 빈 리스트를 유지한다(§19 API 불변).
        if self.base_question.target_traits:
            raise V2DirectProbeBlueprintValidationError(
                f"{self.blueprint.blueprint_id}: base_question.target_traits는 비어 있어야 한다"
                f"(Direct Probe는 공개 응답에 Target Trait를 노출하지 않는다), got "
                f"{self.base_question.target_traits}"
            )
        return self
