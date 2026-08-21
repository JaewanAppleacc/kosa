"""Chat LLM Protocol — CLAUDE.md: "시간, UUID, LLM, DB, Retriever는 테스트에서 주입하거나
대체할 수 있게 한다", "외부 서비스는 Protocol 또는 Adapter 뒤에 둔다". §10 질문 생성기는
이 Protocol만 보고 짜고, 테스트에서는 실제 OpenAI 호출 없는 Fake로 바꿔 끼운다.
"""

from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


class LLMCallError(RuntimeError):
    """LLM 호출 실패 — 예외를 삼키지 않고 원인을 보존한 채 상위(Cache·재생성·Backup
    라우팅, CLAUDE.md 질문 생성 규칙)로 올린다."""


class ChatLLMClient(Protocol):
    def complete_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[ModelT],
    ) -> ModelT:
        """`response_model` 형태의 Structured Output 하나를 반환한다. 실패하면
        LLMCallError를 던진다(§10: 생성 실패 시 Cache·재생성·Backup 순서로 처리하는 건
        호출하는 쪽 책임이지 여기서 조용히 기본값을 반환하지 않는다)."""
        ...
