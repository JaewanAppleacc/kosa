"""Anchor Backup Question 2인 Human Review 상태 로더/Validator — 2026-08-23 Trait
Ontology v2(2.5.4단계) §7/§10.

기존 6개 Backup의 검토 상태 파일(`v2_backup_*_review_status.json`, REVISE 상태·사용자
메모 포함)과 완전히 별개의 새 파일이다 — 사용자가 이미 검수한 결과를 절대 건드리지
않기 위해 처음부터 다른 파일로 분리했다. Schema는 기존과 같은
(`QuestionReviewEntry`/`OptionReviewEntry`, `blueprint_id` 자리에 question_id)를
재사용한다."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from src.data.questions.anchor_backup_questions import ANCHOR_BACKUP_QUESTIONS
from src.schemas.v2_direct_probe_review import OptionReviewEntry, QuestionReviewEntry

_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "reviews"
ANCHOR_BACKUP_QUESTION_REVIEW_PATH = _DATA_DIR / "v2_anchor_backup_question_review_status.json"
ANCHOR_BACKUP_OPTION_REVIEW_PATH = _DATA_DIR / "v2_anchor_backup_option_review_status.json"

_QUESTION_ADAPTER: TypeAdapter[list[QuestionReviewEntry]] = TypeAdapter(list[QuestionReviewEntry])
_OPTION_ADAPTER: TypeAdapter[list[OptionReviewEntry]] = TypeAdapter(list[OptionReviewEntry])


class AnchorBackupReviewStatusValidationError(ValueError):
    """검토 상태 파일의 Key 집합이 실제 Anchor Backup Question 목록과 다를 때."""


def load_anchor_backup_question_review_entries(
    path: Path = ANCHOR_BACKUP_QUESTION_REVIEW_PATH,
) -> list[QuestionReviewEntry]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return _QUESTION_ADAPTER.validate_python(raw)


def load_anchor_backup_option_review_entries(
    path: Path = ANCHOR_BACKUP_OPTION_REVIEW_PATH,
) -> list[OptionReviewEntry]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return _OPTION_ADAPTER.validate_python(raw)


def validate_anchor_backup_review_status_files(
    *,
    question_path: Path = ANCHOR_BACKUP_QUESTION_REVIEW_PATH,
    option_path: Path = ANCHOR_BACKUP_OPTION_REVIEW_PATH,
) -> None:
    question_entries = load_anchor_backup_question_review_entries(question_path)
    option_entries = load_anchor_backup_option_review_entries(option_path)

    expected_question_ids = {q.question_id for q in ANCHOR_BACKUP_QUESTIONS}
    question_ids = [e.blueprint_id for e in question_entries]
    if len(question_ids) != len(set(question_ids)):
        raise AnchorBackupReviewStatusValidationError(f"{question_path}: question_id가 중복됐다: {question_ids}")
    if set(question_ids) != expected_question_ids:
        missing = expected_question_ids - set(question_ids)
        extra = set(question_ids) - expected_question_ids
        raise AnchorBackupReviewStatusValidationError(
            f"{question_path}: 실제 Anchor Backup Question 목록과 일치하지 않는다"
            f"(빠짐: {sorted(missing)}, 불필요: {sorted(extra)})"
        )

    expected_option_keys = {(q.question_id, o.role_id) for q in ANCHOR_BACKUP_QUESTIONS for o in q.options}
    option_keys = [(e.blueprint_id, e.role_id) for e in option_entries]
    if len(option_keys) != len(set(option_keys)):
        raise AnchorBackupReviewStatusValidationError(
            f"{option_path}: (question_id, role_id)가 중복됐다: {option_keys}"
        )
    if set(option_keys) != expected_option_keys:
        missing = expected_option_keys - set(option_keys)
        extra = set(option_keys) - expected_option_keys
        raise AnchorBackupReviewStatusValidationError(
            f"{option_path}: 실제 Anchor Backup Option 목록과 일치하지 않는다"
            f"(빠짐: {sorted(missing)}, 불필요: {sorted(extra)})"
        )
