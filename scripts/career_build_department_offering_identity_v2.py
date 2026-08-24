"""Department Offering Identity v2 산출물 빌더 — 2026-08-25 지시서
(a/offering-identity-v2).

`data/academyinfo_work/2025/packets/department_identity_collision_review.jsonl`
(worker-c 산출, 16 Group·32행, Read-Only)과 `data/master/departments.jsonl`
(35건, Read-Only)만 읽는다. 둘 다 절대 쓰지 않는다.

세 산출물을 만든다:

1. `data/reviews/department_identity_collision_row_review_status.jsonl`
   (32행) — 완료된 사람 판정 정본. `src.engines.department_identity_collision_classifier`
   의 순수 함수로 계산한다(원본 32행의 자동 계산 필드만 입력으로 쓴다 —
   department_id별 하드코딩 목록이 아니다).
2. `data/academyinfo_work/2025/packets/department_offering_identity_v2.jsonl`
   (32행) — Identity v2 offering_id/display_group_id 레코드.
3. `data/academyinfo_work/2025/packets/department_id_migration_map.jsonl`
   (51행 = 충돌 Group 16 + Master 35) — old_department_id → new_offering_ids
   Migration Map.

결정론: `decided_at`은 고정 상수(DECISION_TIMESTAMP)를 쓴다 — 실행 시각을
기록하지 않는다. 모든 출력은 Key로 정렬해서 쓴다. 같은 입력이면 두 번 실행해도
byte-identical하다(`tests/test_department_offering_identity_v2_build.py`의
DeterminismTest가 서로 다른 PYTHONHASHSEED로 이를 확인한다)."""

from __future__ import annotations

import json
from pathlib import Path

from src.engines.department_identity_collision_classifier import RowClassificationInput, classify_row
from src.ids import generate_display_group_id, generate_offering_id
from src.schemas.department_id_migration_map import DepartmentIdMigrationMapEntry
from src.schemas.department_identity_collision_row_review import DepartmentIdentityCollisionRowReview
from src.schemas.department_offering_identity import DepartmentOfferingIdentity

_REPO_ROOT = Path(__file__).resolve().parents[1]
COLLISION_REVIEW_PATH = (
    _REPO_ROOT / "data" / "academyinfo_work" / "2025" / "packets" / "department_identity_collision_review.jsonl"
)
MASTER_DEPARTMENTS_PATH = _REPO_ROOT / "data" / "master" / "departments.jsonl"

ROW_REVIEW_OUTPUT_PATH = _REPO_ROOT / "data" / "reviews" / "department_identity_collision_row_review_status.jsonl"
OFFERING_IDENTITY_OUTPUT_PATH = (
    _REPO_ROOT / "data" / "academyinfo_work" / "2025" / "packets" / "department_offering_identity_v2.jsonl"
)
MIGRATION_MAP_OUTPUT_PATH = (
    _REPO_ROOT / "data" / "academyinfo_work" / "2025" / "packets" / "department_id_migration_map.jsonl"
)

PROVIDER = "academyinfo"
# 2026-08-25 사용자 확인 — 이 라운드에서 32행 전부에 대해 사람 판정이
# 완료됐다고 확정한 시각. 실행할 때마다 바뀌는 실시각(datetime.now())을 쓰지
# 않는다 — 결정론(byte-identical 재실행)을 지키기 위해서다.
DECISION_TIMESTAMP = "2026-08-25T00:00:00+09:00"
DECISION_BASIS_URL = "https://www.academyinfo.go.kr/"

_EXCLUSION_REASON_COMMENT = {
    "ABOLISHED": "운영 상태가 ABOLISHED(폐과)라 일반/계약 구분과 무관하게 추천 대표에서 제외한다.",
    "CONTRACT_OR_INDUSTRY_COMMISSIONED": "계약학과·산업체위탁 편제는 일반 학생 추천 대상이 아니다(기존 CONTRACT_DEPARTMENT 정책과 같은 원칙).",
    "UNCLASSIFIED_SMALL_SERIES": "공식 소계열이 N.C.E로 미분류돼 42개 Canonical Major Group 어디에도 속하지 않는다 — 분류 근거가 없어 추천할 수 없다.",
}
_REPRESENTATIVE_COMMENT = "일반과정·EXISTING·공식 소계열 분류 가능 — 이 표시명 그룹의 추천 대표로 노출한다."


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_row_reviews_and_offerings(
    collision_path: Path | None = None,
) -> tuple[list[DepartmentIdentityCollisionRowReview], list[DepartmentOfferingIdentity]]:
    """32행 각각에 대해 (사람 판정, Identity v2 레코드) 쌍을 계산한다. 이
    함수는 어떤 파일도 쓰지 않는다 — 순수 계산 + 읽기만 한다."""

    groups = _read_jsonl(collision_path or COLLISION_REVIEW_PATH)
    reviews: list[DepartmentIdentityCollisionRowReview] = []
    offerings: list[DepartmentOfferingIdentity] = []

    for group in groups:
        department_id = group["department_id"]
        for candidate in group["candidates"]:
            cr = candidate["classification_result"]
            has_group = cr["mapping_status"] != "UNMAPPED" and bool(cr["candidate_canonical_major_ids"])
            result = classify_row(
                RowClassificationInput(
                    department_status=candidate["department_status"],
                    major_character=candidate["major_character_name"],
                    has_classifiable_canonical_group=has_group,
                )
            )
            offering_id = generate_offering_id(candidate["schl_id"], candidate["source_schl_mjr_id"], provider=PROVIDER)
            display_group_id = generate_display_group_id(
                candidate["schl_id"], candidate["college_name"], candidate["department_name"]
            )
            comment = (
                _REPRESENTATIVE_COMMENT
                if result.is_recommendation_representative
                else _EXCLUSION_REASON_COMMENT[result.exclusion_reason]  # type: ignore[index]
            )

            reviews.append(
                DepartmentIdentityCollisionRowReview(
                    source_record_id=candidate["source_record_id"],
                    department_id=department_id,
                    offering_id=offering_id,
                    schl_id=candidate["schl_id"],
                    source_schl_mjr_id=candidate["source_schl_mjr_id"],
                    major_character=candidate["major_character_name"],
                    department_status=candidate["department_status"],
                    recommendation_scope_decision=result.recommendation_scope_decision,
                    exclusion_reason=result.exclusion_reason,
                    is_recommendation_representative=result.is_recommendation_representative,
                    decision_basis_url=DECISION_BASIS_URL,
                    reviewer_1_status="APPROVE",
                    decided_at=DECISION_TIMESTAMP,
                    reviewer_1_comment=comment,
                )
            )
            offerings.append(
                DepartmentOfferingIdentity(
                    offering_id=offering_id,
                    display_group_id=display_group_id,
                    stable_lineage_id=None,
                    provider=PROVIDER,
                    schl_id=candidate["schl_id"],
                    source_schl_mjr_id=candidate["source_schl_mjr_id"],
                    source_record_id=candidate["source_record_id"],
                    source_svy_year=int(candidate["raw_snapshot"]["svyYr"]),
                    old_department_id=department_id,
                    university_name=candidate["university_name"],
                    college_name=candidate["college_name"],
                    department_name=candidate["department_name"],
                    major_character=candidate["major_character_name"],
                    department_status=candidate["department_status"],
                )
            )

    reviews.sort(key=lambda r: r.source_record_id)
    offerings.sort(key=lambda o: o.offering_id)
    return reviews, offerings


def build_migration_map(
    offerings: list[DepartmentOfferingIdentity], master_path: Path | None = None,
) -> list[DepartmentIdMigrationMapEntry]:
    """충돌 Group 16건(one-to-many) + Master 35건(1:1, 미변경)을 합쳐 51행을
    만든다. Master 35건은 원본 데이터에 schl_id/source_schl_mjr_id가 없어
    실제 offering_id를 계산할 재료가 없다 — new_offering_ids=[]로 정직하게
    비워둔다(값을 지어내지 않는다)."""

    entries: list[DepartmentIdMigrationMapEntry] = []

    by_old_id: dict[str, list[DepartmentOfferingIdentity]] = {}
    for o in offerings:
        by_old_id.setdefault(o.old_department_id, []).append(o)
    for old_department_id, group_offerings in by_old_id.items():
        group_offerings = sorted(group_offerings, key=lambda o: o.offering_id)
        display_group_ids = {o.display_group_id for o in group_offerings}
        entries.append(
            DepartmentIdMigrationMapEntry(
                old_department_id=old_department_id,
                new_offering_ids=[o.offering_id for o in group_offerings],
                display_group_id=next(iter(display_group_ids)) if len(display_group_ids) == 1 else None,
                migration_status="RESOLVED_ONE_TO_MANY_COLLISION",
                decision_reason=(
                    f"identity-key 충돌 Group — 옛 department_id 하나에 서로 다른 편제 {len(group_offerings)}개가 "
                    "걸려 있었다(2026-08-24 department_identity_collision_review.jsonl 감사). schl_id+"
                    "source_schl_mjr_id 기준 offering_id로 분리했다."
                ),
            )
        )

    for row in _read_jsonl(master_path or MASTER_DEPARTMENTS_PATH):
        entries.append(
            DepartmentIdMigrationMapEntry(
                old_department_id=row["department_id"],
                new_offering_ids=[],
                display_group_id=None,
                migration_status="MASTER_UNCHANGED_SOURCE_IDENTIFIERS_UNAVAILABLE",
                decision_reason=(
                    "Master(data/master/departments.jsonl) 35건은 Identity v2 이전에 만들어져 "
                    "schl_id·source_schl_mjr_id를 원본 데이터로 보존하지 않는다 — offering_id를 계산할 "
                    "재료가 없어 이번 라운드에는 값을 만들지 않는다(§5 기존 35건 즉시 교체 금지). "
                    "department_id는 이 라운드에서 전혀 바뀌지 않았다."
                ),
            )
        )

    entries.sort(key=lambda e: e.old_department_id)
    return entries


def _write_jsonl(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(lines) + ("\n" if lines else "")
    tmp_path = path.parent / f".{path.name}.tmp"
    tmp_path.write_text(payload, encoding="utf-8")
    tmp_path.replace(path)


def main() -> None:
    reviews, offerings = build_row_reviews_and_offerings()
    migration_map = build_migration_map(offerings)

    _write_jsonl(ROW_REVIEW_OUTPUT_PATH, [r.model_dump_json() for r in reviews])
    print(f"wrote {ROW_REVIEW_OUTPUT_PATH} ({len(reviews)}행)")

    _write_jsonl(OFFERING_IDENTITY_OUTPUT_PATH, [o.model_dump_json() for o in offerings])
    print(f"wrote {OFFERING_IDENTITY_OUTPUT_PATH} ({len(offerings)}행)")

    _write_jsonl(MIGRATION_MAP_OUTPUT_PATH, [m.model_dump_json() for m in migration_map])
    print(f"wrote {MIGRATION_MAP_OUTPUT_PATH} ({len(migration_map)}행)")


if __name__ == "__main__":
    main()
