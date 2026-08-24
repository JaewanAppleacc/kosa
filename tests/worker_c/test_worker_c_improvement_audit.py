from __future__ import annotations

import json
import unittest

from scripts.career_audit_worker_c_improvements import (
    AUDIT,
    WORK,
    alias_audit,
    build,
    priority_draft,
    rag_audit,
    read_jsonl,
)


class WorkerCImprovementAuditTest(unittest.TestCase):
    def test_priority_is_work_order_not_approval(self) -> None:
        rows = priority_draft(
            [{"source_record_id": "b", "review_cause": "DESIGN", "review_status": "REVIEW_REQUIRED"},
             {"source_record_id": "a", "review_cause": "DESIGN", "review_status": "REVIEW_REQUIRED"}],
            [],
        )
        self.assertEqual([r["source_record_id"] for r in rows], ["a", "b"])
        self.assertTrue(all("승인 확률" in r["priority_meaning"] for r in rows))
        self.assertTrue(all(r["review_status"] == "REVIEW_REQUIRED" for r in rows))

    def test_shipped_audit_preserves_review_state(self) -> None:
        priorities, report = build()
        self.assertEqual(len(priorities), 3837)
        self.assertEqual(report["review_priority"]["auto_approved_rows"], 0)
        self.assertFalse(report["review_priority"]["status_mutated"])
        self.assertFalse(report["claims"]["student_recommendation_accuracy_measured"])

    def test_missing_nationwide_inputs_are_not_pretended(self) -> None:
        _, report = build()
        coverage = report["minor_field_data_coverage"]
        self.assertFalse(coverage["measured"])
        self.assertEqual(coverage["status"], "SOURCE_MISSING")
        self.assertFalse(coverage["recommendation_performance_claim_allowed"])

    def test_alias_audit_does_not_change_master(self) -> None:
        report = alias_audit()
        self.assertFalse(report["master_changed"])
        self.assertEqual(report["status"], "REVIEW_DRAFT_ONLY")

    def test_rag_fixture_is_not_called_service_performance(self) -> None:
        report = rag_audit()
        self.assertFalse(report["performance_claim_allowed"])
        self.assertGreater(report["query_count"], 0)

    def test_committed_outputs_match_generator(self) -> None:
        priorities, report = build()
        self.assertEqual(read_jsonl(WORK / "review_priority_draft.jsonl"), priorities)
        committed = json.loads(
            (AUDIT / "worker_c_improvement_audit.json").read_text(encoding="utf-8")
        )
        self.assertEqual(committed, report)

    def test_priority_draft_is_below_blob_limit(self) -> None:
        self.assertLess((WORK / "review_priority_draft.jsonl").stat().st_size, 5 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
