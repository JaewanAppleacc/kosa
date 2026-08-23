"""Anchor Backup Question 검수 UI Endpoint 테스트 — 2026-08-23 Trait Ontology
v2(2.5.4단계) §7/§8.

기존 Backup 탭(REVISE, 사용자 메모 포함)과 완전히 분리된 새 Endpoint·검수 상태 파일을
확인한다. Preview는 실제 Runtime 후보·Gate 결과와 반드시 일치해야 한다."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.data.questions.anchor_backup_questions import ANCHOR_BACKUP_QUESTIONS
from src.engines.backup_applicability_check import check_backup_candidate
from src.review_ui import review_service as rs
from src.review_ui.app import app

client = TestClient(app)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AnchorBackupReadOnlyEndpointTest(unittest.TestCase):
    def test_get_anchor_backup_questions_returns_15(self) -> None:
        r = client.get("/internal/review/v2/anchor-backup-questions")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["questions"]), 15)

    def test_total_options_is_75(self) -> None:
        r = client.get("/internal/review/v2/anchor-backup-questions")
        total = sum(len(q["options"]) for q in r.json()["questions"])
        self.assertEqual(total, 75)

    def test_response_matches_actual_runtime_question_text(self) -> None:
        r = client.get("/internal/review/v2/anchor-backup-questions")
        by_id = {q.question_id: q for q in ANCHOR_BACKUP_QUESTIONS}
        for q in r.json()["questions"]:
            question = by_id[q["question_id"]]
            self.assertEqual(q["question_text"], question.question_text)
            for opt in q["options"]:
                backend_option = next(o for o in question.options if o.role_id == opt["role_id"])
                self.assertEqual(opt["text"], backend_option.text)
                self.assertEqual(opt["primary_trait_delta"], backend_option.primary_trait_delta)

    def test_allowed_anchor_ids_is_exactly_one_anchor_not_all_permissive(self) -> None:
        r = client.get("/internal/review/v2/anchor-backup-questions")
        for q in r.json()["questions"]:
            self.assertIsNotNone(q["allowed_anchor_ids"])
            self.assertEqual(len(q["allowed_anchor_ids"]), 1)

    def test_superseded_question_ids_reference_old_context_backups(self) -> None:
        r = client.get("/internal/review/v2/anchor-backup-questions")
        for q in r.json()["questions"]:
            self.assertTrue(len(q["superseded_question_ids"]) >= 1)
            for old_id in q["superseded_question_ids"]:
                self.assertTrue(old_id.startswith(f"{q['context_id']}_backup_"))
                self.assertNotIn("_v2", old_id)  # 기존 6개는 "_v2" 접미사가 없다


class AnchorBackupPreviewMatchesRuntimeTest(unittest.TestCase):
    def test_preview_matches_direct_check_backup_candidate_for_matching_anchor(self) -> None:
        from src.data.contexts.context_anchor_presentations import CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY
        from src.data.questions.anchor_backup_applicability import ANCHOR_BACKUP_APPLICABILITY_BY_QUESTION_ID

        question = next(q for q in ANCHOR_BACKUP_QUESTIONS if q.question_id == "media_backup_documentary_v2")
        anchor = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("media", "documentary")]
        applicability = ANCHOR_BACKUP_APPLICABILITY_BY_QUESTION_ID["media_backup_documentary_v2"]
        direct = check_backup_candidate(question, anchor=anchor, applicability=applicability)

        r = client.get(
            "/internal/review/v2/anchor-backup-questions/media_backup_documentary_v2/anchor-preview",
            params={"context_id": "media", "anchor_id": "documentary"},
        )
        self.assertEqual(r.json()["passed"], direct.passed)

    def test_preview_rejects_non_matching_anchor(self) -> None:
        r = client.get(
            "/internal/review/v2/anchor-backup-questions/media_backup_documentary_v2/anchor-preview",
            params={"context_id": "media", "anchor_id": "film_drama"},
        )
        self.assertFalse(r.json()["passed"])

    def test_unknown_question_returns_422(self) -> None:
        r = client.get(
            "/internal/review/v2/anchor-backup-questions/does_not_exist/anchor-preview",
            params={"context_id": "game"},
        )
        self.assertEqual(r.status_code, 422)


class AnchorBackupSavePathsUseTemporaryFilesTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.q_path = Path(self._tmpdir.name) / "abq.json"
        self.o_path = Path(self._tmpdir.name) / "abo.json"
        shutil.copy(rs.ANCHOR_BACKUP_QUESTION_REVIEW_PATH, self.q_path)
        shutil.copy(rs.ANCHOR_BACKUP_OPTION_REVIEW_PATH, self.o_path)
        self._real_q_hash = _sha256(rs.ANCHOR_BACKUP_QUESTION_REVIEW_PATH)
        self._real_o_hash = _sha256(rs.ANCHOR_BACKUP_OPTION_REVIEW_PATH)
        self.addCleanup(self._assert_untouched)

        patcher_q = patch("src.review_ui.review_service.ANCHOR_BACKUP_QUESTION_REVIEW_PATH", self.q_path)
        patcher_o = patch("src.review_ui.review_service.ANCHOR_BACKUP_OPTION_REVIEW_PATH", self.o_path)
        patcher_q.start()
        patcher_o.start()
        self.addCleanup(patcher_q.stop)
        self.addCleanup(patcher_o.stop)

    def _assert_untouched(self) -> None:
        self.assertEqual(_sha256(rs.ANCHOR_BACKUP_QUESTION_REVIEW_PATH), self._real_q_hash)
        self.assertEqual(_sha256(rs.ANCHOR_BACKUP_OPTION_REVIEW_PATH), self._real_o_hash)

    def _revisions(self) -> tuple[str, str]:
        body = client.get("/internal/review/v2/anchor-backup-questions").json()
        return body["question_review_revision"], body["option_review_revision"]

    def test_patch_question_review_saves_as_tbd_not_auto_approved(self) -> None:
        qrev, _ = self._revisions()
        r = client.patch(
            "/internal/review/v2/anchor-backup-questions/game_backup_story_exploration_v2",
            json={"reviewer": "reviewer_1", "status": "APPROVE", "comment": "테스트", "expected_revision": qrev},
        )
        self.assertEqual(r.status_code, 200)

        from src.services.anchor_backup_review_store import load_anchor_backup_question_review_entries

        entries = load_anchor_backup_question_review_entries(self.q_path)
        entry = next(e for e in entries if e.blueprint_id == "game_backup_story_exploration_v2")
        # 사람이 명시적으로 저장했을 때만 값이 바뀐다 — Claude가 자동으로 채운 게 아니다.
        self.assertEqual(entry.reviewer_1_status, "APPROVE")

    def test_stale_revision_returns_409(self) -> None:
        r = client.patch(
            "/internal/review/v2/anchor-backup-questions/game_backup_story_exploration_v2",
            json={"reviewer": "reviewer_1", "status": "APPROVE", "comment": "", "expected_revision": "stale"},
        )
        self.assertEqual(r.status_code, 409)

    def test_saving_does_not_touch_old_revise_backup_review_file(self) -> None:
        old_backup_hash_before = _sha256(rs.BACKUP_QUESTION_REVIEW_PATH)
        old_backup_option_hash_before = _sha256(rs.BACKUP_OPTION_REVIEW_PATH)

        qrev, _ = self._revisions()
        client.patch(
            "/internal/review/v2/anchor-backup-questions/game_backup_story_exploration_v2",
            json={"reviewer": "reviewer_1", "status": "APPROVE", "comment": "", "expected_revision": qrev},
        )

        self.assertEqual(_sha256(rs.BACKUP_QUESTION_REVIEW_PATH), old_backup_hash_before)
        self.assertEqual(_sha256(rs.BACKUP_OPTION_REVIEW_PATH), old_backup_option_hash_before)


class AnchorBackupAllApprovedTest(unittest.TestCase):
    """2.5.5단계 §4 — 사용자가 검수 페이지에서 Anchor Backup 질문 15개·선택지 75개를
    전부 reviewer_1 APPROVE로 판정했다(커밋 867c8c9). 이 테스트는 임시 파일이 아니라
    실제 정본을 읽지만 절대 쓰지 않는다."""

    def test_committed_anchor_backup_review_files_are_all_reviewer_1_approved(self) -> None:
        from src.services.anchor_backup_review_store import (
            load_anchor_backup_option_review_entries,
            load_anchor_backup_question_review_entries,
        )

        question_entries = load_anchor_backup_question_review_entries()
        option_entries = load_anchor_backup_option_review_entries()
        self.assertEqual(len(question_entries), 15)
        self.assertEqual(len(option_entries), 75)
        for entry in [*question_entries, *option_entries]:
            self.assertEqual(entry.reviewer_1_status, "APPROVE")
            self.assertEqual(entry.final_status, "APPROVED")


class AnchorBackupNotOnPublicApiTest(unittest.TestCase):
    def test_public_api_has_no_anchor_backup_route(self) -> None:
        from src.api.main import app as public_app

        public_paths = {route.path for route in public_app.routes}
        for path in public_paths:
            self.assertNotIn("anchor-backup", path)


if __name__ == "__main__":
    unittest.main()
