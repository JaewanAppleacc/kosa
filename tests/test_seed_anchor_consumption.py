"""Seed Anchor Variant 실제 소비 경로 — 2026-08-23 Trait Ontology v2(2.5.1단계) §1/§4/§5/§13.

2.5단계에서 `context_anchor_choices`는 저장만 되고 어디서도 읽히지 않았다(§1 재현).
이 파일은 (1) 그 문제가 실제로 고쳐졌는지 — Anchor가 다르면 Seed 질문이 실제로
달라지는지 — 그리고 (2) Anchor가 Trait Mapping·Evidence·Opportunity·Conflict에는
여전히 전혀 영향을 주지 않는지(§2/§12 "Trait 불변")를 API 레벨과 함수 레벨에서 모두
확인한다."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.api.main as main_module
from src.api.main import app
from src.api.mock_data import seed_question_as_finalized
from src.data.questions.context_routing_blueprints import CONTEXT_ROUTING_BLUEPRINTS_BY_ID
from src.data.questions.vertical_slice_seed_questions import VERTICAL_SLICE_SEED_QUESTIONS

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


def _answer_routing_with_anchor(session_id: str, context_id: str, anchor_id: str) -> None:
    q = client.post("/assessment/next-question", params={"session_id": session_id}).json()["question"]
    routing_bp_id = f"{context_id}_context_router_v1"
    bp = CONTEXT_ROUTING_BLUEPRINTS_BY_ID[routing_bp_id]
    role_id = next(m.role_id for m in bp.option_mappings if m.context_anchor == anchor_id)
    option = next(o for o in q["options"] if o["role_id"] == role_id)
    client.post(
        "/assessment/answer",
        json={"session_id": session_id, "question_id": q["question_id"], "selected_option_id": option["option_id"]},
    )


class MockDataFunctionLevelTest(unittest.TestCase):
    """`seed_question_as_finalized()` 자체를 직접 호출해 결정론적 동작을 확인한다."""

    def test_no_anchor_returns_neutral_base_text(self) -> None:
        seed = VERTICAL_SLICE_SEED_QUESTIONS["game"]
        result = seed_question_as_finalized(seed, anchor_id=None)
        self.assertEqual(result.question_text, seed.question_text)

    def test_unregistered_anchor_falls_back_to_neutral_text(self) -> None:
        seed = VERTICAL_SLICE_SEED_QUESTIONS["game"]
        result = seed_question_as_finalized(seed, anchor_id="not_a_real_anchor")
        self.assertEqual(result.question_text, seed.question_text)

    def test_same_anchor_same_state_always_same_question(self) -> None:
        seed = VERTICAL_SLICE_SEED_QUESTIONS["media"]
        r1 = seed_question_as_finalized(seed, anchor_id="film_drama")
        r2 = seed_question_as_finalized(seed, anchor_id="film_drama")
        self.assertEqual(r1.question_text, r2.question_text)
        self.assertEqual([o.text for o in r1.options], [o.text for o in r2.options])

    def test_anchor_variant_keeps_option_id_role_id_and_trait_delta_unchanged(self) -> None:
        seed = VERTICAL_SLICE_SEED_QUESTIONS["school_life"]
        neutral = seed_question_as_finalized(seed, anchor_id=None)
        anchored = seed_question_as_finalized(seed, anchor_id="friendship")
        self.assertEqual(
            [(o.option_id, o.role_id, o.primary_trait_delta) for o in neutral.options],
            [(o.option_id, o.role_id, o.primary_trait_delta) for o in anchored.options],
        )
        # 문구는 실제로 달라야 한다(둘 다 같으면 Anchor가 반영 안 된 것).
        self.assertNotEqual(
            [o.text for o in neutral.options], [o.text for o in anchored.options],
        )

    def test_game_all_5_anchors_produce_distinct_seed_text(self) -> None:
        seed = VERTICAL_SLICE_SEED_QUESTIONS["game"]
        anchors = ["story_exploration", "strategy_puzzle", "competition_mastery", "cooperative_role", "building_creation"]
        texts = {seed_question_as_finalized(seed, anchor_id=a).question_text for a in anchors}
        self.assertEqual(len(texts), 5)

    def test_media_all_5_anchors_produce_distinct_seed_text(self) -> None:
        seed = VERTICAL_SLICE_SEED_QUESTIONS["media"]
        anchors = ["film_drama", "online_video", "animation_webcontent", "stage_performance", "documentary"]
        texts = {seed_question_as_finalized(seed, anchor_id=a).question_text for a in anchors}
        self.assertEqual(len(texts), 5)

    def test_school_life_all_5_anchors_produce_distinct_seed_text(self) -> None:
        seed = VERTICAL_SLICE_SEED_QUESTIONS["school_life"]
        anchors = ["academic_study", "assignment_evaluation", "course_career", "friendship", "club_activity"]
        texts = {seed_question_as_finalized(seed, anchor_id=a).question_text for a in anchors}
        self.assertEqual(len(texts), 5)


class ApiLevelAnchorConsumptionTest(unittest.TestCase):
    """실제 `/assessment/next-question` 응답 수준에서 Anchor가 반영되는지 확인한다."""

    def setUp(self) -> None:
        os.environ["ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES"] = "true"
        self.addCleanup(os.environ.pop, "ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", None)
        patcher = patch.object(main_module, "_llm_client", None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_game_two_different_anchors_produce_different_seed_questions(self) -> None:
        sid_a = _new_confirmed_session()
        _answer_routing_with_anchor(sid_a, "game", "story_exploration")
        seed_a = client.post("/assessment/next-question", params={"session_id": sid_a}).json()["question"]

        sid_b = _new_confirmed_session()
        _answer_routing_with_anchor(sid_b, "game", "cooperative_role")
        seed_b = client.post("/assessment/next-question", params={"session_id": sid_b}).json()["question"]

        self.assertNotEqual(seed_a["question_text"], seed_b["question_text"])
        self.assertNotEqual([o["text"] for o in seed_a["options"]], [o["text"] for o in seed_b["options"]])
        # role_id 집합과 각 role의 primary_trait_delta는 그대로여야 한다.
        self.assertEqual(
            sorted((o["role_id"], tuple(sorted(o["primary_trait_delta"].items()))) for o in seed_a["options"]),
            sorted((o["role_id"], tuple(sorted(o["primary_trait_delta"].items()))) for o in seed_b["options"]),
        )

    def test_media_two_different_anchors_produce_different_seed_questions(self) -> None:
        sid_a = _new_confirmed_session(final=("media", "game", "school_life"))
        _answer_routing_with_anchor(sid_a, "media", "film_drama")
        seed_a = client.post("/assessment/next-question", params={"session_id": sid_a}).json()["question"]

        sid_b = _new_confirmed_session(final=("media", "game", "school_life"))
        _answer_routing_with_anchor(sid_b, "media", "documentary")
        seed_b = client.post("/assessment/next-question", params={"session_id": sid_b}).json()["question"]

        self.assertNotEqual(seed_a["question_text"], seed_b["question_text"])

    def test_school_life_two_different_anchors_produce_different_seed_questions(self) -> None:
        sid_a = _new_confirmed_session(final=("school_life", "game", "media"))
        _answer_routing_with_anchor(sid_a, "school_life", "friendship")
        seed_a = client.post("/assessment/next-question", params={"session_id": sid_a}).json()["question"]

        sid_b = _new_confirmed_session(final=("school_life", "game", "media"))
        _answer_routing_with_anchor(sid_b, "school_life", "academic_study")
        seed_b = client.post("/assessment/next-question", params={"session_id": sid_b}).json()["question"]

        self.assertNotEqual(seed_a["question_text"], seed_b["question_text"])

    def test_friendship_anchor_first_question_is_not_academic_study_question(self) -> None:
        """§9 적용 가능성: friendship을 선택했다고 학업 질문이 나오면 안 된다(그
        반대도 마찬가지) — 첫 질문이 실제로 그 Anchor의 상황을 반영해야 한다."""

        sid = _new_confirmed_session(final=("school_life", "game", "media"))
        _answer_routing_with_anchor(sid, "school_life", "friendship")
        seed = client.post("/assessment/next-question", params={"session_id": sid}).json()["question"]
        self.assertNotIn("시험 범위", seed["question_text"])

    def test_academic_study_anchor_first_question_is_not_friendship_question(self) -> None:
        sid = _new_confirmed_session(final=("school_life", "game", "media"))
        _answer_routing_with_anchor(sid, "school_life", "academic_study")
        seed = client.post("/assessment/next-question", params={"session_id": sid}).json()["question"]
        self.assertNotIn("오해", seed["question_text"])

    def test_course_career_anchor_first_question_relates_to_course_or_career(self) -> None:
        sid = _new_confirmed_session(final=("school_life", "game", "media"))
        _answer_routing_with_anchor(sid, "school_life", "course_career")
        seed = client.post("/assessment/next-question", params={"session_id": sid}).json()["question"]
        self.assertTrue(
            ("선택과목" in seed["question_text"]) or ("진로" in seed["question_text"]),
            seed["question_text"],
        )

    def test_anchor_choice_does_not_affect_evidence_ledger_or_opportunities(self) -> None:
        sid = _new_confirmed_session()
        _answer_routing_with_anchor(sid, "game", "strategy_puzzle")
        state = main_module._store.load(sid)
        self.assertEqual(len(state.evidence_ledger), 0)
        self.assertEqual(len(state.v2_probe_opportunities), 0)
        self.assertEqual(len(state.answers), 0)

    def test_anchor_choice_does_not_affect_conflict_state(self) -> None:
        sid = _new_confirmed_session()
        _answer_routing_with_anchor(sid, "game", "strategy_puzzle")
        state = main_module._store.load(sid)
        self.assertEqual(state.unresolved_conflict_trait_ids, set())


if __name__ == "__main__":
    unittest.main()
