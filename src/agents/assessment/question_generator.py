"""꼬리질문 생성 — 설계안 §10(Question Generator)·§11(Quality Gate·Fallback)의 공개 진입점.

2026-08-22 6단계: 실제 구현을 src/agents/assessment/graph/question_generation_graph.py의
LangGraph StateGraph로 옮겼다(Cache 조회 → 실시간 생성[재생성 Conditional Edge] → Backup
순서가 이제 Python for 루프가 아니라 실제 Graph Node·Edge로 표현된다). 이 파일은 기존
import 경로(`from src.agents.assessment.question_generator import generate_tail_question`)를
유지하기 위한 얇은 재노출이다.
"""

from __future__ import annotations

from src.agents.assessment.graph.question_generation_graph import (
    QuestionGenerationOutcome,
    generate_tail_question,
)

__all__ = ["QuestionGenerationOutcome", "generate_tail_question"]
