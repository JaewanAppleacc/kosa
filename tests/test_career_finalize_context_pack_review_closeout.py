"""career_finalize_context_pack_review_closeout.py 테스트 —
a/final-integration-master-promotion §7.

실제 `data/reviews/context_packs/`를 tmp 디렉터리로 복사한 뒤 `run_closeout(
review_status_dir=tmp)`로 격리 실행한다 — 실제 파일은 절대 건드리지 않는다."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_REAL_REVIEW_DIR = ROOT / "data" / "reviews" / "context_packs"

from scripts.career_finalize_context_pack_review_closeout import (  # noqa: E402
    RESOLUTION_NOTE,
    run_closeout,
)


def _hash_dir(path: Path) -> dict[str, str]:
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(path.glob("*_review_status.json"))
    }


class DoesNotTouchRealReviewFilesTest(unittest.TestCase):
    def test_run_closeout_with_tmp_dir_leaves_real_files_untouched(self) -> None:
        before = _hash_dir(_REAL_REVIEW_DIR)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            for f in _REAL_REVIEW_DIR.glob("*_review_status.json"):
                shutil.copy(f, tmp_dir / f.name)
            run_closeout(review_status_dir=tmp_dir)
        after = _hash_dir(_REAL_REVIEW_DIR)
        self.assertEqual(before, after, "실제 data/reviews/context_packs/ 파일이 변경됐다")


class ClosureLogicTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp(prefix="fcprc_test_")
        cls.review_status_dir = Path(cls._tmp)
        for f in _REAL_REVIEW_DIR.glob("*_review_status.json"):
            shutil.copy(f, cls.review_status_dir / f.name)
        cls.before_comments = cls._load_comments_by_file(cls.review_status_dir)
        cls.results = run_closeout(review_status_dir=cls.review_status_dir)
        cls.after_comments = cls._load_comments_by_file(cls.review_status_dir)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._tmp, ignore_errors=True)

    @staticmethod
    def _load_comments_by_file(directory: Path) -> dict[str, dict[str, str | None]]:
        out: dict[str, dict[str, str | None]] = {}
        for f in sorted(directory.glob("*_review_status.json")):
            rows = json.loads(f.read_text(encoding="utf-8"))
            out[f.name] = {r["blueprint_id"]: r.get("reviewer_1_comment") for r in rows}
        return out

    def test_twelve_packs_reported(self) -> None:
        self.assertEqual(len(self.results), 12)

    def test_all_132_keys_approved_zero_tbd_revise_hold(self) -> None:
        for context_id, result in self.results.items():
            self.assertEqual(result["tbd_count"], 0, context_id)
            self.assertEqual(result["revise_count"], 0, context_id)
            self.assertEqual(result["hold_count"], 0, context_id)
            self.assertEqual(result["approve_count"], result["total_keys"], context_id)
            self.assertTrue(result["pack_review_approved"], context_id)

    def test_total_key_count_is_132(self) -> None:
        self.assertEqual(sum(r["total_keys"] for r in self.results.values()), 132)

    def test_existing_comments_are_preserved_verbatim(self) -> None:
        for filename, before_by_key in self.before_comments.items():
            after_by_key = self.after_comments[filename]
            for key, comment in before_by_key.items():
                self.assertEqual(after_by_key.get(key), comment, f"{filename}::{key} 코멘트가 바뀌었다")

    def test_resolution_note_applied_to_previously_unresolved_keys(self) -> None:
        rows = json.loads((self.review_status_dir / "art_design_review_status.json").read_text(encoding="utf-8"))
        by_key = {r["blueprint_id"]: r for r in rows}
        self.assertTrue(all(r["resolution_note"] == RESOLUTION_NOTE for r in by_key.values()))


class RerunIsIdempotentTest(unittest.TestCase):
    def test_second_run_reports_zero_updates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            for f in _REAL_REVIEW_DIR.glob("*_review_status.json"):
                shutil.copy(f, tmp_dir / f.name)
            run_closeout(review_status_dir=tmp_dir)
            second = run_closeout(review_status_dir=tmp_dir)
        for context_id, result in second.items():
            self.assertEqual(result["updated_this_run"], 0, context_id)
            self.assertEqual(result["unchanged_this_run"], result["total_keys"], context_id)


if __name__ == "__main__":
    unittest.main()
