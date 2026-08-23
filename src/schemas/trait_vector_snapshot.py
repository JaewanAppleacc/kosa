"""Trait Vector Snapshot Schema — 2026-08-23 Trait Ontology v2(1단계) §10.

이 단계에서는 기존 Profile·Matching 결과를 바꾸지 않고 이 Snapshot을 Shadow Mode로
병행 계산만 한다 — `tendency_score`는 학생의 능력 점수가 아니라 내부 정규화 상태값이고,
가짜 정밀도(임의의 소수점 네 자리 등)를 만들지 않는다(§10).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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
    # 2026-08-23 2단계 §10 — Target Trait 질문이 제시된 횟수와, 그중 실제로 Target
    # Signal이 선택된 횟수. `target_signal_selected=False`는 부정 Evidence가 아니다 —
    # "직접 질문했지만 이 답변에서는 확인 안 됨"이라는 사실만 담는다. 기본값 0이라
    # Direct Probe를 모르는 기존 호출자는 이 필드를 몰라도 된다.
    direct_probe_opportunity_count: int = 0
    direct_probe_primary_evidence_count: int = 0
    # 2026-08-23 2단계 후속(2.1단계) §4 — 후보 우선순위는 PRIMARY와 섞이지 않은
    # RELATED 전용 다양성만 봐야 한다(PRIMARY가 섞이면 "이미 Direct Probe로 확인된
    # 것"과 "아직 RELATED뿐인 것"을 같은 지표로 잘못 비교하게 된다). 아래 4개 필드는
    # `context_count`/`frame_count`/`question_count`(PRIMARY+RELATED 합산, 기존 유지)와
    # 별도로 RELATED만 다시 센 값이다 — 전부 내부 진단 전용, API 미노출.
    related_question_count: int = 0
    related_context_count: int = 0
    related_frame_count: int = 0
    related_context_ids: set[str] = Field(default_factory=set)
    v2_direct_primary_evidence_count: int = 0
    # 2026-08-23 Trait Ontology v2(2.6단계) §4 — "추천 근거는 Evidence까지 역추적
    # 가능해야 한다"(CLAUDE.md)를 v2 Profile에서도 만족하기 위한 값. PRIMARY/RELATED
    # Evidence의 evidence_id를 그대로 담는다(중복 없이, 등장 순서 보존) — 원문·점수는
    # 담지 않고 Evidence Ledger를 다시 찾아갈 수 있는 Key만 남긴다.
    supporting_evidence_ids: list[str] = Field(default_factory=list)

    @property
    def evidence_count(self) -> int:
        """§4 — PRIMARY·RELATED Evidence를 합친 총 개수(저장하지 않고 계산한다,
        primary_evidence_count/related_evidence_count의 파생값이라 별도로 들고 다니면
        불일치 위험만 커진다)."""

        return self.primary_evidence_count + self.related_evidence_count

    @property
    def conflict_status(self) -> bool:
        """§4 — tendency_score/evidence_confidence와 분리된 별도 축. `status`가 이미
        "CONFLICTING"을 표현하지만, Profile·Matching 쪽 호출자가 상태 문자열을 직접
        비교하지 않고 의미가 분명한 이름으로 물을 수 있게 한다."""

        return self.status == "CONFLICTING"


class TraitVectorSnapshot(BaseModel):
    """2026-08-23 1.5단계 §9 — 한 세션의 v2 Trait Vector Snapshot 전체를 담아
    `TraitVectorShadowRepository`에 저장하는 단위. `frozen=True`라 저장 후에는 호출자가
    내용을 고칠 수 없다(list/dict 필드가 없어 frozen만으로 완전히 방어된다 — 다만
    Repository 구현체는 그래도 model_copy(deep=True)로 한 번 더 방어한다, 저장소 자체의
    책임과 값 객체의 책임을 분리하기 위해)."""

    model_config = ConfigDict(frozen=True)

    entries: dict[str, TraitVectorEntry] = Field(default_factory=dict)
