"""Final Mapping Closure — 최종 검수 대상 축소 — a/final-mapping-closure.

Canonical Major Group(42)·Bridge Mapping(44)·Bridge Scope(같은 44행)·P1 분류
후보(374)·N.C.E 중계열(24개·학과 584건) 전부를 실제 Draft·Review Store에서
읽어 세 종류로 분류한 최종 검수 패킷을 만든다:

- PROPOSE_APPROVE: 공식 코드·기존 정본으로 근거가 충분함
- PROPOSE_EXCLUDE: 예체능·추천 범위 밖 등 제외 근거가 명확함
- HUMAN_REVIEW_REQUIRED: 사람 판단이 반드시 필요함

**이 스크립트는 어떤 검수 파일도 만들거나 고치지 않는다.** `data/reviews/`는
읽기만 한다 — Group 검수 상태(`canonical_major_group_review_status.jsonl`)·
Bridge Mapping 검수(`canonical_major_group_bridge_review_status.json`, 기존
APPROVE 38/REVISE 6를 그대로 읽기만 한다)·Bridge Scope/P1/N.C.E 검수(전부
아직 파일 자체가 없다 — Fail-Closed 기본값 그대로)를 전부 읽기 전용으로
집계한다. `auto_approved_rows`는 언제나 0이다.

## 분류 근거(임의로 정하지 않는다 — 전부 실제 파생 필드로 판정)

- **Group(42개)**: 공식 소계열 코드가 실제 대계열·중계열에 대응하는지
  (`getCodeBySeriesSystem`), 전국 학과 후보 수(`classification_dry_run.json`
  의 `departments_per_canonical_group`), Bridge Draft가 이 Group에 대해 직접
  남긴 `boundary_notes`(다른 Group에 대한 넓은 N.C.E/P1 참고 메모는 노이즈가
  커서 여기서는 판정에 쓰지 않는다 — Priority 문서에는 참고용으로 남긴다)로
  판정한다. Bridge Scope로 이미 좁혀 해결된 boundary_notes(business/
  education/industrial_engineering/mechanical_transport)는 PROPOSE_APPROVE로
  본다 — Scope 단계에서 이미 사람이 좁혀 해결한 우려를 Group 단계에서 다시
  미검수로 세지 않는다.
- **Bridge Mapping(44개)**: 기존 사람 검수(38 APPROVE/6 REVISE)를 그대로
  반영한다 — REVISE 6건만 HUMAN_REVIEW_REQUIRED. UNMAPPED(29건, 전부
  APPROVE)는 "이 Group에 서비스 Major 연결이 없다"는 이미 승인된 결론이므로
  PROPOSE_APPROVE로 두되, "포함 승인이 아니라 무연결 확인 승인"이라는 점을
  명시한다. EXCLUDED_RECOMMENDATION(5건, 전부 APPROVE)은 PROPOSE_EXCLUDE.
- **Bridge Scope(같은 44행 중 mapping_status≠UNMAPPED인 15행에만 적용)**:
  `INCLUDED_SMALL_SERIES_ONLY`(공식 소계열 코드 명시, 4건)·`FULL_GROUP`(연결
  Mapping이 이미 APPROVE인 4건)은 PROPOSE_APPROVE.
  `DEPARTMENT_REVIEW_REQUIRED`(2건, bio_medical_engineering→life_science·
  computer_science→hci_ux)는 정의상 HUMAN_REVIEW_REQUIRED.
  `EXCLUDED_RECOMMENDATION`(5건)은 PROPOSE_EXCLUDE. UNMAPPED 29건은 Scope
  질문 자체가 성립하지 않아(`scope_type=None`) 이 분류 밖(not_applicable)이다.
- **P1(374건)**: `judgment_evidence_sufficient`와 `judgment_candidate`로만
  판정한다 — 이름 유사도로 승인하지 않는다. `MEDIA_COMMUNICATION_CANDIDATE`
  (근거 충분, 공식 소계열 확정)는 PROPOSE_APPROVE. `DESIGN_ARTS_EXCLUDED`(근거
  충분, 예체능 제외 정책 대상)는 PROPOSE_EXCLUDE. `HCI_UX_CANDIDATE`(근거
  불충분 — 공식 소계열 대응 코드 자체가 없다)·`NEEDS_OFFICIAL_CURRICULUM`·
  `UNMAPPED`은 HUMAN_REVIEW_REQUIRED.
- **N.C.E(중계열 24개·학과 584건)**: 중계열 Hint는 후보 근거일 뿐 확정 근거가
  아니므로, `group_linkage_status`가 `PROPOSED_GROUP_CANDIDATE`든
  `DEPARTMENT_LEVEL_REVIEW_REQUIRED`든 자동으로 특정 Major에 연결하지
  않는다 — 24개 클러스터(584건 전체) 전부 HUMAN_REVIEW_REQUIRED다. 분류
  결정 단위는 클러스터(24개)로 삼는다 — 사람이 실제로 판단하는 단위가
  학과 584건 개별이 아니라 클러스터이기 때문이다(각 클러스터 카드에 소속
  학과 전부를 나열한다).

## 예상 READY_FOR_PROMOTION

`career_build_national_department_promotion_dry_run.py`의 `load_inputs()`/
`evaluate_department()`를 그대로 재사용해(다시 구현하지 않는다), 이 스크립트가
PROPOSE_APPROVE로 분류한 항목만 승인됐다고 가정한 **임시(tempfile) 검수
Fixture**로 Dry Run을 한 번 더 계산한다 — 이 계산은 실제
`data/reviews/`·`data/master/departments.jsonl`·공개 API 어느 것도 건드리지
않는다. 실제 전국 정규화·분류 결과(대학알리미 API 재호출 없이 이미 복원된
Read-Only Snapshot, `--restore-data-dir`로 명시적으로 지정)가 없으면 이
계산은 건너뛰고 그 사실을 결과에 그대로 남긴다(숫자를 지어내지 않는다)."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_build_national_department_promotion_dry_run import (  # noqa: E402
    evaluate_department,
    load_inputs as load_dry_run_inputs,
    MissingRequiredInputError,
    write_jsonl_atomic,
    write_text_atomic,
)
from scripts.career_console import use_utf8_stdout  # noqa: E402
from src.review_ui.academyinfo_p1_classification_review_service import p1_approve_eligible  # noqa: E402
from src.review_ui.canonical_major_group_review_service import (  # noqa: E402
    _bridge_linked_and_boundary_notes,
    build_canonical_major_group_review_list,
)
from src.services.canonical_major_group_bridge_loader import (  # noqa: E402
    ARTS_EXCLUDED_GROUP_IDS,
    DEFAULT_BRIDGE_DRAFT_PATH,
    load_canonical_major_group_bridge,
)
from src.services.academyinfo_p1_classification_loader import DEFAULT_P1_PACKET_PATH, load_p1_classification_packet  # noqa: E402
from src.services.academyinfo_nce_middle_series_cluster_loader import DEFAULT_NCE_CLUSTER_PATH  # noqa: E402

# ── Bridge Scope §4 — 그대로 보존해야 하는 기존 결정(과제 지시 §4, 임의 변경 금지) ──
PRESERVED_INCLUDED_SMALL_SERIES_SCOPE = {
    "business": (["033"], "business_administration"),
    "education": (["042"], "education"),
    "industrial_engineering": (["102"], "industrial_engineering"),
    "mechanical_transport": (["078"], "mechanical_engineering"),
}
PRESERVED_DEPARTMENT_REVIEW_REQUIRED_SCOPE = {
    ("bio_medical_engineering", "life_science"),
    ("computer_science", "hci_ux"),
}

# 이 4개 Group의 Bridge boundary_notes는 위 Scope 좁히기로 이미 해결됐다고 본다
# (Group 분류 판정에서 "이미 Scope로 해결됨" 사유로 PROPOSE_APPROVE 처리).
_BOUNDARY_RESOLVED_BY_SCOPE_GROUP_IDS = frozenset(PRESERVED_INCLUDED_SMALL_SERIES_SCOPE.keys())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hash_or_missing(path: Path) -> str:
    return sha256_file(path) if path.exists() else "MISSING"


def canonical_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2)


def write_json_atomic(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(canonical_dumps(obj) + "\n", encoding="utf-8", newline="\n")
    tmp.replace(path)


# ============================== 1. Canonical Major Group(42개) ==============================


def classify_groups(*, group_draft_path: Path | None = None, bridge_path: Path | None = None) -> list[dict[str, Any]]:
    """§3 — Group마다 공식 대계열·중계열·소계열 구성, 전국 학과 수, 예체능 여부,
    Bridge 연결(EVIDENCED 기준, 느슨한 "행이 있으면 연결"이 아니다) 여부를 표시하고,
    승인/보류(HOLD) 제안과 근거를 남긴다. `build_canonical_major_group_review_list()`
    (기존 Group 검수 탭 서비스, `a/canonical-major-group-review-ui`가 이미 만든 것)를
    그대로 재사용한다 — 대계열·중계열 조인·전국 학과 수 조인을 다시 만들지 않는다."""

    resp = build_canonical_major_group_review_list(group_draft_path=group_draft_path, bridge_path=bridge_path)

    # 이 Group에 대해 실제로 EVIDENCED 연결이 있는지(기존 서비스의 is_bridge_linked는
    # "이 Group을 언급하는 Bridge 행이 하나라도 있다"는 훨씬 느슨한 정의라 — UNMAPPED
    # 행도 "언급"으로 친다 — 여기서는 더 정확한 정의로 다시 계산한다).
    try:
        bridge_report = load_canonical_major_group_bridge(bridge_path or DEFAULT_BRIDGE_DRAFT_PATH, group_draft_path=group_draft_path)
        evidenced_group_ids = {e.canonical_major_group_id for e in bridge_report.entries if e.mapping_status == "EVIDENCED"}
    except Exception:  # noqa: BLE001 — Group 분류 자체를 막지 않는다, Bridge 쪽 연결 표시만 비운다.
        evidenced_group_ids = set()

    _, bridge_own_notes = _bridge_linked_and_boundary_notes(bridge_path, group_draft_path)

    rows: list[dict[str, Any]] = []
    for r in resp.rows:
        group_id = r.canonical_major_group_id
        own_notes = bridge_own_notes.get(group_id, [])
        has_composition = bool(r.official_series.middle_series_codes) and bool(r.official_series.large_series_codes)
        has_departments = bool(r.national_department_candidate_count)

        if not has_composition:
            disposition = "HUMAN_REVIEW_REQUIRED"
            proposal_decision = "HOLD"
            reason = "공식 소계열 코드가 대계열/중계열 어디에도 대응하지 않는다 — 코드표 정합성부터 사람이 확인해야 한다."
        elif not has_departments:
            disposition = "HUMAN_REVIEW_REQUIRED"
            proposal_decision = "HOLD"
            reason = "이 Group에 대응하는 전국 학과 후보가 0건이다 — 실사용 근거가 없어 유지/병합/제외를 사람이 결정해야 한다."
        elif own_notes and group_id not in _BOUNDARY_RESOLVED_BY_SCOPE_GROUP_IDS:
            disposition = "HUMAN_REVIEW_REQUIRED"
            proposal_decision = "HOLD"
            reason = "Bridge Draft가 이 Group에 대해 직접 남긴 경계 메모가 아직 해결되지 않았다: " + " / ".join(own_notes)
        else:
            disposition = "PROPOSE_APPROVE"
            proposal_decision = "APPROVE_AS_CLASSIFICATION_GROUP"
            if own_notes and group_id in _BOUNDARY_RESOLVED_BY_SCOPE_GROUP_IDS:
                reason = (
                    "공식 소계열 코드가 대계열·중계열에 정합적으로 대응하고 전국 학과 후보도 있다. "
                    "Bridge boundary_notes가 있었지만 Bridge Scope 단계에서 이미 소계열로 좁혀 "
                    "해결됐다(§4 보존 대상): " + " / ".join(own_notes)
                )
            else:
                reason = "공식 소계열 코드가 대계열·중계열에 정합적으로 대응하고, 전국 학과 후보가 있으며, Bridge Draft의 직접 경계 메모가 없다."

        rows.append(
            {
                "canonical_major_group_id": group_id,
                "label": r.label,
                "official_large_series_codes": r.official_series.large_series_codes,
                "official_large_series_names": r.official_series.large_series_names,
                "official_middle_series_codes": r.official_series.middle_series_codes,
                "official_middle_series_names": r.official_series.middle_series_names,
                "included_official_small_series_codes": r.included_official_small_series_codes,
                "included_official_small_series_names": r.official_series.included_small_series_names,
                "national_department_candidate_count": r.national_department_candidate_count,
                "is_arts_or_sports_excluded_from_recommendation": group_id in ARTS_EXCLUDED_GROUP_IDS,
                "has_evidenced_bridge_connection": group_id in evidenced_group_ids,
                "bridge_own_boundary_notes": own_notes,
                "cross_review_reference_notes": r.cross_review_boundary_notes,
                "disposition": disposition,
                "proposal_decision": proposal_decision,
                "proposal_reason": reason,
                "current_review_status": r.review.decision,
            }
        )
    rows.sort(key=lambda x: x["canonical_major_group_id"])
    return rows


# ============================== 2/3. Bridge Mapping(44) · Bridge Scope(같은 44행) ==============================


def _load_bridge_mapping_review_by_key(review_path: Path) -> dict[tuple[str, str | None], str]:
    if not review_path.exists():
        return {}
    rows = json.loads(review_path.read_text(encoding="utf-8"))
    return {(r["canonical_major_group_id"], r.get("canonical_major_id")): r["reviewer_1_status"] for r in rows}


def classify_bridge(
    *, bridge_path: Path | None = None, group_draft_path: Path | None = None,
    mapping_review_path: Path, scope_review_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """§4 — 같은 44행에서 Mapping 축과 Scope 축을 따로 분류한다. Mapping은 기존
    사람 검수(38 APPROVE/6 REVISE)를 그대로 반영한다 — 이 함수가 그 결정을
    다시 판정하지 않는다(§4 "기존 결정은 그대로 보존"). Scope는
    `scope_review_status` 파일이 아직 없으므로(Fail-Closed) 이 함수가 Draft의
    `scope_type`·연결된 Mapping 검수 상태만으로 제안한다."""

    bridge_report = load_canonical_major_group_bridge(bridge_path or DEFAULT_BRIDGE_DRAFT_PATH, group_draft_path=group_draft_path)
    mapping_review_by_key = _load_bridge_mapping_review_by_key(mapping_review_path)
    scope_review_exists = scope_review_path.exists()

    mapping_rows: list[dict[str, Any]] = []
    scope_rows: list[dict[str, Any]] = []

    for e in bridge_report.entries:
        key = (e.canonical_major_group_id, e.canonical_major_id)
        reviewer_status = mapping_review_by_key.get(key, "TBD")

        # ── Mapping 축 ──
        if e.mapping_status == "EXCLUDED_RECOMMENDATION":
            m_disposition = "PROPOSE_EXCLUDE"
            m_reason = f"기존 사람 검수 {reviewer_status} — 예체능 추천 제외 정책 대상(4개 예체능 Group 중 하나)."
        elif reviewer_status == "APPROVE":
            m_disposition = "PROPOSE_APPROVE"
            if e.mapping_status == "UNMAPPED":
                m_reason = (
                    "기존 사람 검수 APPROVE — 단, 이 승인은 '서비스 Major 10개 중 어디에도 연결되지 "
                    "않는다'는 결론에 대한 승인이지, 학과 포함을 승인한 것이 아니다."
                )
            else:
                m_reason = f"기존 사람 검수 APPROVE — {e.decision_reason}"
        else:
            m_disposition = "HUMAN_REVIEW_REQUIRED"
            m_reason = f"기존 사람 검수 {reviewer_status}(REVISE) — 아직 해결되지 않았다. {e.decision_reason}"

        mapping_rows.append(
            {
                "canonical_major_group_id": e.canonical_major_group_id,
                "canonical_major_id": e.canonical_major_id,
                "mapping_status": e.mapping_status,
                "evidence": e.evidence,
                "decision_reason": e.decision_reason,
                "existing_reviewer_1_status": reviewer_status,
                "disposition": m_disposition,
                "proposal_reason": m_reason,
            }
        )

        # ── Scope 축(scope_type이 없으면 질문 자체가 성립하지 않는다) ──
        if e.scope_type is None:
            scope_rows.append(
                {
                    "canonical_major_group_id": e.canonical_major_group_id,
                    "canonical_major_id": e.canonical_major_id,
                    "scope_type": None,
                    "disposition": "NOT_APPLICABLE",
                    "proposal_reason": "Mapping이 UNMAPPED라 Scope 질문 자체가 성립하지 않는다.",
                }
            )
            continue

        if e.scope_type == "DEPARTMENT_REVIEW_REQUIRED":
            s_disposition = "HUMAN_REVIEW_REQUIRED"
            s_reason = f"정의상 학과 단위 검토가 필요하다(§4 보존 대상). {e.scope_decision_reason}"
        elif e.scope_type == "EXCLUDED_RECOMMENDATION":
            s_disposition = "PROPOSE_EXCLUDE"
            s_reason = "예체능 추천 제외 Mapping과 동일한 Scope다."
        elif e.scope_type == "INCLUDED_SMALL_SERIES_ONLY":
            s_disposition = "PROPOSE_APPROVE"
            s_reason = f"공식 소계열 코드 {e.included_small_series_codes}로 범위가 명시돼 있다(§4 보존 대상). {e.scope_decision_reason}"
        elif e.scope_type == "FULL_GROUP":
            if reviewer_status == "APPROVE":
                s_disposition = "PROPOSE_APPROVE"
                s_reason = f"연결된 Mapping이 이미 사람 검수 APPROVE다 — Group 전체 범위를 그대로 유지한다. {e.scope_decision_reason}"
            else:
                s_disposition = "HUMAN_REVIEW_REQUIRED"
                s_reason = "연결된 Mapping 자체가 아직 REVISE라 Scope도 함께 보류한다 — Mapping이 먼저 정리돼야 한다."
        else:
            s_disposition = "HUMAN_REVIEW_REQUIRED"
            s_reason = f"알 수 없는 scope_type({e.scope_type}) — 사람이 확인해야 한다."

        scope_rows.append(
            {
                "canonical_major_group_id": e.canonical_major_group_id,
                "canonical_major_id": e.canonical_major_id,
                "scope_type": e.scope_type,
                "included_small_series_codes": e.included_small_series_codes,
                "excluded_small_series_codes": e.excluded_small_series_codes,
                "scope_decision_reason": e.scope_decision_reason,
                "scope_review_file_exists": scope_review_exists,
                "disposition": s_disposition,
                "proposal_reason": s_reason,
            }
        )

    mapping_rows.sort(key=lambda x: (x["canonical_major_group_id"], x["canonical_major_id"] or ""))
    scope_rows.sort(key=lambda x: (x["canonical_major_group_id"], x["canonical_major_id"] or ""))
    return mapping_rows, scope_rows


class PreservedBridgeScopeMismatchError(RuntimeError):
    """§4 '기존 결정은 그대로 보존' — 실제 Draft가 지시서에 나열된 6개 기존
    결정과 다르면 조용히 넘어가지 않고 여기서 멈춘다."""


def verify_preserved_bridge_scope_decisions(scope_rows: list[dict[str, Any]]) -> None:
    by_key = {(r["canonical_major_group_id"], r["canonical_major_id"]): r for r in scope_rows}
    for group_id, (codes, major_id) in PRESERVED_INCLUDED_SMALL_SERIES_SCOPE.items():
        row = by_key.get((group_id, major_id))
        if row is None or row["scope_type"] != "INCLUDED_SMALL_SERIES_ONLY" or row["included_small_series_codes"] != codes:
            raise PreservedBridgeScopeMismatchError(
                f"{group_id}->{major_id}: 기존 INCLUDED_SMALL_SERIES_ONLY({codes}) 보존 대상이 Draft와 다르다: {row}"
            )
    for group_id, major_id in PRESERVED_DEPARTMENT_REVIEW_REQUIRED_SCOPE:
        row = by_key.get((group_id, major_id))
        if row is None or row["scope_type"] != "DEPARTMENT_REVIEW_REQUIRED":
            raise PreservedBridgeScopeMismatchError(
                f"{group_id}->{major_id}: 기존 DEPARTMENT_REVIEW_REQUIRED 보존 대상이 Draft와 다르다: {row}"
            )


def verify_preserved_bridge_mapping_review(mapping_rows: list[dict[str, Any]]) -> None:
    approve = sum(1 for r in mapping_rows if r["existing_reviewer_1_status"] == "APPROVE")
    revise = sum(1 for r in mapping_rows if r["existing_reviewer_1_status"] == "REVISE")
    if (approve, revise) != (38, 6):
        raise PreservedBridgeScopeMismatchError(
            f"기존 Bridge Mapping 검수(APPROVE 38/REVISE 6)와 다르다: APPROVE={approve}, REVISE={revise}"
        )


# ============================== 4. P1 분류 후보(374건) ==============================


def classify_p1(*, p1_path: Path | None = None) -> list[dict[str, Any]]:
    """§5 — `judgment_evidence_sufficient`/`judgment_candidate`로만 판정한다.
    이름 유사도만으로 승인 제안하지 않는다 — HCI_UX_CANDIDATE는 근거 불충분
    (공식 소계열 대응 코드 자체가 없다, `academyinfo_p1_classification_loader`
    문서 그대로)이라 이름이 비슷해도 HUMAN_REVIEW_REQUIRED로 남긴다."""

    entries = load_p1_classification_packet(p1_path or DEFAULT_P1_PACKET_PATH)
    rows: list[dict[str, Any]] = []
    for e in entries:
        if e.judgment_candidate == "DESIGN_ARTS_EXCLUDED" and e.judgment_evidence_sufficient:
            disposition = "PROPOSE_EXCLUDE"
            reason = f"공식 소계열 기준 예체능 제외 정책 대상으로 확정됨: {e.judgment_candidate_reason}"
        elif e.judgment_evidence_sufficient and p1_approve_eligible(e):
            disposition = "PROPOSE_APPROVE"
            reason = f"공식 소계열 코드로 후보 1개가 확정되고 실제 서비스 Major다: {e.judgment_candidate_reason}"
        else:
            disposition = "HUMAN_REVIEW_REQUIRED"
            reason = (
                f"근거 불충분(judgment_evidence_sufficient=False) 또는 서비스 Major 미확정 — "
                f"이름 유사도만으로 승인하지 않는다: {e.judgment_candidate_reason}"
            )
        rows.append(
            {
                "candidate_id": e.candidate_id,
                "department_id": e.department_id,
                "university_name": e.university_name,
                "college_name": e.college_name,
                "department_name": e.department_name,
                "p1_cluster": e.p1_cluster,
                "judgment_candidate": e.judgment_candidate,
                "judgment_evidence_sufficient": e.judgment_evidence_sufficient,
                "candidate_canonical_major_ids": e.candidate_canonical_major_ids,
                "official_small_series_name": e.official_small_series_name,
                "disposition": disposition,
                "proposal_reason": reason,
            }
        )
    rows.sort(key=lambda x: x["candidate_id"])
    return rows


# ============================== 5. N.C.E 중계열(24개)·학과(584건) ==============================


def classify_nce(*, nce_path: Path | None = None) -> list[dict[str, Any]]:
    """§6 — 중계열 Hint는 후보 근거일 뿐 확정 근거가 아니다. 어떤 클러스터도
    자동으로 특정 Major에 연결하지 않는다 — 24개 클러스터(584건) 전부
    HUMAN_REVIEW_REQUIRED다. `group_linkage_status`는 Pydantic Schema에
    모델링돼 있지 않은 원본 필드라(Draft 저자의 참고용 표시), 원본 JSONL을
    직접 읽어서 그대로 보여준다 — 이 값으로 승인 여부를 가르지 않는다(정보성
    표시일 뿐, 이 함수의 disposition은 이 값과 무관하게 전부 HUMAN_REVIEW_
    REQUIRED로 고정한다)."""

    raw_rows = read_jsonl(nce_path or DEFAULT_NCE_CLUSTER_PATH)
    rows: list[dict[str, Any]] = []
    for row in raw_rows:
        members = row.get("members", [])
        rows.append(
            {
                "cluster_id": row["cluster_id"],
                "official_middle_series_code": row["official_middle_series_code"],
                "official_middle_series_name": row["official_middle_series_name"],
                "group_linkage_status": row.get("group_linkage_status"),
                "candidate_canonical_major_groups": row.get("candidate_canonical_major_groups", []),
                "member_department_count": len(members),
                "member_departments": [
                    {
                        "department_id": m["department_id"], "university_name": m["university_name"],
                        "college_name": m["college_name"], "department_name": m["department_name"],
                    }
                    for m in members
                ],
                "unlinkable_or_too_broad_reason": row.get("unlinkable_or_too_broad_reason", ""),
                "additional_official_evidence_needed": row.get("additional_official_evidence_needed", []),
                "disposition": "HUMAN_REVIEW_REQUIRED",
                "proposal_reason": (
                    "중계열 Hint는 후보 근거일 뿐 확정 근거가 아니다 — N.C.E는 학과 단위 검토 "
                    "전까지 어떤 Major에도 자동 연결하지 않는다(과제 §6)."
                ),
            }
        )
    rows.sort(key=lambda x: x["cluster_id"])
    return rows


# ============================== 예상 READY_FOR_PROMOTION(가정 Dry Run) ==============================


def _write_hypothetical_group_draft(path: Path, group_rows: list[dict[str, Any]], *, real_draft_path: Path) -> None:
    """승격 Dry Run의 `BLOCKED_GROUP_DRAFT` Gate는 별도 검수 Store가 아니라
    `CanonicalMajorGroupDraft.review_status`(Draft 파일 자체의 필드)를 직접 읽는다
    (`evaluate_department()`: `group.review_status != "approved"`) — 그래서
    가정 계산은 Draft 파일의 **복사본**에서 PROPOSE_APPROVE Group만
    `review_status="approved"`로 바꾼 임시 파일을 만든다. 실제
    `data/canonical_major_groups.draft.jsonl`은 전혀 건드리지 않는다."""

    approved_ids = {r["canonical_major_group_id"] for r in group_rows if r["disposition"] == "PROPOSE_APPROVE"}
    rows = read_jsonl(real_draft_path)
    for row in rows:
        if row["canonical_major_id"] in approved_ids:
            row["review_status"] = "approved"
    write_jsonl_atomic(path, rows)


def _write_hypothetical_bridge_scope_review(path: Path, scope_rows: list[dict[str, Any]]) -> None:
    rows = [
        {
            "canonical_major_group_id": r["canonical_major_group_id"],
            "canonical_major_id": r["canonical_major_id"],
            "reviewer_1_status": "APPROVE",
            "reviewer_1_comment": "final-mapping-closure 가정 계산 — 실제 검수 아님",
            "reviewer_2_status": "TBD",
            "reviewer_2_comment": "",
            "resolution_note": "",
            "revision": "",
        }
        for r in scope_rows
        if r["disposition"] == "PROPOSE_APPROVE"
    ]
    write_jsonl_atomic(path, rows)


def _write_hypothetical_p1_review(path: Path, p1_rows: list[dict[str, Any]]) -> None:
    rows = [
        {
            "candidate_id": r["candidate_id"],
            "decision": "APPROVE_PROPOSED_CANDIDATE",
            "reviewer_comment": "final-mapping-closure 가정 계산 — 실제 검수 아님",
            "resolution_note": "",
            "revision": 0,
        }
        for r in p1_rows
        if r["disposition"] == "PROPOSE_APPROVE"
    ]
    write_jsonl_atomic(path, rows)


def compute_hypothetical_ready_for_promotion(
    *, group_rows: list[dict[str, Any]], scope_rows: list[dict[str, Any]], p1_rows: list[dict[str, Any]],
    restore_normalized_path: Path | None, restore_classification_path: Path | None,
) -> dict[str, Any]:
    """이 스크립트가 PROPOSE_APPROVE로 분류한 항목만 승인됐다고 가정하고, 실제
    Dry Run Gate(`evaluate_department`, 다시 구현하지 않는다)를 그대로 돌려
    예상 READY_FOR_PROMOTION을 계산한다. 실제 전국 정규화·분류 결과가
    (명시적으로) 제공되지 않으면 계산을 건너뛰고 그 사실을 그대로 남긴다 —
    숫자를 지어내지 않는다."""

    if restore_normalized_path is None or restore_classification_path is None:
        return {
            "computed": False,
            "reason": (
                "실제 전국 정규화·분류 결과 경로가 제공되지 않았다(--restore-normalized-path/"
                "--restore-classification-path) — 이 통계는 API 재호출 없이 이미 복원된 Snapshot이 "
                "있을 때만 계산한다. 계산하지 않은 채로 0을 보고하지 않는다."
            ),
        }
    if not restore_normalized_path.exists() or not restore_classification_path.exists():
        return {
            "computed": False,
            "reason": f"지정된 경로가 존재하지 않는다: {restore_normalized_path}, {restore_classification_path}",
        }

    with tempfile.TemporaryDirectory(prefix="final_mapping_closure_hypothetical_") as tmp:
        tmp_dir = Path(tmp)
        work_dir = tmp_dir / "academyinfo_work" / "2025"
        reviews_dir = tmp_dir / "reviews"
        work_dir.mkdir(parents=True, exist_ok=True)
        reviews_dir.mkdir(parents=True, exist_ok=True)
        packets_dir = work_dir / "packets"
        packets_dir.mkdir(parents=True, exist_ok=True)

        hypothetical_group_draft_path = tmp_dir / "canonical_major_groups.hypothetical.draft.jsonl"
        _write_hypothetical_group_draft(
            hypothetical_group_draft_path, group_rows, real_draft_path=ROOT / "data" / "canonical_major_groups.draft.jsonl"
        )
        _write_hypothetical_bridge_scope_review(
            reviews_dir / "canonical_major_group_bridge_scope_review_status.jsonl", scope_rows
        )
        _write_hypothetical_p1_review(reviews_dir / "academyinfo_p1_classification_review_status.jsonl", p1_rows)
        # Bridge Mapping 검수·N.C.E 검수는 실제 파일을 그대로 쓴다 — Mapping은 이미
        # 사람이 검수한 38 APPROVE/6 REVISE를 이 계산에서도 바꾸지 않는다(§4 보존).
        # N.C.E는 이 스크립트가 어떤 것도 PROPOSE_APPROVE로 분류하지 않으므로(§6),
        # 검수 파일이 없어도(Fail-Closed) 결과가 달라지지 않는다.

        try:
            inputs = load_dry_run_inputs(
                data_dir=tmp_dir,
                survey_year=2025,
                reviews_dir=reviews_dir,
                group_draft_path=hypothetical_group_draft_path,
                bridge_draft_path=ROOT / "data" / "master" / "canonical_major_group_bridge.draft.jsonl",
                small_series_code_table_path=ROOT / "data" / "academyinfo_raw" / "2025" / "codes" / "getCodeBySmallSeries.jsonl.gz",
                canonical_majors_path=ROOT / "data" / "master" / "canonical_majors.jsonl",
                bridge_mapping_review_path=ROOT / "data" / "reviews" / "canonical_major_group_bridge_review_status.json",
                bridge_scope_review_path=reviews_dir / "canonical_major_group_bridge_scope_review_status.jsonl",
                p1_packet_path=ROOT / "data" / "academyinfo_work" / "2025" / "packets" / "p1_classification_review.jsonl",
                p1_review_path=reviews_dir / "academyinfo_p1_classification_review_status.jsonl",
                nce_clusters_path=ROOT / "data" / "academyinfo_work" / "2025" / "packets" / "nce_reexaminable_middle_series_clusters.jsonl",
                nce_review_path=reviews_dir / "academyinfo_nce_middle_series_review_status.jsonl",
                url_audit_path=tmp_dir / "__no_url_audit__.jsonl",
                normalized_path=restore_normalized_path,
                classification_path=restore_classification_path,
                out_of_scope_path=tmp_dir / "__no_out_of_scope__.jsonl",
            )
        except MissingRequiredInputError as exc:
            return {"computed": False, "reason": f"필수 입력 로딩 실패: {exc}"}

        rows = [evaluate_department(row, inputs) for row in inputs.departments]

    ready = [r for r in rows if r["status"] == "READY_FOR_PROMOTION"]
    blocked = [r for r in rows if r["status"] == "BLOCKED"]
    reason_counts: dict[str, int] = {}
    for r in blocked:
        for reason in r["blocked_reasons"]:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    return {
        "computed": True,
        "evaluated_department_count": len(rows),
        "ready_for_promotion_count": len(ready),
        "blocked_count": len(blocked),
        "blocked_reason_counts": dict(sorted(reason_counts.items())),
        "note": (
            "이 스크립트가 PROPOSE_APPROVE로 분류한 Group/Bridge Scope/P1 항목만 승인됐다고 "
            "가정한 임시(tempfile) Fixture 계산이다 — 실제 data/reviews/·Master·API는 전혀 "
            "바뀌지 않았다. 야간·원격 제외(out_of_recommendation_scope.jsonl)와 URL 정책 감사는 "
            "이번 계산 범위에 포함하지 않았다(이 Worktree의 해당 파일이 이번 복원 Snapshot과 "
            "다른 시점의 것이라 섞으면 왜곡된다)."
        ),
    }


# N.C.E는 규칙상 검수 상태와 무관하게 영구히 BLOCKED_NCE_UNRESOLVED다(과제 §6, Dry
# Run 모듈 docstring §7과 동일 원칙) — 전부 승인돼도 절대 안 풀리는 사유만 별도로
# 표시한다. Duplicate/계약학과/비활성/URL/야간원격도 검수와 무관한 구조적 사유다.
# ARTS_RECOMMENDATION(예체능 정책, 학과 본인이 아니라 정책 자체가 원인)·
# OUTSIDE_SMALL_SERIES_SCOPE(승인된 좁은 Scope에 학과 자신의 공식 소계열이 안 맞음 —
# Scope를 넓히는 별도 결정이 있어야지 "기존 Scope 승인"으로는 안 풀린다)·
# NO_SERVICE_CANONICAL_MAJOR(이 Group에 연결된 Bridge 자체가 없음 — 이번 검수
# 패킷이 다루는 기존 Draft 항목을 전부 승인해도, 존재하지 않는 Bridge를 새로
# 만들지 않는 한 풀리지 않는다)도 이번 검수 패킷의 승인 범위로는 못 푸는
# 구조적 사유다.
PERMANENTLY_STRUCTURAL_BLOCKED_REASONS = frozenset(
    {
        "BLOCKED_NCE_UNRESOLVED", "BLOCKED_INACTIVE_STATUS", "BLOCKED_DUPLICATE_ID",
        "BLOCKED_CONTRACT_DEPARTMENT", "BLOCKED_NIGHT_OR_REMOTE", "BLOCKED_URL_POLICY",
        "BLOCKED_MISSING_LINEAGE", "BLOCKED_MISSING_CLASSIFICATION",
        "BLOCKED_ARTS_RECOMMENDATION", "BLOCKED_OUTSIDE_SMALL_SERIES_SCOPE",
        "BLOCKED_NO_SERVICE_CANONICAL_MAJOR",
    }
)


# ============================== 집계 ==============================


def _counts(rows: list[dict[str, Any]], *, dispositions: tuple[str, ...] = ("PROPOSE_APPROVE", "PROPOSE_EXCLUDE", "HUMAN_REVIEW_REQUIRED")) -> dict[str, int]:
    counts = {d: 0 for d in dispositions}
    for r in rows:
        d = r["disposition"]
        if d in counts:
            counts[d] += 1
    return counts


def build_summary(
    *, group_rows, mapping_rows, scope_rows, p1_rows, nce_rows, hypothetical: dict[str, Any],
    bridge_mapping_review_baseline: dict[str, int], group_review_file_exists: bool,
    bridge_scope_review_file_exists: bool, p1_review_file_exists: bool, nce_review_file_exists: bool,
) -> dict[str, Any]:
    scope_applicable = [r for r in scope_rows if r["disposition"] != "NOT_APPLICABLE"]
    scope_not_applicable = [r for r in scope_rows if r["disposition"] == "NOT_APPLICABLE"]

    group_counts = _counts(group_rows)
    mapping_counts = _counts(mapping_rows)
    scope_counts = _counts(scope_applicable)
    p1_counts = _counts(p1_rows)
    # N.C.E는 클러스터(24) 단위로 집계한다 — 학과(584)는 세부 개수로만 표시한다.
    nce_cluster_counts = _counts(nce_rows)
    nce_department_counts = {"PROPOSED_GROUP_CANDIDATE": 0, "DEPARTMENT_LEVEL_REVIEW_REQUIRED": 0, "OTHER": 0}
    for r in nce_rows:
        status = r.get("group_linkage_status")
        key = status if status in nce_department_counts else "OTHER"
        nce_department_counts[key] += r["member_department_count"]

    propose_approve_total = (
        group_counts["PROPOSE_APPROVE"] + mapping_counts["PROPOSE_APPROVE"] + scope_counts["PROPOSE_APPROVE"]
        + p1_counts["PROPOSE_APPROVE"] + nce_cluster_counts["PROPOSE_APPROVE"]
    )
    propose_exclude_total = (
        group_counts["PROPOSE_EXCLUDE"] + mapping_counts["PROPOSE_EXCLUDE"] + scope_counts["PROPOSE_EXCLUDE"]
        + p1_counts["PROPOSE_EXCLUDE"] + nce_cluster_counts["PROPOSE_EXCLUDE"]
    )
    human_review_total = (
        group_counts["HUMAN_REVIEW_REQUIRED"] + mapping_counts["HUMAN_REVIEW_REQUIRED"]
        + scope_counts["HUMAN_REVIEW_REQUIRED"] + p1_counts["HUMAN_REVIEW_REQUIRED"]
        + nce_cluster_counts["HUMAN_REVIEW_REQUIRED"]
    )

    permanently_structural = {}
    if hypothetical.get("computed"):
        permanently_structural = {
            k: v for k, v in hypothetical["blocked_reason_counts"].items() if k in PERMANENTLY_STRUCTURAL_BLOCKED_REASONS
        }

    return {
        "unit_note": (
            "PROPOSE_APPROVE/PROPOSE_EXCLUDE/HUMAN_REVIEW_REQUIRED 건수는 각 항목의 자연스러운 "
            "검수 결정 단위로 센다 — Group 42개(Group 단위), Bridge Mapping 44개(Group×Major 쌍 "
            "단위), Bridge Scope는 Mapping이 UNMAPPED가 아닌 15개만(29개는 Scope 질문 자체가 "
            "성립하지 않아 not_applicable), P1 374개(학과 단위), N.C.E는 클러스터 24개(학과 584건은 "
            "세부 개수로 별도 표시 — 사람이 실제로 판단하는 단위가 클러스터이기 때문이다)."
        ),
        "baseline_before_this_packet": {
            "group_review_file_exists": group_review_file_exists,
            "group_unreviewed_count": 42,
            "bridge_mapping_review": bridge_mapping_review_baseline,
            "bridge_scope_review_file_exists": bridge_scope_review_file_exists,
            "p1_review_file_exists": p1_review_file_exists,
            "nce_review_file_exists": nce_review_file_exists,
            "note": "Bridge Mapping 외 전부 검수 파일 자체가 없다(Fail-Closed) — 42+44(Scope 적용 15)+374+24개 전부 미검수 상태에서 시작.",
        },
        "by_category": {
            "group": {"total": len(group_rows), **group_counts},
            "bridge_mapping": {"total": len(mapping_rows), **mapping_counts},
            "bridge_scope": {
                "total_rows_in_draft": len(scope_rows), "applicable": len(scope_applicable),
                "not_applicable": len(scope_not_applicable), **scope_counts,
            },
            "p1": {"total": len(p1_rows), **p1_counts},
            "nce_cluster": {"total": len(nce_rows), **nce_cluster_counts},
            "nce_department": {"total": sum(nce_department_counts.values()), **nce_department_counts},
        },
        "totals": {
            "propose_approve_total": propose_approve_total,
            "propose_exclude_total": propose_exclude_total,
            "human_review_required_total": human_review_total,
        },
        "expected_ready_for_promotion": hypothetical,
        "permanently_structural_blocked_reason_counts": permanently_structural,
        "auto_approved_rows": 0,
    }


# ============================== Priority HTML(HUMAN_REVIEW_REQUIRED만) ==============================

_CSS = """
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:0;padding:24px;
background:#0b0f14;color:#dbe4ee;line-height:1.5}
h1{font-size:20px;margin:0 0 4px}
h2{font-size:15px;color:#7fb8e6;border-top:1px solid #263140;padding-top:16px;margin-top:24px}
.sub{color:#8ea0b3;font-size:13px;margin-bottom:16px}
.warn{background:#3a2a12;border:1px solid #8a5a1e;padding:10px 14px;border-radius:6px;
font-size:13px;margin-bottom:20px}
.card{background:#131a22;border:1px solid #263140;border-radius:8px;padding:12px 16px;margin-bottom:10px}
.hd{font-weight:600;font-size:13.5px}
.meta{color:#8ea0b3;font-size:12px;margin-top:2px}
.reason{font-size:12.5px;margin-top:6px;color:#dbe4ee}
code{font-family:ui-monospace,monospace;color:#7fb8e6}
.filters{margin:10px 0}
.filters button{background:#1a2430;color:#dbe4ee;border:1px solid #263140;border-radius:6px;
padding:4px 10px;margin-right:6px;margin-bottom:6px;cursor:pointer;font-size:12px}
.filters button.active{background:#2a4a6a;border-color:#4a7ab0}
.count{color:#8ea0b3;font-size:12px;margin:6px 0}
.dept-list{font-size:12px;color:#9fb3c8;margin-top:6px;max-height:120px;overflow-y:auto}
"""

_JS = """
function pfFilter(kind, value){
  document.querySelectorAll('.filters[data-kind="'+kind+'"] button').forEach(function(b){
    b.classList.toggle('active', b.dataset.value === value);
  });
  var cards = document.querySelectorAll('.card[data-'+kind+']');
  var shown = 0;
  cards.forEach(function(c){
    var match = value === 'ALL' || c.dataset[kind] === value;
    if (!match) { c.style.display = 'none'; return; }
    c.style.display = '';
    shown += 1;
  });
  var counter = document.getElementById(kind + '-shown-count');
  if (counter) counter.textContent = shown;
}
"""


def _esc(v: Any) -> str:
    return html.escape("" if v is None else str(v))


def render_priority_html(*, group_rows, mapping_rows, scope_rows, p1_rows, nce_rows) -> str:
    group_hr = [r for r in group_rows if r["disposition"] == "HUMAN_REVIEW_REQUIRED"]
    mapping_hr = [r for r in mapping_rows if r["disposition"] == "HUMAN_REVIEW_REQUIRED"]
    scope_hr = [r for r in scope_rows if r["disposition"] == "HUMAN_REVIEW_REQUIRED"]
    p1_hr = [r for r in p1_rows if r["disposition"] == "HUMAN_REVIEW_REQUIRED"]
    nce_hr = [r for r in nce_rows if r["disposition"] == "HUMAN_REVIEW_REQUIRED"]

    total = len(group_hr) + len(mapping_hr) + len(scope_hr) + len(p1_hr) + len(nce_hr)

    blocks = ['<h1>Final Mapping Closure — Priority Review(사람이 봐야 하는 항목만)</h1>']
    blocks.append(
        f'<div class="sub">HUMAN_REVIEW_REQUIRED 총 {total}건 — '
        f'Group {len(group_hr)} · Bridge Mapping {len(mapping_hr)} · Bridge Scope {len(scope_hr)} · '
        f'P1 {len(p1_hr)} · N.C.E 클러스터 {len(nce_hr)}</div>'
    )
    blocks.append(
        '<div class="warn">이 문서는 PROPOSE_APPROVE/PROPOSE_EXCLUDE 항목을 포함하지 않는다 — '
        '전부 근거가 부족하거나 사람 판단이 반드시 필요하다고 판정된 항목이다. 이 문서를 읽고 '
        '아무 파일도 자동으로 바뀌지 않는다(reviewer 상태 변경·Master 승격·PATCH 호출 없음).</div>'
    )

    blocks.append("<h2>1. Canonical Major Group</h2>")
    for r in group_hr:
        blocks.append(
            f'<div class="card"><div class="hd">{_esc(r["canonical_major_group_id"])} — {_esc(r["label"])}</div>'
            f'<div class="meta">전국 학과 후보 {_esc(r["national_department_candidate_count"])}건 · '
            f'공식 중계열 {_esc(", ".join(r["official_middle_series_names"]))}</div>'
            f'<div class="reason">{_esc(r["proposal_reason"])}</div></div>'
        )

    blocks.append("<h2>2. Bridge Mapping(REVISE 유지분)</h2>")
    for r in mapping_hr:
        blocks.append(
            f'<div class="card"><div class="hd">{_esc(r["canonical_major_group_id"])} → '
            f'{_esc(r["canonical_major_id"] or "(연결 없음)")}</div>'
            f'<div class="meta">mapping_status={_esc(r["mapping_status"])} · 기존 검수={_esc(r["existing_reviewer_1_status"])}</div>'
            f'<div class="reason">{_esc(r["proposal_reason"])}</div></div>'
        )

    blocks.append("<h2>3. Bridge Scope(DEPARTMENT_REVIEW_REQUIRED)</h2>")
    for r in scope_hr:
        blocks.append(
            f'<div class="card"><div class="hd">{_esc(r["canonical_major_group_id"])} → {_esc(r["canonical_major_id"])}</div>'
            f'<div class="meta">scope_type={_esc(r["scope_type"])}</div>'
            f'<div class="reason">{_esc(r["proposal_reason"])}</div></div>'
        )

    p1_judgment_counts: dict[str, int] = {}
    for r in p1_hr:
        p1_judgment_counts[r["judgment_candidate"]] = p1_judgment_counts.get(r["judgment_candidate"], 0) + 1
    p1_buttons = "".join(
        f'<button data-value="{_esc(v)}" onclick="pfFilter(\'judgment\',\'{_esc(v)}\')">{_esc(v)} ({c})</button>'
        for v, c in sorted(p1_judgment_counts.items())
    )
    blocks.append(
        f'<h2>4. P1 분류 후보(경계 사례 — 디자인·HCI·UX·미디어 우선)</h2>'
        f'<div class="filters" data-kind="judgment">'
        f'<button data-value="ALL" class="active" onclick="pfFilter(\'judgment\',\'ALL\')">전체 ({len(p1_hr)})</button>'
        f'{p1_buttons}</div>'
        f'<div class="count"><span id="judgment-shown-count">{len(p1_hr)}</span> / {len(p1_hr)}건 표시 중</div>'
    )
    for r in p1_hr:
        blocks.append(
            f'<div class="card" data-judgment="{_esc(r["judgment_candidate"])}">'
            f'<div class="hd">{_esc(r["university_name"])} · {_esc(r["department_name"])}</div>'
            f'<div class="meta">{_esc(r["college_name"])} · department_id <code>{_esc(r["department_id"])}</code> · '
            f'공식 소계열 {_esc(r["official_small_series_name"])} · {_esc(r["judgment_candidate"])} · '
            f'근거충분={_esc(r["judgment_evidence_sufficient"])}</div>'
            f'<div class="reason">{_esc(r["proposal_reason"])}</div></div>'
        )

    blocks.append(f"<h2>5. N.C.E 중계열 클러스터(전체 {len(nce_hr)}개 — Hint는 후보일 뿐)</h2>")
    for r in nce_hr:
        dept_list = "".join(
            f'<li>{_esc(m["university_name"])} · {_esc(m["department_name"])}</li>' for m in r["member_departments"]
        )
        candidates = ", ".join(f'{c["canonical_major_id"]}({c["label"]})' for c in r["candidate_canonical_major_groups"])
        blocks.append(
            f'<div class="card"><div class="hd">{_esc(r["official_middle_series_code"])} '
            f'{_esc(r["official_middle_series_name"])} — 소속 학과 {r["member_department_count"]}건</div>'
            f'<div class="meta">group_linkage_status={_esc(r["group_linkage_status"])} · 후보 Group: {_esc(candidates) or "(없음)"}</div>'
            f'<div class="reason">{_esc(r["proposal_reason"])}</div>'
            f'<ul class="dept-list">{dept_list}</ul></div>'
        )

    return (
        '<meta charset="utf-8"><title>Final Mapping Closure — Priority Review</title>'
        f"<style>{_CSS}</style>{''.join(blocks)}<script>{_JS}</script>"
    )


# ============================== Markdown 보고서 ==============================


def render_markdown_report(summary: dict[str, Any], regenerate_cmd: str) -> str:
    lines: list[str] = [
        "# Final Mapping Closure — 최종 검수 대상 축소",
        "",
        "**이 문서는 계산 결과 보고서다.** `data/reviews/`·`data/master/departments.jsonl`·"
        "공개 API는 이 실행으로 전혀 바뀌지 않았다. `auto_approved_rows`는 항상 0이다.",
        "",
        "## 0. 시작 시 미검수·차단 상태",
        "",
    ]
    b = summary["baseline_before_this_packet"]
    lines.append(f"- Group 검수 파일 존재: {b['group_review_file_exists']}(42개 전부 미검수)")
    lines.append(
        f"- Bridge Mapping 기존 검수: APPROVE {b['bridge_mapping_review']['approve']} / "
        f"REVISE {b['bridge_mapping_review']['revise']}(§4 보존)"
    )
    lines.append(f"- Bridge Scope 검수 파일 존재: {b['bridge_scope_review_file_exists']}")
    lines.append(f"- P1 검수 파일 존재: {b['p1_review_file_exists']}")
    lines.append(f"- N.C.E 검수 파일 존재: {b['nce_review_file_exists']}")
    lines.append("")

    lines += ["## 1. 분류 단위 안내", "", summary["unit_note"], "", "## 2. 카테고리별 세부 개수", ""]
    lines.append("| 카테고리 | 전체 | PROPOSE_APPROVE | PROPOSE_EXCLUDE | HUMAN_REVIEW_REQUIRED |")
    lines.append("|---|---:|---:|---:|---:|")
    cat = summary["by_category"]
    lines.append(f"| Group | {cat['group']['total']} | {cat['group']['PROPOSE_APPROVE']} | {cat['group']['PROPOSE_EXCLUDE']} | {cat['group']['HUMAN_REVIEW_REQUIRED']} |")
    lines.append(f"| Bridge Mapping | {cat['bridge_mapping']['total']} | {cat['bridge_mapping']['PROPOSE_APPROVE']} | {cat['bridge_mapping']['PROPOSE_EXCLUDE']} | {cat['bridge_mapping']['HUMAN_REVIEW_REQUIRED']} |")
    lines.append(
        f"| Bridge Scope(적용 {cat['bridge_scope']['applicable']}/전체 {cat['bridge_scope']['total_rows_in_draft']}, "
        f"미적용 {cat['bridge_scope']['not_applicable']}) | {cat['bridge_scope']['applicable']} | "
        f"{cat['bridge_scope']['PROPOSE_APPROVE']} | {cat['bridge_scope']['PROPOSE_EXCLUDE']} | {cat['bridge_scope']['HUMAN_REVIEW_REQUIRED']} |"
    )
    lines.append(f"| P1 | {cat['p1']['total']} | {cat['p1']['PROPOSE_APPROVE']} | {cat['p1']['PROPOSE_EXCLUDE']} | {cat['p1']['HUMAN_REVIEW_REQUIRED']} |")
    lines.append(f"| N.C.E 클러스터 | {cat['nce_cluster']['total']} | {cat['nce_cluster']['PROPOSE_APPROVE']} | {cat['nce_cluster']['PROPOSE_EXCLUDE']} | {cat['nce_cluster']['HUMAN_REVIEW_REQUIRED']} |")
    lines.append(
        f"| N.C.E 학과(세부, 584건) | {cat['nce_department']['total']} | PROPOSED_GROUP_CANDIDATE "
        f"{cat['nce_department']['PROPOSED_GROUP_CANDIDATE']} | DEPARTMENT_LEVEL_REVIEW_REQUIRED "
        f"{cat['nce_department']['DEPARTMENT_LEVEL_REVIEW_REQUIRED']} | (클러스터 단위로 전부 HUMAN_REVIEW_REQUIRED) |"
    )

    t = summary["totals"]
    lines += [
        "",
        "## 3. 합계",
        "",
        f"- PROPOSE_APPROVE 총 {t['propose_approve_total']}건",
        f"- PROPOSE_EXCLUDE 총 {t['propose_exclude_total']}건",
        f"- HUMAN_REVIEW_REQUIRED 총 {t['human_review_required_total']}건(Priority HTML에 전부 수록)",
        f"- auto_approved_rows = {summary['auto_approved_rows']}",
        "",
        "## 4. 예상 READY_FOR_PROMOTION(가정 계산)",
        "",
    ]
    exp = summary["expected_ready_for_promotion"]
    if exp.get("computed"):
        lines.append(f"- 평가 대상 {exp['evaluated_department_count']}건 중 READY_FOR_PROMOTION 예상 **{exp['ready_for_promotion_count']}건**")
        lines.append(f"- BLOCKED 예상 {exp['blocked_count']}건")
        lines.append("")
        lines.append("| 차단 사유 | 예상 잔존 건수 |")
        lines.append("|---|---:|")
        for reason, count in exp["blocked_reason_counts"].items():
            lines.append(f"| {reason} | {count} |")
        lines.append("")
        lines.append(exp["note"])
    else:
        lines.append(f"- 계산 안 함: {exp['reason']}")

    lines += ["", "## 5. 검수가 끝나도 구조적으로 차단되는 사유(영구 구조적)", ""]
    perm = summary["permanently_structural_blocked_reason_counts"]
    if perm:
        lines.append("| 사유 | 건수 |")
        lines.append("|---|---:|")
        for reason, count in perm.items():
            lines.append(f"| {reason} | {count} |")
    else:
        lines.append("- (계산 안 됨 — §4 참고)" if not exp.get("computed") else "- 없음")

    lines += ["", "## 재생성 명령", "", "```", regenerate_cmd, "```"]
    return "\n".join(lines) + "\n"


# ============================== main ==============================


def main(argv: list[str] | None = None) -> int:
    use_utf8_stdout()
    parser = argparse.ArgumentParser(description="Final Mapping Closure — 최종 검수 대상 축소 패킷 생성")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "evaluation")
    parser.add_argument(
        "--restore-normalized-path", type=Path, default=None,
        help="실제 전국 departments.normalized.jsonl 경로(선택 — 없으면 예상 READY_FOR_PROMOTION은 계산하지 않는다)",
    )
    parser.add_argument(
        "--restore-classification-path", type=Path, default=None,
        help="실제 전국 classification_results.jsonl 경로(선택)",
    )
    args = parser.parse_args(argv)

    group_rows = classify_groups()
    mapping_rows, scope_rows = classify_bridge(
        mapping_review_path=ROOT / "data" / "reviews" / "canonical_major_group_bridge_review_status.json",
        scope_review_path=ROOT / "data" / "reviews" / "canonical_major_group_bridge_scope_review_status.jsonl",
    )
    verify_preserved_bridge_scope_decisions(scope_rows)
    verify_preserved_bridge_mapping_review(mapping_rows)
    p1_rows = classify_p1()
    nce_rows = classify_nce()

    hypothetical = compute_hypothetical_ready_for_promotion(
        group_rows=group_rows, scope_rows=scope_rows, p1_rows=p1_rows,
        restore_normalized_path=args.restore_normalized_path,
        restore_classification_path=args.restore_classification_path,
    )

    bridge_mapping_review_baseline = {
        "approve": sum(1 for r in mapping_rows if r["existing_reviewer_1_status"] == "APPROVE"),
        "revise": sum(1 for r in mapping_rows if r["existing_reviewer_1_status"] == "REVISE"),
    }
    summary = build_summary(
        group_rows=group_rows, mapping_rows=mapping_rows, scope_rows=scope_rows, p1_rows=p1_rows, nce_rows=nce_rows,
        hypothetical=hypothetical,
        bridge_mapping_review_baseline=bridge_mapping_review_baseline,
        group_review_file_exists=(ROOT / "data" / "reviews" / "canonical_major_group_review_status.jsonl").exists(),
        bridge_scope_review_file_exists=(ROOT / "data" / "reviews" / "canonical_major_group_bridge_scope_review_status.jsonl").exists(),
        p1_review_file_exists=(ROOT / "data" / "reviews" / "academyinfo_p1_classification_review_status.jsonl").exists(),
        nce_review_file_exists=(ROOT / "data" / "reviews" / "academyinfo_nce_middle_series_review_status.jsonl").exists(),
    )

    summary_path = args.output_dir / "final_mapping_closure_summary.json"
    md_path = args.output_dir / "final_mapping_closure_review.md"
    html_path = args.output_dir / "final_mapping_priority_review.html"

    detail = {
        "group": group_rows, "bridge_mapping": mapping_rows, "bridge_scope": scope_rows,
        "p1": p1_rows, "nce_cluster": nce_rows,
    }
    write_json_atomic(summary_path, {**summary, "detail": detail})

    regenerate_cmd = (
        "PYTHONPATH=. ./.venv/bin/python scripts/career_build_final_mapping_closure.py "
        "--restore-normalized-path <departments.normalized.jsonl> "
        "--restore-classification-path <classification_results.jsonl>  # 두 옵션 생략 시 예상 READY_FOR_PROMOTION 계산은 건너뛴다"
    )
    write_text_atomic(md_path, render_markdown_report(summary, regenerate_cmd))
    write_text_atomic(
        html_path,
        render_priority_html(group_rows=group_rows, mapping_rows=mapping_rows, scope_rows=scope_rows, p1_rows=p1_rows, nce_rows=nce_rows),
    )

    print("Final Mapping Closure 생성 완료")
    print(f"  PROPOSE_APPROVE {summary['totals']['propose_approve_total']}건")
    print(f"  PROPOSE_EXCLUDE {summary['totals']['propose_exclude_total']}건")
    print(f"  HUMAN_REVIEW_REQUIRED {summary['totals']['human_review_required_total']}건")
    if hypothetical.get("computed"):
        print(f"  예상 READY_FOR_PROMOTION {hypothetical['ready_for_promotion_count']}건")
    else:
        print(f"  예상 READY_FOR_PROMOTION 계산 안 함: {hypothetical['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
