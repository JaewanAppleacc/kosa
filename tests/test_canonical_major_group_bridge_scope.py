"""Canonical Major Group Bridge Scope 테스트 — 2026-08-24 지시서
(a/canonical-major-bridge-scope).

전공군(Group) 전체를 통째로 서비스 추천 학과 후보로 연결하지 않고, 공식 소계열
단위(`INCLUDED_SMALL_SERIES_ONLY`) 또는 개별 학과 검토 단위(`DEPARTMENT_REVIEW_
REQUIRED`)로 범위를 제한할 수 있는 Scope 필드(`src/schemas/canonical_major_group_
bridge.py` 확장)와, REVISE 6건에 실제로 적용한 Scope 값(`scripts/career_add_
canonical_major_group_bridge_scope.py`)을 검증한다.

`tests/test_canonical_major_group_bridge.py`(Schema/Loader 계층 일반 규칙)와
역할을 분리한다 — 이 파일은 (1) REVISE 6건의 최종 Scope 값이 지시서 §3과 정확히
일치하는지, (2) 나머지 38개 APPROVE 행·44행 전체·기존 정본(Major 10개, 예체능 5개,
mapping_status 분포)이 그대로 보존됐는지, (3) 소계열 코드 교차 검증(공식 코드표·
그 Group 소계열 목록)이 실제로 동작하는지, (4) Schema 우회 방어(Service 계층
`validate_bridge_scope_row`)가 실제로 작동하는지, (5) 빌드 결정성·기존 Mock/API/
Master/Review JSON 무변경을 다룬다."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from src.schemas.canonical_major_group_bridge import CanonicalMajorGroupBridgeEntry
from src.services.canonical_major_group_bridge_loader import (
    BridgeScopeValidationError,
    DEFAULT_BRIDGE_DRAFT_PATH,
    load_canonical_major_group_bridge,
    load_official_small_series_codes,
    validate_bridge_scope_row,
)
from src.services.canonical_major_group_draft_loader import load_canonical_major_groups_draft
from scripts.career_add_canonical_major_group_bridge_scope import (
    REVISE_SCOPE_OVERRIDES,
    build_scoped_rows,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RealBridgeScopeLoadTest(unittest.TestCase):
    """실제 커밋된 Bridge draft 파일(44행) 전체가 Scope 필드까지 포함해 로드되는지."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.report = load_canonical_major_group_bridge()
        cls.by_key = {(e.canonical_major_group_id, e.canonical_major_id): e for e in cls.report.entries}

    def test_still_exactly_44_rows(self) -> None:
        self.assertEqual(len(self.report.entries), 44)

    def test_mapping_status_distribution_unchanged(self) -> None:
        from collections import Counter

        counts = Counter(e.mapping_status for e in self.report.entries)
        self.assertEqual(
            counts,
            Counter({"UNMAPPED": 29, "EVIDENCED": 8, "EXCLUDED_RECOMMENDATION": 5, "REVIEW_REQUIRED": 2}),
        )

    def test_existing_10_major_ids_unchanged(self) -> None:
        expected = {
            "computer_science", "media_communication", "design", "business_administration",
            "psychology", "mechanical_engineering", "education", "life_science",
            "industrial_engineering", "hci_ux",
        }
        self.assertEqual(self.report.major_ids_covered() | {"design"}, expected | {"design"})
        for major_id in expected:
            self.assertGreater(len(self.report.entries_for_major(major_id)), 0, major_id)

    def test_5_excluded_recommendation_rows_preserved(self) -> None:
        excluded = self.report.entries_by_status("EXCLUDED_RECOMMENDATION")
        self.assertEqual(len(excluded), 5)
        for e in excluded:
            self.assertEqual(e.scope_type, "EXCLUDED_RECOMMENDATION")

    def test_no_scope_review_status_is_pre_approved(self) -> None:
        # 안전 규칙 "사람의 APPROVE/REVISE 상태를 자동 변경하지 마세요" — 이 새 Scope
        # 값 자체를 사람이 검토한 적이 없으므로 44행 전부 scope_review_status="draft"다.
        for e in self.report.entries:
            self.assertEqual(e.scope_review_status, "draft", f"{e.canonical_major_group_id}->{e.canonical_major_id}")

    def test_reviewer_fields_and_review_status_untouched(self) -> None:
        # 기존 review_status/reviewer_id/reviewed_at(Bridge Mapping 자체의 검토 상태)도
        # 이 작업으로 손대지 않았어야 한다.
        for e in self.report.entries:
            self.assertEqual(e.review_status, "draft")
            self.assertIsNone(e.reviewer_id)
            self.assertIsNone(e.reviewed_at)


class Revise6ScopeContentTest(RealBridgeScopeLoadTest):
    """지시서 §3의 REVISE 6건 각각이 요구한 정확한 Scope 값과 일치하는지."""

    def test_bio_medical_engineering_to_life_science_is_department_review_required(self) -> None:
        e = self.by_key[("bio_medical_engineering", "life_science")]
        self.assertEqual(e.scope_type, "DEPARTMENT_REVIEW_REQUIRED")
        self.assertEqual(e.included_small_series_codes, [])
        self.assertEqual(e.excluded_small_series_codes, [])
        self.assertTrue(e.scope_decision_reason.strip())

    def test_business_scoped_to_business_administration_small_series_only(self) -> None:
        e = self.by_key[("business", "business_administration")]
        self.assertEqual(e.scope_type, "INCLUDED_SMALL_SERIES_ONLY")
        self.assertEqual(e.included_small_series_codes, ["033"])  # 경영학
        self.assertEqual(set(e.excluded_small_series_codes), {"035", "041", "151", "152"})

    def test_computer_science_to_hci_ux_is_department_review_required(self) -> None:
        e = self.by_key[("computer_science", "hci_ux")]
        self.assertEqual(e.scope_type, "DEPARTMENT_REVIEW_REQUIRED")
        self.assertEqual(e.included_small_series_codes, [])
        self.assertEqual(e.excluded_small_series_codes, [])

    def test_computer_science_to_computer_science_link_unaffected(self) -> None:
        # hci_ux Scope 좁힘이 같은 Group의 computer_science 연결에는 영향을 주지 않는다.
        e = self.by_key[("computer_science", "computer_science")]
        self.assertEqual(e.mapping_status, "EVIDENCED")
        self.assertEqual(e.scope_type, "FULL_GROUP")

    def test_education_scoped_to_education_small_series_only(self) -> None:
        e = self.by_key[("education", "education")]
        self.assertEqual(e.scope_type, "INCLUDED_SMALL_SERIES_ONLY")
        self.assertEqual(e.included_small_series_codes, ["042"])  # 교육학
        self.assertEqual(set(e.excluded_small_series_codes), {"043", "046", "154", "155"})

    def test_industrial_engineering_scoped_to_industrial_engineering_small_series_only(self) -> None:
        e = self.by_key[("industrial_engineering", "industrial_engineering")]
        self.assertEqual(e.scope_type, "INCLUDED_SMALL_SERIES_ONLY")
        self.assertEqual(e.included_small_series_codes, ["102"])  # 산업공학
        self.assertEqual(set(e.excluded_small_series_codes), {"103", "104"})

    def test_mechanical_transport_scoped_to_mechanical_engineering_small_series_only(self) -> None:
        e = self.by_key[("mechanical_transport", "mechanical_engineering")]
        self.assertEqual(e.scope_type, "INCLUDED_SMALL_SERIES_ONLY")
        self.assertEqual(e.included_small_series_codes, ["078"])  # 기계공학
        self.assertEqual(set(e.excluded_small_series_codes), {"080", "081", "082", "083"})

    def test_all_6_revise_keys_present_in_override_table(self) -> None:
        expected_keys = {
            ("bio_medical_engineering", "life_science"), ("business", "business_administration"),
            ("computer_science", "hci_ux"), ("education", "education"),
            ("industrial_engineering", "industrial_engineering"),
            ("mechanical_transport", "mechanical_engineering"),
        }
        self.assertEqual(set(REVISE_SCOPE_OVERRIDES.keys()), expected_keys)

    def test_included_and_excluded_codes_are_official_small_series_names_named_in_instruction(self) -> None:
        # §3에 명시된 명칭과 코드가 실제로 일치하는지(추측 코드가 아닌지) 공식 코드표로
        # 재확인한다.
        official = load_official_small_series_codes()
        self.assertEqual(official["033"], "경영학")
        self.assertEqual(official["042"], "교육학")
        self.assertEqual(official["102"], "산업공학")
        self.assertEqual(official["078"], "기계공학")
        self.assertEqual(official["035"], "경영정보학")
        self.assertEqual(official["041"], "비서")
        self.assertEqual(official["151"], "금융·보험학")
        self.assertEqual(official["152"], "회계·세무학")
        self.assertEqual(official["103"], "안전공학")
        self.assertEqual(official["104"], "방재공학")


class NonRevisedRowsDefaultScopeTest(RealBridgeScopeLoadTest):
    """REVISE 대상이 아닌 나머지 38개 행은 mapping_status에서 결정론적으로 도출되는
    기본 Scope만 갖고, 기존 Mapping 판단(evidence/decision_reason)은 전혀 바뀌지
    않았는지."""

    def test_non_revised_evidenced_rows_are_full_group(self) -> None:
        non_revised_evidenced = {
            ("computer_science", "computer_science"), ("media_communication", "media_communication"),
            ("psychology", "psychology"), ("life_science", "life_science"),
        }
        for key in non_revised_evidenced:
            e = self.by_key[key]
            self.assertEqual(e.mapping_status, "EVIDENCED")
            self.assertEqual(e.scope_type, "FULL_GROUP")
            self.assertEqual(e.included_small_series_codes, [])
            self.assertEqual(e.excluded_small_series_codes, [])

    def test_unmapped_rows_have_no_scope_type(self) -> None:
        for e in self.report.entries_by_status("UNMAPPED"):
            self.assertIsNone(e.scope_type, e.canonical_major_group_id)
            self.assertEqual(e.included_small_series_codes, [])
            self.assertEqual(e.excluded_small_series_codes, [])

    # 지시서 원문 커밋(ff9b051) 시점의 값을 그대로 굳혀둔다 — git HEAD와 비교하면
    # 이 테스트를 포함한 커밋 이후에는 HEAD 자체가 이미 마이그레이션된 값이라
    # 비교 의미가 사라진다. 그래서 원본 값을 하드코딩해 "이번 작업이 이 필드들을
    # 재작성하지 않았다"를 이 브랜치 어느 시점에 실행해도 항상 같은 기준으로 확인한다.
    _ORIGINAL_MAPPING_FIELDS = {
        ("bio_medical_engineering", "life_science"): {
            "mapping_status": "REVIEW_REQUIRED",
            "evidence": ["소계열 '생명공학'(Group에 포함)", "Major 별칭: 생명공학"],
        },
        ("business", "business_administration"): {
            "mapping_status": "EVIDENCED",
            "evidence": ["소계열 '경영학'", "Major 라벨: 경영학"],
        },
        ("computer_science", "hci_ux"): {
            "mapping_status": "REVIEW_REQUIRED",
            "evidence": [
                "Major 별칭: 인간컴퓨터상호작용, 융합콘텐츠, UX디자인",
                "Group 소계열: 응용소프트웨어공학, 인공지능공학(개념적 연관, 공식 코드명 직접 일치 아님)",
            ],
        },
        ("education", "education"): {
            "mapping_status": "EVIDENCED",
            "evidence": ["소계열 '교육학'", "Major 라벨: 교육학"],
        },
        ("industrial_engineering", "industrial_engineering"): {
            "mapping_status": "EVIDENCED",
            "evidence": [
                "소계열 '산업공학'", "Major 별칭: 산업공학, 산업경영공학, 산업시스템공학",
                "기존 시연 Department(산업경영공학과/산업경영공학부/산업·정보시스템공학과)가 이미 이 Major로 연결됨",
            ],
        },
        ("mechanical_transport", "mechanical_engineering"): {
            "mapping_status": "EVIDENCED",
            "evidence": ["소계열 '기계공학'", "Major 라벨: 기계공학"],
        },
    }

    def test_mapping_evidence_untouched_for_revised_rows(self) -> None:
        # Scope를 좁혔어도 기존 mapping_status/evidence(사람이 검토했던 원문)는
        # 그대로여야 한다 — Bridge Mapping 판단 자체를 재작성하지 않는다.
        raw_rows = [
            json.loads(line)
            for line in DEFAULT_BRIDGE_DRAFT_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        by_key = {(r["canonical_major_group_id"], r["canonical_major_id"]): r for r in raw_rows}
        for key, expected in self._ORIGINAL_MAPPING_FIELDS.items():
            current_row = by_key[key]
            self.assertEqual(current_row["mapping_status"], expected["mapping_status"], key)
            self.assertEqual(current_row["evidence"], expected["evidence"], key)


class OfficialCodeCrossValidationTest(unittest.TestCase):
    """소계열 코드가 (1) 실제 대학알리미 158개 공식 코드표에 있는가, (2) 그 Group
    자신의 소계열 목록에 속하는가 — 둘 다 Loader 계층의 교차 검증이다. 전부
    tempdir에만 쓰고 실제 파일은 절대 건드리지 않는다."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.bridge_path = Path(self.tmpdir.name) / "bridge.draft.jsonl"

    def _full_44_rows_with_business_override(self, business_row: dict) -> list[dict]:
        groups = load_canonical_major_groups_draft()
        from src.services.canonical_major_group_bridge_loader import ARTS_EXCLUDED_GROUP_IDS
        from src.engines.canonical_mapper import load_canonical_majors
        from src.services.canonical_major_group_bridge_loader import DEFAULT_CANONICAL_MAJORS_PATH

        rows: list[dict] = []
        for g in groups:
            if g.canonical_major_id == "business":
                rows.append(business_row)
            elif g.canonical_major_id in ARTS_EXCLUDED_GROUP_IDS:
                rows.append({
                    "canonical_major_group_id": g.canonical_major_id, "canonical_major_id": None,
                    "mapping_status": "EXCLUDED_RECOMMENDATION", "evidence": [], "decision_reason": "예체능 제외",
                    "boundary_notes": "", "review_status": "draft", "reviewer_id": None, "reviewed_at": None,
                    "scope_type": "EXCLUDED_RECOMMENDATION", "included_small_series_codes": [],
                    "excluded_small_series_codes": [], "scope_decision_reason": "", "scope_review_status": "draft",
                })
            else:
                rows.append({
                    "canonical_major_group_id": g.canonical_major_id, "canonical_major_id": None,
                    "mapping_status": "UNMAPPED", "evidence": [], "decision_reason": "",
                    "boundary_notes": "", "review_status": "draft", "reviewer_id": None, "reviewed_at": None,
                    "scope_type": None, "included_small_series_codes": [], "excluded_small_series_codes": [],
                    "scope_decision_reason": "", "scope_review_status": "draft",
                })
        majors = load_canonical_majors(DEFAULT_CANONICAL_MAJORS_PATH)
        rows = [r for r in rows if r["canonical_major_id"] != "business_administration"] + [business_row]
        for m in majors:
            if m.major_id == "business_administration":
                continue
            rows.append({
                "canonical_major_group_id": "business", "canonical_major_id": m.major_id,
                "mapping_status": "REVIEW_REQUIRED", "evidence": [], "decision_reason": "",
                "boundary_notes": "", "review_status": "draft", "reviewer_id": None, "reviewed_at": None,
                "scope_type": "FULL_GROUP", "included_small_series_codes": [], "excluded_small_series_codes": [],
                "scope_decision_reason": "", "scope_review_status": "draft",
            })
        return rows

    def _write(self, rows: list[dict]) -> None:
        self.bridge_path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8",
        )

    def _base_business_row(self, **scope_overrides) -> dict:
        row = {
            "canonical_major_group_id": "business", "canonical_major_id": "business_administration",
            "mapping_status": "EVIDENCED", "evidence": ["소계열 경영학"], "decision_reason": "직접 일치",
            "boundary_notes": "", "review_status": "draft", "reviewer_id": None, "reviewed_at": None,
            "scope_type": "INCLUDED_SMALL_SERIES_ONLY", "included_small_series_codes": ["033"],
            "excluded_small_series_codes": ["035"], "scope_decision_reason": "경영학만", "scope_review_status": "draft",
        }
        row.update(scope_overrides)
        return row

    def test_code_not_in_official_table_rejected(self) -> None:
        bad_row = self._base_business_row(included_small_series_codes=["999999"])
        self._write(self._full_44_rows_with_business_override(bad_row))
        with self.assertRaises(BridgeScopeValidationError):
            load_canonical_major_group_bridge(self.bridge_path)

    def test_code_not_in_this_groups_own_series_list_rejected(self) -> None:
        # "090"(전산학·컴퓨터공학)은 공식 코드표에는 있지만 business Group 소속이 아니다.
        official = load_official_small_series_codes()
        self.assertIn("090", official)
        bad_row = self._base_business_row(included_small_series_codes=["090"])
        self._write(self._full_44_rows_with_business_override(bad_row))
        with self.assertRaises(BridgeScopeValidationError):
            load_canonical_major_group_bridge(self.bridge_path)

    def test_valid_business_scope_codes_load_successfully(self) -> None:
        good_row = self._base_business_row()
        self._write(self._full_44_rows_with_business_override(good_row))
        report = load_canonical_major_group_bridge(self.bridge_path)
        e = next(r for r in report.entries if r.canonical_major_group_id == "business" and r.canonical_major_id == "business_administration")
        self.assertEqual(e.included_small_series_codes, ["033"])


class SchemaBypassDefenseTest(unittest.TestCase):
    """"Schema 우회(model_construct 등)에 대비한 Service 방어 검증" — Pydantic
    검증을 건너뛰고 만든 값도 `validate_bridge_scope_row()`가 잡아내는지 직접 확인한다."""

    def test_model_construct_bypasses_pydantic_but_service_still_rejects(self) -> None:
        # model_construct()는 어떤 model_validator도 실행하지 않는다 — 모순된 값도
        # 예외 없이 만들어진다는 사실 자체를 먼저 증명한다.
        bypassed = CanonicalMajorGroupBridgeEntry.model_construct(
            canonical_major_group_id="business", canonical_major_id="business_administration",
            mapping_status="EVIDENCED", evidence=["x"], decision_reason="y", boundary_notes="",
            review_status="draft", reviewer_id=None, reviewed_at=None,
            scope_type="FULL_GROUP", included_small_series_codes=["033"],  # FULL_GROUP인데 코드가 있음 — 모순.
            excluded_small_series_codes=[], scope_decision_reason="", scope_review_status="draft",
        )
        self.assertEqual(bypassed.scope_type, "FULL_GROUP")  # 정말로 예외 없이 만들어졌다.

        official = load_official_small_series_codes()
        groups = {g.canonical_major_id: g for g in load_canonical_major_groups_draft()}
        group_codes = frozenset(groups["business"].included_official_small_series_codes)
        with self.assertRaises(BridgeScopeValidationError):
            validate_bridge_scope_row(bypassed, official_codes=official, group_small_series_codes=group_codes)

    def test_error_message_contains_no_secrets_or_free_text_user_data(self) -> None:
        # 오류 메시지에는 group_id/major_id/코드값만 담긴다 — API Key, 질문 원문,
        # 사용자 자유서술 같은 값은 애초에 이 함수의 인자에 존재하지 않는다.
        bypassed = CanonicalMajorGroupBridgeEntry.model_construct(
            canonical_major_group_id="business", canonical_major_id="business_administration",
            mapping_status="EVIDENCED", evidence=["x"], decision_reason="y", boundary_notes="",
            review_status="draft", reviewer_id=None, reviewed_at=None,
            scope_type="FULL_GROUP", included_small_series_codes=["033"],
            excluded_small_series_codes=[], scope_decision_reason="", scope_review_status="draft",
        )
        official = load_official_small_series_codes()
        groups = {g.canonical_major_id: g for g in load_canonical_major_groups_draft()}
        group_codes = frozenset(groups["business"].included_official_small_series_codes)
        try:
            validate_bridge_scope_row(bypassed, official_codes=official, group_small_series_codes=group_codes)
            self.fail("예외가 발생해야 한다")
        except BridgeScopeValidationError as exc:
            message = str(exc)
            self.assertNotIn("API_KEY", message.upper())
            self.assertNotIn("SECRET", message.upper())
            for forbidden_pattern in ("sk-", "Bearer "):
                self.assertNotIn(forbidden_pattern, message)


class BuildDeterminismAndImmutabilityTest(unittest.TestCase):
    """빌드 2회 byte-identical + 실제 Master/Mock/OpenAPI/Review JSON 무변경."""

    def test_migration_script_two_runs_byte_identical(self) -> None:
        rows1 = build_scoped_rows()
        rows2 = build_scoped_rows()
        self.assertEqual(rows1, rows2)
        text1 = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows1) + "\n"
        text2 = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows2) + "\n"
        self.assertEqual(text1, text2)

    def test_migration_script_is_idempotent_against_already_migrated_file(self) -> None:
        # 이미 Scope 필드가 채워진 실제 파일에 다시 돌려도(재실행) 같은 44행이 나온다.
        before = DEFAULT_BRIDGE_DRAFT_PATH.read_bytes()
        rows = build_scoped_rows()
        text = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
        self.assertEqual(text.encode("utf-8"), before)

    def test_existing_master_files_unchanged_from_head_except_bridge_draft(self) -> None:
        # canonical_major_group_bridge.draft.jsonl 자체는 이번 작업의 대상이므로
        # 제외하고, 나머지 정본(Major 10개)은 무변경이어야 한다.
        # data/master/departments.jsonl은 2026-08-25 전국 학과 1,072건 Production
        # Master 전환(a/national-master-promotion-final-wiring)이 이 Bridge 작업과
        # 무관하게 의도적으로 바꾼다 — 옛 35건은 archive로 보존됐다.
        # major_profiles_v2.jsonl(당시 3개)도 같은 원칙으로 뺐다 — 2026-08-25
        # a/major-profiles-v2-38 병합이 그 파일을 39개로 정당하게 확장한다(이
        # Bridge 작업 자체와는 무관한 다른 라운드의 의도된 변경).
        for rel_path in (
            "data/master/canonical_majors.jsonl",
            "data/canonical_major_groups.draft.jsonl",
        ):
            result = subprocess.run(
                ["git", "diff", "--exit-code", "HEAD", "--", rel_path],
                cwd=_REPO_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, f"{rel_path} changed:\n{result.stdout}")

    def test_mock_api_and_openapi_outputs_unchanged_from_head(self) -> None:
        # 2026-08-25 전국 학과 1,072건 Production Master 전환(a/national-master-
        # promotion-final-wiring) §7이 scripts/generate_mock_json.py를 다시 실행해
        # departments_normal.json·subgraph_normal.json을 의도적으로 새 Master 기준으로
        # 재생성했다(공개 OpenAPI Schema 자체는 byte-identical로 남아 있음을 별도로
        # 확인했다) — 이 Bridge 작업과 무관한 변경이라 diff 대상에서 뺀다.
        result = subprocess.run(
            [
                "git", "diff", "--exit-code", "HEAD", "--", "outputs/mock_api/",
                ":(exclude)outputs/mock_api/departments_normal.json",
                ":(exclude)outputs/mock_api/subgraph_normal.json",
            ],
            cwd=_REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, f"outputs/mock_api/ changed:\n{result.stdout}")

    def test_build_scoped_rows_itself_never_touches_data_reviews(self) -> None:
        """2026-08(a/final-mapping-review-closeout) 정정, a/offering-identity-v2와의
        병합(2026-08-25)에서 통합 — 이전 버전은 저장소 전체의 `git status --porcelain
        -- data/reviews/`가 항상 빈 문자열이어야 한다고 확인했다. 그 가정은 "이 파일이
        다루는 ADD-SCOPE-FIELD Migration 함수(`build_scoped_rows()`)가 Review 파일에
        부작용이 없다"를 확인하려던 것이었는데, 검사 방식이 저장소 전체 git 상태였던
        탓에 이 브랜치들에서 각자 진행 중인 *다른* 정당한 작업(Mapping/Scope/P1/
        N.C.E 검수 확정 — `scripts/career_finalize_mapping_review_closeout.py`,
        Department Identity Collision Row Review 신규 검수 축 등)이 data/reviews/에
        쓰는 것까지 이 테스트가 실패로 오탐했다(offering-identity-v2 쪽은 `??` 새
        파일만 제외하는 부분 완화를 시도했지만, 여전히 다른 브랜치의 기존 파일
        수정까지 오탐할 수 있었다). 이 함수가 실제로 순수 함수(파일을 전혀 쓰지
        않는 in-memory 계산)라는 원래 취지는 `data/reviews/`의 Before/After 해시를
        `build_scoped_rows()` 호출 앞뒤로만 비교해서 그대로 검증한다 — 저장소 전체의
        다른 변경과 더 이상 얽히지 않는다."""

        reviews_dir = _REPO_ROOT / "data" / "reviews"
        before = {
            str(p.relative_to(reviews_dir)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(reviews_dir.rglob("*")) if p.is_file()
        }
        build_scoped_rows()
        after = {
            str(p.relative_to(reviews_dir)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(reviews_dir.rglob("*")) if p.is_file()
        }
        self.assertEqual(before, after, "build_scoped_rows()가 data/reviews/ 아래 파일을 건드렸다")

    def test_no_review_status_file_was_created_by_this_work(self) -> None:
        self.assertFalse(
            (_REPO_ROOT / "data" / "reviews" / "canonical_major_group_bridge_review_status.json").exists()
            and subprocess.run(
                ["git", "ls-files", "--error-unmatch",
                 "data/reviews/canonical_major_group_bridge_review_status.json"],
                cwd=_REPO_ROOT, capture_output=True, text=True,
            ).returncode != 0,
        )


class DepartmentCountsUnchangedTest(unittest.TestCase):
    """전국 Master 승격·Runtime 연결 없음을 실제 서비스 결과로도 재확인한다 — 기존
    4/3/1/0(media_communication/industrial_engineering/hci_ux/design) + 10(Major
    전체 개수) 결과가 이번 Scope 작업 전후로 그대로다."""

    def test_existing_national_results_unchanged_with_real_data(self) -> None:
        """2026-08-25 전국 학과 1,072건 전환 — 옛 데모 4/3/1/0 대신 실제 전국
        기준값을 확인한다(archive에 옛 값은 그대로 보존돼 있다)."""
        from src.engines.canonical_mapper import load_canonical_majors
        from src.repositories.department_repository import JsonlDepartmentRepository
        from src.services.canonical_major_group_bridge_loader import DEFAULT_CANONICAL_MAJORS_PATH
        from src.services.major_exploration_service import MajorExplorationService

        repo = JsonlDepartmentRepository()
        service = MajorExplorationService(repo)
        self.assertEqual(len(service.list_departments_for_major("media_communication")), 133)
        self.assertEqual(len(service.list_departments_for_major("industrial_engineering")), 53)
        self.assertEqual(len(service.list_departments_for_major("hci_ux")), 0)
        self.assertEqual(len(service.list_departments_for_major("design")), 0)
        self.assertEqual(len(load_canonical_majors(DEFAULT_CANONICAL_MAJORS_PATH)), 10)


class RuntimeNotWiredTest(unittest.TestCase):
    """이번 작업도 이전 Bridge 작업과 동일하게 Runtime·공개 API에 연결하지 않는다."""

    _RUNTIME_MODULES = (
        "src/api/main.py", "src/engines/matching_engine.py", "src/engines/matching_engine_v2.py",
        "src/services/major_exploration_service.py", "src/services/course_planning_service.py",
        "src/services/course_planning_service_v2.py", "src/services/knowledge_subgraph_service.py",
        "src/repositories/department_repository.py",
    )

    def test_no_runtime_or_public_api_module_imports_the_bridge(self) -> None:
        forbidden_import_patterns = (
            "import canonical_major_group_bridge", "from src.schemas.canonical_major_group_bridge",
            "from src.services.canonical_major_group_bridge_loader",
        )
        for rel_path in self._RUNTIME_MODULES:
            path = _REPO_ROOT / rel_path
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            for pattern in forbidden_import_patterns:
                self.assertNotIn(pattern, text, f"{rel_path}: {pattern!r}")

    def test_forbidden_files_untouched_from_head(self) -> None:
        # 2026-08-25 전국 학과 1,072건 Production Master 전환(a/national-master-
        # promotion-final-wiring) §4/§5가 major_exploration_service.py(fail_closed_
        # major_ids 10개 통일)와 departments.jsonl(1,072건 교체)을 실제로 바꾼다 —
        # 이 Bridge 작업과 무관한 변경이라 이 목록에서 뺀다. department_repository.py는
        # 이번 라운드에서도 변경되지 않았으므로 계속 확인한다.
        for rel_path in (
            "src/repositories/department_repository.py",
        ):
            result = subprocess.run(
                ["git", "diff", "--exit-code", "HEAD", "--", rel_path],
                cwd=_REPO_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, f"{rel_path} changed:\n{result.stdout}")


if __name__ == "__main__":
    unittest.main()
