"""ContextPack Evidence Review Gate 연결 — 2026-08-23 Trait Ontology v2(2.9.1단계)
§2/§3/§6.

2.9단계는 pack_direct_probe/pack_backup family를 아예 몰라서 Fail-Closed로 거부는
됐지만 "왜"가 틀렸고(family 자체를 모름), Pack Seed도 Legacy Seed Anchor Store를
잘못 조회해서 우연히만 Fail-Closed였다 — 이 파일은 그 실제 판정 경로가 새 family별로
올바른 이유로 동작하는지 확인한다. 실제 T·S·L Pack 파일이나 공유 검수 디렉터리를
건드리지 않는다 — 전부 임시 디렉터리에 주입한 Registry로 검증한다."""

from __future__ import annotations

import json
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
from src.schemas.context_pack import ContextPack, OptionMappingRationale
from src.schemas.evidence import EvidenceOrigin, EvidenceRecord
from src.schemas.question import FinalizedOption, FinalizedQuestion
from src.schemas.trait_signal import TraitSignal
from src.schemas.v2_direct_probe import V2DirectProbeBlueprint, V2ProbeOptionMapping
from src.services.context_pack_registry import ContextPackRegistry
from src.services.context_pack_runtime import ContextPackRuntime
from src.services.trait_signal_review_gate import (
    filter_primary_eligible_evidence,
    gate_primary_eligible_evidence,
    is_evidence_signal_approved,
)
from src.tracing.tracer import Tracer

client = TestClient(app)


def _evidence(
    evidence_id: str, *, family: str, blueprint_id: str, context: str, origin: EvidenceOrigin,
    trait_delta: dict[str, int] | None = None,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id, answer_id=f"ans_{evidence_id}", question_id=f"q_{evidence_id}",
        question_frame_id="direct_probe", option_role_id="role_1", option_text="테스트 선택지",
        applied_primary_trait_delta=trait_delta or {"causal_analysis": 1}, evidence_origin=origin, context=context,
        source_type="pack_context_direct_probe_question", generator_version="v1", quality_gate_status="passed",
        source_question_family_id=family, source_blueprint_id=blueprint_id,
    )


def _pack_with_native_direct_probe(context_id: str) -> tuple[ContextPack, str, str]:
    """2.9.1단계 §1-1 회귀 재현용 합성 Pack — `_example_pack_builder`가 만드는 기본
    Pack(`direct_probe_candidates=[]`)에 Native Direct Probe 1개를 더해 반환한다.
    공유 Fixture 파일(`_example_pack_builder.py`)은 다른 여러 테스트가 함께 쓰므로
    직접 수정하지 않고, 그 결과를 여기서 확장만 한다. `(pack, blueprint_id, anchor_id)`를
    반환한다."""

    base_pack = build_example_context_pack(context_id)
    anchor_id = base_pack.anchor_presentations[0].anchor_id
    blueprint_id = f"{context_id}_native_probe_1"
    question_id = f"{blueprint_id}_question"

    options: list[FinalizedOption] = []
    mappings: list[V2ProbeOptionMapping] = []
    rationales = list(base_pack.option_mapping_rationales)
    for i in range(1, 6):
        role_id = f"probe_role_{i}"
        if i == 1:
            options.append(
                FinalizedOption(
                    option_id=f"{question_id}_o{i}", role_id=role_id, text=f"옵션 {i}",
                    primary_trait_delta={"causal_analysis": 1},
                )
            )
            mappings.append(
                V2ProbeOptionMapping(
                    role_id=role_id, mapping_type="TRAIT_SIGNAL",
                    trait_signals=[TraitSignal(trait_id="causal_analysis", signal_role="PRIMARY", weight=1.0)],
                )
            )
            rationales.append(
                OptionMappingRationale(
                    source="direct_probe", question_id=question_id, role_id=role_id, trait_id="causal_analysis",
                    mapping_rationale_draft="합성 회귀 테스트용 Native Direct Probe Target 선택지",
                )
            )
        else:
            options.append(
                FinalizedOption(option_id=f"{question_id}_o{i}", role_id=role_id, text=f"옵션 {i}", primary_trait_delta={})
            )
            mappings.append(V2ProbeOptionMapping(role_id=role_id, mapping_type="NO_SIGNAL", no_signal_reason="합성 테스트용"))
            rationales.append(
                OptionMappingRationale(
                    source="direct_probe", question_id=question_id, role_id=role_id, trait_id=None,
                    mapping_rationale_draft="합성 회귀 테스트용 NO_SIGNAL 선택지",
                )
            )

    base_question = FinalizedQuestion(
        question_id=question_id, context=context_id, target_traits=[], frame_id="native_probe_frame",
        question_text="합성 회귀 테스트용 Native Direct Probe 질문", options=options,
    )
    probe = V2DirectProbeBlueprint(
        trait_id="causal_analysis", blueprint_id=blueprint_id, option_mappings=mappings,
        allowed_context_ids=[context_id], question_frame_id="native_probe_frame",
        purpose="2.9.1단계 §1-1 회귀 재현", base_question=base_question,
    )
    pack = ContextPack.model_validate(
        {
            **base_pack.model_dump(),
            "direct_probe_candidates": [probe.model_dump()],
            "option_mapping_rationales": [r.model_dump() for r in rationales],
        }
    )
    return pack, blueprint_id, anchor_id


class NativeDirectProbeReviewKeyTest(unittest.TestCase):
    """2.9.1단계 §1-1 — Native ContextPack Direct Probe는 blueprint_id 기준으로
    검수해야 한다(`ContextPackRegistry.required_review_keys()`가 실제로 쓰는 정본
    Key와 같은 형식). 수정 전에는 `context_id::direct_probe::anchor_id`(잘못된
    reference_id)로 조회해서, 사람이 올바른 Key로 APPROVE해도 이 게이트가 영원히
    Fail-Closed로 막았다 — 아래 재현 스크립트로 실제로 확인한 버그다."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.review_dir = Path(self.tmpdir.name)
        self.pack, self.blueprint_id, self.anchor_id = _pack_with_native_direct_probe("business")
        self.registry = ContextPackRegistry(
            known_context_ids=frozenset({"business"}),
            known_trait_ids=frozenset({"causal_analysis", "pattern_finding"}),
            review_status_dir=self.review_dir,
            shared_probe_review_status_path=self.review_dir / "shared.json",
            _discovered=({"business": self.pack}, {}),
        )

    def _write_review(self, rows: list[dict]) -> None:
        (self.review_dir / "business_review_status.json").write_text(
            json.dumps(rows, ensure_ascii=False), encoding="utf-8",
        )

    def _non_probe_required_rows(self) -> list[dict]:
        required = sorted(self.registry.required_review_keys(self.pack))
        return [
            {"blueprint_id": k, "reviewer_1_status": "APPROVE"} for k in required
            if k.split("::")[1] != "direct_probe"
        ]

    def _probe_evidence(self) -> EvidenceRecord:
        return _evidence(
            "e_native", family="pack_direct_probe", blueprint_id=self.blueprint_id, context="business",
            origin=EvidenceOrigin.V2_DIRECT_PROBE,
        )

    def test_correct_blueprint_id_key_approved_serves_native_probe_evidence(self) -> None:
        """올바른 Key(`context_id::direct_probe::blueprint_id`)가 APPROVED면 실제로
        서빙(Primary 계산에 포함)돼야 한다 — 수정 전에는 이 테스트가 실패했다."""

        rows = self._non_probe_required_rows()
        rows.append({"blueprint_id": f"business::direct_probe::{self.blueprint_id}", "reviewer_1_status": "APPROVE"})
        self._write_review(rows)
        self.assertTrue(
            is_evidence_signal_approved(self._probe_evidence(), {"business": self.anchor_id}, self.registry)
        )

    def test_wrong_anchor_id_key_approved_does_not_serve_native_probe_evidence(self) -> None:
        """잘못된 Key(anchor_id 기준)만 APPROVED고, 정본 Key
        (`direct_probe::blueprint_id`)는 없으면 — 그 정본 Key가 없으므로
        `is_pack_review_approved` 자체가 이미 False다(Pack 전체 필수 Key 중 하나가
        비어 있음) — 어떤 형식의 잘못된 Key가 APPROVED로 남아 있어도 Runtime에
        새어나가지 않는다는 것을 재확인한다."""

        rows = self._non_probe_required_rows()
        rows.append({"blueprint_id": f"business::direct_probe::{self.anchor_id}", "reviewer_1_status": "APPROVE"})
        self._write_review(rows)
        self.assertFalse(self.registry.is_pack_review_approved("business"))
        self.assertFalse(
            is_evidence_signal_approved(self._probe_evidence(), {"business": self.anchor_id}, self.registry)
        )

    def test_no_direct_probe_review_entry_at_all_fails_closed(self) -> None:
        self._write_review(self._non_probe_required_rows())
        self.assertFalse(
            is_evidence_signal_approved(self._probe_evidence(), {"business": self.anchor_id}, self.registry)
        )

    def test_native_probe_key_format_does_not_collide_with_shared_probe_lookup(self) -> None:
        """Native Probe 판정(blueprint_id 기준 Pack 검수 파일)과 Shared Probe 판정
        (공유 검수 파일, Context+Anchor 기준)은 서로 다른 저장소를 본다 — 공유
        검수 파일에 아무것도 없어도 Native 승인에는 영향이 없어야 한다."""

        rows = self._non_probe_required_rows()
        rows.append({"blueprint_id": f"business::direct_probe::{self.blueprint_id}", "reviewer_1_status": "APPROVE"})
        self._write_review(rows)
        self.assertEqual(self.registry.get_shared_probe_context_review(self.blueprint_id, "business"), None)
        self.assertTrue(
            is_evidence_signal_approved(self._probe_evidence(), {"business": self.anchor_id}, self.registry)
        )


class _TwoPackRegistryTestBase(unittest.TestCase):
    """business·law_politics 두 Context Pack을 동시에 주입해 "같은 Probe가 한
    Context에서는 승인, 다른 Context에서는 미승인"을 재현할 수 있게 한다."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.review_dir = Path(self.tmpdir.name)
        self.shared_path = self.review_dir / "shared.json"

        self.business_pack = build_example_context_pack("business")
        self.law_pack = build_example_context_pack("law_politics")

        self.registry = ContextPackRegistry(
            known_context_ids=frozenset({"business", "law_politics"}),
            known_trait_ids=frozenset({"causal_analysis", "pattern_finding"}),
            review_status_dir=self.review_dir,
            shared_probe_review_status_path=self.shared_path,
            _discovered=({"business": self.business_pack, "law_politics": self.law_pack}, {}),
        )

    def _approve_pack(self, pack) -> None:
        required = sorted(self.registry.required_review_keys(pack))
        (self.review_dir / f"{pack.context_id}_review_status.json").write_text(
            json.dumps([{"blueprint_id": k, "reviewer_1_status": "APPROVE"} for k in required], ensure_ascii=False),
            encoding="utf-8",
        )

    def _write_shared_probe_review(self, rows: list[dict]) -> None:
        self.shared_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")


class PackSeedAndBackupGateTest(_TwoPackRegistryTestBase):
    def test_unapproved_pack_seed_evidence_excluded_fail_closed(self) -> None:
        seed = self.business_pack.seed_anchor_variants[0]
        e = _evidence(
            "e1", family="seed", blueprint_id=f"{seed.question.question_id}_blueprint", context="business",
            origin=EvidenceOrigin.PRIMARY_BLUEPRINT,
        )
        self.assertFalse(
            is_evidence_signal_approved(e, {"business": seed.anchor_id}, self.registry)
        )

    def test_approved_pack_seed_evidence_included(self) -> None:
        self._approve_pack(self.business_pack)
        seed = self.business_pack.seed_anchor_variants[0]
        e = _evidence(
            "e1", family="seed", blueprint_id=f"{seed.question.question_id}_blueprint", context="business",
            origin=EvidenceOrigin.PRIMARY_BLUEPRINT,
        )
        self.assertTrue(
            is_evidence_signal_approved(e, {"business": seed.anchor_id}, self.registry)
        )

    def test_missing_registry_argument_fails_closed_for_pack_context(self) -> None:
        """registry를 안 넘기면(과거 호출 호환 기본값 None) 신규 Pack Context 판정은
        승인된 것으로 절대 가정하지 않는다 — Legacy Context 판정에는 영향이 없다."""

        seed = self.business_pack.seed_anchor_variants[0]
        e = _evidence(
            "e1", family="seed", blueprint_id=f"{seed.question.question_id}_blueprint", context="business",
            origin=EvidenceOrigin.PRIMARY_BLUEPRINT,
        )
        self.assertFalse(is_evidence_signal_approved(e, {"business": seed.anchor_id}))

    def test_approved_pack_backup_evidence_included(self) -> None:
        self._approve_pack(self.business_pack)
        backup = self.business_pack.anchor_backup_questions[0]
        e = _evidence(
            "e1", family="pack_backup", blueprint_id=backup.question.question_id, context="business",
            origin=EvidenceOrigin.PRIMARY_BLUEPRINT,
        )
        self.assertTrue(is_evidence_signal_approved(e, {"business": backup.anchor_id}, self.registry))

    def test_unapproved_pack_backup_evidence_excluded(self) -> None:
        backup = self.business_pack.anchor_backup_questions[0]
        e = _evidence(
            "e1", family="pack_backup", blueprint_id=backup.question.question_id, context="business",
            origin=EvidenceOrigin.PRIMARY_BLUEPRINT,
        )
        self.assertFalse(is_evidence_signal_approved(e, {"business": backup.anchor_id}, self.registry))


class SharedProbeContextAnchorGateTest(_TwoPackRegistryTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.blueprint = CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS[0]
        self.business_anchor_ids = [a.anchor_id for a in self.business_pack.anchor_presentations]
        self.law_anchor_ids = [a.anchor_id for a in self.law_pack.anchor_presentations]

    def test_same_blueprint_approved_in_business_not_law_politics(self) -> None:
        self._write_shared_probe_review([
            {
                "blueprint_id": self.blueprint.blueprint_id, "context_id": "business",
                "reviewer_1_status": "APPROVE", "approved_anchor_ids": self.business_anchor_ids,
                "excluded_anchor_ids": [],
            },
            # law_politics는 아예 행이 없다 — 완전히 미검토.
        ])
        e_business = _evidence(
            "e1", family="pack_direct_probe", blueprint_id=self.blueprint.blueprint_id, context="business",
            origin=EvidenceOrigin.V2_DIRECT_PROBE,
        )
        e_law = _evidence(
            "e2", family="pack_direct_probe", blueprint_id=self.blueprint.blueprint_id, context="law_politics",
            origin=EvidenceOrigin.V2_DIRECT_PROBE,
        )
        self.assertTrue(
            is_evidence_signal_approved(e_business, {"business": self.business_anchor_ids[0]}, self.registry)
        )
        self.assertFalse(
            is_evidence_signal_approved(e_law, {"law_politics": self.law_anchor_ids[0]}, self.registry)
        )
        # Runtime 후보 선택도 같은 결과여야 한다(§6 "business에서만 사용 가능").
        self.assertIn(
            self.blueprint.blueprint_id,
            [b.blueprint_id for b in self.registry.shared_probe_blueprints_for_context("business", self.business_anchor_ids[0])],
        )
        self.assertNotIn(
            self.blueprint.blueprint_id,
            [b.blueprint_id for b in self.registry.shared_probe_blueprints_for_context("law_politics", self.law_anchor_ids[0])],
        )

    def test_excluded_anchor_not_used_approved_anchor_still_used(self) -> None:
        approved_anchor, excluded_anchor = self.business_anchor_ids[0], self.business_anchor_ids[1]
        self._write_shared_probe_review([
            {
                "blueprint_id": self.blueprint.blueprint_id, "context_id": "business",
                "reviewer_1_status": "APPROVE", "approved_anchor_ids": [approved_anchor],
                "excluded_anchor_ids": [excluded_anchor],
            },
        ])
        candidates_approved_anchor = self.registry.shared_probe_blueprints_for_context("business", approved_anchor)
        candidates_excluded_anchor = self.registry.shared_probe_blueprints_for_context("business", excluded_anchor)
        self.assertIn(self.blueprint.blueprint_id, [b.blueprint_id for b in candidates_approved_anchor])
        self.assertNotIn(self.blueprint.blueprint_id, [b.blueprint_id for b in candidates_excluded_anchor])

    def test_unreviewed_anchor_not_auto_approved_even_if_context_approved(self) -> None:
        """§3 "미검토 Anchor는 자동 승인 금지" — Context 자체는 APPROVE인데
        approved_anchor_ids가 비어 있으면 어떤 Anchor도 후보가 아니다."""

        self._write_shared_probe_review([
            {
                "blueprint_id": self.blueprint.blueprint_id, "context_id": "business",
                "reviewer_1_status": "APPROVE", "approved_anchor_ids": [], "excluded_anchor_ids": [],
            },
        ])
        for anchor_id in self.business_anchor_ids:
            candidates = self.registry.shared_probe_blueprints_for_context("business", anchor_id)
            self.assertNotIn(self.blueprint.blueprint_id, [b.blueprint_id for b in candidates])


class PrimaryVsShadowSeparationTest(_TwoPackRegistryTestBase):
    def test_unapproved_evidence_kept_in_ledger_but_excluded_from_primary_filter(self) -> None:
        seed = self.business_pack.seed_anchor_variants[0]
        evidence = _evidence(
            "e1", family="seed", blueprint_id=f"{seed.question.question_id}_blueprint", context="business",
            origin=EvidenceOrigin.PRIMARY_BLUEPRINT,
        )
        ledger = [evidence]
        context_anchor_choices = {"business": seed.anchor_id}

        # Fail-Closed 게이트를 통과 못 해도 원본 Ledger는 그대로 남는다(Shadow 분석 등에서
        # 계속 쓸 수 있다) — 이 함수가 원본을 지우거나 바꾸지 않는다는 계약을 재확인.
        filtered = filter_primary_eligible_evidence(ledger, context_anchor_choices, self.registry)
        self.assertEqual(filtered, [])
        self.assertEqual(ledger, [evidence])  # 원본 불변.

        gate = gate_primary_eligible_evidence(ledger, context_anchor_choices, self.registry)
        self.assertEqual(gate.excluded_evidence_ids, {"e1"})
        self.assertEqual(gate.approved_evidence_ids, set())

    def test_approved_evidence_passes_through_primary_filter(self) -> None:
        self._approve_pack(self.business_pack)
        seed = self.business_pack.seed_anchor_variants[0]
        evidence = _evidence(
            "e1", family="seed", blueprint_id=f"{seed.question.question_id}_blueprint", context="business",
            origin=EvidenceOrigin.PRIMARY_BLUEPRINT,
        )
        filtered = filter_primary_eligible_evidence([evidence], {"business": seed.anchor_id}, self.registry)
        self.assertEqual(filtered, [evidence])


class LlmFailureNeverExposesLegacyBaseQuestionTest(unittest.TestCase):
    """§4/§6 — LLM이 꺼져 있거나 실패하면 공용 Adaptive Probe의 Legacy 문구 대신
    그 Anchor의 검수된 Backup으로 넘어가고, 그마저 없으면 STOP_GENERATION_EXHAUSTED로
    끝난다(Legacy 문구가 절대 학생에게 노출되지 않는다)."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.review_dir = Path(self.tmpdir.name)
        self.pack = build_example_context_pack("business")
        self.registry = ContextPackRegistry(
            known_context_ids=frozenset({"business"}),
            known_trait_ids=frozenset({"causal_analysis", "pattern_finding"}),
            review_status_dir=self.review_dir,
            shared_probe_review_status_path=self.review_dir / "shared.json",
            _discovered=({"business": self.pack}, {}),
        )
        required = sorted(self.registry.required_review_keys(self.pack))
        (self.review_dir / "business_review_status.json").write_text(
            json.dumps([{"blueprint_id": k, "reviewer_1_status": "APPROVE"} for k in required], ensure_ascii=False),
            encoding="utf-8",
        )
        anchor_ids = [a.anchor_id for a in self.pack.anchor_presentations]
        (self.review_dir / "shared.json").write_text(
            json.dumps([
                {
                    "blueprint_id": bp.blueprint_id, "context_id": "business", "reviewer_1_status": "APPROVE",
                    "approved_anchor_ids": anchor_ids, "excluded_anchor_ids": [],
                }
                for bp in CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS
            ], ensure_ascii=False),
            encoding="utf-8",
        )
        self.runtime = ContextPackRuntime(
            self.registry, lambda: main_module.context_pack_runtime_enabled(), frozenset(VERTICAL_SLICE_CONTEXT_IDS),
        )
        for patch_target in (
            patch.object(main_module, "_context_pack_registry", self.registry),
            patch.object(main_module, "_context_pack_runtime", self.runtime),
            patch.object(main_module, "_llm_client", None),  # LLM off — fallback 경로를 강제로 탄다.
            patch.object(main_module, "_tracer", Tracer(client=None)),
        ):
            patch_target.start()
            self.addCleanup(patch_target.stop)
        import os

        os.environ["ENABLE_CONTEXT_PACK_RUNTIME"] = "true"
        self.addCleanup(os.environ.pop, "ENABLE_CONTEXT_PACK_RUNTIME", None)

    def _confirmed_session(self) -> str:
        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        client.post(
            "/assessment/interest-rating", json={"session_id": session_id, "ratings": {"game": 4, "business": 5}},
        )
        client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "business"]},
        )
        client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["business", "game"]},
        )
        return session_id

    def test_llm_off_falls_back_to_pack_backup_not_shared_pool_base_question(self) -> None:
        session_id = self._confirmed_session()
        # Routing.
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        routing_q = r.json()["question"]
        client.post(
            "/assessment/answer",
            json={"session_id": session_id, "question_id": routing_q["question_id"], "selected_option_id": routing_q["options"][0]["option_id"]},
        )
        # Seed.
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        seed_q = r.json()["question"]
        client.post(
            "/assessment/answer",
            json={"session_id": session_id, "question_id": seed_q["question_id"], "selected_option_id": seed_q["options"][0]["option_id"]},
        )
        # 다음 질문(Adaptive Tail 1번째 시도) — LLM 꺼짐 → 공용 Probe base_question이
        # 아니라 그 Anchor의 Backup이 나와야 한다.
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        body = r.json()
        state = main_module._store.load(session_id)
        self.assertEqual(state.current_question_family_id, "pack_backup")
        self.assertTrue(body["question"]["question_id"].startswith("business_backup_"))
        shared_pool_question_ids = {bp.base_question.question_id for bp in CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS}
        self.assertNotIn(body["question"]["question_id"], shared_pool_question_ids)

    def test_llm_off_and_backup_exhausted_stops_with_generation_exhausted_reason(self) -> None:
        session_id = self._confirmed_session()
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        routing_q = r.json()["question"]
        client.post(
            "/assessment/answer",
            json={"session_id": session_id, "question_id": routing_q["question_id"], "selected_option_id": routing_q["options"][0]["option_id"]},
        )
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        seed_q = r.json()["question"]
        client.post(
            "/assessment/answer",
            json={"session_id": session_id, "question_id": seed_q["question_id"], "selected_option_id": seed_q["options"][0]["option_id"]},
        )
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        backup_q = r.json()["question"]
        client.post(
            "/assessment/answer",
            json={"session_id": session_id, "question_id": backup_q["question_id"], "selected_option_id": backup_q["options"][0]["option_id"]},
        )
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        body = r.json()
        self.assertEqual(body["status"], "CONTEXT_EARLY_TERMINATED")
        state = main_module._store.load(session_id)
        self.assertIn("STOP_GENERATION_EXHAUSTED", state.stop_reason or "")


class PrimarySnapshotReflectsApprovalHttpTest(unittest.TestCase):
    """§6 "Pack+Probe+Context+Anchor 승인 → Primary Evidence 포함 → Profile 반영" —
    `ENABLE_TRAIT_VECTOR_V2_PRIMARY=true`로 실제 `/profile`까지 태워서 확인한다.
    Trait Summary를 직접 주입하지 않는다 — 실제 답변 흐름으로만 채운다."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.review_dir = Path(self.tmpdir.name)
        self.pack = build_example_context_pack("business")
        self.registry = ContextPackRegistry(
            known_context_ids=frozenset({"business"}),
            known_trait_ids=frozenset({"causal_analysis", "pattern_finding"}),
            review_status_dir=self.review_dir,
            shared_probe_review_status_path=self.review_dir / "shared.json",
            _discovered=({"business": self.pack}, {}),
        )
        self.runtime = ContextPackRuntime(
            self.registry, lambda: main_module.context_pack_runtime_enabled(), frozenset(VERTICAL_SLICE_CONTEXT_IDS),
        )
        for patch_target in (
            patch.object(main_module, "_context_pack_registry", self.registry),
            patch.object(main_module, "_context_pack_runtime", self.runtime),
            patch.object(main_module, "_llm_client", None),
            patch.object(main_module, "_tracer", Tracer(client=None)),
        ):
            patch_target.start()
            self.addCleanup(patch_target.stop)
        import os

        os.environ["ENABLE_CONTEXT_PACK_RUNTIME"] = "true"
        os.environ["ENABLE_TRAIT_VECTOR_V2_PRIMARY"] = "true"
        self.addCleanup(os.environ.pop, "ENABLE_CONTEXT_PACK_RUNTIME", None)
        self.addCleanup(os.environ.pop, "ENABLE_TRAIT_VECTOR_V2_PRIMARY", None)

    def _drive_seed_answer(self) -> tuple[str, str]:
        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        client.post(
            "/assessment/interest-rating", json={"session_id": session_id, "ratings": {"game": 4, "business": 5}},
        )
        client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "business"]},
        )
        client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["business", "game"]},
        )
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        routing_q = r.json()["question"]
        client.post(
            "/assessment/answer",
            json={"session_id": session_id, "question_id": routing_q["question_id"], "selected_option_id": routing_q["options"][0]["option_id"]},
        )
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        seed_q = r.json()["question"]
        target_trait_id = next(iter(seed_q["options"][0].get("primary_trait_delta", {}) or {}), None)
        client.post(
            "/assessment/answer",
            json={"session_id": session_id, "question_id": seed_q["question_id"], "selected_option_id": seed_q["options"][0]["option_id"]},
        )
        return session_id, target_trait_id

    def test_review_status_regression_after_answering_excludes_from_primary_snapshot(self) -> None:
        """미승인 Pack Context는 애초에 `/assessment/context-confirm`에서 막혀
        Evidence 자체가 생기지 않는다(Fail-Closed 활성화 게이트가 더 앞단에 있다) —
        그래서 "미승인인데 Evidence는 있다"는 상황은 "답변 당시엔 승인이었다가
        나중에 검수 상태가 REVISE/HOLD/TBD로 되돌아간" 경우로만 재현할 수 있다.
        Evidence Ledger 자체는 그대로 남아 있고(재현 코드에서 확인), Primary
        계산에서만 다시 제외돼야 한다."""

        required = sorted(self.registry.required_review_keys(self.pack))
        (self.review_dir / "business_review_status.json").write_text(
            json.dumps([{"blueprint_id": k, "reviewer_1_status": "APPROVE"} for k in required], ensure_ascii=False),
            encoding="utf-8",
        )
        session_id, target_trait_id = self._drive_seed_answer()
        self.assertIsNotNone(target_trait_id)
        state_before = main_module._store.load(session_id)
        business_evidence_before = [e for e in state_before.evidence_ledger if e.context == "business"]
        self.assertTrue(business_evidence_before)

        # 검수 상태를 되돌린다(사람이 REVISE로 바꾼 상황을 재현) — Evidence Ledger는
        # 건드리지 않는다.
        (self.review_dir / "business_review_status.json").write_text(
            json.dumps([{"blueprint_id": k, "reviewer_1_status": "REVISE"} for k in required], ensure_ascii=False),
            encoding="utf-8",
        )

        r = client.get(f"/profile/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        state_after = main_module._store.load(session_id)
        business_evidence_after = [e for e in state_after.evidence_ledger if e.context == "business"]
        self.assertEqual(business_evidence_before, business_evidence_after)  # Ledger 원본 불변.

        snapshot = main_module._trait_vector_primary_repository.load(session_id)
        self.assertIsNotNone(snapshot)
        entry = snapshot.entries.get(target_trait_id)
        if entry is not None:
            self.assertEqual(entry.primary_evidence_count, 0)

    def test_approved_pack_seed_evidence_included_in_primary_snapshot(self) -> None:
        required = sorted(self.registry.required_review_keys(self.pack))
        (self.review_dir / "business_review_status.json").write_text(
            json.dumps([{"blueprint_id": k, "reviewer_1_status": "APPROVE"} for k in required], ensure_ascii=False),
            encoding="utf-8",
        )
        session_id, target_trait_id = self._drive_seed_answer()
        self.assertIsNotNone(target_trait_id)
        r = client.get(f"/profile/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        snapshot = main_module._trait_vector_primary_repository.load(session_id)
        self.assertIsNotNone(snapshot)
        entry = snapshot.entries.get(target_trait_id)
        self.assertIsNotNone(entry)
        self.assertGreaterEqual(entry.primary_evidence_count, 1)


if __name__ == "__main__":
    unittest.main()
