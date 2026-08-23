"""Seed Anchor Variant Human Review 상태 Schema — 2026-08-23 Trait Ontology
v2(2.5.2단계) §11, 2.5.5단계(단일 검토자 정책 전환).

`v2_direct_probe_review.py`(`QuestionReviewEntry`/`OptionReviewEntry`)와 완전히 같은
필드·계산 규칙을 쓰지만, Key 모양이 다르다 — Seed Anchor Variant는 `blueprint_id`가
아니라 `(context_id, anchor_id)`로, Option은 그 위에 `role_id`까지 더한 3중 Key로
식별한다. 정본은 `data/reviews/v2_seed_anchor_question_review_status.json`(15개)과
`v2_seed_anchor_option_review_status.json`(75개) 두 파일이다.

2.5.5단계: 이 프로젝트는 2차 검토를 쓰지 않는다 — `final_status`는 `reviewer_1_status`
만으로 계산한다(`v2_direct_probe_review.ReviewEntry`와 동일 규칙)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ReviewerStatus = Literal["APPROVE", "REVISE", "HOLD", "TBD"]
FinalReviewStatus = Literal["DRAFT", "REVIEW_REQUIRED", "APPROVED"]


class SeedAnchorReviewEntry(BaseModel):
    """공통 필드 — `v2_direct_probe_review.ReviewEntry`와 동일한 계산 규칙."""

    reviewer_1_status: ReviewerStatus = "TBD"
    reviewer_1_comment: str = ""
    reviewer_2_status: ReviewerStatus = "TBD"
    reviewer_2_comment: str = ""
    resolution_note: str = ""

    @property
    def final_status(self) -> FinalReviewStatus:
        if self.reviewer_1_status in ("REVISE", "HOLD"):
            return "REVIEW_REQUIRED"
        if self.reviewer_1_status == "APPROVE":
            return "APPROVED"
        return "DRAFT"


class SeedAnchorQuestionReviewEntry(SeedAnchorReviewEntry):
    """Seed Anchor Variant 질문(문항) 단위 검토 — Context 15개(3 Context × 5 Anchor)."""

    context_id: str
    anchor_id: str


class SeedAnchorOptionReviewEntry(SeedAnchorReviewEntry):
    """Seed Anchor Variant 선택지 단위 검토 — 75개(15 질문 × 5 Option)."""

    context_id: str
    anchor_id: str
    role_id: str
