"""조사연도 선택 — A 지시 §1.

**조사연도를 하드코딩하지 않는다.** 코드에 연도를 박으면, 대학알리미가 새 공시를 열어도
수집기는 계속 옛 연도를 받아 오고 아무도 오류를 보지 못한다. 조용히 낡은 데이터를 쌓는
것이 가장 잡기 어려운 실패다(rationale_c/07 §7-16).

두 가지를 구분한다.

    수정일   공공데이터포털의 API 상품·명세 수정일 (예: 2026-05-04)
    조사연도 데이터가 조사된 연도 (getComparisonPubYear 응답)

수정일이 2026이라고 조사연도가 2026인 것이 아니다. 대학알리미 **웹 화면에 2026 선택지가
있다는 사실도 근거가 아니다** — 웹과 API의 제공 범위는 다를 수 있다. **실제 API 응답만
정본이다.**
"""

from __future__ import annotations

from dataclasses import dataclass

from src.data_sources.academyinfo_client import UNIVERSITY_SERVICE, AcademyInfoClient

# 공공데이터포털에 표시된 API 상품·명세 수정일. **조사연도가 아니다.**
# Manifest에 그대로 기록해, 나중에 "2026이라 적혀 있었는데 왜 2025를 받았나"를 되짚을 수 있게 한다.
PUBLIC_API_METADATA_MODIFIED_AT = "2026-05-04"


class SurveyYearUnavailableError(RuntimeError):
    """지원연도를 하나도 못 받았다. 기본값으로 넘어가지 않고 구조화된 오류로 멈춘다."""


@dataclass(frozen=True)
class SurveyYearSelection:
    supported_years: list[int]
    selected_year: int
    reason: str

    @property
    def previous_year(self) -> int | None:
        """직전 지원연도. 연도 간 비교(A 지시 §4)에 쓴다."""
        earlier = [y for y in self.supported_years if y < self.selected_year]
        return max(earlier) if earlier else None


def parse_supported_years(rows: list[dict[str, str]]) -> list[int]:
    """`getComparisonPubYear` 응답에서 연도만 추린다. 숫자가 아닌 값은 조용히 버리지 않고 제외한다."""
    years: set[int] = set()
    for row in rows:
        raw = (row.get("yearVal") or "").strip()
        if raw.isdigit():
            years.add(int(raw))
    return sorted(years, reverse=True)


def select_survey_year(
    client: AcademyInfoClient, *, requested: int | None = None
) -> SurveyYearSelection:
    """API에 지원연도를 직접 물어보고 수집할 연도를 정한다.

    `requested`는 사람이 명시적으로 지정한 경우에만 쓴다. 지원 목록에 없으면 거부한다 —
    "요청했으니 통과"시키면 하드코딩과 같은 문제가 된다.
    """
    rows = client.fetch_code_table(UNIVERSITY_SERVICE, "getComparisonPubYear", survey_year=0)
    supported = parse_supported_years(rows)
    if not supported:
        raise SurveyYearUnavailableError(
            "getComparisonPubYear가 지원연도를 하나도 돌려주지 않았습니다. "
            "기본 연도로 넘어가지 않고 중단합니다 — API 명세가 바뀌었는지 확인하세요."
        )

    latest = supported[0]
    if requested is not None:
        if requested not in supported:
            raise SurveyYearUnavailableError(
                f"요청한 조사연도 {requested}는 API 지원 목록 {supported}에 없습니다."
            )
        reason = (
            f"사람이 --survey-year {requested}로 명시했고 API 지원 목록에 포함됨 "
            f"(지원: {supported})"
        )
        return SurveyYearSelection(supported, requested, reason)

    reason = (
        f"API가 지원하는 조사연도 {supported} 중 최신값. "
        f"포털 명세 수정일({PUBLIC_API_METADATA_MODIFIED_AT})은 조사연도가 아니므로 근거로 쓰지 않음."
    )
    return SurveyYearSelection(supported, latest, reason)


class MajorDataUnavailableError(RuntimeError):
    """지원연도로 광고되지만 학과 데이터가 실제로는 없다."""


def verify_major_data_available(
    client: AcademyInfoClient, survey_year: int, probe_school_ids: list[str]
) -> tuple[bool, str]:
    """선택한 연도에 **학과 데이터가 실제로 있는지** 표본으로 확인한다.

    `getComparisonPubYear`는 `BasicInformationService_2`(대학 비교통계)의 공시연도다.
    학과는 `BasicInformationService_1`의 `getUniversityMajorCode`로 받는데 **서로 다른
    서비스이고 연도 범위가 다르다.**

    실측(2026-08-24): 공시연도는 [2025, 2024, 2023]인데 학과는 2025만 응답한다.
    2024로 전국 수집을 돌렸더니 대학 376개를 받고 학과 0건이 나왔다 — API 호출 398회를
    쓰고 나서야 알았다. 한 서비스의 연도 목록을 다른 서비스에 그대로 적용한 것이 원인이다.

    그래서 **수집 전에 표본 몇 건으로 먼저 찔러 본다.** 실패는 값싸야 한다.
    """
    for school_id in probe_school_ids[:3]:
        rows = client.fetch_departments(survey_year, school_id=school_id, num_of_rows=5)
        if rows:
            return True, f"조사연도 {survey_year} 학과 데이터 확인 (표본 schlId={school_id})"
    return False, (
        f"조사연도 {survey_year}는 getComparisonPubYear에 지원연도로 나오지만 "
        f"getUniversityMajorCode가 학과를 하나도 돌려주지 않습니다 "
        f"(표본 {probe_school_ids[:3]}). 두 오퍼레이션은 서로 다른 서비스라 연도 범위가 다릅니다."
    )
