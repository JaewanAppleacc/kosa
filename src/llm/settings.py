"""LLM 연결 설정 — .env에서 읽는다 (CLAUDE.md: "API Key와 Secret을 코드, 테스트 Fixture,
로그, 프론트엔드, Git에 넣지 않는다"). 이 파일 자체에는 값이 없고 환경변수 이름만 안다.

채팅과 임베딩은 Base URL이 다른 별도 엔드포인트라 설정을 분리해서 들고 있는다
(원본 안내 문서 §4: "채팅용 / 임베딩용 Base URL이 따로 있습니다").
"""

from __future__ import annotations

import os

from pydantic import BaseModel


class LLMSettingsError(RuntimeError):
    """필요한 환경변수가 없을 때 — 조용히 기본값으로 넘어가지 않고 바로 실패시킨다."""


class ChatLLMSettings(BaseModel):
    api_key: str
    base_url: str
    model: str


def load_chat_llm_settings(env: dict[str, str] | None = None) -> ChatLLMSettings:
    """환경변수에서 Chat LLM 설정을 읽는다. `env`를 넘기면 os.environ 대신 그걸 쓴다
    (테스트에서 실제 프로세스 환경을 건드리지 않고 주입하기 위함)."""

    source = env if env is not None else os.environ
    missing = [
        name
        for name in ("OPENAI_API_KEY", "OPENAI_CHAT_BASE_URL", "OPENAI_CHAT_MODEL")
        if not source.get(name)
    ]
    if missing:
        raise LLMSettingsError(
            f"다음 환경변수가 없습니다: {', '.join(missing)}. "
            ".env.example을 참고해 .env를 채워주세요."
        )
    return ChatLLMSettings(
        api_key=source["OPENAI_API_KEY"],
        base_url=source["OPENAI_CHAT_BASE_URL"],
        model=source["OPENAI_CHAT_MODEL"],
    )
