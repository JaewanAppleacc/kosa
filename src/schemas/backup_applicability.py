"""Backup Question Applicability Schema — 2026-08-23 Trait Ontology v2(2.5.3단계) §3.

문자열 금지 검사(Quality Gate의 `forbidden_anchor_assumption_phrases`)만으로는 모든
적합성을 판단할 수 없다 — 2.5.3단계 §1 재현에서 media_backup_02의 "편집 도구" 같은
표현은 stage_performance Anchor의 forbidden_assumptions 문자열("영상 편집")과 정확히
일치하지 않아 그냥 통과해버렸다. `BackupQuestionApplicability`는 그런 경우를 위한
명시적 허용/제외 목록이다 — 다만 2.5.3단계에서는 6개 Backup을 전부 중립 문구로
재작성했기 때문에 실제로 `excluded_anchor_ids`를 쓴 항목은 없다(전부 all-permissive).
메커니즘 자체는 앞으로 배선될 수 있으므로 남겨둔다."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BackupApplicabilityError(ValueError):
    """정본 파일 자체가 구조적으로 잘못됐을 때(미등록 question_id·Context 불일치,
    미등록 Anchor ID, 중복)."""


class BackupQuestionApplicability(BaseModel):
    """`allowed_anchor_ids=None`이면 해당 Context의 모든 Anchor에 쓸 수 있는 중립
    Backup이라는 뜻이다(2.5.3단계 기준 6개 전부 이 경우다). 특정 Anchor에서만
    자연스럽다면 `allowed_anchor_ids`에 명시적으로 그 집합만 넣는다.
    `excluded_anchor_ids`는 그 반대 — "이 Anchor에서는 절대 쓰면 안 된다"는 목록이다.
    `applicability_reason_draft`는 검수용 초안일 뿐 검증 완료를 뜻하지 않는다."""

    question_id: str
    context_id: str
    allowed_anchor_ids: set[str] | None = None
    excluded_anchor_ids: set[str] = Field(default_factory=set)
    applicability_reason_draft: str

    def allows(self, anchor_id: str | None) -> bool:
        if anchor_id is None:
            return True
        if anchor_id in self.excluded_anchor_ids:
            return False
        if self.allowed_anchor_ids is not None and anchor_id not in self.allowed_anchor_ids:
            return False
        return True
