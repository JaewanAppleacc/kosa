"""Trait Evidence Coverage Planner Gap 진단 테스트 — a/trait-evidence-coverage-planner-gap.

핵심 세 가지를 기계적으로 증명한다.
    1. `data/reviews/`를 한 바이트도 바꾸지 않는다(12개 Pack·공용 Adaptive Probe 승인은
       전부 tempfile Fixture 안에서만 만든다).
    2. 서로 다른 PYTHONHASHSEED로 별도 프로세스에서 두 번 실행해도 보고서가
       byte-identical하다.
    3. 보고서가 요구된 구조(Trait 종료 순간 기록·대안 A/B/C/D 비교·추천안 1개)를 실제로
       담고 있다."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "eval" / "trait_evidence_coverage_planner_gap_diagnostics.py"
REVIEWS_DIR = ROOT / "data" / "reviews"
JSON_REPORT = ROOT / "outputs" / "evaluation" / "trait_evidence_coverage_planner_gap_report.json"
MD_REPORT = ROOT / "outputs" / "evaluation" / "trait_evidence_coverage_planner_gap_report.md"


def _hash_tree(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*")) if p.is_file()
    }


class FixtureDoesNotTouchRealReviewFilesTest(unittest.TestCase):
    def test_run_and_summarize_leaves_data_reviews_untouched(self) -> None:
        from eval.trait_evidence_coverage_planner_gap_diagnostics import run_and_summarize

        before = _hash_tree(REVIEWS_DIR)
        run_and_summarize()
        after = _hash_tree(REVIEWS_DIR)
        self.assertEqual(before, after, "data/reviews/ 아래 파일이 변경됐다")

    def test_fixture_registry_review_dir_is_tempdir_not_real_reviews(self) -> None:
        import tempfile

        from eval.trait_evidence_coverage_planner_gap_diagnostics import _build_fixture_registry

        before = _hash_tree(REVIEWS_DIR)
        with tempfile.TemporaryDirectory() as tmp:
            fixture_dir = Path(tmp)
            registry = _build_fixture_registry(fixture_dir)
            self.assertGreater(len(list(fixture_dir.iterdir())), 0, "임시 디렉터리에 아무것도 안 써졌다")
            for pack in registry.all_packs():
                self.assertTrue(registry.is_pack_review_approved(pack.context_id))
                path = registry.review_status_path_for(pack.context_id)
                self.assertEqual(path.parent, fixture_dir)
                self.assertNotEqual(path.parent, REVIEWS_DIR / "context_packs")
        after = _hash_tree(REVIEWS_DIR)
        self.assertEqual(before, after)


class DeterminismTest(unittest.TestCase):
    """반드시 별도 프로세스로 실행한다(PYTHONHASHSEED가 프로세스마다 달라야 set 순회
    순서 버그가 드러난다 — a/trait-evidence-coverage-shadow에서 실제로 이 방식으로 잡은
    버그가 있다)."""

    def _run_once(self, hash_seed: str) -> tuple[bytes, bytes]:
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = hash_seed
        proc = subprocess.run(
            [sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True, timeout=180, env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace")[:4000])
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
        from eval.trait_evidence_coverage_planner_gap_diagnostics import (
            _compare_alternatives,
            _recommendation,
            _write_json_report,
            _write_markdown_report,
            run_and_summarize,
        )

        cls.summary = run_and_summarize()
        cls.comparison = _compare_alternatives(cls.summary)
        cls.recommendation = _recommendation(cls.comparison)
        _write_json_report(cls.summary, cls.comparison, cls.recommendation)
        _write_markdown_report(cls.summary, cls.comparison, cls.recommendation)
        cls.payload = json.loads(JSON_REPORT.read_text(encoding="utf-8"))

    def test_four_personas_present(self) -> None:
        self.assertEqual(len(self.summary["baseline"]), 4)
        for alt in ("A", "B", "C"):
            self.assertEqual(len(self.summary["alternatives"][alt]), 4)

    def test_baseline_trait_termination_covers_all_24_traits(self) -> None:
        from src.data.trait_ontology.trait_probe_capabilities_v2 import CORE_TRAIT_IDS

        for row in self.summary["baseline"]:
            self.assertEqual(set(row["trait_termination"].keys()), set(CORE_TRAIT_IDS))

    def test_stopped_trait_has_context_and_turn_index(self) -> None:
        """Planner가 멈춘 것으로 기록된 Trait는 반드시 멈춘 Context와 질문 순번을 함께
        가진다(둘 다 None이면 '멈췄다'는 판정 자체가 근거 없다)."""

        found_any = False
        for row in self.summary["baseline"]:
            for trait_id in row["stopped_by_planner_but_final_status_not_sufficient"]:
                found_any = True
                info = row["trait_termination"][trait_id]
                self.assertIsNotNone(info["stopped_in_context"])
                self.assertIsNotNone(info["stopped_at_turn_index"])
        self.assertTrue(found_any, "이 4개 Persona 중 하나도 '멈췄지만 SUFFICIENT 미달' Trait가 없다 — 진단 목적과 어긋난다")

    def test_alternatives_never_loosen_coverage_thresholds(self) -> None:
        """§7 '기준을 임의 완화하지 않는다' — 이식된 Coverage 상수 자체가 그대로인지
        확인한다."""

        from src.engines.trait_evidence_coverage_engine import (
            SUFFICIENT_MIN_CONTEXT_COUNT,
            SUFFICIENT_MIN_DIRECTIONAL_CONSISTENCY,
            SUFFICIENT_MIN_EFFECTIVE_WEIGHT,
            SUFFICIENT_MIN_FRAME_COUNT,
            SUFFICIENT_MIN_PRIMARY_COUNT,
        )

        self.assertEqual(SUFFICIENT_MIN_PRIMARY_COUNT, 2)
        self.assertEqual(SUFFICIENT_MIN_EFFECTIVE_WEIGHT, 3.0)
        self.assertEqual(SUFFICIENT_MIN_CONTEXT_COUNT, 2)
        self.assertEqual(SUFFICIENT_MIN_FRAME_COUNT, 2)
        self.assertEqual(SUFFICIENT_MIN_DIRECTIONAL_CONSISTENCY, 0.7)

    def test_alternatives_use_same_question_budget_as_baseline(self) -> None:
        """§ 대안은 Context당 최소4·최대6 Stop Condition을 바꾸지 못한다 — 총 질문 수가
        Baseline과 대안 사이에서 큰 폭으로 벌어지지 않아야 한다(완전히 같을 필요는 없다,
        후보 소진으로 인한 조기 종료 차이는 허용한다)."""

        baseline_total = sum(r["trait_evidence_question_count"] for r in self.summary["baseline"])
        for alt in ("A", "B", "C"):
            alt_total = sum(r["trait_evidence_question_count"] for r in self.summary["alternatives"][alt])
            self.assertLessEqual(abs(alt_total - baseline_total), baseline_total * 0.2)

    def test_recommendation_is_exactly_one_of_four(self) -> None:
        self.assertIn(self.recommendation["chosen"], {"A", "B", "C", "D"})

    def test_recommendation_never_claims_all_24_traits_sufficient(self) -> None:
        """§5 '24개 전체를 SUFFICIENT로 만드는 것을 목표로 삼지 말 것' — 추천 문구가 이를
        달성했다고 주장하지 않는지 확인한다(부정문으로 언급하는 건 허용된다)."""

        blob = self.recommendation["justification"] + self.recommendation["caveat"]
        for claim in ("24개 전체가 SUFFICIENT", "24개 모두 SUFFICIENT", "24개 전체 달성"):
            self.assertNotIn(claim, blob)

    def test_recommendation_ranking_is_internally_consistent(self) -> None:
        """추천 문구가 가리키는 대안이 실제로 결합 점수 최댓값과 일치하는지(하드코딩된
        문구가 아니라 실제 비교 결과를 따르는지) 검증한다."""

        fractions = self.recommendation["combined_top5_top8_fraction_avg_by_alt"]
        chosen = self.recommendation["chosen"]
        if chosen == "D":
            self.assertEqual(max(fractions, key=fractions.get), "baseline")
        else:
            self.assertAlmostEqual(fractions[chosen], max(fractions.values()), places=9)

    def test_markdown_report_mentions_all_required_sections(self) -> None:
        text = MD_REPORT.read_text(encoding="utf-8")
        for heading in (
            "구조적 불일치 요약", "Baseline(실제 Planner)", "Planner가 멈췄지만 SUFFICIENT에 못 미친 Trait",
            "대안 A/B/C/D 비교", "추천안",
        ):
            self.assertIn(heading, text, f"'{heading}' 섹션이 보고서에 없다")

    def test_json_report_has_planner_and_coverage_definitions(self) -> None:
        defs = self.payload["planner_and_coverage_definitions"]
        self.assertIn("support_count<2", defs["planner_gap_condition"])
        self.assertEqual(defs["coverage_sufficient_condition"]["min_effective_weight"], 3.0)


if __name__ == "__main__":
    unittest.main()
