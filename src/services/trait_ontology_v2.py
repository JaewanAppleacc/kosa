"""Trait Ontology v2 Loader — A 소유, 2026-08-31 Trait Ontology v2(1단계) 보조.

`data/master/trait_ontology_v2.jsonl`(24개, `scripts/career_build_trait_ontology_v2.py`가
생성하는 정본)을 읽기만 한다 — Subject/Major Repository와 같은 "빌드 스크립트가 만든
JSONL → 얇은 Loader" 패턴을 그대로 따른다.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.schemas.trait import TraitDefinition

DEFAULT_TRAIT_ONTOLOGY_V2_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "master" / "trait_ontology_v2.jsonl"
)


def load_trait_ontology_v2(path: Path | None = None) -> list[TraitDefinition]:
    source = path or DEFAULT_TRAIT_ONTOLOGY_V2_PATH
    if not source.exists():
        return []
    return [
        TraitDefinition.model_validate(json.loads(line))
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
