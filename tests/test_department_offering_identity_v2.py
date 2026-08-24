"""Department Offering Identity v2 + 16개 충돌 판정 반영 테스트 — 2026-08-25
지시서(a/offering-identity-v2).

Bridge/P1/N.C.E/Canonical Major Group 검수와 같은 2계층 전략(정적 소스
검증 + 실제 빌더/Repository/검증 스크립트 호출)을 따른다. 모든 저장
테스트는 `tempfile.TemporaryDirectory()`만 쓰고 실제
`data/reviews/`·`data/academyinfo_work/`·`data/master/` 파일은 절대
건드리지 않는다 — 매 테스트가 실제 파일들의 SHA-256을 스냅샷하고 종료 시
재확인한다."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from src.engines.department_identity_collision_classifier import RowClassificationInput, classify_row
from src.repositories.department_offering_repository import (
    DuplicateOfferingIdError,
    JsonlDepartmentOfferingRepository,
)
from src.schemas.department_id_migration_map import DepartmentIdMigrationMapEntry
from src.schemas.department_identity_collision_row_review import DepartmentIdentityCollisionRowReview
from src.schemas.department_offering_identity import DepartmentOfferingIdentity
from src.services.department_identity_collision_row_review_store import (
    DuplicateRowReviewKeyError,
    load_row_review_entries_by_key,
    save_row_review_entries,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = _REPO_ROOT / "scripts" / "career_build_department_offering_identity_v2.py"
DRY_RUN_SCRIPT = _REPO_ROOT / "eval" / "department_offering_identity_v2_dry_run.py"
COLLISION_REVIEW_PATH = (
    _REPO_ROOT / "data" / "academyinfo_work" / "2025" / "packets" / "department_identity_collision_review.jsonl"
)
MASTER_PATH = _REPO_ROOT / "data" / "master" / "departments.jsonl"
ROW_REVIEW_REAL_PATH = _REPO_ROOT / "data" / "reviews" / "department_identity_collision_row_review_status.jsonl"
OFFERING_IDENTITY_REAL_PATH = (
    _REPO_ROOT / "data" / "academyinfo_work" / "2025" / "packets" / "department_offering_identity_v2.jsonl"
)
MIGRATION_MAP_REAL_PATH = (
    _REPO_ROOT / "data" / "academyinfo_work" / "2025" / "packets" / "department_id_migration_map.jsonl"
)
JSON_REPORT = _REPO_ROOT / "outputs" / "evaluation" / "department_offering_identity_v2_dry_run.json"
MD_REPORT = _REPO_ROOT / "outputs" / "evaluation" / "department_offering_identity_v2_dry_run.md"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class ClassifierTest(unittest.TestCase):
    """순수 함수 `classify_row()` — 규칙 자체와, 실제 32행 전체에 적용했을 때
    실측값(2026-08-25 사용자 확인)과 정확히 일치하는지 확인한다."""

    def test_abolished_always_excluded_regardless_of_character(self) -> None:
        for character in ("일반과정", "계약학과", "산업체위탁"):
            result = classify_row(RowClassificationInput("ABOLISHED", character, True))
            self.assertEqual(result.recommendation_scope_decision, "OUT_OF_RECOMMENDATION_SCOPE")
            self.assertEqual(result.exclusion_reason, "ABOLISHED")
            self.assertFalse(result.is_recommendation_representative)

    def test_contract_or_industry_excluded_even_if_existing_and_classifiable(self) -> None:
        for character in ("계약학과", "산업체위탁"):
            result = classify_row(RowClassificationInput("EXISTING", character, True))
            self.assertEqual(result.exclusion_reason, "CONTRACT_OR_INDUSTRY_COMMISSIONED")
            self.assertFalse(result.is_recommendation_representative)

    def test_general_track_but_unclassifiable_excluded(self) -> None:
        result = classify_row(RowClassificationInput("EXISTING", "일반과정", False))
        self.assertEqual(result.exclusion_reason, "UNCLASSIFIED_SMALL_SERIES")
        self.assertFalse(result.is_recommendation_representative)

    def test_general_track_existing_classifiable_is_representative(self) -> None:
        result = classify_row(RowClassificationInput("EXISTING", "일반과정", True))
        self.assertEqual(result.recommendation_scope_decision, "IN_RECOMMENDATION_SCOPE")
        self.assertIsNone(result.exclusion_reason)
        self.assertTrue(result.is_recommendation_representative)

    def test_applied_to_real_32_rows_matches_confirmed_tallies(self) -> None:
        """2026-08-25 사용자 확인값: 노출 6 / 계약·위탁(EXISTING) 제외 7 /
        ABOLISHED 제외 17(8+1+8) / 미분류 제외 2 / 합계 32."""

        groups = _read_jsonl(COLLISION_REVIEW_PATH)
        exposed = contract = abolished = unclassified = 0
        for group in groups:
            for c in group["candidates"]:
                cr = c["classification_result"]
                has_group = cr["mapping_status"] != "UNMAPPED" and bool(cr["candidate_canonical_major_ids"])
                result = classify_row(
                    RowClassificationInput(c["department_status"], c["major_character_name"], has_group)
                )
                if result.is_recommendation_representative:
                    exposed += 1
                elif result.exclusion_reason == "CONTRACT_OR_INDUSTRY_COMMISSIONED":
                    contract += 1
                elif result.exclusion_reason == "ABOLISHED":
                    abolished += 1
                elif result.exclusion_reason == "UNCLASSIFIED_SMALL_SERIES":
                    unclassified += 1
        self.assertEqual(exposed, 6)
        self.assertEqual(contract, 7)
        self.assertEqual(abolished, 17)
        self.assertEqual(unclassified, 2)
        self.assertEqual(exposed + contract + abolished + unclassified, 32)


class RowReviewSchemaInvariantTest(unittest.TestCase):
    """§ Group Review 불변식 감사와 같은 원칙 — is_recommendation_representative·
    recommendation_scope_decision·exclusion_reason이 서로 모순되는 조합으로는
    저장할 수 없다."""

    def _base_kwargs(self) -> dict:
        return dict(
            source_record_id="src_x", department_id="dept_x", offering_id="off_x", schl_id="s",
            source_schl_mjr_id="m", major_character="일반과정", department_status="EXISTING",
            decision_basis_url="https://www.academyinfo.go.kr/", decided_at="2026-08-25T00:00:00+09:00",
        )

    def test_representative_true_requires_in_scope_and_no_reason(self) -> None:
        entry = DepartmentIdentityCollisionRowReview(
            **self._base_kwargs(), recommendation_scope_decision="IN_RECOMMENDATION_SCOPE",
            exclusion_reason=None, is_recommendation_representative=True,
        )
        self.assertTrue(entry.is_recommendation_representative)

        with self.assertRaises(Exception):
            DepartmentIdentityCollisionRowReview(
                **self._base_kwargs(), recommendation_scope_decision="OUT_OF_RECOMMENDATION_SCOPE",
                exclusion_reason=None, is_recommendation_representative=True,
            )
        with self.assertRaises(Exception):
            DepartmentIdentityCollisionRowReview(
                **self._base_kwargs(), recommendation_scope_decision="IN_RECOMMENDATION_SCOPE",
                exclusion_reason="ABOLISHED", is_recommendation_representative=True,
            )

    def test_representative_false_requires_out_of_scope_and_a_reason(self) -> None:
        entry = DepartmentIdentityCollisionRowReview(
            **self._base_kwargs(), recommendation_scope_decision="OUT_OF_RECOMMENDATION_SCOPE",
            exclusion_reason="CONTRACT_OR_INDUSTRY_COMMISSIONED", is_recommendation_representative=False,
        )
        self.assertFalse(entry.is_recommendation_representative)

        with self.assertRaises(Exception):
            DepartmentIdentityCollisionRowReview(
                **self._base_kwargs(), recommendation_scope_decision="IN_RECOMMENDATION_SCOPE",
                exclusion_reason="ABOLISHED", is_recommendation_representative=False,
            )
        with self.assertRaises(Exception):
            DepartmentIdentityCollisionRowReview(
                **self._base_kwargs(), recommendation_scope_decision="OUT_OF_RECOMMENDATION_SCOPE",
                exclusion_reason=None, is_recommendation_representative=False,
            )


class OfferingRepositoryTest(unittest.TestCase):
    def _offering(self, offering_id: str, source_record_id: str, major_character: str = "일반과정") -> DepartmentOfferingIdentity:
        return DepartmentOfferingIdentity(
            offering_id=offering_id, display_group_id="dgrp_x", provider="academyinfo", schl_id="s",
            source_schl_mjr_id=source_record_id, source_record_id=source_record_id, source_svy_year=2025,
            old_department_id="dept_x", university_name="U", college_name="C", department_name="D",
            major_character=major_character, department_status="EXISTING",
        )

    def test_duplicate_offering_id_fails_fast(self) -> None:
        dup = [self._offering("off_a", "src_1", "일반과정"), self._offering("off_a", "src_2", "계약학과")]
        with self.assertRaises(DuplicateOfferingIdError):
            JsonlDepartmentOfferingRepository(dup)

    def test_display_name_duplicates_are_allowed(self) -> None:
        """§4 "표시명 그룹 중복은 허용" — display_group_id가 같아도 offering_id
        만 다르면 정상적으로 둘 다 로드된다."""

        rows = [self._offering("off_a", "src_1"), self._offering("off_b", "src_2")]
        repo = JsonlDepartmentOfferingRepository(rows)
        self.assertEqual(len(repo), 2)
        self.assertEqual(len(repo.by_display_group("dgrp_x")), 2)

    def test_no_row_silently_overwritten_or_dropped(self) -> None:
        rows = [self._offering("off_a", "src_1"), self._offering("off_b", "src_2"), self._offering("off_c", "src_3")]
        repo = JsonlDepartmentOfferingRepository(rows)
        self.assertEqual(len(repo.all()), 3)
        for r in rows:
            self.assertIsNotNone(repo.get(r.offering_id))


class _PreservationTestBase(unittest.TestCase):
    """§5/§6 — 지시서가 명시한 파일들의 SHA-256을 테스트 전후로 직접
    대조한다."""

    _PROTECTED_PATHS = [COLLISION_REVIEW_PATH, MASTER_PATH]
    _OPTIONAL_PATHS = [ROW_REVIEW_REAL_PATH, OFFERING_IDENTITY_REAL_PATH, MIGRATION_MAP_REAL_PATH]

    def setUp(self) -> None:
        import tempfile

        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.row_review_path = Path(self.tmpdir.name) / "row_review.jsonl"

        self._before = self._snapshot()
        self.addCleanup(self._assert_unchanged)

    def _snapshot(self) -> dict[str, object]:
        snap: dict[str, object] = {str(p): _sha256(p) for p in self._PROTECTED_PATHS}
        for p in self._OPTIONAL_PATHS:
            snap[f"__exists__{p}"] = p.exists()
            if p.exists():
                snap[f"__sha__{p}"] = _sha256(p)
        return snap

    def _assert_unchanged(self) -> None:
        self.assertEqual(self._before, self._snapshot(), "실제 파일이 테스트 중 바뀌었다 — 절대 금지 위반")


class BuilderTest(_PreservationTestBase):
    def test_build_produces_32_row_reviews_all_approved(self) -> None:
        from scripts.career_build_department_offering_identity_v2 import build_row_reviews_and_offerings

        reviews, offerings = build_row_reviews_and_offerings()
        self.assertEqual(len(reviews), 32)
        self.assertEqual(len(offerings), 32)
        self.assertTrue(all(r.reviewer_1_status == "APPROVE" for r in reviews))

    def test_offering_ids_all_unique(self) -> None:
        from scripts.career_build_department_offering_identity_v2 import build_row_reviews_and_offerings

        _, offerings = build_row_reviews_and_offerings()
        ids = [o.offering_id for o in offerings]
        self.assertEqual(len(ids), len(set(ids)))

    def test_migration_map_has_51_rows_no_duplicate_old_id(self) -> None:
        from scripts.career_build_department_offering_identity_v2 import build_migration_map, build_row_reviews_and_offerings

        _, offerings = build_row_reviews_and_offerings()
        migration = build_migration_map(offerings)
        self.assertEqual(len(migration), 51)
        old_ids = [m.old_department_id for m in migration]
        self.assertEqual(len(old_ids), len(set(old_ids)))
        master_count = sum(1 for m in migration if m.migration_status == "MASTER_UNCHANGED_SOURCE_IDENTIFIERS_UNAVAILABLE")
        collision_count = sum(1 for m in migration if m.migration_status == "RESOLVED_ONE_TO_MANY_COLLISION")
        self.assertEqual(master_count, 35)
        self.assertEqual(collision_count, 16)

    def test_migration_map_one_to_many_for_all_16_collision_groups(self) -> None:
        from scripts.career_build_department_offering_identity_v2 import build_migration_map, build_row_reviews_and_offerings

        _, offerings = build_row_reviews_and_offerings()
        migration = build_migration_map(offerings)
        collision_entries = [m for m in migration if m.migration_status == "RESOLVED_ONE_TO_MANY_COLLISION"]
        for entry in collision_entries:
            self.assertGreaterEqual(len(entry.new_offering_ids), 2, entry.old_department_id)

    def test_master_entries_have_no_fabricated_offering_ids(self) -> None:
        """§3 "값을 지어내지 않는다" — Master 35건은 원본에 schl_id가 없으므로
        new_offering_ids가 비어 있어야 한다."""

        from scripts.career_build_department_offering_identity_v2 import build_migration_map, build_row_reviews_and_offerings

        _, offerings = build_row_reviews_and_offerings()
        migration = build_migration_map(offerings)
        master_entries = [m for m in migration if m.migration_status == "MASTER_UNCHANGED_SOURCE_IDENTIFIERS_UNAVAILABLE"]
        self.assertEqual(len(master_entries), 35)
        for entry in master_entries:
            self.assertEqual(entry.new_offering_ids, [])

    def test_full_script_writes_three_files_via_tempdir_paths_without_touching_real_files(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            row_review_path = Path(tmp) / "row_review.jsonl"
            offering_path = Path(tmp) / "offering_identity.jsonl"
            migration_path = Path(tmp) / "migration_map.jsonl"

            from scripts.career_build_department_offering_identity_v2 import (
                _write_jsonl,
                build_migration_map,
                build_row_reviews_and_offerings,
            )

            reviews, offerings = build_row_reviews_and_offerings()
            migration = build_migration_map(offerings)
            _write_jsonl(row_review_path, [r.model_dump_json() for r in reviews])
            _write_jsonl(offering_path, [o.model_dump_json() for o in offerings])
            _write_jsonl(migration_path, [m.model_dump_json() for m in migration])

            self.assertTrue(row_review_path.exists())
            self.assertEqual(len(_read_jsonl(row_review_path)), 32)
            self.assertEqual(len(_read_jsonl(offering_path)), 32)
            self.assertEqual(len(_read_jsonl(migration_path)), 51)


class RowReviewStoreTest(_PreservationTestBase):
    def test_get_style_load_never_writes_file(self) -> None:
        load_row_review_entries_by_key(self.row_review_path)
        load_row_review_entries_by_key(self.row_review_path)
        self.assertFalse(self.row_review_path.exists())

    def test_duplicate_key_rejected_on_save(self) -> None:
        base = dict(
            department_id="dept_x", offering_id="off_x", schl_id="s", source_schl_mjr_id="m",
            major_character="일반과정", department_status="EXISTING",
            recommendation_scope_decision="IN_RECOMMENDATION_SCOPE", exclusion_reason=None,
            is_recommendation_representative=True, decision_basis_url="https://www.academyinfo.go.kr/",
            reviewer_1_status="APPROVE", decided_at="2026-08-25T00:00:00+09:00",
        )
        dup = [
            DepartmentIdentityCollisionRowReview(source_record_id="dup1", **base),
            DepartmentIdentityCollisionRowReview(source_record_id="dup1", **base),
        ]
        with self.assertRaises(DuplicateRowReviewKeyError):
            save_row_review_entries(dup, self.row_review_path)
        self.assertFalse(self.row_review_path.exists())


class DryRunVerificationTest(_PreservationTestBase):
    def test_offering_id_duplicate_zero_and_tallies_match_confirmed_values(self) -> None:
        from eval.department_offering_identity_v2_dry_run import run_row_level_verification
        from scripts.career_build_department_offering_identity_v2 import build_migration_map, build_row_reviews_and_offerings

        reviews, offerings = build_row_reviews_and_offerings()
        with self._tempdir_paths() as (row_review_path, offering_path):
            from scripts.career_build_department_offering_identity_v2 import _write_jsonl

            _write_jsonl(row_review_path, [r.model_dump_json() for r in reviews])
            _write_jsonl(offering_path, [o.model_dump_json() for o in offerings])

            result = run_row_level_verification(row_review_path=row_review_path, offering_identity_path=offering_path)

        self.assertEqual(result["offering_id_duplicate_count"], 0)
        self.assertEqual(result["exposed_general_track_count"], 6)
        self.assertEqual(result["contract_or_industry_excluded_count"], 7)
        self.assertEqual(result["abolished_excluded_count"], 17)
        self.assertEqual(result["undecided_group_count"], 0)
        self.assertEqual(result["meaningful_representative_correction_count"], 6)
        self.assertTrue(result["contract_department_tag_consistent_with_original"])
        self.assertTrue(result["sungkyunkwan_semiconductor_systems_eng_has_no_representative"])
        self.assertTrue(result["chungnam_pharmacy_representative_is_six_year_general_track"])

    def _tempdir_paths(self):
        import contextlib
        import tempfile

        @contextlib.contextmanager
        def _cm():
            with tempfile.TemporaryDirectory() as tmp:
                yield Path(tmp) / "row_review.jsonl", Path(tmp) / "offering_identity.jsonl"

        return _cm()


class DeterminismTest(unittest.TestCase):
    """반드시 별도 프로세스로 실행한다(PYTHONHASHSEED가 프로세스마다 달라야
    set/dict 순회 순서 버그가 드러난다)."""

    def _run_build_and_dry_run(self, hash_seed: str) -> tuple[bytes, bytes, bytes, bytes]:
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = hash_seed
        env["PYTHONPATH"] = str(_REPO_ROOT)
        build_proc = subprocess.run(
            [sys.executable, str(BUILD_SCRIPT)], cwd=_REPO_ROOT, capture_output=True, timeout=60, env=env,
        )
        self.assertEqual(build_proc.returncode, 0, build_proc.stderr.decode("utf-8", "replace")[:4000])
        dry_run_proc = subprocess.run(
            [sys.executable, str(DRY_RUN_SCRIPT)], cwd=_REPO_ROOT, capture_output=True, timeout=60, env=env,
        )
        self.assertEqual(dry_run_proc.returncode, 0, dry_run_proc.stderr.decode("utf-8", "replace")[:4000])
        # 2026-08-25 병합 전 감사(9b0a495) 정책 6 — Migration Map(51행)도
        # 결정론 대상에 포함한다(이전 버전은 이 파일을 빠뜨리고 있었다).
        return (
            ROW_REVIEW_REAL_PATH.read_bytes(), OFFERING_IDENTITY_REAL_PATH.read_bytes(),
            MIGRATION_MAP_REAL_PATH.read_bytes(), JSON_REPORT.read_bytes(),
        )

    def test_two_runs_with_different_hash_seeds_are_byte_identical(self) -> None:
        before_master = _sha256(MASTER_PATH)
        before_collision = _sha256(COLLISION_REVIEW_PATH)
        try:
            first = self._run_build_and_dry_run("111")
            second = self._run_build_and_dry_run("222")
            self.assertEqual(first, second, "PYTHONHASHSEED만 바뀌어도 산출물이 달라진다")
        finally:
            self.assertEqual(_sha256(MASTER_PATH), before_master, "Master가 결정론 테스트 중 바뀌었다")
            self.assertEqual(_sha256(COLLISION_REVIEW_PATH), before_collision, "충돌 감사 패킷이 결정론 테스트 중 바뀌었다")


class NotWiredIntoExistingRepositoryOrPublicApiTest(unittest.TestCase):
    """§4/§5 — 새 Offering Repository가 기존 C 소유 `department_repository.py`나
    Master를 import하지 않고, 공개 학생 API 어디에도 이 신규 모듈에 대한 참조가
    없어야 한다."""

    def test_offering_repository_does_not_import_department_repository(self) -> None:
        src = (_REPO_ROOT / "src" / "repositories" / "department_offering_repository.py").read_text(encoding="utf-8")
        for forbidden in ("import department_repository", "from src.repositories.department_repository"):
            self.assertNotIn(forbidden, src)

    def test_offering_repository_does_not_read_master(self) -> None:
        src = (_REPO_ROOT / "src" / "repositories" / "department_offering_repository.py").read_text(encoding="utf-8")
        for forbidden in ("DEFAULT_MASTER_PATH", "load_departments(", "JsonlDepartmentRepository("):
            self.assertNotIn(forbidden, src)

    def test_public_api_module_does_not_import_new_offering_modules(self) -> None:
        main_src = (_REPO_ROOT / "src" / "api" / "main.py").read_text(encoding="utf-8")
        for forbidden in (
            "department_offering_repository", "department_offering_identity", "department_identity_collision_row_review",
            "department_id_migration_map", "career_build_department_offering_identity_v2",
        ):
            self.assertNotIn(forbidden, main_src)


if __name__ == "__main__":
    unittest.main()
