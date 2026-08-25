"""예체능 계열 학과 추천 제외 정책 — 2026-08-22 9~10차 리뷰.

9차: `design` Canonical Major 전체를 추천에서 막는 major_id 단위 제외
(EXCLUDED_RECOMMENDATION_MAJOR_IDS)를 도입했다.

10차: major_id 단위 제외만으로는 "다른 major_id로 잘못 Mapping된 예체능 학과"를 막지
못한다는 지적을 반영해, 실제 추천 가능한 대표 전공(VERTICAL_SLICE_MAJOR_PROFILES)에는
학과(department_id) 단위 Fail-Closed 정책(DepartmentRecommendationScopePolicy)을
추가했다 — 명시적으로 APPROVED라고 검토·기록된 학과만 노출한다. 검토 근거는
`data/master/department_recommendation_scope.jsonl`에 공식 계열·입학·교육과정 근거를
분리해서 기록한다(자기선언 bool 하나가 아니라 출처 URL이 딸린 근거 배열).
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from urllib.parse import urlparse

from fastapi.testclient import TestClient

from src.api.main import app
from src.data.contexts.context_definitions import CONTEXT_DEFINITIONS
from src.repositories.department_repository import load_departments
from src.schemas.major import Department
from src.schemas.mcp_contracts import DepartmentSearchCriteria
from src.services.department_recommendation_scope import (
    DepartmentRecommendationScopeRecord,
    JsonlDepartmentRecommendationScopePolicy,
    load_department_recommendation_scope,
)
from src.services.major_exploration_service import (
    DEFAULT_SERVICE_MAJOR_IDS,
    EXCLUDED_RECOMMENDATION_MAJOR_IDS,
    MajorExplorationService,
)

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SCOPE_PATH = DATA_DIR / "master" / "department_recommendation_scope.jsonl"
# 2026-08-25 전국 학과 1,072건 Production Master 전환(a/national-master-promotion-
# final-wiring) §3/§4: 기존 데모 35건 Master와 그 8건 Scope 기록은 archive로 옮겨졌다
# (live 파일과 department_id 체계가 dept_ vs off_로 아예 달라 절대 섞이지 않는다). 이
# 옛 데이터를 특정 department_id로 직접 참조하던 회귀 테스트는 이제 그 archive를 읽는다.
ARCHIVE_MASTER_PATH = DATA_DIR / "archive" / "departments_legacy_demo_35.jsonl"
ARCHIVE_SCOPE_PATH = DATA_DIR / "archive" / "department_recommendation_scope_legacy_demo_8.jsonl"

SEOUL_WOMENS_INDUSTRIAL_DESIGN_DEPARTMENT_ID = "dept_05f004629e6e8f4060e286a9"
EWHA_CONVERGENCE_CONTENTS_DEPARTMENT_ID = "dept_73df7dc773a663930a9800f0"

# 2026-08-25 §4: fail_closed_major_ids가 VERTICAL_SLICE_MAJOR_PROFILES(3개)에서 실제
# 서비스 10개 Canonical Major(DEFAULT_SERVICE_MAJOR_IDS)로 통일됐다 — 이 테스트 파일의
# "추천 가능한 Major" 정의도 실제 배선과 같은 정본을 따른다.
RECOMMENDABLE_MAJOR_IDS = DEFAULT_SERVICE_MAJOR_IDS

client = TestClient(app)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _dept(department_id: str, canonical_major_id: str, *, source_url: str = "https://example.test/dept") -> Department:
    return Department(
        department_id=department_id,
        university_name="테스트대학교",
        campus=None,
        region="서울",
        department_name="테스트학과",
        college_name="테스트대학",
        admission_unit=None,
        department_status="EXISTING",
        source_svy_year=2025,
        source_url=source_url,
        canonical_major_id=canonical_major_id,
    )


class _FakeRepository:
    """검색 조건과 무관하게 지정된 학과를 그대로 반환하는 대역 — "잘못 Mapping된 학과가
    Repository에서 나와도 Service가 걸러내는지" 검증용."""

    def __init__(self, departments: list[Department]) -> None:
        self._departments = departments

    def search(self, criteria: DepartmentSearchCriteria, limit: int = 30) -> list[Department]:
        return list(self._departments)[:limit]

    def get(self, department_id: str) -> Department | None:
        return next((d for d in self._departments if d.department_id == department_id), None)


class _FakeApprovalPolicy:
    """지정된 (department_id, canonical_major_id) 조합만 승인하는 테스트용 Policy —
    실제 JSONL 없이도 MajorExplorationService의 Fail-Closed 배선을 검증한다. 2026-08-22
    11차: department_id만으로는 "다른 전공으로 잘못 재매핑돼도 승인이 그대로 따라오는"
    문제를 재현할 수 없어, 승인 대상을 (department_id, canonical_major_id) 쌍으로
    관리한다."""

    def __init__(self, approved_pairs: set[tuple[str, str]]) -> None:
        self._approved_pairs = approved_pairs

    def is_approved(self, department_id: str, canonical_major_id: str) -> bool:
        return (department_id, canonical_major_id) in self._approved_pairs


class OfficialEvidenceQualityTest(unittest.TestCase):
    """섹션 7 "공식 근거 검증" 1~8.

    2026-08-25: 이화여대 융합콘텐츠학과 검토 기록은 기존 데모 35건 시절(dept_ 접두)
    기록이라 archive(`ARCHIVE_SCOPE_PATH`)에서 읽는다 — live `SCOPE_PATH`는 이제
    전국 1,072건(off_ 접두)만 담는다."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = _read_jsonl(ARCHIVE_SCOPE_PATH)
        cls.ewha_row = next(r for r in cls.rows if r["department_id"] == EWHA_CONVERGENCE_CONTENTS_DEPARTMENT_ID)

    def _all_source_urls(self) -> list[str]:
        urls = []
        for row in self.rows:
            for evidence in row.get("classification_evidence", []):
                urls.append(evidence["source_url"])
            for course in row.get("hci_ux_curriculum_evidence", []):
                urls.append(course["source_url"])
        return urls

    def test_no_namu_wiki_reference_anywhere_in_the_scope_file(self) -> None:
        raw_text = SCOPE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("namu.wiki", raw_text)

    def test_all_evidence_urls_are_https(self) -> None:
        urls = self._all_source_urls()
        self.assertGreater(len(urls), 0)
        for url in urls:
            self.assertEqual(urlparse(url).scheme, "https", url)

    def test_hci_ux_approval_evidence_is_on_an_official_ewha_or_public_domain(self) -> None:
        allowed_domain_suffixes = (".ewha.ac.kr",)
        for evidence in self.ewha_row["classification_evidence"]:
            host = urlparse(evidence["source_url"]).netloc
            self.assertTrue(
                any(host == d.lstrip(".") or host.endswith(d) for d in allowed_domain_suffixes),
                f"{host}는 이화여대 공식 도메인이 아닙니다.",
            )

    def test_no_mock_sample_blog_or_community_urls(self) -> None:
        forbidden_fragments = ("sample://", "example.", "namu.wiki", "blog.", "cafe.")
        for url in self._all_source_urls():
            for fragment in forbidden_fragments:
                self.assertNotIn(fragment, url, f"{url}에 금지 조각 {fragment!r} 포함")

    def test_official_college_classification_evidence_exists_for_ewha(self) -> None:
        types = {e["evidence_type"] for e in self.ewha_row["classification_evidence"]}
        self.assertIn("OFFICIAL_COLLEGE_CLASSIFICATION", types)

    def test_official_admission_guide_evidence_exists_or_review_required(self) -> None:
        types = {e["evidence_type"] for e in self.ewha_row["classification_evidence"]}
        if "OFFICIAL_ADMISSION_GUIDE" not in types:
            self.assertEqual(self.ewha_row["eligibility_status"], "REVIEW_REQUIRED")
        else:
            self.assertEqual(self.ewha_row["eligibility_status"], "APPROVED")

    def test_official_curriculum_evidence_exists_for_ewha(self) -> None:
        types = {e["evidence_type"] for e in self.ewha_row["classification_evidence"]}
        self.assertIn("OFFICIAL_CURRICULUM", types)

    def test_every_hci_ux_course_has_its_own_source_url(self) -> None:
        courses = self.ewha_row["hci_ux_curriculum_evidence"]
        self.assertGreater(len(courses), 0)
        for course in courses:
            self.assertTrue(course["source_url"].strip())
            self.assertTrue(course["course_name"].strip())


class DepartmentLevelPolicyTest(unittest.TestCase):
    """섹션 7 "학과 단위 정책" 9~19."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.departments = load_departments(DATA_DIR / "master" / "departments.jsonl")
        cls.scope_records = load_department_recommendation_scope(SCOPE_PATH)

    def test_every_recommendable_major_department_has_a_scope_record(self) -> None:
        for department in self.departments:
            if department.canonical_major_id in RECOMMENDABLE_MAJOR_IDS:
                self.assertIn(
                    department.department_id, self.scope_records,
                    f"{department.university_name} {department.department_name}에 적격성 검토 기록이 없습니다.",
                )

    def test_only_approved_departments_are_returned_by_service(self) -> None:
        from src.repositories.department_repository import JsonlDepartmentRepository

        real_repository = JsonlDepartmentRepository(path=DATA_DIR / "master" / "departments.jsonl")
        policy = JsonlDepartmentRecommendationScopePolicy(path=SCOPE_PATH)
        service = MajorExplorationService(
            real_repository, recommendation_scope_policy=policy, fail_closed_major_ids=RECOMMENDABLE_MAJOR_IDS,
        )
        for major_id in RECOMMENDABLE_MAJOR_IDS:
            for d in service.list_departments_for_major(major_id):
                record = self.scope_records[d.department_id]
                self.assertEqual(record.eligibility_status, "APPROVED")

    def test_excluded_arts_sports_department_is_not_returned(self) -> None:
        repo = _FakeRepository([_dept("d1", "hci_ux"), _dept("d2", "hci_ux")])
        policy = _FakeApprovalPolicy(approved_pairs=set())  # d1 EXCLUDED_ARTS_SPORTS 흉내
        service = MajorExplorationService(repo, recommendation_scope_policy=policy, fail_closed_major_ids={"hci_ux"})
        self.assertEqual(service.list_departments_for_major("hci_ux"), [])

    def test_review_required_department_is_not_returned(self) -> None:
        repo = _FakeRepository([_dept("d1", "hci_ux")])
        policy = _FakeApprovalPolicy(approved_pairs=set())  # REVIEW_REQUIRED도 미승인 취급
        service = MajorExplorationService(repo, recommendation_scope_policy=policy, fail_closed_major_ids={"hci_ux"})
        self.assertEqual(service.list_departments_for_major("hci_ux"), [])

    def test_department_without_any_scope_record_is_excluded_fail_closed(self) -> None:
        repo = _FakeRepository([_dept("brand_new_dept", "hci_ux")])
        policy = _FakeApprovalPolicy(approved_pairs=set())  # 기록 자체가 없는 상황
        service = MajorExplorationService(repo, recommendation_scope_policy=policy, fail_closed_major_ids={"hci_ux"})
        self.assertEqual(service.list_departments_for_major("hci_ux"), [])

    def test_fake_policy_can_be_injected(self) -> None:
        repo = _FakeRepository([_dept("d1", "hci_ux")])
        policy = _FakeApprovalPolicy(approved_pairs={("d1", "hci_ux")})
        service = MajorExplorationService(repo, recommendation_scope_policy=policy, fail_closed_major_ids={"hci_ux"})
        result = service.list_departments_for_major("hci_ux")
        self.assertEqual([d.department_id for d in result], ["d1"])

    def test_industrial_design_wrongly_mapped_to_hci_ux_by_repository_is_still_excluded(self) -> None:
        """Repository가 (버그로) 산업디자인학과를 hci_ux로 잘못 반환해도, 학과 단위
        Fail-Closed 정책이 마지막 방어선 역할을 한다 — 이 학과는 department_recommendation_
        scope.jsonl에 APPROVED 기록이 없으므로(hci_ux용으로 검토된 적이 없다) 제외된다."""

        wrongly_mapped = _dept(SEOUL_WOMENS_INDUSTRIAL_DESIGN_DEPARTMENT_ID, "hci_ux")
        repo = _FakeRepository([wrongly_mapped])
        policy = JsonlDepartmentRecommendationScopePolicy(path=SCOPE_PATH)
        service = MajorExplorationService(repo, recommendation_scope_policy=policy, fail_closed_major_ids={"hci_ux"})
        self.assertEqual(service.list_departments_for_major("hci_ux"), [])

    def test_design_major_id_block_still_holds(self) -> None:
        r = client.get("/departments/design")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["departments"], [])

    def test_industrial_engineering_departments_are_exposed(self) -> None:
        """2026-08-25 전국 학과 1,072건 전환 — industrial_engineering 기준값이 옛
        데모 3건에서 실제 전국 53건으로 바뀌었다.

        2026-08-25 지시서(c/national-departments-38-majors) 후속 정정 — 53→100.
        Bridge V2는 소계열 Scope 제한이 없어(모듈 tests/test_canonical_major_group_
        bridge_scope.py의 같은 갱신과 동일한 이유) 이 Group의 공식 소계열
        102/103/104가 전부 포함된다."""
        r = client.get("/departments/industrial_engineering")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["departments"]), 100)

    def test_media_communication_departments_are_exposed(self) -> None:
        r = client.get("/departments/media_communication")
        self.assertEqual(r.status_code, 200)
        self.assertGreater(len(r.json()["departments"]), 0)

    def test_departments_response_contract_is_unchanged(self) -> None:
        # 2026-08-25: hci_ux는 전국 승격 후보가 0건이라(§4, 임의 생성 금지) 이제
        # 정당하게 빈 목록이다 — Schema 필드 구성 확인에는 실제로 결과가 있는
        # media_communication을 쓴다.
        r = client.get("/departments/media_communication")
        body = r.json()
        self.assertEqual(set(body.keys()), {"major_id", "departments"})
        dept = body["departments"][0]
        self.assertEqual(
            set(dept.keys()),
            {
                "department_id", "university_name", "campus", "region", "department_name",
                "college_name", "admission_unit", "department_status", "source_svy_year",
                "source_url", "canonical_major_id",
                # A2 지시서(2026-08-24) §1: 학과 공식 홈페이지 URL(선택 필드) 추가.
                "department_url",
            },
        )
        # 내부 적격성 필드는 응답에 노출되지 않는다.
        for internal_field in ("academic_field", "recommendation_eligible", "eligibility_status", "reviewer_id"):
            self.assertNotIn(internal_field, dept)


class MappingRegressionTest(unittest.TestCase):
    """직전(9차) 리뷰의 Mapping 회귀 테스트를 유지한다.

    2026-08-25: 이 클래스가 참조하는 특정 department_id(서울여대 산업디자인학과 등)는
    기존 데모 35건 시절 것들이라, live Master가 아니라 그 archive
    (`ARCHIVE_MASTER_PATH`)에서 계속 검증한다 — 이 회귀 사실 자체는 바뀌지 않았고,
    그 데이터가 있던 위치만 archive로 옮겨졌다."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.departments = load_departments(ARCHIVE_MASTER_PATH)
        cls.by_id = {d.department_id: d for d in cls.departments}

    def test_seoul_womens_industrial_design_is_not_hci_ux(self) -> None:
        department = self.by_id[SEOUL_WOMENS_INDUSTRIAL_DESIGN_DEPARTMENT_ID]
        self.assertNotEqual(department.canonical_major_id, "hci_ux")

    def test_no_active_manual_confirmation_maps_it_to_hci_ux(self) -> None:
        manual = _read_jsonl(DATA_DIR / "master" / "canonical_mapping_manual_confirmations.jsonl")
        for entry in manual:
            if entry["department_id"] == SEOUL_WOMENS_INDUSTRIAL_DESIGN_DEPARTMENT_ID:
                self.assertNotEqual(entry["chosen_major_id"], "hci_ux")

    def test_industrial_engineering_three_departments_are_preserved(self) -> None:
        ie_departments = {d.department_id: d for d in self.departments if d.canonical_major_id == "industrial_engineering"}
        self.assertEqual(len(ie_departments), 3)


class CrossMajorApprovalRegressionTest(unittest.TestCase):
    """섹션 2 "Fake Policy와 테스트 수정" 회귀 테스트 1~7 — is_approved()가 department_id
    뿐 아니라 canonical_major_id까지 함께 확인하는지."""

    MEDIA_DEPT_ID = "dept_media_01"
    HCI_DEPT_ID = "dept_hci_01"

    def _service(self, approved_pairs: set[tuple[str, str]], departments: list[Department]) -> MajorExplorationService:
        repo = _FakeRepository(departments)
        policy = _FakeApprovalPolicy(approved_pairs=approved_pairs)
        return MajorExplorationService(
            repo, recommendation_scope_policy=policy,
            fail_closed_major_ids={"media_communication", "hci_ux", "industrial_engineering"},
        )

    def test_same_department_id_requested_with_its_originally_approved_major_passes(self) -> None:
        service = self._service(
            {(self.MEDIA_DEPT_ID, "media_communication")},
            [_dept(self.MEDIA_DEPT_ID, "media_communication")],
        )
        result = service.list_departments_for_major("media_communication")
        self.assertEqual([d.department_id for d in result], [self.MEDIA_DEPT_ID])

    def test_same_department_id_requested_with_a_different_major_is_rejected(self) -> None:
        # 정책은 media_communication으로만 승인했는데, Repository가 hci_ux로 내보내는 상황.
        service = self._service(
            {(self.MEDIA_DEPT_ID, "media_communication")},
            [_dept(self.MEDIA_DEPT_ID, "hci_ux")],
        )
        self.assertEqual(service.list_departments_for_major("hci_ux"), [])

    def test_media_department_wrongly_remapped_to_hci_ux_is_rejected(self) -> None:
        service = self._service(
            {(self.MEDIA_DEPT_ID, "media_communication")},
            [_dept(self.MEDIA_DEPT_ID, "hci_ux")],
        )
        self.assertEqual(service.list_departments_for_major("hci_ux"), [])

    def test_hci_ux_approved_department_wrongly_remapped_to_media_communication_is_rejected(self) -> None:
        service = self._service(
            {(self.HCI_DEPT_ID, "hci_ux")},
            [_dept(self.HCI_DEPT_ID, "media_communication")],
        )
        self.assertEqual(service.list_departments_for_major("media_communication"), [])

    def test_record_major_mismatch_with_department_major_is_rejected(self) -> None:
        """정책 레코드는 industrial_engineering으로 승인했는데 Department 자체의
        canonical_major_id가 다르면(둘 중 하나가 잘못됐다는 뜻) 거부돼야 한다."""

        service = self._service(
            {("dept_x", "industrial_engineering")},
            [_dept("dept_x", "media_communication")],
        )
        self.assertEqual(service.list_departments_for_major("media_communication"), [])
        self.assertEqual(service.list_departments_for_major("industrial_engineering"), [])

    def test_no_policy_object_means_fail_closed_as_before(self) -> None:
        repo = _FakeRepository([_dept("d1", "hci_ux")])
        service = MajorExplorationService(repo, recommendation_scope_policy=None, fail_closed_major_ids={"hci_ux"})
        self.assertEqual(service.list_departments_for_major("hci_ux"), [])

    def test_recommendable_majors_api_result_counts_unchanged(self) -> None:
        """2026-08-25 전국 학과 1,072건 전환 — 옛 데모 기준값(4/3/1/0)을 실제 전국
        기준값으로 갱신한다. hci_ux는 승격 후보가 0건이라(§4) 정당하게 0이다.

        2026-08-25 지시서(c/national-departments-38-majors) 후속 정정 —
        industrial_engineering만 53→100(Bridge V2는 소계열 Scope 제한이 없다)."""
        expected = {"media_communication": 133, "industrial_engineering": 100, "hci_ux": 0, "design": 0}
        for major_id, count in expected.items():
            r = client.get(f"/departments/{major_id}")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(len(r.json()["departments"]), count, major_id)


class StatusBooleanConsistencyTest(unittest.TestCase):
    """섹션 3 "상태와 Boolean 정합성 검증" — 6개 조합."""

    def _record_kwargs(self, **overrides) -> dict:
        base = dict(
            department_id="d1", university_name="테스트대학교", department_name="테스트학과",
            college_name="테스트대학", canonical_major_id="hci_ux", academic_field="INTERDISCIPLINARY",
            eligibility_status="APPROVED", recommendation_eligible=True,
            classification_evidence=[
                {"evidence_type": "OFFICIAL_COLLEGE_CLASSIFICATION", "source_url": "https://example.ac.kr/x", "summary": "s"}
            ],
            hci_ux_curriculum_evidence=[{"course_name": "UX디자인", "source_url": "https://example.ac.kr/curriculum"}],
            reviewer_id="worker_a", reviewed_at="2026-08-22", decision_reason="reason",
        )
        base.update(overrides)
        return base

    def test_approved_with_true_passes(self) -> None:
        DepartmentRecommendationScopeRecord.model_validate(
            self._record_kwargs(eligibility_status="APPROVED", recommendation_eligible=True)
        )

    def test_approved_with_false_is_rejected(self) -> None:
        with self.assertRaises(Exception):
            DepartmentRecommendationScopeRecord.model_validate(
                self._record_kwargs(eligibility_status="APPROVED", recommendation_eligible=False)
            )

    def test_excluded_arts_sports_with_false_passes(self) -> None:
        DepartmentRecommendationScopeRecord.model_validate(
            self._record_kwargs(eligibility_status="EXCLUDED_ARTS_SPORTS", recommendation_eligible=False)
        )

    def test_excluded_arts_sports_with_true_is_rejected(self) -> None:
        with self.assertRaises(Exception):
            DepartmentRecommendationScopeRecord.model_validate(
                self._record_kwargs(eligibility_status="EXCLUDED_ARTS_SPORTS", recommendation_eligible=True)
            )

    def test_review_required_with_false_passes(self) -> None:
        DepartmentRecommendationScopeRecord.model_validate(
            self._record_kwargs(eligibility_status="REVIEW_REQUIRED", recommendation_eligible=False)
        )

    def test_review_required_with_true_is_rejected(self) -> None:
        with self.assertRaises(Exception):
            DepartmentRecommendationScopeRecord.model_validate(
                self._record_kwargs(eligibility_status="REVIEW_REQUIRED", recommendation_eligible=True)
            )

    def test_policy_defends_even_if_a_record_bypasses_schema_validation(self) -> None:
        """Schema 검증을 우회해서(model_construct) 상태·Boolean이 모순인 레코드를 만들어도,
        Policy.is_approved()는 eligibility_status가 APPROVED가 아니면 거부해야 한다 —
        Schema 검증만 믿지 않는다."""

        inconsistent = DepartmentRecommendationScopeRecord.model_construct(
            department_id="d1", university_name="테스트대학교", department_name="테스트학과",
            college_name="테스트대학", canonical_major_id="hci_ux", academic_field="INTERDISCIPLINARY",
            eligibility_status="REVIEW_REQUIRED", recommendation_eligible=True,  # 모순 상태
            classification_evidence=[], hci_ux_curriculum_evidence=[],
            reviewer_id="worker_a", reviewed_at="2026-08-22", decision_reason="reason",
        )
        policy = JsonlDepartmentRecommendationScopePolicy(records={"d1": inconsistent})
        self.assertFalse(policy.is_approved("d1", "hci_ux"))


class ApprovedEvidenceMinimumTest(unittest.TestCase):
    """섹션 4 "APPROVED 근거 최소조건" — Schema 수준 강제."""

    def _base_kwargs(self, **overrides) -> dict:
        base = dict(
            department_id="d1", university_name="테스트대학교", department_name="테스트학과",
            college_name="테스트대학", canonical_major_id="industrial_engineering",
            academic_field="ENGINEERING", eligibility_status="APPROVED", recommendation_eligible=True,
            classification_evidence=[
                {"evidence_type": "OFFICIAL_COLLEGE_CLASSIFICATION", "source_url": "https://example.ac.kr/x", "summary": "s"}
            ],
            hci_ux_curriculum_evidence=[], reviewer_id="worker_a", reviewed_at="2026-08-22", decision_reason="reason",
        )
        base.update(overrides)
        return base

    def test_approved_without_any_classification_evidence_is_rejected(self) -> None:
        with self.assertRaises(Exception):
            DepartmentRecommendationScopeRecord.model_validate(self._base_kwargs(classification_evidence=[]))

    def test_approved_with_empty_source_url_is_rejected(self) -> None:
        with self.assertRaises(Exception):
            DepartmentRecommendationScopeRecord.model_validate(
                self._base_kwargs(
                    classification_evidence=[{"evidence_type": "OFFICIAL_COLLEGE_CLASSIFICATION", "source_url": "", "summary": "s"}]
                )
            )

    def test_approved_with_empty_reviewer_id_is_rejected(self) -> None:
        with self.assertRaises(Exception):
            DepartmentRecommendationScopeRecord.model_validate(self._base_kwargs(reviewer_id=""))

    def test_approved_with_empty_decision_reason_is_rejected(self) -> None:
        with self.assertRaises(Exception):
            DepartmentRecommendationScopeRecord.model_validate(self._base_kwargs(decision_reason=""))

    def test_hci_ux_approved_without_curriculum_evidence_is_rejected(self) -> None:
        with self.assertRaises(Exception):
            DepartmentRecommendationScopeRecord.model_validate(
                self._base_kwargs(canonical_major_id="hci_ux", hci_ux_curriculum_evidence=[])
            )

    def test_hci_ux_approved_course_missing_source_url_is_rejected(self) -> None:
        with self.assertRaises(Exception):
            DepartmentRecommendationScopeRecord.model_validate(
                self._base_kwargs(
                    canonical_major_id="hci_ux",
                    hci_ux_curriculum_evidence=[{"course_name": "UX디자인", "source_url": ""}],
                )
            )

    def test_non_hci_ux_approved_does_not_require_hci_ux_curriculum_evidence(self) -> None:
        DepartmentRecommendationScopeRecord.model_validate(
            self._base_kwargs(canonical_major_id="industrial_engineering", hci_ux_curriculum_evidence=[])
        )


class DuplicateDepartmentIdTest(unittest.TestCase):
    """섹션 5 "중복 department_id 차단" 1~5."""

    def _write_jsonl(self, tmp_path: Path, rows: list[dict]) -> Path:
        path = tmp_path / "scope.jsonl"
        path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
        return path

    def _row(self, department_id: str, **overrides) -> dict:
        base = {
            "department_id": department_id, "university_name": "테스트대학교", "department_name": "테스트학과",
            "college_name": "테스트대학", "canonical_major_id": "industrial_engineering",
            "academic_field": "ENGINEERING", "eligibility_status": "APPROVED", "recommendation_eligible": True,
            "classification_evidence": [
                {"evidence_type": "OFFICIAL_COLLEGE_CLASSIFICATION", "source_url": "https://example.ac.kr/x", "summary": "s"}
            ],
            "hci_ux_curriculum_evidence": [], "reviewer_id": "worker_a", "reviewed_at": "2026-08-22", "decision_reason": "r",
        }
        base.update(overrides)
        return base

    def test_file_without_duplicates_loads_normally(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_jsonl(Path(tmp), [self._row("d1"), self._row("d2")])
            records = load_department_recommendation_scope(path)
            self.assertEqual(set(records), {"d1", "d2"})

    def test_two_rows_with_same_department_id_raise(self) -> None:
        import tempfile

        from src.services.department_recommendation_scope import DuplicateDepartmentScopeRecordError

        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_jsonl(Path(tmp), [self._row("d1"), self._row("d1")])
            with self.assertRaises(DuplicateDepartmentScopeRecordError):
                load_department_recommendation_scope(path)

    def test_different_ids_load_normally(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_jsonl(Path(tmp), [self._row("d1"), self._row("d2"), self._row("d3")])
            records = load_department_recommendation_scope(path)
            self.assertEqual(len(records), 3)

    def test_duplicate_rows_with_same_status_still_raise(self) -> None:
        import tempfile

        from src.services.department_recommendation_scope import DuplicateDepartmentScopeRecordError

        with tempfile.TemporaryDirectory() as tmp:
            rows = [self._row("d1", eligibility_status="APPROVED", recommendation_eligible=True) for _ in range(2)]
            path = self._write_jsonl(Path(tmp), rows)
            with self.assertRaises(DuplicateDepartmentScopeRecordError):
                load_department_recommendation_scope(path)

    def test_duplicate_rows_with_different_status_still_raise(self) -> None:
        import tempfile

        from src.services.department_recommendation_scope import DuplicateDepartmentScopeRecordError

        with tempfile.TemporaryDirectory() as tmp:
            rows = [
                self._row("d1", eligibility_status="APPROVED", recommendation_eligible=True),
                self._row("d1", eligibility_status="REVIEW_REQUIRED", recommendation_eligible=False),
            ]
            path = self._write_jsonl(Path(tmp), rows)
            with self.assertRaises(DuplicateDepartmentScopeRecordError):
                load_department_recommendation_scope(path)

    def test_app_startup_fails_loudly_on_duplicate_instead_of_silently_using_empty_policy(self) -> None:
        import tempfile

        from src.services.department_recommendation_scope import DuplicateDepartmentScopeRecordError

        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_jsonl(Path(tmp), [self._row("d1"), self._row("d1")])
            with self.assertRaises(DuplicateDepartmentScopeRecordError):
                JsonlDepartmentRecommendationScopePolicy(path=path)


class Ewha2026AdmissionEvidenceTest(unittest.TestCase):
    """섹션 6 "이화여대 입학 근거 최신화" 4개.

    2026-08-25: 대상 기록이 기존 데모 35건 시절 것이라 archive에서 읽는다(위
    OfficialEvidenceQualityTest와 같은 이유)."""

    @classmethod
    def setUpClass(cls) -> None:
        rows = _read_jsonl(ARCHIVE_SCOPE_PATH)
        cls.ewha_row = next(r for r in rows if r["department_id"] == EWHA_CONVERGENCE_CONTENTS_DEPARTMENT_ID)
        cls.admission_evidence = next(
            e for e in cls.ewha_row["classification_evidence"] if e["evidence_type"] == "OFFICIAL_ADMISSION_GUIDE"
        )

    def test_admission_guide_is_the_2026_official_pdf(self) -> None:
        self.assertIn("20250901114849R2K7DN", self.admission_evidence["source_url"])

    def test_old_2024_pdf_url_is_no_longer_present(self) -> None:
        raw_text = ARCHIVE_SCOPE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("20230911092013KBG72F", raw_text)

    def test_admission_guide_uses_official_admission_office_domain(self) -> None:
        self.assertEqual(urlparse(self.admission_evidence["source_url"]).netloc, "admission.ewha.ac.kr")

    def test_admission_guide_summary_mentions_2026_academic_year(self) -> None:
        self.assertIn("2026학년도", self.admission_evidence["summary"])


class ScopeDataFullConsistencyTest(unittest.TestCase):
    """섹션 7 "정책 데이터 전체 정합성 검사" 8개."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.departments_by_id = {
            d.department_id: d for d in load_departments(DATA_DIR / "master" / "departments.jsonl")
        }
        cls.scope_records = load_department_recommendation_scope(SCOPE_PATH)  # 중복 있으면 여기서 즉시 예외

    def test_no_duplicate_department_id_in_scope_file(self) -> None:
        rows = _read_jsonl(SCOPE_PATH)
        ids = [r["department_id"] for r in rows]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_scope_record_department_exists_in_master(self) -> None:
        for department_id in self.scope_records:
            self.assertIn(department_id, self.departments_by_id, f"{department_id}가 departments.jsonl에 없습니다(고아 레코드).")

    def test_scope_record_canonical_major_id_matches_department_master(self) -> None:
        for department_id, record in self.scope_records.items():
            department = self.departments_by_id[department_id]
            self.assertEqual(record.canonical_major_id, department.canonical_major_id)

    def test_approved_status_matches_recommendation_eligible_for_all_records(self) -> None:
        for record in self.scope_records.values():
            self.assertEqual(record.recommendation_eligible, record.eligibility_status == "APPROVED")

    def test_every_record_has_at_least_one_official_evidence(self) -> None:
        for department_id, record in self.scope_records.items():
            self.assertGreater(len(record.classification_evidence), 0, department_id)

    def test_all_source_urls_across_all_records_are_https(self) -> None:
        for record in self.scope_records.values():
            for evidence in record.classification_evidence:
                self.assertEqual(urlparse(evidence.source_url).scheme, "https")
            for course in record.hci_ux_curriculum_evidence:
                self.assertEqual(urlparse(course.source_url).scheme, "https")

    def test_every_recommendable_major_department_has_a_policy_record_full_check(self) -> None:
        for department in self.departments_by_id.values():
            if department.canonical_major_id in RECOMMENDABLE_MAJOR_IDS:
                self.assertIn(department.department_id, self.scope_records)

    def test_no_orphan_scope_records_pointing_to_non_recommendable_or_missing_majors(self) -> None:
        """2026-08-25 지시서(c/national-departments-38-majors) 정정 — 이 라운드는
        Scope 데이터를 38개 Service Canonical Major v2(ACTIVE) 기준으로 재생성했다
        (§4). `RECOMMENDABLE_MAJOR_IDS`(=`DEFAULT_SERVICE_MAJOR_IDS`, 옛 10개)는
        main.py를 건드리지 않는다는 이 라운드의 명시적 제약 때문에 아직 그대로다 —
        그래서 "Scope canonical_major_id가 RECOMMENDABLE_MAJOR_IDS 안"이라는 옛
        검사는 더 이상 이 데이터의 실제 계약이 아니다. 대신 "Service Canonical
        Major v2(ACTIVE, 39개 — 38 FULL_GROUP + hci_ux DEPARTMENT_LEVEL_ONLY) 중
        하나"인지로 검증한다 — 데이터 계층(Master·Scope)이 이미 지원하는 진짜
        상한이 이것이다. Major 노출 정책을 실제로 38개로 넓히는 것은 별도 배선
        라운드의 몫이다."""

        from src.services.service_canonical_major_v2_loader import load_service_canonical_majors_v2

        active_major_ids = frozenset(
            m.major_id for m in load_service_canonical_majors_v2() if m.recommendation_status == "ACTIVE"
        )
        for department_id, record in self.scope_records.items():
            self.assertIn(record.canonical_major_id, active_major_ids)


class ContextIndependenceTest(unittest.TestCase):
    """섹션 7 "Context 독립성 테스트" 20~21."""

    def test_arts_and_pe_related_contexts_are_not_deleted(self) -> None:
        labels = {c.label for c in CONTEXT_DEFINITIONS}
        for expected_label in ("미술·디자인", "스포츠", "미디어", "패션·뷰티"):
            self.assertIn(expected_label, labels)

    def test_selecting_an_arts_context_does_not_change_department_eligibility_policy(self) -> None:
        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        r = client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"art_design": 5, "media": 4}},
        )
        self.assertEqual(r.status_code, 200)

        r = client.get(f"/majors/{session_id}")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        all_major_ids = {m["major_id"] for m in body["relevant_majors"] + body["explore_together_majors"]}
        self.assertEqual(all_major_ids & EXCLUDED_RECOMMENDATION_MAJOR_IDS, set())

        # 예체능 Context를 선택한 뒤에도 hci_ux 조회 결과는 정책 파일 기준 그대로다.
        r = client.get("/departments/hci_ux")
        names = [(d["university_name"], d["department_name"]) for d in r.json()["departments"]]
        self.assertNotIn(("서울여자대학교", "산업디자인학과"), names)


if __name__ == "__main__":
    unittest.main()
