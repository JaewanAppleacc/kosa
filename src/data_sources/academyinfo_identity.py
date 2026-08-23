"""학과 식별자 — A 지시 §5.

원본 행과 "학과 실체"를 분리한다. 하나의 id로 두 질문에 답하려던 것이 §7-8의 혼란이었다.

    source_record_id   schlId + schlMjrId + 조사연도
                       "이 행은 대학알리미 어느 연도 어느 원본 행인가"
                       연도가 들어간다. 연도마다 새로 생기는 것이 정상이다.

    department_id      학교 + 정규화 학과명 + 단과대학
                       "이건 작년 그 학과와 같은 학과인가"
                       연도가 들어가지 않는다. src/ids.py의 기존 규칙을 그대로 쓴다.

`schlMjrId`를 `department_id`로 쓰지 않는다 — 대학알리미가 학과를 재등록하면 값이 바뀌고,
그러면 같은 학과가 연도마다 다른 id를 받아 매핑·검토 이력이 끊긴다.

`src/ids.py`는 A 소유다. 규칙을 바꿔야 한다고 판단되면 비교 보고와 변경안을 A에게 제출한다.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any, Iterable, Mapping


def generate_source_record_id(schl_id: str, schl_mjr_id: str, survey_year: int | str) -> str:
    """특정 연도 원본 행 식별자. 결정론적이어야 재수집 결과를 대조할 수 있다."""
    payload = "|".join([schl_id.strip(), schl_mjr_id.strip(), str(survey_year).strip()])
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"src_{digest}"


def build_lineage(
    current: Iterable[Mapping[str, Any]], previous: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """연도 간 학과 실체를 잇는다.

    `department_id`(연도 무관)로 맞추고, `schlMjrId`가 유지됐는지를 함께 본다.
    **판정하지 않는다** — 상태만 붙여 검토 자료로 남긴다.
    """
    prev_by_dept: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in previous:
        prev_by_dept[row["department_id"]].append(row)

    lineage: list[dict[str, Any]] = []
    for row in current:
        dept_id = row["department_id"]
        matches = prev_by_dept.get(dept_id, [])
        cur_mjr = row.get("source_schl_mjr_id")
        prev_mjr = [m.get("source_schl_mjr_id") for m in matches]

        if not matches:
            status = "NEW_IN_LATEST"          # 직전 연도에 같은 학과 실체가 없다
        elif cur_mjr in prev_mjr:
            status = "STABLE"                 # 학과도 schlMjrId도 유지
        else:
            status = "SCHL_MJR_ID_CHANGED"    # 같은 학과인데 원본 행 id가 바뀌었다
        lineage.append(
            {
                "department_id": dept_id,
                "university_name": row.get("university_name"),
                "department_name": row.get("department_name"),
                "college_name": row.get("college_name"),
                "latest_schl_mjr_id": cur_mjr,
                "previous_schl_mjr_ids": prev_mjr,
                "status": status,
            }
        )

    # 직전 연도에만 있던 학과 — 폐지·개칭 후보다. 조용히 사라지게 두지 않는다.
    current_ids = {row["department_id"] for row in current}
    for dept_id, matches in prev_by_dept.items():
        if dept_id in current_ids:
            continue
        head = matches[0]
        lineage.append(
            {
                "department_id": dept_id,
                "university_name": head.get("university_name"),
                "department_name": head.get("department_name"),
                "college_name": head.get("college_name"),
                "latest_schl_mjr_id": None,
                "previous_schl_mjr_ids": [m.get("source_schl_mjr_id") for m in matches],
                "status": "MISSING_IN_LATEST",
            }
        )
    return lineage


def build_resolution_review_queue(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """같은 `department_id`에 원본 행이 여럿인 건을 검토 대기로 만든다.

    **자동으로 한 행을 고르지 않는다.** 재학생 수 최대값으로 대표 행을 뽑고 싶어지지만,
    신설 학과는 재학생이 0명이라 반례가 즉시 나온다(A 지시 §5).
    """
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["department_id"]].append(row)

    queue: list[dict[str, Any]] = []
    for dept_id, group in grouped.items():
        if len(group) < 2:
            continue
        head = group[0]
        queue.append(
            {
                "department_id": dept_id,
                "university_name": head.get("university_name"),
                "department_name": head.get("department_name"),
                "college_name": head.get("college_name"),
                "candidate_count": len(group),
                "candidates": [
                    {
                        "source_record_id": g.get("source_record_id"),
                        "schl_mjr_id": g.get("source_schl_mjr_id"),
                        "department_status": g.get("department_status"),
                        "enrolled_count": g.get("enrolled_count"),
                        "graduate_count": g.get("graduate_count"),
                        "lesson_term_name": g.get("lesson_term_name"),
                    }
                    for g in group
                ],
                "review_status": "REVIEW_REQUIRED",
                "review_reason": (
                    "같은 department_id로 원본 행이 여럿이다. 어느 schlMjrId가 현행인지 "
                    "사람이 확인해야 한다 — 재학생 수만으로 고르지 않는다(신설 학과는 0명)."
                ),
            }
        )
    return queue


def retention_stats(lineage: list[Mapping[str, Any]]) -> dict[str, Any]:
    """`schlMjrId` 유지율. A 지시 §4의 보고 항목."""
    counts: dict[str, int] = defaultdict(int)
    for row in lineage:
        counts[str(row["status"])] += 1
    matched = counts["STABLE"] + counts["SCHL_MJR_ID_CHANGED"]
    return {
        "stable": counts["STABLE"],
        "schl_mjr_id_changed": counts["SCHL_MJR_ID_CHANGED"],
        "new_in_latest": counts["NEW_IN_LATEST"],
        "missing_in_latest": counts["MISSING_IN_LATEST"],
        "matched_department_count": matched,
        "schl_mjr_id_retention_rate": round(counts["STABLE"] / matched, 4) if matched else None,
    }
