"""LangSmith Trace Client Protocol — CLAUDE.md: "외부 서비스는 Protocol 또는 Adapter
뒤에 둔다", "시간, UUID, LLM, DB, Retriever는 테스트에서 주입하거나 대체할 수 있게 한다".
Tracer(tracer.py)는 이 Protocol만 보고 짜고, 테스트에서는 실제 LangSmith 호출 없는
Fake로 바꿔 끼운다.
"""

from __future__ import annotations

from typing import Protocol


class TraceError(RuntimeError):
    """Trace 기록 실패 — 예외를 삼키지 않고 원인을 보존한다. 이 예외 자체는 Tracer가
    호출자에게 전파하지 않는다(§24 fail-open) — Tracer 내부에서만 잡아 로그로 남긴다."""


class TraceClient(Protocol):
    def record_run(
        self,
        *,
        trace_id: str,
        name: str,
        run_type: str,
        attributes: dict[str, object],
    ) -> None:
        """하나의 Node/Stage 실행을 Run으로 기록한다. 같은 trace_id로 여러 번 호출하면
        LangSmith가 같은 Trace로 묶는다 — Assessment Session 하나가 여러 HTTP 요청에
        걸쳐 진행되므로, 한 Python 호출 스택 안에서 트리를 만드는 대신 이 방식을 쓴다.
        실패하면 TraceError를 던진다(호출자인 Tracer가 fail-open을 책임진다)."""
        ...
