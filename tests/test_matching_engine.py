"""Similarity Matching Engine(§16) 테스트 — 손계산 기반."""

from __future__ import annotations

import unittest
from datetime import datetime

from src.engines.matching_engine import (
    INSUFFICIENT_EVIDENCE_MESSAGE,
    compute_major_match,
    compute_student_trait_states,
    rank_major_relevance,
)
from src.schemas.evidence import TraitEvidenceSummary
from src.schemas.major import MajorProfile
from src.schemas.trait import TraitDefinition


def _trait(trait_id: str, group: str, min_context: int = 2) -> TraitDefinition:
    return TraitDefinition(
        trait_id=trait_id,
        label=trait_id,
        parent_dimension="테스트 차원",
        definition="테스트용 정의",
        positive_indicators=["테스트 긍정 지표"],
        conflicting_indicators=["테스트 상충 지표"],
        source_references=["팀 정의 — 테스트"],
        trait_scope="shared",
        minimum_context_count=min_context,
        primary_vector_group=group,
    )


def _strong(trait_id: str, context_count: int = 2) -> TraitEvidenceSummary:
    return TraitEvidenceSummary(
        trait_id=trait_id, support_count=3, opportunity_count=3, context_count=context_count, distinct_frame_count=2
    )


def _insufficient(trait_id: str) -> TraitEvidenceSummary:
    return TraitEvidenceSummary(trait_id=trait_id, support_count=0, opportunity_count=0)


DEFS = {
    "a": _trait("a", "cognitive"),
    "b": _trait("b", "cognitive"),
    "c": _trait("c", "work_style"),
    "d": _trait("d", "work_style"),  # "확정 안 됨"/"전공과 무관한 추가 Trait" 용도로 남겨둠
    "e": _trait("e", "work_style"),  # work_style 그룹을 2개 이상으로 채우는 두 번째 확정 Trait
}


class ComputeMajorMatchTest(unittest.TestCase):
    def test_insufficient_when_below_minimum_usable_traits(self) -> None:
        """확정된 Trait가 2개뿐이면(최소 3개 미달) insufficient여야 한다."""

        summaries = {"a": _strong("a"), "b": _strong("b"), "c": _insufficient("c"), "d": _insufficient("d")}
        states = compute_student_trait_states(summaries, DEFS, set())
        major = MajorProfile(
            major_id="m1", label="테스트전공",
            cognitive_vector={"a": 1.00, "b": 1.00},
            extraction_method="manual", review_status="draft", profile_version="v1",
            updated_at=datetime(2026, 1, 1),
        )
        result = compute_major_match(states, major)
        self.assertEqual(result.status, "insufficient")

    def test_insufficient_when_only_one_vector_group_usable(self) -> None:
        """Trait는 3개 이상이어도 전부 같은 Vector 그룹이면(최소 2개 그룹 미달) insufficient."""

        summaries = {"a": _strong("a"), "b": _strong("b"), "c": _insufficient("c"), "d": _insufficient("d")}
        states = compute_student_trait_states(summaries, DEFS, set())
        major = MajorProfile(
            major_id="m1", label="테스트전공",
            cognitive_vector={"a": 1.00, "b": 1.00, "extra_not_in_defs": 1.00},
            extraction_method="manual", review_status="draft", profile_version="v1",
            updated_at=datetime(2026, 1, 1),
        )
        # a,b 둘 다 cognitive라 usable_trait_count=2 (3 미만) → insufficient
        result = compute_major_match(states, major)
        self.assertEqual(result.status, "insufficient")

    def test_computed_when_minimums_met(self) -> None:
        summaries = {
            "a": _strong("a"), "b": _strong("b"), "c": _strong("c"), "e": _strong("e"),
            "d": _insufficient("d"),
        }
        states = compute_student_trait_states(summaries, DEFS, set())
        major = MajorProfile(
            major_id="m1", label="테스트전공",
            cognitive_vector={"a": 1.00, "b": 1.00},
            work_style_vector={"c": 1.00, "e": 1.00},
            extraction_method="manual", review_status="draft", profile_version="v1",
            updated_at=datetime(2026, 1, 1),
        )
        result = compute_major_match(states, major)
        self.assertEqual(result.status, "computed")
        self.assertEqual(result.usable_trait_count, 4)
        self.assertIsNotNone(result.score)
        self.assertGreater(result.score, 0)  # 학생 STRONG(1.00)과 전공 가중치(1.00) 방향이 같음

    def test_masked_traits_excluded_from_denominator(self) -> None:
        """CONFLICTING(Mask)된 Trait는 major 벡터에 있어도 usable에서 빠져야 한다."""

        summaries = {"a": _strong("a"), "b": _strong("b"), "c": _strong("c")}
        states = compute_student_trait_states(summaries, DEFS, unresolved_conflict_trait_ids={"c"})
        major = MajorProfile(
            major_id="m1", label="테스트전공",
            cognitive_vector={"a": 1.00, "b": 1.00},
            work_style_vector={"c": 1.00},
            extraction_method="manual", review_status="draft", profile_version="v1",
            updated_at=datetime(2026, 1, 1),
        )
        result = compute_major_match(states, major)
        # c가 Mask되면 work_style 그룹이 통째로 제외 → usable_trait_count는 a,b 둘뿐(2개, 3 미만)
        self.assertEqual(result.status, "insufficient")

    def test_insufficient_evidence_trait_excluded_from_denominator(self) -> None:
        """CONFLICTING뿐 아니라 INSUFFICIENT(opportunity_count=0, 한 번도 못 물어본 Trait)도
        major 벡터에 있으면 usable에서 빠져야 한다 — Evidence가 부족한 Trait은 매칭에서
        제외되지, 0점으로 계산되지 않는다(§16 Missing Evidence)."""

        summaries = {
            "a": _strong("a"), "b": _strong("b"), "c": _strong("c"), "e": _strong("e"),
            "d": _insufficient("d"),
        }
        states = compute_student_trait_states(summaries, DEFS, set())
        major_without_d = MajorProfile(
            major_id="m1", label="테스트전공",
            cognitive_vector={"a": 1.00, "b": 1.00}, work_style_vector={"c": 1.00, "e": 1.00},
            extraction_method="manual", review_status="draft", profile_version="v1",
            updated_at=datetime(2026, 1, 1),
        )
        major_with_d = major_without_d.model_copy(
            update={"work_style_vector": {"c": 1.00, "e": 1.00, "d": 1.00}}
        )

        result_without_d = compute_major_match(states, major_without_d)
        result_with_d = compute_major_match(states, major_with_d)
        # d가 major 벡터에 추가돼도 학생 쪽에서 d가 INSUFFICIENT라 usable_trait_count와
        # score가 그대로여야 한다 — d가 "0점 Trait"로 계산에 끼어들면 안 된다.
        self.assertEqual(result_without_d.usable_trait_count, result_with_d.usable_trait_count)
        self.assertAlmostEqual(result_without_d.score, result_with_d.score)

    def test_extra_student_trait_not_in_major_vector_does_not_change_score(self) -> None:
        """학생에게 이 전공 벡터에 없는 Trait가 추가로 STRONG이어도 이 전공 점수는
        바뀌면 안 된다 — "추가 Trait이 있다고 불이익 받지 않는지"(그리고 이득도 없어야
        한다, 애초에 그 전공과 무관한 Trait이므로) 검증."""

        summaries = {"a": _strong("a"), "b": _strong("b"), "c": _strong("c"), "e": _strong("e")}
        states_without_extra = compute_student_trait_states(summaries, DEFS, set())
        summaries_with_extra = {**summaries, "d": _strong("d")}  # 이 전공 벡터엔 없는 Trait
        states_with_extra = compute_student_trait_states(summaries_with_extra, DEFS, set())

        major = MajorProfile(
            major_id="m1", label="테스트전공",
            cognitive_vector={"a": 1.00, "b": 1.00}, work_style_vector={"c": 1.00, "e": 1.00},
            extraction_method="manual", review_status="draft", profile_version="v1",
            updated_at=datetime(2026, 1, 1),
        )
        result_without_extra = compute_major_match(states_without_extra, major)
        result_with_extra = compute_major_match(states_with_extra, major)
        self.assertEqual(result_without_extra.usable_trait_count, result_with_extra.usable_trait_count)
        self.assertAlmostEqual(result_without_extra.score, result_with_extra.score)

    def test_two_independent_traits_both_strong_do_not_offset_each_other(self) -> None:
        """"협업과 자율성처럼 동시에 높을 수 있는 Trait을 임의로 상충 처리하면 안 된다" —
        서로 다른 두 Trait가 둘 다 STRONG이고 전공도 둘 다 가중치 1.00이면, 서로를 깎아먹지
        않고 최대 유사도(1.0)가 나와야 한다."""

        summaries = {"a": _strong("a"), "b": _strong("b"), "c": _strong("c"), "e": _strong("e")}
        states = compute_student_trait_states(summaries, DEFS, set())
        major = MajorProfile(
            major_id="m1", label="테스트전공",
            cognitive_vector={"a": 1.00, "b": 1.00}, work_style_vector={"c": 1.00, "e": 1.00},
            extraction_method="manual", review_status="draft", profile_version="v1",
            updated_at=datetime(2026, 1, 1),
        )
        result = compute_major_match(states, major)
        self.assertAlmostEqual(result.score, 1.0)


class RankMajorRelevanceTest(unittest.TestCase):
    def test_all_insufficient_returns_message(self) -> None:
        from src.engines.matching_engine import MajorMatchResult

        results = [MajorMatchResult(major_id="m1", status="insufficient")]
        relevant, explore, message = rank_major_relevance(results, {"m1": "테스트전공"})
        self.assertEqual(relevant, [])
        self.assertEqual(explore, [])
        self.assertEqual(message, INSUFFICIENT_EVIDENCE_MESSAGE)

    def test_top_third_gets_relevant_label_with_three_candidates(self) -> None:
        from src.engines.matching_engine import MajorMatchResult

        results = [
            MajorMatchResult(major_id="high", status="computed", score=0.9),
            MajorMatchResult(major_id="mid", status="computed", score=0.5),
            MajorMatchResult(major_id="low", status="computed", score=0.1),
        ]
        labels = {"high": "높음전공", "mid": "중간전공", "low": "낮음전공"}
        relevant, explore, message = rank_major_relevance(results, labels)
        self.assertIsNone(message)
        self.assertEqual([r.major_id for r in relevant], ["high"])
        self.assertEqual([r.major_id for r in explore], ["mid", "low"])
        self.assertEqual(explore[0].relevance_label, "함께 탐색해볼 분야")
        self.assertEqual(explore[1].relevance_label, "비교해볼 만한 분야")

    def test_no_internal_score_leaks_into_major_relevance(self) -> None:
        from src.engines.matching_engine import MajorMatchResult

        results = [MajorMatchResult(major_id="m1", status="computed", score=0.77)]
        relevant, _, _ = rank_major_relevance(results, {"m1": "테스트전공"})
        self.assertNotIn("score", set(type(relevant[0]).model_fields.keys()))

    def test_single_low_score_candidate_is_not_automatically_high_relevance(self) -> None:
        """후보가 1개뿐이면 순위상 항상 1등이라 상대 순위만 쓰면 무조건 "관련성 높음"이
        된다 — 절대 유사도가 낮으면(MINIMUM_SCORE_FOR_HIGH_RELEVANCE 미만) 그러면 안 된다."""

        from src.engines.matching_engine import MINIMUM_SCORE_FOR_HIGH_RELEVANCE, MajorMatchResult

        results = [MajorMatchResult(major_id="m1", status="computed", score=MINIMUM_SCORE_FOR_HIGH_RELEVANCE - 0.1)]
        relevant, explore, message = rank_major_relevance(results, {"m1": "테스트전공"})
        self.assertIsNone(message)
        self.assertEqual(relevant, [])
        self.assertEqual(len(explore), 1)
        self.assertEqual(explore[0].relevance_label, "함께 탐색해볼 분야")

    def test_single_high_score_candidate_can_still_be_high_relevance(self) -> None:
        """후보가 1개여도 절대 유사도가 충분히 높으면 "관련성 높음"이어야 한다 — 위
        테스트와 짝을 이뤄 "무조건 낮춘다"가 아니라 "점수를 실제로 본다"를 검증한다."""

        from src.engines.matching_engine import MajorMatchResult

        results = [MajorMatchResult(major_id="m1", status="computed", score=0.95)]
        relevant, explore, _ = rank_major_relevance(results, {"m1": "테스트전공"})
        self.assertEqual([r.major_id for r in relevant], ["m1"])
        self.assertEqual(explore, [])

    def test_tied_score_majors_get_the_same_relevance_label(self) -> None:
        """동점 학과 두 곳이 있으면 major_id 알파벳 순서 때문에 한쪽만 "관련성 높음"이
        되고 다른 쪽은 "함께 탐색해볼 분야"로 밀려나면 안 된다 — 임의의 우열 금지."""

        from src.engines.matching_engine import MajorMatchResult

        results = [
            MajorMatchResult(major_id="z_major", status="computed", score=0.9),
            MajorMatchResult(major_id="a_major", status="computed", score=0.9),  # 동점, id만 다름
            MajorMatchResult(major_id="low_major", status="computed", score=0.2),
        ]
        labels = {"z_major": "z전공", "a_major": "a전공", "low_major": "낮은전공"}
        relevant, explore, _ = rank_major_relevance(results, labels)
        self.assertEqual({r.major_id for r in relevant}, {"z_major", "a_major"})
        self.assertEqual([r.major_id for r in explore], ["low_major"])


class FixedPersonaVerticalSliceMatchingTest(unittest.TestCase):
    """실제 Vertical Slice 대표 전공 3개(data/majors/vertical_slice_major_profiles.py)를
    그대로 써서, 손으로 설계한 고정 Persona(시각·인지 계열 Trait가 강한 학생)의 매칭
    결과가 상식적으로 말이 되는지 확인한다 — §26 "고정 Persona End-to-End" 정신을
    Matching Engine에도 적용."""

    def setUp(self) -> None:
        from src.data.majors.vertical_slice_major_profiles import VERTICAL_SLICE_MAJOR_PROFILES
        from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAITS

        self.majors = VERTICAL_SLICE_MAJOR_PROFILES
        self.trait_defs = {t.trait_id: t for t in VERTICAL_SLICE_TRAITS}
        self.labels = {m.major_id: m.label for m in self.majors}

    def test_analytical_persona_ranks_industrial_engineering_or_hci_above_media(self) -> None:
        """손계산: 원인 분석·패턴 탐색·정보 비교(전부 산업공학이 1.00으로 가중치를 둔
        Trait)를 STRONG으로, 감정 해석·의견 조정(미디어커뮤니케이션이 높게 보는 Trait)은
        INSUFFICIENT로 설계한 Persona → 산업공학 점수가 미디어커뮤니케이션보다 높아야
        한다. 정확한 점수가 아니라 순위만 검증한다(§6-6 Fixture 원칙과 동일)."""

        # work_style은 최소 2개가 확정돼야 그 그룹이 유사도 계산에 포함된다(1차원 cosine은
        # 항상 1.0이라 무의미하다 — MINIMUM_TRAITS_PER_VECTOR_GROUP). planning 혼자면
        # work_style 그룹이 제외돼서 cognitive 그룹 하나만 남아 usable_vector_group_count=1
        # (2 미만)이 돼버리므로 opinion_mediation도 함께 STRONG으로 만든다 — 산업공학·
        # 미디어커뮤니케이션 둘 다 planning·opinion_mediation에서 산업공학 쪽 가중치가
        # 더 높아(1.00/0.67 vs 0.67/0.33) 방향(cosine)도 산업공학이 더 잘 맞는다.
        strong_traits = {
            "causal_analysis", "pattern_finding", "information_comparison",
            "planning", "opinion_mediation",
        }
        summaries = {}
        for trait_id in self.trait_defs:
            if trait_id in strong_traits:
                summaries[trait_id] = TraitEvidenceSummary(
                    trait_id=trait_id, support_count=3, opportunity_count=3, context_count=2, distinct_frame_count=2
                )
            else:
                summaries[trait_id] = TraitEvidenceSummary(trait_id=trait_id, support_count=0, opportunity_count=0)

        states = compute_student_trait_states(summaries, self.trait_defs, set())
        results = {m.major_id: compute_major_match(states, m) for m in self.majors}

        self.assertEqual(results["industrial_engineering"].status, "computed")
        self.assertEqual(results["media_communication"].status, "computed")
        self.assertGreater(results["industrial_engineering"].score, results["media_communication"].score)

    def test_ranking_result_contains_no_raw_float(self) -> None:
        """MajorRelevance로 변환된 최종 결과에는 score 필드 자체가 없으므로, 학과 3개를
        전부 넣어도 사용자 노출용 목록 어디에도 float이 안 남는다."""

        strong_traits = {
            "causal_analysis", "pattern_finding", "information_comparison",
            "planning", "opinion_mediation",
        }
        summaries = {
            trait_id: (
                TraitEvidenceSummary(trait_id=trait_id, support_count=3, opportunity_count=3, context_count=2, distinct_frame_count=2)
                if trait_id in strong_traits
                else TraitEvidenceSummary(trait_id=trait_id, support_count=0, opportunity_count=0)
            )
            for trait_id in self.trait_defs
        }
        states = compute_student_trait_states(summaries, self.trait_defs, set())
        results = [compute_major_match(states, m) for m in self.majors]
        self.assertTrue(any(r.status == "computed" for r in results))  # 실제로 계산 경로를 탔는지 확인
        relevant, explore, _ = rank_major_relevance(results, self.labels)

        for item in relevant + explore:
            for field_name, field_value in item.model_dump().items():
                self.assertNotIsInstance(
                    field_value, float, f"{field_name}에 float 값이 노출됨: {field_value}"
                )


if __name__ == "__main__":
    unittest.main()
