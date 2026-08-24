"""Canonical Major Group Bridge Scope 검수 상태 Store — 2026-08-24 지시서
(a/bridge-scope-final-review-ui) §4.

기본 경로는 `data/reviews/canonical_major_group_bridge_scope_review_status.jsonl`
이다 — Mapping 검수 Store(`canonical_major_group_bridge_review_store.py`,
JSON 배열·`.json` 확장자)와 파일 형식도 확장자도 다른 완전히 별도 파일이며, 이
Store는 Mapping 검수 파일도 Master Draft(`canonical_major_group_bridge.draft.jsonl`)
도 절대 열거나 쓰지 않는다. 형식만 JSONL(줄 단위 JSON)로 다를 뿐, 원자적 쓰기
(tmp 파일에 먼저 쓰고 `Path.replace()`로 교체)는 Mapping Store와 같은 관례를
따른다."""

from __future__ import annotations

import json
from pathlib import Path

from src.schemas.canonical_major_group_bridge_scope_review import CanonicalMajorGroupBridgeScopeReview

_DEFAULT_PATH = (
    Path(__file__).resolve().parents[2]
    / "data" / "reviews" / "canonical_major_group_bridge_scope_review_status.jsonl"
)


class DuplicateBridgeScopeReviewKeyError(ValueError):
    """저장된 Scope 검수 상태 파일 안에 같은 복합 Key(`canonical_major_group_id` +
    `canonical_major_id`)가 두 번 이상 있을 때. 정상 경로(이 Store의 save 함수만
    사용)에서는 절대 발생하지 않는다 — 파일이 외부에서 수동으로 손상된 경우를
    잡아내는 방어선이다(조용히 하나를 덮어쓰고 넘어가지 않는다)."""


def bridge_scope_review_path(path: Path | None = None) -> Path:
    return path or _DEFAULT_PATH


def load_bridge_scope_review_entries(path: Path | None = None) -> list[CanonicalMajorGroupBridgeScopeReview]:
    resolved = bridge_scope_review_path(path)
    if not resolved.exists():
        return []
    entries: list[CanonicalMajorGroupBridgeScopeReview] = []
    for line_number, line in enumerate(resolved.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entries.append(CanonicalMajorGroupBridgeScopeReview.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"{resolved.name}:{line_number}: Scope 검수 JSONL 행 파싱 실패 — {exc}") from exc
    return entries


def load_bridge_scope_review_entries_by_key(
    path: Path | None = None,
) -> dict[str, CanonicalMajorGroupBridgeScopeReview]:
    """복합 Key로 바로 찾을 수 있는 dict. 같은 Key가 두 번 저장돼 있으면(파일이
    손상된 경우) 조용히 마지막 값으로 덮어쓰지 않고 즉시 예외를 던진다."""

    by_key: dict[str, CanonicalMajorGroupBridgeScopeReview] = {}
    for entry in load_bridge_scope_review_entries(path):
        if entry.key in by_key:
            raise DuplicateBridgeScopeReviewKeyError(f"Scope 검수 상태 파일에 중복된 Key: {entry.key!r}")
        by_key[entry.key] = entry
    return by_key


def save_bridge_scope_review_entries(
    entries: list[CanonicalMajorGroupBridgeScopeReview], path: Path | None = None,
) -> None:
    keys = [e.key for e in entries]
    if len(keys) != len(set(keys)):
        raise DuplicateBridgeScopeReviewKeyError(f"저장하려는 목록에 중복된 Key가 있다: {sorted(keys)}")

    resolved = bridge_scope_review_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    lines = [e.model_dump_json() for e in entries]
    payload = "\n".join(lines) + ("\n" if lines else "")
    tmp_path = resolved.parent / f".{resolved.name}.tmp"
    tmp_path.write_text(payload, encoding="utf-8")
    tmp_path.replace(resolved)
