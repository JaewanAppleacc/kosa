"""career_finalize_mapping_review_closeout.py 테스트 —
a/final-mapping-review-closeout.

전부 `review_root`를 tmp 디렉터리로 주입해서 실제 `data/reviews/`를 절대 건드리지
않는다(Draft·Master 파일은 원래도 읽기 전용이다 — 이 스크립트가 쓰는 값이 아니다)."""

from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_PROTECTED_REAL_REVIEW_FILES = [
    ROOT / "data" / "reviews" / "canonical_major_group_review_status.jsonl",
    ROOT / "data" / "reviews" / "canonical_major_group_bridge_review_status.json",
    ROOT / "data" / "reviews" / "canonical_major_group_bridge_scope_review_status.jsonl",
    ROOT / "data" / "reviews" / "academyinfo_p1_classification_review_status.jsonl",
    ROOT / "data" / "reviews" / "academyinfo_nce_middle_series_review_status.jsonl",
]


def _hash_or_absent(path: Path) -> str:
    if not path.exists():
        return "ABSENT"
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


class DoesNotTouchRealReviewFilesTest(unittest.TestCase):
    def test_run_closeout_with_tmp_root_leaves_real_reviews_untouched(self) -> None:
        import tempfile

        from scripts.career_finalize_mapping_review_closeout import run_closeout

        before = {str(p): _hash_or_absent(p) for p in _PROTECTED_REAL_REVIEW_FILES}
        with tempfile.TemporaryDirectory() as tmp:
            run_closeout(review_root=Path(tmp))
        after = {str(p): _hash_or_absent(p) for p in _PROTECTED_REAL_REVIEW_FILES}
        self.assertEqual(before, after, "실제 data/reviews/ 파일이 변경됐다")

    def test_run_closeout_does_not_touch_draft_or_master_files(self) -> None:
        import hashlib
        import tempfile

        from scripts.career_finalize_mapping_review_closeout import run_closeout

        protected = [
            ROOT / "data" / "canonical_major_groups.draft.jsonl",
            ROOT / "data" / "master" / "canonical_major_group_bridge.draft.jsonl",
            ROOT / "data" / "master" / "departments.jsonl",
            ROOT / "data" / "academyinfo_work" / "2025" / "packets" / "p1_classification_review.jsonl",
            ROOT / "data" / "academyinfo_work" / "2025" / "packets" / "nce_reexaminable_middle_series_clusters.jsonl",
        ]
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
        with tempfile.TemporaryDirectory() as tmp:
            run_closeout(review_root=Path(tmp))
        after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
        self.assertEqual(before, after)


class ClosureLogicTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import tempfile

        from scripts.career_finalize_mapping_review_closeout import run_closeout

        cls._tmp = tempfile.mkdtemp(prefix="fmrc_test_")
        cls.review_root = Path(cls._tmp)
        cls.results = run_closeout(review_root=cls.review_root)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def test_group_all_42_approved_including_arts(self) -> None:
        r = self.results["canonical_major_group"]
        self.assertEqual(r["total"], 42)
        self.assertEqual(r["tbd_count"], 0)
        self.assertEqual(r["hold_count"], 0)
        self.assertEqual(r["approve_count"], 42)

        path = self.review_root / "canonical_major_group_review_status.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        for arts_id in ("fine_arts_design", "music", "performing_media_arts", "sports_dance"):
            row = next(r for r in rows if r["canonical_major_group_id"] == arts_id)
            self.assertEqual(row["decision"], "APPROVE_AS_CLASSIFICATION_GROUP")
            self.assertEqual(row["reviewer_1_status"], "APPROVE")

    def test_bridge_mapping_only_touches_six_revise_rows(self) -> None:
        r = self.results["bridge_mapping"]
        # tmp root는 비어서 시작하므로 이 테스트에서는 "이번 실행에서 실제로 건드린
        # 행 수"만 확인한다(38개 기존 APPROVE는 실제 data/reviews/에서만 검증 가능).
        self.assertEqual(r["updated_this_run"], 6)

        path = self.review_root / "canonical_major_group_bridge_review_status.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 6)
        for row in rows:
            self.assertEqual(row["reviewer_1_status"], "APPROVE")

    def test_bridge_mapping_preserves_pre_existing_revise_comment(self) -> None:
        """기존 REVISE 6건에 이미 사람이 남긴 코멘트가 있는 상태에서 시작해도(빈
        tmp dir가 아니라 실제와 같은 초기 상태) 그 코멘트 원문이 그대로 남는지
        확인한다 — §6 '코멘트 원문 삭제 금지'."""

        import tempfile

        from scripts.career_finalize_mapping_review_closeout import _apply_bridge_mapping_closure
        from src.schemas.canonical_major_group_bridge_review import bridge_review_key
        from src.services.canonical_major_group_bridge_review_store import save_bridge_review_entries
        from src.schemas.canonical_major_group_bridge_review import CanonicalMajorGroupBridgeReview

        seeded = CanonicalMajorGroupBridgeReview(
            canonical_major_group_id="business", canonical_major_id="business_administration",
            reviewer_1_status="REVISE", reviewer_1_comment="경영학 소계열만 포함해야 한다(실제 사람 코멘트).",
            revision="1",
        )
        with tempfile.TemporaryDirectory() as tmp:
            seed_path = Path(tmp) / "canonical_major_group_bridge_review_status.json"
            save_bridge_review_entries([seeded], seed_path)
            _apply_bridge_mapping_closure(review_status_path=seed_path)
            rows = json.loads(seed_path.read_text(encoding="utf-8"))
            row = next(r for r in rows if bridge_review_key(r["canonical_major_group_id"], r["canonical_major_id"]) == bridge_review_key("business", "business_administration"))
            self.assertEqual(row["reviewer_1_status"], "APPROVE")
            self.assertIn("경영학 소계열만 포함해야 한다", row["reviewer_1_comment"])

    def test_bridge_scope_all_44_approved_department_review_required_not_changed_to_full_group(self) -> None:
        r = self.results["bridge_scope"]
        self.assertEqual(r["total"], 44)
        self.assertEqual(r["tbd_count"], 0)
        self.assertEqual(r["approve_count"], 44)
        self.assertEqual(r["scope_type_breakdown"].get("DEPARTMENT_REVIEW_REQUIRED"), 2)
        self.assertEqual(r["scope_type_breakdown"].get("INCLUDED_SMALL_SERIES_ONLY"), 4)
        self.assertEqual(r["scope_type_breakdown"].get("EXCLUDED_RECOMMENDATION"), 5)
        self.assertEqual(r["scope_type_breakdown"].get("FULL_GROUP"), 4)

    def test_p1_374_all_reviewed_none_auto_creates_new_major(self) -> None:
        r = self.results["p1_classification"]
        self.assertEqual(r["total"], 374)
        self.assertEqual(r["tbd_count"], 0)
        self.assertEqual(
            r["approve_count"] + r["exclude_arts_count"] + r["keep_unmapped_count"]
            + r["needs_official_curriculum_count"] + r["revise_candidate_count"] + r["hold_count"],
            374,
        )

    def test_p1_approve_only_for_real_service_majors_with_sufficient_evidence(self) -> None:
        path = self.review_root / "academyinfo_p1_classification_review_status.jsonl"
        rows = {
            json.loads(line)["candidate_id"]: json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
        }
        from src.services.academyinfo_p1_classification_loader import load_p1_classification_packet

        entries = {e.candidate_id: e for e in load_p1_classification_packet()}
        for candidate_id, review_row in rows.items():
            entry = entries[candidate_id]
            if review_row["decision"] == "APPROVE_PROPOSED_CANDIDATE":
                self.assertEqual(len(entry.candidate_canonical_major_ids), 1)
                self.assertTrue(entry.judgment_evidence_sufficient)

    def test_nce_24_all_reviewed_no_group_treated_as_department_auto_promotion(self) -> None:
        r = self.results["nce_middle_series"]
        self.assertEqual(r["total"], 24)
        self.assertEqual(r["tbd_count"], 0)
        self.assertEqual(r["accept_as_candidate_count"], 15)
        self.assertEqual(r["require_department_review_count"], 9)

    def test_resolution_note_records_the_exact_required_phrase(self) -> None:
        expected = "사용자 최종 일괄 검수 결정에 따라 기존 근거·범위 결정을 승인"
        for filename in (
            "canonical_major_group_review_status.jsonl",
            "canonical_major_group_bridge_scope_review_status.jsonl",
            "academyinfo_p1_classification_review_status.jsonl",
            "academyinfo_nce_middle_series_review_status.jsonl",
        ):
            path = self.review_root / filename
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            for row in rows:
                self.assertEqual(row["resolution_note"], expected)

    def test_idempotent_rerun_makes_zero_additional_updates(self) -> None:
        from scripts.career_finalize_mapping_review_closeout import run_closeout

        second = run_closeout(review_root=self.review_root)
        for area, result in second.items():
            self.assertEqual(result["updated_this_run"], 0, f"{area}가 재실행에서도 업데이트됨(멱등 아님)")


class ImportOrderTest(unittest.TestCase):
    """§9 "Import 순서 4종" — 이 스크립트가 쓰는 4개 검수 도메인 모듈(Group/
    Bridge+Scope/P1/N.C.E)을 단독으로, 그리고 두 가지 순서로 새 인터프리터
    프로세스에서 각각 import해도 순환 참조·부작용 없이 성공하는지 확인한다."""

    def _import_in_subprocess(self, import_lines: list[str]) -> None:
        import subprocess
        import sys

        code = "\n".join(import_lines) + "\nprint('OK')"
        proc = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace")[:2000])

    def test_each_review_service_module_imports_standalone(self) -> None:
        modules = [
            "src.review_ui.canonical_major_group_review_service",
            "src.review_ui.canonical_major_group_bridge_review_service",
            "src.review_ui.academyinfo_p1_classification_review_service",
            "src.review_ui.academyinfo_nce_middle_series_review_service",
        ]
        for module in modules:
            self._import_in_subprocess([f"import {module}"])

    def test_all_four_import_together_forward_order(self) -> None:
        self._import_in_subprocess([
            "import src.review_ui.canonical_major_group_review_service",
            "import src.review_ui.canonical_major_group_bridge_review_service",
            "import src.review_ui.academyinfo_p1_classification_review_service",
            "import src.review_ui.academyinfo_nce_middle_series_review_service",
        ])

    def test_all_four_import_together_reverse_order(self) -> None:
        self._import_in_subprocess([
            "import src.review_ui.academyinfo_nce_middle_series_review_service",
            "import src.review_ui.academyinfo_p1_classification_review_service",
            "import src.review_ui.canonical_major_group_bridge_review_service",
            "import src.review_ui.canonical_major_group_review_service",
        ])

    def test_finalize_script_itself_imports_cleanly(self) -> None:
        self._import_in_subprocess(["import scripts.career_finalize_mapping_review_closeout"])


if __name__ == "__main__":
    unittest.main()
