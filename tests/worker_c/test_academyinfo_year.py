"""조사연도 선택 테스트 — A 지시 §10.

실제 네트워크를 쓰지 않는다. 핵심은 "수정일을 조사연도로 오인하지 않는다"이다.
"""

from __future__ import annotations

import unittest
from typing import Any

from src.data_sources.academyinfo_client import AcademyInfoClient, RetryPolicy
from src.data_sources.academyinfo_year import (
    PUBLIC_API_METADATA_MODIFIED_AT,
    SurveyYearUnavailableError,
    parse_supported_years,
    select_survey_year,
)


def year_response(*years: int) -> str:
    items = "".join(f"<item><yearVal>{y}</yearVal></item>" for y in years)
    return (
        "<response><header><resultCode>00</resultCode><resultMsg>OK</resultMsg></header>"
        f"<body><items>{items}</items><numOfRows>100</numOfRows>"
        f"<pageNo>1</pageNo><totalCount>{len(years)}</totalCount></body></response>"
    )


def client_for(xml: str) -> AcademyInfoClient:
    def transport(_url: str, _params: dict[str, Any]) -> tuple[int, str]:
        return 200, xml

    return AcademyInfoClient(
        "fake/key==",
        transport=transport,
        retry=RetryPolicy(max_attempts=1, base_delay_s=0),
        sleep=lambda _s: None,
    )


class YearSelectionTest(unittest.TestCase):
    def test_selects_2026_when_supported(self) -> None:
        sel = select_survey_year(client_for(year_response(2026, 2025, 2024)))
        self.assertEqual(sel.selected_year, 2026)
        self.assertEqual(sel.supported_years, [2026, 2025, 2024])

    def test_selects_2025_when_2026_not_supported(self) -> None:
        sel = select_survey_year(client_for(year_response(2025, 2024, 2023)))
        self.assertEqual(sel.selected_year, 2025)
        self.assertIn("2025", sel.reason)

    def test_reason_records_why(self) -> None:
        """Manifest에 들어갈 문장이라 '왜 그 연도인지'가 읽혀야 한다."""
        sel = select_survey_year(client_for(year_response(2025, 2024)))
        self.assertIn("최신", sel.reason)

    def test_metadata_modified_date_is_not_used_as_survey_year(self) -> None:
        """수정일이 2026이어도 API가 2026을 안 주면 2026을 고르지 않는다."""
        self.assertTrue(PUBLIC_API_METADATA_MODIFIED_AT.startswith("2026"))
        sel = select_survey_year(client_for(year_response(2025, 2024, 2023)))
        self.assertNotEqual(sel.selected_year, 2026)
        self.assertIn(PUBLIC_API_METADATA_MODIFIED_AT, sel.reason)

    def test_empty_year_list_raises_structured_error(self) -> None:
        """지원연도가 없으면 기본값으로 넘어가지 않고 멈춘다."""
        with self.assertRaises(SurveyYearUnavailableError):
            select_survey_year(client_for(year_response()))

    def test_nodata_response_raises_structured_error(self) -> None:
        nodata = (
            "<response><header><resultCode>03</resultCode>"
            "<resultMsg>NODATA_ERROR</resultMsg></header><body/></response>"
        )
        with self.assertRaises(SurveyYearUnavailableError):
            select_survey_year(client_for(nodata))

    def test_explicit_request_must_be_supported(self) -> None:
        with self.assertRaises(SurveyYearUnavailableError):
            select_survey_year(client_for(year_response(2025, 2024)), requested=2026)

    def test_explicit_request_is_honored_when_supported(self) -> None:
        sel = select_survey_year(client_for(year_response(2026, 2025)), requested=2025)
        self.assertEqual(sel.selected_year, 2025)
        self.assertIn("명시", sel.reason)


class PreviousYearTest(unittest.TestCase):
    """A 지시 §4: 최신연도와 직전 지원연도를 비교한다."""

    def test_previous_year_is_next_supported_below(self) -> None:
        sel = select_survey_year(client_for(year_response(2026, 2025, 2024)))
        self.assertEqual(sel.previous_year, 2025)

    def test_previous_year_skips_gaps(self) -> None:
        sel = select_survey_year(client_for(year_response(2026, 2023)))
        self.assertEqual(sel.previous_year, 2023, "연속 연도가 아니어도 직전 '지원연도'를 쓴다")

    def test_previous_year_none_when_only_one(self) -> None:
        sel = select_survey_year(client_for(year_response(2025)))
        self.assertIsNone(sel.previous_year)


class ParseTest(unittest.TestCase):
    def test_non_numeric_values_are_dropped(self) -> None:
        rows = [{"yearVal": "2025"}, {"yearVal": "미정"}, {"yearVal": ""}, {"yearVal": "2024"}]
        self.assertEqual(parse_supported_years(rows), [2025, 2024])

    def test_duplicates_collapse_and_sort_descending(self) -> None:
        rows = [{"yearVal": "2024"}, {"yearVal": "2026"}, {"yearVal": "2024"}]
        self.assertEqual(parse_supported_years(rows), [2026, 2024])


if __name__ == "__main__":
    unittest.main()
