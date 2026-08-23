"""Unsafe Backup 경로 재현·수정 + Backup Quality Gate — 2026-08-23 Trait Ontology
v2(2.5.3단계) §1/§2/§14.

2.5.3단계 이전에는 `_use_backup()`이 Quality Gate 없이 사용하지 않은 첫 Backup을
그대로 반환했다 — Anchor가 금지한 표현이 그대로 나갈 수 있었다(재현 결과는
`outputs/reviews/backup_question_migration_audit.md` 참고). 이 파일은 그 수정이
실제로 동작하는지, 그리고 합성(poisoned) Backup 목록으로 skip→다음 후보→exhausted
경로 전체를 확인한다."""

from __future__ import annotations

import unittest

from src.agents.assessment.graph.question_generation_graph import (
    QuestionGenerationGraphState,
    _use_backup,
)
from src.data.contexts.context_anchor_presentations import CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY
from src.data.contexts.context_definitions import CONTEXT_DEFINITIONS
from src.data.questions.tail_option_blueprints import TAIL_OPTION_BLUEPRINTS_BY_ID
from src.data.questions.vertical_slice_backup_questions import VERTICAL_SLICE_BACKUP_QUESTIONS
from src.schemas.question import FinalizedOption, FinalizedQuestion
from src.services.trait_ontology_v2 import load_trait_ontology_v2

CONTEXT_DEFINITIONS_BY_ID = {c.context_id: c for c in CONTEXT_DEFINITIONS}
_TRAIT_DEFS = {t.trait_id: t for t in load_trait_ontology_v2()}
_BLUEPRINT_ID = "problem_response_v1"
_TRAIT_ID = next(iter(TAIL_OPTION_BLUEPRINTS_BY_ID[_BLUEPRINT_ID].roles[0].primary_trait_delta))


def _poisoned_backup(question_id: str, poisoned_text: str) -> FinalizedQuestion:
    """실제 role_id 5개를 그대로 쓰되, 첫 옵션에 forbidden 표현을 심은 합성 Backup."""

    roles = TAIL_OPTION_BLUEPRINTS_BY_ID[_BLUEPRINT_ID].roles
    options = [
        FinalizedOption(
            option_id=f"{question_id}_o{i}", role_id=r.role_id,
            text=poisoned_text if i == 1 else f"{r.role_id} 정상 문장",
            primary_trait_delta={_TRAIT_ID: 1},
        )
        for i, r in enumerate(roles, start=1)
    ]
    return FinalizedQuestion(
        question_id=question_id, context="game", target_traits=[], frame_id="backup",
        question_text="테스트 질문?", options=options,
    )


def _state(anchor=None, backup_questions=None, used_backup_question_ids=None) -> QuestionGenerationGraphState:
    return QuestionGenerationGraphState(
        question_id="q1", context_definition=CONTEXT_DEFINITIONS_BY_ID["game"],
        trait_definition=_TRAIT_DEFS[_TRAIT_ID], all_trait_labels={_TRAIT_ID: "라벨"},
        option_blueprint_id=_BLUEPRINT_ID, frame_id="problem_check", frame_text="힌트",
        llm_client=None, anchor=anchor,
        backup_questions=backup_questions or [], used_backup_question_ids=used_backup_question_ids or set(),
    )


class UnsafeBackupReproductionFixTest(unittest.TestCase):
    """실제 Backup 정본(재작성 완료)이 모든 Anchor에서 안전하게 반환되는지 확인한다."""

    def test_game_story_exploration_does_not_return_team_presupposing_backup(self) -> None:
        anchor = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("game", "story_exploration")]
        state = _state(anchor=anchor, backup_questions=VERTICAL_SLICE_BACKUP_QUESTIONS["game"])
        result = _use_backup(state)
        outcome = result["outcome"]
        self.assertEqual(outcome.source, "backup")
        all_text = outcome.question.question_text + " " + " ".join(o.text for o in outcome.question.options)
        for phrase in anchor.forbidden_assumptions:
            self.assertNotIn(phrase, all_text)

    def test_media_stage_performance_does_not_return_video_editing_backup(self) -> None:
        anchor = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("media", "stage_performance")]
        state = _state(anchor=anchor, backup_questions=VERTICAL_SLICE_BACKUP_QUESTIONS["media"])
        result = _use_backup(state)
        outcome = result["outcome"]
        self.assertEqual(outcome.source, "backup")
        all_text = outcome.question.question_text + " " + " ".join(o.text for o in outcome.question.options)
        for phrase in anchor.forbidden_assumptions:
            self.assertNotIn(phrase, all_text)

    def test_media_documentary_does_not_return_fictional_production_backup(self) -> None:
        anchor = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("media", "documentary")]
        state = _state(anchor=anchor, backup_questions=VERTICAL_SLICE_BACKUP_QUESTIONS["media"])
        result = _use_backup(state)
        outcome = result["outcome"]
        self.assertEqual(outcome.source, "backup")
        all_text = outcome.question.question_text + " " + " ".join(o.text for o in outcome.question.options)
        for phrase in anchor.forbidden_assumptions:
            self.assertNotIn(phrase, all_text)

    def test_school_life_friendship_does_not_return_group_project_backup(self) -> None:
        anchor = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("school_life", "friendship")]
        state = _state(anchor=anchor, backup_questions=VERTICAL_SLICE_BACKUP_QUESTIONS["school_life"])
        result = _use_backup(state)
        outcome = result["outcome"]
        self.assertEqual(outcome.source, "backup")
        all_text = outcome.question.question_text + " " + " ".join(o.text for o in outcome.question.options)
        for phrase in anchor.forbidden_assumptions:
            self.assertNotIn(phrase, all_text)


class PoisonedBackupSkipLogicTest(unittest.TestCase):
    """합성(poisoned) Backup 목록으로 skip→다음 후보→exhausted 경로를 직접 확인한다."""

    def test_first_candidate_rejected_falls_through_to_next_compatible_candidate(self) -> None:
        anchor = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("game", "story_exploration")]
        poisoned = _poisoned_backup("poisoned_01", "팀원과 함께 경기 순위를 다툰다")
        clean = _poisoned_backup("clean_02", "이 상황에서 무엇을 먼저 할지 생각한다")
        state = _state(anchor=anchor, backup_questions=[poisoned, clean])
        result = _use_backup(state)
        outcome = result["outcome"]
        self.assertEqual(outcome.source, "backup")
        self.assertEqual(outcome.question.question_id, "clean_02")
        self.assertEqual(outcome.backup_candidates_checked, 2)
        self.assertEqual(outcome.backup_candidates_rejected, 1)

    def test_all_candidates_rejected_returns_exhausted_not_a_bad_question(self) -> None:
        anchor = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("game", "story_exploration")]
        poisoned_a = _poisoned_backup("poisoned_a", "팀원과 함께 경기 순위를 다툰다")
        poisoned_b = _poisoned_backup("poisoned_b", "협동 역할을 나눠 팀원과 진행한다")
        state = _state(anchor=anchor, backup_questions=[poisoned_a, poisoned_b])
        result = _use_backup(state)
        outcome = result["outcome"]
        self.assertEqual(outcome.source, "exhausted")
        self.assertIsNone(outcome.question)
        self.assertEqual(outcome.backup_candidates_checked, 2)
        self.assertEqual(outcome.backup_candidates_rejected, 2)

    def test_rejected_candidates_are_never_added_to_used_backup_ids_by_caller_contract(self) -> None:
        """`_use_backup()` 자체는 `used_backup_question_ids`를 직접 건드리지 않는다 —
        호출자(main.py)가 반환된(수락된) question_id만 기록한다는 계약을 확인한다."""

        anchor = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("game", "story_exploration")]
        poisoned = _poisoned_backup("poisoned_01", "팀원과 함께 경기 순위를 다툰다")
        clean = _poisoned_backup("clean_02", "이 상황에서 무엇을 먼저 할지 생각한다")
        state = _state(anchor=anchor, backup_questions=[poisoned, clean], used_backup_question_ids=set())
        _use_backup(state)
        # State 자체의 used_backup_question_ids는 함수 호출로 변하지 않는다(순수 조회).
        self.assertEqual(state.used_backup_question_ids, set())

    def test_already_used_backup_is_skipped_without_being_checked(self) -> None:
        anchor = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("game", "story_exploration")]
        clean_1 = _poisoned_backup("clean_01", "정상 문장 1")
        clean_2 = _poisoned_backup("clean_02", "정상 문장 2")
        state = _state(
            anchor=anchor, backup_questions=[clean_1, clean_2], used_backup_question_ids={"clean_01"},
        )
        result = _use_backup(state)
        outcome = result["outcome"]
        self.assertEqual(outcome.question.question_id, "clean_02")
        self.assertEqual(outcome.backup_candidates_checked, 1)  # clean_01은 검사하지 않고 건너뜀

    def test_deterministic_across_repeated_calls_with_same_state(self) -> None:
        anchor = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("game", "story_exploration")]
        poisoned = _poisoned_backup("poisoned_01", "팀원과 함께 경기 순위를 다툰다")
        clean = _poisoned_backup("clean_02", "정상 문장")
        state = _state(anchor=anchor, backup_questions=[poisoned, clean])
        result1 = _use_backup(state)
        result2 = _use_backup(state)
        self.assertEqual(result1["outcome"].question.question_id, result2["outcome"].question.question_id)


class BackupQualityGateContentTest(unittest.TestCase):
    def test_forbidden_phrase_in_question_text_rejects_candidate(self) -> None:
        anchor = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("game", "story_exploration")]
        poisoned = _poisoned_backup("poisoned_q", "정상 옵션")
        poisoned = poisoned.model_copy(update={"question_text": "팀원과 함께 게임을 시작할 때 무엇을 하나요?"})
        state = _state(anchor=anchor, backup_questions=[poisoned])
        result = _use_backup(state)
        self.assertEqual(result["outcome"].source, "exhausted")

    def test_forbidden_phrase_in_option_text_rejects_candidate(self) -> None:
        anchor = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("game", "story_exploration")]
        poisoned = _poisoned_backup("poisoned_o", "경기 순위를 확인한다")
        state = _state(anchor=anchor, backup_questions=[poisoned])
        result = _use_backup(state)
        self.assertEqual(result["outcome"].source, "exhausted")

    def test_duplicate_of_previous_question_text_rejects_candidate(self) -> None:
        backup = _poisoned_backup("dup_q", "정상 옵션")
        state = QuestionGenerationGraphState(
            question_id="q1", context_definition=CONTEXT_DEFINITIONS_BY_ID["game"],
            trait_definition=_TRAIT_DEFS[_TRAIT_ID], all_trait_labels={_TRAIT_ID: "라벨"},
            option_blueprint_id=_BLUEPRINT_ID, frame_id="problem_check", frame_text="힌트",
            llm_client=None, anchor=None, backup_questions=[backup],
            previous_question_texts=["테스트 질문?"],
        )
        result = _use_backup(state)
        self.assertEqual(result["outcome"].source, "exhausted")

    def test_compatible_neutral_backup_passes(self) -> None:
        backup = _poisoned_backup("neutral_q", "정상 옵션")
        state = _state(anchor=None, backup_questions=[backup])
        result = _use_backup(state)
        self.assertEqual(result["outcome"].source, "backup")

    def test_no_anchor_uses_existing_neutral_policy(self) -> None:
        """Anchor가 없으면 forbidden_anchor_assumption_phrases가 빈 튜플이라 기존
        중립 정책과 동일하게 동작한다."""

        state = _state(anchor=None, backup_questions=VERTICAL_SLICE_BACKUP_QUESTIONS["game"])
        result = _use_backup(state)
        self.assertEqual(result["outcome"].source, "backup")
        self.assertEqual(result["outcome"].question.question_id, "game_backup_01")

    def test_gate_failure_reason_does_not_contain_question_or_option_text(self) -> None:
        from src.engines.backup_applicability_check import check_backup_candidate

        anchor = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[("game", "story_exploration")]
        poisoned = _poisoned_backup("poisoned_reason", "팀원과 경기 순위를 다툰다")
        gate = check_backup_candidate(poisoned, anchor=anchor, applicability=None)
        self.assertFalse(gate.passed)
        for failure in gate.failures:
            # 실패 사유는 "금지 표현: '팀원'" 형태로 짧은 phrase만 담고, 선택지 전체
            # 원문(예: "팀원과 경기 순위를 다툰다")을 통째로 담지 않는다.
            self.assertNotIn("팀원과 경기 순위를 다툰다", failure)


class ContextEarlyTerminationOnExhaustionTest(unittest.TestCase):
    """§14 회귀 — Backup 소진 시 Context 조기 종료가 Anchor가 있는 상태에서도 그대로
    유지되는지 API 레벨로 확인한다."""

    def test_all_backups_rejected_by_anchor_leads_to_early_termination(self) -> None:
        import os
        from unittest.mock import patch

        from fastapi.testclient import TestClient

        import src.api.main as main_module
        from src.api.main import app

        os.environ["ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES"] = "true"
        try:
            client = TestClient(app)
            r = client.post("/assessment/session")
            session_id = r.json()["session_id"]
            client.post(
                "/assessment/interest-rating",
                json={"session_id": session_id, "ratings": {c: 5 for c in ("game", "media", "school_life")}},
            )
            client.post(
                "/assessment/context-select",
                json={"session_id": session_id, "selected_preferred_context_ids": ["game", "media"]},
            )
            client.post(
                "/assessment/context-confirm",
                json={"session_id": session_id, "final_context_ids": ["game", "media", "school_life"]},
            )

            class AlwaysFailLLM:
                def complete_structured(self, *, system_prompt, user_prompt, response_model):
                    from src.llm.protocols import LLMCallError

                    raise LLMCallError("의도적 실패")

            with patch.object(main_module, "_llm_client", AlwaysFailLLM()), \
                 patch(
                     "src.api.main.VERTICAL_SLICE_BACKUP_QUESTIONS",
                     {"game": [], "media": [], "school_life": []},
                 ):
                found_early_termination = False
                for _ in range(30):
                    resp = client.post("/assessment/next-question", params={"session_id": session_id})
                    body = resp.json()
                    if body["status"] == "CONTEXT_EARLY_TERMINATED":
                        found_early_termination = True
                        break
                    question = body.get("question")
                    if question is None:
                        break
                    client.post(
                        "/assessment/answer",
                        json={
                            "session_id": session_id, "question_id": question["question_id"],
                            "selected_option_id": question["options"][0]["option_id"],
                        },
                    )
                self.assertTrue(found_early_termination)
        finally:
            os.environ.pop("ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", None)


if __name__ == "__main__":
    unittest.main()
