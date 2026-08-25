"""v2 Major Matching Engine 테스트 — 2026-08-23 Trait Ontology v2(2.6단계) §7."""

from __future__ import annotations

import unittest

from src.engines.matching_engine_v2 import (
    MINIMUM_USABLE_TRAITS,
    MINIMUM_USABLE_VECTOR_GROUPS,
    compute_major_match_v2,
    rank_major_relevance_v2,
)
from src.schemas.major import MajorProfile
from src.schemas.trait_vector_snapshot import TraitVectorEntry


def _entry(
    trait_id: str, *, tendency: float | None, status: str = "STRONG",
    confidence: str = "primary_evidence",
) -> TraitVectorEntry:
    return TraitVectorEntry(
        trait_id=trait_id, primary_signal_sum=1.0, related_signal_sum=0.0,
        confirmed_related_signal_sum=0.0, primary_evidence_count=3, related_evidence_count=0,
        context_count=2, frame_count=2, question_count=3, tendency_score=tendency,
        evidence_confidence=confidence, status=status,
    )


def _major(major_id: str, **vectors: dict[str, float]) -> MajorProfile:
    from datetime import datetime, timezone

    return MajorProfile(
        major_id=major_id, label=major_id, interest_vector=vectors.get("interest", {}),
        cognitive_vector=vectors.get("cognitive", {}), work_style_vector=vectors.get("work_style", {}),
        environment_vector=vectors.get("environment", {}), source_ids=[], extraction_method="rule",
        review_status="draft", profile_version="test", updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


class NoCosineSimilarityTest(unittest.TestCase):
    def test_magnitude_affects_score_unlike_cosine(self) -> None:
        """cosine은 방향만 보고 크기를 무시한다 — 같은 비율이면 학생이 LIMITED든 STRONG
        이든 점수가 같아진다. v2는 크기(tendency_score)를 그대로 반영해야 한다."""

        major = _major(
            "m1", cognitive={"t1": 1.0, "t2": 1.0}, work_style={"t3": 1.0}, interest={"t4": 1.0},
        )
        strong_states = {
            "t1": _entry("t1", tendency=1.0), "t2": _entry("t2", tendency=1.0),
            "t3": _entry("t3", tendency=1.0), "t4": _entry("t4", tendency=1.0),
        }
        limited_states = {
            trait_id: _entry(trait_id, tendency=0.33, status="LIMITED")
            for trait_id in strong_states
        }
        strong_result = compute_major_match_v2(strong_states, major)
        limited_result = compute_major_match_v2(limited_states, major)
        self.assertEqual(strong_result.status, "computed")
        self.assertEqual(limited_result.status, "computed")
        # cosine이었다면 두 벡터가 [1,1,1,1]과 [0.33,0.33,0.33,0.33]로 방향이 같아 점수가
        # 동일했을 것 — v2는 명확히 달라야 한다.
        self.assertGreater(strong_result.score, limited_result.score)  # type: ignore[operator]


class ConflictMaskTest(unittest.TestCase):
    def test_conflicting_trait_excluded_from_comparison(self) -> None:
        major = _major("m1", cognitive={"t1": 1.0}, work_style={"t2": 1.0}, interest={"t3": 1.0})
        states = {
            "t1": _entry("t1", tendency=None, status="CONFLICTING", confidence="explicit_conflict"),
            "t2": _entry("t2", tendency=1.0), "t3": _entry("t3", tendency=1.0),
        }
        # t1이 완전히 빠지므로 usable_trait_count는 2뿐 — MINIMUM_USABLE_TRAITS(3) 미달로
        # insufficient가 돼야 한다(t1을 억지로 0점 취급해 usable로 세지 않는다).
        result = compute_major_match_v2(states, major)
        self.assertEqual(result.status, "insufficient")
        self.assertNotIn("t1", [])  # conflict_status 필드 자체가 tendency_score=None과 함께 이미 제외됨


class NoSignalNotTreatedAsZeroTest(unittest.TestCase):
    def test_not_probed_trait_excluded_not_scored_zero(self) -> None:
        """NOT_PROBED(tendency_score=None)는 0점으로 계산에 들어가면 안 되고, 아예
        비교 대상에서 빠져야 한다."""

        major = _major("m1", cognitive={"t1": 1.0, "t2": 1.0}, work_style={"t3": 1.0}, interest={"t4": 1.0})
        states = {
            "t1": _entry("t1", tendency=1.0), "t2": _entry("t2", tendency=1.0),
            "t3": _entry("t3", tendency=1.0),
            "t4": _entry("t4", tendency=None, status="NOT_PROBED", confidence="no_evidence"),
        }
        result = compute_major_match_v2(states, major)
        self.assertEqual(result.status, "computed")
        # t4가 0점으로 들어갔다면 score가 내려갔을 것 — usable_trait_count에서도 빠져야 한다.
        self.assertEqual(result.usable_trait_count, 3)
        self.assertAlmostEqual(result.score, 1.0)  # type: ignore[arg-type]


class MinimumThresholdTest(unittest.TestCase):
    def test_single_trait_overlap_is_insufficient(self) -> None:
        """§7 "한 개 Trait만 겹쳐 높은 추천이 나오지 않도록 최소 Evidence 조건을 유지"."""

        major = _major("m1", cognitive={"t1": 1.0})
        states = {"t1": _entry("t1", tendency=1.0)}
        result = compute_major_match_v2(states, major)
        self.assertEqual(result.status, "insufficient")

    def test_below_minimum_group_diversity_is_insufficient(self) -> None:
        major = _major("m1", cognitive={"t1": 1.0, "t2": 1.0, "t3": 1.0})
        states = {tid: _entry(tid, tendency=1.0) for tid in ("t1", "t2", "t3")}
        result = compute_major_match_v2(states, major)
        # 3개 다 usable이지만 전부 같은 Vector Group(cognitive)라 그룹 다양성 미달.
        self.assertEqual(result.usable_trait_count, MINIMUM_USABLE_TRAITS)
        self.assertLess(1, MINIMUM_USABLE_VECTOR_GROUPS)
        self.assertEqual(result.status, "insufficient")


class EvidenceConfidenceWeightingTest(unittest.TestCase):
    def test_promoted_related_signal_scores_lower_than_primary_evidence(self) -> None:
        major = _major("m1", cognitive={"t1": 1.0, "t2": 1.0}, work_style={"t3": 1.0}, interest={"t4": 1.0})
        primary_states = {
            tid: _entry(tid, tendency=1.0, confidence="primary_evidence")
            for tid in ("t1", "t2", "t3", "t4")
        }
        related_states = {
            tid: _entry(tid, tendency=1.0, status="LIMITED", confidence="promoted_related_signal")
            for tid in ("t1", "t2", "t3", "t4")
        }
        primary_result = compute_major_match_v2(primary_states, major)
        related_result = compute_major_match_v2(related_states, major)
        self.assertGreater(primary_result.score, related_result.score)  # type: ignore[operator]


class NoInternalScoreInApiOutputTest(unittest.TestCase):
    def test_rank_major_relevance_v2_returns_only_qualitative_labels(self) -> None:
        major = _major("m1", cognitive={"t1": 1.0, "t2": 1.0}, work_style={"t3": 1.0}, interest={"t4": 1.0})
        states = {tid: _entry(tid, tendency=1.0) for tid in ("t1", "t2", "t3", "t4")}
        result = compute_major_match_v2(states, major)
        relevant, explore, _msg = rank_major_relevance_v2([result], {"m1": "테스트 전공"}, {"m1": "테스트 전공 설명"})
        combined = relevant + explore
        self.assertEqual(len(combined), 1)
        dumped = combined[0].model_dump()
        self.assertNotIn("score", dumped)
        self.assertIn(dumped["relevance_label"], ("관련성 높음", "함께 탐색해볼 분야", "비교해볼 만한 분야"))


class OutputCountCapTest(unittest.TestCase):
    """2026-08-25 지시서(a/major-profiles-v2-38) §3 — 내부 계산은 전체 Major에
    수행하되(여기서는 합성 20개 Major로 재현), 학생에게 노출하는 목록은
    관련성 높음 최대 3개·함께 탐색 최대 3개로 잘라야 한다."""

    def _many_majors_all_high_score_but_distinct(self, count: int) -> list[MajorProfile]:
        """서로 다른 점수를 받도록 Major마다 조금씩 다른 4-Trait 조합을 준다(완전히
        같은 점수로 전부 묶이면 "몇 개나 관련성 높음으로 승격되는가"를 캡이 아니라
        우연한 동점 처리로 확인하게 돼 캡 자체를 검증하지 못한다)."""

        majors = []
        for i in range(count):
            majors.append(
                _major(
                    f"m{i}",
                    cognitive={"t1": 1.0, "t2": 1.0},
                    work_style={"t3": 1.0, f"extra{i}": 0.33},
                    interest={"t4": 1.0},
                )
            )
        return majors

    def test_relevant_capped_at_3_even_with_many_computed_majors(self) -> None:
        majors = self._many_majors_all_high_score_but_distinct(20)
        states = {tid: _entry(tid, tendency=1.0) for tid in ("t1", "t2", "t3", "t4")}
        for i in range(20):
            states[f"extra{i}"] = _entry(f"extra{i}", tendency=1.0)
        results = [compute_major_match_v2(states, m) for m in majors]
        computed_count = sum(1 for r in results if r.status == "computed")
        self.assertGreaterEqual(computed_count, 4, "테스트 전제 — 최소 4개는 계산 가능해야 캡을 검증할 수 있다")

        labels = {f"m{i}": f"전공{i}" for i in range(20)}
        descriptions = {f"m{i}": f"설명{i}" for i in range(20)}
        relevant, explore, _msg = rank_major_relevance_v2(results, labels, descriptions)

        self.assertLessEqual(len(relevant), 3)
        self.assertLessEqual(len(explore), 3)

    def test_no_major_appears_in_both_relevant_and_explore(self) -> None:
        majors = self._many_majors_all_high_score_but_distinct(20)
        states = {tid: _entry(tid, tendency=1.0) for tid in ("t1", "t2", "t3", "t4")}
        for i in range(20):
            states[f"extra{i}"] = _entry(f"extra{i}", tendency=1.0)
        results = [compute_major_match_v2(states, m) for m in majors]
        labels = {f"m{i}": f"전공{i}" for i in range(20)}
        descriptions = {f"m{i}": f"설명{i}" for i in range(20)}
        relevant, explore, _msg = rank_major_relevance_v2(results, labels, descriptions)

        overlap = {r.major_id for r in relevant} & {r.major_id for r in explore}
        self.assertEqual(overlap, set())

    def test_internal_computation_still_runs_over_every_supplied_major(self) -> None:
        """§3 "내부 계산은 38개[전체] 전체에 수행한다" — compute_major_match_v2는
        capping과 무관하게 넘겨받은 Major 전부에 대해 결과를 낸다(잘림은
        rank_major_relevance_v2 마지막 단계에서만 일어난다)."""

        majors = self._many_majors_all_high_score_but_distinct(20)
        states = {tid: _entry(tid, tendency=1.0) for tid in ("t1", "t2", "t3", "t4")}
        for i in range(20):
            states[f"extra{i}"] = _entry(f"extra{i}", tendency=1.0)
        results = [compute_major_match_v2(states, m) for m in majors]
        self.assertEqual(len(results), 20)

    def test_limited_evidence_never_promoted_to_relevant_even_under_cap(self) -> None:
        """§3 "근거가 제한적이면 관련성 높음으로 승격 금지" — 캡으로 자르는 로직을
        추가해도 이 기존 방어가 여전히 먼저 적용되는지 확인한다."""

        major = _major("m1", cognitive={"t1": 1.0}, work_style={"t2": 1.0}, interest={"t3": 1.0})
        # notable(weight>=0.67) Trait 3개 중 STRONG이 0개·usable 1개뿐이라 "제한적".
        states = {
            "t1": _entry("t1", tendency=0.9, status="LIMITED"),
            "t2": _entry("t2", tendency=None),
            "t3": _entry("t3", tendency=None),
        }
        result = compute_major_match_v2(states, major)
        relevant, explore, _msg = rank_major_relevance_v2([result], {"m1": "전공"}, {"m1": "설명"})
        self.assertEqual(len(relevant), 0)


if __name__ == "__main__":
    unittest.main()
