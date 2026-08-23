"""v2 CoursePlanningService — 2026-08-23 Trait Ontology v2(2.6단계) §8/§9.

`src/services/course_planning_service.py`(Legacy)와 같은 책임 분리 원칙을 따른다.
§9 "PRE_SURVEY/POST_OFFERING 흐름 불변" — 이 파일은 Legacy Service의 구조·엔드포인트
계약을 바꾸지 않고, PRIMARY Flag가 켜졌을 때만 쓰는 **별도의 PRE_SURVEY 경로**를
추가한다. POST_OFFERING(학교 실제 개설과목 업로드 이후 재추천)은 이번 Vertical Slice
E2E 범위 밖이라 아직 v2로 옮기지 않았다 — Legacy 경로를 그대로 쓴다(§18 한계로 보고).

`selected_major_id` 검증은 Legacy와 동일한 정신(Vertical Slice 대표 전공 3개 중 하나,
이 세션의 실제 v2 전공 추천 결과에 있어야 함)을 v2 입력으로 다시 구현한다 — Legacy
`validate_selectable_major()`는 `state.trait_summaries`(Legacy)를 요구하므로 그대로
재사용할 수 없다."""

from __future__ import annotations

from src.engines.matching_engine_v2 import compute_major_match_v2, rank_major_relevance_v2
from src.engines.subject_matching_engine import to_course_recommendation_items
from src.engines.subject_matching_engine_v2 import compute_subject_recommendations_v2
from src.repositories.protocols import SubjectRepository
from src.schemas.assessment_state import AssessmentState
from src.schemas.course import CourseProfile
from src.schemas.major import MajorProfile
from src.schemas.trait import TraitDefinition
from src.schemas.trait_vector_snapshot import TraitVectorEntry


class MajorNotSelectableErrorV2(ValueError):
    pass


class CourseEvidenceNotReadyErrorV2(ValueError):
    pass


class CoursePlanningServiceV2:
    def __init__(
        self,
        subject_repository: SubjectRepository,
        major_profiles: list[MajorProfile],
        trait_definitions: dict[str, TraitDefinition],
    ) -> None:
        self._subject_repository = subject_repository
        self._major_profiles = major_profiles
        self._major_by_id = {m.major_id: m for m in major_profiles}
        self._selectable_major_ids = frozenset(m.major_id for m in major_profiles)

    @property
    def selectable_major_ids(self) -> frozenset[str]:
        return self._selectable_major_ids

    def validate_selectable_major(
        self, snapshot_entries: dict[str, TraitVectorEntry], selected_major_id: str
    ) -> None:
        if selected_major_id not in self._selectable_major_ids:
            raise MajorNotSelectableErrorV2(
                f"selected_major_id {selected_major_id!r}는 v2 Vertical Slice 대표 전공 3개"
                f"({sorted(self._selectable_major_ids)}) 중 하나가 아닙니다."
            )

        major_results = [compute_major_match_v2(snapshot_entries, m) for m in self._major_profiles]
        if not any(r.status == "computed" for r in major_results):
            raise CourseEvidenceNotReadyErrorV2(
                "아직 어느 대표 전공도 v2 관련도를 계산할 만큼 검수된 답변 근거가 쌓이지 "
                "않았습니다. 질문에 조금 더 답한 뒤 다시 시도하세요."
            )

        labels_by_major_id = {m.major_id: m.label for m in self._major_profiles}
        relevant, explore_together, _message = rank_major_relevance_v2(major_results, labels_by_major_id)
        recommended_major_ids = {r.major_id for r in relevant} | {r.major_id for r in explore_together}
        if selected_major_id not in recommended_major_ids:
            raise MajorNotSelectableErrorV2(
                f"selected_major_id {selected_major_id!r}는 이 세션의 실제 v2 전공 추천 결과에 "
                "포함돼 있지 않습니다."
            )

    def build_pre_survey_course_profile_v2(
        self,
        state: AssessmentState,
        selected_major_id: str,
        snapshot_entries: dict[str, TraitVectorEntry],
        trait_definitions: dict[str, TraitDefinition],
    ) -> CourseProfile:
        self.validate_selectable_major(snapshot_entries, selected_major_id)

        candidate_subjects = self._subject_repository.related_to_major(selected_major_id)
        subject_results = compute_subject_recommendations_v2(
            snapshot_entries, selected_major_id, candidate_subjects
        )
        major_label = self._major_by_id[selected_major_id].label
        # to_course_recommendation_items()는 결과 타입의 필드(usable_trait_ids/
        # activity_summary/label)만 보고 동작하므로 Legacy 함수를 그대로 재사용한다
        # (이유 문구 생성 로직을 중복하지 않는다).
        recommendations = to_course_recommendation_items(subject_results, major_label, trait_definitions)

        return CourseProfile(
            session_id=state.session_id, source="PRE_SURVEY", recommendations=recommendations,
            unresolved_candidates=[], unavailable_subjects=[],
        )
