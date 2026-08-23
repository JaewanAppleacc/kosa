"""Backup Question Applicability 정본 — 2026-08-23 Trait Ontology v2(2.5.3단계) §3/§9.

6개 Backup 전부 2.5.3단계 §5-7에서 특정 장르·제작·조별 활동에 종속된 표현을 제거하고
중립 문구로 재작성했다 — 그래서 전부 `allowed_anchor_ids=None`(해당 Context의 모든
Anchor에 사용 가능)이고 `excluded_anchor_ids`도 비어 있다. game_backup_01의
`role_split`(collaboration_preference) Option만 예외로, story_exploration처럼
혼자 플레이하는 상황을 우선하는 Anchor에서 다소 부자연스러울 수 있다는 점을
`applicability_reason_draft`에 사람 재검토 항목으로 남겼다(문자열 자체는 금지어를
포함하지 않아 자동 거부 대상은 아니다 — §5 "지나치게 부적절한지 검수 대상으로
남기세요")."""

from __future__ import annotations

from src.data.contexts.context_anchor_presentations import CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY
from src.data.questions.vertical_slice_backup_questions import VERTICAL_SLICE_BACKUP_QUESTIONS
from src.schemas.backup_applicability import BackupApplicabilityError, BackupQuestionApplicability

BACKUP_APPLICABILITY: list[BackupQuestionApplicability] = [
    BackupQuestionApplicability(
        question_id="game_backup_01", context_id="game",
        applicability_reason_draft=(
            "2.5.3단계 재작성으로 '팀원' 전제를 제거해 5개 Anchor 모두에 중립적으로 쓸 수 있다. "
            "다만 role_split(다른 사람과 정보·역할을 나눠 함께 파악) Option은 story_exploration처럼 "
            "혼자 플레이하는 상황을 우선하는 Anchor에서 다소 자연스럽지 않을 수 있어 사람 재검토 항목으로 남긴다."
        ),
    ),
    BackupQuestionApplicability(
        question_id="game_backup_02", context_id="game",
        applicability_reason_draft="screen_review를 직접 표현 행동으로 재작성해 5개 Anchor 모두 중립적으로 쓸 수 있다.",
    ),
    BackupQuestionApplicability(
        question_id="media_backup_01", context_id="media",
        applicability_reason_draft="comment_reading을 감상→해석 행동으로 다듬어 5개 Anchor 모두 중립적으로 쓸 수 있다.",
    ),
    BackupQuestionApplicability(
        question_id="media_backup_02", context_id="media",
        applicability_reason_draft=(
            "제작·편집 전제를 완전히 제거하고 감상 이후 탐구 상황으로 전면 재작성해 "
            "5개 Anchor(특히 stage_performance) 모두 중립적으로 쓸 수 있다."
        ),
    ),
    BackupQuestionApplicability(
        question_id="school_life_backup_01", context_id="school_life",
        applicability_reason_draft="조별 과제 전제를 제거하고 일반적인 의견 차이 상황으로 재작성해 5개 Anchor 모두 중립적으로 쓸 수 있다.",
    ),
    BackupQuestionApplicability(
        question_id="school_life_backup_02", context_id="school_life",
        applicability_reason_draft="anticipate_reaction 문구를 구체화했다 — 5개 Anchor 모두 중립적으로 쓸 수 있다.",
    ),
]

BACKUP_APPLICABILITY_BY_QUESTION_ID: dict[str, BackupQuestionApplicability] = {
    a.question_id: a for a in BACKUP_APPLICABILITY
}


def _validate() -> None:
    all_question_ids = {q.question_id for backups in VERTICAL_SLICE_BACKUP_QUESTIONS.values() for q in backups}
    ids = [a.question_id for a in BACKUP_APPLICABILITY]
    if len(ids) != len(set(ids)):
        raise BackupApplicabilityError(f"question_id 중복이 있다: {ids}")
    if set(ids) != all_question_ids:
        missing = all_question_ids - set(ids)
        extra = set(ids) - all_question_ids
        raise BackupApplicabilityError(
            f"Backup Applicability 목록이 실제 Backup Question 목록과 다르다"
            f"(빠짐: {sorted(missing)}, 불필요: {sorted(extra)})"
        )

    question_id_to_context = {
        q.question_id: context_id
        for context_id, backups in VERTICAL_SLICE_BACKUP_QUESTIONS.items()
        for q in backups
    }
    for applicability in BACKUP_APPLICABILITY:
        expected_context = question_id_to_context[applicability.question_id]
        if applicability.context_id != expected_context:
            raise BackupApplicabilityError(
                f"{applicability.question_id}: context_id가 실제 Backup Question과 다르다"
                f"(정본: {expected_context!r}, 여기: {applicability.context_id!r})"
            )

        registered_anchor_ids = {
            key[1] for key in CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY if key[0] == applicability.context_id
        }
        referenced_anchor_ids = set(applicability.excluded_anchor_ids)
        if applicability.allowed_anchor_ids is not None:
            referenced_anchor_ids |= applicability.allowed_anchor_ids
        unknown = referenced_anchor_ids - registered_anchor_ids
        if unknown:
            raise BackupApplicabilityError(
                f"{applicability.question_id}: 등록되지 않은 Anchor ID를 참조한다: {sorted(unknown)}"
            )


_validate()
