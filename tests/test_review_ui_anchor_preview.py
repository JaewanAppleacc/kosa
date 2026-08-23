"""Review UI Anchor Preview Endpoint 테스트 — 2026-08-23 Trait Ontology v2(2.5.1단계) §11/§13.

Preview가 실제 Runtime 함수(`seed_question_as_finalized`)를 그대로 호출한 결과인지,
Anchor를 바꾸면 실제로 결과가 달라지는지, 읽기 전용이라 어떤 Review JSON도 건드리지
않는지, 그리고 공개 서비스 API(`src.api.main.app`)에는 이 Endpoint가 노출되지 않는지
확인한다."""

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.mock_data import seed_question_as_finalized
from src.data.questions.vertical_slice_seed_questions import VERTICAL_SLICE_SEED_QUESTIONS
from src.review_ui import review_service as rs
from src.review_ui.app import app

client = TestClient(app)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AnchorPreviewEndpointTest(unittest.TestCase):
    def test_preview_matches_direct_runtime_call(self) -> None:
        r = client.get("/internal/review/v2/anchor-preview", params={"context_id": "game", "anchor_id": "story_exploration"})
        self.assertEqual(r.status_code, 200)
        body = r.json()

        direct = seed_question_as_finalized(VERTICAL_SLICE_SEED_QUESTIONS["game"], anchor_id="story_exploration")
        self.assertEqual(body["preview_question_text"], direct.question_text)
        self.assertEqual(
            [(o["role_id"], o["text"]) for o in body["preview_options"]],
            [(o.role_id, o.text) for o in direct.options],
        )

    def test_preview_changes_when_anchor_changes(self) -> None:
        r1 = client.get("/internal/review/v2/anchor-preview", params={"context_id": "media", "anchor_id": "film_drama"})
        r2 = client.get("/internal/review/v2/anchor-preview", params={"context_id": "media", "anchor_id": "documentary"})
        self.assertNotEqual(r1.json()["preview_question_text"], r2.json()["preview_question_text"])

    def test_preview_includes_label_scenarios_and_forbidden_assumptions(self) -> None:
        r = client.get("/internal/review/v2/anchor-preview", params={"context_id": "media", "anchor_id": "stage_performance"})
        body = r.json()
        self.assertEqual(body["anchor_label"], "공연·뮤지컬")
        self.assertTrue(any("편집" in p for p in body["forbidden_assumptions"]))

    def test_unknown_anchor_returns_422(self) -> None:
        r = client.get("/internal/review/v2/anchor-preview", params={"context_id": "game", "anchor_id": "not_real"})
        self.assertEqual(r.status_code, 422)

    def test_preview_does_not_write_any_review_json(self) -> None:
        q_hash_before = _sha256(rs.QUESTION_REVIEW_PATH)
        o_hash_before = _sha256(rs.OPTION_REVIEW_PATH)
        rq_hash_before = _sha256(rs.ROUTING_QUESTION_REVIEW_PATH)
        ro_hash_before = _sha256(rs.ROUTING_OPTION_REVIEW_PATH)

        client.get("/internal/review/v2/anchor-preview", params={"context_id": "school_life", "anchor_id": "friendship"})

        self.assertEqual(_sha256(rs.QUESTION_REVIEW_PATH), q_hash_before)
        self.assertEqual(_sha256(rs.OPTION_REVIEW_PATH), o_hash_before)
        self.assertEqual(_sha256(rs.ROUTING_QUESTION_REVIEW_PATH), rq_hash_before)
        self.assertEqual(_sha256(rs.ROUTING_OPTION_REVIEW_PATH), ro_hash_before)


class AnchorPreviewNotOnPublicApiTest(unittest.TestCase):
    def test_public_api_has_no_anchor_preview_route(self) -> None:
        from src.api.main import app as public_app

        public_paths = {route.path for route in public_app.routes}
        self.assertNotIn("/internal/review/v2/anchor-preview", public_paths)
        for path in public_paths:
            self.assertNotIn("anchor-preview", path)


if __name__ == "__main__":
    unittest.main()
