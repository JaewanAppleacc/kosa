"""정적 Knowledge Subgraph Fail-Fast Loader — 2026-08-25 지시서(a/subgraph-rag-frontend-38-majors) §1/§5.

`scripts/career_build_knowledge_subgraph.py`가 만든 `data/knowledge_subgraph/`
두 파일을 읽는다. 이 저장소의 다른 JSONL Loader(예:
`service_canonical_major_v2_loader.py`)와 같은 원칙 — 문제가 있으면 조용히
넘어가지 않고 로드 시점에 즉시 예외를 던진다."""

from __future__ import annotations

import json
from pathlib import Path

from src.schemas.knowledge_subgraph_static_v1 import StaticSubgraphEdge, StaticSubgraphNode

_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NODES_PATH = _ROOT / "data" / "knowledge_subgraph" / "nodes.jsonl"
DEFAULT_EDGES_PATH = _ROOT / "data" / "knowledge_subgraph" / "edges.jsonl"


class DuplicateNodeIdError(ValueError):
    pass


class DanglingEdgeReferenceError(ValueError):
    pass


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_knowledge_subgraph_nodes(path: Path | None = None) -> list[StaticSubgraphNode]:
    rows = _read_jsonl(path or DEFAULT_NODES_PATH)
    nodes = [StaticSubgraphNode.model_validate(row) for row in rows]

    seen: dict[str, StaticSubgraphNode] = {}
    for node in nodes:
        if node.node_id in seen:
            raise DuplicateNodeIdError(
                f"node_id 중복: {node.node_id!r} "
                f"({seen[node.node_id].node_type} vs {node.node_type})"
            )
        seen[node.node_id] = node
    return nodes


def load_knowledge_subgraph_edges(
    path: Path | None = None, *, known_node_ids: set[str] | None = None
) -> list[StaticSubgraphEdge]:
    rows = _read_jsonl(path or DEFAULT_EDGES_PATH)
    edges = [StaticSubgraphEdge.model_validate(row) for row in rows]

    if known_node_ids is None:
        known_node_ids = {n.node_id for n in load_knowledge_subgraph_nodes()}

    for edge in edges:
        if edge.source_node_id not in known_node_ids:
            raise DanglingEdgeReferenceError(f"source_node_id가 존재하지 않는 노드를 가리킨다: {edge.source_node_id!r}")
        if edge.target_node_id not in known_node_ids:
            raise DanglingEdgeReferenceError(f"target_node_id가 존재하지 않는 노드를 가리킨다: {edge.target_node_id!r}")
    return edges
