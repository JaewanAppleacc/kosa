"""LangSmith 실제 Trace 구조 검증용 Smoke Test — 2026-08-22 3차 리뷰 항목 5.

`unittest discover`는 이 파일을 절대 실행하지 않는다(scripts/에 있고 tests/ 밖이라 discover
대상이 아니다). 이 스크립트도 그 위에 한 번 더 방어선을 둔다 — 아래 두 조건을 모두
만족해야만 실제 네트워크 호출을 시도한다:

1. `RUN_LANGSMITH_SMOKE_TEST=true` (이 스크립트 전용 opt-in — `LANGSMITH_TRACING`과
   별개다. `LANGSMITH_TRACING=true`만 켜져 있으면 평소 API 서버가 켜질 때 자동으로
   Trace를 보내므로, 이 스크립트를 "실수로 매번 같이 실행되는 것"과 구분해야 한다)
2. `LANGSMITH_API_KEY`/`LANGSMITH_PROJECT`가 `.env` 또는 환경변수에 실제로 설정돼 있음
   (`src.tracing.settings.load_tracing_settings()`가 이미 쓰는 것과 동일한 필수값 검사)

무엇을 확인하는가(CLAUDE.md §24 + 2026-08-22 3차/6차 리뷰 요구사항):
  A. 한 세션의 Root Run(Assessment Session) + 6개 Stage(Context Selector →
     Evidence Update → Stop/Continue → Target Planner → Profile Summary Generator →
     Question Generator) Child Run, 총 7개 Run이 실제로 같은 Trace(trace_id)로 묶여
     LangSmith에서 조회되는가.
  B. 2026-08-22 6차 리뷰로 확인된 사실: 예전처럼 매 Run을 `trace_id`만 채운 평행 Run으로
     보내면 서버가 `400 Bad Request(dotted_order is required when trace_id is
     provided)`로 거부한다 — 그래서 지금은 공식 `RunTree`로 세션마다 Root Run 1개를
     만들고 각 Stage를 그 Root의 Child Run으로 기록한다(src/tracing/langsmith_client.py).
     이 스크립트는 그 결과가 실제 서버에서도 Root/Child 트리(parent_run_id가 Root.id를
     가리키고, dotted_order가 Root의 dotted_order로 시작함)로 조회되는지 확인한다.
  C. Sanitizer(§24)를 거치지 않은 원문(예: 학생 자유서술 텍스트)이 실제로 전송되지
     않는지 — 이 스크립트가 일부러 허용되지 않은 필드를 섞어 보내고, 서버에서
     읽어온 결과에 그 원문이 없는지 직접 대조한다.
  D. LangSmith 자체가 죽었을 때(잘못된 API Key로 강제 재현) Tracer.record_stage()가
     예외를 세션 밖으로 던지지 않는지(fail-open, §24).

이 스크립트는 절대로 API Key를 파일에 하드코딩하거나 로그에 출력하지 않는다 — 항상
`os.environ`에서만 읽고, 출력에는 마스킹된 접두사만 남긴다.

실행 방법(로컬에서 실제 LangSmith 계정이 있을 때만):

    LANGSMITH_TRACING=true \\
    LANGSMITH_API_KEY=ls__... \\
    LANGSMITH_PROJECT=<프로젝트명> \\
    RUN_LANGSMITH_SMOKE_TEST=true \\
    ./.venv/bin/python scripts/langsmith_smoke_test.py

Key가 없거나 opt-in 플래그가 꺼져 있으면 아무 네트워크 호출도 하지 않고 그 사실을 그대로
출력한 뒤 종료한다 — "실행 안 됨"을 "성공"으로 위장하지 않는다(CLAUDE.md "외부 API 실패를
성공 응답으로 위장하지 않는다"와 같은 원칙).
"""

from __future__ import annotations

import os
import sys
import time
from uuid import UUID

from dotenv import load_dotenv

load_dotenv()

from src.ids import generate_trace_id
from src.tracing.langsmith_client import LangSmithTraceClient
from src.tracing.settings import TracingSettingsError, load_tracing_settings
from src.tracing.tracer import Tracer

_OPT_IN_VAR = "RUN_LANGSMITH_SMOKE_TEST"

# 실제 main.py가 기록하는 6개 Stage 이름 그대로 재현한다(가짜 이름을 새로 만들지 않는다 —
# 실제 운영 경로와 다른 이름이면 "실제 구조를 검증했다"고 말할 수 없다).
_REAL_STAGE_NAMES = [
    "Context Selector",
    "Evidence Update",
    "Stop / Continue Decision",
    "Target Planner",
    "Profile Summary Generator",
    "Question Generator",
]

# Sanitizer(§24)가 실제로 허용하는 값만 "정상 Attribute"로 섞는다 — sanitizer.py의
# _ALLOWED_PLANNER_DECISION_REASONS/_ALLOWED_STOP_REASONS와 동일한 값을 그대로 쓴다.
_SAFE_ATTRIBUTES: dict[str, dict[str, object]] = {
    "Context Selector": {"graph_node": "context_selector", "context_id": "game"},
    "Evidence Update": {"graph_node": "evidence_update", "stop_reason": "CONTINUE"},
    "Stop / Continue Decision": {"graph_node": "stop_or_continue", "stop_reason": "STOP"},
    "Target Planner": {
        "graph_node": "target_planner",
        "planner_decision_reason": "관심 지점 심화 확인",
    },
    "Profile Summary Generator": {"graph_node": "profile_generator"},
    "Question Generator": {"graph_node": "question_generator", "source": "llm"},
}

# C 검증용 — Sanitizer가 절대 허용하면 안 되는 자유서술 원문 흉내. 이 문자열이 서버에서
# 읽어온 Run에 그대로 남아있으면 Sanitizer가 뚫린 것이다.
_FORBIDDEN_MARKER = "이것은_학생_자유서술_원문_마커_보내면_안됨_67f3a1"


def _mask(secret: str) -> str:
    return secret[:6] + "…" if len(secret) > 6 else "…"


def main() -> int:
    opted_in = os.environ.get(_OPT_IN_VAR, "").strip().lower() in {"1", "true", "yes"}
    if not opted_in:
        print(
            f"[스킵] {_OPT_IN_VAR}=true가 설정되지 않았습니다 — 실제 네트워크 호출을 "
            "하지 않았습니다. 이 스크립트는 opt-in 전용입니다."
        )
        return 0

    try:
        settings = load_tracing_settings()
    except TracingSettingsError as exc:
        print(f"[스킵] LangSmith 설정이 불완전해 실제 네트워크 호출을 하지 않았습니다: {exc}")
        return 0

    print(f"[정보] LANGSMITH_PROJECT={settings.project!r}, API Key={_mask(settings.api_key)}")

    # --- D. fail-open 확인: 일부러 매우 짧은(무효) API Key로 클라이언트를 만들어 실패를
    # 강제 재현한다 — 진짜 계정 Key를 훼손하지 않고도 "장애 상황"을 시뮬레이션한다.
    # 주의: LangSmith 공식 SDK는 기본적으로 Run 전송을 백그라운드 스레드/배치 큐로
    # 미루는 구조라, create_run() 호출 자체는 자격증명이 잘못돼도 그 자리에서 동기적으로
    # 예외를 던지지 않을 수 있다 — 그 경우 이 확인은 "동기 호출 경로의 fail-open"만
    # 증명하고, 배치 전송이 나중에 조용히 실패하는 경로까지는 이 스크립트로 못 잡는다.
    # 이 한계는 아래 결론에도 그대로 보고한다.
    from src.tracing.settings import TracingSettings

    broken_client = LangSmithTraceClient(TracingSettings(api_key="invalid_key_for_smoke_test", project=settings.project))
    broken_tracer = Tracer(broken_client)
    try:
        broken_tracer.record_stage(
            trace_id=generate_trace_id(), stage_name="Smoke Test Fail-Open Probe",
            attributes={"graph_node": "smoke_test"},
        )
        print("[D 확인] fail-open 통과 — 잘못된 API Key로도 record_stage()가 예외를 던지지 않았습니다.")
    except Exception as exc:  # noqa: BLE001 — 이 자체가 실패 사례이므로 그대로 보고한다.
        print(f"[D 실패] record_stage()가 예외를 세션 밖으로 던졌습니다(fail-open 위반): {exc!r}")
        return 1

    # --- A/B/C. 실제 세션 하나를 흉내내 Root Run(Assessment Session) + 6개 Stage
    # Child Run을 같은 trace_id로 기록하고, 서버에서 다시 읽어와 실제 그룹핑·트리
    # 구조·오염 여부를 확인한다.
    real_client = LangSmithTraceClient(settings)
    tracer = Tracer(real_client)
    trace_id = generate_trace_id()
    print(f"[정보] 이번 Smoke Test trace_id={trace_id}(Root Run.id와 동일해야 함)")

    for stage_name in _REAL_STAGE_NAMES:
        attributes = dict(_SAFE_ATTRIBUTES[stage_name])
        # Sanitizer가 이 Key/Value를 실제로 걸러내는지 확인하기 위해 허용되지 않는
        # 필드를 일부러 섞는다 — Sanitizer를 통과하면 안 되는 값이다.
        attributes["student_free_text_should_be_stripped"] = _FORBIDDEN_MARKER
        tracer.record_stage(trace_id=trace_id, stage_name=stage_name, attributes=attributes)

    expected_run_count = 1 + len(_REAL_STAGE_NAMES)  # Root 1개 + Stage 6개
    print(f"[정보] Root 1개 + Stage {len(_REAL_STAGE_NAMES)}개 전송 완료. "
          f"LangSmith 서버 인덱싱 대기 중(5초)...")
    time.sleep(5)

    try:
        from langsmith import Client

        query_client = Client(api_key=settings.api_key)
        fetched = list(query_client.list_runs(trace_id=UUID(trace_id), project_name=settings.project))
    except Exception as exc:  # noqa: BLE001 — 조회 자체가 실패해도 세션엔 영향 없지만, 결과는 정직하게 보고한다.
        print(f"[경고] 방금 보낸 Run을 다시 조회하는 데 실패했습니다: {exc!r}")
        print("계정에서 직접 LangSmith 웹 UI로 trace_id를 검색해 A/B/C 항목을 눈으로 확인하세요.")
        return 0

    print(f"\n=== 조회 결과: trace_id={trace_id}로 {len(fetched)}개 Run 발견(기대값 {expected_run_count}) ===")
    if len(fetched) != expected_run_count:
        print(
            f"[A 주의] Root+Stage는 {expected_run_count}개인데 조회된 Run은 {len(fetched)}개입니다 "
            "— 인덱싱 지연일 수도, 일부 전송이 실패했을 수도 있습니다(재조회 권장)."
        )
    else:
        print(f"[A 확인] Root 1개 + Stage {len(_REAL_STAGE_NAMES)}개가 전부 같은 trace_id로 조회됩니다.")

    # --- B: Root/Child 트리 구조 확인. Root는 자기 id가 곧 trace_id이고 parent_run_id가
    # 없다(None) — 그 Root의 id를 parent_run_id로 가리키는 나머지가 전부 Child여야 한다.
    trace_uuid = UUID(trace_id)
    roots = [r for r in fetched if getattr(r, "id", None) == trace_uuid]
    children = [r for r in fetched if r not in roots]
    print(f"[B 확인] Root로 식별된 Run: {len(roots)}개, Child로 식별된 Run: {len(children)}개")
    if len(roots) != 1:
        print(
            f"[B 실패] Root Run(id==trace_id)이 정확히 1개여야 하는데 {len(roots)}개입니다 — "
            "langsmith_client.py의 Root 생성 로직을 점검하세요."
        )
        return 1
    root = roots[0]
    print(f"[B 확인] Root.parent_run_id={getattr(root, 'parent_run_id', None)} (None이어야 함)")
    mismatched_parent = [c for c in children if getattr(c, "parent_run_id", None) != root.id]
    mismatched_dotted_order = [
        c for c in children
        if not str(getattr(c, "dotted_order", "")).startswith(str(getattr(root, "dotted_order", "")) + ".")
    ]
    if mismatched_parent or mismatched_dotted_order:
        print(
            f"[B 실패] Child 중 parent_run_id 불일치 {len(mismatched_parent)}개, "
            f"dotted_order가 Root로 시작하지 않는 것 {len(mismatched_dotted_order)}개 발견."
        )
        return 1
    print(
        "[B 확인] 모든 Child Run의 parent_run_id==Root.id이고, dotted_order가 "
        "Root.dotted_order로 시작합니다 — 실제 서버에서도 Root/Child 트리로 묶입니다."
    )

    leaked = [r for r in fetched if _FORBIDDEN_MARKER in str(getattr(r, "inputs", {}))]
    if leaked:
        print(
            f"[C 실패] Sanitizer를 우회해 금지 마커가 그대로 전송된 Run이 {len(leaked)}개 있습니다! "
            "sanitize_trace_attributes()의 Allowlist를 점검하세요."
        )
        return 1
    print("[C 확인] 금지 마커가 조회된 어떤 Run의 inputs에도 없습니다 — Sanitizer가 실제로 걸러냅니다.")

    print("\n=== Smoke Test 종료 — 위 [A/B/C/D 확인]·[주의]·[실패] 줄을 사람이 직접 검토하세요. ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
