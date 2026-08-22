"""CoursePlanningService — A 소유 통합 계층, 2026-08-24 14차/2026-08-26 16차 리뷰, 설계안 §20 보조.

`src/services/major_exploration_service.py`(7차 리뷰)와 같은 위치의 서비스다. 전체 흐름:

    검사 답변 → Career Profile 근거(Trait 상태) → 학생이 선택한 대표 전공
    → PRE_SURVEY 희망과목 추천 → 학교 개설과목 업로드·확인(CourseDocumentParsingService)
    → POST_OFFERING 최종 재추천

CLAUDE.md 책임 분리:
- Repository(`SubjectRepository`)는 데이터 조회만 한다.
- Engine(`src.engines.subject_matching_engine`)은 순수 계산만 한다.
- 이 Service는 "어떤 조건이면 거부하고, 무엇을 조합해 최종 결과를 만들지"만 담당한다.
- FastAPI(`src.api.main`)는 요청·응답 변환만 한다.

`selected_major_id`는 이 Service의 메서드 인자로만 흐른다 — `AssessmentState`에도,
Assessment Planner 입력에도 저장하지 않는다(CLAUDE.md "Assessment 단계에서 전공 추천
결과나 성적을 Planner 입력으로 사용하지 않는다" — 반대 방향도 마찬가지로 지킨다.
`src/engines/policy_guard.py::guard_no_major_signal_in_assessment_state`가 이를 구조적으로
검증한다). 업로드·확인 상태는 `CoursePlanningSessionState`(별도 Store,
`src/memory/course_planning_store.py`)에 저장한다 — AssessmentState와 완전히 분리된다.
"""

from __future__ import annotations

from src.engines.matching_engine import (
    StudentTraitState,
    compute_major_match,
    compute_student_trait_states,
    rank_major_relevance,
)
from src.engines.policy_guard import guard_offered_status_matches_core_category, guard_subject_must_be_offered
from src.engines.subject_matching_engine import (
    compute_post_offering_recommendations,
    compute_subject_recommendations,
    to_course_recommendation_items,
)
from src.memory.course_planning_store import CoursePlanningStore
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
        course_planning_store: CoursePlanningStore,
    ) -> None:
        self._subject_repository = subject_repository
        self._major_profiles = major_profiles
        self._major_by_id = {m.major_id: m for m in major_profiles}
        self._trait_definitions = trait_definitions
        self._course_planning_store = course_planning_store
        # §5(15차)/§2(16차): "selected_major_id는 Vertical Slice 대표 전공 3개 중
        # 하나여야 함" — major_profiles에서 그대로 파생시킨다(별도로 하드코딩하지
        # 않는다. design 등 추천 제외 전공은 애초에 VERTICAL_SLICE_MAJOR_PROFILES에
        # 없으므로 자동으로 이 집합 밖이다).
        self._selectable_major_ids = frozenset(m.major_id for m in major_profiles)

    @property
    def selectable_major_ids(self) -> frozenset[str]:
        return self._selectable_major_ids

    def validate_selectable_major(
        self, state: AssessmentState, selected_major_id: str
    ) -> dict[str, StudentTraitState]:
        """2026-08-25 15차 리뷰 §2를 그대로 재사용한다(2026-08-26 16차 리뷰: PRE_SURVEY
        조회뿐 아니라 POST /course/upload도 "이 학생에게 이 전공으로 과목을 추천해도
        되는가"를 똑같이 검증해야 해서 별도 공개 메서드로 뺐다 — 두 곳이 같은 검증
        로직을 복제하지 않는다).

        검증 순서:
        1. Trait Summary 자체가 있는지
        2. selected_major_id가 Vertical Slice 대표 전공 3개 중 하나인지
        3. 전공 매칭 결과 중 `status == "computed"`가 하나라도 있는지
        4. (3이 전부 insufficient라면) → EVIDENCE_NOT_READY
        5. (computed가 하나라도 있다면) selected_major_id가 그 computed 결과 중 실제
           추천 목록에 있는지 → 없으면 MAJOR_NOT_SELECTABLE

        성공하면 이후 과목 매칭에 바로 쓸 수 있는 `student_states`를 반환한다(호출부가
        같은 계산을 다시 하지 않아도 된다). 오류 메시지에는 학생 답변 원문이나 내부
        점수를 절대 담지 않는다."""

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

        return student_states

    def build_pre_survey_course_profile(
        self, state: AssessmentState, selected_major_id: str
    ) -> CourseProfile:
        student_states = self.validate_selectable_major(state, selected_major_id)

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
            unavailable_subjects=[],
        )

    def build_post_offering_course_profile(
        self,
        state: AssessmentState,
        selected_major_id: str,
        confirmed_offered_subject_ids: set[str],
    ) -> CourseProfile:
        """2026-08-26 16차 리뷰 §7/§8. `selected_major_id`는 여기서도 다시 검증한다
        (POST /course/confirm 시점의 학생 Evidence·전공 추천 결과가 업로드 시점과 달라질
        일은 사실상 없지만 — Evidence는 계속 누적되기만 하고 이 요청들 사이에 답변이
        추가로 제출될 일은 없다 — 그래도 검증을 건너뛰지 않는다)."""

        student_states = self.validate_selectable_major(state, selected_major_id)

        candidate_subjects = self._subject_repository.related_to_major(selected_major_id)
        major_label = self._major_by_id[selected_major_id].label
        recommendations, unavailable_subjects = compute_post_offering_recommendations(
            student_states,
            selected_major_id,
            candidate_subjects,
            confirmed_offered_subject_ids,
            major_label,
            self._trait_definitions,
        )
        guard_offered_status_matches_core_category(recommendations, source="POST_OFFERING")
        guard_subject_must_be_offered(
            [r.subject_id for r in recommendations], confirmed_offered_subject_ids
        )

        return CourseProfile(
            session_id=state.session_id,
            source="POST_OFFERING",
            recommendations=recommendations,
            unresolved_candidates=[],
            unavailable_subjects=unavailable_subjects,
        )

    def get_course_profile(self, state: AssessmentState, selected_major_id: str) -> CourseProfile:
        """2026-08-26 16차 리뷰 §10: `GET /subjects/{session_id}?selected_major_id=...`가
        호출하는 진입점. 이 (session_id, selected_major_id) 조합으로 실제 확정
        (`upload_status == "CONFIRMED"`)된 CoursePlanningSessionState가 있으면
        POST_OFFERING 결과를, 없으면 기존 PRE_SURVEY 결과를 반환한다. 다른
        selected_major_id로 확정된 상태를 잘못 재사용하지 않는다(selected_major_id가
        정확히 일치해야만 POST_OFFERING 경로를 탄다) — 같은 입력에는 항상 같은 결과가
        나온다(매번 다시 계산하므로 캐시 불일치가 없다)."""

        planning_state = self._course_planning_store.load(state.session_id)
        if (
            planning_state is not None
            and planning_state.selected_major_id == selected_major_id
            and planning_state.upload_status == "CONFIRMED"
        ):
            return self.build_post_offering_course_profile(
                state, selected_major_id, set(planning_state.confirmed_offered_subject_ids)
            )
        return self.build_pre_survey_course_profile(state, selected_major_id)
