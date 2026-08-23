"""KnowledgeSubgraphService — A 소유, 설계안 §23 실제 구현, 2026-08-28 19차 리뷰.

`GET /subgraph/{session_id}`가 예전엔 `mock_data.mock_subgraph()`의 고정 5개 Node를
그대로 돌려줬다 — 이 Service가 그 자리를 실제 계산으로 채운다.

이 API는 "관련 데이터를 한꺼번에 반환"하는 API가 아니다. 학생의 실제 답변이 어떤
Trait를 거쳐 대표 전공·실제 학과·추천 과목으로 연결됐는지를 설명하는 근거 그래프만
만든다:

    학생 --HAS_TRAIT--> Trait --RELATED_TO--> CanonicalMajor --HAS_DEPARTMENT--> Department
                                                               --RECOMMENDS----> HighSchoolSubject
                                              Department --BELONGS_TO--> University
                                              Trait --RELATED_TO--> HighSchoolSubject

CLAUDE.md 책임 분리:
- 이 Service는 기존 계산 결과(`compute_student_trait_states`/`compute_major_match`/
  `rank_major_relevance`, `MajorExplorationService`, `CoursePlanningService`)를 그대로
  재사용만 한다 — 새 Matching 공식을 만들지 않는다.
- LLM으로 Node·Edge를 만들지 않는다(순수 계산).
- FastAPI(`src.api.main`)는 session_id로 AssessmentState를 조회하고 이 Service를
  호출해 `SubgraphResponse`로 감싸는 것까지만 한다.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from src.engines.matching_engine import (
    compute_major_match,
    compute_student_trait_states,
    rank_major_relevance,
)
from src.ids import generate_university_id
from src.memory.course_planning_store import CoursePlanningStore
from src.repositories.protocols import SubjectRepository
from src.schemas.assessment_state import AssessmentState
from src.schemas.evidence import EvidenceOrigin, TraitState
from src.schemas.graph import SubgraphEdge, SubgraphNode
from src.schemas.major import MajorProfile
from src.schemas.trait import TraitDefinition
from src.services.course_planning_service import CoursePlanningService
from src.services.major_exploration_service import MajorExplorationService
from src.services.major_trait_mapping_evidence import MajorTraitMappingRecord
from src.services.subject_trait_mapping_evidence import SubjectTraitMappingRecord


class SubgraphEvidenceNotReadyError(ValueError):
    """학생 답변이 아예 없어(`state.trait_summaries`가 비어 있음) Subgraph를 만들 근거가
    전혀 없을 때 — `GET /profile`과 동일한 기준(지시서 §9)."""


# 실제 Mapping Evidence 파일에서 나온 값이 아니라 이 Service의 계산 로직 자체 버전을
# 표시하는 구조적 상수다(예전 mock_subgraph()가 모든 Edge에 쓰던 "v1" 관례를 그대로
# 유지한다) — 실제 Mapping 파일의 mapping_version이 있는 RELATED_TO Edge와는 다른 값이다.
STRUCTURAL_EDGE_VERSION = "v1"

_TRAIT_STATE_TO_RELEVANCE_LEVEL: dict[TraitState, int] = {
    TraitState.STRONG: 3,
    TraitState.MODERATE: 2,
    TraitState.LIMITED: 1,
}

# 구조적(Evidence 등급이 아닌) 관계 — "이 학과는 이 전공에 속한다", "이 과목은 이 전공이
# 추천했다"처럼 정도의 문제가 아니라 있다/없다만 있는 관계에 쓴다(mock_subgraph()의
# HAS_DEPARTMENT=3과 동일한 관례).
_STRUCTURAL_RELEVANCE_LEVEL = 3


def _major_vector_value(major: MajorProfile, trait_id: str) -> float:
    """`compute_major_match()`와 동일한 방식으로 4개 Vector 그룹 전부에서 찾는다 — 이
    Service가 새로운 조회 방식을 만들지 않는다."""

    for vector in (
        major.interest_vector,
        major.cognitive_vector,
        major.work_style_vector,
        major.environment_vector,
    ):
        if trait_id in vector:
            return vector[trait_id]
    return 0.0


class KnowledgeSubgraphService:
    def __init__(
        self,
        major_profiles: list[MajorProfile],
        trait_definitions: dict[str, TraitDefinition],
        major_trait_records: list[MajorTraitMappingRecord],
        subject_trait_records: list[SubjectTraitMappingRecord],
        major_exploration_service: MajorExplorationService,
        course_planning_service: CoursePlanningService,
        course_planning_store: CoursePlanningStore,
        subject_repository: SubjectRepository,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._major_profiles = major_profiles
        self._major_by_id = {m.major_id: m for m in major_profiles}
        self._trait_definitions = trait_definitions
        # (major_id, trait_id) -> EVIDENCED 레코드만 남긴다. REVIEW_REQUIRED/UNMAPPED/
        # NO_DIRECT_EVIDENCE는 애초에 조회 대상에서 뺀다 — 확정 관계로 표시할 근거가 없다.
        self._major_trait_evidenced = {
            (r.major_id, r.trait_id): r for r in major_trait_records if r.mapping_status == "EVIDENCED"
        }
        self._subject_trait_evidenced = {
            (r.subject_id, r.trait_id): r
            for r in subject_trait_records
            if r.mapping_status == "EVIDENCED"
        }
        self._major_exploration_service = major_exploration_service
        self._course_planning_service = course_planning_service
        self._course_planning_store = course_planning_store
        self._subject_repository = subject_repository
        # 한 번의 Graph 생성에 포함되는 모든 Edge가 같은 생성 시각을 쓰도록 build() 안에서
        # 딱 한 번만 호출한다 — 테스트에서 고정 Clock을 주입할 수 있어 현재 시간 때문에
        # 비결정적으로 실패하지 않는다.
        self._clock = clock

    def build(self, state: AssessmentState) -> tuple[list[SubgraphNode], list[SubgraphEdge]]:
        if not state.trait_summaries:
            raise SubgraphEvidenceNotReadyError(
                "아직 답변이 없어 Subgraph를 만들 Evidence가 없습니다. 먼저 "
                "/assessment/next-question과 /assessment/answer로 최소 1개 이상 답변한 뒤 "
                "다시 호출하세요."
            )

        now = self._clock()
        nodes: list[SubgraphNode] = []
        edges: list[SubgraphEdge] = []
        seen_node_ids: set[str] = set()
        seen_edge_keys: set[tuple[str, str, str]] = set()

        def add_node(node: SubgraphNode) -> None:
            if node.node_id in seen_node_ids:
                return
            seen_node_ids.add(node.node_id)
            nodes.append(node)

        def add_edge(edge: SubgraphEdge) -> None:
            key = (edge.source_node_id, edge.target_node_id, edge.relation_type)
            if key in seen_edge_keys:
                return
            seen_edge_keys.add(key)
            edges.append(edge)

        # --- 1. 학생 Node. 세션마다 응답 하나에 정확히 하나만 생기므로 값을 사용자
        # 식별자와 무관한 고정 리터럴로 둔다(session_id/user_id는 여기 어디에도 넣지
        # 않는다). ---
        student_node_id = "student_1"
        add_node(SubgraphNode(node_id=student_node_id, node_type="Student", label="학생"))

        # --- 2. Trait Node + Student→Trait Edge. `compute_student_trait_states`가 이미
        # INSUFFICIENT/CONFLICTING(unresolved conflict 포함)을 normalized_value=None으로
        # Mask한다 — 이 Service는 그 결과를 재사용만 하고 별도 판정을 하지 않는다. ---
        student_states = compute_student_trait_states(
            state.trait_summaries,
            self._trait_definitions,
            unresolved_conflict_trait_ids=state.unresolved_conflict_trait_ids,
            resolutions=state.contrast_resolutions,
        )
        usable_trait_ids = sorted(
            tid for tid, s in student_states.items() if s.normalized_value is not None
        )
        for trait_id in usable_trait_ids:
            trait_def = self._trait_definitions[trait_id]
            add_node(SubgraphNode(node_id=f"trait_{trait_id}", node_type="Trait", label=trait_def.label))

            # summarize_trait_evidence()의 support_count와 동일한 필터(PRIMARY_BLUEPRINT +
            # applied_primary_trait_delta에 이 trait_id 포함)를 그대로 써서 evidence_id를
            # 역추적한다 — Conflict Resolution 답변(EvidenceOrigin.CONFLICT_RESOLUTION)은
            # 여기 절대 섞이지 않는다.
            supporting_evidence_ids = [
                r.evidence_id
                for r in state.evidence_ledger
                if r.evidence_origin == EvidenceOrigin.PRIMARY_BLUEPRINT
                and trait_id in r.applied_primary_trait_delta
            ]
            add_edge(
                SubgraphEdge(
                    source_node_id=student_node_id,
                    target_node_id=f"trait_{trait_id}",
                    relation_type="HAS_TRAIT",
                    relevance_level=_TRAIT_STATE_TO_RELEVANCE_LEVEL[student_states[trait_id].state],
                    evidence_ids=supporting_evidence_ids,
                    mapping_version=STRUCTURAL_EDGE_VERSION,
                    created_at=now,
                )
            )

        # --- 3. 대표 전공 Node + Trait→CanonicalMajor Edge. `/majors/{session_id}`와
        # 정확히 같은 계산(compute_major_match/rank_major_relevance)을 그대로 호출한다 —
        # 복제하지 않는다. ---
        major_results = [compute_major_match(student_states, m) for m in self._major_profiles]
        labels_by_major_id = {m.major_id: m.label for m in self._major_profiles}
        relevant, explore_together, _message = rank_major_relevance(major_results, labels_by_major_id)
        recommended_major_ids = sorted(
            {r.major_id for r in relevant} | {r.major_id for r in explore_together}
        )

        for major_id in recommended_major_ids:
            major = self._major_by_id[major_id]
            add_node(SubgraphNode(node_id=f"major_{major_id}", node_type="CanonicalMajor", label=major.label))

            for trait_id in usable_trait_ids:
                if _major_vector_value(major, trait_id) <= 0:
                    continue
                record = self._major_trait_evidenced.get((major_id, trait_id))
                if record is None:  # REVIEW_REQUIRED/UNMAPPED/NO_DIRECT_EVIDENCE는 Edge 생성 대상이 아니다.
                    continue
                add_edge(
                    SubgraphEdge(
                        source_node_id=f"trait_{trait_id}",
                        target_node_id=f"major_{major_id}",
                        relation_type="RELATED_TO",
                        relevance_level=record.grade,  # EVIDENCED이므로 1~3 보장(Schema 검증)
                        evidence_ids=[f"major_trait:{major_id}:{trait_id}:{record.mapping_version}"],
                        source_ids=[e.source_url for e in record.evidence],
                        mapping_version=record.mapping_version,
                        created_at=now,
                    )
                )

        # --- 4. 실제 대학·학과 Node. Repository를 직접 읽지 않고 반드시
        # MajorExplorationService.list_departments_for_major()를 거친다 — 예체능 제외·
        # Fail-Closed 승인·source_url 존재 등 기존 정책을 이 Service가 우회하지 않는다. ---
        for major_id in recommended_major_ids:
            departments = self._major_exploration_service.list_departments_for_major(major_id)
            for department in departments:
                add_node(
                    SubgraphNode(
                        node_id=department.department_id,
                        node_type="Department",
                        label=department.department_name,
                    )
                )
                add_edge(
                    SubgraphEdge(
                        source_node_id=f"major_{major_id}",
                        target_node_id=department.department_id,
                        relation_type="HAS_DEPARTMENT",
                        relevance_level=_STRUCTURAL_RELEVANCE_LEVEL,
                        source_ids=[department.source_url] if department.source_url.strip() else [],
                        mapping_version=STRUCTURAL_EDGE_VERSION,
                        created_at=now,
                    )
                )

                # 같은 대학에 여러 학과가 있어도 University Node는 한 번만 생긴다
                # (add_node의 node_id 중복 방지 + hash() 대신 SHA-256 기반 안정 ID).
                university_id = generate_university_id(department.university_name)
                add_node(
                    SubgraphNode(
                        node_id=university_id, node_type="University", label=department.university_name
                    )
                )
                add_edge(
                    SubgraphEdge(
                        source_node_id=department.department_id,
                        target_node_id=university_id,
                        relation_type="BELONGS_TO",
                        relevance_level=_STRUCTURAL_RELEVANCE_LEVEL,
                        source_ids=[department.source_url] if department.source_url.strip() else [],
                        mapping_version=STRUCTURAL_EDGE_VERSION,
                        created_at=now,
                    )
                )

        # --- 5. 추천 과목 Node. CoursePlanningStore에 이 세션의 확정(CONFIRMED) 상태가
        # 있을 때만 만든다 — 없으면 지어내지 않고 여기서 그대로 끝낸다(Trait·전공·학과까지만
        # 있는 부분 Subgraph를 그대로 반환). ---
        planning_state = self._course_planning_store.load(state.session_id)
        if planning_state is not None and planning_state.upload_status == "CONFIRMED":
            course_profile = self._course_planning_service.get_course_profile(
                state, planning_state.selected_major_id
            )
            if course_profile.source == "POST_OFFERING":
                major_node_id = f"major_{planning_state.selected_major_id}"
                for item in course_profile.recommendations:
                    add_node(
                        SubgraphNode(node_id=item.subject_id, node_type="HighSchoolSubject", label=item.label)
                    )
                    # major_node_id는 구조적으로 항상 이미 추가돼 있다(validate_selectable_major가
                    # selected_major_id를 recommended_major_ids 안에서만 허용) — 그래도
                    # 고아 Edge를 만들지 않도록 방어적으로 다시 확인한다.
                    if major_node_id in seen_node_ids:
                        add_edge(
                            SubgraphEdge(
                                source_node_id=major_node_id,
                                target_node_id=item.subject_id,
                                relation_type="RECOMMENDS",
                                relevance_level=_STRUCTURAL_RELEVANCE_LEVEL,
                                mapping_version=STRUCTURAL_EDGE_VERSION,
                                created_at=now,
                            )
                        )

                    subject = self._subject_repository.get(item.subject_id)
                    subject_trait_ids = set(subject.trait_vector) if subject is not None else set()
                    for trait_id in usable_trait_ids:
                        if trait_id not in subject_trait_ids:
                            continue
                        record = self._subject_trait_evidenced.get((item.subject_id, trait_id))
                        if record is None:
                            continue
                        add_edge(
                            SubgraphEdge(
                                source_node_id=f"trait_{trait_id}",
                                target_node_id=item.subject_id,
                                relation_type="RELATED_TO",
                                relevance_level=record.grade,
                                evidence_ids=[
                                    f"subject_trait:{item.subject_id}:{trait_id}:{record.mapping_version}"
                                ],
                                source_ids=[e.source_url for e in record.curriculum_evidence],
                                mapping_version=record.mapping_version,
                                created_at=now,
                            )
                        )

        return nodes, edges
