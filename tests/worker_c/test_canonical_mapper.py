"""canonical_mapper 계약 테스트 — §17의 "자동 확정 금지" 규칙이 실제로 지켜지는지 본다."""

from __future__ import annotations

import unittest

from src.engines.canonical_mapper import (
    CanonicalMajorEntry,
    CanonicalMapper,
    confirm,
    match_key,
    match_keys,
    normalize_department_name,
    review_required,
)
from src.schemas.major import Department
from tests.worker_c.fixtures import department

ENTRIES = [
    CanonicalMajorEntry(
        major_id="computer_science",
        label="컴퓨터·소프트웨어",
        aliases=["컴퓨터공학", "컴퓨터과학", "소프트웨어"],
        keywords=["프로그래밍", "알고리즘"],
        source_url="https://www.career.go.kr/",
        as_of_date="2026-08-21",
    ),
    CanonicalMajorEntry(
        major_id="design",
        label="디자인",
        aliases=["디자인", "시각디자인"],
        keywords=["조형", "사용자"],
        source_url="https://www.career.go.kr/",
        as_of_date="2026-08-21",
    ),
    CanonicalMajorEntry(
        major_id="education",
        label="교육학",
        aliases=["교육학"],
        keywords=["수업", "학습"],
        source_url="https://www.career.go.kr/",
        as_of_date="2026-08-21",
    ),
]


class NormalizationTest(unittest.TestCase):
    def test_decorations_are_stripped(self) -> None:
        self.assertEqual(normalize_department_name("「경영학과」"), "경영학과")
        self.assertEqual(normalize_department_name("경영학과 (주간)"), "경영학과")
        self.assertEqual(normalize_department_name("　심리학과 "), "심리학과")

    def test_match_keys_include_both_suffix_readings(self) -> None:
        """"컴퓨터공학부"는 "학부"를 떼면 "컴퓨터공"이 되지만 실제로 떼야 할 건 "부"다."""

        keys = match_keys("컴퓨터공학부")
        self.assertIn("컴퓨터공학", keys)
        self.assertIn("컴퓨터공학부", keys)
        self.assertEqual(keys, sorted(keys, key=len, reverse=True))

    def test_match_key_keeps_written_form(self) -> None:
        self.assertEqual(match_key("컴퓨터공학부"), "컴퓨터공학부")


class CanonicalMapperTest(unittest.TestCase):
    def setUp(self) -> None:
        self.mapper = CanonicalMapper(ENTRIES)

    def _map(self, name: str, college: str = "공과대학") -> Department:
        return department(department_name=name, college_name=college)

    def test_exact_alias_auto_maps(self) -> None:
        result = self.mapper.map(self._map("컴퓨터공학부"))
        self.assertEqual(result.mapping_status, "AUTO_MAPPED")
        self.assertEqual(result.primary_candidate, "computer_science")
        self.assertEqual(result.mapping_method, "exact_alias")
        self.assertTrue(result.evidence)

    def test_alias_containment_auto_maps(self) -> None:
        result = self.mapper.map(self._map("컴퓨터소프트웨어학부"))
        self.assertEqual(result.mapping_status, "AUTO_MAPPED")
        self.assertEqual(result.primary_candidate, "computer_science")

    def test_unmatched_name_never_auto_maps(self) -> None:
        """Embedding 후보는 순위만 있을 뿐 확신이 아니므로 자동 확정하면 안 된다."""

        result = self.mapper.map(self._map("자유전공학부", "자유전공학부"))
        self.assertEqual(result.mapping_status, "REVIEW_REQUIRED")
        self.assertEqual(result.mapping_method, "embedding_plus_curriculum")
        self.assertTrue(result.secondary_candidates)

    def test_evidence_has_no_raw_confidence_number(self) -> None:
        """§17: `confidence: 0.84` 같은 미보정 수치를 근거로 남기지 않는다."""

        result = self.mapper.map(self._map("자유전공학부", "자유전공학부"))
        joined = " ".join(result.evidence).lower()
        self.assertNotIn("confidence", joined)
        self.assertNotIn("0.", joined)  # 0.84 같은 소수 점수를 근거로 적지 않는다

    def test_llm_classifier_result_still_requires_review(self) -> None:
        class AlwaysDesign:
            def classify(self, department: Department, candidate_major_ids: list[str]) -> str | None:
                return "design"

        mapper = CanonicalMapper(ENTRIES, classifier=AlwaysDesign())
        result = mapper.map(self._map("자유전공학부", "자유전공학부"))
        self.assertEqual(result.mapping_status, "REVIEW_REQUIRED")
        self.assertEqual(result.mapping_method, "llm_structured")
        self.assertEqual(result.primary_candidate, "design")

    def test_llm_classifier_returning_unknown_id_is_ignored(self) -> None:
        class Nonsense:
            def classify(self, department: Department, candidate_major_ids: list[str]) -> str | None:
                return "존재하지_않는_전공"

        mapper = CanonicalMapper(ENTRIES, classifier=Nonsense())
        result = mapper.map(self._map("자유전공학부", "자유전공학부"))
        self.assertEqual(result.mapping_method, "embedding_plus_curriculum")
        self.assertIn("고르지 못했다", " ".join(result.evidence))

    def test_confirm_is_the_only_path_to_confirmed(self) -> None:
        result = self.mapper.map(self._map("자유전공학부", "자유전공학부"))
        before = {result.primary_candidate, *result.secondary_candidates}
        chosen = sorted(before - {result.primary_candidate})[0]
        confirmed = confirm(result, reviewer_id="worker_a", chosen_major_id=chosen)

        self.assertEqual(confirmed.mapping_status, "CONFIRMED")
        self.assertEqual(confirmed.primary_candidate, chosen)
        # 고른 후보는 secondary에 남지 않고, 나머지 후보는 그대로 보존된다.
        self.assertNotIn(chosen, confirmed.secondary_candidates)
        self.assertEqual({chosen, *confirmed.secondary_candidates}, before)
        self.assertIn("worker_a", confirmed.evidence[-1])

    def test_review_required_filter(self) -> None:
        results = self.mapper.map_all(
            [self._map("컴퓨터공학부"), self._map("자유전공학부", "자유전공학부")]
        )
        pending = review_required(results)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].mapping_status, "REVIEW_REQUIRED")

    def test_ambiguous_alias_is_flagged_not_guessed(self) -> None:
        """같은 매칭 키가 두 major의 alias에 걸리면 자동 확정하지 않는다."""

        entries = ENTRIES + [
            CanonicalMajorEntry(
                major_id="media_design",
                label="미디어디자인",
                aliases=["디자인"],  # design과 같은 alias를 일부러 넣는다
                keywords=[],
                source_url="https://www.career.go.kr/",
                as_of_date="2026-08-21",
            )
        ]
        mapper = CanonicalMapper(entries)
        result = mapper.map(self._map("디자인학부", "예술대학"))
        self.assertEqual(result.mapping_status, "REVIEW_REQUIRED")
        self.assertEqual(result.mapping_method, "exact_alias")
        self.assertIn("design", [result.primary_candidate, *result.secondary_candidates])
        self.assertIn("media_design", [result.primary_candidate, *result.secondary_candidates])

    def test_empty_catalog_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CanonicalMapper([])


if __name__ == "__main__":
    unittest.main()
