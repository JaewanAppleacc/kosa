"""V2 Direct Probe 통합 테스트 — 2026-08-24 Trait Ontology v2(2단계) §21.

Feature Flag OFF/ON 회귀, Evidence 분리, Question Bank 구조, Snapshot 판정을 실제
`/assessment` API 흐름으로 확인한다. 네트워크 호출 없음(LLM off로 고정, LLM ON 시나리오는
FakeLLM으로 결정론적으로 재현한다).
"""

from __future__ import annotations

import os
import re
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.api.main as main_module
from src.api.main import app
from src.data.questions.trait_v2_direct_probe_blueprints import (
    V2_DIRECT_PROBE_BLUEPRINTS,
    V2_DIRECT_PROBE_BLUEPRINTS_BY_TRAIT,
    V2_DIRECT_PROBE_TARGET_TRAIT_IDS,
)
from src.engines.v2_direct_probe_selector import select_blueprint_for_trait, select_v2_probe_candidates
from src.llm.protocols import LLMCallError
from src.schemas.evidence import EvidenceOrigin
from src.schemas.question import GeneratedOption, GeneratedQuestion, QuestionGenerationResult
from src.services.feature_flags import MAX_V2_DIRECT_PROBE_QUESTIONS, trait_vector_v2_direct_probes_enabled

client = TestClient(app)

_CONTEXT_RE = re.compile(r'context 필드에는 "(\w+)"를')
_FRAME_RE = re.compile(r'frame_id 필드에는 "(\w+)"를')
_ROLE_RE = re.compile(r"\[Option Role.*?\]\n(.*?)\n\ncontext 필드", re.DOTALL)


class _SmartFakeLLMClient:
    """V2 Direct Probe user_prompt에서 실제로 요구하는 Context·Frame·Role 목록을 읽어
    항상 그 Blueprint에 맞는 유효한 GeneratedQuestion을 만든다."""

    def __init__(self, mode: str) -> None:
        self.mode = mode  # "success" | "always_fail" | "quality_gate_fail"
        self.call_count = 0

    def complete_structured(self, *, system_prompt, user_prompt, response_model):
        self.call_count += 1
        if self.mode == "always_fail":
            raise LLMCallError("모의 LLM 네트워크 실패")
        context = _CONTEXT_RE.search(user_prompt).group(1)
        frame_id = _FRAME_RE.search(user_prompt).group(1)
        role_block = _ROLE_RE.search(user_prompt).group(1)
        role_ids = [line.removeprefix("- ").strip() for line in role_block.strip().splitlines()]
        question_text = (
            "이 활동을 잘하는 편인가?" if self.mode == "quality_gate_fail"
            else "지금 상황에서 무엇을 가장 먼저 하나요?"
        )
        return QuestionGenerationResult(
            question=GeneratedQuestion(
                context=context, target_traits=[], frame_id=frame_id, question_text=question_text,
                options=[GeneratedOption(role_id=r, text=f"{r} 선택지 문장") for r in role_ids],
            )
        )


def _drive_full_session(final_contexts=("game", "media", "school_life"), option_index=0) -> str:
    r = client.post("/assessment/session")
    session_id = r.json()["session_id"]
    client.post(
        "/assessment/interest-rating",
        json={"session_id": session_id, "ratings": {c: 5 for c in final_contexts}},
    )
    client.post(
        "/assessment/context-select",
        json={"session_id": session_id, "selected_preferred_context_ids": list(final_contexts[:2])},
    )
    client.post(
        "/assessment/context-confirm",
        json={"session_id": session_id, "final_context_ids": list(final_contexts)},
    )
    for _ in range(60):
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        body = r.json()
        if body["status"] == "CONTEXT_EARLY_TERMINATED":
            if body["assessment_complete"]:
                break
            continue
        question = body["question"]
        option = question["options"][option_index]
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


class FeatureFlagLoaderTest(unittest.TestCase):
    def test_unset_is_disabled(self) -> None:
        self.assertFalse(trait_vector_v2_direct_probes_enabled(env={}))

    def test_true_variants_enable(self) -> None:
        for value in ("1", "true", "True", "yes"):
            self.assertTrue(trait_vector_v2_direct_probes_enabled(env={"ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES": value}))

    def test_false_or_garbage_disables(self) -> None:
        for value in ("0", "false", "", "nope"):
            self.assertFalse(trait_vector_v2_direct_probes_enabled(env={"ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES": value}))


class QuestionBankStructureTest(unittest.TestCase):
    def test_exactly_14_blueprints_7_traits_times_2(self) -> None:
        self.assertEqual(len(V2_DIRECT_PROBE_BLUEPRINTS), 14)
        self.assertEqual(len(V2_DIRECT_PROBE_TARGET_TRAIT_IDS), 7)
        for trait_id, blueprints in V2_DIRECT_PROBE_BLUEPRINTS_BY_TRAIT.items():
            with self.subTest(trait_id=trait_id):
                self.assertEqual(len(blueprints), 2)

    def test_each_trait_pair_has_distinct_frames(self) -> None:
        for trait_id, blueprints in V2_DIRECT_PROBE_BLUEPRINTS_BY_TRAIT.items():
            with self.subTest(trait_id=trait_id):
                frames = {b.question_frame_id for b in blueprints}
                self.assertEqual(len(frames), 2, f"{trait_id}: Frame이 서로 달라야 한다")

    def test_all_blueprints_have_exactly_5_options_and_draft_status(self) -> None:
        for bp in V2_DIRECT_PROBE_BLUEPRINTS:
            with self.subTest(blueprint_id=bp.blueprint.blueprint_id):
                self.assertEqual(len(bp.blueprint.roles), 5)
                self.assertEqual(len(bp.base_question.options), 5)
                self.assertEqual(bp.review_status, "draft")

    def test_no_composite_key_duplicates_across_blueprints(self) -> None:
        seen: set[tuple[str, str]] = set()
        for bp in V2_DIRECT_PROBE_BLUEPRINTS:
            for role in bp.blueprint.roles:
                key = (bp.blueprint.blueprint_id, role.role_id)
                self.assertNotIn(key, seen)
                seen.add(key)

    def test_base_question_role_ids_match_blueprint_role_ids(self) -> None:
        for bp in V2_DIRECT_PROBE_BLUEPRINTS:
            with self.subTest(blueprint_id=bp.blueprint.blueprint_id):
                blueprint_roles = [r.role_id for r in bp.blueprint.roles]
                question_roles = [o.role_id for o in bp.base_question.options]
                self.assertEqual(blueprint_roles, question_roles)

    def test_no_trait_label_korean_words_in_base_question_text(self) -> None:
        """§6: Trait Label을 문장에 직접 노출하지 않는다."""

        forbidden = ("구조적 사고", "창의적 발상", "독립적 판단", "지속력", "완수력", "세부 지향")
        for bp in V2_DIRECT_PROBE_BLUEPRINTS:
            all_text = bp.base_question.question_text + " " + " ".join(o.text for o in bp.base_question.options)
            for phrase in forbidden:
                with self.subTest(blueprint_id=bp.blueprint.blueprint_id, phrase=phrase):
                    self.assertNotIn(phrase, all_text)

    def test_no_option_text_is_a_question(self) -> None:
        for bp in V2_DIRECT_PROBE_BLUEPRINTS:
            for option in bp.base_question.options:
                with self.subTest(blueprint_id=bp.blueprint.blueprint_id, role_id=option.role_id):
                    self.assertFalse(option.text.strip().endswith("?"))


class SelectorUnitTest(unittest.TestCase):
    def test_exploration_traits_capped_at_one(self) -> None:
        candidates = select_v2_probe_candidates({}, set())
        exploration = {"creative_ideation", "independent_judgment"}
        self.assertLessEqual(len(exploration & set(candidates)), 1)

    def test_already_probed_traits_are_excluded(self) -> None:
        candidates = select_v2_probe_candidates({}, {"systems_thinking"})
        self.assertNotIn("systems_thinking", candidates)

    def test_select_blueprint_for_trait_respects_context(self) -> None:
        blueprint = select_blueprint_for_trait("systems_thinking", ["media"], set())
        self.assertIsNone(blueprint)  # systems_thinking Blueprint는 game/school_life뿐
        blueprint = select_blueprint_for_trait("systems_thinking", ["game", "media"], set())
        self.assertIsNotNone(blueprint)
        self.assertEqual(blueprint.trait_id, "systems_thinking")

    def test_select_blueprint_for_trait_prefers_unused_frame(self) -> None:
        blueprint = select_blueprint_for_trait(
            "systems_thinking", ["game", "school_life"], used_v2_probe_frame_ids={"new_tool"}
        )
        self.assertEqual(blueprint.question_frame_id, "unexpected_result")


class FeatureFlagOffRegressionTest(unittest.TestCase):
    def setUp(self) -> None:
        patcher = patch.object(main_module, "_llm_client", None)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", None)

    def test_full_session_never_enters_v2_probe_phase(self) -> None:
        session_id = _drive_full_session()
        state = main_module._store.load(session_id)
        self.assertEqual(state.v2_probe_phase, "LEGACY_ASSESSMENT")
        self.assertEqual(state.v2_probe_questions_asked, 0)
        self.assertEqual(state.v2_probed_trait_ids, [])
        self.assertFalse(any(e.evidence_origin == EvidenceOrigin.V2_DIRECT_PROBE for e in state.evidence_ledger))

    def test_answer_count_matches_legacy_only_baseline(self) -> None:
        session_id = _drive_full_session()
        state = main_module._store.load(session_id)
        self.assertEqual(len(state.answers), 21)


class FeatureFlagOnDirectProbeFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        patcher = patch.object(main_module, "_llm_client", None)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ["ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES"] = "true"
        self.addCleanup(os.environ.pop, "ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", None)

    def test_exactly_4_direct_probe_questions_after_legacy(self) -> None:
        session_id = _drive_full_session()
        state = main_module._store.load(session_id)
        self.assertEqual(state.v2_probe_phase, "COMPLETE")
        self.assertEqual(state.v2_probe_questions_asked, MAX_V2_DIRECT_PROBE_QUESTIONS)
        self.assertEqual(len(state.v2_probed_trait_ids), MAX_V2_DIRECT_PROBE_QUESTIONS)
        self.assertEqual(len(state.answers), 21 + MAX_V2_DIRECT_PROBE_QUESTIONS)

    def test_no_trait_probed_twice(self) -> None:
        session_id = _drive_full_session()
        state = main_module._store.load(session_id)
        self.assertEqual(len(state.v2_probed_trait_ids), len(set(state.v2_probed_trait_ids)))

    def test_every_direct_probe_evidence_is_exact_blueprint_never_legacy_adapter(self) -> None:
        session_id = _drive_full_session()
        state = main_module._store.load(session_id)
        direct_probe_records = [e for e in state.evidence_ledger if e.evidence_origin == EvidenceOrigin.V2_DIRECT_PROBE]
        self.assertEqual(len(direct_probe_records), MAX_V2_DIRECT_PROBE_QUESTIONS)
        for record in direct_probe_records:
            with self.subTest(question_id=record.question_id):
                self.assertEqual(record.trait_signal_mapping_source_v2, "EXACT_BLUEPRINT")
                self.assertTrue(any(s.signal_role == "PRIMARY" for s in record.applied_trait_signals_v2))

    def test_legacy_evidence_and_summaries_are_unaffected_by_direct_probe(self) -> None:
        """Feature Flag OFF/ON 두 세션을 동일한 답변 패턴(옵션 0번 계속 선택)으로
        진행했을 때 Legacy trait_summaries는 완전히 동일해야 한다."""

        session_on = _drive_full_session()
        state_on = main_module._store.load(session_on)

        os.environ.pop("ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", None)
        session_off = _drive_full_session()
        state_off = main_module._store.load(session_off)
        os.environ["ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES"] = "true"

        self.assertEqual(
            {tid: s.model_dump() for tid, s in state_on.trait_summaries.items()},
            {tid: s.model_dump() for tid, s in state_off.trait_summaries.items()},
        )
        self.assertEqual(state_on.unresolved_conflict_trait_ids, state_off.unresolved_conflict_trait_ids)

    def test_legacy_only_evidence_count_unchanged_by_direct_probe(self) -> None:
        session_id = _drive_full_session()
        state = main_module._store.load(session_id)
        legacy_records = [e for e in state.evidence_ledger if e.evidence_origin == EvidenceOrigin.PRIMARY_BLUEPRINT]
        self.assertEqual(len(legacy_records), 21)

    def test_direct_probe_does_not_pollute_legacy_planner_state(self) -> None:
        """§9 금지 목록: recent_target_trait_ids/used_frame_ids_in_current_context/
        offered_trait_ids_by_question/questions_asked_in_current_context은 Direct
        Probe 답변으로 바뀌면 안 된다 — Flag ON 세션의 이 필드들은 동일한 답변 패턴의
        Flag OFF 세션과 정확히 같아야 한다(Direct Probe 질문 4개만큼 늘어나 있으면
        안 된다)."""

        session_on = _drive_full_session()
        state_on = main_module._store.load(session_on)

        os.environ.pop("ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", None)
        session_off = _drive_full_session()
        state_off = main_module._store.load(session_off)
        os.environ["ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES"] = "true"

        self.assertEqual(state_on.questions_asked_in_current_context, state_off.questions_asked_in_current_context)
        self.assertEqual(state_on.recent_target_trait_ids, state_off.recent_target_trait_ids)
        self.assertEqual(state_on.offered_trait_ids_by_question, state_off.offered_trait_ids_by_question)
        self.assertEqual(
            state_on.used_frame_ids_in_current_context, state_off.used_frame_ids_in_current_context
        )

    def test_no_candidates_left_terminates_immediately(self) -> None:
        """모든 후보 Trait를 이미 확인했다고 인위적으로 만들면 다음 next-question 호출이
        바로 완료 처리돼야 한다(§12 "후보 Trait 없음")."""

        session_id = _drive_full_session(option_index=0)
        state = main_module._store.load(session_id)
        # 이미 Direct Probe가 4개 진행돼 COMPLETE 상태다 — 강제로 다시 V2_DIRECT_PROBE로
        # 되돌리고 나머지 후보를 전부 probed 처리해 "후보 없음" 종료를 재현한다.
        state.v2_probe_phase = "V2_DIRECT_PROBE"
        state.v2_probed_trait_ids = list(V2_DIRECT_PROBE_TARGET_TRAIT_IDS)
        main_module._store.save(state)
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        body = r.json()
        self.assertEqual(body["status"], "CONTEXT_EARLY_TERMINATED")
        self.assertTrue(body["assessment_complete"])
        state = main_module._store.load(session_id)
        self.assertEqual(state.v2_probe_phase, "COMPLETE")

    def test_non_target_option_selected_records_opportunity_without_negative_evidence(self) -> None:
        """Direct Probe 질문에서 Target Trait가 아닌 선택지를 고르면
        target_signal_selected=False가 기록되지만, 그 Trait의 v2 Snapshot이 부정적으로
        바뀌지는 않는다(§10)."""

        session_id = _drive_full_session(option_index=1)  # 항상 두 번째(Target 아닌) 선택지
        state = main_module._store.load(session_id)
        self.assertTrue(state.v2_probe_opportunities)
        for opp in state.v2_probe_opportunities:
            with self.subTest(question_id=opp.question_id):
                self.assertFalse(opp.target_signal_selected)
        # Target Trait 자체의 PRIMARY Evidence는 기록되지 않아야 한다(비선택은 근거가 아니다).
        for record in state.evidence_ledger:
            if record.evidence_origin != EvidenceOrigin.V2_DIRECT_PROBE:
                continue
            primary_trait_ids = {s.trait_id for s in record.applied_trait_signals_v2 if s.signal_role == "PRIMARY"}
            opp = next(o for o in state.v2_probe_opportunities if o.question_id == record.question_id)
            self.assertNotIn(opp.target_trait_id, primary_trait_ids)


class LLMDrivenDirectProbeTest(unittest.TestCase):
    """2단계 §13/§17 Persona 11~13 — LLM 성공/실패/Quality Gate 실패 각각에서도 Direct
    Probe가 항상 EXACT_BLUEPRINT를 얻는지 확인한다(LEGACY_PRIMARY_ADAPTER 의존 금지, §13)."""

    def _run_to_first_v2_probe_question(self, fake_client) -> tuple[str, dict]:
        os.environ["ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES"] = "true"
        self.addCleanup(os.environ.pop, "ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", None)
        patcher = patch.object(main_module, "_llm_client", None)
        patcher.start()
        self.addCleanup(patcher.stop)

        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 5, "media": 5, "school_life": 5}},
        )
        client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "media"]},
        )
        client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game", "media", "school_life"]},
        )
        body = None
        for _ in range(60):
            r = client.post("/assessment/next-question", params={"session_id": session_id})
            body = r.json()
            if body["status"] == "CONTEXT_EARLY_TERMINATED":
                continue
            state = main_module._store.load(session_id)
            if state.current_question_family_id == "v2_direct_probe":
                # 첫 V2 Probe 질문에 도달한 시점부터 FakeLLM으로 전환한다.
                patcher.stop()
                patch.object(main_module, "_llm_client", fake_client).start()
                return session_id, body
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

    def test_llm_success_gets_exact_blueprint(self) -> None:
        session_id, _ = self._run_to_first_v2_probe_question(_SmartFakeLLMClient("success"))
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        body = r.json()
        self.assertEqual(body["status"], "GENERATED")
        question = body["question"]
        client.post(
            "/assessment/answer",
            json={
                "session_id": session_id, "question_id": question["question_id"],
                "selected_option_id": question["options"][0]["option_id"],
            },
        )
        state = main_module._store.load(session_id)
        evidence = state.evidence_ledger[-1]
        self.assertEqual(evidence.evidence_origin, EvidenceOrigin.V2_DIRECT_PROBE)
        self.assertEqual(evidence.trait_signal_mapping_source_v2, "EXACT_BLUEPRINT")

    def test_llm_always_fails_falls_back_to_base_question_with_exact_blueprint(self) -> None:
        session_id, _ = self._run_to_first_v2_probe_question(_SmartFakeLLMClient("always_fail"))
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        body = r.json()
        self.assertEqual(body["status"], "BACKUP_USED")
        question = body["question"]
        client.post(
            "/assessment/answer",
            json={
                "session_id": session_id, "question_id": question["question_id"],
                "selected_option_id": question["options"][0]["option_id"],
            },
        )
        state = main_module._store.load(session_id)
        evidence = state.evidence_ledger[-1]
        self.assertEqual(evidence.trait_signal_mapping_source_v2, "EXACT_BLUEPRINT")
        self.assertNotEqual(evidence.trait_signal_mapping_source_v2, "LEGACY_PRIMARY_ADAPTER")

    def test_quality_gate_failure_falls_back_to_base_question_with_exact_blueprint(self) -> None:
        session_id, _ = self._run_to_first_v2_probe_question(_SmartFakeLLMClient("quality_gate_fail"))
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        body = r.json()
        self.assertEqual(body["status"], "BACKUP_USED")
        question = body["question"]
        client.post(
            "/assessment/answer",
            json={
                "session_id": session_id, "question_id": question["question_id"],
                "selected_option_id": question["options"][0]["option_id"],
            },
        )
        state = main_module._store.load(session_id)
        evidence = state.evidence_ledger[-1]
        self.assertEqual(evidence.trait_signal_mapping_source_v2, "EXACT_BLUEPRINT")


class ApiContractRegressionTest(unittest.TestCase):
    def setUp(self) -> None:
        patcher = patch.object(main_module, "_llm_client", None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_no_new_endpoints_added_for_v2_direct_probe(self) -> None:
        paths = set(app.openapi()["paths"])
        self.assertEqual(
            paths,
            {
                "/contexts", "/assessment/session", "/assessment/interest-rating",
                "/assessment/context-select", "/assessment/context-confirm",
                "/assessment/next-question", "/assessment/answer", "/profile/{session_id}",
                "/majors/{session_id}", "/departments/{major_id}", "/subjects/{session_id}",
                "/course/upload", "/course/confirm", "/subgraph/{session_id}",
                "/session/{session_id}",
            },
        )

    def test_openapi_never_mentions_v2_direct_probe_internals(self) -> None:
        spec_text = str(app.openapi())
        for forbidden in (
            "v2_direct_probe", "V2ProbeOpportunity", "assessment_phase", "v2_probe_phase",
            "pending_v2_probe_trait_ids", "current_v2_probe_target_trait_id",
            "direct_probe_opportunity_count", "target_signal_selected",
        ):
            self.assertNotIn(forbidden, spec_text, forbidden)

    def test_response_never_leaks_v2_direct_probe_internals(self) -> None:
        os.environ["ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES"] = "true"
        try:
            session_id = _drive_full_session()
        finally:
            os.environ.pop("ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", None)
        for path in (f"/profile/{session_id}", f"/majors/{session_id}", f"/subgraph/{session_id}"):
            body_text = str(client.get(path).json())
            for forbidden in (
                "v2_direct_probe", "target_signal_selected", "V2ProbeOpportunity",
                "systems_thinking", "creative_ideation", "independent_judgment",
            ):
                self.assertNotIn(forbidden, body_text, f"{path} leaked {forbidden!r}")


if __name__ == "__main__":
    unittest.main()
