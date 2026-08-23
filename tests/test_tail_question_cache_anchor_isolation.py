"""Tail 질문 Cache의 Anchor 격리 — 2026-08-23 Trait Ontology v2(2.5.2단계) §5/§15.

`generate_tail_question()`/`_check_cache()`는 `question_cache` 매개변수를 받지만,
2.5.2단계 시점까지 `src/api/main.py`의 실제 호출부는 이 값을 한 번도 전달하지 않는다
(재현: `question_cache=` 호출 횟수 0회) — 그래서 지금은 세션을 넘어 실제로 공유되는
영속 Cache가 없다. 이 파일은 그 사실을 문서화하는 동시에, Cache 메커니즘 자체가
나중에 배선되더라도 안전하도록 Cache Key가 Anchor를 실제로 격리하는지 함수 레벨에서
확인한다."""

from __future__ import annotations

import inspect
import unittest

from src.agents.assessment.graph.question_generation_graph import (
    QuestionGenerationGraphState,
    _check_cache,
    generate_tail_question,
)
from src.data.contexts.context_anchor_presentations import CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY
from src.data.contexts.context_definitions import CONTEXT_DEFINITIONS
from src.data.questions.tail_option_blueprints import TAIL_OPTION_BLUEPRINTS_BY_ID
from src.schemas.question import FinalizedOption, FinalizedQuestion
from src.services.trait_ontology_v2 import load_trait_ontology_v2

CONTEXT_DEFINITIONS_BY_ID = {c.context_id: c for c in CONTEXT_DEFINITIONS}
_TRAIT_DEFS = {t.trait_id: t for t in load_trait_ontology_v2()}
_BLUEPRINT_ID = "problem_response_v1"
_TRAIT_ID = next(iter(TAIL_OPTION_BLUEPRINTS_BY_ID[_BLUEPRINT_ID].roles[0].primary_trait_delta))


def _fake_question(question_id: str) -> FinalizedQuestion:
    return FinalizedQuestion(
        question_id=question_id, context="game", target_traits=[_TRAIT_ID], frame_id="problem_check",
        question_text=f"캐시된 질문 {question_id}",
        options=[
            FinalizedOption(option_id=f"{question_id}_o{i}", role_id=r.role_id, text=f"{r.role_id} 문장", primary_trait_delta={_TRAIT_ID: 1})
            for i, r in enumerate(TAIL_OPTION_BLUEPRINTS_BY_ID[_BLUEPRINT_ID].roles, start=1)
        ],
    )


def _state(anchor=None, question_cache=None) -> QuestionGenerationGraphState:
    return QuestionGenerationGraphState(
        question_id="q1", context_definition=CONTEXT_DEFINITIONS_BY_ID["game"],
        trait_definition=_TRAIT_DEFS[_TRAIT_ID], all_trait_labels={_TRAIT_ID: "라벨"},
        option_blueprint_id=_BLUEPRINT_ID, frame_id="problem_check", frame_text="힌트",
        llm_client=None, question_cache=question_cache or {}, anchor=anchor,
    )


class NoPersistentCacheWiredTest(unittest.TestCase):
    def test_main_py_never_passes_question_cache(self) -> None:
        import src.api.main as main_module

        source = inspect.getsource(main_module)
        self.assertEqual(source.count("question_cache="), 0)


class CacheKeyAnchorIsolationTest(unittest.TestCase):
    def test_different_anchors_produce_different_cache_keys(self) -> None:
        shared_cache: dict = {}
        anchor_a = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("game", "story_exploration")]
        anchor_b = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("game", "cooperative_role")]

        question_a = _fake_question("qa")
        question_b = _fake_question("qb")

        # anchor_a 요청이 먼저 이 Key로 "저장"됐다고 가정한다(실제 쓰기 경로는 아직
        # 없지만, Key 계산 로직만 검증한다).
        state_a = _state(anchor=anchor_a, question_cache=shared_cache)
        cache_key_a = f"{state_a.context_definition.context_id}:{anchor_a.anchor_id}:{state_a.option_blueprint_id}:{state_a.frame_id}:{state_a.trait_definition.trait_id}"
        shared_cache[cache_key_a] = question_a

        # anchor_b로 같은 shared_cache를 조회하면 anchor_a의 항목이 재사용되면 안 된다.
        state_b = _state(anchor=anchor_b, question_cache=shared_cache)
        result_b = _check_cache(state_b)
        self.assertNotIn("outcome", result_b)  # Cache Miss — anchor_a의 질문이 반환되지 않음

    def test_same_anchor_and_key_hits_cache_deterministically(self) -> None:
        anchor = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("game", "story_exploration")]
        question = _fake_question("qc")
        cache_key = f"game:{anchor.anchor_id}:{_BLUEPRINT_ID}:problem_check:{_TRAIT_ID}"
        shared_cache = {cache_key: question}

        state = _state(anchor=anchor, question_cache=shared_cache)
        result1 = _check_cache(state)
        result2 = _check_cache(state)
        self.assertEqual(result1["outcome"].source, "cache")
        self.assertEqual(result2["outcome"].source, "cache")
        self.assertEqual(result1["outcome"].question.question_id, result2["outcome"].question.question_id)

    def test_neutral_anchorless_request_does_not_reuse_anchor_cache_entry(self) -> None:
        anchor = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("game", "story_exploration")]
        question = _fake_question("qd")
        anchor_cache_key = f"game:{anchor.anchor_id}:{_BLUEPRINT_ID}:problem_check:{_TRAIT_ID}"
        shared_cache = {anchor_cache_key: question}

        neutral_state = _state(anchor=None, question_cache=shared_cache)
        result = _check_cache(neutral_state)
        self.assertNotIn("outcome", result)

    def test_existing_anchorless_cache_flow_unchanged_when_key_matches(self) -> None:
        question = _fake_question("qe")
        neutral_cache_key = f"game:neutral:{_BLUEPRINT_ID}:problem_check:{_TRAIT_ID}"
        shared_cache = {neutral_cache_key: question}

        state = _state(anchor=None, question_cache=shared_cache)
        result = _check_cache(state)
        self.assertEqual(result["outcome"].source, "cache")


if __name__ == "__main__":
    unittest.main()
