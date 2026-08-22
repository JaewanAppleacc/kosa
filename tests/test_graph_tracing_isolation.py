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
from src.api.mock_data import seed_question_as_finalized
from src.data.questions.vertical_slice_seed_questions import GAME_SEED_01
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAIT_IDS
from src.schemas.assessment_state import AssessmentState

GAME_SEED_01_FINALIZED = seed_question_as_finalized(GAME_SEED_01)


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


if __name__ == "__main__":
    unittest.main()
