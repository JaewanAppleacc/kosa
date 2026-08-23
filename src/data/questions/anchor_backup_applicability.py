"""Anchor Backup Question Applicability 정본 — 2026-08-23 Trait Ontology v2(2.5.4단계)
§3.

기존(2.5.3단계) 6개 Backup의 Applicability는 전부 `allowed_anchor_ids=None`
(모든 Anchor 허용, all-permissive)이었다 — 이번 단계는 그 반대다. 15개 Anchor Backup은
각자 정확히 그 Anchor 하나에만 허용된다(`allowed_anchor_ids={그 anchor_id}`) — 다른
Anchor에서는 절대 후보로 뽑히면 안 된다는 §3 요구를 구조적으로 강제한다."""

from __future__ import annotations

from src.data.contexts.context_anchor_presentations import CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY
from src.data.questions.anchor_backup_questions import ANCHOR_BACKUP_QUESTIONS_BY_KEY
from src.schemas.backup_applicability import BackupApplicabilityError, BackupQuestionApplicability

ANCHOR_BACKUP_APPLICABILITY: list[BackupQuestionApplicability] = [
    BackupQuestionApplicability(
        question_id=question.question_id, context_id=context_id,
        allowed_anchor_ids={anchor_id},
        applicability_reason_draft=(
            f"{anchor_id} Anchor의 실제 상황만 다루도록 새로 작성했다 — "
            f"다른 Anchor에서는 상황이 안 맞아 후보로 제시하지 않는다."
        ),
    )
    for (context_id, anchor_id), question in ANCHOR_BACKUP_QUESTIONS_BY_KEY.items()
]

ANCHOR_BACKUP_APPLICABILITY_BY_QUESTION_ID: dict[str, BackupQuestionApplicability] = {
    a.question_id: a for a in ANCHOR_BACKUP_APPLICABILITY
}


def _validate() -> None:
    expected_question_ids = {q.question_id for q in ANCHOR_BACKUP_QUESTIONS_BY_KEY.values()}
    ids = [a.question_id for a in ANCHOR_BACKUP_APPLICABILITY]
    if len(ids) != len(set(ids)):
        raise BackupApplicabilityError(f"question_id 중복이 있다: {ids}")
    if set(ids) != expected_question_ids:
        missing = expected_question_ids - set(ids)
        extra = set(ids) - expected_question_ids
        raise BackupApplicabilityError(
            f"Anchor Backup Applicability 목록이 실제 질문 목록과 다르다"
            f"(빠짐: {sorted(missing)}, 불필요: {sorted(extra)})"
        )

    for applicability in ANCHOR_BACKUP_APPLICABILITY:
        if applicability.allowed_anchor_ids is None or len(applicability.allowed_anchor_ids) != 1:
            raise BackupApplicabilityError(
                f"{applicability.question_id}: Anchor Backup은 all-permissive(None)가 아니라 "
                f"정확히 하나의 allowed_anchor_ids만 가져야 한다(§3)"
            )
        (anchor_id,) = applicability.allowed_anchor_ids
        if (applicability.context_id, anchor_id) not in CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY:
            raise BackupApplicabilityError(
                f"{applicability.question_id}: ({applicability.context_id}, {anchor_id})가 "
                "Anchor Presentation 레지스트리에 없다"
            )


_validate()
