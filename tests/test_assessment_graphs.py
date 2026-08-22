"""6단계: 기존 순수 함수를 LangGraph Node로 연결한 결과 검증.

CLAUDE.md 원칙 확인 대상:
- 실제 StateGraph·Conditional Edge로 구현됐는지(흉내만 낸 게 아닌지)
- 재생성 Conditional Edge(자기 자신으로 돌아가는 Edge)가 실제로 존재하는지
- Graph 도입 전후 Evidence·Trait 상태·질문 생성 결과가 동일한지(회귀 없음) —
  이 파일 자체보다도 기존 test_answer_processor.py·test_question_generator.py·
  test_target_planner.py 216개가 전부 변경 없이 그대로 통과한다는 사실이 가장 강력한
  증거다(같은 입력 → 같은 손계산 기대값). 여기서는 Graph 구조 자체와, 기존 테스트가
  다루지 않는 Conditional Edge 경계 조건만 추가로 확인한다.
"""

from __future__ import annotations

import unittest

from langgraph.graph.state import CompiledStateGraph

from src.agents.assessment.answer_processor import submit_answer
from src.agents.assessment.graph.answer_graph import _COMPILED_ANSWER_GRAPH, build_answer_graph
from src.agents.assessment.graph.question_generation_graph import (
    _COMPILED_QUESTION_GENERATION_GRAPH,
    build_question_generation_graph,
)
from src.api.mock_data import seed_question_as_finalized
from src.data.questions.vertical_slice_seed_questions import GAME_SEED_01
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAIT_IDS
from src.schemas.assessment_state import AssessmentState

GAME_SEED_01_FINALIZED = seed_question_as_finalized(GAME_SEED_01)


class GraphsAreRealCompiledStateGraphsTest(unittest.TestCase):
    def test_answer_graph_is_a_compiled_stategraph(self) -> None:
        self.assertIsInstance(_COMPILED_ANSWER_GRAPH, CompiledStateGraph)

    def test_question_generation_graph_is_a_compiled_stategraph(self) -> None:
        self.assertIsInstance(_COMPILED_QUESTION_GENERATION_GRAPH, CompiledStateGraph)


class AnswerGraphStructureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = build_answer_graph().get_graph()
        self.node_names = set(self.graph.nodes.keys())
        self.edges = {(e.source, e.target): e.conditional for e in self.graph.edges}

    def test_has_all_five_design_nodes(self) -> None:
        """§5-2: Option 검증(validate_option) → Evidence Update → Stop/Continue(Conditional)
        → Target Planner. 4개 실제 Node가 전부 그래프에 있어야 한다."""

        for node in ["validate_option", "evidence_update", "stop_or_continue", "target_planner"]:
            self.assertIn(node, self.node_names)

    def test_stop_or_continue_is_a_real_conditional_edge(self) -> None:
        self.assertTrue(self.edges.get(("stop_or_continue", "__end__")))
        self.assertTrue(self.edges.get(("stop_or_continue", "target_planner")))

    def test_validate_option_rejection_is_a_real_conditional_edge(self) -> None:
        self.assertTrue(self.edges.get(("validate_option", "__end__")))
        self.assertTrue(self.edges.get(("validate_option", "evidence_update")))


class QuestionGenerationGraphStructureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = build_question_generation_graph().get_graph()
        self.node_names = set(self.graph.nodes.keys())
        self.edges = {(e.source, e.target): e.conditional for e in self.graph.edges}

    def test_has_all_four_nodes(self) -> None:
        for node in ["check_cache", "prepare_prompt", "generate_attempt", "use_backup"]:
            self.assertIn(node, self.node_names)

    def test_regeneration_self_loop_edge_exists(self) -> None:
        """CLAUDE.md "생성 실패 시 ... 재생성 ... 순서로 완주 가능한 경로를 제공한다"의
        실제 그래프 표현 — generate_attempt가 실패하면 자기 자신으로 돌아가는 Conditional
        Edge가 있어야 한다(예전엔 for 루프 안에 숨어 있었다)."""

        self.assertTrue(self.edges.get(("generate_attempt", "generate_attempt")))

    def test_cache_hit_conditional_edge_can_skip_generation_entirely(self) -> None:
        self.assertTrue(self.edges.get(("check_cache", "__end__")))
        self.assertTrue(self.edges.get(("check_cache", "prepare_prompt")))


class AnswerGraphBehaviorPreservationTest(unittest.TestCase):
    """공개 함수 submit_answer()가 Graph 도입 전과 정확히 같은 반환값을 주는지 손계산으로
    다시 확인한다(test_answer_processor.py의 동일 시나리오를 여기서도 독립적으로 검증)."""

    def test_seed_answer_produces_same_evidence_and_stop_decision_as_before(self) -> None:
        state = AssessmentState(session_id="sess_test", user_id="demo_user_01")
        result = submit_answer(
            state, GAME_SEED_01_FINALIZED, "game_seed_01_o1", VERTICAL_SLICE_TRAIT_IDS, True
        )
        self.assertTrue(result.accepted)
        self.assertEqual(result.stop_decision, "CONTINUE")
        self.assertEqual(result.next_planner_decision.purpose, "관심 지점 심화 확인")
        self.assertEqual(len(state.evidence_ledger), 1)
        self.assertEqual(state.evidence_ledger[0].applied_primary_trait_delta, {"causal_analysis": 1})
        self.assertEqual(state.trait_summaries["causal_analysis"].support_count, 1)

    def test_rejected_option_does_not_reach_evidence_update_node(self) -> None:
        state = AssessmentState(session_id="sess_test", user_id="demo_user_01")
        result = submit_answer(
            state, GAME_SEED_01_FINALIZED, "not_a_real_option_id", VERTICAL_SLICE_TRAIT_IDS, True
        )
        self.assertFalse(result.accepted)
        self.assertEqual(len(state.evidence_ledger), 0)  # validate_option 이후 노드가 실행 안 됨


if __name__ == "__main__":
    unittest.main()
