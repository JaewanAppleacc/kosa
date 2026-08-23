"""Backup Question 검수 UI Endpoint 테스트 — 2026-08-23 Trait Ontology v2(2.5.3단계)
§10/§11/§14."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.data.questions.vertical_slice_backup_questions import VERTICAL_SLICE_BACKUP_QUESTIONS
from src.engines.backup_applicability_check import check_backup_candidate
from src.review_ui import review_service as rs
from src.review_ui.app import app

client = TestClient(app)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BackupReadOnlyEndpointTest(unittest.TestCase):
    def test_get_backup_questions_returns_6(self) -> None:
        r = client.get("/internal/review/v2/backup-questions")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["questions"]), 6)

    def test_total_options_is_30(self) -> None:
        r = client.get("/internal/review/v2/backup-questions")
        total = sum(len(q["options"]) for q in r.json()["questions"])
        self.assertEqual(total, 30)

    def test_response_matches_actual_runtime_backup_text(self) -> None:
        r = client.get("/internal/review/v2/backup-questions")
        backup_by_id = {q.question_id: q for backups in VERTICAL_SLICE_BACKUP_QUESTIONS.values() for q in backups}
        for q in r.json()["questions"]:
            backup = backup_by_id[q["question_id"]]
            self.assertEqual(q["question_text"], backup.question_text)
            for opt in q["options"]:
                backup_option = next(o for o in backup.options if o.role_id == opt["role_id"])
                self.assertEqual(opt["text"], backup_option.text)
                self.assertEqual(opt["primary_trait_delta"], backup_option.primary_trait_delta)

    def test_anchor_gate_results_match_actual_runtime_check(self) -> None:
        from src.data.questions.backup_question_applicability import BACKUP_APPLICABILITY_BY_QUESTION_ID
        from src.data.contexts.context_anchor_presentations import CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY

        r = client.get("/internal/review/v2/backup-questions")
        backup_by_id = {q.question_id: q for backups in VERTICAL_SLICE_BACKUP_QUESTIONS.values() for q in backups}
        for q in r.json()["questions"]:
            backup = backup_by_id[q["question_id"]]
            applicability = BACKUP_APPLICABILITY_BY_QUESTION_ID.get(q["question_id"])
            for anchor_id, passed in q["anchor_gate_results"].items():
                if anchor_id == "neutral":
                    expected = check_backup_candidate(backup, anchor=None, applicability=applicability).passed
                else:
                    anchor = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[(q["context_id"], anchor_id)]
                    expected = check_backup_candidate(backup, anchor=anchor, applicability=applicability).passed
                self.assertEqual(passed, expected, f"{q['question_id']}/{anchor_id}")


class BackupAnchorPreviewEndpointTest(unittest.TestCase):
    def test_preview_matches_direct_check_backup_candidate_call(self) -> None:
        from src.data.contexts.context_anchor_presentations import CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY

        r = client.get(
            "/internal/review/v2/backup-questions/game_backup_01/anchor-preview",
            params={"context_id": "game", "anchor_id": "story_exploration"},
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()

        backup = next(q for q in VERTICAL_SLICE_BACKUP_QUESTIONS["game"] if q.question_id == "game_backup_01")
        anchor = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("game", "story_exploration")]
        direct = check_backup_candidate(backup, anchor=anchor, applicability=None)
        self.assertEqual(body["passed"], direct.passed)

    def test_preview_without_anchor_id_checks_neutral(self) -> None:
        r = client.get(
            "/internal/review/v2/backup-questions/game_backup_01/anchor-preview", params={"context_id": "game"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()["anchor_id"])
        self.assertTrue(r.json()["passed"])

    def test_unknown_question_returns_422(self) -> None:
        r = client.get(
            "/internal/review/v2/backup-questions/does_not_exist/anchor-preview", params={"context_id": "game"},
        )
        self.assertEqual(r.status_code, 422)

    def test_unknown_anchor_returns_422(self) -> None:
        r = client.get(
            "/internal/review/v2/backup-questions/game_backup_01/anchor-preview",
            params={"context_id": "game", "anchor_id": "not_real"},
        )
        self.assertEqual(r.status_code, 422)


class BackupSavePathsUseTemporaryFilesTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.q_path = Path(self._tmpdir.name) / "bq.json"
        self.o_path = Path(self._tmpdir.name) / "bo.json"
        shutil.copy(rs.BACKUP_QUESTION_REVIEW_PATH, self.q_path)
        shutil.copy(rs.BACKUP_OPTION_REVIEW_PATH, self.o_path)
        self._real_q_hash = _sha256(rs.BACKUP_QUESTION_REVIEW_PATH)
        self._real_o_hash = _sha256(rs.BACKUP_OPTION_REVIEW_PATH)
        self.addCleanup(self._assert_untouched)

        patcher_q = patch("src.review_ui.review_service.BACKUP_QUESTION_REVIEW_PATH", self.q_path)
        patcher_o = patch("src.review_ui.review_service.BACKUP_OPTION_REVIEW_PATH", self.o_path)
        patcher_q.start()
        patcher_o.start()
        self.addCleanup(patcher_q.stop)
        self.addCleanup(patcher_o.stop)

    def _assert_untouched(self) -> None:
        self.assertEqual(_sha256(rs.BACKUP_QUESTION_REVIEW_PATH), self._real_q_hash)
        self.assertEqual(_sha256(rs.BACKUP_OPTION_REVIEW_PATH), self._real_o_hash)

    def _revisions(self) -> tuple[str, str]:
        body = client.get("/internal/review/v2/backup-questions").json()
        return body["question_review_revision"], body["option_review_revision"]

    def test_reviewer_1_patch_only_touches_reviewer_1_slot(self) -> None:
        qrev, _ = self._revisions()
        r = client.patch(
            "/internal/review/v2/backup-questions/game_backup_01",
            json={"reviewer": "reviewer_1", "status": "APPROVE", "comment": "좋음", "expected_revision": qrev},
        )
        self.assertEqual(r.status_code, 200)

        from src.services.backup_question_review_store import load_backup_question_review_entries

        entries = load_backup_question_review_entries(self.q_path)
        entry = next(e for e in entries if e.blueprint_id == "game_backup_01")
        self.assertEqual(entry.reviewer_1_status, "APPROVE")
        self.assertEqual(entry.reviewer_2_status, "TBD")  # reviewer_2는 그대로

    def test_reviewer_2_patch_only_touches_reviewer_2_slot(self) -> None:
        _, orev = self._revisions()
        r = client.patch(
            "/internal/review/v2/backup-questions/game_backup_02/options/screen_review",
            json={"reviewer": "reviewer_2", "status": "HOLD", "comment": "확인 필요", "expected_revision": orev},
        )
        self.assertEqual(r.status_code, 200)

        from src.services.backup_question_review_store import load_backup_option_review_entries

        entries = load_backup_option_review_entries(self.o_path)
        entry = next(e for e in entries if e.blueprint_id == "game_backup_02" and e.role_id == "screen_review")
        self.assertEqual(entry.reviewer_2_status, "HOLD")
        self.assertEqual(entry.reviewer_1_status, "TBD")

    def test_stale_revision_returns_409(self) -> None:
        r = client.patch(
            "/internal/review/v2/backup-questions/game_backup_01",
            json={"reviewer": "reviewer_1", "status": "APPROVE", "comment": "", "expected_revision": "stale"},
        )
        self.assertEqual(r.status_code, 409)

    def test_saving_backup_review_does_not_touch_other_review_files(self) -> None:
        dp_hash_before = _sha256(rs.QUESTION_REVIEW_PATH)
        routing_hash_before = _sha256(rs.ROUTING_QUESTION_REVIEW_PATH)
        seed_anchor_hash_before = _sha256(rs.SEED_ANCHOR_QUESTION_REVIEW_PATH)

        qrev, _ = self._revisions()
        client.patch(
            "/internal/review/v2/backup-questions/game_backup_01",
            json={"reviewer": "reviewer_1", "status": "APPROVE", "comment": "", "expected_revision": qrev},
        )

        self.assertEqual(_sha256(rs.QUESTION_REVIEW_PATH), dp_hash_before)
        self.assertEqual(_sha256(rs.ROUTING_QUESTION_REVIEW_PATH), routing_hash_before)
        self.assertEqual(_sha256(rs.SEED_ANCHOR_QUESTION_REVIEW_PATH), seed_anchor_hash_before)


class BackupNotOnPublicApiTest(unittest.TestCase):
    def test_public_api_has_no_backup_review_route(self) -> None:
        from src.api.main import app as public_app

        public_paths = {route.path for route in public_app.routes}
        for path in public_paths:
            self.assertNotIn("backup-questions", path)


if __name__ == "__main__":
    unittest.main()
