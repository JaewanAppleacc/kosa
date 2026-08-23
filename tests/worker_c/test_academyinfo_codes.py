"""공식 코드 기반 판정 테스트 — 지시서 §7·§8-1."""

from __future__ import annotations

import unittest

from src.data_sources.academyinfo_codes import (
    FOUR_YEAR_OR_LONGER_TERM_CODES,
    is_four_year_or_longer,
    is_series_unclassified,
    is_university,
    undergraduate_scope_reason,
)


def row(**over: str) -> dict[str, str]:
    base = {
        "schlKndCd": "03",
        "schlKndNm": "대학교",
        "pbnfDgriCrseDivCd": "3",
        "pbnfDgriCrseDivNm": "학사",
        "lsnTrmCd": "07",
        "korMjrNm": "컴퓨터공학과",
        "srsMclftCd": "05",
        "srsSclftCd": "051",
        "korSrsMclftNm": "컴퓨터·통신",
        "korSrsSclftNm": "컴퓨터공학",
    }
    base.update(over)
    return base


class LessonTermTest(unittest.TestCase):
    def test_four_year_is_included(self) -> None:
        self.assertTrue(is_four_year_or_longer(row(lsnTrmCd="07")))

    def test_six_year_medical_is_included(self) -> None:
        """의·치·한의·수의예과는 6년(11)이다. '정확히 4년'으로 잡으면 통째로 빠진다."""
        self.assertTrue(is_four_year_or_longer(row(lsnTrmCd="11")))
        self.assertIsNone(undergraduate_scope_reason(row(lsnTrmCd="11", korMjrNm="의예과")))

    def test_seven_year_is_included(self) -> None:
        self.assertTrue(is_four_year_or_longer(row(lsnTrmCd="13")))

    def test_three_year_is_excluded(self) -> None:
        self.assertFalse(is_four_year_or_longer(row(lsnTrmCd="05")))

    def test_specialized_short_courses_are_excluded_despite_high_code(self) -> None:
        """14·15는 코드값이 13보다 크지만 실제 연한은 1~2년이다.

        `>= "07"` 같은 부등호로 거르면 이 둘이 딸려 들어온다 — 명시적 집합이어야 하는 이유.
        """
        self.assertFalse(is_four_year_or_longer(row(lsnTrmCd="14")))
        self.assertFalse(is_four_year_or_longer(row(lsnTrmCd="15")))
        self.assertNotIn("14", FOUR_YEAR_OR_LONGER_TERM_CODES)
        self.assertNotIn("15", FOUR_YEAR_OR_LONGER_TERM_CODES)

    def test_unknown_or_missing_code_is_excluded(self) -> None:
        """모르는 값을 포함으로 처리하면 근거 없는 학과가 조용히 들어온다."""
        self.assertFalse(is_four_year_or_longer(row(lsnTrmCd="")))
        self.assertFalse(is_four_year_or_longer(row(lsnTrmCd="99")))

    def test_unpadded_code_is_normalized(self) -> None:
        self.assertTrue(is_four_year_or_longer(row(lsnTrmCd="7")))


class SchoolKindTest(unittest.TestCase):
    def test_university_passes(self) -> None:
        self.assertTrue(is_university(row(schlKndCd="03")))

    def test_non_university_is_rejected_by_code_not_name(self) -> None:
        """이름에 '대학'이 들어가도 종류 코드가 다르면 제외된다 (§7 학교명 추측 금지)."""
        junior = row(schlKndCd="04", schlKndNm="전문대학")
        self.assertFalse(is_university(junior))
        self.assertIn("전문대학", undergraduate_scope_reason(junior) or "")


class ScopeReasonTest(unittest.TestCase):
    def test_included_row_has_no_reason(self) -> None:
        self.assertIsNone(undergraduate_scope_reason(row()))

    def test_reason_names_the_official_field_value(self) -> None:
        """제외 근거에 공식 필드 값이 들어가야 나중에 사람이 판정을 되짚을 수 있다."""
        reason = undergraduate_scope_reason(row(lsnTrmCd="05"))
        self.assertIsNotNone(reason)
        self.assertIn("3년", reason or "")

    def test_graduate_course_is_excluded(self) -> None:
        reason = undergraduate_scope_reason(row(pbnfDgriCrseDivCd="4", pbnfDgriCrseDivNm="석사"))
        self.assertIn("석사", reason or "")


class SeriesClassificationTest(unittest.TestCase):
    def test_classified_series_is_not_flagged(self) -> None:
        self.assertFalse(is_series_unclassified(row()))

    def test_nce_by_code_is_flagged(self) -> None:
        """실제 응답에서 연세대 교양과가 99/999로 왔다."""
        self.assertTrue(is_series_unclassified(row(srsMclftCd="99", srsSclftCd="999")))

    def test_nce_by_label_is_flagged_even_if_code_changes(self) -> None:
        self.assertTrue(
            is_series_unclassified(row(srsMclftCd="88", korSrsMclftNm="N.C.E"))
        )

    def test_small_series_alone_is_enough(self) -> None:
        self.assertTrue(is_series_unclassified(row(srsSclftCd="999")))


if __name__ == "__main__":
    unittest.main()
