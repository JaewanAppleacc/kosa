"""38개 Group 기반 + hci_ux 특수 융합 1개 = 39개 서비스 Major에 대한 Subject-Major
Mapping 확장 계약 테스트 — a/subject-mapping-38-majors 지시서 §6."""

from __future__ import annotations

import unittest

from scripts.career_build_subject_major_mapping_v2_expansion import (
    FORBIDDEN_MAJOR_IDS,
    MAJOR_LINKS,
)
from scripts.career_build_subject_major_mapping_v2_expansion import (
    _generate_link_records as build_link_records,
)
from scripts.career_build_subject_profiles_v2 import build as build_subject_profiles_v2
from scripts.career_build_subject_trait_mapping_evidence_v2 import (
    NEW_SUBJECT_TRAIT_EVIDENCE,
)
from scripts.career_build_subject_trait_mapping_evidence_v2 import (
    build as build_trait_evidence_v2,
)
from src.engines.subject_matching_engine_v2 import (
    compute_post_offering_recommendations_v2,
    compute_subject_recommendations_v2,
)
from src.schemas.trait import TraitDefinition
from src.schemas.trait_vector_snapshot import TraitVectorEntry
from src.services.service_canonical_major_v2_loader import load_service_canonical_majors_v2

_ARTS_EXCLUDED_MAJOR_IDS = frozenset({"fine_arts_design", "music", "performing_media_arts", "sports_dance"})


class DeterminismTest(unittest.TestCase):
    def test_link_evidence_generation_is_deterministic(self) -> None:
        first = [r.model_dump_json() for r in build_link_records()]
        second = [r.model_dump_json() for r in build_link_records()]
        self.assertEqual(first, second)

    def test_trait_evidence_build_is_deterministic(self) -> None:
        first = [r.model_dump_json() for r in build_trait_evidence_v2()]
        second = [r.model_dump_json() for r in build_trait_evidence_v2()]
        self.assertEqual(first, second)

    def test_subject_profiles_build_is_deterministic(self) -> None:
        first = [p.model_dump_json() for p in build_subject_profiles_v2()]
        second = [p.model_dump_json() for p in build_subject_profiles_v2()]
        self.assertEqual(first, second)


class HciUxAndArtsSportsSafetyTest(unittest.TestCase):
    """지시서 필수 준수 — hci_ux는 DEPARTMENT_LEVEL_ONLY(과목 단위 자동 연결 금지),
    fine_arts_design 등 예체능 4개 Group은 추천 Mapping 생성 금지."""

    def test_no_new_hci_ux_links_generated(self) -> None:
        hci_targets = {label for label, links in MAJOR_LINKS.items() if any(m == "hci_ux" for m, _ in links)}
        self.assertEqual(hci_targets, set())

    def test_no_arts_sports_group_links_generated(self) -> None:
        bad = {
            (label, major_id) for label, links in MAJOR_LINKS.items() for major_id, _ in links
            if major_id in _ARTS_EXCLUDED_MAJOR_IDS
        }
        self.assertEqual(bad, set())

    def test_forbidden_major_ids_constant_matches_policy(self) -> None:
        self.assertEqual(FORBIDDEN_MAJOR_IDS, {"hci_ux"} | _ARTS_EXCLUDED_MAJOR_IDS)

    def test_hci_ux_only_carries_preexisting_legacy_links(self) -> None:
        """v2 최종 산출물에서 hci_ux에 연결된 과목은 Legacy `subjects.jsonl`이 이미
        갖고 있던 2개(정보·소프트웨어와 생활)뿐이어야 한다 — 새 과목이 여기 추가로
        딸려오면 안 된다(computer_science Group 전체 자동 연결 금지의 실측 검증)."""

        profiles = build_subject_profiles_v2()
        hci_ux_subjects = {p.label for p in profiles if "hci_ux" in p.related_major_ids}
        self.assertEqual(hci_ux_subjects, {"정보", "소프트웨어와 생활"})


class TraitPolicyTest(unittest.TestCase):
    """신규 확장분(§2)이 EVIDENCED로 매긴 Trait는 전부 Legacy 12-Trait
    (VERTICAL_SLICE_TRAIT_IDS) 안에 있어야 한다 — v2 신규 12개 Trait는 이번 라운드가
    공식 성취기준을 재확인하지 않았으므로 EVIDENCED로 매길 수 없다는 프로젝트 규칙
    (`career_build_major_trait_mapping_evidence_v2.py`와 같은 원칙)."""

    def test_new_subject_evidence_uses_only_legacy_traits(self) -> None:
        from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAIT_IDS

        for label, trait_grades in NEW_SUBJECT_TRAIT_EVIDENCE.items():
            with self.subTest(label=label):
                self.assertTrue(set(trait_grades).issubset(VERTICAL_SLICE_TRAIT_IDS))


class QualityDifferentiationTest(unittest.TestCase):
    """지시서 §3 — 서로 다른 Major가 전부 같은 과목 목록이 되지 않아야 하고, 문과
    (법·정치·인문)·자연과학(화학·지구과학)·공학(기계·전기전자)·교육·사회 영역이
    골고루 커버돼야 한다."""

    def test_majors_do_not_all_share_identical_subject_sets(self) -> None:
        profiles = build_subject_profiles_v2()
        subject_sets_by_major: dict[str, frozenset[str]] = {}
        for p in profiles:
            for major_id in p.related_major_ids:
                subject_sets_by_major.setdefault(major_id, set()).add(p.subject_id)
        frozen_sets = {frozenset(s) for s in subject_sets_by_major.values()}
        # 39개 Major가 전부 정확히 같은 과목 집합이면 안 된다 — 서로 다른 집합이
        # 최소 여러 개는 있어야 한다(완전히 획일화되지 않았다는 증거).
        self.assertGreater(len(frozen_sets), 10)

    def test_covers_humanities_social_and_engineering_fields(self) -> None:
        profiles = build_subject_profiles_v2()
        served_majors = {m for p in profiles for m in p.related_major_ids}
        for expected in ("law", "political_science", "humanities", "chemistry", "mechanical_engineering", "education", "sociology"):
            with self.subTest(major_id=expected):
                self.assertIn(expected, served_majors)


class ThirtyNineMajorCoverageTest(unittest.TestCase):
    def test_all_39_majors_have_core_eligible_subject(self) -> None:
        catalog = {m.major_id for m in load_service_canonical_majors_v2()}
        self.assertEqual(len(catalog), 39)

        profiles = build_subject_profiles_v2()
        by_major: dict[str, list[int]] = {}
        for p in profiles:
            for major_id in p.related_major_ids:
                by_major.setdefault(major_id, []).append(len(p.trait_vector))

        for major_id in sorted(catalog):
            with self.subTest(major_id=major_id):
                self.assertIn(major_id, by_major)
                self.assertTrue(any(count >= 2 for count in by_major[major_id]))


class NewMajorPreSurveyPostOfferingE2ETest(unittest.TestCase):
    """지시서 §2 "PRE_SURVEY/POST_OFFERING 호환" — 새로 커버된 Major(law, 원래
    Vertical Slice 3개 밖) 하나를 골라 실제 Matching Engine으로 PRE_SURVEY→POST_OFFERING
    전체 흐름을 검증한다. Mock/API를 거치지 않고 Engine 함수를 직접 호출해 빠르고
    정확하게 확인한다."""

    MAJOR_ID = "law"

    def _subjects(self):
        return [p for p in build_subject_profiles_v2() if self.MAJOR_ID in p.related_major_ids]

    def _student_entries(self, subjects) -> dict[str, TraitVectorEntry]:
        """대상 Major의 모든 후보 과목의 모든 Trait를 강하게 확정한 학생 벡터 —
        core 카테고리가 실제로 나오는지 확인하기 위해 의도적으로 강한 신호를 준다."""

        trait_ids: set[str] = set()
        for s in subjects:
            trait_ids.update(t for t, w in s.trait_vector.items() if w > 0)
        return {
            trait_id: TraitVectorEntry(
                trait_id=trait_id, primary_signal_sum=1.0, related_signal_sum=0.0,
                confirmed_related_signal_sum=0.0, primary_evidence_count=3, related_evidence_count=0,
                context_count=2, frame_count=2, question_count=3, tendency_score=1.0,
                evidence_confidence="primary_evidence", status="STRONG",
            )
            for trait_id in trait_ids
        }

    def test_pre_survey_produces_core_recommendation(self) -> None:
        subjects = self._subjects()
        self.assertTrue(subjects, f"{self.MAJOR_ID}: 후보 과목이 0건이다")
        entries = self._student_entries(subjects)

        results = compute_subject_recommendations_v2(entries, self.MAJOR_ID, subjects)
        self.assertTrue(results, "PRE_SURVEY 추천이 0건이다 — 희망과목 화면이 비어있게 된다")
        self.assertTrue(any(r.category == "core" for r in results), "core 카테고리가 하나도 없다")

    def test_post_offering_provides_alternative_when_core_missing(self) -> None:
        subjects = self._subjects()
        entries = self._student_entries(subjects)
        original = compute_subject_recommendations_v2(entries, self.MAJOR_ID, subjects)
        core_ids = [r.subject_id for r in original if r.category == "core"]
        explore_ids = [r.subject_id for r in original if r.category == "explore"]
        self.assertTrue(core_ids, "PRE_SURVEY core가 없어 POST_OFFERING 대체 시나리오를 만들 수 없다")

        # 학교가 core 과목은 개설하지 않고 explore 과목만 개설했다고 가정한다.
        confirmed_offered = set(explore_ids)
        trait_definitions = {
            trait_id: TraitDefinition(
                trait_id=trait_id, label=trait_id, parent_dimension="테스트", definition="def",
                positive_indicators=["a"], conflicting_indicators=["b"], source_references=["c"],
                trait_scope="shared", minimum_context_count=1, primary_vector_group="cognitive",
            )
            for trait_id in entries
        }

        recommendations, unavailable = compute_post_offering_recommendations_v2(
            entries, self.MAJOR_ID, subjects, confirmed_offered, "법학", trait_definitions,
        )
        unavailable_ids = {u.subject_id for u in unavailable}
        self.assertTrue(set(core_ids).issubset(unavailable_ids), "미개설 core가 unavailable 목록에 없다")
        if explore_ids:
            alternative_items = [r for r in recommendations if r.category == "alternative"]
            self.assertTrue(alternative_items, "대체 가능한 explore 과목이 있는데 alternative가 비었다")
            for item in alternative_items:
                self.assertTrue(item.is_actually_offered)
                self.assertIsNotNone(item.replaces_subject_id)


if __name__ == "__main__":
    unittest.main()
