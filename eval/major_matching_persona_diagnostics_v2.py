"""39개 Service Major v2 — 고정 Persona 회귀 진단 — 2026-08-25 지시서
(a/major-profiles-v2-38) §4.

Legacy `eval/major_matching_persona_diagnostics.py`(대표 전공 3개)와 같은 원칙을
따른다 — `matching_engine_v2.py`의 공식·가중치·최소 Evidence 기준은 이 모듈이
절대 건드리지 않는다. 있는 그대로 호출한 결과를 사실 그대로 기록한다.

**Persona 구성(최소 38개, §4)**: 39개 Major 각각에 대해 그 Major의 "핵심(1.00
weight) Trait"만 STRONG으로 답한 "자기 전공(self)" Persona를 자동 생성한다 —
`career_build_major_profiles_v2.py`의 `MANUAL_MAJOR_TRAIT_TABLE`/Evidence
결과와 같은 데이터에서 만들므로, Persona를 원하는 결과가 나오도록 손으로
거꾸로 맞춘 게 아니라 Profile 자체의 핵심 신호를 그대로 재현한 것이다(39개).
여기에 "인접 전공 혼동" 대조군 Persona를 추가로 몇 개 더 손으로 정의한다
(의료 계열 전반, 공학 계열 전반 등 — 여러 인접 Major가 동시에 겹치는 Trait
조합) — 합쳐서 39 + 인접군 ≥ 38을 넉넉히 넘는다."""

from __future__ import annotations

from pydantic import BaseModel

from src.data.majors.service_canonical_major_v2_descriptions import SERVICE_CANONICAL_MAJOR_V2_DESCRIPTIONS_BY_ID
from src.data.majors.service_major_profiles_v2 import SERVICE_MAJOR_PROFILES_V2
from src.engines.matching_engine_v2 import (
    MajorMatchResultV2,
    compute_major_match_v2,
    rank_major_relevance_v2,
)
from src.schemas.major import EvidenceSufficiencyLabel, MajorProfile, RelevanceLabel
from src.schemas.trait_vector_snapshot import TraitVectorEntry
from src.services.trait_ontology_v2 import load_trait_ontology_v2

_ALL_TRAIT_IDS: tuple[str, ...] = tuple(sorted(t.trait_id for t in load_trait_ontology_v2()))


class MatchingPersonaV2(BaseModel):
    persona_id: str
    label: str
    rationale: str
    strong_trait_ids: tuple[str, ...]
    target_major_ids: tuple[str, ...]  # 이 Persona가 "맞아야 정상"이라고 기대하는 Major(참고용, 강제 아님).


def _entry(trait_id: str, *, tendency: float | None, status: str = "STRONG", confidence: str = "primary_evidence") -> TraitVectorEntry:
    return TraitVectorEntry(
        trait_id=trait_id, primary_signal_sum=1.0, related_signal_sum=0.0,
        confirmed_related_signal_sum=0.0, primary_evidence_count=3, related_evidence_count=0,
        context_count=2, frame_count=2, question_count=3, tendency_score=tendency,
        evidence_confidence=confidence, status=status,
    )


def build_student_states(persona: MatchingPersonaV2) -> dict[str, TraitVectorEntry]:
    """`strong_trait_ids`만 STRONG(tendency=1.0)으로 관찰되고 나머지 v2 24개
    Trait는 전부 미관찰(tendency=None, NOT_PROBED)이다 — "이 Trait만 답한
    학생"을 그대로 재현한다."""

    states: dict[str, TraitVectorEntry] = {}
    for trait_id in _ALL_TRAIT_IDS:
        if trait_id in persona.strong_trait_ids:
            states[trait_id] = _entry(trait_id, tendency=1.0)
        else:
            states[trait_id] = _entry(trait_id, tendency=None, status="NOT_PROBED", confidence="no_evidence")
    return states


class MajorDiagnosticRowV2(BaseModel):
    major_id: str
    label: str
    status: str
    score: float | None
    usable_trait_count: int
    evidence_sufficiency: EvidenceSufficiencyLabel | None
    relevance_label: RelevanceLabel | None


class PersonaDiagnosticResultV2(BaseModel):
    persona: MatchingPersonaV2
    majors: list[MajorDiagnosticRowV2]
    relevant_major_ids: list[str]
    explore_together_major_ids: list[str]
    self_major_in_relevant: bool | None  # target_major_ids가 비어 있으면 None(대조군 Persona).
    insufficient_evidence_message: str | None


def _evidence_sufficiency_for(result: MajorMatchResultV2) -> EvidenceSufficiencyLabel | None:
    if result.status != "computed":
        return None
    if result.notable_strong_count >= 2:
        return "충분"
    if result.notable_usable_count >= 2:
        return "보통"
    return "제한적"


def diagnose_persona_v2(
    persona: MatchingPersonaV2, majors: list[MajorProfile] | None = None,
) -> PersonaDiagnosticResultV2:
    majors = majors if majors is not None else SERVICE_MAJOR_PROFILES_V2
    student_states = build_student_states(persona)
    results: dict[str, MajorMatchResultV2] = {m.major_id: compute_major_match_v2(student_states, m) for m in majors}
    labels = {m.major_id: m.label for m in majors}

    relevant, explore, insufficient_message = rank_major_relevance_v2(
        list(results.values()), labels, SERVICE_CANONICAL_MAJOR_V2_DESCRIPTIONS_BY_ID
    )
    relevance_by_major_id: dict[str, RelevanceLabel] = {r.major_id: r.relevance_label for r in relevant}
    for r in explore:
        relevance_by_major_id[r.major_id] = r.relevance_label

    rows = [
        MajorDiagnosticRowV2(
            major_id=major_id, label=labels[major_id], status=result.status, score=result.score,
            usable_trait_count=result.usable_trait_count,
            evidence_sufficiency=_evidence_sufficiency_for(result),
            relevance_label=relevance_by_major_id.get(major_id),
        )
        for major_id, result in results.items()
    ]

    relevant_ids = [r.major_id for r in relevant]
    self_major_in_relevant: bool | None = None
    if persona.target_major_ids:
        self_major_in_relevant = any(mid in relevant_ids for mid in persona.target_major_ids)

    return PersonaDiagnosticResultV2(
        persona=persona, majors=rows, relevant_major_ids=relevant_ids,
        explore_together_major_ids=[r.major_id for r in explore],
        self_major_in_relevant=self_major_in_relevant,
        insufficient_evidence_message=insufficient_message,
    )


def _self_personas_from_manual_table() -> list[MatchingPersonaV2]:
    """39개 "자기 전공" Persona — 각 Major의 핵심(1.00) Trait만 STRONG으로
    답한다. 데이터는 `career_build_major_profiles_v2.py`의 두 근거(Evidence
    파일 3개 + MANUAL_MAJOR_TRAIT_TABLE 36개)에서 그대로 가져온다 — Persona를
    별도로 손으로 지어내지 않는다(원하는 결과가 나오도록 거꾸로 맞추지
    않는다는 원칙)."""

    from scripts.career_build_major_profiles_v2 import (
        EVIDENCE_BASED_MAJOR_IDS,
        MANUAL_MAJOR_TRAIT_TABLE,
        V2_EVIDENCE_PATH,
    )
    from src.services.major_trait_mapping_evidence import load_major_trait_mapping_evidence

    personas: list[MatchingPersonaV2] = []

    for major_id in sorted(MANUAL_MAJOR_TRAIT_TABLE):
        # 핵심(1.00)만으로는 일부 Major가 MINIMUM_USABLE_TRAITS(3) 미달로 항상
        # insufficient가 나온다(예: 핵심 2개 + 구분 1개 구성) — "이 Major Profile이
        # 요구하는 Trait를 실제로 전부 강하게 드러내는 학생"을 재현하려면 핵심+구분
        # 전체를 답해야 한다. 여전히 원하는 결과를 위해 거꾸로 맞춘 게 아니라, 그
        # Profile 자체가 가진 Trait 전체를 그대로 재현한 것이다.
        all_traits = tuple(sorted(t for t, weight, tier, _r in MANUAL_MAJOR_TRAIT_TABLE[major_id]))
        personas.append(
            MatchingPersonaV2(
                persona_id=f"self_{major_id}", label=f"{major_id} 자기 전공형",
                rationale=f"{major_id} Profile이 가진 Trait 전부(핵심+구분)를 STRONG으로 답한 학생",
                strong_trait_ids=all_traits, target_major_ids=(major_id,),
            )
        )

    records = load_major_trait_mapping_evidence(V2_EVIDENCE_PATH)
    by_major: dict[str, list] = {}
    for r in records:
        if r.major_id in EVIDENCE_BASED_MAJOR_IDS and r.mapping_status == "EVIDENCED" and (r.grade or 0) >= 1:
            by_major.setdefault(r.major_id, []).append(r.trait_id)
    for major_id in sorted(EVIDENCE_BASED_MAJOR_IDS):
        all_traits = tuple(sorted(by_major.get(major_id, [])))
        personas.append(
            MatchingPersonaV2(
                persona_id=f"self_{major_id}", label=f"{major_id} 자기 전공형",
                rationale=f"{major_id} Profile이 가진 Trait 전부(EVIDENCED, grade>=1)를 STRONG으로 답한 학생",
                strong_trait_ids=all_traits, target_major_ids=(major_id,),
            )
        )
    return personas


# 인접 전공 혼동 대조군에 쓸 Cluster 정의 — target_major_ids만 손으로 정하고
# (실제 계열 인접성에 대한 사람 판단), 각 Persona의 strong_trait_ids는
# `_confusion_persona_traits()`가 실제 39개 Profile에서 그 Cluster 소속 Major들이
# 쓰는 Trait 전체(합집합)를 그대로 읽어 계산한다 — "원하는 결과가 나오도록 손으로
# Trait를 맞추지 않는다"는 원칙을 여기서도 지킨다.
_CONFUSION_CLUSTERS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    # persona_id: (label, rationale, target_major_ids)
    "confusion_medical_cluster": (
        "의료 계열 전반 혼동형", "의학·치의학·약학·한의학·수의학 Profile이 쓰는 Trait 전체를 답한 학생",
        ("medicine", "dentistry", "pharmacy", "korean_medicine", "veterinary"),
    ),
    "confusion_engineering_cluster": (
        "공학 계열 전반 혼동형", "컴퓨터·전자·기계·건축·반도체·의공학 Profile이 쓰는 Trait 전체를 답한 학생",
        (
            "computer_science", "electrical_electronic", "mechanical_engineering",
            "civil_architecture", "semiconductor_materials", "bio_medical_engineering",
        ),
    ),
    "confusion_caring_cluster": (
        "돌봄·지원 계열 혼동형", "간호·사회복지·보건재활 Profile이 쓰는 Trait 전체를 답한 학생",
        ("nursing", "social_welfare", "health_science"),
    ),
    "confusion_planning_cluster": (
        "기획·행정 계열 혼동형", "경영·행정·무역·관광 Profile이 쓰는 Trait 전체를 답한 학생",
        ("business_administration", "public_administration", "trade_logistics", "tourism"),
    ),
    "confusion_natural_science_cluster": (
        "자연과학 계열 혼동형", "화학·물리·생명과학·지구환경·수학통계 Profile이 쓰는 Trait 전체를 답한 학생",
        ("chemistry", "physics_astronomy", "life_science", "earth_environment", "mathematics_statistics"),
    ),
    "confusion_social_science_cluster": (
        "사회과학 계열 혼동형", "사회학·정치외교·인문학·심리학 Profile이 쓰는 Trait 전체를 답한 학생",
        ("sociology", "political_science", "humanities", "psychology"),
    ),
    "confusion_hci_design_cluster": (
        "HCI·미디어 혼동형", "hci_ux·media_communication Profile이 쓰는 Trait 전체를 답한 학생",
        ("hci_ux", "media_communication"),
    ),
}


def _confusion_persona_traits(target_major_ids: tuple[str, ...]) -> tuple[str, ...]:
    by_id = {m.major_id: m for m in SERVICE_MAJOR_PROFILES_V2}
    trait_ids: set[str] = set()
    for major_id in target_major_ids:
        profile = by_id[major_id]
        trait_ids |= set(profile.interest_vector) | set(profile.cognitive_vector)
        trait_ids |= set(profile.work_style_vector) | set(profile.environment_vector)
    return tuple(sorted(trait_ids))


def _confusion_personas() -> list[MatchingPersonaV2]:
    personas = [
        MatchingPersonaV2(
            persona_id=persona_id, label=label, rationale=rationale,
            strong_trait_ids=_confusion_persona_traits(target_major_ids), target_major_ids=target_major_ids,
        )
        for persona_id, (label, rationale, target_major_ids) in sorted(_CONFUSION_CLUSTERS.items())
    ]
    personas.append(
        MatchingPersonaV2(
            persona_id="sparse_low_evidence", label="근거 부족형",
            rationale="Trait 1개만 STRONG — 어느 Major도 MINIMUM_USABLE_TRAITS를 못 채워야 정상(대조군)",
            strong_trait_ids=("tool_utilization",), target_major_ids=(),
        )
    )
    personas.append(
        MatchingPersonaV2(
            persona_id="all_traits_strong", label="전체 Trait 강한형",
            rationale="24개 Trait 전부 STRONG — 특정 3개 Major가 쏠리는지 관찰하는 대조군",
            strong_trait_ids=_ALL_TRAIT_IDS, target_major_ids=(),
        )
    )
    return personas


CONFUSION_PERSONAS: list[MatchingPersonaV2] = _confusion_personas()


def all_personas() -> list[MatchingPersonaV2]:
    """§4 "최소 38개 전형 Persona" — 39개 자기 전공형 + 인접 혼동/대조군 9개 =
    48개(≥38)."""

    return _self_personas_from_manual_table() + CONFUSION_PERSONAS
