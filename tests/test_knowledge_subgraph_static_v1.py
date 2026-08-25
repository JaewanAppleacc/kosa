"""정적 Knowledge Subgraph — 2026-08-25 지시서(a/subgraph-rag-frontend-38-majors) §1/§5 테스트.

네 층위를 확인한다.

    1. Schema 자체가 실제로 근거 없는 Edge를 거부하는지(SchemaValidationTest).
    2. Loader의 Fail-Fast가 합성 Fixture로 실제 작동하는지(LoaderFailFastTest —
       실제 data/knowledge_subgraph/ 파일을 건드리지 않는다).
    3. 실제 생성된 두 파일이 지시서 §5 불변식(39 Major Coverage·고아 Major 0·
       근거 없는 Edge 0)을 지키는지(RealSubgraphInvariantsTest).
    4. 재생성이 byte-identical한지, 그리고 Runtime 중앙 파일이 이 작업으로 전혀
       바뀌지 않았는지(GenerationDeterminismTest / RuntimeUntouchedTest)."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from src.schemas.knowledge_subgraph_static_v1 import StaticSubgraphEdge, StaticSubgraphNode
from src.services.knowledge_subgraph_static_loader import (
    DanglingEdgeReferenceError,
    DuplicateNodeIdError,
    load_knowledge_subgraph_edges,
    load_knowledge_subgraph_nodes,
)
from src.services.service_canonical_major_v2_loader import load_service_canonical_majors_v2

_REPO_ROOT = Path(__file__).resolve().parents[1]
_NODES_PATH = _REPO_ROOT / "data" / "knowledge_subgraph" / "nodes.jsonl"
_EDGES_PATH = _REPO_ROOT / "data" / "knowledge_subgraph" / "edges.jsonl"


class SchemaValidationTest(unittest.TestCase):
    def test_edge_without_evidence_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            StaticSubgraphEdge(
                source_node_id="major_x",
                target_node_id="group_x",
                relation_type="MAJOR_TO_GROUP",
                evidence_refs=[],
                mapping_version="v1",
            )

    def test_edge_with_blank_evidence_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            StaticSubgraphEdge(
                source_node_id="major_x",
                target_node_id="group_x",
                relation_type="MAJOR_TO_GROUP",
                evidence_refs=["   "],
                mapping_version="v1",
            )

    def test_unknown_node_type_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            StaticSubgraphNode(node_id="x", node_type="Occupation", label="x")

    def test_recommendation_score_field_does_not_exist(self) -> None:
        """지시서 §1 "추천 점수는 Graph에 저장하지 않는다" — 필드 자체가 없어야 한다."""

        fields = set(StaticSubgraphEdge.model_fields) | set(StaticSubgraphNode.model_fields)
        self.assertFalse({"score", "relevance_score", "recommendation_score"} & fields)


class LoaderFailFastTest(unittest.TestCase):
    def test_duplicate_node_id_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nodes.jsonl"
            path.write_text(
                json.dumps({"node_id": "trait_x", "node_type": "Trait", "label": "a"}) + "\n"
                + json.dumps({"node_id": "trait_x", "node_type": "Trait", "label": "b"}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(DuplicateNodeIdError):
                load_knowledge_subgraph_nodes(path)

    def test_dangling_edge_reference_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            edges_path = Path(tmp) / "edges.jsonl"
            edges_path.write_text(
                json.dumps(
                    {
                        "source_node_id": "major_ghost",
                        "target_node_id": "group_ghost",
                        "relation_type": "MAJOR_TO_GROUP",
                        "evidence_refs": ["x"],
                        "mapping_version": "v1",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(DanglingEdgeReferenceError):
                load_knowledge_subgraph_edges(edges_path, known_node_ids={"major_real"})


class RealSubgraphInvariantsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.nodes = load_knowledge_subgraph_nodes()
        self.edges = load_knowledge_subgraph_edges()
        self.majors = load_service_canonical_majors_v2()

    def test_trait_node_count_is_24(self) -> None:
        self.assertEqual(sum(1 for n in self.nodes if n.node_type == "Trait"), 24)

    def test_major_node_count_is_39(self) -> None:
        self.assertEqual(sum(1 for n in self.nodes if n.node_type == "Major"), 39)

    def test_every_active_major_has_a_node(self) -> None:
        major_node_ids = {n.node_id for n in self.nodes if n.node_type == "Major"}
        expected = {f"major_{m.major_id}" for m in self.majors}
        self.assertEqual(major_node_ids, expected)

    def test_no_orphan_major_nodes(self) -> None:
        """지시서 §5 "고아 Major 노드 0" — 모든 Major는 최소 1개 Edge의 source다."""

        major_node_ids = {n.node_id for n in self.nodes if n.node_type == "Major"}
        connected = {e.source_node_id for e in self.edges if e.source_node_id in major_node_ids}
        self.assertEqual(major_node_ids - connected, set())

    def test_every_edge_has_evidence(self) -> None:
        """지시서 §5 "근거 없는 Edge 0"."""

        self.assertTrue(all(e.evidence_refs for e in self.edges))
        self.assertTrue(all(all(ref.strip() for ref in e.evidence_refs) for e in self.edges))

    def test_no_dangling_node_references(self) -> None:
        node_ids = {n.node_id for n in self.nodes}
        for edge in self.edges:
            self.assertIn(edge.source_node_id, node_ids)
            self.assertIn(edge.target_node_id, node_ids)

    def test_hci_ux_has_no_department_edge(self) -> None:
        """지시서 "computer_science Group 전체를 hci_ux로 연결 금지" — 개별 학과
        검토가 이번 라운드에 없으므로 hci_ux는 Department Edge가 0이어야 한다."""

        hci_edges = [e for e in self.edges if e.source_node_id == "major_hci_ux"]
        self.assertFalse(any(e.relation_type == "MAJOR_TO_DEPARTMENT" for e in hci_edges))
        self.assertTrue(hci_edges, "hci_ux는 Trait/Subject Edge로 고아가 아니어야 한다")

    def test_hci_ux_has_no_group_edge(self) -> None:
        """hci_ux는 DEPARTMENT_LEVEL_ONLY라 어느 Group에도 통째로 연결되지 않는다."""

        hci_edges = [e for e in self.edges if e.source_node_id == "major_hci_ux"]
        self.assertFalse(any(e.relation_type == "MAJOR_TO_GROUP" for e in hci_edges))

    def test_design_major_has_no_node(self) -> None:
        major_node_ids = {n.node_id for n in self.nodes if n.node_type == "Major"}
        self.assertNotIn("major_design", major_node_ids)

    def test_trait_to_major_edges_reflect_final_39_major_profiles(self) -> None:
        """지시서(a/final-39-major-integration) §5 "TRAIT_TO_MAJOR가 최종 Profile
        39개를 반영" — 옛 3개 Major(EVIDENCED 근거 파일 시절)만 남아 있으면 안 된다."""

        trait_edges = [e for e in self.edges if e.relation_type == "TRAIT_TO_MAJOR"]
        majors_with_trait_edges = {e.target_node_id.removeprefix("major_") for e in trait_edges}
        self.assertEqual(majors_with_trait_edges, {m.major_id for m in self.majors})
        for edge in trait_edges:
            self.assertEqual(edge.mapping_version, "major_profile_v2.0")

    def test_major_to_department_edges_reflect_final_5595_row_master(self) -> None:
        """지시서 §5 "MAJOR_TO_DEPARTMENT가 최종 Master를 반영" — 옛 1,072건/8개
        Major 산출물이 남아 있으면 안 된다."""

        dept_edges = [e for e in self.edges if e.relation_type == "MAJOR_TO_DEPARTMENT"]
        self.assertEqual(len(dept_edges), 5595)
        majors_with_dept_edges = {e.source_node_id.removeprefix("major_") for e in dept_edges}
        self.assertEqual(len(majors_with_dept_edges), 38)

    def test_major_to_subject_edges_reflect_final_subject_mapping_v2(self) -> None:
        """지시서 §5 "MAJOR_TO_SUBJECT가 최종 Subject Mapping을 반영" — 옛
        subjects.jsonl(18개)·subject_major_link_evidence.jsonl(Legacy) 산출물이
        남아 있으면 안 된다."""

        subject_nodes = {n.node_id for n in self.nodes if n.node_type == "Subject"}
        self.assertEqual(len(subject_nodes), 41, "과목 노드는 subject_profiles_v2.jsonl(41개) 기준이어야 한다")
        subject_edges = [e for e in self.edges if e.relation_type == "MAJOR_TO_SUBJECT"]
        self.assertTrue(all(e.target_node_id in subject_nodes for e in subject_edges))


class GenerationDeterminismTest(unittest.TestCase):
    def test_regenerating_subgraph_is_byte_identical(self) -> None:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--", "data/knowledge_subgraph/"],
            cwd=_REPO_ROOT, capture_output=True, text=True,
        )
        before_status = proc.stdout
        before_nodes = _NODES_PATH.read_bytes()
        before_edges = _EDGES_PATH.read_bytes()

        result = subprocess.run(
            ["./.venv/bin/python", "scripts/career_build_knowledge_subgraph.py"],
            cwd=_REPO_ROOT, capture_output=True, text=True, env={"PYTHONPATH": ".", "PATH": "/usr/bin:/bin"},
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        self.assertEqual(before_nodes, _NODES_PATH.read_bytes())
        self.assertEqual(before_edges, _EDGES_PATH.read_bytes())

        proc_after = subprocess.run(
            ["git", "status", "--porcelain", "--", "data/knowledge_subgraph/"],
            cwd=_REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(before_status, proc_after.stdout)

    def test_regeneration_is_independent_of_pythonhashseed(self) -> None:
        """지시서 §5 "서로 다른 PYTHONHASHSEED에서 byte-identical"."""

        before_nodes = _NODES_PATH.read_bytes()
        before_edges = _EDGES_PATH.read_bytes()

        result = subprocess.run(
            ["./.venv/bin/python", "scripts/career_build_knowledge_subgraph.py"],
            cwd=_REPO_ROOT, capture_output=True, text=True,
            env={"PYTHONPATH": ".", "PATH": "/usr/bin:/bin", "PYTHONHASHSEED": "999"},
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before_nodes, _NODES_PATH.read_bytes())
        self.assertEqual(before_edges, _EDGES_PATH.read_bytes())


class RuntimeUntouchedTest(unittest.TestCase):
    """지시서 "Runtime 중앙 파일 수정 금지" — 이 작업이 다음 파일을 전혀 바꾸지 않았는지
    origin/trait-vector-v2 대비 확인한다.

    2026-08-25 갱신(a/final-39-major-integration, 5-way 병합) — a/major-profiles-v2-38이
    이 Subgraph 브랜치 위에 합쳐지면서 `src/api/main.py`가 39개 MajorProfile 배선으로
    실제로 바뀌었다(Major Matching/Course Upload 검증 — Knowledge Subgraph와 무관, git
    diff로 직접 확인함). 그 작업 자체의 "Runtime 배선" 범위이므로 이 목록에서 뺀다 —
    Subgraph가 실제로 절대 건드리면 안 되는 두 파일(Runtime의 세션별 동적 Subgraph
    서비스·그 계약 Schema)만 계속 검사한다."""

    def test_runtime_wiring_files_have_zero_diff(self) -> None:
        proc = subprocess.run(
            [
                "git", "diff", "--name-only", "origin/trait-vector-v2...HEAD", "--",
                "src/services/knowledge_subgraph_service.py",
                "src/schemas/graph.py",
            ],
            cwd=_REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "", "Runtime 중앙 파일이 이 브랜치에서 바뀌었다")


if __name__ == "__main__":
    unittest.main()
