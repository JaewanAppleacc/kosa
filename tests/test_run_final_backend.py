"""scripts/run_final_backend.py 테스트 — 2026-08-25 지시서(a/final-runtime-v2-primary) §2/§7.

이 모듈을 import하는 것만으로는 실제 서버 Process가 뜨지 않는다(uvicorn은 main()
내부에서만 import·호출된다) — `validate_final_runtime_flags()`만 순수 함수로 검사한다.
`main()`의 성공 경로는 `uvicorn.run`을 Mock으로 대체해 실제 바인딩 없이 확인한다."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from scripts.run_final_backend import REQUIRED_FLAG_NAMES, main, validate_final_runtime_flags

_ALL_ON = {name: "true" for name in REQUIRED_FLAG_NAMES}


class ValidateFinalRuntimeFlagsTest(unittest.TestCase):
    def test_all_four_on_returns_empty(self) -> None:
        self.assertEqual(validate_final_runtime_flags(env=_ALL_ON), [])

    def test_default_env_empty_dict_reports_all_four_missing(self) -> None:
        self.assertEqual(sorted(validate_final_runtime_flags(env={})), sorted(REQUIRED_FLAG_NAMES))

    def test_missing_primary_only(self) -> None:
        """§1 재현 시나리오 — 기존 세 Flag만 켜고 PRIMARY가 빠진 경우."""
        env = dict(_ALL_ON)
        del env["ENABLE_TRAIT_VECTOR_V2_PRIMARY"]
        self.assertEqual(validate_final_runtime_flags(env=env), ["ENABLE_TRAIT_VECTOR_V2_PRIMARY"])

    def test_each_single_missing_flag_is_reported_individually(self) -> None:
        for missing_name in REQUIRED_FLAG_NAMES:
            with self.subTest(missing=missing_name):
                env = dict(_ALL_ON)
                del env[missing_name]
                self.assertEqual(validate_final_runtime_flags(env=env), [missing_name])

    def test_garbage_value_counts_as_missing(self) -> None:
        env = dict(_ALL_ON)
        env["ENABLE_TRAIT_VECTOR_V2_PRIMARY"] = "banana"
        self.assertEqual(validate_final_runtime_flags(env=env), ["ENABLE_TRAIT_VECTOR_V2_PRIMARY"])

    def test_case_and_alias_variants_are_accepted(self) -> None:
        for value in ("1", "true", "True", "TRUE", "yes", "YES"):
            with self.subTest(value=value):
                env = {name: value for name in REQUIRED_FLAG_NAMES}
                self.assertEqual(validate_final_runtime_flags(env=env), [])

    def test_default_os_environ_used_when_env_omitted(self) -> None:
        with patch("scripts.run_final_backend.os.environ", dict(_ALL_ON)):
            self.assertEqual(validate_final_runtime_flags(), [])


class MainFailFastTest(unittest.TestCase):
    """§2 "하나라도 빠지면 누락된 Flag 이름을 출력하고 Fail-Fast" — 실제 서버를
    띄우지 않고 확인한다(uvicorn.run이 절대 호출되지 않아야 한다)."""

    def test_missing_flags_exit_code_2_and_lists_missing_names(self) -> None:
        env = dict(_ALL_ON)
        del env["ENABLE_TRAIT_VECTOR_V2_PRIMARY"]
        del env["ENABLE_CONTEXT_PACK_RUNTIME"]
        stderr = io.StringIO()
        with patch("scripts.run_final_backend.os.environ", env), redirect_stderr(stderr):
            code = main([])
        self.assertEqual(code, 2)
        bullet_lines = [line for line in stderr.getvalue().splitlines() if line.strip().startswith("- ")]
        self.assertEqual(
            sorted(line.strip("- ").strip() for line in bullet_lines),
            sorted(["ENABLE_TRAIT_VECTOR_V2_PRIMARY", "ENABLE_CONTEXT_PACK_RUNTIME"]),
        )

    def test_missing_flags_never_calls_uvicorn_run(self) -> None:
        with patch("scripts.run_final_backend.os.environ", {}), patch("uvicorn.run") as mock_run:
            main([])
        mock_run.assert_not_called()

    def test_empty_env_reports_all_four(self) -> None:
        stderr = io.StringIO()
        with patch("scripts.run_final_backend.os.environ", {}), redirect_stderr(stderr):
            code = main([])
        self.assertEqual(code, 2)
        for name in REQUIRED_FLAG_NAMES:
            self.assertIn(name, stderr.getvalue())


class MainSuccessPathTest(unittest.TestCase):
    """네 Flag가 전부 켜져 있으면 uvicorn.run을 정확히 한 번, src.api.main:app으로
    호출한다 — 실제 소켓 바인딩은 uvicorn.run 자체를 Mock으로 대체해 피한다."""

    def test_all_four_on_invokes_uvicorn_run_with_app_target(self) -> None:
        stdout = io.StringIO()
        with (
            patch("scripts.run_final_backend.os.environ", dict(_ALL_ON)),
            patch("uvicorn.run") as mock_run,
            redirect_stdout(stdout),
        ):
            code = main(["--port", "8321"])
        self.assertEqual(code, 0)
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        self.assertEqual(args[0], "src.api.main:app")
        self.assertEqual(kwargs["port"], 8321)

    def test_success_output_does_not_leak_unrelated_env_values(self) -> None:
        """Secret 값을 출력하지 않는다 — 이 스크립트가 실제로 확인하는 것은 Flag
        '이름'뿐이고, env에 다른(민감할 수 있는) 값이 섞여 있어도 그 값 자체를
        출력해서는 안 된다."""
        env = dict(_ALL_ON)
        env["SOME_SECRET_LOOKING_TOKEN"] = "sk-do-not-print-me-12345"
        stdout = io.StringIO()
        with (
            patch("scripts.run_final_backend.os.environ", env),
            patch("uvicorn.run"),
            redirect_stdout(stdout),
        ):
            main([])
        self.assertNotIn("sk-do-not-print-me-12345", stdout.getvalue())

    def test_default_host_and_port_match_existing_uvicorn_convention(self) -> None:
        with (
            patch("scripts.run_final_backend.os.environ", dict(_ALL_ON)),
            patch("uvicorn.run") as mock_run,
        ):
            main([])
        _, kwargs = mock_run.call_args
        self.assertEqual(kwargs["host"], "127.0.0.1")
        self.assertEqual(kwargs["port"], 8000)


if __name__ == "__main__":
    unittest.main()
