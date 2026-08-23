"""TraceClient Protocol의 실제 구현체 — LangSmith 공식 SDK로 Run을 기록한다. 이 파일은
Adapter이므로 얇게 유지한다(src/llm/openai_client.py와 동일한 원칙).

2026-08-22 6차 리뷰(실제 LangSmith 계정으로 Smoke Test — scripts/langsmith_smoke_test.py
— 를 돌려서 확인한 서버 응답): 예전 구현은 매 Stage를 `trace_id`만 채운 독립적인 평행
Run으로 보냈는데, 실제 서버는 이걸 전부 `400 Bad Request`로 거부했다 — "invalid
'dotted_order': dotted_order is required when trace_id is provided". 즉 지금까지 이
서비스가 실제 계정으로 보낸 Trace는 단 하나도 기록되지 않았다(§24 Sanitizer·fail-open은
정상 동작했지만, 그 뒤의 실제 전송 자체가 전부 실패).

이 파일은 LangSmith 공식 `RunTree`를 써서 세션(trace_id)마다 Root Run 하나를 만들고,
각 Stage(Context Selector, Evidence Update, ...)를 그 Root의 Child Run으로 기록한다.
`dotted_order`·`parent_run_id`는 임의 문자열을 조립하지 않고 RunTree가 자동으로 계산한
값을 그대로 쓴다(RunTree.create_child()가 parent의 dotted_order를 prefix로 붙인다).
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from uuid import UUID

from langsmith import Client
from langsmith.run_trees import RunTree

from src.tracing.protocols import TraceError
from src.tracing.settings import TracingSettings

# §24: 한 Assessment Session의 모든 Stage를 묶는 Root Run의 고정 이름. main.py의
# 실제 Stage 이름들(Context Selector, Evidence Update, ...)과 겹치지 않는 이름이면 된다.
ROOT_RUN_NAME = "Assessment Session"


class LangSmithTraceClient:
    def __init__(self, settings: TracingSettings) -> None:
        self._client = Client(api_key=settings.api_key)
        self._project = settings.project
        # trace_id(str) -> 이미 서버에 보낸 Root RunTree. 같은 세션(같은 trace_id) 안에서는
        # Root를 한 번만 만들고, 그 뒤 모든 Stage는 이 Root의 Child로 기록한다. 서로 다른
        # trace_id(= 서로 다른 세션)는 이 dict의 서로 다른 항목이라 자동으로 다른 Root를 쓴다.
        self._roots: dict[str, RunTree] = {}
        # 여러 요청이 동시에 같은 세션의 첫 Stage를 기록하려는 경합을 막는다(Root 중복
        # 생성 방지) — MVP 단일 프로세스 가정이라 무거운 처리는 하지 않는다.
        self._lock = threading.Lock()

    def _get_or_create_root(self, trace_id: str, trace_uuid: UUID) -> RunTree:
        with self._lock:
            root = self._roots.get(trace_id)
            if root is not None:
                return root
            now = datetime.now(timezone.utc)
            # Root Run: id==trace_id, trace_id==trace_id, parent_run_id는 지정하지
            # 않으므로 기본값 None(최상위 Run) — RunTree가 이 조건으로 dotted_order도
            # 자동으로 채운다(부모가 없으니 자기 자신의 구간만).
            root = RunTree(
                name=ROOT_RUN_NAME,
                run_type="chain",
                id=trace_uuid,
                trace_id=trace_uuid,
                project_name=self._project,
                client=self._client,
                inputs={},
                start_time=now,
            )
            root.post()
            self._roots[trace_id] = root
            return root

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
            root = self._get_or_create_root(trace_id, trace_uuid)
            now = datetime.now(timezone.utc)
            # Child Run: create_child()가 Stage별 새 UUID를 발급하고, root와 같은
            # trace_id, parent_run_id=root.id, dotted_order=root.dotted_order + "." +
            # 자기 구간을 전부 자동으로 채운다 — 이 파일에서 dotted_order 문자열을 직접
            # 조립하지 않는다. `attributes`는 Tracer.record_stage()가 이미 Sanitizer를
            # 거쳐 넘긴 값이라 그대로 Child의 inputs로 쓴다.
            child = root.create_child(
                name=name,
                run_type=run_type,
                inputs=attributes,
                start_time=now,
                end_time=now,
            )
            child.post()
        except Exception as exc:  # 원인 보존 — 조용히 삼키지 않는다 (CLAUDE.md)
            raise TraceError(f"LangSmith Trace 기록 실패: {exc}") from exc
