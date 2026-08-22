"""CoursePlanningService — A 소유 통합 계층, 2026-08-24 14차 리뷰, 설계안 §20 보조.

`src/services/major_exploration_service.py`(7차 리뷰)와 같은 위치의 서비스다. 다음
흐름 하나를 완성한다:

    검사 답변 → Career Profile 근거(Trait 상태) → 학생이 선택한 대표 전공
    → 그 전공과 공식적으로 연결된 과목 → PRE_SURVEY 과목 추천

CLAUDE.md 책임 분리:
- Repository(`SubjectRepository`)는 데이터 조회만 한다.
- Engine(`src.engines.subject_matching_engine`)은 순수 계산만 한다.
- 이 Service는 "어떤 조건이면 거부하고, 무엇을 조합해 최종 결과를 만들지"만 담당한다.
- FastAPI(`src.api.main`)는 요청·응답 변환만 한다.

2026-08-24: `selected_major_id`는 이 Service의 메서드 인자로만 흐른다 — `AssessmentState`
에도, Assessment Planner 입력에도 저장하지 않는다(CLAUDE.md "Assessment 단계에서 전공
추천 결과나 성적을 Planner 입력으로 사용하지 않는다" — 반대 방향도 마찬가지로 지킨다.
`src/engines/policy_guard.py::guard_no_major_signal_in_assessment_state`가 이를 구조적으로
검증한다). 이 흐름에 "전공 선택 상태"를 세션 간에 들고 다닐 필요가 생기면, 그때는
AssessmentState가 아니라 이 모듈에 별도의 CoursePlanningState를 추가한다 — 지금은
FastAPI가 매 요청마다 Query Parameter로 `selected_major_id`를 그대로 전달하는 것만으로
충분해서(무상태 GET) 별도 저장소를 만들지 않았다.
"""

from __future__ import annotations

from src.engines.matching_engine import (
    compute_major_match,
    compute_student_trait_states,
    rank_major_relevance,
)
from src.engines.policy_guard import guard_offered_status_matches_core_category
from src.engines.subject_matching_engine import (
    compute_subject_recommendations,
    to_course_recommendation_items,
)
from src.repositories.protocols import SubjectRepository
from src.schemas.assessment_state import AssessmentState
from src.schemas.course import CourseProfile
from src.schemas.major import MajorProfile
from src.schemas.trait import TraitDefinition


class MajorNotSelectableError(ValueError):
    """selected_major_id가 미등록/추천 제외 전공이거나, 이 세션의 실제 전공 추천
    결과(관련성 높음/함께 탐색해볼 분야)에 없을 때."""


class CourseEvidenceNotReadyError(ValueError):
    """학생 Evidence가 과목 추천을 계산하기에 아직 부족할 때(§5 "학생 Evidence가 과목
    추천에 충분해야 함")."""


class CoursePlanningService:
    def __init__(
        self,
        subject_repository: SubjectRepository,
        major_profiles: list[MajorProfile],
        trait_definitions: dict[str, TraitDefinition],
    ) -> None:
        self._subject_repository = subject_repository
        self._major_profiles = major_profiles
        self._major_by_id = {m.major_id: m for m in major_profiles}
        self._trait_definitions = trait_definitions
        # §5: "selected_major_id는 Vertical Slice 대표 전공 3개 중 하나여야 함" —
        # major_profiles에서 그대로 파생시킨다(별도로 하드코딩하지 않는다. design 등
        # 추천 제외 전공은 애초에 VERTICAL_SLICE_MAJOR_PROFILES에 없으므로 자동으로
        # 이 집합 밖이다).
        self._selectable_major_ids = frozenset(m.major_id for m in major_profiles)

    def build_course_profile(self, state: AssessmentState, selected_major_id: str) -> CourseProfile:
        """2026-08-25 15차 리뷰 §2: 검증 순서를 두 종류의 "안 된다"로 명확히 나눈다.

        (세션 존재는 호출부의 `_get_state_or_404`가 이미 처리했다는 전제)
        1. Trait Summary 자체가 있는지
        2. selected_major_id가 Vertical Slice 대표 전공 3개 중 하나인지
        3. 전공 매칭 결과 중 `status == "computed"`가 하나라도 있는지
        4. (3이 전부 insufficient라면) → EVIDENCE_NOT_READY — "Evidence가 있긴 하지만
           어느 전공도 판단하기엔 부족하다"는, selected_major_id의 문제가 아니라
           **근거 자체가 부족한 상황**이라 예전처럼 MAJOR_NOT_SELECTABLE로 잘못
           분류하면 안 된다.
        5. (computed가 하나라도 있다면) selected_major_id가 그 computed 결과 중 실제
           추천 목록(관련성 높음/함께 탐색해볼 분야)에 있는지 → 없으면 MAJOR_NOT_SELECTABLE
           — 이번엔 진짜로 "이 전공은 이 학생에게 추천되지 않았다"는 뜻이다.

        정리: "전공을 판단할 Evidence 자체가 부족함" → EVIDENCE_NOT_READY,
        "Evidence는 충분하지만 이 학생에게 추천되지 않은 전공을 선택함" → MAJOR_NOT_SELECTABLE.
        오류 메시지에는 학생 답변 원문이나 내부 점수를 절대 담지 않는다."""

        if not state.trait_summaries:
            raise CourseEvidenceNotReadyError(
                "아직 답변이 없어 과목을 추천할 Evidence가 없습니다. 먼저 "
                "/assessment/next-question과 /assessment/answer로 최소 1개 이상 답변한 뒤 "
                "다시 호출하세요."
            )

        if selected_major_id not in self._selectable_major_ids:
            raise MajorNotSelectableError(
                f"selected_major_id {selected_major_id!r}는 Vertical Slice 대표 전공 3개"
                f"({sorted(self._selectable_major_ids)}) 중 하나가 아닙니다."
            )

        student_states = compute_student_trait_states(
            state.trait_summaries,
            self._trait_definitions,
            unresolved_conflict_trait_ids=state.unresolved_conflict_trait_ids,
            resolutions=state.contrast_resolutions,
        )
        major_results = [compute_major_match(student_states, m) for m in self._major_profiles]

        if not any(r.status == "computed" for r in major_results):
            raise CourseEvidenceNotReadyError(
                "아직 어느 대표 전공도 관련도를 계산할 만큼 답변 근거가 쌓이지 않았습니다. "
                "질문에 조금 더 답한 뒤 다시 시도하세요."
            )

        labels_by_major_id = {m.major_id: m.label for m in self._major_profiles}
        relevant, explore_together, _message = rank_major_relevance(major_results, labels_by_major_id)
        recommended_major_ids = {r.major_id for r in relevant} | {r.major_id for r in explore_together}

        if selected_major_id not in recommended_major_ids:
            raise MajorNotSelectableError(
                f"selected_major_id {selected_major_id!r}는 이 세션의 실제 전공 추천 결과에 "
                "포함돼 있지 않습니다 — 학생 답변 근거상 이 전공을 추천받지 않았습니다."
            )

        candidate_subjects = self._subject_repository.related_to_major(selected_major_id)
        subject_results = compute_subject_recommendations(
            student_states, selected_major_id, candidate_subjects
        )
        major_label = self._major_by_id[selected_major_id].label
        recommendations = to_course_recommendation_items(
            subject_results, major_label, self._trait_definitions
        )
        guard_offered_status_matches_core_category(recommendations, source="PRE_SURVEY")

        return CourseProfile(
            session_id=state.session_id,
            source="PRE_SURVEY",
            recommendations=recommendations,
            unresolved_candidates=[],
        )
