"""Related Concept Registry Loader — A 소유, 2026-08-23 Trait Ontology v2(1단계) §3.

`data/master/related_concepts_v2.jsonl`을 읽기만 한다(Subject/Major Repository와 같은
패턴). 이번 단계에서는 현재 3개 Context·기존 검토된 질문에서 실제 근거를 찾을 수 있는
Concept만 정의했다(§3 "30~50개를 억지로 채우지 말 것") — 전부 `review_status="draft"`.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.schemas.related_concept import RelatedConceptDefinition

DEFAULT_RELATED_CONCEPTS_V2_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "master" / "related_concepts_v2.jsonl"
)


def load_related_concepts_v2(path: Path | None = None) -> list[RelatedConceptDefinition]:
    source = path or DEFAULT_RELATED_CONCEPTS_V2_PATH
    if not source.exists():
        return []
    return [
        RelatedConceptDefinition.model_validate(json.loads(line))
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
