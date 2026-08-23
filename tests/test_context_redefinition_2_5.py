"""Context 재정의(game/media/school_life) — 2026-08-23 Trait Ontology v2(2.5단계)
§3/§6/§7/§8/§9/§12.

이 파일은 새로 만든 규칙(§9)이 실제로 사용자가 지적한 문제(팀 전제, 포괄 표현, 순차
의존, 학교생활 조별 편중)를 잡아내는지, 그리고 이번 라운드에서 다시 쓴 14개
Blueprint가 그 문제를 실제로 재도입하지 않았는지를 함께 검증한다. 자동 검사
자체(`question_level_flags`)는 어디까지나 Advisory라 "통과 = 완벽히 타당함"을
의미하지 않는다 — 여기서는 "사용자가 지적했던 구체적인 패턴이 다시 나타나면 잡아낸다"
는 것만 확인한다."""

from __future__ import annotations

import unittest

from src.data.questions.trait_v2_direct_probe_blueprints import (
    V2_DIRECT_PROBE_BLUEPRINTS,
    V2_DIRECT_PROBE_BLUEPRINTS_BY_ID,
)
from src.engines.v2_direct_probe_quality_checks import (
    CATCH_ALL_PHRASES,
    SEQUENTIAL_DEPENDENCY_MARKERS,
    TEAM_PRESUPPOSITION_PHRASES,
    question_level_flags,
)
from src.schemas.v2_direct_probe import FinalizedOption, FinalizedQuestion
from src.data.questions.context_routing_blueprints import CONTEXT_ROUTING_BLUEPRINTS_BY_CONTEXT

_GAME_BLUEPRINTS = [bp for bp in V2_DIRECT_PROBE_BLUEPRINTS if bp.base_question.context == "game"]
_MEDIA_BLUEPRINTS = [bp for bp in V2_DIRECT_PROBE_BLUEPRINTS if bp.base_question.context == "media"]
_SCHOOL_LIFE_BLUEPRINTS = [bp for bp in V2_DIRECT_PROBE_BLUEPRINTS if bp.base_question.context == "school_life"]

# §8에서 실제로 배정한 도메인 — 정확히 6개, 슬랙 없이 1:1로 배정했다(2.5단계 마이그레이션
# 감사 문서 `outputs/reviews/v2_direct_probe_migration_audit.md` 참고).
_SCHOOL_LIFE_DOMAIN_BY_BLUEPRINT_ID = {
    "systems_thinking_school_life_v1": "academic_study",
    "persistence_completion_school_life_v1": "academic_study",
    "detail_orientation_school_life_v1": "assignment_evaluation",
    "uncertainty_tolerance_school_life_v1": "course_career",
    "opinion_expression_school_life_v1": "group_activity",
    "independent_judgment_school_life_v1": "friendship",
}


class GameContextTeamPresuppositionTest(unittest.TestCase):
    """§6 — 혼자 플레이하는 학생에게도 적용되는 문구여야 한다."""

    def test_no_game_blueprint_contains_team_presupposition_phrases(self) -> None:
        for bp in _GAME_BLUEPRINTS:
            all_text = bp.base_question.question_text + " " + " ".join(o.text for o in bp.base_question.options)
            for phrase in TEAM_PRESUPPOSITION_PHRASES:
                self.assertNotIn(
                    phrase, all_text, f"{bp.blueprint_id}: 팀 전제 표현 {phrase!r}이 아직 남아 있다",
                )

    def test_automated_check_flags_synthetic_team_presupposition_option(self) -> None:
        """검사기 자체가 실제로 팀 전제 표현을 잡아내는지 합성 데이터로 확인한다."""

        real = _GAME_BLUEPRINTS[0]
        options = list(real.base_question.options)
        mutated_options = [
            options[0].model_copy(update={"text": "팀원에게 어떻게 할지 물어본다"}),
        ] + options[1:]
        mutated_question = real.base_question.model_copy(update={"options": mutated_options})
        mutated_bp = real.model_copy(update={"base_question": mutated_question})
        flags = question_level_flags(mutated_bp)
        self.assertTrue(any("팀 전제" in f for f in flags))

    def test_game_context_routing_has_solo_and_coop_anchors(self) -> None:
        """§4 — game Routing에는 혼자(예: story_exploration)와 협동(cooperative_role)
        Anchor가 둘 다 존재해서, 이후 실제 질문에서 어느 쪽으로도 자연스럽게 이어질 수
        있어야 한다."""

        bp = CONTEXT_ROUTING_BLUEPRINTS_BY_CONTEXT["game"]
        anchors = {m.context_anchor for m in bp.option_mappings}
        self.assertIn("cooperative_role", anchors)
        self.assertTrue(len(anchors) >= 2)


class MediaContextAppreciationTest(unittest.TestCase):
    """§7 — 제작·편집이 아니라 감상자 관점이어야 한다."""

    _PRODUCTION_PHRASES = ("편집", "제출", "촬영본", "결과물을 편집")

    def test_no_media_blueprint_presupposes_production_or_submission(self) -> None:
        for bp in _MEDIA_BLUEPRINTS:
            all_text = bp.base_question.question_text + " " + " ".join(o.text for o in bp.base_question.options)
            for phrase in self._PRODUCTION_PHRASES:
                self.assertNotIn(
                    phrase, all_text, f"{bp.blueprint_id}: 제작/제출 전제 표현 {phrase!r}이 남아 있다",
                )

    def test_stage_anchor_options_do_not_use_video_editing_phrasing(self) -> None:
        """미디어 Context Routing의 stage_performance Anchor로 연결되는 감상 질문에
        영상 편집 표현이 없어야 한다 — mr_stage 자체 문구를 확인한다."""

        bp = CONTEXT_ROUTING_BLUEPRINTS_BY_CONTEXT["media"]
        stage_mapping = next(m for m in bp.option_mappings if m.context_anchor == "stage_performance")
        stage_option = next(o for o in bp.base_question.options if o.role_id == stage_mapping.role_id)
        for phrase in ("편집", "촬영"):
            self.assertNotIn(phrase, stage_option.text)


class SchoolLifeDistributionTest(unittest.TestCase):
    """§8 — 학업·공부(min2)/과제·수행평가(min1)/과목·진로선택(min1)/친구관계(min1)/
    조별·그룹활동(max1). 6개 Blueprint가 정확히 이 기준을 충족해야 한다(슬랙 없음)."""

    def test_all_6_school_life_blueprints_are_classified(self) -> None:
        actual_ids = {bp.blueprint_id for bp in _SCHOOL_LIFE_BLUEPRINTS}
        self.assertEqual(actual_ids, set(_SCHOOL_LIFE_DOMAIN_BY_BLUEPRINT_ID.keys()))

    def test_academic_study_at_least_2(self) -> None:
        count = sum(1 for d in _SCHOOL_LIFE_DOMAIN_BY_BLUEPRINT_ID.values() if d == "academic_study")
        self.assertGreaterEqual(count, 2)

    def test_assignment_evaluation_at_least_1(self) -> None:
        count = sum(1 for d in _SCHOOL_LIFE_DOMAIN_BY_BLUEPRINT_ID.values() if d == "assignment_evaluation")
        self.assertGreaterEqual(count, 1)

    def test_course_career_at_least_1(self) -> None:
        count = sum(1 for d in _SCHOOL_LIFE_DOMAIN_BY_BLUEPRINT_ID.values() if d == "course_career")
        self.assertGreaterEqual(count, 1)

    def test_friendship_at_least_1(self) -> None:
        count = sum(1 for d in _SCHOOL_LIFE_DOMAIN_BY_BLUEPRINT_ID.values() if d == "friendship")
        self.assertGreaterEqual(count, 1)

    def test_group_activity_at_most_1(self) -> None:
        count = sum(1 for d in _SCHOOL_LIFE_DOMAIN_BY_BLUEPRINT_ID.values() if d == "group_activity")
        self.assertLessEqual(count, 1)


class CatchAllAndSequentialDependencyDetectorTest(unittest.TestCase):
    """§9 — 포괄 표현과 순차 의존을 검사기가 실제로 잡아내는지, 그리고 실제 14개
    Blueprint에는 더 이상 남아 있지 않은지(회귀 잠금) 확인한다."""

    def test_no_real_blueprint_triggers_catch_all_or_sequential_flags(self) -> None:
        for bp in V2_DIRECT_PROBE_BLUEPRINTS:
            flags = question_level_flags(bp)
            catch_all_flags = [f for f in flags if "포괄 표현" in f]
            sequential_flags = [f for f in flags if "순차 의존" in f]
            self.assertEqual(catch_all_flags, [], bp.blueprint_id)
            self.assertEqual(sequential_flags, [], bp.blueprint_id)

    def test_detector_flags_synthetic_catch_all_option(self) -> None:
        real = _SCHOOL_LIFE_BLUEPRINTS[0]
        options = list(real.base_question.options)
        mutated_options = [options[0].model_copy(update={"text": "상황에 맞게 대응한다"})] + options[1:]
        mutated_question = real.base_question.model_copy(update={"options": mutated_options})
        mutated_bp = real.model_copy(update={"base_question": mutated_question})
        flags = question_level_flags(mutated_bp)
        self.assertTrue(any("포괄 표현" in f for f in flags))

    def test_detector_flags_synthetic_sequential_dependency_option(self) -> None:
        real = _SCHOOL_LIFE_BLUEPRINTS[0]
        options = list(real.base_question.options)
        mutated_options = [options[0].model_copy(update={"text": "먼저 살펴본 그 후에 다시 계획한다"})] + options[1:]
        mutated_question = real.base_question.model_copy(update={"options": mutated_options})
        mutated_bp = real.model_copy(update={"base_question": mutated_question})
        flags = question_level_flags(mutated_bp)
        self.assertTrue(any("순차 의존" in f for f in flags))

    def test_st_replan_no_longer_depends_on_st_map_impact_wording(self) -> None:
        """사용자가 직접 지적한 사례(systems_thinking_school_life_v1의 st_replan이
        st_map_impact 없이는 나올 수 없는 생각처럼 읽혔던 문제) 재발 방지."""

        bp = V2_DIRECT_PROBE_BLUEPRINTS_BY_ID["systems_thinking_school_life_v1"]
        replan_text = next(o.text for o in bp.base_question.options if o.role_id == "st_replan")
        for marker in SEQUENTIAL_DEPENDENCY_MARKERS:
            self.assertNotIn(marker, replan_text)


if __name__ == "__main__":
    unittest.main()
