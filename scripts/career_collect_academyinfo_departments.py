"""대학알리미 전국 학과 수집기 — 지시서 §4·§5.

원본을 `data/academyinfo_raw/<조사연도>/`에 그대로 쌓는다. 기존 `data/raw/`·`data/master/`는
건드리지 않는다(§1: 별도 수집 디렉터리에서 감사 후 승격).

설계 근거는 `rationale_c/07-academyinfo-collection.md`.

실행:
    python scripts/career_collect_academyinfo_departments.py --survey-year 2025
    python scripts/career_collect_academyinfo_departments.py --dry-run --max-universities 3
    python scripts/career_collect_academyinfo_departments.py --resume
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from scripts.career_console import use_utf8_stdout  # noqa: E402
from src.data_sources.academyinfo_year import (  # noqa: E402
    PUBLIC_API_METADATA_MODIFIED_AT,
    select_survey_year,
)
from src.data_sources.academyinfo_client import (  # noqa: E402
    ACADEMYINFO_DATASET_URL,
    CODE_TABLES,
    AcademyInfoClient,
    AcademyInfoError,
    QuotaError,
    RetryPolicy,
)

COLLECTOR_VERSION = "academyinfo_collector_v0.1"

# 교과목 전문은 학과 한 건이 수만 자다(연세대 교양과 실측). 본 레코드에 두면 원본 JSONL이
# 수백 MB가 되고 Diff도 못 읽는다 — 별도 파일로 떼고 본 레코드엔 해시·길이만 남긴다.
BULK_TEXT_FIELDS = ("edcCrseLtrCtnt",)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _git_sha() -> str:
    """Manifest에 수집기 Git SHA를 남긴다 (§5)."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical_json(row: dict[str, Any]) -> str:
    """키 정렬 + 고정 구분자. 같은 입력이면 Byte-identical해야 한다 (§4)."""
    return json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_jsonl_gz(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    # mtime=0 + filename="": gzip 헤더에는 기본적으로 수집 시각과 **파일명**이 들어간다.
    # 그대로 두면 같은 내용을 다른 경로에 쓰거나 파일명을 바꾸기만 해도 Hash가 달라져,
    # §10 "동일 입력 재빌드 Byte-identical" 검사가 내용이 아니라 경로를 검사하게 된다.
    # 임시 파일에 다 쓰고 나서 교체한다. 대상 파일에 바로 쓰면 그 순간 프로세스가 죽었을 때
    # **잘린 gz가 남고**, Checkpoint는 '여기까지 완료'라는데 파일은 못 읽는 상태가 된다 —
    # --resume이 그 파일을 읽다 EOFError로 죽는다. 실제 수집 중 이 상태를 관측했다.
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0, filename="") as raw:
            for row in rows:
                raw.write((_canonical_json(row) + "\n").encode("utf-8"))
                count += 1
    tmp.replace(path)
    return count


def read_jsonl_gz(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


@dataclass
class Paths:
    raw: Path
    work: Path

    @classmethod
    def for_year(cls, year: int, output_dir: Path) -> "Paths":
        return cls(raw=output_dir / "academyinfo_raw" / str(year), work=output_dir / "academyinfo_work" / str(year))

    @property
    def universities(self) -> Path:
        return self.raw / "universities.raw.jsonl.gz"

    @property
    def departments(self) -> Path:
        return self.raw / "departments.raw.jsonl.gz"

    @property
    def curricula(self) -> Path:
        return self.raw / "curricula"

    @property
    def codes(self) -> Path:
        return self.raw / "codes"

    @property
    def checkpoint(self) -> Path:
        return self.raw / "collection_checkpoint.json"

    @property
    def errors(self) -> Path:
        return self.raw / "collection_errors.jsonl"

    @property
    def manifest(self) -> Path:
        return self.raw / "collection_manifest.json"


def load_checkpoint(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"completed_school_ids": [], "code_tables_done": False}
    return json.loads(path.read_text(encoding="utf-8"))


def save_checkpoint(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # 임시 파일에 쓰고 교체한다 — 수집 중 중단돼도 Checkpoint가 반쯤 쓰인 상태로 남지 않는다.
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def append_error(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(_canonical_json(record) + "\n")


def split_bulk_text(row: dict[str, str], curricula_dir: Path, key: str) -> dict[str, Any]:
    """교과목 전문을 떼어내고 본 레코드엔 해시·길이만 남긴다.

    원본을 버리는 게 아니라 **옮기는** 것이다 — §5 "원문을 손실 없이 복원할 수 있는 필드를
    보존한다"를 지키면서 JSONL을 사람이 읽을 수 있는 크기로 유지한다.
    """
    out: dict[str, Any] = dict(row)
    for field in BULK_TEXT_FIELDS:
        text = out.pop(field, "")
        if not text:
            out[f"{field}__sha256"] = None
            out[f"{field}__len"] = 0
            continue
        digest = _sha256(text)
        curricula_dir.mkdir(parents=True, exist_ok=True)
        target = curricula_dir / f"{key}.txt.gz"
        with target.open("wb") as _f, gzip.GzipFile(fileobj=_f, mode="wb", mtime=0, filename="") as fh:
            fh.write(text.encode("utf-8"))
        out[f"{field}__sha256"] = digest
        out[f"{field}__len"] = len(text)
        out[f"{field}__path"] = str(target.relative_to(curricula_dir.parents[1]))
    return out


def _normalize_university_name(name: str) -> str:
    """대학명 비교용 정규화.

    시연 데이터는 `연세대학교`인데 API는 캠퍼스를 붙여 `중앙대학교(서울)`처럼 온다.
    괄호·공백을 떼고 앞부분만 비교한다 — 여기서 걸러도 원본은 그대로 저장된다.
    """
    base = name.split("(")[0]
    return "".join(base.split())


def select_demo_school_ids(
    universities: list[dict[str, str]], demo_names: set[str]
) -> tuple[list[str], list[str]]:
    """시연 대학 목록과 이름이 맞는 schlId만 고른다. (선택된 id, 못 찾은 이름) 반환.

    본교·분교가 별도 `schlId`로 오므로 같은 대학이 여러 건 잡힐 수 있다 — 임의로 합치지
    않는다(§7 "본교·분교·캠퍼스를 임의 통합하지 않는다").
    """
    wanted = {_normalize_university_name(n) for n in demo_names}
    selected: list[str] = []
    matched: set[str] = set()
    for row in universities:
        key = _normalize_university_name(row.get("schlKrnNm", ""))
        if key in wanted:
            sid = row.get("schlId", "").strip()
            if sid and sid not in selected:
                selected.append(sid)
            matched.add(key)
    missing = sorted(wanted - matched)
    return selected, missing


def load_demo_university_names(master_path: Path) -> set[str]:
    """`data/master/universities.jsonl`의 시연 대학 이름을 읽는다."""
    if not master_path.exists():
        return set()
    names: set[str] = set()
    for line in master_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            names.add(json.loads(line).get("name", "").strip())
    return {n for n in names if n}


def collect_code_tables(client: AcademyInfoClient, paths: Paths, year: int, *, dry_run: bool) -> dict[str, int]:
    """판정 근거가 되는 코드표를 먼저 받는다.

    계열·학교종류·수업연한 판정이 전부 이 표를 근거로 걸리므로, 수집 시점의 표를 스냅샷으로
    남겨야 나중에 같은 판정을 재현할 수 있다.
    """
    counts: dict[str, int] = {}
    for service, operation, label in CODE_TABLES:
        rows = client.fetch_code_table(service, operation, year)
        counts[operation] = len(rows)
        if not dry_run:
            write_jsonl_gz(paths.codes / f"{operation}.jsonl.gz", rows)
        print(f"  [코드표] {label:<16} {operation:<44} {len(rows):>5}건")
    return counts


def collect_universities(client: AcademyInfoClient, paths: Paths, year: int, *, dry_run: bool) -> list[dict[str, str]]:
    rows = client.fetch_universities(year)
    if not dry_run:
        write_jsonl_gz(paths.universities, rows)
    print(f"  [대학] {len(rows)}건 수집")
    return rows


def collect_departments(
    client: AcademyInfoClient,
    paths: Paths,
    year: int,
    school_ids: list[str],
    *,
    dry_run: bool,
    resume: bool,
) -> tuple[int, int]:
    """대학별로 순회하며 학과를 모은다. 대학 하나가 끝날 때마다 Checkpoint를 저장한다."""
    checkpoint = load_checkpoint(paths.checkpoint) if resume else {"completed_school_ids": []}
    done: set[str] = set(checkpoint.get("completed_school_ids", []))

    existing = read_jsonl_gz(paths.departments) if (resume and paths.departments.exists()) else []
    collected: list[dict[str, Any]] = list(existing)
    failed = 0

    todo = [sid for sid in school_ids if sid not in done]
    print(f"  [학과] 대상 {len(todo)}개 대학 (이미 완료 {len(done)}개 건너뜀)")

    for index, school_id in enumerate(todo, start=1):
        try:
            rows = client.fetch_departments(year, school_id=school_id)
        except QuotaError:
            # 한도 초과는 재시도 대상이 아니다. 여기까지 저장하고 정상 종료해서
            # 다음 날 --resume으로 이어받게 한다.
            print(f"  [학과] 일일 한도 도달 — {index - 1}개 대학까지 저장하고 중단합니다.")
            break
        except AcademyInfoError as exc:
            failed += 1
            append_error(
                paths.errors,
                {"stage": "departments", "schl_id": school_id, "error": type(exc).__name__, "message": str(exc), "at": _now_iso()},
            )
            continue

        for row in rows:
            key = row.get("schlMjrId") or f"{school_id}-{len(collected)}"
            collected.append(split_bulk_text(row, paths.curricula, key))

        done.add(school_id)
        if not dry_run:
            write_jsonl_gz(paths.departments, collected)
            save_checkpoint(
                paths.checkpoint,
                {"completed_school_ids": sorted(done), "code_tables_done": True, "updated_at": _now_iso()},
            )
        if index % 25 == 0 or index == len(todo):
            print(f"  [학과] {index}/{len(todo)} 대학 · 누적 {len(collected)}건")

    return len(collected), failed


def write_manifest(paths: Paths, payload: dict[str, Any]) -> None:
    paths.manifest.parent.mkdir(parents=True, exist_ok=True)
    paths.manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    use_utf8_stdout()
    load_dotenv()

    parser = argparse.ArgumentParser(description="대학알리미 전국 학과 수집")
    # 기본값을 두지 않는다 — 연도를 코드에 박으면 새 공시가 열려도 옛 데이터를 계속 받는다.
    # 지정하지 않으면 getComparisonPubYear에 직접 물어 최신 지원연도를 쓴다 (A 지시 §1).
    parser.add_argument(
        "--survey-year",
        type=int,
        default=(int(os.getenv("ACADEMYINFO_SURVEY_YEAR")) if os.getenv("ACADEMYINFO_SURVEY_YEAR") else None),
        help="생략하면 API 지원연도 중 최신값을 자동 선택한다",
    )
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--max-universities", type=int, default=None, help="시범 수집용 상한")
    parser.add_argument("--request-delay-ms", type=int, default=100)
    parser.add_argument("--resume", action="store_true", help="Checkpoint 이후부터 이어서 수집")
    parser.add_argument("--dry-run", action="store_true", help="호출은 하되 파일을 쓰지 않는다")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--skip-code-tables", action="store_true")
    parser.add_argument(
        "--only-demo-universities",
        action="store_true",
        help="data/master/universities.jsonl의 시연 대학만 수집한다 (전국 377개 대신)",
    )
    args = parser.parse_args(argv)

    service_key = os.getenv("DATA_GO_KR_SERVICE_KEY", "")
    if not service_key.strip():
        print("DATA_GO_KR_SERVICE_KEY가 없습니다. .env에 Decoding 키를 넣으세요.", file=sys.stderr)
        return 2

    client = AcademyInfoClient(
        service_key,
        request_delay_ms=args.request_delay_ms,
        retry=RetryPolicy(),
    )

    # 조사연도를 API에 직접 물어본다. 실패하면 기본값으로 넘어가지 않고 멈춘다.
    selection = select_survey_year(client, requested=args.survey_year)
    survey_year = selection.selected_year
    paths = Paths.for_year(survey_year, args.output_dir)

    started_at = _now_iso()
    print(f"대학알리미 수집 시작 — 조사연도 {survey_year}{' (dry-run)' if args.dry_run else ''}")
    print(f"  [연도] 지원 {selection.supported_years} · 선택 {survey_year} · 직전 {selection.previous_year}")
    print(f"  [연도] {selection.reason}")

    code_counts: dict[str, int] = {}
    if not args.skip_code_tables:
        code_counts = collect_code_tables(client, paths, survey_year, dry_run=args.dry_run)

    universities = collect_universities(client, paths, survey_year, dry_run=args.dry_run)

    # 대학 목록에서 schlId를 뽑는다. 4년제 필터는 여기서 하지 않는다 —
    # 원본을 다 받아 두고 판정은 정규화 단계에서 근거를 남기며 한다(§7).
    scope = "전국"
    if args.only_demo_universities:
        demo_names = load_demo_university_names(ROOT / "data" / "master" / "universities.jsonl")
        school_ids, missing = select_demo_school_ids(universities, demo_names)
        scope = f"시연 {len(demo_names)}개 대학"
        print(f"  [범위] {scope} → schlId {len(school_ids)}건 (본교·분교 별도 계산)")
        if missing:
            # 이름이 안 맞는 건 조용히 넘기지 않는다 — 시연 대학이 빠진 채 수집이 끝나면
            # 나중에 "그 대학 학과가 왜 없지"로 되돌아온다.
            print(f"  [범위] ⚠️ 대학알리미에서 못 찾은 시연 대학: {', '.join(missing)}")
    else:
        school_ids = []
        for row in universities:
            sid = row.get("schlId", "").strip()
            if sid and sid not in school_ids:
                school_ids.append(sid)
    if args.max_universities is not None:
        school_ids = school_ids[: args.max_universities]

    dept_count, failed = collect_departments(
        client, paths, survey_year, school_ids, dry_run=args.dry_run, resume=args.resume
    )

    manifest = {
        "collector_version": COLLECTOR_VERSION,
        "collector_git_sha": _git_sha(),
        # 수정일과 조사연도를 구분해 함께 남긴다 — 나중에 "포털엔 2026이라 적혀 있었는데
        # 왜 2025를 받았나"를 이 기록만으로 되짚을 수 있어야 한다 (A 지시 §1).
        "public_api_metadata_modified_at": PUBLIC_API_METADATA_MODIFIED_AT,
        "supported_survey_years": selection.supported_years,
        "selected_survey_year": survey_year,
        "selected_year_reason": selection.reason,
        "previous_survey_year": selection.previous_year,
        "survey_year": survey_year,
        "collected_at": started_at,
        "finished_at": _now_iso(),
        "endpoint_base_url": "https://apis.data.go.kr/B340014",
        "operations": {
            "universities": "BasicInformationService_2/getComparisonUniversitySearchList",
            "departments": "BasicInformationService_1/getUniversityMajorCode",
        },
        # Key가 포함된 호출 URL은 절대 남기지 않는다 (§2·§6).
        "official_source_url": ACADEMYINFO_DATASET_URL,
        "collection_scope": scope,
        "university_count": len(universities),
        "school_ids_targeted": len(school_ids),
        "department_count": dept_count,
        "failed_school_count": failed,
        "code_table_counts": code_counts,
        "api_call_count": client.call_count,
    }
    if not args.dry_run:
        write_manifest(paths, manifest)

    print(
        f"완료 — 대학 {len(universities)}개 · 학과 {dept_count}건 · 실패 {failed}개 대학 · "
        f"API 호출 {client.call_count}회"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
