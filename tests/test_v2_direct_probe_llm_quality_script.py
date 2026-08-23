"""V2 Direct Probe LLM 품질 평가 스크립트 테스트 — 2026-08-23 Trait Ontology v2(2.1단계
§12, 2.4단계 §1). 실제 네트워크 호출 없이 opt-in 게이트와 호출 예산 로직만 확인한다.

2.4단계 §1: 이 파일이 예전에는 `self.module.main()`을 인자 없이 호출해 커밋된 실제
`outputs/evaluation/v2_direct_probe_llm_quality_report.md`를 "실검증 미실행" 상태로
덮어썼다(전체 테스트를 한 번 돌릴 때마다 실제 opt-in 실행 결과가 사라지는 문제). 이제는
모든 테스트가 `TemporaryDirectory` 안의 경로를 `main(output_path=...)`로 넘긴다 — 커밋된
실제 보고서 파일은 이 파일의 테스트가 실행되는 동안 전혀 열리지 않는다."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_MODULE_PATH = "scripts.evaluate_v2_direct_probe_llm_quality"


class OptInGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = os.environ.pop("RUN_V2_DIRECT_PROBE_LLM_REVIEW", None)
        self.addCleanup(self._restore)
        self.module = importlib.import_module(_MODULE_PATH)
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.tmp_output_path = Path(self._tmpdir.name) / "report.md"

    def _restore(self) -> None:
        if self._saved is not None:
            os.environ["RUN_V2_DIRECT_PROBE_LLM_REVIEW"] = self._saved

    def test_default_run_does_not_call_network(self) -> None:
        with patch("src.llm.openai_client.OpenAIChatClient") as mock_client:
            self.module.main(output_path=self.tmp_output_path)
            mock_client.assert_not_called()

    def test_default_run_writes_not_executed_report(self) -> None:
        self.module.main(output_path=self.tmp_output_path)
        text = self.tmp_output_path.read_text(encoding="utf-8")
        self.assertIn("실검증 미실행", text)

    def test_default_run_does_not_touch_real_committed_report(self) -> None:
        """§1 회귀 고정 — 이 opt-in 게이트 테스트가 실제 커밋된 보고서 파일을 절대
        건드리지 않는지 SHA-256으로 확인한다."""

        import hashlib

        real_path = self.module.OUTPUT_PATH
        before = hashlib.sha256(real_path.read_bytes()).hexdigest()
        self.module.main(output_path=self.tmp_output_path)
        after = hashlib.sha256(real_path.read_bytes()).hexdigest()
        self.assertEqual(before, after)

    def test_default_run_output_file_ends_with_exactly_one_trailing_newline(self) -> None:
        """§1 — EOF에 불필요한 빈 줄이 남지 않는지 확인한다(git diff --check 경고 방지)."""

        self.module.main(output_path=self.tmp_output_path)
        text = self.tmp_output_path.read_text(encoding="utf-8")
        self.assertTrue(text.endswith("\n"))
        self.assertFalse(text.endswith("\n\n"))


class CallBudgetedLLMClientTest(unittest.TestCase):
    def test_stops_calling_real_client_after_budget_exhausted(self) -> None:
        module = importlib.import_module(_MODULE_PATH)

        class _FakeInner:
            def __init__(self) -> None:
                self.calls = 0

            def complete_structured(self, *, system_prompt, user_prompt, response_model):
                self.calls += 1
                return "ok"

        inner = _FakeInner()
        budgeted = module._CallBudgetedLLMClient(inner)
        budgeted_max = module.MAX_TOTAL_LLM_CALLS
        for _ in range(budgeted_max):
            budgeted.complete_structured(system_prompt="s", user_prompt="u", response_model=None)
        self.assertEqual(inner.calls, budgeted_max)

        with self.assertRaises(Exception):
            budgeted.complete_structured(system_prompt="s", user_prompt="u", response_model=None)
        self.assertEqual(inner.calls, budgeted_max)  # 예산 초과 후에는 내부 Client를 더 이상 부르지 않는다

    def test_budget_matches_14_blueprints_times_2_samples(self) -> None:
        module = importlib.import_module(_MODULE_PATH)
        self.assertEqual(module.MAX_TOTAL_LLM_CALLS, 28)
        self.assertEqual(module.MAX_SAMPLES_PER_BLUEPRINT, 2)


if __name__ == "__main__":
    unittest.main()
