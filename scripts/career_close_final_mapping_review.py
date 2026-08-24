"""Final Mapping Closure 후속 — 312건 추가 검수 제거(사용자 최종 결정 반영) —
a/final-mapping-closure.

**사용자 최종 결정**(2026-08-25): 추가 사람 검수는 진행하지 않는다. 이전 라운드가
분류한 499건(Group 42·Bridge Mapping 44·Bridge Scope 15·P1 374·N.C.E 24) 전부를
이번 라운드에서 검수 완료 상태로 종결한다.

**검수 완료 ≠ 추천 포함.** 근거가 충분한 항목만 실제로 승인하고, 근거가 부족한
항목(P1 277건·N.C.E 24개 클러스터·Bridge Scope DEPARTMENT_REVIEW_REQUIRED 2건)은
"1차 전국 Master 승격에서 제외"로 명시적으로 결정한다 — 이 스크립트가 추측으로
Major를 연결하지 않는다.

**반드시 기존 Review Store/PATCH Service를 그대로 쓴다**(JSONL 문자열 치환 아님):
- `update_canonical_major_group_review()` (Group)
- `update_bridge_review()` / `update_bridge_scope_review()` (Bridge)
- `update_p1_classification_review()` (P1)
- `update_nce_middle_series_review()` (N.C.E)

전부 이 저장소의 기존 서비스 함수를 그대로 호출한다 — 이 스크립트는 검증·저장
로직을 다시 구현하지 않는다. `reviewer_2`는 어디서도 건드리지 않는다(TBD 유지).
Bridge Mapping의 기존 38 APPROVE 행은 이미 사람이 검수 완료한 상태라 다시
저장하지 않는다(코멘트·revision 불필요한 churn을 만들지 않는다 — 오직 REVISE
6건만 이번에 APPROVE로 종결한다).

실행 전 `career_build_final_mapping_closure.py`의 분류 함수를 그대로 다시 불러
"지금 이 순간의 176/11/312 분류"를 다시 계산한다(재분류 로직을 이 스크립트가
따로 만들지 않는다) — 그 분류 결과를 그대로 저장 대상으로 쓴다.

실행:
    PYTHONPATH=. ./.venv/bin/python scripts/career_close_final_mapping_review.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_build_final_mapping_closure import classify_bridge, classify_groups, classify_nce, classify_p1  # noqa: E402
from scripts.career_console import use_utf8_stdout  # noqa: E402
from src.review_ui.academyinfo_nce_middle_series_review_service import update_nce_middle_series_review  # noqa: E402
from src.review_ui.academyinfo_p1_classification_review_service import update_p1_classification_review  # noqa: E402
from src.review_ui.canonical_major_group_bridge_review_service import (  # noqa: E402
    update_bridge_review,
    update_bridge_scope_review,
)
from src.review_ui.canonical_major_group_review_service import update_canonical_major_group_review  # noqa: E402
from src.schemas.canonical_major_group_bridge_review import bridge_review_key  # noqa: E402
from src.services.academyinfo_nce_middle_series_review_store import load_nce_review_entries_by_key  # noqa: E402
from src.services.academyinfo_p1_classification_review_store import load_p1_review_entries_by_key  # noqa: E402
from src.services.canonical_major_group_bridge_scope_review_store import load_bridge_scope_review_entries_by_key  # noqa: E402
from src.services.canonical_major_group_review_store import load_canonical_major_group_review_entries_by_key  # noqa: E402

RESOLUTION_NOTE = (
    "사용자 최종 결정에 따라 추가 검수 없이 기존 근거 기반 승인 또는 "
    "1차 전국 승격 제외로 종결"
)

REVIEWS_DIR = ROOT / "data" / "reviews"
GROUP_REVIEW_PATH = REVIEWS_DIR / "canonical_major_group_review_status.jsonl"
BRIDGE_MAPPING_REVIEW_PATH = REVIEWS_DIR / "canonical_major_group_bridge_review_status.json"
BRIDGE_SCOPE_REVIEW_PATH = REVIEWS_DIR / "canonical_major_group_bridge_scope_review_status.jsonl"
P1_REVIEW_PATH = REVIEWS_DIR / "academyinfo_p1_classification_review_status.jsonl"
NCE_REVIEW_PATH = REVIEWS_DIR / "academyinfo_nce_middle_series_review_status.jsonl"


def close_group_reviews(group_rows: list[dict[str, Any]]) -> list[str]:
    """§3 — 42개 전부 APPROVE_AS_CLASSIFICATION_GROUP으로 종결한다(추천 제외
    정책·Bridge Scope 제한은 별도 축이라 이 결정과 무관하게 그대로 유지된다 —
    이 함수는 Group 분류(Ontology) 승인만 한다, 서비스 Major·학과 추천을
    자동 생성하지 않는다). 재실행해도 안전하다(이미 목표 상태인 행은
    건드리지 않는다 — expected_revision을 실제 현재 값으로 다시 읽는다)."""

    existing_by_key = load_canonical_major_group_review_entries_by_key(GROUP_REVIEW_PATH)
    closed: list[str] = []
    for row in sorted(group_rows, key=lambda r: r["canonical_major_group_id"]):
        group_id = row["canonical_major_group_id"]
        assert row["disposition"] in ("PROPOSE_APPROVE", "HUMAN_REVIEW_REQUIRED"), row
        existing = existing_by_key.get(group_id)
        if existing is not None and existing.decision == "APPROVE_AS_CLASSIFICATION_GROUP" and existing.resolution_note == RESOLUTION_NOTE:
            continue  # 이미 이 스크립트로 종결된 상태 — 재실행 시 다시 쓰지 않는다.
        update_canonical_major_group_review(
            group_id,
            decision="APPROVE_AS_CLASSIFICATION_GROUP",
            comment=None,
            resolution_note=RESOLUTION_NOTE,
            expected_revision=existing.revision if existing is not None else 0,
            review_status_path=GROUP_REVIEW_PATH,
        )
        closed.append(group_id)
    return closed


def close_bridge_mapping_reviews(mapping_rows: list[dict[str, Any]]) -> list[str]:
    """§4 — REVISE 6건만 APPROVE로 종결한다. 기존 38건은 이미 사람이 승인했으므로
    다시 저장하지 않는다(코멘트·revision 불필요한 변경 방지)."""

    closed: list[str] = []
    for row in sorted(mapping_rows, key=lambda r: (r["canonical_major_group_id"], r["canonical_major_id"] or "")):
        if row["existing_reviewer_1_status"] == "APPROVE":
            continue  # 이미 종결됨(이번 라운드 이전부터, 또는 재실행) — 손대지 않는다
            # (§12 "기존 Review Key·코멘트 보존").
        assert row["existing_reviewer_1_status"] == "REVISE", row
        key = bridge_review_key(row["canonical_major_group_id"], row["canonical_major_id"])
        update_bridge_review(
            key, status="APPROVE", comment=None, resolution_note=RESOLUTION_NOTE,
            review_status_path=BRIDGE_MAPPING_REVIEW_PATH,
        )
        closed.append(key)
    return closed


def close_bridge_scope_reviews(scope_rows: list[dict[str, Any]]) -> list[str]:
    """§5 — 적용 대상 15건 전부 scope_review_status=APPROVE로 종결한다.
    `scope_type`(FULL_GROUP/INCLUDED_SMALL_SERIES_ONLY/EXCLUDED_RECOMMENDATION/
    DEPARTMENT_REVIEW_REQUIRED) 값 자체는 이 함수가 바꾸지 않는다 — Draft
    원본은 Read-Only다. DEPARTMENT_REVIEW_REQUIRED 2건도 scope_type은 그대로
    유지한 채 검수 상태만 APPROVE로 종결한다(§5 "이는 자동 학과 승격 승인이
    아니다")."""

    existing_by_key = load_bridge_scope_review_entries_by_key(BRIDGE_SCOPE_REVIEW_PATH)
    closed: list[str] = []
    applicable = [r for r in scope_rows if r["disposition"] != "NOT_APPLICABLE"]
    for row in sorted(applicable, key=lambda r: (r["canonical_major_group_id"], r["canonical_major_id"] or "")):
        key = bridge_review_key(row["canonical_major_group_id"], row["canonical_major_id"])
        existing = existing_by_key.get(key)
        if existing is not None and existing.reviewer_1_status == "APPROVE" and existing.resolution_note == RESOLUTION_NOTE:
            continue
        update_bridge_scope_review(
            key, status="APPROVE", comment=None, resolution_note=RESOLUTION_NOTE,
            scope_review_status_path=BRIDGE_SCOPE_REVIEW_PATH,
        )
        closed.append(key)
    return closed


def _p1_decision_for(row: dict[str, Any]) -> str:
    if row["disposition"] == "PROPOSE_APPROVE":
        return "APPROVE_PROPOSED_CANDIDATE"
    if row["judgment_candidate"] == "DESIGN_ARTS_EXCLUDED":
        return "EXCLUDE_ARTS_RECOMMENDATION"
    # §6 — 근거 부족(HCI_UX_CANDIDATE·NEEDS_OFFICIAL_CURRICULUM·UNMAPPED) 전부
    # 특정 Major로 추측 연결하지 않고 1차 승격 제외로 명시적으로 종결한다.
    return "EXCLUDE_FROM_INITIAL_PROMOTION"


def close_p1_reviews(p1_rows: list[dict[str, Any]]) -> list[str]:
    existing_by_key = load_p1_review_entries_by_key(P1_REVIEW_PATH)
    closed: list[str] = []
    for row in sorted(p1_rows, key=lambda r: r["candidate_id"]):
        decision = _p1_decision_for(row)
        candidate_id = row["candidate_id"]
        existing = existing_by_key.get(candidate_id)
        if existing is not None and existing.decision == decision and existing.resolution_note == RESOLUTION_NOTE:
            continue
        update_p1_classification_review(
            candidate_id, decision=decision, comment=None, resolution_note=RESOLUTION_NOTE,
            expected_revision=existing.revision if existing is not None else 0, review_status_path=P1_REVIEW_PATH,
        )
        closed.append(candidate_id)
    return closed


def close_nce_reviews(nce_rows: list[dict[str, Any]]) -> list[str]:
    """§7 — 24개 클러스터 전부 EXCLUDE_FROM_INITIAL_PROMOTION으로 종결한다.
    후보 Group Hint(candidate_canonical_major_groups)가 있는 클러스터
    (PROPOSED_GROUP_CANDIDATE, 15개)도 예외 없다 — 중계열 Hint는 후보 근거일
    뿐 확정 근거가 아니다(§ 과제 지시)."""

    existing_by_key = load_nce_review_entries_by_key(NCE_REVIEW_PATH)
    closed: list[str] = []
    for row in sorted(nce_rows, key=lambda r: r["official_middle_series_code"]):
        code = row["official_middle_series_code"]
        existing = existing_by_key.get(code)
        if existing is not None and existing.decision == "EXCLUDE_FROM_INITIAL_PROMOTION" and existing.resolution_note == RESOLUTION_NOTE:
            continue
        update_nce_middle_series_review(
            code, decision="EXCLUDE_FROM_INITIAL_PROMOTION", comment=None, resolution_note=RESOLUTION_NOTE,
            expected_revision=existing.revision if existing is not None else 0, review_status_path=NCE_REVIEW_PATH,
        )
        closed.append(code)
    return closed


def main() -> int:
    use_utf8_stdout()

    group_rows = classify_groups()
    mapping_rows, scope_rows = classify_bridge(
        mapping_review_path=BRIDGE_MAPPING_REVIEW_PATH, scope_review_path=BRIDGE_SCOPE_REVIEW_PATH,
    )
    p1_rows = classify_p1()
    nce_rows = classify_nce()

    closed_groups = close_group_reviews(group_rows)
    closed_mapping = close_bridge_mapping_reviews(mapping_rows)
    closed_scope = close_bridge_scope_reviews(scope_rows)
    closed_p1 = close_p1_reviews(p1_rows)
    closed_nce = close_nce_reviews(nce_rows)

    print("Final Mapping Closure 종결 완료")
    print(f"  Group 검수 저장 {len(closed_groups)}건(42개 전부)")
    print(f"  Bridge Mapping 신규 승인 {len(closed_mapping)}건(기존 38건은 무변경)")
    print(f"  Bridge Scope 검수 저장 {len(closed_scope)}건")
    print(f"  P1 검수 저장 {len(closed_p1)}건")
    print(f"  N.C.E 검수 저장 {len(closed_nce)}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
