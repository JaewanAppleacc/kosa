"""ContextPack Adaptive Tail(Seed→최소 4·최대 6 질문→Career Profile) 실제 흐름 E2E —
2026-08-23 Trait Ontology v2(2.9단계) §4/§7/§8/§9/§10/§13.

실제 T·S·L Pack 파일이나 공유 검수 디렉터리를 전혀 건드리지 않는다 — `main.py`의
`_context_pack_registry`/`_context_pack_runtime` 전역을 테스트 전용 값으로 주입한다
(2.8단계 `test_context_pack_synthetic_e2e.py`와 같은 패턴). LLM은 `tests/
test_v2_direct_probe.py`의 `_SmartFakeLLMClient`와 같은 원리의 Fake Client로 대체하되,
실제 `v2_direct_probe_generator.py`/Question Quality Gate/LangGraph 답변 경로를 그대로
통과시킨다 — Trait Summary를 직접 주입하지 않는다."""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.api.main as main_module
from src.api.main import app
from src.data.context_packs._example_pack_builder import build_example_context_pack
from src.data.contexts.context_definitions import VERTICAL_SLICE_CONTEXT_IDS
from src.data.questions.context_pack_shared_probe_blueprints import CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS
from src.llm.protocols import LLMCallError
from src.schemas.question import GeneratedOption, GeneratedQuestion, QuestionGenerationResult
from src.services.context_pack_registry import ContextPackRegistry
from src.services.context_pack_runtime import ContextPackRuntime
from src.tracing.tracer import Tracer

client = TestClient(app)

_CONTEXT_RE = re.compile(r'context 필드에는 "(\w+)"를')
_FRAME_RE = re.compile(r'frame_id 필드에는 "(\w+)"를')
_ROLE_RE = re.compile(r"\[Option Role.*?\]\n(.*?)\n\ncontext 필드", re.DOTALL)


class _FakeLLMClient:
    """2.1단계 `_SmartFakeLLMClient`와 같은 방식으로 Prompt에서 실제 role_id·context·
    frame_id를 파싱해 그대로 되돌려준다 — 어떤 role_id가 오든 항상 유효한 5개 선택지를
    만들어 실제 Quality Gate를 통과시킨다."""

    def __init__(self, mode: str = "success") -> None:
        self.mode = mode
        self.call_count = 0

    def complete_structured(self, *, system_prompt, user_prompt, response_model):
        self.call_count += 1
        if self.mode == "always_fail":
            raise LLMCallError("모의 LLM 네트워크 실패")
        context = _CONTEXT_RE.search(user_prompt).group(1)
        frame_id = _FRAME_RE.search(user_prompt).group(1)
        role_block = _ROLE_RE.search(user_prompt).group(1)
        role_ids = [line.removeprefix("- ").strip().split(" ")[0] for line in role_block.strip().splitlines()]
        return QuestionGenerationResult(
            question=GeneratedQuestion(
                context=context, target_traits=[], frame_id=frame_id,
                question_text="지금 상황에서 무엇을 가장 먼저 하나요?",
                options=[GeneratedOption(role_id=r, text=f"{r} 선택지 문장") for r in role_ids],
            )
        )


class _PackAdaptiveTestBase(unittest.TestCase):
    """모든 하위 테스트가 공유하는 합성 Pack + 승인된 공용 Adaptive Probe Pool 준비."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.review_dir = Path(self.tmpdir.name)

        self.pack = build_example_context_pack("business")
        self.test_registry = ContextPackRegistry(
            known_context_ids=frozenset({"business"}),
            known_trait_ids=frozenset({"causal_analysis", "pattern_finding"}),
            review_status_dir=self.review_dir,
            shared_probe_review_status_path=self.review_dir / "shared.json",
            _discovered=({"business": self.pack}, {}),
        )
        required_keys = sorted(self.test_registry.required_review_keys(self.pack))
        (self.review_dir / "business_review_status.json").write_text(
            json.dumps([{"blueprint_id": k, "reviewer_1_status": "APPROVE"} for k in required_keys], ensure_ascii=False),
            encoding="utf-8",
        )
        self._approve_shared_probes(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS)
        self.test_runtime = ContextPackRuntime(
            self.test_registry, lambda: main_module.context_pack_runtime_enabled(), frozenset(VERTICAL_SLICE_CONTEXT_IDS),
        )
        self.fake_llm = _FakeLLMClient()
        for patch_target in (
            patch.object(main_module, "_context_pack_registry", self.test_registry),
            patch.object(main_module, "_context_pack_runtime", self.test_runtime),
            patch.object(main_module, "_llm_client", self.fake_llm),
            patch.object(main_module, "_tracer", Tracer(client=None)),
        ):
            patch_target.start()
            self.addCleanup(patch_target.stop)
        import os

        os.environ["ENABLE_CONTEXT_PACK_RUNTIME"] = "true"
        self.addCleanup(os.environ.pop, "ENABLE_CONTEXT_PACK_RUNTIME", None)

    def _approve_shared_probes(
        self, blueprints, *, context_id: str = "business", anchor_ids: list[str] | None = None,
    ) -> None:
        """2026-08-23 2.9.1단계 §3 — Context+Anchor 단위 승인. 기본값은 이 합성 Pack의
        Anchor 5개 전부를 승인한 것으로 취급한다(대부분의 테스트가 "충분히 승인된
        상태"를 원하므로) — Anchor 격리를 직접 검증하는 테스트는 `anchor_ids`를 좁혀
        넘긴다."""

        resolved_anchor_ids = anchor_ids if anchor_ids is not None else [a.anchor_id for a in self.pack.anchor_presentations]
        entries = [
            {
                "blueprint_id": bp.blueprint_id, "context_id": context_id, "reviewer_1_status": "APPROVE",
                "approved_anchor_ids": resolved_anchor_ids, "excluded_anchor_ids": [],
            }
            for bp in blueprints
        ]
        (self.review_dir / "shared.json").write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")

    def _confirmed_session(self, final=("business", "game")) -> str:
        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 4, "business": 5}},
        )
        client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "business"]},
        )
        client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": list(final)},
        )
        return session_id

    def _answer_routing_and_seed(self, session_id: str) -> str:
        """Routing 답변(Anchor 0번 선택) + Seed 답변까지 진행하고 Anchor id를 반환한다."""

        r = client.post("/assessment/next-question", params={"session_id": session_id})
        routing_q = r.json()["question"]
        client.post(
            "/assessment/answer",
            json={"session_id": session_id, "question_id": routing_q["question_id"], "selected_option_id": routing_q["options"][0]["option_id"]},
        )
        state = main_module._store.load(session_id)
        anchor_id = state.context_anchor_choices["business"]

        r = client.post("/assessment/next-question", params={"session_id": session_id})
        seed_q = r.json()["question"]
        client.post(
            "/assessment/answer",
            json={"session_id": session_id, "question_id": seed_q["question_id"], "selected_option_id": seed_q["options"][0]["option_id"]},
        )
        return anchor_id

    def _drive_business_context(self, session_id: str, max_turns: int = 10) -> list[str]:
        """business Context가 끝날 때까지(다음 Context로 넘어가거나 세션이 끝날 때까지)
        옵션[0]을 계속 고르며 진행하고, 실제로 서빙된 question_family_id 목록을 반환한다."""

        families: list[str] = []
        for _ in range(max_turns):
            r = client.post("/assessment/next-question", params={"session_id": session_id})
            body = r.json()
            if body["status"] == "CONTEXT_EARLY_TERMINATED":
                state = main_module._store.load(session_id)
                if state.current_context_id != "business":
                    break
                continue
            question = body["question"]
            state = main_module._store.load(session_id)
            families.append(state.current_question_family_id)
            option = question["options"][0]
            client.post(
                "/assessment/answer",
                json={"session_id": session_id, "question_id": question["question_id"], "selected_option_id": option["option_id"]},
            )
            state_after = main_module._store.load(session_id)
            if state_after.current_context_id != "business":
                break
        return families


class AdaptiveTailMinMaxTest(_PackAdaptiveTestBase):
    def test_at_least_four_and_at_most_six_tail_questions_after_seed(self) -> None:
        session_id = self._confirmed_session()
        self._answer_routing_and_seed(session_id)
        families = self._drive_business_context(session_id)
        tail_families = [f for f in families if f == "pack_direct_probe"]
        self.assertGreaterEqual(len(tail_families), 4)
        self.assertLessEqual(len(tail_families), 6)

    def test_routing_not_counted_as_trait_question(self) -> None:
        session_id = self._confirmed_session()
        anchor_id = self._answer_routing_and_seed(session_id)
        self.assertIsNotNone(anchor_id)
        state = main_module._store.load(session_id)
        # Seed까지만 진행한 시점 — questions_asked_in_current_context는 Seed 1개만 세야
        # 하고 Routing은 포함되면 안 된다.
        self.assertEqual(state.questions_asked_in_current_context, 1)
        self.assertEqual(len(state.routing_answer_history), 1)

    def test_backup_never_used_on_normal_llm_path_with_plentiful_candidates(self) -> None:
        session_id = self._confirmed_session()
        self._answer_routing_and_seed(session_id)
        families = self._drive_business_context(session_id)
        self.assertNotIn("pack_backup", families)

    def test_all_tail_evidence_uses_exact_blueprint_mapping(self) -> None:
        session_id = self._confirmed_session()
        self._answer_routing_and_seed(session_id)
        self._drive_business_context(session_id)
        state = main_module._store.load(session_id)
        tail_evidence = [e for e in state.evidence_ledger if e.context == "business" and e.source_question_family_id == "pack_direct_probe"]
        self.assertTrue(tail_evidence)
        for e in tail_evidence:
            self.assertEqual(e.trait_signal_mapping_source_v2, "EXACT_BLUEPRINT")

    def test_no_blueprint_reused_within_same_context(self) -> None:
        session_id = self._confirmed_session()
        self._answer_routing_and_seed(session_id)
        self._drive_business_context(session_id)
        state = main_module._store.load(session_id)
        tail_blueprint_ids = [
            e.source_blueprint_id for e in state.evidence_ledger
            if e.context == "business" and e.source_question_family_id == "pack_direct_probe"
        ]
        self.assertEqual(len(tail_blueprint_ids), len(set(tail_blueprint_ids)))


class BackupOnlyOnExhaustionTest(_PackAdaptiveTestBase):
    def setUp(self) -> None:
        super().setUp()
        # 후보 Trait 2개짜리(최소 4개 미달)로 인위적으로 제한 — Backup이 "실패 대체"로
        # 쓰이는 경로를 재현한다.
        limited_pool = CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS[:2]
        self._approve_shared_probes(limited_pool)
        self.test_registry = ContextPackRegistry(
            known_context_ids=frozenset({"business"}),
            known_trait_ids=frozenset({"causal_analysis", "pattern_finding"}),
            review_status_dir=self.review_dir,
            shared_probe_review_status_path=self.review_dir / "shared.json",
            shared_probe_pool=limited_pool,
            _discovered=({"business": self.pack}, {}),
        )
        self.test_runtime = ContextPackRuntime(
            self.test_registry, lambda: main_module.context_pack_runtime_enabled(), frozenset(VERTICAL_SLICE_CONTEXT_IDS),
        )
        patch.object(main_module, "_context_pack_registry", self.test_registry).start()
        patch.object(main_module, "_context_pack_runtime", self.test_runtime).start()
        self.addCleanup(patch.stopall)

    def test_backup_used_as_substitute_when_candidates_exhausted_before_minimum(self) -> None:
        session_id = self._confirmed_session()
        self._answer_routing_and_seed(session_id)
        families = self._drive_business_context(session_id)
        # 후보 2개뿐이라 최소 4개(Seed 제외 Adaptive Tail)를 채우려면 Backup이 최소
        # 한 번은 "실패 대체"로 쓰여야 한다.
        self.assertIn("pack_backup", families)

    def test_backup_question_never_reused(self) -> None:
        session_id = self._confirmed_session()
        self._answer_routing_and_seed(session_id)
        self._drive_business_context(session_id)
        state = main_module._store.load(session_id)
        self.assertEqual(len(state.used_backup_question_ids), len(set(state.used_backup_question_ids)))


class CandidateAndBackupExhaustedTest(_PackAdaptiveTestBase):
    """§4 "Backup까지 사용할 수 없으면 기존 조기 종료 정책을 따른다" — 후보도 0개,
    Backup도 이미 소진된 극단 상황에서 예외 없이 정상적으로 Context를 종료하는지
    확인한다."""

    def setUp(self) -> None:
        super().setUp()
        self._approve_shared_probes([])  # 공용 Adaptive Probe 후보를 0개로 만든다.
        self.test_registry = ContextPackRegistry(
            known_context_ids=frozenset({"business"}),
            known_trait_ids=frozenset({"causal_analysis", "pattern_finding"}),
            review_status_dir=self.review_dir,
            shared_probe_review_status_path=self.review_dir / "shared.json",
            shared_probe_pool=[],
            _discovered=({"business": self.pack}, {}),
        )
        self.test_runtime = ContextPackRuntime(
            self.test_registry, lambda: main_module.context_pack_runtime_enabled(), frozenset(VERTICAL_SLICE_CONTEXT_IDS),
        )
        patch.object(main_module, "_context_pack_registry", self.test_registry).start()
        patch.object(main_module, "_context_pack_runtime", self.test_runtime).start()
        self.addCleanup(patch.stopall)

    def test_ends_context_cleanly_when_no_candidates_and_backup_used_up(self) -> None:
        session_id = self._confirmed_session()
        self._answer_routing_and_seed(session_id)
        # 유일한 Anchor Backup 하나를 먼저 소진시킨다.
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        body = r.json()
        self.assertEqual(body["status"], "BACKUP_USED")
        backup_q = body["question"]
        client.post(
            "/assessment/answer",
            json={"session_id": session_id, "question_id": backup_q["question_id"], "selected_option_id": backup_q["options"][0]["option_id"]},
        )
        # 후보도 없고 Backup도 소진 — 예외 없이 조기 종료해야 한다(다음 Context인 game으로).
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        body = r.json()
        self.assertEqual(body["status"], "CONTEXT_EARLY_TERMINATED")
        state = main_module._store.load(session_id)
        self.assertIn("STOP_CANDIDATE_EXHAUSTED", state.stop_reason or "")


class AnchorIsolationInAdaptiveFlowTest(_PackAdaptiveTestBase):
    def test_different_anchor_choice_gets_its_own_seed_and_backup(self) -> None:
        session_a = self._confirmed_session()
        r = client.post("/assessment/next-question", params={"session_id": session_a})
        routing_q = r.json()["question"]
        # 항상 옵션[0]이 아니라, 두 번째 Anchor를 강제로 골라 비교한다.
        client.post(
            "/assessment/answer",
            json={"session_id": session_a, "question_id": routing_q["question_id"], "selected_option_id": routing_q["options"][1]["option_id"]},
        )
        state_a = main_module._store.load(session_a)
        anchor_a = state_a.context_anchor_choices["business"]

        session_b = self._confirmed_session()
        r = client.post("/assessment/next-question", params={"session_id": session_b})
        routing_q_b = r.json()["question"]
        client.post(
            "/assessment/answer",
            json={"session_id": session_b, "question_id": routing_q_b["question_id"], "selected_option_id": routing_q_b["options"][0]["option_id"]},
        )
        state_b = main_module._store.load(session_b)
        anchor_b = state_b.context_anchor_choices["business"]

        self.assertNotEqual(anchor_a, anchor_b)

        seed_a = client.post("/assessment/next-question", params={"session_id": session_a}).json()["question"]
        seed_b = client.post("/assessment/next-question", params={"session_id": session_b}).json()["question"]
        self.assertEqual(seed_a["question_id"], f"business_seed_{anchor_a}")
        self.assertEqual(seed_b["question_id"], f"business_seed_{anchor_b}")
        self.assertNotEqual(seed_a["question_id"], seed_b["question_id"])


class IdempotentReplayTest(_PackAdaptiveTestBase):
    def test_repeated_next_question_call_does_not_advance_counter(self) -> None:
        session_id = self._confirmed_session()
        self._answer_routing_and_seed(session_id)
        first = client.post("/assessment/next-question", params={"session_id": session_id}).json()
        state_after_first = main_module._store.load(session_id)
        second = client.post("/assessment/next-question", params={"session_id": session_id}).json()
        state_after_second = main_module._store.load(session_id)
        self.assertEqual(first["question"]["question_id"], second["question"]["question_id"])
        self.assertEqual(
            state_after_first.questions_asked_in_current_context, state_after_second.questions_asked_in_current_context,
        )

    def test_counter_only_increments_after_successful_answer(self) -> None:
        session_id = self._confirmed_session()
        self._answer_routing_and_seed(session_id)
        before = main_module._store.load(session_id).questions_asked_in_current_context
        client.post("/assessment/next-question", params={"session_id": session_id})
        after_serve = main_module._store.load(session_id).questions_asked_in_current_context
        self.assertEqual(before, after_serve)  # 서빙만으로는 증가하지 않는다.


class FlagOffRegressionForAdaptiveTest(_PackAdaptiveTestBase):
    def test_flag_off_business_never_appears_in_contexts(self) -> None:
        import os

        os.environ.pop("ENABLE_CONTEXT_PACK_RUNTIME", None)
        r = client.get("/contexts")
        supported = {c["context_id"] for c in r.json()["contexts"] if c["assessment_supported"]}
        self.assertNotIn("business", supported)
        os.environ["ENABLE_CONTEXT_PACK_RUNTIME"] = "true"  # tearDown이 다시 pop한다.


class ApiConsistencyTest(_PackAdaptiveTestBase):
    def test_contexts_select_confirm_all_agree_on_business_support(self) -> None:
        r = client.get("/contexts")
        catalog = {c["context_id"]: c["assessment_supported"] for c in r.json()["contexts"]}
        self.assertTrue(catalog["business"])

        session_id = self._confirmed_session()  # 이미 select/confirm에서 business가 통과했다.
        state = main_module._store.load(session_id)
        self.assertIn("business", state.final_contexts)

    def test_unsupported_context_rejected_with_422_at_select(self) -> None:
        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 4, "cooking": 3}},
        )
        r = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "cooking"]},
        )
        self.assertEqual(r.status_code, 422)


class ForbiddenAssumptionRegenerationTest(unittest.TestCase):
    """§9/§13 "forbidden-assumption 위반 시 재생성" — Pack Adaptive Tail이 실제로 쓰는
    `generate_v2_direct_probe_question()`(Legacy V2 Direct Probe와 동일 함수, 2.5.1단계
    §6에서 이미 Anchor forbidden_assumptions 검사를 구현)을 공용 Adaptive Probe
    Blueprint 하나로 직접 호출해 재생성이 실제로 일어나는지 확인한다."""

    def test_first_attempt_violating_forbidden_phrase_triggers_regeneration(self) -> None:
        from src.agents.assessment.v2_direct_probe_generator import generate_v2_direct_probe_question
        from src.data.contexts.context_definitions import CONTEXT_DEFINITIONS
        from src.schemas.context_anchor_presentation import ContextAnchorPresentation

        blueprint = CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS[0]
        anchor = ContextAnchorPresentation(
            context_id="business", anchor_id="zz_forbidden_test_anchor", label="테스트 상황",
            situation_terms=["예제"], preferred_scenarios=["예제 상황"],
            forbidden_assumptions=["팀원과 함께"],
        )
        role_ids = [m.role_id for m in blueprint.option_mappings]

        class _RegeneratingFakeLLM:
            def __init__(self) -> None:
                self.call_count = 0

            def complete_structured(self, *, system_prompt, user_prompt, response_model):
                self.call_count += 1
                text = "팀원과 함께 상의해서 정한다" if self.call_count == 1 else "혼자 판단해서 진행한다"
                return QuestionGenerationResult(
                    question=GeneratedQuestion(
                        context="business", target_traits=[], frame_id=blueprint.question_frame_id,
                        question_text=text,
                        options=[GeneratedOption(role_id=r, text=f"{r} 선택지") for r in role_ids],
                    )
                )

        fake_llm = _RegeneratingFakeLLM()
        outcome = generate_v2_direct_probe_question(
            question_id="zz_forbidden_test_q", context_definition=next(c for c in CONTEXT_DEFINITIONS if c.context_id == "business"),
            blueprint=blueprint, llm_client=fake_llm, anchor=anchor,
        )
        self.assertEqual(fake_llm.call_count, 2)  # 1차 실패 → 재생성 1회 성공.
        self.assertEqual(outcome.source, "llm")
        self.assertNotIn("팀원과 함께", outcome.question.question_text)


if __name__ == "__main__":
    unittest.main()
