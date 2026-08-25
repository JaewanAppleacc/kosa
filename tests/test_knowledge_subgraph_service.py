"""KnowledgeSubgraphService 단위 테스트 — 2026-08-28 19차 리뷰 §12 "Service 단위 테스트".

실제 VERTICAL_SLICE_TRAITS/VERTICAL_SLICE_MAJOR_PROFILES(industrial_engineering)를 그대로
쓴다 — Trait Vector 구조·MINIMUM_USABLE_TRAITS(3)/MINIMUM_USABLE_VECTOR_GROUPS(2) 같은
실제 Matching Engine 임계값을 다시 만들지 않기 위함이다(`test_course_planning_service.py`
의 `_state_with_persona`와 같은 4-Trait Persona를 재사용한다). Major–Trait/Subject–Trait
Mapping Evidence, Department, Subject는 이 파일에서 직접 손으로 만든다(Fake Repository
주입) — 실제 data/master/*.jsonl 파일 내용에 테스트가 의존하지 않게 하기 위함이다.
"""

from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch

from src.data.majors.vertical_slice_major_profiles import VERTICAL_SLICE_MAJOR_PROFILES
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAITS
from src.memory.course_planning_store import InMemoryCoursePlanningStore
from src.schemas.assessment_state import AssessmentState
from src.schemas.course import CoursePlanningSessionState, SubjectProfile
from src.schemas.evidence import ContrastResolutionRecord, ContrastResolutionStatus, EvidenceOrigin, EvidenceRecord, TraitEvidenceSummary
from src.schemas.major import Department
from src.schemas.mcp_contracts import DepartmentSearchCriteria
from src.services.course_planning_service import CoursePlanningService
from src.services.knowledge_subgraph_service import (
    KnowledgeSubgraphService,
    SubgraphEvidenceNotReadyError,
)
from src.services.major_exploration_service import MajorExplorationService
from src.services.major_trait_mapping_evidence import MajorTraitCourseEvidence, MajorTraitMappingRecord
from src.services.subject_trait_mapping_evidence import (
    SubjectTraitCurriculumEvidence,
    SubjectTraitMappingRecord,
)

_TRAIT_DEFS = {t.trait_id: t for t in VERTICAL_SLICE_TRAITS}
_FIXED_DT = datetime(2026, 8, 28, 0, 0, 0)


# --- Fake Repository / Policy ---


class FakeSubjectRepository:
    def __init__(self, subjects: list[SubjectProfile]) -> None:
        self._subjects = subjects

    def all(self) -> list[SubjectProfile]:
        return list(self._subjects)

    def related_to_major(self, major_id: str) -> list[SubjectProfile]:
        return [s for s in self._subjects if major_id in s.related_major_ids]

    def get(self, subject_id: str) -> SubjectProfile | None:
        return next((s for s in self._subjects if s.subject_id == subject_id), None)


class FakeDepartmentRepository:
    def __init__(self, departments: list[Department]) -> None:
        self._departments = departments

    def search(self, criteria: DepartmentSearchCriteria, limit: int = 30) -> list[Department]:
        results = [
            d
            for d in self._departments
            if criteria.canonical_major_id is None or d.canonical_major_id == criteria.canonical_major_id
        ]
        return results[:limit]

    def get(self, department_id: str) -> Department | None:
        return next((d for d in self._departments if d.department_id == department_id), None)


class SelectiveScopePolicy:
    """department_id가 이 집합에 있을 때만 승인 — Fail-Closed 우회 여부를 확인하는 테스트용."""

    def __init__(self, approved_department_ids: set[str]) -> None:
        self._approved = approved_department_ids

    def is_approved(self, department_id: str, canonical_major_id: str) -> bool:
        return department_id in self._approved


# --- 공통 fixture builder ---


def _strong(trait_id: str) -> TraitEvidenceSummary:
    return TraitEvidenceSummary(
        trait_id=trait_id, support_count=3, opportunity_count=3, context_count=2, distinct_frame_count=2
    )


def _insufficient(trait_id: str) -> TraitEvidenceSummary:
    return TraitEvidenceSummary(trait_id=trait_id, support_count=0, opportunity_count=0)


def _evidenced_major_trait(major_id: str, trait_id: str, grade: int) -> MajorTraitMappingRecord:
    return MajorTraitMappingRecord(
        major_id=major_id,
        trait_id=trait_id,
        mapping_status="EVIDENCED",
        grade=grade,
        evidence=[
            MajorTraitCourseEvidence(
                university_name="가짜대학교",
                department_name="가짜학과",
                evidence_type="OFFICIAL_CURRICULUM",
                course_or_goal="가짜 활동",
                source_url=f"https://major-evidence.example/{major_id}/{trait_id}",
                reason="테스트용 근거",
            )
        ],
        author_id="tester",
        mapping_version="major_trait_test_v1",
    )


def _review_required_major_trait(major_id: str, trait_id: str) -> MajorTraitMappingRecord:
    return MajorTraitMappingRecord(
        major_id=major_id,
        trait_id=trait_id,
        mapping_status="REVIEW_REQUIRED",
        author_id="tester",
        mapping_version="major_trait_test_v1",
    )


def _evidenced_subject_trait(subject_id: str, trait_id: str, grade: int) -> SubjectTraitMappingRecord:
    return SubjectTraitMappingRecord(
        subject_id=subject_id,
        trait_id=trait_id,
        mapping_status="EVIDENCED",
        grade=grade,
        curriculum_evidence=[
            SubjectTraitCurriculumEvidence(
                source_url=f"https://subject-evidence.example/{subject_id}/{trait_id}",
                source_type="공식 성취기준",
                course_goal_or_standard="가짜 성취기준",
                reason="테스트용 근거",
            )
        ],
        activity_summary="가짜 활동을 하는 활동",
        author_id="tester",
        mapping_version="subject_trait_test_v1",
    )


# industrial_engineering이 "computed"+"관련성 높음"에 도달하는 4-Trait Persona(round 14~17과
# 동일) — MINIMUM_USABLE_TRAITS(3)/MINIMUM_USABLE_VECTOR_GROUPS(2)를 만족한다
# (cognitive: causal_analysis/pattern_finding/information_comparison, work_style: planning).
_IE_CORE_TRAIT_IDS = {"causal_analysis", "pattern_finding", "planning", "information_comparison"}
# tool_utilization은 industrial_engineering의 environment_vector에도 값이 있지만(0.67),
# 아래 major_trait_records에는 일부러 EVIDENCED 레코드를 안 만든다 — "Vector 값은 0보다
# 크지만 Mapping Evidence가 EVIDENCED가 아닌" 상황을 재현하기 위함이다.
_EXTRA_TRAIT_ID = "tool_utilization"


def _evidence(evidence_id: str, trait_id: str, origin: EvidenceOrigin = EvidenceOrigin.PRIMARY_BLUEPRINT) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        answer_id=f"ans_{evidence_id}",
        question_id="q1",
        question_frame_id="frame1",
        option_role_id="role1",
        option_text="답변 예시",
        applied_primary_trait_delta={trait_id: 1},
        evidence_origin=origin,
        context="game",
        source_type="seed",
        generator_version="v1",
        quality_gate_status="passed",
    )


def _base_state(**overrides) -> AssessmentState:
    trait_summaries = {tid: _strong(tid) for tid in _IE_CORE_TRAIT_IDS | {_EXTRA_TRAIT_ID}}
    trait_summaries.update(overrides.pop("extra_trait_summaries", {}))
    kwargs = dict(
        session_id="sess_test", user_id="user_test", trait_summaries=trait_summaries,
    )
    kwargs.update(overrides)
    return AssessmentState(**kwargs)


_MAJOR_TRAIT_RECORDS = [
    _evidenced_major_trait("industrial_engineering", "causal_analysis", grade=3),
    _evidenced_major_trait("industrial_engineering", "pattern_finding", grade=2),
    _evidenced_major_trait("industrial_engineering", "planning", grade=3),
    _evidenced_major_trait("industrial_engineering", "information_comparison", grade=2),
]


def _build_service(
    *,
    departments: list[Department] | None = None,
    approved_department_ids: set[str] | None = None,
    subjects: list[SubjectProfile] | None = None,
    major_trait_records: list[MajorTraitMappingRecord] | None = None,
    subject_trait_records: list[SubjectTraitMappingRecord] | None = None,
    clock=lambda: _FIXED_DT,
) -> tuple[KnowledgeSubgraphService, InMemoryCoursePlanningStore]:
    departments = departments if departments is not None else []
    approved_department_ids = approved_department_ids if approved_department_ids is not None else set()
    subjects = subjects if subjects is not None else []
    major_trait_records = major_trait_records if major_trait_records is not None else _MAJOR_TRAIT_RECORDS
    subject_trait_records = subject_trait_records if subject_trait_records is not None else []

    subject_repository = FakeSubjectRepository(subjects)
    major_exploration_service = MajorExplorationService(
        FakeDepartmentRepository(departments),
        recommendation_scope_policy=SelectiveScopePolicy(approved_department_ids),
        fail_closed_major_ids=frozenset({"industrial_engineering"}),
    )
    course_planning_store = InMemoryCoursePlanningStore()
    course_planning_service = CoursePlanningService(
        subject_repository,
        major_profiles=VERTICAL_SLICE_MAJOR_PROFILES,
        trait_definitions=_TRAIT_DEFS,
        course_planning_store=course_planning_store,
    )
    service = KnowledgeSubgraphService(
        major_profiles=VERTICAL_SLICE_MAJOR_PROFILES,
        trait_definitions=_TRAIT_DEFS,
        major_trait_records=major_trait_records,
        subject_trait_records=subject_trait_records,
        major_exploration_service=major_exploration_service,
        course_planning_service=course_planning_service,
        course_planning_store=course_planning_store,
        subject_repository=subject_repository,
        clock=clock,
    )
    return service, course_planning_store


def _department(department_id: str, university_name: str, department_name: str) -> Department:
    return Department(
        department_id=department_id,
        university_name=university_name,
        region="서울",
        department_name=department_name,
        college_name="공과대학",
        department_status="EXISTING",
        source_svy_year=2024,
        source_url=f"https://dept.example/{department_id}",
        canonical_major_id="industrial_engineering",
    )


# --- 1~2. 학생 Node / 실제 관찰된 Trait만 ---


class StudentAndTraitNodeTest(unittest.TestCase):
    def test_exactly_one_student_node(self) -> None:
        service, _ = _build_service()
        nodes, _edges = service.build(_base_state())
        student_nodes = [n for n in nodes if n.node_type == "Student"]
        self.assertEqual(len(student_nodes), 1)
        self.assertEqual(student_nodes[0].label, "학생")

    def test_only_observed_traits_are_included(self) -> None:
        service, _ = _build_service()
        nodes, _edges = service.build(_base_state())
        trait_ids = {n.node_id for n in nodes if n.node_type == "Trait"}
        self.assertEqual(trait_ids, {f"trait_{t}" for t in _IE_CORE_TRAIT_IDS | {_EXTRA_TRAIT_ID}})

    def test_insufficient_trait_is_excluded(self) -> None:
        state = _base_state(extra_trait_summaries={"audience_response_prediction": _insufficient("audience_response_prediction")})
        service, _ = _build_service()
        nodes, _edges = service.build(state)
        trait_ids = {n.node_id for n in nodes if n.node_type == "Trait"}
        self.assertNotIn("trait_audience_response_prediction", trait_ids)

    def test_unresolved_conflict_trait_is_excluded(self) -> None:
        state = _base_state(
            extra_trait_summaries={"collaboration_preference": _strong("collaboration_preference")},
            unresolved_conflict_trait_ids={"collaboration_preference"},
        )
        service, _ = _build_service()
        nodes, _edges = service.build(state)
        trait_ids = {n.node_id for n in nodes if n.node_type == "Trait"}
        self.assertNotIn("trait_collaboration_preference", trait_ids)

    def test_resolution_damping_is_passed_through_to_matching_like_majors_endpoint(self) -> None:
        """§4: Resolution 답변 자체를 일반 Trait Evidence로 계산하지 않고, 기존
        `compute_student_trait_states(resolutions=...)`에 그대로 흘려보내는지 확인한다
        (`/majors`가 쓰는 것과 동일한 함수 호출)."""

        resolutions = {
            "contrast_1": ContrastResolutionRecord(
                contrast_id="contrast_1",
                status=ContrastResolutionStatus.RESOLVED_POSITIVE,
                resolved_at_answer_id="ans_1",
                preferred_trait_id="causal_analysis",
                opposite_trait_id="pattern_finding",
            )
        }
        state = _base_state(contrast_resolutions=resolutions)
        service, _ = _build_service()

        with patch(
            "src.services.knowledge_subgraph_service.compute_student_trait_states",
            wraps=__import__(
                "src.engines.matching_engine", fromlist=["compute_student_trait_states"]
            ).compute_student_trait_states,
        ) as spy:
            service.build(state)

        _args, kwargs = spy.call_args
        self.assertEqual(kwargs.get("resolutions"), resolutions)

    def test_student_trait_evidence_is_traceable_to_primary_blueprint_records_only(self) -> None:
        state = _base_state(
            evidence_ledger=[
                _evidence("ev_1", "causal_analysis"),
                _evidence("ev_2", "causal_analysis"),
                _evidence("ev_3", "pattern_finding"),
                _evidence("ev_4", "causal_analysis", origin=EvidenceOrigin.SECONDARY_HYPOTHESIS),
                _evidence("ev_5", "causal_analysis", origin=EvidenceOrigin.CONFLICT_RESOLUTION),
            ]
        )
        service, _ = _build_service()
        _nodes, edges = service.build(state)
        has_trait_edge = next(e for e in edges if e.relation_type == "HAS_TRAIT" and e.target_node_id == "trait_causal_analysis")
        self.assertEqual(has_trait_edge.evidence_ids, ["ev_1", "ev_2"])

    def test_has_trait_relevance_level_matches_trait_state(self) -> None:
        service, _ = _build_service()
        _nodes, edges = service.build(_base_state())
        for edge in edges:
            if edge.relation_type == "HAS_TRAIT":
                self.assertEqual(edge.relevance_level, 3)  # 전부 STRONG persona


# --- 7~8. 대표 전공 Node ---


class MajorNodeTest(unittest.TestCase):
    def test_only_recommended_majors_are_included(self) -> None:
        """이 Persona(causal_analysis/pattern_finding/planning/information_comparison/
        tool_utilization)는 industrial_engineering뿐 아니라 media_communication의
        Vector와도 상당히 겹쳐(둘 다 usable_trait_count>=3, vector_group>=2) 둘 다
        "computed"에 도달한다 — `rank_major_relevance`는 computed된 전공을 전부
        relevant 또는 explore_together 중 하나로 분류하므로(§16), 이 Persona로는
        정확히 이 둘만 CanonicalMajor Node가 돼야 한다."""

        service, _ = _build_service()
        nodes, _edges = service.build(_base_state())
        major_ids = {n.node_id for n in nodes if n.node_type == "CanonicalMajor"}
        self.assertEqual(major_ids, {"major_industrial_engineering", "major_media_communication"})

    def test_insufficient_major_is_excluded(self) -> None:
        """hci_ux는 이 Persona와 tool_utilization 하나만 겹쳐(usable_trait_count=1<3)
        insufficient로 남는다 — CanonicalMajor Node가 되면 안 된다."""

        service, _ = _build_service()
        nodes, _edges = service.build(_base_state())
        major_ids = {n.node_id for n in nodes if n.node_type == "CanonicalMajor"}
        self.assertNotIn("major_hci_ux", major_ids)


# --- 9~10. Major-Trait Edge ---


class MajorTraitEdgeTest(unittest.TestCase):
    def test_only_evidenced_major_trait_edges_are_included(self) -> None:
        service, _ = _build_service()
        _nodes, edges = service.build(_base_state())
        related_to_major_edges = {
            e.source_node_id for e in edges if e.relation_type == "RELATED_TO" and e.target_node_id == "major_industrial_engineering"
        }
        self.assertEqual(related_to_major_edges, {f"trait_{t}" for t in _IE_CORE_TRAIT_IDS})

    def test_review_required_or_missing_mapping_is_excluded_even_when_vector_value_is_positive(self) -> None:
        """tool_utilization은 industrial_engineering의 environment_vector에 0.67(>0)이
        있지만, EVIDENCED Mapping 레코드가 없다(_MAJOR_TRAIT_RECORDS에 빠짐) — Edge가
        생기면 안 된다."""

        service, _ = _build_service()
        _nodes, edges = service.build(_base_state())
        target_ids = {e.target_node_id for e in edges if e.source_node_id == "trait_tool_utilization"}
        self.assertNotIn("major_industrial_engineering", target_ids)

    def test_explicit_review_required_record_is_also_excluded(self) -> None:
        records = _MAJOR_TRAIT_RECORDS + [_review_required_major_trait("industrial_engineering", "tool_utilization")]
        service, _ = _build_service(major_trait_records=records)
        _nodes, edges = service.build(_base_state())
        target_ids = {e.target_node_id for e in edges if e.source_node_id == "trait_tool_utilization"}
        self.assertNotIn("major_industrial_engineering", target_ids)

    def test_related_to_edge_carries_real_grade_and_source_urls_not_scores(self) -> None:
        service, _ = _build_service()
        _nodes, edges = service.build(_base_state())
        edge = next(
            e for e in edges
            if e.relation_type == "RELATED_TO" and e.source_node_id == "trait_causal_analysis"
            and e.target_node_id == "major_industrial_engineering"
        )
        self.assertEqual(edge.relevance_level, 3)  # _evidenced_major_trait(..., grade=3)
        self.assertEqual(edge.mapping_version, "major_trait_test_v1")
        self.assertTrue(all(url.startswith("https://") for url in edge.source_ids))


# --- 11~13. 실제 학과·University Node ---


class DepartmentUniversityNodeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.dept_approved_1 = _department("dept_1", "가짜대학교A", "가짜학과1")
        self.dept_approved_2 = _department("dept_2", "가짜대학교A", "가짜학과2")  # 같은 대학
        self.dept_not_approved = _department("dept_3", "가짜대학교B", "예체능제외학과")

    def test_only_approved_departments_are_included(self) -> None:
        service, _ = _build_service(
            departments=[self.dept_approved_1, self.dept_approved_2, self.dept_not_approved],
            approved_department_ids={"dept_1", "dept_2"},
        )
        nodes, _edges = service.build(_base_state())
        dept_ids = {n.node_id for n in nodes if n.node_type == "Department"}
        self.assertEqual(dept_ids, {"dept_1", "dept_2"})

    def test_fail_closed_policy_is_not_bypassed(self) -> None:
        """예체능/미승인 학과가 Subgraph를 통해 다시 노출되면 안 된다."""

        service, _ = _build_service(
            departments=[self.dept_approved_1, self.dept_not_approved],
            approved_department_ids={"dept_1"},
        )
        nodes, _edges = service.build(_base_state())
        labels = {n.label for n in nodes if n.node_type == "Department"}
        self.assertNotIn("예체능제외학과", labels)

    def test_university_node_is_deduplicated(self) -> None:
        service, _ = _build_service(
            departments=[self.dept_approved_1, self.dept_approved_2],
            approved_department_ids={"dept_1", "dept_2"},
        )
        nodes, edges = service.build(_base_state())
        univ_nodes = [n for n in nodes if n.node_type == "University"]
        self.assertEqual(len(univ_nodes), 1)
        self.assertEqual(univ_nodes[0].label, "가짜대학교A")
        belongs_to_edges = [e for e in edges if e.relation_type == "BELONGS_TO"]
        self.assertEqual(len(belongs_to_edges), 2)  # 두 학과 각각 → 같은 University
        self.assertEqual({e.target_node_id for e in belongs_to_edges}, {univ_nodes[0].node_id})

    def test_no_mock_university_or_department_values_leak(self) -> None:
        service, _ = _build_service(
            departments=[self.dept_approved_1], approved_department_ids={"dept_1"},
        )
        nodes, _edges = service.build(_base_state())
        labels = " ".join(n.label for n in nodes)
        self.assertNotIn("예시대학교", labels)
        node_ids = " ".join(n.node_id for n in nodes)
        self.assertNotIn("dept_mock", node_ids)


# --- 14~17. 추천 과목 Node ---


class SubjectNodeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.subj_core_offered = SubjectProfile(
            subject_id="subj_core_offered", label="확정된 핵심 과목",
            trait_vector={"planning": 1.0, "information_comparison": 1.0},
            related_major_ids=["industrial_engineering"], source_id="https://subj.example/offered",
        )
        self.subj_core_missing = SubjectProfile(
            subject_id="subj_core_missing", label="미개설 핵심 과목",
            trait_vector={"causal_analysis": 1.0, "pattern_finding": 1.0},
            related_major_ids=["industrial_engineering"], source_id="https://subj.example/missing",
        )
        self.subject_trait_records = [
            _evidenced_subject_trait("subj_core_offered", "planning", grade=2),
            # information_comparison은 일부러 EVIDENCED 레코드를 안 만든다(REVIEW_REQUIRED
            # 취급) — Edge가 하나만 생겨야 한다.
        ]

    def _confirm(
        self,
        store: InMemoryCoursePlanningStore,
        *,
        status: str = "CONFIRMED",
        selected_major_id: str = "industrial_engineering",
    ) -> None:
        store.save(
            CoursePlanningSessionState(
                session_id="sess_test", selected_major_id=selected_major_id,
                parsed_candidates=[], confirmed_offered_subject_ids=["subj_core_offered"],
                upload_status=status,
            )
        )

    def test_major_the_legacy_course_path_cannot_plan_yields_partial_subgraph(self) -> None:
        """Service Canonical Major가 39개로 늘어난 뒤, Vertical Slice 3개 밖의 전공이
        확정된 세션에서도 build()가 죽지 않아야 한다(예전에는 MajorNotSelectableError가
        그대로 올라가 GET /subgraph가 500이었다). 과목 Node만 빠지고 Trait/전공은 남는다."""

        service, store = _build_service(
            subjects=[self.subj_core_offered], subject_trait_records=self.subject_trait_records,
        )
        self._confirm(store, selected_major_id="social_welfare")
        nodes, _edges = service.build(_base_state())
        self.assertEqual([n for n in nodes if n.node_type == "HighSchoolSubject"], [])
        self.assertTrue(any(n.node_type == "CanonicalMajor" for n in nodes))

    def test_subject_nodes_included_only_when_confirmed(self) -> None:
        service, store = _build_service(
            subjects=[self.subj_core_offered, self.subj_core_missing],
            subject_trait_records=self.subject_trait_records,
        )
        # 확정 안 됨(store 비어있음) — 과목 Node가 전혀 없어야 하고, Trait/전공은 그대로.
        nodes, _edges = service.build(_base_state())
        self.assertEqual([n for n in nodes if n.node_type == "HighSchoolSubject"], [])
        self.assertTrue(any(n.node_type == "CanonicalMajor" for n in nodes))

    def test_confirmation_required_status_still_excludes_subjects(self) -> None:
        service, store = _build_service(
            subjects=[self.subj_core_offered], subject_trait_records=self.subject_trait_records,
        )
        self._confirm(store, status="CONFIRMATION_REQUIRED")
        nodes, _edges = service.build(_base_state())
        self.assertEqual([n for n in nodes if n.node_type == "HighSchoolSubject"], [])

    def test_only_actually_recommended_subject_is_included(self) -> None:
        service, store = _build_service(
            subjects=[self.subj_core_offered, self.subj_core_missing],
            subject_trait_records=self.subject_trait_records,
        )
        self._confirm(store)
        nodes, _edges = service.build(_base_state())
        subject_ids = {n.node_id for n in nodes if n.node_type == "HighSchoolSubject"}
        self.assertEqual(subject_ids, {"subj_core_offered"})

    def test_unavailable_subject_is_not_a_node(self) -> None:
        """subj_core_missing은 PRE_SURVEY core였지만 confirmed_offered_subject_ids에
        없으므로 unavailable_subjects로 옮겨진다 — Graph에는 안 나타나야 한다."""

        service, store = _build_service(
            subjects=[self.subj_core_offered, self.subj_core_missing],
            subject_trait_records=self.subject_trait_records,
        )
        self._confirm(store)
        course_profile = service._course_planning_service.get_course_profile(
            _base_state(), "industrial_engineering"
        )
        self.assertIn("subj_core_missing", [u.subject_id for u in course_profile.unavailable_subjects])
        nodes, _edges = service.build(_base_state())
        subject_ids = {n.node_id for n in nodes}
        self.assertNotIn("subj_core_missing", subject_ids)

    def test_only_evidenced_subject_trait_edges_are_included(self) -> None:
        service, store = _build_service(
            subjects=[self.subj_core_offered], subject_trait_records=self.subject_trait_records,
        )
        self._confirm(store)
        _nodes, edges = service.build(_base_state())
        related_to_subject_edges = {
            e.source_node_id for e in edges
            if e.relation_type == "RELATED_TO" and e.target_node_id == "subj_core_offered"
        }
        self.assertEqual(related_to_subject_edges, {"trait_planning"})  # information_comparison 제외

    def test_recommends_edge_connects_selected_major_to_subject(self) -> None:
        service, store = _build_service(
            subjects=[self.subj_core_offered], subject_trait_records=self.subject_trait_records,
        )
        self._confirm(store)
        _nodes, edges = service.build(_base_state())
        recommends = [e for e in edges if e.relation_type == "RECOMMENDS"]
        self.assertEqual(len(recommends), 1)
        self.assertEqual(recommends[0].source_node_id, "major_industrial_engineering")
        self.assertEqual(recommends[0].target_node_id, "subj_core_offered")


# --- 18~22. Node·Edge 품질 ---


class GraphIntegrityTest(unittest.TestCase):
    def _full_service(self) -> tuple[KnowledgeSubgraphService, InMemoryCoursePlanningStore]:
        dept = _department("dept_1", "가짜대학교A", "가짜학과1")
        subj = SubjectProfile(
            subject_id="subj_core_offered", label="확정된 핵심 과목",
            trait_vector={"planning": 1.0, "information_comparison": 1.0},
            related_major_ids=["industrial_engineering"], source_id="https://subj.example/offered",
        )
        service, store = _build_service(
            departments=[dept], approved_department_ids={"dept_1"}, subjects=[subj],
            subject_trait_records=[_evidenced_subject_trait("subj_core_offered", "planning", grade=2)],
        )
        store.save(
            CoursePlanningSessionState(
                session_id="sess_test", selected_major_id="industrial_engineering",
                confirmed_offered_subject_ids=["subj_core_offered"], upload_status="CONFIRMED",
            )
        )
        return service, store

    def test_no_duplicate_node_ids(self) -> None:
        service, _ = self._full_service()
        nodes, _edges = service.build(_base_state())
        ids = [n.node_id for n in nodes]
        self.assertEqual(len(ids), len(set(ids)))

    def test_no_duplicate_edges(self) -> None:
        service, _ = self._full_service()
        _nodes, edges = service.build(_base_state())
        keys = [(e.source_node_id, e.target_node_id, e.relation_type) for e in edges]
        self.assertEqual(len(keys), len(set(keys)))

    def test_no_orphan_edges(self) -> None:
        service, _ = self._full_service()
        nodes, edges = service.build(_base_state())
        node_ids = {n.node_id for n in nodes}
        for edge in edges:
            self.assertIn(edge.source_node_id, node_ids)
            self.assertIn(edge.target_node_id, node_ids)

    def test_deterministic_order_across_repeated_calls(self) -> None:
        service, _ = self._full_service()
        nodes1, edges1 = service.build(_base_state())
        nodes2, edges2 = service.build(_base_state())
        self.assertEqual([n.node_id for n in nodes1], [n.node_id for n in nodes2])
        self.assertEqual(
            [(e.source_node_id, e.target_node_id, e.relation_type) for e in edges1],
            [(e.source_node_id, e.target_node_id, e.relation_type) for e in edges2],
        )

    def test_same_clock_produces_byte_equivalent_result(self) -> None:
        service, _ = self._full_service()
        nodes1, edges1 = service.build(_base_state())
        nodes2, edges2 = service.build(_base_state())
        self.assertEqual([n.model_dump() for n in nodes1], [n.model_dump() for n in nodes2])
        self.assertEqual([e.model_dump() for e in edges1], [e.model_dump() for e in edges2])

    def test_all_edges_in_one_build_share_the_same_created_at(self) -> None:
        service, _ = self._full_service()
        _nodes, edges = service.build(_base_state())
        self.assertTrue(edges)
        self.assertEqual({e.created_at for e in edges}, {_FIXED_DT})

    def test_no_internal_score_or_pii_leaks_into_labels(self) -> None:
        service, _ = self._full_service()
        nodes, edges = service.build(_base_state())
        full_text = " ".join(n.label for n in nodes)
        self.assertNotIn("sess_test", full_text)
        self.assertNotIn("user_test", full_text)
        for edge in edges:
            self.assertIsInstance(edge.relevance_level, int)


# --- Evidence Not Ready ---


class SubgraphEvidenceNotReadyTest(unittest.TestCase):
    def test_empty_trait_summaries_raises(self) -> None:
        service, _ = _build_service()
        state = AssessmentState(session_id="sess_empty", user_id="user_test")
        with self.assertRaises(SubgraphEvidenceNotReadyError):
            service.build(state)


if __name__ == "__main__":
    unittest.main()
