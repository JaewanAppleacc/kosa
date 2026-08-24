from __future__ import annotations

import unittest

from scripts.career_evaluate_question_major_trace import OUTPUT, evaluate, render, tourism_draft_profile


class QuestionMinorMajorTraceTest(unittest.TestCase):
    def test_question_answers_produce_repeated_cross_context_traits(self) -> None:
        trace, evidence, _ = evaluate()
        self.assertEqual(len(trace), 8)
        self.assertGreaterEqual(len(evidence["usable_traits"]), 3)
        for trait in evidence["usable_traits"]:
            self.assertGreaterEqual(evidence["support_count"][trait], 2)
            self.assertGreaterEqual(evidence["context_count"][trait], 2)

    def test_minor_profile_cannot_be_promoted(self) -> None:
        profile = tourism_draft_profile()
        self.assertEqual(profile.review_status, "REVIEW_REQUIRED")
        self.assertIn("evaluation_hypothesis_not_official_curriculum", profile.source_ids)

    def test_current_engine_computes_minor_draft(self) -> None:
        _, _, result = evaluate()
        row = next(r for r in result.majors if r.major_id == "tourism_hotel_evaluation_draft")
        self.assertEqual(row.status, "computed")

    def test_committed_report_is_deterministic(self) -> None:
        self.assertEqual(render(), render())
        self.assertEqual(OUTPUT.read_text(encoding="utf-8"), render())


if __name__ == "__main__":
    unittest.main()
