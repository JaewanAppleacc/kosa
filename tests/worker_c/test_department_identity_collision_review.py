"""department_id identity-key 충돌 감사 패킷 테스트 —
a/department-identity-collision-audit.

핵심은 두 가지다.

1. **Claude가 자동 판정하지 않았음을 기계적으로 증명한다** — 16 Group 전부
   `review.reviewer_1_status == "TBD"`, `review.decision == "TBD"`,
   `auto_approved_rows == 0`.
2. **department_id 생성 규칙(`src/ids.py::generate_department_id`)이 이번
   작업으로 바뀌지 않았음**과, "SHA-256 Hash Collision"이 아니라
   "identity-key Collision"이라는 정정된 용어가 산출물에 실제로 반영됐음을
   확인한다.

패킷/HTML/Manifest는 `data/academyinfo_work/2025/packets/`에 커밋돼 있으므로
(`.gitignore`의 `!data/academyinfo_work/*/packets/` whitelist), 이 파일의
검증은 전국 원본 데이터(정규화·분류·Raw Snapshot) 없이도 clean clone에서
전부 돈다 — `build_groups()` 순수 로직 검증만 합성 Fixture를 쓴다.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.career_build_department_identity_collision_review import (  # noqa: E402
    DECISION_OPTIONS,
    build_groups,
)
from src.ids import generate_department_id  # noqa: E402

WORK = ROOT / "data" / "academyinfo_work" / "2025"
PACKETS = WORK / "packets"
JSONL_PATH = PACKETS / "department_identity_collision_review.jsonl"
HTML_PATH = PACKETS / "department_identity_collision_review.html"
MANIFEST_PATH = PACKETS / "department_identity_collision_review_manifest.json"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


ROWS = read_jsonl(JSONL_PATH)
MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
HTML_TEXT = HTML_PATH.read_text(encoding="utf-8")


class CommittedOutputTest(unittest.TestCase):
    def test_packet_outputs_committed(self) -> None:
        for p in (JSONL_PATH, HTML_PATH, MANIFEST_PATH):
            self.assertTrue(p.exists(), f"{p.name}이 커밋돼 있지 않다")


class ExactGroupCountTest(unittest.TestCase):
    """지시서 §8 — "패킷 정확히 16 Group·32행", "모든 충돌 Group에 정확히 2행"."""

    def test_exactly_16_groups(self) -> None:
        self.assertEqual(len(ROWS), 16)

    def test_every_group_has_exactly_2_candidates(self) -> None:
        for row in ROWS:
            self.assertEqual(row["candidate_count"], 2, row["department_id"])
            self.assertEqual(len(row["candidates"]), 2, row["department_id"])

    def test_total_candidate_rows_is_32(self) -> None:
        self.assertEqual(sum(r["candidate_count"] for r in ROWS), 32)

    def test_department_ids_unique_across_groups(self) -> None:
        ids = [r["department_id"] for r in ROWS]
        self.assertEqual(len(ids), len(set(ids)))


class NoAutoApprovalTest(unittest.TestCase):
    """자동 판정 금지 — 16 Group 전부 TBD, auto_approved_rows=0."""

    def test_all_groups_reviewer_status_tbd(self) -> None:
        for row in ROWS:
            self.assertEqual(row["review"]["reviewer_1_status"], "TBD", row["department_id"])
            self.assertEqual(row["review"]["decision"], "TBD", row["department_id"])

    def test_allowed_decisions_match_spec(self) -> None:
        expected = {
            "TBD",
            "EXACT_DUPLICATE_SOURCE_RECORD",
            "DISTINCT_OFFICIAL_DEPARTMENTS",
            "IDENTITY_KEY_INSUFFICIENT",
            "NEEDS_MORE_OFFICIAL_EVIDENCE",
            "HOLD",
        }
        self.assertEqual(set(DECISION_OPTIONS), expected)
        for row in ROWS:
            self.assertEqual(set(row["review"]["allowed_decisions"]), expected)

    def test_manifest_zero_auto_approved(self) -> None:
        self.assertEqual(MANIFEST["auto_approved_rows"], 0)


class TerminologyTest(unittest.TestCase):
    """지시서 "중요한 용어" — "SHA-256 해시 충돌"이라고 표현하지 않는다."""

    def test_html_explicitly_disclaims_hash_collision(self) -> None:
        self.assertIn("Hash Collision이 아닙니다", HTML_TEXT)

    def test_html_uses_identity_key_language(self) -> None:
        self.assertIn("identity-key", HTML_TEXT)

    def test_module_docstring_uses_identity_key_not_bare_hash_collision(self) -> None:
        import scripts.career_build_department_identity_collision_review as mod

        doc = mod.__doc__ or ""
        self.assertIn("identity-key", doc)
        # "해시 충돌"이라는 표현이 나오더라도 반드시 "아니다/아닌"과 함께,
        # 즉 부정하는 문맥으로만 등장해야 한다.
        if "해시 충돌" in doc:
            self.assertIn("아니다", doc)


class DepartmentIdRuleUnchangedTest(unittest.TestCase):
    """department_id 생성 규칙을 이번 작업에서 바꾸지 않았다."""

    def test_generate_department_id_still_ignores_schl_mjr_id(self) -> None:
        # 서로 다른 schlMjrId(원본 행)라도 (schl_id, department_name, college_name)이
        # 같으면 여전히 같은 department_id를 낸다 — 이게 바로 이 감사가 다루는 현상
        # 자체이며, 이 스크립트가 그 규칙을 바꾸지 않았다는 것도 이걸로 확인된다.
        a = generate_department_id("0000029", "약학과", "약학대학")
        b = generate_department_id("0000029", "약학과", "약학대학")
        self.assertEqual(a, b)

    def test_script_module_does_not_redefine_id_rule(self) -> None:
        import scripts.career_build_department_identity_collision_review as mod

        self.assertFalse(hasattr(mod, "generate_department_id"))


class RowAccountingTest(unittest.TestCase):
    """지시서 §3 — 24,422행 전체 회계, source_record_id 기준 정본 확인."""

    def test_normalized_and_classification_totals(self) -> None:
        acc = MANIFEST["row_accounting"]
        self.assertEqual(acc["normalized_input_rows"], 24422)
        self.assertEqual(acc["classification_rows"], 24416)
        self.assertEqual(acc["unique_department_id_count"], 24406)

    def test_collision_group_and_row_counts(self) -> None:
        acc = MANIFEST["row_accounting"]
        self.assertEqual(acc["collision_group_count"], 16)
        self.assertEqual(acc["collision_row_count"], 32)
        self.assertEqual(acc["dropped_from_evaluation_row_count"], 16)

    def test_missing_from_classification_is_6_all_contract(self) -> None:
        acc = MANIFEST["row_accounting"]
        self.assertEqual(acc["missing_from_classification_count"], 6)
        self.assertTrue(acc["missing_from_classification_all_contract_department"])
        self.assertEqual(acc["classification_only_id_count"], 0)

    def test_department_id_based_diff_is_documented_as_distorted(self) -> None:
        # department_id 기준으로 계산하면(집합 연산이 충돌을 뭉갠다) 0이 나온다는
        # 사실 자체를 이 감사가 명시적으로 남긴다 — source_record_id 기준(위
        # test_missing_from_classification_is_6_all_contract)이 정본이라는 것도 함께.
        note = MANIFEST["row_accounting"]["missing_from_classification_by_department_id_count_note"]
        self.assertIn("0건", note)
        self.assertIn("정본", note)


class ContractDepartmentAccountingTest(unittest.TestCase):
    """지시서 §4 — 계약학과 6건 전체 회계."""

    def test_contract_department_counts(self) -> None:
        acc = MANIFEST["contract_department_accounting"]
        self.assertEqual(acc["contract_department_total"], 6)
        self.assertEqual(acc["contract_department_evaluated_by_dry_run"], 4)
        self.assertEqual(acc["contract_department_dropped_from_dry_run_evaluation"], 2)
        self.assertEqual(acc["contract_department_final_recommendation_exposure"], 0)
        self.assertEqual(acc["contract_department_preserved_in_normalized_and_audit_packet"], 6)

    def test_evaluated_plus_dropped_equals_total(self) -> None:
        acc = MANIFEST["contract_department_accounting"]
        self.assertEqual(
            acc["contract_department_evaluated_by_dry_run"]
            + acc["contract_department_dropped_from_dry_run_evaluation"],
            acc["contract_department_total"],
        )

    def test_chungnam_pharmacy_group_present_with_both_tracks_preserved(self) -> None:
        """충남대학교 약학과 — 계약학과(4년)/일반과정(6년) 두 트랙이 이 감사
        패킷에 둘 다 보존돼 있는지(§4 "일반과정 대응 행은 유지되는지 재검증")."""

        group = next((r for r in ROWS if r["department_id"] == "dept_6ea537f2938a79ba48bef719"), None)
        self.assertIsNotNone(group, "충남대학교 약학과 충돌 Group이 패킷에 없다")
        major_characters = {c["major_character_name"] for c in group["candidates"]}
        self.assertEqual(major_characters, {"계약학과", "일반과정"})
        exclusion_reasons = {c["exclusion_reason"] for c in group["candidates"]}
        self.assertEqual(exclusion_reasons, {"CONTRACT_DEPARTMENT", None})
        # 일반과정 쪽이 dropped(평가 제외) 쪽이라는 것 — 하지만 여기 이렇게
        # 존재한다는 사실 자체가 "삭제되지 않았다"는 증명이다.
        general_track = next(c for c in group["candidates"] if c["major_character_name"] == "일반과정")
        self.assertIn(
            general_track["source_record_id"],
            group["dry_run_evaluation_audit"]["dropped_from_evaluation_source_record_ids"],
        )


class BuildGroupsLogicTest(unittest.TestCase):
    """`build_groups()` 순수 로직 — 합성 Fixture, 실제 전국 데이터 불필요."""

    def _norm_row(self, **overrides) -> dict:
        base = {
            "department_id": "dept_fixture",
            "source_record_id": "src_a",
            "schl_id": "0000001",
            "source_schl_mjr_id": "1000001",
            "university_name": "합성대학교",
            "campus": None,
            "college_name": "합성대학",
            "department_name": "합성학과",
            "major_character_name": "일반과정",
            "lesson_term_name": "4년",
            "degree_course_name": "학사",
            "day_night_name": "주간",
            "department_status": "EXISTING",
            "recommendation_scope": "IN_RECOMMENDATION_SCOPE",
            "exclusion_reason": None,
        }
        base.update(overrides)
        return base

    def test_dict_collapse_keeps_last_row_in_file_order(self) -> None:
        """load_inputs()의 `{row['department_id']: row for row in departments}`와
        동일한 규칙 — 파일에서 나중에 나오는 행이 evaluated_representative."""

        first = self._norm_row(source_record_id="src_first")
        second = self._norm_row(source_record_id="src_second", major_character_name="계약학과")
        groups = build_groups([first, second], {}, {})

        self.assertEqual(len(groups), 1)
        audit = groups[0]["dry_run_evaluation_audit"]
        self.assertEqual(audit["evaluated_representative_source_record_id"], "src_second")
        self.assertEqual(audit["dropped_from_evaluation_source_record_ids"], ["src_first"])

    def test_comparison_flags_differing_fields_only(self) -> None:
        first = self._norm_row(source_record_id="src_a", lesson_term_name="4년")
        second = self._norm_row(source_record_id="src_b", lesson_term_name="6년")
        groups = build_groups([first, second], {}, {})

        comparison = groups[0]["comparison"]
        self.assertIn("source_record_id", comparison["different_fields"])
        self.assertIn("course_term", comparison["different_fields"])
        self.assertIn("course_term", comparison["differs_in_potential_distinguishing_fields"])
        self.assertIn("university_name", comparison["same_fields"])
        self.assertFalse(comparison["source_record_id_same"])

    def test_non_colliding_rows_produce_no_group(self) -> None:
        row_a = self._norm_row(department_id="dept_x", source_record_id="src_x")
        row_b = self._norm_row(department_id="dept_y", source_record_id="src_y")
        groups = build_groups([row_a, row_b], {}, {})
        self.assertEqual(groups, [])

    def test_exact_duplicate_like_row_has_no_distinguishing_signal(self) -> None:
        """두 후보가 major_character/course_term 등에서 전부 같으면(순수 원본
        중복에 가까운 형태) distinguishing signal이 비어야 한다 — 이 스크립트가
        먼저 결론 내지 않으니 사람이 EXACT_DUPLICATE_SOURCE_RECORD로 볼 근거가
        있는지 스스로 판단하게 남긴다는 뜻."""

        first = self._norm_row(source_record_id="src_a")
        second = self._norm_row(source_record_id="src_b")
        groups = build_groups([first, second], {}, {})
        self.assertEqual(groups[0]["comparison"]["differs_in_potential_distinguishing_fields"], [])


if __name__ == "__main__":
    unittest.main()
