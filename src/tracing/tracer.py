"""Tracer — §24 Assessment Session Trace 계측 지점(main.py)이 실제로 호출하는 얇은 래퍼.

CLAUDE.md: "LangSmith 장애는 로컬 로그만 남기고 사용자 Session을 중단하지 않는다." 이
보장을 여기 한 곳에서만 구현해서, 계측 지점(main.py 곳곳)마다 각자 try/except를 반복하지
않게 한다 — `record_stage()`는 무슨 일이 있어도 예외를 던지지 않는다(TraceClient가 없거나,
설정이 없거나, 네트워크가 죽었거나 전부 동일하게 "로그만 남기고 계속 진행").
"""

from __future__ import annotations

import logging

from src.tracing.protocols import TraceClient
from src.tracing.sanitizer import sanitize_trace_attributes

logger = logging.getLogger("tracing")


class Tracer:
    def __init__(self, client: TraceClient | None) -> None:
        # client가 None이면(설정 없음·TRACING 꺼짐) 항상 조용히 아무것도 안 한다 —
        # "연동 안 함"과 "연동했는데 장애남"을 같은 fail-open 경로로 처리한다.
        self._client = client

    def record_stage(
        self,
        *,
        trace_id: str,
        stage_name: str,
        run_type: str = "chain",
        attributes: dict[str, object] | None = None,
    ) -> None:
        if self._client is None:
            return
        sanitized = sanitize_trace_attributes(attributes or {})
        try:
            self._client.record_run(
                trace_id=trace_id, name=stage_name, run_type=run_type, attributes=sanitized
            )
        except Exception as exc:  # noqa: BLE001 — §24 fail-open: 어떤 예외든 세션을 막지 않는다
            logger.warning(
                "LangSmith Trace 기록 실패(fail-open, 세션은 계속 진행) — stage=%s: %s",
                stage_name,
                exc,
            )
