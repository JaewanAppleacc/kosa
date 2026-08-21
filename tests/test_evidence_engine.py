"""Hand-Calculated Fixture — CLAUDE.md 필수 테스트 "Evidence 수기 계산과 코드 결과 일치".

각 케이스는 §13 상태 판정 규칙을 손으로 먼저 계산한 값을 주석에 적고, 코드 결과와 비교한다.

2026-08-20 팀 결정: MODERATE도 STRONG과 동일하게 distinct_frame_count>=2를 요구한다.
같은 질문 프레임만 반복해서 나온 증거는 자기확증 방지 규칙(§8)에 가깝다고 판단했다.
"""

from __future__ import annotations

import unittest

from src.engines.evidence_engine import judge_trait_state, summarize_trait_evidence
from src.engines.trait_normalizer import normalize_trait_state
from src.schemas.evidence import EvidenceOrigin, EvidenceRecord, TraitState


def _record(
    evidence_id: str,
    context: str,
    frame: str,
    trait: str,
    origin: EvidenceOrigin = EvidenceOrigin.PRIMARY_BLUEPRINT,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        answer_id=f"ans_{evidence_id}",
        question_id=f"q_{evidence_id}",
        question_frame_id=frame,
        option_role_id="some_role",
        option_text="테스트 선택지 문장",
        applied_primary_trait_delta={trait: 1},
        evidence_origin=origin,
        context=context,
        source_type="generated_question",
        generator_version="qgen_v1",
        quality_gate_status="passed",
    )


class HandCalculatedFixtureTest(unittest.TestCase):
    """demo_user_01 스타일 고정 답변 시나리오. 손으로 먼저 계산: 아래 각 docstring 참고."""

    def test_strong_case(self) -> None:
        """손계산: 4문항에 causal_analysis 제시(opportunity=4), 그중 3번 선택(support=3),
        선택된 3건은 game/media/media 2개 Context, unexpected_result/new_tool 2개 Frame.
        → support>=3, context_count(2)>=min(2), frame_count(2)>=2 → STRONG."""

        records = [
            _record("1", "game", "unexpected_result", "causal_analysis"),
            _record("2", "media", "new_tool", "causal_analysis"),
            _record("3", "media", "unexpected_result", "causal_analysis"),
        ]
        offered = [
            {"causal_analysis"},  # Q1 game, 선택됨
            {"causal_analysis"},  # Q2 media, 선택됨
            {"causal_analysis"},  # Q3 media, 선택됨
            {"causal_analysis"},  # Q4 school_life, 제시만 되고 선택 안 됨
        ]
        summary = summarize_trait_evidence("causal_analysis", records, offered)

        self.assertEqual(summary.support_count, 3)
        self.assertEqual(summary.opportunity_count, 4)
        self.assertEqual(summary.context_count, 2)
        self.assertEqual(summary.distinct_frame_count, 2)
        self.assertAlmostEqual(summary.support_ratio, 0.75)

        judgment = judge_trait_state(summary, minimum_context_count=2, has_unresolved_explicit_conflict=False)
        self.assertEqual(judgment.state, TraitState.STRONG)
        self.assertIsNone(judgment.insufficient_reason)
        self.assertEqual(normalize_trait_state(judgment.state), 1.00)

    def test_moderate_case_requires_two_distinct_frames(self) -> None:
        """손계산: 2문항 제시(opportunity=2), 2번 다 선택(support=2), game/media 2개 Context,
        new_tool/unexpected_result 2개 Frame. → support>=2, context>=min, frame>=2 → MODERATE."""

        records = [
            _record("1", "game", "new_tool", "change_adaptation"),
            _record("2", "media", "unexpected_result", "change_adaptation"),
        ]
        offered = [{"change_adaptation"}, {"change_adaptation"}]
        summary = summarize_trait_evidence("change_adaptation", records, offered)

        self.assertEqual(summary.support_count, 2)
        self.assertEqual(summary.context_count, 2)
        self.assertEqual(summary.distinct_frame_count, 2)

        judgment = judge_trait_state(summary, minimum_context_count=2, has_unresolved_explicit_conflict=False)
        self.assertEqual(judgment.state, TraitState.MODERATE)
        self.assertEqual(normalize_trait_state(judgment.state), 0.67)

    def test_limited_case_same_frame_repeated(self) -> None:
        """손계산: 2문항 제시(opportunity=2), 2번 다 선택(support=2), game/media 2개 Context지만
        둘 다 같은 'new_tool' Frame(distinct_frame_count=1). 2026-08-20 결정으로 MODERATE 자격
        미달 → support>=2인데 frame 다양성 부족 → LIMITED (0.33, 강등)."""

        records = [
            _record("1", "game", "new_tool", "collaboration_preference"),
            _record("2", "media", "new_tool", "collaboration_preference"),  # 같은 frame 재사용
        ]
        offered = [{"collaboration_preference"}, {"collaboration_preference"}]
        summary = summarize_trait_evidence("collaboration_preference", records, offered)

        self.assertEqual(summary.support_count, 2)
        self.assertEqual(summary.context_count, 2)
        self.assertEqual(summary.distinct_frame_count, 1)

        judgment = judge_trait_state(summary, minimum_context_count=2, has_unresolved_explicit_conflict=False)
        self.assertEqual(judgment.state, TraitState.LIMITED)
        self.assertEqual(normalize_trait_state(judgment.state), 0.33)

    def test_limited_case_insufficient_context_diversity(self) -> None:
        """손계산: 2문항 다 game Context에서만 제시·선택(support=2, context_count=1 < min=2).
        → support>=2 이지만 context 다양성 부족 → LIMITED."""

        records = [
            _record("1", "game", "new_tool", "immediate_execution"),
            _record("2", "game", "unexpected_result", "immediate_execution"),
        ]
        offered = [{"immediate_execution"}, {"immediate_execution"}]
        summary = summarize_trait_evidence("immediate_execution", records, offered)

        self.assertEqual(summary.support_count, 2)
        self.assertEqual(summary.context_count, 1)

        judgment = judge_trait_state(summary, minimum_context_count=2, has_unresolved_explicit_conflict=False)
        self.assertEqual(judgment.state, TraitState.LIMITED)
        self.assertEqual(normalize_trait_state(judgment.state), 0.33)

    def test_insufficient_not_probed(self) -> None:
        """손계산: 이 Trait를 확인할 질문 자체가 없었음(opportunity=0)
        → INSUFFICIENT / NOT_PROBED."""

        summary = summarize_trait_evidence("opinion_mediation", [], [])
        self.assertEqual(summary.opportunity_count, 0)
        judgment = judge_trait_state(summary, minimum_context_count=2, has_unresolved_explicit_conflict=False)
        self.assertEqual(judgment.state, TraitState.INSUFFICIENT)
        self.assertEqual(judgment.insufficient_reason, "NOT_PROBED")

    def test_insufficient_no_positive_evidence(self) -> None:
        """손계산: 3번 제시됐지만 한 번도 선택 안 됨(opportunity=3, support=0)
        → INSUFFICIENT / NO_POSITIVE_EVIDENCE."""

        offered = [{"opinion_mediation"}] * 3
        summary = summarize_trait_evidence("opinion_mediation", [], offered)
        self.assertEqual(summary.opportunity_count, 3)
        self.assertEqual(summary.support_count, 0)
        judgment = judge_trait_state(summary, minimum_context_count=2, has_unresolved_explicit_conflict=False)
        self.assertEqual(judgment.state, TraitState.INSUFFICIENT)
        self.assertEqual(judgment.insufficient_reason, "NO_POSITIVE_EVIDENCE")

    def test_insufficient_evidence_limited_single_support(self) -> None:
        """손계산: 3번 제시, 1번만 선택(support=1) → INSUFFICIENT / EVIDENCE_LIMITED."""

        records = [_record("1", "game", "new_tool", "audience_response_prediction")]
        offered = [{"audience_response_prediction"}] * 3
        summary = summarize_trait_evidence("audience_response_prediction", records, offered)
        self.assertEqual(summary.support_count, 1)
        judgment = judge_trait_state(summary, minimum_context_count=2, has_unresolved_explicit_conflict=False)
        self.assertEqual(judgment.state, TraitState.INSUFFICIENT)
        self.assertEqual(judgment.insufficient_reason, "EVIDENCE_LIMITED")

    def test_conflicting_overrides_support_count(self) -> None:
        """손계산: support=3/context=2/frame=2로 STRONG 조건을 만족해도, 해결 안 된 explicit
        conflict가 있으면 CONFLICTING이 우선한다 (§13 판정 순서 2번째)."""

        records = [
            _record("1", "game", "unexpected_result", "planning"),
            _record("2", "media", "new_tool", "planning"),
            _record("3", "media", "unexpected_result", "planning"),
        ]
        offered = [{"planning"}] * 3
        summary = summarize_trait_evidence("planning", records, offered)

        judgment = judge_trait_state(summary, minimum_context_count=2, has_unresolved_explicit_conflict=True)
        self.assertEqual(judgment.state, TraitState.CONFLICTING)
        self.assertIsNone(judgment.insufficient_reason)
        self.assertIsNone(normalize_trait_state(judgment.state))  # Mask

    def test_secondary_hypothesis_records_are_excluded_from_support_count(self) -> None:
        """회귀 테스트(2026-08-20 리뷰): evidence_origin=SECONDARY_HYPOTHESIS인 레코드가
        support_count에 섞여 들어가면 안 된다. CONFIRMED되지 않은 Secondary Hypothesis를
        확정 점수에 반영하지 않는다는 원칙(CLAUDE.md 아키텍처 불변식) 위반이었다."""

        records = [
            _record("1", "game", "unexpected_result", "tool_utilization"),  # primary, 카운트됨
            _record(
                "2",
                "media",
                "new_tool",
                "tool_utilization",
                origin=EvidenceOrigin.SECONDARY_HYPOTHESIS,
            ),  # secondary, 카운트되면 안 됨
        ]
        offered = [{"tool_utilization"}]  # primary로 제시된 기회는 1번뿐
        summary = summarize_trait_evidence("tool_utilization", records, offered)

        self.assertEqual(summary.support_count, 1)  # 2가 아니라 1이어야 한다
        self.assertEqual(summary.context_count, 1)  # media(secondary)는 집계에서 빠져야 한다


if __name__ == "__main__":
    unittest.main()
