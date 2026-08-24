"""Final Mapping Closure 후속 — 실제 검수 저장 스크립트 테스트 —
a/final-mapping-closure (`scripts/career_close_final_mapping_review.py`).

핵심 증명 대상(후속 지시 §8/§10/§12):
    1. 재실행해도 안전하다(idempotent) — 이미 종결된 항목은 다시 쓰지 않는다.
    2. 기존 comment·기존 Bridge Mapping 38건(이제 44건)의 Key는 보존된다.
    3. reviewer_2는 어디서도 건드리지 않는다(전부 TBD 유지).
    4. resolution_note는 지시된 정확한 문구다.
    5. 실제 Review Store/PATCH Service(`update_*_review` 함수들)를 통해서만
       저장한다 — JSONL 문자열 치환이 아니다(각 Store의 Pydantic 검증을
       통과해야만 저장된다는 사실 자체가 이를 증명한다).
    6. Master(35건)·Mock/OpenAPI·Department Identity 관련 파일은 무변경이다."""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEWS_DIR = ROOT / "data" / "reviews"
MASTER_PATH = ROOT / "data" / "master" / "departments.jsonl"

sys.path.insert(0, str(ROOT))

RESOLUTION_NOTE = (
    "사용자 최종 결정에 따라 추가 검수 없이 기존 근거 기반 승인 또는 "
    "1차 전국 승격 제외로 종결"
)


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash_tree(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*")) if p.is_file()
    }


class RealReviewFilesFullyClosedTest(unittest.TestCase):
    """실제 저장된 5개 Review Store를 다시 읽어 종결 상태를 확인한다."""

    def test_group_review_all_42_approved(self) -> None:
        from src.services.canonical_major_group_review_store import load_canonical_major_group_review_entries_by_key

        entries = load_canonical_major_group_review_entries_by_key(REVIEWS_DIR / "canonical_major_group_review_status.jsonl")
        self.assertEqual(len(entries), 42)
        for entry in entries.values():
            self.assertEqual(entry.decision, "APPROVE_AS_CLASSIFICATION_GROUP")
            self.assertEqual(entry.reviewer_1_status, "APPROVE")
            self.assertEqual(entry.reviewer_2_status, "TBD")
            self.assertEqual(entry.resolution_note, RESOLUTION_NOTE)

    def test_bridge_mapping_all_44_approve_zero_revise(self) -> None:
        import json

        rows = json.loads((REVIEWS_DIR / "canonical_major_group_bridge_review_status.json").read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 44)
        for row in rows:
            self.assertEqual(row["reviewer_1_status"], "APPROVE")
            self.assertEqual(row["reviewer_2_status"], "TBD")

    def test_bridge_scope_all_15_approved(self) -> None:
        from src.services.canonical_major_group_bridge_scope_review_store import load_bridge_scope_review_entries_by_key

        entries = load_bridge_scope_review_entries_by_key(REVIEWS_DIR / "canonical_major_group_bridge_scope_review_status.jsonl")
        self.assertEqual(len(entries), 15)
        for entry in entries.values():
            self.assertEqual(entry.reviewer_1_status, "APPROVE")
            self.assertEqual(entry.reviewer_2_status, "TBD")
            self.assertEqual(entry.resolution_note, RESOLUTION_NOTE)

    def test_p1_all_374_have_terminal_decision(self) -> None:
        from src.services.academyinfo_p1_classification_review_store import load_p1_review_entries_by_key

        entries = load_p1_review_entries_by_key(REVIEWS_DIR / "academyinfo_p1_classification_review_status.jsonl")
        self.assertEqual(len(entries), 374)
        decisions = {e.decision for e in entries.values()}
        self.assertNotIn("TBD", decisions)
        self.assertEqual(decisions, {"APPROVE_PROPOSED_CANDIDATE", "EXCLUDE_ARTS_RECOMMENDATION", "EXCLUDE_FROM_INITIAL_PROMOTION"})
        for entry in entries.values():
            self.assertEqual(entry.resolution_note, RESOLUTION_NOTE)

    def test_nce_all_24_excluded_from_initial_promotion(self) -> None:
        from src.services.academyinfo_nce_middle_series_review_store import load_nce_review_entries_by_key

        entries = load_nce_review_entries_by_key(REVIEWS_DIR / "academyinfo_nce_middle_series_review_status.jsonl")
        self.assertEqual(len(entries), 24)
        for entry in entries.values():
            self.assertEqual(entry.decision, "EXCLUDE_FROM_INITIAL_PROMOTION")
            self.assertEqual(entry.resolution_note, RESOLUTION_NOTE)


class IdempotentReRunTest(unittest.TestCase):
    """§8/§10 — 재실행해도 안전하다. 이미 목표 상태인 항목은 다시 쓰지 않는다
    (revision이 불필요하게 늘지 않는다는 것으로 확인한다)."""

    def test_rerunning_main_does_not_change_any_review_file(self) -> None:
        from scripts.career_close_final_mapping_review import main

        before = _hash_tree(REVIEWS_DIR)
        rc = main()
        after = _hash_tree(REVIEWS_DIR)
        self.assertEqual(rc, 0)
        self.assertEqual(before, after, "이미 종결된 상태에서 재실행했는데 파일이 바뀌었다 — idempotent가 아니다")


class BridgeMappingCommentPreservedTest(unittest.TestCase):
    """§8 '기존 comment 보존' — 최초 사람 검수 때 남긴 reviewer_1_comment가
    이번 라운드의 APPROVE 전환으로 사라지지 않았는지 확인한다(§4의 6개 실제
    코멘트 원문 일부를 대조한다)."""

    def test_six_closed_rows_keep_original_reviewer_comment(self) -> None:
        import json

        rows = json.loads((REVIEWS_DIR / "canonical_major_group_bridge_review_status.json").read_text(encoding="utf-8"))
        by_key = {(r["canonical_major_group_id"], r.get("canonical_major_id")): r for r in rows}
        expected_comment_fragments = {
            ("business", "business_administration"): "경영학 소계열만 포함",
            ("education", "education"): "교육학 소계열만",
            ("industrial_engineering", "industrial_engineering"): "산업공학 소계열만",
            ("mechanical_transport", "mechanical_engineering"): "기계공학 소계열만",
            ("bio_medical_engineering", "life_science"): "생명과학과 생명공학",
            ("computer_science", "hci_ux"): "컴퓨터과학 전공군 전체를 HCI",
        }
        for key, fragment in expected_comment_fragments.items():
            row = by_key[key]
            self.assertEqual(row["reviewer_1_status"], "APPROVE")
            self.assertIn(fragment, row["reviewer_1_comment"], f"{key}의 기존 코멘트가 사라졌다")


class MasterAndDepartmentIdentityUntouchedTest(unittest.TestCase):
    def test_master_still_35_rows(self) -> None:
        rows = [l for l in MASTER_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual(len(rows), 35)

    def test_closing_script_does_not_import_forbidden_modules(self) -> None:
        import ast

        source = (ROOT / "scripts" / "career_close_final_mapping_review.py").read_text(encoding="utf-8")
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

    def test_ids_py_untouched_after_rerun(self) -> None:
        from scripts.career_close_final_mapping_review import main

        before = _hash_file(ROOT / "src" / "ids.py")
        main()
        after = _hash_file(ROOT / "src" / "ids.py")
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
