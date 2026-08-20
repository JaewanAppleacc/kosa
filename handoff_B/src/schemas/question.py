"""Question / Option Schema — 설계안 §7-3, §9, §9-1, §10 구현.

역할 구분(설계안 §10 원칙 그대로):
- GeneratedOption / GeneratedQuestion: LLM Structured Output. question_id/option_id를
  포함하지 않는다 — 서버가 생성한다(CLAUDE.md "option_id는 서버가 생성하며 LLM이 만들지 않는다").
- OptionBlueprint: 사람이 미리 검토해 코드로 관리하는 Role→Trait 대응표. LLM은 이 Role을
  자연스러운 문장으로 표현할 뿐 trait_delta를 만들지 않는다.
- FinalizedQuestion/FinalizedOption: 서버가 id를 부여하고 Blueprint의 trait_delta를 결합한
  최종 산출물. Evidence Engine은 이것만 입력으로 받는다.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

from src.ids import generate_option_id


class OptionRole(BaseModel):
    """설계안 §9 Option Blueprint의 개별 role. MVP 규칙: 모든 trait_delta 값은 1이다."""

    role_id: str
    primary_trait_delta: dict[str, int]

    @field_validator("primary_trait_delta")
    @classmethod
    def _validate_trait_delta(cls, value: dict[str, int]) -> dict[str, int]:
        if not value:
            raise ValueError("primary_trait_delta must not be empty (§9-1 Blueprint Lint)")
        if any(v != 1 for v in value.values()):
            raise ValueError(
                "MVP에서 모든 primary_trait_delta 값은 1로 고정한다 (§9-1 Blueprint Lint)"
            )
        return value


class OptionBlueprint(BaseModel):
    blueprint_id: str
    roles: list[OptionRole]

    @model_validator(mode="after")
    def _lint(self) -> "OptionBlueprint":
        # §9-1 Option Blueprint Lint — 사람이 작성한 Blueprint 자체를 검사한다.
        if len(self.roles) != 5:
            raise ValueError(
                f"Option Role은 정확히 5개여야 한다 (§9-1), got {len(self.roles)}: {self.blueprint_id}"
            )
        role_ids = [r.role_id for r in self.roles]
        if len(set(role_ids)) != len(role_ids):
            raise ValueError(f"Blueprint별 Role ID가 서로 달라야 한다 (§9-1): {self.blueprint_id}")

        seen_traits: set[str] = set()
        for role in self.roles:
            for trait_id in role.primary_trait_delta:
                if trait_id in seen_traits:
                    raise ValueError(
                        "한 질문의 여러 Option에 동일 Trait가 중복 배정될 수 없다 (§9-1): "
                        f"{self.blueprint_id} / {trait_id}"
                    )
                seen_traits.add(trait_id)
        return self

    def role_by_id(self, role_id: str) -> OptionRole:
        for role in self.roles:
            if role.role_id == role_id:
                return role
        raise KeyError(f"role_id {role_id!r} not found in blueprint {self.blueprint_id!r}")


class GeneratedOption(BaseModel):
    """LLM Structured Output 일부 — option_id 없음."""

    role_id: str
    text: str

    @field_validator("text")
    @classmethod
    def _validate_text_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("빈 선택지는 허용하지 않는다 (§11 Code Check '빈 선택지 없음')")
        return value


class GeneratedQuestion(BaseModel):
    """LLM Structured Output — question_id 없음. 선택지는 정확히 5개(§11 Code Check).

    여기서 검증하는 건 구조적 결함(빈 문자열)뿐이다. target_traits가 실제 Ontology에
    있는지, context가 실제 Context 목록에 있는지는 이 Schema가 아니라 §11 Quality Gate가
    검증한다 — Quality Gate는 Ontology·Context 목록을 런타임에 주입받아 검사하는 별도
    컴포넌트이고(아직 미구현), Schema가 특정 데이터셋을 직접 참조하게 만들면 재사용성이
    떨어진다.
    """

    context: str
    target_traits: list[str]
    frame_id: str
    question_text: str
    options: list[GeneratedOption]

    @field_validator("context", "frame_id", "question_text")
    @classmethod
    def _validate_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("빈 값은 허용하지 않는다 (§11 Code Check)")
        return value

    @field_validator("options")
    @classmethod
    def _validate_option_count(cls, value: list[GeneratedOption]) -> list[GeneratedOption]:
        if len(value) != 5:
            raise ValueError(f"선택지는 정확히 5개여야 한다 (§11 Code Check), got {len(value)}")
        role_ids = [o.role_id for o in value]
        if len(set(role_ids)) != len(role_ids):
            raise ValueError("모든 Role ID가 서로 달라야 한다 (§11 Code Check)")
        return value


class SecondaryTraitHypothesis(BaseModel):
    trait_id: str
    source_answer_id: str
    status: Literal["HYPOTHESIS", "CONFIRMED", "DISMISSED", "EXPIRED"]
    verification_count: int = 0


class QuestionGenerationResult(BaseModel):
    question: GeneratedQuestion
    secondary_trait_hypotheses_from_previous_answer: list[str] = []


class FinalizedOption(BaseModel):
    """서버가 option_id를 부여하고 Blueprint의 trait_delta를 결합한 최종 Option."""

    option_id: str
    role_id: str
    text: str
    primary_trait_delta: dict[str, int]


class FinalizedQuestion(BaseModel):
    question_id: str
    context: str
    target_traits: list[str]
    frame_id: str
    question_text: str
    options: list[FinalizedOption]

    @field_validator("options")
    @classmethod
    def _validate_option_count(cls, value: list[FinalizedOption]) -> list[FinalizedOption]:
        if len(value) != 5:
            raise ValueError(f"선택지는 정확히 5개여야 한다, got {len(value)}")
        return value


def finalize_question(
    question_id: str,
    generated: GeneratedQuestion,
    blueprint: OptionBlueprint,
) -> FinalizedQuestion:
    """LLM 출력(GeneratedQuestion)에 서버 id와 Blueprint trait_delta를 결합한다.

    LLM이 반환한 role_id가 Blueprint에 없으면 거부한다 (CLAUDE.md
    "LLM이 반환한 Role ID가 Blueprint와 다르면 거부한다").
    """

    finalized_options: list[FinalizedOption] = []
    for i, option in enumerate(generated.options, start=1):
        try:
            role = blueprint.role_by_id(option.role_id)
        except KeyError as exc:
            raise ValueError(
                f"LLM이 반환한 role_id {option.role_id!r}가 blueprint "
                f"{blueprint.blueprint_id!r}에 없다 — 거부"
            ) from exc
        finalized_options.append(
            FinalizedOption(
                option_id=generate_option_id(question_id, i),
                role_id=option.role_id,
                text=option.text,
                primary_trait_delta=role.primary_trait_delta,
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
