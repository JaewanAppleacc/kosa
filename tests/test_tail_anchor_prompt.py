"""일반 Adaptive Tail LLM Prompt에 전달하는 Anchor 정보 — 2026-08-23 Trait Ontology
v2(2.5.2단계) §2/§3/§4/§15.

2.5.1단계에서는 V2 Direct Probe에만 Anchor를 연결했고, 일반 Adaptive Tail
(`generate_tail_question`)에는 연결하지 않았다(2.5.2단계 §1 재현: Anchor만 다른 두
State의 Tail Prompt가 완전히 동일했다). 이 파일은 그 연결이 실제로 동작하는지,
role_id·Trait Mapping은 Anchor와 무관하게 그대로인지, 내부 점수·전공 결과가 Prompt에
새지 않는지 확인한다."""

from __future__ import annotations

import unittest

from src.agents.assessment.graph.question_generation_graph import _build_user_prompt, generate_tail_question
from src.data.contexts.context_anchor_presentations import CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY
from src.data.contexts.context_definitions import CONTEXT_DEFINITIONS
from src.data.questions.tail_option_blueprints import TAIL_OPTION_BLUEPRINTS_BY_ID
from src.llm.protocols import LLMCallError
from src.schemas.question import GeneratedOption, GeneratedQuestion, QuestionGenerationResult
from src.services.trait_ontology_v2 import load_trait_ontology_v2

CONTEXT_DEFINITIONS_BY_ID = {c.context_id: c for c in CONTEXT_DEFINITIONS}
_TRAIT_DEFS = {t.trait_id: t for t in load_trait_ontology_v2()}

_BLUEPRINT_ID = "problem_response_v1"
_BLUEPRINT = TAIL_OPTION_BLUEPRINTS_BY_ID[_BLUEPRINT_ID]
_ROLE_IDS = [r.role_id for r in _BLUEPRINT.roles]
_TRAIT_ID = next(iter(_BLUEPRINT.roles[0].primary_trait_delta))
_TRAIT_DEF = _TRAIT_DEFS[_TRAIT_ID]
_ANCHOR = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("game", "cooperative_role")]


class _StubLLMClient:
    def __init__(self, question_text: str = "테스트 질문?") -> None:
        self.question_text = question_text
        self.call_count = 0
        self.last_user_prompt: str | None = None

    def complete_structured(self, *, system_prompt, user_prompt, response_model):
        self.call_count += 1
        self.last_user_prompt = user_prompt
        return QuestionGenerationResult(
            question=GeneratedQuestion(
                context="game", target_traits=[_TRAIT_ID], frame_id="problem_check",
                question_text=self.question_text,
                options=[GeneratedOption(role_id=r, text=f"{r} 문장") for r in _ROLE_IDS],
            )
        )


class _AlwaysFailLLMClient:
    def complete_structured(self, *, system_prompt, user_prompt, response_model):
        raise LLMCallError("의도적 실패")


def _generate(llm_client, anchor=None, **overrides):
    kwargs = dict(
        question_id="game_tail_anchor_test",
        context_definition=CONTEXT_DEFINITIONS_BY_ID["game"],
        trait_definition=_TRAIT_DEF,
        all_trait_labels={tid: d.label for tid, d in _TRAIT_DEFS.items()},
        option_blueprint_id=_BLUEPRINT_ID,
        frame_id="problem_check",
        frame_text="문제가 생기면 무엇부터 확인하는가?",
        llm_client=llm_client,
        anchor=anchor,
    )
    kwargs.update(overrides)
    return generate_tail_question(**kwargs)


class PromptContentTest(unittest.TestCase):
    def test_no_anchor_prompt_has_no_anchor_section(self) -> None:
        prompt = _build_user_prompt(
            context_definition=CONTEXT_DEFINITIONS_BY_ID["game"], trait_definition=_TRAIT_DEF,
            frame_id="problem_check", frame_text="힌트", blueprint_role_trait_labels=[(r, r) for r in _ROLE_IDS],
            anchor=None,
        )
        self.assertNotIn("[학생이 선택한 세부 Context", prompt)

    def test_anchor_prompt_includes_label_preferred_scenarios_and_forbidden(self) -> None:
        prompt = _build_user_prompt(
            context_definition=CONTEXT_DEFINITIONS_BY_ID["game"], trait_definition=_TRAIT_DEF,
            frame_id="problem_check", frame_text="힌트", blueprint_role_trait_labels=[(r, r) for r in _ROLE_IDS],
            anchor=_ANCHOR,
        )
        self.assertIn(_ANCHOR.label, prompt)
        for scenario in _ANCHOR.preferred_scenarios:
            self.assertIn(scenario, prompt)

    def test_anchor_block_has_no_trait_score_or_major_or_profile_wording(self) -> None:
        prompt = _build_user_prompt(
            context_definition=CONTEXT_DEFINITIONS_BY_ID["game"], trait_definition=_TRAIT_DEF,
            frame_id="problem_check", frame_text="힌트", blueprint_role_trait_labels=[(r, r) for r in _ROLE_IDS],
            anchor=_ANCHOR,
        )
        anchor_block_start = prompt.index("[학생이 선택한 세부 Context")
        anchor_block_end = prompt.index("[직전 질문·답변") if "[직전 질문·답변" in prompt else prompt.index(
            "[이번 질문이 다뤄야 할 Trait"
        )
        anchor_block = prompt[anchor_block_start:anchor_block_end]
        for forbidden_word in ("전공", "Profile", "profile", "점수", "score", _TRAIT_ID):
            self.assertNotIn(forbidden_word, anchor_block)


class GenerationWithAnchorTest(unittest.TestCase):
    def test_no_anchor_matches_existing_behavior(self) -> None:
        llm = _StubLLMClient()
        outcome = _generate(llm, anchor=None)
        self.assertEqual(outcome.source, "llm")
        self.assertNotIn("[학생이 선택한 세부 Context", llm.last_user_prompt)

    def test_anchor_changes_prompt_context(self) -> None:
        llm_a = _StubLLMClient()
        _generate(llm_a, anchor=CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("game", "story_exploration")])
        llm_b = _StubLLMClient()
        _generate(llm_b, anchor=CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("game", "cooperative_role")])
        self.assertNotEqual(llm_a.last_user_prompt, llm_b.last_user_prompt)

    def test_role_ids_and_mapping_unchanged_regardless_of_anchor(self) -> None:
        llm = _StubLLMClient()
        outcome = _generate(llm, anchor=_ANCHOR)
        self.assertEqual({o.role_id for o in outcome.question.options}, set(_ROLE_IDS))
        self.assertEqual(outcome.question.target_traits, [_TRAIT_ID])

    def test_llm_output_with_forbidden_assumption_is_rejected_and_falls_back(self) -> None:
        # cooperative_role은 forbidden_assumptions가 비어 있으므로, 다른 Anchor로 확인한다.
        anchor = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("game", "story_exploration")]
        llm = _StubLLMClient(question_text="팀원과 경기 순위를 다투는 상황에서 무엇부터 하나요?")
        from src.data.questions.vertical_slice_backup_questions import VERTICAL_SLICE_BACKUP_QUESTIONS

        outcome = _generate(
            llm, anchor=anchor, backup_questions=VERTICAL_SLICE_BACKUP_QUESTIONS["game"], max_regenerations=1,
        )
        # Quality Gate가 forbidden_assumptions("팀원")를 걸러내 재생성까지 실패하고
        # 중립 Backup으로 떨어져야 한다 — LLM이 생성한 문구가 그대로 채택되지 않는다.
        self.assertEqual(outcome.source, "backup")
        self.assertEqual(llm.call_count, 2)  # 최초 시도 + 재생성 1회, 둘 다 거부됨

    def test_llm_call_error_with_anchor_falls_back(self) -> None:
        from src.data.questions.vertical_slice_backup_questions import VERTICAL_SLICE_BACKUP_QUESTIONS

        outcome = _generate(
            _AlwaysFailLLMClient(), anchor=_ANCHOR,
            backup_questions=VERTICAL_SLICE_BACKUP_QUESTIONS["game"], max_regenerations=0,
        )
        self.assertEqual(outcome.source, "backup")


if __name__ == "__main__":
    unittest.main()
