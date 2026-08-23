"""V2 Direct Probe Blueprint Schema — 2026-08-23 Trait Ontology v2(2단계 §5, 2.1단계 §6,
2.2단계 §4/§5).

신규 Trait를 직접 관찰하기 위한 Blueprint다. `base_question`은 사람이 직접 검토한 완성된
`FinalizedQuestion`이며, LLM이 꺼져 있거나 재생성이 전부 실패했을 때 그대로 쓰는
Fallback이기도 하다(Legacy Seed Question과 같은 역할).

2.2단계 §4/§5: 기존에는 이 Blueprint가 `OptionBlueprint`/`OptionRole`(Tail Blueprint와
동일한 타입)을 그대로 재사용했다. `OptionRole`은 "모든 Role은 Primary Trait를 가져야
한다"는 Legacy 규칙(`primary_trait_delta` 비어있으면 거부)을 강제하는데, 이 규칙은 Legacy
Tail Blueprint에는 여전히 맞지만(약화하지 않는다) Direct Probe에는 맞지 않는 경우가
있다는 게 2.2단계 감사 결과다 — 의미가 불명확한 비Target 선택지를 억지로 다른 Trait에
매핑하지 않고 "NO_SIGNAL"로 정직하게 표시해야 한다. 그래서 Direct Probe는 이제
`OptionBlueprint`를 전혀 쓰지 않고 이 파일의 `V2ProbeOptionMapping`(NO_SIGNAL 허용)을
정본으로 쓴다 — Legacy `OptionRole`/`OptionBlueprint`는 이 변경으로 전혀 손대지 않는다
(Tail Blueprint가 계속 그 타입을 그대로 쓴다).

Core Trait Ontology 존재 여부·전역 blueprint_id/question_id 중복은 다른 Blueprint·외부
Ontology와 비교해야 하므로 `src/data/questions/trait_v2_direct_probe_blueprints.py` 모듈
로드 시점에 별도로 검사한다(Schema 계층이 서비스 계층을 참조하지 않는다는 기존 원칙을
지키기 위해)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from src.ids import generate_option_id
from src.schemas.question import FinalizedOption, FinalizedQuestion, GeneratedQuestion
from src.schemas.trait_signal import TraitSignal


class V2DirectProbeBlueprintValidationError(ValueError):
    """Blueprint 자체의 Cross-field 정합성이 깨졌을 때."""


class V2ProbeOptionMapping(BaseModel):
    """2.2단계 §4 — Direct Probe 전용 Role→Trait 대응. `mapping_type`으로 "이 Role이
    Target/다른 Core Trait를 직접 나타낸다"(TRAIT_SIGNAL)와 "이번 질문에서는 특정 Core
    Trait를 직접 확인할 만큼 근거가 명확하지 않다"(NO_SIGNAL)를 명시적으로 구분한다.
    NO_SIGNAL은 낮은 Trait·능력 부족·반대 Trait·부정 Evidence·0점 중 어떤 것도 의미하지
    않는다 — 그냥 "이 선택지에서는 판단하지 않는다"는 뜻이다."""

    role_id: str
    mapping_type: Literal["TRAIT_SIGNAL", "NO_SIGNAL"]
    # 2.3단계 §1: Pydantic v2는 bare list/dict/set 기본값도 인스턴스마다 독립적으로
    # 복사한다(공유 객체 버그가 실제로 발생하지 않는다 — 테스트로 확인). 그래도
    # `default_factory`가 관례적으로 더 명확하므로 통일한다.
    trait_signals: list[TraitSignal] = Field(default_factory=list)
    no_signal_reason: str | None = None

    @model_validator(mode="after")
    def _consistency(self) -> "V2ProbeOptionMapping":
        if self.mapping_type == "TRAIT_SIGNAL":
            if not self.trait_signals:
                raise V2DirectProbeBlueprintValidationError(
                    f"{self.role_id}: TRAIT_SIGNAL Role은 Signal이 최소 1개 필요하다"
                )
            if not any(s.signal_role == "PRIMARY" for s in self.trait_signals):
                raise V2DirectProbeBlueprintValidationError(
                    f"{self.role_id}: TRAIT_SIGNAL Role은 PRIMARY Signal이 최소 1개 필요하다"
                )
            if self.no_signal_reason is not None:
                raise V2DirectProbeBlueprintValidationError(
                    f"{self.role_id}: TRAIT_SIGNAL Role에는 no_signal_reason을 두지 않는다"
                )
        else:  # NO_SIGNAL
            if self.trait_signals:
                raise V2DirectProbeBlueprintValidationError(
                    f"{self.role_id}: NO_SIGNAL Role은 trait_signals가 비어 있어야 한다 "
                    "(Counter/Negative Signal을 만들지 않는다)"
                )
            if not self.no_signal_reason or not self.no_signal_reason.strip():
                raise V2DirectProbeBlueprintValidationError(
                    f"{self.role_id}: NO_SIGNAL Role은 no_signal_reason이 필수다"
                )
        return self

    @property
    def primary_trait_id(self) -> str | None:
        for signal in self.trait_signals:
            if signal.signal_role == "PRIMARY":
                return signal.trait_id
        return None


class V2DirectProbeBlueprint(BaseModel):
    trait_id: str
    blueprint_id: str
    option_mappings: list[V2ProbeOptionMapping]
    allowed_context_ids: list[str]
    question_frame_id: str
    purpose: str
    base_question: FinalizedQuestion
    # 2.5.5단계: 단일 검토자 정책 전환으로 "team_reviewed" 대신 "approved"를 쓴다.
    review_status: Literal["draft", "approved"] = "draft"

    @field_validator("allowed_context_ids")
    @classmethod
    def _not_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("allowed_context_ids must not be empty")
        return value

    def mapping_by_role(self, role_id: str) -> V2ProbeOptionMapping:
        for mapping in self.option_mappings:
            if mapping.role_id == role_id:
                return mapping
        raise KeyError(f"role_id {role_id!r} not found in blueprint {self.blueprint_id!r}")

    @model_validator(mode="after")
    def _cross_field_consistency(self) -> "V2DirectProbeBlueprint":
        if len(self.option_mappings) != 5:
            raise V2DirectProbeBlueprintValidationError(
                f"{self.blueprint_id}: option_mappings는 정확히 5개여야 한다(got {len(self.option_mappings)})"
            )
        mapping_role_ids = [m.role_id for m in self.option_mappings]
        if len(set(mapping_role_ids)) != len(mapping_role_ids):
            raise V2DirectProbeBlueprintValidationError(
                f"{self.blueprint_id}: option_mappings의 role_id가 서로 달라야 한다"
            )

        # base_question.context가 allowed_context_ids에 포함돼야 한다.
        if self.base_question.context not in self.allowed_context_ids:
            raise V2DirectProbeBlueprintValidationError(
                f"{self.blueprint_id}: base_question.context "
                f"{self.base_question.context!r}가 allowed_context_ids {self.allowed_context_ids}에 없다"
            )
        # base_question.frame_id == question_frame_id.
        if self.base_question.frame_id != self.question_frame_id:
            raise V2DirectProbeBlueprintValidationError(
                f"{self.blueprint_id}: base_question.frame_id "
                f"{self.base_question.frame_id!r} != question_frame_id {self.question_frame_id!r}"
            )

        option_role_ids = [o.role_id for o in self.base_question.options]
        # Role ID 집합과 순서가 정확히 일치해야 한다.
        if mapping_role_ids != option_role_ids:
            raise V2DirectProbeBlueprintValidationError(
                f"{self.blueprint_id}: option_mappings 순서 {mapping_role_ids} != "
                f"Base Question Option 순서 {option_role_ids}"
            )
        # 각 Role의 Mapping이 대응하는 Base Question Option의 primary_trait_delta와
        # 정확히 일치해야 한다 — TRAIT_SIGNAL은 {primary_trait_id: 1}, NO_SIGNAL은 {}.
        options_by_role = {o.role_id: o for o in self.base_question.options}
        for mapping in self.option_mappings:
            option = options_by_role[mapping.role_id]
            expected_delta = (
                {mapping.primary_trait_id: 1} if mapping.mapping_type == "TRAIT_SIGNAL" else {}
            )
            if option.primary_trait_delta != expected_delta:
                raise V2DirectProbeBlueprintValidationError(
                    f"{self.blueprint_id}/{mapping.role_id}: Mapping이 기대하는 primary_trait_delta "
                    f"{expected_delta} != Base Question Option primary_trait_delta "
                    f"{option.primary_trait_delta}"
                )

        # Target Trait를 PRIMARY로 갖는 Option이 정확히 1개여야 하고, NO_SIGNAL이면 안 된다.
        target_mappings = [
            m for m in self.option_mappings
            if m.mapping_type == "TRAIT_SIGNAL" and m.primary_trait_id == self.trait_id
        ]
        if len(target_mappings) != 1:
            raise V2DirectProbeBlueprintValidationError(
                f"{self.blueprint_id}: Target Trait {self.trait_id!r}를 PRIMARY로 갖는 "
                f"Option이 {len(target_mappings)}개다(정확히 1개여야 함)"
            )

        # base_question.target_traits는 공개 응답에서 이 Blueprint의 정체를 드러내는 데
        # 쓰이면 안 된다 — Direct Probe 질문은 항상 빈 리스트를 유지한다(§19 API 불변).
        if self.base_question.target_traits:
            raise V2DirectProbeBlueprintValidationError(
                f"{self.blueprint_id}: base_question.target_traits는 비어 있어야 한다"
                f"(Direct Probe는 공개 응답에 Target Trait를 노출하지 않는다), got "
                f"{self.base_question.target_traits}"
            )
        return self


def finalize_v2_probe_question(
    question_id: str,
    generated: GeneratedQuestion,
    blueprint: V2DirectProbeBlueprint,
) -> FinalizedQuestion:
    """2.2단계 §4/§5 — `finalize_question()`(Legacy, `OptionBlueprint` 기반)과 같은 역할을
    Direct Probe 전용 `V2ProbeOptionMapping`으로 수행한다. LLM이 반환한 role_id가
    Blueprint에 없으면 거부한다(CLAUDE.md 규칙 그대로). NO_SIGNAL Role은 공개
    `primary_trait_delta`에 가짜 Trait를 넣지 않고 정직하게 빈 dict `{}`로 만든다."""

    finalized_options: list[FinalizedOption] = []
    for i, option in enumerate(generated.options, start=1):
        try:
            mapping = blueprint.mapping_by_role(option.role_id)
        except KeyError as exc:
            raise ValueError(
                f"LLM이 반환한 role_id {option.role_id!r}가 blueprint "
                f"{blueprint.blueprint_id!r}에 없다 — 거부"
            ) from exc
        primary_trait_delta = (
            {mapping.primary_trait_id: 1} if mapping.mapping_type == "TRAIT_SIGNAL" else {}
        )
        finalized_options.append(
            FinalizedOption(
                option_id=generate_option_id(question_id, i),
                role_id=option.role_id,
                text=option.text,
                primary_trait_delta=primary_trait_delta,
            )
        )

    return FinalizedQuestion(
        question_id=question_id,
        context=generated.context,
        target_traits=generated.target_traits,
        frame_id=generated.frame_id,
        question_text=generated.question_text,
        options=finalized_options,
    )
