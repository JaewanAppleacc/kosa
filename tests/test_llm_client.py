"""LLM 설정 로딩 + Protocol 주입 테스트. 실제 네트워크 호출은 하지 않는다 — Fake로
ChatLLMClient Protocol을 만족시켜서 §10 질문 생성기가 이 인터페이스만으로 동작함을 검증한다.
"""

from __future__ import annotations

import unittest

from pydantic import BaseModel

from src.llm.protocols import LLMCallError
from src.llm.settings import LLMSettingsError, load_chat_llm_settings


class LoadChatLLMSettingsTest(unittest.TestCase):
    def test_missing_env_vars_raises(self) -> None:
        with self.assertRaises(LLMSettingsError):
            load_chat_llm_settings(env={})

    def test_partial_env_vars_raises(self) -> None:
        with self.assertRaises(LLMSettingsError):
            load_chat_llm_settings(env={"OPENAI_API_KEY": "sk-test"})

    def test_complete_env_vars_loads(self) -> None:
        settings = load_chat_llm_settings(
            env={
                "OPENAI_API_KEY": "sk-test",
                "OPENAI_CHAT_BASE_URL": "https://example.com/v1",
                "OPENAI_CHAT_MODEL": "openai/gpt-4.1-mini",
            }
        )
        self.assertEqual(settings.api_key, "sk-test")
        self.assertEqual(settings.base_url, "https://example.com/v1")
        self.assertEqual(settings.model, "openai/gpt-4.1-mini")


class _Greeting(BaseModel):
    text: str


class _FakeChatLLMClient:
    """ChatLLMClient Protocol을 만족하는 테스트용 대역 — 실제 OpenAI 호출 없음."""

    def __init__(self, canned_response: _Greeting | None = None, should_fail: bool = False) -> None:
        self._canned_response = canned_response
        self._should_fail = should_fail
        self.calls: list[tuple[str, str]] = []

    def complete_structured(self, *, system_prompt, user_prompt, response_model):
        self.calls.append((system_prompt, user_prompt))
        if self._should_fail:
            raise LLMCallError("모의 실패")
        return self._canned_response


class ChatLLMClientProtocolTest(unittest.TestCase):
    def test_fake_client_satisfies_protocol_usage(self) -> None:
        fake = _FakeChatLLMClient(canned_response=_Greeting(text="안녕하세요"))
        result = fake.complete_structured(
            system_prompt="sys", user_prompt="user", response_model=_Greeting
        )
        self.assertEqual(result.text, "안녕하세요")
        self.assertEqual(fake.calls, [("sys", "user")])

    def test_fake_client_raises_llm_call_error(self) -> None:
        fake = _FakeChatLLMClient(should_fail=True)
        with self.assertRaises(LLMCallError):
            fake.complete_structured(
                system_prompt="sys", user_prompt="user", response_model=_Greeting
            )


if __name__ == "__main__":
    unittest.main()
