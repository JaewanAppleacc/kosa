"""대학알리미 N.C.E 중계열 검수 상태 Store — 2026-08-24 지시서
(a/academyinfo-review-ui-p1-nce) §2/§4.

기본 경로는 `data/reviews/academyinfo_nce_middle_series_review_status.jsonl`이다.
Bridge Mapping/Scope/P1 Store와 물리적으로 완전히 분리된 파일이며, 이 Store는 그
파일들을 절대 열거나 쓰지 않는다."""

from __future__ import annotations

import json
from pathlib import Path

from src.schemas.academyinfo_nce_middle_series_cluster_review import AcademyInfoNceMiddleSeriesReview

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_PATH = _REPO_ROOT / "data" / "reviews" / "academyinfo_nce_middle_series_review_status.jsonl"


class DuplicateNceReviewKeyError(ValueError):
    """저장된 검수 상태 파일 안에 같은 official_middle_series_code가 두 번 이상
    있을 때 — 정상 경로에서는 절대 발생하지 않는다."""


def nce_review_path(path: Path | None = None) -> Path:
    return path or _DEFAULT_PATH


def load_nce_review_entries(path: Path | None = None) -> list[AcademyInfoNceMiddleSeriesReview]:
    resolved = nce_review_path(path)
    if not resolved.exists():
        return []
    entries: list[AcademyInfoNceMiddleSeriesReview] = []
    for line_number, line in enumerate(resolved.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entries.append(AcademyInfoNceMiddleSeriesReview.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"{resolved.name}:{line_number}: N.C.E 검수 JSONL 행 파싱 실패 — {exc}") from exc
    return entries


def load_nce_review_entries_by_key(path: Path | None = None) -> dict[str, AcademyInfoNceMiddleSeriesReview]:
    by_key: dict[str, AcademyInfoNceMiddleSeriesReview] = {}
    for entry in load_nce_review_entries(path):
        if entry.key in by_key:
            raise DuplicateNceReviewKeyError(f"N.C.E 검수 상태 파일에 중복된 Key: {entry.key!r}")
        by_key[entry.key] = entry
    return by_key


def save_nce_review_entries(entries: list[AcademyInfoNceMiddleSeriesReview], path: Path | None = None) -> None:
    keys = [e.key for e in entries]
    if len(keys) != len(set(keys)):
        raise DuplicateNceReviewKeyError(f"저장하려는 목록에 중복된 Key가 있다: {sorted(keys)}")

    resolved = nce_review_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    lines = [e.model_dump_json() for e in entries]
    payload = "\n".join(lines) + ("\n" if lines else "")
    tmp_path = resolved.parent / f".{resolved.name}.tmp"
    tmp_path.write_text(payload, encoding="utf-8")
    tmp_path.replace(resolved)
