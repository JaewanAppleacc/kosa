"""Persona / Hand-Calculated Fixture Schema — 설계안 §6-6, §26 구현.

C가 §3 "고정 Persona 답변 데이터"와 "Hand-Calculated Fixture 초안"을 만들 때 이 Schema를
따른다(A 지시서 §6: "Persona·Fixture가 충족해야 할 필드"). A의 Evaluation Harness는
`compare_fixture_to_actual()`(eval/trait_eval.py)로 이 Fixture와 실제 코드 계산 결과를
자동 비교한다.
"""

from __future__ import annotations

from pydantic import BaseModel

from src.schemas.evidence import InsufficientReason, TraitState


class PersonaAnswer(BaseModel):
    """Persona가 특정 질문에서 실제로 고른 선택지 한 건."""

    context_id: str
    question_id: str
    question_frame_id: str
    selected_option_id: str
    selected_role_id: str


class Persona(BaseModel):
    """§26 End-to-End Persona. 고정된 질문·답변 시퀀스라 세션마다 항상 같은 결과가 나와야 한다
    (동일 답변 재실행 일관성 — §26 Evaluation 항목)."""

    persona_id: str
    user_id: str
    label: str  # 예: "분석·구조화 중심"
    description: str
    final_context_ids: list[str]  # Vertical Slice에서는 3개
    answers: list[PersonaAnswer]


class HandCalculatedTraitExpectation(BaseModel):
    """Trait 하나에 대해 사람이 손으로 미리 계산해 둔 기대값. calculation_notes에는 "왜
    이 숫자가 나오는지"를 반드시 적는다 — 숫자만 있으면 나중에 검토자가 재검산할 수 없다."""

    trait_id: str
    expected_support_count: int
    expected_opportunity_count: int
    expected_context_count: int
    expected_distinct_frame_count: int
    expected_state: TraitState
    expected_insufficient_reason: InsufficientReason | None = None
    calculation_notes: str


class HandCalculatedFixture(BaseModel):
    """§6-6: "학생 답변 → 선택 Option과 role_id → Primary Trait Evidence → support_ratio와
    Evidence 기반 내부 상태 → Student Profile → 전공 관련도 순위 → 과목 추천"을 팀이 손으로
    검산한 결과. `expected_top_major_relevance_order`는 정확한 점수가 아니라 순위만 담는다
    — 이 시스템은 내부 점수를 사용자에게 노출하지 않으므로 순위 일치 여부만 검증 대상이다.
    """

    fixture_id: str
    persona_id: str
    trait_expectations: list[HandCalculatedTraitExpectation]
    expected_top_major_relevance_order: list[str] = []  # major_id, 순위대로
    notes: str = ""
