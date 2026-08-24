"""Master 승격 전 검토 Queue 테스트 — A 지시(2026-08-24) §6.

정본 정책: outputs/handoff/academyinfo_a_decisions.md
실제 산출물을 읽어 검증한다 — Queue가 보고 수치와 어긋나면 검토 계획 자체가 틀어진다.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "data" / "academyinfo_work" / "2025"


def read_jsonl(name: str) -> list[dict]:
    p = WORK / name
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


DUPLICATE = read_jsonl("duplicate_department_review_queue.jsonl")
CLASSIFICATION = read_jsonl("classification_review_queue.jsonl")
NCE = read_jsonl("unmapped_nce_queue.jsonl")
URL_AUDIT = read_jsonl("department_url_scope_audit.jsonl")
DRY_RUN = json.loads((WORK / "classification_dry_run.json").read_text(encoding="utf-8"))
NORMALIZATION = json.loads((WORK / "normalization_report.json").read_text(encoding="utf-8"))

GROUPS_PATH = ROOT / "data" / "canonical_major_groups.draft.jsonl"
CANONICAL_GROUP_IDS = {
    json.loads(l)["canonical_major_id"]
    for l in GROUPS_PATH.read_text(encoding="utf-8").splitlines() if l.strip()
}


class QueueCountsMatchReportsTest(unittest.TestCase):
    """§6: Queue 행 수가 기존 보고 수와 일치한다."""

    def test_duplicate_group_count_matches_normalization_report(self) -> None:
        # 보고서와의 **일치**만 검사한다. 고정 숫자를 박으면 정책이 바뀔 때마다
        # 테스트를 고쳐야 하고, 그러면 "보고와 산출물이 어긋났는지"를 못 잡는다.
        self.assertEqual(len(DUPLICATE), NORMALIZATION["duplicate_department_id_count"])

    def test_duplicate_record_count_matches(self) -> None:
        total = sum(q["record_count"] for q in DUPLICATE)
        self.assertEqual(total, NORMALIZATION["review_required_count"])

    def test_queues_are_not_empty(self) -> None:
        """숫자 고정을 뺀 대신, Queue가 통째로 비어버린 사고는 잡는다."""
        self.assertGreater(len(CLASSIFICATION), 0)
        self.assertGreater(len(NCE), 0)
        self.assertEqual(len(URL_AUDIT), 37)

    def test_classification_queue_matches_dry_run(self) -> None:
        self.assertEqual(len(CLASSIFICATION), DRY_RUN["eligibility_breakdown"]["REVIEW_REQUIRED"])

    def test_nce_queue_matches_dry_run(self) -> None:
        self.assertEqual(len(NCE), DRY_RUN["unclassified_nce_count"])

    def test_url_audit_preserves_all_37(self) -> None:
        self.assertEqual(len(URL_AUDIT), 37)


class DuplicateQueueTest(unittest.TestCase):
    def test_no_duplicate_department_id_across_groups(self) -> None:
        ids = [q["department_id"] for q in DUPLICATE]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_group_has_at_least_two_records(self) -> None:
        self.assertTrue(all(q["record_count"] >= 2 for q in DUPLICATE))

    def test_no_automatic_representative_selected(self) -> None:
        """§1: 자동 대표 행 선정 금지."""
        self.assertTrue(all(q["selected_source_record_id"] is None for q in DUPLICATE))
        self.assertTrue(all(q["decision_status"] == "REVIEW_REQUIRED" for q in DUPLICATE))

    def test_enrolled_count_is_shown_but_not_used_to_decide(self) -> None:
        """재학생 수는 보여주되 선택 근거가 되지 않는다 — 신설 학과는 0명이다."""
        with_zero = [
            q for q in DUPLICATE
            if any(c.get("enrolled_count") == 0 for c in q["candidates"])
            and any((c.get("enrolled_count") or 0) > 0 for c in q["candidates"])
        ]
        self.assertTrue(with_zero, "재학생 0명 행이 섞인 그룹이 있어야 이 위험이 실재함을 보인다")
        for q in with_zero:
            self.assertIsNone(q["selected_source_record_id"])

    def test_all_source_records_are_kept(self) -> None:
        for q in DUPLICATE:
            self.assertEqual(len(q["candidates"]), q["record_count"])
            self.assertEqual(len(q["source_record_ids"]), q["record_count"])

    def test_cause_candidates_are_candidates_not_conclusions(self) -> None:
        """신설·폐지·통합·분리로 단정하지 않는다 — 필드명이 candidate여야 한다."""
        for q in DUPLICATE[:50]:
            self.assertIn("duplicate_cause_candidates", q)
            self.assertTrue(q["duplicate_cause_candidates"])

    def test_queue_does_not_copy_whole_source_row(self) -> None:
        """§1: 원본 전체를 복제하지 말고 검토에 필요한 필드만 포함한다."""
        heavy = {"education_goal", "education_goal_keywords", "curriculum_sha256", "official_classification"}
        for q in DUPLICATE[:50]:
            for c in q["candidates"]:
                self.assertFalse(heavy & set(c), "무거운 원본 필드가 Queue에 복제됐다")


class ReviewBatchTest(unittest.TestCase):
    """검토 묶음은 작업 정리지 판정이 아니다."""

    def test_every_group_has_a_batch(self) -> None:
        allowed = {"BATCH_DAY_NIGHT_ONLY", "BATCH_DAY_NIGHT_PLUS", "INDIVIDUAL"}
        self.assertTrue(all(q["review_batch"] in allowed for q in DUPLICATE))

    def test_batching_does_not_decide_anything(self) -> None:
        """묶었다고 대표가 정해지면 안 된다 — A 지시 §1 자동 선정 금지."""
        for q in DUPLICATE:
            self.assertEqual(q["decision_status"], "REVIEW_REQUIRED")
            self.assertIsNone(q["selected_source_record_id"])

    def test_day_night_only_batch_really_differs_only_in_day_night(self) -> None:
        """야간 제외 정책 적용 후에는 이 묶음이 0건이어야 정상이다 —
        주야간만 다른 중복은 야간 쪽이 빠지면서 사라진다."""
        for q in DUPLICATE:
            if q["review_batch"] == "BATCH_DAY_NIGHT_ONLY":
                self.assertEqual(q["differing_fields"], ["day_night_name"])

    def test_individual_batch_has_no_day_night_difference(self) -> None:
        for q in DUPLICATE:
            if q["review_batch"] == "INDIVIDUAL":
                self.assertNotIn("day_night_name", q["differing_fields"])


class ClassificationQueueTest(unittest.TestCase):
    def test_every_row_is_review_required(self) -> None:
        self.assertTrue(all(q["review_status"] == "REVIEW_REQUIRED" for q in CLASSIFICATION))

    def test_no_row_is_auto_approved(self) -> None:
        """§2: LLM·문자열 유사도만으로 APPROVE 금지."""
        self.assertFalse(any(q["review_status"] == "APPROVED" for q in CLASSIFICATION))
        self.assertTrue(all(q["reviewer_id"] is None for q in CLASSIFICATION))

    def test_causes_are_split_by_required_categories(self) -> None:
        causes = {q["review_cause"] for q in CLASSIFICATION}
        for required in ("CONVERGENCE", "DESIGN", "MEDIA_CONTENT", "HCI_UX"):
            self.assertIn(required, causes, f"{required} 원인이 분리 집계돼야 한다")

    def test_every_row_has_one_cause_and_a_reason(self) -> None:
        for q in CLASSIFICATION[:200]:
            self.assertTrue(q["review_cause"])
            self.assertTrue(q["review_reason"])

    def test_arts_possibility_is_not_a_decision(self) -> None:
        """예체능 가능성은 확인 대상 표시지 판정이 아니다."""
        allowed = {"CONFIRMED_BY_OFFICIAL_SERIES", "POSSIBLE_NEEDS_CHECK", "UNLIKELY"}
        self.assertTrue(all(q["arts_sports_possibility"] in allowed for q in CLASSIFICATION))

    def test_official_evidence_needed_is_listed(self) -> None:
        for q in CLASSIFICATION[:200]:
            self.assertTrue(q["official_evidence_needed"])

    def test_candidate_groups_are_known_ids(self) -> None:
        for q in CLASSIFICATION[:500]:
            for gid in q["candidate_canonical_major_ids"]:
                self.assertIn(gid, CANONICAL_GROUP_IDS)


class NceQueueTest(unittest.TestCase):
    def test_never_force_mapped_to_a_group(self) -> None:
        """§3: 42개 Group에 강제 배정 금지."""
        for q in NCE:
            self.assertEqual(q["candidate_canonical_major_ids"], [])

    def test_status_is_unmapped_not_review(self) -> None:
        self.assertTrue(all(q["mapping_status"] == "UNMAPPED" for q in NCE))
        self.assertTrue(all(q["review_status"] == "UNMAPPED" for q in NCE))

    def test_nce_is_not_treated_as_a_field_of_study(self) -> None:
        """N.C.E를 실제 학문 분야로 해석하지 않는다."""
        for q in NCE[:200]:
            self.assertIn("센티널", q["unmapped_reason"])

    def test_promotion_condition_requires_official_evidence(self) -> None:
        for q in NCE[:200]:
            self.assertIn("공식", q["promotion_condition"])

    def test_overlap_with_classification_queue_is_flagged_not_hidden(self) -> None:
        """두 Queue는 축이 다르다 — 겹침을 없애지 말고 드러낸다.

        "어느 전공군인가"(분류)와 "추천해도 되나"(적격성)는 별개 질문이라 둘 다 미결일 수
        있다. 겹침을 제거하면 한쪽 근거가 사라진다. 대신 상호 참조 플래그를 붙여
        검토자가 같은 학과를 두 번 볼 때 헷갈리지 않게 한다.
        """
        nce_ids = {q["source_record_id"] for q in NCE}
        cls_ids = {q["source_record_id"] for q in CLASSIFICATION}
        overlap = nce_ids & cls_ids
        self.assertTrue(overlap, "실측상 겹치는 행이 존재한다")
        for q in NCE:
            self.assertEqual(q["also_in_classification_review_queue"],
                             q["source_record_id"] in overlap)
        for q in CLASSIFICATION:
            self.assertEqual(q["also_in_unmapped_nce_queue"],
                             q["source_record_id"] in overlap)


class UrlAuditTest(unittest.TestCase):
    def test_scope_counts_are_preserved(self) -> None:
        scopes = {}
        for u in URL_AUDIT:
            scopes[u["department_url_scope"]] = scopes.get(u["department_url_scope"], 0) + 1
        self.assertEqual(scopes, {"department": 34, "college": 3})

    def test_college_scope_is_never_a_public_candidate(self) -> None:
        """A 결정 §5: college scope는 공개 시 항상 None."""
        for u in URL_AUDIT:
            if u["department_url_scope"] == "college":
                self.assertFalse(u["eligible_for_public_department_url"])
                self.assertEqual(u["audit_status"], "COLLEGE_SCOPE_KEEP_INTERNAL")

    def test_college_urls_and_reasons_are_preserved_not_deleted(self) -> None:
        """공개하지 않을 뿐 값과 사유는 버리지 않는다."""
        college = [u for u in URL_AUDIT if u["department_url_scope"] == "college"]
        self.assertEqual(len(college), 3)
        for u in college:
            self.assertTrue(u["department_url"])
            self.assertTrue(u["department_url_note"])

    def test_no_url_contains_api_key(self) -> None:
        self.assertFalse(any(u["contains_api_key"] for u in URL_AUDIT))

    def test_no_openapi_or_portal_url_is_confirmed(self) -> None:
        for u in URL_AUDIT:
            if u["audit_status"] == "DEPARTMENT_SCOPE_CONFIRMED":
                self.assertNotIn("data.go.kr", u["department_url"])
                self.assertNotIn("academyinfo.go.kr", u["department_url"])

    def test_all_confirmed_urls_are_official_university_domains(self) -> None:
        for u in URL_AUDIT:
            if u["eligible_for_public_department_url"]:
                self.assertTrue(u["is_official_university_domain"])

    def test_http_only_is_recorded_as_fact_not_hidden(self) -> None:
        """HTTPS 미지원은 우리가 고칠 수 없는 사실이다 — 감추지 않고 기록한다."""
        http_only = [u for u in URL_AUDIT if not u["uses_https"]]
        self.assertTrue(http_only, "실측상 HTTP만 제공하는 학교가 있다")
        for u in http_only:
            self.assertTrue(any("HTTP만 제공" in f for f in u["findings"]))


class DeterminismTest(unittest.TestCase):
    def test_regeneration_is_byte_identical(self) -> None:
        """§6: 결정론적 재생성."""
        targets = [
            "duplicate_department_review_queue.jsonl",
            "classification_review_queue.jsonl",
            "unmapped_nce_queue.jsonl",
            "department_url_scope_audit.jsonl",
        ]
        before = {t: (WORK / t).read_bytes() for t in targets}
        subprocess.run(
            [sys.executable, "scripts/career_build_academyinfo_review_queues.py", "--survey-year", "2025"],
            cwd=ROOT, capture_output=True, timeout=600, check=True,
        )
        for t in targets:
            self.assertEqual(before[t], (WORK / t).read_bytes(), f"{t}가 재생성마다 달라진다")


class SecretAndMasterUnchangedTest(unittest.TestCase):
    """§6: Secret 미포함 · 기존 Master/공개 API 무변경."""

    def test_no_secret_like_string_in_queues(self) -> None:
        blob = "".join(
            (WORK / n).read_text(encoding="utf-8")
            for n in ("duplicate_department_review_queue.jsonl", "classification_review_queue.jsonl",
                      "unmapped_nce_queue.jsonl", "department_url_scope_audit.jsonl")
        )
        for token in ("serviceKey", "DATA_GO_KR_SERVICE_KEY", "apikey", "access_token"):
            self.assertNotIn(token, blob)

    def test_demo_master_still_has_35_departments(self) -> None:
        rows = [
            l for l in (ROOT / "data" / "master" / "departments.jsonl")
            .read_text(encoding="utf-8").splitlines() if l.strip()
        ]
        self.assertEqual(len(rows), 35, "이번 작업은 Master를 건드리지 않는다")

    def test_demo_master_department_url_is_untouched(self) -> None:
        """공개 Master에는 아직 department_url을 넣지 않는다."""
        for line in (ROOT / "data" / "master" / "departments.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                self.assertNotIn("department_url_scope", line)


if __name__ == "__main__":
    unittest.main()
