"""Trait Vector Snapshot Schema — 2026-08-31 Trait Ontology v2(1단계) §10.

이 단계에서는 기존 Profile·Matching 결과를 바꾸지 않고 이 Snapshot을 Shadow Mode로
병행 계산만 한다 — `tendency_score`는 학생의 능력 점수가 아니라 내부 정규화 상태값이고,
가짜 정밀도(임의의 소수점 네 자리 등)를 만들지 않는다(§10).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

TraitVectorStatus = Literal["NOT_PROBED", "HYPOTHESIS", "LIMITED", "MODERATE", "STRONG", "CONFLICTING"]

# §10: "현재 검증 데이터가 없으므로 임의의 복잡한 수식이나 소수점 네 자리 점수를 만들지
# 말고, 초기에는 다음과 같은 설명 가능한 값만 사용한다." — evidence_engine.trait_normalizer
# 의 등급 값과 동일한 스케일을 그대로 재사용한다(새 정규화 정책을 만들지 않는다).
TENDENCY_SCORE_BY_STATUS: dict[str, float | None] = {
    "NOT_PROBED": None,
    "HYPOTHESIS": None,
    "LIMITED": 0.33,
    "MODERATE": 0.67,
    "STRONG": 1.00,
    "CONFLICTING": None,
}


class TraitVectorEntry(BaseModel):
    trait_id: str
    primary_signal_sum: float
    related_signal_sum: float
    confirmed_related_signal_sum: float
    primary_evidence_count: int
    related_evidence_count: int
    context_count: int
    frame_count: int
    question_count: int
    tendency_score: float | None
    # "왜 이 status가 됐는가"를 사람이 읽을 수 있게 남기는 짧은 사유 — status와는 다른
    # 축이다(status는 상태 자체, evidence_confidence는 그 상태에 도달한 근거의 성격).
    evidence_confidence: Literal[
        "primary_evidence", "promoted_related_signal", "unconfirmed_related_signal",
        "no_evidence", "explicit_conflict",
    ]
    status: TraitVectorStatus
