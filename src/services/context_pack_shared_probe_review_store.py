"""ContextPack 공용 Adaptive Probe 검수 상태 Store — 2026-08-23 Trait Ontology
v2(2.9/2.9.1단계) §5/§6/§11 / §3.

`context_pack_shared_probe_blueprints.py`의 Blueprint는 특정 Context 하나가 아니라
신규 12개 Context 전부에 노출된다 — 그래서 Context별 파일(`data/reviews/context_packs/
<context_id>_review_status.json`)이 아니라 단일 공유 파일(`data/reviews/
context_pack_shared_probes_review_status.json`)을 쓰되, 그 파일 안의 각 행은
`(blueprint_id, context_id)` 단위다(2.9.1단계 §3 — blueprint_id 하나만으로는 한
Context에서의 승인이 나머지 11개 Context로 새어나갔다). 기존 5개 검수 Store와 같은
원칙 — Claude가 검수 결과를 스스로 채우거나 승격시키지 않는다."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from src.schemas.context_pack_shared_probe_review import SharedProbeContextReview

_DEFAULT_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "reviews" / "context_pack_shared_probes_review_status.json"
)

_ADAPTER: TypeAdapter[list[SharedProbeContextReview]] = TypeAdapter(list[SharedProbeContextReview])


def shared_probe_review_path(path: Path | None = None) -> Path:
    return path or _DEFAULT_PATH


def load_shared_probe_review_entries(path: Path | None = None) -> list[SharedProbeContextReview]:
    resolved = shared_probe_review_path(path)
    if not resolved.exists():
        return []
    raw = json.loads(resolved.read_text(encoding="utf-8"))
    return _ADAPTER.validate_python(raw)


def load_shared_probe_review_entries_by_key(path: Path | None = None) -> dict[str, SharedProbeContextReview]:
    """`(blueprint_id, context_id)` 복합 Key로 바로 찾을 수 있는 dict — Registry/Gate
    양쪽에서 반복해 쓰는 조회 패턴이라 여기서 한 번만 만든다."""

    return {e.key: e for e in load_shared_probe_review_entries(path)}


def save_shared_probe_review_entries(entries: list[SharedProbeContextReview], path: Path | None = None) -> None:
    resolved = shared_probe_review_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps([json.loads(e.model_dump_json()) for e in entries], ensure_ascii=False, indent=2)
    tmp_path = resolved.parent / f".{resolved.name}.tmp"
    tmp_path.write_text(payload, encoding="utf-8")
    tmp_path.replace(resolved)
