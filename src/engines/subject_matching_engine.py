"""Subject Matching Engine — PRE_SURVEY 과목 추천, 2026-08-24 14차 리뷰, 설계안 §20 보조.

LLM·DB 호출 없는 순수 계산이다(`src/engines/matching_engine.py`와 같은 성격). Major
Matching Engine과 동일한 원칙을 그대로 따른다:

- 미해결 Conflict Trait는 확정 추천 근거에서 제외한다 — `student_states`는 이미
  `compute_student_trait_states()`가 Mask(normalized_value=None) 처리한 값을 받는다.
  이 파일은 Conflict 판정을 다시 하지 않는다(중복 금지).
- UNMAPPED/REVIEW_REQUIRED Trait는 0점이 아니라 비교에서 제외한다 —
  `SubjectProfile.trait_vector`가 이미 그렇게 만들어져 있다(scripts/career_build_
  subject_profiles.py, weight>0인 Key만 존재).
- 선택한 전공과 공식적으로 연결된 과목(`SubjectProfile.related_major_ids`)만 후보로
  쓴다 — 그 밖의 과목은 애초에 candidates에도 들어가지 않는다.
- 내부 점수(score)는 API로 나가는 `CourseRecommendationItem`에 절대 포함하지 않는다.
- 특정 결과를 만들기 위해 이 임계값들을 나중에 바꾸지 않는다(§16과 같은 정신 —
  "검증된 값이 아니라 MVP 초기 휴리스틱"임을 그대로 인정하고 명시한다).
"""

from __future__ import annotations

from pydantic import BaseModel

from src.engines.matching_engine import StudentTraitState, _weighted_trait_coverage
from src.schemas.course import CourseRecommendationItem
from src.schemas.course import SubjectProfile
from src.schemas.trait import TraitDefinition

# MVP 초기 휴리스틱 — matching_engine.py의 MINIMUM_USABLE_TRAITS/MINIMUM_SCORE_FOR_HIGH_
# RELEVANCE와 같은 성격이다. 과목은 전공보다 Trait Vector가 훨씬 희소하다(보통 2~4개)라
# 전공 기준(3개)을 그대로 가져오면 거의 모든 과목이 "explore" 밑으로 떨어진다 — 그래서
# 과목 전용으로 별도 상수를 둔다.
MINIMUM_USABLE_TRAITS_FOR_EXPLORE = 1
MINIMUM_USABLE_TRAITS_FOR_CORE = 2
MINIMUM_SCORE_FOR_CORE = 0.6


class SubjectMatchResult(BaseModel):
    """내부 계산 결과. `score`는 절대 API로 노출하지 않는다(§7)."""

    subject_id: str
    label: str
    category: str  # "core" | "explore" — PRE_SURVEY는 "alternative"를 만들지 않는다.
    score: float
    usable_trait_count: int
    usable_trait_ids: list[str] = []


def compute_subject_recommendations(
    student_states: dict[str, StudentTraitState],
    selected_major_id: str,
    subjects: list[SubjectProfile],
) -> list[SubjectMatchResult]:
    """§7 원칙 그대로: `selected_major_id`와 공식적으로 연결된 과목만 후보로 삼고,
    학생이 확정한(Mask 아닌) Trait와 과목 Trait Vector가 공유하는 항목만 비교한다.
    공유 Trait가 하나도 없으면 그 과목은 결과에 아예 포함하지 않는다("빈 추천"이
    정직한 결과일 수 있다 — §7 "관련 Trait가 부족하면 빈 추천 또는 정직한 부족 상태
    반환")."""

    candidates = [s for s in subjects if selected_major_id in s.related_major_ids]

    results: list[SubjectMatchResult] = []
    for subject in candidates:
        shared_trait_ids = sorted(
            t for t, weight in subject.trait_vector.items()
            if weight > 0
            and t in student_states
            and student_states[t].normalized_value is not None
        )
        if not shared_trait_ids:
            continue

        student_values = [student_states[t].normalized_value for t in shared_trait_ids]  # type: ignore[misc]
        subject_weights = [subject.trait_vector[t] for t in shared_trait_ids]
        score = _weighted_trait_coverage(student_values, subject_weights)
        if score is None:
            continue

        usable_trait_count = len(shared_trait_ids)
        if usable_trait_count >= MINIMUM_USABLE_TRAITS_FOR_CORE and score >= MINIMUM_SCORE_FOR_CORE:
            category = "core"
        elif usable_trait_count >= MINIMUM_USABLE_TRAITS_FOR_EXPLORE:
            category = "explore"
        else:
            continue

        results.append(
            SubjectMatchResult(
                subject_id=subject.subject_id,
                label=subject.label,
                category=category,
                score=score,
                usable_trait_count=usable_trait_count,
                usable_trait_ids=shared_trait_ids,
            )
        )

    # 결정론적 정렬: core 먼저, 점수 내림차순, 동점이면 subject_id 오름차순(major_id
    # 알파벳 순서로 표시 순서만 정하고 등급에는 안 쓰는 rank_major_relevance와 같은 이유).
    category_order = {"core": 0, "explore": 1}
    results.sort(key=lambda r: (category_order[r.category], -r.score, r.subject_id))
    return results


def build_reason(
    result: SubjectMatchResult, major_label: str, trait_definitions: dict[str, TraitDefinition]
) -> str:
    """§7: reason에는 (1) 선택한 전공과의 연결 이유, (2) 학생 답변에서 확인된 Trait,
    (3) 과목에서 경험하게 되는 활동만 정성적으로 담는다. 숫자 유사도는 넣지 않는다."""

    trait_labels = "·".join(
        trait_definitions[t].label for t in result.usable_trait_ids if t in trait_definitions
    )
    return (
        f"선택한 전공({major_label})과 공식적으로 연결된 과목입니다. "
        f"학생 답변에서 확인된 {trait_labels} 경향과 관련된 활동을 이 과목에서 경험하게 됩니다."
    )


def to_course_recommendation_items(
    results: list[SubjectMatchResult],
    major_label: str,
    trait_definitions: dict[str, TraitDefinition],
) -> list[CourseRecommendationItem]:
    """내부 결과를 API로 나가는 형태로 바꾼다 — `score`는 여기서 완전히 사라진다.
    PRE_SURVEY이므로 `is_actually_offered=None`(개설 여부 미확정, §6)이고, "핵심"은
    "실제 개설 확인"이 아니라 "희망 우선과목"이라는 뜻이다."""

    return [
        CourseRecommendationItem(
            subject_id=result.subject_id,
            category=result.category,  # type: ignore[arg-type]
            is_actually_offered=None,
            reason=build_reason(result, major_label, trait_definitions),
        )
        for result in results
    ]
