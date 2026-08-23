"""전공 추천 설명 필드(MajorRelevance.description) 계약 테스트 — 2026-08-24 A3
지시서 §10.

Canonical Major 정본 데이터, Legacy/v2 Matching 연결, Fail-Fast 규칙, Canonical
Mapping 결과 불변을 확인한다."""

from __future__ import annotations

import json
import unittest
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from src.data.majors.canonical_major_descriptions import CANONICAL_MAJOR_DESCRIPTIONS_BY_ID
from src.data.majors.vertical_slice_major_profiles import VERTICAL_SLICE_MAJOR_PROFILES
from src.data.majors.vertical_slice_major_profiles_v2 import VERTICAL_SLICE_MAJOR_PROFILES_V2
from src.engines.canonical_mapper import CanonicalMajorEntry, CanonicalMapper, load_canonical_majors
from src.engines.matching_engine import MajorMatchResult, MissingMajorDescriptionError, rank_major_relevance
from src.engines.matching_engine_v2 import MajorMatchResultV2, rank_major_relevance_v2
from src.schemas.major import MajorProfile, MajorRelevance

_CANONICAL_MAJORS_PATH = Path(__file__).resolve().parents[1] / "data" / "master" / "canonical_majors.jsonl"


class CanonicalMajorDataTest(unittest.TestCase):
    def setUp(self) -> None:
        self.raw_rows = [json.loads(line) for line in _CANONICAL_MAJORS_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.entries = load_canonical_majors(_CANONICAL_MAJORS_PATH)

    def test_every_row_has_a_description(self) -> None:
        for row in self.raw_rows:
            self.assertIn("description", row, row)

    def test_no_description_is_blank(self) -> None:
        for entry in self.entries:
            self.assertTrue(entry.description.strip(), entry.major_id)

    def test_no_duplicate_major_ids(self) -> None:
        major_ids = [e.major_id for e in self.entries]
        self.assertEqual(len(major_ids), len(set(major_ids)))

    def test_description_length_is_reasonable(self) -> None:
        for entry in self.entries:
            self.assertGreaterEqual(len(entry.description), 20, entry.major_id)
            self.assertLessEqual(len(entry.description), 120, entry.major_id)

    def test_description_is_not_keywords_joined_by_comma(self) -> None:
        """§4 "keywords를 쉼표로 연결해 설명처럼 위장하지 않음"."""

        for entry in self.entries:
            keyword_join = ",".join(entry.keywords)
            self.assertNotEqual(entry.description, keyword_join, entry.major_id)
            # 쉼표로만 나열된 단어 목록 형태가 아니라 실제 문장(조사·서술어 포함)이어야 한다.
            self.assertTrue(entry.description.endswith("니다.") or entry.description.endswith("다."), entry.major_id)

    def test_description_does_not_contain_forbidden_phrases(self) -> None:
        forbidden = ("취업이 잘", "당신에게", "가장 적합", "잘 맞습니다")
        for entry in self.entries:
            for phrase in forbidden:
                self.assertNotIn(phrase, entry.description, f"{entry.major_id}: {phrase!r}")

    def test_schema_rejects_blank_description(self) -> None:
        with self.assertRaises(ValidationError):
            CanonicalMajorEntry(
                major_id="x", label="테스트", description="   ",
                source_url="https://example.com", as_of_date="2026-08-24",
            )

    def test_schema_rejects_percentage_in_description(self) -> None:
        with self.assertRaises(ValidationError):
            CanonicalMajorEntry(
                major_id="x", label="테스트", description="이 전공은 취업률이 90%인 전공 분야입니다.",
                source_url="https://example.com", as_of_date="2026-08-24",
            )

    def test_schema_rejects_guarantee_phrase_in_description(self) -> None:
        with self.assertRaises(ValidationError):
            CanonicalMajorEntry(
                major_id="x", label="테스트", description="당신에게 가장 적합한 전공 분야입니다.",
                source_url="https://example.com", as_of_date="2026-08-24",
            )

    def test_all_vertical_slice_major_profiles_have_a_description(self) -> None:
        for profile in VERTICAL_SLICE_MAJOR_PROFILES:
            self.assertIn(profile.major_id, CANONICAL_MAJOR_DESCRIPTIONS_BY_ID, profile.major_id)
        for profile in VERTICAL_SLICE_MAJOR_PROFILES_V2:
            self.assertIn(profile.major_id, CANONICAL_MAJOR_DESCRIPTIONS_BY_ID, profile.major_id)

    def test_description_is_a_separate_field_from_keywords(self) -> None:
        for entry in self.entries:
            self.assertNotEqual(entry.description, entry.keywords)
            self.assertIsInstance(entry.description, str)
            self.assertIsInstance(entry.keywords, list)


class CanonicalMappingUnaffectedByDescriptionTest(unittest.TestCase):
    """§5 "description 추가 전후 Canonical Mapping 결과 불변" — embedding_text()가
    description을 섞지 않는지 직접 확인하고, description만 다른 두 Entry가 같은
    Mapping 결과를 내는지 확인한다."""

    def test_embedding_text_excludes_description(self) -> None:
        entry = CanonicalMajorEntry(
            major_id="x", label="컴퓨터공학", description="이 문장은 절대 embedding_text에 섞이면 안 된다",
            aliases=["컴공"], keywords=["프로그래밍"], source_url="https://example.com", as_of_date="2026-08-24",
        )
        text = entry.embedding_text()
        self.assertNotIn("절대 embedding_text에 섞이면 안 된다", text)
        self.assertEqual(text, "컴퓨터공학 컴공 프로그래밍")

    def test_mapping_result_identical_regardless_of_description_content(self) -> None:
        def _dept():
            from src.schemas.major import Department

            return Department(
                department_id="d1", university_name="테스트대", region="서울",
                department_name="컴퓨터공학과", college_name="공과대학",
                department_status="EXISTING", source_svy_year=2026,
                source_url="https://example.com",
            )

        entry_a = CanonicalMajorEntry(
            major_id="computer_science", label="컴퓨터·소프트웨어", description="설명 A입니다.",
            aliases=["컴퓨터공학"], keywords=["프로그래밍"], source_url="https://example.com", as_of_date="2026-08-24",
        )
        entry_b = entry_a.model_copy(update={"description": "완전히 다른 설명 B입니다."})

        mapper_a = CanonicalMapper([entry_a])
        mapper_b = CanonicalMapper([entry_b])
        result_a = mapper_a.map(_dept())
        result_b = mapper_b.map(_dept())
        self.assertEqual(result_a.model_dump(), result_b.model_dump())


def _match_result(major_id: str, score: float = 0.8) -> MajorMatchResult:
    return MajorMatchResult(
        major_id=major_id, status="computed", score=score, usable_trait_count=5,
        notable_strong_count=2, notable_usable_count=3, max_context_count_among_notable=3,
    )


def _match_result_v2(major_id: str, score: float = 0.8) -> MajorMatchResultV2:
    return MajorMatchResultV2(
        major_id=major_id, status="computed", score=score, usable_trait_count=5,
        notable_strong_count=2, notable_usable_count=3, max_evidence_count_among_notable=3,
    )


class MajorRelevanceDescriptionTest(unittest.TestCase):
    def test_description_is_required_field(self) -> None:
        with self.assertRaises(ValidationError):
            MajorRelevance(
                major_id="m1", label="테스트전공", relevance_label="관련성 높음",
                evidence_sufficiency="충분", repeated_context_count=1,
            )  # type: ignore[call-arg]

    def test_description_rejects_blank_string(self) -> None:
        with self.assertRaises(ValidationError):
            MajorRelevance(
                major_id="m1", label="테스트전공", description="   ", relevance_label="관련성 높음",
                evidence_sufficiency="충분", repeated_context_count=1,
            )

    def test_no_score_or_relevance_score_field(self) -> None:
        self.assertNotIn("score", MajorRelevance.model_fields)
        self.assertNotIn("relevance_score", MajorRelevance.model_fields)


class LegacyMatchingDescriptionConnectionTest(unittest.TestCase):
    def test_legacy_result_includes_correct_description(self) -> None:
        relevant, explore, _msg = rank_major_relevance(
            [_match_result("m1")], {"m1": "테스트전공"}, {"m1": "테스트전공 설명입니다."},
        )
        combined = relevant + explore
        self.assertEqual(len(combined), 1)
        self.assertEqual(combined[0].description, "테스트전공 설명입니다.")

    def test_legacy_missing_description_fails_fast(self) -> None:
        with self.assertRaises(MissingMajorDescriptionError):
            rank_major_relevance([_match_result("m1")], {"m1": "테스트전공"}, {})

    def test_legacy_missing_description_does_not_fall_back_to_major_id_or_label(self) -> None:
        try:
            rank_major_relevance([_match_result("m1")], {"m1": "테스트전공"}, {})
        except MissingMajorDescriptionError as exc:
            self.assertNotEqual(str(exc), "m1")
            self.assertNotEqual(str(exc), "테스트전공")
        else:
            self.fail("MissingMajorDescriptionError를 기대했다")

    def test_ranking_and_relevance_label_unaffected_by_description_content(self) -> None:
        """§7 "정렬·점수·관련성 Label 계산은 변경하지 않음" — description 값을 바꿔도
        순위·Label은 그대로여야 한다."""

        results = [_match_result("m1", score=0.9), _match_result("m2", score=0.3)]
        labels = {"m1": "높은전공", "m2": "낮은전공"}
        relevant_a, explore_a, _ = rank_major_relevance(results, labels, {"m1": "설명 A", "m2": "설명 B"})
        relevant_b, explore_b, _ = rank_major_relevance(results, labels, {"m1": "완전히 다른 설명", "m2": "또 다른 설명"})
        self.assertEqual(
            [(r.major_id, r.relevance_label) for r in relevant_a + explore_a],
            [(r.major_id, r.relevance_label) for r in relevant_b + explore_b],
        )


class V2MatchingDescriptionConnectionTest(unittest.TestCase):
    def test_v2_result_includes_correct_description(self) -> None:
        relevant, explore, _msg = rank_major_relevance_v2(
            [_match_result_v2("m1")], {"m1": "테스트전공"}, {"m1": "테스트전공 설명입니다."},
        )
        combined = relevant + explore
        self.assertEqual(len(combined), 1)
        self.assertEqual(combined[0].description, "테스트전공 설명입니다.")

    def test_v2_missing_description_fails_fast(self) -> None:
        with self.assertRaises(MissingMajorDescriptionError):
            rank_major_relevance_v2([_match_result_v2("m1")], {"m1": "테스트전공"}, {})

    def test_legacy_and_v2_use_identical_description_for_same_major_id(self) -> None:
        """§7 "Legacy와 v2가 서로 다른 설명을 만들지 않음" — 같은 공용
        CANONICAL_MAJOR_DESCRIPTIONS_BY_ID를 넘기면 두 엔진이 정확히 같은 문자열을
        돌려준다."""

        major_id = "media_communication"
        description = CANONICAL_MAJOR_DESCRIPTIONS_BY_ID[major_id]

        legacy_relevant, legacy_explore, _ = rank_major_relevance(
            [_match_result(major_id)], {major_id: "미디어"}, CANONICAL_MAJOR_DESCRIPTIONS_BY_ID,
        )
        v2_relevant, v2_explore, _ = rank_major_relevance_v2(
            [_match_result_v2(major_id)], {major_id: "미디어"}, CANONICAL_MAJOR_DESCRIPTIONS_BY_ID,
        )
        legacy_item = (legacy_relevant + legacy_explore)[0]
        v2_item = (v2_relevant + v2_explore)[0]
        self.assertEqual(legacy_item.description, description)
        self.assertEqual(v2_item.description, description)
        self.assertEqual(legacy_item.description, v2_item.description)


if __name__ == "__main__":
    unittest.main()
