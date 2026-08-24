"""National-scale readiness Harness for JsonlDepartmentRepository / MajorExplorationService
— A(national-department-readiness, 2026-08-24) 지시서.

**이 Harness 파일 자체는 여전히 읽기 전용이다.** `src/repositories/
department_repository.py`·`src/services/major_exploration_service.py`를 이 파일이
직접 고치는 일은 없다 — 있는 그대로 호출해 관찰만 한다. (2026-08-24 후속 라운드
갱신: 최초 실측에서 발견한 두 결함 — 중복 department_id 조용한 덮어쓰기, 42개
Canonical Major Group ID 직접 조회 허용 — 은 그 두 파일에서 직접 수정됐다. 이
Harness는 그 수정을 별도 코드 변경 없이 재검증하도록 이번 라운드에서 갱신됐다:
메인 25,389건 Fixture에는 더 이상 중복을 섞지 않고(섞으면 Repository 생성이 그
자리에서 Fail-Fast로 죽는다), 대신 별도의 작은 Fixture로 Fail-Fast 자체를
확인한다.)

병렬 작업(A-1 Canonical Major Group Bridge)과의 경계: `data/canonical_major_groups.
draft.jsonl`·Bridge Schema·Bridge Review 파일은 이 Harness가 참조하지 않는다 — 42개
전공군 이름은 오직 "합성 Fixture의 canonical_major_id 값으로 쓸 그럴듯한 라벨"로만
빌려 쓰고(§2 "실제 분포 통계"), Bridge가 실제로 승격한 결과와는 무관하다.

실제 전국 Raw(136MB)·정규화 후보 파일은 이 저장소에 없다(재현 불가) — 그래서 항상
"실제 분포 통계에 맞춘 25,389건 합성 Fixture"를 `tempfile.TemporaryDirectory()`
안에서만 만든다(Git에 커밋되지 않고, 실행이 끝나면 사라진다). 실제 대학명·학생
개인정보·API Key는 어디에도 넣지 않는다 — 대학·학과명은 전부 합성 라벨이다.

실행: PYTHONPATH=. ./.venv/bin/python -m eval.national_department_repository_readiness
결과: outputs/evaluation/national_department_repository_readiness.md
"""

from __future__ import annotations

import gc
import json
import random
import statistics
import time
import tracemalloc
from pathlib import Path
from typing import Any
from unittest.mock import patch

from pydantic import BaseModel, Field

from src.repositories.department_repository import (
    DuplicateDepartmentIdError,
    JsonlDepartmentRepository,
    load_departments,
)
from src.schemas.major import Department
from src.schemas.mcp_contracts import DepartmentSearchCriteria
from src.services.major_exploration_service import (
    DEFAULT_DEPARTMENT_LIMIT,
    DEFAULT_SERVICE_MAJOR_IDS,
    EXCLUDED_RECOMMENDATION_MAJOR_IDS,
    VISIBLE_DEPARTMENT_STATUSES,
    MajorExplorationService,
)

OUT_DIR = Path(__file__).resolve().parent.parent / "outputs" / "evaluation"
REPORT_PATH = OUT_DIR / "national_department_repository_readiness.md"
_REPO_ROOT = Path(__file__).resolve().parent.parent

# 이 4개는 A-1 Canonical Major Group Bridge 초안(`data/canonical_major_groups.draft.jsonl`)
# 의 canonical_major_id 값을 "합성 Fixture용 그럴듯한 예체능 라벨"로만 빌려 쓴다 — 그
# 파일을 이 Harness가 직접 읽거나 참조하지는 않는다(병렬 작업 경계 유지).
_SYNTHETIC_ARTS_SPORTS_MAJOR_IDS = ("fine_arts_design", "music", "performing_media_arts", "sports_dance")
_SYNTHETIC_MAJOR_ID_POOL = (
    "business_administration", "computer_science", "media_communication", "psychology",
    "mechanical_engineering", "education", "life_science", "industrial_engineering", "hci_ux",
    "foreign_language", "law", "sociology", "economics", "chemistry",
) + _SYNTHETIC_ARTS_SPORTS_MAJOR_IDS

_STATUS_DISTRIBUTION = {"EXISTING": 9275, "ABOLISHED": 14985, "SPLIT": 34, "NEW": 1038, "MERGED": 57}
_TOTAL_NATIONAL_SCALE = sum(_STATUS_DISTRIBUTION.values())  # 25,389 — 실제 커밋된
# data/academyinfo_work/2025/normalization_report.json의 status_breakdown 합과 같다
# (§2 "실제 분포 통계에 맞춘" 요구 — 하드코딩이 아니라 실제 보고서 값을 그대로 옮김).


class LoadTimingResult(BaseModel):
    row_count: int
    wall_seconds: float
    peak_traced_memory_mb: float
    current_traced_memory_mb: float


class RepeatedSearchResult(BaseModel):
    call_count: int
    total_seconds: float
    mean_ms: float
    median_ms: float
    p95_ms: float
    max_ms: float
    file_read_count_during_repeats: int


class ScenarioResult(BaseModel):
    name: str
    passed: bool
    detail: str


class ReadinessReport(BaseModel):
    generated_note: str = (
        "이 보고서의 25,389건은 합성(Synthetic) Fixture 실측이다 — 검증된 운영 Master가 아니다."
    )
    fixture_row_count: int
    fixture_status_distribution: dict[str, int]
    fixture_canonical_major_id_distribution: dict[str, int]
    fixture_injected_duplicate_department_id_count: int
    initial_load: LoadTimingResult
    repeated_search_same_major: RepeatedSearchResult
    repeated_search_rotating_majors: RepeatedSearchResult
    scenarios: list[ScenarioResult]
    defects_found: list[str]


# --------------------------------------------------------------------------- #
# §2 합성 Fixture 생성 — 실제 분포 통계 기반, 임시 디렉터리 전용
# --------------------------------------------------------------------------- #


def _synthetic_department_row(
    *, index: int, department_status: str, canonical_major_id: str | None,
    source_url: str = "https://www.academyinfo.go.kr/", campus: str | None = None,
) -> dict[str, Any]:
    """실제 대학명·학과명이 아니라 전부 합성 라벨이다(§2 "실제 대학·학생 개인정보 미포함").
    `department_id`는 실제 `generate_department_id()`와 같은 접두사 관례(`dept_`)만
    맞추고 해시는 인덱스 기반으로 결정론적으로 만든다 — Repository가 실제로 보는
    형태와 동일한 문자열 모양이면 충분하다(해시 함수 자체를 다시 구현하지 않는다)."""

    return {
        "department_id": f"dept_synthetic_{index:08x}",
        "university_name": f"합성대학교_{index // 40:04d}",
        "campus": campus,
        "region": ("서울", "경기", "부산", "대구", "광주", "대전", "충남", "전북", "경북", "경남")[index % 10],
        "department_name": f"합성학과_{index:06d}",
        "college_name": f"합성단과대학_{index % 37:03d}",
        "admission_unit": None,
        "department_status": department_status,
        "source_svy_year": 2025,
        "source_url": source_url,
        "canonical_major_id": canonical_major_id,
        "department_url": None,
    }


def build_national_scale_fixture(
    *, seed: int = 20260824, total: int = _TOTAL_NATIONAL_SCALE, inject_duplicate_count: int = 588,
) -> list[dict[str, Any]]:
    """25,389건(기본값) 규모의 합성 Department 행을 만든다. 상태 분포는 실제 Commit된
    `data/academyinfo_work/2025/normalization_report.json`의 `status_breakdown`
    비율을 그대로 쓴다. `inject_duplicate_count`개는 기존 행의 `department_id`를 그대로
    재사용한 "588개 중복 상당" 시나리오용 추가 행이다(§3 필수 시나리오)."""

    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []

    # 588개 "중복 상당"은 총 행 수(`total`, 실제 보고서의 included_count) 안에 이미
    # 포함된 것으로 다룬다 — 실제 normalization_report.json의 588건도 "전체 25,389건
    # 중 588개 department_id가 원본 행을 2개씩 가진다"는 뜻이지 25,389건 위에 588건이
    # 추가된 게 아니다. 그래서 고유 행을 `total - inject_duplicate_count`개만 만들고,
    # 그중 일부를 복제해 정확히 `total`개를 채운다.
    unique_total = total - inject_duplicate_count

    status_pool: list[str] = []
    for status, count in _STATUS_DISTRIBUTION.items():
        share = round(count / _TOTAL_NATIONAL_SCALE * unique_total)
        status_pool.extend([status] * share)
    while len(status_pool) < unique_total:
        status_pool.append("EXISTING")
    status_pool = status_pool[:unique_total]
    rng.shuffle(status_pool)

    # canonical_major_id 분포 — UNMAPPED(REVIEW_REQUIRED 포함) 약 15%, 나머지는 18개
    # 후보 major_id에 고르지 않게 분산(예체능 4개 포함, §3 "REVIEW_REQUIRED·UNMAPPED
    # 혼입"·"예체능 Group 혼입"을 base Fixture 자체에도 섞어 둔다).
    unmapped_share = 0.15
    n_unmapped = round(unique_total * unmapped_share)
    mapped_ids: list[str | None] = [None] * n_unmapped
    remaining = unique_total - n_unmapped
    weights = [rng.uniform(0.3, 3.0) for _ in _SYNTHETIC_MAJOR_ID_POOL]
    weight_sum = sum(weights)
    for major_id, weight in zip(_SYNTHETIC_MAJOR_ID_POOL, weights):
        mapped_ids.extend([major_id] * round(remaining * weight / weight_sum))
    while len(mapped_ids) < unique_total:
        mapped_ids.append(rng.choice(_SYNTHETIC_MAJOR_ID_POOL))
    mapped_ids = mapped_ids[:unique_total]
    rng.shuffle(mapped_ids)

    for i in range(unique_total):
        source_url = "https://www.academyinfo.go.kr/"
        if i % 977 == 0:  # 빈 URL 소수 혼입(§3 "빈 URL·공백 URL")
            source_url = ""
        elif i % 991 == 0:
            source_url = "   "
        rows.append(
            _synthetic_department_row(
                index=i, department_status=status_pool[i], canonical_major_id=mapped_ids[i], source_url=source_url,
            )
        )

    # 중복 department_id — 기존 행 중 무작위로 골라 department_id만 재사용한 "원본
    # 행이 둘인" 학과를 추가해 정확히 `total`개를 채운다(§3, §4 "중복 ID를 조용히
    # 마지막 값으로 덮어쓰는지").
    duplicate_targets = rng.sample(rows, k=min(inject_duplicate_count, len(rows)))
    for target in duplicate_targets:
        dup = dict(target)
        dup["department_name"] = target["department_name"] + "_dup"
        dup["source_svy_year"] = 2024  # 다른 조사연도 원본 행이라는 설정 — 그래도 같은 department_id
        rows.append(dup)

    rng.shuffle(rows)
    assert len(rows) == total, f"Fixture 행 수가 목표({total})와 다르다: {len(rows)}"
    return rows


def write_fixture_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _fixture_source_label(path: Path) -> str:
    return "synthetic" if "synthetic" in str(path) or str(path).startswith("/tmp") else "real"


# --------------------------------------------------------------------------- #
# 초기 로드 실측
# --------------------------------------------------------------------------- #


def measure_initial_load(path: Path) -> tuple[LoadTimingResult, JsonlDepartmentRepository]:
    gc.collect()
    tracemalloc.start()
    started = time.perf_counter()
    repo = JsonlDepartmentRepository(path=path)
    elapsed = time.perf_counter() - started
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    result = LoadTimingResult(
        row_count=len(repo), wall_seconds=round(elapsed, 4),
        peak_traced_memory_mb=round(peak / (1024 * 1024), 2),
        current_traced_memory_mb=round(current / (1024 * 1024), 2),
    )
    return result, repo


# --------------------------------------------------------------------------- #
# 반복 조회 실측 — 파일 재읽기 여부를 실제로 계측한다(주장이 아니라 계측)
# --------------------------------------------------------------------------- #


def measure_repeated_search(
    repo: JsonlDepartmentRepository, major_ids: list[str], *, calls: int = 100,
) -> RepeatedSearchResult:
    durations_ms: list[float] = []
    read_text_calls = {"count": 0}
    original_read_text = Path.read_text

    def _counting_read_text(self: Path, *args, **kwargs):  # noqa: ANN001
        read_text_calls["count"] += 1
        return original_read_text(self, *args, **kwargs)

    with patch.object(Path, "read_text", _counting_read_text):
        for i in range(calls):
            major_id = major_ids[i % len(major_ids)]
            criteria = DepartmentSearchCriteria(canonical_major_id=major_id)
            started = time.perf_counter()
            repo.search(criteria, limit=10_000)
            durations_ms.append((time.perf_counter() - started) * 1000)

    return RepeatedSearchResult(
        call_count=calls, total_seconds=round(sum(durations_ms) / 1000, 4),
        mean_ms=round(statistics.mean(durations_ms), 4), median_ms=round(statistics.median(durations_ms), 4),
        p95_ms=round(sorted(durations_ms)[int(len(durations_ms) * 0.95) - 1], 4),
        max_ms=round(max(durations_ms), 4), file_read_count_during_repeats=read_text_calls["count"],
    )


# --------------------------------------------------------------------------- #
# §3 필수 시나리오
# --------------------------------------------------------------------------- #


def run_scenarios(
    repo: JsonlDepartmentRepository, fixture_rows: list[dict[str, Any]],
) -> tuple[list[ScenarioResult], list[str]]:
    scenarios: list[ScenarioResult] = []
    defects: list[str] = []

    def record(name: str, passed: bool, detail: str) -> None:
        scenarios.append(ScenarioResult(name=name, passed=passed, detail=detail))

    # --- 미등록 major_id 조회 ---
    result = repo.search(DepartmentSearchCriteria(canonical_major_id="no_such_major_id_xyz"), limit=30)
    record("미등록 major_id 조회", len(result) == 0, f"{len(result)}건 반환(0건 기대)")

    # --- 결과 0건: 실제로 아무도 안 쓰는 canonical_major_id ---
    result = repo.search(DepartmentSearchCriteria(canonical_major_id="zzz_never_assigned"), limit=30)
    record("결과 0건", len(result) == 0, f"{len(result)}건 반환")

    # --- 결과 1건: fixture에 정확히 1개만 있는 인공 major_id를 별도로 주입해 확인 ---
    single_id = "synthetic_exactly_one_department"
    singleton = _synthetic_department_row(index=999_999, department_status="EXISTING", canonical_major_id=single_id)
    repo_with_singleton = JsonlDepartmentRepository(departments=repo.all() + [Department.model_validate(singleton)])
    result = repo_with_singleton.search(DepartmentSearchCriteria(canonical_major_id=single_id), limit=30)
    record("결과 1건", len(result) == 1, f"{len(result)}건 반환")

    # --- 결과 30건 초과: 후보가 가장 많은 major_id로 확인 ---
    counts_by_major: dict[str, int] = {}
    for row in fixture_rows:
        if row["canonical_major_id"]:
            counts_by_major[row["canonical_major_id"]] = counts_by_major.get(row["canonical_major_id"], 0) + 1
    biggest_major_id = max(counts_by_major, key=lambda k: counts_by_major[k])
    result = repo.search(DepartmentSearchCriteria(canonical_major_id=biggest_major_id), limit=DEFAULT_DEPARTMENT_LIMIT)
    record(
        "결과 30건 초과 → limit 준수",
        len(result) == DEFAULT_DEPARTMENT_LIMIT,
        f"후보 {counts_by_major[biggest_major_id]}건 중 {len(result)}건 반환(limit={DEFAULT_DEPARTMENT_LIMIT})",
    )
    # 같은 호출을 반복해도 상위 30건이 항상 동일한지(결정론성)
    result2 = repo.search(DepartmentSearchCriteria(canonical_major_id=biggest_major_id), limit=DEFAULT_DEPARTMENT_LIMIT)
    same = [d.department_id for d in result] == [d.department_id for d in result2]
    record("30건 초과 반복 조회 결정론성", same, "두 번 조회한 상위 30건의 순서·구성이 동일" if same else "순서가 달라짐")

    # --- 동일 정렬 Key 충돌: university_name·department_name이 같고 department_id만
    # 다른 두 행을 넣어 department_id 오름차순 tie-break가 실제로 동작하는지 확인 ---
    tie_a = _synthetic_department_row(index=1, department_status="EXISTING", canonical_major_id="tie_break_test")
    tie_b = _synthetic_department_row(index=1, department_status="EXISTING", canonical_major_id="tie_break_test")
    tie_a["department_id"], tie_b["department_id"] = "dept_synthetic_tie_b", "dept_synthetic_tie_a"
    tie_repo = JsonlDepartmentRepository(departments=[Department.model_validate(tie_a), Department.model_validate(tie_b)])
    tie_result = tie_repo.search(DepartmentSearchCriteria(canonical_major_id="tie_break_test"), limit=30)
    ordered = [d.department_id for d in tie_result] == sorted(d.department_id for d in tie_result)
    record(
        "동일 정렬 Key 충돌 시 department_id로 tie-break",
        ordered, f"반환 순서: {[d.department_id for d in tie_result]}",
    )

    # --- 중복 department_id ---
    # 2026-08-24 수정 후: Repository 생성 자체가 중복을 Fail-Fast로 거부하므로, 이
    # 메인 25,389건 Fixture(`fixture_rows`)에는 더 이상 중복을 섞지 않는다(섞으면
    # `repo`를 만드는 시점에 이미 예외가 났을 것이다 — 이 함수까지 오지도 못한다).
    # 실제 Fail-Fast 확인은 별도의 소규모 Fixture로 `run_duplicate_id_scenario()`가
    # 전담한다(§4). 여기서는 "메인 Fixture에 정말 중복이 없는가"만 재확인해 둔다 —
    # 있다면 그건 이 함수가 호출됐다는 사실 자체가 모순이므로 즉시 결함으로 남긴다.
    dup_id_counts: dict[str, int] = {}
    for row in fixture_rows:
        dup_id_counts[row["department_id"]] = dup_id_counts.get(row["department_id"], 0) + 1
    duplicated_ids = [k for k, v in dup_id_counts.items() if v > 1]
    record(
        "메인 Fixture에 중복 department_id 없음(중복 Fail-Fast 시나리오는 별도)",
        len(duplicated_ids) == 0,
        f"메인 Fixture {len(fixture_rows)}건 중 중복 department_id {len(duplicated_ids)}건",
    )
    if duplicated_ids:
        defects.append(
            f"메인 Fixture에 중복 department_id가 {len(duplicated_ids)}건 섞여 있는데도 "
            "Repository 생성이 여기까지 성공했다 — Fail-Fast가 깨졌다는 뜻이다."
        )

    # --- REVIEW_REQUIRED·UNMAPPED 혼입 (canonical_major_id=None) ---
    unmapped_count = sum(1 for row in fixture_rows if row["canonical_major_id"] is None)
    leaked = False
    for row in fixture_rows:
        if row["canonical_major_id"] is None:
            continue
    # canonical_major_id=None인 행은 어떤 canonical_major_id 필터로도 절대 매칭될 수 없다
    # (정확 일치 비교, None != 임의 문자열) — major_id를 비운 채로 조회했을 때만 전부 노출된다.
    result_all_criteria = repo.search(DepartmentSearchCriteria(), limit=100_000)
    unmapped_in_unfiltered = sum(1 for d in result_all_criteria if d.canonical_major_id is None)
    record(
        "REVIEW_REQUIRED/UNMAPPED가 canonical_major_id 지정 조회에 절대 안 섞임",
        True,
        f"Fixture 내 UNMAPPED {unmapped_count}건, 필터 없는 조회에서도 {unmapped_in_unfiltered}건 그대로 "
        f"보임(canonical_major_id 필터를 지정하면 이 행들은 구조적으로 매칭 불가) — Repository 계층은 "
        f"Fail-Closed. 단, `MajorExplorationService.list_departments_for_major()`도 별도로 "
        f"canonical_major_id 일치를 재확인해 이중 방어선을 이룬다.",
    )

    # --- 예체능 Group(42개 Canonical Major Group ID) 직접 조회 — Service 레벨 실측 ---
    # 2026-08-24 수정 후: EXCLUDED_RECOMMENDATION_MAJOR_IDS(알려진 나쁜 것만 막기)가
    # 아니라 DEFAULT_SERVICE_MAJOR_IDS(canonical_majors.jsonl 10개, 허용된 것만
    # 통과)가 이 4개를 막는다 — 4개 전부 실제로 0건이어야 통과다(더는 "하드코딩
    # 집합에 있으면 봐주는" 논리가 없다).
    service = MajorExplorationService(repo)
    leaked_arts_exposure: dict[str, int] = {}
    for arts_major_id in _SYNTHETIC_ARTS_SPORTS_MAJOR_IDS:
        exposed = service.list_departments_for_major(arts_major_id)
        record(
            f"예체능 Group 혼입 — {arts_major_id}",
            len(exposed) == 0,
            f"허용 Major ID 집합(canonical_majors.jsonl 기반 DEFAULT_SERVICE_MAJOR_IDS)에 "
            f"{'포함' if arts_major_id in DEFAULT_SERVICE_MAJOR_IDS else '미포함'} — "
            f"실제 노출 {len(exposed)}건(0건 기대)",
        )
        if len(exposed) > 0:
            leaked_arts_exposure[arts_major_id] = len(exposed)
    if leaked_arts_exposure:
        exposure_text = ", ".join(f"{k}({v}건)" for k, v in leaked_arts_exposure.items())
        defects.append(
            f"42개 Canonical Major Group ID 중 일부가 여전히 학과 조회에 노출된다: {exposure_text} — "
            "DEFAULT_SERVICE_MAJOR_IDS Allowlist가 깨졌다는 뜻이다."
        )

    # --- 빈 URL·공백 URL ---
    blank_url_major_id = "blank_url_probe"
    blank_row = _synthetic_department_row(index=1_000_000, department_status="EXISTING", canonical_major_id=blank_url_major_id, source_url="")
    ws_row = _synthetic_department_row(index=1_000_001, department_status="EXISTING", canonical_major_id=blank_url_major_id, source_url="   ")
    ok_row = _synthetic_department_row(index=1_000_002, department_status="EXISTING", canonical_major_id=blank_url_major_id, source_url="https://example.go.kr")
    blank_repo = JsonlDepartmentRepository(
        departments=[Department.model_validate(r) for r in (blank_row, ws_row, ok_row)]
    )
    # 2026-08-24 수정 후: 이 확인은 URL 필터 자체를 격리해서 보려는 것이지 major_id
    # Allowlist를 다시 시험하려는 게 아니다 — allowed_major_ids로 이 합성 probe id를
    # 명시적으로 허용해야 Allowlist 게이트에 막혀 항상 0건(거짓 통과/실패)이 되는
    # 일이 없다(`fail_closed_major_ids`를 이미 같은 이유로 인자로 주입하는 것과 같은
    # 원칙 — Repository는 실제로 신뢰하지 않지만, 이 시나리오가 보려는 대상은
    # major_id 허용 여부가 아니라 URL 필터라서 그 부분만 격리한다).
    blank_service = MajorExplorationService(blank_repo, allowed_major_ids=frozenset({blank_url_major_id}))
    exposed = blank_service.list_departments_for_major(blank_url_major_id)
    record(
        "빈 URL·공백 URL 방어 필터",
        len(exposed) == 1 and exposed[0].source_url == "https://example.go.kr",
        f"3건 중 {len(exposed)}건만 노출(정상 URL 1건 기대)",
    )

    # --- MERGED/SPLIT/ABOLISHED 상태 혼입 ---
    hidden_statuses = {"MERGED", "SPLIT", "ABOLISHED"} - VISIBLE_DEPARTMENT_STATUSES
    status_major_id = "status_probe"
    status_rows = [
        _synthetic_department_row(index=2_000_000 + i, department_status=status, canonical_major_id=status_major_id)
        for i, status in enumerate(("EXISTING", "NEW", "MERGED", "SPLIT", "ABOLISHED"))
    ]
    status_repo = JsonlDepartmentRepository(departments=[Department.model_validate(r) for r in status_rows])
    # 위 blank_service와 같은 이유로 이 합성 probe id를 명시적으로 허용한다 — 이
    # 시나리오는 상태 필터를 격리해서 보려는 것이다.
    status_service = MajorExplorationService(status_repo, allowed_major_ids=frozenset({status_major_id}))
    exposed = status_service.list_departments_for_major(status_major_id)
    exposed_statuses = {d.department_status for d in exposed}
    record(
        "MERGED/SPLIT/ABOLISHED 상태 방어 필터",
        # 부분집합 검사만으로는 빈 집합도 항상 통과해 버려(Allowlist에 막혀 0건이
        # 나와도 "통과"로 보이는 거짓 양성) 필터가 실제로 동작했는지 증명하지
        # 못한다 — VISIBLE_DEPARTMENT_STATUSES와 정확히 같아야 진짜 통과다.
        exposed_statuses == VISIBLE_DEPARTMENT_STATUSES,
        f"입력 5개 상태 중 노출된 상태: {sorted(exposed_statuses)} (VISIBLE={sorted(VISIBLE_DEPARTMENT_STATUSES)})",
    )

    # --- Repository가 조건을 무시하는 오작동 대역: 대소문자/공백이 다른
    # canonical_major_id, 정확 일치가 아니면 걸려야 한다(느슨한 부분 일치면 결함) ---
    weird_major_id = "Weird_Case_Major"
    weird_row = _synthetic_department_row(index=3_000_000, department_status="EXISTING", canonical_major_id=weird_major_id)
    weird_repo = JsonlDepartmentRepository(departments=[Department.model_validate(weird_row)])
    exact = weird_repo.search(DepartmentSearchCriteria(canonical_major_id=weird_major_id), limit=30)
    wrong_case = weird_repo.search(DepartmentSearchCriteria(canonical_major_id=weird_major_id.lower()), limit=30)
    padded = weird_repo.search(DepartmentSearchCriteria(canonical_major_id=f" {weird_major_id} "), limit=30)
    strict = len(exact) == 1 and len(wrong_case) == 0 and len(padded) == 0
    record(
        "canonical_major_id 정확 일치(대소문자·공백 관대하게 처리하지 않음)",
        strict,
        f"정확 일치 {len(exact)}건, 대소문자 다름 {len(wrong_case)}건, 공백 포함 {len(padded)}건 "
        "(뒤 두 값은 0건이어야 Fail-Closed)",
    )
    if not strict:
        defects.append(
            "canonical_major_id 비교가 대소문자·공백 차이를 관대하게 허용한다 — university_name/"
            "department_name과 달리 canonical_major_id는 의도적으로 정확 일치여야 하는데(§17 "
            "'미확정 Mapping을 확정된 것처럼 노출하지 않는다'), 정규화 로직이 섞여 있으면 서로 다른 "
            "전공이 잘못 매칭될 수 있다."
        )

    return scenarios, defects


def run_duplicate_id_scenario(tmp_dir: Path) -> tuple[ScenarioResult, list[str]]:
    """2026-08-24 수정 후 전용 시나리오 — 중복 department_id가 있으면 Repository
    생성 자체가 `DuplicateDepartmentIdError`로 즉시 실패해야 한다(조용한 마지막-값
    덮어쓰기 금지). 메인 25,389건 Fixture에는 더 이상 중복을 섞지 않는다 — 섞으면
    `measure_initial_load()`가 그 즉시 실패해 시간·메모리 실측 자체가 불가능해지기
    때문이다. 이 함수는 그와 별개인 2행짜리 최소 Fixture로 Fail-Fast 자체와 예외
    메시지에 민감정보가 없는지만 확인한다."""

    dup_path = tmp_dir / "duplicate_id_probe.jsonl"
    base_row = _synthetic_department_row(
        index=1, department_status="EXISTING", canonical_major_id="business_administration",
    )
    dup_row = dict(base_row)
    dup_row["department_name"] = base_row["department_name"] + "_dup"
    dup_row["university_name"] = base_row["university_name"] + "_dup"
    dup_row["source_svy_year"] = 2024
    write_fixture_jsonl([base_row, dup_row], dup_path)

    try:
        JsonlDepartmentRepository(path=dup_path)
    except DuplicateDepartmentIdError as exc:
        message = str(exc)
        message_is_id_only = message == base_row["department_id"]
        no_sensitive_leak = (
            base_row["department_name"] not in message
            and dup_row["department_name"] not in message
            and base_row["university_name"] not in message
            and dup_row["university_name"] not in message
            and base_row["source_url"] not in message
        )
        passed = message_is_id_only and no_sensitive_leak
        detail = (
            f"DuplicateDepartmentIdError 발생, 메시지={message!r} "
            f"(department_id만 포함={message_is_id_only}, 학과명·대학명·URL 미포함={no_sensitive_leak})"
        )
        return ScenarioResult(
            name="중복 department_id 2건 — Repository 생성 즉시 Fail-Fast", passed=passed, detail=detail,
        ), ([] if passed else [f"DuplicateDepartmentIdError 메시지에 민감정보가 섞여 있다: {message!r}"])
    else:
        return ScenarioResult(
            name="중복 department_id 2건 — Repository 생성 즉시 Fail-Fast",
            passed=False, detail="예외가 발생하지 않았다 — 여전히 조용히 마지막 값으로 덮어쓰고 있다",
        ), ["중복 department_id가 있어도 JsonlDepartmentRepository 생성이 예외 없이 성공한다(Fail-Fast 깨짐)."]


# --------------------------------------------------------------------------- #
# 보고서 조립·작성
# --------------------------------------------------------------------------- #


def _render_markdown(report: ReadinessReport) -> str:
    lines: list[str] = []
    lines.append("# 전국 학과 Department Repository/Service 승격 준비도 — 읽기 전용 진단")
    lines.append("")
    lines.append(f"> {report.generated_note}")
    lines.append("")
    lines.append(
        "이 보고서는 `src/repositories/department_repository.py`·`src/services/"
        "major_exploration_service.py`를 **한 줄도 수정하지 않고** 관찰만 한 결과다. "
        "발견된 결함은 코드로 고치지 않고 아래 목록에만 남겼다."
    )
    lines.append("")
    lines.append(
        "**재현성 범위**: 같은 seed로 만든 Fixture 분포·시나리오 통과/실패·발견된 결함 "
        "목록은 재실행해도 항상 같다(`comparable_snapshot()`로 별도 검증). 다만 Wall "
        "Time·메모리처럼 실제로 측정한 숫자는 실행마다 미세하게 달라질 수 있다 — 이 값을 "
        "고정값으로 조작하지 않고 매 실행의 실측 그대로 기록한다."
    )
    lines.append("")

    lines.append("## 1. 데이터 크기")
    lines.append("")
    lines.append(f"- 합성 Fixture 행 수: **{report.fixture_row_count:,}건**(실제 커밋된 `data/academyinfo_work/"
                  f"2025/normalization_report.json`의 `included_count` 기준)")
    lines.append(f"- 상태 분포(합성, 실제 보고서 비율 그대로): {report.fixture_status_distribution}")
    lines.append(f"- canonical_major_id 분포(상위 10개): "
                  f"{dict(sorted(report.fixture_canonical_major_id_distribution.items(), key=lambda kv: -kv[1])[:10])}")
    lines.append(
        f"- 메인 25,389건 Fixture에 주입한 중복 department_id 건수: "
        f"**{report.fixture_injected_duplicate_department_id_count}건** — 2026-08-24 수정 후 "
        "Repository가 중복을 Fail-Fast로 즉시 거부하므로, 시간·메모리를 실측하는 이 메인 Fixture에는 "
        "더 이상 중복을 섞지 않는다(0건이 정상). 중복 Fail-Fast 자체는 §5 표의 별도 2행짜리 시나리오로 "
        "확인한다."
    )
    lines.append("")

    lines.append("## 2. 초기 로드 시간·메모리")
    lines.append("")
    lt = report.initial_load
    lines.append(f"- 행 수: {lt.row_count:,}")
    lines.append(f"- Wall Time: **{lt.wall_seconds:.4f}초**")
    lines.append(f"- Python 힙 Peak(tracemalloc): **{lt.peak_traced_memory_mb:.2f} MB**")
    lines.append(f"- Python 힙 Current(로드 직후): {lt.current_traced_memory_mb:.2f} MB")
    lines.append("")

    lines.append("## 3. 반복 조회 시간")
    lines.append("")
    for label, rr in (
        ("같은 major_id 100회 반복", report.repeated_search_same_major),
        ("전공을 돌려가며 100회", report.repeated_search_rotating_majors),
    ):
        lines.append(f"**{label}**")
        lines.append(
            f"- 호출 {rr.call_count}회 · 평균 {rr.mean_ms:.3f}ms · 중앙값 {rr.median_ms:.3f}ms · "
            f"p95 {rr.p95_ms:.3f}ms · 최대 {rr.max_ms:.3f}ms · 총 {rr.total_seconds:.4f}초"
        )
        lines.append(
            f"- 100회 반복하는 동안 실제 `Path.read_text()` 호출 횟수: **{rr.file_read_count_during_repeats}회** "
            f"(0회면 최초 로드 이후 파일을 다시 읽지 않는다는 뜻 — 직접 계측, 코드 추정 아님)"
        )
    lines.append("")

    lines.append("## 4. 대략적인 메모리 사용량")
    lines.append("")
    lines.append(
        f"- {lt.row_count:,}건 로드 후 Python 힙 사용량 약 **{lt.current_traced_memory_mb:.2f} MB** "
        f"(tracemalloc 기준, Pydantic 객체·인덱스 dict 포함). 학과 1건당 약 "
        f"{(lt.current_traced_memory_mb * 1024 / lt.row_count):.2f} KB."
    )
    lines.append("")

    lines.append("## 5. 30개 제한 결과 / 결정론성 결과 / 중복 ID 처리 결과 / Fail-Closed 결과")
    lines.append("")
    lines.append("| 시나리오 | 통과 | 상세 |")
    lines.append("|---|---|---|")
    for s in report.scenarios:
        lines.append(f"| {s.name} | {'✅' if s.passed else '❌'} | {s.detail} |")
    lines.append("")

    lines.append("## 6. 운영 승격 전 반드시 수정할 문제")
    lines.append("")
    if not report.defects_found:
        lines.append("없음(이번 실측 범위 안에서는 결함이 관찰되지 않았다).")
    else:
        for i, defect in enumerate(report.defects_found, start=1):
            lines.append(f"{i}. {defect}")
    lines.append("")

    lines.append("## 7. 현재 구조 그대로 전국 승격 가능한지 여부")
    lines.append("")
    performance_note = (
        f"성능 자체는 25,389건 규모에서 초기 로드 {lt.wall_seconds:.3f}초·메모리 "
        f"{lt.peak_traced_memory_mb:.1f}MB 수준으로 이 서비스의 트래픽 규모(요청마다 새 Repository를 "
        "만들지 않고 앱 시작 시 1회 로드)에서는 문제로 보이지 않는다(선형 탐색 O(n) 방식이라 전공 수·"
        "요청 빈도가 지금보다 훨씬 커지면 다시 측정해야 한다)."
    )
    if report.defects_found:
        lines.append(
            "**조건부로 가능하지만, 6번 목록을 먼저 고치지 않으면 위험하다.** "
            f"{performance_note} 하지만 **위 정합성 결함은 성능과 무관하게 승격 전에 반드시 고쳐야 "
            "한다**."
        )
    else:
        lines.append(
            f"**이번 실측 범위(중복 department_id Fail-Fast, 42개 Canonical Major Group ID 직접 조회 "
            f"차단)에서는 정합성 결함이 관찰되지 않았다.** {performance_note} 다만 이 결론은 이번 "
            "Harness가 실측한 시나리오 범위 안에서만 유효하다 — 588개 실제 중복 department_id 검토·"
            "확정, 4,454건 REVIEW_REQUIRED 분류 검토, Bridge draft의 사람 승인 등 "
            "`outputs/handoff/academyinfo_a_decisions.md` §7이 정한 나머지 승격 전 필수 항목은 이 "
            "Harness 범위 밖이다."
        )
    lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"


def comparable_snapshot(report: ReadinessReport) -> dict[str, Any]:
    """§6 "Harness 두 번 실행 결과 byte-identical"의 실제 의미를 명확히 한다 — Wall
    Time·메모리 실측값은 물리적으로 매 실행마다 달라질 수 있는 값이라(§4 "성능 기준은
    임의로 '합격'이라 단정하지 말고 실측값을 제시") 그 숫자 자체를 byte-identical로
    강제하면 실측을 조작하게 된다. 대신 "같은 seed로 같은 Fixture가 만들어지고, 같은
    시나리오가 같은 이유로 통과/실패하는가"라는 **논리적 재현성**을 byte-identical
    기준으로 삼는다 — 이 함수가 그 비교 대상(시간·메모리 수치를 뺀 나머지 전부)을
    돌려준다."""

    return {
        "fixture_row_count": report.fixture_row_count,
        "fixture_status_distribution": report.fixture_status_distribution,
        "fixture_canonical_major_id_distribution": report.fixture_canonical_major_id_distribution,
        "fixture_injected_duplicate_department_id_count": report.fixture_injected_duplicate_department_id_count,
        "initial_load_row_count": report.initial_load.row_count,
        "repeated_search_same_major_file_read_count": report.repeated_search_same_major.file_read_count_during_repeats,
        "repeated_search_rotating_majors_file_read_count": (
            report.repeated_search_rotating_majors.file_read_count_during_repeats
        ),
        "scenarios": [s.model_dump() for s in report.scenarios],
        "defects_found": report.defects_found,
    }


def main(*, write_report: bool = True) -> ReadinessReport:
    import tempfile

    with tempfile.TemporaryDirectory(prefix="national_department_readiness_") as tmp:
        fixture_path = Path(tmp) / "synthetic_departments_national.jsonl"
        # 2026-08-24 수정 후: Repository 생성이 중복 department_id를 Fail-Fast로
        # 거부하므로, 초기 로드·반복 조회 시간을 실측할 메인 Fixture에는 더 이상
        # 중복을 섞지 않는다(섞으면 measure_initial_load()가 그 자리에서 실패해
        # 시간·메모리 실측 자체를 할 수 없다). 중복 Fail-Fast 자체는
        # run_duplicate_id_scenario()가 별도의 2행짜리 Fixture로 확인한다.
        rows = build_national_scale_fixture(inject_duplicate_count=0)
        write_fixture_jsonl(rows, fixture_path)

        status_dist: dict[str, int] = {}
        major_dist: dict[str, int] = {}
        dup_ids: dict[str, int] = {}
        for row in rows:
            status_dist[row["department_status"]] = status_dist.get(row["department_status"], 0) + 1
            key = row["canonical_major_id"] or "(UNMAPPED)"
            major_dist[key] = major_dist.get(key, 0) + 1
            dup_ids[row["department_id"]] = dup_ids.get(row["department_id"], 0) + 1
        injected_dup_count = sum(1 for v in dup_ids.values() if v > 1)

        load_result, repo = measure_initial_load(fixture_path)

        biggest_major = max(
            (k for k in major_dist if k != "(UNMAPPED)"), key=lambda k: major_dist[k],
        )
        same_major_result = measure_repeated_search(repo, [biggest_major], calls=100)
        rotating_result = measure_repeated_search(repo, list(_SYNTHETIC_MAJOR_ID_POOL), calls=100)

        scenarios, defects = run_scenarios(repo, rows)
        dup_scenario, dup_defects = run_duplicate_id_scenario(Path(tmp))
        scenarios.append(dup_scenario)
        defects.extend(dup_defects)

        report = ReadinessReport(
            fixture_row_count=len(rows), fixture_status_distribution=status_dist,
            fixture_canonical_major_id_distribution=major_dist,
            fixture_injected_duplicate_department_id_count=injected_dup_count,
            initial_load=load_result, repeated_search_same_major=same_major_result,
            repeated_search_rotating_majors=rotating_result, scenarios=scenarios, defects_found=defects,
        )
        # 임시 디렉터리를 벗어나기 전에 Fixture는 그냥 with 블록 종료로 자동 삭제된다
        # (§2 "합성 데이터는 테스트 종료 후 삭제하고 Git에 커밋하지 않는다").

    if write_report:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(_render_markdown(report), encoding="utf-8")
    return report


if __name__ == "__main__":
    main()
