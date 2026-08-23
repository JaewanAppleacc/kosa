"""공식 소계열 → 대표 전공군 분류 테스트 — A 지시 §6·§7·§10."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.career_classify_academyinfo import (
    ELIGIBILITY_APPROVED,
    ELIGIBILITY_EXCLUDED,
    ELIGIBILITY_REVIEW,
    GROUPS_PATH,
    build_series_index,
    classify,
    read_jsonl,
)

GROUPS = read_jsonl(GROUPS_PATH)
INDEX = build_series_index(GROUPS)
EXCLUDED = set(GROUPS[0]["excluded_series_codes"]) if GROUPS else set()


def dept(small: str, large: str, name: str = "컴퓨터공학부", college: str = "공과대학", **over) -> dict:
    row = {
        "department_id": "d1",
        "source_record_id": "src_x",
        "university_name": "테스트대학교",
        "department_name": name,
        "college_name": college,
        "official_classification": {
            "small_series_code": small,
            "small_series_name": "테스트소계열",
            "large_series_code": large,
            "large_series_name": {"A": "인문사회계열", "B": "자연과학계열", "C": "예체능계열",
                                  "D": "공학계열", "E": "의학계열"}.get(large, ""),
            "self_series_name": None,
            "is_unclassified": small in ("", "999"),
        },
    }
    row.update(over)
    return row


def run(row: dict) -> dict:
    return classify(row, INDEX, EXCLUDED)


class GroupTableTest(unittest.TestCase):
    def test_group_count_is_within_target_range(self) -> None:
        """A 지시 §6-2: "약 20~40개".

        현재 42개다. 40을 2개 넘긴 이유는 실측 근거로 두 군을 분리했기 때문이다.

            무역·유통·관광 922 → 무역·유통 427 / 관광 417  (거의 반반, 진로가 갈린다)
            생활과학      670 → 식품 520 / 의류·주거 150

        되돌려 합칠 후보는 치의학 11·한의학 13·수의학 17뿐인데, 이들은 "진로가 완전히
        다르다"는 이유로 분리한 것이라 합치면 분리 근거가 무너진다. 상한을 지키려고
        더 나쁜 묶음을 만들지 않는다 — 초과 사실은 보고서에 명시해 A 판단에 맡긴다.
        """
        self.assertGreaterEqual(len(GROUPS), 20)
        self.assertLessEqual(len(GROUPS), 42, "42를 넘기면 상한 초과 근거를 다시 써야 한다")

    def test_every_group_is_draft(self) -> None:
        """사람 검토 없이 CONFIRMED로 승격하지 않는다 (A 지시 §6-2)."""
        self.assertTrue(all(g["review_status"] == "draft" for g in GROUPS))

    def test_no_small_series_assigned_to_two_groups(self) -> None:
        """한 소계열이 두 전공군에 들어가면 학과가 매번 REVIEW_REQUIRED가 된다."""
        seen: dict[str, str] = {}
        for g in GROUPS:
            for code in g["included_official_small_series_codes"]:
                self.assertNotIn(code, seen, f"소계열 {code}가 {seen.get(code)}와 중복 배정")
                seen[code] = g["canonical_major_id"]

    def test_general_education_series_are_excluded(self) -> None:
        """교양 소계열은 전공이 아니다 — 학부대학 교양과정 단위다."""
        assigned = {c for g in GROUPS for c in g["included_official_small_series_codes"]}
        for code in ("012", "018", "032", "071", "106"):
            self.assertNotIn(code, assigned)

    def test_labels_are_student_facing_not_code_names(self) -> None:
        """공식 소계열 코드를 그대로 라벨로 쓰면 학생이 못 읽는다."""
        for g in GROUPS:
            self.assertFalse(g["label"].strip().isdigit())
            self.assertNotIn("N.C.E", g["label"])


class MappingTest(unittest.TestCase):
    def test_single_series_becomes_auto_candidate_not_confirmed(self) -> None:
        """자동 확정이 아니라 후보다 — 이름부터 CONFIRMED가 아니어야 한다."""
        r = run(dept("090", "D"))
        self.assertEqual(r["mapping_status"], "AUTO_CANDIDATE")
        self.assertEqual(r["candidate_canonical_major_ids"], ["computer_science"])
        self.assertEqual(r["review_status"], "draft")
        self.assertNotEqual(r["mapping_status"], "CONFIRMED")

    def test_computer_series_all_land_in_one_group(self) -> None:
        """서울대 컴퓨터공학부·연세대 컴퓨터과학과·고려대 컴퓨터학과가 한 전공군으로 묶여야 한다."""
        for code in ("089", "090", "157"):
            self.assertEqual(run(dept(code, "D"))["candidate_canonical_major_ids"], ["computer_science"])

    def test_nce_is_unmapped_not_a_major(self) -> None:
        """미분류 Sentinel을 전공으로 만들지 않는다 (A 지시 §6-1)."""
        r = run(dept("999", "A"))
        self.assertEqual(r["mapping_status"], "UNMAPPED")
        self.assertEqual(r["candidate_canonical_major_ids"], [])

    def test_empty_series_is_unmapped(self) -> None:
        self.assertEqual(run(dept("", "A"))["mapping_status"], "UNMAPPED")

    def test_general_education_series_is_unmapped(self) -> None:
        r = run(dept("018", "A", name="교양과", college="학부대학"))
        self.assertEqual(r["mapping_status"], "UNMAPPED")
        self.assertIn("교양", r["decision_reason"])

    def test_unknown_series_is_unmapped_not_guessed(self) -> None:
        """모르는 코드를 아무 전공군에 밀어 넣지 않는다."""
        self.assertEqual(run(dept("777", "D"))["mapping_status"], "UNMAPPED")

    def test_decision_reason_is_always_recorded(self) -> None:
        for code in ("090", "999", "018", "777"):
            self.assertTrue(run(dept(code, "D"))["decision_reason"])


class EligibilityTest(unittest.TestCase):
    """A 지시 §7 — 예체능은 원본 보존, 추천만 제외."""

    def test_arts_large_series_is_excluded(self) -> None:
        r = run(dept("126", "C", name="회화과", college="예술대학"))
        self.assertEqual(r["eligibility_status"], ELIGIBILITY_EXCLUDED)

    def test_excluded_row_is_still_classified_and_kept(self) -> None:
        """추천에서 빼는 것이지 데이터에서 지우는 것이 아니다."""
        r = run(dept("126", "C", name="회화과", college="예술대학"))
        self.assertIsNotNone(r["department_id"])
        self.assertTrue(r["candidate_canonical_major_ids"])

    def test_engineering_is_approved(self) -> None:
        self.assertEqual(run(dept("090", "D"))["eligibility_status"], ELIGIBILITY_APPROVED)

    def test_design_name_alone_does_not_decide(self) -> None:
        """디자인·콘텐츠·미디어라는 이름만으로 확정하지 않는다 — Fail-Closed."""
        r = run(dept("090", "D", name="인터랙션디자인학과", college="소프트웨어융합대학"))
        self.assertEqual(r["eligibility_status"], ELIGIBILITY_REVIEW)

    def test_convergence_department_is_review_required(self) -> None:
        for name in ("융합콘텐츠학과", "미디어학부", "HCI학과", "자유전공학부"):
            self.assertEqual(
                run(dept("027", "A", name=name))["eligibility_status"],
                ELIGIBILITY_REVIEW,
                f"{name}은 공식 근거 확인 전까지 REVIEW_REQUIRED여야 한다",
            )

    def test_missing_large_series_is_review_not_approved(self) -> None:
        """판정 근거가 없으면 승인하지 않는다."""
        self.assertEqual(run(dept("090", ""))["eligibility_status"], ELIGIBILITY_REVIEW)

    def test_uses_existing_status_names(self) -> None:
        """기존 department_recommendation_scope 상태명을 그대로 쓴다 — 새 이름을 만들지 않는다."""
        self.assertEqual(ELIGIBILITY_APPROVED, "APPROVED")
        self.assertEqual(ELIGIBILITY_EXCLUDED, "EXCLUDED_ARTS_SPORTS")
        self.assertEqual(ELIGIBILITY_REVIEW, "REVIEW_REQUIRED")


if __name__ == "__main__":
    unittest.main()
