"""C의 초안(`data/drafts/`) 검토 단계 Schema.

`MappingReview.agreement_status`(§15: AGREED/REVIEW_REQUIRED/REJECTED)와 이름이 겹치지
않게 일부러 다른 어휘를 썼다 — MappingReview는 Major-Trait Mapping 하나를 2인이 정식으로
교차검토하는 절차 전용이고, 여기는 `data/drafts/`에 쌓이는 모든 종류의 초안(Context·Trait
검토안, Question Blueprint, Major/Subject-Trait Mapping 초안)이 "확정 데이터로 승격되기
전 어느 단계에 있는지"를 보는 더 가벼운 개념이다. 두 Schema를 같은 이름으로 두면 나중에
"이게 그 REVIEW_REQUIRED인가?" 하고 헷갈리게 된다.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel


class DraftReviewStage(str, Enum):
    DRAFT = "DRAFT"  # 작성 중 또는 막 작성 완료
    STAGED = "STAGED"  # A의 검토를 기다리는 상태
    PUBLISHED = "PUBLISHED"  # A가 승인해 확정 데이터(src/data/)로 승격됨


DraftType = Literal[
    "context_trait_review",
    "question_blueprint",
    "major_trait_mapping",
    "subject_trait_mapping",
]


class DraftEntry(BaseModel):
    """`data/drafts/<유형>/`에 있는 파일 하나의 메타데이터. data/drafts/README.md가 요구하는
    source_url·as_of_date·author_id·review_status를 그대로 타입으로 만든 것이다."""

    draft_id: str
    draft_type: DraftType
    author_id: str
    review_stage: DraftReviewStage
    source_url: str | None = None
    as_of_date: date | None = None
    notes: str = ""
