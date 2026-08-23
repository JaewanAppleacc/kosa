"""Seed Anchor Variant 2인 Human Review 상태 로더/Validator — 2026-08-23 Trait Ontology
v2(2.5.2단계) §11.

`v2_direct_probe_review_store.py`/`context_routing_review_store.py`와 같은 패턴을
Seed Anchor Variant 15개(75개 Option)에 대해 반복한다."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from src.data.questions.seed_anchor_variants import SEED_ANCHOR_VARIANTS
from src.schemas.seed_anchor_review import SeedAnchorOptionReviewEntry, SeedAnchorQuestionReviewEntry

_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "reviews"
SEED_ANCHOR_QUESTION_REVIEW_PATH = _DATA_DIR / "v2_seed_anchor_question_review_status.json"
SEED_ANCHOR_OPTION_REVIEW_PATH = _DATA_DIR / "v2_seed_anchor_option_review_status.json"

_QUESTION_ADAPTER: TypeAdapter[list[SeedAnchorQuestionReviewEntry]] = TypeAdapter(
    list[SeedAnchorQuestionReviewEntry]
)
_OPTION_ADAPTER: TypeAdapter[list[SeedAnchorOptionReviewEntry]] = TypeAdapter(list[SeedAnchorOptionReviewEntry])


class SeedAnchorReviewStatusValidationError(ValueError):
    """검토 상태 파일의 Key 집합이 실제 Seed Anchor Variant 목록과 다를 때."""


def load_seed_anchor_question_review_entries(
    path: Path = SEED_ANCHOR_QUESTION_REVIEW_PATH,
) -> list[SeedAnchorQuestionReviewEntry]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return _QUESTION_ADAPTER.validate_python(raw)


def load_seed_anchor_option_review_entries(
    path: Path = SEED_ANCHOR_OPTION_REVIEW_PATH,
) -> list[SeedAnchorOptionReviewEntry]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return _OPTION_ADAPTER.validate_python(raw)


def validate_seed_anchor_review_status_files(
    *,
    question_path: Path = SEED_ANCHOR_QUESTION_REVIEW_PATH,
    option_path: Path = SEED_ANCHOR_OPTION_REVIEW_PATH,
) -> None:
    question_entries = load_seed_anchor_question_review_entries(question_path)
    option_entries = load_seed_anchor_option_review_entries(option_path)

    expected_question_keys = {(v.context_id, v.anchor_id) for v in SEED_ANCHOR_VARIANTS}
    question_keys = [(e.context_id, e.anchor_id) for e in question_entries]
    if len(question_keys) != len(set(question_keys)):
        raise SeedAnchorReviewStatusValidationError(f"{question_path}: (context_id, anchor_id)가 중복됐다: {question_keys}")
    if set(question_keys) != expected_question_keys:
        missing = expected_question_keys - set(question_keys)
        extra = set(question_keys) - expected_question_keys
        raise SeedAnchorReviewStatusValidationError(
            f"{question_path}: 실제 Seed Anchor Variant 목록과 일치하지 않는다"
            f"(빠짐: {sorted(missing)}, 불필요: {sorted(extra)})"
        )

    expected_option_keys = {
        (v.context_id, v.anchor_id, role_id) for v in SEED_ANCHOR_VARIANTS for role_id in v.option_text_by_role_id
    }
    option_keys = [(e.context_id, e.anchor_id, e.role_id) for e in option_entries]
    if len(option_keys) != len(set(option_keys)):
        raise SeedAnchorReviewStatusValidationError(f"{option_path}: (context_id, anchor_id, role_id)가 중복됐다: {option_keys}")
    if set(option_keys) != expected_option_keys:
        missing = expected_option_keys - set(option_keys)
        extra = set(option_keys) - expected_option_keys
        raise SeedAnchorReviewStatusValidationError(
            f"{option_path}: 실제 Seed Anchor Option 목록과 일치하지 않는다"
            f"(빠짐: {sorted(missing)}, 불필요: {sorted(extra)})"
        )
