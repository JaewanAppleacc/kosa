"""대학알리미 P1 분류 REVIEW 검수 상태 Store — 2026-08-24 지시서
(a/academyinfo-review-ui-p1-nce) §1/§4.

기본 경로는 `data/reviews/academyinfo_p1_classification_review_status.jsonl`이다.
Bridge Mapping/Scope Store와 물리적으로 완전히 분리된 파일이며, 이 Store는 그
파일들을 절대 열거나 쓰지 않는다. 원자적 쓰기(tmp 파일 → `Path.replace()`)는
기존 관례를 그대로 따른다."""

from __future__ import annotations

import json
from pathlib import Path

from src.schemas.academyinfo_p1_classification_candidate_review import AcademyInfoP1ClassificationReview

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_PATH = _REPO_ROOT / "data" / "reviews" / "academyinfo_p1_classification_review_status.jsonl"


class DuplicateP1ReviewKeyError(ValueError):
    """저장된 검수 상태 파일 안에 같은 candidate_id가 두 번 이상 있을 때 — 정상
    경로에서는 절대 발생하지 않는다(파일이 외부에서 손상된 경우를 잡는 방어선)."""


def p1_review_path(path: Path | None = None) -> Path:
    return path or _DEFAULT_PATH


def load_p1_review_entries(path: Path | None = None) -> list[AcademyInfoP1ClassificationReview]:
    resolved = p1_review_path(path)
    if not resolved.exists():
        return []
    entries: list[AcademyInfoP1ClassificationReview] = []
    for line_number, line in enumerate(resolved.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entries.append(AcademyInfoP1ClassificationReview.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"{resolved.name}:{line_number}: P1 검수 JSONL 행 파싱 실패 — {exc}") from exc
    return entries


def load_p1_review_entries_by_key(path: Path | None = None) -> dict[str, AcademyInfoP1ClassificationReview]:
    by_key: dict[str, AcademyInfoP1ClassificationReview] = {}
    for entry in load_p1_review_entries(path):
        if entry.key in by_key:
            raise DuplicateP1ReviewKeyError(f"P1 검수 상태 파일에 중복된 Key: {entry.key!r}")
        by_key[entry.key] = entry
    return by_key


def save_p1_review_entries(entries: list[AcademyInfoP1ClassificationReview], path: Path | None = None) -> None:
    keys = [e.key for e in entries]
    if len(keys) != len(set(keys)):
        raise DuplicateP1ReviewKeyError(f"저장하려는 목록에 중복된 Key가 있다: {sorted(keys)}")

    resolved = p1_review_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    lines = [e.model_dump_json() for e in entries]
    payload = "\n".join(lines) + ("\n" if lines else "")
    tmp_path = resolved.parent / f".{resolved.name}.tmp"
    tmp_path.write_text(payload, encoding="utf-8")
    tmp_path.replace(resolved)
