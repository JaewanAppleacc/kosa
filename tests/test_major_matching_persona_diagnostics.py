"""2026-08-23 13차 리뷰 §4 — 고정 Persona 매칭 진단 회귀 테스트.

`outputs/evaluation/major_matching_persona_report.md`에 기록된 두 가지 알려진 동점 현상
(HCI 관련 Trait 강함 → hci_ux/media_communication 동점, 분석 Trait 강함 →
industrial_engineering/media_communication 동점)은 매칭 공식 버그가 아니라 실제 근거
데이터의 구조적 결과라고 리포트에서 분석했다 — 이 테스트는 "이 현상이 계속 그대로
관찰된다"를 회귀로 고정한다. 벡터가 바뀌어 이 현상이 사라지거나 등장하면 이 테스트가
깨져서, 리포트를 다시 생성해 비교해야 한다는 신호를 준다(§13 25번과 같은 취지).

이 파일은 매칭 공식(src/engines/matching_engine.py)을 절대 수정하지 않는다 — 있는 그대로
호출한 결과를 관찰만 한다.
"""

from __future__ import annotations

import unittest

from eval.major_matching_persona_diagnostics import PERSONAS, diagnose_persona
from src.data.majors.vertical_slice_major_profiles import VERTICAL_SLICE_MAJOR_PROFILES
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAITS


class PersonaDiagnosticsRegressionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.trait_defs = {t.trait_id: t for t in VERTICAL_SLICE_TRAITS}
        self.results_by_id = {
            persona.persona_id: diagnose_persona(persona, VERTICAL_SLICE_MAJOR_PROFILES, self.trait_defs)
            for persona in PERSONAS
        }

    def _score(self, persona_id: str, major_id: str) -> float | None:
        result = self.results_by_id[persona_id]
        return next(row.score for row in result.majors if row.major_id == major_id)

    def test_seven_required_personas_are_defined(self) -> None:
        self.assertEqual(
            {p.persona_id for p in PERSONAS},
            {
                "analytical", "visual_user_facing", "planning_collaboration", "tool_only",
                "all_limited", "sparse_partial", "unresolved_conflict",
            },
        )

    def test_analytical_persona_ties_industrial_engineering_and_media_communication(self) -> None:
        """§14 사전 지적: 분석 Trait가 강하면 industrial_engineering과 media_communication이
        동점 가능 — 현재 근거 데이터에서 실제로 동점(score 1.0000)임을 고정한다."""

        result = self.results_by_id["analytical"]
        self.assertTrue(result.is_tied_for_first)
        self.assertEqual(set(result.relevant_major_ids), {"industrial_engineering", "media_communication"})
        self.assertEqual(
            self._score("analytical", "industrial_engineering"),
            self._score("analytical", "media_communication"),
        )

    def test_visual_user_facing_persona_ties_hci_ux_and_media_communication(self) -> None:
        """§14 사전 지적: HCI 관련 Trait가 강하면 hci_ux와 media_communication이 동점
        가능 — hci_ux의 3개 Trait가 media_communication에 동일한 가중치로 포함돼 있어서다."""

        result = self.results_by_id["visual_user_facing"]
        self.assertTrue(result.is_tied_for_first)
        self.assertEqual(set(result.relevant_major_ids), {"hci_ux", "media_communication"})
        self.assertEqual(
            self._score("visual_user_facing", "hci_ux"),
            self._score("visual_user_facing", "media_communication"),
        )

    def test_all_limited_persona_produces_uniform_low_scores_not_high_relevance(self) -> None:
        result = self.results_by_id["all_limited"]
        scores = {row.major_id: row.score for row in result.majors}
        self.assertTrue(all(status == "computed" for status in (row.status for row in result.majors)))
        self.assertEqual(len(set(scores.values())), 1)
        self.assertEqual(result.relevant_major_ids, [])

    def test_sparse_evidence_personas_are_insufficient_for_every_major(self) -> None:
        for persona_id in ("tool_only", "sparse_partial"):
            with self.subTest(persona_id=persona_id):
                result = self.results_by_id[persona_id]
                self.assertTrue(all(row.status == "insufficient" for row in result.majors))
                self.assertEqual(result.relevant_major_ids, [])

    def test_unresolved_conflict_masks_the_trait_without_treating_it_as_zero(self) -> None:
        """미해결 Conflict Trait(planning)는 major 벡터에 가중치가 있어도 usable에서
        완전히 빠져야 한다(0점으로 반영되는 게 아니라 분모·분자 양쪽에서 제외) — §12."""

        result = self.results_by_id["unresolved_conflict"]
        ie_row = next(r for r in result.majors if r.major_id == "industrial_engineering")
        # industrial_engineering 벡터는 causal_analysis/pattern_finding/information_comparison
        # (cognitive) + planning(work_style) + tool_utilization(environment) 5개인데,
        # planning이 Mask되면 cognitive 3개만 usable로 남아 그룹 수가 1로 떨어진다.
        self.assertEqual(ie_row.usable_trait_count, 3)
        self.assertEqual(ie_row.usable_vector_group_count, 1)
        self.assertEqual(ie_row.status, "insufficient")

    def test_planning_collaboration_persona_stays_below_usable_trait_threshold(self) -> None:
        result = self.results_by_id["planning_collaboration"]
        media_row = next(r for r in result.majors if r.major_id == "media_communication")
        self.assertEqual(media_row.usable_trait_count, 2)
        self.assertEqual(media_row.status, "insufficient")

    def test_report_generation_script_is_deterministic(self) -> None:
        from scripts.career_generate_major_matching_persona_report import render_report

        first = render_report(list(self.results_by_id.values()))
        second_results = [
            diagnose_persona(persona, VERTICAL_SLICE_MAJOR_PROFILES, self.trait_defs) for persona in PERSONAS
        ]
        second = render_report(second_results)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
