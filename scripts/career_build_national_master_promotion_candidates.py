"""전국 학과 승격 후보 v2 — 2026-08-25 지시서(a/final-integration-master-promotion) §6.

**이 스크립트는 실제 `data/master/departments.jsonl`을 절대 바꾸지 않는다.** §4가 이미
확정한 원칙("기존 Master 35건의 department_id는 Migration 완료 전까지 그대로 유지한다")과
§6이 요구한 원칙("기존 35건을 무조건 삭제하지 않음")을 문자 그대로 지킨다 — 두 원칙을
동시에 만족하는 유일한 방법은 실제 Master 파일 자체를 오늘 건드리지 않는 것이다.

대신 §6이 요구한 "READY 행만 전국 Master 후보로 승격"·"기존 35건과 신규 Offering의
Migration/병합 결과를 생성"을 그대로 이행하는 **별도 산출물**을 만든다:

- `national_master_promotion_candidates.jsonl` — `career_build_national_department_
  promotion_dry_run.py`의 `promotion_candidates.jsonl`(READY_FOR_PROMOTION만, 이미
  계약학과·산업체위탁·ABOLISHED/MERGED/SPLIT·예체능·N.C.E/P1 근거 부족·중복 offering_id
  전부 제외된 상태)을 그대로 옮겨 담되, 실제 Master 승격 시 필요한 필드 이름
  (`Department` Schema와 최대한 맞춘 이름)으로 재배열한다. **이 파일이 실제
  `data/master/departments.jsonl`에 자동으로 합쳐지지 않는다** — 이후 별도의, 사람이
  검토하는 실제 Migration 라운드가 이 파일을 입력으로 쓸 수 있다.
- `national_master_promotion_report.json`/`.md` — Before/After 행 수, Major별·학교별
  학과 수, 차단 사유별 수(Dry Run 요약을 그대로 인용), 기존 35건과 신규 후보의
  관계(같은 표시명 그룹(`display_group_id`)을 공유하는 기존 Master 행이 있는지 —
  감사 목적일 뿐 자동 병합 근거로 쓰지 않는다) 전부를 담는다.

입력은 오직 `career_build_national_department_promotion_dry_run.py`가 이미 계산해
디스크에 남긴 산출물(`promotion_candidates.jsonl`/`promotion_summary.json`)과 실제
Master(읽기 전용)뿐이다 — Gate를 다시 계산하지 않는다(그 스크립트가 이미 Fail-Closed로
계산한 결과를 그대로 신뢰한다)."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _canonical_dumps(row: dict[str, Any]) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True)


def _write_jsonl_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(_canonical_dumps(row) + "\n")
    tmp.replace(path)


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(path)


def build_candidate_row(dry_run_row: dict[str, Any]) -> dict[str, Any]:
    """Dry Run이 이미 확정한 READY 행 하나를 Master 후보 형태로 재배열한다 — 새로
    계산하는 값은 없다(Gate 재계산 없음)."""

    return {
        "offering_id": dry_run_row["offering_id"],
        "display_group_id": dry_run_row["display_group_id"],
        "old_department_id": dry_run_row["old_department_id"],
        "university_name": dry_run_row["university_name"],
        "department_name": dry_run_row["department_name"],
        "college_name": dry_run_row["college_name"],
        "department_status": dry_run_row["department_status"],
        "source_svy_year": dry_run_row["survey_year"],
        "source_url": "https://www.academyinfo.go.kr/",
        "canonical_major_id": dry_run_row["resolved_canonical_major_id"],
        "department_url": dry_run_row["resolved_department_url"],
    }


def build_report(
    *, candidates: list[dict[str, Any]], existing_master: list[dict[str, Any]],
    dry_run_summary: dict[str, Any], survey_year: int,
) -> dict[str, Any]:
    offering_ids = [c["offering_id"] for c in candidates]
    duplicate_offering_ids = sorted(oid for oid, count in Counter(offering_ids).items() if count > 1)

    major_counts = dict(Counter(c["canonical_major_id"] for c in candidates).most_common())
    university_counts = dict(Counter(c["university_name"] for c in candidates).most_common())

    existing_display_groups = {
        # 기존 Master는 department_id만 있다 — 그 값 자체가 이미
        # generate_department_id(schl_id, department_name, college_name)와 같은 재료로
        # 만들어졌으므로, "이 기존 학과가 새 후보 중 어느 표시명 그룹과 같은가"는
        # department_id 그 자체로 이미 판정 가능하다(감사용, 자동 병합 근거 아님).
        row["department_id"] for row in existing_master
    }
    candidates_sharing_existing_display_group = sorted(
        c["offering_id"] for c in candidates if c["old_department_id"] in existing_display_groups
    )

    return {
        "survey_year": survey_year,
        "existing_master_row_count": len(existing_master),
        "new_candidate_row_count": len(candidates),
        "duplicate_offering_id_count": len(duplicate_offering_ids),
        "duplicate_offering_ids": duplicate_offering_ids,
        "major_breakdown": major_counts,
        "university_count": len(university_counts),
        "university_breakdown_top20": dict(list(university_counts.items())[:20]),
        "blocked_reason_counts": dry_run_summary["blocked_reason_counts"],
        "candidates_sharing_existing_master_display_group_count": len(candidates_sharing_existing_display_group),
        "candidates_sharing_existing_master_display_group": candidates_sharing_existing_display_group,
        "note": (
            "이 산출물은 실제 data/master/departments.jsonl을 바꾸지 않는다 — 기존 35건은 "
            "Migration 완료 전까지 그대로 유지한다(2026-08-25 지시서 §4/§6). "
            "national_master_promotion_candidates.jsonl은 이후 별도의, 사람이 검토하는 "
            "실제 Migration 라운드가 입력으로 쓸 수 있는 후보 목록일 뿐이다. "
            "candidates_sharing_existing_master_display_group은 새 후보의 old_department_id가 "
            "기존 Master 35건 중 하나와 같은 경우를 표시한다(감사용 참고일 뿐 자동 병합 "
            "근거로 쓰지 않는다 — 같은 department_id라도 실제로는 서로 다른 offering일 수 "
            "있다는 사실이 바로 Identity v2가 고치려는 문제였다)."
        ),
    }


def build_report_markdown(report: dict[str, Any], regenerate_cmd: str) -> str:
    lines = [
        f"# 전국 학과 Master 승격 후보 v2 — {report['survey_year']}년",
        "",
        "**이 문서는 후보 목록·통계 보고서다. `data/master/departments.jsonl`은 이 산출물로",
        "바뀌지 않았다 — 기존 35건은 Migration 완료 전까지 그대로 유지한다.**",
        "",
        "## 요약",
        "",
        f"- 기존 Master 행 수: {report['existing_master_row_count']}건",
        f"- 신규 승격 후보 행 수: {report['new_candidate_row_count']}건",
        f"- 후보 중 offering_id 중복: {report['duplicate_offering_id_count']}건",
        f"- 신규 후보가 걸치는 대학 수: {report['university_count']}개",
        f"- 신규 후보 중 기존 Master 35건과 old_department_id(표시명 그룹)를 공유하는 건수: "
        f"{report['candidates_sharing_existing_master_display_group_count']}건(감사 참고용)",
        "",
        "## Major별 신규 후보 수",
        "",
        "| Canonical Major | 후보 수 |",
        "|---|---|",
    ]
    for major_id, count in report["major_breakdown"].items():
        lines.append(f"| {major_id} | {count} |")

    lines += ["", "## Dry Run 차단 사유별 수(참고, §5 결과 그대로 인용)", "", "| 사유 | 개수 |", "|---|---|"]
    for reason, count in sorted(report["blocked_reason_counts"].items()):
        lines.append(f"| {reason} | {count} |")

    lines += ["", "## 재생성 명령", "", "```", regenerate_cmd, "```", ""]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    use_utf8_stdout()
    import argparse

    parser = argparse.ArgumentParser(description="전국 학과 Master 승격 후보 v2 생성(실제 Master 무변경)")
    parser.add_argument("--survey-year", type=int, default=2025)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--dry-run-dir", type=Path, default=None, help="기본값: <data-dir>/academyinfo_work/<year>/promotion_dry_run")
    parser.add_argument("--output-dir", type=Path, default=None, help="기본값: --dry-run-dir과 동일")
    args = parser.parse_args(argv)

    dry_run_dir = args.dry_run_dir or (args.data_dir / "academyinfo_work" / str(args.survey_year) / "promotion_dry_run")
    output_dir = args.output_dir or dry_run_dir

    candidates_path = dry_run_dir / "promotion_candidates.jsonl"
    summary_path = dry_run_dir / "promotion_summary.json"
    if not candidates_path.exists() or not summary_path.exists():
        print(f"필수 입력이 없습니다: {candidates_path} / {summary_path}", file=sys.stderr)
        print("먼저 scripts/career_build_national_department_promotion_dry_run.py를 실행하세요.", file=sys.stderr)
        return 2

    dry_run_rows = _read_jsonl(candidates_path)
    dry_run_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    existing_master = _read_jsonl(args.data_dir / "master" / "departments.jsonl")

    if dry_run_summary["ready_for_promotion_count"] == 0:
        print("READY_FOR_PROMOTION이 0건입니다 — Master 후보를 생성하지 않습니다.", file=sys.stderr)
        print("Gate별 실제 차단 원인은 promotion_summary.json을 확인하세요.", file=sys.stderr)
        return 2

    candidates = [build_candidate_row(r) for r in dry_run_rows]
    candidates.sort(key=lambda r: r["offering_id"])

    report = build_report(
        candidates=candidates, existing_master=existing_master,
        dry_run_summary=dry_run_summary, survey_year=args.survey_year,
    )
    regenerate_cmd = (
        f"PYTHONPATH=. ./.venv/bin/python scripts/career_build_national_master_promotion_candidates.py "
        f"--survey-year {args.survey_year} --data-dir {args.data_dir}"
    )
    report_md = build_report_markdown(report, regenerate_cmd)

    candidates_out_path = output_dir / "national_master_promotion_candidates.jsonl"
    report_path = output_dir / "national_master_promotion_report.json"
    report_md_path = output_dir / "national_master_promotion_report.md"

    _write_jsonl_atomic(candidates_out_path, candidates)
    _write_text_atomic(report_path, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _write_text_atomic(report_md_path, report_md)

    print(f"Master 승격 후보 v2 완료 — 조사연도 {args.survey_year}")
    print(f"  기존 Master {report['existing_master_row_count']}건 (무변경)")
    print(f"  신규 후보 {report['new_candidate_row_count']}건")
    print(f"  후보 offering_id 중복 {report['duplicate_offering_id_count']}건")
    print(f"  대학 수 {report['university_count']}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
