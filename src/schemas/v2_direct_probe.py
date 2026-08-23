"""V2 Direct Probe Blueprint Schema — 2026-08-24 Trait Ontology v2(2단계) §5.

신규 Trait를 직접 관찰하기 위한 Blueprint다. 기존 `OptionBlueprint`/`OptionRole`
(Tail Blueprint와 동일한 타입)를 그대로 재사용한다 — 새 Question/Option 타입을 만들지
않고, `FinalizedQuestion`/`finalize_question()` 등 기존 §9/§10 파이프라인을 그대로
탄다(공개 API Schema를 바꾸지 않기 위한 선택이기도 하다, §19). `base_question`은 사람이
직접 검토한 완성된 `FinalizedQuestion`이며, LLM이 꺼져 있거나 재생성이 전부 실패했을 때
그대로 쓰는 Fallback이기도 하다(Legacy Seed Question과 같은 역할 — "구조도 실제, 문구도
실제"인 항상 동작하는 기준값)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator

from src.schemas.question import FinalizedQuestion, OptionBlueprint


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
