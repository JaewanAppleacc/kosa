"""Seed Question 3개(§7-1) 검증 — Schema 규칙과 실제 콘텐츠 데이터 둘 다 확인한다."""

from __future__ import annotations

import unittest

import pydantic

from src.data.questions.vertical_slice_seed_questions import (
    GAME_SEED_01,
    MEDIA_SEED_01,
    SCHOOL_LIFE_SEED_01,
    VERTICAL_SLICE_SEED_QUESTIONS,
)
from src.data.question_frames.frame_role_map import QUESTION_FRAME_TEXT
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAIT_IDS
from src.schemas.question import SeedOption, SeedQuestion, seed_question_to_blueprint


class SeedQuestionSchemaTest(unittest.TestCase):
    def _seed(self, options: list[SeedOption]) -> SeedQuestion:
        return SeedQuestion(
            question_id="test_seed_01", context="game", question_text="테스트 질문", options=options
        )

    def _option(self, role_id: str, trait: str) -> SeedOption:
        return SeedOption(
            option_id=f"test_seed_01_o_{role_id}",
            text=f"{role_id} 선택지",
            role_id=role_id,
            primary_trait_delta={trait: 1},
            next_probe="다음 질문 힌트",
        )

    def test_requires_exactly_five_options(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            self._seed([self._option("a", "causal_analysis")])

    def test_rejects_duplicate_role_id(self) -> None:
        opts = [self._option("dup", t) for t in ["causal_analysis", "planning"]] + [
            self._option("x3", "immediate_execution"),
            self._option("x4", "collaboration_preference"),
            self._option("x5", "tool_utilization"),
        ]
        with self.assertRaises(pydantic.ValidationError):
            self._seed(opts)

    def test_rejects_duplicate_trait_across_options(self) -> None:
        opts = [
            self._option("a", "causal_analysis"),
            self._option("b", "causal_analysis"),  # 중복 Trait
            self._option("c", "planning"),
            self._option("d", "immediate_execution"),
            self._option("e", "collaboration_preference"),
        ]
        with self.assertRaises(pydantic.ValidationError):
            self._seed(opts)

    def test_rejects_blank_next_probe(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            SeedOption(
                option_id="x",
                text="선택지",
                role_id="r",
                primary_trait_delta={"causal_analysis": 1},
                next_probe="   ",
            )

    def test_seed_question_to_blueprint_conversion(self) -> None:
        blueprint = seed_question_to_blueprint(GAME_SEED_01)
        self.assertEqual(len(blueprint.roles), 5)
        role = blueprint.role_by_id("strategy_analysis")
        self.assertEqual(role.primary_trait_delta, {"causal_analysis": 1})


class SeedQuestionContentTest(unittest.TestCase):
    def test_three_seed_questions_exist(self) -> None:
        self.assertEqual(set(VERTICAL_SLICE_SEED_QUESTIONS.keys()), {"game", "media", "school_life"})

    def test_each_seed_has_five_options(self) -> None:
        for seed in VERTICAL_SLICE_SEED_QUESTIONS.values():
            self.assertEqual(len(seed.options), 5)

    def test_all_trait_ids_referenced_are_in_ontology(self) -> None:
        for seed in VERTICAL_SLICE_SEED_QUESTIONS.values():
            for option in seed.options:
                for trait_id in option.primary_trait_delta:
                    self.assertIn(trait_id, VERTICAL_SLICE_TRAIT_IDS, f"{seed.question_id}: {trait_id}")

    def test_all_preferred_frames_are_real_frame_ids(self) -> None:
        for seed in VERTICAL_SLICE_SEED_QUESTIONS.values():
            for option in seed.options:
                for frame_id in option.preferred_frames:
                    self.assertIn(frame_id, QUESTION_FRAME_TEXT, f"{seed.question_id}: {frame_id}")

    def test_all_twelve_traits_covered_across_three_seeds(self) -> None:
        """§6-6: 15개 선택지로 12개 Trait를 전부 최소 1번씩 다루도록 설계했다."""

        covered: set[str] = set()
        for seed in [GAME_SEED_01, MEDIA_SEED_01, SCHOOL_LIFE_SEED_01]:
            for option in seed.options:
                covered.update(option.primary_trait_delta.keys())
        self.assertEqual(covered, VERTICAL_SLICE_TRAIT_IDS)

    def test_question_ids_match_context(self) -> None:
        self.assertEqual(GAME_SEED_01.question_id, "game_seed_01")
        self.assertEqual(MEDIA_SEED_01.question_id, "media_seed_01")
        self.assertEqual(SCHOOL_LIFE_SEED_01.question_id, "school_life_seed_01")


if __name__ == "__main__":
    unittest.main()
