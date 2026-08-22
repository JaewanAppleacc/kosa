"""LangSmith 연결 설정 — .env에서 읽는다 (CLAUDE.md: "API Key와 Secret을 코드, 테스트
Fixture, 로그, 프론트엔드, Git에 넣지 않는다"). 이 파일 자체에는 값이 없고 환경변수
이름만 안다. src/llm/settings.py와 동일한 패턴이다.
"""

from __future__ import annotations

import os

from pydantic import BaseModel


class TracingSettingsError(RuntimeError):
    """필요한 환경변수가 없을 때 — 조용히 기본값으로 넘어가지 않고 바로 실패시킨다."""


class TracingSettings(BaseModel):
    api_key: str
    project: str


def load_tracing_settings(env: dict[str, str] | None = None) -> TracingSettings:
    """환경변수에서 LangSmith 설정을 읽는다. `env`를 넘기면 os.environ 대신 그걸 쓴다
    (테스트에서 실제 프로세스 환경을 건드리지 않고 주입하기 위함)."""

    source = env if env is not None else os.environ
    missing = [name for name in ("LANGSMITH_API_KEY", "LANGSMITH_PROJECT") if not source.get(name)]
    if missing:
        raise TracingSettingsError(
            f"다음 환경변수가 없습니다: {', '.join(missing)}. "
            ".env.example을 참고해 .env를 채워주세요."
        )
    return TracingSettings(api_key=source["LANGSMITH_API_KEY"], project=source["LANGSMITH_PROJECT"])


def tracing_enabled(env: dict[str, str] | None = None) -> bool:
    """명시적 opt-in 플래그. `unittest discover`가 개발자 로컬 `.env`의 실제 Key를
    우연히 읽어서 테스트 중 진짜 네트워크 호출을 하는 사고를 막기 위함이다(§10
    ENABLE_LLM_QUESTION_GENERATION과 동일한 안전장치)."""

    source = env if env is not None else os.environ
    return source.get("LANGSMITH_TRACING", "").strip().lower() in {"1", "true", "yes"}
