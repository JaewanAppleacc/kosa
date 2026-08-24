"""Canonical Major Group Bridge 검수 상태 Store — 2026-08-24 지시서
(a/canonical-major-bridge-review-ui) §1.

기본 경로는 `data/reviews/canonical_major_group_bridge_review_status.json`이다 —
검수 대상인 `data/master/canonical_major_group_bridge.draft.jsonl`(Master Draft)과
완전히 분리된 별도 파일이며, 이 Store는 Draft 파일을 절대 열거나 쓰지 않는다.
기존 5개 검수 Store(`context_pack_shared_probe_review_store.py` 등)와 같은 원칙 —
Claude가 검수 결과를 스스로 채우거나 승격시키지 않는다. 저장은 항상 tmp 파일에
먼저 쓰고 `Path.replace()`로 교체하는 원자적 쓰기다."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from src.schemas.canonical_major_group_bridge_review import CanonicalMajorGroupBridgeReview

_DEFAULT_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "reviews" / "canonical_major_group_bridge_review_status.json"
)

_ADAPTER: TypeAdapter[list[CanonicalMajorGroupBridgeReview]] = TypeAdapter(list[CanonicalMajorGroupBridgeReview])


class DuplicateBridgeReviewKeyError(ValueError):
    """저장된 검수 상태 파일 안에 같은 복합 Key(`canonical_major_group_id` +
    `canonical_major_id`)가 두 번 이상 있을 때. 정상 경로(이 Store의 save 함수만
    사용)에서는 절대 발생하지 않는다 — 파일이 외부에서 수동으로 손상된 경우를
    잡아내는 방어선이다(조용히 하나를 덮어쓰고 넘어가지 않는다)."""


def bridge_review_path(path: Path | None = None) -> Path:
    return path or _DEFAULT_PATH


def load_bridge_review_entries(path: Path | None = None) -> list[CanonicalMajorGroupBridgeReview]:
    resolved = bridge_review_path(path)
    if not resolved.exists():
        return []
    raw = json.loads(resolved.read_text(encoding="utf-8"))
    return _ADAPTER.validate_python(raw)


def load_bridge_review_entries_by_key(path: Path | None = None) -> dict[str, CanonicalMajorGroupBridgeReview]:
    """복합 Key로 바로 찾을 수 있는 dict. 같은 Key가 두 번 저장돼 있으면(파일이 손상된
    경우) 조용히 마지막 값으로 덮어쓰지 않고 즉시 예외를 던진다."""

    by_key: dict[str, CanonicalMajorGroupBridgeReview] = {}
    for entry in load_bridge_review_entries(path):
        if entry.key in by_key:
            raise DuplicateBridgeReviewKeyError(f"검수 상태 파일에 중복된 Key: {entry.key!r}")
        by_key[entry.key] = entry
    return by_key


def save_bridge_review_entries(entries: list[CanonicalMajorGroupBridgeReview], path: Path | None = None) -> None:
    keys = [e.key for e in entries]
    if len(keys) != len(set(keys)):
        raise DuplicateBridgeReviewKeyError(f"저장하려는 목록에 중복된 Key가 있다: {sorted(keys)}")

    resolved = bridge_review_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps([json.loads(e.model_dump_json()) for e in entries], ensure_ascii=False, indent=2)
    tmp_path = resolved.parent / f".{resolved.name}.tmp"
    tmp_path.write_text(payload, encoding="utf-8")
    tmp_path.replace(resolved)
