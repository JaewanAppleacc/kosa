"""Clean clone 환경 테스트 — A 결정(2026-08-24) §2.

전제: **저장소를 새로 clone한 사람은 전국 입력 파일을 갖고 있지 않다.**
`departments.normalized.jsonl`·`classification_results.jsonl`은 `.gitignore` 대상이라
커밋되지 않는다. 그런데도 검증은 돌아야 한다.

그래서 둘로 나눈다.

    항상 수행   커밋된 Queue의 행 수·Hash·상태 검사 (입력 파일 불필요)
    항상 수행   작은 Fixture로 Queue 생성 결정론성 검증 (API·전국 데이터 불필요)
    Skip 가능   전국 입력으로 재생성해 Byte 비교 (입력이 있을 때만)

API 재수집은 어떤 테스트도 하지 않는다.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "data" / "academyinfo_work" / "2025"

QUEUE_FILES = (
    "duplicate_department_review_queue.jsonl",
    "classification_review_queue.jsonl",
    "unmapped_nce_queue.jsonl",
    "department_url_scope_audit.jsonl",
    "out_of_recommendation_scope.jsonl",
)
GENERATION_INPUTS = ("departments.normalized.jsonl", "classification_results.jsonl")


def has_generation_inputs() -> bool:
    return all((WORK / n).exists() for n in GENERATION_INPUTS)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CommittedQueueAlwaysCheckedTest(unittest.TestCase):
    """입력 파일이 없어도 항상 도는 검사 — clean clone에서 여기까지는 반드시 통과해야 한다."""

    def test_all_queue_files_are_committed(self) -> None:
        for name in QUEUE_FILES:
            self.assertTrue((WORK / name).exists(), f"{name}이 커밋돼 있지 않다")

    def test_queue_files_are_valid_jsonl(self) -> None:
        for name in QUEUE_FILES:
            rows = read_jsonl(WORK / name)
            if name == "duplicate_department_review_queue.jsonl":
                self.assertEqual(rows, [], "계약학과 제외 후 추천 후보 중복은 0건이어야 한다")
            else:
                self.assertTrue(rows, f"{name}이 비어 있다")

    def test_queue_hashes_are_stable_within_a_run(self) -> None:
        """같은 파일을 두 번 읽어도 Hash가 같다 — 읽기만으로 파일이 바뀌지 않는다."""
        for name in QUEUE_FILES:
            self.assertEqual(sha256(WORK / name), sha256(WORK / name))

    def test_every_queue_row_is_in_a_pending_state(self) -> None:
        """커밋된 Queue에 이미 승인된 행이 섞여 있으면 안 된다."""
        for name, field, allowed in (
            ("duplicate_department_review_queue.jsonl", "decision_status", {"REVIEW_REQUIRED"}),
            ("classification_review_queue.jsonl", "review_status", {"REVIEW_REQUIRED"}),
            ("unmapped_nce_queue.jsonl", "review_status", {"UNMAPPED"}),
        ):
            for row in read_jsonl(WORK / name):
                self.assertIn(row[field], allowed, f"{name}에 {row[field]} 상태가 있다")

    def test_no_reviewer_decision_is_prefilled(self) -> None:
        for name in ("duplicate_department_review_queue.jsonl",
                     "classification_review_queue.jsonl", "unmapped_nce_queue.jsonl"):
            for row in read_jsonl(WORK / name):
                self.assertIsNone(row.get("reviewer_id"))
                self.assertIsNone(row.get("reviewer_comment"))

    def test_queues_contain_no_secret_like_string(self) -> None:
        for name in QUEUE_FILES:
            blob = (WORK / name).read_text(encoding="utf-8")
            for token in ("serviceKey", "DATA_GO_KR_SERVICE_KEY", "apikey", "access_token"):
                self.assertNotIn(token, blob)

    def test_report_counts_match_committed_queues(self) -> None:
        report = json.loads((WORK / "review_queue_report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["duplicate_group_count"],
                         len(read_jsonl(WORK / "duplicate_department_review_queue.jsonl")))
        self.assertEqual(report["classification_review_count"],
                         len(read_jsonl(WORK / "classification_review_queue.jsonl")))
        self.assertEqual(report["nce_queue_count"],
                         len(read_jsonl(WORK / "unmapped_nce_queue.jsonl")))


class FixtureDeterminismTest(unittest.TestCase):
    """작은 Fixture로 결정론성을 **항상** 검증한다 — 전국 데이터도 API도 필요 없다."""

    @staticmethod
    def _fixture_rows() -> tuple[list[dict], list[dict]]:
        def dept(rid: str, dep_id: str, name: str, status: str = "EXISTING", **over) -> dict:
            row = {
                "source_record_id": rid, "department_id": dep_id,
                "university_name": "픽스처대학교", "department_name": name,
                "college_name": "공과대학", "campus": None, "campus_division_name": "본교",
                "admission_unit": None, "day_night_name": "주간",
                "degree_course_name": "학사", "lesson_term_name": "4년",
                "department_status": status, "major_character_name": "일반과정",
                "source_svy_year": 2025, "source_schl_mjr_id": rid,
                "enrolled_count": 0, "graduate_count": 0,
            }
            row.update(over)
            return row

        normalized = [
            dept("r1", "d1", "컴퓨터공학과", schl_id="s1"),
            dept("r2", "d1", "컴퓨터공학과", schl_id="s1",
                 major_character_name="계약학과",
                 recommendation_scope="OUT_OF_RECOMMENDATION_SCOPE",
                 exclusion_reason="CONTRACT_DEPARTMENT"),  # 중복
            dept("r3", "d2", "융합콘텐츠학과"),
            dept("r4", "d3", "폐지학과", status="ABOLISHED"),  # 승격 후보 아님
        ]
        results = [
            {"department_id": "d1", "source_record_id": "r1", "university_name": "픽스처대학교",
             "department_name": "컴퓨터공학과", "college_name": "공과대학",
             "department_status": "EXISTING", "official_small_series_name": "전산학·컴퓨터공학",
             "official_large_series_name": "공학계열", "official_large_series_code": "D",
             "candidate_canonical_major_ids": ["computer_science"], "mapping_status": "AUTO_CANDIDATE",
             "decision_reason": "공식 소계열 090 단독 배정", "eligibility_status": "APPROVED",
             "eligibility_reason": "예체능 아님", "self_series_name": None,
             "official_middle_series_name": "전기·전자·컴퓨터"},
            {"department_id": "d1", "source_record_id": "r2", "university_name": "픽스처대학교",
             "department_name": "컴퓨터공학과", "college_name": "공과대학",
             "department_status": "EXISTING", "official_small_series_name": "전산학·컴퓨터공학",
             "official_large_series_name": "공학계열", "official_large_series_code": "D",
             "candidate_canonical_major_ids": ["computer_science"], "mapping_status": "AUTO_CANDIDATE",
             "decision_reason": "공식 소계열 090 단독 배정", "eligibility_status": "APPROVED",
             "eligibility_reason": "예체능 아님", "self_series_name": None,
             "official_middle_series_name": "전기·전자·컴퓨터"},
            {"department_id": "d2", "source_record_id": "r3", "university_name": "픽스처대학교",
             "department_name": "융합콘텐츠학과", "college_name": "공과대학",
             "department_status": "EXISTING", "official_small_series_name": "N.C.E.",
             "official_large_series_name": "공학계열", "official_large_series_code": "D",
             "candidate_canonical_major_ids": [], "mapping_status": "UNMAPPED",
             "decision_reason": "공식 소계열이 미분류(N.C.E)라 근거가 없다",
             "eligibility_status": "REVIEW_REQUIRED", "eligibility_reason": "융합 명칭",
             "self_series_name": None, "official_middle_series_name": "N.C.E"},
            {"department_id": "d3", "source_record_id": "r4", "university_name": "픽스처대학교",
             "department_name": "폐지학과", "college_name": "공과대학",
             "department_status": "ABOLISHED", "official_small_series_name": "N.C.E.",
             "official_large_series_name": "공학계열", "official_large_series_code": "D",
             "candidate_canonical_major_ids": [], "mapping_status": "UNMAPPED",
             "decision_reason": "공식 소계열이 미분류(N.C.E)라 근거가 없다",
             "eligibility_status": "REVIEW_REQUIRED", "eligibility_reason": "융합 명칭",
             "self_series_name": None, "official_middle_series_name": "N.C.E"},
        ]
        return normalized, results

    def _run_in(self, data_dir: Path) -> dict[str, bytes]:
        work = data_dir / "academyinfo_work" / "2025"
        work.mkdir(parents=True, exist_ok=True)
        normalized, results = self._fixture_rows()
        (work / "departments.normalized.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in normalized),
            encoding="utf-8")
        (work / "classification_results.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in results),
            encoding="utf-8")
        contract = next(r for r in normalized if r.get("major_character_name") == "계약학과")
        preserved = dict(contract)
        preserved.update({
            "recommendation_scope": "OUT_OF_RECOMMENDATION_SCOPE",
            "exclusion_reason": "CONTRACT_DEPARTMENT",
        })
        (work / "out_of_recommendation_scope.jsonl").write_text(
            json.dumps(preserved, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (data_dir / "raw").mkdir(parents=True, exist_ok=True)
        (data_dir / "raw" / "departments.raw.jsonl").write_text("", encoding="utf-8")

        proc = subprocess.run(
            [sys.executable, "scripts/career_build_academyinfo_review_queues.py",
             "--survey-year", "2025", "--data-dir", str(data_dir)],
            cwd=ROOT, capture_output=True, timeout=300,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace")[:800])
        return {n: (work / n).read_bytes() for n in QUEUE_FILES if (work / n).exists()}

    def test_same_fixture_input_produces_identical_output(self) -> None:
        """API도 전국 데이터도 없이 결정론성을 검증한다."""
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            first = self._run_in(Path(a))
            second = self._run_in(Path(b))
            self.assertTrue(first, "Fixture로 Queue가 하나도 안 만들어졌다")
            self.assertEqual(first.keys(), second.keys())
            for name in first:
                self.assertEqual(first[name], second[name], f"{name}이 재실행마다 다르다")

    def test_abolished_row_is_excluded_from_queues(self) -> None:
        """폐지 학과는 승격 검토 Queue에 들어가지 않는다 (A 결정 §1)."""
        with tempfile.TemporaryDirectory() as tmp:
            out = self._run_in(Path(tmp))
            nce = out["unmapped_nce_queue.jsonl"].decode("utf-8")
            self.assertIn("융합콘텐츠학과", nce, "EXISTING 행은 Queue에 있어야 한다")
            self.assertNotIn("폐지학과", nce, "ABOLISHED 행이 Queue에 섞였다")

    def test_contract_department_is_preserved_but_not_a_promotion_candidate(self) -> None:
        """공식 학과특성이 계약학과인 행은 삭제하지 않고 추천 범위 밖에 보존한다."""
        with tempfile.TemporaryDirectory() as tmp:
            out = self._run_in(Path(tmp))
            duplicate = out["duplicate_department_review_queue.jsonl"].decode("utf-8")
            preserved = read_jsonl(Path(tmp) / "academyinfo_work" / "2025"
                                   / "out_of_recommendation_scope.jsonl")

            self.assertEqual(duplicate, "", "계약학과 때문에 생긴 중복이 추천 후보에 남았다")
            contract = [r for r in preserved if r.get("source_record_id") == "r2"]
            self.assertEqual(len(contract), 1)
            self.assertEqual(contract[0]["recommendation_scope"], "OUT_OF_RECOMMENDATION_SCOPE")
            self.assertEqual(contract[0]["exclusion_reason"], "CONTRACT_DEPARTMENT")
            self.assertEqual(contract[0]["department_status"], "EXISTING")

    def test_general_course_remains_in_recommendation_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._run_in(Path(tmp))
            report = json.loads((Path(tmp) / "academyinfo_work" / "2025"
                                 / "review_queue_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["current_status_candidate_count"], 3)
            self.assertEqual(report["recommendation_candidate_count"], 2)
            self.assertEqual(report["out_of_recommendation_scope_count"], 1)

    def test_generation_does_not_touch_repository_queues(self) -> None:
        """--data-dir로 격리 실행하면 저장소의 커밋된 Queue를 건드리지 않는다."""
        before = {n: sha256(WORK / n) for n in QUEUE_FILES}
        with tempfile.TemporaryDirectory() as tmp:
            self._run_in(Path(tmp))
        for name in QUEUE_FILES:
            self.assertEqual(before[name], sha256(WORK / name), f"{name}이 바뀌었다")


class NationwideRegenerationTest(unittest.TestCase):
    """전국 입력이 있을 때만 도는 검사. clean clone에서는 명시적으로 Skip된다."""

    def setUp(self) -> None:
        if not has_generation_inputs():
            self.skipTest(
                "전국 생성 입력(departments.normalized.jsonl · classification_results.jsonl)이 "
                "없다 — .gitignore 대상이라 clean clone에는 존재하지 않는다. "
                "재수집하지 않고 Skip한다."
            )

    def test_regeneration_is_byte_identical(self) -> None:
        before = {n: (WORK / n).read_bytes() for n in QUEUE_FILES}
        proc = subprocess.run(
            [sys.executable, "scripts/career_build_academyinfo_review_queues.py",
             "--survey-year", "2025"],
            cwd=ROOT, capture_output=True, timeout=600,
        )
        self.assertEqual(proc.returncode, 0)
        for name in QUEUE_FILES:
            self.assertEqual(before[name], (WORK / name).read_bytes(), f"{name}이 재생성마다 다르다")


class MissingInputSafetyTest(unittest.TestCase):
    """생성 입력이 없으면 기존 Queue를 부분 덮어쓰지 않는다 (A 결정 §2)."""

    def test_missing_input_exits_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            (data_dir / "academyinfo_work" / "2025").mkdir(parents=True)
            (data_dir / "raw").mkdir(parents=True)
            (data_dir / "raw" / "departments.raw.jsonl").write_text("", encoding="utf-8")

            proc = subprocess.run(
                [sys.executable, "scripts/career_build_academyinfo_review_queues.py",
                 "--survey-year", "2025", "--data-dir", str(data_dir)],
                cwd=ROOT, capture_output=True, timeout=300,
            )
            self.assertNotEqual(proc.returncode, 0, "입력이 없는데 성공으로 끝났다")
            for name in QUEUE_FILES:
                self.assertFalse(
                    (data_dir / "academyinfo_work" / "2025" / name).exists(),
                    f"입력이 없는데 {name}을 썼다 — 부분 덮어쓰기다",
                )

    def test_missing_url_audit_raw_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            work = data_dir / "academyinfo_work" / "2025"
            work.mkdir(parents=True)
            fixture = {"source_record_id": "r1", "department_id": "d1",
                       "department_status": "EXISTING", "major_character_name": "일반과정"}
            for name in GENERATION_INPUTS:
                (work / name).write_text(
                    json.dumps(fixture, ensure_ascii=False) + "\n", encoding="utf-8"
                )
            (work / "out_of_recommendation_scope.jsonl").write_text("", encoding="utf-8")

            proc = subprocess.run(
                [sys.executable, "scripts/career_build_academyinfo_review_queues.py",
                 "--survey-year", "2025", "--data-dir", str(data_dir)],
                cwd=ROOT, capture_output=True, timeout=300,
            )
            self.assertNotEqual(proc.returncode, 0)
            for name in QUEUE_FILES:
                if name == "out_of_recommendation_scope.jsonl":
                    self.assertEqual((work / name).read_text(encoding="utf-8"), "")
                else:
                    self.assertFalse((work / name).exists(), f"{name}이 부분 생성됐다")


if __name__ == "__main__":
    unittest.main()
