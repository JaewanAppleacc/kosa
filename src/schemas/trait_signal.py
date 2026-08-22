"""Sparse Trait Signal Schema — 2026-08-31 Trait Ontology v2(1단계) §4.

답변 하나가 24개 Trait 전부에 점수를 주는 Dense Vector 방식은 금지한다(지시서 §4) —
선택지 하나는 관련 있는 소수 Trait에만 Signal을 발생시킨다. 이 파일은 Signal 하나의
형태만 정의한다 — "선택지 하나에 몇 개까지 허용되는가" 같은 목록 단위 검증은
`src/services/trait_signal_registry.py::validate_role_signals()`가 한다(이 Schema는
그 검증에 필요한 Cross-Reference 정보, 즉 Ontology·Related Concept 전체 목록을 모르기
때문이다 — 순수 Pydantic 필드 검증만 여기서 한다).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, model_validator

SignalRole = Literal["PRIMARY", "RELATED"]

# 지시서 §4 "초기 허용 가중치": PRIMARY는 항상 1.0, RELATED는 0.33 또는 0.67만 허용한다.
# LLM이 weight를 결정하는 구조를 막기 위해 이 상수 밖의 값은 전부 거부한다(가짜 정밀도
# 방지 — 임의의 0.4123 같은 값을 허용하지 않는다).
PRIMARY_WEIGHT = 1.0
ALLOWED_RELATED_WEIGHTS = frozenset({0.33, 0.67})


class TraitSignal(BaseModel):
    trait_id: str
    signal_role: SignalRole
    weight: float
    related_concept_ids: list[str] = []

    @model_validator(mode="after")
    def _weight_matches_role(self) -> "TraitSignal":
        if self.signal_role == "PRIMARY" and self.weight != PRIMARY_WEIGHT:
            raise ValueError(
                f"{self.trait_id}: PRIMARY Signal의 weight는 반드시 {PRIMARY_WEIGHT}여야 한다"
                f"(got {self.weight!r}) — LLM이나 임의 계산이 weight를 정하지 않는다"
            )
        if self.signal_role == "RELATED" and self.weight not in ALLOWED_RELATED_WEIGHTS:
            raise ValueError(
                f"{self.trait_id}: RELATED Signal의 weight는 {sorted(ALLOWED_RELATED_WEIGHTS)} "
                f"중 하나여야 한다(got {self.weight!r})"
            )
        return self
