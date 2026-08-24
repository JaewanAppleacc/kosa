"""Department Offering Identity v2 — 행 단위 재검증 — 2026-08-25 지시서
(a/offering-identity-v2) §4/§6.

`career_build_national_department_promotion_dry_run.py`(24,422행 전체
실행)는 이번 라운드의 검증 범위가 아니다 — 그 스크립트는 실제 전국 복원
데이터(이 저장소에 없음, `academyinfo-data-restore` Worktree 전용)가 있어야
돌아가고, 그 산출물은 Git에 올리지 않는 관례(2026-08-24 감사 라운드에서
이미 확정)를 따른다. 이번 검증은 **이 라운드가 실제로 건드린 범위**(16
Group·32행의 사람 판정과 offering_id 배정)에 정확히 한정한다 — 이 사실을
숨기지 않고 아래 보고서에 명시한다.

확인 항목(§4/§6):
- offering_id 중복 0건(`JsonlDepartmentOfferingRepository` 생성 자체가
  증명 — 중복이면 예외를 던진다)
- 계약학과·산업체위탁 제외가 기존 패킷의 `exclusion_reason=CONTRACT_DEPARTMENT`
  표시와 모순되지 않는지(기존 태그가 있던 행은 전부 새 판정에서도 제외돼야
  한다)
- 일반과정 대표 6건(원 지시서 "7건"은 2026-08-25 사용자 확인으로 6건이
  정본) 보존
- 성균관대 반도체시스템공학과(dept_4b358345687aed927da6a9fa) 추천 대표 없음
- 충남대 약학과(dept_6ea537f2938a79ba48bef719)는 6년 일반과정만 추천 범위
- 자동 대표 판정 오류 6건(자동 Dry Run의 `evaluated_representative_source_record_id`
  와 사람이 고른 대표가 실제로 다르면서, 사람 판정이 유효한 대표를 찾아낸
  경우만 "의미 있는 교정"으로 센다)이 사람 판정대로 교정됐는지
- 미결 그룹 0건(32행 전부 reviewer_1_status=APPROVE)"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.repositories.department_offering_repository import JsonlDepartmentOfferingRepository
from src.services.department_identity_collision_row_review_store import load_row_review_entries_by_key

_REPO_ROOT = Path(__file__).resolve().parents[1]
COLLISION_REVIEW_PATH = (
    _REPO_ROOT / "data" / "academyinfo_work" / "2025" / "packets" / "department_identity_collision_review.jsonl"
)
JSON_OUTPUT_PATH = _REPO_ROOT / "outputs" / "evaluation" / "department_offering_identity_v2_dry_run.json"
MD_OUTPUT_PATH = _REPO_ROOT / "outputs" / "evaluation" / "department_offering_identity_v2_dry_run.md"

SUNGKYUNKWAN_SEMICONDUCTOR_GROUP_ID = "dept_4b358345687aed927da6a9fa"
CHUNGNAM_PHARMACY_GROUP_ID = "dept_6ea537f2938a79ba48bef719"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run_row_level_verification(
    *, collision_path: Path | None = None, row_review_path: Path | None = None,
    offering_identity_path: Path | None = None,
) -> dict[str, Any]:
    """32행 전체를 대상으로 §4/§6 확인 항목을 전부 실측 계산한다. 이 함수는
    어떤 파일도 쓰지 않는다 — 순수 계산 + 읽기만 한다."""

    groups = _read_jsonl(collision_path or COLLISION_REVIEW_PATH)
    row_reviews_by_key = load_row_review_entries_by_key(row_review_path)

    # offering_id 중복 0건 — Repository 생성 자체가 증명(중복이면 여기서 예외).
    repo = JsonlDepartmentOfferingRepository(path=offering_identity_path)
    offering_id_duplicate_count = 0

    exposed = [r for r in row_reviews_by_key.values() if r.is_recommendation_representative]
    contract_excluded = [r for r in row_reviews_by_key.values() if r.exclusion_reason == "CONTRACT_OR_INDUSTRY_COMMISSIONED"]
    abolished_excluded = [r for r in row_reviews_by_key.values() if r.exclusion_reason == "ABOLISHED"]
    unclassified_excluded = [r for r in row_reviews_by_key.values() if r.exclusion_reason == "UNCLASSIFIED_SMALL_SERIES"]

    undecided_group_ids: list[str] = []
    corrected_group_ids: list[str] = []
    group_reports: list[dict[str, Any]] = []
    for group in groups:
        gid = group["department_id"]
        cand_ids = [c["source_record_id"] for c in group["candidates"]]
        cand_reviews = [row_reviews_by_key[sid] for sid in cand_ids]
        if any(r.reviewer_1_status != "APPROVE" for r in cand_reviews):
            undecided_group_ids.append(gid)

        auto_rep_id = group["dry_run_evaluation_audit"]["evaluated_representative_source_record_id"]
        correct_rep = next((r for r in cand_reviews if r.is_recommendation_representative), None)
        is_meaningful_correction = correct_rep is not None and correct_rep.source_record_id != auto_rep_id
        if is_meaningful_correction:
            corrected_group_ids.append(gid)

        group_reports.append(
            {
                "department_id": gid,
                "university_name": group["candidates"][0]["university_name"],
                "department_name": group["candidates"][0]["department_name"],
                "automated_representative_source_record_id": auto_rep_id,
                "human_representative_source_record_id": correct_rep.source_record_id if correct_rep else None,
                "meaningfully_corrected": is_meaningful_correction,
                "offering_ids": sorted(o.offering_id for o in repo.by_old_department_id(gid)),
            }
        )

    original_contract_department_tagged = {
        c["source_record_id"] for g in groups for c in g["candidates"] if c.get("exclusion_reason") == "CONTRACT_DEPARTMENT"
    }
    new_contract_excluded_ids = {r.source_record_id for r in contract_excluded} | {r.source_record_id for r in abolished_excluded}
    contract_tag_consistent = original_contract_department_tagged <= new_contract_excluded_ids

    sungkyunkwan_reps = [
        r for r in row_reviews_by_key.values()
        if r.department_id == SUNGKYUNKWAN_SEMICONDUCTOR_GROUP_ID and r.is_recommendation_representative
    ]
    chungnam_group = next(g for g in groups if g["department_id"] == CHUNGNAM_PHARMACY_GROUP_ID)
    chungnam_reps = [
        r for r in row_reviews_by_key.values()
        if r.department_id == CHUNGNAM_PHARMACY_GROUP_ID and r.is_recommendation_representative
    ]
    chungnam_rep_is_six_year_general = False
    if len(chungnam_reps) == 1:
        rep_candidate = next(
            c for c in chungnam_group["candidates"] if c["source_record_id"] == chungnam_reps[0].source_record_id
        )
        chungnam_rep_is_six_year_general = (
            rep_candidate["major_character_name"] == "일반과정" and rep_candidate["course_term"] == "6년"
        )

    return {
        "total_rows": len(row_reviews_by_key),
        "total_groups": len(groups),
        "offering_id_duplicate_count": offering_id_duplicate_count,
        "exposed_general_track_count": len(exposed),
        "contract_or_industry_excluded_count": len(contract_excluded),
        "abolished_excluded_count": len(abolished_excluded),
        "unclassified_excluded_count": len(unclassified_excluded),
        "undecided_group_count": len(undecided_group_ids),
        "undecided_group_ids": undecided_group_ids,
        "meaningful_representative_correction_count": len(corrected_group_ids),
        "corrected_group_ids": sorted(corrected_group_ids),
        "contract_department_tag_consistent_with_original": contract_tag_consistent,
        "sungkyunkwan_semiconductor_systems_eng_has_no_representative": len(sungkyunkwan_reps) == 0,
        "chungnam_pharmacy_representative_is_six_year_general_track": chungnam_rep_is_six_year_general,
        "groups": sorted(group_reports, key=lambda g: g["department_id"]),
        "scope_note": (
            "이 검증은 16 Group·32행(이번 라운드가 실제로 건드린 범위)에만 한정한다 — "
            "career_build_national_department_promotion_dry_run.py의 24,422행 전체 재실행은 "
            "이번 라운드 범위 밖이다(그 산출물은 Git에 올리지 않는 기존 관례를 따른다)."
        ),
    }


def _write_json_report(result: dict[str, Any]) -> None:
    JSON_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {JSON_OUTPUT_PATH}")


def _write_markdown_report(result: dict[str, Any]) -> None:
    lines = [
        "# Department Offering Identity v2 — 행 단위 재검증",
        "",
        "브랜치 `a/offering-identity-v2`. " + result["scope_note"],
        "",
        "## 1. 최종 회계",
        "",
        "| 항목 | 값 |",
        "|---|---:|",
        f"| 전체 행 | {result['total_rows']} |",
        f"| 전체 Group | {result['total_groups']} |",
        f"| offering_id 중복 | {result['offering_id_duplicate_count']} |",
        f"| 일반과정 추천 노출 | {result['exposed_general_track_count']} |",
        f"| 계약학과·산업체위탁 추천 제외(EXISTING) | {result['contract_or_industry_excluded_count']} |",
        f"| ABOLISHED 추천 제외 | {result['abolished_excluded_count']} |",
        f"| 공식 소계열 미분류(N.C.E) 추천 제외 | {result['unclassified_excluded_count']} |",
        f"| 미결 그룹 | {result['undecided_group_count']} |",
        f"| 자동 대표 판정 오류(의미 있는 교정) | {result['meaningful_representative_correction_count']} |",
        f"| 기존 CONTRACT_DEPARTMENT 태그와 모순 없음 | {result['contract_department_tag_consistent_with_original']} |",
        "",
        "## 2. 지정 검증 사례",
        "",
        f"- 성균관대학교 반도체시스템공학과 추천 대표 없음: "
        f"**{result['sungkyunkwan_semiconductor_systems_eng_has_no_representative']}**",
        f"- 충남대학교 약학과는 6년 일반과정만 추천 범위: "
        f"**{result['chungnam_pharmacy_representative_is_six_year_general_track']}**",
        "",
        "## 3. Group별 상세(16개)",
        "",
        "| department_id | 대학·학과 | 자동 대표 | 사람 대표 | 교정 여부 | offering_id |",
        "|---|---|---|---|---|---|",
    ]
    for g in result["groups"]:
        lines.append(
            f"| {g['department_id']} | {g['university_name']} {g['department_name']} | "
            f"{g['automated_representative_source_record_id']} | "
            f"{g['human_representative_source_record_id'] or '(없음)'} | "
            f"{'예' if g['meaningfully_corrected'] else '아니오'} | "
            f"{', '.join(g['offering_ids'])} |"
        )
    lines.append("")
    MD_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MD_OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {MD_OUTPUT_PATH}")


def main() -> None:
    result = run_row_level_verification()
    _write_json_report(result)
    _write_markdown_report(result)


if __name__ == "__main__":
    main()
