"""대학알리미 원본 → 정규화 — 지시서 §6·§7.

`data/academyinfo_raw/<연도>/`를 읽어 `data/academyinfo_work/<연도>/`에 쓴다.
**원본은 읽기만 하고 절대 고치지 않는다** (§9). 기존 `data/master/`도 건드리지 않는다 —
승격은 §10 품질검사를 통과한 뒤 A가 판단한다.

이 단계가 하는 일은 셋뿐이다.

    1. 필드 이름 매핑 (기존 Raw Schema 유지, §6)
    2. 4년제 학사 범위 판정 — 포함/제외를 **근거와 함께** 가른다 (§7)
    3. Canonical Major 후보를 만들 재료 정리 — 확정은 하지 않는다 (§8-1)

설계 근거: `rationale_c/07-academyinfo-collection.md`.

실행:
    python scripts/career_normalize_academyinfo.py --survey-year 2025
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402
from src.data_sources.academyinfo_client import ACADEMYINFO_DATASET_URL  # noqa: E402
from src.data_sources.academyinfo_codes import (  # noqa: E402
    is_series_unclassified,
    undergraduate_scope_reason,
)
from src.data_sources.academyinfo_identity import (  # noqa: E402
    build_lineage,
    build_resolution_review_queue,
    generate_source_record_id,
    retention_stats,
)
from src.ids import generate_department_id  # noqa: E402

ACADEMYINFO_DATASET_NAME = "한국대학교육협의회 대학알리미 대학 기본 정보 (data.go.kr B340014)"

# 대학알리미 `schlMjrStatNm` → 기존 Department.department_status Literal.
# 기존 career_build_department_master.py의 STATUS_MAP과 같은 표를 쓴다 — 두 곳이
# 갈라지면 같은 원본이 빌더에 따라 다른 상태로 저장된다.
STATUS_MAP: dict[str, str] = {
    "기존": "EXISTING",
    "신설": "NEW",
    "통합": "MERGED",
    "분리": "SPLIT",
    "폐지": "ABOLISHED",
    "폐과": "ABOLISHED",
}


def read_jsonl_gz(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def _campus_of(raw: dict[str, Any]) -> str | None:
    """본교면 None, 분교·제2캠퍼스면 소재지를 남긴다.

    본교를 `"본교"`라는 문자열로 채우면 기존 35건(전부 None)과 Diff가 전부 어긋난다.
    """
    div = (raw.get("psbsDivNm") or "").strip()
    if not div or div == "본교":
        return None
    area = (raw.get("mjrAreaNm") or "").strip()
    return f"{div}({area})" if area else div


def normalize_department(raw: dict[str, Any]) -> dict[str, Any]:
    """원본 한 행 → 정규화 한 행. 판정은 하지 않고 재료만 정리한다."""
    schl_id = (raw.get("schlId") or "").strip()
    department_name = (raw.get("korMjrNm") or "").strip()
    college_name = (raw.get("clgNm") or "").strip()

    return {
        # A 지시 §5: 원본 행 식별자와 학과 실체 식별자를 분리한다.
        # source_record_id는 연도를 포함하고, department_id는 포함하지 않는다.
        "source_record_id": generate_source_record_id(
            schl_id, (raw.get("schlMjrId") or "").strip(), raw.get("svyYr") or 0
        ),
        "department_id": generate_department_id(schl_id, department_name, college_name),
        "schl_id": schl_id,
        "university_name": (raw.get("korSchlNm") or "").strip(),
        "campus": _campus_of(raw),
        "region": (raw.get("mjrAreaNm") or "").strip(),
        "department_name": department_name,
        "college_name": college_name,
        # 대학알리미에 모집단위 필드가 없다. 비슷해 보이는 단과대학으로 대신 채우지 않는다
        # (rationale_c/07 §7-11).
        "admission_unit": None,
        "department_status": STATUS_MAP.get((raw.get("schlMjrStatNm") or "").strip(), "EXISTING"),
        "source_svy_year": int(raw.get("svyYr") or 0),
        # 이 **데이터**의 출처. 대학알리미는 조회 폼 기반이라 학과별 고정 링크가 없으므로,
        # 검증 가능한 최소 단위인 공개 데이터셋 URL을 쓴다 (§7-6).
        "source_url": ACADEMYINFO_DATASET_URL,
        "source_dataset": ACADEMYINFO_DATASET_NAME,
        # 학생이 더 알아볼 학과 홈페이지. API가 주지 않으므로 확인된 것만 사람이 채운다.
        # 대학 대표 홈페이지로 대신 채우지 않는다.
        "department_url": None,
        # 원본 식별자 보존 — 연도 간 추적·재조회에 쓴다 (§7-8, 아직 ID 키로는 안 쓴다).
        "source_schl_mjr_id": (raw.get("schlMjrId") or "").strip() or None,
        "source_mjr_id": (raw.get("mjrId") or "").strip() or None,
        "source_kedi_mjr_id": (raw.get("kediMjrId") or "").strip() or None,
        # §8-1 분류 근거 — 확정이 아니라 후보를 만들 재료다.
        "official_classification": {
            "large_series_code": (raw.get("srsLclftCd") or "").strip() or None,
            "large_series_name": (raw.get("korSrsLclftNm") or "").strip() or None,
            "middle_series_code": (raw.get("srsMclftCd") or "").strip() or None,
            "middle_series_name": (raw.get("korSrsMclftNm") or "").strip() or None,
            "small_series_code": (raw.get("srsSclftCd") or "").strip() or None,
            "small_series_name": (raw.get("korSrsSclftNm") or "").strip() or None,
            # 대학이 스스로 붙인 계열. 표준분류와 충돌하면 REVIEW_REQUIRED 신호다.
            "self_series_name": (raw.get("onsfSrsClftNm") or "").strip() or None,
            "is_unclassified": is_series_unclassified(raw),
        },
        "lesson_term_code": (raw.get("lsnTrmCd") or "").strip() or None,
        "lesson_term_name": (raw.get("lsnTrmNm") or "").strip() or None,
        "degree_course_name": (raw.get("pbnfDgriCrseDivNm") or "").strip() or None,
        "major_character_name": (raw.get("schlMjrCharNm") or "").strip() or None,
        "enrolled_count": int(raw.get("eschlPscpNum") or 0),
        "graduate_count": int(raw.get("grdtNum") or 0),
        # 교육목표·교과목은 §8-1 3순위 근거다. 교과목 전문은 분리 저장돼 있어 해시만 온다.
        "education_goal": (raw.get("edcGoalCtnt") or "").strip() or None,
        "education_goal_keywords": [
            k for k in (raw.get("edcGoalKwrdLtrCtnt") or "").split("|") if k.strip()
        ],
        "curriculum_sha256": raw.get("edcCrseLtrCtnt__sha256"),
        "curriculum_path": raw.get("edcCrseLtrCtnt__path"),
        "source_updated_at": (raw.get("mjrUpdtDtm") or "").strip() or None,
    }


def normalize(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(포함, 제외) 두 목록으로 가른다. 제외 행도 버리지 않는다 (§7)."""
    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for raw in rows:
        reason = undergraduate_scope_reason(raw)
        if reason is None:
            included.append(normalize_department(raw))
            continue
        # 제외 근거와 함께 판정에 쓴 공식 필드를 그대로 남긴다 — 나중에 기준이 바뀌면
        # 재수집이 아니라 이 파일만 다시 읽어 재판정할 수 있어야 한다.
        excluded.append(
            {
                "schl_id": (raw.get("schlId") or "").strip(),
                "schl_mjr_id": (raw.get("schlMjrId") or "").strip(),
                "university_name": (raw.get("korSchlNm") or "").strip(),
                "department_name": (raw.get("korMjrNm") or "").strip(),
                "exclusion_reason": reason,
                "official_fields": {
                    "schlKndCd": raw.get("schlKndCd"),
                    "schlKndNm": raw.get("schlKndNm"),
                    "lsnTrmCd": raw.get("lsnTrmCd"),
                    "lsnTrmNm": raw.get("lsnTrmNm"),
                    "pbnfDgriCrseDivCd": raw.get("pbnfDgriCrseDivCd"),
                    "pbnfDgriCrseDivNm": raw.get("pbnfDgriCrseDivNm"),
                },
            }
        )

    return included, excluded


def annotate_duplicate_groups(included: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """같은 `department_id`가 여러 건이면 전부 표시한다. 임의로 하나만 남기지 않는다.

    대학알리미는 같은 학과를 여러 `schlMjrId`로 나눠 보낸다 — 폐지 이력이 함께 오거나,
    재학생 0명인 중복 등록이 남아 있는 경우다. `generate_department_id()`는
    (schl_id, 학과명, 단과대학) 셋만 쓰므로 이들을 구분하지 못한다.

    여기서 "재학생이 많은 쪽"을 골라 남기고 싶어지지만, 그건 **판정**이다. §9가 사람이
    검토하지 않은 것을 확정하지 말라고 했으므로 표시만 하고 검토로 넘긴다
    (rationale_c/07 §7-8).
    """
    groups = Counter(r["department_id"] for r in included)
    for row in included:
        size = groups[row["department_id"]]
        row["duplicate_group_size"] = size
        row["review_status"] = "REVIEW_REQUIRED" if size > 1 else "CANDIDATE"
        if size > 1:
            row["review_reason"] = (
                "같은 department_id로 여러 원본 행이 왔다 — 어느 schlMjrId가 현행인지 "
                "사람이 확인해야 한다"
            )
    return included


def build_report(
    included: list[dict[str, Any]], excluded: list[dict[str, Any]], year: int
) -> dict[str, Any]:
    """§10 품질검사가 볼 숫자. 여기서 통과/실패를 판정하지는 않는다."""
    dup = [k for k, v in Counter(r["department_id"] for r in included).items() if v > 1]
    unclassified = sum(1 for r in included if r["official_classification"]["is_unclassified"])
    missing_college = sum(1 for r in included if not r["college_name"])

    return {
        "survey_year": year,
        "included_count": len(included),
        "excluded_count": len(excluded),
        "university_count": len({r["schl_id"] for r in included}),
        "duplicate_department_id_count": len(dup),
        "duplicate_department_ids": dup,
        "review_required_count": sum(1 for r in included if r.get("review_status") == "REVIEW_REQUIRED"),
        "series_unclassified_count": unclassified,
        "missing_college_name_count": missing_college,
        "department_url_missing_count": sum(1 for r in included if not r["department_url"]),
        "status_breakdown": dict(Counter(r["department_status"] for r in included)),
        "large_series_breakdown": dict(
            Counter(r["official_classification"]["large_series_name"] for r in included)
        ),
        "lesson_term_breakdown": dict(Counter(r["lesson_term_name"] for r in included)),
        "exclusion_breakdown": dict(Counter(r["exclusion_reason"] for r in excluded)),
    }


def main(argv: list[str] | None = None) -> int:
    use_utf8_stdout()
    parser = argparse.ArgumentParser(description="대학알리미 원본 정규화")
    parser.add_argument("--survey-year", type=int, default=2025)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args(argv)

    raw_dir = args.data_dir / "academyinfo_raw" / str(args.survey_year)
    work_dir = args.data_dir / "academyinfo_work" / str(args.survey_year)
    raw_path = raw_dir / "departments.raw.jsonl.gz"

    if not raw_path.exists():
        print(f"원본이 없습니다: {raw_path}", file=sys.stderr)
        print("먼저 scripts/career_collect_academyinfo_departments.py를 실행하세요.", file=sys.stderr)
        return 2

    rows = read_jsonl_gz(raw_path)
    included, excluded = normalize(rows)
    included = annotate_duplicate_groups(included)

    write_jsonl(work_dir / "departments.normalized.jsonl", included)
    write_jsonl(work_dir / "excluded_records.jsonl", excluded)

    # A 지시 §5: 중복은 자동으로 한 행을 고르지 않고 검토 대기열로 넘긴다.
    review_queue = build_resolution_review_queue(included)
    write_jsonl(work_dir / "department_resolution_review_queue.jsonl", review_queue)

    # A 지시 §4: 직전 지원연도가 이미 수집돼 있으면 연도 간 lineage를 만든다.
    lineage: list[dict] = []
    retention: dict = {}
    prev_year = args.survey_year - 1
    prev_path = args.data_dir / "academyinfo_work" / str(prev_year) / "departments.normalized.jsonl"
    if prev_path.exists():
        prev_rows = [json.loads(l) for l in prev_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        lineage = build_lineage(included, prev_rows)
        retention = retention_stats(lineage)
        write_jsonl(work_dir / "department_lineage.jsonl", lineage)
        print(f"  Lineage: {prev_year} → {args.survey_year} · schlMjrId 유지율 "
              f"{retention.get('schl_mjr_id_retention_rate')}")
    else:
        print(f"  Lineage: 직전연도({prev_year}) 정규화 결과가 없어 비교를 건너뜁니다.")
    report = build_report(included, excluded, args.survey_year)
    report["review_queue_count"] = len(review_queue)
    report["lineage"] = retention or None
    (work_dir / "normalization_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"정규화 완료 — 조사연도 {args.survey_year}")
    print(f"  포함 {report['included_count']}건 · 제외 {report['excluded_count']}건 "
          f"· 대학 {report['university_count']}개")
    if report["duplicate_department_ids"]:
        print(f"  ⚠️ department_id 중복 {len(report['duplicate_department_ids'])}건")
    print(f"  계열 미분류(N.C.E) {report['series_unclassified_count']}건 — Canonical 매핑 대상 아님")
    for reason, count in report["exclusion_breakdown"].items():
        print(f"  제외: {reason} — {count}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
