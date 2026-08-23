"""V2 Direct Probe Human Review 상태 Schema/Validator 테스트 — 2026-08-23
Trait Ontology v2(2.3단계) §4, 2.5.5단계(단일 검토자 정책 전환)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from src.data.questions.trait_v2_direct_probe_blueprints import V2_DIRECT_PROBE_BLUEPRINTS
from src.schemas.v2_direct_probe_review import OptionReviewEntry, QuestionReviewEntry
from src.services.v2_direct_probe_review_store import (
    OPTION_REVIEW_PATH,
    QUESTION_REVIEW_PATH,
    ReviewStatusValidationError,
    load_option_review_entries,
    load_question_review_entries,
    validate_review_status_files,
)


class FinalStatusComputationTest(unittest.TestCase):
    """2.5.5단계: 이 프로젝트는 2차 검토를 쓰지 않는다 — `final_status`는
    `reviewer_1_status`만으로 결정되고, `reviewer_2_status`는 어떤 값이어도 결과에
    영향을 주지 않는다."""

    def test_reviewer_1_approve_with_reviewer_2_tbd_is_approved(self) -> None:
        entry = QuestionReviewEntry(blueprint_id="x", reviewer_1_status="APPROVE", reviewer_2_status="TBD")
        self.assertEqual(entry.final_status, "APPROVED")

    def test_reviewer_1_approve_with_reviewer_2_approve_is_approved(self) -> None:
        entry = QuestionReviewEntry(blueprint_id="x", reviewer_1_status="APPROVE", reviewer_2_status="APPROVE")
        self.assertEqual(entry.final_status, "APPROVED")

    def test_reviewer_1_tbd_is_draft(self) -> None:
        entry = QuestionReviewEntry(blueprint_id="x")
        self.assertEqual(entry.final_status, "DRAFT")

    def test_reviewer_1_revise_is_review_required(self) -> None:
        entry = QuestionReviewEntry(blueprint_id="x", reviewer_1_status="REVISE", reviewer_2_status="APPROVE")
        self.assertEqual(entry.final_status, "REVIEW_REQUIRED")

    def test_reviewer_1_hold_is_review_required(self) -> None:
        entry = QuestionReviewEntry(blueprint_id="x", reviewer_1_status="HOLD", reviewer_2_status="APPROVE")
        self.assertEqual(entry.final_status, "REVIEW_REQUIRED")

    def test_reviewer_1_revise_beats_reviewer_2_tbd(self) -> None:
        entry = QuestionReviewEntry(blueprint_id="x", reviewer_1_status="REVISE", reviewer_2_status="TBD")
        self.assertEqual(entry.final_status, "REVIEW_REQUIRED")

    def test_reviewer_2_status_alone_never_changes_final_status(self) -> None:
        """reviewer_1을 고정하고 reviewer_2만 4가지 값으로 바꿔도 final_status는
        전혀 달라지지 않아야 한다(§6 필수 검증 항목)."""

        for reviewer_1_status, expected in (
            ("TBD", "DRAFT"), ("APPROVE", "APPROVED"), ("REVISE", "REVIEW_REQUIRED"), ("HOLD", "REVIEW_REQUIRED"),
        ):
            for reviewer_2_status in ("TBD", "APPROVE", "REVISE", "HOLD"):
                with self.subTest(reviewer_1=reviewer_1_status, reviewer_2=reviewer_2_status):
                    entry = QuestionReviewEntry(
                        blueprint_id="x", reviewer_1_status=reviewer_1_status, reviewer_2_status=reviewer_2_status,
                    )
                    self.assertEqual(entry.final_status, expected)

    def test_invalid_status_value_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            QuestionReviewEntry(blueprint_id="x", reviewer_1_status="APPROVED")  # type: ignore[arg-type]


class RealReviewStatusFilesTest(unittest.TestCase):
    """실제로 커밋된 두 JSON 파일(전부 TBD 상태)이 구조적으로 올바른지 확인한다."""

    def test_question_file_has_exactly_14_entries_matching_real_blueprints(self) -> None:
        entries = load_question_review_entries()
        self.assertEqual(len(entries), 14)
        self.assertEqual(
            {e.blueprint_id for e in entries}, {b.blueprint_id for b in V2_DIRECT_PROBE_BLUEPRINTS}
        )

    def test_option_file_has_exactly_70_entries_matching_real_options(self) -> None:
        entries = load_option_review_entries()
        self.assertEqual(len(entries), 70)
        expected = {
            (b.blueprint_id, m.role_id) for b in V2_DIRECT_PROBE_BLUEPRINTS for m in b.option_mappings
        }
        self.assertEqual({(e.blueprint_id, e.role_id) for e in entries}, expected)

    def test_no_entry_is_pre_approved_or_promoted(self) -> None:
        """§4 규칙: Claude나 테스트가 reviewer 값을 대신 채우면 안 된다 — 현재 커밋된
        파일은 전부 TBD/DRAFT 상태여야 한다."""

        for entry in load_question_review_entries():
            with self.subTest(blueprint_id=entry.blueprint_id):
                self.assertEqual(entry.reviewer_1_status, "TBD")
                self.assertEqual(entry.reviewer_2_status, "TBD")
                self.assertEqual(entry.final_status, "DRAFT")
        for entry in load_option_review_entries():
            with self.subTest(blueprint_id=entry.blueprint_id, role_id=entry.role_id):
                self.assertEqual(entry.reviewer_1_status, "TBD")
                self.assertEqual(entry.reviewer_2_status, "TBD")
                self.assertEqual(entry.final_status, "DRAFT")

    def test_no_real_blueprint_is_approved_yet(self) -> None:
        for bp in V2_DIRECT_PROBE_BLUEPRINTS:
            self.assertEqual(bp.review_status, "draft")

    def test_validate_real_files_passes(self) -> None:
        validate_review_status_files()  # 예외 없으면 통과

    def test_validator_run_does_not_modify_files_on_disk(self) -> None:
        before_q = QUESTION_REVIEW_PATH.read_bytes()
        before_o = OPTION_REVIEW_PATH.read_bytes()
        validate_review_status_files()
        self.assertEqual(QUESTION_REVIEW_PATH.read_bytes(), before_q)
        self.assertEqual(OPTION_REVIEW_PATH.read_bytes(), before_o)


class PromotionConsistencyValidatorTest(unittest.TestCase):
    """§4 Validator 핵심 규칙 — approved로 승격된 Blueprint는 실제로 reviewer_1이
    APPROVE인 상태와만 일치해야 한다(2.5.5단계: reviewer_2는 이 판정에 관여하지
    않는다)."""

    def test_promoted_blueprint_without_full_approval_fails(self) -> None:
        promoted = [
            b.model_copy(update={"review_status": "approved"}) if i == 0 else b
            for i, b in enumerate(V2_DIRECT_PROBE_BLUEPRINTS)
        ]
        # 실제 커밋된 JSON 파일은 전부 TBD이므로, 이 Blueprint가 approved로
        # "승격됐다"고 주장하는 것과 모순된다.
        with patch("src.services.v2_direct_probe_review_store.V2_DIRECT_PROBE_BLUEPRINTS", promoted):
            with self.assertRaises(ReviewStatusValidationError):
                validate_review_status_files()

    def test_promoted_blueprint_with_reviewer_1_approval_passes(self) -> None:
        bp = V2_DIRECT_PROBE_BLUEPRINTS[0]
        promoted_bp = bp.model_copy(update={"review_status": "approved"})

        with tempfile.TemporaryDirectory() as tmp:
            q_path = Path(tmp) / "q.json"
            o_path = Path(tmp) / "o.json"
            q_path.write_text(
                json.dumps([{
                    "blueprint_id": bp.blueprint_id,
                    "reviewer_1_status": "APPROVE", "reviewer_1_comment": "ok",
                    # reviewer_2는 TBD여도 무방하다 — 승격 판정에 관여하지 않는다.
                    "reviewer_2_status": "TBD", "reviewer_2_comment": "",
                }]),
                encoding="utf-8",
            )
            o_path.write_text(
                json.dumps([
                    {
                        "blueprint_id": bp.blueprint_id, "role_id": m.role_id,
                        "reviewer_1_status": "APPROVE", "reviewer_1_comment": "ok",
                        "reviewer_2_status": "TBD", "reviewer_2_comment": "",
                    }
                    for m in bp.option_mappings
                ]),
                encoding="utf-8",
            )
            with patch("src.services.v2_direct_probe_review_store.V2_DIRECT_PROBE_BLUEPRINTS", [promoted_bp]):
                validate_review_status_files(question_path=q_path, option_path=o_path)  # 예외 없으면 통과

    def test_promoted_blueprint_with_one_option_reviewer_1_still_tbd_fails(self) -> None:
        bp = V2_DIRECT_PROBE_BLUEPRINTS[0]
        promoted_bp = bp.model_copy(update={"review_status": "approved"})

        with tempfile.TemporaryDirectory() as tmp:
            q_path = Path(tmp) / "q.json"
            o_path = Path(tmp) / "o.json"
            q_path.write_text(
                json.dumps([{
                    "blueprint_id": bp.blueprint_id,
                    "reviewer_1_status": "APPROVE", "reviewer_2_status": "APPROVE",
                }]),
                encoding="utf-8",
            )
            option_rows = [
                {
                    "blueprint_id": bp.blueprint_id, "role_id": m.role_id,
                    "reviewer_1_status": "APPROVE", "reviewer_2_status": "APPROVE",
                }
                for m in bp.option_mappings
            ]
            # 선택지 하나만 reviewer_1이 아직 TBD — reviewer_2가 APPROVE여도 승격
            # 조건을 만족하지 못해야 한다(2.5.5단계: reviewer_2는 무관하다).
            option_rows[0]["reviewer_1_status"] = "TBD"
            o_path.write_text(json.dumps(option_rows), encoding="utf-8")

            with patch("src.services.v2_direct_probe_review_store.V2_DIRECT_PROBE_BLUEPRINTS", [promoted_bp]):
                with self.assertRaises(ReviewStatusValidationError):
                    validate_review_status_files(question_path=q_path, option_path=o_path)

    def test_missing_blueprint_id_in_question_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            q_path = Path(tmp) / "q.json"
            o_path = Path(tmp) / "o.json"
            bp = V2_DIRECT_PROBE_BLUEPRINTS[0]
            q_path.write_text(json.dumps([]), encoding="utf-8")  # 아예 빠짐
            o_path.write_text(
                json.dumps([
                    {"blueprint_id": bp.blueprint_id, "role_id": m.role_id}
                    for m in bp.option_mappings
                ]),
                encoding="utf-8",
            )
            with patch("src.services.v2_direct_probe_review_store.V2_DIRECT_PROBE_BLUEPRINTS", [bp]):
                with self.assertRaises(ReviewStatusValidationError):
                    validate_review_status_files(question_path=q_path, option_path=o_path)


if __name__ == "__main__":
    unittest.main()
