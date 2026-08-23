"""고정 Persona 매칭 진단 — 2026-08-23 13차 리뷰 §4.

Matching 공식(`src/engines/matching_engine.py`)은 이 라운드에서 건드리지 않는다. 이 모듈은
그 공식을 그대로 호출해 여러 고정 Persona에 대한 전공별 결과를 관찰만 하는 "진단용"
계층이다 — 원하는 순위를 만들려고 가중치나 Persona를 거꾸로 맞추지 않는다. Persona는
"이런 학생이 실제로 있을 법하다"는 독립적인 기준(분석형/시각형/계획형/도구형/근거부족형 등)
으로 먼저 정하고, 그 결과를 있는 그대로 기록한다.

`usable_vector_group_count`는 `MajorMatchResult`에 없는 값이라(매칭 공식 코드를 건드리지
않기 위해 필드를 추가하지 않았다), 여기서 Matching Engine과 동일한 그룹 판정 로직을
읽기 전용으로 재현해 계산한다 — 계산 방식을 바꾸는 게 아니라 Engine 내부에서 이미 쓰는
`compute_major_match`의 그룹 판정 조건(가중치>0, 학생 값 확정)을 그대로 다시 읽는다.
"""

from __future__ import annotations

from pydantic import BaseModel

from src.data.majors.canonical_major_descriptions import CANONICAL_MAJOR_DESCRIPTIONS_BY_ID
from src.engines.matching_engine import (
    MajorMatchResult,
    StudentTraitState,
    compute_major_match,
    compute_student_trait_states,
    rank_major_relevance,
)
from src.schemas.evidence import TraitEvidenceSummary
from src.schemas.major import EvidenceSufficiencyLabel, MajorProfile, RelevanceLabel
from src.schemas.trait import TraitDefinition


class PersonaTraitSpec(BaseModel):
    """§13 상태 판정 입력을 손으로 다시 조립하지 않도록, "이 Trait는 STRONG/MODERATE/
    LIMITED/미관찰(NOT_PROBED)이다"만 선언하면 되는 축약 표현."""

    strong: set[str] = set()
    moderate: set[str] = set()
    limited: set[str] = set()
    unresolved_conflict: set[str] = set()  # judge_trait_state 3순위 CONFLICTING 강제


class MatchingPersona(BaseModel):
    persona_id: str
    label: str
    rationale: str
    trait_spec: PersonaTraitSpec


def _summary_for(trait_id: str, spec: PersonaTraitSpec) -> TraitEvidenceSummary:
    if trait_id in spec.strong:
        return TraitEvidenceSummary(
            trait_id=trait_id, support_count=3, opportunity_count=3, context_count=2, distinct_frame_count=2
        )
    if trait_id in spec.moderate:
        return TraitEvidenceSummary(
            trait_id=trait_id, support_count=2, opportunity_count=2, context_count=2, distinct_frame_count=2
        )
    if trait_id in spec.limited:
        # LIMITED: support_count=2지만 context_count=1(최소 미달)이라 §13 기준상 LIMITED.
        return TraitEvidenceSummary(
            trait_id=trait_id, support_count=2, opportunity_count=2, context_count=1, distinct_frame_count=1
        )
    return TraitEvidenceSummary(trait_id=trait_id, support_count=0, opportunity_count=0)


def build_student_states(
    persona: MatchingPersona, trait_defs: dict[str, TraitDefinition]
) -> dict[str, StudentTraitState]:
    summaries = {
        trait_id: _summary_for(trait_id, persona.trait_spec) for trait_id in trait_defs
    }
    return compute_student_trait_states(
        summaries, trait_defs, persona.trait_spec.unresolved_conflict
    )


def _usable_vector_group_count(
    student_states: dict[str, StudentTraitState], major: MajorProfile
) -> int:
    """compute_major_match와 동일한 그룹-사용가능 판정(가중치>0 and 학생 값 확정)을
    읽기 전용으로 재현한다 — Matching Engine 코드/공식은 변경하지 않는다."""

    vector_by_group = {
        "interest": major.interest_vector,
        "cognitive": major.cognitive_vector,
        "work_style": major.work_style_vector,
        "environment": major.environment_vector,
    }
    count = 0
    for major_vector in vector_by_group.values():
        has_usable = any(
            weight > 0 and t in student_states and student_states[t].normalized_value is not None
            for t, weight in major_vector.items()
        )
        if has_usable:
            count += 1
    return count


class MajorDiagnosticRow(BaseModel):
    major_id: str
    label: str
    status: str
    score: float | None
    usable_trait_count: int
    usable_vector_group_count: int
    evidence_sufficiency: EvidenceSufficiencyLabel | None
    relevance_label: RelevanceLabel | None


class PersonaDiagnosticResult(BaseModel):
    persona: MatchingPersona
    majors: list[MajorDiagnosticRow]
    relevant_major_ids: list[str]
    is_tied_for_first: bool
    insufficient_evidence_message: str | None


def diagnose_persona(
    persona: MatchingPersona,
    majors: list[MajorProfile],
    trait_defs: dict[str, TraitDefinition],
) -> PersonaDiagnosticResult:
    student_states = build_student_states(persona, trait_defs)
    results: dict[str, MajorMatchResult] = {
        m.major_id: compute_major_match(student_states, m) for m in majors
    }
    labels = {m.major_id: m.label for m in majors}

    relevant, _explore, insufficient_message = rank_major_relevance(
        list(results.values()), labels, CANONICAL_MAJOR_DESCRIPTIONS_BY_ID
    )

    # evidence_sufficiency는 rank_major_relevance 내부(_evidence_sufficiency_label)에서만
    # 계산되고 MajorRelevance로 나가는 값이라, 여기서는 computed 항목에 한해 같은 규칙을
    # 읽기 전용으로 다시 계산해 진단표에 넣는다(§16 "가짜 정확도" 우려 없음 — 사용자
    # 노출용이 아니라 내부 진단 문서이므로 score도 그대로 보여준다).
    def evidence_sufficiency_for(result: MajorMatchResult) -> EvidenceSufficiencyLabel | None:
        if result.status != "computed":
            return None
        if result.notable_strong_count >= 2:
            return "충분"
        if result.notable_usable_count >= 2:
            return "보통"
        return "제한적"

    relevance_by_major_id = {r.major_id: r.relevance_label for r in relevant}
    for r in _explore:
        relevance_by_major_id[r.major_id] = r.relevance_label

    computed_scores = [r.score for r in results.values() if r.status == "computed" and r.score is not None]
    is_tied_for_first = len(computed_scores) >= 2 and computed_scores.count(max(computed_scores)) >= 2

    rows = [
        MajorDiagnosticRow(
            major_id=major_id,
            label=labels[major_id],
            status=result.status,
            score=result.score,
            usable_trait_count=result.usable_trait_count,
            usable_vector_group_count=_usable_vector_group_count(
                student_states, next(m for m in majors if m.major_id == major_id)
            ),
            evidence_sufficiency=evidence_sufficiency_for(result),
            relevance_label=relevance_by_major_id.get(major_id),
        )
        for major_id, result in results.items()
    ]

    return PersonaDiagnosticResult(
        persona=persona,
        majors=rows,
        relevant_major_ids=[r.major_id for r in relevant],
        is_tied_for_first=is_tied_for_first,
        insufficient_evidence_message=insufficient_message,
    )


# §4가 요구하는 7개 최소 Persona. 매칭 결과를 원하는 방향으로 만들려고 이 목록을 거꾸로
# 조정하지 않는다 — 각 Persona는 "이런 성향의 학생"이라는 독립적 서술에서 먼저 정하고,
# 실제 3개 대표 전공 Vector에 대해 결과가 어떻게 나오는지는 diagnose_persona()가 있는
# 그대로 계산한다.
PERSONAS: list[MatchingPersona] = [
    MatchingPersona(
        persona_id="analytical",
        label="분석·구조화 중심",
        rationale=(
            "원인 분석·패턴 탐색·정보 비교·계획을 반복적으로 강하게 드러내는 학생. "
            "industrial_engineering이 1.0 근처 가중치를 두는 Trait 조합과 그대로 겹친다."
        ),
        trait_spec=PersonaTraitSpec(
            strong={"causal_analysis", "pattern_finding", "information_comparison", "planning"}
        ),
    ),
    MatchingPersona(
        persona_id="visual_user_facing",
        label="시각·사용자 관점 중심",
        rationale=(
            "시각적 표현·수용자 반응 예측·도구 활용을 강하게 드러내고 그 외에는 답변이 없는 "
            "학생. 이 3개 Trait는 hci_ux Vector 전체와 정확히 일치하고, media_communication "
            "Vector에도 '동일한 가중치'로 포함돼 있어 두 전공이 동점을 낼 조건을 그대로 만든다."
        ),
        trait_spec=PersonaTraitSpec(
            strong={"visual_expression", "audience_response_prediction", "tool_utilization"}
        ),
    ),
    MatchingPersona(
        persona_id="planning_collaboration",
        label="계획·협업 중심",
        rationale=(
            "계획·협업 선호·의견 조정을 강하게 드러내는 학생. opinion_mediation은 세 대표 "
            "전공 Vector 어디에도 없는 Trait라 매칭에는 반영되지 않고, planning·"
            "collaboration_preference만 실제로 반영된다 — 다만 이 둘은 media_communication "
            "Vector에서 모두 work_style 그룹 하나에 몰려 있어(usable_trait_count=2), "
            "MINIMUM_USABLE_TRAITS(3) 미달로 insufficient가 나올 가능성이 있다. '전공에 유리한 "
            "Trait를 답했는데도 관련도를 계산 못하는' 경계 사례를 보여주는 대조군이다."
        ),
        trait_spec=PersonaTraitSpec(
            strong={"planning", "collaboration_preference", "opinion_mediation"}
        ),
    ),
    MatchingPersona(
        persona_id="tool_only",
        label="도구 활용 중심",
        rationale=(
            "도구 활용 하나만 강하게 관찰되고 그 외에는 전혀 확인되지 않은 학생. Trait 1개로는 "
            "MINIMUM_USABLE_TRAITS(3) 요건을 어느 전공도 못 채워 insufficient가 나올 것으로 "
            "예상된다 — '근거 부족'과 '매칭 공식 결함'을 구분하는 대조군."
        ),
        trait_spec=PersonaTraitSpec(strong={"tool_utilization"}),
    ),
    MatchingPersona(
        persona_id="all_limited",
        label="전체 Trait가 LIMITED인 학생",
        rationale=(
            "12개 Trait 전부가 LIMITED(약한 근거)로만 관찰된 학생. 가중 충족도는 값이 전부 "
            "같으면 가중치 분포와 무관하게 동일한 결과가 나오므로(가중평균 성질), 세 전공이 "
            "전부 같은 낮은 점수로 나올 것으로 예상된다."
        ),
        trait_spec=PersonaTraitSpec(
            limited={
                "causal_analysis", "pattern_finding", "planning", "immediate_execution",
                "change_adaptation", "collaboration_preference", "opinion_mediation",
                "emotional_interpretation", "audience_response_prediction", "visual_expression",
                "information_comparison", "tool_utilization",
            }
        ),
    ),
    MatchingPersona(
        persona_id="sparse_partial",
        label="일부 Trait만 충분히 관찰된 학생",
        rationale=(
            "12개 중 단 2개(causal_analysis STRONG, tool_utilization LIMITED)만 관찰되고 "
            "나머지는 전혀 답변 기회가 없었던 학생. 초반 몇 문항만 답한 상태를 흉내낸다 — "
            "usable_trait_count가 낮아 insufficient가 나오는 게 정상인지 확인하는 대조군."
        ),
        trait_spec=PersonaTraitSpec(strong={"causal_analysis"}, limited={"tool_utilization"}),
    ),
    MatchingPersona(
        persona_id="unresolved_conflict",
        label="Conflict가 해결되지 않은 학생",
        rationale=(
            "분석형 학생과 같은 답변 패턴이지만, planning(=planning_vs_execution Contrast의 "
            "한 축)이 아직 해결되지 않은 EXPLICIT_CONFLICT 상태라고 가정한다. judge_trait_state "
            "3순위 규칙에 따라 planning은 CONFLICTING으로 Mask돼 어느 전공 비교에도 안 들어가야 "
            "한다(0점 취급이 아니라 완전 제외) — §12 '0점과 다르다'를 Persona 단위로 재확인."
        ),
        trait_spec=PersonaTraitSpec(
            # planning도 strong에 넣어야 opportunity_count>0이 돼 judge_trait_state가
            # unresolved_conflict 분기까지 도달한다(opportunity_count==0이면 그보다 먼저
            # INSUFFICIENT/NOT_PROBED로 끝나버려 Conflict 분기 자체를 안 탄다) — 즉 "답변
            # 패턴은 STRONG처럼 보이지만 아직 해결 안 된 Conflict라 Mask된다"를 그대로 재현.
            strong={"causal_analysis", "pattern_finding", "information_comparison", "planning"},
            unresolved_conflict={"planning"},
        ),
    ),
]
