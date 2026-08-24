"""공식 소계열 → 대표 전공군 후보 분류 + Dry Run 보고서 — A 지시 §6·§7·§9.

**확정하지 않는다.** 모든 결과는 `draft` / `REVIEW_REQUIRED` / `UNMAPPED`로 남기고
사람 검토를 거친다(A 지시 §6-2·§9).

Mapping 순서(A 지시 §6-3):

    1. 공식 소계열            ← 이 스크립트가 하는 것
    2. 검토된 Exact Alias     ← 기존 canonical_mapper.py 몫
    3. 학과명 정규화
    4. 공식 교육목표·교육과정·졸업 후 진로
    5. 후보 여럿·근거 충돌   → REVIEW_REQUIRED
    6. 근거 없음             → UNMAPPED

Embedding·LLM 결과만으로 자동 확정하지 않는다.

실행:
    python scripts/career_classify_academyinfo.py --survey-year 2025
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402

GROUPS_PATH = ROOT / "data" / "canonical_major_groups.draft.jsonl"

# 예체능 추천 제외 — 기존 department_recommendation_scope의 상태명을 그대로 쓴다.
# A 지시 §7: "같은 의미의 새 필드명을 만들지 마세요."
ARTS_SPORTS_LARGE_SERIES = "C"  # 예체능계열
ELIGIBILITY_APPROVED = "APPROVED"
ELIGIBILITY_EXCLUDED = "EXCLUDED_ARTS_SPORTS"
ELIGIBILITY_REVIEW = "REVIEW_REQUIRED"

# 이름만으로 예체능 여부를 확정하면 안 되는 학과 (A 지시 §7).
# 공식 단과대학·교육과정 근거가 불충분하면 REVIEW_REQUIRED로 둔다 — Fail-Closed.
CONVERGENCE_KEYWORDS = ("디자인", "콘텐츠", "미디어", "HCI", "UX", "융합", "자유전공", "인터랙션")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows),
        encoding="utf-8",
    )


def build_series_index(groups: list[dict[str, Any]]) -> dict[str, list[str]]:
    """소계열 코드 → 대표 전공군 id 목록. 여럿이면 REVIEW_REQUIRED 신호다."""
    index: dict[str, list[str]] = defaultdict(list)
    for g in groups:
        for code in g["included_official_small_series_codes"]:
            index[code].append(g["canonical_major_id"])
    return index


def is_convergence(row: dict[str, Any]) -> bool:
    name = (row.get("department_name") or "") + " " + (row.get("college_name") or "")
    return any(k in name for k in CONVERGENCE_KEYWORDS)


def classify(row: dict[str, Any], index: dict[str, list[str]], excluded_codes: set[str]) -> dict[str, Any]:
    cls = row.get("official_classification") or {}
    small = (cls.get("small_series_code") or "").strip()
    large = (cls.get("large_series_code") or "").strip()
    self_series = cls.get("self_series_name")

    # --- Canonical 후보 판정 -------------------------------------------------
    if cls.get("is_unclassified") or small in ("", "999"):
        status, candidates, reason = "UNMAPPED", [], "공식 소계열이 미분류(N.C.E)라 근거가 없다"
    elif small in excluded_codes:
        status, candidates, reason = "UNMAPPED", [], "교양 과정 소계열이라 전공군에 넣지 않는다"
    else:
        candidates = index.get(small, [])
        if not candidates:
            status, reason = "UNMAPPED", f"소계열 {small}이 어느 전공군에도 배정되지 않았다"
        elif len(candidates) > 1:
            status, reason = "REVIEW_REQUIRED", f"소계열 {small}이 전공군 {candidates}에 동시에 걸린다"
        else:
            # 자동 확정이 아니라 **후보**다. 사람 검토 전에는 CONFIRMED가 되지 않는다.
            status, reason = "AUTO_CANDIDATE", f"공식 소계열 {small} 단독 배정"

    # --- 추천 적격성(예체능) 판정 -------------------------------------------
    if large == ARTS_SPORTS_LARGE_SERIES:
        eligibility = ELIGIBILITY_EXCLUDED
        elig_reason = "공식 대계열이 예체능계열"
    elif is_convergence(row):
        # 이름에 디자인·콘텐츠·미디어가 있다는 이유만으로 확정하지 않는다.
        eligibility = ELIGIBILITY_REVIEW
        elig_reason = "융합·디자인·콘텐츠 계열 명칭 — 공식 교육과정 근거 확인 필요(Fail-Closed)"
    elif not large:
        eligibility = ELIGIBILITY_REVIEW
        elig_reason = "공식 대계열이 비어 있어 판정 근거가 없다"
    else:
        eligibility = ELIGIBILITY_APPROVED
        elig_reason = f"공식 대계열 {large}({cls.get('large_series_name')})이 예체능이 아님"

    return {
        "department_id": row["department_id"],
        "source_record_id": row.get("source_record_id"),
        "university_name": row.get("university_name"),
        "department_name": row.get("department_name"),
        "college_name": row.get("college_name"),
        # 승격 검토 Queue가 상태로 거를 수 있게 실어 보낸다 (A 결정 2026-08-24).
        "department_status": row.get("department_status"),
        "official_small_series_code": small or None,
        "official_small_series_name": cls.get("small_series_name"),
        "official_large_series_code": large or None,
        # 이름도 함께 내보낸다. 코드만 있으면 검수 패킷에서 사람이 못 읽고,
        # 하위 Queue가 이름을 읽으려다 전부 None을 받는다(2026-08-24 실측 버그).
        "official_large_series_name": cls.get("large_series_name"),
        "official_middle_series_code": (cls.get("middle_series_code") or "").strip() or None,
        "official_middle_series_name": cls.get("middle_series_name"),
        "self_series_name": self_series,
        "candidate_canonical_major_ids": candidates,
        "mapping_status": status,
        "mapping_method": "official_small_series",
        "decision_reason": reason,
        "academic_field_large_series": large or None,
        "eligibility_status": eligibility,
        "eligibility_reason": elig_reason,
        # 사람 검토 전에는 절대 승격하지 않는다 (A 지시 §9)
        "review_status": "draft",
    }


def build_dry_run(
    results: list[dict[str, Any]], groups: list[dict[str, Any]], included_total: int, survey_year: int
) -> dict[str, Any]:
    status = Counter(r["mapping_status"] for r in results)
    elig = Counter(r["eligibility_status"] for r in results)
    per_group = Counter(
        r["candidate_canonical_major_ids"][0]
        for r in results
        if r["mapping_status"] == "AUTO_CANDIDATE"
    )
    labels = {g["canonical_major_id"]: g["label"] for g in groups}

    # 확인용 예시 — 컴퓨터 계열이 실제로 한 전공군으로 묶이는지 (A 지시 §9)
    samples = [
        r for r in results
        if r["university_name"] in ("서울대학교", "연세대학교", "고려대학교")
        and any(k in (r["department_name"] or "") for k in ("컴퓨터", "소프트웨어", "인공지능"))
    ][:8]

    return {
        "survey_year": survey_year,
        "included_department_total": included_total,
        "classified_total": len(results),
        "mapping_status_breakdown": dict(status),
        "auto_candidate_rate": round(status["AUTO_CANDIDATE"] / len(results), 4) if results else None,
        "eligibility_breakdown": dict(elig),
        "official_small_series_distribution": dict(
            Counter(r["official_small_series_name"] for r in results).most_common(30)
        ),
        "unclassified_nce_count": sum(
            1 for r in results if r["decision_reason"].startswith("공식 소계열이 미분류")
        ),
        "multi_group_conflict_count": status["REVIEW_REQUIRED"],
        "canonical_group_count": len(groups),
        "departments_per_canonical_group": {
            labels.get(k, k): v for k, v in per_group.most_common()
        },
        "empty_canonical_groups": sorted(
            labels[g] for g in labels if g not in per_group
        ),
        "computer_science_samples": [
            {
                "university": r["university_name"],
                "department": r["department_name"],
                "candidates": r["candidate_canonical_major_ids"],
                "status": r["mapping_status"],
            }
            for r in samples
        ],
        "note": "전부 draft다. 사람 검토 없이 학생 화면용 Mapping으로 승격하지 않는다.",
    }


def main(argv: list[str] | None = None) -> int:
    use_utf8_stdout()
    parser = argparse.ArgumentParser(description="대학알리미 학과 → 대표 전공군 후보 분류(Dry Run)")
    parser.add_argument("--survey-year", type=int, required=True)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args(argv)

    work = args.data_dir / "academyinfo_work" / str(args.survey_year)
    normalized = read_jsonl(work / "departments.normalized.jsonl")
    if not normalized:
        print(f"정규화 결과가 없습니다: {work}", file=sys.stderr)
        return 2

    groups = read_jsonl(GROUPS_PATH)
    index = build_series_index(groups)
    excluded_codes = set(groups[0].get("excluded_series_codes", [])) if groups else set()

    results = [classify(r, index, excluded_codes) for r in normalized]
    write_jsonl(work / "classification_results.jsonl", results)
    write_jsonl(
        work / "classification_review_queue.jsonl",
        [r for r in results if r["mapping_status"] == "REVIEW_REQUIRED"
         or r["eligibility_status"] == ELIGIBILITY_REVIEW],
    )

    report = build_dry_run(results, groups, len(normalized), args.survey_year)
    (work / "classification_dry_run.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"분류 Dry Run — 조사연도 {args.survey_year}")
    print(f"  대상 {len(results)}건 · 전공군 {len(groups)}개")
    for k, v in report["mapping_status_breakdown"].items():
        print(f"  {k:<16} {v}")
    print(f"  자동 후보 비율 {report['auto_candidate_rate']}")
    for k, v in report["eligibility_breakdown"].items():
        print(f"  {k:<24} {v}")
    if report["empty_canonical_groups"]:
        print(f"  ⚠️ 학과가 하나도 없는 전공군: {report['empty_canonical_groups']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
