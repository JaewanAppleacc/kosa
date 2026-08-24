"""대학알리미 중복 과정의 사람 승인 결정 Schema.

worker-c가 생성하는 ``duplicate_decision_draft.jsonl``은 매번 다시 만들 수 있는
검토 패킷이므로 항상 TBD/PENDING으로 남긴다. 실제 사람 결정은 이 Schema를 사용하는
별도 정본에 저장해, 패킷 재생성으로 승인 기록이 사라지지 않게 한다.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

RelationDecision = Literal["DISTINCT_DEPARTMENTS_KEEP_SEPARATE"]
RecommendationScope = Literal["IN_RECOMMENDATION_SCOPE", "OUT_OF_RECOMMENDATION_SCOPE"]
MajorCharacter = Literal["일반과정", "계약학과"]


class AcademyInfoReviewedRecordScope(BaseModel):
    source_record_id: str
    schl_mjr_id: str
    major_character_name: MajorCharacter
    recommendation_scope: RecommendationScope
    exclusion_reason: Literal["CONTRACT_DEPARTMENT"] | None = None

    @field_validator("source_record_id", "schl_mjr_id")
    @classmethod
    def _identifier_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("검수 레코드 식별자는 빈 값일 수 없다")
        return value

    @model_validator(mode="after")
    def _scope_matches_major_character(self) -> "AcademyInfoReviewedRecordScope":
        if self.major_character_name == "일반과정":
            if self.recommendation_scope != "IN_RECOMMENDATION_SCOPE" or self.exclusion_reason is not None:
                raise ValueError("일반과정은 추천 범위에 유지하고 제외 사유를 두지 않아야 한다")
        else:
            if self.recommendation_scope != "OUT_OF_RECOMMENDATION_SCOPE":
                raise ValueError("계약학과는 추천 범위 밖이어야 한다")
            if self.exclusion_reason != "CONTRACT_DEPARTMENT":
                raise ValueError("계약학과 제외 사유는 CONTRACT_DEPARTMENT여야 한다")
        return self


class AcademyInfoDuplicateScopeDecision(BaseModel):
    candidate_id: str
    department_id: str
    approved_decision: RelationDecision
    reviewer_1_status: Literal["APPROVE"]
    reviewer_1_comment: str
    resolution_status: Literal["CONFIRMED"]
    reviewer_id: Literal["reviewer_1"] = "reviewer_1"
    reviewed_at: date
    records: list[AcademyInfoReviewedRecordScope] = Field(min_length=2, max_length=2)

    @field_validator("candidate_id", "department_id", "reviewer_1_comment")
    @classmethod
    def _required_text_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("승인 결정의 필수 문자열은 빈 값일 수 없다")
        return value

    @model_validator(mode="after")
    def _one_general_and_one_contract_record(self) -> "AcademyInfoDuplicateScopeDecision":
        if len({record.source_record_id for record in self.records}) != 2:
            raise ValueError("승인 결정 안의 source_record_id는 서로 달라야 한다")
        if len({record.schl_mjr_id for record in self.records}) != 2:
            raise ValueError("별도 과정은 서로 다른 schl_mjr_id를 가져야 한다")
        if {record.major_character_name for record in self.records} != {"일반과정", "계약학과"}:
            raise ValueError("승인 결정은 일반과정 1건과 계약학과 1건으로 구성돼야 한다")
        return self
