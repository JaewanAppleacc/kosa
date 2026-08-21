"""Question Quality Gate(§11 Code Check) 테스트."""

from __future__ import annotations

import unittest

from src.engines.question_quality_gate import (
    MAX_QUESTION_TEXT_LENGTH,
    run_quality_gate,
)
from src.schemas.question import FinalizedOption, FinalizedQuestion


def _make_question(question_text: str, option_texts: list[str]) -> FinalizedQuestion:
    trait_ids = ["causal_analysis", "planning", "collaboration_preference", "pattern_finding", "tool_utilization"]
    return FinalizedQuestion(
        question_id="game_tail_01",
        context="game",
        target_traits=["causal_analysis"],
        frame_id="problem_check",
        question_text=question_text,
        options=[
            FinalizedOption(
                option_id=f"game_tail_01_o{i}",
                role_id=f"role_{i}",
                text=text,
                primary_trait_delta={trait_ids[i - 1]: 1},
            )
            for i, text in enumerate(option_texts, start=1)
        ],
    )


class QuestionQualityGateTest(unittest.TestCase):
    def test_passes_normal_question(self) -> None:
        question = _make_question(
            "문제가 생기면 무엇부터 하나요?",
            ["원인을 분석한다", "계획을 세운다", "친구에게 묻는다", "패턴을 찾는다", "도구를 써본다"],
        )
        result = run_quality_gate(question)
        self.assertTrue(result.passed, result.failures)

    def test_rejects_too_long_question_text(self) -> None:
        question = _make_question(
            "가" * (MAX_QUESTION_TEXT_LENGTH + 1),
            ["원인을 분석한다", "계획을 세운다", "친구에게 묻는다", "패턴을 찾는다", "도구를 써본다"],
        )
        result = run_quality_gate(question)
        self.assertFalse(result.passed)
        self.assertTrue(any("길이 제한" in f for f in result.failures))

    def test_rejects_forbidden_major_name(self) -> None:
        question = _make_question(
            "미디어커뮤니케이션 학과에 관심이 있나요?",
            ["원인을 분석한다", "계획을 세운다", "친구에게 묻는다", "패턴을 찾는다", "도구를 써본다"],
        )
        result = run_quality_gate(question)
        self.assertFalse(result.passed)
        self.assertTrue(any("금지 표현" in f for f in result.failures))

    def test_rejects_ability_self_assessment_phrase(self) -> None:
        question = _make_question(
            "이 활동을 잘하는 편인가?",
            ["원인을 분석한다", "계획을 세운다", "친구에게 묻는다", "패턴을 찾는다", "도구를 써본다"],
        )
        result = run_quality_gate(question)
        self.assertFalse(result.passed)

    def test_rejects_exact_repeat_of_previous_question(self) -> None:
        question = _make_question(
            "문제가 생기면 무엇부터 하나요?",
            ["원인을 분석한다", "계획을 세운다", "친구에게 묻는다", "패턴을 찾는다", "도구를 써본다"],
        )
        result = run_quality_gate(question, previous_question_texts=["문제가 생기면 무엇부터 하나요?"])
        self.assertFalse(result.passed)
        self.assertTrue(any("반복" in f for f in result.failures))


if __name__ == "__main__":
    unittest.main()
