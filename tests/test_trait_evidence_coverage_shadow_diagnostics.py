"""Trait Evidence Coverage Shadow 진단 Harness 테스트 — a/trait-evidence-coverage-shadow.

핵심 두 가지를 기계적으로 증명한다.
    1. 임시 승인 Fixture(`tempfile`)가 실제 `data/reviews/`를 한 바이트도 바꾸지 않는다.
    2. 서로 다른 PYTHONHASHSEED로 별도 프로세스에서 두 번 실행해도 보고서가
       byte-identical하다(같은 프로세스 안에서 두 번 부르는 것만으로는 set 순회 순서
       버그를 못 잡는다 — 실제로 이 버그를 이 방식으로 잡아서 고쳤다)."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "eval" / "trait_evidence_coverage_shadow_diagnostics.py"
REVIEWS_DIR = ROOT / "data" / "reviews"
JSON_REPORT = ROOT / "outputs" / "evaluation" / "trait_evidence_coverage_inventory_ceiling_report.json"
MD_REPORT = ROOT / "outputs" / "evaluation" / "trait_evidence_coverage_inventory_ceiling_report.md"


def _hash_tree(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*")) if p.is_file()
    }


class FixtureDoesNotTouchRealReviewFilesTest(unittest.TestCase):
    def test_run_diagnostics_leaves_data_reviews_untouched(self) -> None:
        from eval.trait_evidence_coverage_shadow_diagnostics import run_diagnostics

        before = _hash_tree(REVIEWS_DIR)
        run_diagnostics()
        after = _hash_tree(REVIEWS_DIR)
        self.assertEqual(before, after, "data/reviews/ 아래 파일이 변경됐다")

    def test_fixture_helper_writes_only_into_given_tempdir(self) -> None:
        from eval.trait_evidence_coverage_shadow_diagnostics import (
            _build_registry_with_fixture_approval,
        )

        before = _hash_tree(REVIEWS_DIR)
        with tempfile.TemporaryDirectory() as tmp:
            fixture_dir = Path(tmp)
            registry = _build_registry_with_fixture_approval(fixture_dir)
            written = list(fixture_dir.iterdir())
            self.assertGreater(len(written), 0, "임시 디렉터리에 아무것도 안 써졌다")
            for pack in registry.all_packs():
                self.assertTrue(registry.is_pack_review_approved(pack.context_id))
        after = _hash_tree(REVIEWS_DIR)
        self.assertEqual(before, after)

    def test_context_pack_registry_review_dir_is_the_tempdir_not_real_reviews(self) -> None:
        from eval.trait_evidence_coverage_shadow_diagnostics import (
            _build_registry_with_fixture_approval,
        )

        with tempfile.TemporaryDirectory() as tmp:
            fixture_dir = Path(tmp)
            registry = _build_registry_with_fixture_approval(fixture_dir)
            for pack in registry.all_packs():
                path = registry.review_status_path_for(pack.context_id)
                self.assertEqual(path.parent, fixture_dir)
                self.assertNotEqual(path.parent, REVIEWS_DIR / "context_packs")


class DeterminismTest(unittest.TestCase):
    """§9 — 시간·메모리 값 없음, 재실행해도 byte-identical. 반드시 별도 프로세스로
    실행한다(PYTHONHASHSEED가 프로세스마다 달라야 set 순회 순서 버그가 드러난다)."""

    def _run_once(self, hash_seed: str) -> tuple[bytes, bytes]:
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = hash_seed
        proc = subprocess.run(
            [sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True, timeout=120, env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace")[:2000])
        return JSON_REPORT.read_bytes(), MD_REPORT.read_bytes()

    def test_two_runs_with_different_hash_seeds_are_byte_identical(self) -> None:
        first_json, first_md = self._run_once("111")
        second_json, second_md = self._run_once("222")
        self.assertEqual(first_json, second_json, "PYTHONHASHSEED만 바뀌어도 JSON이 달라진다")
        self.assertEqual(first_md, second_md, "PYTHONHASHSEED만 바뀌어도 Markdown이 달라진다")

    def test_report_has_no_timestamp_fields(self) -> None:
        self._run_once("333")
        blob = JSON_REPORT.read_text(encoding="utf-8") + MD_REPORT.read_text(encoding="utf-8")
        for token in ("generated_at", "created_at", "timestamp", "run_at"):
            self.assertNotIn(token, blob)


class ReportContentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from eval.trait_evidence_coverage_shadow_diagnostics import (
            _write_json_report,
            _write_markdown_report,
            run_diagnostics,
        )

        cls.diagnostics = run_diagnostics()
        _write_json_report(cls.diagnostics)
        _write_markdown_report(cls.diagnostics)
        cls.payload = json.loads(JSON_REPORT.read_text(encoding="utf-8"))

    def test_five_coverage_statuses_present_in_full_results(self) -> None:
        from src.engines.trait_evidence_coverage_engine import coverage_status_breakdown

        for env_key in ("env_a", "env_b"):
            breakdown = coverage_status_breakdown(self.diagnostics[env_key]["full_results"])
            self.assertEqual(
                set(breakdown.keys()),
                {"UNOBSERVED", "LIMITED", "SUPPORTED", "SUFFICIENT", "CONFLICTED"},
            )

    def test_env_b_pool_is_strictly_larger_than_env_a(self) -> None:
        self.assertGreater(
            self.diagnostics["env_b"]["total_available_questions"],
            self.diagnostics["env_a"]["total_available_questions"],
        )

    def test_env_b_has_more_or_equal_contexts_than_env_a(self) -> None:
        self.assertGreaterEqual(
            len(self.diagnostics["env_b"]["distinct_contexts"]),
            len(self.diagnostics["env_a"]["distinct_contexts"]),
        )
        self.assertEqual(len(self.diagnostics["env_a"]["distinct_contexts"]), 3)

    def test_question_caps_present_in_json(self) -> None:
        caps = self.payload["environments"]["env_b"]["coverage_status_breakdown_by_cap"]
        for cap in (20, 30, 40, 50):
            self.assertIn(str(cap), caps)

    def test_gap_classification_uses_only_known_labels(self) -> None:
        allowed = {"MAPPING_GAP", "CONTEXT_GAP", "POLICY_LIMITED", "SUFFICIENT"}
        for env_key in ("env_a", "env_b"):
            labels = set(self.payload["environments"][env_key]["gap_classification_by_trait"].values())
            self.assertTrue(labels.issubset(allowed), labels - allowed)

    def test_recommended_range_minimum_not_greater_than_maximum(self) -> None:
        rng = self.payload["cross_environment_summary"]["recommended_question_range"]
        if rng["minimum"] is not None and rng["maximum"] is not None:
            self.assertLessEqual(rng["minimum"], rng["maximum"])

    def test_markdown_report_mentions_all_required_sections(self) -> None:
        text = MD_REPORT.read_text(encoding="utf-8")
        for heading in (
            "Coverage Policy 최종 기준", "현재 3 Context 결과", "15 Context, 임시 승인 Fixture 결과",
            "가장 자주 미관찰", "질문 Mapping 부족", "권장 최소·최대 질문 수",
            "Coverage 기반 종료를 Runtime에 연결해도 되는가", "설계 결정과 한계",
        ):
            self.assertIn(heading, text, f"'{heading}' 섹션이 보고서에 없다")


if __name__ == "__main__":
    unittest.main()
