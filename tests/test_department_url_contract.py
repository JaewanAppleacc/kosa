"""Department.department_url 계약 테스트 — A2 지시서(2026-08-24) §1/§4.

확정된 정책:
- department_url은 공개 API에 추가하는 선택 필드다(학과 공식 홈페이지 URL).
- source_dataset은 추가하지 않는다 — 출처 표시는 source_svy_year + source_url로만
  구성한다.
- 이번 라운드는 Schema·Builder·Repository·API 응답·Mock/OpenAPI·None 처리까지만
  다룬다. C의 검증된 URL 데이터는 아직 통합하지 않는다(실제 저장소
  `data/master/departments.jsonl` 35개는 전부 department_url이 없다).
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.api import main as main_module
from src.api.main import app
from src.repositories.department_repository import JsonlDepartmentRepository
from src.schemas.major import Department

client = TestClient(app)

_BASE_DEPARTMENT_KWARGS = dict(
    department_id="dept_test_url_0001",
    university_name="테스트대학교",
    region="서울",
    department_name="테스트학과",
    college_name="테스트대학",
    department_status="EXISTING",
    source_svy_year=2025,
    source_url="https://www.academyinfo.go.kr/",
)


class SchemaFieldDefaultTest(unittest.TestCase):
    """department_url이 없어도 기존 Department가 정상 생성된다(하위 호환)."""

    def test_department_url_defaults_to_none(self) -> None:
        dept = Department(**_BASE_DEPARTMENT_KWARGS)
        self.assertIsNone(dept.department_url)

    def test_existing_required_fields_unaffected(self) -> None:
        dept = Department(**_BASE_DEPARTMENT_KWARGS)
        self.assertEqual(dept.source_url, "https://www.academyinfo.go.kr/")
        self.assertEqual(dept.source_svy_year, 2025)
        # source_dataset/source_label 필드는 추가하지 않았다(§1 확정 정책).
        self.assertFalse(hasattr(dept, "source_dataset"))
        self.assertFalse(hasattr(dept, "source_label"))


class BlankNormalizationTest(unittest.TestCase):
    """빈 문자열·공백만 있는 값은 None으로 정규화한다(§1 department_url 규칙)."""

    def test_empty_string_normalizes_to_none(self) -> None:
        dept = Department(**_BASE_DEPARTMENT_KWARGS, department_url="")
        self.assertIsNone(dept.department_url)

    def test_whitespace_only_normalizes_to_none(self) -> None:
        dept = Department(**_BASE_DEPARTMENT_KWARGS, department_url="   ")
        self.assertIsNone(dept.department_url)

    def test_surrounding_whitespace_is_stripped(self) -> None:
        dept = Department(**_BASE_DEPARTMENT_KWARGS, department_url="  https://cs.example.ac.kr  ")
        self.assertEqual(dept.department_url, "https://cs.example.ac.kr")


class ValidUrlAcceptedTest(unittest.TestCase):
    def test_https_department_homepage_accepted(self) -> None:
        dept = Department(**_BASE_DEPARTMENT_KWARGS, department_url="https://cs.snu.ac.kr")
        self.assertEqual(dept.department_url, "https://cs.snu.ac.kr")

    def test_http_department_homepage_accepted_but_not_required(self) -> None:
        """HTTPS를 우선하되(§1) http 자체를 하드 거부하지는 않는다 — 데이터 큐레이션
        가이드라인이지 Schema 강제 규칙이 아니다."""

        dept = Department(**_BASE_DEPARTMENT_KWARGS, department_url="http://cs.example.ac.kr")
        self.assertEqual(dept.department_url, "http://cs.example.ac.kr")


class RejectApiKeyUrlTest(unittest.TestCase):
    """API Key가 들어간 URL을 거부한다(§4 필수 테스트)."""

    def test_rejects_service_key_query_param(self) -> None:
        with self.assertRaises(ValidationError):
            Department(
                **_BASE_DEPARTMENT_KWARGS,
                department_url="https://www.academyinfo.go.kr/openapi/svc?serviceKey=SECRET123",
            )

    def test_rejects_api_key_query_param_case_insensitive(self) -> None:
        with self.assertRaises(ValidationError):
            Department(**_BASE_DEPARTMENT_KWARGS, department_url="https://api.example.com/dept?ApiKey=abcd")

    def test_rejects_generic_key_query_param(self) -> None:
        with self.assertRaises(ValidationError):
            Department(**_BASE_DEPARTMENT_KWARGS, department_url="https://api.example.com/dept?key=abcd")

    def test_rejects_academyinfo_openapi_call_url_even_without_key_param(self) -> None:
        """대학알리미 API 호출 URL 자체를 학과 홈페이지로 위장하지 않는다(§1)."""

        with self.assertRaises(ValidationError):
            Department(
                **_BASE_DEPARTMENT_KWARGS,
                department_url="https://www.academyinfo.go.kr/openapi/service/department-list",
            )

    def test_plain_academyinfo_portal_url_is_not_rejected_as_openapi(self) -> None:
        """source_url로 쓰는 대학알리미 포털 URL 자체(경로에 openapi가 없는 경우)는
        department_url로도 구조적으로는 거부하지 않는다 — 다만 "학과 홈페이지로
        위장하지 않는다"는 정책은 Schema가 판단할 수 없는 큐레이션 규칙이라 사람
        검수가 최종 판단한다(§1)."""

        dept = Department(**_BASE_DEPARTMENT_KWARGS, department_url="https://www.academyinfo.go.kr/")
        self.assertEqual(dept.department_url, "https://www.academyinfo.go.kr/")

    def test_rejects_non_absolute_url(self) -> None:
        with self.assertRaises(ValidationError):
            Department(**_BASE_DEPARTMENT_KWARGS, department_url="cs.example.ac.kr")


class SchemeRestrictionTest(unittest.TestCase):
    """A2 후속 보완(2026-08-24) §2-1 — http/https만 허용한다."""

    def test_https_accepted(self) -> None:
        dept = Department(**_BASE_DEPARTMENT_KWARGS, department_url="https://cs.example.ac.kr")
        self.assertEqual(dept.department_url, "https://cs.example.ac.kr")

    def test_http_accepted(self) -> None:
        dept = Department(**_BASE_DEPARTMENT_KWARGS, department_url="http://cs.example.ac.kr")
        self.assertEqual(dept.department_url, "http://cs.example.ac.kr")

    def test_ftp_scheme_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            Department(**_BASE_DEPARTMENT_KWARGS, department_url="ftp://cs.example.ac.kr/homepage")

    def test_file_scheme_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            Department(**_BASE_DEPARTMENT_KWARGS, department_url="file:///etc/passwd")

    def test_javascript_scheme_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            Department(**_BASE_DEPARTMENT_KWARGS, department_url="javascript:alert(document.cookie)")

    def test_mailto_scheme_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            Department(**_BASE_DEPARTMENT_KWARGS, department_url="mailto:dept@example.ac.kr")


class BlankValueApiKeyQueryTest(unittest.TestCase):
    """A2 후속 보완(2026-08-24) §2-2 — 값이 비어 있는 API Key 계열 쿼리 파라미터도
    `parse_qsl(..., keep_blank_values=True)`로 잡아낸다. `parse_qs` 기본값은 빈 값을
    조용히 버려서(`?serviceKey=`가 아예 파라미터 목록에서 사라짐) 이 케이스를
    통과시켜 버리는 구멍이 있었다."""

    def test_blank_service_key_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            Department(**_BASE_DEPARTMENT_KWARGS, department_url="https://example.com/path?serviceKey=")

    def test_blank_api_key_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            Department(**_BASE_DEPARTMENT_KWARGS, department_url="https://example.com/path?api_key=")

    def test_blank_token_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            Department(**_BASE_DEPARTMENT_KWARGS, department_url="https://example.com/path?token=")

    def test_blank_key_among_other_params_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            Department(
                **_BASE_DEPARTMENT_KWARGS,
                department_url="https://example.com/path?lang=ko&serviceKey=&tab=intro",
            )

    def test_case_different_service_key_rejected(self) -> None:
        """대소문자가 다른 파라미터 이름도 걸러야 한다(§2-2 "대소문자 차이 무시")."""

        with self.assertRaises(ValidationError):
            Department(**_BASE_DEPARTMENT_KWARGS, department_url="https://example.com/path?ServiceKey=")

    def test_non_blank_service_key_still_rejected(self) -> None:
        """빈 값 처리를 새로 넣었다고 기존 비어있지 않은 값 차단 동작이 깨지면 안 된다."""

        with self.assertRaises(ValidationError):
            Department(**_BASE_DEPARTMENT_KWARGS, department_url="https://example.com/path?serviceKey=abc123")


class ErrorMessageDoesNotLeakUrlOrSecretTest(unittest.TestCase):
    """A2 후속 보완(2026-08-24) §2-3 — 검증 오류 메시지에 원본 URL 전체나 그 안의
    가짜 Secret 값을 담지 않는다. `field_validator`가 직접 만든 메시지(Pydantic이
    감싸기 전의 원본 `ValueError`)를 확인한다 — Pydantic이 `ValidationError` 전체를
    문자열로 바꿀 때 프레임워크 차원에서 붙이는 `input_value=...` 축약 echo는 이
    Schema만의 문제가 아니라 모든 필드 검증 실패에 공통으로 붙는 별개 계층이라
    이 테스트의 대상이 아니다 — 이 테스트는 우리가 작성한 메시지 자체가 깨끗한지를
    본다."""

    def _own_message(self, url: str) -> str:
        with self.assertRaises(ValidationError) as cm:
            Department(**_BASE_DEPARTMENT_KWARGS, department_url=url)
        errors = cm.exception.errors()
        self.assertEqual(len(errors), 1)
        return errors[0]["msg"]

    def test_message_does_not_contain_raw_url_for_scheme_rejection(self) -> None:
        url = "javascript:doSomethingSecret('token-abc123')"
        message = self._own_message(url)
        self.assertNotIn(url, message)
        self.assertNotIn("token-abc123", message)

    def test_message_does_not_contain_raw_url_or_secret_for_api_key_rejection(self) -> None:
        secret = "SUPER_SECRET_VALUE_XYZ"
        url = f"https://example.com/path?serviceKey={secret}"
        message = self._own_message(url)
        self.assertNotIn(url, message)
        self.assertNotIn(secret, message)
        self.assertNotIn("example.com", message)

    def test_message_does_not_contain_raw_url_for_non_absolute_rejection(self) -> None:
        url = "cs.example.ac.kr/secret-path?token=abcdef"
        message = self._own_message(url)
        self.assertNotIn(url, message)
        self.assertNotIn("abcdef", message)

    def test_message_matches_recommended_style(self) -> None:
        """지시문이 제시한 좋은 예시와 같은 성격의 문구인지(구체적 스킴/도메인/값을
        나열하지 않고 규칙만 설명하는지) 확인한다."""

        message = self._own_message("ftp://cs.example.ac.kr")
        self.assertIn("http", message.lower())


class RepositoryLoadTest(unittest.TestCase):
    """2026-08-25 전국 학과 1,072건 Production Master 전환 — 옛 데모 35건(전부
    department_url 없음)은 `data/archive/departments_legacy_demo_35.jsonl`로
    보존됐다. 실제 Repository는 이제 1,072건이고, 그중 일부는 대학알리미 URL
    정책 감사(department_url_scope_audit.jsonl)를 통과한 실제 department_url을
    갖는다 — "전부 None"은 더 이상 사실이 아니다."""

    def test_existing_1072_national_departments_load_and_validate_department_url_policy(self) -> None:
        repo = JsonlDepartmentRepository()
        self.assertEqual(len(repo), 1072)
        for dept in repo.all():
            if dept.department_url is not None:
                self.assertTrue(dept.department_url.startswith(("http://", "https://")))

    def test_repository_round_trips_a_department_with_url(self) -> None:
        """Builder가 만드는 JSONL과 같은 방식(Pydantic → JSON → 재파싱)으로 URL이
        있는 학과도 왕복 저장·로드가 되는지 확인한다(§3 "Builder 통과")."""

        dept = Department(**_BASE_DEPARTMENT_KWARGS, department_url="https://cs.example.ac.kr")
        raw = dept.model_dump_json()
        reloaded = Department.model_validate(json.loads(raw))
        self.assertEqual(reloaded.department_url, "https://cs.example.ac.kr")


class _AlwaysApprovePolicy:
    """2026-08-25 §4: fail_closed_major_ids가 10개 Canonical Major 전부로 통일된
    뒤로는(computer_science 포함) 합성 Department 하나만 Repository에 꽂아 넣는
    것만으로는 부족하다 — 학과 단위 Scope 정책도 그 department_id를 명시적으로
    APPROVED라고 승인해야 노출된다. 이 대역은 무조건 승인해 Repository/API 응답
    직렬화 자체(department_url 유무)만 순수하게 검증한다."""

    def is_approved(self, department_id: str, canonical_major_id: str) -> bool:
        return True


class ApiResponseTest(unittest.TestCase):
    """§4 API 테스트 — department_url이 없어도/있어도 응답이 정상이어야 한다.

    2026-08-25 전국 학과 1,072건 전환 이후 실제 computer_science 209건 중 일부는
    이미 department_url이 채워져 있다("전부 None"이 더 이상 사실이 아니다) — 그래서
    직렬화 계약 자체는 합성 Repository로 각각 독립적으로 검증한다."""

    def _get_with_synthetic(self, department: Department):
        synthetic_repo = JsonlDepartmentRepository(departments=[department])
        with (
            patch.object(main_module._major_exploration_service, "_department_repository", synthetic_repo),
            patch.object(
                main_module._major_exploration_service, "_recommendation_scope_policy", _AlwaysApprovePolicy(),
            ),
        ):
            return client.get("/departments/computer_science")

    def test_department_url_absent_serializes_as_null(self) -> None:
        synthetic = Department(
            **{**_BASE_DEPARTMENT_KWARGS, "department_id": "dept_test_url_absent"},
            canonical_major_id="computer_science",
        )
        r = self._get_with_synthetic(synthetic)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(len(body["departments"]), 1)
        self.assertIn("department_url", body["departments"][0])  # 필드 자체는 항상 노출된다.
        self.assertIsNone(body["departments"][0]["department_url"])

    def test_department_url_present_is_passed_through_as_is(self) -> None:
        """Repository가 department_url이 채워진 학과를 반환하면 API 응답에 그대로
        담겨야 한다(§4 "department_url이 있으면 응답에 그대로 포함")."""

        synthetic = Department(
            **{**_BASE_DEPARTMENT_KWARGS, "department_id": "dept_test_url_synthetic"},
            canonical_major_id="computer_science",
            department_url="https://cs.example.ac.kr",
        )
        r = self._get_with_synthetic(synthetic)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(len(body["departments"]), 1)
        self.assertEqual(body["departments"][0]["department_url"], "https://cs.example.ac.kr")

    def test_existing_fields_still_present_no_field_removed(self) -> None:
        r = client.get("/departments/computer_science")
        dept = r.json()["departments"][0]
        for field in (
            "department_id", "university_name", "campus", "region", "department_name",
            "college_name", "admission_unit", "department_status", "source_svy_year",
            "source_url", "canonical_major_id",
        ):
            self.assertIn(field, dept)

    def test_unmapped_major_id_still_returns_empty_list(self) -> None:
        r = client.get("/departments/no_such_major_id_at_all")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"major_id": "no_such_major_id_at_all", "departments": []})


class MockAndOpenApiDeterminismTest(unittest.TestCase):
    """Mock/OpenAPI 재생성이 결정론적인지 확인한다(§4). 실제 재생성은
    `scripts/generate_mock_json.py`로 수행하고(검증 절차 §6), 여기서는 이미 생성된
    산출물이 department_url을 올바르게 반영하는지만 확인한다."""

    def test_openapi_schema_declares_department_url_as_optional_string(self) -> None:
        openapi_path = Path("outputs/mock_api/openapi.json")
        if not openapi_path.exists():
            self.skipTest("outputs/mock_api/openapi.json이 아직 생성되지 않음")
        spec = json.loads(openapi_path.read_text(encoding="utf-8"))
        dept_schema = spec["components"]["schemas"]["Department"]
        self.assertIn("department_url", dept_schema["properties"])
        self.assertNotIn("department_url", dept_schema.get("required", []))

    def test_departments_normal_mock_has_department_url_field(self) -> None:
        mock_path = Path("outputs/mock_api/departments_normal.json")
        if not mock_path.exists():
            self.skipTest("outputs/mock_api/departments_normal.json이 아직 생성되지 않음")
        payload = json.loads(mock_path.read_text(encoding="utf-8"))
        self.assertGreater(len(payload["departments"]), 0)
        for dept in payload["departments"]:
            self.assertIn("department_url", dept)


if __name__ == "__main__":
    unittest.main()
