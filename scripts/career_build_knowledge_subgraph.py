"""정적 Knowledge Subgraph 생성 — 2026-08-25 지시서(a/subgraph-rag-frontend-38-majors §1,
a/final-39-major-integration §5 최종 재생성).

`src/services/knowledge_subgraph_service.py`(Runtime, 세션별 동적 Subgraph)를 건드리지
않는다 — "Runtime 중앙 파일 수정 금지". 이 스크립트는 그 파일과 완전히 별개로,
39개 서비스 Major·24개 Trait·학과·과목 전체를 한 번 계산해
`data/knowledge_subgraph/nodes.jsonl`·`data/knowledge_subgraph/edges.jsonl`에
저장하는 정적 스냅샷을 만든다. `src/schemas/knowledge_subgraph_static_v1.py`가 이
산출물의 계약이다 — Edge 종류 선택(특히 Major→Group을 추가한 이유)은 그 파일
docstring에 있다.

추천 점수는 어디에도 저장하지 않는다(지시서 §1). 모든 Edge는 evidence_refs를
최소 1개 갖는다 — Schema의 `model_validator`가 강제하므로, 근거 없는 Edge를 만들면
이 스크립트 실행 자체가 즉시 실패한다(Fail-Fast).

## 2026-08-25 재생성(a/final-39-major-integration) — 입력을 최종 병합본으로 교체

최초 버전(a/subgraph-rag-frontend-38-majors)은 그 시점에 있던 데이터만 썼다 —
Trait→Major는 `major_trait_mapping_evidence_v2.jsonl`의 EVIDENCED 3개 Major뿐이었고
(나머지 36개는 Major→Group으로만 고아를 면했다), Department는 옛 1,072건·8개 Major,
Subject는 옛 `subjects.jsonl` 18개·`subject_major_link_evidence.jsonl` 16행이었다.

4개 upstream 브랜치(Profile v2·Subject Mapping v2·전국 학과 38개 재분류·이 Subgraph
자신)가 전부 병합된 지금은 그 산출물을 "최종값"으로 보지 않는다(지시서 §5 명시) —
다음처럼 전부 최종 정본으로 바꿨다.

- **Trait→Major**: `data/master/major_profiles_v2.jsonl`(39개 Major 전부, 4개
  Vector Group)의 0이 아닌 모든 (trait_id, major_id) 쌍. evidence_refs는 그 Profile
  행의 `source_ids`(이미 실제 공식 데이터 포털 URL) 그대로 — Major→Group과 마찬가지로
  "이미 있는 관계를 그대로 옮긴 것"이라 지어낸 게 아니다. 이제 39개 Major 전부가
  이 Edge만으로도 고아가 아니다(Major→Group은 38개 FULL_GROUP Major에 여전히 추가
  근거로 남긴다 — 있어서 나쁠 게 없는 추가 grounding이다).
- **Major→Department**: `data/master/departments.jsonl`이 같은 경로에서 그대로
  5,595건·38개 Major로 교체됐다 — 이 스크립트 코드는 바뀌지 않는다.
- **Major→Subject**: `data/master/subject_major_link_evidence_v2.jsonl`(71건 RELATED,
  35개 Major 정식 검토 근거)을 우선 쓰고, 거기 없는 4개 Major(education·hci_ux·
  industrial_engineering·psychology)만 `data/master/subject_profiles_v2.jsonl`(41개
  과목)의 related_major_ids + 그 과목 자신의 source_id로 보완한다 — 이전 버전과
  같은 "정식 근거 우선, 없으면 과목 자체 근거로 보완" 원칙을 그대로 유지한다.
  hci_ux는 이 41개 과목 중 "정보"·"소프트웨어와 생활" 2개에만 이미 연결돼 있고
  (subject-mapping-38-majors 자체 테스트가 새 hci_ux 연결 0건을 보장), 이 스크립트가
  새로 만들지 않는다.

실행:
    PYTHONPATH=. ./.venv/bin/python scripts/career_build_knowledge_subgraph.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402
from src.schemas.knowledge_subgraph_static_v1 import (  # noqa: E402
    STATIC_SUBGRAPH_VERSION,
    StaticSubgraphEdge,
    StaticSubgraphNode,
)
from src.services.service_canonical_major_v2_loader import load_service_canonical_majors_v2  # noqa: E402

OUT_DIR = ROOT / "data" / "knowledge_subgraph"
TRAITS_PATH = ROOT / "data" / "master" / "trait_ontology_v2.jsonl"
GROUPS_PATH = ROOT / "data" / "canonical_major_groups.draft.jsonl"
BRIDGE_PATH = ROOT / "data" / "master" / "canonical_major_group_to_service_major_v2.jsonl"
DEPARTMENTS_PATH = ROOT / "data" / "master" / "departments.jsonl"
MAJOR_PROFILES_PATH = ROOT / "data" / "master" / "major_profiles_v2.jsonl"
SUBJECTS_PATH = ROOT / "data" / "master" / "subject_profiles_v2.jsonl"
SUBJECT_MAJOR_EVIDENCE_PATH = ROOT / "data" / "master" / "subject_major_link_evidence_v2.jsonl"
_VECTOR_GROUP_FIELDS = (
    "interest_vector", "cognitive_vector", "work_style_vector", "environment_vector",
)


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[StaticSubgraphNode] | list[StaticSubgraphEdge]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(row.model_dump_json() + "\n" for row in rows), encoding="utf-8"
    )


def build_trait_nodes() -> list[StaticSubgraphNode]:
    traits = _read_jsonl(TRAITS_PATH)
    return [
        StaticSubgraphNode(node_id=f"trait_{t['trait_id']}", node_type="Trait", label=t["label"])
        for t in sorted(traits, key=lambda t: t["trait_id"])
    ]


def build_major_nodes(majors) -> list[StaticSubgraphNode]:
    return [
        StaticSubgraphNode(node_id=f"major_{m.major_id}", node_type="Major", label=m.label)
        for m in sorted(majors, key=lambda m: m.major_id)
    ]


def build_group_nodes(majors, groups_by_id: dict[str, dict]) -> list[StaticSubgraphNode]:
    group_ids = sorted({m.canonical_major_group_id for m in majors if m.mapping_scope == "FULL_GROUP"})
    return [
        StaticSubgraphNode(node_id=f"group_{gid}", node_type="Group", label=groups_by_id[gid]["label"])
        for gid in group_ids
    ]


def build_department_nodes(departments: list[dict]) -> list[StaticSubgraphNode]:
    return [
        StaticSubgraphNode(
            node_id=d["department_id"],
            node_type="Department",
            label=f"{d['university_name']} {d['department_name']}",
        )
        for d in sorted(departments, key=lambda d: d["department_id"])
    ]


def build_subject_nodes(subjects: list[dict]) -> list[StaticSubgraphNode]:
    return [
        StaticSubgraphNode(node_id=s["subject_id"], node_type="Subject", label=s["label"])
        for s in sorted(subjects, key=lambda s: s["subject_id"])
    ]


def build_trait_to_major_edges(major_profiles: list[dict], major_ids: set[str]) -> list[StaticSubgraphEdge]:
    """`major_profiles_v2.jsonl`(39개 Major 전부)의 0이 아닌 (trait_id, major_id) 쌍
    전부를 Edge로 옮긴다 — 근거는 그 Profile 행 자신의 source_ids다."""

    edges = []
    for profile in sorted(major_profiles, key=lambda p: p["major_id"]):
        if profile["major_id"] not in major_ids:
            continue
        trait_ids: set[str] = set()
        for field in _VECTOR_GROUP_FIELDS:
            trait_ids.update(profile[field])
        refs = sorted(profile["source_ids"])
        for trait_id in sorted(trait_ids):
            edges.append(
                StaticSubgraphEdge(
                    source_node_id=f"trait_{trait_id}",
                    target_node_id=f"major_{profile['major_id']}",
                    relation_type="TRAIT_TO_MAJOR",
                    evidence_refs=refs,
                    mapping_version=profile["profile_version"],
                )
            )
    return edges


def build_major_to_group_edges(majors) -> list[StaticSubgraphEdge]:
    edges = []
    for m in sorted(majors, key=lambda m: m.major_id):
        if m.mapping_scope != "FULL_GROUP":
            continue
        edges.append(
            StaticSubgraphEdge(
                source_node_id=f"major_{m.major_id}",
                target_node_id=f"group_{m.canonical_major_group_id}",
                relation_type="MAJOR_TO_GROUP",
                evidence_refs=[
                    f"data/master/canonical_major_group_to_service_major_v2.jsonl"
                    f"#canonical_major_group_id={m.canonical_major_group_id}"
                ],
                mapping_version=STATIC_SUBGRAPH_VERSION,
            )
        )
    return edges


def build_major_to_department_edges(departments: list[dict], major_ids: set[str]) -> list[StaticSubgraphEdge]:
    edges = []
    for d in sorted(departments, key=lambda d: d["department_id"]):
        if d["canonical_major_id"] not in major_ids:
            continue
        ref = d["department_url"] or d["source_url"]
        edges.append(
            StaticSubgraphEdge(
                source_node_id=f"major_{d['canonical_major_id']}",
                target_node_id=d["department_id"],
                relation_type="MAJOR_TO_DEPARTMENT",
                evidence_refs=[f"{ref}#{d['department_id']}"],
                mapping_version=STATIC_SUBGRAPH_VERSION,
            )
        )
    return edges


def build_major_to_subject_edges(subjects: list[dict], major_ids: set[str]) -> list[StaticSubgraphEdge]:
    """근거 우선순위: 정식 검토를 거친 `subject_major_link_evidence_v2.jsonl`(71건,
    35개 Major)의 RELATED 행이 있으면 그걸 쓰고, 거기 없는 4개 Major(education·
    hci_ux·industrial_engineering·psychology)만 `subject_profiles_v2.jsonl` 자체의
    related_major_ids + 그 과목의 source_id(교육부 공식 교육과정)를 근거로 쓴다 —
    둘 다 이미 committed된 실제 데이터라 어느 쪽도 지어낸 게 아니다."""

    formal = {
        (r["major_id"], r["subject_id"]): r
        for r in _read_jsonl(SUBJECT_MAJOR_EVIDENCE_PATH)
        if r["link_status"] == "RELATED"
    }

    pairs: dict[tuple[str, str], list[str]] = {}
    for s in subjects:
        for major_id in s["related_major_ids"]:
            if major_id not in major_ids:
                continue
            key = (major_id, s["subject_id"])
            formal_row = formal.get(key)
            if formal_row is not None:
                refs = sorted({ev["source_url"] for ev in formal_row["evidence"]})
            else:
                refs = [f"{s['source_id']}#{s['subject_id']}"]
            pairs[key] = refs

    edges = []
    for (major_id, subject_id), refs in sorted(pairs.items()):
        edges.append(
            StaticSubgraphEdge(
                source_node_id=f"major_{major_id}",
                target_node_id=subject_id,
                relation_type="MAJOR_TO_SUBJECT",
                evidence_refs=refs,
                mapping_version=STATIC_SUBGRAPH_VERSION,
            )
        )
    return edges


def build() -> tuple[list[StaticSubgraphNode], list[StaticSubgraphEdge]]:
    majors = sorted(load_service_canonical_majors_v2(), key=lambda m: m.major_id)
    major_ids = {m.major_id for m in majors}
    groups_by_id = {g["canonical_major_id"]: g for g in _read_jsonl(GROUPS_PATH)}
    departments = _read_jsonl(DEPARTMENTS_PATH)
    subjects = _read_jsonl(SUBJECTS_PATH)
    major_profiles = _read_jsonl(MAJOR_PROFILES_PATH)

    nodes = (
        build_trait_nodes()
        + build_major_nodes(majors)
        + build_group_nodes(majors, groups_by_id)
        + build_department_nodes(departments)
        + build_subject_nodes(subjects)
    )
    edges = (
        build_trait_to_major_edges(major_profiles, major_ids)
        + build_major_to_group_edges(majors)
        + build_major_to_department_edges(departments, major_ids)
        + build_major_to_subject_edges(subjects, major_ids)
    )

    node_ids = [n.node_id for n in nodes]
    if len(node_ids) != len(set(node_ids)):
        raise SystemExit("중복 node_id가 생성됐다 — 생성 로직을 확인해야 한다")

    _write_jsonl(OUT_DIR / "nodes.jsonl", nodes)
    _write_jsonl(OUT_DIR / "edges.jsonl", edges)
    return nodes, edges


if __name__ == "__main__":
    use_utf8_stdout()
    nodes, edges = build()
    by_type: dict[str, int] = {}
    for n in nodes:
        by_type[n.node_type] = by_type.get(n.node_type, 0) + 1
    print(f"Node {len(nodes)}개: {by_type}")

    by_relation: dict[str, int] = {}
    for e in edges:
        by_relation[e.relation_type] = by_relation.get(e.relation_type, 0) + 1
    print(f"Edge {len(edges)}개: {by_relation}")

    major_node_ids = {n.node_id for n in nodes if n.node_type == "Major"}
    connected_majors = {e.source_node_id for e in edges if e.source_node_id in major_node_ids}
    orphans = major_node_ids - connected_majors
    print(f"고아 Major 노드: {len(orphans)}개 ({sorted(orphans)})")
