"""Final Activation Readiness Audit 테스트 — a/final-activation-readiness-audit.

핵심 세 가지를 기계적으로 증명한다.
    1. 이 진단은 읽기 전용이다 — data/reviews·data/master·src(Runtime)를 한 바이트도
       바꾸지 않는다.
    2. 서로 다른 PYTHONHASHSEED로 별도 프로세스에서 두 번 실행해도 보고서가
       byte-identical하다.
    3. 보고서가 8개 영역(Context·Trait·질문 흐름·전공학과·과목·Frontend·Feature Flag·
       최종 판정)을 모두 담고, 각 상태 값이 허용된 6개 중 하나다."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "eval" / "final_activation_readiness_audit.py"
JSON_REPORT = ROOT / "outputs" / "evaluation" / "final_activation_readiness_report.json"
MD_REPORT = ROOT / "outputs" / "evaluation" / "final_activation_readiness_report.md"

ALLOWED_STATUSES = {
    "READY", "READY_AFTER_HUMAN_REVIEW", "BLOCKED_BY_DATA", "BLOCKED_BY_MAPPING", "SHADOW_ONLY", "NOT_IMPLEMENTED",
}

# 이 진단이 절대 건드리면 안 되는 실제 Runtime·Review·Master 경로들.
_PROTECTED_PATHS = [
    ROOT / "data" / "reviews",
    ROOT / "data" / "master",
    ROOT / "src" / "api" / "main.py",
    ROOT / "src" / "engines",
    ROOT / "src" / "services",
    ROOT / "data" / "canonical_major_groups.draft.jsonl",
]


def _hash_tree(root: Path) -> dict[str, str]:
    if root.is_file():
        return {str(root): hashlib.sha256(root.read_bytes()).hexdigest()}
    return {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts
    }


class ReadOnlyTest(unittest.TestCase):
    def test_run_audit_leaves_protected_paths_untouched(self) -> None:
        from eval.final_activation_readiness_audit import run_audit

        before = {str(p): _hash_tree(p) for p in _PROTECTED_PATHS}
        run_audit()
        after = {str(p): _hash_tree(p) for p in _PROTECTED_PATHS}
        self.assertEqual(before, after, "읽기 전용이어야 할 경로가 변경됐다")

    def test_run_audit_is_idempotent_within_one_process(self) -> None:
        """전역 mutable Registry(trait_signal_registry._REGISTRY)에 두 번 등록해도
        멱등이라 예외 없이 두 번 호출 가능해야 한다."""

        from eval.final_activation_readiness_audit import run_audit

        first = run_audit()
        second = run_audit()
        self.assertEqual(
            json.dumps(first, sort_keys=True, default=str),
            json.dumps(second, sort_keys=True, default=str),
        )


class DeterminismTest(unittest.TestCase):
    def _run_once(self, hash_seed: str) -> tuple[bytes, bytes]:
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = hash_seed
        proc = subprocess.run(
            [sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True, timeout=120, env=env,
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
        from eval.final_activation_readiness_audit import run_audit, _write_json_report, _write_markdown_report

        cls.sections = run_audit()
        _write_json_report(cls.sections)
        _write_markdown_report(cls.sections)
        cls.payload = json.loads(JSON_REPORT.read_text(encoding="utf-8"))

    def test_context_readiness_covers_all_15(self) -> None:
        self.assertEqual(len(self.sections["context_readiness"]), 15)
        ids = {r["context_id"] for r in self.sections["context_readiness"]}
        self.assertEqual(len(ids), 15)

    def test_trait_readiness_covers_all_24(self) -> None:
        self.assertEqual(len(self.sections["trait_readiness"]), 24)

    def test_all_statuses_are_from_allowed_set(self) -> None:
        for row in self.sections["context_readiness"] + self.sections["trait_readiness"]:
            self.assertIn(row["status"], ALLOWED_STATUSES, row)
        self.assertIn(self.sections["final_verdict"]["overall"], ALLOWED_STATUSES)
        for status in self.sections["final_verdict"]["per_section"].values():
            self.assertIn(status, ALLOWED_STATUSES)

    def test_final_verdict_is_worst_of_sections_not_optimistic(self) -> None:
        """전체 판정이 개별 영역 중 가장 나쁜 상태보다 낙관적이면 안 된다."""

        severity = {
            "READY": 0, "READY_AFTER_HUMAN_REVIEW": 1, "SHADOW_ONLY": 2,
            "BLOCKED_BY_DATA": 3, "BLOCKED_BY_MAPPING": 3, "NOT_IMPLEMENTED": 4,
        }
        per_section = self.sections["final_verdict"]["per_section"]
        worst = max(severity[s] for s in per_section.values())
        overall = severity[self.sections["final_verdict"]["overall"]]
        self.assertEqual(overall, worst)

    def test_business_pack_reported_as_blocked_by_revise_not_hidden(self) -> None:
        row = next(r for r in self.sections["context_readiness"] if r["context_id"] == "business")
        self.assertFalse(row["runtime_activatable"])
        self.assertIn("REVISE", str(row["blocking_reasons"]))

    def test_science_and_sports_packs_reported_ready(self) -> None:
        for context_id in ("science", "sports"):
            row = next(r for r in self.sections["context_readiness"] if r["context_id"] == context_id)
            self.assertTrue(row["runtime_activatable"])
            self.assertEqual(row["status"], "READY")

    def test_mapping_gap_traits_flagged_blocked_by_mapping(self) -> None:
        for row in self.sections["trait_readiness"]:
            if row["mapping_gap"]:
                self.assertEqual(row["status"], "BLOCKED_BY_MAPPING")

    def test_four_plus_one_meets_minimum_today(self) -> None:
        flow = self.sections["question_flow_readiness"]["flow_4plus1_flag_on"]
        self.assertTrue(flow["meets_minimum_today"])
        self.assertEqual(flow["effective_supported_context_count_if_pack_runtime_on"], 5)

    def test_coverage_stop_condition_marked_shadow_only(self) -> None:
        self.assertEqual(
            self.sections["question_flow_readiness"]["coverage_stop_condition_wiring"]["status"], "SHADOW_ONLY",
        )

    def test_major_department_readiness_expected_counts(self) -> None:
        md = self.sections["major_department_readiness"]
        self.assertEqual(md["service_canonical_majors"]["count"], 10)
        self.assertEqual(md["canonical_major_groups"]["count"], 42)
        self.assertEqual(md["bridge_mapping"]["count"], 44)
        self.assertEqual(md["p1_classification"]["count"], 374)
        self.assertEqual(md["nce"]["cluster_count"], 24)
        self.assertEqual(md["nce"]["member_row_total"], 584)
        self.assertEqual(md["identity_key_conflicts"]["group_count"], 16)
        self.assertEqual(md["identity_key_conflicts"]["candidate_row_total"], 32)
        self.assertEqual(md["current_master"]["department_count"], 35)

    def test_subject_readiness_lists_unsupported_majors(self) -> None:
        sd = self.sections["subject_readiness"]
        self.assertEqual(len(sd["per_major"]), 10)
        self.assertTrue(sd["unsupported_majors"])
        for major_id in sd["unsupported_majors"]:
            row = next(r for r in sd["per_major"] if r["major_id"] == major_id)
            self.assertEqual(row["subject_major_link_count"], 0)

    def test_feature_flag_table_includes_minimum_required_flags(self) -> None:
        flags = {row["flag"] for row in self.sections["feature_flags"]}
        for required in (
            "ENABLE_TRAIT_VECTOR_V2_PRIMARY", "ENABLE_CONTEXT_PACK_RUNTIME",
            "ENABLE_CONTEXT_SELECTION_4_PLUS_1", "ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES",
        ):
            self.assertIn(required, flags)

    def test_markdown_report_mentions_all_required_sections(self) -> None:
        text = MD_REPORT.read_text(encoding="utf-8")
        for heading in (
            "최종 판정", "Context 준비도", "Trait 준비도", "질문 흐름 준비도",
            "전공·학과 준비도", "과목 준비도", "Frontend 준비도", "Feature Flag 표", "최종 상태 판정",
        ):
            self.assertIn(heading, text, f"'{heading}' 섹션이 보고서에 없다")


if __name__ == "__main__":
    unittest.main()
