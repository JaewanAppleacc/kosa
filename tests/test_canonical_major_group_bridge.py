"""Canonical Major Group ↔ Canonical Major Bridge 계약 테스트 — 2026-08-24
지시서(Bridge 계약) §7.

42개 Canonical Major Group(분류용 중간 Ontology)과 10개 Canonical Major(서비스
추천 정본) 사이를 잇는 Bridge(`data/master/canonical_major_group_bridge.draft.jsonl`)
가 두 계층을 대체하지 않고, 근거 없이 확정하지 않으며, Runtime에 아직 연결되지
않았는지를 검증한다."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from src.engines.canonical_mapper import load_canonical_majors
from src.schemas.canonical_major_group_bridge import CanonicalMajorGroupBridgeEntry
from src.services.canonical_major_group_bridge_loader import (
    ARTS_EXCLUDED_GROUP_IDS,
    BridgeValidationError,
    DEFAULT_CANONICAL_MAJORS_PATH,
    load_canonical_major_group_bridge,
)
from src.services.canonical_major_group_draft_loader import load_canonical_major_groups_draft

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


class RealBridgeFileLoadTest(unittest.TestCase):
    """실제 커밋된 Bridge draft 파일 자체가 42개 Group·10개 Major 전체와 정합적인지."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.report = load_canonical_major_group_bridge()

    # 42개 Group 정본 로드.
    def test_all_42_groups_covered(self) -> None:
        group_ids = {g.canonical_major_id for g in load_canonical_major_groups_draft()}
        self.assertEqual(len(group_ids), 42)
        self.assertEqual(self.report.group_ids_covered(), group_ids)

    # 기존 10개 Major ID 불변 — Bridge 로드가 canonical_majors.jsonl을 전혀
    # 수정하지 않고, 10개 그대로 읽는지.
    def test_existing_10_major_ids_unchanged(self) -> None:
        majors = load_canonical_majors(DEFAULT_CANONICAL_MAJORS_PATH)
        major_ids = {m.major_id for m in majors}
        self.assertEqual(len(major_ids), 10)
        expected = {
            "computer_science", "media_communication", "design", "business_administration",
            "psychology", "mechanical_engineering", "education", "life_science",
            "industrial_engineering", "hci_ux",
        }
        self.assertEqual(major_ids, expected)

    def test_every_major_has_at_least_one_bridge_candidate(self) -> None:
        majors = load_canonical_majors(DEFAULT_CANONICAL_MAJORS_PATH)
        for m in majors:
            self.assertGreater(len(self.report.entries_for_major(m.major_id)), 0, m.major_id)

    # 예체능 Fail-Closed — 4개 Group은 항상 EXCLUDED_RECOMMENDATION이고, 다른 어떤
    # 상태로도 등장하지 않는다.
    def test_arts_groups_are_always_excluded_recommendation(self) -> None:
        self.assertEqual(ARTS_EXCLUDED_GROUP_IDS, {"fine_arts_design", "music", "performing_media_arts", "sports_dance"})
        for group_id in ARTS_EXCLUDED_GROUP_IDS:
            rows = self.report.entries_for_group(group_id)
            self.assertGreater(len(rows), 0, group_id)
            for r in rows:
                self.assertEqual(r.mapping_status, "EXCLUDED_RECOMMENDATION", f"{group_id}: {r.mapping_status}")

    def test_design_major_excluded_group_matches_existing_runtime_exclusion_policy(self) -> None:
        from src.services.major_exploration_service import EXCLUDED_RECOMMENDATION_MAJOR_IDS

        design_rows = self.report.entries_for_major("design")
        self.assertGreater(len(design_rows), 0)
        for r in design_rows:
            self.assertEqual(r.mapping_status, "EXCLUDED_RECOMMENDATION")
        self.assertIn("design", EXCLUDED_RECOMMENDATION_MAJOR_IDS)

    # 상태·근거 정합성.
    def test_evidenced_rows_have_evidence_and_reason(self) -> None:
        for r in self.report.entries_by_status("EVIDENCED"):
            self.assertIsNotNone(r.canonical_major_id)
            self.assertGreater(len(r.evidence), 0, r.canonical_major_group_id)
            self.assertTrue(r.decision_reason.strip(), r.canonical_major_group_id)

    def test_unmapped_rows_have_no_major_target(self) -> None:
        for r in self.report.entries_by_status("UNMAPPED"):
            self.assertIsNone(r.canonical_major_id, r.canonical_major_group_id)

    def test_no_review_status_is_pre_approved(self) -> None:
        for r in self.report.entries:
            self.assertEqual(r.review_status, "draft", r.canonical_major_group_id)
            self.assertIsNone(r.reviewer_id)
            self.assertIsNone(r.reviewed_at)


class SchemaFieldValidationTest(unittest.TestCase):
    """행 하나만 봐도 판단 가능한 구조 규칙 — Pydantic 계층."""

    def test_evidenced_without_major_id_rejected(self) -> None:
        with self.assertRaises(PydanticValidationError):
            CanonicalMajorGroupBridgeEntry(
                canonical_major_group_id="business", canonical_major_id=None,
                mapping_status="EVIDENCED", evidence=["x"], decision_reason="y",
            )

    def test_evidenced_without_evidence_rejected(self) -> None:
        with self.assertRaises(PydanticValidationError):
            CanonicalMajorGroupBridgeEntry(
                canonical_major_group_id="business", canonical_major_id="business_administration",
                mapping_status="EVIDENCED", evidence=[], decision_reason="y",
            )

    def test_evidenced_without_decision_reason_rejected(self) -> None:
        with self.assertRaises(PydanticValidationError):
            CanonicalMajorGroupBridgeEntry(
                canonical_major_group_id="business", canonical_major_id="business_administration",
                mapping_status="EVIDENCED", evidence=["x"], decision_reason="   ",
            )

    def test_unmapped_with_major_id_rejected(self) -> None:
        with self.assertRaises(PydanticValidationError):
            CanonicalMajorGroupBridgeEntry(
                canonical_major_group_id="law", canonical_major_id="business_administration",
                mapping_status="UNMAPPED",
            )

    def test_review_required_without_major_id_rejected(self) -> None:
        with self.assertRaises(PydanticValidationError):
            CanonicalMajorGroupBridgeEntry(canonical_major_group_id="law", mapping_status="REVIEW_REQUIRED")

    def test_review_required_and_unmapped_do_not_require_evidence(self) -> None:
        # REVIEW_REQUIRED/UNMAPPED를 EVIDENCED처럼 강제로 취급하지 않는다 — evidence가
        # 없어도 구조적으로는 유효하다(EVIDENCED만 evidence를 강제한다).
        entry = CanonicalMajorGroupBridgeEntry(
            canonical_major_group_id="law", canonical_major_id="business_administration",
            mapping_status="REVIEW_REQUIRED", scope_type="DEPARTMENT_REVIEW_REQUIRED",
        )
        self.assertEqual(entry.evidence, [])

    def test_valid_evidenced_row_ok(self) -> None:
        entry = CanonicalMajorGroupBridgeEntry(
            canonical_major_group_id="business", canonical_major_id="business_administration",
            mapping_status="EVIDENCED", evidence=["소계열 경영학"], decision_reason="라벨 직접 일치",
            scope_type="FULL_GROUP",
        )
        self.assertEqual(entry.review_status, "draft")
        self.assertEqual(entry.scope_review_status, "draft")

    # 2026-08-24 a/canonical-major-bridge-scope 지시서 §2 — Scope 필드 자체의 행 단위
    # 검증(신규). 교차 검증(코드가 실제 코드표·그 Group에 속하는가)은 Loader 계층
    # 몫이므로 아래 CrossFileValidationTest에서 다룬다.
    def test_evidenced_without_scope_type_rejected(self) -> None:
        with self.assertRaises(PydanticValidationError):
            CanonicalMajorGroupBridgeEntry(
                canonical_major_group_id="business", canonical_major_id="business_administration",
                mapping_status="EVIDENCED", evidence=["x"], decision_reason="y",
            )

    def test_unmapped_with_scope_type_rejected(self) -> None:
        with self.assertRaises(PydanticValidationError):
            CanonicalMajorGroupBridgeEntry(
                canonical_major_group_id="law", mapping_status="UNMAPPED", scope_type="FULL_GROUP",
            )

    def test_excluded_recommendation_scope_type_must_match(self) -> None:
        with self.assertRaises(PydanticValidationError):
            CanonicalMajorGroupBridgeEntry(
                canonical_major_group_id="music", mapping_status="EXCLUDED_RECOMMENDATION", scope_type="FULL_GROUP",
            )

    def test_scope_type_excluded_recommendation_requires_matching_mapping_status(self) -> None:
        with self.assertRaises(PydanticValidationError):
            CanonicalMajorGroupBridgeEntry(
                canonical_major_group_id="business", canonical_major_id="business_administration",
                mapping_status="EVIDENCED", evidence=["x"], decision_reason="y",
                scope_type="EXCLUDED_RECOMMENDATION",
            )

    def test_full_group_with_included_codes_rejected(self) -> None:
        with self.assertRaises(PydanticValidationError):
            CanonicalMajorGroupBridgeEntry(
                canonical_major_group_id="business", canonical_major_id="business_administration",
                mapping_status="EVIDENCED", evidence=["x"], decision_reason="y",
                scope_type="FULL_GROUP", included_small_series_codes=["033"],
            )

    def test_full_group_with_excluded_codes_rejected(self) -> None:
        with self.assertRaises(PydanticValidationError):
            CanonicalMajorGroupBridgeEntry(
                canonical_major_group_id="business", canonical_major_id="business_administration",
                mapping_status="EVIDENCED", evidence=["x"], decision_reason="y",
                scope_type="FULL_GROUP", excluded_small_series_codes=["035"],
            )

    def test_included_small_series_only_without_included_codes_rejected(self) -> None:
        with self.assertRaises(PydanticValidationError):
            CanonicalMajorGroupBridgeEntry(
                canonical_major_group_id="business", canonical_major_id="business_administration",
                mapping_status="EVIDENCED", evidence=["x"], decision_reason="y",
                scope_type="INCLUDED_SMALL_SERIES_ONLY", included_small_series_codes=[],
            )

    def test_included_excluded_intersection_rejected(self) -> None:
        with self.assertRaises(PydanticValidationError):
            CanonicalMajorGroupBridgeEntry(
                canonical_major_group_id="business", canonical_major_id="business_administration",
                mapping_status="EVIDENCED", evidence=["x"], decision_reason="y",
                scope_type="INCLUDED_SMALL_SERIES_ONLY",
                included_small_series_codes=["033", "035"], excluded_small_series_codes=["035"],
            )

    def test_duplicate_code_within_included_rejected(self) -> None:
        with self.assertRaises(PydanticValidationError):
            CanonicalMajorGroupBridgeEntry(
                canonical_major_group_id="business", canonical_major_id="business_administration",
                mapping_status="EVIDENCED", evidence=["x"], decision_reason="y",
                scope_type="INCLUDED_SMALL_SERIES_ONLY", included_small_series_codes=["033", "033"],
            )

    def test_blank_code_rejected(self) -> None:
        with self.assertRaises(PydanticValidationError):
            CanonicalMajorGroupBridgeEntry(
                canonical_major_group_id="business", canonical_major_id="business_administration",
                mapping_status="EVIDENCED", evidence=["x"], decision_reason="y",
                scope_type="INCLUDED_SMALL_SERIES_ONLY", included_small_series_codes=["033", "   "],
            )

    def test_department_review_required_does_not_auto_promote_scope_review_status(self) -> None:
        # DEPARTMENT_REVIEW_REQUIRED는 Group 전체를 자동 승격할 수 없다 — Schema
        # 기본값 자체가 scope_review_status="draft"이고, 이 scope_type이라고 해서
        # "approved"로 자동 전환되지 않는다는 사실을 명시적으로 고정한다.
        entry = CanonicalMajorGroupBridgeEntry(
            canonical_major_group_id="bio_medical_engineering", canonical_major_id="life_science",
            mapping_status="REVIEW_REQUIRED", scope_type="DEPARTMENT_REVIEW_REQUIRED",
        )
        self.assertEqual(entry.scope_review_status, "draft")


class CrossFileValidationTest(unittest.TestCase):
    """파일 전체·다른 정본과 대조해야 하는 규칙 — Loader 계층. 전부 tempdir에만
    쓰고 실제 data/master/canonical_major_group_bridge.draft.jsonl은 읽기만 한다."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.bridge_path = Path(self.tmpdir.name) / "bridge.draft.jsonl"

    def _valid_minimal_row(self, **overrides) -> dict:
        row = {
            "canonical_major_group_id": "business", "canonical_major_id": "business_administration",
            "mapping_status": "EVIDENCED", "evidence": ["소계열 경영학"], "decision_reason": "직접 일치",
            "boundary_notes": "", "review_status": "draft", "reviewer_id": None, "reviewed_at": None,
            # 2026-08-24 a/canonical-major-bridge-scope 지시서 — EVIDENCED 기본값은
            # FULL_GROUP(소계열 코드가 필요 없어 어떤 Group에든 안전하게 쓸 수 있다).
            # UNMAPPED/EXCLUDED_RECOMMENDATION로 overrides하는 호출부는 scope_type도
            # 함께 override해야 한다(안 하면 Schema가 그 모순을 바로 거부한다).
            "scope_type": "FULL_GROUP", "included_small_series_codes": [], "excluded_small_series_codes": [],
            "scope_decision_reason": "", "scope_review_status": "draft",
        }
        row.update(overrides)
        return row

    # 존재하지 않는 Group 거부.
    def test_unknown_group_id_rejected(self) -> None:
        _write_jsonl(self.bridge_path, [self._valid_minimal_row(canonical_major_group_id="not_a_real_group")])
        with self.assertRaises(BridgeValidationError):
            load_canonical_major_group_bridge(self.bridge_path)

    # 존재하지 않는 Major 거부.
    def test_unknown_major_id_rejected(self) -> None:
        _write_jsonl(self.bridge_path, [self._valid_minimal_row(canonical_major_id="not_a_real_major")])
        with self.assertRaises(BridgeValidationError):
            load_canonical_major_group_bridge(self.bridge_path)

    # Bridge 중복 차단.
    def test_duplicate_bridge_key_rejected(self) -> None:
        _write_jsonl(self.bridge_path, [self._valid_minimal_row(), self._valid_minimal_row()])
        with self.assertRaises(BridgeValidationError):
            load_canonical_major_group_bridge(self.bridge_path)

    def test_group_with_unmapped_row_cannot_also_have_other_rows(self) -> None:
        rows = [
            self._valid_minimal_row(
                canonical_major_group_id="law", canonical_major_id=None, mapping_status="UNMAPPED",
                evidence=[], decision_reason="", scope_type=None,
            ),
            self._valid_minimal_row(canonical_major_group_id="law", canonical_major_id="business_administration"),
        ]
        _write_jsonl(self.bridge_path, rows)
        with self.assertRaises(BridgeValidationError):
            load_canonical_major_group_bridge(self.bridge_path)

    # 예체능 Fail-Closed(Loader 레벨) — 4개 Group 중 하나가 EVIDENCED로 저장되면 거부.
    def test_arts_group_stored_as_evidenced_rejected(self) -> None:
        _write_jsonl(
            self.bridge_path,
            [self._valid_minimal_row(canonical_major_group_id="fine_arts_design", canonical_major_id="design")],
        )
        with self.assertRaises(BridgeValidationError):
            load_canonical_major_group_bridge(self.bridge_path)

    def test_missing_group_coverage_rejected(self) -> None:
        # 42개 중 하나도 없는 완전히 빈 파일 — "감사 불가" 상태.
        _write_jsonl(self.bridge_path, [])
        with self.assertRaises(BridgeValidationError):
            load_canonical_major_group_bridge(self.bridge_path)

    def test_valid_two_group_file_loads(self) -> None:
        # 이 테스트는 완결성 검증(42개 전체 커버)을 우회하기 위해 존재하는 Group
        # 전체를 넣어야 하므로, 실제 42개 draft를 그대로 재사용하되 major 연결
        # 하나만 커스텀으로 바꿔서 로드가 성공하는지 확인한다.
        real_groups = load_canonical_major_groups_draft()
        rows = []
        for g in real_groups:
            if g.canonical_major_id == "business":
                rows.append(self._valid_minimal_row())
            elif g.canonical_major_id in ARTS_EXCLUDED_GROUP_IDS:
                rows.append(self._valid_minimal_row(
                    canonical_major_group_id=g.canonical_major_id, canonical_major_id=None,
                    mapping_status="EXCLUDED_RECOMMENDATION", evidence=[], decision_reason="예체능 제외",
                    scope_type="EXCLUDED_RECOMMENDATION",
                ))
            else:
                rows.append(self._valid_minimal_row(
                    canonical_major_group_id=g.canonical_major_id, canonical_major_id=None,
                    mapping_status="UNMAPPED", evidence=[], decision_reason="", scope_type=None,
                ))
        # 10개 Major 전부 최소 하나의 후보가 있어야 하는 완결성 규칙도 만족시킨다
        # (business 하나만 연결하면 나머지 9개 Major가 후보 없음으로 거부되므로).
        majors = load_canonical_majors(DEFAULT_CANONICAL_MAJORS_PATH)
        rows = [r for r in rows if r["canonical_major_id"] != "business_administration"] + [
            self._valid_minimal_row(
                canonical_major_group_id="business", canonical_major_id="business_administration",
            )
        ]
        for m in majors:
            if m.major_id == "business_administration":
                continue
            rows.append(self._valid_minimal_row(
                canonical_major_group_id="business", canonical_major_id=m.major_id,
                mapping_status="REVIEW_REQUIRED", evidence=[], decision_reason="",
            ))
        _write_jsonl(self.bridge_path, rows)
        report = load_canonical_major_group_bridge(self.bridge_path)
        self.assertEqual(len(report.group_ids_covered()), 42)


class RuntimeNotWiredTest(unittest.TestCase):
    """REVIEW_REQUIRED/UNMAPPED Runtime 미사용 — 이번 단계에서는 Loader·검증기까지만
    만들고 실제 조회 경로(공개 API·Matching Engine)에는 아직 연결하지 않는다(§3)."""

    _RUNTIME_MODULES = (
        "src/api/main.py", "src/engines/matching_engine.py", "src/engines/matching_engine_v2.py",
        "src/services/major_exploration_service.py", "src/services/course_planning_service.py",
        "src/services/course_planning_service_v2.py", "src/services/knowledge_subgraph_service.py",
    )

    def test_no_runtime_or_public_api_module_imports_the_bridge(self) -> None:
        # 실제 import 문(모듈 경로로서의 canonical_major_group_bridge[_loader])만
        # 금지한다 — "왜 42개 Group ID를 막는지" 설명하는 주석·docstring이 이 파일
        # 이름을 문서화 목적으로 언급하는 것까지는 막지 않는다(예:
        # major_exploration_service.py의 DEFAULT_SERVICE_MAJOR_IDS 설명 주석).
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

    def test_public_schemas_do_not_reference_bridge(self) -> None:
        # major.py는 이미 자기 것과 무관한 mapping_status 필드를 갖고 있다
        # (CanonicalMappingResult, department↔major 확정 파이프라인 — 이 Bridge와는
        # 완전히 다른 기존 기능이다) — 그래서 "mapping_status" 문자열 자체가 아니라
        # 이 Bridge 모듈을 실제로 import하는지만 확인한다.
        path = _REPO_ROOT / "src" / "schemas" / "major.py"
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("canonical_major_group_bridge", text)
        self.assertNotIn("CanonicalMajorGroupBridgeEntry", text)


class BuildDeterminismTest(unittest.TestCase):
    """빌드 2회 byte-identical — 리뷰 마크다운 생성기를 실제로 두 번 실행해 비교한다.
    실제 outputs/reviews/canonical_major_group_bridge_review.md를 건드리지 않도록
    임시 경로로 OUTPUT_PATH를 바꿔치기한다."""

    def test_two_runs_produce_byte_identical_markdown(self) -> None:
        import scripts.career_generate_canonical_major_group_bridge_review as gen

        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            out1 = Path(tmp1) / "review.md"
            out2 = Path(tmp2) / "review.md"
            with unittest_mock_output_path(gen, out1):
                gen.main()
            with unittest_mock_output_path(gen, out2):
                gen.main()
            self.assertEqual(out1.read_bytes(), out2.read_bytes())
            self.assertTrue(out1.read_bytes().endswith(b"\n"))
            self.assertFalse(out1.read_bytes().endswith(b"\n\n"))


def unittest_mock_output_path(module, path: Path):
    from unittest.mock import patch

    return patch.object(module, "OUTPUT_PATH", path)


class ExistingMatchingAndMockUnaffectedTest(unittest.TestCase):
    """기존 Matching 결과·API Mock byte-identical — 이번 Bridge 작업이
    outputs/mock_api/*.json이나 canonical_majors.jsonl/major_profiles_v2.jsonl을
    전혀 건드리지 않았는지 Git과 대조한다(작업 전 기록한 값과 동일해야 한다)."""

    def test_existing_master_files_unchanged_from_head(self) -> None:
        # 2026-08-25 전국 학과 1,072건 Production Master 전환(a/national-master-
        # promotion-final-wiring)이 data/master/departments.jsonl을 의도적으로
        # 바꾼다 — 이 Bridge 작업 자체와는 무관한 변경이라 이 목록에서 뺀다(기존
        # 35건은 data/archive/departments_legacy_demo_35.jsonl로 보존됐다).
        #
        # 2026-08-25 추가 갱신(a/major-profiles-v2-38 병합) — major_profiles_v2.jsonl
        # (당시 3개)은 그 후속 작업이 39개로 정당하게 확장하는 파일이라 같은 이유로
        # 이 목록에서 뺐다(§ 위 departments.jsonl과 동일한 원칙 — 이 Bridge 작업
        # 자체와 무관한, 다른 라운드의 의도된 변경).
        for rel_path in (
            "data/master/canonical_majors.jsonl",
        ):
            result = subprocess.run(
                ["git", "diff", "--exit-code", "HEAD", "--", rel_path],
                cwd=_REPO_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, f"{rel_path} changed:\n{result.stdout}")

    def test_mock_api_outputs_unchanged_from_head(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
