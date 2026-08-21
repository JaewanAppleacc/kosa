"""Career Profile 결과 카드 Schema — 설계안 §14 구현. B가 결과 화면에 그대로 쓰는 계약이다."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator, model_validator

# 2026-08-21 리뷰: 기획 원칙 "학생을 유형으로 규정하지 않는다"와 "Evidence 부족을 학생의
# 결핍처럼 표현하지 않는다"를 Prompt 지시만으로 두지 않고 기계적으로도 막는다(§11 Quality
# Gate에서도 같은 이유로 프롬프트 지시 + Code Check를 이중으로 뒀다).
_BANNED_TITLE_TYPE_MARKERS = ("유형", "타입")
_BANNED_DEFICIENCY_PHRASES = (
    "경험이 부족",
    "경험 부족",
    "능력이 부족",
    "능력 부족",
    "약하다",
    "소질이 없",
    "잘하지 못",
)


def _reject_fixed_type_label(title: str) -> None:
    stripped = title.strip()
    if stripped.endswith("형"):
        raise ValueError(
            f"title이 '~형'으로 끝나면 안 된다(고정 유형 라벨처럼 읽힘): {title!r}"
        )
    for marker in _BANNED_TITLE_TYPE_MARKERS:
        if marker in stripped:
            raise ValueError(f"title에 고정 유형 표현({marker!r})을 쓰면 안 된다: {title!r}")


def _reject_deficiency_phrasing(text: str) -> None:
    for phrase in _BANNED_DEFICIENCY_PHRASES:
        if phrase in text:
            raise ValueError(
                f"결핍 표현({phrase!r})은 금지한다 — Evidence 부족은 시스템이 관찰하지 "
                f"못했다는 뜻이지 학생의 능력·경험 부족이 아니다: {text!r}"
            )


class CareerProfileHighlight(BaseModel):
    text: str  # "복잡한 내용에서 핵심과 흐름을 찾아 정리하는 데 흥미를 느껴요." 같은 한 줄
    supporting_trait_ids: list[str]


class DimensionEvidenceItem(BaseModel):
    context_id: str
    description: str  # "장면 순서를 바꿔 내용을 이해하기 쉽게 만드는 활동 선택"


class CareerProfile(BaseModel):
    session_id: str
    user_id: str
    title: str  # 임시 요약 제목. 고정 유형이 아님을 화면에 함께 표시해야 한다.
    highlights: list[CareerProfileHighlight]
    hashtags: list[str]
    disclaimer: str = (
        "현재 답변을 바탕으로 만든 요약이며 새로운 경험과 답변에 따라 달라질 수 있습니다."
    )
    # "왜 이런 결과가 나왔나요?" 상세 근거. key는 Career Dimension label.
    detailed_evidence_by_dimension: dict[str, list[DimensionEvidenceItem]]
    generated_at: datetime

    @field_validator("highlights")
    @classmethod
    def _validate_highlight_count(cls, value: list[CareerProfileHighlight]) -> list[CareerProfileHighlight]:
        # §14: "첫 화면에는 핵심 특징 5~8줄만 보여준다."
        if not (5 <= len(value) <= 8):
            raise ValueError(f"highlights는 5~8줄이어야 한다 (§14), got {len(value)}")
        return value


class GeneratedProfileHighlight(BaseModel):
    """LLM Structured Output 일부 — 어떤 Trait를 문장으로 표현했는지는 trait_id로 서버가
    검증한다(§10과 동일 원칙: LLM이 반환한 식별자를 그대로 신뢰하지 않는다)."""

    trait_id: str
    text: str

    @field_validator("text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("빈 highlight 문장은 허용하지 않는다")
        _reject_deficiency_phrasing(value)
        return value


class GeneratedCareerProfile(BaseModel):
    """§14 Career Profile의 LLM Structured Output. session_id·user_id·generated_at·
    detailed_evidence_by_dimension은 서버가 채운다(engines/profile_engine.py가 이미
    결정론적으로 계산한 값이다)."""

    title: str
    highlights: list[GeneratedProfileHighlight]
    hashtags: list[str]

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("빈 title은 허용하지 않는다")
        _reject_fixed_type_label(value)
        return value

    @model_validator(mode="after")
    def _hashtags_not_empty(self) -> "GeneratedCareerProfile":
        if not self.hashtags:
            raise ValueError("hashtags는 최소 1개 이상이어야 한다")
        return self
