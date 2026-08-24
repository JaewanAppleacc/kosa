"""서비스 추천 범위 테스트 — A 결정(2026-08-24).

정책: 4~7년제 학사과정의 **주간 과정**만 Master 승격 후보다.
야간·원격·사이버대학은 원본·Lineage·Audit에 보존하되 승격·분류·추천에서 제외한다.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.data_sources.academyinfo_codes import (
    EXCLUDED_DISTANCE_UNIVERSITY,
    EXCLUDED_NIGHT_COURSE,
    EXCLUDED_UNKNOWN_DAY_NIGHT,
    is_distance_university,
    recommendation_scope_exclusion,
)
from scripts.career_normalize_academyinfo import normalize

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "data" / "academyinfo_work" / "2025"


def read_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


INCLUDED = read_jsonl(WORK / "departments.normalized.jsonl")
OUT_OF_SCOPE = read_jsonl(WORK / "out_of_recommendation_scope.jsonl")
DUPLICATE = read_jsonl(WORK / "duplicate_department_review_queue.jsonl")
CLASSIFICATION = read_jsonl(WORK / "classification_review_queue.jsonl")
NCE = read_jsonl(WORK / "unmapped_nce_queue.jsonl")


def row(**over) -> dict:
    base = {
        "schlKndCd": "03", "schlKndNm": "대학교",
        "pbnfDgriCrseDivCd": "3", "pbnfDgriCrseDivNm": "학사",
        "lsnTrmCd": "07", "dghtDivNm": "주간",
        "korSchlNm": "테스트대학교", "korMjrNm": "컴퓨터공학과",
    }
    base.update(over)
    return base


class DayNightScopeTest(unittest.TestCase):
    def test_day_course_is_included(self) -> None:
        self.assertIsNone(recommendation_scope_exclusion(row(dghtDivNm="주간")))

    def test_night_course_is_excluded_regardless_of_status(self) -> None:
        """야간은 EXISTING·NEW·ABOLISHED 어느 상태든 승격 후보에서 빠진다."""
        for status in ("기존", "신설", "폐지", "통합", "분리"):
            self.assertEqual(
                recommendation_scope_exclusion(row(dghtDivNm="야간", schlMjrStatNm=status)),
                EXCLUDED_NIGHT_COURSE,
                f"야간 + {status}가 제외되지 않았다",
            )

    def test_missing_day_night_is_not_assumed_to_be_day(self) -> None:
        """값이 없다고 주간으로 추정하지 않는다 (A 결정 §3)."""
        self.assertEqual(recommendation_scope_exclusion(row(dghtDivNm="")), EXCLUDED_UNKNOWN_DAY_NIGHT)
        self.assertEqual(recommendation_scope_exclusion(row(dghtDivNm=None)), EXCLUDED_UNKNOWN_DAY_NIGHT)

    def test_third_value_is_excluded_and_distinguished_from_night(self) -> None:
        """'원격' 같은 제3의 값도 주간이 아니라 제외하되, 야간과 사유를 구분한다."""
        result = recommendation_scope_exclusion(row(dghtDivNm="원격"))
        self.assertEqual(result, EXCLUDED_UNKNOWN_DAY_NIGHT)
        self.assertNotEqual(result, EXCLUDED_NIGHT_COURSE)


class DistanceUniversityTest(unittest.TestCase):
    def test_official_cyber_university_kind_is_excluded(self) -> None:
        self.assertTrue(is_distance_university(row(schlKndCd="04", schlKndNm="사이버대학(대학)")))
        self.assertEqual(
            recommendation_scope_exclusion(row(schlKndCd="04", schlKndNm="사이버대학(대학)")),
            EXCLUDED_DISTANCE_UNIVERSITY,
        )

    def test_broadcast_university_is_excluded_by_kind_not_name(self) -> None:
        """한국방송통신대학교는 **학교종류 유형**으로 걸린다."""
        self.assertTrue(
            is_distance_university(row(schlKndNm="방송통신대학", korSchlNm="한국방송통신대학교"))
        )

    def test_regular_university_digital_department_is_not_excluded(self) -> None:
        """일반 대학의 컴퓨터·디지털·온라인 학과는 이름만으로 제외되지 않는다."""
        for name in ("디지털미디어학과", "온라인콘텐츠학과", "사이버보안학과",
                     "컴퓨터공학과", "원격탐사공학과"):
            r = row(korMjrNm=name)
            self.assertFalse(is_distance_university(r), f"{name}이 교명 신호로 잘못 걸렸다")
            self.assertIsNone(recommendation_scope_exclusion(r))

    def test_university_named_cyber_is_not_excluded_by_name_alone(self) -> None:
        """교명에 '사이버'가 들어가도 학교종류가 일반 대학교면 제외하지 않는다.

        판정은 공식 코드로만 한다 — 교명 문자열로 거르면 반례를 만든다.
        """
        r = row(korSchlNm="OO사이버보안대학교", schlKndCd="03", schlKndNm="대학교")
        self.assertFalse(is_distance_university(r))

    def test_distance_exclusion_takes_precedence_over_night(self) -> None:
        """두 사유가 겹치면 원격대학 사유가 먼저 기록된다 — 감사에서 구분 가능해야 한다."""
        r = row(schlKndCd="04", schlKndNm="사이버대학(대학)", dghtDivNm="야간")
        self.assertEqual(recommendation_scope_exclusion(r), EXCLUDED_DISTANCE_UNIVERSITY)


class ContractDepartmentScopeTest(unittest.TestCase):
    def test_contract_department_stays_normalized_and_is_also_preserved_out_of_scope(self) -> None:
        raw = row(
            schlId="0000029", schlMjrId="0220559", svyYr=2025,
            korSchlNm="충남대학교", korMjrNm="약학과", clgNm="약학대학",
            schlMjrCharNm="계약학과", schlMjrStatNm="기존", lsnTrmNm="4년",
        )
        included, excluded, out_of_scope = normalize([raw])

        self.assertEqual(excluded, [])
        self.assertEqual(len(included), 1, "전국 정규화 데이터에서 삭제하면 안 된다")
        self.assertEqual(included[0]["recommendation_scope"], "OUT_OF_RECOMMENDATION_SCOPE")
        self.assertEqual(included[0]["exclusion_reason"], "CONTRACT_DEPARTMENT")
        self.assertEqual(len(out_of_scope), 1)
        self.assertEqual(out_of_scope[0]["department_status"], "EXISTING")

    def test_general_department_remains_in_scope(self) -> None:
        included, _, out_of_scope = normalize([row(
            schlId="0000029", schlMjrId="0010025", svyYr=2025,
            korSchlNm="충남대학교", korMjrNm="약학과", clgNm="약학대학",
            schlMjrCharNm="일반과정", schlMjrStatNm="기존", lsnTrmNm="6년",
        )])
        self.assertEqual(included[0]["recommendation_scope"], "IN_RECOMMENDATION_SCOPE")
        self.assertIsNone(included[0]["exclusion_reason"])
        self.assertEqual(out_of_scope, [])


class NormalizedOutputTest(unittest.TestCase):
    """실제 산출물 검증."""

    def test_no_night_course_in_promotion_candidates(self) -> None:
        self.assertFalse(
            [r for r in INCLUDED if r.get("day_night_name") == "야간"],
            "야간 과정이 승격 후보에 남아 있다",
        )

    def test_all_promotion_candidates_are_day_courses(self) -> None:
        self.assertTrue(all(r.get("day_night_name") == "주간" for r in INCLUDED))

    def test_night_records_are_preserved_not_deleted(self) -> None:
        """§8: 야간 원본을 삭제하거나 없었던 것처럼 처리하지 않는다."""
        night = [r for r in OUT_OF_SCOPE if r["recommendation_scope_status"] == EXCLUDED_NIGHT_COURSE]
        self.assertTrue(night, "야간 레코드가 보존돼야 한다")
        for r in night[:20]:
            self.assertTrue(r.get("department_name"))
            self.assertTrue(r.get("source_record_id"))
            self.assertTrue(r.get("recommendation_scope_note"))

    def test_every_out_of_scope_row_has_an_auditable_reason(self) -> None:
        allowed = {EXCLUDED_NIGHT_COURSE, EXCLUDED_DISTANCE_UNIVERSITY,
                   EXCLUDED_UNKNOWN_DAY_NIGHT, "CONTRACT_DEPARTMENT"}
        self.assertTrue(all(
            (r.get("exclusion_reason") or r.get("recommendation_scope_status")) in allowed
            for r in OUT_OF_SCOPE
        ))

    def test_six_contract_rows_are_preserved_outside_recommendation_scope(self) -> None:
        contract = [r for r in OUT_OF_SCOPE if r.get("exclusion_reason") == "CONTRACT_DEPARTMENT"]
        self.assertEqual(len(contract), 6)
        self.assertTrue(all(r["recommendation_scope"] == "OUT_OF_RECOMMENDATION_SCOPE"
                            for r in contract))
        self.assertTrue(all(r["major_character_name"] == "계약학과" for r in contract))
        self.assertFalse(any(r["department_status"] == "ABOLISHED" for r in contract))

    def test_six_general_rows_are_kept_in_duplicate_decision_audit(self) -> None:
        draft = read_jsonl(WORK / "packets" / "duplicate_decision_draft.jsonl")
        general = [r for g in draft for r in g["records"]
                   if r.get("major_character_name") == "일반과정"]
        self.assertEqual(len(general), 6)
        self.assertTrue(all(r["recommendation_scope"] == "IN_RECOMMENDATION_SCOPE"
                            for r in general))

    def test_raw_still_contains_night_rows(self) -> None:
        """Raw 원본에는 야간이 그대로 있어야 한다."""
        import gzip
        raw = ROOT / "data" / "academyinfo_raw" / "2025" / "departments.raw.jsonl.gz"
        if not raw.exists():
            self.skipTest("원본이 로컬에 없다(.gitignore 대상)")
        night = sum(
            1 for l in gzip.open(raw, "rt", encoding="utf-8")
            if json.loads(l).get("dghtDivNm") == "야간"
        )
        self.assertGreater(night, 0, "Raw에서 야간이 사라졌다")


class QueueImpactTest(unittest.TestCase):
    def test_day_night_only_duplicate_groups_are_gone(self) -> None:
        """주야간만 달랐던 중복 그룹이 사라져야 한다 — 야간이 빠졌으므로."""
        self.assertFalse(
            [q for q in DUPLICATE if q["differing_fields"] == ["day_night_name"]],
            "주야간만 다른 중복이 남아 있다",
        )

    def test_no_queue_contains_night_courses(self) -> None:
        night_ids = {
            r["source_record_id"] for r in OUT_OF_SCOPE
            if r["recommendation_scope_status"] == EXCLUDED_NIGHT_COURSE
        }
        for queue, label in ((CLASSIFICATION, "분류"), (NCE, "N.C.E")):
            ids = {q.get("source_record_id") for q in queue}
            self.assertEqual(ids & night_ids, set(), f"{label} Queue에 야간이 섞였다")

    def test_duplicate_queue_shrank(self) -> None:
        """588 → 16. 야간 제외만으로 줄었다(ids.py 변경 없이)."""
        self.assertLess(len(DUPLICATE), 100)

    def test_recommendation_candidates_have_no_duplicate_department_id(self) -> None:
        self.assertEqual(len(DUPLICATE), 0)


class MasterUnchangedTest(unittest.TestCase):
    def test_demo_master_still_35(self) -> None:
        rows = [
            l for l in (ROOT / "data" / "master" / "departments.jsonl")
            .read_text(encoding="utf-8").splitlines() if l.strip()
        ]
        self.assertEqual(len(rows), 35)

    def test_generate_department_id_signature_unchanged(self) -> None:
        """§4: generate_department_id()에 day_night를 추가하지 않는다."""
        import inspect
        from src.ids import generate_department_id
        params = list(inspect.signature(generate_department_id).parameters)
        self.assertEqual(params, ["schl_id", "department_name", "college_name"])


if __name__ == "__main__":
    unittest.main()
