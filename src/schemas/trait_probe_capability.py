"""Trait Probe Capability Schema — 2026-08-23 Trait Ontology v2(1.5단계) §7.

1단계는 "서로 다른 role_id 2개 ≈ 서로 다른 질문 2개 ≈ 서로 다른 Frame 또는 Context"라는
가정으로 `VERTICAL_SLICE_ACTIVE_TRAIT_IDS`를 계산했다 — 이 가정은 성립하지 않는다(같은
Blueprint 안에서 role_id가 2개 다르다고 서로 다른 Frame·Context가 보장되지 않는다). 이
Schema는 Trait별로 Blueprint·Context·Frame 각각을 독립적으로, 실제 구조에서 명시적으로
계산한 결과를 담는다."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TraitProbeCapability(BaseModel):
    trait_id: str
    blueprint_ids: set[str] = Field(default_factory=set)
    context_ids: set[str] = Field(default_factory=set)
    frame_ids: set[str] = Field(default_factory=set)
    primary_probe_count: int = 0
    related_probe_count: int = 0
