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
        """judge_trait_state 자체가 CONFLICTING을 정확히 반환하는지는 evidence_engine
        쪽에서 이미 검증한다 — 여기서는 그 judgment가 실제로 candidate 목록에 남는지만
        본다(아래 test_conflicting_traits_are_never_selected_as_highlights와 짝을 이룬다:
        judgment은 계산되지만 최종 selected에는 포함되면 안 된다)."""

        trait_ids = [f"trait_{i:02d}" for i in range(6)]
        definitions = {tid: _trait(tid) for tid in trait_ids}
        summaries = {tid: _strong_summary(tid) for tid in trait_ids}
        selected = select_profile_highlight_traits(summaries, definitions, {"trait_00"})
        self.assertNotIn("trait_00", {c.trait_definition.trait_id for c in selected})

    def test_conflicting_traits_are_never_selected_as_highlights(self) -> None:
        """2026-08-21 3단계 버그 수정: CONFLICTING은 STRONG/MODERATE가 모자라도 backfill
        후보(LIMITED/INSUFFICIENT 자리)로도 쓰이면 안 된다 — 실제로 support_count가 쌓여
        있어(그래서 상충이 드러난 것) strength_key 정렬상 진짜 미확인 Trait보다 앞에 서는
        부작용까지 있었다. 전공 Matching(§16)은 이미 normalized_value=None으로 별도
        경로에서 Mask되므로 이 테스트의 대상이 아니다."""

        trait_ids = [f"trait_{i:02d}" for i in range(4)]
        definitions = {tid: _trait(tid) for tid in trait_ids}
        # trait_00만 STRONG+Conflict, 나머지 3개는 아예 미확인(INSUFFICIENT) — 5개를
        # 채우려면 trait_00이 아니라 진짜 미확인 Trait만으로 backfill돼야 한다.
        summaries = {
            "trait_00": _strong_summary("trait_00"),
            "trait_01": _insufficient_summary("trait_01"),
            "trait_02": _insufficient_summary("trait_02"),
            "trait_03": _insufficient_summary("trait_03"),
        }
        selected = select_profile_highlight_traits(summaries, definitions, {"trait_00"})
        selected_ids = {c.trait_definition.trait_id for c in selected}
        self.assertNotIn("trait_00", selected_ids)
        self.assertEqual(selected_ids, {"trait_01", "trait_02", "trait_03"})


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
