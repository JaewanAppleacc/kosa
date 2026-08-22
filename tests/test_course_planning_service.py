"""CoursePlanningService 단위 테스트 — Fake SubjectRepository 주입, 2026-08-24 14차 리뷰 §8."""

from __future__ import annotations

import unittest

from src.data.majors.vertical_slice_major_profiles import VERTICAL_SLICE_MAJOR_PROFILES
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAITS
from src.schemas.assessment_state import AssessmentState
from src.schemas.course import SubjectProfile
from src.schemas.evidence import TraitEvidenceSummary
from src.memory.course_planning_store import InMemoryCoursePlanningStore
from src.services.course_planning_service import (
    CourseEvidenceNotReadyError,
    CoursePlanningService,
    MajorNotSelectableError,
)

_TRAIT_DEFS = {t.trait_id: t for t in VERTICAL_SLICE_TRAITS}


class FakeSubjectRepository:
    """§8 "테스트에서는 Fake Repository를 주입할 수 있어야 한다" — Protocol만 만족하면
    JsonlSubjectRepository가 아니어도 CoursePlanningService가 그대로 동작해야 한다."""

    def __init__(self, subjects: list[SubjectProfile]) -> None:
        self._subjects = subjects

    def all(self) -> list[SubjectProfile]:
        return list(self._subjects)

    def related_to_major(self, major_id: str) -> list[SubjectProfile]:
        return [s for s in self._subjects if major_id in s.related_major_ids]

    def get(self, subject_id: str) -> SubjectProfile | None:
        return next((s for s in self._subjects if s.subject_id == subject_id), None)


def _strong(trait_id: str) -> TraitEvidenceSummary:
    return TraitEvidenceSummary(
        trait_id=trait_id, support_count=3, opportunity_count=3, context_count=2, distinct_frame_count=2
    )


def _state_with_persona(strong: set[str]) -> AssessmentState:
    summaries = {}
    for t in _TRAIT_DEFS:
        summaries[t] = _strong(t) if t in strong else TraitEvidenceSummary(trait_id=t, support_count=0, opportunity_count=0)
    return AssessmentState(session_id="sess_test", user_id="user_test", trait_summaries=summaries)


class CoursePlanningServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fake_subject = SubjectProfile(
            subject_id="subj_fake_ie", label="가짜 산업공학 과목",
            trait_vector={"causal_analysis": 1.0, "pattern_finding": 1.0},
            related_major_ids=["industrial_engineering"], source_id="https://example.moe.go.kr/",
        )
        self.repository = FakeSubjectRepository([self.fake_subject])
        self.service = CoursePlanningService(
            self.repository, major_profiles=VERTICAL_SLICE_MAJOR_PROFILES, trait_definitions=_TRAIT_DEFS,
            course_planning_store=InMemoryCoursePlanningStore(),
        )

    def test_no_evidence_raises_course_evidence_not_ready(self) -> None:
        state = AssessmentState(session_id="sess_empty", user_id="user_test")
        with self.assertRaises(CourseEvidenceNotReadyError):
            self.service.build_pre_survey_course_profile(state, "industrial_engineering")

    def test_unregistered_major_raises_major_not_selectable(self) -> None:
        state = _state_with_persona({"causal_analysis", "pattern_finding", "information_comparison", "planning"})
        with self.assertRaises(MajorNotSelectableError):
            self.service.build_pre_survey_course_profile(state, "no_such_major")

    def test_design_is_not_selectable(self) -> None:
        state = _state_with_persona({"causal_analysis", "pattern_finding", "information_comparison", "planning"})
        with self.assertRaises(MajorNotSelectableError):
            self.service.build_pre_survey_course_profile(state, "design")

    def test_all_majors_insufficient_raises_evidence_not_ready_not_major_not_selectable(self) -> None:
        """2026-08-25 15차 리뷰 §2: tool_utilization 하나만 강하면 세 전공 모두 insufficient
        (computed가 하나도 없음) — 이건 selected_major_id의 문제가 아니라 Evidence 자체가
        부족한 상황이라 EVIDENCE_NOT_READY여야 한다(예전엔 MAJOR_NOT_SELECTABLE로 잘못
        분류됐다)."""

        state = _state_with_persona({"tool_utilization"})
        with self.assertRaises(CourseEvidenceNotReadyError):
            self.service.build_pre_survey_course_profile(state, "industrial_engineering")

    def test_some_majors_computed_but_selected_one_is_insufficient_raises_major_not_selectable(self) -> None:
        """§2: media_communication/industrial_engineering은 computed인데 hci_ux만
        insufficient인 Persona — 이번엔 진짜로 "이 전공은 이 학생에게 추천되지 않았다"는
        뜻이라 MAJOR_NOT_SELECTABLE이어야 한다."""

        state = _state_with_persona(
            {"causal_analysis", "pattern_finding", "information_comparison", "planning"}
        )
        with self.assertRaises(MajorNotSelectableError):
            self.service.build_pre_survey_course_profile(state, "hci_ux")

    def test_fake_repository_is_used_for_subject_lookup(self) -> None:
        state = _state_with_persona({"causal_analysis", "pattern_finding", "information_comparison", "planning"})
        profile = self.service.build_pre_survey_course_profile(state, "industrial_engineering")
        self.assertEqual(profile.session_id, "sess_test")
        self.assertEqual(profile.source, "PRE_SURVEY")
        self.assertEqual([r.subject_id for r in profile.recommendations], ["subj_fake_ie"])
        self.assertIsNone(profile.recommendations[0].is_actually_offered)

    def test_selected_major_id_is_not_written_back_into_assessment_state(self) -> None:
        """§5: selected_major_id를 AssessmentState 어디에도 저장하지 않는다."""

        state = _state_with_persona({"causal_analysis", "pattern_finding", "information_comparison", "planning"})
        before = state.model_dump()
        self.service.build_pre_survey_course_profile(state, "industrial_engineering")
        after = state.model_dump()
        self.assertEqual(before, after, "CoursePlanningService가 AssessmentState를 변형했다")

    def test_post_offering_recommendations_are_all_marked_actually_offered(self) -> None:
        state = _state_with_persona({"causal_analysis", "pattern_finding", "information_comparison", "planning"})
        profile = self.service.build_post_offering_course_profile(
            state, "industrial_engineering", {"subj_fake_ie"}
        )
        self.assertEqual(profile.source, "POST_OFFERING")
        self.assertTrue(profile.recommendations)
        for item in profile.recommendations:
            self.assertIs(item.is_actually_offered, True)

    def test_post_offering_marks_unavailable_when_not_offered(self) -> None:
        state = _state_with_persona({"causal_analysis", "pattern_finding", "information_comparison", "planning"})
        profile = self.service.build_post_offering_course_profile(
            state, "industrial_engineering", set()  # 아무것도 개설 안 됨
        )
        self.assertEqual(profile.recommendations, [])
        self.assertEqual([u.subject_id for u in profile.unavailable_subjects], ["subj_fake_ie"])


class GetCourseProfileStateRestorationTest(unittest.TestCase):
    """2026-08-26 16차 리뷰 §10: GET /subjects 재조회 시 CONFIRMED 상태 여부에 따라
    PRE_SURVEY/POST_OFFERING을 정확히 분기하는지 확인."""

    def setUp(self) -> None:
        self.fake_subject = SubjectProfile(
            subject_id="subj_fake_ie", label="가짜 산업공학 과목",
            trait_vector={"causal_analysis": 1.0, "pattern_finding": 1.0},
            related_major_ids=["industrial_engineering"], source_id="https://example.moe.go.kr/",
        )
        self.repository = FakeSubjectRepository([self.fake_subject])
        self.store = InMemoryCoursePlanningStore()
        self.service = CoursePlanningService(
            self.repository, major_profiles=VERTICAL_SLICE_MAJOR_PROFILES, trait_definitions=_TRAIT_DEFS,
            course_planning_store=self.store,
        )
        self.state = _state_with_persona(
            {"causal_analysis", "pattern_finding", "information_comparison", "planning"}
        )

    def test_no_planning_state_returns_pre_survey(self) -> None:
        profile = self.service.get_course_profile(self.state, "industrial_engineering")
        self.assertEqual(profile.source, "PRE_SURVEY")

    def test_confirmed_planning_state_returns_post_offering(self) -> None:
        from src.schemas.course import CoursePlanningSessionState

        self.store.save(
            CoursePlanningSessionState(
                session_id=self.state.session_id, selected_major_id="industrial_engineering",
                confirmed_offered_subject_ids=["subj_fake_ie"], upload_status="CONFIRMED",
            )
        )
        profile = self.service.get_course_profile(self.state, "industrial_engineering")
        self.assertEqual(profile.source, "POST_OFFERING")

    def test_unconfirmed_planning_state_still_returns_pre_survey(self) -> None:
        """업로드는 했지만 아직 /course/confirm을 안 거쳤으면 여전히 PRE_SURVEY다."""

        from src.schemas.course import CoursePlanningSessionState

        self.store.save(
            CoursePlanningSessionState(
                session_id=self.state.session_id, selected_major_id="industrial_engineering",
                upload_status="CONFIRMATION_REQUIRED",
            )
        )
        profile = self.service.get_course_profile(self.state, "industrial_engineering")
        self.assertEqual(profile.source, "PRE_SURVEY")

    def test_confirmed_for_different_major_does_not_leak_into_this_major(self) -> None:
        """다른 selected_major_id로 확정된 상태를 잘못 재사용하지 않는다."""

        from src.schemas.course import CoursePlanningSessionState

        self.store.save(
            CoursePlanningSessionState(
                session_id=self.state.session_id, selected_major_id="media_communication",
                confirmed_offered_subject_ids=["subj_fake_ie"], upload_status="CONFIRMED",
            )
        )
        profile = self.service.get_course_profile(self.state, "industrial_engineering")
        self.assertEqual(profile.source, "PRE_SURVEY")

    def test_repeated_query_after_confirmation_is_identical(self) -> None:
        """§10: 같은 입력에는 항상 같은 결과가 나와야 한다(캐시 불일치 없음)."""

        from src.schemas.course import CoursePlanningSessionState

        self.store.save(
            CoursePlanningSessionState(
                session_id=self.state.session_id, selected_major_id="industrial_engineering",
                confirmed_offered_subject_ids=["subj_fake_ie"], upload_status="CONFIRMED",
            )
        )
        first = self.service.get_course_profile(self.state, "industrial_engineering")
        second = self.service.get_course_profile(self.state, "industrial_engineering")
        self.assertEqual(first.model_dump(), second.model_dump())


if __name__ == "__main__":
    unittest.main()
