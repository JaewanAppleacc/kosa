"""ContextPack Matrix Diagnostics Harness 계약 테스트 — `a/contextpack-matrix-eval`
(2026-08-24) §7/§8.

`tests/test_generate_mock_json_script.py`와 같은 패턴이다 — `OUT_DIR`을 임시
디렉터리로 바꿔치기해서 실제 `outputs/evaluation/context_pack_matrix_report.*`를
건드리지 않고, Harness의 `main()`을 실제로 두 번 실행해 결정론성을 확인한다. 이
Harness 자체가 이미 "실제 검수 파일을 읽기 전용으로만 연다"·"임시 경로에만
쓴다"는 계약을 지키므로, 이 테스트는 그 계약이 실제로 지켜지는지(특히 진짜
`data/reviews/` 아래 파일이 하나도 바뀌지 않는지)까지 확인한다."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import eval.context_pack_matrix_diagnostics as harness
from src.data.contexts.context_activation_batches import ALL_BATCH_CONTEXT_IDS
from src.data.contexts.context_definitions import VERTICAL_SLICE_CONTEXT_IDS

_REAL_REVIEW_DIR = Path(__file__).resolve().parents[1] / "data" / "reviews" / "context_packs"
_REAL_SHARED_PROBE_REVIEW_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "reviews" / "context_pack_shared_probes_review_status.json"
)


def _snapshot_real_review_files() -> dict[str, str]:
    """실제 검수 파일들의 내용을 읽어 스냅샷을 만든다(읽기 전용) — Harness 실행 전후로
    바이트 단위로 비교해 "실제 파일 무변경"을 직접 증명한다."""

    snapshot: dict[str, str] = {}
    if _REAL_REVIEW_DIR.exists():
        for path in sorted(_REAL_REVIEW_DIR.glob("*.json")):
            snapshot[str(path)] = path.read_text(encoding="utf-8")
    if _REAL_SHARED_PROBE_REVIEW_PATH.exists():
        snapshot[str(_REAL_SHARED_PROBE_REVIEW_PATH)] = _REAL_SHARED_PROBE_REVIEW_PATH.read_text(encoding="utf-8")
    return snapshot


class RealReviewFilesUntouchedTest(unittest.TestCase):
    """지시서 "절대 금지: 실제 data/reviews/context_packs/*.json 수정, 실제 Shared
    Probe 검수 파일 생성·수정"을 실제로 지키는지 확인하는 가장 중요한 테스트다."""

    def test_full_harness_run_does_not_modify_any_real_review_file(self) -> None:
        before = _snapshot_real_review_files()
        with tempfile.TemporaryDirectory() as tmp:
            out_dir_patcher = patch.object(harness, "OUT_DIR", Path(tmp))
            json_path_patcher = patch.object(harness, "JSON_REPORT_PATH", Path(tmp) / "report.json")
            md_path_patcher = patch.object(harness, "MD_REPORT_PATH", Path(tmp) / "report.md")
            for p in (out_dir_patcher, json_path_patcher, md_path_patcher):
                p.start()
                self.addCleanup(p.stop)
            harness.main()
        after = _snapshot_real_review_files()
        self.assertEqual(before, after, "Harness 실행이 실제 검수 파일을 바꿨다 — 절대 금지 위반")

    def test_shared_probe_real_file_still_absent_or_unchanged(self) -> None:
        """실제 공용 Probe 검수 파일이 원래 없었다면 Harness 실행 후에도 여전히
        없어야 한다(Harness가 실수로 실제 경로에 새로 만들면 안 된다)."""

        existed_before = _REAL_SHARED_PROBE_REVIEW_PATH.exists()
        with tempfile.TemporaryDirectory() as tmp:
            for target, value in (
                ("OUT_DIR", Path(tmp)), ("JSON_REPORT_PATH", Path(tmp) / "r.json"), ("MD_REPORT_PATH", Path(tmp) / "r.md"),
            ):
                p = patch.object(harness, target, value)
                p.start()
                self.addCleanup(p.stop)
            harness.main()
        self.assertEqual(_REAL_SHARED_PROBE_REVIEW_PATH.exists(), existed_before)


def _run_main_into_temp(tmp_dir: Path) -> harness.MatrixReport:
    with (
        patch.object(harness, "OUT_DIR", tmp_dir),
        patch.object(harness, "JSON_REPORT_PATH", tmp_dir / "context_pack_matrix_report.json"),
        patch.object(harness, "MD_REPORT_PATH", tmp_dir / "context_pack_matrix_report.md"),
    ):
        return harness.main()


class DeterminismTest(unittest.TestCase):
    """§8 "Harness를 두 번 실행해 보고서가 바이트 단위로 동일한지 확인"."""

    def test_two_consecutive_runs_produce_byte_identical_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            _run_main_into_temp(Path(tmp1))
            _run_main_into_temp(Path(tmp2))
            json1 = (Path(tmp1) / "context_pack_matrix_report.json").read_bytes()
            json2 = (Path(tmp2) / "context_pack_matrix_report.json").read_bytes()
            md1 = (Path(tmp1) / "context_pack_matrix_report.md").read_bytes()
            md2 = (Path(tmp2) / "context_pack_matrix_report.md").read_bytes()
        self.assertEqual(json1, json2, "재실행마다 JSON 보고서가 달라진다")
        self.assertEqual(md1, md2, "재실행마다 Markdown 보고서가 달라진다")

    def test_markdown_report_ends_with_exactly_one_newline_no_trailing_blank_line(self) -> None:
        """2026-08-24 검수 시작 전 점검: `git show --check`가 잡아낸 "new blank line
        at EOF"를 재발 방지한다 — 파일을 손으로 고치는 대신 생성기(`_render_markdown`)
        자체가 정확히 한 개의 마지막 개행으로만 끝나도록 만든다."""

        with tempfile.TemporaryDirectory() as tmp:
            _run_main_into_temp(Path(tmp))
            md = (Path(tmp) / "context_pack_matrix_report.md").read_bytes()
        self.assertTrue(md.endswith(b"\n"), "Markdown 파일이 개행으로 끝나지 않는다")
        self.assertFalse(md.endswith(b"\n\n"), "Markdown 파일 끝에 불필요한 빈 줄이 있다")


class ReportShapeTest(unittest.TestCase):
    """생성된 보고서가 지시서 §5가 요구하는 필드를 실제로 채우는지 확인한다."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.report = _run_main_into_temp(Path(cls._tmp.name))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_60_combinations_covering_12_contexts_times_5_anchors(self) -> None:
        self.assertEqual(len(self.report.combos), 60)
        self.assertEqual({c.context_id for c in self.report.combos}, set(ALL_BATCH_CONTEXT_IDS))
        for context_id in ALL_BATCH_CONTEXT_IDS:
            anchors = {c.anchor_id for c in self.report.combos if c.context_id == context_id}
            self.assertEqual(len(anchors), 5, f"{context_id}의 Anchor 조합이 5개가 아니다: {anchors}")

    def test_no_actual_errors_or_leaks_in_matrix(self) -> None:
        """이 Harness는 60개 조합 전부 임시로 완전 승인된 상태로 돌린다 — 그 상태에서
        Context/Anchor 격리·Review Gate가 깨지면 실제 Runtime 버그다."""

        self.assertEqual(self.report.summary.actual_error_count, 0)
        self.assertEqual(self.report.summary.legacy_question_leak_count, 0)
        self.assertEqual(self.report.summary.anchor_mismatch_count, 0)
        self.assertEqual(self.report.summary.unapproved_signal_reflected_count, 0)
        self.assertFalse(self.report.summary.infinite_loop_or_cap_exceeded)

    def test_no_question_text_or_answer_text_leaked_into_report(self) -> None:
        """질문 원문·학생 답변 원문은 보고서에 저장하지 않는다(지시서 §5) — 구조화된
        필드에는 trait_id·상태 코드만 있고 자유 텍스트 필드가 없다는 것을 모델
        수준에서 확인한다."""

        combo_fields = set(harness.ComboResult.model_fields)
        forbidden_free_text_fields = {"question_text", "option_text", "answer_text", "selected_text"}
        self.assertEqual(combo_fields & forbidden_free_text_fields, set())

    def test_audit_reports_all_12_packs_discovered_with_expected_structure(self) -> None:
        for context_id in ALL_BATCH_CONTEXT_IDS:
            structure = self.report.audit.per_pack_structure[context_id]
            self.assertTrue(structure.discovered, f"{context_id} Pack이 discover되지 않았다")
            self.assertEqual(structure.routing_count, 1)
            self.assertEqual(structure.anchor_count, 5)
            self.assertEqual(structure.seed_count, 5)
            self.assertEqual(structure.backup_count, 5)
            self.assertEqual(structure.review_key_count, 11)

    def test_audit_reports_current_real_review_state_without_assuming_tbd(self) -> None:
        for context_id in ALL_BATCH_CONTEXT_IDS:
            tbd = self.report.audit.real_review_all_tbd[context_id]
            self.assertIn(tbd, (True, False, None))

    def test_audit_flag_off_supports_only_vertical_slice_three(self) -> None:
        self.assertEqual(self.report.audit.flag_off_supported_context_ids, sorted(VERTICAL_SLICE_CONTEXT_IDS))
        self.assertTrue(self.report.audit.flag_off_matches_vertical_slice_only)

    def test_audit_flag_on_matches_current_human_review_state(self) -> None:
        expected = sorted(
            harness.main_module._context_pack_registry.assessment_supported_context_ids(
                sorted(VERTICAL_SLICE_CONTEXT_IDS)
            )
        )
        self.assertEqual(
            self.report.audit.flag_on_but_unapproved_supported_context_ids,
            expected,
        )
        self.assertEqual(
            self.report.audit.flag_on_unapproved_still_matches_vertical_slice_only,
            expected == sorted(VERTICAL_SLICE_CONTEXT_IDS),
        )

    def test_fail_closed_checks_all_pass(self) -> None:
        fc = self.report.fail_closed_checks
        self.assertTrue(fc.unapproved_pack_excluded_from_supported)
        self.assertTrue(fc.unapproved_pack_rejected_at_context_select)
        self.assertTrue(fc.unapproved_pack_signal_excluded_by_gate)
        self.assertTrue(fc.unapproved_shared_probe_anchor_excluded_from_candidates)
        self.assertTrue(fc.approved_shared_probe_anchor_included_in_candidates)
        self.assertTrue(fc.approved_pack_included_when_fully_approved)

    def test_every_combo_completed_routing_and_seed(self) -> None:
        for c in self.report.combos:
            self.assertTrue(c.routing_ok, f"{c.context_id}/{c.anchor_id}: routing 실패")
            self.assertTrue(c.seed_ok, f"{c.context_id}/{c.anchor_id}: seed 실패")
            self.assertIsNone(c.failure_stage, f"{c.context_id}/{c.anchor_id}: {c.failure_stage}/{c.failure_reason_code}")

    def test_evidence_insufficient_is_a_valid_outcome_not_fabricated(self) -> None:
        """§4 "결과가 비어 있다고 억지 Fixture로 Trait를 주입하지 마세요" — Major
        결과가 비었으면 정직하게 빈 채로 기록됐는지 확인한다(가짜로 채워지지 않았다)."""

        insufficient = [c for c in self.report.combos if c.major_status == "INSUFFICIENT_EVIDENCE"]
        self.assertGreater(len(insufficient), 0)
        for c in insufficient:
            self.assertIn(c.department_status, ("SKIPPED_NO_MAJOR",))
            self.assertIn(c.subject_status, ("SKIPPED_NO_MAJOR",))

    def test_supplementary_stub_llm_section_present_and_leak_free(self) -> None:
        self.assertEqual(len(self.report.supplementary_stub_llm_combos), 12)
        for c in self.report.supplementary_stub_llm_combos:
            self.assertTrue(c.no_cross_context_leak)
            self.assertTrue(c.no_cross_anchor_leak)
            self.assertTrue(c.review_gate_applied)
            self.assertIsNone(c.failure_stage)


if __name__ == "__main__":
    unittest.main()
