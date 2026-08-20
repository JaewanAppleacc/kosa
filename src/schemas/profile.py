"""Career Profile 결과 카드 Schema — 설계안 §14 구현. B가 결과 화면에 그대로 쓰는 계약이다."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


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
