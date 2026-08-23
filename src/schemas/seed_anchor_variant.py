"""Seed Anchor Variant Schema — 2026-08-23 Trait Ontology v2(2.5.1단계) §4/§5.

Context Routing의 Anchor 선택이 "최소 첫 번째 후속 질문"(Seed Question, 모든 세션에서
Routing 바로 다음에 항상 나오는 유일한 질문)에는 반드시 반영되도록 만드는 결정론적
장치다 — LLM이 꺼져 있어도(§5) 동작해야 한다.

`SeedAnchorVariant`는 Seed Question의 문구만 Anchor에 맞게 다시 쓴 것이지, Trait
Mapping을 새로 만든 게 아니다 — `option_text_by_role_id`의 Key는 항상 그 Context의
실제 Seed Question(`VERTICAL_SLICE_SEED_QUESTIONS`)이 이미 갖고 있는 role_id와 정확히
같아야 하고, `role_id → primary_trait_delta` 매핑 자체는 그대로 원본 SeedQuestion이
소유한다(§2 "Trait Mapping은 기존 Blueprint가 소유")."""

from __future__ import annotations

from pydantic import BaseModel


class SeedAnchorVariantError(ValueError):
    """Variant 정본 파일 자체가 구조적으로 잘못됐을 때(중복 Key, Seed Question의
    role_id 집합과 불일치, 등록되지 않은 Anchor Presentation 참조)."""


class SeedAnchorVariant(BaseModel):
    context_id: str
    anchor_id: str
    question_text: str
    option_text_by_role_id: dict[str, str]
