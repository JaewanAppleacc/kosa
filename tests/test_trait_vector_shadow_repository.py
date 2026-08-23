"""Trait Vector Shadow Repository / Runtime 배선 테스트 — 1.5단계 지시서 §14 "Runtime Shadow"."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.api.main as main_module
from src.api.main import app
from src.schemas.trait_vector_snapshot import TraitVectorEntry, TraitVectorSnapshot
from src.services.trait_vector_shadow_repository import InMemoryTraitVectorShadowRepository

client = TestClient(app)


def _entry(trait_id: str, status: str = "STRONG") -> TraitVectorEntry:
    return TraitVectorEntry(
        trait_id=trait_id, primary_signal_sum=1.0, related_signal_sum=0.0,
        confirmed_related_signal_sum=0.0, primary_evidence_count=1, related_evidence_count=0,
        context_count=1, frame_count=1, question_count=1, tendency_score=1.0,
        evidence_confidence="primary_evidence", status=status,
    )


class InMemoryRepositoryUnitTest(unittest.TestCase):
    def test_save_then_load_round_trips(self) -> None:
        repo = InMemoryTraitVectorShadowRepository()
        snapshot = TraitVectorSnapshot(entries={"causal_analysis": _entry("causal_analysis")})
        repo.save("s1", snapshot)
        loaded = repo.load("s1")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.entries["causal_analysis"].trait_id, "causal_analysis")

    def test_load_unknown_session_returns_none(self) -> None:
        repo = InMemoryTraitVectorShadowRepository()
        self.assertIsNone(repo.load("no_such_session"))

    def test_save_is_defensively_copied(self) -> None:
        """저장한 뒤 원본 Snapshot의 entries dict를 고쳐도 저장소 내용이 안 바뀐다."""

        repo = InMemoryTraitVectorShadowRepository()
        entries = {"causal_analysis": _entry("causal_analysis")}
        snapshot = TraitVectorSnapshot(entries=entries)
        repo.save("s1", snapshot)
        entries["causal_analysis"] = _entry("causal_analysis", status="NOT_PROBED")
        loaded = repo.load("s1")
        self.assertEqual(loaded.entries["causal_analysis"].status, "STRONG")

    def test_load_is_defensively_copied(self) -> None:
        """load()가 반환한 객체를 고쳐도 저장소 원본이 안 바뀐다."""

        repo = InMemoryTraitVectorShadowRepository()
        repo.save("s1", TraitVectorSnapshot(entries={"causal_analysis": _entry("causal_analysis")}))
        first_load = repo.load("s1")
        first_load.entries["causal_analysis"] = _entry("causal_analysis", status="NOT_PROBED")
        second_load = repo.load("s1")
        self.assertEqual(second_load.entries["causal_analysis"].status, "STRONG")

    def test_resaving_same_session_overwrites_not_accumulates(self) -> None:
        repo = InMemoryTraitVectorShadowRepository()
        repo.save("s1", TraitVectorSnapshot(entries={"causal_analysis": _entry("causal_analysis")}))
        repo.save("s1", TraitVectorSnapshot(entries={"planning": _entry("planning")}))
        loaded = repo.load("s1")
        self.assertEqual(set(loaded.entries), {"planning"})

    def test_different_sessions_do_not_cross_contaminate(self) -> None:
        repo = InMemoryTraitVectorShadowRepository()
        repo.save("s1", TraitVectorSnapshot(entries={"causal_analysis": _entry("causal_analysis")}))
        repo.save("s2", TraitVectorSnapshot(entries={"planning": _entry("planning")}))
        self.assertEqual(set(repo.load("s1").entries), {"causal_analysis"})
        self.assertEqual(set(repo.load("s2").entries), {"planning"})


class RuntimeProfileWiringTest(unittest.TestCase):
    """실제 /profile 흐름에서 Shadow Snapshot이 계산·저장되는지, 실패해도 Profile 응답이
    영향받지 않는지(Fail-Open) 확인한다."""

    def setUp(self) -> None:
        patcher = patch.object(main_module, "_llm_client", None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _answer_one_seed_question(self) -> str:
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
        client.post(
            "/assessment/answer",
            json={
                "session_id": session_id, "question_id": question["question_id"],
                "selected_option_id": question["options"][0]["option_id"],
            },
        )
        return session_id

    def test_profile_call_populates_shadow_repository(self) -> None:
        session_id = self._answer_one_seed_question()
        r = client.get(f"/profile/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        snapshot = main_module._trait_vector_shadow_repository.load(session_id)
        self.assertIsNotNone(snapshot)
        self.assertTrue(snapshot.entries)
        self.assertEqual(set(snapshot.entries), main_module.CORE_TRAIT_IDS)

    def test_repeated_profile_calls_do_not_accumulate_or_change_result(self) -> None:
        session_id = self._answer_one_seed_question()
        client.get(f"/profile/{session_id}")
        first = main_module._trait_vector_shadow_repository.load(session_id)
        client.get(f"/profile/{session_id}")
        second = main_module._trait_vector_shadow_repository.load(session_id)
        self.assertEqual(
            {tid: e.status for tid, e in first.entries.items()},
            {tid: e.status for tid, e in second.entries.items()},
        )
        self.assertEqual(len(first.entries), len(second.entries))

    def test_shadow_computation_failure_does_not_break_profile_response(self) -> None:
        """Fail-Open 확인: Shadow 계산 자체가 예외를 던지도록 강제해도 /profile은
        정상 200을 반환해야 한다."""

        session_id = self._answer_one_seed_question()
        with patch.object(
            main_module, "compute_trait_vector_snapshot_all", side_effect=RuntimeError("모의 계산 실패")
        ):
            r = client.get(f"/profile/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        # 계산 자체가 실패했으므로 이번 호출로는 저장되지 않는다(이전 상태 유지, 없으면 None).
        self.assertIsNone(main_module._trait_vector_shadow_repository.load(session_id))

    def test_profile_response_never_leaks_shadow_snapshot_fields(self) -> None:
        session_id = self._answer_one_seed_question()
        r = client.get(f"/profile/{session_id}")
        body_text = str(r.json())
        for forbidden in ("tendency_score", "evidence_confidence", "TraitVectorSnapshot", "primary_signal_sum"):
            self.assertNotIn(forbidden, body_text)


if __name__ == "__main__":
    unittest.main()
