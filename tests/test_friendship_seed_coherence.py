"""Friendship Seed 질문–선택지 정합성 — 2026-08-23 Trait Ontology v2(2.5.3단계) §8/§14.

기존 문제: 질문("생각이 다르거나 오해가 생겼을 때 가장 신경 쓰는 부분")에 대해
team_project Option("함께 해결할 일이 생기면 역할을 나눠 같이 진행하는 것")이 직접적인
답이 아니었다. 질문을 넓혀 5개 Trait 전부가 같은 상황·같은 의사결정 시점의 자연스러운
답이 되도록 맞췄는지 확인한다."""

from __future__ import annotations

import unittest

from src.data.questions.seed_anchor_variants import SEED_ANCHOR_VARIANTS_BY_KEY

_VARIANT = SEED_ANCHOR_VARIANTS_BY_KEY[("school_life", "friendship")]


class FriendshipQuestionOptionCoherenceTest(unittest.TestCase):
    def test_question_mentions_both_shared_activity_and_disagreement(self) -> None:
        # "함께 하기로 한 일"(collaboration 배경)과 "생각이 다르거나 오해"(조율/이해
        # 배경)가 한 문장에 같이 있어야 5개 Trait 모두 같은 상황에서 자연스럽다.
        self.assertIn("함께", _VARIANT.question_text)
        self.assertTrue(("생각이 다르" in _VARIANT.question_text) or ("오해" in _VARIANT.question_text))

    def test_collaboration_option_contains_actual_joint_action(self) -> None:
        text = _VARIANT.option_text_by_role_id["team_project"]
        self.assertTrue(("역할" in text) or ("함께" in text and "해결" in text))

    def test_opinion_mediation_option_contains_multi_party_coordination(self) -> None:
        text = _VARIANT.option_text_by_role_id["conflict_mediation"]
        self.assertIn("조율", text)

    def test_planning_option_contains_sequence_or_method_setting(self) -> None:
        text = _VARIANT.option_text_by_role_id["task_planning"]
        self.assertTrue(("순서" in text) or ("방법" in text))

    def test_emotional_interpretation_option_contains_understanding_of_thoughts_or_feelings(self) -> None:
        text = _VARIANT.option_text_by_role_id["peer_understanding"]
        self.assertTrue(("생각" in text or "감정" in text) and "이해" in text)

    def test_change_adaptation_option_contains_response_to_change(self) -> None:
        text = _VARIANT.option_text_by_role_id["adapting_change"]
        self.assertTrue(("변화" in text) or ("상황" in text and ("조정" in text or "바꾸" in text)))

    def test_all_5_options_are_at_the_same_decision_point_no_sequential_markers(self) -> None:
        from src.engines.v2_direct_probe_quality_checks import SEQUENTIAL_DEPENDENCY_MARKERS

        for role_id, text in _VARIANT.option_text_by_role_id.items():
            for marker in SEQUENTIAL_DEPENDENCY_MARKERS:
                self.assertNotIn(marker, text, f"{role_id}: {marker!r}")

    def test_role_ids_and_trait_mapping_still_match_neutral_seed(self) -> None:
        from src.data.questions.vertical_slice_seed_questions import VERTICAL_SLICE_SEED_QUESTIONS

        seed = VERTICAL_SLICE_SEED_QUESTIONS["school_life"]
        expected_role_ids = {o.role_id for o in seed.options}
        self.assertEqual(set(_VARIANT.option_text_by_role_id.keys()), expected_role_ids)


if __name__ == "__main__":
    unittest.main()
