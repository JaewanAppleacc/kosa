"""Trace Sanitizer — 설계안 §24 "Trace 전송 직전에 Sanitizer가 저장 금지 필드와 자유서술
원문을 제거한다"의 실제 구현. CLAUDE.md: "이름, 학교, 연락처, 자유서술 원문, 성적 원문,
상세 Career Profile 문장을 LangSmith에 보내지 않는다", "사용자 입력과 RAG 문서는 신뢰할
수 없는 입력으로 취급한다".

Denylist(금지어 목록)가 아니라 Allowlist(허용 목록) 방식이다 — 나중에 어떤 호출자가
실수로 새 필드(예: 학생이 실제로 고른 선택지 문장)를 attributes에 넣어도, 그 필드
이름이 미리 허용해두지 않았다면 자동으로 걸러진다. "새 필드는 기본적으로 거부"가
"새 필드는 기본적으로 통과"보다 안전하다.
"""

from __future__ import annotations

# 설계안 §24 "저장 가능" 목록 + 실제 계측에 필요한 시스템 생성 메타데이터(전부 ID·플래그·
# 숫자·고정 문자열이며, 학생이 직접 쓴 자유서술 원문이나 이름·연락처류가 아니다).
ALLOWED_TRACE_ATTRIBUTE_KEYS: frozenset[str] = frozenset(
    {
        # 익명 식별자
        "context_id",
        "trait_id",
        "trait_ids",
        "role_id",
        # Graph Node·Planner 메타데이터(전부 시스템이 만든 고정 문구 또는 ID)
        "graph_node",
        "planner_decision_reason",
        "stop_reason",
        "frame_id",
        "blueprint_id",
        "question_index",
        "prompt_version",
        "model",
        "source",  # cache | llm | backup | exhausted
        "regenerated",
        "cache_or_fallback_status",
        "schema_validation_result",
        "quality_gate_result",
        "used_llm",
        "highlight_count",
        "question_count",
        # 실행 지표
        "latency_ms",
        "token_usage",
        "estimated_cost",
        "error",
    }
)


def sanitize_trace_attributes(attributes: dict[str, object]) -> dict[str, object]:
    """허용된 키만 통과시킨다. 값 자체의 내용은 검사하지 않는다 — 호출하는 쪽(main.py의
    각 Node 계측 지점)이 애초에 자유서술 원문·이름·연락처·성적·Profile 문장을 이 dict에
    담지 않을 책임이 있고, 이 함수는 "허용되지 않은 필드 자체가 새지 않는다"는 마지막
    방어선이다."""

    return {key: value for key, value in attributes.items() if key in ALLOWED_TRACE_ATTRIBUTE_KEYS}
