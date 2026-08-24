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
            mapping_status="REVIEW_REQUIRED",
        )
        self.assertEqual(entry.evidence, [])

    def test_valid_evidenced_row_ok(self) -> None:
        entry = CanonicalMajorGroupBridgeEntry(
            canonical_major_group_id="business", canonical_major_id="business_administration",
            mapping_status="EVIDENCED", evidence=["소계열 경영학"], decision_reason="라벨 직접 일치",
        )
        self.assertEqual(entry.review_status, "draft")


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
                evidence=[], decision_reason="",
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
                ))
            else:
                rows.append(self._valid_minimal_row(
                    canonical_major_group_id=g.canonical_major_id, canonical_major_id=None,
                    mapping_status="UNMAPPED", evidence=[], decision_reason="",
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
        for rel_path in self._RUNTIME_MODULES:
            path = _REPO_ROOT / rel_path
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("canonical_major_group_bridge", text, rel_path)

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
        for rel_path in (
            "data/master/canonical_majors.jsonl", "data/master/major_profiles_v2.jsonl",
            "data/master/departments.jsonl",
        ):
            result = subprocess.run(
                ["git", "diff", "--exit-code", "HEAD", "--", rel_path],
                cwd=_REPO_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, f"{rel_path} changed:\n{result.stdout}")

    def test_mock_api_outputs_unchanged_from_head(self) -> None:
        result = subprocess.run(
            ["git", "diff", "--exit-code", "HEAD", "--", "outputs/mock_api/"],
            cwd=_REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, f"outputs/mock_api/ changed:\n{result.stdout}")


if __name__ == "__main__":
    unittest.main()
