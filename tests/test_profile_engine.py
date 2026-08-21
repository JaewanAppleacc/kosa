"""Career Profile 계산(§13/§14 중 순수 Python 부분) 테스트."""

from __future__ import annotations

import unittest

from src.engines.profile_engine import (
    MAX_HIGHLIGHTS,
    MIN_HIGHLIGHTS,
    build_detailed_evidence_by_dimension,
    select_profile_highlight_traits,
)
from src.schemas.evidence import EvidenceOrigin, EvidenceRecord, TraitEvidenceSummary, TraitState
from src.schemas.trait import TraitDefinition


def _trait(trait_id: str, dimension: str = "테스트 차원") -> TraitDefinition:
    return TraitDefinition(
        trait_id=trait_id,
        label=trait_id,
        parent_dimension=dimension,
        definition="테스트용 정의",
        positive_indicators=["테스트 긍정 지표"],
        conflicting_indicators=["테스트 상충 지표"],
        source_references=["팀 정의 — 테스트"],
        trait_scope="shared",
        minimum_context_count=2,
        primary_vector_group="cognitive",
    )


def _strong_summary(trait_id: str) -> TraitEvidenceSummary:
    return TraitEvidenceSummary(
        trait_id=trait_id, support_count=3, opportunity_count=3, context_count=2, distinct_frame_count=2
    )


def _insufficient_summary(trait_id: str) -> TraitEvidenceSummary:
    return TraitEvidenceSummary(trait_id=trait_id, support_count=0, opportunity_count=0, context_count=0)


def _evidence(trait_id: str, context: str, option_text: str) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=f"ev_{trait_id}_{context}",
        answer_id=f"ans_{trait_id}_{context}",
        question_id=f"q_{trait_id}",
        question_frame_id="problem_check",
        option_role_id="some_role",
        option_text=option_text,
        applied_primary_trait_delta={trait_id: 1},
        evidence_origin=EvidenceOrigin.PRIMARY_BLUEPRINT,
        context=context,
        source_type="generated_question",
        generator_version="v1",
        quality_gate_status="passed",
    )


class SelectProfileHighlightTraitsTest(unittest.TestCase):
    def test_all_strong_traits_selected_up_to_max(self) -> None:
        """12개 전부 STRONG이면 8개까지만 잘라야 한다(§14 5~8줄 제약)."""

        trait_ids = [f"trait_{i:02d}" for i in range(12)]
        definitions = {tid: _trait(tid) for tid in trait_ids}
        summaries = {tid: _strong_summary(tid) for tid in trait_ids}

        selected = select_profile_highlight_traits(summaries, definitions, set())
        self.assertEqual(len(selected), MAX_HIGHLIGHTS)
        self.assertTrue(all(c.judgment.state == TraitState.STRONG for c in selected))

    def test_insufficient_traits_fill_up_to_minimum(self) -> None:
        """STRONG/MODERATE가 2개뿐이면 나머지를 INSUFFICIENT로 채워서 최소 5개를 맞춘다
        (§14 예시: "협업 방식은 아직 Evidence가 적어 추가 탐색이 필요해요")."""

        trait_ids = [f"trait_{i:02d}" for i in range(12)]
        definitions = {tid: _trait(tid) for tid in trait_ids}
        summaries = {tid: (_strong_summary(tid) if i < 2 else _insufficient_summary(tid))
                     for i, tid in enumerate(trait_ids)}

        selected = select_profile_highlight_traits(summaries, definitions, set())
        self.assertEqual(len(selected), MIN_HIGHLIGHTS)
        states = [c.judgment.state for c in selected]
        self.assertEqual(states.count(TraitState.STRONG), 2)
        self.assertEqual(states.count(TraitState.INSUFFICIENT), 3)

    def test_strong_ranked_before_moderate(self) -> None:
        definitions = {"a": _trait("a"), "b": _trait("b")}
        summaries = {
            "a": TraitEvidenceSummary(trait_id="a", support_count=2, opportunity_count=2, context_count=2, distinct_frame_count=2),  # MODERATE
            "b": _strong_summary("b"),  # STRONG
        }
        selected = select_profile_highlight_traits(summaries, definitions, set())
        # 5개 미만이라 나머지가 없는 Trait로 채워지긴 하지만, STRONG(b)이 항상 먼저 와야 한다.
        self.assertEqual(selected[0].trait_definition.trait_id, "b")
        self.assertEqual(selected[0].judgment.state, TraitState.STRONG)

    def test_unresolved_conflict_forces_conflicting_state(self) -> None:
        definitions = {"a": _trait("a")}
        summaries = {"a": _strong_summary("a")}
        selected = select_profile_highlight_traits(summaries, definitions, {"a"})
        self.assertEqual(selected[0].judgment.state, TraitState.CONFLICTING)


class BuildDetailedEvidenceByDimensionTest(unittest.TestCase):
    def test_groups_by_dimension_and_deduplicates(self) -> None:
        definitions = {"causal_analysis": _trait("causal_analysis", dimension="분석과 구조화")}
        summaries = {"causal_analysis": _strong_summary("causal_analysis")}
        candidates = select_profile_highlight_traits(summaries, definitions, set())

        ledger = [
            _evidence("causal_analysis", "game", "여러 전략을 비교하는 방식 선택"),
            _evidence("causal_analysis", "media", "장면 순서를 바꿔 이해하기 쉽게 만드는 활동 선택"),
            _evidence("causal_analysis", "game", "여러 전략을 비교하는 방식 선택"),  # 완전 중복
        ]
        grouped = build_detailed_evidence_by_dimension(candidates, ledger)

        self.assertEqual(set(grouped.keys()), {"분석과 구조화"})
        self.assertEqual(len(grouped["분석과 구조화"]), 2)  # 중복 제거됨

    def test_excludes_traits_not_in_highlights(self) -> None:
        definitions = {"causal_analysis": _trait("causal_analysis")}
        summaries = {"causal_analysis": _strong_summary("causal_analysis")}
        candidates = select_profile_highlight_traits(summaries, definitions, set())

        ledger = [_evidence("planning", "game", "미리 계획을 세운다")]  # highlight에 없는 Trait
        grouped = build_detailed_evidence_by_dimension(candidates, ledger)
        self.assertEqual(grouped, {})

    def test_excludes_secondary_hypothesis_records(self) -> None:
        definitions = {"causal_analysis": _trait("causal_analysis")}
        summaries = {"causal_analysis": _strong_summary("causal_analysis")}
        candidates = select_profile_highlight_traits(summaries, definitions, set())

        secondary = _evidence("causal_analysis", "game", "이건 Secondary라 빠져야 함").model_copy(
            update={"evidence_origin": EvidenceOrigin.SECONDARY_HYPOTHESIS}
        )
        grouped = build_detailed_evidence_by_dimension(candidates, [secondary])
        self.assertEqual(grouped, {})


if __name__ == "__main__":
    unittest.main()
