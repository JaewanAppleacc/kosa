"""Seed Anchor Variant 75개 Option 의미 감사 회귀 — 2026-08-23 Trait Ontology
v2(2.5.2단계) §7/§8/§9/§15.

2.5.2단계에서 수정한 12개 Option(media creative_making 5개, school_life
team_project 2개, conflict_mediation 5개)이 실제로 문제를 재도입하지 않았는지, 그리고
75개 Option 전체가 구조적으로 빠짐없이 존재하는지 확인한다."""

from __future__ import annotations

import unittest

from src.data.questions.seed_anchor_variants import SEED_ANCHOR_VARIANTS, SEED_ANCHOR_VARIANTS_BY_KEY

_PASSIVE_APPRECIATION_PHRASES = ("살펴보는 것", "감상하는 것", "바라보는 것")
_EXPRESSION_VERBS = ("표현해보는", "표현하는")


class MediaVisualExpressionOptionTest(unittest.TestCase):
    """§10(2.5.1단계 A)·§7(2.5.2단계) — 단순 "살펴본다"만으로 visual_expression에
    Mapping되지 않는다. 이번 라운드는 NO_SIGNAL 전환 대신 "직접 표현" 행동으로
    재작성하는 방향을 택했으므로, 실제로 표현 동사가 들어있는지 확인한다."""

    def test_all_5_creative_making_options_use_expression_verbs_not_passive_appreciation(self) -> None:
        for v in SEED_ANCHOR_VARIANTS:
            if v.context_id != "media":
                continue
            text = v.option_text_by_role_id["creative_making"]
            for phrase in _PASSIVE_APPRECIATION_PHRASES:
                self.assertNotIn(phrase, text, f"{v.anchor_id}: {text!r}")
            self.assertTrue(
                any(verb in text for verb in _EXPRESSION_VERBS),
                f"{v.anchor_id}: {text!r}에 표현 동사가 없다",
            )

    def test_creative_making_still_maps_to_visual_expression(self) -> None:
        from src.data.questions.vertical_slice_seed_questions import VERTICAL_SLICE_SEED_QUESTIONS

        seed = VERTICAL_SLICE_SEED_QUESTIONS["media"]
        option = next(o for o in seed.options if o.role_id == "creative_making")
        self.assertEqual(option.primary_trait_delta, {"visual_expression": 1})


class SchoolLifeTeamProjectRoleDivisionTest(unittest.TestCase):
    """§9 — team_project Option이 공동 작업·역할 분담 의미를 갖는다(단순 정보 공유·
    친목이 아니라)."""

    def test_all_5_team_project_options_mention_role_division_or_joint_work(self) -> None:
        markers = ("역할을 나눠", "역할을 나누", "역할 나눠")
        for v in SEED_ANCHOR_VARIANTS:
            if v.context_id != "school_life":
                continue
            text = v.option_text_by_role_id["team_project"]
            self.assertTrue(any(m in text for m in markers), f"{v.anchor_id}: {text!r}")

    def test_friendship_team_project_no_longer_pure_socializing(self) -> None:
        text = SEED_ANCHOR_VARIANTS_BY_KEY[("school_life", "friendship")].option_text_by_role_id["team_project"]
        self.assertNotIn("시간을 보내며 관계를 맞춰가는 것", text)


class SchoolLifeConflictMediationTest(unittest.TestCase):
    """§9 — conflict_mediation Option이 "내 기준을 세우는" 독립판단이 아니라 복수
    의견 사이의 조정 의미를 갖는다."""

    def test_all_5_conflict_mediation_options_mention_mediation_not_own_standard(self) -> None:
        for v in SEED_ANCHOR_VARIANTS:
            if v.context_id != "school_life":
                continue
            text = v.option_text_by_role_id["conflict_mediation"]
            self.assertIn("조율", text, f"{v.anchor_id}: {text!r}")
            self.assertNotIn("내 기준을 세우고", text, f"{v.anchor_id}: {text!r}")

    def test_course_career_conflict_mediation_matches_recommended_wording(self) -> None:
        text = SEED_ANCHOR_VARIANTS_BY_KEY[("school_life", "course_career")].option_text_by_role_id["conflict_mediation"]
        self.assertEqual(text, "부모·교사·친구 의견이 다를 때 공통으로 중요하게 보는 기준을 찾아 조율하는 것")


class Full75OptionCompletenessTest(unittest.TestCase):
    def test_exactly_75_option_keys_no_missing_no_duplicate(self) -> None:
        keys = [
            (v.context_id, v.anchor_id, role_id)
            for v in SEED_ANCHOR_VARIANTS
            for role_id in v.option_text_by_role_id
        ]
        self.assertEqual(len(keys), 75)
        self.assertEqual(len(keys), len(set(keys)))

    def test_mapping_rationale_draft_is_never_empty(self) -> None:
        for v in SEED_ANCHOR_VARIANTS:
            for role_id, rationale in v.option_mapping_rationale_draft.items():
                self.assertTrue(rationale.strip(), f"{v.context_id}/{v.anchor_id}/{role_id}")

    def test_mapping_rationale_draft_keys_match_option_text_keys_for_every_variant(self) -> None:
        for v in SEED_ANCHOR_VARIANTS:
            self.assertEqual(
                set(v.option_mapping_rationale_draft.keys()), set(v.option_text_by_role_id.keys()),
            )


if __name__ == "__main__":
    unittest.main()
