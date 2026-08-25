"""Static Knowledge Subgraph v1 — 2026-08-25 지시서(a/subgraph-rag-frontend-38-majors) §1.

`src/services/knowledge_subgraph_service.py`(Runtime, 학생 세션 하나마다 그때그때
만드는 동적 Subgraph)와는 다른 산출물이다. 저건 매 요청마다 그래프를 새로 만들고,
이건 39개 서비스 Major·24개 Trait·학과·과목 전체를 미리 계산해
`data/knowledge_subgraph/`에 정적으로 저장해 두는 스냅샷이다 — 이 파일이 그 계약을
정의하고 `scripts/career_build_knowledge_subgraph.py`가 채운다. Runtime 파일은
이 스키마를 아직 참조하지 않는다(배선은 이번 라운드 범위 밖 — "Runtime 중앙 파일
수정 금지").

`src/schemas/graph.py`의 `SubgraphNode`/`SubgraphEdge`(§23, Runtime 계약)를 그대로
재사용하지 않고 새로 정의하는 이유: 그 NodeType/RelationType Literal은 B의
obsidian_exporter.py가 소비하는 고정 계약이라 손대면 안 되는데, 이 정적 Subgraph는
그 계약에 없는 "Group"(Major→Group, 근거 문단 참고)이 필요하다. 계약을 건드리는
대신 이 산출물 전용 스키마를 새로 만든다.

## Major 노드가 고아가 되지 않는 이유 — Group Edge를 추가한 근거

지시서가 요구하는 4종 Edge(Trait→Major/Major→Department/Major→Subject/Subject
대체 관계)만으로는 "고아 Major 노드 0"을 만족할 수 없다. 실제 데이터가 그렇다:

- `data/master/major_trait_mapping_evidence_v2.jsonl`의 EVIDENCED 행은 3개
  Major(media_communication·hci_ux·industrial_engineering)에만 있다.
- `data/master/departments.jsonl`의 canonical_major_id도 8개 Major에만 실제로
  걸려 있다 — 나머지 30개 신규 Major는 `rationale_c/08-service-canonical-major-v2.md`
  "다음 라운드가 할 일"에 명시된 대로 **아직 학과 재연결 작업 자체가 없다.**
- `data/master/subjects.jsonl`의 related_major_ids도 9개 Major만 커버한다.

이 세 Edge의 합집합은 9개 Major만 근거를 갖는다. 나머지 30개를 "고아 아님"으로
만들려면 둘 중 하나다 — 없는 학과·과목·Trait 근거를 지어내거나(§27 위반, 이 라운드
"금지" 항목이 명시적으로 막음), 아니면 **이미 그 자체로 100% 근거가 있는 관계**를
쓰거나. 후자를 택했다 — 38개 FULL_GROUP Major는 애초에
`data/master/canonical_major_group_to_service_major_v2.jsonl`(정본 Bridge, 이번
라운드가 만들지 않은 이미 검증된 데이터)로 정확히 하나의 Group에 연결되도록
확정돼 있다. 이 연결 자체가 그 Major의 정의다 — 지어낼 필요가 없다. 그래서
Major→Group Edge를 추가해 이 근거로 고아를 없앤다. hci_ux(DEPARTMENT_LEVEL_ONLY,
Group 없음)는 Group Edge가 없지만 Trait·Subject Edge가 이미 있어 고아가 아니다.

이 확장을 완료 보고서에 투명하게 남긴다 — Trait/Department/Subject Edge가 실제로
근거를 가진 Major는 9개뿐이고, 나머지 30개는 Group Edge 하나만 갖는다는 사실을
숨기지 않는다.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

NodeType = Literal["Trait", "Major", "Group", "Department", "Subject"]

RelationType = Literal[
    "TRAIT_TO_MAJOR",
    "MAJOR_TO_GROUP",
    "MAJOR_TO_DEPARTMENT",
    "MAJOR_TO_SUBJECT",
]

STATIC_SUBGRAPH_VERSION = "knowledge_subgraph_static_v1.0"


class StaticSubgraphNode(BaseModel):
    node_id: str
    node_type: NodeType
    label: str


class StaticSubgraphEdge(BaseModel):
    """추천 점수는 여기 저장하지 않는다(지시서 §1 "추천 점수는 Graph에 저장하지
    않는다") — 이 Edge는 구조적 사실·근거일 뿐, 관련도 순위가 아니다.

    evidence_refs는 항상 비어 있지 않아야 한다 — 근거 없는 Edge를 만들 방법을
    구조적으로 없앤다(지시서 §5 "근거 없는 Edge 0")."""

    source_node_id: str
    target_node_id: str
    relation_type: RelationType
    evidence_refs: list[str] = Field(min_length=1)
    mapping_version: str

    @model_validator(mode="after")
    def _evidence_refs_must_be_non_blank(self) -> "StaticSubgraphEdge":
        if any(not ref.strip() for ref in self.evidence_refs):
            raise ValueError("evidence_refs에 빈 문자열이 있으면 안 된다")
        return self
