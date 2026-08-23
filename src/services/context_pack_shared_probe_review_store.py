"""ContextPack 공용 Adaptive Probe 검수 상태 Store — 2026-08-23 Trait Ontology
v2(2.9단계) §5/§6/§11.

`context_pack_shared_probe_blueprints.py`의 Blueprint는 특정 Context 하나가 아니라
신규 12개 Context 전부가 공유한다 — 그래서 Context별 파일(`data/reviews/context_packs/
<context_id>_review_status.json`)이 아니라 단일 공유 파일(`data/reviews/
context_pack_shared_probes_review_status.json`)에 blueprint_id 단위로 검수 상태를
담는다. 기존 5개 검수 Store와 같은 원칙 — Claude가 검수 결과를 스스로 채우거나
승격시키지 않는다."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from src.schemas.v2_direct_probe_review import QuestionReviewEntry

_DEFAULT_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "reviews" / "context_pack_shared_probes_review_status.json"
)

_ADAPTER: TypeAdapter[list[QuestionReviewEntry]] = TypeAdapter(list[QuestionReviewEntry])


def shared_probe_review_path(path: Path | None = None) -> Path:
    return path or _DEFAULT_PATH


def load_shared_probe_review_entries(path: Path | None = None) -> list[QuestionReviewEntry]:
    resolved = shared_probe_review_path(path)
    if not resolved.exists():
        return []
    raw = json.loads(resolved.read_text(encoding="utf-8"))
    return _ADAPTER.validate_python(raw)


def save_shared_probe_review_entries(entries: list[QuestionReviewEntry], path: Path | None = None) -> None:
    resolved = shared_probe_review_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps([json.loads(e.model_dump_json()) for e in entries], ensure_ascii=False, indent=2)
    tmp_path = resolved.parent / f".{resolved.name}.tmp"
    tmp_path.write_text(payload, encoding="utf-8")
    tmp_path.replace(resolved)
