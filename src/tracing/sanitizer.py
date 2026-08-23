"""Trace Sanitizer — 설계안 §24 "Trace 전송 직전에 Sanitizer가 저장 금지 필드와 자유서술
원문을 제거한다"의 실제 구현. CLAUDE.md: "이름, 학교, 연락처, 자유서술 원문, 성적 원문,
상세 Career Profile 문장을 LangSmith에 보내지 않는다", "사용자 입력과 RAG 문서는 신뢰할
수 없는 입력으로 취급한다".

Denylist(금지어 목록)가 아니라 Allowlist(허용 목록) 방식이고, 2026-08-22 리뷰로 Key뿐
아니라 Value의 "모양"까지 검사하도록 강화했다 — 허용된 Key라도 값이 정해둔 형태(짧은
slug, 사전 정의된 고정 문구, 숫자 등)와 다르면 통과시키지 않는다. 예전엔 Key만 걸러서,
`error` 같은 필드에 예외 메시지 원문(요청 정보나 예상 못한 문자열 포함 가능)이 그대로
샐 수 있었다.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from src.ids import is_valid_slug

# §10/§8이 실제로 만드는 고정 문구만 허용한다(target_planner.py 원문과 동일하게 유지) —
# 새 문구를 추가하려면 여기도 같이 늘려야 한다는 게 의도된 마찰이다(자유 텍스트가 섞여
# 들어오는 걸 막는 안전장치이지, 목록 유지보수를 피하려고 정규식으로 느슨하게 풀면 안 된다).
_ALLOWED_PLANNER_DECISION_REASONS: frozenset[str] = frozenset(
    {
        "관심 지점 심화 확인",
        "실제 행동·문제 해결 방식 확인",
        "다른 Context Evidence와 교차 확인",
        "반대·대안 상황에서의 선택 확인",
        "해결되지 않은 Explicit Conflict 보완",
        "Evidence가 부족한 핵심 Trait 보완",
        "추가 확인(특정 Gap 없음)",
        "Explicit Conflict 확인 질문",
    }
)

_ALLOWED_STOP_REASONS: frozenset[str] = frozenset({"CONTINUE", "STOP"})
_ALLOWED_SOURCES: frozenset[str] = frozenset({"cache", "llm", "backup", "exhausted"})
_ALLOWED_GATE_RESULTS: frozenset[str] = frozenset({"passed", "failed"})
# question_generator.py/question_generation_graph.py가 실제로 만드는 실패 사유 3종 +
# 그 외 전부를 묶는 unknown_error. 예외 메시지 원문은 여기 들어가지 않는다 — 호출자가
# classify_generation_failure()로 분류한 결과만 들어온다.
_ALLOWED_ERROR_TYPES: frozenset[str] = frozenset(
    {"llm_call_error", "role_id_mismatch", "quality_gate_failure", "trace_error", "unknown_error"}
)
_TOKEN_USAGE_KEYS: frozenset[str] = frozenset({"prompt_tokens", "completion_tokens", "total_tokens"})
_ERROR_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_SHORT_TOKEN_PATTERN = re.compile(r"^[a-zA-Z0-9_.\-]{1,80}$")


def _is_bool(value: object) -> bool:
    return isinstance(value, bool)


def _is_nonneg_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_nonneg_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def _is_slug_or_blank(value: object) -> bool:
    # blueprint_id는 Explicit Conflict 확인 질문(고정 문항)일 때 ""를 쓴다(§12-1 확장) —
    # "해당 없음"을 표현하는 값이지 자유 텍스트가 아니다.
    return value == "" or (isinstance(value, str) and is_valid_slug(value))


def _is_slug(value: object) -> bool:
    return isinstance(value, str) and is_valid_slug(value)


def _is_slug_list(value: object) -> bool:
    return isinstance(value, list) and all(_is_slug(item) for item in value)


def _is_short_token(value: object) -> bool:
    return isinstance(value, str) and bool(_SHORT_TOKEN_PATTERN.match(value))


def _is_error_code(value: object) -> bool:
    return isinstance(value, str) and bool(_ERROR_CODE_PATTERN.match(value))


def _is_token_usage(value: object) -> bool:
    if _is_nonneg_int(value):
        return True
    if isinstance(value, dict):
        return bool(value) and all(
            key in _TOKEN_USAGE_KEYS and _is_nonneg_int(v) for key, v in value.items()
        )
    return False


def _allow_none(inner: Callable[[object], bool]) -> Callable[[object], bool]:
    return lambda value: value is None or inner(value)


# 허용된 Key 전부에 값 검증기가 있어야 한다 — 검증기가 없는 Key는 새지 않는다(아래
# sanitize_trace_attributes가 검증기 없는 Key를 자동으로 거부한다).
_VALUE_VALIDATORS: dict[str, Callable[[object], bool]] = {
    "context_id": _allow_none(_is_slug),
    # 2026-08-23 Trait Ontology v2(2.5.2단계) §6 — Anchor ID는 사전 정의된 고정
    # slug(예: "story_exploration")뿐이라 trait_id/context_id와 같은 검증기를 쓴다.
    # 학생 자유서술 원문은 애초에 이 값에 담기지 않는다(Anchor 선택은 서버가 만든
    # 5개 고정 role_id 중 하나를 고르는 것뿐이지 자유 텍스트가 아니다).
    "context_anchor_id": _allow_none(_is_slug),
    "trait_id": _allow_none(_is_slug),
    "trait_ids": _allow_none(_is_slug_list),
    "role_id": _allow_none(_is_slug),
    "frame_id": _allow_none(_is_slug),
    "blueprint_id": _allow_none(_is_slug_or_blank),
    "contrast_id": _allow_none(_is_slug),
    "graph_node": _allow_none(_is_slug),
    "planner_decision_reason": _allow_none(lambda v: v in _ALLOWED_PLANNER_DECISION_REASONS),
    "stop_reason": _allow_none(lambda v: v in _ALLOWED_STOP_REASONS),
    "source": _allow_none(lambda v: v in _ALLOWED_SOURCES),
    "cache_or_fallback_status": _allow_none(lambda v: v in _ALLOWED_SOURCES),
    "fallback_source": _allow_none(lambda v: v in _ALLOWED_SOURCES),
    "error_type": _allow_none(lambda v: v in _ALLOWED_ERROR_TYPES),
    "error_code": _allow_none(_is_error_code),
    "regenerated": _is_bool,
    "used_llm": _is_bool,
    "highlight_count": _is_nonneg_int,
    "question_count": _is_nonneg_int,
    "question_index": _is_nonneg_int,
    # 2026-08-23 Trait Ontology v2(2.5.3단계) §12 — Backup 후보 검사 결과는 숫자로만
    # 보낸다. 질문·선택지 원문은 애초에 이 Allowlist에 Key가 없어 구조적으로 샐 수 없다.
    "backup_candidates_checked": _is_nonneg_int,
    "backup_candidates_rejected": _is_nonneg_int,
    "latency_ms": _is_nonneg_number,
    "estimated_cost": _is_nonneg_number,
    "token_usage": _is_token_usage,
    "schema_validation_result": _allow_none(lambda v: v in _ALLOWED_GATE_RESULTS),
    "quality_gate_result": _allow_none(lambda v: v in _ALLOWED_GATE_RESULTS),
    "prompt_version": _allow_none(_is_short_token),
    "model": _allow_none(_is_short_token),
    # 2026-08-28 19차 리뷰: Knowledge Subgraph Extractor Stage(§10) — Node·Edge 개수
    # 요약만 허용한다. session_id/user_id/학생 답변 원문/질문 원문/과목 문서 원문·추천
    # 이유 전문은 애초에 이 Allowlist에 Key 자체가 없으므로 구조적으로 샐 수 없다.
    "node_count": _is_nonneg_int,
    "edge_count": _is_nonneg_int,
    "trait_node_count": _is_nonneg_int,
    "major_node_count": _is_nonneg_int,
    "department_node_count": _is_nonneg_int,
    "subject_node_count": _is_nonneg_int,
    # 2026-08-29 19차 후속 보완: "Confirm까지 마쳤는가"(CoursePlanningStore 상태 기준)와
    # "실제로 과목 Node가 생겼는가"(Graph 생성 결과 기준)는 다른 사실이라 필드를
    # 나눴다(빈 confirmed_subject_ids=[]로도 CONFIRMED는 가능하다) — 둘 다 `_is_bool`이라
    # `isinstance(value, bool)`로 엄격히 검사한다(bool이 int의 하위 타입이라는 점 때문에
    # `1`/`0`이 새지 않도록: `isinstance(1, bool)`은 False다).
    "has_confirmed_course_profile": _is_bool,
    "has_subject_nodes": _is_bool,
    # 2026-08-23 Trait Ontology v2(1.5단계) §9 — Trait Vector Shadow Snapshot Stage.
    # 개수 집계만 허용한다. 학생 답변 원문·선택지 원문·user_id·Trait Signal 세부 내용
    # (trait_id·weight·related_concept_ids 등)은 애초에 이 Allowlist에 Key 자체가
    # 없으므로 구조적으로 샐 수 없다(Subgraph Stage와 같은 원칙).
    "core_trait_count": _is_nonneg_int,
    "directly_measurable_count": _is_nonneg_int,
    "related_only_count": _is_nonneg_int,
    "hypothesis_count": _is_nonneg_int,
    "promoted_related_count": _is_nonneg_int,
    "conflict_count": _is_nonneg_int,
    "mapping_source_exact_count": _is_nonneg_int,
    "mapping_source_legacy_adapter_count": _is_nonneg_int,
    "mapping_missing_count": _is_nonneg_int,
    # 2026-08-23 Trait Ontology v2(2단계) §1: "구조상 관찰 가능한가"(질문 Bank 자체의
    # 정적 구조, 학생과 무관하게 항상 같은 값)와 "이 학생 세션에서 실제로 관찰됐는가"
    # (세션마다 다른 값)를 이름으로도 명확히 구분한다 — 1.5단계의 observable_trait_count/
    # not_probed_count는 이름만으로는 어느 쪽인지 알 수 없어서 실제로 값 계산 버그(둘 다
    # len(observed) 재사용)를 숨겼다. 두 필드를 완전히 제거하고 아래 네 필드로 교체한다.
    "structurally_observable_trait_count": _is_nonneg_int,
    "structurally_not_probed_trait_count": _is_nonneg_int,
    "observed_in_session_count": _is_nonneg_int,
    "not_observed_in_session_count": _is_nonneg_int,
}

ALLOWED_TRACE_ATTRIBUTE_KEYS: frozenset[str] = frozenset(_VALUE_VALIDATORS.keys())


def sanitize_trace_attributes(attributes: dict[str, object]) -> dict[str, object]:
    """허용된 키 + 그 키에 맞는 값 모양만 통과시킨다. 값이 검증기를 통과하지 못하면(예:
    자유 텍스트, 중첩 dict, 정해지지 않은 문구) 그 필드 전체를 조용히 버린다 — 무엇을
    보낼지 자체가 Trace를 막지 않는다(§24 fail-open과 같은 정신: Sanitizer 실패가 세션을
    끊으면 안 된다). 예외를 던지지 않는다."""

    result: dict[str, object] = {}
    try:
        for key, value in attributes.items():
            validator = _VALUE_VALIDATORS.get(key)
            if validator is None:
                continue
            try:
                if validator(value):
                    result[key] = value
            except Exception:  # noqa: BLE001 — 검증기 자체가 예상 못한 타입에 터져도 무시하고 버린다
                continue
    except Exception:  # noqa: BLE001 — attributes.items() 자체가 이상해도 빈 결과로 안전하게 종료
        return {}
    return result
