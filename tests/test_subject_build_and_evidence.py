"""Subject-Trait/Subject-Major Evidence Schema + 결정론적 빌드 — 2026-08-24 14차 리뷰 §3/§4."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAITS
from src.engines.trait_normalizer import normalize_grade
from src.ids import generate_subject_id
from src.repositories.subject_repository import JsonlSubjectRepository, load_subjects
from src.services.subject_major_link_evidence import (
    SubjectMajorLinkRecord,
    load_subject_major_link_evidence,
)
from src.services.subject_trait_mapping_evidence import (
    SubjectTraitMappingRecord,
    load_subject_trait_mapping_evidence,
)

from scripts.career_build_subject_profiles import (
    CURRICULUM_CODE,
    LEGACY_SUBJECTS,
    TOUCHED_SUBJECT_LABELS,
    VERTICAL_SLICE_MAJOR_IDS,
    build,
)


def _profiles():
    return build()[0]

_KNOWN_TRAIT_IDS = {t.trait_id for t in VERTICAL_SLICE_TRAITS}


class SubjectTraitEvidenceSchemaTest(unittest.TestCase):
    def _record(self, status: str, grade, with_evidence: bool) -> dict:
        payload = {
            "subject_id": "subj_test", "trait_id": "causal_analysis", "mapping_status": status,
            "grade": grade, "author_id": "worker_a", "mapping_version": "test_v1",
        }
        if with_evidence:
            payload["curriculum_evidence"] = [
                {
                    "source_url": "https://www.moe.go.kr/example",
                    "source_type": "OFFICIAL_CURRICULUM_MOE_NOTICE",
                    "course_goal_or_standard": "테스트 성취기준",
                    "reason": "테스트용",
                }
            ]
        return payload

    def test_evidenced_requires_grade_1_to_3(self) -> None:
        for grade in (1, 2, 3):
            SubjectTraitMappingRecord.model_validate(self._record("EVIDENCED", grade, True))
        with self.assertRaises(ValidationError):
            SubjectTraitMappingRecord.model_validate(self._record("EVIDENCED", 0, True))

    def test_no_direct_evidence_requires_grade_0(self) -> None:
        SubjectTraitMappingRecord.model_validate(self._record("NO_DIRECT_EVIDENCE", 0, True))
        with self.assertRaises(ValidationError):
            SubjectTraitMappingRecord.model_validate(self._record("NO_DIRECT_EVIDENCE", 1, True))

    def test_unmapped_and_review_required_forbid_grade(self) -> None:
        for status in ("UNMAPPED", "REVIEW_REQUIRED"):
            SubjectTraitMappingRecord.model_validate(self._record(status, None, False))
            with self.assertRaises(ValidationError):
                SubjectTraitMappingRecord.model_validate(self._record(status, 2, True))

    def test_real_data_file_loads_and_validates(self) -> None:
        records = load_subject_trait_mapping_evidence()
        self.assertGreater(len(records), 0)
        for record in records:
            self.assertIn(record.subject_id, TOUCHED_SUBJECT_LABELS)
            self.assertIn(record.trait_id, _KNOWN_TRAIT_IDS)

    def test_no_duplicate_subject_trait_pairs_in_real_data(self) -> None:
        records = load_subject_trait_mapping_evidence()
        pairs = [(r.subject_id, r.trait_id) for r in records]
        self.assertEqual(len(pairs), len(set(pairs)))


class SubjectMajorLinkEvidenceSchemaTest(unittest.TestCase):
    def test_related_requires_evidence(self) -> None:
        with self.assertRaises(ValidationError):
            SubjectMajorLinkRecord.model_validate(
                {
                    "subject_id": "subj_test", "major_id": "industrial_engineering",
                    "link_status": "RELATED", "evidence": [], "author_id": "worker_a",
                    "mapping_version": "test_v1",
                }
            )

    def test_review_required_allows_empty_evidence(self) -> None:
        SubjectMajorLinkRecord.model_validate(
            {
                "subject_id": "subj_test", "major_id": "industrial_engineering",
                "link_status": "REVIEW_REQUIRED", "evidence": [], "author_id": "worker_a",
                "mapping_version": "test_v1",
            }
        )

    def test_real_data_only_targets_vertical_slice_majors(self) -> None:
        records = load_subject_major_link_evidence()
        self.assertGreater(len(records), 0)
        for record in records:
            self.assertIn(record.major_id, VERTICAL_SLICE_MAJOR_IDS)
            self.assertIn(record.subject_id, TOUCHED_SUBJECT_LABELS)


class SubjectProfileBuildTest(unittest.TestCase):
    def test_rerunning_build_is_byte_identical(self) -> None:
        first = [p.model_dump_json() for p in _profiles()]
        second = [p.model_dump_json() for p in _profiles()]
        self.assertEqual(first, second)

    def test_all_eighteen_subjects_are_generated(self) -> None:
        profiles = _profiles()
        self.assertEqual(len(profiles), 18)
        self.assertEqual(len({p.subject_id for p in profiles}), 18)

    def test_legacy_subjects_are_untouched(self) -> None:
        built_by_id = {p.subject_id: p for p in _profiles()}
        for label, _group, _category, major_ids, grades, _reason, _aliases in LEGACY_SUBJECTS:
            subject_id = generate_subject_id(CURRICULUM_CODE, label)
            built = built_by_id[subject_id]
            self.assertEqual(built.label, label)
            self.assertEqual(built.related_major_ids, major_ids)
            self.assertEqual(built.trait_vector, {t: normalize_grade(g) for t, g in grades.items()})

    def test_media_communication_no_longer_auto_includes_common_korean_1(self) -> None:
        """§1/§2: 기존 연결을 자동 승인하지 않는다 — 공통국어1은 이번 재검토로
        REVIEW_REQUIRED로 내려가 media_communication이 related_major_ids에서 빠졌다."""

        profiles = {p.subject_id: p for p in _profiles()}
        common_korean_1 = profiles["subj_0e164d085252178c42a11cb2"]
        self.assertNotIn("media_communication", common_korean_1.related_major_ids)

    def test_industrial_engineering_and_hci_ux_each_have_at_least_one_related_subject(self) -> None:
        """§1: hci_ux/industrial_engineering 관련 과목이 0개였던 문제가 실제로
        해결됐는지 확인한다."""

        profiles = _profiles()
        for major_id in ("industrial_engineering", "hci_ux"):
            related = [p for p in profiles if major_id in p.related_major_ids]
            self.assertGreater(len(related), 0, f"{major_id}에 연결된 과목이 여전히 0개다")

    def test_no_subject_id_was_changed_from_shipped_data(self) -> None:
        shipped_ids = {s.subject_id for s in load_subjects()}
        built_ids = {p.subject_id for p in _profiles()}
        self.assertEqual(shipped_ids, built_ids)

    def test_alias_table_has_no_collisions_and_covers_all_subjects(self) -> None:
        _profiles_list, aliases, _written = build()
        alias_targets: dict[str, set[str]] = {}
        for row in aliases:
            alias_targets.setdefault(row["alias"], set()).add(row["subject_id"])
        for alias, targets in alias_targets.items():
            self.assertEqual(len(targets), 1, f"alias {alias!r}가 여러 과목을 가리킨다: {targets}")
        self.assertEqual({row["subject_id"] for row in aliases}, {p.subject_id for p in _profiles_list})


class SubjectRepositoryTest(unittest.TestCase):
    def test_related_to_major_filters_correctly(self) -> None:
        repository = JsonlSubjectRepository()
        ie_subjects = repository.related_to_major("industrial_engineering")
        self.assertGreater(len(ie_subjects), 0)
        for subject in ie_subjects:
            self.assertIn("industrial_engineering", subject.related_major_ids)

    def test_related_to_major_with_empty_string_returns_empty(self) -> None:
        repository = JsonlSubjectRepository()
        self.assertEqual(repository.related_to_major(""), [])

    def test_get_returns_none_for_unknown_subject(self) -> None:
        repository = JsonlSubjectRepository()
        self.assertIsNone(repository.get("subj_does_not_exist"))


if __name__ == "__main__":
    unittest.main()
