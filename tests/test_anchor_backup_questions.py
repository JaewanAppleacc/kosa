"""Anchor Backup Question 15개 구조·의미 감사 — 2026-08-23 Trait Ontology v2(2.5.4단계)
§3/§4/§5/§8.

사용자가 기존 6개 Backup(Context 공통)을 전부 부자연스럽다고 REVISE 판정한 뒤,
15개 Anchor마다 자연스러운 Backup 질문 1개씩으로 다시 설계했다. 이 파일은 그 15개가
구조적으로 정확한지(Anchor당 정확히 1개, 중복 없음), §4/§5 설계 원칙(드문 행동 금지,
자동 Trait 연결 금지, Anchor forbidden_assumptions 위반 없음)을 지키는지 확인한다."""

from __future__ import annotations

import unittest

from src.data.contexts.context_anchor_presentations import CONTEXT_ANCHOR_PRESENTATIONS
from src.data.questions.anchor_backup_mapping_rationale import ANCHOR_BACKUP_MAPPING_RATIONALE
from src.data.questions.anchor_backup_questions import ANCHOR_BACKUP_QUESTIONS, ANCHOR_BACKUP_QUESTIONS_BY_KEY
from src.services.trait_ontology_v2 import load_trait_ontology_v2

_KNOWN_TRAIT_IDS = {t.trait_id for t in load_trait_ontology_v2()}


class StructuralCompletenessTest(unittest.TestCase):
    def test_exactly_15_questions(self) -> None:
        self.assertEqual(len(ANCHOR_BACKUP_QUESTIONS), 15)

    def test_exactly_one_question_per_anchor(self) -> None:
        for presentation in CONTEXT_ANCHOR_PRESENTATIONS:
            key = (presentation.context_id, presentation.anchor_id)
            self.assertIn(key, ANCHOR_BACKUP_QUESTIONS_BY_KEY, key)

    def test_no_duplicate_question_ids(self) -> None:
        ids = [q.question_id for q in ANCHOR_BACKUP_QUESTIONS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_no_duplicate_option_ids_across_all_questions(self) -> None:
        option_ids = [o.option_id for q in ANCHOR_BACKUP_QUESTIONS for o in q.options]
        self.assertEqual(len(option_ids), len(set(option_ids)))

    def test_no_duplicate_role_ids_within_a_question(self) -> None:
        for q in ANCHOR_BACKUP_QUESTIONS:
            role_ids = [o.role_id for o in q.options]
            self.assertEqual(len(role_ids), len(set(role_ids)), q.question_id)

    def test_every_question_has_exactly_5_options(self) -> None:
        for q in ANCHOR_BACKUP_QUESTIONS:
            self.assertEqual(len(q.options), 5, q.question_id)


class TraitMappingValidityTest(unittest.TestCase):
    def test_all_used_trait_ids_are_in_supported_v2_ontology(self) -> None:
        for q in ANCHOR_BACKUP_QUESTIONS:
            for o in q.options:
                for trait_id in o.primary_trait_delta:
                    self.assertIn(trait_id, _KNOWN_TRAIT_IDS, f"{q.question_id}/{o.role_id}: {trait_id}")

    def test_each_option_has_at_most_one_trait_or_is_no_signal(self) -> None:
        for q in ANCHOR_BACKUP_QUESTIONS:
            for o in q.options:
                self.assertLessEqual(len(o.primary_trait_delta), 1, f"{q.question_id}/{o.role_id}")

    def test_not_every_question_needs_5_distinct_traits(self) -> None:
        """§4: "한 질문에서 5개 Trait를 반드시 다르게 만들 필요 없음" — 실제로 NO_SIGNAL이
        여러 개인 질문이 존재해야 한다(전부 강제로 5개를 채우지 않았다는 증거)."""

        has_multi_no_signal = any(
            sum(1 for o in q.options if not o.primary_trait_delta) >= 2 for q in ANCHOR_BACKUP_QUESTIONS
        )
        self.assertTrue(has_multi_no_signal)


class RareBehaviorAndAutoLinkingBanTest(unittest.TestCase):
    """§5 — 금지된 자동 연결 패턴이 재도입되지 않았는지 확인한다."""

    def test_no_option_maps_passive_viewing_to_visual_expression(self) -> None:
        passive_markers = ("살펴본다", "본다", "본다.", "보는")
        for q in ANCHOR_BACKUP_QUESTIONS:
            for o in q.options:
                if o.primary_trait_delta == {"visual_expression": 1}:
                    self.fail(f"{q.question_id}/{o.role_id}: visual_expression Mapping 자체를 쓰지 않는 게 이번 설계 방향이다")

    def test_visual_expression_is_never_used(self) -> None:
        """§5의 "게임 결과를 그림이나 도표로 표현한다" 같은 드문 행동 금지 — 이번
        15개는 실제로 visual_expression을 전혀 쓰지 않는다(모든 시청 행동은
        NO_SIGNAL로 정직하게 처리했다)."""

        used_traits = {
            trait_id for q in ANCHOR_BACKUP_QUESTIONS for o in q.options for trait_id in o.primary_trait_delta
        }
        self.assertNotIn("visual_expression", used_traits)

    def test_audience_response_prediction_only_used_for_genuine_prediction(self) -> None:
        for q in ANCHOR_BACKUP_QUESTIONS:
            for o in q.options:
                if o.primary_trait_delta == {"audience_response_prediction": 1}:
                    self.assertIn("예상", o.text, f"{q.question_id}/{o.role_id}: {o.text!r}")

    def test_collaboration_preference_only_used_for_role_division_not_plain_talk(self) -> None:
        for q in ANCHOR_BACKUP_QUESTIONS:
            for o in q.options:
                if o.primary_trait_delta == {"collaboration_preference": 1}:
                    self.assertTrue("역할" in o.text or "함께" in o.text, f"{q.question_id}/{o.role_id}: {o.text!r}")

    def test_uncertainty_tolerance_only_used_for_incomplete_information_decision(self) -> None:
        for q in ANCHOR_BACKUP_QUESTIONS:
            for o in q.options:
                if o.primary_trait_delta == {"uncertainty_tolerance": 1}:
                    self.assertIn("지금까지", o.text)


class AnchorForbiddenAssumptionComplianceTest(unittest.TestCase):
    def test_every_anchor_backup_avoids_its_own_anchors_forbidden_phrases(self) -> None:
        for presentation in CONTEXT_ANCHOR_PRESENTATIONS:
            question = ANCHOR_BACKUP_QUESTIONS_BY_KEY[(presentation.context_id, presentation.anchor_id)]
            all_text = question.question_text + " " + " ".join(o.text for o in question.options)
            for phrase in presentation.forbidden_assumptions:
                self.assertNotIn(phrase, all_text, f"{question.question_id}: {phrase!r}")


class MediaNoProductionAndSchoolLifeNoGroupOnlyTest(unittest.TestCase):
    def test_media_anchor_backups_have_no_production_requirement(self) -> None:
        for q in ANCHOR_BACKUP_QUESTIONS:
            if q.context != "media":
                continue
            all_text = q.question_text + " " + " ".join(o.text for o in q.options)
            for word in ("편집", "촬영", "직접 제작", "직접 작화"):
                self.assertNotIn(word, all_text, f"{q.question_id}: {word!r}")

    def test_school_life_anchor_backups_do_not_all_presuppose_group_activity(self) -> None:
        group_only_words = ("조별", "조원")
        for q in ANCHOR_BACKUP_QUESTIONS:
            if q.context != "school_life":
                continue
            all_text = q.question_text + " " + " ".join(o.text for o in q.options)
            for word in group_only_words:
                self.assertNotIn(word, all_text, f"{q.question_id}: {word!r}")


class MappingRationaleTest(unittest.TestCase):
    def test_exactly_75_rationale_entries(self) -> None:
        self.assertEqual(len(ANCHOR_BACKUP_MAPPING_RATIONALE), 75)

    def test_no_rationale_is_empty(self) -> None:
        for r in ANCHOR_BACKUP_MAPPING_RATIONALE:
            self.assertTrue(r.mapping_rationale_draft.strip())


if __name__ == "__main__":
    unittest.main()
