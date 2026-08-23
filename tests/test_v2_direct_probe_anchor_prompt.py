"""V2 Direct Probe LLM Prompt에 전달하는 Anchor 정보 — 2026-08-23 Trait Ontology
v2(2.5.1단계) §6/§10/§13.

`generate_v2_direct_probe_question()`에 `anchor`를 넘기면 (1) Prompt에 그 Anchor의
상황 정보가 실제로 포함되는지, (2) role_id 집합·Trait Mapping은 Anchor와 무관하게
그대로인지(`finalize_v2_probe_question`이 구조적으로 강제하므로 당연하지만 회귀
확인용으로 다시 짚는다), (3) 생성된 문장에 `forbidden_assumptions` 문구가 남아 있으면
재생성하고, 계속 실패하면 Anchor를 반영하지 않은 중립 Fallback을 쓰는지 확인한다."""

from __future__ import annotations

import unittest

from src.agents.assessment.v2_direct_probe_generator import _build_user_prompt, generate_v2_direct_probe_question
from src.data.contexts.context_anchor_presentations import CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY
from src.data.contexts.context_definitions import CONTEXT_DEFINITIONS

CONTEXT_DEFINITIONS_BY_ID = {c.context_id: c for c in CONTEXT_DEFINITIONS}
from src.data.questions.trait_v2_direct_probe_blueprints import V2_DIRECT_PROBE_BLUEPRINTS_BY_ID
from src.llm.protocols import LLMCallError
from src.schemas.question import GeneratedOption, GeneratedQuestion, QuestionGenerationResult

_BLUEPRINT = V2_DIRECT_PROBE_BLUEPRINTS_BY_ID["systems_thinking_game_v1"]
_CONTEXT_DEF = CONTEXT_DEFINITIONS_BY_ID["game"]
_ANCHOR = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("game", "story_exploration")]


class _StubLLMClient:
    def __init__(self, question_text: str) -> None:
        self.question_text = question_text
        self.call_count = 0
        self.last_user_prompt: str | None = None

    def complete_structured(self, *, system_prompt, user_prompt, response_model):
        self.call_count += 1
        self.last_user_prompt = user_prompt
        role_ids = [m.role_id for m in _BLUEPRINT.option_mappings]
        return QuestionGenerationResult(
            question=GeneratedQuestion(
                context="game", target_traits=[], frame_id=_BLUEPRINT.question_frame_id,
                question_text=self.question_text,
                options=[GeneratedOption(role_id=r, text=f"{r} 상황 문장") for r in role_ids],
            )
        )


class _AlwaysFailLLMClient:
    def complete_structured(self, *, system_prompt, user_prompt, response_model):
        raise LLMCallError("의도적 실패")


class PromptContentTest(unittest.TestCase):
    def test_no_anchor_prompt_has_no_anchor_section(self) -> None:
        prompt = _build_user_prompt(context_definition=_CONTEXT_DEF, blueprint=_BLUEPRINT, anchor=None)
        self.assertNotIn("[학생이 고른 세부 상황", prompt)

    def test_anchor_prompt_includes_label_scenarios_and_forbidden_assumptions(self) -> None:
        prompt = _build_user_prompt(context_definition=_CONTEXT_DEF, blueprint=_BLUEPRINT, anchor=_ANCHOR)
        self.assertIn(_ANCHOR.label, prompt)
        for scenario in _ANCHOR.preferred_scenarios:
            self.assertIn(scenario, prompt)
        for phrase in _ANCHOR.forbidden_assumptions:
            self.assertIn(phrase, prompt)

    def test_anchor_prompt_does_not_mention_role_id_or_trait_id(self) -> None:
        """§6: Anchor 정보 블록 자체는 role_id·Trait 이름을 언급하지 않아야 한다 —
        LLM이 Anchor에서 새 Trait를 추론할 실마리를 주지 않기 위해서다."""

        prompt = _build_user_prompt(context_definition=_CONTEXT_DEF, blueprint=_BLUEPRINT, anchor=_ANCHOR)
        anchor_block_start = prompt.index("[학생이 고른 세부 상황")
        anchor_block_end = prompt.index("[참고용 기준 질문")
        anchor_block = prompt[anchor_block_start:anchor_block_end]
        self.assertNotIn(_BLUEPRINT.trait_id, anchor_block)
        for mapping in _BLUEPRINT.option_mappings:
            self.assertNotIn(mapping.role_id, anchor_block)


class GenerationWithAnchorTest(unittest.TestCase):
    def test_successful_generation_with_anchor_uses_llm_and_keeps_role_ids(self) -> None:
        llm = _StubLLMClient("이야기 진행 중 예상 못한 상황을 마주치면 무엇을 하나요?")
        outcome = generate_v2_direct_probe_question(
            question_id="test_q1", context_definition=_CONTEXT_DEF, blueprint=_BLUEPRINT,
            llm_client=llm, anchor=_ANCHOR,
        )
        self.assertEqual(outcome.source, "llm")
        self.assertIn(_ANCHOR.label, llm.last_user_prompt)
        self.assertEqual(
            {o.role_id for o in outcome.question.options},
            {m.role_id for m in _BLUEPRINT.option_mappings},
        )
        # Trait Mapping은 base_question과 정확히 같아야 한다(Anchor가 Mapping을 바꾸지 않음).
        base_deltas = {o.role_id: o.primary_trait_delta for o in _BLUEPRINT.base_question.options}
        for option in outcome.question.options:
            self.assertEqual(option.primary_trait_delta, base_deltas[option.role_id])

    def test_no_llm_client_falls_back_to_neutral_base_question_even_with_anchor(self) -> None:
        outcome = generate_v2_direct_probe_question(
            question_id="test_q2", context_definition=_CONTEXT_DEF, blueprint=_BLUEPRINT,
            llm_client=None, anchor=_ANCHOR,
        )
        self.assertEqual(outcome.source, "backup")
        self.assertEqual(outcome.question.question_text, _BLUEPRINT.base_question.question_text)

    def test_llm_output_containing_forbidden_assumption_is_rejected_and_falls_back(self) -> None:
        # story_exploration의 forbidden_assumptions에는 "팀원"이 있다 — LLM이 그 표현을
        # 계속 반환하면 재생성 예산(max_regenerations)을 다 써도 통과하지 못하고
        # 중립 Fallback으로 떨어져야 한다.
        llm = _StubLLMClient("팀원과 함께 이야기를 진행할 때 무엇을 가장 먼저 하나요?")
        outcome = generate_v2_direct_probe_question(
            question_id="test_q3", context_definition=_CONTEXT_DEF, blueprint=_BLUEPRINT,
            llm_client=llm, anchor=_ANCHOR, max_regenerations=1,
        )
        self.assertEqual(outcome.source, "backup")
        self.assertEqual(outcome.question.question_text, _BLUEPRINT.base_question.question_text)
        self.assertEqual(llm.call_count, 2)  # 최초 시도 + 재생성 1회

    def test_llm_call_error_with_anchor_falls_back_to_neutral(self) -> None:
        outcome = generate_v2_direct_probe_question(
            question_id="test_q4", context_definition=_CONTEXT_DEF, blueprint=_BLUEPRINT,
            llm_client=_AlwaysFailLLMClient(), anchor=_ANCHOR, max_regenerations=0,
        )
        self.assertEqual(outcome.source, "backup")


if __name__ == "__main__":
    unittest.main()
