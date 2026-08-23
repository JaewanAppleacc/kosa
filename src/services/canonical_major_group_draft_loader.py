"""Canonical Major Group Draft Loader — A-2 지시서(integration/academyinfo-pipeline,
2026-08-24) §4. A 소유(얇은 Loader — `trait_ontology_v2.py`/`department_repository.py`
와 같은 "빌드 산출물 JSONL → Pydantic" 패턴).

이 Loader는 읽기만 한다 — `data/canonical_major_groups.draft.jsonl` 자체는 worker-c
소유 산출물이고, A는 여기서 파일을 고치지 않는다."""

from __future__ import annotations

import json
from pathlib import Path

from src.schemas.canonical_major_group import CanonicalMajorGroupDraft

DEFAULT_CANONICAL_MAJOR_GROUPS_DRAFT_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "canonical_major_groups.draft.jsonl"
)


def load_canonical_major_groups_draft(path: Path | None = None) -> list[CanonicalMajorGroupDraft]:
    source = path or DEFAULT_CANONICAL_MAJOR_GROUPS_DRAFT_PATH
    if not source.exists():
        return []
    return [
        CanonicalMajorGroupDraft.model_validate(json.loads(line))
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
