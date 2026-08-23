"""ContextPack Review Status Store — 2026-08-23 Trait Ontology v2(2.8단계) §9. A 소유.

`data/reviews/context_packs/<context_id>_review_status.json`을 읽고 쓴다. Key 형식은
`ContextPackRegistry.required_review_keys()`가 이미 정의한 것과 정확히 같다
(`f"{context_id}::routing::{blueprint_id}"`/`"seed"`/`"anchor_backup"`/
`"direct_probe"`) — 질문(Blueprint) 단위만 다룬다(Option 단위는 이번 계약 범위 밖,
`context_pack_registry.py` 주석과 동일한 한계).

기존 5개 검수 Store(`v2_direct_probe_review_store.py` 등)와 같은 원칙 — 검토 결과를
스스로 채우거나 승격시키지 않는다, Claude가 자동 APPROVE하지 않는다(§9/CLAUDE.md)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from src.schemas.v2_direct_probe_review import QuestionReviewEntry

_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "reviews" / "context_packs"

_ADAPTER: TypeAdapter[list[QuestionReviewEntry]] = TypeAdapter(list[QuestionReviewEntry])


def review_status_path_for(context_id: str, base_dir: Path | None = None) -> Path:
    return (base_dir or _DATA_DIR) / f"{context_id}_review_status.json"


def load_context_pack_review_entries(context_id: str, base_dir: Path | None = None) -> list[QuestionReviewEntry]:
    path = review_status_path_for(context_id, base_dir)
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return _ADAPTER.validate_python(raw)


def save_context_pack_review_entries(
    context_id: str, entries: list[QuestionReviewEntry], base_dir: Path | None = None
) -> None:
    """원자적 쓰기 — 기존 review_service.py의 `_atomic_write` 원칙과 동일하게 임시
    파일에 먼저 쓴 뒤 교체한다(쓰다가 실패해도 기존 파일이 안전하게 남는다)."""

    path = review_status_path_for(context_id, base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps([json.loads(e.model_dump_json()) for e in entries], ensure_ascii=False, indent=2)
    tmp_path = path.parent / f".{path.name}.tmp"
    tmp_path.write_text(payload, encoding="utf-8")
    tmp_path.replace(path)
