"""ID 명명 규칙 — 작업자 A/B/C 합의 사항(2026-08-20) 구현.

- context_id / trait_id: 설계안 JSON 예시(§7-3, §9, §12)와 동일하게 프리픽스 없는 snake_case.
- question_id / option_id: 서버가 생성한다. LLM Structured Output에는 포함하지 않는다(설계안 §10).
- department_id: 조사년도를 해시에 포함하지 않는다 — 포함하면 재수집 때마다 같은 학과가 새 ID를
  받아 §18의 "신설·통합·폐과 이력 보존"이 끊긴다. 연도는 별도 필드(source_svy_year)로 관리한다.
- subject_id: 학교별 원본 표기가 아니라 정규화된 canonical 과목명으로 해시한다 — 원본 표기를 그대로
  해시하면 같은 과목이 학교마다 다른 ID를 받는다.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from typing import Literal

_SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def is_valid_slug(value: str) -> bool:
    """context_id/trait_id 등에 쓰는 프리픽스 없는 snake_case 규칙."""
    return bool(_SLUG_PATTERN.match(value))


def generate_question_id(context_id: str, phase: Literal["seed", "tail"], index: int) -> str:
    if not is_valid_slug(context_id):
        raise ValueError(f"context_id must be snake_case slug, got: {context_id!r}")
    if index < 1:
        raise ValueError("index must be 1-based")
    return f"{context_id}_{phase}_{index:02d}"


def generate_option_id(question_id: str, option_index: int) -> str:
    """option_id = question_id + 옵션 순번 (설계안 §10)."""
    if option_index < 1:
        raise ValueError("option_index must be 1-based")
    return f"{question_id}_o{option_index}"


def generate_session_id() -> str:
    return f"sess_{uuid.uuid4().hex}"


def generate_trace_id() -> str:
    """§24 LangSmith Observability: "PostgreSQL의 session_id와 LangSmith의 trace_id를
    매핑하되, LangSmith에는 익명화된 식별자만 전달한다" — session_id와 별개의 무작위
    식별자를 만들어, LangSmith 쪽에는 이 값만 보내고 session_id 원문은 보내지 않는다.

    2026-08-22 리뷰 반영: 예전엔 "trace_" 접두사를 붙인 문자열이었는데, 설치된 LangSmith
    SDK의 Run.trace_id는 UUID 타입이다 — 접두사가 붙으면 `uuid.UUID(trace_id)` 파싱이
    실패해 실제 LangSmith 서버에서 거부될 수 있었다(fail-open이라 서비스는 멀쩡해 보이지만
    Trace는 하나도 안 쌓이는 조용한 실패). 순수 UUID 문자열로 바꾼다."""
    return str(uuid.uuid4())


def generate_evidence_id() -> str:
    return f"ev_{uuid.uuid4().hex}"


def _sha256_prefix(*parts: str, length: int = 24) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:length]


def generate_department_id(schl_id: str, department_name: str, college_name: str) -> str:
    """조사년도(svyYr)는 의도적으로 제외한다 — C 질문 2번 결정 사항."""
    return f"dept_{_sha256_prefix(schl_id, department_name, college_name)}"


def generate_subject_id(curriculum_code: str, canonical_subject_name: str) -> str:
    """raw 과목명이 아니라 Alias 정규화를 마친 canonical_subject_name을 넣어야 한다."""
    return f"subj_{_sha256_prefix(curriculum_code, canonical_subject_name)}"
