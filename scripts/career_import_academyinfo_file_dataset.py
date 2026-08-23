"""대학알리미 파일 데이터셋(xlsx) → 정규화 — A 지시 §4 연도 비교용.

`getUniversityMajorCode`는 2025만 응답한다(rationale_c/07 §7-24). 직전 연도를 비교하려면
공공데이터포털의 **파일 데이터셋**을 써야 하는데, 다운로드에 로그인이 필요해 사람이 한 번
받아 준다. 그 뒤 처리는 이 스크립트가 한다.

    교육부_대학알리미_학교별 학부·학과(전공) 리스트
    https://www.data.go.kr/data/15139338/fileData.do

파일 컬럼은 API 필드와 이름이 다르지만 **같은 값**이다. 특히 `학교별학과코드`가
`schlMjrId`라 유지율 계산이 가능하다.

판정 규칙은 API 경로와 **같은 함수**(`academyinfo_codes`)를 쓴다 — 두 경로가 다른 기준으로
거르면 비교 자체가 무의미해진다.

실행:
    python scripts/career_import_academyinfo_file_dataset.py \
        --xlsx "data/academyinfo_raw/file_dataset/학교별 교육편제단위 정보_20241007기준.xlsx"
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import openpyxl  # noqa: E402

from scripts.career_console import use_utf8_stdout  # noqa: E402
from src.data_sources.academyinfo_identity import generate_source_record_id  # noqa: E402
from src.ids import generate_department_id  # noqa: E402

# 파일 컬럼 → API 필드. 값이 같은 것끼리만 잇는다.
COLUMN_TO_API = {
    "학교코드": "schlId",
    "학교명": "korSchlNm",
    "학교별학과코드": "schlMjrId",
    "학부·과(전공)명": "korMjrNm",
    "단과대학명": "clgNm",
    "단과대학코드": "clgCd",
    "본분교": "psbsDivNm",
    "(학과)소재지": "mjrAreaNm",
    "(학과)소재지(상세)": "mjrAreaSignguNm",
    "학과상태": "schlMjrStatNm",
    "학과특성": "schlMjrCharNm",
    "주야간구분": "dghtDivNm",
    "대계열분류": "korSrsLclftNm",
    "중계열분류": "korSrsMclftNm",
    "소계열분류": "korSrsSclftNm",
    "대학자체대계열": "onsfSrsClftNm",
    "수업연한": "lsnTrmNm",
    "학위과정": "pbnfDgriCrseDivNm",
    "학교구분": "schlKndNm",
    "조사년도": "svyYr",
}

# 파일에는 코드가 아니라 이름만 오는 축이 있다. 판정 함수는 코드를 보므로 되돌려 준다.
# academyinfo_codes.LESSON_TERM_LABELS의 역방향이며, 파일에만 있는 표기도 함께 받는다.
LESSON_TERM_NAME_TO_CODE = {
    "1년": "01", "1.5년": "02", "2년": "03", "2.5년": "04", "3년": "05",
    "3.5년": "06", "4년": "07", "4.5년": "08", "5년": "09", "5.5년": "10",
    "6년": "11", "6.5년": "12", "7년": "13",
    "1년(전공심화)": "14", "2년(전공심화)": "15",
    "1년(교육특성화)": "14", "2년(교육특성화)": "15",
}
SCHOOL_KIND_NAME_TO_CODE = {"대학교": "03"}
DEGREE_NAME_TO_CODE = {"학사": "3"}
UNCLASSIFIED_NAMES = {"N.C.E", "N.C.E."}


def read_xlsx(path: Path) -> list[dict[str, Any]]:
    """헤더 위에 안내문이 몇 줄 있다. '조사년도'가 있는 행을 헤더로 잡는다."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = list(wb.active.iter_rows(values_only=True))
    header_index = next(
        i for i, r in enumerate(rows[:20])
        if r and any(str(c).strip() == "조사년도" for c in r if c)
    )
    header = [str(c).strip() if c else "" for c in rows[header_index]]
    return [dict(zip(header, r)) for r in rows[header_index + 1:] if r and r[0]]


def to_api_shape(row: dict[str, Any]) -> dict[str, str]:
    """파일 한 행을 API 응답과 같은 모양으로 옮긴다. 값을 만들어내지 않는다."""
    out: dict[str, str] = {}
    for column, field in COLUMN_TO_API.items():
        value = row.get(column)
        out[field] = "" if value is None else str(value).strip()

    # 이름만 오는 축을 코드로 되돌린다. 모르는 표기는 빈 값으로 두어 보수적으로 제외되게 한다.
    out["lsnTrmCd"] = LESSON_TERM_NAME_TO_CODE.get(out.get("lsnTrmNm", ""), "")
    out["schlKndCd"] = SCHOOL_KIND_NAME_TO_CODE.get(out.get("schlKndNm", ""), "")
    out["pbnfDgriCrseDivCd"] = DEGREE_NAME_TO_CODE.get(out.get("pbnfDgriCrseDivNm", ""), "")
    # 계열 코드는 파일에 없다. 미분류 여부만 이름으로 판정한다(§7-9).
    out["srsMclftCd"] = "99" if out.get("korSrsMclftNm") in UNCLASSIFIED_NAMES else ""
    out["srsSclftCd"] = "999" if out.get("korSrsSclftNm") in UNCLASSIFIED_NAMES else ""
    return out


def normalize(api_rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], Counter]:
    """API 경로와 **같은 판정 함수**를 쓴다. 기준이 갈리면 비교가 무의미해진다."""
    from src.data_sources.academyinfo_codes import undergraduate_scope_reason

    included: list[dict[str, Any]] = []
    excluded: Counter = Counter()
    for raw in api_rows:
        reason = undergraduate_scope_reason(raw)
        if reason is not None:
            excluded[reason] += 1
            continue
        schl_id = raw["schlId"]
        name = raw["korMjrNm"]
        college = raw["clgNm"]
        included.append(
            {
                "source_record_id": generate_source_record_id(schl_id, raw["schlMjrId"], raw["svyYr"]),
                "department_id": generate_department_id(schl_id, name, college),
                "schl_id": schl_id,
                "university_name": raw["korSchlNm"],
                "department_name": name,
                "college_name": college,
                "source_schl_mjr_id": raw["schlMjrId"] or None,
                "source_svy_year": int(raw["svyYr"] or 0),
                "lesson_term_name": raw.get("lsnTrmNm"),
                "department_status_raw": raw.get("schlMjrStatNm"),
                "official_classification": {
                    "large_series_name": raw.get("korSrsLclftNm") or None,
                    "middle_series_name": raw.get("korSrsMclftNm") or None,
                    "small_series_name": raw.get("korSrsSclftNm") or None,
                    "self_series_name": raw.get("onsfSrsClftNm") or None,
                    "is_unclassified": raw.get("korSrsSclftNm") in UNCLASSIFIED_NAMES,
                },
                "source_origin": "file_dataset",
            }
        )
    return included, excluded


def main(argv: list[str] | None = None) -> int:
    use_utf8_stdout()
    parser = argparse.ArgumentParser(description="대학알리미 파일 데이터셋 → 정규화")
    parser.add_argument("--xlsx", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args(argv)

    if not args.xlsx.exists():
        print(f"파일이 없습니다: {args.xlsx}", file=sys.stderr)
        return 2

    raw_rows = read_xlsx(args.xlsx)
    api_rows = [to_api_shape(r) for r in raw_rows]
    years = Counter(r["svyYr"] for r in api_rows)
    if len(years) != 1:
        print(f"조사연도가 섞여 있습니다: {dict(years)}", file=sys.stderr)
        return 2
    survey_year = int(next(iter(years)))

    included, excluded = normalize(api_rows)
    work = args.data_dir / "academyinfo_work" / str(survey_year)
    work.mkdir(parents=True, exist_ok=True)
    (work / "departments.normalized.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in included),
        encoding="utf-8",
    )
    (work / "file_dataset_import_report.json").write_text(
        json.dumps(
            {
                "source_file": args.xlsx.name,
                "source_origin": "file_dataset",
                "official_source_url": "https://www.data.go.kr/data/15139338/fileData.do",
                "survey_year": survey_year,
                "total_rows": len(raw_rows),
                "included_count": len(included),
                "excluded_count": sum(excluded.values()),
                "exclusion_breakdown": dict(excluded),
                "note": "판정은 API 경로와 같은 academyinfo_codes 함수를 쓴다.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"파일 데이터셋 가져오기 — 조사연도 {survey_year}")
    print(f"  전체 {len(raw_rows)}행 · 포함 {len(included)} · 제외 {sum(excluded.values())}")
    for reason, count in excluded.most_common(6):
        print(f"  제외: {reason} — {count}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
