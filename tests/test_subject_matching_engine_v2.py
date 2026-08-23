"""v2 Subject Matching Engine 테스트 — 2026-08-23 Trait Ontology v2(2.6단계) §8."""

from __future__ import annotations

import unittest

from src.engines.subject_matching_engine_v2 import compute_subject_recommendations_v2
from src.schemas.course import SubjectProfile
from src.schemas.trait_vector_snapshot import TraitVectorEntry


def _entry(trait_id: str, tendency: float | None, status: str = "STRONG") -> TraitVectorEntry:
    return TraitVectorEntry(
        trait_id=trait_id, primary_signal_sum=1.0, related_signal_sum=0.0,
        confirmed_related_signal_sum=0.0, primary_evidence_count=3, related_evidence_count=0,
        context_count=2, frame_count=2, question_count=3, tendency_score=tendency,
        evidence_confidence="primary_evidence" if tendency is not None else "no_evidence", status=status,
    )


def _subject(subject_id: str, trait_vector: dict[str, float], related_major_ids: list[str]) -> SubjectProfile:
    return SubjectProfile(
        subject_id=subject_id, label=subject_id, trait_vector=trait_vector,
        related_major_ids=related_major_ids, source_id="src_test", activity_summary="테스트 활동",
    )


class SubjectMatchingV2Test(unittest.TestCase):
    def test_only_related_major_subjects_are_candidates(self) -> None:
        subjects = [
            _subject("s1", {"t1": 1.0}, ["media_communication"]),
            _subject("s2", {"t1": 1.0}, ["hci_ux"]),
        ]
        states = {"t1": _entry("t1", 1.0)}
        results = compute_subject_recommendations_v2(states, "media_communication", subjects)
        self.assertEqual([r.subject_id for r in results], ["s1"])

    def test_no_shared_trait_excludes_subject(self) -> None:
        subjects = [_subject("s1", {"t9": 1.0}, ["media_communication"])]
        states = {"t1": _entry("t1", 1.0)}
        results = compute_subject_recommendations_v2(states, "media_communication", subjects)
        self.assertEqual(results, [])

    def test_score_not_in_output_type_when_converted_to_api_item(self) -> None:
        from src.engines.subject_matching_engine import to_course_recommendation_items
        from src.schemas.trait import TraitDefinition

        subjects = [_subject("s1", {"t1": 1.0, "t2": 1.0}, ["media_communication"])]
        states = {"t1": _entry("t1", 1.0), "t2": _entry("t2", 1.0)}
        results = compute_subject_recommendations_v2(states, "media_communication", subjects)
        self.assertEqual(len(results), 1)
        self.assertIsNotNone(results[0].score)  # 내부 결과 타입에는 있음

        trait_defs = {
            tid: TraitDefinition(
                trait_id=tid, label=tid, parent_dimension="테스트", definition="def",
                positive_indicators=["a"], conflicting_indicators=["b"], source_references=["c"],
                trait_scope="shared", minimum_context_count=1, primary_vector_group="cognitive",
            )
            for tid in ("t1", "t2")
        }
        items = to_course_recommendation_items(results, "테스트 전공", trait_defs)
        self.assertEqual(len(items), 1)
        self.assertNotIn("score", items[0].model_dump())

    def test_conflicting_trait_not_treated_as_zero_overlap(self) -> None:
        subjects = [_subject("s1", {"t1": 1.0}, ["media_communication"])]
        states = {"t1": _entry("t1", None, status="CONFLICTING")}
        results = compute_subject_recommendations_v2(states, "media_communication", subjects)
        self.assertEqual(results, [])  # Conflict인 Trait는 겹치지 않은 것과 동일하게 제외


if __name__ == "__main__":
    unittest.main()
