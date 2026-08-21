"""단계 0 계약 확정 — Schema 레벨 필수 테스트.

CLAUDE.md 필수 테스트 목록 중 이 단계에서 검증 가능한 항목만 다룬다:
선택지 정확히 5개 / option_id 서버 생성.
"""

from __future__ import annotations

import unittest

import pydantic

from src.data.contexts.context_definitions import CONTEXT_DEFINITIONS, CORE_CONTEXT_IDS
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAITS
from src.ids import generate_option_id, generate_question_id
from src.schemas.question import (
    FinalizedQuestion,
    GeneratedOption,
    GeneratedQuestion,
    OptionBlueprint,
    OptionRole,
    finalize_question,
)


def _make_blueprint(blueprint_id: str = "problem_response_v1") -> OptionBlueprint:
    return OptionBlueprint(
        blueprint_id=blueprint_id,
        roles=[
            OptionRole(
                role_id="cause_analysis",
                primary_trait_delta={"causal_analysis": 1},
                next_probe="원인 분석 경향이 다른 상황에서도 이어지는지 확인",
            ),
            OptionRole(role_id="strategy_change", primary_trait_delta={"change_adaptation": 1}),
            OptionRole(role_id="direct_trial", primary_trait_delta={"immediate_execution": 1}),
            OptionRole(role_id="external_research", primary_trait_delta={"information_comparison": 1}),
            OptionRole(role_id="ask_others", primary_trait_delta={"collaboration_preference": 1}),
        ],
    )


def _make_generated_question(role_ids: list[str]) -> GeneratedQuestion:
    return GeneratedQuestion(
        context="media",
        target_traits=["causal_analysis"],
        frame_id="unexpected_result",
        question_text="결과가 예상과 다르면 어떻게 하나요?",
        options=[GeneratedOption(role_id=r, text=f"선택지 {r}") for r in role_ids],
    )


class OptionCountTest(unittest.TestCase):
    def test_generated_question_requires_exactly_five_options(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            _make_generated_question(["cause_analysis", "strategy_change"])  # 2개뿐

    def test_generated_question_accepts_five_options(self) -> None:
        q = _make_generated_question(
            ["cause_analysis", "strategy_change", "direct_trial", "external_research", "ask_others"]
        )
        self.assertEqual(len(q.options), 5)

    def test_generated_question_rejects_duplicate_role_ids(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            _make_generated_question(
                ["cause_analysis", "cause_analysis", "direct_trial", "external_research", "ask_others"]
            )

    def test_blueprint_lint_rejects_wrong_role_count(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            OptionBlueprint(
                blueprint_id="bad",
                roles=[OptionRole(role_id="only_one", primary_trait_delta={"causal_analysis": 1})],
            )

    def test_blueprint_lint_rejects_trait_delta_not_equal_one(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            OptionRole(role_id="x", primary_trait_delta={"causal_analysis": 2})

    def test_generated_question_rejects_blank_question_text(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            GeneratedQuestion(
                context="media",
                target_traits=["causal_analysis"],
                frame_id="unexpected_result",
                question_text="   ",
                options=[
                    GeneratedOption(role_id=r, text=f"선택지 {r}")
                    for r in ["a", "b", "c", "d", "e"]
                ],
            )

    def test_generated_option_rejects_blank_text(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            GeneratedOption(role_id="a", text="")

    def test_ontology_and_context_whitelist_check_is_intentionally_not_here(self) -> None:
        """2026-08-20 리뷰 항목: target_traits가 실제 Ontology에 있는지, context가 실제
        Context 목록에 있는지는 이 Schema가 아니라 §11 Quality Gate(미구현)의 책임이다.
        아래는 그 사실을 문서화하는 테스트다 — Quality Gate가 생기면 이 케이스가
        거부되는 새 테스트를 quality_gate 쪽에 추가하고, 이 테스트는 지워도 된다."""

        # 지금은 예외 없이 통과한다 — 의도된 동작(Quality Gate 책임)이다.
        q = GeneratedQuestion(
            context="존재하지_않는_context",
            target_traits=["존재하지_않는_trait"],
            frame_id="unexpected_result",
            question_text="이 질문은 통과해야 한다",
            options=[
                GeneratedOption(role_id=r, text=f"선택지 {r}")
                for r in ["a", "b", "c", "d", "e"]
            ],
        )
        self.assertEqual(q.context, "존재하지_않는_context")
        self.assertEqual(q.target_traits, ["존재하지_않는_trait"])


class ServerGeneratedIdTest(unittest.TestCase):
    def test_generated_option_has_no_id_field(self) -> None:
        # LLM Structured Output 스키마에는 option_id/question_id가 아예 없어야 한다.
        self.assertNotIn("option_id", GeneratedOption.model_fields)
        self.assertNotIn("question_id", type(_make_generated_question(
            ["cause_analysis", "strategy_change", "direct_trial", "external_research", "ask_others"]
        )).model_fields)

    def test_finalize_question_assigns_server_generated_ids(self) -> None:
        blueprint = _make_blueprint()
        generated = _make_generated_question(
            ["cause_analysis", "strategy_change", "direct_trial", "external_research", "ask_others"]
        )
        question_id = generate_question_id("media", "tail", 4)
        finalized = finalize_question(question_id, generated, blueprint)

        self.assertIsInstance(finalized, FinalizedQuestion)
        self.assertEqual(finalized.question_id, "media_tail_04")
        self.assertEqual(
            [o.option_id for o in finalized.options],
            [generate_option_id(question_id, i) for i in range(1, 6)],
        )
        # Blueprint의 trait_delta가 정확히 결합됐는지
        self.assertEqual(finalized.options[0].primary_trait_delta, {"causal_analysis": 1})
        # Blueprint Role의 next_probe도 함께 결합돼야 한다(§7-3/§8 문구 연속성 재료).
        self.assertEqual(
            finalized.options[0].next_probe, "원인 분석 경향이 다른 상황에서도 이어지는지 확인"
        )
        self.assertIsNone(finalized.options[1].next_probe)  # 이 Fixture는 다른 role에 next_probe를 안 줌

    def test_finalize_question_rejects_role_id_not_in_blueprint(self) -> None:
        blueprint = _make_blueprint()
        generated = _make_generated_question(
            ["cause_analysis", "strategy_change", "direct_trial", "external_research", "made_up_role"]
        )
        with self.assertRaises(ValueError):
            finalize_question(generate_question_id("media", "tail", 1), generated, blueprint)


class DataPopulationTest(unittest.TestCase):
    def test_exactly_twelve_traits(self) -> None:
        self.assertEqual(len(VERTICAL_SLICE_TRAITS), 12)

    def test_trait_ids_unique(self) -> None:
        ids = [t.trait_id for t in VERTICAL_SLICE_TRAITS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_exactly_fifteen_contexts_five_core(self) -> None:
        self.assertEqual(len(CONTEXT_DEFINITIONS), 15)
        self.assertEqual(len(CORE_CONTEXT_IDS), 5)

    def test_context_ids_unique(self) -> None:
        ids = [c.context_id for c in CONTEXT_DEFINITIONS]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
