"""꼬리질문 생성기(§10/§11) 테스트 — 실제 네트워크 호출 없이 Fake LLM Client로 검증한다."""

from __future__ import annotations

import unittest

from src.agents.assessment.question_generator import generate_tail_question
from src.data.contexts.context_definitions import CONTEXT_DEFINITIONS
from src.data.questions.vertical_slice_backup_questions import VERTICAL_SLICE_BACKUP_QUESTIONS
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAITS
from src.llm.protocols import LLMCallError
from src.schemas.question import GeneratedOption, GeneratedQuestion, QuestionGenerationResult

CONTEXT_DEFINITIONS_BY_ID = {c.context_id: c for c in CONTEXT_DEFINITIONS}
TRAIT_DEFINITIONS_BY_ID = {t.trait_id: t for t in VERTICAL_SLICE_TRAITS}

# causal_analysis는 problem_response_v1 Blueprint 소속 — 5개 role_id는 이 순서.
BLUEPRINT_ROLE_IDS = ["cause_analysis", "strategy_change", "direct_trial", "external_research", "ask_others"]


def _valid_generated_question(frame_id: str = "problem_check") -> GeneratedQuestion:
    return GeneratedQuestion(
        context="game",
        target_traits=["causal_analysis"],
        frame_id=frame_id,
        question_text="예상과 다른 결과가 나오면 무엇부터 하나요?",
        options=[GeneratedOption(role_id=r, text=f"{r} 선택지 문장") for r in BLUEPRINT_ROLE_IDS],
    )


class _ScriptedFakeLLMClient:
    """호출할 때마다 미리 정해둔 결과/예외를 순서대로 반환한다."""

    def __init__(self, scripted_results: list[object]) -> None:
        self._scripted_results = scripted_results
        self.call_count = 0
        self.captured_user_prompts: list[str] = []

    def complete_structured(self, *, system_prompt, user_prompt, response_model):
        self.captured_user_prompts.append(user_prompt)
        result = self._scripted_results[self.call_count]
        self.call_count += 1
        if isinstance(result, Exception):
            raise result
        return result


class GenerateTailQuestionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.context_definition = CONTEXT_DEFINITIONS_BY_ID["game"]
        self.trait_definition = TRAIT_DEFINITIONS_BY_ID["causal_analysis"]
        self.backups = VERTICAL_SLICE_BACKUP_QUESTIONS["game"]

    def _generate(self, client, **overrides):
        kwargs = dict(
            question_id="game_tail_02",
            context_definition=self.context_definition,
            trait_definition=self.trait_definition,
            all_trait_labels={tid: t.label for tid, t in TRAIT_DEFINITIONS_BY_ID.items()},
            frame_id="problem_check",
            frame_text="문제가 생기면 무엇부터 확인하는가?",
            llm_client=client,
            backup_questions=self.backups,
        )
        kwargs.update(overrides)
        return generate_tail_question(**kwargs)

    def test_happy_path_returns_llm_generated_question(self) -> None:
        client = _ScriptedFakeLLMClient(
            [QuestionGenerationResult(question=_valid_generated_question())]
        )
        outcome = self._generate(client)
        self.assertEqual(outcome.source, "llm")
        self.assertIsNotNone(outcome.question)
        self.assertEqual(outcome.question.question_id, "game_tail_02")
        self.assertEqual(len(outcome.question.options), 5)
        self.assertEqual(client.call_count, 1)

    def test_previous_next_probe_is_threaded_into_prompt_not_into_target(self) -> None:
        """§7-3/§8: next_probe는 프롬프트의 "말투" 재료로만 들어가야 하고, target_trait이나
        Blueprint Role 구성 자체는 바뀌면 안 된다."""

        client = _ScriptedFakeLLMClient(
            [QuestionGenerationResult(question=_valid_generated_question())]
        )
        outcome = self._generate(
            client, previous_next_probe="원인 분석을 더 깊이 파고드는 경향인지 확인"
        )
        self.assertEqual(outcome.source, "llm")
        self.assertEqual(len(client.captured_user_prompts), 1)
        self.assertIn("원인 분석을 더 깊이 파고드는 경향인지 확인", client.captured_user_prompts[0])
        # 목표 Trait은 여전히 causal_analysis(problem_response_v1)이어야 한다 — next_probe가
        # 다른 Trait/Blueprint로 목표를 바꾸지 않는다.
        self.assertEqual(outcome.question.target_traits, ["causal_analysis"])

    def test_no_previous_next_probe_omits_continuity_block(self) -> None:
        client = _ScriptedFakeLLMClient(
            [QuestionGenerationResult(question=_valid_generated_question())]
        )
        self._generate(client, previous_next_probe=None)
        self.assertNotIn("직전 답변의 관심 신호", client.captured_user_prompts[0])

    def test_llm_call_error_falls_back_to_backup_after_one_regeneration(self) -> None:
        client = _ScriptedFakeLLMClient([LLMCallError("네트워크 실패"), LLMCallError("네트워크 실패")])
        outcome = self._generate(client)
        self.assertEqual(outcome.source, "backup")
        self.assertIsNotNone(outcome.question)
        self.assertEqual(outcome.question.context, "game")
        self.assertEqual(client.call_count, 2)  # 최초 1회 + 재생성 1회(max_regenerations=1 기본값)

    def test_role_id_mismatch_falls_back_to_backup(self) -> None:
        bad_question = _valid_generated_question().model_copy(
            update={"options": [GeneratedOption(role_id="not_a_real_role", text="x") for _ in range(5)]}
        )
        client = _ScriptedFakeLLMClient(
            [
                QuestionGenerationResult(question=bad_question),
                QuestionGenerationResult(question=bad_question),
            ]
        )
        outcome = self._generate(client)
        self.assertEqual(outcome.source, "backup")
        self.assertIn("거부", outcome.failure_reason or "")

    def test_quality_gate_failure_falls_back_to_backup(self) -> None:
        forbidden = _valid_generated_question().model_copy(
            update={"question_text": "이 활동을 잘하는 편인가?"}
        )
        client = _ScriptedFakeLLMClient(
            [
                QuestionGenerationResult(question=forbidden),
                QuestionGenerationResult(question=forbidden),
            ]
        )
        outcome = self._generate(client)
        self.assertEqual(outcome.source, "backup")
        self.assertIn("Quality Gate", outcome.failure_reason or "")

    def test_backup_exhausted_returns_none_question(self) -> None:
        client = _ScriptedFakeLLMClient([LLMCallError("실패"), LLMCallError("실패")])
        used_ids = {b.question_id for b in self.backups}
        outcome = self._generate(client, used_backup_question_ids=used_ids)
        self.assertEqual(outcome.source, "exhausted")
        self.assertIsNone(outcome.question)

    def test_cache_hit_skips_llm_call(self) -> None:
        cached = _valid_generated_question()  # GeneratedQuestion이 아니라 FinalizedQuestion이 필요하므로 아래에서 변환
        from src.data.questions.tail_option_blueprints import blueprint_for_target_trait
        from src.schemas.question import finalize_question

        finalized = finalize_question(
            "game_tail_02", cached, blueprint_for_target_trait("causal_analysis")
        )
        client = _ScriptedFakeLLMClient([])  # 호출되면 IndexError로 바로 실패 — HIT라면 호출 자체가 없어야 함
        cache_key = "game:problem_check:causal_analysis"
        outcome = self._generate(client, question_cache={cache_key: finalized})
        self.assertEqual(outcome.source, "cache")
        self.assertEqual(client.call_count, 0)


if __name__ == "__main__":
    unittest.main()
