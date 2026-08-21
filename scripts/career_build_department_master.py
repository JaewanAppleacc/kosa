"""원본(data/raw/) → 정제 Master(data/master/) 변환 + Canonical Mapping 1차 실행.

C 지시서 §3 "원본 데이터와 정제 데이터를 분리해 보존한다"를 파일 단위로 지킨다.
`data/raw/*.raw.jsonl`은 손대지 않고, 이 스크립트가 매번 `data/master/*.jsonl`을 다시 만든다.

하는 일:
1. 대학명·학과명 정규화 (canonical_mapper.normalize_department_name)
2. `generate_department_id()`로 ID 부여 — 조사년도는 해시에 넣지 않는다(§ids.py)
3. 중복 학과 행 제거 (같은 department_id가 두 번 나오면 첫 행만 남기고 기록)
4. 출처 URL 없는 행 제외 (§3 "출처 불명 학과를 구분한다")
5. Canonical Mapping을 돌려 결과와 REVIEW_REQUIRED 목록을 따로 저장

실행:
    python scripts/career_build_department_master.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.engines.canonical_mapper import (  # noqa: E402
    CanonicalMapper,
    load_canonical_majors,
    normalize_department_name,
    review_required,
)
from src.ids import generate_department_id  # noqa: E402
from src.schemas.major import Department  # noqa: E402

RAW_DIR = ROOT / "data" / "raw"
MASTER_DIR = ROOT / "data" / "master"

# 대학알리미 `schlMjrStatNm` 계열 값 → A의 Department.department_status Literal.
# 모르는 값을 임의로 EXISTING에 밀어 넣지 않는다 — 실제 값이 확인되면 여기만 넓힌다.
STATUS_MAP: dict[str, str] = {
    "기존": "EXISTING",
    "신설": "NEW",
    "통합": "MERGED",
    "분리": "SPLIT",
    "폐지": "ABOLISHED",
    "폐과": "ABOLISHED",
}


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _write_jsonl(path: Path, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(r + "\n" for r in rows), encoding="utf-8")


def build_universities() -> list[dict]:
    rows = _read_jsonl(RAW_DIR / "universities.raw.jsonl")
    cleaned = []
    for row in rows:
        cleaned.append(
            {
                "schl_id": row["schl_id"].strip(),
                "name": normalize_department_name(row["name"]),
                "region": row["region"].strip(),
                "establishment_type": row["establishment_type"].strip(),
                "homepage": row["homepage"].strip(),
            }
        )
    _write_jsonl(
        MASTER_DIR / "universities.jsonl",
        [json.dumps(c, ensure_ascii=False) for c in cleaned],
    )
    return cleaned


def build_departments() -> tuple[list[Department], list[dict]]:
    rows = _read_jsonl(RAW_DIR / "departments.raw.jsonl")
    departments: list[Department] = []
    rejected: list[dict] = []
    seen: set[str] = set()

    for line_no, row in enumerate(rows, start=1):
        source_url = (row.get("source_url") or "").strip()
        if not source_url:
            rejected.append(
                {"line": line_no, "reason": "source_url 없음", "raw": row}
            )
            continue

        status = STATUS_MAP.get((row.get("status_raw") or "").strip())
        if status is None:
            rejected.append(
                {
                    "line": line_no,
                    "reason": f"알 수 없는 status_raw {row.get('status_raw')!r}",
                    "raw": row,
                }
            )
            continue

        department_name = normalize_department_name(row["department_name"])
        college_name = normalize_department_name(row["college_name"])
        department_id = generate_department_id(row["schl_id"], department_name, college_name)
        if department_id in seen:
            rejected.append({"line": line_no, "reason": "중복 학과 행", "raw": row})
            continue
        seen.add(department_id)

        departments.append(
            Department(
                department_id=department_id,
                university_name=normalize_department_name(row["university_name"]),
                campus=(row.get("campus") or None),
                region=row["region"].strip(),
                department_name=department_name,
                college_name=college_name,
                admission_unit=normalize_department_name(row["admission_unit"])
                if row.get("admission_unit")
                else None,
                department_status=status,  # type: ignore[arg-type]
                source_svy_year=int(row["svy_year"]),
                source_url=source_url,
            )
        )

    _write_jsonl(
        MASTER_DIR / "departments.jsonl", [d.model_dump_json() for d in departments]
    )
    _write_jsonl(
        MASTER_DIR / "departments_rejected.jsonl",
        [json.dumps(r, ensure_ascii=False) for r in rejected],
    )
    return departments, rejected


def build_mappings(departments: list[Department]) -> None:
    mapper = CanonicalMapper(load_canonical_majors(MASTER_DIR / "canonical_majors.jsonl"))
    results = mapper.map_all(departments)
    _write_jsonl(
        MASTER_DIR / "canonical_mapping_results.jsonl", [r.model_dump_json() for r in results]
    )
    _write_jsonl(
        MASTER_DIR / "canonical_mapping_review_required.jsonl",
        [r.model_dump_json() for r in review_required(results)],
    )

    # AUTO_MAPPED만 Department.canonical_major_id에 반영한다. REVIEW_REQUIRED는 비워 둔 채
    # 남긴다 — 미확정 결과가 확정 데이터에 섞이면 §8 완료 조건이 깨진다.
    by_id = {r.department_id: r for r in results}
    updated = [
        d.model_copy(
            update={
                "canonical_major_id": by_id[d.department_id].primary_candidate
                if by_id[d.department_id].mapping_status == "AUTO_MAPPED"
                else None
            }
        )
        for d in departments
    ]
    _write_jsonl(MASTER_DIR / "departments.jsonl", [d.model_dump_json() for d in updated])

    auto = sum(1 for r in results if r.mapping_status == "AUTO_MAPPED")
    print(f"Canonical Mapping: AUTO_MAPPED {auto} / REVIEW_REQUIRED {len(results) - auto}")


if __name__ == "__main__":
    universities = build_universities()
    departments, rejected = build_departments()
    print(f"대학 {len(universities)}개, 학과 {len(departments)}개 정제 완료")
    if rejected:
        print(f"제외 {len(rejected)}행 — data/master/departments_rejected.jsonl 참고")
        for item in rejected:
            print(f"  line {item['line']}: {item['reason']}")
    build_mappings(departments)
