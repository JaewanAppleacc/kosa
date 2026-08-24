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

        report1 = harness.main(write_report=False)
        snapshot1 = json.dumps(harness.comparable_snapshot(report1), ensure_ascii=False, sort_keys=True)
        report2 = harness.main(write_report=False)
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
        harness.main(write_report=False)
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
        harness.main(write_report=False)
        for path, before_hash in self._before_hashes.items():
            after_hash = _sha256(_REPO_ROOT / path)
            self.assertEqual(before_hash, after_hash, f"{path}의 SHA-256이 Harness 실행 후 바뀜")

    def test_departments_jsonl_has_1072_rows(self) -> None:
        """2026-08-25(a/national-master-promotion-final-wiring) §7: 전국 학과 1,072건
        Production Master 전환 이후 이 값은 더 이상 35(데모)가 아니다 — 기존 35건은
        `data/archive/departments_legacy_demo_35.jsonl`로 보존됐다(§3). "git-clean"
        조건은 이 승격 라운드 자체가 `data/master/departments.jsonl`을 바꾸는 커밋이라
        의미가 없어져 제거한다 — Harness가 이 파일을 추가로 건드리지 않는지는 위
        `test_master_and_public_schema_sha256_unchanged_after_harness_run`이 이미
        (하드코딩된 값이 아니라 실행 시점 SHA-256으로) 확인한다."""
        path = _REPO_ROOT / "data" / "master" / "departments.jsonl"
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(lines), 1072)

    def test_legacy_35_department_archive_exists_and_is_readonly(self) -> None:
        archive_path = _REPO_ROOT / "data" / "archive" / "departments_legacy_demo_35.jsonl"
        lines = [line for line in archive_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(lines), 35)

    def test_mock_api_directory_git_clean(self) -> None:
        # 2026-08-25 전국 학과 1,072건 Production Master 전환(a/national-master-
        # promotion-final-wiring) §7이 scripts/generate_mock_json.py를 다시 실행해
        # departments_normal.json·subgraph_normal.json을 의도적으로 새 Master 기준으로
        # 재생성했다(공개 OpenAPI Schema 자체는 byte-identical로 남아 있음을 별도로
        # 확인했다) — 이 클래스가 지키려는 "harness.main() 실행이 Mock을 건드리지
        # 않는다"와는 무관한 변경이라 diff 대상에서 뺀다.
        result = subprocess.run(
            [
                "git", "diff", "--exit-code", "HEAD", "--", "outputs/mock_api/",
                ":(exclude)outputs/mock_api/departments_normal.json",
                ":(exclude)outputs/mock_api/subgraph_normal.json",
            ],
            cwd=_REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    # 2026-08(a/final-mapping-review-closeout)가 사용자 최종 결정에 따라 이 5개
    # 파일에 실제 검수 결과를 기록했다 — 이 테스트가 실제로 지키려는 것은 "이 클래스
    # 위의 harness.main() 실행이 data/reviews/를 건드리지 않는다"이지 "브랜치의
    # data/reviews/ 전체가 영원히 git-clean이어야 한다"가 아니다. 그 5개만 제외하고
    # 나머지는 여전히 무변경이어야 한다.
    # 2026-08-25(a/final-integration-master-promotion §7)가 사용자 최종 결정("기존
    # 코멘트로 수정 요청된 문항을 제외하고 수정 완료된 질문은 모두 통과")에 따라
    # 12개 ContextPack 검수 상태 파일도 실제로 갱신했다 — 같은 이유로 허용 목록에
    # 추가한다.
    _INTENTIONALLY_FINALIZED_REVIEW_FILES = (
        "data/reviews/canonical_major_group_review_status.jsonl",
        "data/reviews/canonical_major_group_bridge_review_status.json",
        "data/reviews/canonical_major_group_bridge_scope_review_status.jsonl",
        "data/reviews/academyinfo_p1_classification_review_status.jsonl",
        "data/reviews/academyinfo_nce_middle_series_review_status.jsonl",
        "data/reviews/context_packs/art_design_review_status.json",
        "data/reviews/context_packs/business_review_status.json",
        "data/reviews/context_packs/cooking_review_status.json",
        "data/reviews/context_packs/fashion_beauty_review_status.json",
        "data/reviews/context_packs/history_humanities_review_status.json",
        "data/reviews/context_packs/law_politics_review_status.json",
        "data/reviews/context_packs/making_review_status.json",
        "data/reviews/context_packs/science_review_status.json",
        "data/reviews/context_packs/sports_review_status.json",
        "data/reviews/context_packs/travel_review_status.json",
        "data/reviews/context_packs/volunteer_review_status.json",
        "data/reviews/context_packs/writing_review_status.json",
    )

    def test_data_reviews_directory_git_clean(self) -> None:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--", "data/reviews/"],
            cwd=_REPO_ROOT, capture_output=True, text=True,
        )
        changed = [line[3:] for line in result.stdout.splitlines() if line.strip()]
        unexpected = [p for p in changed if p not in self._INTENTIONALLY_FINALIZED_REVIEW_FILES]
        self.assertEqual(unexpected, [], f"data/reviews/ 아래 의도하지 않은 변경: {unexpected}")

    def test_current_1072_department_api_counts_unchanged(self) -> None:
        """2026-08-25(a/national-master-promotion-final-wiring) §7: 전국 학과 1,072건
        승격 이후의 실제 /departments 기준값으로 갱신한다 — 옛 데모 35건 기준값
        (media_communication=4·industrial_engineering=3·hci_ux=1)은
        `data/archive/departments_legacy_demo_35.jsonl`에만 남아 있고 더 이상 이
        Harness가 건드리지 않는 실제 Repository 값이 아니다."""

        repo = JsonlDepartmentRepository()
        self.assertEqual(len(repo), 1072)
        counts = {}
        for d in repo.all():
            if d.canonical_major_id:
                counts[d.canonical_major_id] = counts.get(d.canonical_major_id, 0) + 1
        self.assertEqual(counts.get("business_administration"), 271)
        self.assertEqual(counts.get("media_communication"), 133)
        self.assertEqual(counts.get("life_science"), 134)
        self.assertEqual(counts.get("mechanical_engineering"), 114)
        self.assertEqual(counts.get("computer_science"), 209)
        self.assertEqual(counts.get("education"), 78)
        self.assertEqual(counts.get("industrial_engineering"), 53)
        self.assertEqual(counts.get("psychology"), 80)
        self.assertIsNone(counts.get("hci_ux"))
        self.assertIsNone(counts.get("design"))


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
        cls.report = harness.main(write_report=False)

    def test_all_required_scenarios_are_present(self) -> None:
        names = {s.name for s in self.report.scenarios}
        required_substrings = [
            "미등록 major_id", "결과 0건", "결과 1건", "30건 초과", "정렬 Key 충돌",
            "중복 department_id", "UNMAPPED", "예체능 Group", "URL", "MERGED/SPLIT/ABOLISHED",
            "정확 일치",
        ]
        for substr in required_substrings:
            self.assertTrue(any(substr in n for n in names), f"'{substr}' 관련 시나리오가 없음: {names}")

    def test_report_confirms_the_two_known_defects_are_now_fixed(self) -> None:
        """2026-08-24 후속 라운드(national-department-readiness 정합성 수정): 최초
        실측에서 발견했던 두 결함(중복 department_id 조용한 덮어쓰기,
        EXCLUDED_RECOMMENDATION_MAJOR_IDS 하드코딩이 새 42개 Group ID를 못 막음)이
        `src/repositories/department_repository.py`·`src/services/
        major_exploration_service.py`에서 실제로 고쳐졌다 — 이 Harness를 다시
        실행하면 그 두 시나리오가 더 이상 결함으로 잡히지 않아야 한다."""

        joined = " ".join(self.report.defects_found)
        self.assertNotIn("_by_id", joined)
        self.assertNotIn("EXCLUDED_RECOMMENDATION_MAJOR_IDS", joined)
        self.assertEqual(self.report.defects_found, [])

        by_name = {s.name: s for s in self.report.scenarios}
        fail_fast_scenario = next(s for s in self.report.scenarios if "Fail-Fast" in s.name)
        self.assertTrue(fail_fast_scenario.passed, fail_fast_scenario.detail)
        for arts_major_id in ("fine_arts_design", "music", "performing_media_arts", "sports_dance"):
            scenario = by_name[f"예체능 Group 혼입 — {arts_major_id}"]
            self.assertTrue(scenario.passed, scenario.detail)

    def test_report_does_not_claim_synthetic_data_is_verified_operational_master(self) -> None:
        self.assertIn("합성", self.report.generated_note)
        self.assertIn("아니다", self.report.generated_note)


if __name__ == "__main__":
    unittest.main()
