"""대학알리미 P1 분류 REVIEW 검수 패킷 Loader — 2026-08-24 지시서
(a/academyinfo-review-ui-p1-nce).

`data/academyinfo_work/2025/packets/p1_classification_review.jsonl`(374행,
Read-Only)을 읽고 Fail-Fast로 검증한다. 이 파일을 쓰는 코드는 없다 — Master
Draft(Bridge)와 같은 원칙."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from src.schemas.academyinfo_p1_classification import AcademyInfoP1ClassificationEntry

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_P1_PACKET_PATH = (
    _REPO_ROOT / "data" / "academyinfo_work" / "2025" / "packets" / "p1_classification_review.jsonl"
)


class P1PacketValidationError(ValueError):
    """패킷 파일 전체 수준의 구조 오류(JSON 파싱 실패, 중복 candidate_id,
    Pydantic Schema 위반)."""


def load_p1_classification_packet(path: Path | None = None) -> list[AcademyInfoP1ClassificationEntry]:
    resolved = path or DEFAULT_P1_PACKET_PATH
    entries: list[AcademyInfoP1ClassificationEntry] = []
    seen_ids: set[str] = set()
    for line_number, line in enumerate(resolved.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise P1PacketValidationError(f"{resolved.name}:{line_number}: JSONL 파싱 실패") from exc
        try:
            entry = AcademyInfoP1ClassificationEntry.model_validate(row)
        except PydanticValidationError as exc:
            raise P1PacketValidationError(f"{resolved.name}:{line_number}: Schema 검증 실패 — {exc}") from exc
        if entry.candidate_id in seen_ids:
            raise P1PacketValidationError(f"중복 candidate_id: {entry.candidate_id!r}")
        seen_ids.add(entry.candidate_id)
        entries.append(entry)
    return entries
