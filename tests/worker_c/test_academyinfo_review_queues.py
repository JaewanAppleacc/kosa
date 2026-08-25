"""Master 승격 전 검토 Queue 테스트 — A 지시(2026-08-24) §6.

정본 정책: outputs/handoff/academyinfo_a_decisions.md
실제 산출물을 읽어 검증한다 — Queue가 보고 수치와 어긋나면 검토 계획 자체가 틀어진다.
"""

from __future__ import annotations

import json
import hashlib
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
QUEUE_REPORT = json.loads((WORK / "review_queue_report.json").read_text(encoding="utf-8"))

GROUPS_PATH = ROOT / "data" / "canonical_major_groups.draft.jsonl"
CANONICAL_GROUP_IDS = {
    json.loads(l)["canonical_major_id"]
    for l in GROUPS_PATH.read_text(encoding="utf-8").splitlines() if l.strip()
}


class QueueCountsMatchReportsTest(unittest.TestCase):
    """§6: Queue 행 수가 기존 보고 수와 일치한다."""

    def test_duplicate_group_count_matches_queue_report(self) -> None:
        """Queue는 승격 후보(EXISTING/NEW)만 담는다.

        정규화 보고서의 duplicate_department_id_count는 **전체**를 세므로 그것과
        직접 비교하면 어긋난다 — 대조 대상은 Queue 보고서다.
        """
        self.assertEqual(len(DUPLICATE), QUEUE_REPORT["duplicate_group_count"])
        self.assertLessEqual(len(DUPLICATE), NORMALIZATION["duplicate_department_id_count"],
                             "후보만 담으므로 전체보다 많을 수 없다")

    def test_duplicate_record_count_matches(self) -> None:
        total = sum(q["record_count"] for q in DUPLICATE)
        self.assertEqual(total, QUEUE_REPORT["duplicate_record_count"])

    def test_queues_are_not_empty(self) -> None:
        """숫자 고정을 뺀 대신, Queue가 통째로 비어버린 사고는 잡는다."""
        self.assertGreater(len(CLASSIFICATION), 0)
        self.assertGreater(len(NCE), 0)
        self.assertEqual(len(URL_AUDIT), 37)

    def test_classification_queue_matches_dry_run(self) -> None:
        self.assertEqual(len(CLASSIFICATION), QUEUE_REPORT["promotion_pool_classification_review_count"])
        self.assertLessEqual(len(CLASSIFICATION), DRY_RUN["eligibility_breakdown"]["REVIEW_REQUIRED"])

    def test_nce_queue_matches_dry_run(self) -> None:
        self.assertEqual(len(NCE), QUEUE_REPORT["promotion_pool_nce_count"])
        self.assertLessEqual(len(NCE), DRY_RUN["unclassified_nce_count"])

    def test_url_audit_preserves_all_37(self) -> None:
        self.assertEqual(len(URL_AUDIT), 37)

    def test_contract_scope_statistics_are_recalculated(self) -> None:
        self.assertEqual(QUEUE_REPORT["normalized_daytime_bachelor_total"], 24422)
        self.assertEqual(QUEUE_REPORT["current_status_candidate_count"], 10063)
        self.assertEqual(QUEUE_REPORT["recommendation_candidate_count"], 10057)
        self.assertEqual(QUEUE_REPORT["approvable_candidate_count"], 5449)
        self.assertEqual(QUEUE_REPORT["out_of_recommendation_scope_count"], 973)
        self.assertEqual(QUEUE_REPORT["contract_department_exclusion_count"], 6)
        self.assertEqual(QUEUE_REPORT["review_queue_total_count"], 3837)


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
        packet = read_jsonl("packets/duplicate_decision_draft.jsonl")
        with_zero = [g for g in packet
                     if any(r.get("enrolled_count") == 0 for r in g["records"])
                     and any((r.get("enrolled_count") or 0) > 0 for r in g["records"])]
        self.assertTrue(with_zero, "재학생 0명 행이 섞인 그룹이 있어야 이 위험이 실재함을 보인다")
        for group in with_zero:
            self.assertEqual(group["reviewer_1_status"], "TBD")

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


# 결정론성 검사는 test_academyinfo_queue_clean_clone.py로 옮겼다.
#
# 여기 있던 DeterminismTest는 생성기를 **무조건** 실행하고 check=True였다. 그래서
# clean clone(생성 입력이 .gitignore 대상이라 없는 환경)에서는 생성기가 0이 아닌 코드로
# 끝나면서 **Skip이 아니라 오류로 실패**했다 — "입력이 없으면 명시적으로 Skip한다"는
# 정책과 정면으로 어긋난다.
#
# 이제 두 곳에서 나눠 검증한다.
#   FixtureDeterminismTest        작은 Fixture로 **항상** 결정론성 검증 (입력 불필요)
#   NationwideRegenerationTest    전국 입력이 있을 때만 Byte 비교, 없으면 사유 출력 후 Skip


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

    def test_demo_master_still_has_5595_departments(self) -> None:
        """2026-08-25 전국 학과 1,072건 Production Master 전환(a/national-master-
        promotion-final-wiring) — 이 테스트가 지키려던 "Master를 건드리지 않는다"는
        이 review-queue 라운드 자체의 범위였다. 그 옛 35건은 지금
        `data/archive/departments_legacy_demo_35.jsonl`로 그대로 보존돼 있고(다음
        SHA-256 테스트가 확인한다), 실제 Master는 이후 라운드가 의도적으로 1,072건
        으로 교체했다.

        2026-08-25 지시서(c/national-departments-38-majors) 후속 정정 — 8개
        Major·1,072건을 38개 Major·5,595건으로 다시 교체했다."""
        rows = [
            l for l in (ROOT / "data" / "master" / "departments.jsonl")
            .read_text(encoding="utf-8").splitlines() if l.strip()
        ]
        self.assertEqual(len(rows), 5595)

    def test_legacy_35_department_archive_sha256_matches_pre_promotion_master(self) -> None:
        digest = hashlib.sha256(
            (ROOT / "data" / "archive" / "departments_legacy_demo_35.jsonl").read_bytes()
        ).hexdigest()
        self.assertEqual(
            digest,
            "2d862b84b74946bbc598c0d829907d415e6dbadf0439df8c1386e936caeeef65",
        )

    def test_demo_master_department_url_is_untouched(self) -> None:
        """공개 Master에는 아직 department_url을 넣지 않는다."""
        for line in (ROOT / "data" / "master" / "departments.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                self.assertNotIn("department_url_scope", line)


if __name__ == "__main__":
    unittest.main()
