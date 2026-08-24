"""Canonical Major Group 검수 상태 Store — 2026-08-24 지시서
(a/canonical-major-group-review-ui).

기본 경로는 `data/reviews/canonical_major_group_review_status.jsonl`이다. Bridge
Mapping/Scope/P1/N.C.E Store와 물리적으로 완전히 분리된 파일이며, 이 Store는 그
파일들을 절대 열거나 쓰지 않는다.

`load_*`는 파일이 없으면 빈 목록을 돌려줄 뿐 파일을 만들지 않는다 — 실제
저장(`save_canonical_major_group_review_entries`)이 호출되기 전까지는 이
파일이 디스크에 존재하지 않는다(§5 "GET 호출로 파일 미생성" 요구사항을
이 함수 자체의 동작으로 보장한다)."""

from __future__ import annotations

import json
from pathlib import Path

from src.schemas.canonical_major_group_review import CanonicalMajorGroupReview

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_PATH = _REPO_ROOT / "data" / "reviews" / "canonical_major_group_review_status.jsonl"


class DuplicateCanonicalMajorGroupReviewKeyError(ValueError):
    """저장된 검수 상태 파일 안에 같은 canonical_major_group_id가 두 번 이상
    있을 때 — 정상 경로에서는 절대 발생하지 않는다."""


def canonical_major_group_review_path(path: Path | None = None) -> Path:
    return path or _DEFAULT_PATH


def load_canonical_major_group_review_entries(path: Path | None = None) -> list[CanonicalMajorGroupReview]:
    resolved = canonical_major_group_review_path(path)
    if not resolved.exists():
        return []
    entries: list[CanonicalMajorGroupReview] = []
    for line_number, line in enumerate(resolved.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entries.append(CanonicalMajorGroupReview.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"{resolved.name}:{line_number}: Canonical Major Group 검수 JSONL 행 파싱 실패 — {exc}") from exc
    return entries


def load_canonical_major_group_review_entries_by_key(
    path: Path | None = None,
) -> dict[str, CanonicalMajorGroupReview]:
    by_key: dict[str, CanonicalMajorGroupReview] = {}
    for entry in load_canonical_major_group_review_entries(path):
        if entry.key in by_key:
            raise DuplicateCanonicalMajorGroupReviewKeyError(f"검수 상태 파일에 중복된 Key: {entry.key!r}")
        by_key[entry.key] = entry
    return by_key


def save_canonical_major_group_review_entries(
    entries: list[CanonicalMajorGroupReview], path: Path | None = None,
) -> None:
    keys = [e.key for e in entries]
    if len(keys) != len(set(keys)):
        raise DuplicateCanonicalMajorGroupReviewKeyError(f"저장하려는 목록에 중복된 Key가 있다: {sorted(keys)}")

    resolved = canonical_major_group_review_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    lines = [e.model_dump_json() for e in entries]
    payload = "\n".join(lines) + ("\n" if lines else "")
    tmp_path = resolved.parent / f".{resolved.name}.tmp"
    tmp_path.write_text(payload, encoding="utf-8")
    tmp_path.replace(resolved)
