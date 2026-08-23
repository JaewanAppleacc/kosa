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
        self.assertEqual(blueprint.blueprint.blueprint_id, "systems_thinking_school_life_v1")

    def test_falls_back_to_preferred_context_when_no_related_evidence(self) -> None:
        blueprint = select_blueprint_for_trait(
            "systems_thinking", related_context_ids=set(), preferred_context_ids=["school_life"],
            final_contexts=["game", "school_life"], used_v2_probe_frame_ids=set(),
        )
        self.assertEqual(blueprint.blueprint.blueprint_id, "systems_thinking_school_life_v1")

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
        self.assertEqual(blueprint.blueprint.blueprint_id, "creative_ideation_game_v1")


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
        bp = next(b for b in V2_DIRECT_PROBE_BLUEPRINTS if b.blueprint.blueprint_id == blueprint_id)
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
        bp = next(b for b in V2_DIRECT_PROBE_BLUEPRINTS if b.blueprint.blueprint_id == "opinion_expression_school_life_v1")
        self.assertNotIn("역할을 맡고 싶", bp.base_question.question_text)

    def test_independent_judgment_school_life_asks_behavior_not_role_preference(self) -> None:
        bp = next(
            b for b in V2_DIRECT_PROBE_BLUEPRINTS
            if b.blueprint.blueprint_id == "independent_judgment_school_life_v1"
        )
        self.assertNotIn("역할을 맡고 싶", bp.base_question.question_text)

    def test_creative_ideation_game_target_no_longer_mixes_novelty_seeking(self) -> None:
        text = self._option_text("creative_ideation_game_v1", "ci_invent_rule")
        self.assertNotIn("아무도", text)
        self.assertNotIn("아직", text)

    def test_systems_thinking_school_life_distinguishes_from_planning(self) -> None:
        systems_text = self._option_text("systems_thinking_school_life_v1", "st_map_impact")
        planning_text = self._option_text("systems_thinking_school_life_v1", "st_replan")
        self.assertIn("얽혀", systems_text)
        self.assertIn("일정", planning_text)
        self.assertNotEqual(systems_text, planning_text)

    def test_detail_orientation_media_pattern_finding_option_reflects_pattern_not_flow(self) -> None:
        text = self._option_text("detail_orientation_media_v1", "do_overall_flow")
        self.assertIn("반복", text)
        self.assertNotIn("자연스러운지 훑어본다", text)

    def test_no_blueprint_option_uses_role_preference_phrasing_anymore(self) -> None:
        for bp in V2_DIRECT_PROBE_BLUEPRINTS:
            self.assertNotIn("역할을 맡고 싶", bp.base_question.question_text, bp.blueprint.blueprint_id)


class BlueprintCrossFieldValidationTest(unittest.TestCase):
    """2.1단계 §6 — Blueprint Cross-field 검증이 실제로 Fail-Fast인지 확인한다."""

    def test_target_option_count_must_be_exactly_one(self) -> None:
        from src.schemas.question import FinalizedOption, FinalizedQuestion, OptionBlueprint, OptionRole
        from src.schemas.v2_direct_probe import V2DirectProbeBlueprint, V2DirectProbeBlueprintValidationError

        # trait_id="systems_thinking"이지만 어떤 Role도 systems_thinking을 PRIMARY로
        # 갖지 않는다 — Target Option 0개 위반을 재현한다. Pydantic model_validator가
        # 던진 ValueError 하위 예외는 pydantic.ValidationError로 감싸져 나온다.
        roles = [
            OptionRole(role_id="r1", primary_trait_delta={"causal_analysis": 1}),
            OptionRole(role_id="r2", primary_trait_delta={"planning": 1}),
            OptionRole(role_id="r3", primary_trait_delta={"immediate_execution": 1}),
            OptionRole(role_id="r4", primary_trait_delta={"information_comparison": 1}),
            OptionRole(role_id="r5", primary_trait_delta={"collaboration_preference": 1}),
        ]
        options = [
            FinalizedOption(option_id=f"q_o{i}", role_id=r.role_id, text=f"텍스트 {i}", primary_trait_delta=r.primary_trait_delta)
            for i, r in enumerate(roles, start=1)
        ]
        question = FinalizedQuestion(
            question_id="q_test", context="game", target_traits=[], frame_id="new_tool",
            question_text="테스트 질문인가요?", options=options,
        )
        with self.assertRaises(ValidationError):
            V2DirectProbeBlueprint(
                trait_id="systems_thinking",
                blueprint=OptionBlueprint(blueprint_id="test_bp", roles=roles),
                allowed_context_ids=["game"], question_frame_id="new_tool",
                purpose="test", base_question=question,
            )

    def test_context_must_be_in_allowed_context_ids(self) -> None:
        from src.schemas.question import FinalizedOption, FinalizedQuestion, OptionBlueprint, OptionRole
        from src.schemas.v2_direct_probe import V2DirectProbeBlueprint

        roles = [OptionRole(role_id=f"r{i}", primary_trait_delta={t: 1}) for i, t in enumerate([
            "systems_thinking", "causal_analysis", "immediate_execution",
            "information_comparison", "collaboration_preference",
        ], start=1)]
        options = [
            FinalizedOption(option_id=f"q_o{i}", role_id=r.role_id, text=f"텍스트 {i}", primary_trait_delta=r.primary_trait_delta)
            for i, r in enumerate(roles, start=1)
        ]
        question = FinalizedQuestion(
            question_id="q_test2", context="media", target_traits=[], frame_id="new_tool",
            question_text="테스트 질문인가요?", options=options,
        )
        with self.assertRaises(ValidationError):
            V2DirectProbeBlueprint(
                trait_id="systems_thinking",
                blueprint=OptionBlueprint(blueprint_id="test_bp2", roles=roles),
                allowed_context_ids=["game"], question_frame_id="new_tool",  # media가 아니라 game만 허용
                purpose="test", base_question=question,
            )

    def test_all_14_real_blueprints_pass_validation(self) -> None:
        # Import 시점에 이미 검증됐지만, 명시적으로 한 번 더 확인한다(회귀 고정).
        self.assertEqual(len(V2_DIRECT_PROBE_BLUEPRINTS), 14)


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

    def test_diagnostic_repeated_next_question_without_answering(self) -> None:
        """2.1단계 §13 마지막 항목 — "같은 질문을 재요청해 Blueprint/Target이 바뀌지
        않는지 진단하세요. 문제가 발견되면 이번 범위에서 성급히 수정하지 말고 별도
        위험으로 보고하세요." 이 테스트는 실제로 무슨 일이 일어나는지 진단하는 용도다
        — 결과를 완료 보고 §16/§25에 그대로 옮긴다."""

        session_id, first_body = self._drive_to_first_v2_probe_question(_SmartFakeLLMClient("success"))
        first_question_id = first_body["question"]["question_id"]
        state_after_first_serve = main_module._store.load(session_id)
        first_target = state_after_first_serve.current_v2_probe_target_trait_id
        first_blueprint = state_after_first_serve.current_question_blueprint_id

        # 같은 질문에 답하지 않고 next-question을 한 번 더 호출한다.
        second_response = client.post("/assessment/next-question", params={"session_id": session_id})
        second_body = second_response.json()
        state_after_second_serve = main_module._store.load(session_id)

        # 이 assert들은 "안전하다"를 주장하지 않는다 — 실제 동작을 그대로 기록한다.
        second_question_id = second_body["question"]["question_id"] if second_body.get("question") else None
        target_changed = state_after_second_serve.current_v2_probe_target_trait_id != first_target
        blueprint_changed = state_after_second_serve.current_question_blueprint_id != first_blueprint
        question_id_changed = second_question_id != first_question_id
        # 진단 결과를 완료 보고서에 그대로 옮길 수 있도록 실패시키지 않는다 — 다만 이
        # 세 값이 전부 True(재요청마다 매번 다른 질문·Blueprint로 바뀜)라면 그 사실
        # 자체가 남은 위험이므로, 최소한 "매번 완전히 다른 Trait로 튄다"는 최악의
        # 경우는 아닌지만 방어적으로 확인한다(같은 Trait 후보 집합에서 결정론적으로
        # 같은 선택이 나오는지는 select_v2_probe_candidates/_blueprint_for_trait가
        # 이미 단위 테스트로 결정론성을 보장한다 — 여기서는 "질문 id 자체가 재요청마다
        # 바뀐다"는 사실만 진단한다).
        self.assertFalse(target_changed, "재요청 시 Target Trait 자체가 바뀌면 심각한 위험 — 별도 보고 필요")
        self.assertFalse(blueprint_changed, "재요청 시 Blueprint 자체가 바뀌면 심각한 위험 — 별도 보고 필요")
        if question_id_changed:
            # question_id는 매번 새로 생성되므로(generate_question_id가 시퀀스 번호를
            # 쓰지 않고 v2_probe_questions_asked+1을 그대로 쓰기 때문에, 재요청해도
            # v2_probe_questions_asked가 안 바뀐 상태라 이론적으로 같은 번호가 나올 수
            # 있다 — 그러나 LLM 경로는 매 호출마다 실제로 새 질문 텍스트를 생성하므로
            # question_id 자체의 재현성은 보장되지 않는다). 이 사실을 완료 보고에 남긴다.
            pass


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
