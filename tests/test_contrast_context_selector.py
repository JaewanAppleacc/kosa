"""Contrast Context Selector(§5-1/§6-5) 테스트 — 손계산 기반."""

from __future__ import annotations

import unittest

from src.engines.contrast_context_selector import (
    ContextSelectionError,
    select_contrast_context,
    validate_context_id_list,
)
from src.schemas.context import ContextVector


def _vec(value: float) -> ContextVector:
    """모든 축을 같은 값으로 둔 단순화 Fixture — 거리 비교를 한 스칼라 값 비교로 만든다."""
    return ContextVector(
        individual_vs_team=value, digital_vs_physical=value, people_vs_system=value,
        appreciation_vs_creation=value, expression_vs_analysis=value, exploration_vs_goal=value,
    )


TRAIT_LABELS = {"a": "특성A", "b": "특성B"}


class SelectContrastContextTest(unittest.TestCase):
    def _select(self, **overrides):
        defaults = dict(
            preferred_context_ids=["p1", "p2", "p3", "p4"],
            interest_ratings={"p1": 5, "p2": 5, "p3": 5, "p4": 5, "c_near": 2, "c_far": 2},
            all_context_ids={"p1", "p2", "p3", "p4", "c_near", "c_far"},
            context_vectors={
                "p1": _vec(0.0), "p2": _vec(0.0), "p3": _vec(0.0), "p4": _vec(0.0),
                "c_near": _vec(0.1), "c_far": _vec(0.9),
            },
            coverage_matrix={
                "p1": {"a": 0, "b": 0}, "p2": {"a": 0, "b": 0}, "p3": {"a": 0, "b": 0}, "p4": {"a": 0, "b": 0},
                "c_near": {"a": 0, "b": 0}, "c_far": {"a": 0, "b": 0},
            },
            all_trait_ids={"a", "b"},
            trait_labels=TRAIT_LABELS,
        )
        defaults.update(overrides)
        return select_contrast_context(**defaults)

    def test_farther_context_wins_when_coverage_ties(self) -> None:
        """coverage_gain이 동률이면(둘 다 0) context_distance가 큰 쪽(c_far)이 이겨야 한다."""

        result = self._select()
        self.assertEqual(result.contrast_context_id, "c_far")
        self.assertEqual(result.candidate_pool_tier, "interest_2_3")

    def test_coverage_gain_can_tip_the_ranking_between_two_similarly_far_candidates(self) -> None:
        """distance 가중치(0.6)가 coverage_gain 가중치(0.4)보다 커서, 후보가 딱 2개뿐이고
        거리·coverage_gain이 서로 완전히 갈리면 항상 거리가 이긴다(정규화가 0/1로 양극화되고
        0.6 > 0.4라서 구조적으로 그렇다) — 그래서 이 테스트는 "둘 다 비슷하게 먼" 후보
        중, Gap Trait를 보완하는 쪽이 근소하게 덜 먼 경쟁자를 이기는지를 본다(c_high_coverage
        거리=0.90, c_farthest 거리=0.95 — 둘 다 멀지만 c_farthest가 아주 조금 더 멀다)."""

        result = self._select(
            all_context_ids={"p1", "p2", "p3", "p4", "c_high_coverage", "c_farthest", "c_baseline"},
            interest_ratings={
                "p1": 5, "p2": 5, "p3": 5, "p4": 5,
                "c_high_coverage": 2, "c_farthest": 2, "c_baseline": 2,
            },
            context_vectors={
                "p1": _vec(0.0), "p2": _vec(0.0), "p3": _vec(0.0), "p4": _vec(0.0),
                "c_high_coverage": _vec(0.90), "c_farthest": _vec(0.95), "c_baseline": _vec(0.1),
            },
            coverage_matrix={
                "p1": {"a": 0, "b": 0}, "p2": {"a": 0, "b": 0}, "p3": {"a": 0, "b": 0}, "p4": {"a": 0, "b": 0},
                "c_high_coverage": {"a": 3, "b": 3}, "c_farthest": {"a": 0, "b": 0}, "c_baseline": {"a": 0, "b": 0},
            },
        )
        self.assertEqual(result.contrast_context_id, "c_high_coverage")

    def test_already_selected_contexts_are_never_candidates(self) -> None:
        """선호 4개 중 하나가 관심도 2~3점이어도(이론상 재선택 방지 확인) 후보에서 제외돼야
        한다 — p1을 관심도 3점으로 바꿔도 후보 풀에 남으면 안 된다."""

        result = self._select(interest_ratings={"p1": 3, "p2": 5, "p3": 5, "p4": 5, "c_near": 2, "c_far": 2})
        self.assertNotIn(result.contrast_context_id, {"p1", "p2", "p3", "p4"})

    def test_tied_score_breaks_alphabetically(self) -> None:
        """거리·coverage_gain이 완전히 동일하면 context_id 알파벳 순으로 결정론적으로 고른다."""

        result = self._select(
            context_vectors={
                "p1": _vec(0.0), "p2": _vec(0.0), "p3": _vec(0.0), "p4": _vec(0.0),
                "c_near": _vec(0.5), "c_far": _vec(0.5),
            },
        )
        self.assertEqual(result.contrast_context_id, "c_far")  # "c_far" < "c_near" 알파벳순

    def test_falls_back_to_wider_interest_tier_when_2_3_pool_empty(self) -> None:
        """관심도 2~3점 후보가 아예 없으면 4~5점으로, 그것도 없으면 1점으로 단계적으로
        넓힌다(§5-1: "1점은 학생이 직접 허용한 경우에만")."""

        result_45 = self._select(
            interest_ratings={"p1": 5, "p2": 5, "p3": 5, "p4": 5, "c_near": 4, "c_far": 5},
        )
        self.assertEqual(result_45.candidate_pool_tier, "interest_4_5_widened")

        result_1 = self._select(
            interest_ratings={"p1": 5, "p2": 5, "p3": 5, "p4": 5, "c_near": 1, "c_far": 1},
        )
        self.assertEqual(result_1.candidate_pool_tier, "interest_1_last_resort")

    def test_no_rated_candidate_still_returns_a_valid_context_id(self) -> None:
        """API 계약상 contrast_context_id는 항상 str이어야 한다 — 관심도 정보가 아예
        없어도(1~5 어디에도 안 걸림) None이 아니라 결정론적 후보를 반환해야 한다."""

        result = self._select(interest_ratings={"p1": 5, "p2": 5, "p3": 5, "p4": 5})
        self.assertIn(result.contrast_context_id, {"c_near", "c_far"})
        self.assertEqual(result.candidate_pool_tier, "no_rated_candidate_arbitrary_fallback")

    def test_reason_text_reflects_actual_preferred_context_count(self) -> None:
        """2026-08-22 3차 리뷰 항목 4: 예전엔 실제 선호 개수와 무관하게 "선택한 4개
        Context"라고 고정 출력됐다 — Vertical Slice(2개)·Full Mode(4개) 양쪽에서 문구가
        실제 개수를 반영해야 한다."""

        two_selected = self._select(
            preferred_context_ids=["p1", "p2"],
            interest_ratings={"p1": 5, "p2": 5, "c_near": 2, "c_far": 2},
            context_vectors={
                "p1": _vec(0.0), "p2": _vec(0.0), "c_near": _vec(0.1), "c_far": _vec(0.9),
            },
            coverage_matrix={
                "p1": {"a": 0, "b": 0}, "p2": {"a": 0, "b": 0},
                "c_near": {"a": 0, "b": 0}, "c_far": {"a": 0, "b": 0},
            },
        )
        self.assertIn("선택한 2개 Context", two_selected.contrast_reason)
        self.assertNotIn("4개", two_selected.contrast_reason)

        four_selected = self._select()  # 기본값이 4개 선호
        self.assertIn("선택한 4개 Context", four_selected.contrast_reason)

    def test_does_not_require_or_use_student_trait_state(self) -> None:
        """CLAUDE.md: "관심 Context 선택 점수를 Trait 점수로 직접 변환하지 않는다" —
        함수 시그니처 자체에 학생 Trait 상태·전공 순위를 받는 자리가 없다는 걸 구조적으로
        확인한다(관심도 dict[str,int]만 입력, TraitEvidenceSummary류는 전혀 등장하지 않음)."""

        import inspect

        params = inspect.signature(select_contrast_context).parameters
        self.assertNotIn("trait_summaries", params)
        self.assertNotIn("student_states", params)
        self.assertNotIn("major_relevance", params)


class ValidateContextIdListTest(unittest.TestCase):
    """2026-08-22 6항목: Context 선택·확정 입력 구조 검증."""

    ALL_IDS = {"game", "media", "school_life", "business", "making"}

    def test_empty_list_rejected(self) -> None:
        with self.assertRaises(ContextSelectionError):
            validate_context_id_list([], self.ALL_IDS, minimum_count=1, label="테스트")

    def test_duplicate_context_rejected(self) -> None:
        with self.assertRaises(ContextSelectionError):
            validate_context_id_list(["game", "game"], self.ALL_IDS, minimum_count=1, label="테스트")

    def test_unknown_context_rejected(self) -> None:
        with self.assertRaises(ContextSelectionError):
            validate_context_id_list(["game", "not_a_real_context"], self.ALL_IDS, minimum_count=1, label="테스트")

    def test_below_minimum_count_rejected(self) -> None:
        with self.assertRaises(ContextSelectionError):
            validate_context_id_list(["game"], self.ALL_IDS, minimum_count=2, label="테스트")

    def test_valid_list_passes_without_raising(self) -> None:
        validate_context_id_list(["game", "media"], self.ALL_IDS, minimum_count=2, label="테스트")  # 예외 없으면 통과

    # --- 2026-08-30 20차 리뷰: maximum_count 추가 ---

    def test_maximum_count_none_by_default_no_upper_bound(self) -> None:
        """기존 호출부(maximum_count를 안 넘기는 곳)는 그대로 상한 없이 동작해야 한다."""

        validate_context_id_list(
            ["game", "media", "school_life", "business", "making"],
            self.ALL_IDS, minimum_count=1, label="테스트",
        )  # 예외 없으면 통과 — 5개 전부 넘겨도 상한이 없다.

    def test_above_maximum_count_rejected(self) -> None:
        with self.assertRaises(ContextSelectionError):
            validate_context_id_list(
                ["game", "media", "school_life"], self.ALL_IDS,
                minimum_count=1, maximum_count=2, label="테스트",
            )

    def test_exactly_maximum_count_passes(self) -> None:
        validate_context_id_list(
            ["game", "media"], self.ALL_IDS, minimum_count=1, maximum_count=2, label="테스트",
        )  # 예외 없으면 통과

    def test_minimum_equals_maximum_expresses_exact_count(self) -> None:
        with self.assertRaises(ContextSelectionError):
            validate_context_id_list(
                ["game"], self.ALL_IDS, minimum_count=2, maximum_count=2, label="테스트",
            )
        with self.assertRaises(ContextSelectionError):
            validate_context_id_list(
                ["game", "media", "school_life"], self.ALL_IDS,
                minimum_count=2, maximum_count=2, label="테스트",
            )
        validate_context_id_list(
            ["game", "media"], self.ALL_IDS, minimum_count=2, maximum_count=2, label="테스트",
        )  # 예외 없으면 통과 — 정확히 2개만 허용


if __name__ == "__main__":
    unittest.main()
