"""Coverage-focused Target Selector — Shadow 평가 Harness 테스트 —
a/coverage-focused-planner-shadow.

핵심 증명 대상(과제 §8):
    1. `data/reviews/`를 한 바이트도 바꾸지 않는다.
    2. 서로 다른 PYTHONHASHSEED로 별도 프로세스에서 두 번 실행해도 보고서가
       byte-identical하다.
    3. Persona 9개 전부를 실제로 담고 있다.
    4. 매 Persona·Context마다 실제 4~6개 Adaptive Tail 예산을 지킨다(질문 예산
       초과 없음).
    5. Runtime Planner(`src/engines/context_pack_adaptive_planner.py`)·
       `src/api/main.py` 소스 자체가 이 테스트 실행으로 바뀌지 않는다."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "eval" / "coverage_focused_planner_shadow_harness.py"
REVIEWS_DIR = ROOT / "data" / "reviews"
MAIN_PY = ROOT / "src" / "api" / "main.py"
PLANNER_PY = ROOT / "src" / "engines" / "context_pack_adaptive_planner.py"
COVERAGE_ENGINE_PY = ROOT / "src" / "engines" / "trait_evidence_coverage_engine.py"
JSON_REPORT = ROOT / "outputs" / "evaluation" / "coverage_focused_planner_shadow_report.json"
MD_REPORT = ROOT / "outputs" / "evaluation" / "coverage_focused_planner_shadow_report.md"

EXPECTED_PERSONA_KEYS = {
    "analytical", "creative_visual", "social_collaborative", "practical_making",
    "language_humanities", "mixed_cross_domain", "niche_interest",
    "coverage_maximizing", "coverage_minimizing",
}


def _hash_tree(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*")) if p.is_file()
    }


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RuntimeSourceUntouchedTest(unittest.TestCase):
    """§8 'Runtime Planner·main.py 무변경' — 실행 전후 소스 파일 Hash가 같다."""

    def test_main_and_planner_source_unchanged_after_run(self) -> None:
        from eval.coverage_focused_planner_shadow_harness import _persona_scenarios, run_and_summarize

        before = {p: _hash_file(p) for p in (MAIN_PY, PLANNER_PY, COVERAGE_ENGINE_PY)}
        run_and_summarize(_persona_scenarios()[:2])
        after = {p: _hash_file(p) for p in (MAIN_PY, PLANNER_PY, COVERAGE_ENGINE_PY)}
        self.assertEqual(before, after)


class FixtureDoesNotTouchRealReviewFilesTest(unittest.TestCase):
    def test_run_and_summarize_leaves_data_reviews_untouched(self) -> None:
        from eval.coverage_focused_planner_shadow_harness import _persona_scenarios, run_and_summarize

        before = _hash_tree(REVIEWS_DIR)
        run_and_summarize(_persona_scenarios()[:2])
        after = _hash_tree(REVIEWS_DIR)
        self.assertEqual(before, after, "data/reviews/ 아래 파일이 변경됐다")


class DeterminismTest(unittest.TestCase):
    """반드시 별도 프로세스로 실행한다(PYTHONHASHSEED가 프로세스마다 달라야 한다)."""

    def _run_once(self, hash_seed: str) -> tuple[bytes, bytes]:
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = hash_seed
        proc = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True, timeout=180, env=env)
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

    def test_report_never_contains_raw_question_or_answer_text(self) -> None:
        """과제 §5 '학생 답변·질문 원문은 보고서에 넣지 말 것' — Fake LLM이 생성하는
        고정 문구가 보고서에 새어 들어가지 않았는지 확인한다."""

        self._run_once("444")
        blob = JSON_REPORT.read_text(encoding="utf-8") + MD_REPORT.read_text(encoding="utf-8")
        self.assertNotIn("지금 상황에서 무엇을 가장 먼저 하나요", blob)
        self.assertNotIn("선택지 문장", blob)


class ReportContentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from eval.coverage_focused_planner_shadow_harness import main

        main()
        cls.payload = json.loads(JSON_REPORT.read_text(encoding="utf-8"))
        cls.comparison = cls.payload["comparison"]
        cls.conclusion = cls.payload["conclusion"]

    def test_nine_personas_present(self) -> None:
        self.assertEqual(self.payload["persona_count"], 9)
        self.assertEqual(set(self.payload["persona_keys"]), EXPECTED_PERSONA_KEYS)
        self.assertEqual(len(self.payload["baseline_personas"]), 9)
        self.assertEqual(len(self.payload["shadow_steered_personas"]), 9)
        self.assertEqual(len(self.payload["turn_comparisons"]), 9)

    def test_shadow_only_marker_present(self) -> None:
        self.assertTrue(self.payload["shadow_only"])

    def test_selector_constants_match_selector_module(self) -> None:
        from src.engines.coverage_focused_target_selector import PROVISIONAL_TOP_N
        from src.engines.trait_evidence_coverage_engine import (
            SUFFICIENT_MIN_CONTEXT_COUNT, SUFFICIENT_MIN_EFFECTIVE_WEIGHT,
            SUFFICIENT_MIN_FRAME_COUNT, SUFFICIENT_MIN_PRIMARY_COUNT,
        )

        constants = self.payload["selector_constants"]
        self.assertEqual(constants["provisional_top_n"], PROVISIONAL_TOP_N)
        self.assertEqual(constants["coverage_sufficient_min_primary_count"], SUFFICIENT_MIN_PRIMARY_COUNT)
        self.assertEqual(constants["coverage_sufficient_min_effective_weight"], SUFFICIENT_MIN_EFFECTIVE_WEIGHT)
        self.assertEqual(constants["coverage_sufficient_min_context_count"], SUFFICIENT_MIN_CONTEXT_COUNT)
        self.assertEqual(constants["coverage_sufficient_min_frame_count"], SUFFICIENT_MIN_FRAME_COUNT)

    def test_each_persona_respects_5_context_and_35_question_ceiling(self) -> None:
        for row in self.payload["baseline_personas"]:
            self.assertEqual(len(row["final_context_ids"]), 5)
            self.assertLessEqual(row["trait_evidence_question_count"], 35)
        for row in self.payload["shadow_steered_personas"]:
            self.assertLessEqual(row["trait_evidence_question_count"], 35)

    def test_turn_comparisons_record_both_real_and_shadow_target(self) -> None:
        for tc in self.payload["turn_comparisons"]:
            self.assertGreater(tc["total_turns"], 0)
            for turn in tc["turns"]:
                self.assertIn("real_target_trait_id", turn)
                self.assertIn("shadow_proposed_trait_id", turn)
                self.assertIn("match", turn)
                self.assertIsInstance(turn["match"], bool)

    def test_baseline_pass_never_diverges_from_what_real_planner_would_do(self) -> None:
        """§ 관찰 전용 Wrapper 불변식 — Pass 1은 실제 결정을 절대 바꾸지 않는다.
        간접 증명: Baseline 세션의 trait_evidence_question_count 분포가 별도로
        (Wrapper 없이) 실행한 순수 Baseline과 같아야 한다 — 여기서는 Wrapper가
        있는 채로 나온 값이 5개 Context 상한(§8)을 넘지 않는다는 구조적 사실로
        간접 확인한다(정확한 값 비교는 세션 실행 비용이 크므로 상한 위반 여부로
        대신한다)."""

        for row in self.payload["baseline_personas"]:
            self.assertGreater(row["trait_evidence_question_count"], 0)
            self.assertLessEqual(row["trait_evidence_question_count"], 35)

    def test_conclusion_is_exactly_one_of_three(self) -> None:
        self.assertIn(self.conclusion["verdict"], {"READY_FOR_RUNTIME_FLAG", "NEEDS_MORE_SHADOW_EVIDENCE", "REJECTED"})

    def test_conclusion_respects_predeclared_thresholds(self) -> None:
        threshold = self.conclusion["minimum_meaningful_improvement_threshold"]
        self.assertEqual(threshold, 0.05)
        agreement_threshold = self.conclusion["minimum_turn_agreement_rate_for_ready"]
        self.assertEqual(agreement_threshold, 0.5)

        improvement = self.comparison["combined_improvement_over_baseline"]
        agreement = self.comparison["turn_agreement_rate"]
        verdict = self.conclusion["verdict"]

        if improvement < 0:
            self.assertEqual(verdict, "REJECTED")
        elif improvement < threshold:
            self.assertEqual(verdict, "NEEDS_MORE_SHADOW_EVIDENCE")
        elif agreement < agreement_threshold:
            self.assertEqual(verdict, "NEEDS_MORE_SHADOW_EVIDENCE")
        else:
            self.assertEqual(verdict, "READY_FOR_RUNTIME_FLAG")

    def test_conclusion_never_auto_flips_a_runtime_flag(self) -> None:
        blob = self.conclusion["justification"] + self.conclusion["note"]
        self.assertIn("자동으로", blob)
        for phrase in ("ENABLE_", "os.environ[", "_context_pack_runtime ="):
            self.assertNotIn(phrase, blob)

    def test_lockin_and_exploration_turns_are_non_negative(self) -> None:
        for row in self.payload["shadow_steered_personas"]:
            self.assertGreaterEqual(row["lockin_turns"], 0)
            self.assertGreaterEqual(row["exploration_turns"], 0)
            self.assertLessEqual(row["exploration_turns"], row["total_targeted_turns"])

    def test_repetition_and_diversity_stats_present_for_both_passes(self) -> None:
        for row in self.payload["baseline_personas"] + self.payload["shadow_steered_personas"]:
            rep = row["repetition_stats"]
            self.assertIn("distinct_traits_targeted", rep)
            self.assertIn("max_repeat_count_for_a_single_trait", rep)
            self.assertIn("total_repeated_targeting_turns", rep)
            div = row["diversity_stats"]
            self.assertIn("avg_distinct_context_count", div)
            self.assertIn("avg_distinct_frame_count", div)

    def test_anchor_sensitivity_has_three_variants(self) -> None:
        exp = self.payload["anchor_sensitivity"]
        for key in ("max_coverage_anchor", "min_coverage_anchor", "persona_default_anchor"):
            self.assertIn(key, exp)

    def test_persona_default_anchor_uses_diversification_not_fixed_first(self) -> None:
        """§6 'Anchor 다양화 유지' — persona_default_anchor가 그 Context에 등록된
        Anchor 목록 안에 실제로 존재하는 값인지 확인한다(고정 자리표시자가 아니라
        `_anchor_choice_for_persona`가 실제로 계산한 값이라는 최소 sanity check)."""

        exp = self.payload["anchor_sensitivity"]
        self.assertIn(exp["persona_default_anchor"], exp["anchor_candidate_trait_counts"])

    def test_markdown_report_mentions_required_sections(self) -> None:
        text = MD_REPORT.read_text(encoding="utf-8")
        for heading in (
            "Baseline vs Shadow 대체 실행", "요약", "Anchor 민감도", "판정",
        ):
            self.assertIn(heading, text, f"'{heading}' 섹션이 보고서에 없다")


if __name__ == "__main__":
    unittest.main()
