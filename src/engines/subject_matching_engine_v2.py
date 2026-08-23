"""v2 Subject Matching Engine — 2026-08-23 Trait Ontology v2(2.6단계) §8.

`src/engines/subject_matching_engine.py`(Legacy)와 같은 원칙(cosine 아님, UNMAPPED/
REVIEW_REQUIRED는 비교에서 제외, `score`는 API에 절대 노출하지 않음)을 그대로 따르되,
입력이 `dict[str, TraitVectorEntry]`(v2)이고 결합 공식이
`matching_engine_v2._effective_tendency()`(tendency × evidence confidence, Conflict
Mask 포함)라는 점이 다르다.

결과 타입은 Legacy `SubjectMatchResult`를 **그대로 재사용**한다(§8 "API Schema를
가능하면 변경하지 않음") — `build_reason`/`to_course_recommendation_items`처럼 결과
타입의 필드만 보고 동작하는 Legacy 함수들을 그대로 다시 쓸 수 있어 이유 문구 생성
로직을 중복하지 않는다."""

from __future__ import annotations

from src.engines.matching_engine_v2 import _effective_tendency
from src.engines.subject_matching_engine import SubjectMatchResult
from src.schemas.course import SubjectProfile
from src.schemas.trait_vector_snapshot import TraitVectorEntry

MINIMUM_USABLE_TRAITS_FOR_EXPLORE = 1
MINIMUM_USABLE_TRAITS_FOR_CORE = 2
MINIMUM_SCORE_FOR_CORE = 0.6


def compute_subject_recommendations_v2(
    student_entries: dict[str, TraitVectorEntry],
    selected_major_id: str,
    subjects: list[SubjectProfile],
) -> list[SubjectMatchResult]:
    """§8 — 선택한 전공과 공식적으로 연결된 과목만 후보로 삼고, 학생이 확정한(Conflict
    Mask 통과, non-null) v2 Trait와 과목 Trait Vector가 공유하는 항목만 비교한다.
    공유 Trait가 하나도 없으면 그 과목은 결과에서 빠진다(빈 추천이 정직한 결과일 수
    있다 — Legacy와 동일 원칙)."""

    candidates = [s for s in subjects if selected_major_id in s.related_major_ids]

    results: list[SubjectMatchResult] = []
    for subject in candidates:
        shared: list[tuple[str, float, float]] = []
        for trait_id, importance_w in subject.trait_vector.items():
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
        score = sum(w * t for _, w, t in shared) / total_weight
        shared_trait_ids = sorted(t for t, _, _ in shared)

        usable_trait_count = len(shared_trait_ids)
        if usable_trait_count >= MINIMUM_USABLE_TRAITS_FOR_CORE and score >= MINIMUM_SCORE_FOR_CORE:
            category = "core"
        elif usable_trait_count >= MINIMUM_USABLE_TRAITS_FOR_EXPLORE:
            category = "explore"
        else:
            continue

        results.append(
            SubjectMatchResult(
                subject_id=subject.subject_id, label=subject.label, category=category, score=score,
                usable_trait_count=usable_trait_count, usable_trait_ids=shared_trait_ids,
                activity_summary=subject.activity_summary,
            )
        )

    category_order = {"core": 0, "explore": 1}
    results.sort(key=lambda r: (category_order[r.category], -r.score, r.subject_id))
    return results
