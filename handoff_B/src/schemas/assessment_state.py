"""AssessmentState — LangGraph Checkpointer가 들고 다니는 상태 (설계안 §5-1, §5-2, §22).

CLAUDE.md 아키텍처 불변식: "Assessment 단계에서 전공 추천 결과나 성적을 Planner 입력으로
사용하지 않는다." 이 State에는 그래서 major/전공 관련 필드를 의도적으로 넣지 않는다 —
정책 위반을 코드 리뷰로 잡는 대신 애초에 State에 그 필드 자체가 존재하지 않게 한다.
(tests/test_policy_guard.py에서 이 불변식을 구조적으로 검증한다.)
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from src.schemas.evidence import EvidenceRecord, TraitEvidenceSummary
from src.schemas.question import FinalizedQuestion


class AssessmentPhase(str, Enum):
    INTEREST_RATING = "INTEREST_RATING"
    CONTEXT_SELECTION = "CONTEXT_SELECTION"
    CONTRAST_PROPOSAL = "CONTRAST_PROPOSAL"
    COVERAGE_CHECK = "COVERAGE_CHECK"
    QUESTION_LOOP = "QUESTION_LOOP"
    PROFILE_GENERATION = "PROFILE_GENERATION"
    DONE = "DONE"


class AnsweredQuestion(BaseModel):
    question_id: str
    selected_option_id: str
    selected_role_id: str


class AssessmentState(BaseModel):
    session_id: str
    user_id: str
    phase: AssessmentPhase = AssessmentPhase.INTEREST_RATING

    # §5-1 Context 선택 흐름
    interest_ratings: dict[str, int] = {}  # context_id -> 1~5
    selected_preferred_contexts: list[str] = []  # 학생이 직접 고른 4개
    contrast_context_id: str | None = None
    coverage_replacement_offered: list[str] = []  # 최대 2개
    final_contexts: list[str] = []  # 확정된 심층 Context (Vertical Slice에서는 3개)
    context_processing_order: list[str] = []  # 선호 4개 → Contrast 마지막

    # §5-2 질문 진행
    current_context_index: int = 0
    current_question: FinalizedQuestion | None = None
    questions_asked_in_current_context: int = 0
    answers: list[AnsweredQuestion] = []

    # §12/§13 Evidence·Trait 상태
    evidence_ledger: list[EvidenceRecord] = []
    trait_summaries: dict[str, TraitEvidenceSummary] = {}

    # §24 LLM 호출 예산
    llm_call_count: int = 0
    regeneration_count_current_question: int = 0

    # §5-3 Stop Condition
    stop_reason: str | None = None

    @property
    def current_context_id(self) -> str | None:
        if 0 <= self.current_context_index < len(self.context_processing_order):
            return self.context_processing_order[self.current_context_index]
        return None
