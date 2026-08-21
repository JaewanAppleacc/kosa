"""Similarity Matching Engine — 설계안 §16 순수 계산 로직. LLM·DB 호출 없음.

CLAUDE.md: "Assessment 단계에서 전공 추천 결과나 성적을 Planner 입력으로 사용하지 않는다"
— 이 파일은 그 반대 방향(Assessment 결과 → 전공 관련도)만 계산하고, 절대 Planner나
질문 생성 쪽으로 값을 되돌려보내지 않는다.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from src.engines.evidence_engine import judge_trait_state
from src.engines.trait_normalizer import normalize_trait_state
from src.schemas.evidence import TraitEvidenceSummary, TraitState
from src.schemas.major import EvidenceSufficiencyLabel, MajorProfile, MajorRelevance, RelevanceLabel
from src.schemas.trait import TraitDefinition

# §16: "가중치는 검증된 상수가 아니며 평가셋을 통해 조정한다" — 그대로 옮긴 MVP 초기값.
VECTOR_GROUP_WEIGHTS: dict[str, float] = {
    "interest": 0.35,
    "cognitive": 0.30,
    "work_style": 0.20,
    "environment": 0.15,
}

# §16 matching_policy — "검증된 값이 아니라 MVP 초기 휴리스틱"이라고 설계안이 명시한 그대로.
MINIMUM_USABLE_TRAITS = 3
MINIMUM_USABLE_VECTOR_GROUPS = 2

INSUFFICIENT_EVIDENCE_MESSAGE = "아직 관련도를 계산하기에 답변이 부족합니다. 추가 탐색이 필요합니다."

# 2026-08-21 리뷰: 순수 상대 순위만 쓰면 후보가 1개뿐일 때 그 점수가 아무리 낮아도 무조건
# 1등이라 "관련성 높음"이 돼버린다. 가중 Trait 충족도는 값이 전부 [0, 1] 범위이므로,
# 상대 순위 상위 구간이어도 이 절대 하한을 넘지 못하면 "관련성 높음"을 주지 않는다 —
# §16처럼 "검증된 임계값이 아니라 MVP 초기 휴리스틱"이다.
MINIMUM_SCORE_FOR_HIGH_RELEVANCE = 0.6


class StudentTraitState(BaseModel):
    """§13 상태 판정 결과 + 매칭용 정규화 값. state가 STRONG/MODERATE/LIMITED일 때만
    normalized_value가 채워진다(INSUFFICIENT/CONFLICTING은 Mask)."""

    trait_id: str
    state: TraitState
    normalized_value: float | None
    context_count: int
    primary_vector_group: str


def compute_student_trait_states(
    trait_summaries: dict[str, TraitEvidenceSummary],
    all_trait_definitions: dict[str, TraitDefinition],
    unresolved_conflict_trait_ids: set[str],
) -> dict[str, StudentTraitState]:
    """§13 상태 판정을 전체 Trait에 대해 한 번 계산해서 재사용한다(Profile 화면과 Matching이
    같은 판정 결과를 쓰게 하기 위함 — 서로 다른 곳에서 각자 판정하면 불일치가 생길 수 있다)."""

    result: dict[str, StudentTraitState] = {}
    for trait_id, trait_def in all_trait_definitions.items():
        summary = trait_summaries.get(trait_id) or TraitEvidenceSummary(trait_id=trait_id)
        judgment = judge_trait_state(
            summary, trait_def.minimum_context_count, trait_id in unresolved_conflict_trait_ids
        )
        result[trait_id] = StudentTraitState(
            trait_id=trait_id,
            state=judgment.state,
            normalized_value=normalize_trait_state(judgment.state),
            context_count=summary.context_count,
            primary_vector_group=trait_def.primary_vector_group,
        )
    return result


def _weighted_trait_coverage(student_values: list[float], major_weights: list[float]) -> float | None:
    """2026-08-21 리뷰로 cosine similarity를 교체한 공식.

    cosine similarity는 크기(magnitude)를 무시하고 방향(비율)만 본다 — 학생이 [0.33, 0.33]
    (LIMITED)이든 [1.00, 1.00](STRONG)이든 전공 [1.00, 1.00]과의 cosine은 둘 다 1.0으로
    같았다. 실제로는 LIMITED 학생이 STRONG 학생과 같은 정도로 그 전공에 맞는다고 볼 수
    없으므로, "전공이 중요하게 보는 Trait를 학생이 얼마나 충족하는가"를 그대로 재는 가중
    평균(충족도)으로 바꾼다: Σ(전공 가중치 × 학생 정규화 값) ÷ Σ(전공 가중치).

    이 공식은 항목이 1개뿐이어도(1차원) 의미가 있다 — 결과가 그 학생의 정규화 값 자체가
    되므로(가중치로 나눠도 비율은 그대로), cosine처럼 "1개면 무조건 1.0" 축퇴가 없다.
    그래서 예전의 MINIMUM_TRAITS_PER_VECTOR_GROUP(그룹당 최소 2개 Trait) 제약은 더 이상
    필요 없어 제거했다."""

    total_weight = sum(major_weights)
    if total_weight == 0:
        return None
    return sum(s * w for s, w in zip(student_values, major_weights)) / total_weight


class MajorMatchResult(BaseModel):
    major_id: str
    status: Literal["computed", "insufficient"]
    score: float | None = None  # 후보군 내 정렬에만 쓰는 내부 값. 사용자 화면에 노출 금지(§16).
    usable_trait_count: int = 0
    notable_strong_count: int = 0  # 이 전공이 중요하게 보는 Trait 중 STRONG인 개수(Evidence 충분성용)
    notable_usable_count: int = 0  # 이 전공이 중요하게 보는 Trait 중 학생이 확정한 개수
    max_context_count_among_notable: int = 0


def compute_major_match(
    student_states: dict[str, StudentTraitState], major: MajorProfile
) -> MajorMatchResult:
    """§16: Vector 그룹별 가중 Trait 충족도(_weighted_trait_coverage)를 다시 가중합한다.
    전공 벡터에서 가중치가 0보다 큰 항목만, 그리고 학생 쪽에서 확정(non-Mask)된 Trait만
    분자·분모 양쪽에 넣는다. 그룹당 최소 개수 제약은 없다 — 가중 충족도는 Trait 1개뿐인
    그룹(Vertical Slice의 interest·environment)에서도 크기를 반영해 의미 있게 계산된다."""

    vector_by_group = {
        "interest": major.interest_vector,
        "cognitive": major.cognitive_vector,
        "work_style": major.work_style_vector,
        "environment": major.environment_vector,
    }

    group_coverages: dict[str, float] = {}
    usable_trait_ids: set[str] = set()

    for group, major_vector in vector_by_group.items():
        shared_trait_ids = sorted(
            t for t, weight in major_vector.items()
            if weight > 0
            and t in student_states
            and student_states[t].normalized_value is not None
        )
        if not shared_trait_ids:
            continue
        student_values = [student_states[t].normalized_value for t in shared_trait_ids]  # type: ignore[misc]
        major_weights = [major_vector[t] for t in shared_trait_ids]
        coverage = _weighted_trait_coverage(student_values, major_weights)
        if coverage is None:
            continue
        group_coverages[group] = coverage
        usable_trait_ids.update(shared_trait_ids)

    usable_vector_group_count = len(group_coverages)
    usable_trait_count = len(usable_trait_ids)

    # "이 전공이 중요하게 보는 Trait"(가중치 0.67 이상, §15 "자주 활용" 이상) 중 학생이
    # 확정한 것만으로 Evidence 충분성·반복 관찰 Context를 판단한다 — 전공마다 다른 결과가
    # 나오게 하기 위함이다(모든 전공이 같은 12개 Trait를 다 정의해두면, 단순 교집합만으로는
    # 전공별 차이가 안 드러난다).
    notable_trait_ids = {t for group in vector_by_group.values() for t, w in group.items() if w >= 0.67}
    notable_usable = [
        student_states[t] for t in notable_trait_ids
        if t in student_states and student_states[t].normalized_value is not None
    ]
    notable_strong_count = sum(1 for s in notable_usable if s.state == TraitState.STRONG)
    max_context_count = max((s.context_count for s in notable_usable), default=0)

    if usable_trait_count < MINIMUM_USABLE_TRAITS or usable_vector_group_count < MINIMUM_USABLE_VECTOR_GROUPS:
        return MajorMatchResult(major_id=major.major_id, status="insufficient", usable_trait_count=usable_trait_count)

    total_weight = sum(VECTOR_GROUP_WEIGHTS[g] for g in group_coverages)
    score = sum(VECTOR_GROUP_WEIGHTS[g] * cov for g, cov in group_coverages.items()) / total_weight

    return MajorMatchResult(
        major_id=major.major_id,
        status="computed",
        score=score,
        usable_trait_count=usable_trait_count,
        notable_strong_count=notable_strong_count,
        notable_usable_count=len(notable_usable),
        max_context_count_among_notable=max_context_count,
    )


def _evidence_sufficiency_label(result: MajorMatchResult) -> EvidenceSufficiencyLabel:
    # MVP 초기 휴리스틱 — §16처럼 검증된 임계값이 아니다.
    if result.notable_strong_count >= 2:
        return "충분"
    if result.notable_usable_count >= 2:
        return "보통"
    return "제한적"


def rank_major_relevance(
    results: list[MajorMatchResult], labels_by_major_id: dict[str, str]
) -> tuple[list[MajorRelevance], list[MajorRelevance], str | None]:
    """§16 "내부에서는 후보군 내 분포... 기준으로 상대 순위를 계산한다"를 구현한다.

    2026-08-21 리뷰로 두 가지를 고쳤다:
    1. 등수(rank, 0/1/2/...)가 아니라 "고유한 점수 값의 순서"로 구간을 나눈다. 등수 기준이면
       점수가 완전히 같은 두 전공도 앞뒤로 갈려서 서로 다른 등급을 받을 수 있었다(임의의
       우열) — 점수가 같으면 항상 같은 구간에 들어가게 했다.
    2. 절대 점수 하한(MINIMUM_SCORE_FOR_HIGH_RELEVANCE)을 추가로 요구한다. 안 그러면 후보가
       1개뿐이거나 전부 낮은 점수여도 상위 구간은 무조건 "관련성 높음"이 돼버린다.

    반환값: (관련성 높음 목록, 나머지 목록, 전체가 insufficient일 때의 안내 메시지)."""

    computed = [r for r in results if r.status == "computed"]
    if not computed:
        return [], [], INSUFFICIENT_EVIDENCE_MESSAGE

    computed.sort(key=lambda r: (-r.score, r.major_id))  # type: ignore[arg-type]  # major_id는 표시 순서만 결정, 등급에는 안 씀

    unique_scores_desc = sorted({r.score for r in computed}, reverse=True)  # type: ignore[arg-type]

    def relevance_label_for_score(score: float) -> RelevanceLabel:
        # 점수가 같은 후보는 항상 같은 구간(고유 점수 목록에서의 위치로 구간 결정).
        score_rank = unique_scores_desc.index(score)
        tier = (score_rank * 3) // len(unique_scores_desc)
        label = ["관련성 높음", "함께 탐색해볼 분야", "비교해볼 만한 분야"][min(tier, 2)]
        if label == "관련성 높음" and score < MINIMUM_SCORE_FOR_HIGH_RELEVANCE:
            # 상대 순위는 1등이어도 절대 유사도가 낮으면 "관련성 높음"을 주지 않는다
            # (후보가 1개뿐이거나 전부 낮은 점수인 경우의 방어).
            label = "함께 탐색해볼 분야"
        return label

    relevant: list[MajorRelevance] = []
    explore_together: list[MajorRelevance] = []

    for result in computed:
        relevance = relevance_label_for_score(result.score)  # type: ignore[arg-type]
        item = MajorRelevance(
            major_id=result.major_id,
            label=labels_by_major_id.get(result.major_id, result.major_id),
            relevance_label=relevance,
            evidence_sufficiency=_evidence_sufficiency_label(result),
            repeated_context_count=result.max_context_count_among_notable,
        )
        if relevance == "관련성 높음":
            relevant.append(item)
        else:
            explore_together.append(item)

    return relevant, explore_together, None
