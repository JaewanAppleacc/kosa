"""Service Canonical Major v2(39개) MajorProfile Loader 테스트 — 2026-08-25
지시서(a/major-profiles-v2-38) §2/§6.

`src/data/majors/service_major_profiles_v2.py`(3개 고정 구조를 대체한 새
Loader)가 실제로 39개를 자동 로드하고, Catalog와 어긋나면 Fail-Fast로 막는지
확인한다."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from src.data.majors.service_major_profiles_v2 import SERVICE_MAJOR_PROFILES_V2, load_service_major_profiles_v2
from src.schemas.major import MajorProfile
from src.services.service_canonical_major_v2_loader import load_service_canonical_majors_v2

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _profile(major_id: str) -> MajorProfile:
    return MajorProfile(
        major_id=major_id, label=major_id, interest_vector={}, cognitive_vector={"causal_analysis": 1.0},
        work_style_vector={"planning": 0.67}, environment_vector={}, source_ids=[], extraction_method="manual",
        review_status="draft", profile_version="test", updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def _write(path: Path, profiles: list[MajorProfile]) -> None:
    path.write_text("".join(p.model_dump_json() + "\n" for p in profiles), encoding="utf-8")


class LoaderRealFileTest(unittest.TestCase):
    """실제 커밋된 major_profiles_v2.jsonl로 확인한다(§6 "Profile 정확히 39개",
    "Catalog와 1:1")."""

    def test_exactly_39_profiles_loaded(self) -> None:
        self.assertEqual(len(SERVICE_MAJOR_PROFILES_V2), 39)

    def test_catalog_and_profile_ids_match_exactly(self) -> None:
        catalog_ids = {m.major_id for m in load_service_canonical_majors_v2()}
        profile_ids = {p.major_id for p in SERVICE_MAJOR_PROFILES_V2}
        self.assertEqual(catalog_ids, profile_ids)

    def test_arts_excluded_groups_never_loaded(self) -> None:
        arts_group_ids = {"fine_arts_design", "music", "performing_media_arts", "sports_dance"}
        profile_ids = {p.major_id for p in SERVICE_MAJOR_PROFILES_V2}
        self.assertEqual(profile_ids & arts_group_ids, set())

    def test_hci_ux_present_as_department_level_only_special_case(self) -> None:
        self.assertIn("hci_ux", {p.major_id for p in SERVICE_MAJOR_PROFILES_V2})

    def test_no_duplicate_major_ids(self) -> None:
        ids = [p.major_id for p in SERVICE_MAJOR_PROFILES_V2]
        self.assertEqual(len(ids), len(set(ids)))

    def test_only_trait_ids_from_24_trait_ontology_used(self) -> None:
        from src.services.trait_ontology_v2 import load_trait_ontology_v2

        valid_trait_ids = {t.trait_id for t in load_trait_ontology_v2()}
        for profile in SERVICE_MAJOR_PROFILES_V2:
            all_traits = (
                set(profile.interest_vector) | set(profile.cognitive_vector)
                | set(profile.work_style_vector) | set(profile.environment_vector)
            )
            with self.subTest(major_id=profile.major_id):
                self.assertTrue(all_traits <= valid_trait_ids, all_traits - valid_trait_ids)

    def test_only_weights_0_33_0_67_1_00_used(self) -> None:
        allowed = {0.33, 0.67, 1.00}
        for profile in SERVICE_MAJOR_PROFILES_V2:
            all_weights = [
                w for v in (
                    profile.interest_vector, profile.cognitive_vector,
                    profile.work_style_vector, profile.environment_vector,
                )
                for w in v.values()
            ]
            with self.subTest(major_id=profile.major_id):
                for w in all_weights:
                    self.assertIn(round(w, 2), allowed, (profile.major_id, w))

    def test_every_profile_has_signal_in_at_least_2_vector_groups(self) -> None:
        for profile in SERVICE_MAJOR_PROFILES_V2:
            used_groups = sum(
                1 for v in (
                    profile.interest_vector, profile.cognitive_vector,
                    profile.work_style_vector, profile.environment_vector,
                ) if v
            )
            with self.subTest(major_id=profile.major_id):
                self.assertGreaterEqual(used_groups, 2)

    def test_no_two_majors_share_an_identical_vector_signature(self) -> None:
        """§1 "38개 Profile이 전부 같은 일반론적 Vector가 되지 않도록 검사" — 완전히
        동일한 (Trait, Weight) 조합을 가진 두 Major가 없어야 한다."""

        seen: dict[tuple, str] = {}
        for profile in SERVICE_MAJOR_PROFILES_V2:
            key = (
                frozenset(profile.interest_vector.items()), frozenset(profile.cognitive_vector.items()),
                frozenset(profile.work_style_vector.items()), frozenset(profile.environment_vector.items()),
            )
            self.assertNotIn(key, seen, f"{profile.major_id}와 {seen.get(key)}의 Vector가 완전히 동일하다")
            seen[key] = profile.major_id

    def test_no_review_status_is_pre_approved(self) -> None:
        for profile in SERVICE_MAJOR_PROFILES_V2:
            self.assertEqual(profile.review_status, "draft", profile.major_id)


class LoaderFailFastTest(unittest.TestCase):
    """합성 파일로 Fail-Fast 경로 자체를 직접 검증한다 — 실제 파일을 건드리지 않는다."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.path = Path(self.tmpdir.name) / "major_profiles_v2.jsonl"

    def test_missing_file_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_service_major_profiles_v2(self.path)

    def test_missing_one_catalog_major_raises(self) -> None:
        catalog_ids = sorted(m.major_id for m in load_service_canonical_majors_v2())
        _write(self.path, [_profile(mid) for mid in catalog_ids[:-1]])  # 1개 누락
        with self.assertRaises(ValueError):
            load_service_major_profiles_v2(self.path)

    def test_extra_non_catalog_major_raises(self) -> None:
        catalog_ids = sorted(m.major_id for m in load_service_canonical_majors_v2())
        _write(self.path, [_profile(mid) for mid in catalog_ids] + [_profile("fine_arts_design")])
        with self.assertRaises(ValueError):
            load_service_major_profiles_v2(self.path)

    def test_duplicate_major_id_raises(self) -> None:
        catalog_ids = sorted(m.major_id for m in load_service_canonical_majors_v2())
        profiles = [_profile(mid) for mid in catalog_ids]
        profiles.append(_profile(catalog_ids[0]))  # 중복
        _write(self.path, profiles)
        with self.assertRaises(ValueError):
            load_service_major_profiles_v2(self.path)

    def test_exact_39_catalog_majors_loads_successfully(self) -> None:
        catalog_ids = sorted(m.major_id for m in load_service_canonical_majors_v2())
        _write(self.path, [_profile(mid) for mid in catalog_ids])
        loaded = load_service_major_profiles_v2(self.path)
        self.assertEqual(len(loaded), 39)
        self.assertEqual({p.major_id for p in loaded}, set(catalog_ids))


class BuildScriptDeterminismAndPreservationTest(unittest.TestCase):
    """§6 결정론 — 빌드 스크립트가 두 번 실행해도 같은 결과를 내는지, 그리고
    Evidence 기반 3개 파일·Catalog 파일은 이 라운드가 전혀 건드리지 않는지
    SHA-256으로 확인한다."""

    _PROTECTED_PATHS = (
        _REPO_ROOT / "data" / "master" / "major_trait_mapping_evidence_v2.jsonl",
        _REPO_ROOT / "data" / "master" / "service_canonical_majors_v2.jsonl",
        _REPO_ROOT / "data" / "canonical_major_groups.draft.jsonl",
    )

    def test_build_script_is_deterministic(self) -> None:
        from scripts.career_build_major_profiles_v2 import build

        first = build()
        second = build()
        self.assertEqual([p.model_dump_json() for p in first], [p.model_dump_json() for p in second])

    def test_evidence_and_catalog_files_untouched_by_import(self) -> None:
        import hashlib

        def sha(p: Path) -> str:
            return hashlib.sha256(p.read_bytes()).hexdigest()

        before = {p: sha(p) for p in self._PROTECTED_PATHS}
        load_service_major_profiles_v2()
        after = {p: sha(p) for p in self._PROTECTED_PATHS}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
