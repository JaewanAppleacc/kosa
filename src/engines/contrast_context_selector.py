"""Contrast Context Selector — 설계안 §5-1/§6-5 순수 계산 로직. LLM·DB 호출 없음.

CLAUDE.md: "관심 Context 선택 점수를 Trait 점수로 직접 변환하지 않는다." 이 파일은 관심도
평가와 Context Vector·Coverage Matrix(둘 다 사전 정의된 팀 데이터)만 보고 후보 Context
하나를 고를 뿐, 학생의 Trait 점수나 전공 순위를 참조하지 않는다.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel

from src.schemas.context import ContextVector

# §6-5: "0.6/0.4는 검증된 상수가 아니라 Contrast 목적을 우선하기 위한 MVP 초기값이다."
DISTANCE_WEIGHT = 0.6
COVERAGE_WEIGHT = 0.4

# §5-1: 후보군 선정에 쓰는 관심도 등급 우선순위. 2~3점을 원칙으로 하고, 후보가 없을 때만
# 단계적으로 넓힌다("1점은 학생이 직접 허용한 경우에만"이므로 가장 마지막 단계에만 쓴다).
CandidatePoolTier = Literal[
    "interest_2_3", "interest_4_5_widened", "interest_1_last_resort", "no_rated_candidate_arbitrary_fallback"
]

_POOL_TIERS: list[tuple[CandidatePoolTier, set[int]]] = [
    ("interest_2_3", {2, 3}),
    ("interest_4_5_widened", {4, 5}),
    ("interest_1_last_resort", {1}),
]


class ContrastSelectionResult(BaseModel):
    contrast_context_id: str
    contrast_reason: str
    # 내부 진단용 — API 응답에는 포함하지 않는다(설계안 §16과 동일 원칙: 내부 점수·근거
    # 단계는 화면에 숫자로 노출하지 않는다).
    candidate_pool_tier: CandidatePoolTier


def _vector_fields() -> list[str]:
    return list(ContextVector.model_fields.keys())


def _average_vector(vectors: list[ContextVector]) -> ContextVector:
    fields = _vector_fields()
    return ContextVector(
        **{field: sum(getattr(v, field) for v in vectors) / len(vectors) for field in fields}
    )


def _distance(a: ContextVector, b: ContextVector) -> float:
    return math.sqrt(sum((getattr(a, f) - getattr(b, f)) ** 2 for f in _vector_fields()))


def _normalize(values: dict[str, float]) -> dict[str, float]:
    """Min-Max 정규화. 후보가 1개뿐이거나 전부 같은 값이면(구별할 정보가 없음) 전부 1.0으로
    둔다 — 0으로 나누는 오류를 피하면서, "정보가 없으면 중립적으로 취급한다"는 원칙을 따른다."""

    if not values:
        return {}
    lo, hi = min(values.values()), max(values.values())
    if hi == lo:
        return {k: 1.0 for k in values}
    return {k: (v - lo) / (hi - lo) for k, v in values.items()}


def _build_reason(tier: CandidatePoolTier, covered_gap_trait_labels: list[str]) -> str:
    if covered_gap_trait_labels:
        base = (
            "선택한 4개 Context와 활동 방식이 달라 새로운 관점에서 성향을 관찰할 수 있고, "
            f"{', '.join(covered_gap_trait_labels)} 특성을 추가로 확인할 수 있습니다."
        )
    else:
        base = "선택한 4개 Context와 활동 방식이 가장 달라 새로운 관점에서 성향을 확인할 수 있습니다."

    if tier == "interest_4_5_widened":
        base += " (관심도 2~3점 범위에 후보가 없어 관심도가 더 높은 Context 중에서 골랐습니다.)"
    elif tier == "interest_1_last_resort":
        base += " (관심도 2점 이상인 후보가 없어 관심도가 낮은 Context를 제안합니다 — 원치 않으면 다른 Context를 선택할 수 있습니다.)"
    elif tier == "no_rated_candidate_arbitrary_fallback":
        base = "아직 관심도가 표시되지 않은 Context 중 하나를 제안합니다 — 원치 않으면 다른 Context를 선택할 수 있습니다."
    return base


def select_contrast_context(
    *,
    preferred_context_ids: list[str],
    interest_ratings: dict[str, int],
    all_context_ids: set[str],
    context_vectors: dict[str, ContextVector],
    coverage_matrix: dict[str, dict[str, int]],
    all_trait_ids: set[str],
    trait_labels: dict[str, str],
) -> ContrastSelectionResult:
    """§5-1 Contrast Context 제안 규칙 그대로:

    1. 후보군 = 선호 4개를 제외한 나머지 중 관심도 2~3점(부족하면 단계적으로 완화).
    2. context_distance = 선호 4개 평균 Context Vector와 후보 간 유클리드 거리.
    3. coverage_gain = 선호 4개에서 부족한(관찰 가능 Context 2개 미만인) Trait를 후보가
       보완(coverage_grade>=2)하는 개수.
    4. contrast_score = distance_normalized*0.6 + coverage_gain_normalized*0.4.
    5. 동점이면 context_id 알파벳 순으로 결정론적으로 고른다.
    """

    remaining = sorted(all_context_ids - set(preferred_context_ids))
    if not remaining:
        raise ValueError("Contrast Context 후보가 없습니다 — all_context_ids가 preferred_context_ids뿐입니다.")

    def pool_for(allowed_ratings: set[int]) -> list[str]:
        return [cid for cid in remaining if interest_ratings.get(cid) in allowed_ratings]

    tier: CandidatePoolTier = "no_rated_candidate_arbitrary_fallback"
    candidates: list[str] = []
    for candidate_tier, allowed in _POOL_TIERS:
        candidates = pool_for(allowed)
        if candidates:
            tier = candidate_tier
            break
    if not candidates:
        # 관심도 자체가 없거나(미평가) 1~5 어디에도 안 걸리는 값이면 마지막 방어선으로
        # 알파벳 순 결정론적 후보를 쓴다 — 그래도 str을 항상 반환해야 하는 API 계약을 지킨다.
        candidates = remaining

    selected_vectors = [context_vectors[cid] for cid in preferred_context_ids if cid in context_vectors]
    avg_vector = _average_vector(selected_vectors) if selected_vectors else None

    def observed_count(trait_id: str) -> int:
        return sum(
            1 for cid in preferred_context_ids
            if coverage_matrix.get(cid, {}).get(trait_id, 0) >= 2
        )

    gap_trait_ids = {t for t in all_trait_ids if observed_count(t) < 2}

    distances: dict[str, float] = {}
    coverage_gains: dict[str, float] = {}
    for cid in candidates:
        candidate_vector = context_vectors.get(cid)
        distances[cid] = _distance(avg_vector, candidate_vector) if avg_vector and candidate_vector else 0.0
        candidate_coverage = coverage_matrix.get(cid, {})
        coverage_gains[cid] = sum(1 for t in gap_trait_ids if candidate_coverage.get(t, 0) >= 2)

    normalized_distance = _normalize(distances)
    normalized_gain = _normalize(coverage_gains)

    def score(cid: str) -> float:
        return normalized_distance.get(cid, 0.0) * DISTANCE_WEIGHT + normalized_gain.get(cid, 0.0) * COVERAGE_WEIGHT

    best = sorted(candidates, key=lambda cid: (-score(cid), cid))[0]

    covered_gap_labels = sorted(
        trait_labels.get(t, t)
        for t in gap_trait_ids
        if coverage_matrix.get(best, {}).get(t, 0) >= 2
    )
    reason = _build_reason(tier, covered_gap_labels)

    return ContrastSelectionResult(contrast_context_id=best, contrast_reason=reason, candidate_pool_tier=tier)
