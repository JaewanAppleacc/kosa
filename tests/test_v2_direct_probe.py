"""V2 Direct Probe 통합 테스트 — 2026-08-23 Trait Ontology v2(2단계) §21.

Feature Flag OFF/ON 회귀, Evidence 분리, Question Bank 구조, Snapshot 판정을 실제
`/assessment` API 흐름으로 확인한다. 네트워크 호출 없음(LLM off로 고정, LLM ON 시나리오는
FakeLLM으로 결정론적으로 재현한다).
"""

from __future__ import annotations

import os
import re
import unittest
from unittest.mock import patch

from pydantic import ValidationError

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
from src.schemas.trait_vector_snapshot import TraitVectorEntry
from src.services.feature_flags import MAX_V2_DIRECT_PROBE_QUESTIONS, trait_vector_v2_direct_probes_enabled

client = TestClient(app)

_CONTEXT_RE = re.compile(r'context 필드에는 "(\w+)"를')
_FRAME_RE = re.compile(r'frame_id 필드에는 "(\w+)"를')
_ROLE_RE = re.compile(r"\[Option Role.*?\]\n(.*?)\n\ncontext 필드", re.DOTALL)


class _SmartFakeLLMClient:
    """Legacy Tail 질문(question_generation_graph.py)과 V2 Direct Probe 질문
    (v2_direct_probe_generator.py) 두 Prompt 포맷을 전부 이해한다 — 세션 시작부터 끝까지
    LLM Client를 교체하지 않고 하나로 계속 쓸 수 있어야, "첫 Direct Probe 질문부터 실제
    LLM 경로로 생성되는지"를 재요청 없이 검증할 수 있다(2.1단계 §13). 두 포맷의 유일한
    차이는 Role 목록 줄이 Legacy는 "role_id (측정 대상: 라벨)", Direct Probe는
    "role_id"뿐이라는 것 — 공백으로 잘라 첫 토큰만 취하면 둘 다 처리된다."""

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
        role_ids = [
            line.removeprefix("- ").strip().split(" ")[0] for line in role_block.strip().splitlines()
        ]
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
            with self.subTest(blueprint_id=bp.blueprint_id):
                self.assertEqual(len(bp.option_mappings), 5)
                self.assertEqual(len(bp.base_question.options), 5)
                self.assertEqual(bp.review_status, "draft")

    def test_no_composite_key_duplicates_across_blueprints(self) -> None:
        seen: set[tuple[str, str]] = set()
        for bp in V2_DIRECT_PROBE_BLUEPRINTS:
            for mapping in bp.option_mappings:
                key = (bp.blueprint_id, mapping.role_id)
                self.assertNotIn(key, seen)
                seen.add(key)

    def test_base_question_role_ids_match_blueprint_role_ids(self) -> None:
        for bp in V2_DIRECT_PROBE_BLUEPRINTS:
            with self.subTest(blueprint_id=bp.blueprint_id):
                blueprint_roles = [m.role_id for m in bp.option_mappings]
                question_roles = [o.role_id for o in bp.base_question.options]
                self.assertEqual(blueprint_roles, question_roles)

    def test_no_trait_label_korean_words_in_base_question_text(self) -> None:
        """§6: Trait Label을 문장에 직접 노출하지 않는다."""

        forbidden = ("구조적 사고", "창의적 발상", "독립적 판단", "지속력", "완수력", "세부 지향")
        for bp in V2_DIRECT_PROBE_BLUEPRINTS:
            all_text = bp.base_question.question_text + " " + " ".join(o.text for o in bp.base_question.options)
            for phrase in forbidden:
                with self.subTest(blueprint_id=bp.blueprint_id, phrase=phrase):
                    self.assertNotIn(phrase, all_text)

    def test_no_option_text_is_a_question(self) -> None:
        for bp in V2_DIRECT_PROBE_BLUEPRINTS:
            for option in bp.base_question.options:
                with self.subTest(blueprint_id=bp.blueprint_id, role_id=option.role_id):
                    self.assertFalse(option.text.strip().endswith("?"))


def _entry(
    trait_id: str, *, status: str = "NOT_PROBED", related_evidence_count: int = 0,
    evidence_confidence: str = "no_evidence", related_question_count: int = 0,
    related_context_count: int = 0, related_frame_count: int = 0,
    related_signal_sum: float = 0.0, related_context_ids: set[str] | None = None,
) -> TraitVectorEntry:
    return TraitVectorEntry(
        trait_id=trait_id, primary_signal_sum=0.0, related_signal_sum=related_signal_sum,
        confirmed_related_signal_sum=0.0, primary_evidence_count=0,
        related_evidence_count=related_evidence_count, context_count=0, frame_count=0,
        question_count=0, tendency_score=None, evidence_confidence=evidence_confidence,
        status=status, related_question_count=related_question_count,
        related_context_count=related_context_count, related_frame_count=related_frame_count,
        related_context_ids=related_context_ids or set(),
    )


_ALL_CONTEXTS = ["game", "media", "school_life"]


class SelectorEligibilityTest(unittest.TestCase):
    """2.1단계 §1/§2 — 후보 "자격"과 "정렬 순서"를 분리해서 검증한다."""

    def test_zero_evidence_hypothesis_traits_are_excluded_not_just_deprioritized(self) -> None:
        """2단계 버그 재현 시나리오 1: 신규 7개 Trait 전부 Evidence 0 — Hypothesis 기반
        5개는 후보에서 완전히 빠지고, 탐색 Trait 1개만 남아야 한다."""

        snapshot = {t: _entry(t) for t in V2_DIRECT_PROBE_TARGET_TRAIT_IDS}
        candidates = select_v2_probe_candidates(
            snapshot, set(), final_contexts=_ALL_CONTEXTS, used_v2_probe_frame_ids=set()
        )
        hypothesis_based = {
            "systems_thinking", "detail_orientation", "persistence_completion",
            "uncertainty_tolerance", "opinion_expression",
        }
        self.assertEqual(set(candidates) & hypothesis_based, set())
        self.assertEqual(len(candidates), 1)  # 탐색 Trait 1개만

    def test_related_evidence_of_one_makes_trait_eligible(self) -> None:
        """재현 시나리오 2: systems_thinking에만 RELATED 1개 — 후보에 포함돼야 한다."""

        snapshot = {t: _entry(t) for t in V2_DIRECT_PROBE_TARGET_TRAIT_IDS}
        snapshot["systems_thinking"] = _entry(
            "systems_thinking", status="HYPOTHESIS", related_evidence_count=1,
            evidence_confidence="unconfirmed_related_signal", related_question_count=1,
        )
        candidates = select_v2_probe_candidates(
            snapshot, set(), final_contexts=_ALL_CONTEXTS, used_v2_probe_frame_ids=set()
        )
        self.assertIn("systems_thinking", candidates)

    def test_related_evidence_on_five_traits_all_eligible(self) -> None:
        """재현 시나리오 3: 5개 Trait 모두 RELATED 1개씩 — 전부 후보여야 한다(순서는
        RELATED 다양성으로 정렬되지만 전부 남아 있어야 한다)."""

        snapshot = {t: _entry(t) for t in V2_DIRECT_PROBE_TARGET_TRAIT_IDS}
        for t in ("systems_thinking", "detail_orientation", "persistence_completion",
                  "uncertainty_tolerance", "opinion_expression"):
            snapshot[t] = _entry(
                t, status="HYPOTHESIS", related_evidence_count=1,
                evidence_confidence="unconfirmed_related_signal", related_question_count=1,
            )
        candidates = select_v2_probe_candidates(
            snapshot, set(), final_contexts=_ALL_CONTEXTS, used_v2_probe_frame_ids=set()
        )
        hypothesis_based = {
            "systems_thinking", "detail_orientation", "persistence_completion",
            "uncertainty_tolerance", "opinion_expression",
        }
        self.assertTrue(hypothesis_based <= set(candidates))

    def test_moderate_or_strong_status_excludes_trait(self) -> None:
        snapshot = {"systems_thinking": _entry("systems_thinking", status="MODERATE", related_evidence_count=3)}
        candidates = select_v2_probe_candidates(
            snapshot, set(), final_contexts=_ALL_CONTEXTS, used_v2_probe_frame_ids=set()
        )
        self.assertNotIn("systems_thinking", candidates)

    def test_conflicting_status_excludes_trait(self) -> None:
        snapshot = {"systems_thinking": _entry("systems_thinking", status="CONFLICTING", related_evidence_count=3)}
        candidates = select_v2_probe_candidates(
            snapshot, set(), final_contexts=_ALL_CONTEXTS, used_v2_probe_frame_ids=set()
        )
        self.assertNotIn("systems_thinking", candidates)

    def test_already_probed_traits_are_excluded(self) -> None:
        snapshot = {"systems_thinking": _entry("systems_thinking", related_evidence_count=2)}
        candidates = select_v2_probe_candidates(
            snapshot, {"systems_thinking"}, final_contexts=_ALL_CONTEXTS, used_v2_probe_frame_ids=set()
        )
        self.assertNotIn("systems_thinking", candidates)

    def test_no_usable_blueprint_for_context_excludes_trait(self) -> None:
        """systems_thinking Blueprint는 game/school_life뿐 — media만 있는 세션에서는
        후보가 될 수 없다(§2 "학생의 최종 Context 안에서 사용할 Blueprint가 존재")."""

        snapshot = {"systems_thinking": _entry("systems_thinking", related_evidence_count=2)}
        candidates = select_v2_probe_candidates(
            snapshot, set(), final_contexts=["media"], used_v2_probe_frame_ids=set()
        )
        self.assertNotIn("systems_thinking", candidates)

    def test_exploration_traits_capped_at_one(self) -> None:
        candidates = select_v2_probe_candidates(
            {}, set(), final_contexts=_ALL_CONTEXTS, used_v2_probe_frame_ids=set()
        )
        exploration = {"creative_ideation", "independent_judgment"}
        self.assertLessEqual(len(exploration & set(candidates)), 1)

    def test_evidence_dependent_candidate_count_not_always_full(self) -> None:
        """2단계 회귀 차단: Evidence가 없으면 후보 수가 4보다 훨씬 적어야 한다(항상
        4개가 되는 현상 제거)."""

        candidates = select_v2_probe_candidates(
            {}, set(), final_contexts=_ALL_CONTEXTS, used_v2_probe_frame_ids=set()
        )
        self.assertLessEqual(len(candidates), 1)


class IncidentalPrimaryEvidencePolicyTest(unittest.TestCase):
    """2.1단계 §15 정책: "Direct PRIMARY를 다른 Probe의 비Target 선택지에서 얻은 경우 —
    Evidence에는 기록하지만, Target Probe 재질문 여부는 후보 정책에 따라 명시적으로
    결정한다." 정책: `already_probed_trait_ids`는 그 Trait 자체가 실제 Target으로
    Probe됐을 때만 커진다(§9 Opportunity 기록과 별개) — 그래서 다른 Trait의 비Target
    선택지에서 우연히 PRIMARY를 얻은 Trait는 "이미 Target Probe했다"로 취급되지 않고,
    RELATED Evidence가 있다면 여전히 후보로 남는다(다만 그 PRIMARY 자체가 이미
    MODERATE/STRONG까지 끌어올렸다면 기존 "충분히 확인됨" 규칙으로 자연히 제외된다)."""

    def test_incidental_primary_alone_keeps_trait_eligible_if_related_evidence_exists(self) -> None:
        # detail_orientation은 persistence_completion_school_life_v1의 비Target Role
        # "pc_detail_stage"에서 우연히 PRIMARY를 받을 수 있다(§9 Worksheet 참고) — 이
        # 상황을 Snapshot 값으로 직접 재현한다: PRIMARY 1개(LIMITED) + RELATED 1개.
        entry = _entry(
            "detail_orientation", status="LIMITED", related_evidence_count=1,
            evidence_confidence="primary_evidence", related_question_count=1,
        )
        snapshot = {"detail_orientation": entry}
        candidates = select_v2_probe_candidates(
            snapshot, already_probed_trait_ids=set(),  # 실제로 Target Probe한 적은 없다
            final_contexts=_ALL_CONTEXTS, used_v2_probe_frame_ids=set(),
        )
        self.assertIn("detail_orientation", candidates)

    def test_incidental_primary_reaching_moderate_excludes_trait_via_existing_rule(self) -> None:
        entry = _entry(
            "detail_orientation", status="MODERATE", related_evidence_count=1,
            evidence_confidence="primary_evidence",
        )
        snapshot = {"detail_orientation": entry}
        candidates = select_v2_probe_candidates(
            snapshot, already_probed_trait_ids=set(),
            final_contexts=_ALL_CONTEXTS, used_v2_probe_frame_ids=set(),
        )
        self.assertNotIn("detail_orientation", candidates)


class SelectorSortOrderTest(unittest.TestCase):
    def test_sort_key_uses_related_diversity_not_mixed_primary(self) -> None:
        """§4 정렬 기준 2~4는 RELATED 전용 다양성만 써야 한다."""

        snapshot = {
            "systems_thinking": _entry(
                "systems_thinking", status="HYPOTHESIS", related_evidence_count=1,
                related_question_count=1, related_context_count=1, related_frame_count=1,
                related_signal_sum=0.33,
            ),
            "detail_orientation": _entry(
                "detail_orientation", status="HYPOTHESIS", related_evidence_count=2,
                related_question_count=2, related_context_count=2, related_frame_count=2,
                related_signal_sum=0.66,
            ),
        }
        candidates = select_v2_probe_candidates(
            snapshot, set(), final_contexts=_ALL_CONTEXTS, used_v2_probe_frame_ids=set()
        )
        self.assertEqual(candidates.index("detail_orientation"), 0)  # 더 넓게 관찰된 쪽이 먼저

    def test_trait_id_is_deterministic_tie_break(self) -> None:
        snapshot = {
            "opinion_expression": _entry(
                "opinion_expression", status="HYPOTHESIS", related_evidence_count=1,
                related_question_count=1, related_context_count=1, related_frame_count=1,
            ),
            "detail_orientation": _entry(
                "detail_orientation", status="HYPOTHESIS", related_evidence_count=1,
                related_question_count=1, related_context_count=1, related_frame_count=1,
            ),
        }
        candidates = select_v2_probe_candidates(
            snapshot, set(), final_contexts=_ALL_CONTEXTS, used_v2_probe_frame_ids=set()
        )
        hypothesis_candidates = [c for c in candidates if c in ("opinion_expression", "detail_orientation")]
        self.assertEqual(hypothesis_candidates, sorted(hypothesis_candidates))


class BlueprintContextSelectionTest(unittest.TestCase):
    def test_respects_final_context(self) -> None:
        blueprint = select_blueprint_for_trait(
            "systems_thinking", related_context_ids=set(), preferred_context_ids=[],
            final_contexts=["media"], used_v2_probe_frame_ids=set(),
        )
        self.assertIsNone(blueprint)  # systems_thinking Blueprint는 game/school_life뿐
        blueprint = select_blueprint_for_trait(
            "systems_thinking", related_context_ids=set(), preferred_context_ids=[],
            final_contexts=["game", "media"], used_v2_probe_frame_ids=set(),
        )
        self.assertIsNotNone(blueprint)
        self.assertEqual(blueprint.trait_id, "systems_thinking")

    def test_prefers_context_with_related_evidence_first(self) -> None:
        """§5 우선순위 1: RELATED Evidence가 실제 관찰된 Context를 최우선으로 쓴다."""

        blueprint = select_blueprint_for_trait(
            "systems_thinking", related_context_ids={"school_life"}, preferred_context_ids=["game"],
            final_contexts=["game", "school_life"], used_v2_probe_frame_ids=set(),
        )
        # school_life에서 RELATED가 나왔으므로 game이 Preferred라도 school_life Blueprint를 고른다.
        self.assertEqual(blueprint.blueprint_id, "systems_thinking_school_life_v1")

    def test_falls_back_to_preferred_context_when_no_related_evidence(self) -> None:
        blueprint = select_blueprint_for_trait(
            "systems_thinking", related_context_ids=set(), preferred_context_ids=["school_life"],
            final_contexts=["game", "school_life"], used_v2_probe_frame_ids=set(),
        )
        self.assertEqual(blueprint.blueprint_id, "systems_thinking_school_life_v1")

    def test_prefers_unused_frame_when_context_signals_tie(self) -> None:
        blueprint = select_blueprint_for_trait(
            "systems_thinking", related_context_ids=set(), preferred_context_ids=[],
            final_contexts=["game", "school_life"], used_v2_probe_frame_ids={"new_tool"},
        )
        self.assertEqual(blueprint.question_frame_id, "unexpected_result")

    def test_exploration_trait_context_priority_is_preferred_then_final_then_frame(self) -> None:
        """탐색 Trait는 RELATED Evidence가 없으므로 Preferred → Final → 미사용 Frame
        순으로 정해져야 한다."""

        blueprint = select_blueprint_for_trait(
            "creative_ideation", related_context_ids=set(), preferred_context_ids=["game"],
            final_contexts=["game", "media"], used_v2_probe_frame_ids=set(),
        )
        self.assertEqual(blueprint.blueprint_id, "creative_ideation_game_v1")


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

    def test_default_option0_persona_gets_evidence_driven_question_count(self) -> None:
        """2.1단계 §1/§3 핵심 완료 조건: 옵션[0]만 계속 고르는 기본 Persona는
        game/media Seed에서 systems_thinking RELATED 2개, school_life Seed에서
        persistence_completion RELATED 1개를 얻는다 — 실제 후보는 Hypothesis 2개
        (systems_thinking·persistence_completion) + 탐색 1개 = 3개이지, 2단계처럼
        "항상 4개"가 아니다."""

        session_id = _drive_full_session()
        state = main_module._store.load(session_id)
        self.assertEqual(state.v2_probe_phase, "COMPLETE")
        self.assertEqual(state.v2_probe_questions_asked, 3)
        self.assertLess(state.v2_probe_questions_asked, MAX_V2_DIRECT_PROBE_QUESTIONS)
        probed = set(state.v2_probed_trait_ids)
        self.assertTrue({"systems_thinking", "persistence_completion"} <= probed)
        self.assertEqual(len(probed & {"creative_ideation", "independent_judgment"}), 1)
        self.assertEqual(len(state.answers), 21 + 3)

    def test_no_trait_probed_twice(self) -> None:
        session_id = _drive_full_session()
        state = main_module._store.load(session_id)
        self.assertEqual(len(state.v2_probed_trait_ids), len(set(state.v2_probed_trait_ids)))

    def test_at_most_one_exploration_trait_probed_across_whole_session(self) -> None:
        """2.1단계 버그 수정: Exploration Trait 상한(1개)은 매 후보 계산 1회가 아니라
        세션 전체에 걸쳐 적용돼야 한다."""

        session_id = _drive_full_session()
        state = main_module._store.load(session_id)
        exploration = {"creative_ideation", "independent_judgment"}
        self.assertLessEqual(len(exploration & set(state.v2_probed_trait_ids)), 1)

    def test_every_direct_probe_evidence_is_exact_blueprint_never_legacy_adapter(self) -> None:
        session_id = _drive_full_session()
        state = main_module._store.load(session_id)
        direct_probe_records = [e for e in state.evidence_ledger if e.evidence_origin == EvidenceOrigin.V2_DIRECT_PROBE]
        self.assertTrue(direct_probe_records)
        for record in direct_probe_records:
            with self.subTest(question_id=record.question_id):
                self.assertEqual(record.trait_signal_mapping_source_v2, "EXACT_BLUEPRINT")
                self.assertTrue(any(s.signal_role == "PRIMARY" for s in record.applied_trait_signals_v2))

    def test_max_cap_of_4_is_still_enforced_when_more_candidates_are_eligible(self) -> None:
        """§3 "최대치는 그대로 유지" — Hypothesis 4개 이상이 진짜로 Eligible해지면
        4개에서 멈춰야 한다(강제로 5개 Trait 모두에 RELATED Evidence를 심어 재현)."""

        os.environ["ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES"] = "true"
        session_id = _drive_full_session(final_contexts=("game", "media", "school_life"))
        state = main_module._store.load(session_id)
        # 이미 COMPLETE 상태다 — Legacy Seed 3개로부터 얻은 RELATED만으로 5개 Trait 전부에
        # 인위적으로 RELATED Evidence를 추가하고, Direct Probe Phase로 되돌려 재현한다.
        from src.schemas.evidence import AppliedTraitSignal, EvidenceOrigin as Origin, EvidenceRecord as ER
        from src.ids import generate_evidence_id

        for trait_id in ("uncertainty_tolerance", "opinion_expression", "detail_orientation"):
            state.evidence_ledger.append(
                ER(
                    evidence_id=generate_evidence_id(), answer_id=f"ans_synthetic_{trait_id}",
                    question_id=f"q_synthetic_{trait_id}", question_frame_id="problem_check",
                    option_role_id="synthetic_role", option_text="합성 답변",
                    applied_primary_trait_delta={}, evidence_origin=Origin.PRIMARY_BLUEPRINT,
                    context="game", source_type="seed_question", generator_version="v1",
                    quality_gate_status="passed",
                    applied_trait_signals_v2=[
                        AppliedTraitSignal(trait_id=trait_id, signal_role="RELATED", weight=0.33)
                    ],
                )
            )
        state.v2_probe_phase = "V2_DIRECT_PROBE"
        state.v2_probe_questions_asked = 0
        state.v2_probed_trait_ids = []
        main_module._store.save(state)

        for _ in range(10):
            r = client.post("/assessment/next-question", params={"session_id": session_id})
            body = r.json()
            if body["status"] == "CONTEXT_EARLY_TERMINATED":
                break
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
        state = main_module._store.load(session_id)
        self.assertEqual(state.v2_probe_questions_asked, MAX_V2_DIRECT_PROBE_QUESTIONS)

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


class FlaggedQuestionRegressionTest(unittest.TestCase):
    """2.1단계 §8/§19 — 반드시 재검토하라고 지목된 7개 문항의 문제 문구가 실제로
    사라졌는지 회귀 확인한다."""

    def _option_text(self, blueprint_id: str, role_id: str) -> str:
        bp = next(b for b in V2_DIRECT_PROBE_BLUEPRINTS if b.blueprint_id == blueprint_id)
        return next(o.text for o in bp.base_question.options if o.role_id == role_id)

    def test_persistence_completion_game_target_no_longer_mixes_change_adaptation(self) -> None:
        text = self._option_text("persistence_completion_game_v1", "pc_keep_going")
        self.assertNotIn("방법을 바꿔가며", text)
        self.assertIn("목표", text)

    def test_persistence_completion_game_break_option_no_longer_reads_as_persistence(self) -> None:
        text = self._option_text("persistence_completion_game_v1", "pc_take_break")
        self.assertNotIn("잠깐", text)
        self.assertNotIn("다시 돌아온다", text)

    def test_uncertainty_tolerance_game_distinguishes_from_immediate_execution(self) -> None:
        tolerance_text = self._option_text("uncertainty_tolerance_game_v1", "ut_proceed_calm")
        execution_text = self._option_text("uncertainty_tolerance_game_v1", "ut_try_now")
        self.assertNotIn("진행한다", tolerance_text.replace("계속 진행한다", ""))
        self.assertIn("몰라도", tolerance_text)
        self.assertIn("정보", execution_text)

    def test_opinion_expression_school_life_asks_behavior_not_role_preference(self) -> None:
        bp = next(b for b in V2_DIRECT_PROBE_BLUEPRINTS if b.blueprint_id == "opinion_expression_school_life_v1")
        self.assertNotIn("역할을 맡고 싶", bp.base_question.question_text)

    def test_independent_judgment_school_life_asks_behavior_not_role_preference(self) -> None:
        bp = next(
            b for b in V2_DIRECT_PROBE_BLUEPRINTS
            if b.blueprint_id == "independent_judgment_school_life_v1"
        )
        self.assertNotIn("역할을 맡고 싶", bp.base_question.question_text)

    def test_creative_ideation_game_target_no_longer_mixes_novelty_seeking(self) -> None:
        text = self._option_text("creative_ideation_game_v1", "ci_invent_rule")
        self.assertNotIn("아무도", text)
        self.assertNotIn("아직", text)

    def test_systems_thinking_school_life_distinguishes_from_planning(self) -> None:
        """2.5단계 §8: 사용자 검수 피드백("남은 일정과 순서를 처음부터 다시 짜는건
        무조건적으로 1번 선택지인 이 변화가 어떤 영향을 주는지 짚어본 후에야 나올 수
        있는 생각인것같아")을 반영해 두 선택지를 서로 독립적인 표현으로 다시 썼다 —
        st_replan은 st_map_impact 없이도 바로 선택할 수 있는 행동이어야 한다."""

        systems_text = self._option_text("systems_thinking_school_life_v1", "st_map_impact")
        planning_text = self._option_text("systems_thinking_school_life_v1", "st_replan")
        self.assertIn("영향", systems_text)
        self.assertIn("다시 짠다", planning_text)
        # planning 문구가 systems_thinking 문구를 전제하는 표현("짚어본 후"/"그 후에"
        # 등)을 담지 않는지 확인한다 — 순차 의존 재발 방지.
        self.assertNotIn("짚어본 후", planning_text)
        self.assertNotIn("그 후에", planning_text)
        self.assertNotEqual(systems_text, planning_text)

    def test_detail_orientation_media_pattern_finding_option_reflects_pattern_not_flow(self) -> None:
        text = self._option_text("detail_orientation_media_v1", "do_overall_flow")
        self.assertIn("반복", text)
        self.assertNotIn("자연스러운지 훑어본다", text)

    def test_no_blueprint_option_uses_role_preference_phrasing_anymore(self) -> None:
        for bp in V2_DIRECT_PROBE_BLUEPRINTS:
            self.assertNotIn("역할을 맡고 싶", bp.base_question.question_text, bp.blueprint_id)


def _trait_signal_mapping(role_id: str, trait_id: str):
    from src.schemas.trait_signal import TraitSignal
    from src.schemas.v2_direct_probe import V2ProbeOptionMapping

    return V2ProbeOptionMapping(
        role_id=role_id, mapping_type="TRAIT_SIGNAL",
        trait_signals=[TraitSignal(trait_id=trait_id, signal_role="PRIMARY", weight=1.0)],
    )


def _no_signal_mapping(role_id: str, reason: str = "근거가 약함"):
    from src.schemas.v2_direct_probe import V2ProbeOptionMapping

    return V2ProbeOptionMapping(role_id=role_id, mapping_type="NO_SIGNAL", no_signal_reason=reason)


class BlueprintCrossFieldValidationTest(unittest.TestCase):
    """2.1단계 §6, 2.2단계 §4 — Blueprint Cross-field 검증이 실제로 Fail-Fast인지 확인한다."""

    def test_target_option_count_must_be_exactly_one(self) -> None:
        from src.schemas.question import FinalizedOption, FinalizedQuestion
        from src.schemas.v2_direct_probe import V2DirectProbeBlueprint

        # trait_id="systems_thinking"이지만 어떤 Role도 systems_thinking을 PRIMARY로
        # 갖지 않는다 — Target Option 0개 위반을 재현한다. Pydantic model_validator가
        # 던진 ValueError 하위 예외는 pydantic.ValidationError로 감싸져 나온다.
        mappings = [
            _trait_signal_mapping("r1", "causal_analysis"),
            _trait_signal_mapping("r2", "planning"),
            _trait_signal_mapping("r3", "immediate_execution"),
            _trait_signal_mapping("r4", "information_comparison"),
            _trait_signal_mapping("r5", "collaboration_preference"),
        ]
        options = [
            FinalizedOption(
                option_id=f"q_o{i}", role_id=m.role_id, text=f"텍스트 {i}",
                primary_trait_delta={m.primary_trait_id: 1},
            )
            for i, m in enumerate(mappings, start=1)
        ]
        question = FinalizedQuestion(
            question_id="q_test", context="game", target_traits=[], frame_id="new_tool",
            question_text="테스트 질문인가요?", options=options,
        )
        with self.assertRaises(ValidationError):
            V2DirectProbeBlueprint(
                trait_id="systems_thinking", blueprint_id="test_bp", option_mappings=mappings,
                allowed_context_ids=["game"], question_frame_id="new_tool",
                purpose="test", base_question=question,
            )

    def test_context_must_be_in_allowed_context_ids(self) -> None:
        from src.schemas.question import FinalizedOption, FinalizedQuestion
        from src.schemas.v2_direct_probe import V2DirectProbeBlueprint

        mappings = [
            _trait_signal_mapping(f"r{i}", t) for i, t in enumerate([
                "systems_thinking", "causal_analysis", "immediate_execution",
                "information_comparison", "collaboration_preference",
            ], start=1)
        ]
        options = [
            FinalizedOption(
                option_id=f"q_o{i}", role_id=m.role_id, text=f"텍스트 {i}",
                primary_trait_delta={m.primary_trait_id: 1},
            )
            for i, m in enumerate(mappings, start=1)
        ]
        question = FinalizedQuestion(
            question_id="q_test2", context="media", target_traits=[], frame_id="new_tool",
            question_text="테스트 질문인가요?", options=options,
        )
        with self.assertRaises(ValidationError):
            V2DirectProbeBlueprint(
                trait_id="systems_thinking", blueprint_id="test_bp2", option_mappings=mappings,
                allowed_context_ids=["game"], question_frame_id="new_tool",  # media가 아니라 game만 허용
                purpose="test", base_question=question,
            )

    def test_all_14_real_blueprints_pass_validation(self) -> None:
        # Import 시점에 이미 검증됐지만, 명시적으로 한 번 더 확인한다(회귀 고정).
        self.assertEqual(len(V2_DIRECT_PROBE_BLUEPRINTS), 14)


class MutableDefaultSafetyTest(unittest.TestCase):
    """2.3단계 §1 — v2가 추가한 Schema의 list 기본값이 인스턴스 사이에 공유되지
    않는지, JSON 직렬화 결과가 `Field(default_factory=list)` 적용 전후로 그대로인지
    확인한다."""

    def test_two_v2_probe_option_mappings_do_not_share_trait_signals_list(self) -> None:
        from src.schemas.v2_direct_probe import V2ProbeOptionMapping

        a = V2ProbeOptionMapping(role_id="r1", mapping_type="NO_SIGNAL", no_signal_reason="근거 약함")
        b = V2ProbeOptionMapping(role_id="r2", mapping_type="NO_SIGNAL", no_signal_reason="근거 약함")
        self.assertIsNot(a.trait_signals, b.trait_signals)

    def test_mutating_one_instance_trait_signals_does_not_affect_another(self) -> None:
        from src.schemas.trait_signal import TraitSignal
        from src.schemas.v2_direct_probe import V2ProbeOptionMapping

        a = V2ProbeOptionMapping(role_id="r1", mapping_type="NO_SIGNAL", no_signal_reason="근거 약함")
        b = V2ProbeOptionMapping(role_id="r2", mapping_type="NO_SIGNAL", no_signal_reason="근거 약함")
        a.trait_signals.append(TraitSignal(trait_id="planning", signal_role="PRIMARY", weight=1.0))
        self.assertEqual(b.trait_signals, [])

    def test_v2_probe_option_mapping_json_round_trip_unchanged(self) -> None:
        from src.schemas.v2_direct_probe import V2ProbeOptionMapping

        original = V2ProbeOptionMapping(role_id="r1", mapping_type="NO_SIGNAL", no_signal_reason="근거 약함")
        dumped = original.model_dump_json()
        self.assertEqual(dumped, '{"role_id":"r1","mapping_type":"NO_SIGNAL","trait_signals":[],"no_signal_reason":"근거 약함"}')
        restored = V2ProbeOptionMapping.model_validate_json(dumped)
        self.assertEqual(restored, original)

    def test_assessment_state_v2_list_fields_do_not_share_across_instances(self) -> None:
        from src.schemas.assessment_state import AssessmentState

        s1 = AssessmentState(session_id="s1", user_id="u1")
        s2 = AssessmentState(session_id="s2", user_id="u2")
        self.assertIsNot(s1.pending_v2_probe_trait_ids, s2.pending_v2_probe_trait_ids)
        self.assertIsNot(s1.v2_probed_trait_ids, s2.v2_probed_trait_ids)
        self.assertIsNot(s1.v2_probe_opportunities, s2.v2_probe_opportunities)
        s1.pending_v2_probe_trait_ids.append("systems_thinking")
        s1.v2_probed_trait_ids.append("systems_thinking")
        self.assertEqual(s2.pending_v2_probe_trait_ids, [])
        self.assertEqual(s2.v2_probed_trait_ids, [])


class NoSignalMappingTest(unittest.TestCase):
    """2.2단계 §4/§18 — NO_SIGNAL 전용 검증 규칙."""

    def test_no_signal_requires_reason(self) -> None:
        from src.schemas.v2_direct_probe import V2ProbeOptionMapping

        with self.assertRaises(ValidationError):
            V2ProbeOptionMapping(role_id="r1", mapping_type="NO_SIGNAL")

    def test_no_signal_forbids_trait_signals(self) -> None:
        from src.schemas.trait_signal import TraitSignal
        from src.schemas.v2_direct_probe import V2ProbeOptionMapping

        with self.assertRaises(ValidationError):
            V2ProbeOptionMapping(
                role_id="r1", mapping_type="NO_SIGNAL", no_signal_reason="근거 약함",
                trait_signals=[TraitSignal(trait_id="planning", signal_role="PRIMARY", weight=1.0)],
            )

    def test_trait_signal_requires_at_least_one_signal(self) -> None:
        from src.schemas.v2_direct_probe import V2ProbeOptionMapping

        with self.assertRaises(ValidationError):
            V2ProbeOptionMapping(role_id="r1", mapping_type="TRAIT_SIGNAL")

    def test_trait_signal_forbids_no_signal_reason(self) -> None:
        with self.assertRaises(ValidationError):
            from src.schemas.v2_direct_probe import V2ProbeOptionMapping
            from src.schemas.trait_signal import TraitSignal

            V2ProbeOptionMapping(
                role_id="r1", mapping_type="TRAIT_SIGNAL", no_signal_reason="이유 있으면 안 됨",
                trait_signals=[TraitSignal(trait_id="planning", signal_role="PRIMARY", weight=1.0)],
            )

    def test_target_role_cannot_be_no_signal(self) -> None:
        """Blueprint Cross-field 검증: Target Trait를 PRIMARY로 갖는 Option이 정확히
        1개여야 하므로, Target 자리에 NO_SIGNAL을 두면 "0개" 위반으로 거부된다."""

        from src.schemas.question import FinalizedOption, FinalizedQuestion
        from src.schemas.v2_direct_probe import V2DirectProbeBlueprint

        mappings = [
            _no_signal_mapping("r1", "Target인데 근거 불명확이라고 잘못 표시함"),
            _trait_signal_mapping("r2", "causal_analysis"),
            _trait_signal_mapping("r3", "immediate_execution"),
            _trait_signal_mapping("r4", "information_comparison"),
            _trait_signal_mapping("r5", "collaboration_preference"),
        ]
        options = [
            FinalizedOption(option_id="q_o1", role_id="r1", text="텍스트 1", primary_trait_delta={}),
            *[
                FinalizedOption(
                    option_id=f"q_o{i}", role_id=m.role_id, text=f"텍스트 {i}",
                    primary_trait_delta={m.primary_trait_id: 1},
                )
                for i, m in enumerate(mappings[1:], start=2)
            ],
        ]
        question = FinalizedQuestion(
            question_id="q_test3", context="game", target_traits=[], frame_id="new_tool",
            question_text="테스트 질문인가요?", options=options,
        )
        with self.assertRaises(ValidationError):
            V2DirectProbeBlueprint(
                trait_id="systems_thinking", blueprint_id="test_bp3", option_mappings=mappings,
                allowed_context_ids=["game"], question_frame_id="new_tool",
                purpose="test", base_question=question,
            )

    def test_no_sentinel_trait_ids_used_anywhere_in_real_blueprints(self) -> None:
        sentinel_ids = {"no_signal", "neutral", "none", "unknown"}
        for bp in V2_DIRECT_PROBE_BLUEPRINTS:
            for mapping in bp.option_mappings:
                for signal in mapping.trait_signals:
                    self.assertNotIn(signal.trait_id, sentinel_ids)

    def test_15_no_signal_options_exist_and_are_never_the_target(self) -> None:
        no_signal_count = 0
        for bp in V2_DIRECT_PROBE_BLUEPRINTS:
            for mapping in bp.option_mappings:
                if mapping.mapping_type == "NO_SIGNAL":
                    no_signal_count += 1
                    self.assertFalse(
                        mapping.primary_trait_id == bp.trait_id,
                        f"{bp.blueprint_id}/{mapping.role_id}: NO_SIGNAL이 Target일 수 없다",
                    )
        # 2.5단계 §7: do_visual_check(detail_orientation_media_v1)가 미디어 재정의로
        # NO_SIGNAL에서 TRAIT_SIGNAL(visual_expression)로 바뀌었다(14 → 13).
        # 2.5.1단계 §10-A/§10-C: do_visual_check를 다시 NO_SIGNAL로 되돌리고(13 → 14,
        # "관심·감상"은 "직접 표현"의 근거가 아니라는 이유), independent_judgment_
        # school_life_v1의 ij_adapt_role도 change_adaptation에서 "다수 추종" NO_SIGNAL로
        # 바꿨다(14 → 15).
        self.assertEqual(no_signal_count, 15)

    def test_no_signal_options_public_primary_trait_delta_is_empty_dict(self) -> None:
        for bp in V2_DIRECT_PROBE_BLUEPRINTS:
            no_signal_role_ids = {m.role_id for m in bp.option_mappings if m.mapping_type == "NO_SIGNAL"}
            for option in bp.base_question.options:
                if option.role_id in no_signal_role_ids:
                    self.assertEqual(option.primary_trait_delta, {})

    def test_legacy_option_role_still_rejects_empty_delta(self) -> None:
        """Legacy `OptionRole`(Tail Blueprint가 쓰는 타입)은 이번 라운드에도 약화하지
        않았다 — 여전히 빈 delta를 거부해야 한다."""

        from src.schemas.question import OptionRole

        with self.assertRaises(ValidationError):
            OptionRole(role_id="r1", primary_trait_delta={})

    def test_resolve_trait_signals_returns_exact_blueprint_no_signal(self) -> None:
        from src.services.trait_signal_registry import resolve_trait_signals

        bp = next(b for b in V2_DIRECT_PROBE_BLUEPRINTS if any(
            m.mapping_type == "NO_SIGNAL" for m in b.option_mappings
        ))
        no_signal_mapping = next(m for m in bp.option_mappings if m.mapping_type == "NO_SIGNAL")
        resolution = resolve_trait_signals(
            question_family_id="v2_direct_probe", blueprint_id=bp.blueprint_id,
            role_id=no_signal_mapping.role_id, legacy_primary_trait_delta={},
            is_resolution_question=False,
        )
        self.assertEqual(resolution.mapping_source, "EXACT_BLUEPRINT_NO_SIGNAL")
        self.assertEqual(resolution.signals, [])


class LLMDrivenDirectProbeTest(unittest.TestCase):
    """2단계 §13/§17 Persona 11~13, 2.1단계 §13 수정 — LLM 성공/실패/Quality Gate 실패
    각각에서도 Direct Probe가 항상 EXACT_BLUEPRINT를 얻는지 확인한다
    (LEGACY_PRIMARY_ADAPTER 의존 금지, §13). 2.1단계 수정: 이전 버전은 첫 Direct Probe
    질문을 LLM-off로 이미 서빙한 뒤에야 LLM Client를 교체하고 같은 질문을 다시
    요청했다 — 정상 흐름이 아니다. 이제는 세션 시작부터 끝까지 같은 FakeLLM Client
    하나만 쓰고, "첫 Direct Probe 질문 자체"가 이미 LLM 경로로 생성됐는지를 그 자리에서
    확인한다(재요청 없음)."""

    def _drive_to_first_v2_probe_question(self, fake_client) -> tuple[str, dict]:
        """세션 시작부터 `fake_client` 하나만 쓴다 — Legacy Tail 질문도 전부 이
        Client를 거친다. 첫 V2 Direct Probe 질문이 서빙되는 그 응답을 그대로 반환한다
        (그 질문에 아직 답하지 않은 상태 — 재요청하지 않는다)."""

        os.environ["ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES"] = "true"
        self.addCleanup(os.environ.pop, "ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", None)
        patcher = patch.object(main_module, "_llm_client", fake_client)
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
        for _ in range(60):
            r = client.post("/assessment/next-question", params={"session_id": session_id})
            body = r.json()
            if body["status"] == "CONTEXT_EARLY_TERMINATED":
                continue
            state = main_module._store.load(session_id)
            if state.current_question_family_id == "v2_direct_probe":
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

    def test_llm_success_gets_exact_blueprint_on_the_first_serve(self) -> None:
        session_id, body = self._drive_to_first_v2_probe_question(_SmartFakeLLMClient("success"))
        # 재요청 없이 "첫 서빙" 자체가 이미 LLM 경로여야 한다.
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

    def test_llm_always_fails_falls_back_to_base_question_on_the_first_serve(self) -> None:
        session_id, body = self._drive_to_first_v2_probe_question(_SmartFakeLLMClient("always_fail"))
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

    def test_quality_gate_failure_falls_back_to_base_question_on_the_first_serve(self) -> None:
        session_id, body = self._drive_to_first_v2_probe_question(_SmartFakeLLMClient("quality_gate_fail"))
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

    def test_repeated_next_question_without_answering_is_now_fully_idempotent(self) -> None:
        """2.1단계 §13에서 "재요청 시 LLM이 다시 호출되고 문구가 바뀔 수 있다"는 잔여
        위험으로만 보고했던 문제를 2.2단계 §11에서 실제로 고쳤다 — 이제 답하지 않은
        질문을 반복 요청하면 question_id·문구·Option까지 완전히 동일한 응답을 그대로
        돌려주고, LLM도 다시 호출하지 않는다(FakeLLM call_count로 확인)."""

        session_id, first_body = self._drive_to_first_v2_probe_question(_SmartFakeLLMClient("success"))
        state_after_first_serve = main_module._store.load(session_id)
        fake_client = main_module._llm_client
        call_count_after_first_serve = fake_client.call_count

        second_response = client.post("/assessment/next-question", params={"session_id": session_id})
        second_body = second_response.json()
        state_after_second_serve = main_module._store.load(session_id)

        self.assertEqual(first_body, second_body)
        self.assertEqual(fake_client.call_count, call_count_after_first_serve)
        self.assertEqual(
            state_after_second_serve.current_v2_probe_target_trait_id,
            state_after_first_serve.current_v2_probe_target_trait_id,
        )
        self.assertEqual(
            state_after_second_serve.current_question_blueprint_id,
            state_after_first_serve.current_question_blueprint_id,
        )


def _confirmed_session(preferred: list[str], final: tuple[str, ...] = ("game", "media", "school_life")) -> str:
    r = client.post("/assessment/session")
    session_id = r.json()["session_id"]
    client.post(
        "/assessment/interest-rating",
        json={"session_id": session_id, "ratings": {c: 5 for c in final}},
    )
    client.post(
        "/assessment/context-select",
        json={"session_id": session_id, "selected_preferred_context_ids": preferred},
    )
    client.post(
        "/assessment/context-confirm",
        json={"session_id": session_id, "final_context_ids": list(final)},
    )
    return session_id


class ExplorationContextAffinityTest(unittest.TestCase):
    """2.2단계 §1/§2 — Exploration Trait가 더 이상 trait_id 알파벳 순서에 고정되지
    않고, 학생의 Preferred Context·관심도에 따라 달라지는지 확인한다."""

    def test_creative_ideation_wins_with_game_media_preferred(self) -> None:
        candidates = select_v2_probe_candidates(
            {}, set(), final_contexts=_ALL_CONTEXTS, used_v2_probe_frame_ids=set(),
            preferred_context_ids=["game", "media"], interest_ratings={"game": 5, "media": 5},
        )
        self.assertEqual(candidates[0], "creative_ideation")

    def test_independent_judgment_wins_with_game_school_life_preferred(self) -> None:
        candidates = select_v2_probe_candidates(
            {}, set(), final_contexts=_ALL_CONTEXTS, used_v2_probe_frame_ids=set(),
            preferred_context_ids=["game", "school_life"], interest_ratings={"game": 5, "school_life": 5},
        )
        self.assertEqual(candidates[0], "independent_judgment")

    def test_media_school_life_tie_broken_by_higher_interest_rating(self) -> None:
        media_favored = select_v2_probe_candidates(
            {}, set(), final_contexts=_ALL_CONTEXTS, used_v2_probe_frame_ids=set(),
            preferred_context_ids=["media", "school_life"], interest_ratings={"media": 5, "school_life": 3},
        )
        self.assertEqual(media_favored[0], "creative_ideation")
        school_favored = select_v2_probe_candidates(
            {}, set(), final_contexts=_ALL_CONTEXTS, used_v2_probe_frame_ids=set(),
            preferred_context_ids=["media", "school_life"], interest_ratings={"media": 3, "school_life": 5},
        )
        self.assertEqual(school_favored[0], "independent_judgment")

    def test_media_school_life_interest_tie_broken_by_preferred_order(self) -> None:
        media_first = select_v2_probe_candidates(
            {}, set(), final_contexts=_ALL_CONTEXTS, used_v2_probe_frame_ids=set(),
            preferred_context_ids=["media", "school_life"], interest_ratings={"media": 5, "school_life": 5},
        )
        self.assertEqual(media_first[0], "creative_ideation")
        school_first = select_v2_probe_candidates(
            {}, set(), final_contexts=_ALL_CONTEXTS, used_v2_probe_frame_ids=set(),
            preferred_context_ids=["school_life", "media"], interest_ratings={"media": 5, "school_life": 5},
        )
        self.assertEqual(school_first[0], "independent_judgment")

    def test_no_preferred_link_falls_back_to_deterministic_trait_id_not_random(self) -> None:
        candidates = select_v2_probe_candidates(
            {}, set(), final_contexts=_ALL_CONTEXTS, used_v2_probe_frame_ids=set(),
            preferred_context_ids=[], interest_ratings={},
        )
        self.assertEqual(candidates[0], "creative_ideation")

    def test_independent_judgment_reachable_via_real_api_session(self) -> None:
        os.environ["ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES"] = "true"
        self.addCleanup(os.environ.pop, "ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", None)
        patcher = patch.object(main_module, "_llm_client", None)
        patcher.start()
        self.addCleanup(patcher.stop)

        session_id = _confirmed_session(["game", "school_life"], final=("game", "school_life", "media"))
        for _ in range(60):
            r = client.post("/assessment/next-question", params={"session_id": session_id})
            body = r.json()
            if body["status"] == "CONTEXT_EARLY_TERMINATED":
                if body["assessment_complete"]:
                    break
                continue
            question = body["question"]
            ar = client.post(
                "/assessment/answer",
                json={"session_id": session_id, "question_id": question["question_id"],
                      "selected_option_id": question["options"][0]["option_id"]},
            )
            if ar.json()["next_action"] == "ASSESSMENT_COMPLETE":
                break
        state = main_module._store.load(session_id)
        self.assertIn("independent_judgment", state.v2_probed_trait_ids)

    def test_creative_ideation_reachable_via_real_api_session(self) -> None:
        os.environ["ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES"] = "true"
        self.addCleanup(os.environ.pop, "ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", None)
        patcher = patch.object(main_module, "_llm_client", None)
        patcher.start()
        self.addCleanup(patcher.stop)

        session_id = _drive_full_session()  # 기본 Persona: preferred=[game, media]
        state = main_module._store.load(session_id)
        self.assertIn("creative_ideation", state.v2_probed_trait_ids)


class NextQuestionIdempotencyTest(unittest.TestCase):
    """2.2단계 §11 — 답하지 않은 질문을 다시 요청하면 저장된 응답을 그대로 돌려주고,
    LLM·Planner·Registry를 다시 부르지 않는다."""

    def setUp(self) -> None:
        os.environ["ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES"] = "true"
        self.addCleanup(os.environ.pop, "ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", None)

    def test_legacy_seed_replay_is_identical_and_does_not_advance_state(self) -> None:
        patcher = patch.object(main_module, "_llm_client", None)
        patcher.start()
        self.addCleanup(patcher.stop)
        session_id = _confirmed_session(["game", "media"])

        first = client.post("/assessment/next-question", params={"session_id": session_id}).json()
        state_after_first = main_module._store.load(session_id)
        second = client.post("/assessment/next-question", params={"session_id": session_id}).json()
        state_after_second = main_module._store.load(session_id)

        self.assertEqual(first, second)
        self.assertEqual(
            state_after_second.questions_asked_in_current_context,
            state_after_first.questions_asked_in_current_context,
        )

    def test_legacy_llm_tail_replay_does_not_call_llm_again(self) -> None:
        fake_client = _SmartFakeLLMClient("success")
        patcher = patch.object(main_module, "_llm_client", fake_client)
        patcher.start()
        self.addCleanup(patcher.stop)
        session_id = _confirmed_session(["game", "media"])

        # Seed(1번째)에 답해서 첫 Tail 질문(LLM 경로)까지 이동한다.
        seed_body = client.post("/assessment/next-question", params={"session_id": session_id}).json()
        seed_question = seed_body["question"]
        client.post(
            "/assessment/answer",
            json={"session_id": session_id, "question_id": seed_question["question_id"],
                  "selected_option_id": seed_question["options"][0]["option_id"]},
        )
        first = client.post("/assessment/next-question", params={"session_id": session_id}).json()
        self.assertEqual(first["status"], "GENERATED")
        call_count_after_first = fake_client.call_count

        second = client.post("/assessment/next-question", params={"session_id": session_id}).json()
        self.assertEqual(first, second)
        self.assertEqual(fake_client.call_count, call_count_after_first)

    def test_v2_direct_probe_llm_replay_does_not_call_llm_again(self) -> None:
        fake_client = _SmartFakeLLMClient("success")
        patcher = patch.object(main_module, "_llm_client", fake_client)
        patcher.start()
        self.addCleanup(patcher.stop)
        session_id = _confirmed_session(["game", "media"])

        first_body = None
        for _ in range(60):
            r = client.post("/assessment/next-question", params={"session_id": session_id})
            body = r.json()
            if body["status"] == "CONTEXT_EARLY_TERMINATED":
                continue
            state = main_module._store.load(session_id)
            if state.current_question_family_id == "v2_direct_probe":
                first_body = body
                break
            question = body["question"]
            ar = client.post(
                "/assessment/answer",
                json={"session_id": session_id, "question_id": question["question_id"],
                      "selected_option_id": question["options"][0]["option_id"]},
            )
            if ar.json()["next_action"] == "ASSESSMENT_COMPLETE":
                break
        self.assertIsNotNone(first_body, "V2 Direct Probe 질문에 도달하지 못했다")
        call_count_after_first_serve = fake_client.call_count

        second_body = client.post("/assessment/next-question", params={"session_id": session_id}).json()
        self.assertEqual(first_body, second_body)
        self.assertEqual(fake_client.call_count, call_count_after_first_serve)

    def test_v2_direct_probe_fallback_replay_is_identical_without_llm(self) -> None:
        patcher = patch.object(main_module, "_llm_client", None)
        patcher.start()
        self.addCleanup(patcher.stop)
        session_id = _confirmed_session(["game", "media"])

        first_body = None
        for _ in range(60):
            r = client.post("/assessment/next-question", params={"session_id": session_id})
            body = r.json()
            if body["status"] == "CONTEXT_EARLY_TERMINATED":
                continue
            state = main_module._store.load(session_id)
            if state.current_question_family_id == "v2_direct_probe":
                first_body = body
                break
            question = body["question"]
            ar = client.post(
                "/assessment/answer",
                json={"session_id": session_id, "question_id": question["question_id"],
                      "selected_option_id": question["options"][0]["option_id"]},
            )
            if ar.json()["next_action"] == "ASSESSMENT_COMPLETE":
                break
        self.assertIsNotNone(first_body, "V2 Direct Probe 질문에 도달하지 못했다")
        self.assertEqual(first_body["status"], "BACKUP_USED")

        second_body = client.post("/assessment/next-question", params={"session_id": session_id}).json()
        self.assertEqual(first_body, second_body)


class DuplicateAnswerRejectionTest(unittest.TestCase):
    """2.2단계 §13 — 같은 question_id로 답변을 두 번 제출해도 Evidence·Opportunity·
    질문 Count가 중복되지 않는다."""

    def setUp(self) -> None:
        os.environ["ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES"] = "true"
        self.addCleanup(os.environ.pop, "ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", None)
        patcher = patch.object(main_module, "_llm_client", None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_legacy_duplicate_answer_is_rejected_with_422_and_evidence_not_duplicated(self) -> None:
        session_id = _confirmed_session(["game", "media"])
        question = client.post("/assessment/next-question", params={"session_id": session_id}).json()["question"]
        payload = {
            "session_id": session_id, "question_id": question["question_id"],
            "selected_option_id": question["options"][0]["option_id"],
        }
        first = client.post("/assessment/answer", json=payload)
        self.assertEqual(first.status_code, 200)
        state = main_module._store.load(session_id)
        ledger_len_after_first = len(state.evidence_ledger)
        answers_len_after_first = len(state.answers)

        second = client.post("/assessment/answer", json=payload)
        self.assertEqual(second.status_code, 422)
        self.assertEqual(second.json()["detail"]["error_code"], "VALIDATION_ERROR")

        state_after_second = main_module._store.load(session_id)
        self.assertEqual(len(state_after_second.evidence_ledger), ledger_len_after_first)
        self.assertEqual(len(state_after_second.answers), answers_len_after_first)

    def test_v2_direct_probe_duplicate_answer_is_rejected_with_422_and_no_duplicate_opportunity(self) -> None:
        session_id = _confirmed_session(["game", "media"])
        question = None
        for _ in range(60):
            r = client.post("/assessment/next-question", params={"session_id": session_id})
            body = r.json()
            if body["status"] == "CONTEXT_EARLY_TERMINATED":
                continue
            state = main_module._store.load(session_id)
            if state.current_question_family_id == "v2_direct_probe":
                question = body["question"]
                break
            q = body["question"]
            ar = client.post(
                "/assessment/answer",
                json={"session_id": session_id, "question_id": q["question_id"],
                      "selected_option_id": q["options"][0]["option_id"]},
            )
            if ar.json()["next_action"] == "ASSESSMENT_COMPLETE":
                break
        self.assertIsNotNone(question, "V2 Direct Probe 질문에 도달하지 못했다")

        payload = {
            "session_id": session_id, "question_id": question["question_id"],
            "selected_option_id": question["options"][0]["option_id"],
        }
        first = client.post("/assessment/answer", json=payload)
        self.assertEqual(first.status_code, 200)
        state = main_module._store.load(session_id)
        opportunities_after_first = len(state.v2_probe_opportunities)
        questions_asked_after_first = state.v2_probe_questions_asked
        ledger_len_after_first = len(state.evidence_ledger)

        second = client.post("/assessment/answer", json=payload)
        self.assertEqual(second.status_code, 422)

        state_after_second = main_module._store.load(session_id)
        self.assertEqual(len(state_after_second.v2_probe_opportunities), opportunities_after_first)
        self.assertEqual(state_after_second.v2_probe_questions_asked, questions_asked_after_first)
        self.assertEqual(len(state_after_second.evidence_ledger), ledger_len_after_first)

    def test_wrong_option_id_rejection_keeps_current_question_answerable(self) -> None:
        """§12 — 잘못된 option_id로 거부된 답변은 current_question을 지우지 않는다.
        학생이 올바른 선택지로 다시 답할 수 있어야 한다."""

        session_id = _confirmed_session(["game", "media"])
        question = client.post("/assessment/next-question", params={"session_id": session_id}).json()["question"]

        bad = client.post(
            "/assessment/answer",
            json={"session_id": session_id, "question_id": question["question_id"], "selected_option_id": "bogus"},
        )
        self.assertEqual(bad.status_code, 422)
        state = main_module._store.load(session_id)
        self.assertIsNotNone(state.current_question)
        self.assertEqual(state.current_question.question_id, question["question_id"])

        good = client.post(
            "/assessment/answer",
            json={
                "session_id": session_id, "question_id": question["question_id"],
                "selected_option_id": question["options"][0]["option_id"],
            },
        )
        self.assertEqual(good.status_code, 200)


class NoSignalAnswerFlowTest(unittest.TestCase):
    """2.2단계 §6 — Direct Probe에서 NO_SIGNAL Option을 고르면 Evidence·Opportunity가
    올바르게 처리되는지 실제 /assessment/answer 경로로 확인한다."""

    def setUp(self) -> None:
        os.environ["ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES"] = "true"
        self.addCleanup(os.environ.pop, "ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", None)
        patcher = patch.object(main_module, "_llm_client", None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_no_signal_option_produces_empty_evidence_and_records_opportunity_only(self) -> None:
        from src.data.questions.trait_v2_direct_probe_blueprints import SYSTEMS_THINKING_GAME_V1

        session_id = _confirmed_session(["game", "media"])
        base_question = SYSTEMS_THINKING_GAME_V1.base_question.model_copy(
            update={"question_id": "q_test_no_signal"}
        )
        state = main_module._store.load(session_id)
        state.v2_probe_phase = "V2_DIRECT_PROBE"
        state.current_question = base_question
        state.current_question_family_id = "v2_direct_probe"
        state.current_question_blueprint_id = "systems_thinking_game_v1"
        state.current_v2_probe_target_trait_id = "systems_thinking"
        main_module._store.save(state)

        no_signal_option = next(o for o in base_question.options if o.role_id == "st_ask_team")
        response = client.post(
            "/assessment/answer",
            json={
                "session_id": session_id, "question_id": base_question.question_id,
                "selected_option_id": no_signal_option.option_id,
            },
        )
        self.assertEqual(response.status_code, 200)

        state = main_module._store.load(session_id)
        evidence = state.evidence_ledger[-1]
        self.assertEqual(evidence.evidence_origin, EvidenceOrigin.V2_DIRECT_PROBE)
        self.assertEqual(evidence.applied_primary_trait_delta, {})
        self.assertEqual(evidence.applied_trait_signals_v2, [])
        self.assertEqual(evidence.trait_signal_mapping_source_v2, "EXACT_BLUEPRINT_NO_SIGNAL")

        opportunity = state.v2_probe_opportunities[-1]
        self.assertFalse(opportunity.target_signal_selected)
        self.assertEqual(opportunity.target_trait_id, "systems_thinking")
        self.assertEqual(state.v2_probe_questions_asked, 1)

        entry = main_module._compute_v2_snapshot(state).get("systems_thinking")
        if entry is not None:
            self.assertEqual(entry.primary_evidence_count, 0)
            self.assertEqual(entry.related_evidence_count, 0)


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
