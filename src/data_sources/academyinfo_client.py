"""대학알리미 Open API 클라이언트 — 지시서 §3·§4.

이 모듈은 **가져오기만** 한다. 정규화·4년제 판정·계열 분류는 하지 않는다.

설계 근거는 `rationale_c/07-academyinfo-collection.md`에 정리했다. 코드에서 반복 설명하지
않고, 유지보수 중 "왜 이렇게 했지" 하고 멈추게 되는 지점에만 짧게 남긴다.

두 서비스를 쓴다(같은 인증키, 다른 경로):

    BasicInformationService_2   대학 목록·학교종류/유형/지역/공시년도 코드
    BasicInformationService_1   학교별 학과 + 표준분류 대·중·소계열 코드
"""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator
from urllib.parse import unquote

import httpx

ACADEMYINFO_BASE_URL = "https://apis.data.go.kr/B340014"
UNIVERSITY_SERVICE = "BasicInformationService_2"
MAJOR_SERVICE = "BasicInformationService_1"

# 공식 출처 표기용. Key가 붙지 않은 URL만 쓴다 (지시서 §6).
ACADEMYINFO_DATASET_URL = "https://www.data.go.kr/data/15158963/openapi.do"
ACADEMYINFO_PORTAL_URL = "https://www.academyinfo.go.kr/"


class AcademyInfoError(Exception):
    """이 모듈이 던지는 모든 오류의 뿌리. Key가 절대 메시지에 들어가지 않는다."""


class AuthError(AcademyInfoError):
    """인증 실패. 재시도해도 달라지지 않으므로 즉시 중단한다."""


class QuotaError(AcademyInfoError):
    """일일 호출 한도 초과. 재시도하면 다음 날 몫까지 태운다 — 중단하고 사람이 판단한다."""


class RequestError(AcademyInfoError):
    """요청 파라미터가 틀렸다. 우리 쪽 버그이므로 재시도하지 않는다."""


class TransientError(AcademyInfoError):
    """일시적 서버·네트워크 오류. 이것만 재시도 대상이다."""


class SchemaDriftError(AcademyInfoError):
    """응답 구조가 계약과 다르다. 조용히 넘기면 빈 데이터가 정상처럼 저장된다 — Fail-Fast."""


# data.go.kr 공통 resultCode. 모르는 코드를 임의로 '성공'이나 '일시 오류'에 밀어 넣지 않는다.
_AUTH_CODES = {"20", "21", "30", "31", "32", "33"}
_QUOTA_CODES = {"22"}
_REQUEST_CODES = {"10", "11", "12"}
_TRANSIENT_CODES = {"01", "02", "04", "05", "99"}
_EMPTY_CODES = {"03"}  # NODATA_ERROR — 이름은 ERROR지만 "결과 없음"이라 오류가 아니다.
_OK_CODES = {"00"}


@dataclass(frozen=True)
class ApiPage:
    """한 페이지 응답. Pagination 종료 판단에 필요한 값만 담는다."""

    items: list[dict[str, str]]
    page_no: int
    num_of_rows: int
    total_count: int

    @property
    def is_last(self) -> bool:
        # totalCount를 신뢰하되, 빈 페이지도 종료로 본다(서버가 totalCount를 과대 보고하는 경우 대비).
        if not self.items:
            return True
        return self.page_no * self.num_of_rows >= self.total_count


@dataclass
class RetryPolicy:
    """지수 Backoff. 지시서 §4 "제한된 재시도·지수 Backoff"."""

    max_attempts: int = 4
    base_delay_s: float = 1.0
    multiplier: float = 2.0
    max_delay_s: float = 30.0

    def delay_for(self, attempt: int) -> float:
        return min(self.base_delay_s * (self.multiplier ** (attempt - 1)), self.max_delay_s)


def normalize_service_key(raw: str) -> str:
    """Encoding 키가 들어와도 동작하게 한 번 푼다.

    httpx가 Query String을 다시 인코딩하므로, Encoding 키(`%2F`·`%2B` 포함)를 그대로 넘기면
    `%252F`로 이중 인코딩되어 인증에 실패한다. Decoding 키에 unquote를 걸어도 값이 변하지
    않으므로 양쪽 모두 안전하다.
    """
    return unquote(raw.strip())


def _mask(text: str, secret: str) -> str:
    """예외 메시지·로그에서 Key를 지운다 (지시서 §2: Key 앞부분도 남기지 않는다)."""
    if not secret:
        return text
    return text.replace(secret, "***SERVICE_KEY***").replace(
        unquote(secret), "***SERVICE_KEY***"
    )


def _parse_envelope(xml_text: str) -> tuple[str, str, ET.Element | None]:
    """(resultCode, resultMsg, body) 추출.

    data.go.kr은 인증 실패도 **HTTP 200**으로 내려준다. 상태코드로 성공을 판단하면 인증
    실패가 '빈 결과'로 둔갑한다 — 그래서 항상 본문의 resultCode를 본다.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise SchemaDriftError(f"XML로 파싱되지 않는 응답입니다: {exc}") from exc

    # 정상 응답은 <response><header><resultCode>, 게이트웨이 오류는 <OpenAPI_ServiceResponse>
    # 아래 <cmmMsgHeader><returnReasonCode> 형태로 온다. 둘 다 받는다.
    code_el = root.find(".//resultCode")
    msg_el = root.find(".//resultMsg")
    if code_el is None:
        code_el = root.find(".//returnReasonCode")
        msg_el = root.find(".//returnAuthMsg")
    if code_el is None or code_el.text is None:
        raise SchemaDriftError("응답에 resultCode가 없습니다.")

    code = code_el.text.strip().zfill(2)
    msg = (msg_el.text or "").strip() if msg_el is not None else ""
    return code, msg, root.find(".//body")


def _parse_items(body: ET.Element | None) -> ApiPage:
    if body is None:
        raise SchemaDriftError("응답에 body가 없습니다.")

    items: list[dict[str, str]] = []
    for item in body.findall("./items/item"):
        # 자식 태그를 그대로 dict로 옮긴다. 필드 이름을 여기서 바꾸지 않는다 —
        # 원본 보존(§5)은 정규화 단계와 분리되어야 재현이 가능하다.
        items.append({child.tag: (child.text or "") for child in item})

    def _int(tag: str, default: int) -> int:
        el = body.find(tag)
        if el is None or not (el.text or "").strip():
            return default
        try:
            return int(el.text.strip())
        except ValueError as exc:
            raise SchemaDriftError(f"{tag}가 정수가 아닙니다: {el.text!r}") from exc

    return ApiPage(
        items=items,
        page_no=_int("pageNo", 1),
        num_of_rows=_int("numOfRows", len(items) or 1),
        total_count=_int("totalCount", len(items)),
    )


class AcademyInfoClient:
    """대학알리미 API 호출기.

    `transport`를 주입하면 실제 네트워크 없이 테스트할 수 있다(지시서 §11: 테스트는
    Fake Client/Fixture를 쓰고 실제 네트워크나 실제 Key에 의존하지 않는다).
    """

    def __init__(
        self,
        service_key: str,
        *,
        base_url: str = ACADEMYINFO_BASE_URL,
        timeout_s: float = 30.0,
        request_delay_ms: int = 0,
        retry: RetryPolicy | None = None,
        transport: Callable[[str, dict[str, Any]], tuple[int, str]] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not service_key.strip():
            raise AuthError("DATA_GO_KR_SERVICE_KEY가 비어 있습니다. .env를 확인하세요.")
        self._key = normalize_service_key(service_key)
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._request_delay_ms = request_delay_ms
        self._retry = retry or RetryPolicy()
        self._transport = transport
        self._sleep = sleep
        self.call_count = 0

    # ── 저수준 ────────────────────────────────────────────────────────

    def _send(self, url: str, params: dict[str, Any]) -> tuple[int, str]:
        if self._transport is not None:
            return self._transport(url, params)
        response = httpx.get(url, params=params, timeout=self._timeout_s)
        return response.status_code, response.text

    def fetch_page(
        self,
        service: str,
        operation: str,
        *,
        page_no: int = 1,
        num_of_rows: int = 100,
        **params: Any,
    ) -> ApiPage | None:
        """한 페이지를 가져온다. 결과가 없으면(정상 빈 응답) None.

        오류는 지시서 §3이 요구한 5종으로 구분해 던진다:
        인증(AuthError) / 한도(QuotaError) / 정상 빈 응답(None) /
        Schema 변경(SchemaDriftError) / 일시 오류(TransientError).
        """
        url = f"{self._base_url}/{service}/{operation}"
        query: dict[str, Any] = {
            "serviceKey": self._key,
            "pageNo": page_no,
            "numOfRows": num_of_rows,
            **{k: v for k, v in params.items() if v is not None},
        }

        last_transient: Exception | None = None
        for attempt in range(1, self._retry.max_attempts + 1):
            if self._request_delay_ms:
                self._sleep(self._request_delay_ms / 1000)
            try:
                status, text = self._send(url, query)
                self.call_count += 1
            except httpx.HTTPError as exc:
                # 네트워크 계층 실패는 일시 오류로 본다. 실제로 수집 중 ConnectTimeout이
                # 관측됐다 — 재시도 없이 400여 콜을 돌리면 중간에 통째로 깨진다.
                last_transient = TransientError(
                    f"{operation} 네트워크 오류: {_mask(type(exc).__name__, self._key)}"
                )
            else:
                if status >= 500:
                    last_transient = TransientError(f"{operation} HTTP {status}")
                else:
                    try:
                        return self._interpret(operation, text)
                    except TransientError as exc:
                        # resultCode가 일시 오류(01/02/04/05/99)인 경우도 재시도 대상이다.
                        # 네트워크 실패만 재시도하면 서버측 일시 오류에서 그냥 죽는다.
                        last_transient = exc

            if attempt < self._retry.max_attempts:
                self._sleep(self._retry.delay_for(attempt))

        assert last_transient is not None
        raise last_transient

    def _interpret(self, operation: str, text: str) -> ApiPage | None:
        code, msg, body = _parse_envelope(_mask(text, self._key))
        safe = f"{operation}: [{code}] {msg}"

        if code in _OK_CODES:
            return _parse_items(body)
        if code in _EMPTY_CODES:
            return None
        if code in _AUTH_CODES:
            raise AuthError(
                f"{safe} — 인증 실패입니다. .env의 DATA_GO_KR_SERVICE_KEY가 Decoding 키인지, "
                f"해당 서비스에 활용신청이 승인됐는지 확인하세요."
            )
        if code in _QUOTA_CODES:
            raise QuotaError(f"{safe} — 일일 호출 한도를 넘었습니다. --resume으로 이어서 받으세요.")
        if code in _REQUEST_CODES:
            raise RequestError(f"{safe} — 요청 파라미터 문제입니다.")
        if code in _TRANSIENT_CODES:
            raise TransientError(safe)
        raise SchemaDriftError(f"{safe} — 정의되지 않은 resultCode입니다.")

    # ── 고수준 ────────────────────────────────────────────────────────

    def iter_pages(
        self,
        service: str,
        operation: str,
        *,
        num_of_rows: int = 100,
        max_pages: int | None = None,
        **params: Any,
    ) -> Iterator[ApiPage]:
        """Pagination이 끝날 때까지 순회한다 (지시서 §4)."""
        page_no = 1
        while True:
            page = self.fetch_page(
                service, operation, page_no=page_no, num_of_rows=num_of_rows, **params
            )
            if page is None:
                return
            yield page
            if page.is_last:
                return
            if max_pages is not None and page_no >= max_pages:
                return
            page_no += 1

    def fetch_all(
        self, service: str, operation: str, *, num_of_rows: int = 100, **params: Any
    ) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for page in self.iter_pages(service, operation, num_of_rows=num_of_rows, **params):
            rows.extend(page.items)
        return rows

    # ── 이번 작업에서 쓰는 오퍼레이션 ────────────────────────────────

    def fetch_code_table(self, service: str, operation: str, survey_year: int) -> list[dict[str, str]]:
        """코드표(cdid/cdnm) 조회. 계열·학교종류·학과상태 등 판정 근거의 원본이다."""
        return self.fetch_all(service, operation, svyYr=survey_year, num_of_rows=1000)

    def fetch_universities(self, survey_year: int, *, num_of_rows: int = 100) -> list[dict[str, str]]:
        return self.fetch_all(
            UNIVERSITY_SERVICE,
            "getComparisonUniversitySearchList",
            svyYr=survey_year,
            num_of_rows=num_of_rows,
        )

    def fetch_departments(
        self, survey_year: int, *, school_id: str | None = None, num_of_rows: int = 100
    ) -> list[dict[str, str]]:
        """학과 조회. `school_id`를 주면 그 대학만, 생략하면 전국 전체를 페이지네이션한다."""
        return self.fetch_all(
            MAJOR_SERVICE,
            "getUniversityMajorCode",
            svyYr=survey_year,
            schlId=school_id,
            num_of_rows=num_of_rows,
        )


# 코드표 목록. 판정 근거로 실제 쓰는 것만 받는다 — 근거로 안 쓸 표를 받아두면
# "원본에 있으니 맞겠지"라는 착시가 생긴다(rationale_c/07 §7-3).
CODE_TABLES: tuple[tuple[str, str, str], ...] = (
    (MAJOR_SERVICE, "getCodeByLargeSeries", "표준분류 대계열"),
    (MAJOR_SERVICE, "getCodeByMiddleSeries", "표준분류 중계열"),
    (MAJOR_SERVICE, "getCodeBySmallSeries", "표준분류 소계열"),
    (MAJOR_SERVICE, "getCodeBySeriesSystem", "표준분류 계열체계"),
    (MAJOR_SERVICE, "getCodeByMajorStatus", "학과상태"),
    (MAJOR_SERVICE, "getCodeByLessonTerm", "수업연한"),
    (MAJOR_SERVICE, "getCodeByDegreeCourse", "학위과정"),
    (MAJOR_SERVICE, "getCodeByCollege", "단과대학"),
    (MAJOR_SERVICE, "getCodeByMajorCharacter", "학과특성"),
    (MAJOR_SERVICE, "getCodeByOneselfSeries", "대학자체계열"),
    (MAJOR_SERVICE, "getCodeByPrincipalSchoolBranchSchool", "본분교"),
    (MAJOR_SERVICE, "getCodeByDayAndNight", "주야간"),
    (UNIVERSITY_SERVICE, "getCodeByKind", "학교종류"),
    (UNIVERSITY_SERVICE, "getCodeByType", "학교유형"),
    (UNIVERSITY_SERVICE, "getCodeByRegion", "지역"),
    (UNIVERSITY_SERVICE, "getComparisonPubYear", "공시년도"),
)
