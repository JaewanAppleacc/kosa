"""EvidenceRecord v2 Signal 통합 테스트 — 1단계 지시서 §15 "Evidence" + 1.5단계 §14
"Signal 전달" (answer_graph 실제 배선).

Mock Trait Summary를 직접 주입하지 않고 실제 /assessment 흐름으로 확인한다.
"""

from __future__ import annotations

import re
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.api.main as main_module
from src.api.main import app
from src.llm.protocols import LLMCallError
from src.schemas.evidence import EvidenceOrigin
from src.schemas.question import GeneratedOption, GeneratedQuestion, QuestionGenerationResult

client = TestClient(app)

_CONTEXT_RE = re.compile(r'context 필드에는 "(\w+)"를')
_FRAME_RE = re.compile(r'frame_id 필드에는 "(\w+)"를')
_ROLE_RE = re.compile(r"- (\w+) \(측정 대상")


class _SmartFakeLLMClient:
    """실제 user_prompt에서 이번 호출이 요구하는 Context·Frame·Role 목록을 그대로
    읽어내 항상 그 Blueprint에 맞는 유효한 GeneratedQuestion을 만든다 — 어떤 Blueprint를
    Planner가 고를지 테스트가 미리 알 필요가 없다. `mode`로 실패 시나리오를 재현한다:
    "success"(항상 성공), "always_fail"(항상 LLMCallError), "quality_gate_fail"(항상
    금지 표현이 든 문장 반환 — Quality Gate에서 거부됨)."""

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.call_count = 0

    def complete_structured(self, *, system_prompt, user_prompt, response_model):
        self.call_count += 1
        if self.mode == "always_fail":
            raise LLMCallError("모의 LLM 네트워크 실패")
        context = _CONTEXT_RE.search(user_prompt).group(1)
        frame_id = _FRAME_RE.search(user_prompt).group(1)
        role_ids = _ROLE_RE.findall(user_prompt)[:5]
        question_text = (
            "이 활동을 잘하는 편인가?" if self.mode == "quality_gate_fail"
            else "지금 상황에서 무엇을 가장 먼저 하나요?"
        )
        return QuestionGenerationResult(
            question=GeneratedQuestion(
                context=context, target_traits=["causal_analysis"], frame_id=frame_id,
                question_text=question_text,
                options=[GeneratedOption(role_id=r, text=f"{r} 선택지 문장") for r in role_ids],
            )
        )


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
            for forbidden in (
                "trait_signal", "signal_role", "related_concept_ids", "primary_signal_sum",
                "mapping_source", "EXACT_BLUEPRINT", "LEGACY_PRIMARY_ADAPTER",
            ):
                self.assertNotIn(forbidden, body_text, f"{path} leaked {forbidden!r}")

    def test_conflict_resolution_answers_never_get_v2_signals(self) -> None:
        """resolve_trait_signals()가 is_resolution_question=True면 항상 빈 목록을
        반환하는 방어적 분기가 실제로 배선돼 있는지 회귀 확인 — 1.5단계부터는 등록 안 된
        role_id도 Legacy Adapter로 빈 목록을 피해가므로, Conflict Resolution 자체가 빈
        목록으로 남는 유일한 정상 경로다."""

        session_id = self._new_session_answer_seed()
        state = main_module._store.load(session_id)
        for evidence in state.evidence_ledger:
            if evidence.evidence_origin == EvidenceOrigin.CONFLICT_RESOLUTION:
                self.assertEqual(evidence.applied_trait_signals_v2, [])
                self.assertEqual(evidence.trait_signal_mapping_source_v2, "NONE_CONFLICT_RESOLUTION")

    def test_no_normal_question_ever_has_empty_v2_signal_list(self) -> None:
        """1.5단계 §2/§4 완료 조건: 정상 질문(Conflict Resolution이 아닌 질문)은 절대
        applied_trait_signals_v2=[]로 끝나지 않는다."""

        session_id = self._new_session_answer_seed()
        state = main_module._store.load(session_id)
        for evidence in state.evidence_ledger:
            if evidence.evidence_origin != EvidenceOrigin.CONFLICT_RESOLUTION:
                self.assertTrue(evidence.applied_trait_signals_v2, evidence.question_id)
                self.assertIn(
                    evidence.trait_signal_mapping_source_v2, ("EXACT_BLUEPRINT", "LEGACY_PRIMARY_ADAPTER")
                )


def _drive_full_session(scripted_llm_client, contexts=("game", "media", "school_life")):
    """세션 하나를 끝까지(ASSESSMENT_COMPLETE) 진행하고 session_id를 반환한다."""

    r = client.post("/assessment/session")
    session_id = r.json()["session_id"]
    client.post(
        "/assessment/interest-rating",
        json={"session_id": session_id, "ratings": {c: 5 for c in contexts}},
    )
    client.post(
        "/assessment/context-select",
        json={"session_id": session_id, "selected_preferred_context_ids": list(contexts[:2])},
    )
    client.post(
        "/assessment/context-confirm",
        json={"session_id": session_id, "final_context_ids": list(contexts)},
    )
    for _ in range(60):
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        body = r.json()
        if body["status"] == "CONTEXT_EARLY_TERMINATED":
            if body["assessment_complete"]:
                break
            continue
        question = body["question"]
        option = question["options"][0]
        ar = client.post(
            "/assessment/answer",
            json={
                "session_id": session_id, "question_id": question["question_id"],
                "selected_option_id": option["option_id"],
            },
        )
        if ar.json()["next_action"] == "ASSESSMENT_COMPLETE":
            break
    return session_id


class LLMOffFullSessionCoverageTest(unittest.TestCase):
    """1.5단계 §4 시나리오 1(LLM 완전 비활성화) + §14 A: LLM-off 완주 세션의 모든
    일반 질문에 v2 PRIMARY Signal이 기록돼야 한다는 완료 조건을 실제 API 흐름으로 확인."""

    def setUp(self) -> None:
        patcher = patch.object(main_module, "_llm_client", None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_every_general_answer_has_primary_signal_and_seed_uses_exact_blueprint(self) -> None:
        session_id = _drive_full_session(None)
        state = main_module._store.load(session_id)
        general = [e for e in state.evidence_ledger if e.evidence_origin != EvidenceOrigin.CONFLICT_RESOLUTION]
        self.assertTrue(general)
        for evidence in general:
            primary = [s for s in evidence.applied_trait_signals_v2 if s.signal_role == "PRIMARY"]
            self.assertGreaterEqual(len(primary), 1, evidence.question_id)

        seed_records = [e for e in general if e.question_frame_id == "seed_frame"]
        self.assertTrue(seed_records)
        for evidence in seed_records:
            self.assertEqual(evidence.trait_signal_mapping_source_v2, "EXACT_BLUEPRINT")

        # LLM-off Mock 꼬리질문은 Registry에 등록될 수 없는 자리표시자 role_id이므로
        # 항상 LEGACY_PRIMARY_ADAPTER여야 한다(§1 감사에서 확인한 원래 설계).
        mock_tail_records = [e for e in general if e.question_frame_id != "seed_frame"]
        self.assertTrue(mock_tail_records)
        for evidence in mock_tail_records:
            self.assertEqual(evidence.trait_signal_mapping_source_v2, "LEGACY_PRIMARY_ADAPTER")


class LLMOnSignalMappingTest(unittest.TestCase):
    """1.5단계 §4 시나리오 2/3/4/5: LLM 성공·재생성 성공·전체 실패 후 Backup·Quality Gate
    실패 후 Backup 각각에서 v2 Signal이 기록되는지 확인. 실제 네트워크 호출 없이 FakeLLM만
    쓴다."""

    def _answer_seed_then_get_tail(self, fake_client) -> tuple[str, dict]:
        patcher = patch.object(main_module, "_llm_client", fake_client)
        patcher.start()
        self.addCleanup(patcher.stop)

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
        seed_question = r.json()["question"]
        r = client.post(
            "/assessment/answer",
            json={
                "session_id": session_id, "question_id": seed_question["question_id"],
                "selected_option_id": seed_question["options"][0]["option_id"],
            },
        )
        self.assertEqual(r.json()["next_action"], "NEXT_QUESTION")
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        return session_id, r.json()

    def _answer_current_question(self, session_id: str, question: dict) -> None:
        r = client.post(
            "/assessment/answer",
            json={
                "session_id": session_id, "question_id": question["question_id"],
                "selected_option_id": question["options"][0]["option_id"],
            },
        )
        self.assertEqual(r.status_code, 200, r.text)

    def test_llm_success_gets_exact_blueprint_primary_signal(self) -> None:
        session_id, body = self._answer_seed_then_get_tail(_SmartFakeLLMClient("success"))
        self.assertEqual(body["status"], "GENERATED")
        self._answer_current_question(session_id, body["question"])
        state = main_module._store.load(session_id)
        evidence = state.evidence_ledger[-1]
        self.assertEqual(evidence.trait_signal_mapping_source_v2, "EXACT_BLUEPRINT")
        self.assertTrue(any(s.signal_role == "PRIMARY" for s in evidence.applied_trait_signals_v2))

    def test_llm_regeneration_success_still_gets_exact_blueprint(self) -> None:
        """첫 시도는 Quality Gate 실패, 재생성은 성공 — 재생성된 질문도 EXACT_BLUEPRINT여야
        한다(재생성 과정에서 내부 Blueprint id가 보존되는지 확인)."""

        class _RegenerateOnceClient(_SmartFakeLLMClient):
            def __init__(self) -> None:
                super().__init__("success")
                self._first = True

            def complete_structured(self, *, system_prompt, user_prompt, response_model):
                if self._first:
                    self._first = False
                    original_mode = self.mode
                    self.mode = "quality_gate_fail"
                    try:
                        return super().complete_structured(
                            system_prompt=system_prompt, user_prompt=user_prompt, response_model=response_model
                        )
                    finally:
                        self.mode = original_mode
                return super().complete_structured(
                    system_prompt=system_prompt, user_prompt=user_prompt, response_model=response_model
                )

        session_id, body = self._answer_seed_then_get_tail(_RegenerateOnceClient())
        self.assertEqual(body["status"], "GENERATED")
        self._answer_current_question(session_id, body["question"])
        state = main_module._store.load(session_id)
        evidence = state.evidence_ledger[-1]
        self.assertEqual(evidence.trait_signal_mapping_source_v2, "EXACT_BLUEPRINT")

    def test_llm_always_fails_falls_back_to_backup_with_exact_blueprint_signal(self) -> None:
        """1.5단계 §2/§4 핵심 수정: 1단계는 Backup Question이 Registry에 전혀 등록돼
        있지 않아 이 경로에서 v2 Signal이 전부 비었다. 지금은 Backup도 등록돼 있어야
        EXACT_BLUEPRINT가 나온다."""

        session_id, body = self._answer_seed_then_get_tail(_SmartFakeLLMClient("always_fail"))
        self.assertEqual(body["status"], "BACKUP_USED")
        self._answer_current_question(session_id, body["question"])
        state = main_module._store.load(session_id)
        evidence = state.evidence_ledger[-1]
        self.assertEqual(evidence.trait_signal_mapping_source_v2, "EXACT_BLUEPRINT")
        self.assertTrue(any(s.signal_role == "PRIMARY" for s in evidence.applied_trait_signals_v2))

    def test_quality_gate_always_fails_falls_back_to_backup_with_exact_blueprint_signal(self) -> None:
        session_id, body = self._answer_seed_then_get_tail(_SmartFakeLLMClient("quality_gate_fail"))
        self.assertEqual(body["status"], "BACKUP_USED")
        self._answer_current_question(session_id, body["question"])
        state = main_module._store.load(session_id)
        evidence = state.evidence_ledger[-1]
        self.assertEqual(evidence.trait_signal_mapping_source_v2, "EXACT_BLUEPRINT")

    def test_legacy_evidence_fields_unchanged_regardless_of_mapping_source(self) -> None:
        """v2 Signal 배선이 기존 legacy 계산(applied_primary_trait_delta·evidence_origin
        등)에 어떤 영향도 주지 않는지 회귀 확인."""

        session_id, body = self._answer_seed_then_get_tail(_SmartFakeLLMClient("always_fail"))
        self._answer_current_question(session_id, body["question"])
        state = main_module._store.load(session_id)
        evidence = state.evidence_ledger[-1]
        self.assertTrue(evidence.applied_primary_trait_delta)
        self.assertEqual(evidence.evidence_origin, EvidenceOrigin.PRIMARY_BLUEPRINT)


if __name__ == "__main__":
    unittest.main()
