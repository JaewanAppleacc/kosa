"""Similarity Matching Engine(§16) 테스트 — 손계산 기반."""

from __future__ import annotations

import unittest
from datetime import datetime

from src.engines.matching_engine import (
    INSUFFICIENT_EVIDENCE_MESSAGE,
    _weighted_trait_coverage,
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
    "e": _trait("e", "work_style"),  # work_style 그룹의 두 번째 확정 Trait(다중 Trait 그룹 검증용)
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


class WeightedTraitCoverageMathTest(unittest.TestCase):
    """2026-08-21 2단계: cosine similarity를 대체한 가중 Trait 충족도 공식을 직접
    검증한다. 사용자가 제시한 손계산 예시(LIMITED [0.33,0.33] vs 전공 [1.00,1.00] → 0.33,
    STRONG [1.00,1.00] vs 같은 전공 → 1.00)를 그대로 옮긴다."""

    def test_limited_student_yields_033_coverage(self) -> None:
        coverage = _weighted_trait_coverage([0.33, 0.33], [1.00, 1.00])
        self.assertAlmostEqual(coverage, 0.33)

    def test_strong_student_yields_100_coverage(self) -> None:
        coverage = _weighted_trait_coverage([1.00, 1.00], [1.00, 1.00])
        self.assertAlmostEqual(coverage, 1.00)

    def test_single_trait_preserves_magnitude_not_degenerate_one(self) -> None:
        """cosine similarity였다면 1차원에서 항상 1.0이었다(버그의 원인). 가중 충족도는
        1개짜리 벡터에서도 학생의 실제 정규화 값을 그대로 돌려줘야 한다."""

        self.assertAlmostEqual(_weighted_trait_coverage([0.67], [1.00]), 0.67)
        self.assertNotAlmostEqual(_weighted_trait_coverage([0.33], [1.00]), 1.00)

    def test_zero_total_weight_returns_none(self) -> None:
        self.assertIsNone(_weighted_trait_coverage([1.00], [0.0]))


class MagnitudeSensitivityTest(unittest.TestCase):
    """cosine similarity의 원래 버그: 방향(비율)만 보고 크기를 무시해서 LIMITED 학생과
    STRONG 학생이 같은 전공에 대해 동일 점수를 받았다. 가중 충족도로 바꾼 뒤에는 두 학생의
    점수가 달라야 한다."""

    def _summary(self, trait_id: str, *, support: int, context: int, frame: int) -> TraitEvidenceSummary:
        return TraitEvidenceSummary(
            trait_id=trait_id, support_count=support, opportunity_count=support, context_count=context,
            distinct_frame_count=frame,
        )

    def test_limited_and_strong_students_get_different_scores_against_same_major(self) -> None:
        major = MajorProfile(
            major_id="m1", label="테스트전공",
            cognitive_vector={"a": 1.00, "b": 1.00}, work_style_vector={"c": 1.00, "e": 1.00},
            extraction_method="manual", review_status="draft", profile_version="v1",
            updated_at=datetime(2026, 1, 1),
        )

        strong_summaries = {
            tid: self._summary(tid, support=3, context=2, frame=2) for tid in ["a", "b", "c", "e"]
        }
        # LIMITED: support_count=2지만 context_count=1(최소 2 미달)이라 §13 기준상 LIMITED.
        limited_summaries = {
            tid: self._summary(tid, support=2, context=1, frame=1) for tid in ["a", "b", "c", "e"]
        }

        strong_states = compute_student_trait_states(strong_summaries, DEFS, set())
        limited_states = compute_student_trait_states(limited_summaries, DEFS, set())
        self.assertEqual(limited_states["a"].state.value, "LIMITED")

        strong_result = compute_major_match(strong_states, major)
        limited_result = compute_major_match(limited_states, major)

        self.assertAlmostEqual(strong_result.score, 1.0)
        self.assertAlmostEqual(limited_result.score, 0.33)
        self.assertNotAlmostEqual(strong_result.score, limited_result.score)


class SingleTraitVectorGroupTest(unittest.TestCase):
    """예전 MINIMUM_TRAITS_PER_VECTOR_GROUP(그룹당 최소 2개)이 없어졌으므로, Trait 1개뿐인
    그룹(Vertical Slice의 interest·environment 실제 상황)도 매칭 점수에 비례해서 반영돼야
    한다 — 통째로 제외되면 안 된다."""

    def setUp(self) -> None:
        self.defs = {**DEFS, "f": _trait("f", "interest")}

    def _states(self, f_summary: TraitEvidenceSummary):
        summaries = {"a": _strong("a"), "b": _strong("b"), "f": f_summary}
        return compute_student_trait_states(summaries, self.defs, set())

    def test_single_trait_group_included_and_changes_score(self) -> None:
        major = MajorProfile(
            major_id="m1", label="테스트전공",
            interest_vector={"f": 1.00}, cognitive_vector={"a": 1.00, "b": 1.00},
            extraction_method="manual", review_status="draft", profile_version="v1",
            updated_at=datetime(2026, 1, 1),
        )

        strong_states = self._states(_strong("f"))
        weak_states = self._states(
            TraitEvidenceSummary(trait_id="f", support_count=2, opportunity_count=2, context_count=1, distinct_frame_count=1)
        )

        strong_result = compute_major_match(strong_states, major)
        weak_result = compute_major_match(weak_states, major)

        self.assertEqual(strong_result.status, "computed")
        self.assertEqual(weak_result.status, "computed")
        self.assertEqual(strong_result.usable_trait_count, 3)  # a, b, f 전부 포함(예전엔 f 제외됐음)
        # f 하나만 값이 달라졌는데 interest 그룹 가중치(0.35)만큼 전체 점수가 달라져야 한다
        # — f가 통째로 제외됐다면(예전 동작) 두 점수가 똑같이 1.0(cognitive만)이었을 것이다.
        self.assertNotAlmostEqual(strong_result.score, weak_result.score)
        self.assertAlmostEqual(strong_result.score, 1.0)


class MaskExclusionFromCoverageTest(unittest.TestCase):
    """Mask(CONFLICTING/INSUFFICIENT)된 Trait는 분자뿐 아니라 분모(전공 가중치 합)에서도
    빠져야 한다 — 분모에만 남아있으면 실제로 확인되지 않은 Trait 때문에 점수가 부당하게
    깎인다."""

    def test_masked_trait_weight_excluded_from_denominator_not_just_numerator(self) -> None:
        summaries = {
            "a": _strong("a"), "b": _strong("b"), "c": _strong("c"), "e": _strong("e"),
        }
        states_with_conflict = compute_student_trait_states(summaries, DEFS, unresolved_conflict_trait_ids={"e"})

        # e가 벡터에 있지만 Mask됨 — e의 가중치(0.50)가 분모에 남아있으면 c만으로는
        # coverage가 1.00*1.00/(1.00+0.50)=0.667이 돼야 하고, 분모에서도 제외됐다면 1.00이어야 한다.
        major_with_masked_e = MajorProfile(
            major_id="m1", label="테스트전공",
            cognitive_vector={"a": 1.00, "b": 1.00}, work_style_vector={"c": 1.00, "e": 0.50},
            extraction_method="manual", review_status="draft", profile_version="v1",
            updated_at=datetime(2026, 1, 1),
        )
        # e가 벡터에 아예 없는 대조군 — 분모 제외가 맞다면 위와 점수가 같아야 한다.
        major_without_e = MajorProfile(
            major_id="m1", label="테스트전공",
            cognitive_vector={"a": 1.00, "b": 1.00}, work_style_vector={"c": 1.00},
            extraction_method="manual", review_status="draft", profile_version="v1",
            updated_at=datetime(2026, 1, 1),
        )

        result_with_masked_e = compute_major_match(states_with_conflict, major_with_masked_e)
        result_without_e = compute_major_match(states_with_conflict, major_without_e)

        self.assertAlmostEqual(result_with_masked_e.score, 1.0)
        self.assertAlmostEqual(result_with_masked_e.score, result_without_e.score)


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

    def test_analytical_persona_ranks_industrial_engineering_above_media_and_hci(self) -> None:
        """가중 충족도 공식(2026-08-21 2단계) 하에서는, 모든 확정 Trait가 동일하게 STRONG이면
        전공별 가중치 분포가 달라도 coverage가 똑같이 1.0이 나온다(가중평균의 성질상 값이
        전부 같으면 가중치 분포는 결과에 영향을 못 준다) — 그래서 전공 간 실제 차별화를
        검증하려면 Persona의 Trait 강도 자체가 달라야 한다.

        원인 분석·패턴 탐색·정보 비교·계획(산업공학이 1.00으로 가중치를 둔 Trait)은 STRONG,
        감정 해석·수용자 반응 예측(미디어·HCI가 1.00 근처로 가중치를 둔 Trait)은 LIMITED로
        설계한다 — 산업공학은 학생이 강한 영역을 중요하게 보고, 미디어/HCI는 학생이 약한
        영역을 중요하게 보므로 산업공학 점수가 가장 높아야 한다."""

        strong_traits = {"causal_analysis", "pattern_finding", "information_comparison", "planning"}
        limited_traits = {"emotional_interpretation", "audience_response_prediction"}
        summaries = {}
        for trait_id in self.trait_defs:
            if trait_id in strong_traits:
                summaries[trait_id] = TraitEvidenceSummary(
                    trait_id=trait_id, support_count=3, opportunity_count=3, context_count=2, distinct_frame_count=2
                )
            elif trait_id in limited_traits:
                # LIMITED: support_count=2지만 context_count=1(최소 미달)이라 §13 기준상 LIMITED.
                summaries[trait_id] = TraitEvidenceSummary(
                    trait_id=trait_id, support_count=2, opportunity_count=2, context_count=1, distinct_frame_count=1
                )
            else:
                summaries[trait_id] = TraitEvidenceSummary(trait_id=trait_id, support_count=0, opportunity_count=0)

        states = compute_student_trait_states(summaries, self.trait_defs, set())
        results = {m.major_id: compute_major_match(states, m) for m in self.majors}

        self.assertEqual(results["industrial_engineering"].status, "computed")
        self.assertEqual(results["media_communication"].status, "computed")
        self.assertEqual(results["hci_ux"].status, "computed")
        self.assertGreater(results["industrial_engineering"].score, results["hci_ux"].score)
        self.assertGreater(results["hci_ux"].score, results["media_communication"].score)

    def test_ranking_result_contains_no_raw_float(self) -> None:
        """MajorRelevance로 변환된 최종 결과에는 score 필드 자체가 없으므로, 학과 3개를
        전부 넣어도 사용자 노출용 목록 어디에도 float이 안 남는다."""

        strong_traits = {"causal_analysis", "pattern_finding", "information_comparison", "planning"}
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
