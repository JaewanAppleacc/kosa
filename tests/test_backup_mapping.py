"""Backup Question Mapping 구조·의미 감사 회귀 — 2026-08-23 Trait Ontology
v2(2.5.3단계) §4/§9/§14."""

from __future__ import annotations

import unittest

from src.data.questions.backup_mapping_rationale import BACKUP_MAPPING_RATIONALE
from src.data.questions.backup_question_applicability import BACKUP_APPLICABILITY
from src.data.questions.vertical_slice_backup_questions import VERTICAL_SLICE_BACKUP_QUESTIONS
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAIT_IDS


class BackupStructuralCompletenessTest(unittest.TestCase):
    def test_exactly_6_backup_questions(self) -> None:
        total = sum(len(backups) for backups in VERTICAL_SLICE_BACKUP_QUESTIONS.values())
        self.assertEqual(total, 6)

    def test_exactly_30_backup_options_no_dup_no_missing(self) -> None:
        keys = [
            (q.question_id, o.role_id)
            for backups in VERTICAL_SLICE_BACKUP_QUESTIONS.values() for q in backups for o in q.options
        ]
        self.assertEqual(len(keys), 30)
        self.assertEqual(len(keys), len(set(keys)))

    def test_no_duplicate_question_ids(self) -> None:
        ids = [q.question_id for backups in VERTICAL_SLICE_BACKUP_QUESTIONS.values() for q in backups]
        self.assertEqual(len(ids), len(set(ids)))

    def test_all_trait_ids_exist_in_supported_legacy_ontology(self) -> None:
        for backups in VERTICAL_SLICE_BACKUP_QUESTIONS.values():
            for q in backups:
                for o in q.options:
                    trait_id = next(iter(o.primary_trait_delta))
                    self.assertIn(trait_id, VERTICAL_SLICE_TRAIT_IDS, f"{q.question_id}/{o.role_id}: {trait_id}")

    def test_mapping_rationale_draft_never_empty_and_matches_30_options(self) -> None:
        self.assertEqual(len(BACKUP_MAPPING_RATIONALE), 30)
        for r in BACKUP_MAPPING_RATIONALE:
            self.assertTrue(r.mapping_rationale_draft.strip())

    def test_applicability_covers_exactly_6_questions(self) -> None:
        self.assertEqual(len(BACKUP_APPLICABILITY), 6)


class GameVisualExpressionFixTest(unittest.TestCase):
    """§5/§9 — game_backup_02의 screen_review가 더 이상 단순 화면 감상이 아니다."""

    def test_screen_review_is_a_direct_expression_action_not_passive_viewing(self) -> None:
        backup = next(q for q in VERTICAL_SLICE_BACKUP_QUESTIONS["game"] if q.question_id == "game_backup_02")
        option = next(o for o in backup.options if o.role_id == "screen_review")
        self.assertNotIn("살펴보며", option.text)
        self.assertIn("표현해서", option.text)
        self.assertEqual(option.primary_trait_delta, {"visual_expression": 1})


class MediaNoProductionPrerequisiteTest(unittest.TestCase):
    """§6 — 감상 Context에 제작 경험을 필수 전제로 요구하지 않는다."""

    _PRODUCTION_WORDS = ("편집", "촬영", "기획할 때", "제작")

    def test_no_media_backup_option_requires_production_experience(self) -> None:
        for backup in VERTICAL_SLICE_BACKUP_QUESTIONS["media"]:
            all_text = backup.question_text + " " + " ".join(o.text for o in backup.options)
            for word in self._PRODUCTION_WORDS:
                self.assertNotIn(word, all_text, f"{backup.question_id}: {word!r}")


class SchoolLifeNoGroupOnlyPrerequisiteTest(unittest.TestCase):
    """§7 — school_life Backup이 조별활동만 전제하지 않는다."""

    def test_no_school_life_backup_hardcodes_group_project(self) -> None:
        for backup in VERTICAL_SLICE_BACKUP_QUESTIONS["school_life"]:
            all_text = backup.question_text + " " + " ".join(o.text for o in backup.options)
            self.assertNotIn("조별 과제", all_text, backup.question_id)
            self.assertNotIn("다른 조", all_text, backup.question_id)


class BackupAnchorNeutralityTest(unittest.TestCase):
    """6개 Backup 전부가 재작성 후 모든 Anchor에서 통과하는지 다시 확인한다(§3/§9
    "가능하면 중립으로 개선" 목표가 실제로 달성됐는지)."""

    def test_every_backup_passes_every_anchor_of_its_context(self) -> None:
        from src.data.contexts.context_anchor_presentations import CONTEXT_ANCHOR_PRESENTATIONS
        from src.engines.backup_applicability_check import check_backup_candidate
        from src.data.questions.backup_question_applicability import BACKUP_APPLICABILITY_BY_QUESTION_ID

        for context_id, backups in VERTICAL_SLICE_BACKUP_QUESTIONS.items():
            anchors = [p for p in CONTEXT_ANCHOR_PRESENTATIONS if p.context_id == context_id]
            for backup in backups:
                applicability = BACKUP_APPLICABILITY_BY_QUESTION_ID.get(backup.question_id)
                for anchor in anchors:
                    gate = check_backup_candidate(backup, anchor=anchor, applicability=applicability)
                    self.assertTrue(gate.passed, f"{backup.question_id} vs {anchor.anchor_id}: {gate.failures}")


if __name__ == "__main__":
    unittest.main()
