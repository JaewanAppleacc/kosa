"""EvidenceRecord v2 Signal 통합 테스트 — 지시서 §15 "Evidence" (answer_graph 실제 배선).

Mock Trait Summary를 직접 주입하지 않고 실제 /assessment 흐름으로 확인한다.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.api.main as main_module
from src.api.main import app
from src.schemas.evidence import EvidenceOrigin

client = TestClient(app)


class EvidenceLedgerV2SignalIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        patcher = patch.object(main_module, "_llm_client", None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _new_session_answer_seed(self) -> str:
        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 5, "media": 5, "school_life": 4}},
        )
        client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "media"]},
        )
        client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game", "media", "school_life"]},
        )
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        question = r.json()["question"]
        option = question["options"][0]
        r = client.post(
            "/assessment/answer",
            json={
                "session_id": session_id,
                "question_id": question["question_id"],
                "selected_option_id": option["option_id"],
            },
        )
        self.assertEqual(r.status_code, 200)
        return session_id

    def test_seed_answer_populates_applied_trait_signals_v2(self) -> None:
        session_id = self._new_session_answer_seed()
        state = main_module._store.load(session_id)
        evidence = state.evidence_ledger[-1]
        self.assertTrue(evidence.applied_trait_signals_v2)
        primary = [s for s in evidence.applied_trait_signals_v2 if s.signal_role == "PRIMARY"]
        self.assertEqual(len(primary), 1)
        # legacy와 v2 PRIMARY는 항상 같은 Trait·weight=1.0을 가리켜야 한다(같은 사실의
        # 두 표현일 뿐 새로운 판단이 아니다).
        self.assertEqual(set(evidence.applied_primary_trait_delta), {primary[0].trait_id})

    def test_legacy_applied_primary_trait_delta_is_still_populated(self) -> None:
        """기존 applied_primary_trait_delta는 즉시 제거하지 않고 하위 호환을 위해
        그대로 유지한다(§8)."""

        session_id = self._new_session_answer_seed()
        state = main_module._store.load(session_id)
        evidence = state.evidence_ledger[-1]
        self.assertTrue(evidence.applied_primary_trait_delta)

    def test_v2_signal_never_appears_in_any_api_response(self) -> None:
        session_id = self._new_session_answer_seed()
        for path in (f"/profile/{session_id}", f"/majors/{session_id}", f"/subgraph/{session_id}"):
            r = client.get(path)
            body_text = str(r.json())
            for forbidden in ("trait_signal", "signal_role", "related_concept_ids", "primary_signal_sum"):
                self.assertNotIn(forbidden, body_text, f"{path} leaked {forbidden!r}")

    def test_conflict_resolution_answers_never_get_v2_signals(self) -> None:
        """등록되지 않은 role_id는 원래도 빈 목록이지만, Conflict Resolution Origin은
        방어적으로 한 번 더 비운다는 코드 경로 자체가 실제로 존재하는지 회귀 확인."""

        session_id = self._new_session_answer_seed()
        state = main_module._store.load(session_id)
        for evidence in state.evidence_ledger:
            if evidence.evidence_origin == EvidenceOrigin.CONFLICT_RESOLUTION:
                self.assertEqual(evidence.applied_trait_signals_v2, [])


if __name__ == "__main__":
    unittest.main()
