"""Context Routing 질문 — 2026-08-23 Trait Ontology v2(2.5단계) §4/§5/§12.

Context Routing 질문(game/media/school_life 각 1개)은 Context 선택 취향을 더 잘게
나누기 위한 질문일 뿐, 답변이 어떤 Trait 점수에도 반영되지 않는다(§2). 이 파일은
그 "0 Trait Signal" 성질과, Routing 답변이 Legacy/v2 Evidence·Opportunity·Conflict
파이프라인을 전혀 건드리지 않는다는 것을, 실제 답변 처리 결과를 수기로 다시 계산해서
검증한다. v2 기능 Flag가 꺼져 있으면 Routing 질문 자체가 나오지 않아야 한다(§12
Feature Flag OFF Legacy Flow 불변)도 함께 확인한다."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.api.main as main_module
from src.api.main import app
from src.data.questions.context_routing_blueprints import CONTEXT_ROUTING_BLUEPRINTS_BY_CONTEXT
from src.services.context_routing_review_store import validate_routing_review_status_files

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
    return main_module._store.load(session_id).model_dump()


class ContextRoutingBlueprintStructureTest(unittest.TestCase):
    """Blueprint 자체가 구조적으로 Trait Signal이 없다는 것부터 확인한다(§4)."""

    def test_every_routing_option_has_zero_trait_delta(self) -> None:
        for context_id, bp in CONTEXT_ROUTING_BLUEPRINTS_BY_CONTEXT.items():
            for option in bp.base_question.options:
                self.assertEqual(
                    option.primary_trait_delta, {},
                    f"{context_id}/{option.role_id}: Routing 선택지는 primary_trait_delta가 반드시 빈 dict여야 한다",
                )

    def test_base_question_has_no_target_traits(self) -> None:
        for bp in CONTEXT_ROUTING_BLUEPRINTS_BY_CONTEXT.values():
            self.assertEqual(bp.base_question.target_traits, [])

    def test_exactly_5_distinct_anchors_per_context(self) -> None:
        for context_id, bp in CONTEXT_ROUTING_BLUEPRINTS_BY_CONTEXT.items():
            anchors = [m.context_anchor for m in bp.option_mappings]
            self.assertEqual(len(anchors), 5, context_id)
            self.assertEqual(len(set(anchors)), 5, f"{context_id}: Anchor가 서로 겹친다")


class ContextRoutingReviewStatusFileTest(unittest.TestCase):
    """실제 커밋 대상 검토 상태 파일(`data/reviews/v2_context_routing_*.json`)이 실제
    Blueprint 목록과 정확히 일치하는 Key 집합을 갖는지 확인한다."""

    def test_committed_review_status_files_validate_cleanly(self) -> None:
        validate_routing_review_status_files()


class ContextRoutingFlagOffRegressionTest(unittest.TestCase):
    """§12 회귀 요구사항 — Feature Flag OFF면 Routing 질문이 아예 나오지 않는다."""

    def setUp(self) -> None:
        os.environ.pop("ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", None)
        patcher = patch.object(main_module, "_llm_client", None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_first_next_question_after_confirm_is_seed_not_routing(self) -> None:
        session_id = _new_confirmed_session()
        body = client.post("/assessment/next-question", params={"session_id": session_id}).json()
        state = main_module._store.load(session_id)
        self.assertNotEqual(state.current_question_family_id, "context_routing")
        self.assertEqual(body["status"], "GENERATED")
        self.assertEqual(state.context_anchor_choices, {})
        self.assertEqual(state.routing_answer_history, [])


class ContextRoutingFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES"] = "true"
        self.addCleanup(os.environ.pop, "ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", None)
        patcher = patch.object(main_module, "_llm_client", None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_routing_question_served_before_seed_for_first_context(self) -> None:
        session_id = _new_confirmed_session()
        body = client.post("/assessment/next-question", params={"session_id": session_id}).json()
        state = main_module._store.load(session_id)
        self.assertEqual(state.current_question_family_id, "context_routing")
        self.assertEqual(len(body["question"]["options"]), 5)

    def test_idempotent_replay_returns_identical_question(self) -> None:
        session_id = _new_confirmed_session()
        first = client.post("/assessment/next-question", params={"session_id": session_id}).json()
        second = client.post("/assessment/next-question", params={"session_id": session_id}).json()
        self.assertEqual(first["question"]["question_id"], second["question"]["question_id"])
        self.assertEqual(
            [o["option_id"] for o in first["question"]["options"]],
            [o["option_id"] for o in second["question"]["options"]],
        )

    def test_answering_routing_records_only_anchor_choice_and_history(self) -> None:
        session_id = _new_confirmed_session()
        question = client.post("/assessment/next-question", params={"session_id": session_id}).json()["question"]
        before = main_module._store.load(session_id)
        self.assertEqual(len(before.evidence_ledger), 0)
        self.assertEqual(len(before.answers), 0)
        self.assertEqual(len(before.v2_probe_opportunities), 0)

        selected_option = question["options"][2]
        resp = client.post(
            "/assessment/answer",
            json={
                "session_id": session_id, "question_id": question["question_id"],
                "selected_option_id": selected_option["option_id"],
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["next_action"], "NEXT_QUESTION")

        after = main_module._store.load(session_id)
        # Routing 답변은 Legacy/v2 Evidence·Opportunity·Conflict 상태를 전혀 건드리지 않는다.
        self.assertEqual(len(after.evidence_ledger), 0)
        self.assertEqual(len(after.answers), 0)
        self.assertEqual(len(after.v2_probe_opportunities), 0)
        self.assertEqual(after.trait_summaries, {})
        self.assertEqual(after.offered_trait_ids_by_question, {})

        # Anchor 선택과 별도 이력에만 기록된다.
        self.assertIn("game", after.context_anchor_choices)
        self.assertEqual(len(after.routing_answer_history), 1)
        record = after.routing_answer_history[0]
        self.assertEqual(record.context_id, "game")
        self.assertEqual(record.selected_option_id, selected_option["option_id"])
        self.assertEqual(record.selected_role_id, selected_option["role_id"])
        self.assertEqual(record.context_anchor, after.context_anchor_choices["game"])

        self.assertIsNone(after.current_question)

    def test_proceeds_to_seed_after_routing_answer(self) -> None:
        session_id = _new_confirmed_session()
        question = client.post("/assessment/next-question", params={"session_id": session_id}).json()["question"]
        client.post(
            "/assessment/answer",
            json={
                "session_id": session_id, "question_id": question["question_id"],
                "selected_option_id": question["options"][0]["option_id"],
            },
        )
        next_body = client.post("/assessment/next-question", params={"session_id": session_id}).json()
        state = main_module._store.load(session_id)
        self.assertNotEqual(state.current_question_family_id, "context_routing")

    def test_routing_only_served_once_per_context(self) -> None:
        """같은 Context로는 두 번째 Routing 질문이 다시 나오지 않는다(Anchor가 이미
        정해졌으므로)."""

        session_id = _new_confirmed_session()
        question = client.post("/assessment/next-question", params={"session_id": session_id}).json()["question"]
        client.post(
            "/assessment/answer",
            json={
                "session_id": session_id, "question_id": question["question_id"],
                "selected_option_id": question["options"][0]["option_id"],
            },
        )
        # Seed로 넘어간 뒤에도 같은 game Context 안에서는 Routing이 다시 나오지 않는다.
        seed_body = client.post("/assessment/next-question", params={"session_id": session_id}).json()
        state = main_module._store.load(session_id)
        self.assertEqual(state.current_question_family_id, "seed")
        self.assertNotEqual(seed_body["question"]["question_id"], question["question_id"])

    def test_invalid_option_id_raises_and_leaves_state_untouched(self) -> None:
        session_id = _new_confirmed_session()
        question = client.post("/assessment/next-question", params={"session_id": session_id}).json()["question"]
        before = _stored_snapshot(session_id)

        resp = client.post(
            "/assessment/answer",
            json={
                "session_id": session_id, "question_id": question["question_id"],
                "selected_option_id": "not-a-real-option-id",
            },
        )
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(_stored_snapshot(session_id), before)

    def test_exception_right_before_store_save_leaves_stored_state_untouched(self) -> None:
        session_id = _new_confirmed_session()
        question = client.post("/assessment/next-question", params={"session_id": session_id}).json()["question"]
        before = _stored_snapshot(session_id)

        with patch.object(main_module._store, "save", side_effect=RuntimeError("의도적 주입 실패: Routing 저장")):
            with self.assertRaises(RuntimeError):
                client.post(
                    "/assessment/answer",
                    json={
                        "session_id": session_id, "question_id": question["question_id"],
                        "selected_option_id": question["options"][0]["option_id"],
                    },
                )

        self.assertEqual(_stored_snapshot(session_id), before)

    def test_exception_during_next_question_generation_leaves_stored_state_untouched(self) -> None:
        session_id = _new_confirmed_session()
        before = _stored_snapshot(session_id)

        with patch.object(main_module._store, "save", side_effect=RuntimeError("의도적 주입 실패: Routing 생성")):
            with self.assertRaises(RuntimeError):
                client.post("/assessment/next-question", params={"session_id": session_id})

        self.assertEqual(_stored_snapshot(session_id), before)


if __name__ == "__main__":
    unittest.main()
