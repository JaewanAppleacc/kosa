"""V2 Direct Probe LLM 품질 평가 스크립트 테스트 — 2026-08-23 Trait Ontology v2(2.1단계)
§12. 실제 네트워크 호출 없이 opt-in 게이트와 호출 예산 로직만 확인한다."""

from __future__ import annotations

import importlib
import os
import unittest
from unittest.mock import patch

_MODULE_PATH = "scripts.evaluate_v2_direct_probe_llm_quality"


class OptInGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = os.environ.pop("RUN_V2_DIRECT_PROBE_LLM_REVIEW", None)
        self.addCleanup(self._restore)
        self.module = importlib.import_module(_MODULE_PATH)

    def _restore(self) -> None:
        if self._saved is not None:
            os.environ["RUN_V2_DIRECT_PROBE_LLM_REVIEW"] = self._saved

    def test_default_run_does_not_call_network(self) -> None:
        with patch("src.llm.openai_client.OpenAIChatClient") as mock_client:
            self.module.main()
            mock_client.assert_not_called()

    def test_default_run_writes_not_executed_report(self) -> None:
        self.module.main()
        text = self.module.OUTPUT_PATH.read_text(encoding="utf-8")
        self.assertIn("실검증 미실행", text)


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
