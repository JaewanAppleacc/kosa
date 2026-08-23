"""V2 Direct Probe 검수 UI — Review Service 테스트 — 2026-08-23 Trait Ontology
v2(2.4단계) §13.

모든 저장(update) 테스트는 실제 커밋된 `data/reviews/*.json`을 절대 건드리지 않는다 —
`TemporaryDirectory`에 복사한 사본만 수정한다."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.data.questions.trait_v2_direct_probe_blueprints import V2_DIRECT_PROBE_BLUEPRINTS
from src.review_ui import review_service as rs


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TempReviewFilesTestCase(unittest.TestCase):
    """실제 커밋된 JSON을 복사해 임시 디렉터리에서만 쓰고 지운다."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.q_path = Path(self._tmpdir.name) / "q.json"
        self.o_path = Path(self._tmpdir.name) / "o.json"
        shutil.copy(rs.QUESTION_REVIEW_PATH, self.q_path)
        shutil.copy(rs.OPTION_REVIEW_PATH, self.o_path)
        self._real_q_hash_before = _sha256(rs.QUESTION_REVIEW_PATH)
        self._real_o_hash_before = _sha256(rs.OPTION_REVIEW_PATH)
        self.addCleanup(self._assert_real_files_untouched)

    def _assert_real_files_untouched(self) -> None:
        self.assertEqual(_sha256(rs.QUESTION_REVIEW_PATH), self._real_q_hash_before)
        self.assertEqual(_sha256(rs.OPTION_REVIEW_PATH), self._real_o_hash_before)


class LoadingTest(TempReviewFilesTestCase):
    def test_loads_exactly_14_questions(self) -> None:
        questions, _, _ = rs.build_question_list(question_path=self.q_path, option_path=self.o_path)
        self.assertEqual(len(questions), 14)

    def test_loads_exactly_70_options_total(self) -> None:
        questions, _, _ = rs.build_question_list(question_path=self.q_path, option_path=self.o_path)
        self.assertEqual(sum(len(q.options) for q in questions), 70)

    def test_questions_connect_to_real_blueprint_and_mapping(self) -> None:
        questions, _, _ = rs.build_question_list(question_path=self.q_path, option_path=self.o_path)
        by_id = {q.blueprint_id: q for q in questions}
        for bp in V2_DIRECT_PROBE_BLUEPRINTS:
            item = by_id[bp.blueprint_id]
            self.assertEqual(item.trait_id, bp.trait_id)
            self.assertEqual(item.question_text, bp.base_question.question_text)
            option_role_ids = [o.role_id for o in item.options]
            self.assertEqual(option_role_ids, [o.role_id for o in bp.base_question.options])
            for option_item, mapping in zip(item.options, bp.option_mappings):
                self.assertEqual(option_item.role_id, mapping.role_id)
                self.assertEqual(option_item.mapping_type, mapping.mapping_type)
                if mapping.mapping_type == "NO_SIGNAL":
                    self.assertEqual(option_item.no_signal_reason, mapping.no_signal_reason)
                    self.assertEqual(option_item.signals, [])
                else:
                    self.assertTrue(option_item.signals)

    def test_target_option_flagged_correctly(self) -> None:
        questions, _, _ = rs.build_question_list(question_path=self.q_path, option_path=self.o_path)
        for q in questions:
            targets = [o for o in q.options if o.is_target]
            self.assertEqual(len(targets), 1)
            self.assertEqual(targets[0].signals[0].trait_id, q.trait_id)


class QuestionUpdateTest(TempReviewFilesTestCase):
    def test_rejects_unknown_blueprint_id(self) -> None:
        _, qrev, _ = rs.build_question_list(question_path=self.q_path, option_path=self.o_path)
        with self.assertRaises(rs.UnknownBlueprintError):
            rs.update_question_review(
                blueprint_id="does_not_exist", reviewer="reviewer_1", status="APPROVE", comment="",
                resolution_note=None, expected_revision=qrev, question_path=self.q_path,
            )

    def test_rejects_invalid_status(self) -> None:
        bp_id = V2_DIRECT_PROBE_BLUEPRINTS[0].blueprint_id
        _, qrev, _ = rs.build_question_list(question_path=self.q_path, option_path=self.o_path)
        with self.assertRaises(rs.InvalidReviewStatusError):
            rs.update_question_review(
                blueprint_id=bp_id, reviewer="reviewer_1", status="YES", comment="",
                resolution_note=None, expected_revision=qrev, question_path=self.q_path,
            )

    def test_rejects_invalid_reviewer_slot(self) -> None:
        bp_id = V2_DIRECT_PROBE_BLUEPRINTS[0].blueprint_id
        _, qrev, _ = rs.build_question_list(question_path=self.q_path, option_path=self.o_path)
        with self.assertRaises(rs.InvalidReviewStatusError):
            rs.update_question_review(
                blueprint_id=bp_id, reviewer="reviewer_3", status="APPROVE", comment="",
                resolution_note=None, expected_revision=qrev, question_path=self.q_path,
            )

    def test_stale_revision_rejected(self) -> None:
        bp_id = V2_DIRECT_PROBE_BLUEPRINTS[0].blueprint_id
        with self.assertRaises(rs.StaleRevisionError):
            rs.update_question_review(
                blueprint_id=bp_id, reviewer="reviewer_1", status="APPROVE", comment="",
                resolution_note=None, expected_revision="stale-value", question_path=self.q_path,
            )

    def test_updates_only_selected_reviewer_slot_and_preserves_other(self) -> None:
        bp_id = V2_DIRECT_PROBE_BLUEPRINTS[0].blueprint_id
        _, qrev, _ = rs.build_question_list(question_path=self.q_path, option_path=self.o_path)
        rs.update_question_review(
            blueprint_id=bp_id, reviewer="reviewer_1", status="APPROVE", comment="1차 승인",
            resolution_note=None, expected_revision=qrev, question_path=self.q_path,
        )
        entries = rs.load_question_review_entries(self.q_path)
        entry = next(e for e in entries if e.blueprint_id == bp_id)
        self.assertEqual(entry.reviewer_1_status, "APPROVE")
        self.assertEqual(entry.reviewer_1_comment, "1차 승인")
        self.assertEqual(entry.reviewer_2_status, "TBD")  # reviewer_2는 그대로 보존

    def test_final_status_computed_correctly_after_both_approve(self) -> None:
        bp_id = V2_DIRECT_PROBE_BLUEPRINTS[0].blueprint_id
        _, qrev, _ = rs.build_question_list(question_path=self.q_path, option_path=self.o_path)
        _, qrev = rs.update_question_review(
            blueprint_id=bp_id, reviewer="reviewer_1", status="APPROVE", comment="",
            resolution_note=None, expected_revision=qrev, question_path=self.q_path,
        )
        final_status, _ = rs.update_question_review(
            blueprint_id=bp_id, reviewer="reviewer_2", status="APPROVE", comment="",
            resolution_note=None, expected_revision=qrev, question_path=self.q_path,
        )
        self.assertEqual(final_status, "TEAM_REVIEWED")

    def test_does_not_promote_underlying_blueprint_review_status(self) -> None:
        """§11 — Review Service가 저장하는 건 검수 JSON뿐이다. 실제
        `V2DirectProbeBlueprint.review_status`(코드에 박힌 값)는 절대 건드리지 않는다."""

        bp_id = V2_DIRECT_PROBE_BLUEPRINTS[0].blueprint_id
        _, qrev, orev = rs.build_question_list(question_path=self.q_path, option_path=self.o_path)
        rs.update_question_review(
            blueprint_id=bp_id, reviewer="reviewer_1", status="APPROVE", comment="",
            resolution_note=None, expected_revision=qrev, question_path=self.q_path,
        )
        for bp in V2_DIRECT_PROBE_BLUEPRINTS:
            self.assertEqual(bp.review_status, "draft")

    def test_atomic_write_creates_no_leftover_temp_files(self) -> None:
        bp_id = V2_DIRECT_PROBE_BLUEPRINTS[0].blueprint_id
        _, qrev, _ = rs.build_question_list(question_path=self.q_path, option_path=self.o_path)
        rs.update_question_review(
            blueprint_id=bp_id, reviewer="reviewer_1", status="APPROVE", comment="",
            resolution_note=None, expected_revision=qrev, question_path=self.q_path,
        )
        leftovers = list(self.q_path.parent.glob(f".{self.q_path.name}.*.tmp"))
        self.assertEqual(leftovers, [])

    def test_write_failure_preserves_original_file(self) -> None:
        bp_id = V2_DIRECT_PROBE_BLUEPRINTS[0].blueprint_id
        _, qrev, _ = rs.build_question_list(question_path=self.q_path, option_path=self.o_path)
        before_bytes = self.q_path.read_bytes()

        with patch("src.review_ui.review_service.os.replace", side_effect=OSError("디스크 오류 주입")):
            with self.assertRaises(OSError):
                rs.update_question_review(
                    blueprint_id=bp_id, reviewer="reviewer_1", status="APPROVE", comment="",
                    resolution_note=None, expected_revision=qrev, question_path=self.q_path,
                )

        self.assertEqual(self.q_path.read_bytes(), before_bytes)
        leftovers = list(self.q_path.parent.glob(f".{self.q_path.name}.*.tmp"))
        self.assertEqual(leftovers, [])  # 실패 시 임시 파일도 정리된다


class OptionUpdateTest(TempReviewFilesTestCase):
    def test_rejects_unknown_role_id(self) -> None:
        bp_id = V2_DIRECT_PROBE_BLUEPRINTS[0].blueprint_id
        _, _, orev = rs.build_question_list(question_path=self.q_path, option_path=self.o_path)
        with self.assertRaises(rs.UnknownRoleError):
            rs.update_option_review(
                blueprint_id=bp_id, role_id="does_not_exist", reviewer="reviewer_1", status="APPROVE",
                comment="", resolution_note=None, expected_revision=orev, option_path=self.o_path,
            )

    def test_updates_only_selected_slot(self) -> None:
        bp = V2_DIRECT_PROBE_BLUEPRINTS[0]
        role_id = bp.option_mappings[0].role_id
        _, _, orev = rs.build_question_list(question_path=self.q_path, option_path=self.o_path)
        rs.update_option_review(
            blueprint_id=bp.blueprint_id, role_id=role_id, reviewer="reviewer_2", status="REVISE",
            comment="문구 다시 보기", resolution_note=None, expected_revision=orev, option_path=self.o_path,
        )
        entries = rs.load_option_review_entries(self.o_path)
        entry = next(e for e in entries if e.blueprint_id == bp.blueprint_id and e.role_id == role_id)
        self.assertEqual(entry.reviewer_2_status, "REVISE")
        self.assertEqual(entry.reviewer_1_status, "TBD")

    def test_stale_option_revision_rejected(self) -> None:
        bp = V2_DIRECT_PROBE_BLUEPRINTS[0]
        role_id = bp.option_mappings[0].role_id
        with self.assertRaises(rs.StaleRevisionError):
            rs.update_option_review(
                blueprint_id=bp.blueprint_id, role_id=role_id, reviewer="reviewer_1", status="APPROVE",
                comment="", resolution_note=None, expected_revision="stale", option_path=self.o_path,
            )


class SummaryTest(TempReviewFilesTestCase):
    def test_summary_matches_totals(self) -> None:
        summary = rs.build_summary(question_path=self.q_path, option_path=self.o_path)
        self.assertEqual(summary.question_total, 14)
        self.assertEqual(summary.option_total, 70)
        self.assertEqual(summary.team_reviewed_eligible_blueprint_ids, [])

    def test_no_blueprint_eligible_for_team_reviewed_until_all_approve(self) -> None:
        bp = V2_DIRECT_PROBE_BLUEPRINTS[0]
        _, qrev, orev = rs.build_question_list(question_path=self.q_path, option_path=self.o_path)
        qrev_final = qrev
        for reviewer in ("reviewer_1", "reviewer_2"):
            _, qrev_final = rs.update_question_review(
                blueprint_id=bp.blueprint_id, reviewer=reviewer, status="APPROVE", comment="",
                resolution_note=None, expected_revision=qrev_final, question_path=self.q_path,
            )
        summary = rs.build_summary(question_path=self.q_path, option_path=self.o_path)
        # 질문은 TEAM_REVIEWED지만 선택지 5개는 아직 전부 TBD이므로 승격 후보에 없어야 한다.
        self.assertNotIn(bp.blueprint_id, summary.team_reviewed_eligible_blueprint_ids)

    def test_blueprint_eligible_only_after_question_and_all_options_approved(self) -> None:
        bp = V2_DIRECT_PROBE_BLUEPRINTS[0]
        _, qrev, orev = rs.build_question_list(question_path=self.q_path, option_path=self.o_path)
        qrev_final = qrev
        for reviewer in ("reviewer_1", "reviewer_2"):
            _, qrev_final = rs.update_question_review(
                blueprint_id=bp.blueprint_id, reviewer=reviewer, status="APPROVE", comment="",
                resolution_note=None, expected_revision=qrev_final, question_path=self.q_path,
            )
        orev_current = orev
        for mapping in bp.option_mappings:
            for reviewer in ("reviewer_1", "reviewer_2"):
                _, orev_current = rs.update_option_review(
                    blueprint_id=bp.blueprint_id, role_id=mapping.role_id, reviewer=reviewer,
                    status="APPROVE", comment="", resolution_note=None,
                    expected_revision=orev_current, option_path=self.o_path,
                )
        summary = rs.build_summary(question_path=self.q_path, option_path=self.o_path)
        self.assertIn(bp.blueprint_id, summary.team_reviewed_eligible_blueprint_ids)


if __name__ == "__main__":
    unittest.main()
