"""대학알리미 클라이언트 테스트 — 지시서 §11.

전부 Fake transport로 돈다. 실제 네트워크도, 실제 Key도 쓰지 않는다.
"""

from __future__ import annotations

import unittest
from typing import Any

import httpx

from src.data_sources.academyinfo_client import (
    AcademyInfoClient,
    AuthError,
    QuotaError,
    RequestError,
    RetryPolicy,
    SchemaDriftError,
    TransientError,
    normalize_service_key,
)

FAKE_KEY = "fake+decoding/key=="


def envelope(items_xml: str, *, page_no: int = 1, num_of_rows: int = 10, total: int = 1) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        "<response><header><resultCode>00</resultCode>"
        "<resultMsg>NORMAL SERVICE.</resultMsg></header>"
        f"<body><items>{items_xml}</items>"
        f"<numOfRows>{num_of_rows}</numOfRows><pageNo>{page_no}</pageNo>"
        f"<totalCount>{total}</totalCount></body></response>"
    )


def error_envelope(code: str, msg: str = "ERR") -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<response><header><resultCode>{code}</resultCode>"
        f"<resultMsg>{msg}</resultMsg></header><body/></response>"
    )


def major_item(schl_mjr_id: str, name: str = "컴퓨터공학과") -> str:
    return (
        "<item>"
        f"<schlId>0000149</schlId><schlMjrId>{schl_mjr_id}</schlMjrId>"
        f"<korMjrNm>{name}</korMjrNm><korSchlNm>연세대학교</korSchlNm>"
        "<clgNm>공과대학</clgNm><schlMjrStatNm>기존</schlMjrStatNm>"
        "<lsnTrmNm>4년</lsnTrmNm><schlKndCd>03</schlKndCd>"
        "<srsLclftCd>C</srsLclftCd><korSrsLclftNm>공학계열</korSrsLclftNm>"
        "<svyYr>2025</svyYr>"
        "</item>"
    )


class FakeTransport:
    """호출을 기록하고 미리 정한 응답을 순서대로 돌려준다."""

    def __init__(self, responses: list[tuple[int, str] | Exception]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, url: str, params: dict[str, Any]) -> tuple[int, str]:
        self.calls.append((url, dict(params)))
        nxt = self._responses.pop(0) if self._responses else (200, envelope(""))
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def make_client(responses: list[Any], **kw: Any) -> tuple[AcademyInfoClient, FakeTransport]:
    transport = FakeTransport(responses)
    client = AcademyInfoClient(
        FAKE_KEY,
        transport=transport,
        retry=kw.pop("retry", RetryPolicy(max_attempts=3, base_delay_s=0)),
        sleep=lambda _s: None,
        **kw,
    )
    return client, transport


class ServiceKeyTest(unittest.TestCase):
    def test_encoding_key_is_normalized(self) -> None:
        """Encoding 키를 넣어도 동작해야 한다 — 실제로 사람이 가장 자주 틀리는 지점."""
        self.assertEqual(normalize_service_key("ab%2Fcd%2Bef"), "ab/cd+ef")

    def test_decoding_key_is_unchanged(self) -> None:
        self.assertEqual(normalize_service_key("ab/cd+ef=="), "ab/cd+ef==")

    def test_empty_key_fails_fast(self) -> None:
        with self.assertRaises(AuthError):
            AcademyInfoClient("   ")


class ErrorClassificationTest(unittest.TestCase):
    """지시서 §3: 실패를 5종으로 구분한다."""

    def test_auth_error_is_not_retried(self) -> None:
        client, transport = make_client([(200, error_envelope("30", "SERVICE KEY IS NOT REGISTERED"))])
        with self.assertRaises(AuthError):
            client.fetch_page("S", "op")
        self.assertEqual(len(transport.calls), 1, "인증 실패는 재시도하지 않는다")

    def test_quota_error_is_not_retried(self) -> None:
        client, transport = make_client([(200, error_envelope("22"))])
        with self.assertRaises(QuotaError):
            client.fetch_page("S", "op")
        self.assertEqual(len(transport.calls), 1, "한도 초과를 재시도하면 다음 날 몫까지 태운다")

    def test_request_error_is_not_retried(self) -> None:
        client, _ = make_client([(200, error_envelope("10"))])
        with self.assertRaises(RequestError):
            client.fetch_page("S", "op")

    def test_empty_response_is_not_an_error(self) -> None:
        """NODATA_ERROR(03)는 이름만 ERROR다. 결과 없음은 정상 종료다."""
        client, _ = make_client([(200, error_envelope("03", "NODATA_ERROR"))])
        self.assertIsNone(client.fetch_page("S", "op"))

    def test_unknown_result_code_fails_fast(self) -> None:
        """모르는 코드를 성공이나 일시 오류로 밀어 넣으면 빈 데이터가 정상처럼 저장된다."""
        client, _ = make_client([(200, error_envelope("77", "무언가 새로운 것"))])
        with self.assertRaises(SchemaDriftError):
            client.fetch_page("S", "op")

    def test_non_xml_response_is_schema_drift(self) -> None:
        client, _ = make_client([(200, "<html>503 Service Unavailable</html>")])
        with self.assertRaises(SchemaDriftError):
            client.fetch_page("S", "op")

    def test_gateway_error_envelope_is_recognized(self) -> None:
        """게이트웨이 오류는 cmmMsgHeader/returnReasonCode 형태로 온다."""
        gateway = (
            "<OpenAPI_ServiceResponse><cmmMsgHeader>"
            "<returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg>"
            "<returnReasonCode>30</returnReasonCode>"
            "</cmmMsgHeader></OpenAPI_ServiceResponse>"
        )
        client, _ = make_client([(200, gateway)])
        with self.assertRaises(AuthError):
            client.fetch_page("S", "op")


class RetryTest(unittest.TestCase):
    def test_transient_error_is_retried_then_succeeds(self) -> None:
        client, transport = make_client(
            [(200, error_envelope("05", "SERVICETIMEOUT")), (200, envelope(major_item("1")))]
        )
        page = client.fetch_page("S", "op")
        assert page is not None
        self.assertEqual(len(page.items), 1)
        self.assertEqual(len(transport.calls), 2)

    def test_network_error_is_retried(self) -> None:
        """실제 수집 중 ConnectTimeout이 관측됐다. 재시도 없이 400여 콜은 못 돈다."""
        client, transport = make_client(
            [httpx.ConnectTimeout("timeout"), (200, envelope(major_item("1")))]
        )
        page = client.fetch_page("S", "op")
        assert page is not None
        self.assertEqual(len(transport.calls), 2)

    def test_retry_is_bounded(self) -> None:
        client, transport = make_client([(200, error_envelope("05"))] * 5)
        with self.assertRaises(TransientError):
            client.fetch_page("S", "op")
        self.assertEqual(len(transport.calls), 3, "max_attempts를 넘겨 무한 재시도하지 않는다")

    def test_backoff_grows_exponentially(self) -> None:
        policy = RetryPolicy(max_attempts=5, base_delay_s=1.0, multiplier=2.0, max_delay_s=30.0)
        self.assertEqual([policy.delay_for(n) for n in (1, 2, 3, 4)], [1.0, 2.0, 4.0, 8.0])

    def test_backoff_is_capped(self) -> None:
        policy = RetryPolicy(base_delay_s=1.0, multiplier=10.0, max_delay_s=5.0)
        self.assertEqual(policy.delay_for(4), 5.0)


class PaginationTest(unittest.TestCase):
    def test_iterates_until_total_count_reached(self) -> None:
        pages = [
            (200, envelope(major_item("1") + major_item("2"), page_no=1, num_of_rows=2, total=5)),
            (200, envelope(major_item("3") + major_item("4"), page_no=2, num_of_rows=2, total=5)),
            (200, envelope(major_item("5"), page_no=3, num_of_rows=2, total=5)),
        ]
        client, transport = make_client(pages)
        rows = client.fetch_all("S", "op", num_of_rows=2)
        self.assertEqual(len(rows), 5)
        self.assertEqual(len(transport.calls), 3)

    def test_empty_page_terminates_even_if_total_count_lies(self) -> None:
        """서버가 totalCount를 과대 보고해도 빈 페이지에서 멈춘다."""
        pages = [
            (200, envelope(major_item("1"), page_no=1, num_of_rows=1, total=999)),
            (200, envelope("", page_no=2, num_of_rows=1, total=999)),
        ]
        client, _ = make_client(pages)
        self.assertEqual(len(client.fetch_all("S", "op", num_of_rows=1)), 1)

    def test_nodata_on_first_page_yields_nothing(self) -> None:
        client, _ = make_client([(200, error_envelope("03"))])
        self.assertEqual(client.fetch_all("S", "op"), [])


class SecretHygieneTest(unittest.TestCase):
    """지시서 §2: Key와 요청 Query가 로그·오류 메시지에 남지 않는다."""

    def test_key_is_not_in_error_message(self) -> None:
        leaky = error_envelope("30", f"invalid key {FAKE_KEY} rejected")
        client, _ = make_client([(200, leaky)])
        with self.assertRaises(AuthError) as ctx:
            client.fetch_page("S", "op")
        self.assertNotIn(FAKE_KEY, str(ctx.exception))
        self.assertIn("***SERVICE_KEY***", str(ctx.exception))

    def test_key_is_not_in_network_error_message(self) -> None:
        client, _ = make_client(
            [httpx.ConnectTimeout(f"failed for key={FAKE_KEY}")] * 4,
            retry=RetryPolicy(max_attempts=1, base_delay_s=0),
        )
        with self.assertRaises(TransientError) as ctx:
            client.fetch_page("S", "op")
        self.assertNotIn(FAKE_KEY, str(ctx.exception))

    def test_url_never_contains_the_key(self) -> None:
        """Key는 params로만 넘긴다 — URL 문자열에 박아 두면 로그로 새기 쉽다."""
        client, transport = make_client([(200, envelope(major_item("1")))])
        client.fetch_page("S", "op")
        url, params = transport.calls[0]
        self.assertNotIn(FAKE_KEY, url)
        self.assertEqual(params["serviceKey"], normalize_service_key(FAKE_KEY))


class RequestShapeTest(unittest.TestCase):
    def test_department_request_carries_school_id(self) -> None:
        client, transport = make_client([(200, envelope(major_item("1")))])
        client.fetch_departments(2025, school_id="0000149")
        _url, params = transport.calls[0]
        self.assertEqual(params["schlId"], "0000149")
        self.assertEqual(params["svyYr"], 2025)

    def test_none_params_are_dropped(self) -> None:
        """schlId 생략 시 빈 값을 보내면 서버가 파라미터 오류로 거절한다."""
        client, transport = make_client([(200, envelope(major_item("1")))])
        client.fetch_departments(2025, school_id=None)
        _url, params = transport.calls[0]
        self.assertNotIn("schlId", params)

    def test_items_keep_original_field_names(self) -> None:
        """원본 필드명을 클라이언트에서 바꾸지 않는다 — 정규화는 별도 단계다(§5)."""
        client, _ = make_client([(200, envelope(major_item("0012796")))])
        rows = client.fetch_all("S", "op")
        self.assertEqual(rows[0]["schlMjrId"], "0012796")
        self.assertEqual(rows[0]["korSrsLclftNm"], "공학계열")


if __name__ == "__main__":
    unittest.main()
