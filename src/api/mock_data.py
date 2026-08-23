"""B·C가 실제 계산 로직 완성을 기다리지 않고 화면/데이터 작업을 시작할 수 있도록 만든
손으로 채운 예시 데이터. A 지시서 §3: "B와 C가 실제 구현을 기다리지 않고 작업할 수 있도록
Mock 응답을 먼저 제공한다." 실제 값이 아니라 "이런 모양이 온다"를 보여주는 용도다.
"""

from __future__ import annotations

from datetime import date, datetime

from src.data.contexts.context_definitions import VERTICAL_SLICE_CONTEXT_IDS
from src.data.question_frames.frame_role_map import QUESTION_FRAME_TEXT
from src.data.questions.seed_anchor_variants import SEED_ANCHOR_VARIANTS_BY_KEY
from src.data.questions.vertical_slice_seed_questions import VERTICAL_SLICE_SEED_QUESTIONS
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAIT_IDS
from src.ids import generate_option_id
from src.schemas.course import CourseProfile, CourseRecommendationItem, ParsedSubjectCandidate
from src.schemas.major import AdmissionReference, Department
from src.schemas.question import FinalizedOption, FinalizedQuestion, SeedQuestion
from src.schemas.retrieval import RetrievedDocument


def seed_question_as_finalized(seed: SeedQuestion, anchor_id: str | None = None) -> FinalizedQuestion:
    """실제 확정된 Seed Question(§7-1)을 B가 받는 FinalizedQuestion 모양으로 바꾼다.
    target_traits/frame_id는 Seed에 없는 개념이라(Adaptive 전용) 빈 값·"seed_frame"으로 채운다.

    2026-08-23 Trait Ontology v2(2.5.1단계) §4/§5 — `anchor_id`가 주어지고 그
    (context, anchor_id)에 등록된 `SeedAnchorVariant`가 있으면 question_text와 각
    옵션의 text를 그 Variant 문구로 바꾼다. `option_id`/`role_id`/`primary_trait_delta`/
    `next_probe`는 항상 원본 SeedQuestion 값을 그대로 쓴다 — Anchor는 표현만 바꿀 뿐
    Trait Mapping을 전혀 건드리지 않는다(§2). Variant가 없으면(미등록 Anchor, Anchor
    미선택) 기존 중립 문구를 그대로 쓴다(§13 "Anchor가 없어도 기존 중립 질문 가능")."""

    variant = SEED_ANCHOR_VARIANTS_BY_KEY.get((seed.context, anchor_id)) if anchor_id else None
    question_text = variant.question_text if variant else seed.question_text

    return FinalizedQuestion(
        question_id=seed.question_id,
        context=seed.context,
        target_traits=[],
        frame_id="seed_frame",
        question_text=question_text,
        options=[
            FinalizedOption(
                option_id=o.option_id,
                role_id=o.role_id,
                text=variant.option_text_by_role_id[o.role_id] if variant else o.text,
                primary_trait_delta=o.primary_trait_delta,
                next_probe=o.next_probe,
            )
            for o in seed.options
        ],
    )


def tail_question_from_planner_decision(
    question_id: str,
    context_id: str,
    target_traits: list[str],
    question_frame: str,
) -> FinalizedQuestion:
    """Target Planner(§8)가 정한 목표 Trait·Frame을 실제로 반영한 꼬리질문을 만든다.
    목표 Trait와 Frame 문구는 진짜지만, 아직 LLM 연동(§10)이 없어서 선택지 문장은
    Mock이다 — "구조는 실제, 문구는 가짜"인 중간 단계라는 걸 alt(선택지 텍스트)에
    그대로 드러낸다."""

    target_trait = target_traits[0] if target_traits else "causal_analysis"
    other_traits = [t for t in sorted(VERTICAL_SLICE_TRAIT_IDS) if t != target_trait][:4]
    all_traits = [target_trait, *other_traits]
    frame_text = QUESTION_FRAME_TEXT.get(question_frame, "다음 상황에서 어떻게 하나요?")

    return FinalizedQuestion(
        question_id=question_id,
        context=context_id,
        target_traits=[target_trait],
        frame_id=question_frame,
        question_text=frame_text,
        options=[
            FinalizedOption(
                option_id=generate_option_id(question_id, i),
                role_id=f"role_{trait}",
                text=f"[Mock] {trait} 관련 선택지 — 실제 LLM 문구 생성(§10) 전까지의 자리표시자",
                primary_trait_delta={trait: 1},
            )
            for i, trait in enumerate(all_traits, start=1)
        ],
    )


def next_mock_question(
    context_id: str, questions_asked_in_current_context: int, anchor_id: str | None = None,
) -> FinalizedQuestion:
    """이 Context에서 첫 질문(0개 답변)이면 실제 Seed를, 그 이후엔 여전히 Mock 꼬리질문을
    반환한다 — 실제 Adaptive 질문 생성(§10)은 아직 없다.

    2.5.1단계 §5: `anchor_id`는 Seed(첫 질문)에만 적용한다 — Tail(`mock_finalized_question`)은
    아직 실제 LLM 연동이 없는 자리표시자 Mock이라 Anchor 반영 대상이 아니다(§24에
    한계로 명시)."""

    if questions_asked_in_current_context == 0 and context_id in VERTICAL_SLICE_SEED_QUESTIONS:
        return seed_question_as_finalized(VERTICAL_SLICE_SEED_QUESTIONS[context_id], anchor_id=anchor_id)
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


# 2026-08-21 리뷰: mock_career_profile()/mock_majors_relevance()는 여기서 삭제했다.
# /profile, /majors 둘 다 이제 항상 실제 계산 경로를 타서(LLM 없으면 profile_generator의
# 결정론적 Fallback, 답변 없으면 EVIDENCE_NOT_READY/insufficient_evidence_message) 이
# 함수들을 부르는 곳이 하나도 안 남았다 — 무관한 학생의 고정 Profile·전공을 보여주는
# 경로 자체를 코드에서 없앴다.


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
                label="데이터 과학",
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


# 2026-08-28 19차 리뷰: mock_subgraph()는 삭제했다 — GET /subgraph/{session_id}가
# KnowledgeSubgraphService(src/services/knowledge_subgraph_service.py)의 실제 계산으로
# 완전히 교체돼 더 이상 이 함수를 호출하는 곳이 없다(테스트·Mock JSON 생성 스크립트
# 포함, 삭제 전 전부 확인함).


VERTICAL_SLICE_PROCESSING_ORDER: list[str] = list(VERTICAL_SLICE_CONTEXT_IDS)
