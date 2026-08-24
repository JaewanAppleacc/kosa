"""대학알리미 N.C.E 재검토 가능 중계열 클러스터 Loader — 2026-08-24 지시서
(a/academyinfo-review-ui-p1-nce).

`data/academyinfo_work/2025/packets/nce_reexaminable_middle_series_clusters.jsonl`
(24행, Read-Only)을 읽고 Fail-Fast로 검증한다."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from src.schemas.academyinfo_nce_middle_series_cluster import AcademyInfoNceMiddleSeriesClusterEntry

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NCE_CLUSTER_PATH = (
    _REPO_ROOT / "data" / "academyinfo_work" / "2025" / "packets" / "nce_reexaminable_middle_series_clusters.jsonl"
)


class NceClusterValidationError(ValueError):
    """패킷 파일 전체 수준의 구조 오류(JSON 파싱 실패, 중복
    official_middle_series_code, Pydantic Schema 위반, row_count 불일치)."""


def load_nce_middle_series_clusters(
    path: Path | None = None,
) -> list[AcademyInfoNceMiddleSeriesClusterEntry]:
    resolved = path or DEFAULT_NCE_CLUSTER_PATH
    entries: list[AcademyInfoNceMiddleSeriesClusterEntry] = []
    seen_codes: set[str] = set()
    for line_number, line in enumerate(resolved.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise NceClusterValidationError(f"{resolved.name}:{line_number}: JSONL 파싱 실패") from exc
        try:
            entry = AcademyInfoNceMiddleSeriesClusterEntry.model_validate(row)
        except PydanticValidationError as exc:
            raise NceClusterValidationError(f"{resolved.name}:{line_number}: Schema 검증 실패 — {exc}") from exc
        if entry.official_middle_series_code in seen_codes:
            raise NceClusterValidationError(f"중복 official_middle_series_code: {entry.official_middle_series_code!r}")
        seen_codes.add(entry.official_middle_series_code)
        # row_count가 실제 members 길이와 어긋나면(예: 산출 스크립트 결함으로 일부
        # 학과가 누락) "대상 학과 총 584건"이라는 집계 자체가 조용히 틀릴 수 있다 —
        # 즉시 드러낸다.
        if entry.row_count != len(entry.members):
            raise NceClusterValidationError(
                f"{entry.official_middle_series_code!r}: row_count({entry.row_count}) != "
                f"members 실제 개수({len(entry.members)})"
            )
        entries.append(entry)
    return entries
