"""6단계 발견 사항: LangGraph/LangChain은 LANGSMITH_TRACING 환경변수만 보고 원본 Node
입출력(학생 답변 원문·생성된 질문 원문 포함)을 §24 Sanitizer 없이 자동으로 LangSmith에
전송하려 한다 — 직접 확인해보니 실제로 `Client.create_run`이 호출된다. answer_graph.py·
question_generation_graph.py가 `tracing_context(enabled=False)`로 이 자동 전송을 확실히
막고 있는지 회귀 테스트로 고정한다.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from langsmith.client import Client

from src.agents.assessment.answer_processor import submit_answer
from src.agents.assessment.question_generator import generate_tail_question
from src.api.mock_data import seed_question_as_finalized
from src.data.contexts.context_definitions import CONTEXT_DEFINITIONS
from src.data.questions.vertical_slice_backup_questions import VERTICAL_SLICE_BACKUP_QUESTIONS
from src.data.questions.vertical_slice_seed_questions import GAME_SEED_01
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAIT_IDS, VERTICAL_SLICE_TRAITS
from src.schemas.assessment_state import AssessmentState
from src.schemas.question import GeneratedOption, GeneratedQuestion, QuestionGenerationResult

GAME_SEED_01_FINALIZED = seed_question_as_finalized(GAME_SEED_01)

_CONTEXT_DEFINITIONS_BY_ID = {c.context_id: c for c in CONTEXT_DEFINITIONS}
_TRAIT_DEFINITIONS_BY_ID = {t.trait_id: t for t in VERTICAL_SLICE_TRAITS}
_BLUEPRINT_ROLE_IDS = ["cause_analysis", "strategy_change", "direct_trial", "external_research", "ask_others"]


class _FakeLLMClient:
    """실제 네트워크 호출 없이 QuestionGenerationResult를 즉시 반환하는 대역."""

    def complete_structured(self, *, system_prompt, user_prompt, response_model):
        return QuestionGenerationResult(
            question=GeneratedQuestion(
                context="game",
                target_traits=["causal_analysis"],
                frame_id="problem_check",
                question_text="예상과 다른 결과가 나오면 무엇부터 하나요?",
                options=[
                    GeneratedOption(role_id=r, text=f"{r} 선택지 문장 — 학생이 직접 고를 실제 문장")
                    for r in _BLUEPRINT_ROLE_IDS
                ],
            )
        )


class GraphDoesNotAutoTraceRawStateTest(unittest.TestCase):
    """LANGSMITH_TRACING=true + 가짜 API Key가 환경변수에 있어도(로컬 .env를 흉내낸
    상황), 그래프 실행이 LangChain의 자동(비Sanitizer) 전송 경로를 타면 안 된다."""

    def setUp(self) -> None:
        env_patcher = patch.dict(
            "os.environ",
            {"LANGSMITH_TRACING": "true", "LANGSMITH_API_KEY": "ls-fake-key-for-test"},
        )
        env_patcher.start()
        self.addCleanup(env_patcher.stop)

        create_run_patcher = patch.object(Client, "create_run")
        self.mock_create_run = create_run_patcher.start()
        self.addCleanup(create_run_patcher.stop)

    def test_answer_graph_never_calls_langsmith_create_run_directly(self) -> None:
        state = AssessmentState(session_id="sess_test", user_id="demo_user_01")
        submit_answer(
            state, GAME_SEED_01_FINALIZED, "game_seed_01_o1", VERTICAL_SLICE_TRAIT_IDS, True
        )
        self.mock_create_run.assert_not_called()

    def test_question_generation_graph_never_calls_langsmith_create_run_directly(self) -> None:
        """2026-08-22 리뷰 5항목: answer_graph만이 아니라 question_generation_graph도
        같은 위험(생성된 질문·선택지 원문, 직전 답변 원문이 원본 그대로 자동 전송될 수
        있음)이 있다 — 실제 LLM 생성 경로(Fake Client)로 그래프를 끝까지 실행해도
        Client.create_run이 전혀 호출되지 않아야 한다."""

        outcome = generate_tail_question(
            question_id="game_tail_02",
            context_definition=_CONTEXT_DEFINITIONS_BY_ID["game"],
            trait_definition=_TRAIT_DEFINITIONS_BY_ID["causal_analysis"],
            all_trait_labels={tid: t.label for tid, t in _TRAIT_DEFINITIONS_BY_ID.items()},
            option_blueprint_id="problem_response_v1",
            frame_id="problem_check",
            frame_text="문제가 생기면 무엇부터 확인하는가?",
            llm_client=_FakeLLMClient(),
            previous_question_texts=["게임을 할 때 가장 재미있다고 느끼는 순간은 언제인가요?"],
            previous_answer_text="왜 이런 결과가 나왔는지 이유와 원리를 알아가는 순간",
            backup_questions=VERTICAL_SLICE_BACKUP_QUESTIONS["game"],
        )

        self.assertEqual(outcome.source, "llm")  # Fake Client가 정상 생성했는지 전제 확인
        self.mock_create_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
