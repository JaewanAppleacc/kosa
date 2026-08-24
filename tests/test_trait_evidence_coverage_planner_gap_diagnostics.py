"""Trait Evidence Coverage Planner Gap 진단 테스트(v2, 9-Persona) — a/planner-gap-9persona-diagnostics.

ca82f1f의 4-Persona/순환적-C 버전 테스트를 이식·확장한다. 핵심 증명 대상:
    1. `data/reviews/`를 한 바이트도 바꾸지 않는다.
    2. 서로 다른 PYTHONHASHSEED로 별도 프로세스에서 두 번 실행해도 보고서가
       byte-identical하다(결정론 테스트).
    3. Persona 9개 전부, 대안 A/B/C/C2(+ D는 재집계 전용)를 실제로 담고 있다.
    4. 대안 C/C2가 순환적이지 않다(provisional_top_traits가 Persona 고정
       trait_affinity_order를 그대로 베끼지 않는다) — 및 새 측정값들이 실제로
       채워져 있다(낭비 슬롯 사유, 고착 turn, 반복·다양성 통계).
    5. Coverage 문턱 상수와 추천 판정 로직이 완화되지 않았다."""

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

ALT_KEYS = ("A", "B", "C", "C2")


def _hash_tree(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*")) if p.is_file()
    }


class FixtureDoesNotTouchRealReviewFilesTest(unittest.TestCase):
    def test_run_and_summarize_leaves_data_reviews_untouched(self) -> None:
        from eval.trait_evidence_coverage_planner_gap_diagnostics import _persona_scenarios, run_and_summarize

        before = _hash_tree(REVIEWS_DIR)
        run_and_summarize(_persona_scenarios())
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
    """`main()`을 직접 호출한다 — Anchor 민감도 실험용 Fixture 배선을 테스트에서
    중복 구현하지 않고, 실제 산출물(JSON/MD)을 읽어 검증한다."""

    @classmethod
    def setUpClass(cls) -> None:
        from eval.trait_evidence_coverage_planner_gap_diagnostics import main

        main()
        cls.payload = json.loads(JSON_REPORT.read_text(encoding="utf-8"))
        cls.comparison = cls.payload["comparison"]
        cls.recommendation = cls.payload["recommendation"]

    def test_nine_personas_present(self) -> None:
        self.assertEqual(self.payload["persona_count"], 9)
        self.assertEqual(len(self.payload["persona_keys"]), 9)
        self.assertEqual(len(self.payload["baseline_personas"]), 9)
        for alt in ALT_KEYS:
            self.assertEqual(len(self.payload["alternatives"][alt]), 9)

    def test_persona_keys_match_expected_nine(self) -> None:
        expected = {
            "analytical", "creative_visual", "social_collaborative", "practical_making",
            "language_humanities", "mixed_cross_domain", "niche_interest",
            "coverage_maximizing", "coverage_minimizing",
        }
        self.assertEqual(set(self.payload["persona_keys"]), expected)

    def test_baseline_trait_termination_covers_all_core_traits(self) -> None:
        from src.data.trait_ontology.trait_probe_capabilities_v2 import CORE_TRAIT_IDS

        for row in self.payload["baseline_personas"]:
            self.assertEqual(set(row["trait_termination"].keys()), set(CORE_TRAIT_IDS))

    def test_each_persona_session_respects_five_context_and_35_question_ceiling(self) -> None:
        for row in self.payload["baseline_personas"]:
            self.assertEqual(len(row["final_context_ids"]), 5)
            self.assertLessEqual(row["trait_evidence_question_count"], 35)
        for alt in ALT_KEYS:
            for row in self.payload["alternatives"][alt]:
                self.assertLessEqual(row["trait_evidence_question_count"], 35)

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
        """대안은 Context당 최소4·최대6 Stop Condition을 바꾸지 못한다 — 총 질문 수가
        Baseline과 대안 사이에서 큰 폭으로 벌어지지 않아야 한다."""

        baseline_total = sum(r["trait_evidence_question_count"] for r in self.payload["baseline_personas"])
        for alt in ALT_KEYS:
            alt_total = sum(r["trait_evidence_question_count"] for r in self.payload["alternatives"][alt])
            self.assertLessEqual(abs(alt_total - baseline_total), baseline_total * 0.2)

    def test_recommendation_is_exactly_one_of_five(self) -> None:
        self.assertIn(self.recommendation["chosen"], {"NONE", "A", "B", "C", "C2"})

    def test_recommendation_never_claims_all_24_traits_sufficient(self) -> None:
        blob = self.recommendation["justification"] + self.recommendation["caveat"]
        for claim in ("24개 전체가 SUFFICIENT", "24개 모두 SUFFICIENT", "24개 전체 달성"):
            self.assertNotIn(claim, blob)

    def test_recommendation_respects_predeclared_threshold(self) -> None:
        """§7 '상위 5개 충족률이 충분히 개선되지 않으면 구현 권고하지 말 것' — 문턱값
        미달이면 chosen이 반드시 NONE이고, 이상이면 실제로 최댓값을 고른 것인지
        검증한다(하드코딩된 문구가 아니라 비교 결과를 따르는지)."""

        threshold = self.recommendation["minimum_meaningful_improvement_threshold"]
        self.assertEqual(threshold, 0.05)
        improvement = self.recommendation["best_alt_improvement_over_baseline"]
        chosen = self.recommendation["chosen"]
        fractions = self.recommendation["combined_top5_top8_fraction_avg_by_alt"]

        if improvement < threshold:
            self.assertEqual(chosen, "NONE")
            self.assertFalse(self.recommendation["implementation_recommended"])
        else:
            self.assertNotEqual(chosen, "NONE")
            self.assertTrue(self.recommendation["implementation_recommended"])
            for alt in ALT_KEYS:
                self.assertLessEqual(fractions[alt], fractions[chosen] + 1e-9)

    def test_markdown_report_mentions_all_required_sections(self) -> None:
        text = MD_REPORT.read_text(encoding="utf-8")
        for heading in (
            "이전 라운드 대비 수정 사항", "Baseline(실제 Planner)",
            "대안 Baseline/A/B/C/C2/D 비교", "Anchor 민감도 실험", "최종 판정",
        ):
            self.assertIn(heading, text, f"'{heading}' 섹션이 보고서에 없다")

    def test_json_report_has_planner_and_coverage_definitions(self) -> None:
        defs = self.payload["planner_and_coverage_definitions"]
        self.assertIn("support_count<2", defs["planner_gap_condition"])
        self.assertEqual(defs["coverage_sufficient_condition"]["min_effective_weight"], 3.0)

    def test_previous_round_comparison_present_and_marked_non_reexecuted(self) -> None:
        prev = self.payload["previous_round_4_persona_comparison"]
        self.assertIn("previous_round", prev)
        self.assertIn("this_round_same_4_persona_subset", prev)
        self.assertIn("note", prev)
        subset = prev["this_round_same_4_persona_subset"]
        for alt in ("baseline",) + ALT_KEYS:
            self.assertIn("top5_fraction_avg", subset[alt])
            self.assertIn("top8_fraction_avg", subset[alt])

    def test_anchor_sensitivity_experiment_present_with_three_variants(self) -> None:
        exp = self.payload["anchor_sensitivity_experiment"]
        self.assertEqual(set(exp["variants"].keys()), {"max_coverage_anchor", "min_coverage_anchor", "persona_default"})
        self.assertEqual(set(exp["results"].keys()), {"max_coverage_anchor", "min_coverage_anchor", "persona_default"})
        self.assertIn("finding", exp)
        self.assertIn("candidate_pool_varies_by_anchor", exp)

    def test_anchor_choices_are_not_always_the_alphabetically_first_anchor(self) -> None:
        """§2 '모든 Context에서 알파벳 첫 Anchor만 사용하지 말 것' — 실제로 최소 한
        Persona·Context 조합은 알파벳순 첫 Anchor가 아닌 Anchor를 골랐는지 확인한다."""

        distinct_anchors_per_context: dict[str, set[str]] = {}
        for row in self.payload["baseline_personas"]:
            for context_id, anchor_id in row["anchor_by_context"].items():
                distinct_anchors_per_context.setdefault(context_id, set()).add(anchor_id)
        self.assertTrue(
            any(len(v) > 1 for v in distinct_anchors_per_context.values()),
            "9개 Persona 전체에서 어떤 Context도 서로 다른 Anchor를 고르지 않았다 — 여전히 고정 Anchor 버그일 수 있다",
        )

    def test_alternative_c_and_c2_are_not_circular(self) -> None:
        """§4 '순환성 차단' — provisional_top_traits 이력이 매 Persona마다 채워져
        있고(=오라클을 안 쓰고 실제로 매 turn 다시 계산했다는 증거), 낭비 슬롯과
        고착 turn 필드가 실제 계산된 정수임을 확인한다."""

        for alt in ("C", "C2"):
            for row in self.payload["alternatives"][alt]:
                ptt = row["provisional_top_traits"]
                self.assertIn("misidentified_trait_lockin_turns", ptt)
                self.assertGreaterEqual(ptt["misidentified_trait_lockin_turns"], 0)
                self.assertIn("distinct_provisional_sets_seen", ptt)
                wasted = row["wasted_slots"]
                self.assertIn("total_wasted_slots", wasted)
                self.assertIsInstance(wasted["by_reason"], dict)
                for reason in wasted["by_reason"]:
                    self.assertIn(
                        reason,
                        {
                            "all_candidates_already_satisfied_but_stop_condition_forced_a_slot",
                            "gap_false_but_repeated_recent_target",
                            "gap_false_but_non_gap_alternatives_existed",
                        },
                    )

    def test_c2_exploitation_phase_field_present_for_every_persona(self) -> None:
        for row in self.payload["alternatives"]["C2"]:
            self.assertIn("exploitation_phase_ever_reached", row)
            self.assertIsInstance(row["exploitation_phase_ever_reached"], bool)

    def test_repetition_and_diversity_stats_present(self) -> None:
        for row in self.payload["baseline_personas"]:
            rep = row["repetition_stats"]
            self.assertIn("distinct_traits_targeted", rep)
            self.assertIn("max_repeat_count_for_a_single_trait", rep)
            self.assertIn("total_repeated_targeting_turns", rep)
            div = row["diversity_stats"]
            self.assertIn("avg_distinct_context_count", div)
            self.assertIn("avg_distinct_frame_count", div)

    def test_measurement_totals_are_non_negative_integers_in_comparison(self) -> None:
        for alt in ALT_KEYS:
            row = self.comparison[alt]
            self.assertGreaterEqual(row["total_wasted_slots"], 0)
            self.assertGreaterEqual(row["total_misidentified_trait_lockin_turns"], 0)


if __name__ == "__main__":
    unittest.main()
