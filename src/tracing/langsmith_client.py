"""TraceClient Protocol의 실제 구현체 — LangSmith 공식 SDK로 Run을 기록한다. 이 파일은
Adapter이므로 얇게 유지한다(src/llm/openai_client.py와 동일한 원칙).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

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
            # 2026-08-22 리뷰: LangSmith SDK의 Run.trace_id는 UUID 타입이다 — 문자열을
            # 그대로 넘기면 서버가 조용히 거부할 수 있다(fail-open이라 서비스는 안 끊기지만
            # Trace가 하나도 안 쌓이는 소리 없는 실패). 여기서 명시적으로 파싱해서, 형식이
            # 잘못된 trace_id는 TraceError로 바로 드러나게 한다.
            trace_uuid = UUID(trace_id)
            now = datetime.now(timezone.utc)
            self._client.create_run(
                id=uuid4(),
                trace_id=trace_uuid,
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
