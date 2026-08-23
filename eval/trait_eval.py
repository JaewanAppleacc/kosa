"""trait_eval.py — Persona 답변을 실제로 Evidence Engine에 흘려서, C가 만든
Hand-Calculated Fixture와 자동 비교한다. CLAUDE.md 필수 테스트 "Evidence 수기 계산과
코드 결과 일치"를 Fixture 파일 단위로 반복 실행할 수 있게 만든 도구다.
"""

from __future__ import annotations

from pydantic import BaseModel

from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAITS
from src.engines.evidence_engine import judge_trait_state, summarize_trait_evidence
from src.schemas.evidence import EvidenceOrigin, EvidenceRecord
from src.schemas.persona import HandCalculatedFixture, Persona
from src.schemas.question import OptionBlueprint

_MIN_CONTEXT_COUNT_BY_TRAIT: dict[str, int] = {
    t.trait_id: t.minimum_context_count for t in VERTICAL_SLICE_TRAITS
}


class FixtureMismatch(BaseModel):
    trait_id: str
    field: str
    expected: str
    actual: str


class FixtureComparisonResult(BaseModel):
    fixture_id: str
    passed: bool
    mismatches: list[FixtureMismatch] = []


def build_evidence_records(
    persona: Persona, blueprint_by_question_id: dict[str, OptionBlueprint]
) -> tuple[list[EvidenceRecord], list[set[str]]]:
    """Persona의 답변을 EvidenceRecord 리스트와 "질문별 제시된 Trait 집합" 리스트로 바꾼다.

    후자는 summarize_trait_evidence의 opportunity_count 계산 입력이다 — 질문 하나가
    제시한 5개 Option(=Blueprint의 5개 Role) 각각의 primary_trait_delta 키를 모은 것.
    """

    records: list[EvidenceRecord] = []
    offered_per_question: list[set[str]] = []

    for i, answer in enumerate(persona.answers, start=1):
        blueprint = blueprint_by_question_id[answer.question_id]
        role = blueprint.role_by_id(answer.selected_role_id)

        records.append(
            EvidenceRecord(
                evidence_id=f"ev_{persona.persona_id}_{i}",
                answer_id=f"ans_{persona.persona_id}_{i}",
                question_id=answer.question_id,
                question_frame_id=answer.question_frame_id,
                option_role_id=answer.selected_role_id,
                # PersonaAnswer(§26 Fixture)는 실제 선택지 문장을 담지 않는다 — 손계산
                # 검증용 자리표시자임을 명시한다.
                option_text=f"[Fixture] {answer.selected_role_id}",
                applied_primary_trait_delta=role.primary_trait_delta,
                evidence_origin=EvidenceOrigin.PRIMARY_BLUEPRINT,
                context=answer.context_id,
                source_type="persona_fixture",
                generator_version="fixture_v1",
                quality_gate_status="passed",
            )
        )
        offered_this_question: set[str] = set()
        for r in blueprint.roles:
            offered_this_question.update(r.primary_trait_delta.keys())
        offered_per_question.append(offered_this_question)

    return records, offered_per_question


def evaluate_persona_against_fixture(
    persona: Persona,
    fixture: HandCalculatedFixture,
    blueprint_by_question_id: dict[str, OptionBlueprint],
) -> FixtureComparisonResult:
    records, offered_per_question = build_evidence_records(persona, blueprint_by_question_id)
    mismatches: list[FixtureMismatch] = []

    for expectation in fixture.trait_expectations:
        min_context = _MIN_CONTEXT_COUNT_BY_TRAIT.get(expectation.trait_id, 2)
        summary = summarize_trait_evidence(expectation.trait_id, records, offered_per_question)
        judgment = judge_trait_state(
            summary, minimum_context_count=min_context, has_unresolved_explicit_conflict=False
        )

        checks = [
            ("support_count", expectation.expected_support_count, summary.support_count),
            ("opportunity_count", expectation.expected_opportunity_count, summary.opportunity_count),
            ("context_count", expectation.expected_context_count, summary.context_count),
            (
                "distinct_frame_count",
                expectation.expected_distinct_frame_count,
                summary.distinct_frame_count,
            ),
            ("state", expectation.expected_state.value, judgment.state.value),
            (
                "insufficient_reason",
                expectation.expected_insufficient_reason,
                judgment.insufficient_reason,
            ),
        ]
        for field, expected, actual in checks:
            if expected != actual:
                mismatches.append(
                    FixtureMismatch(
                        trait_id=expectation.trait_id,
                        field=field,
                        expected=str(expected),
                        actual=str(actual),
                    )
                )

    return FixtureComparisonResult(
        fixture_id=fixture.fixture_id, passed=not mismatches, mismatches=mismatches
    )
