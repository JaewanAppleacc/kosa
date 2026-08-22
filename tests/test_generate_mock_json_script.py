"""2026-08-22 리뷰 7항목: Mock JSON 생성 스크립트가 로컬 `.env` 상태와 무관하게 항상
결정론적 Mock/Fallback 경로만 타는지, 실제 네트워크 호출을 전혀 하지 않는지 확인한다.
스크립트가 실제로 쓰는 outputs/mock_api/를 건드리지 않도록 임시 디렉터리로 격리한다.
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.generate_mock_json as mock_script
import src.api.main as main_module
from src.llm.protocols import LLMCallError


def _run_main_quietly() -> None:
    with contextlib.redirect_stdout(io.StringIO()):
        mock_script.main()


class _AlwaysFailingLLMClient:
    """main()이 실제로 이걸 쓰면 즉시 실패한다 — "네트워크를 안 쓴다"가 아니라 "이
    Client를 아예 안 부른다"를 검증하기 위한 감시견(watchdog) 역할."""

    def complete_structured(self, *, system_prompt, user_prompt, response_model):
        raise LLMCallError("이 Fake Client가 호출됐다면 스크립트가 _llm_client를 제대로 끄지 못한 것")


class GenerateMockJsonScriptTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp_dir.cleanup)
        self.out_dir = Path(self._tmp_dir.name)
        out_dir_patcher = patch.object(mock_script, "OUT_DIR", self.out_dir)
        out_dir_patcher.start()
        self.addCleanup(out_dir_patcher.stop)

    def test_main_never_touches_llm_client_even_when_one_is_already_configured(self) -> None:
        """로컬 .env가 ENABLE_LLM_QUESTION_GENERATION=true였다고 가정하고, main.py의
        _llm_client가 이미 실제 Client처럼 설정된 상태에서 시작해도, 스크립트 실행 중에는
        절대 호출되지 않아야 한다."""

        watchdog = _AlwaysFailingLLMClient()
        with patch.object(main_module, "_llm_client", watchdog):
            _run_main_quietly()  # 예외 없이 끝나야 한다 — watchdog가 호출됐다면 LLMCallError로 실패

        # 스크립트가 끝난 뒤에는 main_module._llm_client가 patch 컨텍스트 종료로 원래
        # watchdog로 복원된다 — 이건 스크립트 실행 "동안"만 껐다는 뜻이고, 실제로
        # 아무 파일도 못 만들었다면 애초에 위 호출에서 예외가 났을 것이다.
        self.assertTrue((self.out_dir / "profile_normal.json").exists())

    def test_two_consecutive_runs_produce_byte_identical_output(self) -> None:
        _run_main_quietly()
        first_run = {p.name: p.read_bytes() for p in self.out_dir.glob("*.json")}

        # 같은 임시 디렉터리에 다시 생성 — 파일이 덮어써진다.
        _run_main_quietly()
        second_run = {p.name: p.read_bytes() for p in self.out_dir.glob("*.json")}

        self.assertEqual(set(first_run), set(second_run))
        mismatched = [name for name in first_run if first_run[name] != second_run[name]]
        self.assertEqual(mismatched, [], f"재실행마다 달라지는 파일: {mismatched}")

    def test_generated_files_are_valid_json(self) -> None:
        _run_main_quietly()
        json_files = list(self.out_dir.glob("*.json"))
        self.assertGreater(len(json_files), 10)  # 스크립트가 실제로 여러 파일을 만들었는지 확인
        for path in json_files:
            with self.subTest(file=path.name):
                json.loads(path.read_text(encoding="utf-8"))  # 파싱 실패하면 바로 테스트 실패

    def test_profile_normal_matches_career_profile_schema(self) -> None:
        from src.schemas.profile import CareerProfile

        _run_main_quietly()
        payload = json.loads((self.out_dir / "profile_normal.json").read_text(encoding="utf-8"))
        CareerProfile.model_validate(payload)  # 실패하면 ValidationError로 테스트가 바로 실패

    def test_majors_normal_matches_majors_response_schema(self) -> None:
        from src.schemas.api import MajorsResponse

        _run_main_quietly()
        payload = json.loads((self.out_dir / "majors_normal.json").read_text(encoding="utf-8"))
        MajorsResponse.model_validate(payload)


if __name__ == "__main__":
    unittest.main()
