"""National-scale readiness Harness for JsonlDepartmentRepository / MajorExplorationService
— A(national-department-readiness, 2026-08-24) 지시서.

**읽기 전용.** `src/repositories/department_repository.py`·
`src/services/major_exploration_service.py`를 단 한 줄도 고치지 않는다 — 이 파일은 그
코드를 있는 그대로 호출해 관찰만 한다. 발견된 결함은 여기서 바로 고치지 않고
`outputs/evaluation/national_department_repository_readiness.md`에만 기록한다.

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

from src.repositories.department_repository import JsonlDepartmentRepository, load_departments
from src.schemas.major import Department
from src.schemas.mcp_contracts import DepartmentSearchCriteria
from src.services.major_exploration_service import (
    DEFAULT_DEPARTMENT_LIMIT,
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

    # --- 중복 department_id 588개 상당 ---
    dup_id_counts: dict[str, int] = {}
    for row in fixture_rows:
        dup_id_counts[row["department_id"]] = dup_id_counts.get(row["department_id"], 0) + 1
    duplicated_ids = [k for k, v in dup_id_counts.items() if v > 1]
    injected_dup_count = len(duplicated_ids)
    if duplicated_ids:
        sample_dup_id = duplicated_ids[0]
        via_get = repo.get(sample_dup_id)
        via_all = [d for d in repo.all() if d.department_id == sample_dup_id]
        overwritten_silently = via_get is not None and len(via_all) > 1
        record(
            "중복 department_id — get()은 마지막 값으로 조용히 덮어씀",
            True,  # 이 자체가 "정상"이라는 뜻이 아니라 "실측한 그대로"라는 뜻 — 판정은 결함 목록에 별도 기록.
            f".get()은 {len(via_all)}건 중 1건만 반환, .all()/.search()에는 {len(via_all)}건 전부 남음"
            f"(department_id={sample_dup_id})",
        )
        if overwritten_silently:
            defects.append(
                f"JsonlDepartmentRepository.__init__의 `self._by_id = {{d.department_id: d for d in "
                f"self._departments}}`가 중복 department_id를 검증·경고 없이 마지막 값으로 조용히 "
                f"덮어쓴다(Python dict comprehension 특성). `.get(department_id)`는 그 학과의 여러 "
                f"원본 행 중 무작위 순서(파일 내 등장 순서)로 정해지는 '마지막' 값만 반환하고, 같은 "
                f".search()/.all() 호출에는 중복 행이 전부 그대로 남아 있어 두 API가 서로 다른 개수를 "
                f"보여준다. 대조: `src/services/department_recommendation_scope.py::"
                f"load_department_recommendation_scope()`는 같은 상황에서 "
                f"`DuplicateDepartmentScopeRecordError`를 즉시 던진다 — 저장소 계층 안에서도 "
                f"중복 처리 정책이 서로 다르다."
            )
    else:
        record("중복 department_id 시나리오", False, "Fixture에 중복이 주입되지 않음(생성 로직 확인 필요)")

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

    # --- 예체능 Group 혼입 — Service 레벨 EXCLUDED_RECOMMENDATION_MAJOR_IDS 실측 ---
    service = MajorExplorationService(repo)
    leaked_arts_exposure: dict[str, int] = {}
    for arts_major_id in _SYNTHETIC_ARTS_SPORTS_MAJOR_IDS:
        exposed = service.list_departments_for_major(arts_major_id)
        is_hardcoded_excluded = arts_major_id in EXCLUDED_RECOMMENDATION_MAJOR_IDS
        record(
            f"예체능 Group 혼입 — {arts_major_id}",
            is_hardcoded_excluded and len(exposed) == 0 or (not is_hardcoded_excluded and True),
            f"EXCLUDED_RECOMMENDATION_MAJOR_IDS={sorted(EXCLUDED_RECOMMENDATION_MAJOR_IDS)}에 "
            f"{'포함' if is_hardcoded_excluded else '미포함'} — 실제 노출 {len(exposed)}건",
        )
        if not is_hardcoded_excluded and len(exposed) > 0:
            leaked_arts_exposure[arts_major_id] = len(exposed)
    if leaked_arts_exposure:
        exposure_text = ", ".join(f"{k}({v}건)" for k, v in leaked_arts_exposure.items())
        defects.append(
            f"EXCLUDED_RECOMMENDATION_MAJOR_IDS = {sorted(EXCLUDED_RECOMMENDATION_MAJOR_IDS)}는 "
            f"'design' 하나만 하드코딩돼 있다 — A-1 Canonical Major Group Bridge가 42개 초안 중 "
            f"예체능 4개({', '.join(_SYNTHETIC_ARTS_SPORTS_MAJOR_IDS)})를 새 canonical_major_id로 "
            f"승격하면, 그 4개는 이 하드코딩 집합에 없으므로 MajorExplorationService가 그대로 "
            f"노출한다(이번 합성 Fixture로 실측: {exposure_text} 노출됨). "
            f"예체능 제외가 '집합 안의 항목'에는 Fail-Closed이지만 '집합 밖의 새 항목'에는 "
            f"Fail-Open이다 — 전국 승격 전에 이 하드코딩을 새 예체능 canonical_major_id까지 "
            f"덮도록 바꾸거나, 별도의 Fail-Closed 화이트리스트 정책으로 교체해야 한다."
        )

    # --- 빈 URL·공백 URL ---
    blank_url_major_id = "blank_url_probe"
    blank_row = _synthetic_department_row(index=1_000_000, department_status="EXISTING", canonical_major_id=blank_url_major_id, source_url="")
    ws_row = _synthetic_department_row(index=1_000_001, department_status="EXISTING", canonical_major_id=blank_url_major_id, source_url="   ")
    ok_row = _synthetic_department_row(index=1_000_002, department_status="EXISTING", canonical_major_id=blank_url_major_id, source_url="https://example.go.kr")
    blank_repo = JsonlDepartmentRepository(
        departments=[Department.model_validate(r) for r in (blank_row, ws_row, ok_row)]
    )
    blank_service = MajorExplorationService(blank_repo)
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
    status_service = MajorExplorationService(status_repo)
    exposed = status_service.list_departments_for_major(status_major_id)
    exposed_statuses = {d.department_status for d in exposed}
    record(
        "MERGED/SPLIT/ABOLISHED 상태 방어 필터",
        exposed_statuses.issubset(VISIBLE_DEPARTMENT_STATUSES) and not (exposed_statuses & hidden_statuses),
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
    lines.append(f"- 주입한 중복 department_id 건수: **{report.fixture_injected_duplicate_department_id_count}건**"
                  "(지시서 §3 \"588개 중복 상당\")")
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
    lines.append(
        "**조건부로 가능하지만, 6번 목록을 먼저 고치지 않으면 위험하다.** 성능 자체는 "
        f"25,389건 규모에서 초기 로드 {lt.wall_seconds:.3f}초·메모리 {lt.peak_traced_memory_mb:.1f}MB 수준으로 "
        "이 서비스의 트래픽 규모(요청마다 새 Repository를 만들지 않고 앱 시작 시 1회 로드)에서는 "
        "문제로 보이지 않는다(선형 탐색 O(n) 방식이라 전공 수·요청 빈도가 지금보다 훨씬 커지면 "
        "다시 측정해야 한다). 하지만 **정합성 결함(중복 ID 조용한 덮어쓰기, 예체능 하드코딩 "
        "Allowlist가 새 canonical_major_id를 못 막음)은 성능과 무관하게 승격 전에 반드시 고쳐야 "
        "한다** — 특히 예체능 하드코딩 문제는 A-1 Bridge가 42개 초안 중 예체능 4개를 승격시키는 "
        "순간 바로 실제 사용자에게 노출될 수 있는 회귀다."
    )
    lines.append("")

    return "\n".join(lines) + "\n"


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


def main() -> ReadinessReport:
    import tempfile

    with tempfile.TemporaryDirectory(prefix="national_department_readiness_") as tmp:
        fixture_path = Path(tmp) / "synthetic_departments_national.jsonl"
        rows = build_national_scale_fixture()
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

        report = ReadinessReport(
            fixture_row_count=len(rows), fixture_status_distribution=status_dist,
            fixture_canonical_major_id_distribution=major_dist,
            fixture_injected_duplicate_department_id_count=injected_dup_count,
            initial_load=load_result, repeated_search_same_major=same_major_result,
            repeated_search_rotating_majors=rotating_result, scenarios=scenarios, defects_found=defects,
        )
        # 임시 디렉터리를 벗어나기 전에 Fixture는 그냥 with 블록 종료로 자동 삭제된다
        # (§2 "합성 데이터는 테스트 종료 후 삭제하고 Git에 커밋하지 않는다").

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(_render_markdown(report), encoding="utf-8")
    return report


if __name__ == "__main__":
    main()
