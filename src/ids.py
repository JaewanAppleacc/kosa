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
import unicodedata
import uuid
from typing import Literal

_SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def is_valid_slug(value: str) -> bool:
    """context_id/trait_id 등에 쓰는 프리픽스 없는 snake_case 규칙."""
    return bool(_SLUG_PATTERN.match(value))


def generate_question_id(context_id: str, phase: Literal["seed", "tail", "v2_probe", "routing"], index: int) -> str:
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
    """조사년도(svyYr)는 의도적으로 제외한다 — C 질문 2번 결정 사항.

    2026-08-25 Identity v2(a/offering-identity-v2) §1·§4-8 감사에서 확인: 이
    3-tuple만으로는 유일성이 보장되지 않는다 — 같은 (schl_id, department_name,
    college_name)에 일반과정·계약학과·산업체위탁처럼 서로 다른 실제 편제가
    동시에 걸리는 경우가 실제로 16 Group·32행 존재한다("SHA-256 Hash
    Collision"이 아니라 identity-key 설계 자체의 한계). 이 함수 자체는 Master
    35건이 이미 이 값을 Key로 쓰고 있어 바꾸지 않는다(§5 "기존 35건 즉시 교체
    금지") — 새 코드는 이 함수 대신 아래 `generate_offering_id()`(Repository
    유일 키)와 `generate_display_group_id()`(표시용 그룹화 전용)를 쓴다."""

    return f"dept_{_sha256_prefix(schl_id, department_name, college_name)}"


def generate_offering_id(
    schl_id: str, source_schl_mjr_id: str, *, provider: str = "academyinfo", survey_year: int | None = None,
) -> str:
    """Identity v2(§2) 원천 편제 ID — 새 Repository의 유일 키가 될 값이다.
    `schl_id`+`source_schl_mjr_id`(대학알리미 schlMjrId, 학교가 실제로
    관리하는 편제 번호)가 핵심 재료다 — 이 둘이 다르면 표시명이 같아도
    구조적으로 다른 편제로 취급한다(16 Group·32행이 바로 이 사실을
    보여준다). `provider`는 데이터 제공자 namespace(기본값
    "academyinfo") — 다른 제공자가 같은 schl_id·schlMjrId 번호 체계를 우연히
    재사용해도 충돌하지 않게 한다. `survey_year`는 기본적으로 해시에 넣지
    않는다(department_id와 같은 원칙 — 재수집 때마다 새 id를 받으면 Lineage
    보존이 끊긴다) — 특정 제공자가 연도마다 편제 번호를 재사용하는 것으로
    확인되면 그때만 명시적으로 전달해 충돌을 막는다."""

    parts = [provider, schl_id, source_schl_mjr_id]
    if survey_year is not None:
        parts.append(str(survey_year))
    return f"off_{_sha256_prefix(*parts)}"


def generate_display_group_id(schl_id: str, college_name: str, department_name: str) -> str:
    """Identity v2(§2) 표시명 그룹 ID — 검색·UI 그룹화 전용이다. 계산 재료는
    `generate_department_id()`와 완전히 같은 3-tuple이지만(우연이 아니라
    의도적 — 기존 department_id가 실제로 하던 역할이 "표시명 그룹화"였다는
    사실을 그대로 인정한다), Repository의 유일 키나 department_id 대체로
    쓰면 안 된다. **이름이 같다는 이유만으로 서로 다른 두 편제를 병합하는
    근거로 쓰지 않는다** — 일반과정·계약학과·산업체위탁은 이 그룹 안에서
    여전히 서로 다른 offering_id를 유지해야 한다."""

    return f"dgrp_{_sha256_prefix(schl_id, department_name, college_name)}"


def generate_offering_lineage_id(*verified_same_offering_keys: str) -> str:
    """Identity v2(§2) 연도 간 Stable Lineage ID. 호출자가 이미 검증한 연결
    근거(예: 여러 조사연도의 offering_id, 또는 사람이 확인한 식별 근거 키)를
    최소 2개 이상 명시적으로 전달해야만 계산된다 — `source_schl_mjr_id`가
    같다는 사실 하나만으로 자동으로 만들어지지 않는다(§2 "무조건 동일 편제라고
    단정하지 않음"). 인자 순서에 무관하게 같은 값이 나오도록 정렬 후
    해시한다."""

    if len(verified_same_offering_keys) < 2:
        raise ValueError(
            "Lineage ID는 최소 2개 이상의 검증된 연결 근거가 있어야 계산할 수 있다 — 근거 없이 단정하지 않는다"
        )
    ordered = sorted(verified_same_offering_keys)
    return f"lin_{_sha256_prefix(*ordered)}"


def generate_subject_id(curriculum_code: str, canonical_subject_name: str) -> str:
    """raw 과목명이 아니라 Alias 정규화를 마친 canonical_subject_name을 넣어야 한다."""
    return f"subj_{_sha256_prefix(curriculum_code, canonical_subject_name)}"


def generate_university_id(university_name: str) -> str:
    """Knowledge Subgraph(2026-08-28 19차)의 University Node id. `hash()`는 프로세스마다
    Salt가 달라(PYTHONHASHSEED) 같은 대학명이 실행할 때마다 다른 id를 받으므로 쓰지
    않는다 — department_id/subject_id와 같은 안정적 SHA-256 해시 방식을 그대로 따른다.
    앞뒤 공백만 정리하고(NFKC) 대학명 표기 자체는 원문 그대로 해시한다."""

    normalized = unicodedata.normalize("NFKC", university_name).strip()
    return f"univ_{_sha256_prefix(normalized)}"
