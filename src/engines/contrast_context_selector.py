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

# 2026-08-22 리뷰: §5-1 FROZEN 설계는 "선호 Context 4개"를 요구하지만, Vertical Slice는
# Context 자체가 3~15개 규모로 다르고 지금 실제로 쓰이는 흐름은 2~3개다. 지금 당장 4개를
# 강제하면 기존 Vertical Slice 세션 흐름이 전부 깨진다 — "설정값 또는 실행 모드로
# 분리"하라는 지시대로 최소 개수를 모드별 상수로 나눠두고, 지금은 Vertical Slice 값을
# 쓴다. Full Mode 전환 시 이 상수만 바꾸면 된다(§5-1 자체 재구현은 이번 범위 밖).
MINIMUM_PREFERRED_CONTEXT_COUNT_VERTICAL_SLICE = 2
MINIMUM_PREFERRED_CONTEXT_COUNT_FULL_MODE = 4
# 2026-08-30 20차 리뷰: 선호 Context는 Vertical Slice에서 "정확히 2개"다 — 최솟값과
# 최댓값을 같은 값으로 둬서 "정확히"를 표현한다(별도 exact_count 매개변수를 새로 만들지
# 않고 기존 minimum/maximum 쌍으로 표현 가능해서, validate_context_id_list()를 재사용).
MAXIMUM_PREFERRED_CONTEXT_COUNT_VERTICAL_SLICE = MINIMUM_PREFERRED_CONTEXT_COUNT_VERTICAL_SLICE
# 최종 확정 Context — 선호 2개(그대로 유지 가능) ~ 선호 2개+Contrast 1개(수용) 범위다.
MINIMUM_FINAL_CONTEXT_COUNT_VERTICAL_SLICE = 2
MAXIMUM_FINAL_CONTEXT_COUNT_VERTICAL_SLICE = 3
CONTRAST_CONTEXT_COUNT_VERTICAL_SLICE = 1
# Coverage Replacement(관심 Context 부족분을 자동으로 보완 제안하는 기능)는 아직 실제
# 계산이 없다 — `ContextSelectResponse.coverage_replacement_offered`가 항상 빈 배열인
# 이유와 같은 사실을 `GET /contexts`의 selection_policy로도 명시적으로 알려준다.
COVERAGE_REPLACEMENT_ENABLED_VERTICAL_SLICE = False


class ContextSelectionError(ValueError):
    """Context 선택·확정 입력이 유효하지 않을 때(중복, 미지의 ID, 빈 목록, 개수 미달·초과)."""


def validate_context_id_list(
    context_ids: list[str],
    all_context_ids: set[str],
    *,
    minimum_count: int,
    maximum_count: int | None = None,
    label: str,
) -> None:
    """§5-1 "학생이 선호 Context를 직접 선택한다"/"최종 Context 확정"에 공통으로 적용하는
    구조적 검증 — 빈 목록·중복·미지의 Context id·개수 미달(및 `maximum_count`가 주어지면
    개수 초과)을 거부한다. "제안한 Contrast 후보만 허용"처럼 내용을 강제하지는 않는다
    (학생이 다른 Context로 교체할 수 있어야 하므로, §5-1 "학생은 유지·수용·다른 Context
    선택 중 하나를 고른다"). `maximum_count=None`(기본값)은 기존 호출부와 동일하게 상한이
    없다는 뜻이다 — 2026-08-30 20차 리뷰로 추가된 매개변수라 기존 호출부를 깨지 않는다."""

    if not context_ids:
        raise ContextSelectionError(f"{label} 목록이 비어 있습니다.")
    if len(set(context_ids)) != len(context_ids):
        duplicates = sorted({c for c in context_ids if context_ids.count(c) > 1})
        raise ContextSelectionError(f"{label}에 중복된 Context id가 있습니다: {duplicates}")
    unknown = sorted(set(context_ids) - all_context_ids)
    if unknown:
        raise ContextSelectionError(f"{label}에 알 수 없는 Context id가 있습니다: {unknown}")
    if len(context_ids) < minimum_count:
        raise ContextSelectionError(
            f"{label}는 최소 {minimum_count}개 이상이어야 합니다 (현재 {len(context_ids)}개)."
        )
    if maximum_count is not None and len(context_ids) > maximum_count:
        raise ContextSelectionError(
            f"{label}는 최대 {maximum_count}개까지만 선택할 수 있습니다 (현재 {len(context_ids)}개)."
        )


MINIMUM_RATING_SCORE = 1
MAXIMUM_RATING_SCORE = 5


def validate_interest_ratings(
    ratings: dict[str, int],
    all_context_ids: set[str],
    *,
    minimum_count: int,
) -> None:
    """2026-08-22 3차 리뷰: `/assessment/interest-rating`이 이전엔 `dict[str, int]`
    형태만 확인하고 값 자체는 검증하지 않아, 점수 범위를 벗어나거나(0, 6, 음수) 등록
    되지 않은 Context id로도 그대로 저장됐다 — 이 값이 나중에 Context Selector(§5-1/§6-5)
    입력으로 그대로 쓰이므로, 여기서 구조적으로 막는다.

    Context id는 dict의 key라 애초에 중복될 수 없다(같은 key로 오면 마지막 값으로
    덮어써질 뿐 별도 항목이 되지 않는다) — 그래서 별도 중복 검사가 필요 없고, "정규화
    충돌"도 CONTEXT_IDS가 이미 정규 slug만 등록하므로 미등록 id 거부로 함께 막힌다."""

    if not ratings:
        raise ContextSelectionError("관심도 평가가 비어 있습니다.")

    unknown = sorted(set(ratings) - all_context_ids)
    if unknown:
        raise ContextSelectionError(f"관심도 평가에 알 수 없는 Context id가 있습니다: {unknown}")

    invalid = sorted(
        context_id
        for context_id, score in ratings.items()
        if isinstance(score, bool) or not isinstance(score, int)
        or score < MINIMUM_RATING_SCORE or score > MAXIMUM_RATING_SCORE
    )
    if invalid:
        raise ContextSelectionError(
            f"관심도 점수는 {MINIMUM_RATING_SCORE}~{MAXIMUM_RATING_SCORE} 사이의 정수여야 합니다: {invalid}"
        )

    if len(ratings) < minimum_count:
        raise ContextSelectionError(
            f"관심도 평가는 최소 {minimum_count}개 이상이어야 합니다 (현재 {len(ratings)}개)."
        )


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


def _build_reason(tier: CandidatePoolTier, covered_gap_trait_labels: list[str], preferred_count: int) -> str:
    """2026-08-22 3차 리뷰 항목 4: 이전엔 선호 Context 개수를 "4개"로 고정 문구에 박아뒀다
    — §5-1 FROZEN 설계의 Full Mode 기준 개수일 뿐, Vertical Slice는 실제로 2개를 쓴다
    (MINIMUM_PREFERRED_CONTEXT_COUNT_VERTICAL_SLICE). 실제 호출자가 넘긴 개수를 그대로
    반영해 두 흐름 모두에서 문구가 사실과 맞게 한다."""

    if covered_gap_trait_labels:
        base = (
            f"선택한 {preferred_count}개 Context와 활동 방식이 달라 새로운 관점에서 성향을 관찰할 수 있고, "
            f"{', '.join(covered_gap_trait_labels)} 특성을 추가로 확인할 수 있습니다."
        )
    else:
        base = f"선택한 {preferred_count}개 Context와 활동 방식이 가장 달라 새로운 관점에서 성향을 확인할 수 있습니다."

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
    reason = _build_reason(tier, covered_gap_labels, len(preferred_context_ids))

    return ContrastSelectionResult(contrast_context_id=best, contrast_reason=reason, candidate_pool_tier=tier)
