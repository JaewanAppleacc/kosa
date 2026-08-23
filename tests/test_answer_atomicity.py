"""답변·질문 생성 처리의 예외 원자성 — 2026-08-23 Trait Ontology v2(2.3단계) §2.

`_get_state_or_404()`가 항상 State의 깊은 복사본을 반환하도록 바꿨다(`src/api/main.py`).
이 파일은 그 변경이 실제로 "예외 원자성"(답변 처리 도중 예외가 나면 Store에 저장된
원본 State가 전혀 바뀌지 않는다)을 만족하는지, 실제 여러 지점에 예외를 주입해서
확인한다. DB 수준의 동시성이나 분산 트랜잭션은 다루지 않는다 — In-Memory Store 위에서
"부분 반영을 남기지 않는다"는 성질만 검증한다.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.api.main as main_module
from src.api.main import app

client = TestClient(app)


def _new_confirmed_session(final=("game", "media", "school_life"), preferred=("game", "media")) -> str:
    r = client.post("/assessment/session")
    session_id = r.json()["session_id"]
    client.post(
        "/assessment/interest-rating",
        json={"session_id": session_id, "ratings": {c: 5 for c in final}},
    )
    client.post(
        "/assessment/context-select",
        json={"session_id": session_id, "selected_preferred_context_ids": list(preferred)},
    )
    client.post(
        "/assessment/context-confirm",
        json={"session_id": session_id, "final_context_ids": list(final)},
    )
    return session_id


def _stored_snapshot(session_id: str) -> dict:
    """Store에 실제로 저장된 State를 딥카피 dict로 떠 둔다 — 이후 같은 세션의 저장된
    State와 다시 비교해 "정말 하나도 안 바뀌었는지" 확인한다."""

    state = main_module._store.load(session_id)
    return state.model_dump()


def _drive_to_first_tail_question(session_id: str) -> dict:
    """Seed(1번째 질문)에 옵션[0]으로 답해 첫 Legacy Tail 질문까지 이동한다."""

    seed_body = client.post("/assessment/next-question", params={"session_id": session_id}).json()
    seed_question = seed_body["question"]
    client.post(
        "/assessment/answer",
        json={
            "session_id": session_id, "question_id": seed_question["question_id"],
            "selected_option_id": seed_question["options"][0]["option_id"],
        },
    )
    return client.post("/assessment/next-question", params={"session_id": session_id}).json()["question"]


def _drive_to_first_v2_probe_question(session_id: str) -> dict:
    """LLM 없이(Backup/base_question 경로) 첫 V2 Direct Probe 질문까지 이동한다."""

    for _ in range(60):
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        body = r.json()
        if body["status"] == "CONTEXT_EARLY_TERMINATED":
            continue
        state = main_module._store.load(session_id)
        if state.current_question_family_id == "v2_direct_probe":
            return body["question"]
        question = body["question"]
        ar = client.post(
            "/assessment/answer",
            json={
                "session_id": session_id, "question_id": question["question_id"],
                "selected_option_id": question["options"][0]["option_id"],
            },
        )
        if ar.json()["next_action"] == "ASSESSMENT_COMPLETE":
            break
    raise AssertionError("V2 Direct Probe 질문에 도달하지 못했다")


class LegacySeedAnswerAtomicityTest(unittest.TestCase):
    def setUp(self) -> None:
        patcher = patch.object(main_module, "_llm_client", None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_exception_during_evidence_update_leaves_stored_state_untouched(self) -> None:
        session_id = _new_confirmed_session()
        question = client.post("/assessment/next-question", params={"session_id": session_id}).json()["question"]
        before = _stored_snapshot(session_id)

        with patch(
            "src.agents.assessment.graph.answer_graph.resolve_trait_signals",
            side_effect=RuntimeError("의도적 주입 실패: Evidence 갱신"),
        ):
            with self.assertRaises(RuntimeError):
                client.post(
                    "/assessment/answer",
                    json={
                        "session_id": session_id, "question_id": question["question_id"],
                        "selected_option_id": question["options"][0]["option_id"],
                    },
                )

        self.assertEqual(_stored_snapshot(session_id), before)

    def test_exception_during_conflict_detection_leaves_stored_state_untouched(self) -> None:
        session_id = _new_confirmed_session()
        question = client.post("/assessment/next-question", params={"session_id": session_id}).json()["question"]
        before = _stored_snapshot(session_id)

        with patch(
            "src.agents.assessment.graph.answer_graph.detect_explicit_conflicts",
            side_effect=RuntimeError("의도적 주입 실패: Conflict 판정"),
        ):
            with self.assertRaises(RuntimeError):
                client.post(
                    "/assessment/answer",
                    json={
                        "session_id": session_id, "question_id": question["question_id"],
                        "selected_option_id": question["options"][0]["option_id"],
                    },
                )

        self.assertEqual(_stored_snapshot(session_id), before)

    def test_exception_during_stop_continue_leaves_stored_state_untouched(self) -> None:
        session_id = _new_confirmed_session()
        question = client.post("/assessment/next-question", params={"session_id": session_id}).json()["question"]
        before = _stored_snapshot(session_id)

        with patch(
            "src.agents.assessment.graph.answer_graph.decide_stop_or_continue",
            side_effect=RuntimeError("의도적 주입 실패: Stop/Continue 판단"),
        ):
            with self.assertRaises(RuntimeError):
                client.post(
                    "/assessment/answer",
                    json={
                        "session_id": session_id, "question_id": question["question_id"],
                        "selected_option_id": question["options"][0]["option_id"],
                    },
                )

        self.assertEqual(_stored_snapshot(session_id), before)

    def test_exception_right_before_store_save_leaves_stored_state_untouched(self) -> None:
        session_id = _new_confirmed_session()
        question = client.post("/assessment/next-question", params={"session_id": session_id}).json()["question"]
        before = _stored_snapshot(session_id)

        with patch.object(main_module._store, "save", side_effect=RuntimeError("의도적 주입 실패: Store 저장")):
            with self.assertRaises(RuntimeError):
                client.post(
                    "/assessment/answer",
                    json={
                        "session_id": session_id, "question_id": question["question_id"],
                        "selected_option_id": question["options"][0]["option_id"],
                    },
                )

        self.assertEqual(_stored_snapshot(session_id), before)

    def test_exception_during_seed_next_question_generation_leaves_stored_state_untouched(self) -> None:
        session_id = _new_confirmed_session()
        before = _stored_snapshot(session_id)

        with patch(
            "src.api.mock_data.next_mock_question", side_effect=RuntimeError("의도적 주입 실패: Seed 생성"),
        ):
            with self.assertRaises(RuntimeError):
                client.post("/assessment/next-question", params={"session_id": session_id})

        self.assertEqual(_stored_snapshot(session_id), before)

    def test_retry_after_injected_failure_succeeds_and_evidence_recorded_exactly_once(self) -> None:
        session_id = _new_confirmed_session()
        question = client.post("/assessment/next-question", params={"session_id": session_id}).json()["question"]
        ledger_len_before = len(main_module._store.load(session_id).evidence_ledger)
        payload = {
            "session_id": session_id, "question_id": question["question_id"],
            "selected_option_id": question["options"][0]["option_id"],
        }

        with patch(
            "src.agents.assessment.graph.answer_graph.resolve_trait_signals",
            side_effect=RuntimeError("의도적 주입 실패"),
        ):
            with self.assertRaises(RuntimeError):
                client.post("/assessment/answer", json=payload)

        # 실패 직후에도 current_question은 그대로 남아 재시도할 수 있어야 한다.
        state = main_module._store.load(session_id)
        self.assertIsNotNone(state.current_question)
        self.assertEqual(state.current_question.question_id, question["question_id"])
        self.assertEqual(len(state.evidence_ledger), ledger_len_before)

        retry = client.post("/assessment/answer", json=payload)
        self.assertEqual(retry.status_code, 200)

        state = main_module._store.load(session_id)
        self.assertEqual(len(state.evidence_ledger), ledger_len_before + 1)
        self.assertIsNone(state.current_question)


class LegacyTailAnswerAtomicityTest(unittest.TestCase):
    def setUp(self) -> None:
        patcher = patch.object(main_module, "_llm_client", None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_exception_during_tail_next_question_generation_leaves_stored_state_untouched(self) -> None:
        session_id = _new_confirmed_session()
        seed_body = client.post("/assessment/next-question", params={"session_id": session_id}).json()
        seed_question = seed_body["question"]
        client.post(
            "/assessment/answer",
            json={
                "session_id": session_id, "question_id": seed_question["question_id"],
                "selected_option_id": seed_question["options"][0]["option_id"],
            },
        )
        before = _stored_snapshot(session_id)

        with patch(
            "src.api.mock_data.tail_question_from_planner_decision",
            side_effect=RuntimeError("의도적 주입 실패: Tail(Mock) 생성"),
        ):
            with self.assertRaises(RuntimeError):
                client.post("/assessment/next-question", params={"session_id": session_id})

        self.assertEqual(_stored_snapshot(session_id), before)

    def test_exception_during_evidence_update_after_tail_answer_leaves_stored_state_untouched(self) -> None:
        session_id = _new_confirmed_session()
        question = _drive_to_first_tail_question(session_id)
        before = _stored_snapshot(session_id)

        with patch(
            "src.agents.assessment.graph.answer_graph.resolve_trait_signals",
            side_effect=RuntimeError("의도적 주입 실패: Tail 답변 Evidence 갱신"),
        ):
            with self.assertRaises(RuntimeError):
                client.post(
                    "/assessment/answer",
                    json={
                        "session_id": session_id, "question_id": question["question_id"],
                        "selected_option_id": question["options"][0]["option_id"],
                    },
                )

        self.assertEqual(_stored_snapshot(session_id), before)


class V2DirectProbeAnswerAtomicityTest(unittest.TestCase):
    def setUp(self) -> None:
        import os

        os.environ["ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES"] = "true"
        self.addCleanup(os.environ.pop, "ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", None)
        patcher = patch.object(main_module, "_llm_client", None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_exception_during_v2_signal_recording_leaves_stored_state_untouched(self) -> None:
        session_id = _new_confirmed_session()
        question = _drive_to_first_v2_probe_question(session_id)
        before = _stored_snapshot(session_id)

        with patch(
            "src.api.main.resolve_trait_signals", side_effect=RuntimeError("의도적 주입 실패: v2 Signal 기록"),
        ):
            with self.assertRaises(RuntimeError):
                client.post(
                    "/assessment/answer",
                    json={
                        "session_id": session_id, "question_id": question["question_id"],
                        "selected_option_id": question["options"][0]["option_id"],
                    },
                )

        self.assertEqual(_stored_snapshot(session_id), before)

    def test_exception_during_v2_direct_probe_question_generation_leaves_stored_state_untouched(self) -> None:
        session_id = _new_confirmed_session()
        # Legacy를 실제로 끝내는 답변 하나가 v2_probe_phase를 V2_DIRECT_PROBE로 바꾼다
        # (그 답변 처리 자체가 current_question도 이미 비운다) — next-question이 그
        # 상태에서 다음 v2 질문을 "서빙"하려는 그 시도 자체를 실패시킨다.
        state = main_module._store.load(session_id)
        for _ in range(60):
            if state.v2_probe_phase == "V2_DIRECT_PROBE":
                break
            r = client.post("/assessment/next-question", params={"session_id": session_id})
            body = r.json()
            if body["status"] == "CONTEXT_EARLY_TERMINATED":
                state = main_module._store.load(session_id)
                continue
            question = body["question"]
            ar = client.post(
                "/assessment/answer",
                json={
                    "session_id": session_id, "question_id": question["question_id"],
                    "selected_option_id": question["options"][0]["option_id"],
                },
            )
            if ar.json()["next_action"] == "ASSESSMENT_COMPLETE":
                self.fail("V2 Direct Probe 진입 전에 세션이 끝났다")
            state = main_module._store.load(session_id)
        else:
            self.fail("V2 Direct Probe Phase에 도달하지 못했다")
        self.assertIsNone(state.current_question)
        before = _stored_snapshot(session_id)

        with patch(
            "src.api.main.generate_v2_direct_probe_question",
            side_effect=RuntimeError("의도적 주입 실패: v2 질문 생성"),
        ):
            with self.assertRaises(RuntimeError):
                client.post("/assessment/next-question", params={"session_id": session_id})

        self.assertEqual(_stored_snapshot(session_id), before)

    def test_retry_after_injected_failure_records_opportunity_exactly_once(self) -> None:
        session_id = _new_confirmed_session()
        question = _drive_to_first_v2_probe_question(session_id)
        opportunities_before = len(main_module._store.load(session_id).v2_probe_opportunities)
        payload = {
            "session_id": session_id, "question_id": question["question_id"],
            "selected_option_id": question["options"][0]["option_id"],
        }

        with patch(
            "src.api.main.resolve_trait_signals", side_effect=RuntimeError("의도적 주입 실패"),
        ):
            with self.assertRaises(RuntimeError):
                client.post("/assessment/answer", json=payload)

        state = main_module._store.load(session_id)
        self.assertIsNotNone(state.current_question)
        self.assertEqual(len(state.v2_probe_opportunities), opportunities_before)

        retry = client.post("/assessment/answer", json=payload)
        self.assertEqual(retry.status_code, 200)

        state = main_module._store.load(session_id)
        self.assertEqual(len(state.v2_probe_opportunities), opportunities_before + 1)


if __name__ == "__main__":
    unittest.main()
