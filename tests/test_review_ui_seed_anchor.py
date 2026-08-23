"""Seed Anchor Variant 검수 UI Endpoint 테스트 — 2026-08-23 Trait Ontology v2(2.5.2단계)
§12/§13/§15.

`test_review_ui_context_routing.py`와 같은 안전장치를 Seed Anchor Variant
Endpoint(`/internal/review/v2/seed-anchor-questions`)에 대해 반복한다. Preview/조회는
실제 Runtime Variant(`SEED_ANCHOR_VARIANTS`)와 정확히 일치해야 하고, 저장 테스트는
실제 `data/reviews/v2_seed_anchor_*.json`을 절대 건드리지 않는다."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.data.questions.seed_anchor_variants import SEED_ANCHOR_VARIANTS
from src.review_ui import review_service as rs
from src.review_ui.app import app

client = TestClient(app)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SeedAnchorReadOnlyEndpointTest(unittest.TestCase):
    def test_get_seed_anchor_questions_returns_15(self) -> None:
        r = client.get("/internal/review/v2/seed-anchor-questions")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(len(body["questions"]), 15)

    def test_every_question_has_5_options_total_75(self) -> None:
        r = client.get("/internal/review/v2/seed-anchor-questions")
        body = r.json()
        total = sum(len(q["options"]) for q in body["questions"])
        self.assertEqual(total, 75)

    def test_response_matches_actual_runtime_variant_text(self) -> None:
        r = client.get("/internal/review/v2/seed-anchor-questions")
        body = r.json()
        variant_by_key = {(v.context_id, v.anchor_id): v for v in SEED_ANCHOR_VARIANTS}
        for q in body["questions"]:
            variant = variant_by_key[(q["context_id"], q["anchor_id"])]
            self.assertEqual(q["question_text"], variant.question_text)
            for opt in q["options"]:
                self.assertEqual(opt["text"], variant.option_text_by_role_id[opt["role_id"]])
                self.assertEqual(
                    opt["mapping_rationale_draft"], variant.option_mapping_rationale_draft[opt["role_id"]],
                )

    def test_options_include_trait_and_neutral_comparison_fields(self) -> None:
        r = client.get("/internal/review/v2/seed-anchor-questions")
        body = r.json()
        for q in body["questions"]:
            self.assertTrue(q["neutral_question_text"])
            for opt in q["options"]:
                self.assertTrue(opt["trait_id"])
                self.assertTrue(opt["trait_label"])
                self.assertTrue(opt["neutral_text"])
                self.assertEqual(len(opt["primary_trait_delta"]), 1)


class SeedAnchorSavePathsUseTemporaryFilesTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.q_path = Path(self._tmpdir.name) / "saq.json"
        self.o_path = Path(self._tmpdir.name) / "sao.json"
        shutil.copy(rs.SEED_ANCHOR_QUESTION_REVIEW_PATH, self.q_path)
        shutil.copy(rs.SEED_ANCHOR_OPTION_REVIEW_PATH, self.o_path)
        self._real_q_hash = _sha256(rs.SEED_ANCHOR_QUESTION_REVIEW_PATH)
        self._real_o_hash = _sha256(rs.SEED_ANCHOR_OPTION_REVIEW_PATH)
        self.addCleanup(self._assert_untouched)

        patcher_q = patch("src.review_ui.review_service.SEED_ANCHOR_QUESTION_REVIEW_PATH", self.q_path)
        patcher_o = patch("src.review_ui.review_service.SEED_ANCHOR_OPTION_REVIEW_PATH", self.o_path)
        patcher_q.start()
        patcher_o.start()
        self.addCleanup(patcher_q.stop)
        self.addCleanup(patcher_o.stop)

    def _assert_untouched(self) -> None:
        self.assertEqual(_sha256(rs.SEED_ANCHOR_QUESTION_REVIEW_PATH), self._real_q_hash)
        self.assertEqual(_sha256(rs.SEED_ANCHOR_OPTION_REVIEW_PATH), self._real_o_hash)

    def _revisions(self) -> tuple[str, str]:
        body = client.get("/internal/review/v2/seed-anchor-questions").json()
        return body["question_review_revision"], body["option_review_revision"]

    def test_patch_question_review_saves(self) -> None:
        qrev, _ = self._revisions()
        r = client.patch(
            "/internal/review/v2/seed-anchor-questions/game/story_exploration",
            json={"reviewer": "reviewer_1", "status": "APPROVE", "comment": "좋음", "expected_revision": qrev},
        )
        self.assertEqual(r.status_code, 200)
        # 2.5.5단계: 단일 검토자 정책 — reviewer_1 APPROVE만으로 APPROVED가 된다.
        self.assertEqual(r.json()["final_status"], "APPROVED")

        from src.services.seed_anchor_review_store import load_seed_anchor_question_review_entries

        entries = load_seed_anchor_question_review_entries(self.q_path)
        entry = next(e for e in entries if e.context_id == "game" and e.anchor_id == "story_exploration")
        self.assertEqual(entry.reviewer_1_status, "APPROVE")
        self.assertEqual(entry.reviewer_1_comment, "좋음")

    def test_patch_option_review_saves(self) -> None:
        _, orev = self._revisions()
        r = client.patch(
            "/internal/review/v2/seed-anchor-questions/media/documentary/options/creative_making",
            json={"reviewer": "reviewer_2", "status": "HOLD", "comment": "확인 필요", "expected_revision": orev},
        )
        self.assertEqual(r.status_code, 200)

        from src.services.seed_anchor_review_store import load_seed_anchor_option_review_entries

        entries = load_seed_anchor_option_review_entries(self.o_path)
        entry = next(
            e for e in entries
            if e.context_id == "media" and e.anchor_id == "documentary" and e.role_id == "creative_making"
        )
        self.assertEqual(entry.reviewer_2_status, "HOLD")

    def test_stale_revision_returns_409(self) -> None:
        r = client.patch(
            "/internal/review/v2/seed-anchor-questions/game/story_exploration",
            json={"reviewer": "reviewer_1", "status": "APPROVE", "comment": "", "expected_revision": "stale"},
        )
        self.assertEqual(r.status_code, 409)

    def test_unknown_context_anchor_returns_422(self) -> None:
        qrev, _ = self._revisions()
        r = client.patch(
            "/internal/review/v2/seed-anchor-questions/game/does_not_exist",
            json={"reviewer": "reviewer_1", "status": "APPROVE", "comment": "", "expected_revision": qrev},
        )
        self.assertEqual(r.status_code, 422)

    def test_save_failure_leaves_file_unchanged(self) -> None:
        """저장 실패(잘못된 status)가 파일을 부분적으로 바꾸지 않는지 확인한다."""

        before = self.q_path.read_bytes()
        qrev, _ = self._revisions()
        r = client.patch(
            "/internal/review/v2/seed-anchor-questions/game/story_exploration",
            json={"reviewer": "reviewer_1", "status": "NOT_A_STATUS", "comment": "", "expected_revision": qrev},
        )
        self.assertEqual(r.status_code, 422)
        self.assertEqual(self.q_path.read_bytes(), before)

    def test_saving_seed_anchor_review_does_not_touch_other_review_files(self) -> None:
        """§13 — Seed Anchor 검수 저장이 v2 Direct Probe·Routing 검수 파일에 영향을
        주지 않는지 확인한다."""

        dp_q_hash_before = _sha256(rs.QUESTION_REVIEW_PATH)
        dp_o_hash_before = _sha256(rs.OPTION_REVIEW_PATH)
        routing_q_hash_before = _sha256(rs.ROUTING_QUESTION_REVIEW_PATH)

        qrev, _ = self._revisions()
        client.patch(
            "/internal/review/v2/seed-anchor-questions/game/story_exploration",
            json={"reviewer": "reviewer_1", "status": "APPROVE", "comment": "", "expected_revision": qrev},
        )

        self.assertEqual(_sha256(rs.QUESTION_REVIEW_PATH), dp_q_hash_before)
        self.assertEqual(_sha256(rs.OPTION_REVIEW_PATH), dp_o_hash_before)
        self.assertEqual(_sha256(rs.ROUTING_QUESTION_REVIEW_PATH), routing_q_hash_before)


class SeedAnchorNotOnPublicApiTest(unittest.TestCase):
    def test_public_api_has_no_seed_anchor_route(self) -> None:
        from src.api.main import app as public_app

        public_paths = {route.path for route in public_app.routes}
        for path in public_paths:
            self.assertNotIn("seed-anchor", path)


if __name__ == "__main__":
    unittest.main()
