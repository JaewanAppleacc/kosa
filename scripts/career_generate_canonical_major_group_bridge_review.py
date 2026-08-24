"""Canonical Major Group ↔ Canonical Major Bridge 검수 자료 생성 — 2026-08-24
지시서(Bridge 계약) §5/§6.

`outputs/reviews/canonical_major_group_bridge_review.md`를 만든다. 이 스크립트는
어떤 Bridge 행도 승인(approve)하지 않는다 — 지금 저장된 draft 상태를 그대로
읽어서 사람이 검토하기 좋은 표로 옮길 뿐이다("사용자 검토 결과" 열은 항상
비워 둔다).

§6 영향 분석 수치는 "승격 전 후보 분석"이다 — 실제 추천 API가 이 Bridge를 아직
전혀 참조하지 않으므로(§3), 여기 나온 학과 후보 수는 학생에게 보이는 추천
결과가 아니다.

실행:
    PYTHONPATH=. python scripts/career_generate_canonical_major_group_bridge_review.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402

from src.engines.canonical_mapper import load_canonical_majors  # noqa: E402
from src.services.canonical_major_group_bridge_loader import (  # noqa: E402
    ARTS_EXCLUDED_GROUP_IDS,
    DEFAULT_CANONICAL_MAJORS_PATH,
    load_canonical_major_group_bridge,
)
from src.services.canonical_major_group_draft_loader import load_canonical_major_groups_draft  # noqa: E402

OUTPUT_PATH = ROOT / "outputs" / "reviews" / "canonical_major_group_bridge_review.md"
_CLASSIFICATION_DRY_RUN_PATH = ROOT / "data" / "academyinfo_work" / "2025" / "classification_dry_run.json"
_REPRESENTATIVE_MAJOR_IDS = ("media_communication", "industrial_engineering", "hci_ux")


def _load_departments_per_group_label() -> dict[str, int]:
    if not _CLASSIFICATION_DRY_RUN_PATH.exists():
        return {}
    data = json.loads(_CLASSIFICATION_DRY_RUN_PATH.read_text(encoding="utf-8"))
    return data.get("departments_per_canonical_group", {})


def _unclassified_nce_count() -> int:
    if not _CLASSIFICATION_DRY_RUN_PATH.exists():
        return 0
    data = json.loads(_CLASSIFICATION_DRY_RUN_PATH.read_text(encoding="utf-8"))
    return int(data.get("unclassified_nce_count", 0))


def _excluded_arts_sports_count() -> int | None:
    """`eligibility_breakdown.EXCLUDED_ARTS_SPORTS`를 매번 파일에서 직접 읽는다 —
    이 값을 과거에 문자열로 하드코딩했다가 worker-c가 주간 학사과정만 추천 범위로
    제한하면서(2026-08-24) 3667 -> 3588로 바뀐 걸 놓쳐 문서가 낡은 값을 계속
    보여준 적이 있다(회귀 검증 중 발견). 같은 문제가 다시 생기지 않도록 항상
    실측한다."""

    if not _CLASSIFICATION_DRY_RUN_PATH.exists():
        return None
    data = json.loads(_CLASSIFICATION_DRY_RUN_PATH.read_text(encoding="utf-8"))
    value = data.get("eligibility_breakdown", {}).get("EXCLUDED_ARTS_SPORTS")
    return int(value) if value is not None else None


def _render_markdown() -> str:
    report = load_canonical_major_group_bridge()
    groups_by_id = {g.canonical_major_id: g for g in load_canonical_major_groups_draft()}
    majors_by_id = {m.major_id: m for m in load_canonical_majors(DEFAULT_CANONICAL_MAJORS_PATH)}
    dept_counts_by_label = _load_departments_per_group_label()

    def dept_count_for_group(group_id: str) -> int:
        label = groups_by_id[group_id].label
        return dept_counts_by_label.get(label, 0)

    lines: list[str] = []
    lines.append("# Canonical Major Group ↔ Canonical Major Bridge 검수 자료")
    lines.append("")
    lines.append(
        "대학알리미 표준분류 소계열 158개를 묶은 42개 Canonical Major Group(분류용 "
        "중간 Ontology)과, 학생에게 실제로 보여주는 10개 서비스 추천 전공"
        "(`data/master/canonical_majors.jsonl`) 사이의 연결을 명시적으로 남긴 자료다. "
        "**42개 Group은 10개 추천 전공을 대체하지 않는다** — 이 문서는 두 계층을 잇는 "
        "다리(Bridge)의 현재 draft 상태를 보여줄 뿐이다."
    )
    lines.append("")
    lines.append(
        "**이 문서의 어떤 항목도 이미 승인(APPROVE)된 것이 아니다.** \"현재 상태\" 열은 "
        "시스템이 계산한 분류 판단(`mapping_status`)이고, \"사용자 검토 결과\" 열은 사람이 "
        "실제로 검토하기 전까지 항상 빈 칸이다."
    )
    lines.append("")

    # ---- §6 영향 분석(승격 전 후보 분석 — 추천 결과 아님) ----
    lines.append("## 1. 영향 분석 (승격 전 후보 분석 — 실제 추천 결과가 아님)")
    lines.append("")
    lines.append(
        "아래 수치는 `data/master/canonical_major_group_bridge.draft.jsonl`(모두 draft 상태)과 "
        "`data/academyinfo_work/2025/classification_dry_run.json`(분류 단계 집계)을 그대로 "
        "센 것이다. 공개 API·Matching은 이 Bridge를 아직 전혀 참조하지 않는다(§3) — 학생에게 "
        "보이는 추천 결과와 무관하다."
    )
    lines.append("")

    lines.append("### 1-1. 기존 10개 Major별 연결 Group 후보 수")
    lines.append("")
    lines.append("| major_id | label | 연결 Group 후보 수 | 상태 구성 |")
    lines.append("|---|---|---|---|")
    for major_id in sorted(majors_by_id):
        rows = report.entries_for_major(major_id)
        status_counts: dict[str, int] = {}
        for r in rows:
            status_counts[r.mapping_status] = status_counts.get(r.mapping_status, 0) + 1
        status_desc = ", ".join(f"{k} {v}" for k, v in sorted(status_counts.items()))
        lines.append(f"| {major_id} | {majors_by_id[major_id].label} | {len(rows)} | {status_desc} |")
    lines.append("")

    lines.append("### 1-2. 대표 전공 3개와 연결 가능한 전국 학과 후보 수 (승격 전)")
    lines.append("")
    lines.append("| major_id | 연결 Group(상태) | 그 Group의 학과 후보 수 | 비고 |")
    lines.append("|---|---|---|---|")
    for major_id in _REPRESENTATIVE_MAJOR_IDS:
        rows = report.entries_for_major(major_id)
        for r in rows:
            note = "확정 아님 — 사람 검토 필요" if r.mapping_status == "REVIEW_REQUIRED" else "확정 아님 — Bridge 자체가 draft"
            lines.append(
                f"| {major_id} | {r.canonical_major_group_id}({r.mapping_status}) | "
                f"{dept_count_for_group(r.canonical_major_group_id)} | {note} |"
            )
    lines.append("")

    review_required_rows = report.entries_by_status("REVIEW_REQUIRED")
    review_required_dept_total = sum(dept_count_for_group(r.canonical_major_group_id) for r in review_required_rows)
    lines.append("### 1-3. REVIEW_REQUIRED로 인해 확정에서 제외되는 수")
    lines.append("")
    lines.append(f"- REVIEW_REQUIRED Bridge 행 수: {len(review_required_rows)}")
    lines.append(f"- 그 행들이 가리키는 Group의 학과 후보 수 합계(중복 Group 있으면 중복 합산): {review_required_dept_total}")
    lines.append("")

    excluded_rows = report.entries_by_status("EXCLUDED_RECOMMENDATION")
    excluded_group_ids = sorted({r.canonical_major_group_id for r in excluded_rows})
    excluded_dept_total = sum(dept_count_for_group(gid) for gid in excluded_group_ids)
    lines.append("### 1-4. 예체능 제외 수")
    lines.append("")
    lines.append(f"- EXCLUDED_RECOMMENDATION Group 수: {len(excluded_group_ids)}개 ({', '.join(excluded_group_ids)})")
    lines.append(f"- 그 Group들의 학과 후보 수 합계(`departments_per_canonical_group` 기준): {excluded_dept_total}")
    dry_run_excluded_arts_sports = _excluded_arts_sports_count()
    if dry_run_excluded_arts_sports is not None:
        lines.append(
            f"- 참고: `classification_dry_run.json`의 `eligibility_breakdown.EXCLUDED_ARTS_SPORTS` = "
            f"{dry_run_excluded_arts_sports}(분류 자격 판정 단계 집계, Group 배정 이후 집계인 위 "
            f"{excluded_dept_total}과 집계 시점이 달라 정확히 일치하지 않는다 — 두 수치를 그대로 병기한다)."
        )
    lines.append("")

    unmapped_rows = report.entries_by_status("UNMAPPED")
    unmapped_dept_total = sum(dept_count_for_group(r.canonical_major_group_id) for r in unmapped_rows)
    lines.append("### 1-5. N.C.E / UNMAPPED 수")
    lines.append("")
    lines.append(f"- Bridge UNMAPPED Group 수(10개 서비스 전공 중 대응 항목 없음): {len(unmapped_rows)}개")
    lines.append(f"- 그 Group들의 학과 후보 수 합계: {unmapped_dept_total}")
    lines.append(
        f"- N.C.E(대학알리미 표준분류 미분류, 42개 Group 어디에도 배정되지 않음) 원본 학과 수: "
        f"{_unclassified_nce_count()}건(`classification_dry_run.json`의 `unclassified_nce_count` — "
        "이 수는 Bridge의 UNMAPPED와 별개다. Bridge UNMAPPED는 \"42개 Group 중 하나로는 분류됐지만 "
        "10개 서비스 전공에는 대응이 없다\"이고, N.C.E는 \"애초에 42개 Group 중 어디에도 분류되지 "
        "않았다\"이다.)"
    )
    lines.append("")

    # ---- §5 42개 Group 전체 표 ----
    lines.append("## 2. 42개 Group 전체 — 연결 후보·근거·경계 사례")
    lines.append("")
    lines.append(
        "| Group ID | Group 라벨 | 공식 소계열 코드·명칭 | 연결 후보 Major | 근거 | 경계 사례 | 현재 상태 | 사용자 검토 결과 | Scope |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for group_id in sorted(groups_by_id):
        group = groups_by_id[group_id]
        codes_desc = ", ".join(group.included_official_small_series_codes)
        rows = sorted(report.entries_for_group(group_id), key=lambda r: (r.canonical_major_id or "", r.mapping_status))
        if not rows:
            lines.append(f"| {group_id} | {group.label} | {codes_desc} | (없음) | (없음) | (없음) | (없음) | | |")
            continue
        for r in rows:
            major_desc = r.canonical_major_id if r.canonical_major_id else "(대응 없음)"
            evidence_desc = "; ".join(r.evidence) if r.evidence else "(없음)"
            boundary_desc = r.boundary_notes or "(없음)"
            lines.append(
                f"| {group_id} | {group.label} | {codes_desc} | {major_desc} | {evidence_desc} | "
                f"{boundary_desc} | {r.mapping_status} | | {_scope_desc(r)} |"
            )
    lines.append("")

    lines.append("## 3. 근거 문장(decision_reason) 상세")
    lines.append("")
    lines.append("표가 좁아 잘리는 근거 설명 전문을 Group 순서대로 남긴다.")
    lines.append("")
    for group_id in sorted(groups_by_id):
        rows = sorted(report.entries_for_group(group_id), key=lambda r: (r.canonical_major_id or "", r.mapping_status))
        for r in rows:
            major_desc = r.canonical_major_id if r.canonical_major_id else "(대응 없음)"
            lines.append(f"- **{group_id} → {major_desc}** ({r.mapping_status}): {r.decision_reason}")
    lines.append("")

    # ---- §2 Scope 상세(2026-08-24 a/canonical-major-bridge-scope 지시서) ----
    lines.append("## 4. Scope 상세 — 전공군 전체 대신 좁힌 범위")
    lines.append(
        "\n42개 Group ↔ 10개 Major 연결이 있다고 해서 그 Group의 공식 소계열 전체를 그대로 "
        "추천 학과 후보로 써도 되는 것은 아니다. 아래는 각 연결 행의 `scope_type`(FULL_GROUP/"
        "INCLUDED_SMALL_SERIES_ONLY/DEPARTMENT_REVIEW_REQUIRED/EXCLUDED_RECOMMENDATION)과, "
        "소계열 단위로 좁힌 경우 실제 포함/제외 코드다. **이 Scope 값도 아직 draft다** — "
        "`scope_review_status`가 \"approved\"인 행은 하나도 없다(사람이 아직 이 Scope 자체를 "
        "검토한 적이 없다)."
    )
    lines.append("")
    scoped_rows = [r for r in report.entries if r.scope_type is not None]
    lines.append("| Group ID | 연결 Major | scope_type | included_small_series_codes | excluded_small_series_codes | scope_review_status |")
    lines.append("|---|---|---|---|---|---|")
    for r in sorted(scoped_rows, key=lambda r: (r.canonical_major_group_id, r.canonical_major_id or "")):
        major_desc = r.canonical_major_id if r.canonical_major_id else "(대응 없음)"
        lines.append(
            f"| {r.canonical_major_group_id} | {major_desc} | {r.scope_type} | "
            f"{', '.join(r.included_small_series_codes) or '(없음)'} | "
            f"{', '.join(r.excluded_small_series_codes) or '(없음)'} | {r.scope_review_status} |"
        )
    lines.append("")
    narrowed = [r for r in report.entries if r.scope_type == "INCLUDED_SMALL_SERIES_ONLY"]
    department_review = [r for r in report.entries if r.scope_type == "DEPARTMENT_REVIEW_REQUIRED"]
    lines.append(
        f"- INCLUDED_SMALL_SERIES_ONLY(소계열 일부만 포함) 행 수: {len(narrowed)}"
        f"({', '.join(f'{r.canonical_major_group_id}->{r.canonical_major_id}' for r in narrowed)})"
    )
    lines.append(
        f"- DEPARTMENT_REVIEW_REQUIRED(학과 개별 검토 필요) 행 수: {len(department_review)}"
        f"({', '.join(f'{r.canonical_major_group_id}->{r.canonical_major_id}' for r in department_review)})"
    )
    lines.append("")
    for r in narrowed:
        lines.append(
            f"- **{r.canonical_major_group_id} → {r.canonical_major_id}**: {r.scope_decision_reason}"
        )
    for r in department_review:
        lines.append(
            f"- **{r.canonical_major_group_id} → {r.canonical_major_id}**: {r.scope_decision_reason}"
        )
    lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"


def _scope_desc(entry) -> str:
    if entry.scope_type is None:
        return "(해당 없음)"
    if entry.scope_type == "INCLUDED_SMALL_SERIES_ONLY":
        return f"INCLUDED_SMALL_SERIES_ONLY({', '.join(entry.included_small_series_codes)})"
    return entry.scope_type


def main() -> None:
    use_utf8_stdout()
    markdown = _render_markdown()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(markdown, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
