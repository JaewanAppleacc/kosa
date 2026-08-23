"""Backup Question 2인 Human Review 상태 로더/Validator — 2026-08-23 Trait Ontology
v2(2.5.3단계) §10.

`v2_direct_probe_review_store.py`/`seed_anchor_review_store.py`와 같은 패턴을 Backup
Question 6개(30개 Option)에 대해 반복한다. Key는 v2 Direct Probe와 같은 모양
(question_id/blueprint_id 단위 + role_id)이라 스키마 자체(`QuestionReviewEntry`/
`OptionReviewEntry`)도 그대로 재사용한다 — Backup은 `blueprint_id` 자리에
`question_id`를 그대로 쓴다(main.py도 이미 "Backup Question은 그 자체가 하나의 고정
Blueprint" 취급을 하고 있다 — 1.5단계 §2/§4 규칙과 동일)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from src.data.questions.vertical_slice_backup_questions import VERTICAL_SLICE_BACKUP_QUESTIONS
from src.schemas.v2_direct_probe_review import OptionReviewEntry, QuestionReviewEntry

_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "reviews"
BACKUP_QUESTION_REVIEW_PATH = _DATA_DIR / "v2_backup_question_review_status.json"
BACKUP_OPTION_REVIEW_PATH = _DATA_DIR / "v2_backup_option_review_status.json"

_QUESTION_ADAPTER: TypeAdapter[list[QuestionReviewEntry]] = TypeAdapter(list[QuestionReviewEntry])
_OPTION_ADAPTER: TypeAdapter[list[OptionReviewEntry]] = TypeAdapter(list[OptionReviewEntry])


class BackupReviewStatusValidationError(ValueError):
    """검토 상태 파일의 Key 집합이 실제 Backup Question 목록과 다를 때."""


def load_backup_question_review_entries(path: Path = BACKUP_QUESTION_REVIEW_PATH) -> list[QuestionReviewEntry]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return _QUESTION_ADAPTER.validate_python(raw)


def load_backup_option_review_entries(path: Path = BACKUP_OPTION_REVIEW_PATH) -> list[OptionReviewEntry]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return _OPTION_ADAPTER.validate_python(raw)


def validate_backup_review_status_files(
    *,
    question_path: Path = BACKUP_QUESTION_REVIEW_PATH,
    option_path: Path = BACKUP_OPTION_REVIEW_PATH,
) -> None:
    question_entries = load_backup_question_review_entries(question_path)
    option_entries = load_backup_option_review_entries(option_path)

    expected_question_ids = {q.question_id for backups in VERTICAL_SLICE_BACKUP_QUESTIONS.values() for q in backups}
    question_ids = [e.blueprint_id for e in question_entries]
    if len(question_ids) != len(set(question_ids)):
        raise BackupReviewStatusValidationError(f"{question_path}: question_id가 중복됐다: {question_ids}")
    if set(question_ids) != expected_question_ids:
        missing = expected_question_ids - set(question_ids)
        extra = set(question_ids) - expected_question_ids
        raise BackupReviewStatusValidationError(
            f"{question_path}: 실제 Backup Question 목록과 일치하지 않는다"
            f"(빠짐: {sorted(missing)}, 불필요: {sorted(extra)})"
        )

    expected_option_keys = {
        (q.question_id, o.role_id) for backups in VERTICAL_SLICE_BACKUP_QUESTIONS.values()
        for q in backups for o in q.options
    }
    option_keys = [(e.blueprint_id, e.role_id) for e in option_entries]
    if len(option_keys) != len(set(option_keys)):
        raise BackupReviewStatusValidationError(f"{option_path}: (question_id, role_id)가 중복됐다: {option_keys}")
    if set(option_keys) != expected_option_keys:
        missing = expected_option_keys - set(option_keys)
        extra = set(option_keys) - expected_option_keys
        raise BackupReviewStatusValidationError(
            f"{option_path}: 실제 Backup Option 목록과 일치하지 않는다"
            f"(빠짐: {sorted(missing)}, 불필요: {sorted(extra)})"
        )
