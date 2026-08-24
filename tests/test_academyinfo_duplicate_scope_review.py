"""계약학과 중복 관계의 A 승인 정본 검증."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from src.schemas.academyinfo_duplicate_scope_review import (
    AcademyInfoDuplicateScopeDecision,
    AcademyInfoReviewedRecordScope,
)
from src.services.academyinfo_duplicate_scope_review_loader import (
    AcademyInfoReviewPacketMismatchError,
    DuplicateAcademyInfoReviewKeyError,
    DEFAULT_DECISION_PATH,
    DEFAULT_PACKET_PATH,
    load_academyinfo_duplicate_scope_decisions,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_MASTER_PATH = _REPO_ROOT / "data" / "master" / "departments.jsonl"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


class RealDecisionDataTest(unittest.TestCase):
    def test_all_six_relations_are_approved_and_confirmed(self) -> None:
        decisions = load_academyinfo_duplicate_scope_decisions()
        self.assertEqual(len(decisions), 6)
        self.assertEqual({d.reviewer_1_status for d in decisions}, {"APPROVE"})
        self.assertEqual({d.resolution_status for d in decisions}, {"CONFIRMED"})
        self.assertEqual({d.approved_decision for d in decisions}, {"DISTINCT_DEPARTMENTS_KEEP_SEPARATE"})

    def test_each_relation_keeps_one_general_and_excludes_one_contract_course(self) -> None:
        for decision in load_academyinfo_duplicate_scope_decisions():
            general = next(r for r in decision.records if r.major_character_name == "일반과정")
            contract = next(r for r in decision.records if r.major_character_name == "계약학과")
            self.assertEqual(general.recommendation_scope, "IN_RECOMMENDATION_SCOPE")
            self.assertIsNone(general.exclusion_reason)
            self.assertEqual(contract.recommendation_scope, "OUT_OF_RECOMMENDATION_SCOPE")
            self.assertEqual(contract.exclusion_reason, "CONTRACT_DEPARTMENT")

    def test_chungnam_pharmacy_decision_preserves_six_year_general_course(self) -> None:
        decisions = load_academyinfo_duplicate_scope_decisions()
        chungnam = next(d for d in decisions if d.candidate_id == "dup_78e3d5bd30dab8651ef7")
        general = next(r for r in chungnam.records if r.major_character_name == "일반과정")
        contract = next(r for r in chungnam.records if r.major_character_name == "계약학과")
        self.assertEqual(general.schl_mjr_id, "0010025")
        self.assertEqual(contract.schl_mjr_id, "0220559")

        packet = next(r for r in _read_jsonl(DEFAULT_PACKET_PATH) if r["candidate_id"] == chungnam.candidate_id)
        terms = {r["source_record_id"]: r["lesson_term_name"] for r in packet["records"]}
        self.assertEqual(terms[general.source_record_id], "6년")
        self.assertEqual(terms[contract.source_record_id], "4년")

    def test_generated_packet_remains_unapproved_draft(self) -> None:
        packet = _read_jsonl(DEFAULT_PACKET_PATH)
        self.assertEqual({row["reviewer_1_status"] for row in packet}, {"TBD"})
        self.assertEqual({row["resolution_status"] for row in packet}, {"PENDING"})

    def test_loading_decisions_does_not_mutate_packet_or_master(self) -> None:
        before = (_sha256(DEFAULT_PACKET_PATH), _sha256(_MASTER_PATH))
        load_academyinfo_duplicate_scope_decisions()
        self.assertEqual(before, (_sha256(DEFAULT_PACKET_PATH), _sha256(_MASTER_PATH)))


class SchemaConsistencyTest(unittest.TestCase):
    def test_general_course_cannot_be_excluded(self) -> None:
        with self.assertRaises(ValidationError):
            AcademyInfoReviewedRecordScope(
                source_record_id="src_1",
                schl_mjr_id="001",
                major_character_name="일반과정",
                recommendation_scope="OUT_OF_RECOMMENDATION_SCOPE",
                exclusion_reason="CONTRACT_DEPARTMENT",
            )

    def test_contract_course_requires_contract_exclusion_reason(self) -> None:
        with self.assertRaises(ValidationError):
            AcademyInfoReviewedRecordScope(
                source_record_id="src_1",
                schl_mjr_id="001",
                major_character_name="계약학과",
                recommendation_scope="OUT_OF_RECOMMENDATION_SCOPE",
                exclusion_reason=None,
            )

    def test_decision_requires_one_general_and_one_contract_course(self) -> None:
        record = {
            "source_record_id": "src_1",
            "schl_mjr_id": "001",
            "major_character_name": "일반과정",
            "recommendation_scope": "IN_RECOMMENDATION_SCOPE",
            "exclusion_reason": None,
        }
        with self.assertRaises(ValidationError):
            AcademyInfoDuplicateScopeDecision(
                candidate_id="dup_1",
                department_id="dept_1",
                approved_decision="DISTINCT_DEPARTMENTS_KEEP_SEPARATE",
                reviewer_1_status="APPROVE",
                reviewer_1_comment="승인",
                resolution_status="CONFIRMED",
                reviewed_at="2026-08-24",
                records=[record, {**record, "source_record_id": "src_2", "schl_mjr_id": "002"}],
            )


class PacketCrossValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.decision_path = Path(self.tmpdir.name) / "decisions.jsonl"
        self.packet_path = Path(self.tmpdir.name) / "packet.jsonl"
        self.decisions = _read_jsonl(DEFAULT_DECISION_PATH)
        self.packet = _read_jsonl(DEFAULT_PACKET_PATH)

    def _load(self) -> list[AcademyInfoDuplicateScopeDecision]:
        _write_jsonl(self.decision_path, self.decisions)
        _write_jsonl(self.packet_path, self.packet)
        return load_academyinfo_duplicate_scope_decisions(self.decision_path, self.packet_path)

    def test_duplicate_candidate_id_is_rejected(self) -> None:
        self.decisions.append(self.decisions[0])
        with self.assertRaises(DuplicateAcademyInfoReviewKeyError):
            self._load()

    def test_missing_candidate_decision_is_rejected(self) -> None:
        self.decisions.pop()
        with self.assertRaises(AcademyInfoReviewPacketMismatchError):
            self._load()

    def test_department_id_mismatch_is_rejected(self) -> None:
        self.decisions[0]["department_id"] = "dept_wrong"
        with self.assertRaises(AcademyInfoReviewPacketMismatchError):
            self._load()

    def test_record_scope_mismatch_is_rejected(self) -> None:
        packet_record = self.packet[0]["records"][0]
        packet_record["recommendation_scope"] = "OUT_OF_RECOMMENDATION_SCOPE"
        packet_record["exclusion_reason"] = "CONTRACT_DEPARTMENT"
        with self.assertRaises(AcademyInfoReviewPacketMismatchError):
            self._load()


if __name__ == "__main__":
    unittest.main()
