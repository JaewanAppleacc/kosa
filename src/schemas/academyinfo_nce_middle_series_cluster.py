"""대학알리미 N.C.E 재검토 가능(REEXAMINABLE_BY_OFFICIAL_EVIDENCE) 중계열 클러스터
원본 Schema — 2026-08-24 지시서(a/academyinfo-review-ui-p1-nce).

`data/academyinfo_work/2025/packets/nce_reexaminable_middle_series_clusters.jsonl`
(worker-c 산출, 24개 클러스터·584개 학과, Read-Only Draft)을 읽어 검증한다. 이
파일 자체를 절대 수정하지 않는다 — 사람 검수 결과는 완전히 별도 파일
(`data/reviews/academyinfo_nce_middle_series_review_status.jsonl`)에만 저장한다.

원본 행에도 `reviewer_1_status`/`reviewer_1_comment`(worker-c가 만든 자리
표시자, 전부 TBD 고정값)가 있지만 이 Schema는 그 필드를 모델링하지 않는다 —
실제 사람 검수 결과의 유일한 정본은 별도 Store다."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# 원본 산출물 실측 분포: PROPOSED_GROUP_CANDIDATE 15개 클러스터(208건) /
# DEPARTMENT_LEVEL_REVIEW_REQUIRED 9개 클러스터(376건).
GroupLinkageStatus = Literal["PROPOSED_GROUP_CANDIDATE", "DEPARTMENT_LEVEL_REVIEW_REQUIRED"]


class NceCandidateMajorGroup(BaseModel):
    """이 중계열이 걸릴 수 있는 42개 Canonical Major Group 후보 하나. 원본 필드명이
    `canonical_major_id`이지만(worker-c 산출물 그대로 보존) 실제로는 42개 Group
    ID다 — `canonical_major_group_bridge.py`가 이미 정리한 "Group ID와 서비스
    Major ID는 우연히 문자열이 겹치는 별개 ID 공간" 문제와 같은 함정이라, 이 필드를
    그대로 서비스 Major ID로 오인하면 안 된다."""

    canonical_major_id: str  # 실제로는 canonical_major_group_id.
    label: str


class NceMemberDepartment(BaseModel):
    """이 중계열 클러스터에 속한 학과 하나."""

    candidate_id: str
    university_name: str
    college_name: str
    department_name: str
    department_id: str
    source_record_id: str


class AcademyInfoNceMiddleSeriesClusterEntry(BaseModel):
    """중계열 클러스터 하나. `official_middle_series_code`가 24개 클러스터 전체에서
    유일한 Key다(cluster_id도 유일하지만, 지시서가 명시한 PATCH 경로 변수는
    middle_series_code다)."""

    cluster_id: str
    official_middle_series_code: str
    official_middle_series_name: str
    official_middle_series_code_source: str
    group_linkage_status: GroupLinkageStatus
    candidate_canonical_major_groups: list[NceCandidateMajorGroup] = Field(default_factory=list)
    candidate_canonical_major_group_basis: str
    unlinkable_or_too_broad_reason: str = ""
    additional_official_evidence_needed: list[str] = Field(default_factory=list)
    forbidden: list[str] = Field(default_factory=list)
    members: list[NceMemberDepartment] = Field(default_factory=list)
    row_count: int

    @field_validator("official_middle_series_code", "cluster_id")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("빈 ID는 허용하지 않는다")
        return value
