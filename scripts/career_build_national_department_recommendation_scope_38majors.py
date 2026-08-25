"""전국 학과 38개 서비스 Major 재분류 추천 Scope 승인 기록 생성 —
c/national-departments-38-majors §4.

`MajorExplorationService`는 `fail_closed_major_ids`에 속한 Major는 학과(department_id,
canonical_major_id) 쌍이 `data/master/department_recommendation_scope.jsonl`에
eligibility_status=APPROVED로 기록돼 있어야만 노출한다(Fail-Closed). 이 스크립트는
이번 라운드의 5,595건(38개 Major) 각각에 대해 **실제로 이미 끝난 검수 결정**(Canonical
Major Group Review + Service Canonical Major v2 Bridge, 이미 확정된 정본)만 인용해
APPROVED 기록을 만든다 — 새 교육과정 근거를 지어내지 않는다.

`scripts/career_build_national_department_recommendation_scope.py`(8개 Major·1,072건
라운드)와 다른 점: Bridge Mapping/Scope 두 단계 사람 검수 인용이 없다 — Bridge V2는
Group 하나당 정확히 한 확정 행이라(canonical_major_group_to_service_major_v2.jsonl,
decision_reason 포함) 그 결정 하나만 인용하면 된다.

입력:
    - `data/master/departments.jsonl`(5,595건, 이번 라운드로 이미 교체됨 — 정본)
    - `promotion_dry_run/promotion_candidates.jsonl`(Gate 판정에 실제로 쓰인
      resolved_canonical_major_group_id/official_small_series_code 복원용 — offering_id로
      교집합만 쓴다)
    - `data/reviews/canonical_major_group_review_status.jsonl`
    - `data/master/canonical_major_group_to_service_major_v2.jsonl`

기존 1,072건 Scope 기록(8개 Major 라운드)은 삭제하지 않되,
`data/archive/department_recommendation_scope_legacy_1072_8majors.jsonl`로 읽기 전용
보존한다(그 department_id는 이제 Archive로 옮겨진 옛 Master에만 있고 live Master에는
없다 — live Scope 파일에 남겨두면 "Master에 없는 고아 Scope 레코드"가 된다).

실행:
    PYTHONPATH=. ./.venv/bin/python scripts/career_build_national_department_recommendation_scope_38majors.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402
from src.services.department_recommendation_scope import (  # noqa: E402
    DEFAULT_SCOPE_PATH,
    DepartmentRecommendationScopeRecord,
)
from src.services.service_canonical_major_v2_loader import (  # noqa: E402
    load_canonical_major_group_to_service_major_bridge_v2,
)

MASTER_PATH = ROOT / "data" / "master" / "departments.jsonl"
RAW_DRY_RUN_CANDIDATES_PATH = ROOT / "data" / "academyinfo_work" / "2025" / "promotion_dry_run" / (
    "promotion_candidates.jsonl"
)
GROUP_REVIEW_PATH = ROOT / "data" / "reviews" / "canonical_major_group_review_status.jsonl"
LEGACY_SCOPE_ARCHIVE_PATH = ROOT / "data" / "archive" / (
    "department_recommendation_scope_legacy_1072_8majors.jsonl"
)

OFFICIAL_SOURCE_URL = "https://www.academyinfo.go.kr/"
REVIEWER_ID = "reviewer_1"
REVIEWED_AT = "2026-08-25"

# 대표 전공(canonical_major_id) 단위의 대분류 — 학과별 교육과정을 새로 조사해 판정한
# 값이 아니라, `data/master/service_canonical_majors_v2.jsonl`이 이미 정의한 전공
# 그 자체의 통상적 계열이다(§4가 금지하는 "학과 단위 허위 교육과정 근거"와는 다른
# 층위 — 옛 8개 Major 라운드의 ACADEMIC_FIELD_BY_MAJOR와 같은 성격, 39개로 확장).
ACADEMIC_FIELD_BY_MAJOR: dict[str, str] = {
    "agriculture_fisheries": "NATURAL_SCIENCE",
    "bio_medical_engineering": "ENGINEERING",
    "business_administration": "HUMANITIES_SOCIAL",
    "chemical_energy": "ENGINEERING",
    "chemistry": "NATURAL_SCIENCE",
    "civil_architecture": "ENGINEERING",
    "clothing_housing": "INTERDISCIPLINARY",
    "computer_science": "ENGINEERING",
    "dentistry": "NATURAL_SCIENCE",
    "earth_environment": "NATURAL_SCIENCE",
    "economics": "HUMANITIES_SOCIAL",
    "education": "EDUCATION",
    "electrical_electronic": "ENGINEERING",
    "food_nutrition": "NATURAL_SCIENCE",
    "foreign_language": "HUMANITIES_SOCIAL",
    "hci_ux": "INTERDISCIPLINARY",
    "health_science": "NATURAL_SCIENCE",
    "humanities": "HUMANITIES_SOCIAL",
    "industrial_engineering": "ENGINEERING",
    "korean_literature": "HUMANITIES_SOCIAL",
    "korean_medicine": "NATURAL_SCIENCE",
    "law": "HUMANITIES_SOCIAL",
    "life_science": "NATURAL_SCIENCE",
    "mathematics_statistics": "NATURAL_SCIENCE",
    "mechanical_engineering": "ENGINEERING",
    "media_communication": "HUMANITIES_SOCIAL",
    "medicine": "NATURAL_SCIENCE",
    "nursing": "NATURAL_SCIENCE",
    "pharmacy": "NATURAL_SCIENCE",
    "physics_astronomy": "NATURAL_SCIENCE",
    "political_science": "HUMANITIES_SOCIAL",
    "psychology": "HUMANITIES_SOCIAL",
    "public_administration": "HUMANITIES_SOCIAL",
    "semiconductor_materials": "ENGINEERING",
    "social_welfare": "HUMANITIES_SOCIAL",
    "sociology": "HUMANITIES_SOCIAL",
    "tourism": "HUMANITIES_SOCIAL",
    "trade_logistics": "HUMANITIES_SOCIAL",
    "veterinary": "NATURAL_SCIENCE",
}


class ScopeGenerationError(ValueError):
    pass


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise ScopeGenerationError(f"필수 입력이 없다: {path}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    tmp.replace(path)


def build_bridge_v2_evidence(
    *, group_id: str, major_id: str, small_series_code: str | None,
    group_review: dict[str, Any], bridge_entry: Any,
) -> tuple[list[dict[str, str]], str]:
    if group_review.get("decision") != "APPROVE_AS_CLASSIFICATION_GROUP":
        raise ScopeGenerationError(f"Group {group_id} 검수가 APPROVE_AS_CLASSIFICATION_GROUP이 아니다")
    if bridge_entry is None or bridge_entry.recommendation_status != "ACTIVE" or bridge_entry.service_major_id != major_id:
        raise ScopeGenerationError(f"Bridge V2 {group_id}->{major_id}가 ACTIVE로 확정돼 있지 않다")

    evidence = [
        {
            "evidence_type": "OFFICIAL_CLASSIFICATION_REVIEW",
            "source_url": OFFICIAL_SOURCE_URL,
            "summary": (
                f"공식 소계열 코드 {small_series_code} — Canonical Major Group 검수"
                f"(canonical_major_group_review_status.jsonl, canonical_major_group_id="
                f"{group_id}, decision={group_review['decision']}, {group_review.get('resolution_note') or ''})"
                f"로 대표 전공군 {group_id} 확정."
            ),
        },
        {
            "evidence_type": "OFFICIAL_CLASSIFICATION_REVIEW",
            "source_url": OFFICIAL_SOURCE_URL,
            "summary": (
                f"Service Canonical Major v2 Bridge(canonical_major_group_to_service_major_v2.jsonl, "
                f"canonical_major_group_id={group_id}, recommendation_status=ACTIVE, "
                f"service_major_id={major_id}, {bridge_entry.decision_reason})로 "
                f"전공군 {group_id} → 서비스 Major {major_id} 매핑을 확정."
            ),
        },
    ]
    decision_reason = (
        f"공식 소계열 {small_series_code}이 전공군 {group_id} 하나로 분류됐고, Canonical Major Group "
        f"검수({REVIEWER_ID}) APPROVE + Service Canonical Major v2 Bridge ACTIVE 확정으로 "
        f"대표 전공 {major_id}로 추천 대상 승인한다."
    )
    return evidence, decision_reason


def main(argv: list[str] | None = None) -> int:
    use_utf8_stdout()

    master_rows = _read_jsonl(MASTER_PATH)
    raw_dry_run_rows = {r["offering_id"]: r for r in _read_jsonl(RAW_DRY_RUN_CANDIDATES_PATH)}
    missing_raw = [r["department_id"] for r in master_rows if r["department_id"] not in raw_dry_run_rows]
    if missing_raw:
        raise ScopeGenerationError(
            f"로컬 재실행 promotion_candidates.jsonl에서 못 찾은 offering_id {len(missing_raw)}건 — "
            "먼저 scripts/career_build_national_department_promotion_dry_run.py를 다시 실행하세요."
        )

    group_reviews = {r["canonical_major_group_id"]: r for r in _read_jsonl(GROUP_REVIEW_PATH)}
    bridge_by_group = load_canonical_major_group_to_service_major_bridge_v2()

    new_records: list[dict[str, Any]] = []
    for master_row in master_rows:
        offering_id = master_row["department_id"]
        major_id = master_row["canonical_major_id"]
        raw_row = raw_dry_run_rows[offering_id]
        group_id = raw_row["resolved_canonical_major_group_id"]
        small_series_code = raw_row.get("official_small_series_code")

        group_review = group_reviews.get(group_id)
        if group_review is None:
            raise ScopeGenerationError(f"{offering_id}: Group 검수 기록을 찾을 수 없다 (Group={group_id})")
        bridge_entry = bridge_by_group.get(group_id)

        evidence, decision_reason = build_bridge_v2_evidence(
            group_id=group_id, major_id=major_id, small_series_code=small_series_code,
            group_review=group_review, bridge_entry=bridge_entry,
        )

        academic_field = ACADEMIC_FIELD_BY_MAJOR.get(major_id)
        if academic_field is None:
            raise ScopeGenerationError(f"{offering_id}: ACADEMIC_FIELD_BY_MAJOR에 {major_id}가 없다")

        record = {
            "department_id": offering_id,
            "university_name": master_row["university_name"],
            "department_name": master_row["department_name"],
            "college_name": master_row["college_name"],
            "canonical_major_id": major_id,
            "academic_field": academic_field,
            "eligibility_status": "APPROVED",
            "recommendation_eligible": True,
            "classification_evidence": evidence,
            "hci_ux_curriculum_evidence": [],
            "reviewer_id": REVIEWER_ID,
            "reviewed_at": REVIEWED_AT,
            "decision_reason": decision_reason,
        }
        # Fail-Fast — Pydantic Schema(§4가 이미 강제하는 최소 근거 조건)를 여기서도
        # 다시 확인한다. hci_ux는 이 5,595건에 0건이라 그 분기는 실행되지 않는다.
        DepartmentRecommendationScopeRecord.model_validate(record)
        new_records.append(record)

    new_records.sort(key=lambda r: r["department_id"])

    # 2026-08-25 지시서(c/national-departments-38-majors) 정정 — 옛 8개 Major 라운드
    # (`career_build_national_department_recommendation_scope.py`)는 기존 dept_
    # 접두 8건(데모 35건 시절)과 새 off_ 접두 1,072건이 서로 다른 ID 체계라 겹칠 수
    # 없었다. 이번 라운드는 같은 offering_id 체계 위에서 "같은 학과가 재분류"되는
    # 경우가 실제로 있다(예: computer_science로 이미 분류됐던 학과가 이번에도
    # computer_science로 남는다) — 그래서 겹침을 오류로 보지 않는다. 이 Scope
    # 파일은 Master와 마찬가지로 8개 Major 라운드 전체를 대체한다(병합이 아니다) —
    # 기존 1,072건 전부를 무조건 Archive하고 이 5,595건으로 완전히 교체한다.
    existing_records = _read_jsonl(DEFAULT_SCOPE_PATH) if DEFAULT_SCOPE_PATH.exists() else []

    if existing_records:
        if LEGACY_SCOPE_ARCHIVE_PATH.exists():
            archived = _read_jsonl(LEGACY_SCOPE_ARCHIVE_PATH)
            if archived != existing_records:
                raise ScopeGenerationError(
                    f"{LEGACY_SCOPE_ARCHIVE_PATH}가 이미 있는데 현재 기존 Scope 기록과 내용이 다르다 — "
                    "다른 내용을 덮어쓰지 않는다."
                )
        else:
            _write_jsonl_atomic(LEGACY_SCOPE_ARCHIVE_PATH, existing_records)
            LEGACY_SCOPE_ARCHIVE_PATH.chmod(0o444)

    _write_jsonl_atomic(DEFAULT_SCOPE_PATH, new_records)

    print("전국 학과 38개 서비스 Major 추천 Scope 승인 기록 생성 완료")
    print(f"  기존 기록(archive로 보존): {len(existing_records)}건")
    print(f"  신규 승인 기록(live): {len(new_records)}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
