"""Service Canonical Major v2 Schema — 2026-08-25 지시서(a/service-major-catalog-v2)
§1/§2/§3.

`data/canonical_major_groups.draft.jsonl`(42개 분류 Ontology Group, worker-c 소유)
중 추천 제외 예체능 4개(fine_arts_design/music/performing_media_arts/sports_dance)를
뺀 38개를 실제 서비스 추천 후보 Major로 확정한 결과물 Schema다.

이 Schema는 두 파일을 정의한다.

    1. `data/master/service_canonical_majors_v2.jsonl` — 38개 Catalog 행 하나하나
       (`ServiceCanonicalMajorV2`).
    2. `data/master/canonical_major_group_to_service_major_v2.jsonl` — 42개 Group
       전부에 대한 Migration/Bridge 기록(`CanonicalMajorGroupServiceMajorBridgeV2`) —
       ACTIVE 38 + EXCLUDED_RECOMMENDATION 4 = 42, Group 누락 0.

이번 작업은 Catalog 확정까지만 다룬다 — Trait Weight·학과·과목 Mapping은 별도 라운드
몫이다(지시서 §3 "이번 작업에서는 만들지 않는다")."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

RecommendationStatus = Literal["ACTIVE", "EXCLUDED_RECOMMENDATION"]

# 42개 Group 중 추천 제외 예체능 4개 — 지시서 §(목표)가 명시한 유일한 정본 목록이다.
# 이 4개는 분류 Ontology·Context에서는 그대로 유지하되(그 자체를 지우지 않는다),
# 서비스 추천 Major로는 절대 승격되지 않는다.
EXCLUDED_RECOMMENDATION_GROUP_IDS = frozenset(
    {"fine_arts_design", "music", "performing_media_arts", "sports_dance"}
)

# src/engines/canonical_mapper.py::CanonicalMajorEntry(A3 지시서 2026-08-24 §4/§5)와
# 같은 금지 표현·길이 규칙을 그대로 재사용한다 — "학생 화면에 노출되는 전공 설명"이라는
# 성격이 동일하므로 새 규칙을 따로 만들지 않는다(단일 정본 원칙). 지시서 §3 "적합 보장·
# 취업 보장·점수 표현 금지"가 요구하는 검사와 정확히 같다.
_FORBIDDEN_DESCRIPTION_PHRASES = (
    "취업이 잘", "취업률", "합격이", "합격률", "성공적인", "당신에게", "당신의 적성",
    "가장 적합", "잘 맞습니다", "잘 맞는", "적성에 맞", "보장",
)
_MAX_DESCRIPTION_LENGTH = 120


def _validate_description_text(value: str, *, field_name: str = "description") -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name}은 빈 문자열이나 공백만 있는 값을 허용하지 않는다")
    if len(stripped) > _MAX_DESCRIPTION_LENGTH:
        raise ValueError(f"{field_name}이 너무 길다({len(stripped)}자, 최대 {_MAX_DESCRIPTION_LENGTH}자): {stripped!r}")
    if "%" in stripped or re.search(r"\d+\s*점", stripped):
        raise ValueError(f"{field_name}에 내부 숫자 점수·백분율 표현을 넣을 수 없다: {stripped!r}")
    lowered = stripped.replace(" ", "")
    for phrase in _FORBIDDEN_DESCRIPTION_PHRASES:
        if phrase.replace(" ", "") in lowered:
            raise ValueError(f"{field_name}에 금지 표현이 포함됐다({phrase!r}): {stripped!r}")
    return stripped


class ServiceCanonicalMajorV2(BaseModel):
    """`data/master/service_canonical_majors_v2.jsonl`의 한 행 — 38개 서비스 추천
    Major 중 하나. `major_id`는 기존 10개 Canonical Major와 겹치는 경우 가능한 한
    그 값을 그대로 쓴다(§1 "기존 10개 ID·설명은 가능한 한 보존") — 새 값을 만들 때만
    `canonical_major_group_id`와 같은 문자열을 쓴다."""

    major_id: str
    label: str
    description: str
    aliases: list[str] = []
    keywords: list[str] = []
    # 이 Major가 유래한 42개 Group 중 하나 — Loader가 실제 Group 목록과 대조해
    # Fail-Fast로 확인한다(§3 "공식 Group 존재 확인").
    canonical_major_group_id: str
    recommendation_status: RecommendationStatus = "ACTIVE"
    official_source_urls: list[str]
    catalog_version: str

    @field_validator("major_id", "label", "canonical_major_group_id", "catalog_version")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("빈 값은 허용하지 않는다")
        return value

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str) -> str:
        return _validate_description_text(value)

    @field_validator("aliases")
    @classmethod
    def _aliases_not_blank_and_unique_within_entry(cls, value: list[str]) -> list[str]:
        stripped = [a.strip() for a in value]
        if any(not a for a in stripped):
            raise ValueError("aliases에 빈 문자열을 넣을 수 없다")
        if len(stripped) != len(set(stripped)):
            raise ValueError(f"같은 Major 안에서 alias가 중복됐다: {stripped}")
        return stripped

    @field_validator("keywords")
    @classmethod
    def _keywords_not_blank(cls, value: list[str]) -> list[str]:
        stripped = [k.strip() for k in value]
        if any(not k for k in stripped):
            raise ValueError("keywords에 빈 문자열을 넣을 수 없다")
        return stripped

    @field_validator("official_source_urls")
    @classmethod
    def _official_source_urls_not_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("official_source_urls는 최소 1개 이상이어야 한다(출처 없는 Major 금지)")
        return value

    @model_validator(mode="after")
    def _excluded_group_cannot_be_active(self) -> "ServiceCanonicalMajorV2":
        # §3 "예체능 4개 ACTIVE 금지" — Schema 수준에서도 이중으로 막는다(Loader의
        # 목록 대조와 같은 근거를 여기서도 강제해, 이 Model을 다른 경로로 직접
        # 생성해도 조용히 통과하지 않게 한다).
        if self.canonical_major_group_id in EXCLUDED_RECOMMENDATION_GROUP_IDS and self.recommendation_status == "ACTIVE":
            raise ValueError(
                f"{self.canonical_major_group_id}는 추천 제외 예체능 Group이라 ACTIVE 서비스 Major가 될 수 없다"
            )
        return self


class CanonicalMajorGroupServiceMajorBridgeV2(BaseModel):
    """`data/master/canonical_major_group_to_service_major_v2.jsonl`의 한 행 — 42개
    Group 전부가 정확히 하나씩 가진다(§2 "Group 누락 0"). ACTIVE는 반드시
    `service_major_id`가 있어야 하고, EXCLUDED_RECOMMENDATION은 반드시 없어야 한다."""

    canonical_major_group_id: str
    service_major_id: str | None
    recommendation_status: RecommendationStatus
    decision_reason: str

    @field_validator("canonical_major_group_id", "decision_reason")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("빈 값은 허용하지 않는다")
        return value

    @field_validator("service_major_id")
    @classmethod
    def _service_major_id_not_blank_if_present(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("service_major_id는 None이거나 비어 있지 않은 문자열이어야 한다(빈 문자열 금지)")
        return value

    @model_validator(mode="after")
    def _status_and_service_major_id_must_agree(self) -> "CanonicalMajorGroupServiceMajorBridgeV2":
        if self.recommendation_status == "ACTIVE" and self.service_major_id is None:
            raise ValueError(f"{self.canonical_major_group_id}: ACTIVE인데 service_major_id가 없다")
        if self.recommendation_status == "EXCLUDED_RECOMMENDATION" and self.service_major_id is not None:
            raise ValueError(
                f"{self.canonical_major_group_id}: EXCLUDED_RECOMMENDATION인데 service_major_id가 채워져 있다"
            )
        return self
