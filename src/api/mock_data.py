"""B·C가 실제 계산 로직 완성을 기다리지 않고 화면/데이터 작업을 시작할 수 있도록 만든
손으로 채운 예시 데이터. A 지시서 §3: "B와 C가 실제 구현을 기다리지 않고 작업할 수 있도록
Mock 응답을 먼저 제공한다." 실제 값이 아니라 "이런 모양이 온다"를 보여주는 용도다.
"""

from __future__ import annotations

from datetime import date, datetime

from src.data.contexts.context_definitions import VERTICAL_SLICE_CONTEXT_IDS
from src.data.questions.vertical_slice_seed_questions import VERTICAL_SLICE_SEED_QUESTIONS
from src.schemas.course import CourseProfile, CourseRecommendationItem, ParsedSubjectCandidate
from src.schemas.graph import SubgraphEdge, SubgraphNode
from src.schemas.major import AdmissionReference, Department, MajorRelevance
from src.schemas.profile import CareerProfile, CareerProfileHighlight, DimensionEvidenceItem
from src.schemas.question import FinalizedOption, FinalizedQuestion, SeedQuestion
from src.schemas.retrieval import RetrievedDocument


def seed_question_as_finalized(seed: SeedQuestion) -> FinalizedQuestion:
    """실제 확정된 Seed Question(§7-1)을 B가 받는 FinalizedQuestion 모양으로 바꾼다.
    target_traits/frame_id는 Seed에 없는 개념이라(Adaptive 전용) 빈 값·"seed_frame"으로 채운다."""

    return FinalizedQuestion(
        question_id=seed.question_id,
        context=seed.context,
        target_traits=[],
        frame_id="seed_frame",
        question_text=seed.question_text,
        options=[
            FinalizedOption(
                option_id=o.option_id,
                role_id=o.role_id,
                text=o.text,
                primary_trait_delta=o.primary_trait_delta,
            )
            for o in seed.options
        ],
    )


def next_mock_question(context_id: str, questions_asked_in_current_context: int) -> FinalizedQuestion:
    """이 Context에서 첫 질문(0개 답변)이면 실제 Seed를, 그 이후엔 여전히 Mock 꼬리질문을
    반환한다 — 실제 Adaptive 질문 생성(§10)은 아직 없다."""

    if questions_asked_in_current_context == 0 and context_id in VERTICAL_SLICE_SEED_QUESTIONS:
        return seed_question_as_finalized(VERTICAL_SLICE_SEED_QUESTIONS[context_id])
    return mock_finalized_question(context_id, questions_asked_in_current_context)


def mock_finalized_question(context_id: str = "media", index: int = 4) -> FinalizedQuestion:
    question_id = f"{context_id}_tail_{index:02d}"
    role_ids = ["cause_analysis", "strategy_change", "direct_trial", "external_research", "ask_others"]
    trait_ids = [
        "causal_analysis",
        "change_adaptation",
        "immediate_execution",
        "information_comparison",
        "collaboration_preference",
    ]
    return FinalizedQuestion(
        question_id=question_id,
        context=context_id,
        target_traits=["causal_analysis"],
        frame_id="unexpected_result",
        question_text="만든 콘텐츠 반응이 예상과 다르면 가장 먼저 무엇을 하나요?",
        options=[
            FinalizedOption(
                option_id=f"{question_id}_o{i}",
                role_id=role_ids[i - 1],
                text=text,
                primary_trait_delta={trait_ids[i - 1]: 1},
            )
            for i, text in enumerate(
                [
                    "왜 이런 반응이 나왔는지부터 분석한다",
                    "다른 방식으로 바꿔서 다시 시도한다",
                    "일단 조금 수정해서 바로 올려본다",
                    "비슷한 사례를 더 찾아본다",
                    "주변 사람들에게 의견을 물어본다",
                ],
                start=1,
            )
        ],
    )


def mock_career_profile(session_id: str, user_id: str = "demo_user_01") -> CareerProfile:
    return CareerProfile(
        session_id=session_id,
        user_id=user_id,
        title="구조를 읽고 사람의 반응까지 생각하는 탐색형 설계자",
        highlights=[
            CareerProfileHighlight(text=t, supporting_trait_ids=[tid])
            for t, tid in [
                ("복잡한 내용에서 핵심과 흐름을 찾아 정리하는 데 흥미를 느껴요.", "pattern_finding"),
                ("단순히 감상하기보다 왜 이런 구조가 되었는지 생각하는 편이에요.", "causal_analysis"),
                (
                    "결과물을 만들 때 보는 사람이 어떻게 받아들일지도 중요하게 생각해요.",
                    "audience_response_prediction",
                ),
                ("기존 방식을 그대로 따르기보다 순서나 구성을 바꿔보는 것을 좋아해요.", "change_adaptation"),
                ("아이디어에 머무르기보다 도구로 직접 시험해보려는 경향이 있어요.", "immediate_execution"),
                ("여러 선택지를 비교한 뒤 납득할 수 있는 기준으로 결정하는 편이에요.", "information_comparison"),
                ("협업 방식은 아직 Evidence가 적어 추가 탐색이 필요해요.", "collaboration_preference"),
            ]
        ],
        hashtags=["#구조화", "#사용자관점", "#패턴탐색", "#콘텐츠기획", "#직접실행"],
        detailed_evidence_by_dimension={
            "분석과 구조화": [
                DimensionEvidenceItem(context_id="media", description="장면 순서를 바꿔 이해하기 쉽게 만드는 활동 선택"),
                DimensionEvidenceItem(context_id="game", description="여러 전략을 조건별로 비교하는 방식 선택"),
            ],
        },
        generated_at=datetime.now(),
    )


def mock_majors_relevance() -> tuple[list[MajorRelevance], list[MajorRelevance]]:
    relevant = [
        MajorRelevance(
            major_id="media_communication",
            label="미디어커뮤니케이션",
            relevance_label="관련성 높음",
            evidence_sufficiency="충분",
            repeated_context_count=3,
        ),
        MajorRelevance(
            major_id="hci_ux",
            label="HCI·UX",
            relevance_label="관련성 높음",
            evidence_sufficiency="보통",
            repeated_context_count=2,
        ),
    ]
    explore_together = [
        MajorRelevance(
            major_id="industrial_engineering",
            label="산업공학",
            relevance_label="함께 탐색해볼 분야",
            evidence_sufficiency="보통",
            repeated_context_count=1,
        ),
    ]
    return relevant, explore_together


def mock_departments(major_id: str = "media_communication") -> list[Department]:
    dept = Department(
        department_id="dept_mock0000000000000001",
        university_name="예시대학교",
        campus="본교",
        region="서울",
        department_name="미디어커뮤니케이션학과",
        college_name="사회과학대학",
        admission_unit="인문계열",
        department_status="EXISTING",
        source_svy_year=2024,
        source_url="https://example.ac.kr/media-comm",
        canonical_major_id=major_id,
    )
    return [dept]


def mock_admission_reference() -> AdmissionReference:
    return AdmissionReference(
        department_id="dept_mock0000000000000001",
        admission_year=2025,
        admission_type="수시",
        admission_track="학생부종합",
        score_metric="평균등급",
        score_70_cut=1.9,
        source_url="https://example.ac.kr/admission/2025",
        data_comparability_group="2025_수시_학생부종합_평균등급_70cut",
        review_status="verified",
        verified_at=datetime.now(),
    )


def mock_retrieved_document() -> RetrievedDocument:
    return RetrievedDocument(
        document_id="doc_mock_001",
        source_url="https://example.ac.kr/media-comm/curriculum",
        as_of_date=date(2025, 3, 1),
        document_type="교육과정",
        excerpt="미디어커뮤니케이션학과는 콘텐츠 기획, 제작, 유통 전반을 다루며...",
        relevance_score=0.82,
        rank=1,
        related_department_id="dept_mock0000000000000001",
    )


def mock_course_profile(session_id: str) -> CourseProfile:
    return CourseProfile(
        session_id=session_id,
        source="PRE_SURVEY",
        recommendations=[
            CourseRecommendationItem(
                subject_id="subj_mock0000000000000001",
                category="core",
                is_actually_offered=True,
                reason="정보 비교·탐색, 패턴 탐색 Trait와 관련도가 높음",
            ),
        ],
        unresolved_candidates=[
            ParsedSubjectCandidate(
                raw_text="데이터과학탐구",
                matched_subject_id=None,
                confidence="low",
                requires_user_confirmation=True,
            )
        ],
    )


def mock_subgraph(session_id: str) -> tuple[list[SubgraphNode], list[SubgraphEdge]]:
    nodes = [
        SubgraphNode(node_id="student_1", node_type="Student", label="학생"),
        SubgraphNode(node_id="trait_causal_analysis", node_type="Trait", label="원인 분석"),
        SubgraphNode(node_id="dim_analysis", node_type="CareerDimension", label="분석과 구조화"),
        SubgraphNode(node_id="major_media_communication", node_type="CanonicalMajor", label="미디어커뮤니케이션"),
        SubgraphNode(node_id="dept_mock0000000000000001", node_type="Department", label="예시대학교 미디어커뮤니케이션학과"),
    ]
    edges = [
        SubgraphEdge(
            source_node_id="student_1",
            target_node_id="trait_causal_analysis",
            relation_type="HAS_TRAIT",
            relevance_level=3,
            evidence_ids=["ev_1", "ev_2", "ev_3"],
            mapping_version="v1",
            created_at=datetime.now(),
        ),
        SubgraphEdge(
            source_node_id="trait_causal_analysis",
            target_node_id="dim_analysis",
            relation_type="GROUPED_AS",
            relevance_level=3,
            mapping_version="v1",
            created_at=datetime.now(),
        ),
        SubgraphEdge(
            source_node_id="trait_causal_analysis",
            target_node_id="major_media_communication",
            relation_type="RELATED_TO",
            relevance_level=2,
            mapping_version="v1",
            created_at=datetime.now(),
        ),
        SubgraphEdge(
            source_node_id="major_media_communication",
            target_node_id="dept_mock0000000000000001",
            relation_type="HAS_DEPARTMENT",
            relevance_level=3,
            mapping_version="v1",
            created_at=datetime.now(),
        ),
    ]
    return nodes, edges


VERTICAL_SLICE_PROCESSING_ORDER: list[str] = list(VERTICAL_SLICE_CONTEXT_IDS)
