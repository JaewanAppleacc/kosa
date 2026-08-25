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
from src.data.majors.service_major_profiles_v2 import SERVICE_MAJOR_PROFILES_V2
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
    """2026-08-25 지시서(a/major-profiles-v2-38) — 3개 고정 구조를 제거하고 39개
    Service Catalog 전체를 다룬다. `MAJOR_LABELS`는 더 이상 3개 하드코딩이 아니라
    39개 Service Catalog에서 그대로 가져온 값이다(career_build_major_profiles_v2.py)."""

    def test_39_majors_present(self) -> None:
        self.assertEqual(len(MAJOR_LABELS), 39)
        self.assertEqual({p.major_id for p in SERVICE_MAJOR_PROFILES_V2}, set(MAJOR_LABELS))

    def test_vectors_do_not_force_fill_all_24_traits(self) -> None:
        """§6 "24개 Trait를 억지로 모두 채우지 않음" — Evidence 기반 3개·수동
        큐레이션 36개 모두에 적용되는 불변식이다."""

        for profile in SERVICE_MAJOR_PROFILES_V2:
            total = (
                len(profile.interest_vector) + len(profile.cognitive_vector)
                + len(profile.work_style_vector) + len(profile.environment_vector)
            )
            with self.subTest(major_id=profile.major_id):
                self.assertLess(total, 24)
                self.assertGreater(total, 0)

    def test_review_required_traits_never_appear_in_vectors(self) -> None:
        """Evidence 파일(major_trait_mapping_evidence_v2.jsonl)은 여전히 Evidence
        기반 3개만 담는다 — 수동 큐레이션 36개는 이 파일에 레코드가 없으므로
        `review_required_by_major.get(...)`가 빈 집합을 돌려줘 아래 검사가
        공집합 교집합으로 자동 통과한다(그 36개는 애초에 이 Evidence 파일의
        대상이 아니다)."""

        from scripts.career_build_major_trait_mapping_evidence_v2 import OUTPUT_PATH

        records = load_major_trait_mapping_evidence(OUTPUT_PATH)
        review_required_by_major: dict[str, set[str]] = {}
        for r in records:
            if r.mapping_status in ("UNMAPPED", "REVIEW_REQUIRED"):
                review_required_by_major.setdefault(r.major_id, set()).add(r.trait_id)

        for profile in SERVICE_MAJOR_PROFILES_V2:
            all_vector_traits = (
                set(profile.interest_vector) | set(profile.cognitive_vector)
                | set(profile.work_style_vector) | set(profile.environment_vector)
            )
            excluded = review_required_by_major.get(profile.major_id, set())
            with self.subTest(major_id=profile.major_id):
                self.assertEqual(all_vector_traits & excluded, set())

    def test_review_status_not_auto_promoted(self) -> None:
        for profile in SERVICE_MAJOR_PROFILES_V2:
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
    def test_original_six_target_subjects_still_present(self) -> None:
        """2026-08-25 a/subject-mapping-38-majors 확장 이후에도 원래 Vertical Slice
        6개 과목(media_communication/hci_ux/industrial_engineering 대표 전공용)은
        그대로 남아 있어야 한다 — 확장이 기존 것을 지우지 않는다는 회귀 검증."""

        from scripts.career_build_subject_trait_mapping_evidence_v2 import _target_subject_ids

        profiles = build_subject_profiles_v2()
        profile_ids = {p.subject_id for p in profiles}
        self.assertTrue(set(_target_subject_ids()).issubset(profile_ids))

    def test_covers_all_39_service_majors(self) -> None:
        """39개 서비스 Major(38개 Group 기반 + hci_ux) 전부가 v2 후보 과목을
        최소 1개(core 후보 자격은 최소 2개 EVIDENCED/NO_DIRECT_EVIDENCE Trait) 갖는지
        확인한다 — a/subject-mapping-38-majors 지시서의 핵심 목표."""

        from src.services.service_canonical_major_v2_loader import load_service_canonical_majors_v2

        profiles = build_subject_profiles_v2()
        catalog_major_ids = {m.major_id for m in load_service_canonical_majors_v2()}

        by_major: dict[str, list[int]] = {}
        for p in profiles:
            for major_id in p.related_major_ids:
                by_major.setdefault(major_id, []).append(len(p.trait_vector))

        for major_id in sorted(catalog_major_ids):
            with self.subTest(major_id=major_id):
                self.assertIn(major_id, by_major, f"{major_id}: 후보 과목이 0건이다")
                self.assertTrue(
                    any(count >= 2 for count in by_major[major_id]),
                    f"{major_id}: core 후보 자격(2개 이상 Trait Evidence)을 만족하는 과목이 없다",
                )

    def test_activity_summary_reused_from_legacy_not_invented(self) -> None:
        """원래 Vertical Slice 6개 과목은 Legacy `subjects.jsonl`의 검토된 값을 그대로
        재사용해야 한다(그 6개는 이번 확장이 activity_summary 계산 방식을 바꾸지 않은
        범위다 — 우연히 값이 같아서 통과하는 게 아니라 Legacy 값 자체를 근거로 삼는다)."""

        from scripts.career_build_subject_trait_mapping_evidence_v2 import TARGET_MAJOR_IDS
        from src.repositories.subject_repository import load_subjects

        legacy_by_id = {s.subject_id: s for s in load_subjects()}
        original_six_ids = {
            s.subject_id for s in legacy_by_id.values()
            if any(m in s.related_major_ids for m in TARGET_MAJOR_IDS)
        }
        profiles = build_subject_profiles_v2()
        for p in profiles:
            if p.subject_id not in original_six_ids:
                continue
            with self.subTest(subject_id=p.subject_id):
                self.assertEqual(p.activity_summary, legacy_by_id[p.subject_id].activity_summary)

    def test_expanded_activity_summary_matches_highest_grade_evidence(self) -> None:
        """2026-08-25 확장분(원래 6개 밖의 과목)은 activity_summary를 v2 Trait
        Evidence에서 직접 계산한다(Legacy에 값이 아예 없다) — EVIDENCED 중 grade가
        가장 높은 것(동점이면 trait_id 알파벳순)의 reason과 같아야 하고, 임의로 지어낸
        문장이면 안 된다."""

        from scripts.career_build_subject_trait_mapping_evidence_v2 import OUTPUT_PATH, TARGET_MAJOR_IDS
        from src.repositories.subject_repository import load_subjects

        original_six_ids = {
            s.subject_id for s in load_subjects()
            if any(m in s.related_major_ids for m in TARGET_MAJOR_IDS)
        }
        expanded_evidence_records = load_subject_trait_mapping_evidence(OUTPUT_PATH)
        by_subject: dict[str, list] = {}
        for r in expanded_evidence_records:
            if r.mapping_status == "EVIDENCED":
                by_subject.setdefault(r.subject_id, []).append(r)

        profiles = build_subject_profiles_v2()
        for p in profiles:
            if p.subject_id in original_six_ids:
                continue  # 위 테스트가 이미 확인한다.
            with self.subTest(subject_id=p.subject_id):
                candidates = by_subject.get(p.subject_id, [])
                self.assertTrue(candidates, f"{p.subject_id}: EVIDENCED Trait가 하나도 없다")
                best = min(candidates, key=lambda r: (-r.grade, r.trait_id))
                self.assertEqual(p.activity_summary, best.activity_summary)

    def test_build_is_deterministic(self) -> None:
        first = build_subject_profiles_v2()
        second = build_subject_profiles_v2()
        self.assertEqual([p.model_dump_json() for p in first], [p.model_dump_json() for p in second])


if __name__ == "__main__":
    unittest.main()
