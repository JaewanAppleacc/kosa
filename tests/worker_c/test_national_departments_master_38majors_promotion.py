"""career_promote_national_departments_master_38majors.py 계약 테스트 —
c/national-departments-38-majors §3.

실제 `data/master/departments.jsonl`을 절대 건드리지 않는다 — 전부 monkeypatch로
모듈 경로 상수를 tmp 경로로 바꿔서 검증한다(다른 이 계열 테스트 파일들과 같은 패턴)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]

import sys  # noqa: E402

sys.path.insert(0, str(ROOT))

import scripts.career_promote_national_departments_master_38majors as promote_mod  # noqa: E402
from src.ids import generate_offering_id  # noqa: E402


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def _candidate_row(
    offering_id: str, *, canonical_major_id: str = "computer_science",
    schl_id: str = "schl_1", source_schl_mjr_id: str = "mjr_1",
    university_name: str = "테스트대학교", department_name: str = "테스트학과",
    college_name: str = "테스트단과대학", department_status: str = "EXISTING",
    major_character_name: str = "일반과정",
) -> dict:
    return {
        "offering_id": offering_id, "old_department_id": f"dept_{offering_id}",
        "display_group_id": f"dgrp_{offering_id}", "university_name": university_name,
        "department_name": department_name, "college_name": college_name,
        "department_status": department_status, "major_character_name": major_character_name,
        "status": "READY_FOR_PROMOTION", "blocked_reasons": [],
        "resolved_canonical_major_group_id": canonical_major_id, "resolved_canonical_major_id": canonical_major_id,
        "canonical_major_id": canonical_major_id,
        "resolved_department_url": None, "official_small_series_code": "089",
        "lineage_level": "ROW_IDENTITY_ONLY", "p1_candidate_id": None, "p1_review_decision": None,
        "nce_middle_series_code": None, "nce_review_decision": None, "survey_year": 2025,
        "source_url": "https://www.academyinfo.go.kr/", "source_svy_year": 2025,
        "schl_id": schl_id, "source_schl_mjr_id": source_schl_mjr_id,
    }


def _snapshot_row(
    schl_id: str, source_schl_mjr_id: str, *, department_status: str = "EXISTING",
    large_series_code: str = "E", major_character_name: str = "일반과정",
) -> dict:
    return {
        "schl_id": schl_id, "source_schl_mjr_id": source_schl_mjr_id, "campus": None,
        "region": "서울", "admission_unit": None, "department_status": department_status,
        "official_classification": {"large_series_code": large_series_code},
        "major_character_name": major_character_name,
    }


class _Fixture(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

        self.candidates_path = self.root / "candidates.jsonl"
        self.snapshot_path = self.root / "snapshot.jsonl"
        self.master_path = self.root / "master" / "departments.jsonl"
        self.archive_path = self.root / "archive" / "departments_legacy_1072_8majors.jsonl"
        self.archive_manifest_path = self.root / "archive" / "departments_legacy_1072_8majors.manifest.json"
        self.promotion_manifest_path = self.root / "master" / "departments_promotion_manifest_38majors.json"

        self._patches = [
            patch.object(promote_mod, "CANDIDATES_PATH", self.candidates_path),
            patch.object(promote_mod, "SNAPSHOT_PATH", self.snapshot_path),
            patch.object(promote_mod, "MASTER_PATH", self.master_path),
            patch.object(promote_mod, "ARCHIVE_PATH", self.archive_path),
            patch.object(promote_mod, "ARCHIVE_MANIFEST_PATH", self.archive_manifest_path),
            patch.object(promote_mod, "PROMOTION_MANIFEST_PATH", self.promotion_manifest_path),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)

        _write_jsonl(self.master_path, [{"department_id": "dept_old_1", "canonical_major_id": "old_major"}])

    def _run(self, candidates: list[dict], snapshot: list[dict], *, active_major_ids: frozenset[str]) -> int:
        _write_jsonl(self.candidates_path, candidates)
        _write_jsonl(self.snapshot_path, snapshot)
        with patch.object(
            promote_mod, "load_service_canonical_majors_v2",
            return_value=[
                _FakeMajor(m) for m in active_major_ids
            ],
        ):
            return promote_mod.main([])


class _FakeMajor:
    def __init__(self, major_id: str) -> None:
        self.major_id = major_id
        self.recommendation_status = "ACTIVE"


class HappyPathTest(_Fixture):
    def test_promotes_and_archives_existing_master(self) -> None:
        oid1 = generate_offering_id("schl_1", "mjr_1")
        oid2 = generate_offering_id("schl_2", "mjr_2")
        candidates = [
            _candidate_row(oid1, canonical_major_id="computer_science", schl_id="schl_1", source_schl_mjr_id="mjr_1"),
            _candidate_row(oid2, canonical_major_id="civil_architecture", schl_id="schl_2", source_schl_mjr_id="mjr_2"),
        ]
        snapshot = [_snapshot_row("schl_1", "mjr_1"), _snapshot_row("schl_2", "mjr_2")]

        code = self._run(candidates, snapshot, active_major_ids=frozenset({"computer_science", "civil_architecture"}))
        self.assertEqual(code, 0)

        master_rows = [json.loads(line) for line in self.master_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(master_rows), 2)
        self.assertEqual({r["department_id"] for r in master_rows}, {oid1, oid2})

        archived_rows = [json.loads(line) for line in self.archive_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(archived_rows, [{"department_id": "dept_old_1", "canonical_major_id": "old_major"}])

        manifest = json.loads(self.promotion_manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["master_row_count"], 2)
        self.assertEqual(manifest["distinct_major_count"], 2)

    def test_second_run_refuses_to_overwrite_a_different_already_archived_master(self) -> None:
        """archive_existing_master()는 "이미 Archive가 있는데 지금 Master 내용이
        그것과 다르면 덮어쓰지 않는다"는 원칙을 지킨다 — 1차 실행이 Master를 이미
        새 내용으로 교체했으므로, 그 상태에서 다시 실행하면(Archive는 원래의 옛
        Master만 담고 있는데 현재 Master는 이미 다른 내용) Fail-Closed로 막혀야
        한다(사고로 두 번 실행해도 조용히 잘못된 Archive를 만들지 않는다)."""

        oid1 = generate_offering_id("schl_1", "mjr_1")
        candidates = [_candidate_row(oid1, schl_id="schl_1", source_schl_mjr_id="mjr_1")]
        snapshot = [_snapshot_row("schl_1", "mjr_1")]
        self._run(candidates, snapshot, active_major_ids=frozenset({"computer_science"}))
        with self.assertRaises(promote_mod.PromotionValidationError):
            self._run(candidates, snapshot, active_major_ids=frozenset({"computer_science"}))


class ValidationFailureTest(_Fixture):
    def test_duplicate_offering_id_rejected(self) -> None:
        oid = generate_offering_id("schl_1", "mjr_1")
        candidates = [
            _candidate_row(oid, schl_id="schl_1", source_schl_mjr_id="mjr_1"),
            _candidate_row(oid, schl_id="schl_1", source_schl_mjr_id="mjr_1"),
        ]
        snapshot = [_snapshot_row("schl_1", "mjr_1")]
        with self.assertRaises(promote_mod.PromotionValidationError):
            self._run(candidates, snapshot, active_major_ids=frozenset({"computer_science"}))
        self.assertEqual(self.master_path.read_bytes(), json.dumps({"department_id": "dept_old_1", "canonical_major_id": "old_major"}, ensure_ascii=False).encode() + b"\n")

    def test_unknown_major_id_rejected(self) -> None:
        oid = generate_offering_id("schl_1", "mjr_1")
        candidates = [_candidate_row(oid, canonical_major_id="not_a_real_major", schl_id="schl_1", source_schl_mjr_id="mjr_1")]
        snapshot = [_snapshot_row("schl_1", "mjr_1")]
        with self.assertRaises(promote_mod.PromotionValidationError):
            self._run(candidates, snapshot, active_major_ids=frozenset({"computer_science"}))

    def test_contract_department_rejected(self) -> None:
        """major_character_name은 candidate 행이 아니라 Snapshot 조인으로만 재검증
        한다 — national_master_promotion_candidates.jsonl에는 이 필드가 없다."""

        oid = generate_offering_id("schl_1", "mjr_1")
        candidates = [_candidate_row(oid, schl_id="schl_1", source_schl_mjr_id="mjr_1")]
        snapshot = [_snapshot_row("schl_1", "mjr_1", major_character_name="계약학과")]
        with self.assertRaises(promote_mod.PromotionValidationError):
            self._run(candidates, snapshot, active_major_ids=frozenset({"computer_science"}))

    def test_arts_large_series_rejected(self) -> None:
        oid = generate_offering_id("schl_1", "mjr_1")
        candidates = [_candidate_row(oid, schl_id="schl_1", source_schl_mjr_id="mjr_1")]
        snapshot = [_snapshot_row("schl_1", "mjr_1", large_series_code="C")]
        with self.assertRaises(promote_mod.PromotionValidationError):
            self._run(candidates, snapshot, active_major_ids=frozenset({"computer_science"}))

    def test_missing_snapshot_join_rejected(self) -> None:
        oid = generate_offering_id("schl_1", "mjr_1")
        candidates = [_candidate_row(oid, schl_id="schl_1", source_schl_mjr_id="mjr_1")]
        with self.assertRaises(promote_mod.SnapshotJoinError):
            self._run(candidates, [], active_major_ids=frozenset({"computer_science"}))

    def test_zero_candidates_rejected(self) -> None:
        with self.assertRaises(promote_mod.PromotionValidationError):
            self._run([], [], active_major_ids=frozenset({"computer_science"}))


if __name__ == "__main__":
    unittest.main()
