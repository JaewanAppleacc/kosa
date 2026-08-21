"""demo_user_01 Persona + Hand-Calculated Fixture가 실제 Evidence Engine 계산과 일치하는지
확인한다. C가 만들 나머지 Persona도 이 메커니즘(evaluate_persona_against_fixture)으로
검증받게 된다.
"""

from __future__ import annotations

import unittest

from eval.trait_eval import build_evidence_records, evaluate_persona_against_fixture
from src.data.personas.demo_user_01 import (
    BLUEPRINT_BY_QUESTION_ID,
    DEMO_USER_01_FIXTURE,
    DEMO_USER_01_PERSONA,
)
from src.schemas.persona import HandCalculatedFixture, HandCalculatedTraitExpectation


class DemoPersonaFixtureTest(unittest.TestCase):
    def test_persona_matches_hand_calculated_fixture(self) -> None:
        result = evaluate_persona_against_fixture(
            DEMO_USER_01_PERSONA, DEMO_USER_01_FIXTURE, BLUEPRINT_BY_QUESTION_ID
        )
        self.assertTrue(result.passed, msg=f"불일치: {result.mismatches}")
        self.assertEqual(result.mismatches, [])

    def test_persona_produces_expected_evidence_record_count(self) -> None:
        records, offered = build_evidence_records(DEMO_USER_01_PERSONA, BLUEPRINT_BY_QUESTION_ID)
        # Seed 3개 + 꼬리질문 6개 = 9개 답변(2026-08-21, 실제 Seed 적용 후 갱신).
        self.assertEqual(len(records), 9)
        self.assertEqual(len(offered), 9)
        # Seed·꼬리질문 전부 5개 선택지 = 5개 Trait를 제시한다.
        for offered_set in offered:
            self.assertEqual(len(offered_set), 5)

    def test_comparator_detects_intentional_mismatch(self) -> None:
        """비교기 자체가 실제로 불일치를 잡아내는지 확인 — 일부러 틀린 기대값을 넣는다."""

        wrong_fixture = HandCalculatedFixture(
            fixture_id="fixture_intentionally_wrong",
            persona_id=DEMO_USER_01_PERSONA.persona_id,
            trait_expectations=[
                HandCalculatedTraitExpectation(
                    trait_id="causal_analysis",
                    expected_support_count=99,  # 실제로는 3
                    expected_opportunity_count=8,
                    expected_context_count=2,
                    expected_distinct_frame_count=2,
                    expected_state="STRONG",
                    calculation_notes="일부러 틀린 값",
                )
            ],
        )
        result = evaluate_persona_against_fixture(
            DEMO_USER_01_PERSONA, wrong_fixture, BLUEPRINT_BY_QUESTION_ID
        )
        self.assertFalse(result.passed)
        self.assertEqual(len(result.mismatches), 1)
        self.assertEqual(result.mismatches[0].field, "support_count")
        self.assertEqual(result.mismatches[0].expected, "99")
        self.assertEqual(result.mismatches[0].actual, "3")


if __name__ == "__main__":
    unittest.main()
