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
from src.schemas.course import CourseRecommendationItem, SubjectProfile, UnavailableSubjectItem
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
    # 2026-08-25 15차 리뷰: SubjectProfile.activity_summary를 그대로 옮겨 담는다 — 여기서
    # 새로 만들지 않는다(정본 값만 쓴다). compute_subject_recommendations()가 이미 usable_
    # trait_ids가 최소 1개 이상인 과목만 결과에 넣으므로, 그 과목은 반드시 EVIDENCED
    # Trait가 있고(§4 model_validator) 따라서 activity_summary도 항상 채워져 있다.
    activity_summary: str = ""


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
                activity_summary=subject.activity_summary,
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
    """§3/§4(2026-08-25 15차 리뷰): 예전 문구("선택한 전공과 공식적으로 연결된 과목입니다")는
    Subject–Major/Subject–Trait Mapping이 아직 review_status="draft"(2인 검토 전)라는
    사실과 안 맞는 과장이었다 — "공식적으로 연결됨"이 아니라 "공식 자료를 근거로 삼아
    연결해 본 시연 과목"이라는 더 정직한 수위로 낮춘다.

    reason에는 (1) 선택한 전공, (2) 학생 답변에서 확인된 Trait, (3) 그 과목의 공식
    교육과정 근거에서 뽑은 짧은 활동 요약(`SubjectProfile.activity_summary`, 성취기준
    원문을 그대로 노출하지 않는다)만 정성적으로 담는다 — 숫자 유사도는 절대 넣지 않는다.

    `activity_summary`가 비어 있으면(정본에 근거가 없다는 뜻) 활동을 지어내지 않고
    제한적인 문구로 대체한다 — compute_subject_recommendations()가 이미 EVIDENCED
    Trait가 있는 과목만 결과에 넣으므로 실제로는 거의 발생하지 않지만, 방어적으로 남긴다."""

    trait_labels = "·".join(
        trait_definitions[t].label for t in result.usable_trait_ids if t in trait_definitions
    )
    if not result.activity_summary.strip():
        return (
            f"공식 교육과정 자료를 바탕으로 {major_label} 탐색과 연결해 본 시연 과목입니다. "
            f"학생 답변에서 확인된 {trait_labels} 경향과 관련이 있지만, 구체적인 학습 활동 "
            "근거는 아직 정리되지 않았습니다."
        )
    return (
        f"공식 교육과정 자료를 바탕으로 {major_label} 탐색과 연결한 시연 과목입니다. "
        f"{result.label}에서 {result.activity_summary}을 경험할 수 있으며, "
        f"학생 답변에서 확인된 {trait_labels} 경향과 연결됩니다."
    )


def to_course_recommendation_items(
    results: list[SubjectMatchResult],
    major_label: str,
    trait_definitions: dict[str, TraitDefinition],
    *,
    is_actually_offered: bool | None = None,
) -> list[CourseRecommendationItem]:
    """내부 결과를 API로 나가는 형태로 바꾼다 — `score`는 여기서 완전히 사라진다.
    PRE_SURVEY 호출부(기본값)는 `is_actually_offered=None`(개설 여부 미확정, §6)이고,
    "핵심"은 "실제 개설 확인"이 아니라 "희망 우선과목"이라는 뜻이다. 2026-08-26 16차
    리뷰: POST_OFFERING에서 실제 개설이 확인된 core/explore 과목을 그대로 옮길 때는
    `is_actually_offered=True`를 명시적으로 넘긴다(대체과목은 별도로
    `to_alternative_course_recommendation_items`가 만든다). `label`은 정본
    SubjectProfile.label을 그대로 옮긴다(§1 — 화면 표시용 이름을 새로 만들지 않는다)."""

    return [
        CourseRecommendationItem(
            subject_id=result.subject_id,
            label=result.label,
            category=result.category,  # type: ignore[arg-type]
            is_actually_offered=is_actually_offered,
            reason=build_reason(result, major_label, trait_definitions),
        )
        for result in results
    ]


# --- POST_OFFERING (2026-08-26 16차 리뷰, §7/§8) ---


def _has_final_consonant(word: str) -> bool:
    """한글 조사(은/는, 을/를) 선택용 — 마지막 글자의 받침 유무를 유니코드 조합 규칙으로
    판정한다(가나다순 완성형 한글은 0xAC00부터 28개 종성 단위로 배열돼 있다). 한글이
    아닌 문자로 끝나면(드물게 영문 과목명 등) 받침 없음으로 취급한다 — 완벽하진 않지만
    현재 데이터(전부 한글 과목명)에서는 항상 정확하다."""

    if not word:
        return False
    code = ord(word[-1])
    if 0xAC00 <= code <= 0xD7A3:
        return (code - 0xAC00) % 28 != 0
    return False


def _topic_particle(word: str) -> str:
    return "은" if _has_final_consonant(word) else "는"


def _object_particle(word: str) -> str:
    return "을" if _has_final_consonant(word) else "를"


def build_unavailable_reason(missing: SubjectMatchResult, major_label: str) -> str:
    """§7/§8: 원래 희망과목이 실제 개설 목록에 없다는 사실만 정직하게 담는다 — 숫자
    유사도·내부 점수는 절대 포함하지 않는다."""

    particle = _topic_particle(missing.label)
    return (
        f"{missing.label}{particle} 원래 {major_label} 탐색 희망 과목이었지만, "
        "이 학교의 실제 개설과목 목록에는 없습니다."
    )


def build_alternative_reason(
    alternative: SubjectMatchResult,
    missing: SubjectMatchResult,
    major_label: str,
    trait_definitions: dict[str, TraitDefinition],
) -> str:
    """§8: 대체 추천 이유에는 (1) 원래 희망과목이 미개설이라는 사실, (2) 이 과목이 실제
    개설됐다는 사실, (3) 선택 전공·학생 Trait와 연결되는 이유, (4) 실제 과목 활동
    요약을 전부 담는다. 숫자 유사도는 넣지 않는다."""

    trait_labels = "·".join(
        trait_definitions[t].label for t in alternative.usable_trait_ids if t in trait_definitions
    )
    missing_particle = _topic_particle(missing.label)
    alt_object_particle = _object_particle(alternative.label)
    if alternative.activity_summary.strip():
        activity_clause = f"{alternative.label}에서 {alternative.activity_summary}을 경험할 수 있습니다."
    else:
        activity_clause = f"{alternative.label}의 구체적인 학습 활동 근거는 아직 정리되지 않았습니다."
    return (
        f"원래 희망했던 {missing.label}{missing_particle} 이 학교에서 실제로 개설되지 "
        f"않았습니다. 대신 {major_label} 탐색과 연결되고 실제 개설이 확인된 "
        f"{alternative.label}{alt_object_particle} 대체 과목으로 제안합니다. {activity_clause} "
        f"학생 답변에서 확인된 {trait_labels} 경향과도 연결됩니다."
    )


def to_alternative_course_recommendation_items(
    assignments: list[tuple[SubjectMatchResult, SubjectMatchResult]],
    major_label: str,
    trait_definitions: dict[str, TraitDefinition],
) -> list[CourseRecommendationItem]:
    """`assignments`는 (대체과목 SubjectMatchResult, 대체되는 미개설 과목 SubjectMatchResult)
    쌍의 목록이다. 전부 실제 개설이 확인된 과목이므로 `is_actually_offered=True`,
    `category="alternative"`, `replaces_subject_id`에 원래 희망과목의 subject_id를 담는다."""

    return [
        CourseRecommendationItem(
            subject_id=alternative.subject_id,
            label=alternative.label,
            category="alternative",
            is_actually_offered=True,
            reason=build_alternative_reason(alternative, missing, major_label, trait_definitions),
            replaces_subject_id=missing.subject_id,
        )
        for alternative, missing in assignments
    ]


def compute_post_offering_recommendations(
    student_states: dict[str, StudentTraitState],
    selected_major_id: str,
    subjects: list[SubjectProfile],
    confirmed_offered_subject_ids: set[str],
    major_label: str,
    trait_definitions: dict[str, TraitDefinition],
) -> tuple[list[CourseRecommendationItem], list[UnavailableSubjectItem]]:
    """§7/§8 POST_OFFERING 재추천. 입력은 PRE_SURVEY와 완전히 동일한 종류(학생 Trait
    상태, 선택 전공, 과목 정본)에 "실제로 확정된 개설과목 집합" 하나만 추가된다 —
    매칭 점수·임계값 자체는 `compute_subject_recommendations`(PRE_SURVEY와 동일 함수)를
    그대로 재사용해서 다시 계산한다(복제하지 않는다).

    처리 순서(§8 그대로):
    1. `compute_subject_recommendations`로 PRE_SURVEY와 동일한 전체 wishlist(core+explore)
       를 다시 계산한다.
    2. 원래 core였던 과목 중 실제 개설된 것은 core로, explore였던 과목 중 실제 개설된
       것은 explore로 그대로 유지한다(대체과목으로 소비되지 않는 한).
    3. 원래 core였는데 미개설인 과목은 `unavailable_subjects`로 옮기고, 그 각각에 대해
       대체 후보를 찾는다 — 후보 조건: 원래 explore 등급이었고(즉 "확실한 희망"까지는
       아니었던), 실제로 개설됐고, 아직 다른 미개설 과목에 배정되지 않은 과목. 이
       조건을 만족하는 후보가 여러 개면 원래 wishlist에서의 순위(점수 내림차순,
       subject_id 오름차순 — compute_subject_recommendations의 결정론적 정렬)가 가장
       높은 것을 고른다.
    4. 같은 대체과목을 여러 미개설 과목에 중복 배정하지 않는다(배정되면 후보 목록에서
       제거).
    5. 대체 후보를 못 찾으면 대체과목 없이 unavailable만 남긴다(지어내지 않는다).
    6. 원래 explore였는데 미개설인 과목도 unavailable_subjects에는 들어가지만(사실을
       숨기지 않는다), explore는 애초에 "확실한 희망"이 아니었으므로 이 과목을 위한
       대체 후보 탐색은 하지 않는다(§8이 요구하는 범위를 벗어난 과도한 추정을 피한다).
    """

    original_results = compute_subject_recommendations(student_states, selected_major_id, subjects)
    original_core = [r for r in original_results if r.category == "core"]
    original_explore = [r for r in original_results if r.category == "explore"]

    kept_core = [r for r in original_core if r.subject_id in confirmed_offered_subject_ids]
    missing_core = [r for r in original_core if r.subject_id not in confirmed_offered_subject_ids]
    missing_explore = [r for r in original_explore if r.subject_id not in confirmed_offered_subject_ids]

    # explore 등급이면서 실제 개설된 과목만 대체 후보 풀이 된다 — 이미
    # compute_subject_recommendations가 점수 내림차순으로 정렬해 줬으므로 그 순서를
    # 그대로 "가장 적절한 순서"로 쓴다(§8 "가장 적절한 실제 개설 과목을 제안").
    alternative_pool = [r for r in original_explore if r.subject_id in confirmed_offered_subject_ids]
    used_alternative_ids: set[str] = set()

    unavailable: list[UnavailableSubjectItem] = []
    assignments: list[tuple[SubjectMatchResult, SubjectMatchResult]] = []

    for missing in missing_core:
        unavailable.append(
            UnavailableSubjectItem(
                subject_id=missing.subject_id,
                label=missing.label,
                reason=build_unavailable_reason(missing, major_label),
            )
        )
        candidate = next(
            (c for c in alternative_pool if c.subject_id not in used_alternative_ids), None
        )
        if candidate is not None:
            used_alternative_ids.add(candidate.subject_id)
            assignments.append((candidate, missing))

    for missing in missing_explore:
        unavailable.append(
            UnavailableSubjectItem(
                subject_id=missing.subject_id,
                label=missing.label,
                reason=build_unavailable_reason(missing, major_label),
            )
        )

    kept_explore = [
        r for r in original_explore
        if r.subject_id in confirmed_offered_subject_ids and r.subject_id not in used_alternative_ids
    ]

    kept_recommendations = to_course_recommendation_items(
        kept_core + kept_explore, major_label, trait_definitions, is_actually_offered=True
    )
    alternative_recommendations = to_alternative_course_recommendation_items(
        assignments, major_label, trait_definitions
    )

    # 결정론적 정렬 — core → explore → alternative, 나머지는 이미 결정론적으로 만들어진
    # 순서(compute_subject_recommendations)를 그대로 이어 붙인 것이라 다시 섞지 않는다.
    # kept_recommendations는 이미 core(점수 내림차순) → explore(점수 내림차순) 순서다
    # (kept_core/kept_explore가 compute_subject_recommendations의 정렬된 출력에서 뽑은
    # 부분집합이므로). alternative_recommendations는 missing_core를 순회한 순서(그
    # 자체가 이미 core 점수 내림차순)라 그 상대 순서도 이미 결정론적이다 — 그래서
    # category만 기준으로 안정 정렬(stable sort)하면 각 category 내부 순서를 다시
    # subject_id로 섞지 않고 그대로 보존한다(점수를 API에 노출하지 않으면서도 순서는
    # 점수 기반을 유지한다).
    category_order: dict[str, int] = {"core": 0, "explore": 1, "alternative": 2}
    recommendations = sorted(
        kept_recommendations + alternative_recommendations,
        key=lambda item: category_order[item.category],
    )

    return recommendations, unavailable
