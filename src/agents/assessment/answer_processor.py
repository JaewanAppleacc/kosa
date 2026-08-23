"""답변 처리 파이프라인 — 설계안 §5-2 Assessment Graph 중 "학생 답변 → ... → 다음 질문
목표 결정" 구간의 공개 진입점.

2026-08-22 6단계: 실제 구현을 src/agents/assessment/graph/answer_graph.py의 LangGraph
StateGraph로 옮겼다. 이 파일은 기존 import 경로(`from
src.agents.assessment.answer_processor import submit_answer`)를 그대로 유지하기 위한
얇은 재노출(re-export)이다 — main.py도, 기존 테스트도 이 파일이 LangGraph를 쓰는지 몰라도
된다(6단계 지시사항: "API 응답 계약을 유지하면서 그래프를 통해 호출").
"""

from __future__ import annotations

from src.agents.assessment.graph.answer_graph import AnswerSubmissionResult, submit_answer

__all__ = ["AnswerSubmissionResult", "submit_answer"]
