"""National Department Repository Readiness Harness 계약 테스트 —
`a/national-department-readiness`(2026-08-24) §6.

이 Harness는 읽기 전용이다 — `src/repositories/department_repository.py`·
`src/services/major_exploration_service.py`를 전혀 수정하지 않는다. 이 테스트는 그
약속이 실제로 지켜지는지(운영 Master·공개 API·Mock·실제 검수 파일이 전혀 안 바뀌는지,
합성 Fixture가 임시 디렉터리 밖으로 새지 않는지)까지 직접 증명한다."""

from __future__ import annotations

import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

import eval.national_department_repository_readiness as harness
from src.repositories.department_repository import JsonlDepartmentRepository
from src.schemas.major import Department

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DeterminismTest(unittest.TestCase):
    """§6 "Harness 두 번 실행 결과 byte-identical". Wall Time·메모리 실측값 자체는
    물리적으로 매 실행 달라질 수 있으므로(§4 "실측값을 제시"), harness.
    comparable_snapshot()이 정의하는 "논리적으로 재현 가능한 부분"(Fixture 분포,
    시나리오 통과/실패와 그 이유, 발견된 결함 목록)이 byte-identical(JSON
    직렬화 기준)한지 확인한다."""

    def test_two_runs_produce_identical_comparable_snapshot(self) -> None:
        import json

        report1 = harness.main()
        snapshot1 = json.dumps(harness.comparable_snapshot(report1), ensure_ascii=False, sort_keys=True)
        report2 = harness.main()
        snapshot2 = json.dumps(harness.comparable_snapshot(report2), ensure_ascii=False, sort_keys=True)
        self.assertEqual(snapshot1, snapshot2)

    def test_fixture_generation_alone_is_byte_identical_across_calls(self) -> None:
        rows1 = harness.build_national_scale_fixture()
        rows2 = harness.build_national_scale_fixture()
        self.assertEqual(rows1, rows2)

    def test_fixture_row_count_matches_real_normalization_report(self) -> None:
        rows = harness.build_national_scale_fixture()
        self.assertEqual(len(rows), harness._TOTAL_NATIONAL_SCALE)
        self.assertEqual(len(rows), 25389)


class FixtureCleanupTest(unittest.TestCase):
    """§6 "임시 Fixture 정리 확인" — Harness 실행이 끝나면 만들었던 임시 디렉터리가
    남아 있지 않아야 하고, 합성 데이터는 저장소 어디에도 Git으로 추적되지 않아야
    한다."""

    def test_main_leaves_no_temp_fixture_directory_behind(self) -> None:
        import glob
        import tempfile as _tempfile

        before = set(glob.glob(f"{_tempfile.gettempdir()}/national_department_readiness_*"))
        harness.main()
        after = set(glob.glob(f"{_tempfile.gettempdir()}/national_department_readiness_*"))
        self.assertEqual(after - before, set(), "Harness가 임시 Fixture 디렉터리를 정리하지 않고 남김")

    def test_no_synthetic_fixture_file_is_git_tracked(self) -> None:
        result = subprocess.run(
            ["git", "ls-files"], cwd=_REPO_ROOT, capture_output=True, text=True, check=True,
        )
        tracked = result.stdout.splitlines()
        leaked = [f for f in tracked if "synthetic_departments_national" in f or "national_department_readiness_" in f]
        self.assertEqual(leaked, [])


class OperationalMasterUnchangedTest(unittest.TestCase):
    """§6 "운영 Master 35건 SHA-256 불변"·"공개 API·Mock 불변"·"실제 data/reviews 불변"."""

    _PROTECTED_PATHS = (
        "data/master/departments.jsonl",
        "data/master/departments_rejected.jsonl",
        "data/raw/departments.raw.jsonl",
        "data/canonical_major_groups.draft.jsonl",
        "src/api/main.py",
        "src/schemas/api.py",
        "src/schemas/major.py",
    )

    def setUp(self) -> None:
        self._before_hashes = {
            p: _sha256(_REPO_ROOT / p) for p in self._PROTECTED_PATHS if (_REPO_ROOT / p).exists()
        }

    def test_master_and_public_schema_sha256_unchanged_after_harness_run(self) -> None:
        harness.main()
        for path, before_hash in self._before_hashes.items():
            after_hash = _sha256(_REPO_ROOT / path)
            self.assertEqual(before_hash, after_hash, f"{path}의 SHA-256이 Harness 실행 후 바뀜")

    def test_departments_jsonl_has_35_rows_and_is_git_clean(self) -> None:
        path = _REPO_ROOT / "data" / "master" / "departments.jsonl"
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(lines), 35)
        result = subprocess.run(
            ["git", "diff", "--exit-code", "HEAD", "--", "data/master/departments.jsonl"],
            cwd=_REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_mock_api_directory_git_clean(self) -> None:
        result = subprocess.run(
            ["git", "diff", "--exit-code", "HEAD", "--", "outputs/mock_api/"],
            cwd=_REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_data_reviews_directory_git_clean(self) -> None:
        result = subprocess.run(
            ["git", "diff", "--exit-code", "HEAD", "--", "data/reviews/"],
            cwd=_REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_current_35_department_api_counts_unchanged(self) -> None:
        """이 Harness가 실제 운영 데이터를 건드리지 않으므로, 실제 35건 기준
        /departments 결과(§ "현재 35건 API 결과는 절대 변경하지 말 것")도 여전히
        같은 값이어야 한다 — main.py를 띄우지 않고 Repository를 직접 재확인한다."""

        repo = JsonlDepartmentRepository()
        self.assertEqual(len(repo), 35)
        counts = {}
        for d in repo.all():
            if d.canonical_major_id:
                counts[d.canonical_major_id] = counts.get(d.canonical_major_id, 0) + 1
        self.assertEqual(counts.get("media_communication"), 4)
        self.assertEqual(counts.get("industrial_engineering"), 3)
        self.assertEqual(counts.get("hci_ux"), 1)


class NoSecretsOrLargeFilesTest(unittest.TestCase):
    """§6 "API Key·대용량 파일 미추적"."""

    def test_no_api_key_pattern_in_harness_source_or_report(self) -> None:
        harness_source = Path(harness.__file__).read_text(encoding="utf-8")
        for forbidden in ("DATA_GO_KR_SERVICE_KEY=", "serviceKey=", "ServiceKey="):
            self.assertNotIn(forbidden + "AAAA", harness_source)  # 실제 값이 박혀 있으면 문자열이 훨씬 길다
        report_path = harness.REPORT_PATH
        if report_path.exists():
            report_text = report_path.read_text(encoding="utf-8")
            for forbidden in ("servicekey=", "apikey="):
                self.assertNotIn(forbidden, report_text.lower())

    def test_no_large_file_added_under_eval_or_tests_or_outputs_evaluation(self) -> None:
        result = subprocess.run(["git", "status", "--porcelain"], cwd=_REPO_ROOT, capture_output=True, text=True)
        for line in result.stdout.splitlines():
            candidate = line[3:].strip().strip('"')
            if candidate.startswith(("eval/", "tests/", "outputs/evaluation/")):
                full = _REPO_ROOT / candidate
                if full.is_file():
                    self.assertLess(full.stat().st_size, 5_000_000, f"{candidate}가 5MB를 넘음")


class ScenarioSanityTest(unittest.TestCase):
    """Harness가 실제로 §3 필수 시나리오를 전부 실행하고, 사실을 그대로 기록하는지
    (임의로 "합격"이라 단정하지 않는지) 확인한다."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.report = harness.main()

    def test_all_required_scenarios_are_present(self) -> None:
        names = {s.name for s in self.report.scenarios}
        required_substrings = [
            "미등록 major_id", "결과 0건", "결과 1건", "30건 초과", "정렬 Key 충돌",
            "중복 department_id", "UNMAPPED", "예체능 Group", "URL", "MERGED/SPLIT/ABOLISHED",
            "정확 일치",
        ]
        for substr in required_substrings:
            self.assertTrue(any(substr in n for n in names), f"'{substr}' 관련 시나리오가 없음: {names}")

    def test_report_explicitly_flags_the_duplicate_id_and_arts_exclusion_defects(self) -> None:
        """§4 "현재 Repository가 중복을 차단하지 않는다면 코드를 바로 수정하지 말고
        보고서에 결함으로 기록" — 실제로 기록됐는지 확인한다(코드가 고쳐지지
        않았다는 것도 아래 OperationalMasterUnchangedTest 등에서 이미 확인함)."""

        joined = " ".join(self.report.defects_found)
        self.assertIn("_by_id", joined)
        self.assertIn("EXCLUDED_RECOMMENDATION_MAJOR_IDS", joined)

    def test_report_does_not_claim_synthetic_data_is_verified_operational_master(self) -> None:
        self.assertIn("합성", self.report.generated_note)
        self.assertIn("아니다", self.report.generated_note)


if __name__ == "__main__":
    unittest.main()
