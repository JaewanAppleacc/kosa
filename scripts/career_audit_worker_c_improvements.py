"""C 단독 개선 감사 산출물을 만든다.

다른 작업자의 Prompt·API·화면·Master 판정을 바꾸지 않고, 이미 커밋된 C 검토
Queue와 평가 fixture를 읽어 다음을 결정론적으로 생성한다.

* 검토 우선순위 초안 (승인 점수가 아닌 작업 순서)
* 실패 유형·Alias 위험·RAG 기대값 감사
* 전국 원본 부재 시 측정 불가 항목의 명시적 상태

실행:
    python scripts/career_audit_worker_c_improvements.py
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
WORK = DATA / "academyinfo_work" / "2025"
AUDIT = DATA / "audit"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def priority_draft(classification: list[dict], nce: list[dict]) -> list[dict]:
    """판정을 건드리지 않고 반복 영향도와 확보 근거만으로 작업 순서를 만든다."""
    combined = [("CLASSIFICATION_REVIEW", row) for row in classification]
    combined += [("NCE_UNMAPPED", row) for row in nce]
    cluster_counts = Counter(
        (kind, row.get("review_cause") or row.get("official_small_series_name") or "OTHER")
        for kind, row in combined
    )
    rows: list[dict] = []
    for kind, row in combined:
        cluster = row.get("review_cause") or row.get("official_small_series_name") or "OTHER"
        repeated = cluster_counts[(kind, cluster)]
        evidence_fields = sum(
            bool(row.get(key))
            for key in ("official_large_series_name", "official_middle_series_name", "official_small_series_name")
        )
        overlap = bool(
            row.get("also_in_unmapped_nce_queue") or row.get("also_in_classification_review_queue")
        )
        # 이 값은 승인 가능성이 아니다. 같은 정책 판단의 파급력과 검토 준비도만 나타낸다.
        workload_priority = min(repeated, 9999) * 10 + evidence_fields + (5 if overlap else 0)
        rows.append({
            "queue_type": kind,
            "source_record_id": row.get("source_record_id"),
            "department_id": row.get("department_id"),
            "university_name": row.get("university_name"),
            "department_name": row.get("department_name"),
            "review_cluster": cluster,
            "cluster_row_count": repeated,
            "cross_queue_overlap": overlap,
            "official_series_fields_present": evidence_fields,
            "workload_priority": workload_priority,
            "priority_meaning": "검토 작업 순서이며 승인 확률·전공 적합도 점수가 아님",
            "review_status": row.get("review_status"),
        })
    return sorted(rows, key=lambda r: (-r["workload_priority"], r["queue_type"], r["source_record_id"] or ""))


def alias_audit() -> dict[str, Any]:
    majors = read_jsonl(DATA / "master" / "canonical_majors.jsonl")
    subjects = read_jsonl(DATA / "master" / "subject_aliases.jsonl")
    targets: dict[str, set[str]] = defaultdict(set)
    raw_labels: dict[str, set[str]] = defaultdict(set)
    for major in majors:
        for alias in [major.get("label"), *(major.get("aliases") or [])]:
            if alias:
                key = re.sub(r"[\s·ㆍ._-]", "", alias).casefold()
                targets[key].add(major["major_id"])
                raw_labels[key].add(alias)
    collisions = [
        {"normalized_alias": key, "aliases": sorted(raw_labels[key]), "major_ids": sorted(ids)}
        for key, ids in sorted(targets.items()) if len(ids) > 1
    ]
    short = [
        {"normalized_alias": key, "aliases": sorted(raw_labels[key]), "major_ids": sorted(ids)}
        for key, ids in sorted(targets.items()) if len(key) <= 2
    ]
    subject_targets: dict[str, set[str]] = defaultdict(set)
    for row in subjects:
        key = re.sub(r"\s", "", row["alias"]).casefold()
        subject_targets[key].add(row["subject_id"])
    subject_collisions = [
        {"normalized_alias": key, "subject_ids": sorted(ids)}
        for key, ids in sorted(subject_targets.items()) if len(ids) > 1
    ]
    return {
        "status": "REVIEW_DRAFT_ONLY",
        "canonical_major_alias_count": sum(len(m.get("aliases") or []) + 1 for m in majors),
        "normalized_major_alias_collision_count": len(collisions),
        "normalized_major_alias_collisions": collisions,
        "short_major_alias_count": len(short),
        "short_major_aliases": short,
        "subject_alias_count": len(subjects),
        "normalized_subject_alias_collision_count": len(subject_collisions),
        "normalized_subject_alias_collisions": subject_collisions,
        "master_changed": False,
    }


def rag_audit() -> dict[str, Any]:
    path = DATA / "eval_fixtures" / "rag_query_expectations.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    queries = payload["queries"]
    positive = [q for q in queries if q["expect_min_results"] > 0]
    negative = [q for q in queries if q["expect_min_results"] == 0]
    hit5 = sum(
        any((q.get("expect_source_contains") or "") in url for url in q["observed_top_source_urls"][:5])
        for q in positive
    )
    correct_empty = sum(not q["observed_top_source_urls"] for q in negative)
    return {
        "fixture_role": "PIPELINE_SMOKE_FIXTURE_NOT_SERVICE_PERFORMANCE",
        "query_count": len(queries),
        "positive_query_count": len(positive),
        "negative_query_count": len(negative),
        "positive_recall_at_5": hit5 / len(positive) if positive else None,
        "no_evidence_accuracy": correct_empty / len(negative) if negative else None,
        "official_source_query_count": 0,
        "sample_source_query_count": len(queries),
        "performance_claim_allowed": False,
        "limitation": "샘플 문서 기반 소규모 fixture이므로 전국 검색 성능으로 해석할 수 없음",
    }


def build() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    classification = read_jsonl(WORK / "classification_review_queue.jsonl")
    nce = read_jsonl(WORK / "unmapped_nce_queue.jsonl")
    priorities = priority_draft(classification, nce)
    normalized = WORK / "departments.normalized.jsonl"
    classified = WORK / "classification_results.jsonl"
    report = {
        "format_version": "worker_c_improvement_audit_v1",
        "scope": "C_ONLY_NO_MASTER_API_UI_MUTATION",
        "review_priority": {
            "row_count": len(priorities),
            "classification_review_count": len(classification),
            "nce_count": len(nce),
            "auto_approved_rows": 0,
            "status_mutated": False,
        },
        "failure_catalog": {
            "classification_cause_breakdown": dict(sorted(Counter(r.get("review_cause") or "OTHER" for r in classification).items())),
            "nce_small_series_breakdown": dict(sorted(Counter(r.get("official_small_series_name") or "UNKNOWN" for r in nce).items())),
            "cross_queue_overlap_count": sum(bool(r.get("also_in_unmapped_nce_queue")) for r in classification),
        },
        "alias_audit": alias_audit(),
        "rag_audit": rag_audit(),
        "minor_field_data_coverage": {
            "status": "SOURCE_MISSING",
            "measured": False,
            "required_inputs": [str(normalized.relative_to(ROOT)), str(classified.relative_to(ROOT))],
            "missing_inputs": [str(p.relative_to(ROOT)) for p in (normalized, classified) if not p.exists()],
            "reason": "전국 정규화·분류 입력은 대용량 비커밋 파일이며 Queue만으로 전체 전공군 분포를 복원할 수 없음",
            "recommendation_performance_claim_allowed": False,
        },
        "claims": {
            "student_recommendation_accuracy_measured": False,
            "multiturn_quality_measured": False,
            "llm_question_quality_measured": False,
        },
    }
    return priorities, report


def main() -> int:
    priorities, report = build()
    write_jsonl(WORK / "review_priority_draft.jsonl", priorities)
    AUDIT.mkdir(parents=True, exist_ok=True)
    (AUDIT / "worker_c_improvement_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"review priority draft: {len(priorities)} rows")
    print("auto approved: 0")
    print(f"minor-field coverage: {report['minor_field_data_coverage']['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
