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
    """설계안 §9 Option Blueprint의 개별 role. MVP 규칙: 모든 trait_delta 값은 1이다.

    `next_probe`는 §7-3/§8과 동일한 개념이다 — "이 Option을 고른 학생에게 이어질 다음
    질문이 자연스럽게 이어지도록 잇는 재료"이며, Target Trait 자체를 바꾸지 않는다(§8:
    "직전 답변에서 강하게 나타난 관심은 우선순위 조건이 아니라... 문구를 자연스럽게
    잇는 재료로만 사용한다"). 기존 Fixture 호환을 위해 Optional로 둔다."""

    role_id: str
    primary_trait_delta: dict[str, int]
    next_probe: str | None = None

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
    """서버가 option_id를 부여하고 Blueprint의 trait_delta를 결합한 최종 Option.

    `next_probe`는 이 Option이 선택됐을 때 다음 질문 문구를 자연스럽게 잇기 위한 재료다
    (§7-3, §8). Mock·Backup 경로는 채우지 않을 수 있어 Optional이다."""

    option_id: str
    role_id: str
    text: str
    primary_trait_delta: dict[str, int]
    next_probe: str | None = None


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


class SeedOption(BaseModel):
    """§7-3 Seed Option. Seed는 LLM이 생성하지 않고 전부 손으로 작성하므로, Adaptive
    흐름(GeneratedOption→Blueprint 결합)과 달리 role_id·text·primary_trait_delta를
    한 객체에 바로 담는다. `next_probe`는 이 Option을 고른 학생에게 다음 질문이
    무엇을 확인해야 하는지 알려주는 메모이고(§7-3: "선택한 Option의 next_probe만
    LLM에 전달"), `preferred_frames`는 그 다음 질문에 어울리는 Frame 후보다."""

    option_id: str
    text: str
    role_id: str
    primary_trait_delta: dict[str, int]
    next_probe: str
    preferred_frames: list[str] = []

    @field_validator("text", "next_probe")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("빈 값은 허용하지 않는다")
        return value

    @field_validator("primary_trait_delta")
    @classmethod
    def _trait_delta_is_one(cls, value: dict[str, int]) -> dict[str, int]:
        if not value:
            raise ValueError("primary_trait_delta must not be empty")
        if any(v != 1 for v in value.values()):
            raise ValueError("MVP에서 모든 primary_trait_delta 값은 1로 고정한다")
        return value


class SeedQuestion(BaseModel):
    """§7-1 고정 Seed Question. Context당 1개, 선택지 정확히 5개."""

    question_id: str
    context: str
    question_text: str
    options: list[SeedOption]

    @field_validator("question_text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("빈 값은 허용하지 않는다")
        return value

    @model_validator(mode="after")
    def _lint(self) -> "SeedQuestion":
        if len(self.options) != 5:
            raise ValueError(f"선택지는 정확히 5개여야 한다, got {len(self.options)}: {self.question_id}")
        role_ids = [o.role_id for o in self.options]
        if len(set(role_ids)) != len(role_ids):
            raise ValueError(f"모든 Role ID가 서로 달라야 한다: {self.question_id}")
        seen_traits: set[str] = set()
        for option in self.options:
            for trait_id in option.primary_trait_delta:
                if trait_id in seen_traits:
                    raise ValueError(
                        f"한 질문의 여러 Option에 동일 Trait가 중복 배정될 수 없다: "
                        f"{self.question_id} / {trait_id}"
                    )
                seen_traits.add(trait_id)
        return self


def seed_question_to_blueprint(seed: SeedQuestion) -> OptionBlueprint:
    """Persona/Fixture 검증 도구(eval/trait_eval.py)가 Seed도 Adaptive와 같은 인터페이스로
    다룰 수 있도록, Seed의 Role→Trait 대응을 OptionBlueprint 형태로 파생시킨다."""

    return OptionBlueprint(
        blueprint_id=f"{seed.question_id}_blueprint",
        roles=[
            OptionRole(role_id=o.role_id, primary_trait_delta=o.primary_trait_delta)
            for o in seed.options
        ],
    )


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
                next_probe=role.next_probe,
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
