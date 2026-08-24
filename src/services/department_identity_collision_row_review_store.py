"""department_id Identity-Key 충돌 32행 — 사람 판정 정본 Store — 2026-08-25
지시서(a/offering-identity-v2) §1.

기본 경로는 `data/reviews/department_identity_collision_row_review_status.jsonl`
이다. 다른 검수 Store(Bridge/P1/N.C.E/Canonical Major Group)와 물리적으로
완전히 분리된 파일이며, 이 Store는 그 파일들을 절대 열거나 쓰지 않는다."""

from __future__ import annotations

import json
from pathlib import Path

from src.schemas.department_identity_collision_row_review import DepartmentIdentityCollisionRowReview

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_PATH = _REPO_ROOT / "data" / "reviews" / "department_identity_collision_row_review_status.jsonl"


class DuplicateRowReviewKeyError(ValueError):
    """저장된 판정 파일 안에 같은 source_record_id가 두 번 이상 있을 때 —
    정상 경로에서는 절대 발생하지 않는다."""


def row_review_path(path: Path | None = None) -> Path:
    return path or _DEFAULT_PATH


def load_row_review_entries(path: Path | None = None) -> list[DepartmentIdentityCollisionRowReview]:
    resolved = row_review_path(path)
    if not resolved.exists():
        return []
    entries: list[DepartmentIdentityCollisionRowReview] = []
    for line_number, line in enumerate(resolved.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entries.append(DepartmentIdentityCollisionRowReview.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"{resolved.name}:{line_number}: 판정 JSONL 행 파싱 실패 — {exc}") from exc
    return entries


def load_row_review_entries_by_key(path: Path | None = None) -> dict[str, DepartmentIdentityCollisionRowReview]:
    by_key: dict[str, DepartmentIdentityCollisionRowReview] = {}
    for entry in load_row_review_entries(path):
        if entry.key in by_key:
            raise DuplicateRowReviewKeyError(f"판정 파일에 중복된 Key: {entry.key!r}")
        by_key[entry.key] = entry
    return by_key


def save_row_review_entries(entries: list[DepartmentIdentityCollisionRowReview], path: Path | None = None) -> None:
    keys = [e.key for e in entries]
    if len(keys) != len(set(keys)):
        raise DuplicateRowReviewKeyError(f"저장하려는 목록에 중복된 Key가 있다: {sorted(keys)}")

    resolved = row_review_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    lines = [e.model_dump_json() for e in entries]
    payload = "\n".join(lines) + ("\n" if lines else "")
    tmp_path = resolved.parent / f".{resolved.name}.tmp"
    tmp_path.write_text(payload, encoding="utf-8")
    tmp_path.replace(resolved)
