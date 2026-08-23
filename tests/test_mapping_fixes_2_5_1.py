"""V2 Direct Probe Mapping 수정 3건 — 2026-08-23 Trait Ontology v2(2.5.1단계) §10/§13.

A) detail_orientation_media_v1의 do_visual_check: visual_expression 직접 Mapping을
   되돌리고 NO_SIGNAL로 처리.
B) uncertainty_tolerance_school_life_v1의 ut_decide_now: 감정 상태("불안해하지 않고")와
   행동을 분리.
C) independent_judgment_school_life_v1: 성급해 보이는 상황을 현실적인 선택과목·동아리
   상황으로 재설계.
"""

from __future__ import annotations

import unittest

from src.data.questions.trait_v2_direct_probe_blueprints import V2_DIRECT_PROBE_BLUEPRINTS_BY_ID
from src.engines.v2_direct_probe_quality_checks import question_level_flags


class VisualAppreciationMappingRegressionTest(unittest.TestCase):
    """§10-A."""

    def test_do_visual_check_is_no_signal_not_visual_expression(self) -> None:
        bp = V2_DIRECT_PROBE_BLUEPRINTS_BY_ID["detail_orientation_media_v1"]
        mapping = bp.mapping_by_role("do_visual_check")
        self.assertEqual(mapping.mapping_type, "NO_SIGNAL")
        self.assertTrue(mapping.no_signal_reason)

    def test_do_visual_check_option_has_empty_public_trait_delta(self) -> None:
        bp = V2_DIRECT_PROBE_BLUEPRINTS_BY_ID["detail_orientation_media_v1"]
        option = next(o for o in bp.base_question.options if o.role_id == "do_visual_check")
        self.assertEqual(option.primary_trait_delta, {})

    def test_target_option_is_still_detail_orientation(self) -> None:
        bp = V2_DIRECT_PROBE_BLUEPRINTS_BY_ID["detail_orientation_media_v1"]
        target = next(
            o for o in bp.base_question.options
            if bp.mapping_by_role(o.role_id).mapping_type == "TRAIT_SIGNAL"
            and bp.mapping_by_role(o.role_id).primary_trait_id == bp.trait_id
        )
        self.assertEqual(target.role_id, "do_scan_errors")


class UncertaintyToleranceOptionSplitTest(unittest.TestCase):
    """§10-B."""

    def test_ut_decide_now_has_no_emotional_language(self) -> None:
        bp = V2_DIRECT_PROBE_BLUEPRINTS_BY_ID["uncertainty_tolerance_school_life_v1"]
        option = next(o for o in bp.base_question.options if o.role_id == "ut_decide_now")
        for phrase in ("불안", "걱정", "편안"):
            self.assertNotIn(phrase, option.text)

    def test_ut_decide_now_is_still_the_uncertainty_tolerance_target(self) -> None:
        bp = V2_DIRECT_PROBE_BLUEPRINTS_BY_ID["uncertainty_tolerance_school_life_v1"]
        mapping = bp.mapping_by_role("ut_decide_now")
        self.assertEqual(mapping.mapping_type, "TRAIT_SIGNAL")
        self.assertEqual(mapping.primary_trait_id, "uncertainty_tolerance")

    def test_no_option_in_this_blueprint_combines_emotion_and_action(self) -> None:
        bp = V2_DIRECT_PROBE_BLUEPRINTS_BY_ID["uncertainty_tolerance_school_life_v1"]
        emotion_words = ("불안", "걱정되", "편안하")
        for option in bp.base_question.options:
            emotion_hits = [w for w in emotion_words if w in option.text]
            if option.role_id == "ut_voice_concern":
                # 이 role은 opinion_expression이 목표라 "걱정된다는 내 생각을 말한다"는
                # 표현 자체가 핵심 행동(의견 표명)이다 — 감정은 말하는 대상일 뿐 판정
                # 기준이 아니다. 나머지 4개 role에는 감정 어휘가 전혀 없어야 한다.
                continue
            self.assertEqual(emotion_hits, [], f"{option.role_id}: {emotion_hits}")


class IndependentJudgmentSchoolLifeRedesignTest(unittest.TestCase):
    """§10-C."""

    def test_scenario_is_course_or_club_choice_not_friend_behavior_change(self) -> None:
        bp = V2_DIRECT_PROBE_BLUEPRINTS_BY_ID["independent_judgment_school_life_v1"]
        self.assertNotIn("평소와 달라졌는데", bp.base_question.question_text)
        self.assertTrue(
            ("선택과목" in bp.base_question.question_text) or ("동아리" in bp.base_question.question_text)
        )

    def test_four_distinct_behavior_categories_present(self) -> None:
        bp = V2_DIRECT_PROBE_BLUEPRINTS_BY_ID["independent_judgment_school_life_v1"]
        target = next(
            m for m in bp.option_mappings
            if m.mapping_type == "TRAIT_SIGNAL" and m.primary_trait_id == bp.trait_id
        )
        self.assertEqual(target.role_id, "ij_set_own_standard")

        info_comparison = bp.mapping_by_role("ij_plan_role")
        self.assertEqual(info_comparison.mapping_type, "TRAIT_SIGNAL")
        self.assertEqual(info_comparison.primary_trait_id, "information_comparison")

        opinion = bp.mapping_by_role("ij_speak_role")
        self.assertEqual(opinion.mapping_type, "TRAIT_SIGNAL")
        self.assertEqual(opinion.primary_trait_id, "opinion_expression")

        majority = bp.mapping_by_role("ij_adapt_role")
        self.assertEqual(majority.mapping_type, "NO_SIGNAL")

    def test_asking_friend_option_is_not_moralized_as_the_only_valid_answer(self) -> None:
        """§10-C 목표: "친구에게 묻는 선택지만 도덕적 정답처럼 보이지 않음" — 자동으로는
        "정답처럼 보인다"를 판정할 수 없으니, 적어도 극단/사회적 바람직성 표현이 그
        선택지에만 몰려 있지 않은지 quality_flags로 확인한다."""

        bp = V2_DIRECT_PROBE_BLUEPRINTS_BY_ID["independent_judgment_school_life_v1"]
        flags = question_level_flags(bp)
        moralizing_flags = [f for f in flags if "극단 표현" in f]
        self.assertEqual(moralizing_flags, [])

    def test_all_5_options_exist_at_the_same_decision_point(self) -> None:
        """순차 의존 표현이 재도입되지 않았는지 확인한다(§9 규칙 재사용)."""

        bp = V2_DIRECT_PROBE_BLUEPRINTS_BY_ID["independent_judgment_school_life_v1"]
        flags = question_level_flags(bp)
        sequential_flags = [f for f in flags if "순차 의존" in f]
        self.assertEqual(sequential_flags, [])


if __name__ == "__main__":
    unittest.main()
