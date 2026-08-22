"""예체능 계열 학과 추천 제외 정책 — 2026-08-22 9차 리뷰.

사용자가 확정한 정책: "예체능 계열 대학 학과는 추천·탐색 대상에서 제외한다." 서울여자
대학교 산업디자인학과가 실제 UX 교육과정을 갖고 있어도, 학과 자체가 예체능(디자인)
계열이라 hci_ux 추천 대상에서 제외돼야 한다(직전 8차 리뷰에서 이 학과를 hci_ux로
confirm()한 결정을 취소한다). 관심 Context(미술·디자인/스포츠/미디어/패션·뷰티)는
이 정책과 별개로 그대로 유지한다 — Context에서 뽑는 Shared Trait와 "이 Context를
선택했다고 예체능 학과를 추천"하는 것은 다른 문제다.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.main import app
from src.data.contexts.context_definitions import CONTEXT_DEFINITIONS
from src.data.majors.vertical_slice_major_profiles import VERTICAL_SLICE_MAJOR_PROFILES
from src.repositories.department_repository import load_departments
from src.services.major_exploration_service import (
    EXCLUDED_RECOMMENDATION_MAJOR_IDS,
    MajorExplorationService,
)

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

SEOUL_WOMENS_INDUSTRIAL_DESIGN_DEPARTMENT_ID = "dept_05f004629e6e8f4060e286a9"

client = TestClient(app)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


class MappingRegressionTest(unittest.TestCase):
    """섹션 7 "Mapping 회귀 테스트" 1~5."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.departments = load_departments(DATA_DIR / "master" / "departments.jsonl")
        cls.by_id = {d.department_id: d for d in cls.departments}

    def test_seoul_womens_industrial_design_is_not_hci_ux(self) -> None:
        department = self.by_id[SEOUL_WOMENS_INDUSTRIAL_DESIGN_DEPARTMENT_ID]
        self.assertEqual(department.university_name, "서울여자대학교")
        self.assertEqual(department.department_name, "산업디자인학과")
        self.assertNotEqual(department.canonical_major_id, "hci_ux")

    def test_no_active_manual_confirmation_maps_it_to_hci_ux(self) -> None:
        manual = _read_jsonl(DATA_DIR / "master" / "canonical_mapping_manual_confirmations.jsonl")
        for entry in manual:
            if entry["department_id"] == SEOUL_WOMENS_INDUSTRIAL_DESIGN_DEPARTMENT_ID:
                self.assertNotEqual(
                    entry["chosen_major_id"], "hci_ux",
                    "산업디자인학과를 hci_ux로 확정하는 수동 기록이 아직 활성 상태입니다.",
                )

    def test_rebuilding_pipeline_does_not_remap_it_to_hci_ux(self) -> None:
        """빌드 파이프라인을 다시 돌려도(raw 데이터·canonical_majors.jsonl이 그대로면)
        같은 결과가 나와야 한다 — Exact-Alias가 우연히 다시 hci_ux를 만들어내지 않는다."""

        import os
        import subprocess
        import sys

        env = {**os.environ, "PYTHONPATH": str(ROOT)}
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "career_build_department_master.py")],
            cwd=ROOT, capture_output=True, text=True, env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        departments = load_departments(DATA_DIR / "master" / "departments.jsonl")
        by_id = {d.department_id: d for d in departments}
        self.assertNotEqual(
            by_id[SEOUL_WOMENS_INDUSTRIAL_DESIGN_DEPARTMENT_ID].canonical_major_id, "hci_ux"
        )

    def test_every_hci_ux_department_has_official_review_evidence(self) -> None:
        review_by_id = {
            row["department_id"]: row
            for row in _read_jsonl(DATA_DIR / "master" / "hci_ux_department_review.jsonl")
        }
        hci_ux_departments = [d for d in self.departments if d.canonical_major_id == "hci_ux"]
        self.assertGreater(len(hci_ux_departments), 0)
        for department in hci_ux_departments:
            self.assertIn(
                department.department_id, review_by_id,
                f"{department.university_name} {department.department_name}에 공식 검토 근거 기록이 없습니다.",
            )
            review = review_by_id[department.department_id]
            self.assertFalse(review["is_arts_or_pe"])
            self.assertTrue(review["hci_ux_curriculum_evidence"])
            self.assertTrue(review["source_url"].strip())

    def test_industrial_engineering_three_departments_are_preserved(self) -> None:
        ie_departments = {
            d.department_id: d for d in self.departments if d.canonical_major_id == "industrial_engineering"
        }
        self.assertEqual(len(ie_departments), 3)
        universities = {d.university_name for d in ie_departments.values()}
        self.assertEqual(universities, {"고려대학교", "경희대학교", "숭실대학교"})


class RecommendationScopeTest(unittest.TestCase):
    """섹션 7 "추천 범위 테스트" 6~10."""

    def test_design_is_not_in_vertical_slice_major_profiles(self) -> None:
        major_ids = {m.major_id for m in VERTICAL_SLICE_MAJOR_PROFILES}
        self.assertNotIn("design", major_ids)

    def test_majors_endpoint_never_recommends_an_excluded_major(self) -> None:
        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        r = client.get(f"/majors/{session_id}")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        all_major_ids = {m["major_id"] for m in body["relevant_majors"] + body["explore_together_majors"]}
        self.assertEqual(all_major_ids & EXCLUDED_RECOMMENDATION_MAJOR_IDS, set())

    def test_departments_hci_ux_does_not_contain_industrial_design(self) -> None:
        r = client.get("/departments/hci_ux")
        self.assertEqual(r.status_code, 200)
        names = [(d["university_name"], d["department_name"]) for d in r.json()["departments"]]
        self.assertNotIn(("서울여자대학교", "산업디자인학과"), names)

    def test_hci_ux_departments_are_not_in_arts_or_pe_colleges(self) -> None:
        excluded_college_fragments = ("예술대학", "미술대학", "디자인대학", "체육대학")
        r = client.get("/departments/hci_ux")
        for d in r.json()["departments"]:
            for fragment in excluded_college_fragments:
                self.assertNotIn(fragment, d["college_name"])

    def test_existing_media_and_industrial_engineering_lookups_still_work(self) -> None:
        r = client.get("/departments/media_communication")
        self.assertEqual(r.status_code, 200)
        self.assertGreater(len(r.json()["departments"]), 0)

        r = client.get("/departments/industrial_engineering")
        self.assertEqual(r.status_code, 200)
        self.assertGreater(len(r.json()["departments"]), 0)

    def test_departments_design_returns_empty_even_though_data_exists(self) -> None:
        """design 자체 학과 데이터는 여전히 존재하지만(삭제하지 않음), 추천 경로에서는
        노출되지 않아야 한다 — 존재 여부와 노출 여부를 구분한다."""

        repository_has_design_departments = any(
            d.canonical_major_id == "design"
            for d in load_departments(DATA_DIR / "master" / "departments.jsonl")
        )
        self.assertTrue(repository_has_design_departments, "design 학과 데이터 자체가 사라졌습니다.")

        r = client.get("/departments/design")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["departments"], [])


class ContextIndependenceTest(unittest.TestCase):
    """섹션 7 "Context 독립성 테스트" 11~12."""

    def test_arts_and_pe_related_contexts_are_not_deleted(self) -> None:
        labels = {c.label for c in CONTEXT_DEFINITIONS}
        for expected_label in ("미술·디자인", "스포츠", "미디어", "패션·뷰티"):
            self.assertIn(expected_label, labels)

    def test_selecting_an_arts_context_does_not_change_recommendable_major_ids(self) -> None:
        """미술·디자인 Context를 관심으로 선택해도(관심 Context ≠ 추천 학과 범위),
        /majors가 추천할 수 있는 대표 전공 목록 자체는 바뀌지 않는다 — 특정 Context
        선택이 예체능 전공을 직접 추천으로 바꾸는 로직이 없다는 뜻이다."""

        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        r = client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"art_design": 5, "media": 4}},
        )
        self.assertEqual(r.status_code, 200)

        r = client.get(f"/majors/{session_id}")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        all_major_ids = {m["major_id"] for m in body["relevant_majors"] + body["explore_together_majors"]}
        self.assertTrue(all_major_ids <= {m.major_id for m in VERTICAL_SLICE_MAJOR_PROFILES})
        self.assertEqual(all_major_ids & EXCLUDED_RECOMMENDATION_MAJOR_IDS, set())


if __name__ == "__main__":
    unittest.main()
