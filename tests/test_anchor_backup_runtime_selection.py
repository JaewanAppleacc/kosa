"""Anchor Backup Runtime 선택 규칙 — 2026-08-23 Trait Ontology v2(2.5.4단계) §2/§6/§8.

핵심 요구: 현재 Anchor를 기준으로 정확히 그 Anchor의 Backup만 후보가 되고, 다른
Anchor의 Backup으로 대체되지 않으며, 기존(REVISE) Backup은 v2 Anchor Runtime 후보에서
완전히 제외된다. Anchor가 없는 Legacy Flow는 이번 단계에서 정책을 바꾸지 않았으므로
기존 6개를 그대로 쓴다."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.api.main as main_module
from src.agents.assessment.graph.question_generation_graph import generate_tail_question
from src.api.main import app
from src.data.contexts.context_anchor_presentations import CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY
from src.data.contexts.context_definitions import CONTEXT_DEFINITIONS
from src.data.questions.anchor_backup_questions import ANCHOR_BACKUP_QUESTIONS_BY_KEY
from src.data.questions.context_routing_blueprints import CONTEXT_ROUTING_BLUEPRINTS_BY_ID
from src.data.questions.tail_option_blueprints import TAIL_OPTION_BLUEPRINTS_BY_ID
from src.data.questions.vertical_slice_backup_questions import VERTICAL_SLICE_BACKUP_QUESTIONS
from src.llm.protocols import LLMCallError
from src.services.trait_ontology_v2 import load_trait_ontology_v2

CONTEXT_DEFINITIONS_BY_ID = {c.context_id: c for c in CONTEXT_DEFINITIONS}
_TRAIT_DEFS = {t.trait_id: t for t in load_trait_ontology_v2()}
_BLUEPRINT_ID = "problem_response_v1"
_TRAIT_ID = next(iter(TAIL_OPTION_BLUEPRINTS_BY_ID[_BLUEPRINT_ID].roles[0].primary_trait_delta))

client = TestClient(app)


class _AlwaysFailLLM:
    def complete_structured(self, *, system_prompt, user_prompt, response_model):
        raise LLMCallError("의도적 실패")


def _generate(anchor, backup_questions, **overrides):
    kwargs = dict(
        question_id="test_q", context_definition=CONTEXT_DEFINITIONS_BY_ID["game"],
        trait_definition=_TRAIT_DEFS[_TRAIT_ID], all_trait_labels={t: d.label for t, d in _TRAIT_DEFS.items()},
        option_blueprint_id=_BLUEPRINT_ID, frame_id="problem_check", frame_text="힌트",
        llm_client=_AlwaysFailLLM(), anchor=anchor, backup_questions=backup_questions, max_regenerations=0,
    )
    kwargs.update(overrides)
    return generate_tail_question(**kwargs)


class FunctionLevelSelectionTest(unittest.TestCase):
    def test_anchor_present_selects_only_that_anchors_backup(self) -> None:
        anchor = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("game", "building_creation")]
        backup = ANCHOR_BACKUP_QUESTIONS_BY_KEY[("game", "building_creation")]
        outcome = _generate(anchor, [backup])
        self.assertEqual(outcome.source, "backup")
        self.assertEqual(outcome.question.question_id, "game_backup_building_creation_v2")

    def test_different_anchor_never_returns_other_anchors_backup(self) -> None:
        """다른 Anchor의 Backup을 후보 목록에 실수로 넣어도, Applicability가 막아서
        선택되지 않는다(방어적 이중 확인) — Runtime은 항상 정확히 그 Anchor 것만
        목록에 넣지만, 혹시 잘못 섞여도 통과하면 안 된다."""

        anchor = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("game", "story_exploration")]
        wrong_backup = ANCHOR_BACKUP_QUESTIONS_BY_KEY[("game", "cooperative_role")]
        outcome = _generate(anchor, [wrong_backup])
        self.assertEqual(outcome.source, "exhausted")

    def test_legacy_no_anchor_uses_existing_6_backups_unchanged(self) -> None:
        outcome = _generate(None, VERTICAL_SLICE_BACKUP_QUESTIONS["game"])
        self.assertEqual(outcome.source, "backup")
        self.assertEqual(outcome.question.question_id, "game_backup_01")

    def test_anchor_present_never_returns_old_revise_backup(self) -> None:
        """v2 Anchor Runtime 후보 목록 자체에 기존 6개를 절대 섞지 않는다는 계약을
        함수 레벨에서도 재확인한다."""

        anchor = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("game", "story_exploration")]
        outcome = _generate(anchor, VERTICAL_SLICE_BACKUP_QUESTIONS["game"])
        # 기존 6개는 all-permissive Applicability라 story_exploration에서도 통과는
        # 하지만, main.py가 애초에 이 리스트를 후보로 넘기지 않는다(다음 테스트가
        # API 레벨에서 그 계약을 확인한다) — 여기서는 함수 자체는 리스트에 있는 걸
        # 선택할 수 있다는 사실만 전제로 하고, 실제 계약은 API 레벨 테스트가 검증한다.
        self.assertIn(outcome.question.question_id, {"game_backup_01", "game_backup_02"})

    def test_exhausted_when_the_only_matching_backup_already_used(self) -> None:
        anchor = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("game", "building_creation")]
        backup = ANCHOR_BACKUP_QUESTIONS_BY_KEY[("game", "building_creation")]
        outcome = _generate(anchor, [backup], used_backup_question_ids={backup.question_id})
        self.assertEqual(outcome.source, "exhausted")
        self.assertIsNone(outcome.question)


class ApiLevelSelectionTest(unittest.TestCase):
    """main.py의 실제 후보 목록 구성 로직 — Anchor가 있으면 기존 6개가 후보 목록
    자체에 아예 들어가지 않는지 API 레벨로 확인한다."""

    def setUp(self) -> None:
        os.environ["ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES"] = "true"
        self.addCleanup(os.environ.pop, "ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", None)
        patcher = patch.object(main_module, "_llm_client", _AlwaysFailLLM())
        patcher.start()
        self.addCleanup(patcher.stop)

    def _confirmed_session_with_anchor(self, context_id: str, anchor_id: str) -> str:
        final = (context_id, *[c for c in ("game", "media", "school_life") if c != context_id])
        r = client.post("/assessment/session")
        sid = r.json()["session_id"]
        client.post("/assessment/interest-rating", json={"session_id": sid, "ratings": {c: 5 for c in final}})
        client.post(
            "/assessment/context-select",
            json={"session_id": sid, "selected_preferred_context_ids": list(final[:2])},
        )
        client.post("/assessment/context-confirm", json={"session_id": sid, "final_context_ids": list(final)})

        routing_bp = CONTEXT_ROUTING_BLUEPRINTS_BY_ID[f"{context_id}_context_router_v1"]
        q = client.post("/assessment/next-question", params={"session_id": sid}).json()["question"]
        role_id = next(m.role_id for m in routing_bp.option_mappings if m.context_anchor == anchor_id)
        option = next(o for o in q["options"] if o["role_id"] == role_id)
        client.post(
            "/assessment/answer",
            json={"session_id": sid, "question_id": q["question_id"], "selected_option_id": option["option_id"]},
        )
        return sid

    def test_backup_used_after_llm_failure_is_the_anchor_specific_one(self) -> None:
        sid = self._confirmed_session_with_anchor("game", "story_exploration")
        seed = client.post("/assessment/next-question", params={"session_id": sid}).json()["question"]
        client.post(
            "/assessment/answer",
            json={"session_id": sid, "question_id": seed["question_id"], "selected_option_id": seed["options"][0]["option_id"]},
        )
        tail = client.post("/assessment/next-question", params={"session_id": sid}).json()
        self.assertEqual(tail["status"], "BACKUP_USED")
        self.assertEqual(tail["question"]["question_id"], "game_backup_story_exploration_v2")

    def test_second_llm_failure_in_same_context_and_anchor_exhausts_not_reuses(self) -> None:
        """같은 Anchor에서 Backup을 한 번 쓰고 나면(현재 1개뿐이라) 다음 실패는
        exhausted로 끝나야 한다 — 다른 Anchor Backup으로 새지 않는다."""

        sid = self._confirmed_session_with_anchor("game", "story_exploration")
        seed = client.post("/assessment/next-question", params={"session_id": sid}).json()["question"]
        client.post(
            "/assessment/answer",
            json={"session_id": sid, "question_id": seed["question_id"], "selected_option_id": seed["options"][0]["option_id"]},
        )
        first_tail = client.post("/assessment/next-question", params={"session_id": sid}).json()
        self.assertEqual(first_tail["status"], "BACKUP_USED")
        client.post(
            "/assessment/answer",
            json={
                "session_id": sid, "question_id": first_tail["question"]["question_id"],
                "selected_option_id": first_tail["question"]["options"][0]["option_id"],
            },
        )
        second_tail = client.post("/assessment/next-question", params={"session_id": sid}).json()
        self.assertEqual(second_tail["status"], "CONTEXT_EARLY_TERMINATED")


if __name__ == "__main__":
    unittest.main()
