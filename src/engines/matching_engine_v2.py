"""v2 Major Matching Engine — 2026-08-23 Trait Ontology v2(2.6단계) §7.

`src/engines/matching_engine.py`(Legacy)와 같은 "cosine similarity 대신 가중 충족도"
원칙을 그대로 따르되, §7이 요구하는 대로 다음 요소를 명시적으로 분리해서 계산한다.

- Trait 중요도(major_vector의 가중치, 0.33/0.67/1.00)
- 학생 tendency(TraitVectorEntry.tendency_score)
- 학생 evidence confidence(TraitVectorEntry.evidence_confidence → 숫자 가중치)
- 전공 요구·관련 등급("이 전공이 중요하게 보는 Trait" — 가중치 0.67 이상)
- Conflict Mask(TraitVectorEntry.conflict_status — True면 그 Trait는 비교에서 제외)
- 사용 가능한 Trait 개수(MINIMUM_USABLE_TRAITS 미만이면 insufficient)
- Trait Group 다양성(MINIMUM_USABLE_VECTOR_GROUPS 미만이면 insufficient)

내부 score는 절대 API로 노출하지 않는다 — `rank_major_relevance_v2()`가 Legacy와 동일한
`MajorRelevance`(정성 Label만 포함)로 변환해서 반환한다(§7 "API에는 기존 정성 Label만
반환").
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from src.engines.matching_engine import MissingMajorDescriptionError
from src.schemas.major import EvidenceSufficiencyLabel, MajorProfile, MajorRelevance, RelevanceLabel
from src.schemas.trait_vector_snapshot import TraitVectorEntry

# §16(Legacy)과 같은 성격의 값 — "검증된 상수가 아니라 MVP 초기 휴리스틱".
VECTOR_GROUP_WEIGHTS: dict[str, float] = {
    "interest": 0.35, "cognitive": 0.30, "work_style": 0.20, "environment": 0.15,
}

# §7 "학생 evidence confidence" — PRIMARY Evidence로 확정된 판정을 가장 신뢰하고,
# RELATED만으로 승격된 판정은 한 단계 낮춰 반영한다(Legacy의 damping과 같은 폭 0.67을
# 재사용 — 새 임의 상수를 만들지 않는다).
_EVIDENCE_CONFIDENCE_WEIGHT: dict[str, float] = {
    "primary_evidence": 1.0,
    "promoted_related_signal": 0.67,
}

MINIMUM_USABLE_TRAITS = 3
MINIMUM_USABLE_VECTOR_GROUPS = 2
MINIMUM_SCORE_FOR_HIGH_RELEVANCE = 0.6
# "전공 요구·관련 등급" — 이 전공이 그 Trait를 "자주 활용" 이상으로 요구한다는 뜻(Legacy와
# 동일 임계값 0.67, §15 Rubric과 일치).
NOTABLE_TRAIT_WEIGHT_THRESHOLD = 0.67

# 2026-08-25 지시서(a/major-profiles-v2-38) §3 — 39개 Major 전체를 내부 계산 대상으로
# 넓히면서, 학생에게 노출하는 카드 수까지 함께 늘리지 않기 위한 상한이다. 내부 계산
# 자체(compute_major_match_v2)는 이 상수와 무관하게 여전히 39개 전부에 대해 수행된다 —
# 이 상수는 rank_major_relevance_v2()가 반환하는 두 목록의 "길이"만 자른다.
MAX_RELEVANT_MAJORS = 3
MAX_EXPLORE_TOGETHER_MAJORS = 3

INSUFFICIENT_EVIDENCE_MESSAGE_V2 = "아직 v2 관련도를 계산하기에 답변이 부족합니다. 추가 탐색이 필요합니다."


class MajorMatchResultV2(BaseModel):
    major_id: str
    status: Literal["computed", "insufficient"]
    score: float | None = None  # 후보군 내 정렬 전용 — API에는 절대 노출하지 않는다.
    usable_trait_count: int = 0
    notable_strong_count: int = 0
    notable_usable_count: int = 0
    max_evidence_count_among_notable: int = 0


def _effective_tendency(entry: TraitVectorEntry) -> float | None:
    """§7 "학생 tendency"와 "학생 evidence confidence"를 분리 계산한 뒤 곱으로
    결합한다 — tendency_score가 None(미관찰/미해소 Conflict)이면 애초에 비교 대상이
    아니다(호출하는 쪽이 먼저 걸러낸다)."""

    if entry.tendency_score is None or entry.conflict_status:
        return None
    confidence_weight = _EVIDENCE_CONFIDENCE_WEIGHT.get(entry.evidence_confidence)
    if confidence_weight is None:
        return None
    return entry.tendency_score * confidence_weight


def compute_major_match_v2(
    student_entries: dict[str, TraitVectorEntry], major: MajorProfile
) -> MajorMatchResultV2:
    """§7 — Vector Group별로 (Trait 중요도 × effective_tendency)의 가중 평균을 구하고,
    그 결과를 다시 VECTOR_GROUP_WEIGHTS로 가중합한다. 학생·전공 둘 다에서 확정된
    (Conflict Mask 통과, non-null) Trait만 분자·분모에 넣는다."""

    vector_by_group = {
        "interest": major.interest_vector, "cognitive": major.cognitive_vector,
        "work_style": major.work_style_vector, "environment": major.environment_vector,
    }

    group_coverages: dict[str, float] = {}
    usable_trait_ids: set[str] = set()

    for group, major_vector in vector_by_group.items():
        shared: list[tuple[str, float, float]] = []  # (trait_id, importance_w, effective_tendency)
        for trait_id, importance_w in major_vector.items():
            if importance_w <= 0:
                continue
            entry = student_entries.get(trait_id)
            if entry is None:
                continue
            tendency = _effective_tendency(entry)
            if tendency is None:
                continue
            shared.append((trait_id, importance_w, tendency))
        if not shared:
            continue
        total_weight = sum(w for _, w, _ in shared)
        if total_weight == 0:
            continue
        group_coverages[group] = sum(w * t for _, w, t in shared) / total_weight
        usable_trait_ids.update(t for t, _, _ in shared)

    usable_vector_group_count = len(group_coverages)
    usable_trait_count = len(usable_trait_ids)

    # "전공 요구·관련 등급" — 이 전공이 중요하게 보는 Trait 중 학생이 확정한 것만으로
    # Evidence 충분성을 판단한다(Legacy와 동일 목적: 전공마다 다른 결과가 나오게 함).
    notable_trait_ids = {
        t for group in vector_by_group.values() for t, w in group.items() if w >= NOTABLE_TRAIT_WEIGHT_THRESHOLD
    }
    notable_usable = [
        (t, student_entries[t]) for t in notable_trait_ids
        if t in student_entries and _effective_tendency(student_entries[t]) is not None
    ]
    notable_strong_count = sum(1 for _, e in notable_usable if e.status == "STRONG")
    max_evidence_count = max((e.evidence_count for _, e in notable_usable), default=0)

    if usable_trait_count < MINIMUM_USABLE_TRAITS or usable_vector_group_count < MINIMUM_USABLE_VECTOR_GROUPS:
        return MajorMatchResultV2(major_id=major.major_id, status="insufficient", usable_trait_count=usable_trait_count)

    total_weight = sum(VECTOR_GROUP_WEIGHTS[g] for g in group_coverages)
    score = sum(VECTOR_GROUP_WEIGHTS[g] * cov for g, cov in group_coverages.items()) / total_weight

    return MajorMatchResultV2(
        major_id=major.major_id, status="computed", score=score, usable_trait_count=usable_trait_count,
        notable_strong_count=notable_strong_count, notable_usable_count=len(notable_usable),
        max_evidence_count_among_notable=max_evidence_count,
    )


def _evidence_sufficiency_label_v2(result: MajorMatchResultV2) -> EvidenceSufficiencyLabel:
    if result.notable_strong_count >= 2:
        return "충분"
    if result.notable_usable_count >= 2:
        return "보통"
    return "제한적"


def rank_major_relevance_v2(
    results: list[MajorMatchResultV2], labels_by_major_id: dict[str, str],
    descriptions_by_major_id: dict[str, str],
) -> tuple[list[MajorRelevance], list[MajorRelevance], str | None]:
    """Legacy `rank_major_relevance()`와 동일한 3가지 방어(고유 점수 구간, 절대 하한,
    Evidence 충분성)를 그대로 적용한다 — v2도 같은 정직성 원칙을 지킨다.

    2026-08-24 A3 지시서 §6/§7: `descriptions_by_major_id`도 Legacy와 완전히 같은
    Fail-Fast 규칙을 따른다(`MissingMajorDescriptionError`) — 호출부는 Legacy와
    v2가 서로 다른 설명을 만들지 않도록 항상 같은 `CANONICAL_MAJOR_DESCRIPTIONS_BY_ID`
    를 넘겨야 한다.

    2026-08-25 지시서(a/major-profiles-v2-38) §3 — `results`는 39개 전체에 대해
    이미 계산된 값을 그대로 받는다(내부 계산은 39개 전부에 수행한다는 요구는
    호출부가 39개 MajorProfile을 그대로 넘기는 것으로 충족된다). 이 함수는 그
    결과를 사용자에게 보여줄 두 목록으로 좁히는 마지막 단계에서
    `MAX_RELEVANT_MAJORS`/`MAX_EXPLORE_TOGETHER_MAJORS`로 자른다 — "근거가
    제한적이면 관련성 높음으로 승격 금지"(위 `relevance_label_for`의 기존 방어)
    로직보다 뒤에 적용해, 승격 방어를 우회해 카드 수만 늘리는 경로가 없게 한다."""

    computed = [r for r in results if r.status == "computed"]
    if not computed:
        return [], [], INSUFFICIENT_EVIDENCE_MESSAGE_V2

    computed.sort(key=lambda r: (-r.score, r.major_id))  # type: ignore[arg-type]
    unique_scores_desc = sorted({r.score for r in computed}, reverse=True)  # type: ignore[arg-type]

    def relevance_label_for(score: float, evidence_sufficiency: EvidenceSufficiencyLabel) -> RelevanceLabel:
        score_rank = unique_scores_desc.index(score)
        tier = (score_rank * 3) // len(unique_scores_desc)
        label = ["관련성 높음", "함께 탐색해볼 분야", "비교해볼 만한 분야"][min(tier, 2)]
        if label == "관련성 높음" and score < MINIMUM_SCORE_FOR_HIGH_RELEVANCE:
            label = "함께 탐색해볼 분야"
        if label == "관련성 높음" and evidence_sufficiency == "제한적":
            label = "함께 탐색해볼 분야"
        return label

    relevant: list[MajorRelevance] = []
    explore_together: list[MajorRelevance] = []
    for result in computed:
        evidence_sufficiency = _evidence_sufficiency_label_v2(result)
        relevance = relevance_label_for(result.score, evidence_sufficiency)  # type: ignore[arg-type]
        description = descriptions_by_major_id.get(result.major_id)
        if not description or not description.strip():
            raise MissingMajorDescriptionError(
                f"major_id {result.major_id!r}에 대한 검토된 설명(description)이 없다 — "
                "canonical_majors.jsonl에 항목을 추가하거나 descriptions_by_major_id 호출을 확인하세요."
            )
        item = MajorRelevance(
            major_id=result.major_id, label=labels_by_major_id.get(result.major_id, result.major_id),
            description=description, relevance_label=relevance, evidence_sufficiency=evidence_sufficiency,
            repeated_context_count=result.max_evidence_count_among_notable,
        )
        if relevance == "관련성 높음":
            relevant.append(item)
        else:
            explore_together.append(item)

    # §3 "학생 API에는 과도한 카드가 나오지 않도록" — computed 순회 순서가 이미
    # (-score, major_id) 정렬이라(위), 각 목록도 그 순서를 그대로 유지한 채 앞에서부터
    # 자른다. 잘린 나머지는 그냥 버린다 — 다른 목록으로 옮기지 않는다(관련성 높음에서
    # 넘친 항목을 함께 탐색으로 승격시키면 그 자체가 새로운 "관련성 높음" 승격 우회
    # 경로가 된다).
    return relevant[:MAX_RELEVANT_MAJORS], explore_together[:MAX_EXPLORE_TOGETHER_MAJORS], None
