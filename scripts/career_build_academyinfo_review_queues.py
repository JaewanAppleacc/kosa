"""Master 승격 전 검토 Queue 생성 — A 지시(2026-08-24) §1~§5.

전국 25,389건을 Master로 승격하기 전에, **사람이 처리해야 하는 것**을 재현 가능한
Queue로 분리한다. 정본 정책은 `outputs/handoff/academyinfo_a_decisions.md`.

만드는 것 넷:

    duplicate_department_review_queue.jsonl   같은 department_id에 원본 행이 여럿
    classification_review_queue.jsonl         분류 근거 불충분 (원인별 분리)
    unmapped_nce_queue.jsonl                  표준분류 미분류 — 42개 군에 배정 금지
    department_url_scope_audit.jsonl          URL 37건 재감사

관통하는 원칙 하나 — **자동으로 확정하지 않는다.**

- 대표 행을 재학생 수로 고르지 않는다 (신설 학과는 0명이라 반례가 즉시 나온다)
- 신설·폐지·통합·분리로 단정하지 않는다 (상태 코드는 후보일 뿐이다)
- N.C.E를 학문 분야로 해석하지 않는다 (분류명이 아니라 "분류 없음" 센티널이다)
- 문자열 유사도·LLM만으로 APPROVE하지 않는다

실행:
    python scripts/career_build_academyinfo_review_queues.py --survey-year 2025
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402

# 분류 REVIEW_REQUIRED를 원인별로 가른다 (A 지시 §2).
# 순서가 곧 우선순위다 — 앞에서 걸리면 뒤는 보지 않는다. 한 학과가 여러 원인에
# 걸릴 때 "어느 근거로 보류됐는지"가 하나로 정해져야 검토자가 헷갈리지 않는다.
REVIEW_CAUSE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("HCI_UX", ("HCI", "UX", "UI", "인터랙션", "인터렉션")),
    ("DESIGN", ("디자인",)),
    ("MEDIA_CONTENT", ("미디어", "콘텐츠", "컨텐츠", "영상", "게임", "애니")),
    ("CONVERGENCE", ("융합", "자유전공", "연계", "통합")),
)
CAUSE_SERIES_CONFLICT = "SERIES_NAME_CONFLICT"
CAUSE_OTHER = "OTHER"

# 학과명이 공식 소계열과 어긋나 보이는지 판정할 때 쓰는 최소 신호.
# **이름만으로 확정하지 않는다** — 검토 대상으로 올릴 뿐이다.
SERIES_KEYWORD_HINTS: dict[str, tuple[str, ...]] = {
    "컴퓨터": ("전산", "컴퓨터", "소프트웨어", "인공지능"),
    "전자": ("전자", "전기", "통신", "반도체"),
    "경영": ("경영", "회계", "금융"),
    "간호": ("간호",),
}
ARTS_LARGE_SERIES_NAME = "예체능계열"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows),
        encoding="utf-8",
    )
    return len(rows)


# ── §1 중복 department_id Queue ──────────────────────────────────────────

# 그룹 안에서 실제로 값이 갈리는 필드만 뽑는다. 원본 전체를 복제하지 않는다(A 지시 §1).
DIFF_FIELDS = (
    "department_name", "college_name", "campus", "campus_division_name",
    "admission_unit", "day_night_name", "degree_course_name", "lesson_term_name",
    "department_status", "major_character_name", "source_svy_year",
)

DUPLICATE_CAUSE_HINTS = (
    ("DAY_NIGHT_SPLIT", "day_night_name", "주야간이 갈린다 — 같은 학과의 주간/야간 과정일 수 있다"),
    ("CAMPUS_SPLIT", "campus_division_name", "본교/분교가 갈린다 — 캠퍼스별 동명 학과일 수 있다"),
    ("STATUS_HISTORY", "department_status", "학과 상태가 갈린다 — 폐지 이력이 함께 온 것일 수 있다"),
    ("DEGREE_SPLIT", "degree_course_name", "학위과정이 갈린다"),
    ("TERM_SPLIT", "lesson_term_name", "수업연한이 갈린다"),
    ("ADMISSION_UNIT_SPLIT", "admission_unit", "모집단위가 갈린다"),
)


def build_duplicate_queue(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        grouped[r["department_id"]].append(r)

    queue: list[dict[str, Any]] = []
    for department_id, group in sorted(grouped.items()):
        if len(group) < 2:
            continue

        differing = [
            f for f in DIFF_FIELDS
            if len({json.dumps(g.get(f), ensure_ascii=False) for g in group}) > 1
        ]
        causes = [
            {"cause": code, "field": field, "note": note}
            for code, field, note in DUPLICATE_CAUSE_HINTS
            if field in differing
        ]
        if not causes:
            causes = [{
                "cause": "UNKNOWN",
                "field": None,
                "note": "검사한 필드에서 차이를 찾지 못했다 — 원본을 직접 확인해야 한다",
            }]

        head = group[0]
        queue.append({
            "department_id": department_id,
            "source_record_ids": sorted(g.get("source_record_id") for g in group),
            "record_count": len(group),
            "university_name": head.get("university_name"),
            "campus": head.get("campus"),
            "department_name": head.get("department_name"),
            "college_name": head.get("college_name"),
            "candidates": [
                {
                    "source_record_id": g.get("source_record_id"),
                    "schl_mjr_id": g.get("source_schl_mjr_id"),
                    "department_name": g.get("department_name"),
                    "college_name": g.get("college_name"),
                    "campus": g.get("campus"),
                    "admission_unit": g.get("admission_unit"),
                    "day_night_name": g.get("day_night_name"),
                    "degree_course_name": g.get("degree_course_name"),
                    "department_status": g.get("department_status"),
                    "survey_year": g.get("source_svy_year"),
                    # 재학생 수는 **보여주되 자동 선택에 쓰지 않는다**. 신설 학과는 0명이다.
                    "enrolled_count": g.get("enrolled_count"),
                    "graduate_count": g.get("graduate_count"),
                }
                for g in group
            ],
            "differing_fields": differing,
            "duplicate_cause_candidates": causes,
            # 자동 대표 행 선정 금지 (A 지시 §1)
            "decision_status": "REVIEW_REQUIRED",
            "selected_source_record_id": None,
            "reviewer_id": None,
            "reviewer_comment": None,
            "review_note": (
                "대표 행을 자동으로 고르지 않았다. 재학생 수가 많은 행을 기준으로 삼지 말 것 — "
                "신설 학과는 재학생이 0명이라 그 기준이 즉시 반례를 만든다. "
                "신설·폐지·통합·분리로 단정하지 말고 공식 근거로 확인할 것."
            ),
        })
    return queue


# ── §2 분류 REVIEW_REQUIRED Queue ────────────────────────────────────────

def classify_review_cause(row: dict[str, Any]) -> tuple[str, str]:
    """보류 원인을 하나로 정한다. 이름 신호가 없으면 계열-학과명 충돌을 본다."""
    text = f"{row.get('department_name') or ''} {row.get('college_name') or ''}"
    for cause, keywords in REVIEW_CAUSE_PATTERNS:
        hit = next((k for k in keywords if k in text), None)
        if hit:
            return cause, f"학과·단과대학 명칭에 '{hit}'이(가) 있어 공식 교육과정 확인이 필요하다"

    small = row.get("official_small_series_name") or ""
    for series_key, keywords in SERIES_KEYWORD_HINTS.items():
        if series_key in small and not any(k in text for k in keywords):
            return (
                CAUSE_SERIES_CONFLICT,
                f"공식 소계열은 '{small}'인데 학과명에 대응 표현이 없다 — 표기 차이인지 분류 오류인지 확인 필요",
            )
    return CAUSE_OTHER, (row.get("eligibility_reason") or "공식 대계열 근거가 불충분하다")


def build_classification_queue(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    for r in results:
        if r.get("eligibility_status") != "REVIEW_REQUIRED":
            continue
        cause, reason = classify_review_cause(r)
        large = r.get("official_large_series_code")
        queue.append({
            "department_id": r["department_id"],
            "source_record_id": r.get("source_record_id"),
            "university_name": r.get("university_name"),
            "department_name": r.get("department_name"),
            "college_name": r.get("college_name"),
            "official_large_series_name": r.get("official_large_series_name"),
            "official_middle_series_name": r.get("official_middle_series_name"),
            "official_small_series_name": r.get("official_small_series_name"),
            "self_series_name": r.get("self_series_name"),
            "candidate_canonical_major_ids": r.get("candidate_canonical_major_ids", []),
            "multiple_candidate_reason": (
                r.get("decision_reason") if len(r.get("candidate_canonical_major_ids", [])) > 1
                else None
            ),
            "review_cause": cause,
            "review_reason": reason,
            # 예체능 가능성은 **판정이 아니라 확인 대상**이다.
            "arts_sports_possibility": (
                "CONFIRMED_BY_OFFICIAL_SERIES" if r.get("official_large_series_name") == ARTS_LARGE_SERIES_NAME
                else "POSSIBLE_NEEDS_CHECK" if cause in ("DESIGN", "MEDIA_CONTENT", "HCI_UX")
                else "UNLIKELY"
            ),
            "official_evidence_needed": [
                "공식 교육과정(개설 교과목)",
                "공식 단과대학 소속",
                "공식 입학전형 자료의 실기·실적 전형 여부",
            ] if cause in ("DESIGN", "MEDIA_CONTENT", "HCI_UX", "CONVERGENCE")
            else ["공식 소계열 분류 근거", "학과 교육목표"],
            "review_status": "REVIEW_REQUIRED",
            "reviewer_id": None,
            "reviewer_comment": None,
            "review_note": (
                "문자열 유사도나 LLM 결과만으로 APPROVE하지 말 것. "
                "공식 자료로 확인한 뒤에만 상태를 바꾼다."
            ),
            "_large_series_code": large,
        })
    for q in queue:
        q.pop("_large_series_code", None)
    return queue


# ── §3 N.C.E UNMAPPED Queue ──────────────────────────────────────────────

def build_nce_queue(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """N.C.E는 42개 군에 배정하지 않는다. 후속 공식 근거가 생겨야 승격 가능하다."""
    queue: list[dict[str, Any]] = []
    for r in results:
        reason = r.get("decision_reason") or ""
        if not reason.startswith("공식 소계열이 미분류"):
            continue
        queue.append({
            "department_id": r["department_id"],
            "source_record_id": r.get("source_record_id"),
            "university_name": r.get("university_name"),
            "department_name": r.get("department_name"),
            "college_name": r.get("college_name"),
            "official_large_series_name": r.get("official_large_series_name"),
            "official_middle_series_name": r.get("official_middle_series_name"),
            "official_small_series_name": r.get("official_small_series_name"),
            "self_series_name": r.get("self_series_name"),
            # 강제 배정 금지 — 빈 목록으로 고정한다.
            "candidate_canonical_major_ids": [],
            "mapping_status": "UNMAPPED",
            "unmapped_reason": "표준분류 미분류(N.C.E) — 분류명이 아니라 '분류 없음' 센티널이다",
            "promotion_condition": (
                "대학알리미 공식 소계열이 채워지거나, 공식 교육과정·교육목표 근거가 확보되면 "
                "그때 분류 후보를 만든다. 학과명 유사도로 배정하지 않는다."
            ),
            "review_status": "UNMAPPED",
            "reviewer_id": None,
            "reviewer_comment": None,
        })
    return queue


# ── §4 URL Scope 감사 ────────────────────────────────────────────────────

API_KEY_PATTERN = re.compile(r"serviceKey|apikey|api_key|access_token", re.I)
OFFICIAL_DOMAIN_PATTERN = re.compile(r"\.(ac\.kr|edu)(/|$|:)", re.I)


def audit_url(row: dict[str, Any]) -> dict[str, Any] | None:
    url = row.get("department_url")
    if not url:
        return None
    scope = row.get("department_url_scope") or "unknown"
    findings: list[str] = []

    is_official = bool(OFFICIAL_DOMAIN_PATTERN.search(url))
    if not is_official:
        findings.append("공식 대학 도메인(.ac.kr/.edu)이 아니다")
    if API_KEY_PATTERN.search(url):
        findings.append("URL에 API Key로 보이는 쿼리가 있다")
    if "academyinfo.go.kr" in url:
        findings.append("대학알리미 URL이다 — 학과 홈페이지가 아니다")
    if "data.go.kr" in url:
        findings.append("공공데이터포털 URL이다 — 학과 홈페이지가 아니다")
    https_ok = url.lower().startswith("https://")
    if not https_ok:
        # HTTP라는 사실만으로 REVIEW로 올리지 않는다. 실측 결과 이 3건은 학교 서버가
        # HTTPS를 아예 열지 않는다(https:// 로 바꾸면 ConnectError). 우리가 고칠 수 있는
        # 문제가 아니라 "그 학교가 아직 HTTP만 쓴다"는 사실이다 — 사실로 기록하고
        # 공개 여부는 A가 정하게 둔다.
        findings.append("HTTP만 제공 — 해당 학교 서버가 HTTPS를 열지 않음(실측 확인)")

    # 학과 홈페이지가 아닌 것으로 판명된 URL만 REVIEW로 올린다.
    blocking = [f for f in findings if ("API Key" in f or "대학알리미" in f or "공공데이터" in f
                                        or "공식 대학 도메인" in f)]
    if blocking:
        status = "REVIEW_REQUIRED"
    elif scope == "college":
        # A 결정 §5: college scope는 공개 시 항상 None. 값과 사유는 보존한다.
        status = "COLLEGE_SCOPE_KEEP_INTERNAL"
    elif scope == "department":
        # HTTP-only는 공개를 막지 않는다. 공개 시 http 그대로 쓸지는 A 판단이다.
        status = "DEPARTMENT_SCOPE_CONFIRMED"
    else:
        status = "REVIEW_REQUIRED"

    return {
        "university_name": row.get("university_name"),
        "department_name": row.get("department_name"),
        "college_name": row.get("college_name"),
        "department_url": url,
        "department_url_scope": scope,
        "department_url_note": row.get("department_url_note"),
        "is_official_university_domain": is_official,
        "uses_https": https_ok,
        "https_available": https_ok or None,  # False가 아니라 None — 실측하지 않은 건과 구분
        "contains_api_key": bool(API_KEY_PATTERN.search(url)),
        "findings": findings,
        "audit_status": status,
        # A 결정 §5: department scope만 공개 후보다.
        "eligible_for_public_department_url": status == "DEPARTMENT_SCOPE_CONFIRMED",
        "reviewer_id": None,
        "reviewer_comment": None,
    }


def main(argv: list[str] | None = None) -> int:
    use_utf8_stdout()
    parser = argparse.ArgumentParser(description="Master 승격 전 검토 Queue 생성")
    parser.add_argument("--survey-year", type=int, default=2025)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args(argv)

    work = args.data_dir / "academyinfo_work" / str(args.survey_year)
    normalized = read_jsonl(work / "departments.normalized.jsonl")
    results = read_jsonl(work / "classification_results.jsonl")
    raw_demo = read_jsonl(args.data_dir / "raw" / "departments.raw.jsonl")
    if not normalized or not results:
        print(f"정규화·분류 결과가 없습니다: {work}", file=sys.stderr)
        return 2

    dup = build_duplicate_queue(normalized)
    cls = build_classification_queue(results)
    nce = build_nce_queue(results)

    # 한 학과가 두 Queue에 동시에 오를 수 있다. 버그가 아니라 **축이 다르기 때문**이다 —
    # "어느 전공군인가"(분류)와 "추천해도 되나"(적격성)는 별개 질문이고 둘 다 미결일 수 있다.
    # 겹침을 없애면 한쪽 근거가 사라지므로, 없애는 대신 서로 가리키게 해서
    # 검토자가 같은 학과를 두 번 볼 때 "왜 또 나오지"로 헷갈리지 않게 한다.
    nce_ids = {q["source_record_id"] for q in nce}
    cls_ids = {q["source_record_id"] for q in cls}
    overlap = nce_ids & cls_ids
    for q in cls:
        q["also_in_unmapped_nce_queue"] = q["source_record_id"] in overlap
    for q in nce:
        q["also_in_classification_review_queue"] = q["source_record_id"] in overlap
    urls = [a for a in (audit_url(r) for r in raw_demo) if a]

    write_jsonl(work / "duplicate_department_review_queue.jsonl", dup)
    write_jsonl(work / "classification_review_queue.jsonl", cls)
    write_jsonl(work / "unmapped_nce_queue.jsonl", nce)
    write_jsonl(work / "department_url_scope_audit.jsonl", urls)

    report = {
        "survey_year": args.survey_year,
        "duplicate_group_count": len(dup),
        "duplicate_record_count": sum(q["record_count"] for q in dup),
        "duplicate_cause_breakdown": dict(
            Counter(c["cause"] for q in dup for c in q["duplicate_cause_candidates"])
        ),
        "classification_review_count": len(cls),
        "classification_cause_breakdown": dict(Counter(q["review_cause"] for q in cls)),
        "arts_possibility_breakdown": dict(Counter(q["arts_sports_possibility"] for q in cls)),
        "nce_queue_count": len(nce),
        "nce_and_classification_overlap_count": len(overlap),
        "overlap_note": (
            "N.C.E(분류 근거 없음)와 분류 REVIEW(추천 적격성 미정)는 서로 다른 축이라 "
            "같은 학과가 양쪽에 오를 수 있다. 겹치는 행은 양쪽에 상호 참조 플래그를 붙였다."
        ),
        "url_audit_count": len(urls),
        "url_audit_breakdown": dict(Counter(u["audit_status"] for u in urls)),
        "url_scope_breakdown": dict(Counter(u["department_url_scope"] for u in urls)),
        "public_department_url_candidates": sum(1 for u in urls if u["eligible_for_public_department_url"]),
        "note": "전부 검토 대기다. 자동 승인·자동 대표 선정·강제 매핑을 하지 않았다.",
    }
    (work / "review_queue_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"검토 Queue 생성 — 조사연도 {args.survey_year}")
    print(f"  중복 그룹        {len(dup):>6}  (원본 행 {report['duplicate_record_count']})")
    print(f"  분류 REVIEW      {len(cls):>6}")
    for k, v in report["classification_cause_breakdown"].items():
        print(f"      {k:<20} {v}")
    print(f"  N.C.E UNMAPPED   {len(nce):>6}  (분류 REVIEW와 겹침 {len(overlap)})")
    print(f"  URL 감사         {len(urls):>6}  {report['url_audit_breakdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
