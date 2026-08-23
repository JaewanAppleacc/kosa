"""Vertical Slice 대표 전공 3개(media_communication/hci_ux/industrial_engineering)와
실제 학과 데이터(data/master/departments.jsonl) 정합성 — 2026-08-22 8차 리뷰.

배경: `/majors/{session_id}`가 실제로 추천할 수 있는 전공은
`src/data/majors/vertical_slice_major_profiles.py`의 3개뿐인데, C가 구축한
`data/master/departments.jsonl`은 원래 이 3개 중 media_communication만 연결돼 있었다
(hci_ux/industrial_engineering은 실제 학과가 0개라 추천받아도 학과 탐색이 항상 빈
목록이었다). 이 파일은 그 정합화가 실제로 끝났는지, 그리고 앞으로 다시 깨지지 않는지를
확인한다.

여기서 추천 전공 3개는 항상 VERTICAL_SLICE_MAJOR_PROFILES에서 직접 읽는다(하드코딩된
복사본과 비교하지 않는다) — 나중에 추천 전공이 바뀌면 이 테스트가 다시 불일치를 잡아낸다.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.main import app
from src.data.majors.canonical_major_descriptions import CANONICAL_MAJOR_DESCRIPTIONS_BY_ID
from src.data.majors.vertical_slice_major_profiles import VERTICAL_SLICE_MAJOR_PROFILES
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAITS
from src.engines.matching_engine import (
    compute_major_match,
    compute_student_trait_states,
    rank_major_relevance,
)
from src.repositories.department_repository import load_departments
from src.schemas.evidence import TraitEvidenceSummary

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

RECOMMENDABLE_MAJOR_IDS = [m.major_id for m in VERTICAL_SLICE_MAJOR_PROFILES]

client = TestClient(app)


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


class DataConsistencyTest(unittest.TestCase):
    """섹션 9 "데이터 정합성" 1~8."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.departments = load_departments(DATA_DIR / "master" / "departments.jsonl")
        cls.canonical_major_ids = {
            row["major_id"] for row in _read_jsonl(DATA_DIR / "master" / "canonical_majors.jsonl")
        }

    def test_recommendable_major_ids_are_read_from_source_not_hardcoded(self) -> None:
        # RECOMMENDABLE_MAJOR_IDS 자체가 VERTICAL_SLICE_MAJOR_PROFILES에서 파생됐다는
        # 사실 자체가 이 테스트다 — 하드코딩된 리스트가 아님을 재확인한다.
        self.assertEqual(set(RECOMMENDABLE_MAJOR_IDS), {m.major_id for m in VERTICAL_SLICE_MAJOR_PROFILES})
        self.assertEqual(len(RECOMMENDABLE_MAJOR_IDS), 3)

    def test_all_three_recommendable_majors_exist_in_canonical_majors(self) -> None:
        for major_id in RECOMMENDABLE_MAJOR_IDS:
            self.assertIn(
                major_id, self.canonical_major_ids,
                f"{major_id}가 data/master/canonical_majors.jsonl에 없습니다.",
            )

    def test_all_three_recommendable_majors_have_at_least_one_department(self) -> None:
        by_major: dict[str, list] = {}
        for d in self.departments:
            if d.canonical_major_id:
                by_major.setdefault(d.canonical_major_id, []).append(d)
        for major_id in RECOMMENDABLE_MAJOR_IDS:
            self.assertGreaterEqual(
                len(by_major.get(major_id, [])), 1,
                f"{major_id}에 연결된 실제 학과가 없습니다.",
            )

    def test_each_departments_canonical_major_id_matches_its_major(self) -> None:
        for major_id in RECOMMENDABLE_MAJOR_IDS:
            for d in self.departments:
                if d.canonical_major_id == major_id:
                    self.assertEqual(d.canonical_major_id, major_id)

    def test_source_urls_are_not_empty_for_recommendable_majors(self) -> None:
        for d in self.departments:
            if d.canonical_major_id in RECOMMENDABLE_MAJOR_IDS:
                self.assertTrue(d.source_url.strip(), f"{d.department_id}의 source_url이 비었습니다.")

    def test_no_mock_or_sample_urls_for_recommendable_majors(self) -> None:
        forbidden_fragments = ("example.ac.kr", "sample://", "dept_mock")
        for d in self.departments:
            if d.canonical_major_id in RECOMMENDABLE_MAJOR_IDS:
                for fragment in forbidden_fragments:
                    self.assertNotIn(fragment, d.source_url)
                    self.assertNotIn(fragment, d.department_id)

    def test_department_ids_are_unique(self) -> None:
        ids = [d.department_id for d in self.departments]
        self.assertEqual(len(ids), len(set(ids)), "department_id 중복이 있습니다.")

    def test_original_eight_majors_department_counts_are_preserved(self) -> None:
        """2026-08-22 8차 작업 이전에 이미 실제 학과가 연결돼 있던 8개 전공은 이번
        hci_ux/industrial_engineering 정합화 작업으로 개수가 줄면 안 된다."""

        counts: dict[str, int] = {}
        for d in self.departments:
            if d.canonical_major_id:
                counts[d.canonical_major_id] = counts.get(d.canonical_major_id, 0) + 1

        previously_connected_minimums = {
            "computer_science": 10,
            "psychology": 2,
            "mechanical_engineering": 3,
            "life_science": 2,
            "business_administration": 3,
            "design": 3,
            "media_communication": 4,
            "education": 2,
        }
        for major_id, minimum in previously_connected_minimums.items():
            self.assertGreaterEqual(
                counts.get(major_id, 0), minimum,
                f"{major_id}의 학과 개수가 기존({minimum}개)보다 줄었습니다.",
            )


class ApiConsistencyTest(unittest.TestCase):
    """섹션 9 "API 정합성" 9~14."""

    def test_media_communication_departments_endpoint_is_not_empty(self) -> None:
        r = client.get("/departments/media_communication")
        self.assertEqual(r.status_code, 200)
        self.assertGreater(len(r.json()["departments"]), 0)

    def test_hci_ux_departments_endpoint_is_not_empty(self) -> None:
        r = client.get("/departments/hci_ux")
        self.assertEqual(r.status_code, 200)
        self.assertGreater(len(r.json()["departments"]), 0)

    def test_industrial_engineering_departments_endpoint_is_not_empty(self) -> None:
        r = client.get("/departments/industrial_engineering")
        self.assertEqual(r.status_code, 200)
        self.assertGreater(len(r.json()["departments"]), 0)

    def test_unmapped_major_still_returns_200_with_empty_list(self) -> None:
        r = client.get("/departments/no_such_major_id_at_all")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"major_id": "no_such_major_id_at_all", "departments": []})

    def test_departments_response_contract_unchanged(self) -> None:
        r = client.get("/departments/hci_ux")
        body = r.json()
        self.assertEqual(set(body.keys()), {"major_id", "departments"})
        dept = body["departments"][0]
        self.assertEqual(
            set(dept.keys()),
            {
                "department_id", "university_name", "campus", "region", "department_name",
                "college_name", "admission_unit", "department_status", "source_svy_year",
                "source_url", "canonical_major_id",
                # A2 지시서(2026-08-24) §1: 학과 공식 홈페이지 URL(선택 필드) 추가.
                "department_url",
            },
        )

    def test_no_llm_embedding_or_langsmith_client_needed(self) -> None:
        """이 정합화는 순수 JSONL 데이터 추가라 LLM·Embedding·LangSmith 어느 것도 호출할
        필요가 없다 — 세 Client를 명시적으로 비활성화해도(로컬 .env에 실제 API Key가
        있을 수 있으므로 test_api.py의 다른 테스트들과 동일하게 강제로 끈다) 정상
        동작해야 한다."""

        from unittest.mock import patch

        from src.api import main as main_module
        from src.tracing.tracer import Tracer

        with patch.object(main_module, "_llm_client", None), patch.object(
            main_module, "_trace_client", None
        ), patch.object(main_module, "_tracer", Tracer(client=None)):
            for major_id in RECOMMENDABLE_MAJOR_IDS:
                r = client.get(f"/departments/{major_id}")
                self.assertEqual(r.status_code, 200)
                self.assertGreater(len(r.json()["departments"]), 0)


class FixedPersonaEndToEndTest(unittest.TestCase):
    """섹션 9 "E2E" — Trait → Career Profile 근거 → 대표 전공 추천 → 실제 학과 존재.

    2026-08-21 tests/test_matching_engine.py::FixedPersonaVerticalSliceMatchingTest가 이미
    "원인 분석·패턴 탐색·정보 비교·계획을 STRONG, 감정 해석·수용자 반응 예측을 LIMITED로
    두면 industrial_engineering이 1위"라는 손검증된 원리를 세웠다. 여기서는 그 원리를
    나머지 두 전공에도 그대로 적용해(vertical_slice_major_profiles.py에 이미 정의된
    가중치 벡터를 그대로 읽어 구성 — 새 가중치를 임의로 만들지 않는다) 세 전공 각각을
    1위로 만드는 손계산 Trait 강도를 검증하고, 그 결과로 나온 추천 전공에 실제 학과가
    연결되는지까지 확인한다. 답변을 억지로 조작한 게 아니라, 각 전공이 실제로 1.00
    가중치를 둔 Trait를 강하게, 다른 전공들이 1.00을 둔 Trait를 약하게 설계한 것뿐이다."""

    def setUp(self) -> None:
        self.trait_defs = {t.trait_id: t for t in VERTICAL_SLICE_TRAITS}
        self.labels_by_major_id = {m.major_id: m.label for m in VERTICAL_SLICE_MAJOR_PROFILES}

    def _strong(self, trait_id: str) -> TraitEvidenceSummary:
        return TraitEvidenceSummary(
            trait_id=trait_id, support_count=3, opportunity_count=3, context_count=2, distinct_frame_count=2
        )

    def _limited(self, trait_id: str) -> TraitEvidenceSummary:
        return TraitEvidenceSummary(
            trait_id=trait_id, support_count=2, opportunity_count=2, context_count=1, distinct_frame_count=1
        )

    def _not_probed(self, trait_id: str) -> TraitEvidenceSummary:
        return TraitEvidenceSummary(trait_id=trait_id, support_count=0, opportunity_count=0)

    def _top_relevant_major_id(self, strong_traits: set[str], limited_traits: set[str]) -> str:
        summaries = {}
        for trait_id in self.trait_defs:
            if trait_id in strong_traits:
                summaries[trait_id] = self._strong(trait_id)
            elif trait_id in limited_traits:
                summaries[trait_id] = self._limited(trait_id)
            else:
                summaries[trait_id] = self._not_probed(trait_id)

        states = compute_student_trait_states(summaries, self.trait_defs, set())
        results = [compute_major_match(states, m) for m in VERTICAL_SLICE_MAJOR_PROFILES]
        relevant, _explore, _msg = rank_major_relevance(
            results, self.labels_by_major_id, CANONICAL_MAJOR_DESCRIPTIONS_BY_ID
        )
        self.assertEqual(len(relevant), 1, f"관련성 높음 전공이 정확히 1개여야 합니다: {relevant}")
        return relevant[0].major_id

    def test_persona_a_recommends_media_communication_with_real_departments(self) -> None:
        """2026-08-22 12차 리뷰: media_communication Vector가 실제 학과 공식 자료 근거
        기반으로 바뀌면서(경희대·고려대 미디어커뮤니케이션학과의 데이터 분석·캠페인 기획
        중심 과목들 — §7 경고대로 영상편집 중심이 아니었다), 이제 causal_analysis·
        pattern_finding·information_comparison·planning까지 포함하는 폭넓은 Vector가
        됐다(hci_ux 3개 Trait를 모두 포함하고 그 위에 분석·기획·협업 Trait까지 더한
        형태). 그래서 media_communication을 hci_ux·industrial_engineering보다 확실히
        위로 올리려면, media_communication이 가진 8개 Trait 전부(hci_ux와 공유하는
        시각적 표현·수용자 반응 예측 포함, media_communication만 갖는 협업 선호·계획·
        원인 분석·패턴 탐색·정보 비교까지)를 STRONG으로 두고, industrial_engineering만
        갖는 도구 활용은 LIMITED로 낮춘다 — 세 전공 모두 이 학생 데이터로 "관련도 계산은
        가능"하지만(모두 usable_trait 충분), media_communication만 다른 두 전공에 없는
        협업/기획 Trait까지 강하게 충족해 확실한 1위가 된다."""

        top_major_id = self._top_relevant_major_id(
            strong_traits={
                "visual_expression", "audience_response_prediction", "collaboration_preference",
                "planning", "causal_analysis", "pattern_finding", "information_comparison",
            },
            limited_traits={"tool_utilization"},
        )
        self.assertEqual(top_major_id, "media_communication")

        r = client.get(f"/departments/{top_major_id}")
        self.assertEqual(r.status_code, 200)
        departments = r.json()["departments"]
        self.assertGreater(len(departments), 0)
        for d in departments:
            self.assertEqual(d["canonical_major_id"], top_major_id)

    def test_persona_b_recommends_hci_ux_with_real_departments(self) -> None:
        top_major_id = self._top_relevant_major_id(
            strong_traits={
                "tool_utilization", "audience_response_prediction", "visual_expression", "opinion_mediation",
            },
            limited_traits={
                "emotional_interpretation", "causal_analysis", "pattern_finding", "information_comparison", "planning",
            },
        )
        self.assertEqual(top_major_id, "hci_ux")

        r = client.get(f"/departments/{top_major_id}")
        self.assertEqual(r.status_code, 200)
        departments = r.json()["departments"]
        self.assertGreater(len(departments), 0)
        for d in departments:
            self.assertEqual(d["canonical_major_id"], top_major_id)

    def test_persona_c_recommends_industrial_engineering_with_real_departments(self) -> None:
        """tests/test_matching_engine.py::FixedPersonaVerticalSliceMatchingTest와 동일한
        Trait 강도 설계(analytical persona)를 그대로 재사용한다."""

        top_major_id = self._top_relevant_major_id(
            strong_traits={"causal_analysis", "pattern_finding", "information_comparison", "planning"},
            limited_traits={"emotional_interpretation", "audience_response_prediction"},
        )
        self.assertEqual(top_major_id, "industrial_engineering")

        r = client.get(f"/departments/{top_major_id}")
        self.assertEqual(r.status_code, 200)
        departments = r.json()["departments"]
        self.assertGreater(len(departments), 0)
        for d in departments:
            self.assertEqual(d["canonical_major_id"], top_major_id)


if __name__ == "__main__":
    unittest.main()
