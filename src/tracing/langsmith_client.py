"""TraceClient Protocol의 실제 구현체 — LangSmith 공식 SDK로 Run을 기록한다. 이 파일은
Adapter이므로 얇게 유지한다(src/llm/openai_client.py와 동일한 원칙).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from langsmith import Client

from src.tracing.protocols import TraceError
from src.tracing.settings import TracingSettings


class LangSmithTraceClient:
    def __init__(self, settings: TracingSettings) -> None:
        self._client = Client(api_key=settings.api_key)
        self._project = settings.project

    def record_run(
        self,
        *,
        trace_id: str,
        name: str,
        run_type: str,
        attributes: dict[str, object],
    ) -> None:
        try:
            now = datetime.now(timezone.utc)
            self._client.create_run(
                id=uuid4(),
                trace_id=trace_id,
                name=name,
                run_type=run_type,
                project_name=self._project,
                inputs=attributes,
                outputs={},
                start_time=now,
                end_time=now,
            )
        except Exception as exc:  # 원인 보존 — 조용히 삼키지 않는다 (CLAUDE.md)
            raise TraceError(f"LangSmith Trace 기록 실패: {exc}") from exc
