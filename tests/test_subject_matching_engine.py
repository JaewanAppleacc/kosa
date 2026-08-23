"""SubjectMatchingEngine 단위 테스트 — 2026-08-24 14차 리뷰 §7."""

from __future__ import annotations

import unittest

from src.engines.matching_engine import StudentTraitState
from src.engines.subject_matching_engine import (
    MINIMUM_SCORE_FOR_CORE,
    MINIMUM_USABLE_TRAITS_FOR_CORE,
    MINIMUM_USABLE_TRAITS_FOR_EXPLORE,
    build_reason,
    compute_post_offering_recommendations,
    compute_subject_recommendations,
    to_course_recommendation_items,
)
from src.schemas.course import SubjectProfile
from src.schemas.trait import TraitDefinition


def _state(trait_id: str, value: float | None, group: str = "cognitive") -> StudentTraitState:
    from src.schemas.evidence import TraitState

    state = TraitState.STRONG if value == 1.0 else TraitState.LIMITED if value is not None else TraitState.INSUFFICIENT
    return StudentTraitState(
        trait_id=trait_id, state=state, normalized_value=value, context_count=2, primary_vector_group=group
    )


def _subject(
    subject_id: str,
    trait_vector: dict[str, float],
    related_major_ids: list[str],
    label: str | None = None,
    activity_summary: str = "테스트 활동을 수행하는 활동",
) -> SubjectProfile:
    return SubjectProfile(
        subject_id=subject_id, label=label or subject_id, trait_vector=trait_vector,
        related_major_ids=related_major_ids, source_id="https://example.moe.go.kr/",
        activity_summary=activity_summary,
    )


def _trait_def(trait_id: str, label: str) -> TraitDefinition:
    return TraitDefinition(
        trait_id=trait_id, label=label, parent_dimension="테스트", definition="테스트 정의",
        positive_indicators=["테스트 지표"], conflicting_indicators=["테스트 반대 지표"],
        source_references=["팀 정의 — 테스트"], trait_scope="shared", minimum_context_count=1,
        primary_vector_group="cognitive",
    )


class ComputeSubjectRecommendationsTest(unittest.TestCase):
    def test_only_subjects_linked_to_selected_major_are_candidates(self) -> None:
        subjects = [
            _subject("subj_related", {"causal_analysis": 1.0}, ["industrial_engineering"]),
            _subject("subj_unrelated", {"causal_analysis": 1.0}, ["media_communication"]),
        ]
        states = {"causal_analysis": _state("causal_analysis", 1.0)}
        results = compute_subject_recommendations(states, "industrial_engineering", subjects)
        self.assertEqual([r.subject_id for r in results], ["subj_related"])

    def test_subject_with_no_shared_confirmed_trait_is_excluded(self) -> None:
        subjects = [_subject("subj_a", {"causal_analysis": 1.0}, ["industrial_engineering"])]
        states = {"pattern_finding": _state("pattern_finding", 1.0)}  # causal_analysis 자체가 없음
        results = compute_subject_recommendations(states, "industrial_engineering", subjects)
        self.assertEqual(results, [])

    def test_masked_trait_is_excluded_not_treated_as_zero(self) -> None:
        """UNMAPPED/미확정 Trait(normalized_value=None)는 비교에서 완전히 빠져야 한다 —
        과목에 causal_analysis 가중치가 있어도 학생이 그 Trait를 확정하지 못했으면 안 쓴다."""

        subjects = [_subject("subj_a", {"causal_analysis": 1.0, "pattern_finding": 1.0}, ["industrial_engineering"])]
        states = {
            "causal_analysis": _state("causal_analysis", None),  # Mask(INSUFFICIENT/CONFLICTING)
            "pattern_finding": _state("pattern_finding", 1.0),
        }
        results = compute_subject_recommendations(states, "industrial_engineering", subjects)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].usable_trait_count, 1)
        self.assertEqual(results[0].usable_trait_ids, ["pattern_finding"])

    def test_high_usable_count_and_score_yields_core(self) -> None:
        subjects = [_subject("subj_a", {"causal_analysis": 1.0, "pattern_finding": 1.0}, ["industrial_engineering"])]
        states = {"causal_analysis": _state("causal_analysis", 1.0), "pattern_finding": _state("pattern_finding", 1.0)}
        results = compute_subject_recommendations(states, "industrial_engineering", subjects)
        self.assertEqual(results[0].category, "core")
        self.assertGreaterEqual(results[0].usable_trait_count, MINIMUM_USABLE_TRAITS_FOR_CORE)
        self.assertGreaterEqual(results[0].score, MINIMUM_SCORE_FOR_CORE)

    def test_single_usable_trait_yields_explore_not_core(self) -> None:
        subjects = [_subject("subj_a", {"causal_analysis": 1.0}, ["industrial_engineering"])]
        states = {"causal_analysis": _state("causal_analysis", 1.0)}
        results = compute_subject_recommendations(states, "industrial_engineering", subjects)
        self.assertEqual(results[0].category, "explore")
        self.assertEqual(results[0].usable_trait_count, MINIMUM_USABLE_TRAITS_FOR_EXPLORE)

    def test_low_score_with_enough_traits_yields_explore_not_core(self) -> None:
        subjects = [_subject("subj_a", {"causal_analysis": 1.0, "pattern_finding": 1.0}, ["industrial_engineering"])]
        states = {"causal_analysis": _state("causal_analysis", 0.33), "pattern_finding": _state("pattern_finding", 0.33)}
        results = compute_subject_recommendations(states, "industrial_engineering", subjects)
        self.assertEqual(results[0].category, "explore")

    def test_deterministic_order_core_before_explore_then_score_then_subject_id(self) -> None:
        subjects = [
            _subject("subj_z_explore", {"causal_analysis": 1.0}, ["industrial_engineering"]),
            _subject("subj_a_core", {"causal_analysis": 1.0, "pattern_finding": 1.0}, ["industrial_engineering"]),
            _subject("subj_b_core", {"causal_analysis": 1.0, "pattern_finding": 1.0}, ["industrial_engineering"]),
        ]
        states = {"causal_analysis": _state("causal_analysis", 1.0), "pattern_finding": _state("pattern_finding", 1.0)}
        results = compute_subject_recommendations(states, "industrial_engineering", subjects)
        self.assertEqual(
            [r.subject_id for r in results], ["subj_a_core", "subj_b_core", "subj_z_explore"]
        )

    def test_rerunning_with_same_input_is_identical(self) -> None:
        subjects = [_subject("subj_a", {"causal_analysis": 1.0, "pattern_finding": 1.0}, ["industrial_engineering"])]
        states = {"causal_analysis": _state("causal_analysis", 1.0), "pattern_finding": _state("pattern_finding", 1.0)}
        first = compute_subject_recommendations(states, "industrial_engineering", subjects)
        second = compute_subject_recommendations(states, "industrial_engineering", subjects)
        self.assertEqual([r.model_dump() for r in first], [r.model_dump() for r in second])


class ReasonAndMappingTest(unittest.TestCase):
    def test_reason_contains_major_label_and_trait_labels_not_numbers(self) -> None:
        subjects = [_subject("subj_a", {"causal_analysis": 1.0}, ["industrial_engineering"])]
        states = {"causal_analysis": _state("causal_analysis", 1.0)}
        results = compute_subject_recommendations(states, "industrial_engineering", subjects)
        trait_defs = {"causal_analysis": _trait_def("causal_analysis", "원인 분석")}
        reason = build_reason(results[0], "산업공학", trait_defs)
        self.assertIn("산업공학", reason)
        self.assertIn("원인 분석", reason)
        for token in reason.split():
            self.assertFalse(any(ch.isdigit() for ch in token) and "." in token, f"숫자 유사도로 보이는 토큰: {token}")

    def test_to_course_recommendation_items_has_no_score_field_and_offered_is_none(self) -> None:
        subjects = [_subject("subj_a", {"causal_analysis": 1.0, "pattern_finding": 1.0}, ["industrial_engineering"])]
        states = {"causal_analysis": _state("causal_analysis", 1.0), "pattern_finding": _state("pattern_finding", 1.0)}
        results = compute_subject_recommendations(states, "industrial_engineering", subjects)
        trait_defs = {
            "causal_analysis": _trait_def("causal_analysis", "원인 분석"),
            "pattern_finding": _trait_def("pattern_finding", "패턴 탐색"),
        }
        items = to_course_recommendation_items(results, "산업공학", trait_defs)
        self.assertEqual(len(items), 1)
        self.assertNotIn("score", items[0].model_dump())
        self.assertIsNone(items[0].is_actually_offered)
        self.assertEqual(items[0].category, "core")

    def test_to_course_recommendation_items_carries_the_subject_label(self) -> None:
        """2026-08-25 15차 리뷰 §1: subject_id만으로는 B가 과목명을 못 띄웠다 — 정본
        SubjectProfile.label을 그대로 옮겨야 한다."""

        subjects = [
            _subject("subj_a", {"causal_analysis": 1.0}, ["industrial_engineering"], label="확률과 통계")
        ]
        states = {"causal_analysis": _state("causal_analysis", 1.0)}
        results = compute_subject_recommendations(states, "industrial_engineering", subjects)
        items = to_course_recommendation_items(
            results, "산업공학", {"causal_analysis": _trait_def("causal_analysis", "원인 분석")}
        )
        self.assertEqual(items[0].subject_id, "subj_a")
        self.assertEqual(items[0].label, "확률과 통계")

    def test_reason_does_not_use_banned_overclaiming_phrases(self) -> None:
        """§3: Mapping이 아직 draft(2인 검토 전)라 "검증된"/"공식적으로 연결된" 같은
        과장된 확정 표현을 쓰면 안 된다."""

        subjects = [
            _subject(
                "subj_a", {"causal_analysis": 1.0}, ["industrial_engineering"],
                label="확률과 통계", activity_summary="자료를 분석하고 결과를 비교하는 활동",
            )
        ]
        states = {"causal_analysis": _state("causal_analysis", 1.0)}
        results = compute_subject_recommendations(states, "industrial_engineering", subjects)
        reason = build_reason(
            results[0], "산업공학", {"causal_analysis": _trait_def("causal_analysis", "원인 분석")}
        )
        banned_phrases = [
            "검증된 과목", "공식 추천 과목", "반드시 들어야 하는 과목",
            "이 전공에 필수인 과목", "적합도가 입증된 과목", "공식적으로 연결된 과목",
        ]
        for phrase in banned_phrases:
            self.assertNotIn(phrase, reason, f"금지 표현이 reason에 남아 있다: {phrase!r}")

    def test_reason_includes_selected_major_observed_trait_and_concrete_activity(self) -> None:
        """§4: reason에 (1) 선택 전공, (2) 학생 답변에서 확인된 Trait, (3) 과목의 공식
        교육과정 근거에서 뽑은 구체적 활동이 실제로 들어가야 한다."""

        subjects = [
            _subject(
                "subj_a", {"causal_analysis": 1.0}, ["industrial_engineering"],
                label="확률과 통계", activity_summary="자료를 분석하고 결과를 비교하는 활동",
            )
        ]
        states = {"causal_analysis": _state("causal_analysis", 1.0)}
        results = compute_subject_recommendations(states, "industrial_engineering", subjects)
        reason = build_reason(
            results[0], "산업공학", {"causal_analysis": _trait_def("causal_analysis", "원인 분석")}
        )
        self.assertIn("산업공학", reason)
        self.assertIn("원인 분석", reason)
        self.assertIn("확률과 통계", reason)
        self.assertIn("자료를 분석하고 결과를 비교하는 활동", reason)

    def test_reason_falls_back_to_limited_wording_when_activity_summary_missing(self) -> None:
        """§4: "근거가 없으면 활동을 지어내지 말고... 제한적 이유로 표시" — activity_summary
        가 비어 있으면 구체 활동을 지어내지 않고 제한적 문구로 대체해야 한다."""

        subjects = [
            _subject(
                "subj_a", {"causal_analysis": 1.0}, ["industrial_engineering"],
                label="근거 없는 과목", activity_summary="",
            )
        ]
        states = {"causal_analysis": _state("causal_analysis", 1.0)}
        results = compute_subject_recommendations(states, "industrial_engineering", subjects)
        reason = build_reason(
            results[0], "산업공학", {"causal_analysis": _trait_def("causal_analysis", "원인 분석")}
        )
        self.assertIn("아직 정리되지 않았습니다", reason)
        self.assertNotIn("경험할 수 있으며", reason)  # 활동을 지어내는 문장 구조가 안 쓰였는지


class ComputePostOfferingRecommendationsTest(unittest.TestCase):
    """2026-08-26 16차 리뷰 §7/§8 — POST_OFFERING 재추천 순수 계산.

    합성 데이터로 구성한다(진짜 subjects.jsonl 값에 의존하지 않는다) — 시나리오:
    - subj_core_a: core, 실제 개설됨 → 그대로 core 유지.
    - subj_core_b: core, 미개설 → unavailable + 대체 후보 탐색.
    - subj_explore_c: explore, 실제 개설됨 → subj_core_b의 대체과목으로 소비됨.
    - subj_explore_d: explore, 실제 개설됨, 아무 것도 대체하지 않음 → 그대로 explore 유지.
    - subj_explore_e: explore, 미개설 → unavailable에는 들어가지만 대체 후보 탐색은
      하지 않는다(§8 "explore는 확실한 희망이 아니었으므로 대체 탐색 범위 밖").
    """

    def _trait_defs(self) -> dict[str, TraitDefinition]:
        return {
            "causal_analysis": _trait_def("causal_analysis", "원인 분석"),
            "pattern_finding": _trait_def("pattern_finding", "패턴 탐색"),
        }

    def _subjects(self) -> list[SubjectProfile]:
        return [
            _subject(
                "subj_core_a", {"causal_analysis": 1.0, "pattern_finding": 1.0}, ["test_major"],
                label="핵심 개설과목 A", activity_summary="핵심 활동 A를 수행하는 활동",
            ),
            _subject(
                "subj_core_b", {"causal_analysis": 1.0, "pattern_finding": 1.0}, ["test_major"],
                label="핵심 미개설과목 B", activity_summary="핵심 활동 B를 수행하는 활동",
            ),
            _subject(
                "subj_explore_c", {"causal_analysis": 1.0}, ["test_major"],
                label="탐색 개설과목 C", activity_summary="탐색 활동 C를 수행하는 활동",
            ),
            _subject(
                "subj_explore_d", {"pattern_finding": 1.0}, ["test_major"],
                label="탐색 개설과목 D", activity_summary="탐색 활동 D를 수행하는 활동",
            ),
            _subject(
                "subj_explore_e", {"causal_analysis": 1.0}, ["test_major"],
                label="탐색 미개설과목 E", activity_summary="탐색 활동 E를 수행하는 활동",
            ),
        ]

    def _states(self) -> dict[str, StudentTraitState]:
        return {
            "causal_analysis": _state("causal_analysis", 1.0),
            "pattern_finding": _state("pattern_finding", 1.0),
        }

    def _offered(self) -> set[str]:
        return {"subj_core_a", "subj_explore_c", "subj_explore_d"}

    def test_offered_core_is_kept_as_core_with_offered_true(self) -> None:
        recs, _unavail = compute_post_offering_recommendations(
            self._states(), "test_major", self._subjects(), self._offered(), "테스트 전공", self._trait_defs()
        )
        core_items = [r for r in recs if r.subject_id == "subj_core_a"]
        self.assertEqual(len(core_items), 1)
        self.assertEqual(core_items[0].category, "core")
        self.assertIs(core_items[0].is_actually_offered, True)
        self.assertIsNone(core_items[0].replaces_subject_id)

    def test_missing_core_becomes_unavailable_and_gets_an_alternative(self) -> None:
        recs, unavail = compute_post_offering_recommendations(
            self._states(), "test_major", self._subjects(), self._offered(), "테스트 전공", self._trait_defs()
        )
        self.assertEqual([u.subject_id for u in unavail if u.subject_id == "subj_core_b"], ["subj_core_b"])
        alternative_items = [r for r in recs if r.category == "alternative"]
        self.assertEqual(len(alternative_items), 1)
        self.assertEqual(alternative_items[0].replaces_subject_id, "subj_core_b")
        self.assertIs(alternative_items[0].is_actually_offered, True)
        # 동점 후보(subj_explore_c/d 둘 다 usable_trait_count=1, score=1.0)는 subject_id
        # 오름차순으로 결정론적으로 골라야 한다 — "subj_explore_c" < "subj_explore_d".
        self.assertEqual(alternative_items[0].subject_id, "subj_explore_c")

    def test_alternative_is_not_duplicated_as_its_own_explore_item(self) -> None:
        """대체과목으로 소비된 explore 과목은 별도의 explore 추천으로 중복 노출되면
        안 된다 — 한 번만(alternative로) 나와야 한다."""

        recs, _unavail = compute_post_offering_recommendations(
            self._states(), "test_major", self._subjects(), self._offered(), "테스트 전공", self._trait_defs()
        )
        subject_ids = [r.subject_id for r in recs]
        self.assertEqual(subject_ids.count("subj_explore_c"), 1)

    def test_unconsumed_offered_explore_is_kept_as_explore(self) -> None:
        recs, _unavail = compute_post_offering_recommendations(
            self._states(), "test_major", self._subjects(), self._offered(), "테스트 전공", self._trait_defs()
        )
        explore_d = [r for r in recs if r.subject_id == "subj_explore_d"]
        self.assertEqual(len(explore_d), 1)
        self.assertEqual(explore_d[0].category, "explore")
        self.assertIs(explore_d[0].is_actually_offered, True)

    def test_missing_explore_is_unavailable_without_alternative_search(self) -> None:
        """§8: explore는 확실한 희망이 아니었으므로 대체 탐색 범위 밖이다 — 미개설
        subj_explore_e는 unavailable에는 들어가지만 어떤 recommendation도 이를 대체하지
        않는다."""

        recs, unavail = compute_post_offering_recommendations(
            self._states(), "test_major", self._subjects(), self._offered(), "테스트 전공", self._trait_defs()
        )
        self.assertIn("subj_explore_e", [u.subject_id for u in unavail])
        self.assertNotIn("subj_explore_e", [r.replaces_subject_id for r in recs])

    def test_no_alternative_available_leaves_unavailable_only(self) -> None:
        """§8 "대체 후보를 못 찾으면 지어내지 않고 unavailable 상태만 유지"."""

        subjects = self._subjects()[:2]  # subj_core_a, subj_core_b만 — explore 후보 없음
        recs, unavail = compute_post_offering_recommendations(
            self._states(), "test_major", subjects, {"subj_core_a"}, "테스트 전공", self._trait_defs()
        )
        self.assertEqual([r.category for r in recs], ["core"])  # subj_core_a만
        self.assertEqual([u.subject_id for u in unavail], ["subj_core_b"])

    def test_same_alternative_is_never_assigned_to_two_missing_subjects(self) -> None:
        """§8 "동일한 대체과목을 여러 미개설 과목에 무조건 중복 배정하지 말 것"."""

        subjects = [
            _subject("subj_core_x", {"causal_analysis": 1.0, "pattern_finding": 1.0}, ["test_major"], activity_summary="a"),
            _subject("subj_core_y", {"causal_analysis": 1.0, "pattern_finding": 1.0}, ["test_major"], activity_summary="b"),
            _subject("subj_explore_only", {"causal_analysis": 1.0}, ["test_major"], activity_summary="c"),
        ]
        recs, unavail = compute_post_offering_recommendations(
            self._states(), "test_major", subjects, {"subj_explore_only"}, "테스트 전공", self._trait_defs()
        )
        alternative_subject_ids = [r.subject_id for r in recs if r.category == "alternative"]
        # 두 개의 core가 모두 미개설이고 대체 후보는 explore 1개뿐 — 그중 하나만
        # 대체과목을 받고, 나머지 하나는 대체 없이 unavailable로만 남아야 한다.
        self.assertEqual(len(alternative_subject_ids), 1)
        self.assertEqual(len(unavail), 2)

    def test_rerunning_with_same_input_is_identical(self) -> None:
        first = compute_post_offering_recommendations(
            self._states(), "test_major", self._subjects(), self._offered(), "테스트 전공", self._trait_defs()
        )
        second = compute_post_offering_recommendations(
            self._states(), "test_major", self._subjects(), self._offered(), "테스트 전공", self._trait_defs()
        )
        self.assertEqual(
            [r.model_dump() for r in first[0]], [r.model_dump() for r in second[0]]
        )
        self.assertEqual(
            [u.model_dump() for u in first[1]], [u.model_dump() for u in second[1]]
        )

    def test_no_score_leaks_into_post_offering_items(self) -> None:
        recs, _unavail = compute_post_offering_recommendations(
            self._states(), "test_major", self._subjects(), self._offered(), "테스트 전공", self._trait_defs()
        )
        for item in recs:
            self.assertNotIn("score", item.model_dump())


class ImportRequiredSymbolsTest(unittest.TestCase):
    """모듈에서 POST_OFFERING용 함수들을 정상적으로 가져올 수 있는지 확인 — 위 테스트가
    전부 import에 의존하므로, import 자체가 실패하면 이 파일 전체가 collection error로
    조용히 스킵될 수 있다(명시적으로 한 번 더 확인)."""

    def test_functions_are_importable(self) -> None:
        from src.engines.subject_matching_engine import (  # noqa: F401
            build_alternative_reason,
            build_unavailable_reason,
            compute_post_offering_recommendations,
            to_alternative_course_recommendation_items,
        )


if __name__ == "__main__":
    unittest.main()
