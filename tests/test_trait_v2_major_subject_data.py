"""v2 Major/Subject-Trait Mapping Evidence + Profile 정본 데이터 테스트 —
2026-08-23 Trait Ontology v2(2.6단계) §6/§8."""

from __future__ import annotations

import unittest

from scripts.career_build_major_profiles_v2 import MAJOR_LABELS
from scripts.career_build_major_profiles_v2 import build as build_major_profiles_v2
from scripts.career_build_major_trait_mapping_evidence_v2 import TARGET_MAJOR_IDS
from scripts.career_build_major_trait_mapping_evidence_v2 import build as build_major_evidence_v2
from scripts.career_build_subject_profiles_v2 import build as build_subject_profiles_v2
from scripts.career_build_subject_trait_mapping_evidence_v2 import build as build_subject_evidence_v2
from src.data.majors.vertical_slice_major_profiles_v2 import VERTICAL_SLICE_MAJOR_PROFILES_V2
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAIT_IDS
from src.services.major_trait_mapping_evidence import load_major_trait_mapping_evidence
from src.services.subject_trait_mapping_evidence import load_subject_trait_mapping_evidence
from src.services.trait_ontology_v2 import load_trait_ontology_v2

_ALL_V2_TRAIT_IDS = {t.trait_id for t in load_trait_ontology_v2()}
_V2_MAJOR_EVIDENCE_PATH = None  # 기본 경로(data/master/major_trait_mapping_evidence_v2.jsonl) 사용


class MajorTraitMappingEvidenceV2Test(unittest.TestCase):
    def test_covers_3_majors_times_24_traits_exactly(self) -> None:
        from scripts.career_build_major_trait_mapping_evidence_v2 import OUTPUT_PATH

        records = load_major_trait_mapping_evidence(OUTPUT_PATH)
        self.assertEqual(len(records), 3 * 24)
        pairs = {(r.major_id, r.trait_id) for r in records}
        self.assertEqual(len(pairs), 3 * 24)
        for major_id in TARGET_MAJOR_IDS:
            for trait_id in _ALL_V2_TRAIT_IDS:
                self.assertIn((major_id, trait_id), pairs)

    def test_new_v2_traits_are_review_required_with_no_grade(self) -> None:
        """§6 "새 v2 Trait에 대한 직접 근거가 없다면 REVIEW_REQUIRED 유지", "자동 승격 금지"."""

        from scripts.career_build_major_trait_mapping_evidence_v2 import OUTPUT_PATH

        records = load_major_trait_mapping_evidence(OUTPUT_PATH)
        new_trait_ids = _ALL_V2_TRAIT_IDS - VERTICAL_SLICE_TRAIT_IDS
        self.assertEqual(len(new_trait_ids), 12)
        for r in records:
            if r.trait_id in new_trait_ids:
                with self.subTest(major_id=r.major_id, trait_id=r.trait_id):
                    self.assertEqual(r.mapping_status, "REVIEW_REQUIRED")
                    self.assertIsNone(r.grade)
                    self.assertEqual(r.evidence, [])
                    self.assertEqual(r.review_status, "draft")

    def test_legacy_12_traits_reused_verbatim_from_legacy_file(self) -> None:
        """§6 "기존 Major–Trait Evidence URL 재사용 가능" — grade/evidence/mapping_status가
        Legacy와 완전히 동일해야 한다(값을 새로 지어내지 않는다)."""

        from scripts.career_build_major_trait_mapping_evidence_v2 import OUTPUT_PATH

        v2_records = {(r.major_id, r.trait_id): r for r in load_major_trait_mapping_evidence(OUTPUT_PATH)}
        legacy_records = {
            (r.major_id, r.trait_id): r
            for r in load_major_trait_mapping_evidence()
            if r.major_id in TARGET_MAJOR_IDS
        }
        for key, legacy in legacy_records.items():
            v2 = v2_records[key]
            with self.subTest(key=key):
                self.assertEqual(v2.mapping_status, legacy.mapping_status)
                self.assertEqual(v2.grade, legacy.grade)
                self.assertEqual([e.model_dump() for e in v2.evidence], [e.model_dump() for e in legacy.evidence])

    def test_no_evidence_record_is_pre_approved(self) -> None:
        from scripts.career_build_major_trait_mapping_evidence_v2 import OUTPUT_PATH

        for r in load_major_trait_mapping_evidence(OUTPUT_PATH):
            self.assertEqual(r.review_status, "draft")

    def test_build_is_deterministic(self) -> None:
        first = build_major_evidence_v2()
        second = build_major_evidence_v2()
        self.assertEqual(
            [r.model_dump_json() for r in first], [r.model_dump_json() for r in second]
        )


class MajorProfilesV2Test(unittest.TestCase):
    def test_three_majors_present(self) -> None:
        self.assertEqual({p.major_id for p in VERTICAL_SLICE_MAJOR_PROFILES_V2}, set(MAJOR_LABELS))

    def test_vectors_do_not_force_fill_all_24_traits(self) -> None:
        """§6 "24개 Trait를 억지로 모두 채우지 않음"."""

        for profile in VERTICAL_SLICE_MAJOR_PROFILES_V2:
            total = (
                len(profile.interest_vector) + len(profile.cognitive_vector)
                + len(profile.work_style_vector) + len(profile.environment_vector)
            )
            with self.subTest(major_id=profile.major_id):
                self.assertLess(total, 24)
                self.assertGreater(total, 0)

    def test_review_required_traits_never_appear_in_vectors(self) -> None:
        from scripts.career_build_major_trait_mapping_evidence_v2 import OUTPUT_PATH

        records = load_major_trait_mapping_evidence(OUTPUT_PATH)
        review_required_by_major: dict[str, set[str]] = {}
        for r in records:
            if r.mapping_status in ("UNMAPPED", "REVIEW_REQUIRED"):
                review_required_by_major.setdefault(r.major_id, set()).add(r.trait_id)

        for profile in VERTICAL_SLICE_MAJOR_PROFILES_V2:
            all_vector_traits = (
                set(profile.interest_vector) | set(profile.cognitive_vector)
                | set(profile.work_style_vector) | set(profile.environment_vector)
            )
            excluded = review_required_by_major.get(profile.major_id, set())
            with self.subTest(major_id=profile.major_id):
                self.assertEqual(all_vector_traits & excluded, set())

    def test_review_status_not_auto_promoted(self) -> None:
        for profile in VERTICAL_SLICE_MAJOR_PROFILES_V2:
            self.assertEqual(profile.review_status, "draft")

    def test_build_is_deterministic(self) -> None:
        first = build_major_profiles_v2()
        second = build_major_profiles_v2()
        self.assertEqual([p.model_dump_json() for p in first], [p.model_dump_json() for p in second])


class SubjectTraitMappingEvidenceV2Test(unittest.TestCase):
    def test_new_v2_traits_are_review_required(self) -> None:
        from scripts.career_build_subject_trait_mapping_evidence_v2 import OUTPUT_PATH

        records = load_subject_trait_mapping_evidence(OUTPUT_PATH)
        new_trait_ids = _ALL_V2_TRAIT_IDS - VERTICAL_SLICE_TRAIT_IDS
        for r in records:
            if r.trait_id in new_trait_ids:
                with self.subTest(subject_id=r.subject_id, trait_id=r.trait_id):
                    self.assertEqual(r.mapping_status, "REVIEW_REQUIRED")
                    self.assertIsNone(r.grade)

    def test_no_duplicate_subject_trait_pairs(self) -> None:
        from scripts.career_build_subject_trait_mapping_evidence_v2 import OUTPUT_PATH

        records = load_subject_trait_mapping_evidence(OUTPUT_PATH)
        pairs = [(r.subject_id, r.trait_id) for r in records]
        self.assertEqual(len(pairs), len(set(pairs)))

    def test_build_is_deterministic(self) -> None:
        first = build_subject_evidence_v2()
        second = build_subject_evidence_v2()
        self.assertEqual([r.model_dump_json() for r in first], [r.model_dump_json() for r in second])


class SubjectProfilesV2Test(unittest.TestCase):
    def test_six_target_subjects_present(self) -> None:
        from scripts.career_build_subject_trait_mapping_evidence_v2 import _target_subject_ids

        profiles = build_subject_profiles_v2()
        self.assertEqual({p.subject_id for p in profiles}, set(_target_subject_ids()))

    def test_activity_summary_reused_from_legacy_not_invented(self) -> None:
        from src.repositories.subject_repository import load_subjects

        legacy_by_id = {s.subject_id: s for s in load_subjects()}
        profiles = build_subject_profiles_v2()
        for p in profiles:
            with self.subTest(subject_id=p.subject_id):
                self.assertEqual(p.activity_summary, legacy_by_id[p.subject_id].activity_summary)

    def test_build_is_deterministic(self) -> None:
        first = build_subject_profiles_v2()
        second = build_subject_profiles_v2()
        self.assertEqual([p.model_dump_json() for p in first], [p.model_dump_json() for p in second])


if __name__ == "__main__":
    unittest.main()
