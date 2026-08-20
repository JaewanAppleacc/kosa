"""Knowledge Subgraph Schema — 설계안 §23 구현. B의 obsidian_exporter.py가 소비하는 계약이다.

A는 이 두 타입과 `/subgraph/{session_id}` API 응답만 제공한다. Obsidian 변환·렌더링은 B 소유.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

NodeType = Literal[
    "Student",
    "Trait",
    "RelatedConcept",
    "CareerDimension",
    "CanonicalMajor",
    "Department",
    "University",
    "HighSchoolSubject",
    "Occupation",
]

RelationType = Literal[
    "HAS_TRAIT",
    "RELATED_CONCEPT",
    "GROUPED_AS",
    "RELATED_TO",
    "HAS_DEPARTMENT",
    "BELONGS_TO",
    "RECOMMENDS",
]

_NODE_COLOR: dict[NodeType, str] = {
    "Student": "yellow",
    "Trait": "purple",
    "RelatedConcept": "gray",
    "CareerDimension": "pink",
    "CanonicalMajor": "blue",
    "Department": "green",
    "HighSchoolSubject": "orange",
    "Occupation": "red",
    "University": "green",
}


class SubgraphNode(BaseModel):
    node_id: str
    node_type: NodeType
    label: str

    @property
    def display_color(self) -> str:
        return _NODE_COLOR[self.node_type]


class SubgraphEdge(BaseModel):
    """§23 원문 그대로. relation_type이 RELATED_CONCEPT이면 점선으로 그려야 한다(§12-2) —
    확정 관찰 Evidence가 아니라 추론된 연관성이라는 걸 시각적으로 구분하기 위함이다."""

    source_node_id: str
    target_node_id: str
    relation_type: RelationType
    relevance_level: int
    evidence_ids: list[str] = []
    source_ids: list[str] = []
    mapping_version: str
    created_at: datetime
