"""GET /subgraph 실제 Full Flow E2E — 2026-08-28 19차 리뷰 §12 "실제 Full Flow E2E".

Mock Trait Summary를 직접 주입하지 않는다 — `tests/test_post_offering_full_flow_e2e.py`
(17차)가 이미 검증해 둔, 실제 관심도·Context 선택·옵션[0] 고정 선택 패턴이 결정론적으로
industrial_engineering을 "관련성 높음"으로 수렴시킨다는 사실을 그대로 재사용한다:

    POST /assessment/session → 관심도·Context 선택·확정 → 실제 질문·답변 반복
    → GET /profile → GET /majors → 대표 전공 선택 → 실제 학과 조회
    → 학교 편제표 업로드(demo_school_offerings.xlsx) → 개설과목 Confirm
    → POST_OFFERING 추천 → GET /subgraph/{session_id}

`_llm_client`/`_tracer`를 강제로 꺼서 실제 LLM·LangSmith 네트워크 호출이 전혀 없다.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.api.main as main_module
from src.api.main import app
from src.tracing.tracer import Tracer

client = TestClient(app)

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "data" / "fixtures" / "course_offerings" / "demo_school_offerings.xlsx"
)
_XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_MAX_TURNS = 30


class SubgraphFullFlowEndToEndTest(unittest.TestCase):
    def setUp(self) -> None:
        for patch_target in (
            patch.object(main_module, "_llm_client", None),
            patch.object(main_module, "_tracer", Tracer(client=None)),
        ):
            patch_target.start()
            self.addCleanup(patch_target.stop)

    def test_full_flow_produces_a_real_evidence_grounded_subgraph(self) -> None:
        self.assertTrue(_FIXTURE_PATH.exists(), f"Fixture가 없다: {_FIXTURE_PATH}")

        # 1. 세션 생성
        r = client.post("/assessment/session")
        self.assertEqual(r.status_code, 200)
        session_id = r.json()["session_id"]

        # 2~4. 관심도·Context 선택·확정 — industrial_engineering으로 결정론적으로
        # 수렴하는 것이 검증된 패턴(17차)을 그대로 재사용한다.
        r = client.post(
            "/assessment/interest-rating",
            json={
                "session_id": session_id,
                "ratings": {"game": 3, "media": 3, "school_life": 5, "business": 2, "making": 2},
            },
        )
        self.assertEqual(r.status_code, 200)
        r = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["school_life", "game"]},
        )
        self.assertEqual(r.status_code, 200)
        r = client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["school_life", "game", "media"]},
        )
        self.assertEqual(r.status_code, 200)

        # 5~6. 질문↔답변 반복 — 항상 첫 번째 선택지.
        for _turn in range(_MAX_TURNS):
            r = client.post("/assessment/next-question", params={"session_id": session_id})
            self.assertEqual(r.status_code, 200, r.text)
            body = r.json()
            if body["status"] == "CONTEXT_EARLY_TERMINATED":
                if body["assessment_complete"]:
                    break
                continue
            question = body["question"]
            option = question["options"][0]
            ar = client.post(
                "/assessment/answer",
                json={
                    "session_id": session_id,
                    "question_id": question["question_id"],
                    "selected_option_id": option["option_id"],
                },
            )
            self.assertEqual(ar.status_code, 200, ar.text)
            if ar.json()["next_action"] == "ASSESSMENT_COMPLETE":
                break

        # 7. Career Profile 생성 확인.
        r = client.get(f"/profile/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)

        # 8. 실제 대표 전공 추천. 이 세션은 industrial_engineering뿐 아니라 다른 대표
        # 전공도 함께 "관련성 높음"/"함께 탐색해볼 분야"로 추천될 수 있다 — Subgraph는
        # 그 전부를 CanonicalMajor Node로 포함하므로(§5), 이후 학과 비교도 추천된 대표
        # 전공 전부를 대상으로 한다.
        r = client.get(f"/majors/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        majors_body = r.json()
        recommended_major_ids = sorted(
            {m["major_id"] for m in majors_body["relevant_majors"]}
            | {m["major_id"] for m in majors_body["explore_together_majors"]}
        )
        self.assertIn("industrial_engineering", recommended_major_ids)
        selected_major_id = "industrial_engineering"

        # 9. 실제 학과 조회(화면의 "자세히 보기"와 같은 행동) — 추천된 대표 전공 전부에
        # 대해 조회해 Subgraph의 Department Node 집합과 정확히 비교할 기준을 만든다.
        real_departments: list[dict] = []
        for major_id in recommended_major_ids:
            r = client.get(f"/departments/{major_id}")
            self.assertEqual(r.status_code, 200, r.text)
            real_departments.extend(r.json()["departments"])
        self.assertTrue(real_departments, "추천된 대표 전공에 연결된 실제 학과가 있어야 한다")

        # 10. 학교 편제표 업로드.
        with open(_FIXTURE_PATH, "rb") as f:
            file_bytes = f.read()
        r = client.post(
            "/course/upload",
            data={"session_id": session_id, "selected_major_id": selected_major_id},
            files={"file": ("demo_school_offerings.xlsx", file_bytes, _XLSX_CONTENT_TYPE)},
        )
        self.assertEqual(r.status_code, 200, r.text)
        candidates = r.json()["parsed_candidates"]
        matched_ids = sorted({c["matched_subject_id"] for c in candidates if c["matched_subject_id"]})
        self.assertTrue(matched_ids)

        # 11. 개설과목 Confirm.
        r = client.post(
            "/course/confirm", json={"session_id": session_id, "confirmed_subject_ids": matched_ids}
        )
        self.assertEqual(r.status_code, 200, r.text)
        post_offering = r.json()["course_profile"]
        self.assertEqual(post_offering["source"], "POST_OFFERING")

        # 12. GET /subgraph/{session_id}.
        r = client.get(f"/subgraph/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        graph = r.json()
        self.assertEqual(graph["session_id"], session_id)
        nodes = graph["nodes"]
        edges = graph["edges"]
        node_by_id = {n["node_id"]: n for n in nodes}

        # --- 필수 확인 ---

        # Student Node 존재.
        student_nodes = [n for n in nodes if n["node_type"] == "Student"]
        self.assertEqual(len(student_nodes), 1)
        self.assertEqual(student_nodes[0]["label"], "학생")

        # 실제 Trait Node 존재.
        trait_nodes = [n for n in nodes if n["node_type"] == "Trait"]
        self.assertTrue(trait_nodes)

        # 실제 추천 전공 Node 존재(industrial_engineering).
        self.assertIn("major_industrial_engineering", node_by_id)
        self.assertEqual(node_by_id["major_industrial_engineering"]["node_type"], "CanonicalMajor")

        # 해당 전공의 승인된 실제 대학·학과 Node 존재 — GET /departments가 돌려준 것과
        # 정확히 같은 department_id 집합이어야 한다(같은 정책을 재사용했다는 증거).
        graph_department_ids = {n["node_id"] for n in nodes if n["node_type"] == "Department"}
        expected_department_ids = {d["department_id"] for d in real_departments}
        self.assertEqual(graph_department_ids, expected_department_ids)
        self.assertTrue(any(n["node_type"] == "University" for n in nodes))

        # 실제 확정 추천 과목 Node 존재 — post_offering.recommendations와 정확히 일치.
        graph_subject_ids = {n["node_id"] for n in nodes if n["node_type"] == "HighSchoolSubject"}
        expected_subject_ids = {item["subject_id"] for item in post_offering["recommendations"]}
        self.assertTrue(expected_subject_ids, "POST_OFFERING 추천이 비어 있으면 안 된다")
        self.assertEqual(graph_subject_ids, expected_subject_ids)
        for subject_id in graph_subject_ids:
            self.assertEqual(
                node_by_id[subject_id]["label"],
                next(item["label"] for item in post_offering["recommendations"] if item["subject_id"] == subject_id),
            )

        # Student→Trait→Major→Department/University 연결 존재.
        has_trait_edges = [e for e in edges if e["relation_type"] == "HAS_TRAIT"]
        self.assertTrue(has_trait_edges)
        trait_to_major_edges = [
            e for e in edges if e["relation_type"] == "RELATED_TO" and e["target_node_id"] == "major_industrial_engineering"
        ]
        self.assertTrue(trait_to_major_edges)
        major_to_department_edges = [
            e for e in edges if e["relation_type"] == "HAS_DEPARTMENT" and e["source_node_id"] == "major_industrial_engineering"
        ]
        self.assertTrue(major_to_department_edges)
        department_to_university_edges = [e for e in edges if e["relation_type"] == "BELONGS_TO"]
        self.assertTrue(department_to_university_edges)

        # Trait→Subject 연결 존재(최소 한 과목이 EVIDENCED Trait로 이어져 있어야 한다).
        trait_to_subject_edges = [
            e for e in edges if e["relation_type"] == "RELATED_TO" and e["target_node_id"] in graph_subject_ids
        ]
        self.assertTrue(trait_to_subject_edges)

        # RECOMMENDS는 확정 전공에서만 나간다.
        recommends_edges = [e for e in edges if e["relation_type"] == "RECOMMENDS"]
        self.assertTrue(recommends_edges)
        for edge in recommends_edges:
            self.assertEqual(edge["source_node_id"], "major_industrial_engineering")

        # 교과(군)·정체불명 과목ABC는 Subgraph 어디에도 없어야 한다(Parser 잡음/unmatched
        # 후보는 애초에 course_profile.recommendations에 들어가지 않는다 — 18차 정정 이후).
        full_text = str(graph)
        self.assertNotIn("교과(군)", full_text)
        self.assertNotIn("정체불명 과목ABC", full_text)
        self.assertNotIn("예시대학교", full_text)
        self.assertNotIn("dept_mock", full_text)

        # 고아 Edge 없음.
        node_ids = set(node_by_id)
        for edge in edges:
            self.assertIn(edge["source_node_id"], node_ids)
            self.assertIn(edge["target_node_id"], node_ids)

        # Node/Edge 중복 없음.
        self.assertEqual(len(node_ids), len(nodes))
        edge_keys = [(e["source_node_id"], e["target_node_id"], e["relation_type"]) for e in edges]
        self.assertEqual(len(edge_keys), len(set(edge_keys)))

        # 내부 float 점수 미노출.
        def _assert_no_float(node) -> None:
            if isinstance(node, float):
                self.fail(f"float 값이 노출됨: {node}")
            elif isinstance(node, dict):
                for value in node.values():
                    _assert_no_float(value)
            elif isinstance(node, list):
                for value in node:
                    _assert_no_float(value)

        _assert_no_float(graph)


if __name__ == "__main__":
    unittest.main()
