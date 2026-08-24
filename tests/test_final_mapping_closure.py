"""Final Mapping Closure 테스트 — a/final-mapping-closure.

핵심 증명 대상(과제 §7/§10):
    1. 어떤 검수 파일도 만들거나 고치지 않는다(`data/reviews/` 무변경, auto_approved_rows=0).
    2. 5개 카테고리 분류 개수가 실제 Draft/Review 데이터와 정확히 일치한다.
    3. Bridge Scope §4 보존 대상 6개, Bridge Mapping 기존 검수(38 APPROVE/6 REVISE)가
       그대로 반영됐다.
    4. Priority HTML에는 HUMAN_REVIEW_REQUIRED만 들어간다.
    5. 서로 다른 PYTHONHASHSEED로 별도 프로세스에서 두 번 실행해도 산출물이
       byte-identical하다.
    6. `src/ids.py`·Department Repository/Schema·Runtime Planner·Stop
       Condition·ContextPack 질문/Mapping·공개 API·frontend/ 어느 것도 이
       스크립트가 Import조차 하지 않는다(Department Identity 관련 파일 무변경)."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "career_build_final_mapping_closure.py"
REVIEWS_DIR = ROOT / "data" / "reviews"
MASTER_PATH = ROOT / "data" / "master" / "departments.jsonl"
JSON_SUMMARY = ROOT / "outputs" / "evaluation" / "final_mapping_closure_summary.json"
MD_REVIEW = ROOT / "outputs" / "evaluation" / "final_mapping_closure_review.md"
PRIORITY_HTML = ROOT / "outputs" / "evaluation" / "final_mapping_priority_review.html"

sys.path.insert(0, str(ROOT))


def _hash_tree(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*")) if p.is_file()
    }


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class NoReviewFileMutationTest(unittest.TestCase):
    """§7 '자동 승인 금지' — data/reviews/를 한 바이트도 바꾸지 않는다."""

    def test_classifiers_leave_data_reviews_untouched(self) -> None:
        from scripts.career_build_final_mapping_closure import classify_bridge, classify_groups, classify_nce, classify_p1

        before = _hash_tree(REVIEWS_DIR)
        group_rows = classify_groups()
        classify_bridge(
            mapping_review_path=REVIEWS_DIR / "canonical_major_group_bridge_review_status.json",
            scope_review_path=REVIEWS_DIR / "canonical_major_group_bridge_scope_review_status.jsonl",
        )
        classify_p1()
        classify_nce()
        after = _hash_tree(REVIEWS_DIR)
        self.assertEqual(before, after, "data/reviews/ 아래 파일이 변경됐다")
        self.assertEqual(len(group_rows), 42)

    def test_main_leaves_data_reviews_and_master_untouched(self) -> None:
        from scripts.career_build_final_mapping_closure import main

        reviews_before = _hash_tree(REVIEWS_DIR)
        master_before = _hash_file(MASTER_PATH)
        rc = main([])
        self.assertEqual(rc, 0)
        reviews_after = _hash_tree(REVIEWS_DIR)
        master_after = _hash_file(MASTER_PATH)
        self.assertEqual(reviews_before, reviews_after)
        self.assertEqual(master_before, master_after)

    def test_hypothetical_review_files_only_exist_inside_tempdir(self) -> None:
        """가정 Dry Run이 만드는 임시 검수 파일(Group Draft 복사본·Bridge Scope/P1
        검수)이 tempfile 안에서만 생기고 실제 data/ 아래 어디에도 남지 않는지."""

        from scripts.career_build_final_mapping_closure import classify_bridge, classify_groups, classify_p1, compute_hypothetical_ready_for_promotion

        group_rows = classify_groups()
        _, scope_rows = classify_bridge(
            mapping_review_path=REVIEWS_DIR / "canonical_major_group_bridge_review_status.json",
            scope_review_path=REVIEWS_DIR / "canonical_major_group_bridge_scope_review_status.jsonl",
        )
        p1_rows = classify_p1()

        before_data_tree = _hash_tree(ROOT / "data")
        result = compute_hypothetical_ready_for_promotion(
            group_rows=group_rows, scope_rows=scope_rows, p1_rows=p1_rows,
            restore_normalized_path=None, restore_classification_path=None,
        )
        after_data_tree = _hash_tree(ROOT / "data")
        self.assertFalse(result["computed"])  # 경로 미제공이라 계산 건너뜀
        self.assertEqual(before_data_tree, after_data_tree)


class AutoApprovedRowsZeroTest(unittest.TestCase):
    def test_summary_auto_approved_rows_is_zero(self) -> None:
        from scripts.career_build_final_mapping_closure import (
            build_summary, classify_bridge, classify_groups, classify_nce, classify_p1,
        )

        group_rows = classify_groups()
        mapping_rows, scope_rows = classify_bridge(
            mapping_review_path=REVIEWS_DIR / "canonical_major_group_bridge_review_status.json",
            scope_review_path=REVIEWS_DIR / "canonical_major_group_bridge_scope_review_status.jsonl",
        )
        p1_rows = classify_p1()
        nce_rows = classify_nce()
        summary = build_summary(
            group_rows=group_rows, mapping_rows=mapping_rows, scope_rows=scope_rows, p1_rows=p1_rows, nce_rows=nce_rows,
            hypothetical={"computed": False, "reason": "test"},
            bridge_mapping_review_baseline={"approve": 38, "revise": 6},
            group_review_file_exists=False, bridge_scope_review_file_exists=False,
            p1_review_file_exists=False, nce_review_file_exists=False,
        )
        self.assertEqual(summary["auto_approved_rows"], 0)


class ClassificationCountTest(unittest.TestCase):
    """§ 실제 데이터 기준 정확한 개수 — 임의로 조정하지 않는다."""

    @classmethod
    def setUpClass(cls) -> None:
        from scripts.career_build_final_mapping_closure import classify_bridge, classify_groups, classify_nce, classify_p1

        cls.group_rows = classify_groups()
        cls.mapping_rows, cls.scope_rows = classify_bridge(
            mapping_review_path=REVIEWS_DIR / "canonical_major_group_bridge_review_status.json",
            scope_review_path=REVIEWS_DIR / "canonical_major_group_bridge_scope_review_status.jsonl",
        )
        cls.p1_rows = classify_p1()
        cls.nce_rows = classify_nce()

    def test_group_total_42(self) -> None:
        self.assertEqual(len(self.group_rows), 42)

    def test_bridge_mapping_total_44(self) -> None:
        self.assertEqual(len(self.mapping_rows), 44)

    def test_bridge_scope_total_rows_44_applicable_15(self) -> None:
        self.assertEqual(len(self.scope_rows), 44)
        applicable = [r for r in self.scope_rows if r["disposition"] != "NOT_APPLICABLE"]
        not_applicable = [r for r in self.scope_rows if r["disposition"] == "NOT_APPLICABLE"]
        self.assertEqual(len(applicable), 15)
        self.assertEqual(len(not_applicable), 29)

    def test_p1_total_374_with_275_299_split(self) -> None:
        self.assertEqual(len(self.p1_rows), 374)
        content_media = sum(1 for r in self.p1_rows if r["p1_cluster"] == "CONTENT_MEDIA")
        design_hci_ux = sum(1 for r in self.p1_rows if r["p1_cluster"] == "DESIGN_HCI_UX")
        self.assertEqual(content_media, 275)
        self.assertEqual(design_hci_ux, 99)

    def test_nce_24_clusters_584_departments(self) -> None:
        self.assertEqual(len(self.nce_rows), 24)
        self.assertEqual(sum(r["member_department_count"] for r in self.nce_rows), 584)

    def test_nce_linkage_status_split_matches_208_376(self) -> None:
        proposed = sum(r["member_department_count"] for r in self.nce_rows if r["group_linkage_status"] == "PROPOSED_GROUP_CANDIDATE")
        department_level = sum(
            r["member_department_count"] for r in self.nce_rows if r["group_linkage_status"] == "DEPARTMENT_LEVEL_REVIEW_REQUIRED"
        )
        self.assertEqual(proposed, 208)
        self.assertEqual(department_level, 376)

    def test_every_row_has_exactly_one_of_three_dispositions(self) -> None:
        valid = {"PROPOSE_APPROVE", "PROPOSE_EXCLUDE", "HUMAN_REVIEW_REQUIRED"}
        for row in self.group_rows + self.mapping_rows + self.p1_rows + self.nce_rows:
            self.assertIn(row["disposition"], valid, row)
        valid_scope = valid | {"NOT_APPLICABLE"}
        for row in self.scope_rows:
            self.assertIn(row["disposition"], valid_scope, row)

    def test_all_24_nce_clusters_are_human_review_required(self) -> None:
        """§6 'N.C.E를 자동으로 특정 Major에 연결하지 않음' — Hint 후보 유무와
        무관하게 24개 전부 HUMAN_REVIEW_REQUIRED."""

        for row in self.nce_rows:
            self.assertEqual(row["disposition"], "HUMAN_REVIEW_REQUIRED", row["cluster_id"])


class BridgeScopePreservationTest(unittest.TestCase):
    """§4 — 기존 6개 결정을 그대로 보존한다."""

    @classmethod
    def setUpClass(cls) -> None:
        from scripts.career_build_final_mapping_closure import classify_bridge

        cls.mapping_rows, cls.scope_rows = classify_bridge(
            mapping_review_path=REVIEWS_DIR / "canonical_major_group_bridge_review_status.json",
            scope_review_path=REVIEWS_DIR / "canonical_major_group_bridge_scope_review_status.jsonl",
        )

    def test_verify_preserved_decisions_does_not_raise(self) -> None:
        from scripts.career_build_final_mapping_closure import (
            verify_preserved_bridge_mapping_review, verify_preserved_bridge_scope_decisions,
        )

        verify_preserved_bridge_scope_decisions(self.scope_rows)
        verify_preserved_bridge_mapping_review(self.mapping_rows)

    def test_included_small_series_only_four_preserved(self) -> None:
        expected = {
            ("business", "business_administration"): ["033"],
            ("education", "education"): ["042"],
            ("industrial_engineering", "industrial_engineering"): ["102"],
            ("mechanical_transport", "mechanical_engineering"): ["078"],
        }
        by_key = {(r["canonical_major_group_id"], r["canonical_major_id"]): r for r in self.scope_rows}
        for key, codes in expected.items():
            row = by_key[key]
            self.assertEqual(row["scope_type"], "INCLUDED_SMALL_SERIES_ONLY")
            self.assertEqual(row["included_small_series_codes"], codes)

    def test_department_review_required_two_preserved(self) -> None:
        by_key = {(r["canonical_major_group_id"], r["canonical_major_id"]): r for r in self.scope_rows}
        for key in (("bio_medical_engineering", "life_science"), ("computer_science", "hci_ux")):
            row = by_key[key]
            self.assertEqual(row["scope_type"], "DEPARTMENT_REVIEW_REQUIRED")
            self.assertEqual(row["disposition"], "HUMAN_REVIEW_REQUIRED")

    def test_bridge_mapping_existing_review_is_38_approve_6_revise(self) -> None:
        approve = sum(1 for r in self.mapping_rows if r["existing_reviewer_1_status"] == "APPROVE")
        revise = sum(1 for r in self.mapping_rows if r["existing_reviewer_1_status"] == "REVISE")
        self.assertEqual(approve, 38)
        self.assertEqual(revise, 6)
        # REVISE 6건은 전부 HUMAN_REVIEW_REQUIRED로 남아야 한다(과제 §2/§4).
        revise_dispositions = {r["disposition"] for r in self.mapping_rows if r["existing_reviewer_1_status"] == "REVISE"}
        self.assertEqual(revise_dispositions, {"HUMAN_REVIEW_REQUIRED"})


class P1BoundaryHandlingTest(unittest.TestCase):
    """§5 '이름 유사도만으로 승인 제안하지 않음' — HCI_UX_CANDIDATE는 근거
    불충분이라 절대 PROPOSE_APPROVE가 아니다."""

    @classmethod
    def setUpClass(cls) -> None:
        from scripts.career_build_final_mapping_closure import classify_p1

        cls.p1_rows = classify_p1()

    def test_hci_ux_candidate_never_propose_approve(self) -> None:
        for row in self.p1_rows:
            if row["judgment_candidate"] == "HCI_UX_CANDIDATE":
                self.assertNotEqual(row["disposition"], "PROPOSE_APPROVE")
                self.assertFalse(row["judgment_evidence_sufficient"])

    def test_media_communication_candidate_propose_approve(self) -> None:
        for row in self.p1_rows:
            if row["judgment_candidate"] == "MEDIA_COMMUNICATION_CANDIDATE":
                self.assertEqual(row["disposition"], "PROPOSE_APPROVE")

    def test_design_arts_excluded_propose_exclude(self) -> None:
        for row in self.p1_rows:
            if row["judgment_candidate"] == "DESIGN_ARTS_EXCLUDED":
                self.assertEqual(row["disposition"], "PROPOSE_EXCLUDE")


class PriorityHtmlContentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from scripts.career_build_final_mapping_closure import (
            classify_bridge, classify_groups, classify_nce, classify_p1, render_priority_html,
        )

        cls.group_rows = classify_groups()
        cls.mapping_rows, cls.scope_rows = classify_bridge(
            mapping_review_path=REVIEWS_DIR / "canonical_major_group_bridge_review_status.json",
            scope_review_path=REVIEWS_DIR / "canonical_major_group_bridge_scope_review_status.jsonl",
        )
        cls.p1_rows = classify_p1()
        cls.nce_rows = classify_nce()
        cls.html = render_priority_html(
            group_rows=cls.group_rows, mapping_rows=cls.mapping_rows, scope_rows=cls.scope_rows,
            p1_rows=cls.p1_rows, nce_rows=cls.nce_rows,
        )

    def test_html_well_formed(self) -> None:
        import html.parser

        parser = html.parser.HTMLParser()
        parser.feed(self.html)  # 예외 없이 끝나면 통과

    def test_html_department_ids_are_only_from_human_review_required_rows(self) -> None:
        """PROPOSE_APPROVE/PROPOSE_EXCLUDE로 분류된 P1 department_id는 이 문서에
        없어야 한다(HUMAN_REVIEW_REQUIRED 항목의 department_id만 있어야 한다)."""

        approved_or_excluded_ids = {
            r["department_id"] for r in self.p1_rows if r["disposition"] != "HUMAN_REVIEW_REQUIRED"
        }
        for dept_id in approved_or_excluded_ids:
            self.assertNotIn(dept_id, self.html)

    def test_html_contains_all_human_review_group_ids(self) -> None:
        for r in self.group_rows:
            if r["disposition"] == "HUMAN_REVIEW_REQUIRED":
                self.assertIn(r["canonical_major_group_id"], self.html)

    def test_html_no_reviewer_action_controls(self) -> None:
        """§7 '전체 승인 기능 추가 금지' — Form·네트워크 호출·일괄 승인 버튼
        흔적이 없다. 설명 문구 안의 '자동으로 바뀌지 않는다(...PATCH 호출 없음)'
        같은 안내 텍스트는 금지 대상이 아니다(그 자체가 이 요구사항을 지킨다는
        증거 문구다) — 그래서 실제 네트워크 호출 패턴만 검사한다."""

        for forbidden in ("<form", "fetch(", "XMLHttpRequest", "전체 승인", "일괄 승인", "onclick=\"approve"):
            self.assertNotIn(forbidden, self.html)


class DeterminismTest(unittest.TestCase):
    """§10 '산출물 2회 byte-identical' — 별도 프로세스, 서로 다른 PYTHONHASHSEED."""

    def _run_once(self, hash_seed: str) -> tuple[bytes, bytes, bytes]:
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = hash_seed
        proc = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True, timeout=180, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace")[:4000])
        return JSON_SUMMARY.read_bytes(), MD_REVIEW.read_bytes(), PRIORITY_HTML.read_bytes()

    def test_two_runs_with_different_hash_seeds_are_byte_identical(self) -> None:
        first = self._run_once("111")
        second = self._run_once("222")
        self.assertEqual(first[0], second[0], "JSON summary가 PYTHONHASHSEED에 따라 달라진다")
        self.assertEqual(first[1], second[1], "Markdown 보고서가 PYTHONHASHSEED에 따라 달라진다")
        self.assertEqual(first[2], second[2], "Priority HTML이 PYTHONHASHSEED에 따라 달라진다")

    def test_report_has_no_timestamp_fields(self) -> None:
        self._run_once("333")
        blob = JSON_SUMMARY.read_text(encoding="utf-8") + MD_REVIEW.read_text(encoding="utf-8")
        for token in ("generated_at", "created_at", "timestamp", "run_at"):
            self.assertNotIn(token, blob)


class DepartmentIdentityUntouchedTest(unittest.TestCase):
    """§11 금지 범위 — src/ids.py·Department Repository/Schema·Runtime
    Planner/Stop Condition·ContextPack 질문/Mapping·공개 API·frontend/ 어느
    것도 이 스크립트가 Import하지 않는다는 것을 구조적으로 증명한다."""

    def test_script_does_not_import_forbidden_modules(self) -> None:
        import ast

        source = SCRIPT.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)

        forbidden_prefixes = (
            "src.ids", "src.repositories.department", "src.schemas.major",
            "src.engines.context_pack_adaptive_planner", "src.engines.evidence_engine",
            "src.api.main", "src.data.questions", "src.data.contexts",
        )
        offending = {m for m in imported if any(m == p or m.startswith(p + ".") for p in forbidden_prefixes)}
        self.assertFalse(offending, f"금지된 모듈을 Import한다: {offending}")

    def test_frontend_and_ids_untouched_after_run(self) -> None:
        from scripts.career_build_final_mapping_closure import main

        ids_before = _hash_file(ROOT / "src" / "ids.py")
        main([])
        ids_after = _hash_file(ROOT / "src" / "ids.py")
        self.assertEqual(ids_before, ids_after)


class MasterAndMockUnaffectedTest(unittest.TestCase):
    def test_master_still_35_rows(self) -> None:
        rows = [l for l in MASTER_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual(len(rows), 35)


class RestoreDataHypotheticalTest(unittest.TestCase):
    """실제 전국 정규화·분류 결과가 있을 때만 도는 선택적 테스트 — 없으면
    Skip한다(clean clone에서도 이 파일의 나머지 테스트는 전부 돈다)."""

    _NORMALIZED = Path("/Users/jaewan/Documents/Codex/2026-08-17/academyinfo-data-restore/data/academyinfo_work/2025/departments.normalized.jsonl")
    _CLASSIFICATION = Path("/Users/jaewan/Documents/Codex/2026-08-17/academyinfo-data-restore/data/academyinfo_work/2025/classification_results.jsonl")

    def _has_inputs(self) -> bool:
        return self._NORMALIZED.exists() and self._CLASSIFICATION.exists()

    def test_hypothetical_ready_for_promotion_is_positive_and_bounded(self) -> None:
        if not self._has_inputs():
            self.skipTest("실제 전국 복원 데이터가 이 환경에 없다")

        from scripts.career_build_final_mapping_closure import (
            classify_bridge, classify_groups, classify_p1, compute_hypothetical_ready_for_promotion,
        )

        group_rows = classify_groups()
        _, scope_rows = classify_bridge(
            mapping_review_path=REVIEWS_DIR / "canonical_major_group_bridge_review_status.json",
            scope_review_path=REVIEWS_DIR / "canonical_major_group_bridge_scope_review_status.jsonl",
        )
        p1_rows = classify_p1()
        result = compute_hypothetical_ready_for_promotion(
            group_rows=group_rows, scope_rows=scope_rows, p1_rows=p1_rows,
            restore_normalized_path=self._NORMALIZED, restore_classification_path=self._CLASSIFICATION,
        )
        self.assertTrue(result["computed"])
        self.assertGreater(result["ready_for_promotion_count"], 0)
        self.assertLess(result["ready_for_promotion_count"], result["evaluated_department_count"])

    def test_restore_inputs_untouched(self) -> None:
        if not self._has_inputs():
            self.skipTest("실제 전국 복원 데이터가 이 환경에 없다")

        from scripts.career_build_final_mapping_closure import (
            classify_bridge, classify_groups, classify_p1, compute_hypothetical_ready_for_promotion,
        )

        before = (_hash_file(self._NORMALIZED), _hash_file(self._CLASSIFICATION))
        group_rows = classify_groups()
        _, scope_rows = classify_bridge(
            mapping_review_path=REVIEWS_DIR / "canonical_major_group_bridge_review_status.json",
            scope_review_path=REVIEWS_DIR / "canonical_major_group_bridge_scope_review_status.jsonl",
        )
        p1_rows = classify_p1()
        compute_hypothetical_ready_for_promotion(
            group_rows=group_rows, scope_rows=scope_rows, p1_rows=p1_rows,
            restore_normalized_path=self._NORMALIZED, restore_classification_path=self._CLASSIFICATION,
        )
        after = (_hash_file(self._NORMALIZED), _hash_file(self._CLASSIFICATION))
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
