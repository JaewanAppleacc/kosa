"""department_id(v1) → offering_id(v2) Migration Map Loader — 2026-08-25
지시서(a/offering-identity-v2) §3. A 소유 얇은 Loader — 읽기만 한다."""

from __future__ import annotations

import json
from pathlib import Path

from src.schemas.department_id_migration_map import DepartmentIdMigrationMapEntry

DEFAULT_MIGRATION_MAP_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "academyinfo_work"
    / "2025"
    / "packets"
    / "department_id_migration_map.jsonl"
)


def load_migration_map(path: Path | None = None) -> list[DepartmentIdMigrationMapEntry]:
    source = path or DEFAULT_MIGRATION_MAP_PATH
    if not source.exists():
        return []
    return [
        DepartmentIdMigrationMapEntry.model_validate(json.loads(line))
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
