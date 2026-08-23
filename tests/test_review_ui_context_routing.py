"""Context Routing 검수 UI Endpoint 테스트 — 2026-08-23 Trait Ontology v2(2.5단계) §10.

`test_review_ui_api.py`(v2 Direct Probe 검수 UI)와 완전히 같은 안전장치를 Context
Routing Endpoint(`/internal/review/v2/routing-questions`)에 대해 반복한다 — 저장
테스트는 실제 `data/reviews/v2_context_routing_*_review_status.json`을 절대 건드리지
않고, 임시 파일로 monkeypatch한 채로만 PATCH를 호출한다."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.data.questions.context_routing_blueprints import CONTEXT_ROUTING_BLUEPRINTS
from src.review_ui import review_service as rs
from src.review_ui.app import app

client = TestClient(app)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RoutingReadOnlyEndpointTest(unittest.TestCase):
    def test_get_routing_questions_returns_3(self) -> None:
        r = client.get("/internal/review/v2/routing-questions")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(len(body["questions"]), 3)

    def test_routing_question_has_no_trait_mapping_fields(self) -> None:
        r = client.get("/internal/review/v2/routing-questions")
        body = r.json()
        for q in body["questions"]:
            self.assertNotIn("trait_id", q)
            self.assertNotIn("trait_label", q)
            self.assertTrue(q["trait_signal_free"])
            self.assertEqual(q["distinct_anchor_count"], 5)
            self.assertEqual(q["total_anchor_count"], 5)
            for opt in q["options"]:
                self.assertNotIn("mapping_type", opt)
                self.assertNotIn("signals", opt)
                self.assertIn("context_anchor", opt)
                self.assertIn("anchor_label", opt)

    def test_options_have_no_overlapping_anchor_within_question(self) -> None:
        r = client.get("/internal/review/v2/routing-questions")
        for q in r.json()["questions"]:
            anchors = [o["context_anchor"] for o in q["options"]]
            self.assertEqual(len(anchors), len(set(anchors)))


class RoutingSavePathsUseTemporaryFilesTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.q_path = Path(self._tmpdir.name) / "rq.json"
        self.o_path = Path(self._tmpdir.name) / "ro.json"
        shutil.copy(rs.ROUTING_QUESTION_REVIEW_PATH, self.q_path)
        shutil.copy(rs.ROUTING_OPTION_REVIEW_PATH, self.o_path)
        self._real_q_hash = _sha256(rs.ROUTING_QUESTION_REVIEW_PATH)
        self._real_o_hash = _sha256(rs.ROUTING_OPTION_REVIEW_PATH)
        self.addCleanup(self._assert_untouched)

        patcher_q = patch("src.review_ui.review_service.ROUTING_QUESTION_REVIEW_PATH", self.q_path)
        patcher_o = patch("src.review_ui.review_service.ROUTING_OPTION_REVIEW_PATH", self.o_path)
        patcher_q.start()
        patcher_o.start()
        self.addCleanup(patcher_q.stop)
        self.addCleanup(patcher_o.stop)

    def _assert_untouched(self) -> None:
        self.assertEqual(_sha256(rs.ROUTING_QUESTION_REVIEW_PATH), self._real_q_hash)
        self.assertEqual(_sha256(rs.ROUTING_OPTION_REVIEW_PATH), self._real_o_hash)

    def _revisions(self) -> tuple[str, str]:
        body = client.get("/internal/review/v2/routing-questions").json()
        return body["question_review_revision"], body["option_review_revision"]

    def test_patch_routing_question_review_saves(self) -> None:
        bp_id = CONTEXT_ROUTING_BLUEPRINTS[0].blueprint_id
        qrev, _ = self._revisions()
        r = client.patch(
            f"/internal/review/v2/routing-questions/{bp_id}",
            json={"reviewer": "reviewer_1", "status": "APPROVE", "comment": "구분됨", "expected_revision": qrev},
        )
        self.assertEqual(r.status_code, 200)
        # 2.5.5단계: 단일 검토자 정책 — reviewer_1 APPROVE만으로 APPROVED가 된다.
        self.assertEqual(r.json()["final_status"], "APPROVED")

        from src.services.context_routing_review_store import load_routing_question_review_entries

        entries = load_routing_question_review_entries(self.q_path)
        entry = next(e for e in entries if e.blueprint_id == bp_id)
        self.assertEqual(entry.reviewer_1_status, "APPROVE")
        self.assertEqual(entry.reviewer_1_comment, "구분됨")

    def test_patch_routing_option_review_saves(self) -> None:
        bp = CONTEXT_ROUTING_BLUEPRINTS[0]
        role_id = bp.option_mappings[0].role_id
        _, orev = self._revisions()
        r = client.patch(
            f"/internal/review/v2/routing-questions/{bp.blueprint_id}/options/{role_id}",
            json={"reviewer": "reviewer_2", "status": "HOLD", "comment": "확인", "expected_revision": orev},
        )
        self.assertEqual(r.status_code, 200)

        from src.services.context_routing_review_store import load_routing_option_review_entries

        entries = load_routing_option_review_entries(self.o_path)
        entry = next(e for e in entries if e.blueprint_id == bp.blueprint_id and e.role_id == role_id)
        self.assertEqual(entry.reviewer_2_status, "HOLD")

    def test_stale_revision_returns_409(self) -> None:
        bp_id = CONTEXT_ROUTING_BLUEPRINTS[0].blueprint_id
        r = client.patch(
            f"/internal/review/v2/routing-questions/{bp_id}",
            json={"reviewer": "reviewer_1", "status": "APPROVE", "comment": "", "expected_revision": "stale"},
        )
        self.assertEqual(r.status_code, 409)

    def test_unknown_blueprint_returns_422(self) -> None:
        qrev, _ = self._revisions()
        r = client.patch(
            "/internal/review/v2/routing-questions/does_not_exist",
            json={"reviewer": "reviewer_1", "status": "APPROVE", "comment": "", "expected_revision": qrev},
        )
        self.assertEqual(r.status_code, 422)

    def test_saving_routing_review_does_not_touch_v2_direct_probe_review_files(self) -> None:
        """§10 — Routing 검수 저장이 기존 v2 Direct Probe 검수 파일(사용자 메모가 있는
        실제 파일)에 어떤 영향도 주지 않는지 이중 확인한다."""

        dp_q_hash_before = _sha256(rs.QUESTION_REVIEW_PATH)
        dp_o_hash_before = _sha256(rs.OPTION_REVIEW_PATH)

        bp_id = CONTEXT_ROUTING_BLUEPRINTS[0].blueprint_id
        qrev, _ = self._revisions()
        client.patch(
            f"/internal/review/v2/routing-questions/{bp_id}",
            json={"reviewer": "reviewer_1", "status": "APPROVE", "comment": "", "expected_revision": qrev},
        )

        self.assertEqual(_sha256(rs.QUESTION_REVIEW_PATH), dp_q_hash_before)
        self.assertEqual(_sha256(rs.OPTION_REVIEW_PATH), dp_o_hash_before)


if __name__ == "__main__":
    unittest.main()
