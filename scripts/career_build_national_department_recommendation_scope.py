"""전국 학과 1,072건 추천 Scope 승인 기록 생성 — 2026-08-25 지시서
(a/national-master-promotion-final-wiring) §4.

`MajorExplorationService`는 `fail_closed_major_ids`에 속한 Major는 학과(department_id,
canonical_major_id) 쌍이 `data/master/department_recommendation_scope.jsonl`에
eligibility_status=APPROVED로 기록돼 있어야만 노출한다(Fail-Closed). 이 스크립트는 그
1,072건 각각에 대해, **실제로 이미 끝난 검수 결정**(Canonical Major Group Review /
Bridge Mapping Review / Bridge Scope Review / P1 Review)만 인용해 APPROVED 기록을
만든다 — 새 교육과정 근거를 지어내지 않는다(§4 "허위 교육과정 근거 생성 금지").

한 학과가 READY_FOR_PROMOTION에 도달한 경로는 실측으로 정확히 두 가지뿐이다(§4
검증 — `promotion_candidates.jsonl` 1,072건 재확인):

    1. 순수 Group/Bridge 경로(976건) — 공식 소계열이 Group 하나에 단독 배정되고
       그 Group이 승인, Bridge Mapping·Bridge Scope가 모두 승인된 경우.
    2. P1 경로(96건) — 소계열이 여러 Group에 걸려 REVIEW_REQUIRED였다가, P1 검수
       Store(candidate_id 키)에서 APPROVE_PROPOSED_CANDIDATE로 확정된 뒤 같은
       Group/Bridge Gate를 통과한 경우.

N.C.E 경로(ACCEPT_GROUP_AS_REVIEW_CANDIDATE)는 이 1,072건 중 단 한 건도 없다(N.C.E
승인은 구조적으로 그 자체만으로는 승격 승인이 아니다 — dry run 자체의 설계 제약).

입력:
    - `national_master_promotion_candidates.jsonl`(1,072건, 정본)
    - 로컬 재실행한 `promotion_candidates.jsonl`(Gate 판정에 실제로 쓰인
      p1_candidate_id/p1_review_decision/resolved_canonical_major_group_id/
      official_small_series_code를 복원하기 위한 재료 — offering_id로 교집합만 쓴다)
    - `data/reviews/canonical_major_group_review_status.jsonl`
    - `data/reviews/canonical_major_group_bridge_review_status.json`
    - `data/reviews/canonical_major_group_bridge_scope_review_status.jsonl`
    - `data/reviews/academyinfo_p1_classification_review_status.jsonl`

기존 8건(2026-08-22, 기존 데모 35건 시절 검수 기록)은 삭제하지 않되, §3이 기존 Master
35건을 그렇게 했듯 `data/archive/department_recommendation_scope_legacy_demo_8.jsonl`로
읽기 전용 보존한다 — 그 8건의 department_id(dept_ 접두)는 이제 archive로 옮겨진 기존
Master에만 있고 live `data/master/departments.jsonl`(1,072건, off_ 접두)에는 없어서,
live Scope 파일에 남겨두면 "Master에 없는 고아 Scope 레코드"가 된다(정책 데이터
정합성 위반 — `test_every_scope_record_department_exists_in_master`가 실제로 이를
검증한다).

실행:
    PYTHONPATH=. ./.venv/bin/python scripts/career_build_national_department_recommendation_scope.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402
from src.schemas.canonical_major_group_bridge_review import bridge_review_key  # noqa: E402
from src.services.department_recommendation_scope import (  # noqa: E402
    DEFAULT_SCOPE_PATH,
    DepartmentRecommendationScopeRecord,
)

CANDIDATES_PATH = ROOT / "data" / "academyinfo_work" / "2025" / "promotion_dry_run" / (
    "national_master_promotion_candidates.jsonl"
)
RAW_DRY_RUN_CANDIDATES_PATH = ROOT / "data" / "academyinfo_work" / "2025" / "promotion_dry_run" / (
    "promotion_candidates.jsonl"
)
GROUP_REVIEW_PATH = ROOT / "data" / "reviews" / "canonical_major_group_review_status.jsonl"
BRIDGE_MAPPING_REVIEW_PATH = ROOT / "data" / "reviews" / "canonical_major_group_bridge_review_status.json"
BRIDGE_SCOPE_REVIEW_PATH = ROOT / "data" / "reviews" / "canonical_major_group_bridge_scope_review_status.jsonl"
P1_REVIEW_PATH = ROOT / "data" / "reviews" / "academyinfo_p1_classification_review_status.jsonl"
LEGACY_SCOPE_ARCHIVE_PATH = ROOT / "data" / "archive" / "department_recommendation_scope_legacy_demo_8.jsonl"

OFFICIAL_SOURCE_URL = "https://www.academyinfo.go.kr/"
REVIEWER_ID = "reviewer_1"
REVIEWED_AT = "2026-08-24"

# 대표 전공(canonical_major_id) 단위의 대분류 — 학과별 교육과정을 새로 조사해 판정한
# 값이 아니라, `data/master/canonical_majors.jsonl`이 이미 정의한 전공 그 자체의
# 통상적 계열이다(§4가 금지하는 "학과 단위 허위 교육과정 근거"와는 다른 층위).
ACADEMIC_FIELD_BY_MAJOR = {
    "business_administration": "HUMANITIES_SOCIAL",
    "media_communication": "HUMANITIES_SOCIAL",
    "life_science": "NATURAL_SCIENCE",
    "mechanical_engineering": "ENGINEERING",
    "computer_science": "ENGINEERING",
    "education": "EDUCATION",
    "industrial_engineering": "ENGINEERING",
    "psychology": "HUMANITIES_SOCIAL",
}


class ScopeGenerationError(ValueError):
    pass


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise ScopeGenerationError(f"필수 입력이 없다: {path}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise ScopeGenerationError(f"필수 입력이 없다: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_jsonl_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    tmp.replace(path)


def build_group_bridge_evidence(
    *, group_id: str, major_id: str, small_series_code: str | None,
    group_review: dict[str, Any], bridge_mapping_review: dict[str, Any], bridge_scope_review: dict[str, Any],
) -> tuple[list[dict[str, str]], str]:
    if group_review.get("decision") != "APPROVE_AS_CLASSIFICATION_GROUP":
        raise ScopeGenerationError(f"Group {group_id} 검수가 APPROVE_AS_CLASSIFICATION_GROUP이 아니다")
    if bridge_mapping_review.get("reviewer_1_status") != "APPROVE":
        raise ScopeGenerationError(f"Bridge Mapping {group_id}::{major_id} 검수가 APPROVE가 아니다")
    if bridge_scope_review.get("reviewer_1_status") != "APPROVE":
        raise ScopeGenerationError(f"Bridge Scope {group_id}::{major_id} 검수가 APPROVE가 아니다")

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
                f"Bridge Mapping 검수(canonical_major_group_bridge_review_status.json, Key="
                f"{bridge_review_key(group_id, major_id)}, reviewer_1_status=APPROVE) + Bridge Scope "
                f"검수(canonical_major_group_bridge_scope_review_status.jsonl, 같은 Key, "
                f"reviewer_1_status=APPROVE)로 전공군 {group_id} → 대표 전공 {major_id} 매핑·범위를 최종 승인."
            ),
        },
    ]
    decision_reason = (
        f"공식 소계열 {small_series_code}이 전공군 {group_id} 하나에만 단독 배정됐고, "
        f"Group·Bridge Mapping·Bridge Scope 검수({REVIEWER_ID}) 전부 APPROVE로 확정돼 "
        f"대표 전공 {major_id}로 추천 대상 승인한다."
    )
    return evidence, decision_reason


def build_p1_evidence(
    *, group_id: str, major_id: str, p1_candidate_id: str, small_series_code: str | None,
    group_review: dict[str, Any], bridge_mapping_review: dict[str, Any], bridge_scope_review: dict[str, Any],
    p1_review: dict[str, Any],
) -> tuple[list[dict[str, str]], str]:
    if p1_review.get("decision") != "APPROVE_PROPOSED_CANDIDATE":
        raise ScopeGenerationError(f"P1 후보 {p1_candidate_id} 검수가 APPROVE_PROPOSED_CANDIDATE가 아니다")
    if group_review.get("decision") != "APPROVE_AS_CLASSIFICATION_GROUP":
        raise ScopeGenerationError(f"Group {group_id} 검수가 APPROVE_AS_CLASSIFICATION_GROUP이 아니다")
    if bridge_mapping_review.get("reviewer_1_status") != "APPROVE":
        raise ScopeGenerationError(f"Bridge Mapping {group_id}::{major_id} 검수가 APPROVE가 아니다")
    if bridge_scope_review.get("reviewer_1_status") != "APPROVE":
        raise ScopeGenerationError(f"Bridge Scope {group_id}::{major_id} 검수가 APPROVE가 아니다")

    evidence = [
        {
            "evidence_type": "OFFICIAL_CLASSIFICATION_REVIEW",
            "source_url": OFFICIAL_SOURCE_URL,
            "summary": (
                f"공식 소계열 코드 {small_series_code}이 복수 전공군 후보에 걸려 P1 검수 대상이 됐다 — "
                f"P1 검수(academyinfo_p1_classification_review_status.jsonl, candidate_id={p1_candidate_id}, "
                f"decision=APPROVE_PROPOSED_CANDIDATE, {p1_review.get('resolution_note') or ''})로 "
                f"전공군 {group_id} 단독 확정."
            ),
        },
        {
            "evidence_type": "OFFICIAL_CLASSIFICATION_REVIEW",
            "source_url": OFFICIAL_SOURCE_URL,
            "summary": (
                f"확정된 전공군 {group_id}에 대해 Canonical Major Group 검수(decision="
                f"{group_review['decision']}) + Bridge Mapping·Bridge Scope 검수(Key="
                f"{bridge_review_key(group_id, major_id)}, 둘 다 reviewer_1_status=APPROVE)로 대표 전공 "
                f"{major_id} 매핑·범위를 최종 승인."
            ),
        },
    ]
    decision_reason = (
        f"공식 소계열 {small_series_code}이 여러 전공군에 걸려 P1 검수 대상이었으나, P1 검수 후보 "
        f"{p1_candidate_id}가 APPROVE_PROPOSED_CANDIDATE({REVIEWER_ID})로 확정돼 전공군 {group_id} "
        f"하나로 좁혀졌고, 그 뒤 Group·Bridge Mapping·Bridge Scope Gate까지 전부 통과해 "
        f"대표 전공 {major_id}로 추천 대상 승인한다."
    )
    return evidence, decision_reason


def main(argv: list[str] | None = None) -> int:
    use_utf8_stdout()

    candidates = _read_jsonl(CANDIDATES_PATH)
    if len(candidates) != 1072:
        raise ScopeGenerationError(f"후보가 1,072건이 아니다: {len(candidates)}건")

    raw_dry_run_rows = {r["offering_id"]: r for r in _read_jsonl(RAW_DRY_RUN_CANDIDATES_PATH)}
    missing_raw = [c["offering_id"] for c in candidates if c["offering_id"] not in raw_dry_run_rows]
    if missing_raw:
        raise ScopeGenerationError(
            f"로컬 재실행 promotion_candidates.jsonl에서 못 찾은 offering_id {len(missing_raw)}건 — "
            "먼저 scripts/career_build_national_department_promotion_dry_run.py를 다시 실행하세요."
        )

    group_reviews = {r["canonical_major_group_id"]: r for r in _read_jsonl(GROUP_REVIEW_PATH)}
    bridge_mapping_reviews = {
        bridge_review_key(r["canonical_major_group_id"], r.get("canonical_major_id")): r
        for r in _read_json_list(BRIDGE_MAPPING_REVIEW_PATH)
    }
    bridge_scope_reviews = {
        bridge_review_key(r["canonical_major_group_id"], r.get("canonical_major_id")): r
        for r in _read_jsonl(BRIDGE_SCOPE_REVIEW_PATH)
    }
    p1_reviews = {r["candidate_id"]: r for r in _read_jsonl(P1_REVIEW_PATH)}

    new_records: list[dict[str, Any]] = []
    for candidate in candidates:
        offering_id = candidate["offering_id"]
        major_id = candidate["canonical_major_id"]
        raw_row = raw_dry_run_rows[offering_id]
        group_id = raw_row["resolved_canonical_major_group_id"]
        small_series_code = raw_row.get("official_small_series_code")
        bridge_key = bridge_review_key(group_id, major_id)

        group_review = group_reviews.get(group_id)
        bridge_mapping_review = bridge_mapping_reviews.get(bridge_key)
        bridge_scope_review = bridge_scope_reviews.get(bridge_key)
        if group_review is None or bridge_mapping_review is None or bridge_scope_review is None:
            raise ScopeGenerationError(f"{offering_id}: Group/Bridge 검수 기록을 찾을 수 없다 (Key={bridge_key})")

        if raw_row.get("p1_review_decision") == "APPROVE_PROPOSED_CANDIDATE":
            p1_candidate_id = raw_row["p1_candidate_id"]
            p1_review = p1_reviews.get(p1_candidate_id)
            if p1_review is None:
                raise ScopeGenerationError(f"{offering_id}: P1 검수 기록을 찾을 수 없다 (candidate_id={p1_candidate_id})")
            evidence, decision_reason = build_p1_evidence(
                group_id=group_id, major_id=major_id, p1_candidate_id=p1_candidate_id,
                small_series_code=small_series_code, group_review=group_review,
                bridge_mapping_review=bridge_mapping_review, bridge_scope_review=bridge_scope_review,
                p1_review=p1_review,
            )
        elif raw_row.get("nce_review_decision") == "ACCEPT_GROUP_AS_REVIEW_CANDIDATE":
            raise ScopeGenerationError(
                f"{offering_id}: N.C.E 경로는 실측 1,072건 중 0건이어야 하는데 발견됐다 — 가정이 깨졌다."
            )
        else:
            evidence, decision_reason = build_group_bridge_evidence(
                group_id=group_id, major_id=major_id, small_series_code=small_series_code,
                group_review=group_review, bridge_mapping_review=bridge_mapping_review,
                bridge_scope_review=bridge_scope_review,
            )

        record = {
            "department_id": offering_id,
            "university_name": candidate["university_name"],
            "department_name": candidate["department_name"],
            "college_name": candidate["college_name"],
            "canonical_major_id": major_id,
            "academic_field": ACADEMIC_FIELD_BY_MAJOR[major_id],
            "eligibility_status": "APPROVED",
            "recommendation_eligible": True,
            "classification_evidence": evidence,
            "hci_ux_curriculum_evidence": [],
            "reviewer_id": REVIEWER_ID,
            "reviewed_at": REVIEWED_AT,
            "decision_reason": decision_reason,
        }
        # Fail-Fast — Pydantic Schema(§4가 이미 강제하는 최소 근거 조건)를 여기서도
        # 다시 확인한다. hci_ux는 이 1,072건에 0건이라 그 분기는 실행되지 않는다.
        DepartmentRecommendationScopeRecord.model_validate(record)
        new_records.append(record)

    new_records.sort(key=lambda r: r["department_id"])

    existing_records = _read_jsonl(DEFAULT_SCOPE_PATH) if DEFAULT_SCOPE_PATH.exists() else []
    new_ids = {r["department_id"] for r in new_records}
    overlap = [r["department_id"] for r in existing_records if r["department_id"] in new_ids]
    if overlap:
        raise ScopeGenerationError(f"기존 Scope 기록과 department_id가 겹친다: {overlap}")

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

    print("전국 학과 추천 Scope 승인 기록 생성 완료")
    print(f"  기존 기록(archive로 보존): {len(existing_records)}건")
    print(f"  신규 승인 기록(live): {len(new_records)}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
