"""Sparse Trait Signal Schema — 2026-08-23 Trait Ontology v2(1.5단계) §2/§4/§6.

답변 하나가 24개 Trait 전부에 점수를 주는 Dense Vector 방식은 금지한다(1단계 지시서 §4) —
선택지 하나는 관련 있는 소수 Trait에만 Signal을 발생시킨다. 이 파일은 Signal 하나의
형태(`TraitSignal`)와, 그 Signal을 실제로 어떤 질문 계열·Blueprint·Role에서 조회했는지를
가리키는 복합 Key(`TraitSignalRegistryKey`), 그리고 조회 결과(`TraitSignalResolution`)를
정의한다 — "선택지 하나에 몇 개까지 허용되는가" 같은 목록 단위 검증은
`src/services/trait_signal_registry.py::validate_role_signals()`가 한다(이 Schema는
그 검증에 필요한 Cross-Reference 정보, 즉 Ontology·Related Concept 전체 목록을 모르기
때문이다 — 순수 Pydantic 필드 검증만 여기서 한다).

1.5단계 §6 안정성 수정: `TraitSignal`은 `frozen=True`로 고정한다 — Registry가 반환한
Signal을 호출자가 실수로(또는 악의적으로) 고쳐도 정본 Registry가 오염되지 않는다. 다만
`related_concept_ids`는 list 필드라 frozen만으로는 in-place mutation(`.append()`)까지
막지 못한다 — Registry 쪽(`resolve_trait_signals`)이 반환 직전 `model_copy(deep=True)`로
방어적 복사본을 만들어 이 문제를 마저 막는다(frozen + deep copy 이중 방어).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SignalRole = Literal["PRIMARY", "RELATED"]

# 1단계 §4 "초기 허용 가중치": PRIMARY는 항상 1.0, RELATED는 0.33 또는 0.67만 허용한다.
# LLM이 weight를 결정하는 구조를 막기 위해 이 상수 밖의 값은 전부 거부한다(가짜 정밀도
# 방지 — 임의의 0.4123 같은 값을 허용하지 않는다).
PRIMARY_WEIGHT = 1.0
ALLOWED_RELATED_WEIGHTS = frozenset({0.33, 0.67})


class TraitSignal(BaseModel):
    model_config = ConfigDict(frozen=True)

    trait_id: str
    signal_role: SignalRole
    weight: float
    related_concept_ids: list[str] = Field(default_factory=list)

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


# 질문 계열 — Conflict Resolution은 이 Registry에 아예 등록하지 않는다(항상
# NONE_CONFLICT_RESOLUTION으로 조회된다), 그래서 여기 나열하지 않는다.
# 2026-08-24 2단계 §8: "v2_direct_probe"를 추가한다 — 신규 Trait Direct Probe 질문
# 전용 계열이다. 이 값은 서버 내부 Registry Key에서만 쓰이고 API에는 노출하지 않는다.
QuestionFamilyId = Literal["seed", "tail_blueprint", "backup", "mock_placeholder", "v2_direct_probe"]


class TraitSignalRegistryKey(BaseModel):
    """1.5단계 §2: role_id 단독 조회는 같은 role_id가 서로 다른 질문 계열·Blueprint에서
    재사용될 때 다른 Signal Mapping을 표현할 수 없다는 문제가 있었다(예: "team_coordination"이
    Tail Blueprint와 Seed 양쪽에 등장). 이 복합 Key는 (질문 계열, Blueprint, Role) 세 값을
    모두 구분해서, 같은 role_id라도 서로 다른 Blueprint에 속하면 완전히 다른 등록으로
    취급한다 — 우연히 같은 값이 나오는 것과 구조적으로 같은 Key인 것을 더 이상 혼동하지
    않는다."""

    model_config = ConfigDict(frozen=True)

    question_family_id: QuestionFamilyId
    blueprint_id: str
    role_id: str


MappingSource = Literal["EXACT_BLUEPRINT", "LEGACY_PRIMARY_ADAPTER", "NONE_CONFLICT_RESOLUTION"]


class TraitSignalResolution(BaseModel):
    """`resolve_trait_signals()`의 반환값. `mapping_source`로 이 Signal이 사람이 직접
    검토한 Registry 값인지(EXACT_BLUEPRINT), 아직 Registry에 없어 기존 legacy
    `primary_trait_delta`를 그대로 옮긴 것인지(LEGACY_PRIMARY_ADAPTER), Conflict
    Resolution 질문이라 아예 비운 것인지(NONE_CONFLICT_RESOLUTION)를 구분한다 — "정상
    질문인데 signals=[]로 조용히 끝나는 경로"를 없애는 게 목적이라, 정상 질문은
    EXACT_BLUEPRINT 또는 LEGACY_PRIMARY_ADAPTER 둘 중 하나로 반드시 PRIMARY Signal을
    최소 1개 갖는다."""

    signals: list[TraitSignal] = Field(default_factory=list)
    mapping_source: MappingSource
