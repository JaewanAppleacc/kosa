"""Trait Signal Review Gate(Fail-Closed) 테스트 — 2026-08-23 Trait Ontology v2(2.6단계) §3."""

from __future__ import annotations

import unittest

from src.schemas.evidence import EvidenceOrigin, EvidenceRecord
from src.services.anchor_backup_review_store import load_anchor_backup_question_review_entries
from src.services.backup_question_review_store import load_backup_question_review_entries
from src.services.seed_anchor_review_store import load_seed_anchor_question_review_entries
from src.services.trait_signal_review_gate import (
    filter_primary_eligible_evidence,
    gate_primary_eligible_evidence,
    is_evidence_signal_approved,
)
from src.services.v2_direct_probe_review_store import load_question_review_entries


def _evidence(
    evidence_id: str, *, origin: EvidenceOrigin, family: str | None, blueprint_id: str | None,
    context: str = "game", trait_delta: dict[str, int] | None = None,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id, answer_id=f"ans_{evidence_id}", question_id=f"q_{evidence_id}",
        question_frame_id="problem_check", option_role_id="role_1", option_text="테스트 선택지",
        applied_primary_trait_delta=trait_delta or {}, evidence_origin=origin, context=context,
        source_type="generated_question", generator_version="v1", quality_gate_status="passed",
        source_question_family_id=family, source_blueprint_id=blueprint_id,
    )


class AlwaysApprovedFamilyTest(unittest.TestCase):
    def test_tail_blueprint_always_approved(self) -> None:
        e = _evidence("e1", origin=EvidenceOrigin.PRIMARY_BLUEPRINT, family="tail_blueprint", blueprint_id="bp1")
        self.assertTrue(is_evidence_signal_approved(e, {}))

    def test_mock_placeholder_always_approved(self) -> None:
        e = _evidence("e1", origin=EvidenceOrigin.PRIMARY_BLUEPRINT, family="mock_placeholder", blueprint_id="q1")
        self.assertTrue(is_evidence_signal_approved(e, {}))

    def test_conflict_resolution_always_approved(self) -> None:
        e = _evidence(
            "e1", origin=EvidenceOrigin.CONFLICT_RESOLUTION, family="conflict_resolution", blueprint_id="c1",
        )
        self.assertTrue(is_evidence_signal_approved(e, {}))

    def test_context_routing_always_approved(self) -> None:
        e = _evidence("e1", origin=EvidenceOrigin.PRIMARY_BLUEPRINT, family="context_routing", blueprint_id="r1")
        self.assertTrue(is_evidence_signal_approved(e, {}))

    def test_none_family_always_approved(self) -> None:
        """하위 호환 — 2.6단계 이전(source_question_family_id 필드 도입 전) 기록."""

        e = _evidence("e1", origin=EvidenceOrigin.PRIMARY_BLUEPRINT, family=None, blueprint_id=None)
        self.assertTrue(is_evidence_signal_approved(e, {}))

    def test_unknown_family_fails_closed(self) -> None:
        e = _evidence("e1", origin=EvidenceOrigin.PRIMARY_BLUEPRINT, family="some_future_family", blueprint_id="x")
        self.assertFalse(is_evidence_signal_approved(e, {}))


class V2DirectProbeGateTest(unittest.TestCase):
    def test_draft_direct_probe_excluded(self) -> None:
        """실제 커밋된 V2 Direct Probe 질문은 전부 아직 DRAFT다(§4 규칙 — 검수 결과를
        대신 채우지 않는다) — 따라서 전부 거부돼야 한다."""

        entries = load_question_review_entries()
        self.assertTrue(all(e.final_status == "DRAFT" for e in entries))
        for entry in entries:
            e = _evidence(
                "e1", origin=EvidenceOrigin.V2_DIRECT_PROBE, family="v2_direct_probe",
                blueprint_id=entry.blueprint_id,
            )
            with self.subTest(blueprint_id=entry.blueprint_id):
                self.assertFalse(is_evidence_signal_approved(e, {}))

    def test_unknown_blueprint_id_excluded(self) -> None:
        e = _evidence(
            "e1", origin=EvidenceOrigin.V2_DIRECT_PROBE, family="v2_direct_probe",
            blueprint_id="does_not_exist",
        )
        self.assertFalse(is_evidence_signal_approved(e, {}))


class BackupFamilyGateTest(unittest.TestCase):
    def test_anchor_backup_approved_blueprint_passes(self) -> None:
        entries = load_anchor_backup_question_review_entries()
        approved = [e for e in entries if e.final_status == "APPROVED"]
        self.assertEqual(len(approved), 15)  # 2.5.5단계에서 사용자가 15개 전부 APPROVE
        for entry in approved:
            e = _evidence("e1", origin=EvidenceOrigin.PRIMARY_BLUEPRINT, family="backup", blueprint_id=entry.blueprint_id)
            with self.subTest(blueprint_id=entry.blueprint_id):
                self.assertTrue(is_evidence_signal_approved(e, {}))

    def test_old_backup_review_required_blueprint_fails(self) -> None:
        entries = load_backup_question_review_entries()
        self.assertTrue(all(e.final_status == "REVIEW_REQUIRED" for e in entries))
        for entry in entries:
            e = _evidence("e1", origin=EvidenceOrigin.PRIMARY_BLUEPRINT, family="backup", blueprint_id=entry.blueprint_id)
            with self.subTest(blueprint_id=entry.blueprint_id):
                self.assertFalse(is_evidence_signal_approved(e, {}))


class SeedAnchorGateTest(unittest.TestCase):
    def test_approved_seed_anchor_variant_passes(self) -> None:
        entries = load_seed_anchor_question_review_entries()
        approved = [e for e in entries if e.final_status == "APPROVED"]
        self.assertEqual(len(approved), 15)
        for entry in approved:
            e = _evidence(
                "e1", origin=EvidenceOrigin.PRIMARY_BLUEPRINT, family="seed",
                blueprint_id=f"whatever_{entry.anchor_id}_blueprint", context=entry.context_id,
            )
            with self.subTest(context_id=entry.context_id, anchor_id=entry.anchor_id):
                self.assertTrue(
                    is_evidence_signal_approved(e, {entry.context_id: entry.anchor_id})
                )

    def test_legacy_seed_without_anchor_always_approved(self) -> None:
        e = _evidence("e1", origin=EvidenceOrigin.PRIMARY_BLUEPRINT, family="seed", blueprint_id="q_seed_blueprint")
        self.assertTrue(is_evidence_signal_approved(e, {}))  # context_anchor_choices에 없음


class FilterPrimaryEligibleEvidenceTest(unittest.TestCase):
    def test_filters_out_only_unapproved_records(self) -> None:
        approved = _evidence("e1", origin=EvidenceOrigin.PRIMARY_BLUEPRINT, family="tail_blueprint", blueprint_id="bp1")
        rejected = _evidence(
            "e2", origin=EvidenceOrigin.V2_DIRECT_PROBE, family="v2_direct_probe", blueprint_id="does_not_exist",
        )
        conflict = _evidence("e3", origin=EvidenceOrigin.CONFLICT_RESOLUTION, family="conflict_resolution", blueprint_id="c1")
        filtered = filter_primary_eligible_evidence([approved, rejected, conflict], {})
        self.assertEqual({e.evidence_id for e in filtered}, {"e1", "e3"})

    def test_does_not_mutate_original_ledger(self) -> None:
        ledger = [_evidence("e1", origin=EvidenceOrigin.PRIMARY_BLUEPRINT, family="tail_blueprint", blueprint_id="bp1")]
        before = list(ledger)
        filter_primary_eligible_evidence(ledger, {})
        self.assertEqual(ledger, before)

    def test_gate_result_reports_excluded_ids_for_diagnostics(self) -> None:
        """§3 "어떤 Signal이 검수 미완료로 제외됐는지 Trace와 진단 결과에서 확인
        가능하게 함"을 뒷받침하는 값."""

        rejected = _evidence(
            "e2", origin=EvidenceOrigin.V2_DIRECT_PROBE, family="v2_direct_probe", blueprint_id="does_not_exist",
        )
        result = gate_primary_eligible_evidence([rejected], {})
        self.assertEqual(result.excluded_evidence_ids, {"e2"})
        self.assertEqual(result.approved_evidence_ids, set())


if __name__ == "__main__":
    unittest.main()
