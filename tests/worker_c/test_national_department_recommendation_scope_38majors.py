"""career_build_national_department_recommendation_scope_38majors.py 계약 테스트 —
c/national-departments-38-majors §4.

실제 `data/master/department_recommendation_scope.jsonl`을 절대 건드리지 않는다 —
전부 monkeypatch로 모듈 경로 상수를 tmp 경로로 바꿔서 검증한다."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import scripts.career_build_national_department_recommendation_scope_38majors as scope_mod  # noqa: E402
from src.schemas.service_canonical_major_v2 import CanonicalMajorGroupServiceMajorBridgeV2  # noqa: E402


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def _master_row(offering_id: str, *, canonical_major_id: str = "computer_science") -> dict:
    return {
        "department_id": offering_id, "university_name": "테스트대학교", "campus": None,
        "region": "서울", "department_name": "테스트학과", "college_name": "테스트단과대학",
        "admission_unit": None, "department_status": "EXISTING", "source_svy_year": 2025,
        "source_url": "https://www.academyinfo.go.kr/", "canonical_major_id": canonical_major_id,
        "department_url": None,
    }


def _raw_dry_run_row(offering_id: str, *, group_id: str = "computer_science", small_series: str = "089") -> dict:
    return {"offering_id": offering_id, "resolved_canonical_major_group_id": group_id, "official_small_series_code": small_series}


def _group_review_row(group_id: str) -> dict:
    return {"canonical_major_group_id": group_id, "decision": "APPROVE_AS_CLASSIFICATION_GROUP", "resolution_note": "테스트 승인"}


class _Fixture(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

        self.master_path = self.root / "master" / "departments.jsonl"
        self.raw_dry_run_path = self.root / "promotion_candidates.jsonl"
        self.group_review_path = self.root / "reviews" / "canonical_major_group_review_status.jsonl"
        self.scope_path = self.root / "master" / "department_recommendation_scope.jsonl"
        self.legacy_archive_path = self.root / "archive" / "legacy_scope.jsonl"

        self._patches = [
            patch.object(scope_mod, "MASTER_PATH", self.master_path),
            patch.object(scope_mod, "RAW_DRY_RUN_CANDIDATES_PATH", self.raw_dry_run_path),
            patch.object(scope_mod, "GROUP_REVIEW_PATH", self.group_review_path),
            patch.object(scope_mod, "DEFAULT_SCOPE_PATH", self.scope_path),
            patch.object(scope_mod, "LEGACY_SCOPE_ARCHIVE_PATH", self.legacy_archive_path),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)

    def _run(
        self, master_rows: list[dict], raw_rows: list[dict], group_reviews: list[dict],
        bridge_by_group: dict[str, CanonicalMajorGroupServiceMajorBridgeV2],
    ) -> int:
        _write_jsonl(self.master_path, master_rows)
        _write_jsonl(self.raw_dry_run_path, raw_rows)
        _write_jsonl(self.group_review_path, group_reviews)
        with patch.object(scope_mod, "load_canonical_major_group_to_service_major_bridge_v2", return_value=bridge_by_group):
            return scope_mod.main([])


def _bridge_entry(group_id: str, major_id: str) -> CanonicalMajorGroupServiceMajorBridgeV2:
    return CanonicalMajorGroupServiceMajorBridgeV2(
        canonical_major_group_id=group_id, service_major_id=major_id,
        recommendation_status="ACTIVE", decision_reason="테스트 Bridge V2 사유",
    )


class HappyPathTest(_Fixture):
    def test_generates_approved_records_for_every_master_row(self) -> None:
        code = self._run(
            master_rows=[_master_row("off_1"), _master_row("off_2", canonical_major_id="civil_architecture")],
            raw_rows=[_raw_dry_run_row("off_1"), _raw_dry_run_row("off_2", group_id="civil_architecture", small_series="072")],
            group_reviews=[_group_review_row("computer_science"), _group_review_row("civil_architecture")],
            bridge_by_group={
                "computer_science": _bridge_entry("computer_science", "computer_science"),
                "civil_architecture": _bridge_entry("civil_architecture", "civil_architecture"),
            },
        )
        self.assertEqual(code, 0)
        records = [json.loads(line) for line in self.scope_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(records), 2)
        for record in records:
            self.assertEqual(record["eligibility_status"], "APPROVED")
            self.assertTrue(record["recommendation_eligible"])
            self.assertEqual(record["reviewer_id"], "reviewer_1")

    def test_existing_records_archived_even_when_overlapping_ids(self) -> None:
        """2026-08-25 정정 — 이번 라운드는 offering_id 체계가 같아 옛 기록과 겹칠 수
        있다(같은 학과가 재분류). 겹쳐도 오류가 아니라 전부 Archive 후 교체돼야
        한다."""

        _write_jsonl(self.scope_path, [{"department_id": "off_1", "canonical_major_id": "old_major"}])
        code = self._run(
            master_rows=[_master_row("off_1")],
            raw_rows=[_raw_dry_run_row("off_1")],
            group_reviews=[_group_review_row("computer_science")],
            bridge_by_group={"computer_science": _bridge_entry("computer_science", "computer_science")},
        )
        self.assertEqual(code, 0)
        archived = [json.loads(line) for line in self.legacy_archive_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(archived, [{"department_id": "off_1", "canonical_major_id": "old_major"}])
        live = [json.loads(line) for line in self.scope_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(live), 1)
        self.assertEqual(live[0]["canonical_major_id"], "computer_science")


class ValidationFailureTest(_Fixture):
    def test_group_not_approved_rejected(self) -> None:
        with self.assertRaises(scope_mod.ScopeGenerationError):
            self._run(
                master_rows=[_master_row("off_1")],
                raw_rows=[_raw_dry_run_row("off_1")],
                group_reviews=[],
                bridge_by_group={"computer_science": _bridge_entry("computer_science", "computer_science")},
            )

    def test_bridge_not_active_rejected(self) -> None:
        excluded_entry = CanonicalMajorGroupServiceMajorBridgeV2(
            canonical_major_group_id="computer_science", service_major_id=None,
            recommendation_status="EXCLUDED_RECOMMENDATION", decision_reason="테스트",
        )
        with self.assertRaises(scope_mod.ScopeGenerationError):
            self._run(
                master_rows=[_master_row("off_1")],
                raw_rows=[_raw_dry_run_row("off_1")],
                group_reviews=[_group_review_row("computer_science")],
                bridge_by_group={"computer_science": excluded_entry},
            )

    def test_missing_raw_dry_run_row_rejected(self) -> None:
        with self.assertRaises(scope_mod.ScopeGenerationError):
            self._run(
                master_rows=[_master_row("off_1")],
                raw_rows=[],
                group_reviews=[_group_review_row("computer_science")],
                bridge_by_group={"computer_science": _bridge_entry("computer_science", "computer_science")},
            )

    def test_unknown_major_id_missing_academic_field_rejected(self) -> None:
        with self.assertRaises(scope_mod.ScopeGenerationError):
            self._run(
                master_rows=[_master_row("off_1", canonical_major_id="not_a_real_major")],
                raw_rows=[_raw_dry_run_row("off_1", group_id="computer_science")],
                group_reviews=[_group_review_row("computer_science")],
                bridge_by_group={"computer_science": _bridge_entry("computer_science", "not_a_real_major")},
            )


if __name__ == "__main__":
    unittest.main()
