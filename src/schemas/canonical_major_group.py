"""Canonical Major Group Draft Schema — A-2 지시서(integration/academyinfo-pipeline,
2026-08-24) §1/§4.

`data/canonical_major_groups.draft.jsonl`(worker-c 소유, 대학알리미 표준분류 소계열
158개를 후보 전공군으로 묶은 분류 Ontology 초안)을 A가 읽기 위한 계약이다.

**이 42개는 "검증된 추천 전공"이 아니라 "분류 후보 Ontology"다**(A 결정사항 §1
"대표 전공군"). `review_status`가 여전히 "draft"인 동안에는 어떤 사용자 추천에도
쓰이지 않는다 — 이 Schema 자체는 그 강제를 하지 않는다(Pydantic은 "draft 값이 뭔지"만
검증한다); 실제 강제는 이 파일을 소비할 미래의 Matching 코드(아직 없음)가 한다."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator

CanonicalMajorGroupReviewStatus = Literal["draft", "approved"]


class CanonicalMajorGroupDraft(BaseModel):
    canonical_major_id: str
    label: str
    description: str
    # 대학알리미 표준분류 소계열(getCodeBySmallSeries) 공식 코드만 담는다 — N.C.E(999)
    # 는 "분류 없음" 센티널이라 여기 들어가면 안 된다(§4 "N.C.E 99/999를 일반 전공군으로
    # 취급하지 않음", src.data_sources.academyinfo_codes.UNCLASSIFIED_SMALL_SERIES 참고).
    included_official_small_series_codes: list[str]
    middle_series_hint: list[str]
    boundary_cases: list[str] = []
    excluded_series_codes: list[str] = []
    official_source_urls: list[str]
    classification_basis: str
    review_status: CanonicalMajorGroupReviewStatus

    @field_validator("canonical_major_id", "label", "description", "classification_basis")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("빈 값은 허용하지 않는다")
        return value

    @field_validator("official_source_urls")
    @classmethod
    def _official_source_urls_not_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("official_source_urls는 최소 1개 이상이어야 한다(출처 없는 분류 금지)")
        return value

    @field_validator("included_official_small_series_codes")
    @classmethod
    def _included_codes_not_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("included_official_small_series_codes는 최소 1개 이상이어야 한다")
        return value
