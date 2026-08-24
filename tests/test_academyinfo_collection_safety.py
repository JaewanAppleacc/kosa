"""대학알리미 수집·정규화 안전성 검증 — A-2 지시서(integration/academyinfo-pipeline,
2026-08-24) §5.

실제 전국 API를 다시 호출하지 않는다 — 이미 Commit된 Manifest·Report를 근거로
검증하거나, 실제 호출이 필요한 부분(Quota·Resume)은 Fake Client로만 확인한다."""

from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from pathlib import Path

import scripts.career_collect_academyinfo_departments as collector
from src.data_sources.academyinfo_client import QuotaError
from src.data_sources.academyinfo_codes import (
    FOUR_YEAR_OR_LONGER_TERM_CODES,
    UNCLASSIFIED_MIDDLE_SERIES,
    UNCLASSIFIED_SMALL_SERIES,
)
from src.data_sources.academyinfo_identity import (
    build_lineage,
    generate_source_record_id,
    retention_stats,
)
from src.data_sources.academyinfo_year import (
    PUBLIC_API_METADATA_MODIFIED_AT,
    SurveyYearUnavailableError,
    parse_supported_years,
    select_survey_year,
)
from src.ids import generate_department_id

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_json(relative_path: str) -> dict:
    return json.loads((_REPO_ROOT / relative_path).read_text(encoding="utf-8"))


class SurveyYearManifestConsistencyTest(unittest.TestCase):
    """2025 Manifest가 실제로 동적 조회·최신값 선택·수정일 미사용 정책을 반영했는지
    Commit된 산출물로 확인한다(A 결정사항 §1 "조사연도")."""

    def setUp(self) -> None:
        self.manifest = _load_json("data/academyinfo_raw/2025/collection_manifest.json")

    def test_selected_year_is_2025_and_is_the_max_of_supported(self) -> None:
        self.assertEqual(self.manifest["selected_survey_year"], 2025)
        self.assertEqual(self.manifest["selected_survey_year"], max(self.manifest["supported_survey_years"]))

    def test_2026_is_not_in_supported_years_so_2025_was_correctly_chosen(self) -> None:
        self.assertNotIn(2026, self.manifest["supported_survey_years"])

    def test_portal_metadata_modified_date_is_recorded_separately_from_survey_year(self) -> None:
        self.assertEqual(self.manifest["public_api_metadata_modified_at"], "2026-05-04")
        # 수정일(2026-05-04)의 연도 2026을 조사연도로 오인하지 않았는지 — 실제 선택된
        # 값은 API가 지원하는 2025다.
        self.assertEqual(self.manifest["selected_survey_year"], 2025)
        self.assertNotEqual(self.manifest["selected_survey_year"], 2026)

    def test_selected_year_reason_explicitly_rejects_metadata_date_as_basis(self) -> None:
        self.assertIn("수정일", self.manifest["selected_year_reason"])
        self.assertIn("아니므로", self.manifest["selected_year_reason"])

    def test_constant_matches_manifest(self) -> None:
        self.assertEqual(PUBLIC_API_METADATA_MODIFIED_AT, self.manifest["public_api_metadata_modified_at"])


class SurveyYearSelectionFunctionTest(unittest.TestCase):
    """실제 API를 부르지 않는 Fake Client로 `select_survey_year()` 자체의 동작을
    재확인한다(worker-c의 `tests/worker_c/test_academyinfo_year.py`와 같은 함수를
    보되, 여기서는 "2026 미지원 시 2025 선택"이라는 이번 라운드 정책 문장 그대로를
    시나리오로 만든다)."""

    class _FakeYearClient:
        def __init__(self, years: list[int]) -> None:
            self._years = years

        def fetch_code_table(self, service, operation, survey_year):  # noqa: ANN001
            return [{"yearVal": str(y)} for y in self._years]

    def test_2026_not_supported_selects_2025(self) -> None:
        selection = select_survey_year(self._FakeYearClient([2025, 2024, 2023]))
        self.assertEqual(selection.selected_year, 2025)

    def test_empty_year_list_raises_instead_of_defaulting(self) -> None:
        with self.assertRaises(SurveyYearUnavailableError):
            select_survey_year(self._FakeYearClient([]))

    def test_non_numeric_rows_are_dropped_not_defaulted(self) -> None:
        years = parse_supported_years([{"yearVal": "2025"}, {"yearVal": "N/A"}, {"yearVal": ""}])
        self.assertEqual(years, [2025])


class QuotaAndResumeAndAtomicWriteTest(unittest.TestCase):
    """§5 "Resume과 원자적 파일 교체"·"Quota/실패 기록" — 실제 네트워크 없이 Fake
    Client로만 검증한다."""

    class _FakeDepartmentClient:
        """`quota_after`번째 호출부터 QuotaError를 낸다."""

        def __init__(self, quota_after: int | None = None) -> None:
            self.quota_after = quota_after
            self.calls = 0

        def fetch_departments(self, survey_year: int, *, school_id: str, num_of_rows: int = 100):
            self.calls += 1
            if self.quota_after is not None and self.calls > self.quota_after:
                raise QuotaError("일일 한도 초과(Fake, 네트워크 호출 없음)")
            return [{"schlId": school_id, "schlMjrId": f"m{self.calls}", "deptKrnNm": "테스트학과"}]

    def test_quota_error_stops_cleanly_without_raising_and_keeps_partial_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = collector.Paths.for_year(2099, Path(tmp))
            client = self._FakeDepartmentClient(quota_after=2)
            collected, failed = collector.collect_departments(
                client, paths, 2099, ["s1", "s2", "s3", "s4"], dry_run=False, resume=False,
            )
            self.assertEqual(collected, 2)
            self.assertEqual(failed, 0)
            self.assertTrue(paths.checkpoint.exists())
            checkpoint = json.loads(paths.checkpoint.read_text(encoding="utf-8"))
            self.assertEqual(sorted(checkpoint["completed_school_ids"]), ["s1", "s2"])

    def test_resume_continues_from_checkpoint_without_recollecting_done_schools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = collector.Paths.for_year(2099, Path(tmp))
            first_client = self._FakeDepartmentClient(quota_after=2)
            collector.collect_departments(first_client, paths, 2099, ["s1", "s2", "s3"], dry_run=False, resume=False)

            second_client = self._FakeDepartmentClient(quota_after=None)
            collected, _failed = collector.collect_departments(
                second_client, paths, 2099, ["s1", "s2", "s3"], dry_run=False, resume=True,
            )
            self.assertEqual(collected, 3, "이미 완료한 s1/s2는 다시 모으지 않고 s3만 이어받아야 한다")
            self.assertEqual(second_client.calls, 1, "s1/s2는 재호출되면 안 된다")

    def test_write_jsonl_gz_leaves_no_tmp_file_and_content_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "sample.jsonl.gz"
            rows = [{"a": 1}, {"b": 2}]
            collector.write_jsonl_gz(target, rows)
            self.assertTrue(target.exists())
            self.assertFalse(target.with_suffix(target.suffix + ".tmp").exists())
            self.assertEqual(collector.read_jsonl_gz(target), rows)

    def test_save_checkpoint_leaves_no_tmp_file_and_is_atomic_replace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "collection_checkpoint.json"
            collector.save_checkpoint(path, {"completed_school_ids": ["s1"]})
            self.assertTrue(path.exists())
            self.assertFalse(path.with_suffix(".json.tmp").exists())
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["completed_school_ids"], ["s1"])

    def test_same_department_rows_produce_byte_identical_gz(self) -> None:
        """§4 "같은 입력이면 Byte-identical해야 한다" — 키 정렬·고정 gzip 헤더 덕분에
        같은 논리 내용은 재실행해도 항상 같은 바이트가 나와야 한다(Diff 가능성)."""

        rows = [{"b": 2, "a": 1}, {"d": 4, "c": 3}]
        with tempfile.TemporaryDirectory() as tmp:
            p1 = Path(tmp) / "one.jsonl.gz"
            p2 = Path(tmp) / "two.jsonl.gz"
            collector.write_jsonl_gz(p1, rows)
            collector.write_jsonl_gz(p2, rows)
            self.assertEqual(p1.read_bytes(), p2.read_bytes())


class FourToSevenYearScopeTest(unittest.TestCase):
    """§5 "4~7년 학사과정 포함, 전문대·교육대·2~3년 과정 제외"를 코드 상수와 실제
    정규화 보고서 양쪽에서 확인한다."""

    def test_four_year_or_longer_codes_cover_4_through_7_years_only(self) -> None:
        from src.data_sources.academyinfo_codes import lesson_term_label

        included_labels = {lesson_term_label(c) for c in sorted(FOUR_YEAR_OR_LONGER_TERM_CODES)}
        self.assertEqual(included_labels, {"4년", "4.5년", "5년", "5.5년", "6년", "6.5년", "7년"})

    def test_short_and_education_specialized_terms_excluded(self) -> None:
        # "14"="1년(교육특성화)", "15"="2년(교육특성화)" — 코드값은 크지만 실제 연한은
        # 짧다. 부등호 비교였다면 잘못 포함됐을 것이다(모듈 docstring 그대로).
        self.assertNotIn("14", FOUR_YEAR_OR_LONGER_TERM_CODES)
        self.assertNotIn("15", FOUR_YEAR_OR_LONGER_TERM_CODES)
        for short_code in ("01", "02", "03", "04", "05", "06"):
            self.assertNotIn(short_code, FOUR_YEAR_OR_LONGER_TERM_CODES)

    def test_normalization_report_lesson_terms_are_all_4_years_or_longer(self) -> None:
        report = _load_json("data/academyinfo_work/2025/normalization_report.json")
        self.assertEqual(set(report["lesson_term_breakdown"]), {"4년", "5년", "6년"})

    def test_normalization_report_exclusion_reasons_preserve_short_term_and_non_university(self) -> None:
        report = _load_json("data/academyinfo_work/2025/normalization_report.json")
        reasons = report["exclusion_breakdown"]
        self.assertIn("학교종류가 대학교가 아님: 전문대학", reasons)
        self.assertIn("학교종류가 대학교가 아님: 교육대학", reasons)
        self.assertIn("수업연한이 4년 미만: 3년", reasons)
        self.assertIn("수업연한이 4년 미만: 2년", reasons)
        self.assertGreater(sum(reasons.values()), 0)

    def test_file_dataset_import_report_also_preserves_exclusion_reasons(self) -> None:
        report = _load_json("data/academyinfo_work/2024/file_dataset_import_report.json")
        self.assertGreater(len(report["exclusion_breakdown"]), 0)
        self.assertEqual(
            report["included_count"] + report["excluded_count"], report["total_rows"],
            "포함+제외 합이 전체 행 수와 일치해야 한다 — 원본을 조용히 버린 행이 없다는 뜻",
        )


class NceExclusionTest(unittest.TestCase):
    """§5(+§4) "N.C.E 99/999를 일반 전공군으로 취급하지 않음" — 실제 분류 Dry-run
    결과에서도 N.C.E가 별도 버킷으로 빠졌는지 확인한다."""

    def test_classification_dry_run_counts_nce_separately_from_review_required(self) -> None:
        # 2026-08-24 worker-c 정제 통합(d26213a) — 주간 학사과정만 추천 범위로
        # 제한하면서 야간·원격 학과가 모수에서 빠져 아래 수치가 이전(3657)보다
        # 줄었다. classification_dry_run.json 자체가 갱신된 결과이지, 이 테스트가
        # 임의로 낮춘 값이 아니다.
        report = _load_json("data/academyinfo_work/2025/classification_dry_run.json")
        self.assertEqual(report["unclassified_nce_count"], 3539)
        self.assertIn("N.C.E.", report["official_small_series_distribution"])
        # N.C.E는 UNMAPPED로 잡히지, APPROVED/REVIEW_REQUIRED로 섞이지 않는다.
        self.assertEqual(report["mapping_status_breakdown"]["UNMAPPED"] >= report["unclassified_nce_count"], True)

    def test_classification_dry_run_review_required_count_matches_report(self) -> None:
        # 2026-08-24 worker-c 정제 통합(d26213a) — 위와 같은 이유로 4454/3667에서
        # 갱신됐다.
        report = _load_json("data/academyinfo_work/2025/classification_dry_run.json")
        self.assertEqual(report["eligibility_breakdown"]["REVIEW_REQUIRED"], 4258)
        self.assertEqual(report["eligibility_breakdown"]["EXCLUDED_ARTS_SPORTS"], 3588)


class SourceRecordIdAndDepartmentIdYearPolicyTest(unittest.TestCase):
    """§5 "source_record_id에는 조사연도 포함, department_id에는 조사연도 미포함,
    schlMjrId를 안정 Entity ID로 사용하지 않음"을 직접 함수 호출로 확인한다."""

    def test_source_record_id_changes_when_survey_year_changes(self) -> None:
        id_2024 = generate_source_record_id("school1", "mjr1", 2024)
        id_2025 = generate_source_record_id("school1", "mjr1", 2025)
        self.assertNotEqual(id_2024, id_2025, "source_record_id는 조사연도가 다르면 달라져야 한다")

    def test_source_record_id_is_deterministic(self) -> None:
        self.assertEqual(
            generate_source_record_id("school1", "mjr1", 2025), generate_source_record_id("school1", "mjr1", 2025)
        )

    def test_department_id_signature_does_not_accept_survey_year(self) -> None:
        """`generate_department_id`(A 소유, `src/ids.py`)에는 조사연도 인자가 아예
        없다 — 시그니처 자체가 "연도를 넣을 수 없다"를 강제한다."""

        import inspect

        params = list(inspect.signature(generate_department_id).parameters)
        self.assertNotIn("survey_year", params)
        self.assertNotIn("svy_year", params)
        self.assertEqual(params, ["schl_id", "department_name", "college_name"])

    def test_department_id_is_stable_across_survey_years(self) -> None:
        id_a = generate_department_id("school1", "테스트학과", "테스트단과대학")
        id_b = generate_department_id("school1", "테스트학과", "테스트단과대학")
        self.assertEqual(id_a, id_b, "department_id는 조사연도와 무관하게 항상 같아야 한다")

    def test_schl_mjr_id_is_not_used_to_build_department_id(self) -> None:
        """`build_lineage`는 department_id로 매칭하고 schlMjrId는 상태 판정에만 쓴다 —
        schlMjrId가 바뀌어도(SCHL_MJR_ID_CHANGED) department_id 매칭 자체는 끊기지
        않는다는 것을 작은 Fixture로 직접 확인한다."""

        dept_id = generate_department_id("school1", "컴퓨터공학과", "공과대학")
        previous = [{"department_id": dept_id, "university_name": "테스트대", "department_name": "컴퓨터공학과", "college_name": "공과대학", "source_schl_mjr_id": "old_mjr_999"}]
        current = [{"department_id": dept_id, "university_name": "테스트대", "department_name": "컴퓨터공학과", "college_name": "공과대학", "source_schl_mjr_id": "new_mjr_111"}]
        lineage = build_lineage(current, previous)
        self.assertEqual(len(lineage), 1)
        self.assertEqual(lineage[0]["status"], "SCHL_MJR_ID_CHANGED")
        self.assertEqual(lineage[0]["department_id"], dept_id, "schlMjrId가 바뀌어도 department_id로 계속 같은 학과로 인식돼야 한다")


class NewMissingIsNotDeclaredAsFoundedOrAbolishedTest(unittest.TestCase):
    """§5 "NEW/MISSING을 신설·폐지로 단정하지 않음" — 실제 상태 라벨이 중립적인
    이름(NEW_IN_LATEST/MISSING_IN_LATEST)이지, "신설학과"/"폐지학과"처럼 단정하는
    표현이 아님을 확인한다."""

    def test_lineage_status_labels_are_neutral_not_declarative(self) -> None:
        dept_id_new = generate_department_id("school2", "새학과", "신설단과대학")
        dept_id_missing = generate_department_id("school3", "옛학과", "구단과대학")
        current = [{"department_id": dept_id_new, "university_name": "u", "department_name": "새학과", "college_name": "c", "source_schl_mjr_id": "m1"}]
        previous = [{"department_id": dept_id_missing, "university_name": "u", "department_name": "옛학과", "college_name": "c", "source_schl_mjr_id": "m2"}]
        lineage = build_lineage(current, previous)
        statuses = {row["status"] for row in lineage}
        self.assertEqual(statuses, {"NEW_IN_LATEST", "MISSING_IN_LATEST"})
        for forbidden in ("신설", "폐지", "FOUNDED", "ABOLISHED_DECLARED"):
            self.assertNotIn(forbidden, statuses)

    def test_retention_stats_are_computed_over_matched_only(self) -> None:
        lineage = [
            {"status": "STABLE"}, {"status": "STABLE"}, {"status": "SCHL_MJR_ID_CHANGED"},
            {"status": "NEW_IN_LATEST"}, {"status": "NEW_IN_LATEST"}, {"status": "MISSING_IN_LATEST"},
        ]
        stats = retention_stats(lineage)
        self.assertEqual(stats["matched_department_count"], 3)  # STABLE 2 + CHANGED 1, NEW/MISSING 제외
        self.assertEqual(stats["schl_mjr_id_retention_rate"], round(2 / 3, 4))


class YearComparisonReportMatchesRetentionPolicyTest(unittest.TestCase):
    """§5 "2024/2025 유지율 99.6% 보고서와 일치"를 실제 Commit된 Report로 확인한다."""

    def setUp(self) -> None:
        self.report = _load_json("data/academyinfo_work/2025/year_comparison_report.json")

    def test_retention_rate_is_99_6_percent(self) -> None:
        self.assertEqual(self.report["schl_mjr_id_retention_rate"], 0.996)

    def test_retention_rate_matches_stable_over_matched_math(self) -> None:
        matched = self.report["stable"] + self.report["schl_mjr_id_changed"]
        self.assertEqual(matched, self.report["matched_department_count"])
        self.assertEqual(round(self.report["stable"] / matched, 4), self.report["schl_mjr_id_retention_rate"])

    def test_new_and_missing_are_excluded_from_retention_denominator(self) -> None:
        total_rows = (
            self.report["stable"] + self.report["schl_mjr_id_changed"]
            + self.report["new_in_latest"] + self.report["missing_in_latest"]
        )
        self.assertGreater(total_rows, self.report["matched_department_count"])


if __name__ == "__main__":
    unittest.main()
