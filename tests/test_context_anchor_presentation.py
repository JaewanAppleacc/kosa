"""Context Anchor Presentation·Seed Anchor Variant 정본 — 2026-08-23 Trait Ontology
v2(2.5.1단계) §3/§7/§8/§9/§13.

두 데이터 파일(`src/data/contexts/context_anchor_presentations.py`,
`src/data/questions/seed_anchor_variants.py`)은 이미 import 시점에 자체 `_validate()`를
실행한다 — 이 파일이 정상 import된다는 사실 자체가 구조 검증 1차 통과다. 여기서는 그
내용이 §7/§8/§9가 요구한 구체적인 규칙(예: cooperative_role에서만 팀 상황을 기본
전제로 쓸 수 있음)을 실제로 지키는지 확인한다."""

from __future__ import annotations

import unittest

from src.data.contexts.context_anchor_presentations import (
    CONTEXT_ANCHOR_PRESENTATIONS,
    CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY,
)
from src.data.questions.context_routing_blueprints import CONTEXT_ROUTING_BLUEPRINTS_BY_CONTEXT
from src.data.questions.seed_anchor_variants import SEED_ANCHOR_VARIANTS, SEED_ANCHOR_VARIANTS_BY_KEY
from src.data.questions.vertical_slice_seed_questions import VERTICAL_SLICE_SEED_QUESTIONS


class ContextAnchorPresentationRegistryTest(unittest.TestCase):
    def test_15_presentations_registered(self) -> None:
        self.assertEqual(len(CONTEXT_ANCHOR_PRESENTATIONS), 15)

    def test_anchor_sets_match_routing_blueprints_exactly(self) -> None:
        for context_id, bp in CONTEXT_ROUTING_BLUEPRINTS_BY_CONTEXT.items():
            expected = {m.context_anchor for m in bp.option_mappings}
            actual = {p.anchor_id for p in CONTEXT_ANCHOR_PRESENTATIONS if p.context_id == context_id}
            self.assertEqual(actual, expected, context_id)

    def test_cooperative_role_is_the_only_game_anchor_without_team_restriction(self) -> None:
        game_presentations = {p.anchor_id: p for p in CONTEXT_ANCHOR_PRESENTATIONS if p.context_id == "game"}
        for anchor_id, presentation in game_presentations.items():
            if anchor_id == "cooperative_role":
                self.assertEqual(presentation.forbidden_assumptions, [])
            else:
                self.assertIn("팀원", presentation.forbidden_assumptions, anchor_id)

    def test_story_exploration_forbids_ranking_and_building_creation_forbids_win_loss(self) -> None:
        story = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("game", "story_exploration")]
        self.assertIn("경기 순위", story.forbidden_assumptions)
        building = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("game", "building_creation")]
        self.assertIn("승패", building.forbidden_assumptions)

    def test_stage_performance_forbids_video_editing(self) -> None:
        stage = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("media", "stage_performance")]
        self.assertTrue(any("편집" in phrase for phrase in stage.forbidden_assumptions))

    def test_documentary_forbids_fictional_ending_change(self) -> None:
        documentary = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("media", "documentary")]
        self.assertTrue(any("결말" in phrase for phrase in documentary.forbidden_assumptions))

    def test_school_life_academic_and_assignment_and_course_forbid_group_work(self) -> None:
        for anchor_id in ("academic_study", "assignment_evaluation", "course_career"):
            presentation = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("school_life", anchor_id)]
            self.assertIn("조별", presentation.forbidden_assumptions, anchor_id)


class SeedAnchorVariantRegistryTest(unittest.TestCase):
    def test_15_variants_registered(self) -> None:
        self.assertEqual(len(SEED_ANCHOR_VARIANTS), 15)

    def test_role_id_sets_match_seed_question_exactly(self) -> None:
        for variant in SEED_ANCHOR_VARIANTS:
            seed = VERTICAL_SLICE_SEED_QUESTIONS[variant.context_id]
            expected_role_ids = {o.role_id for o in seed.options}
            self.assertEqual(set(variant.option_text_by_role_id.keys()), expected_role_ids)

    def test_every_variant_avoids_its_own_forbidden_assumption_phrases(self) -> None:
        for variant in SEED_ANCHOR_VARIANTS:
            presentation = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[(variant.context_id, variant.anchor_id)]
            all_text = variant.question_text + " " + " ".join(variant.option_text_by_role_id.values())
            for phrase in presentation.forbidden_assumptions:
                self.assertNotIn(phrase, all_text, f"{variant.context_id}/{variant.anchor_id}: {phrase!r}")

    def test_game_5_anchors_produce_5_distinct_question_texts(self) -> None:
        texts = {v.question_text for v in SEED_ANCHOR_VARIANTS if v.context_id == "game"}
        self.assertEqual(len(texts), 5)

    def test_media_5_anchors_produce_5_distinct_question_texts(self) -> None:
        texts = {v.question_text for v in SEED_ANCHOR_VARIANTS if v.context_id == "media"}
        self.assertEqual(len(texts), 5)

    def test_school_life_5_anchors_produce_5_distinct_question_texts(self) -> None:
        texts = {v.question_text for v in SEED_ANCHOR_VARIANTS if v.context_id == "school_life"}
        self.assertEqual(len(texts), 5)

    def test_cooperative_role_variant_may_use_team_phrasing(self) -> None:
        variant = SEED_ANCHOR_VARIANTS_BY_KEY[("game", "cooperative_role")]
        self.assertIn("팀원", variant.question_text)


if __name__ == "__main__":
    unittest.main()
