"""V2 Direct Probe 검수 UI — 내부 FastAPI App 테스트 — 2026-08-23 Trait Ontology
v2(2.4단계) §13.

`src/review_ui/app.py`가 `src/api/main.py`(공개 서비스 API)와 완전히 분리돼 있는지,
저장 요청이 안전하게 검증되는지 확인한다. 저장 관련 테스트는 실제 커밋된
`data/reviews/*.json`을 절대 건드리지 않는다 — `app.dependency_overrides` 대신 Review
Service의 경로 인자를 그대로 monkeypatch해 임시 파일만 쓴다."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.data.questions.trait_v2_direct_probe_blueprints import V2_DIRECT_PROBE_BLUEPRINTS
from src.review_ui import review_service as rs
from src.review_ui.app import app

client = TestClient(app)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ReadOnlyEndpointsTest(unittest.TestCase):
    def test_get_questions_returns_14(self) -> None:
        r = client.get("/internal/review/v2/questions")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["questions"]), 14)

    def test_get_summary_returns_totals(self) -> None:
        r = client.get("/internal/review/v2/summary")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["question_total"], 14)
        self.assertEqual(body["option_total"], 70)

    def test_index_page_served(self) -> None:
        r = client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/html", r.headers["content-type"])


class SavePathsUseTemporaryFilesTest(unittest.TestCase):
    """저장 관련 API 테스트는 review_service 모듈의 경로 상수를 임시 파일로
    monkeypatch한 채로만 PATCH를 호출한다 — 실제 커밋된 JSON을 절대 건드리지 않는다."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.q_path = Path(self._tmpdir.name) / "q.json"
        self.o_path = Path(self._tmpdir.name) / "o.json"
        shutil.copy(rs.QUESTION_REVIEW_PATH, self.q_path)
        shutil.copy(rs.OPTION_REVIEW_PATH, self.o_path)
        self._real_q_hash = _sha256(rs.QUESTION_REVIEW_PATH)
        self._real_o_hash = _sha256(rs.OPTION_REVIEW_PATH)
        self.addCleanup(self._assert_untouched)

        patcher_q = patch("src.review_ui.review_service.QUESTION_REVIEW_PATH", self.q_path)
        patcher_o = patch("src.review_ui.review_service.OPTION_REVIEW_PATH", self.o_path)
        patcher_q.start()
        patcher_o.start()
        self.addCleanup(patcher_q.stop)
        self.addCleanup(patcher_o.stop)

    def _assert_untouched(self) -> None:
        self.assertEqual(_sha256(rs.QUESTION_REVIEW_PATH), self._real_q_hash)
        self.assertEqual(_sha256(rs.OPTION_REVIEW_PATH), self._real_o_hash)

    def _revisions(self) -> tuple[str, str]:
        body = client.get("/internal/review/v2/questions").json()
        return body["question_review_revision"], body["option_review_revision"]

    def test_patch_question_review_saves(self) -> None:
        bp_id = V2_DIRECT_PROBE_BLUEPRINTS[0].blueprint_id
        qrev, _ = self._revisions()
        r = client.patch(
            f"/internal/review/v2/questions/{bp_id}",
            json={"reviewer": "reviewer_1", "status": "APPROVE", "comment": "좋음", "expected_revision": qrev},
        )
        self.assertEqual(r.status_code, 200)
        # 2.5.5단계: 단일 검토자 정책 — reviewer_1 APPROVE만으로 APPROVED가 된다.
        # reviewer_2가 TBD인 것은 결과에 영향을 주지 않는다.
        self.assertEqual(r.json()["final_status"], "APPROVED")

        entries = rs.load_question_review_entries(self.q_path)
        entry = next(e for e in entries if e.blueprint_id == bp_id)
        self.assertEqual(entry.reviewer_1_status, "APPROVE")
        self.assertEqual(entry.reviewer_1_comment, "좋음")

    def test_patch_option_review_saves(self) -> None:
        bp = V2_DIRECT_PROBE_BLUEPRINTS[0]
        role_id = bp.option_mappings[0].role_id
        _, orev = self._revisions()
        r = client.patch(
            f"/internal/review/v2/questions/{bp.blueprint_id}/options/{role_id}",
            json={"reviewer": "reviewer_2", "status": "HOLD", "comment": "확인 필요", "expected_revision": orev},
        )
        self.assertEqual(r.status_code, 200)
        entries = rs.load_option_review_entries(self.o_path)
        entry = next(e for e in entries if e.blueprint_id == bp.blueprint_id and e.role_id == role_id)
        self.assertEqual(entry.reviewer_2_status, "HOLD")

    def test_missing_reviewer_field_rejected(self) -> None:
        bp_id = V2_DIRECT_PROBE_BLUEPRINTS[0].blueprint_id
        qrev, _ = self._revisions()
        r = client.patch(
            f"/internal/review/v2/questions/{bp_id}",
            json={"status": "APPROVE", "comment": "", "expected_revision": qrev},
        )
        self.assertEqual(r.status_code, 422)

    def test_invalid_reviewer_value_rejected(self) -> None:
        bp_id = V2_DIRECT_PROBE_BLUEPRINTS[0].blueprint_id
        qrev, _ = self._revisions()
        r = client.patch(
            f"/internal/review/v2/questions/{bp_id}",
            json={"reviewer": "someone_else", "status": "APPROVE", "comment": "", "expected_revision": qrev},
        )
        self.assertEqual(r.status_code, 422)

    def test_stale_revision_returns_409(self) -> None:
        bp_id = V2_DIRECT_PROBE_BLUEPRINTS[0].blueprint_id
        r = client.patch(
            f"/internal/review/v2/questions/{bp_id}",
            json={"reviewer": "reviewer_1", "status": "APPROVE", "comment": "", "expected_revision": "stale"},
        )
        self.assertEqual(r.status_code, 409)

    def test_unknown_blueprint_returns_422(self) -> None:
        qrev, _ = self._revisions()
        r = client.patch(
            "/internal/review/v2/questions/does_not_exist",
            json={"reviewer": "reviewer_1", "status": "APPROVE", "comment": "", "expected_revision": qrev},
        )
        self.assertEqual(r.status_code, 422)


class SeparationFromPublicApiTest(unittest.TestCase):
    def test_public_api_has_no_review_routes(self) -> None:
        from src.api.main import app as public_app

        public_paths = {route.path for route in public_app.routes}
        review_paths = {route.path for route in app.routes if hasattr(route, "path")}
        self.assertEqual(public_paths & {p for p in review_paths if "internal" in p}, set())
        for path in public_paths:
            self.assertNotIn("internal", path)

    def test_review_app_is_a_different_object_than_public_app(self) -> None:
        from src.api.main import app as public_app

        self.assertIsNot(app, public_app)


class LocalOnlyBindingTest(unittest.TestCase):
    def test_launcher_binds_127_0_0_1_by_default(self) -> None:
        import importlib

        launcher = importlib.import_module("scripts.run_v2_direct_probe_review_ui")
        self.assertEqual(launcher.HOST, "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
