"""Canonical Major Group Bridge 검수 탭 View 조립 — 2026-08-24 지시서
(a/canonical-major-bridge-review-ui).

`src/services/canonical_major_group_bridge_loader.py::load_canonical_major_group_bridge()`
(A-1이 이미 만든 정본 Loader, Fail-Fast 검증 포함)가 44행을 검증까지 마쳐서
돌려주면, 이 모듈은 그 결과에 세 가지를 조인해서 화면이 바로 쓸 수 있는 View로
바꾼다.

1. Group 라벨(`data/canonical_major_groups.draft.jsonl`)
2. 서비스 Major 라벨(`data/master/canonical_majors.jsonl`)
3. 전국 학과 후보 개수(`data/academyinfo_work/2025/classification_dry_run.json`의
   `departments_per_canonical_group`, Group 라벨로 조인 — Bridge Draft 자체에는
   없는 필드다)

그리고 사람 검수 상태(`data/reviews/canonical_major_group_bridge_review_status.json`,
이 지시서에서 새로 만드는 파일)를 덧붙인다. 이 모듈은 Master Draft를 읽기만 하고
절대 쓰지 않는다 — Runtime Matching·Department 조회 어디에도 연결되지 않는다."""

from __future__ import annotations

import json
from pathlib import Path

from src.engines.canonical_mapper import load_canonical_majors
from src.review_ui.schemas import (
    BridgeReviewListResponse,
    BridgeReviewRowView,
    BridgeReviewSummary,
    QuestionReviewView,
    UpdateReviewResponse,
)
from src.schemas.canonical_major_group_bridge_review import CanonicalMajorGroupBridgeReview, bridge_review_key
from src.schemas.canonical_major_group_bridge_scope_review import CanonicalMajorGroupBridgeScopeReview
from src.services.canonical_major_group_bridge_loader import (
    DEFAULT_BRIDGE_DRAFT_PATH,
    DEFAULT_CANONICAL_MAJORS_PATH,
    DEFAULT_SMALL_SERIES_CODE_TABLE_PATH,
    load_canonical_major_group_bridge,
    load_official_small_series_codes,
)
from src.services.canonical_major_group_bridge_review_store import bridge_review_path as _bridge_review_path
from src.services.canonical_major_group_bridge_review_store import (
    load_bridge_review_entries_by_key,
    save_bridge_review_entries,
)
from src.services.canonical_major_group_bridge_scope_review_store import (
    bridge_scope_review_path as _bridge_scope_review_path,
)
from src.services.canonical_major_group_bridge_scope_review_store import (
    load_bridge_scope_review_entries_by_key,
    save_bridge_scope_review_entries,
)
from src.services.canonical_major_group_draft_loader import (
    DEFAULT_CANONICAL_MAJOR_GROUPS_DRAFT_PATH,
    load_canonical_major_groups_draft,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
# worker-c 산출물(A-2 통합 시 A가 그대로 유지하기로 결정한 2025년도 조사 Dry-Run
# 결과) — Bridge Draft 자체에는 없는 "전국 학과 후보 개수"의 유일한 출처다.
DEFAULT_CLASSIFICATION_DRY_RUN_PATH = (
    _REPO_ROOT / "data" / "academyinfo_work" / "2025" / "classification_dry_run.json"
)

# 2026-08-24 §13 관례(review_service.QUESTION_REVIEW_PATH와 동일) — 모듈 속성으로
# 노출해서, app.py가 매 요청마다 이 이름을 "그때그때" 다시 읽게 한다. 테스트가
# `unittest.mock.patch("src.review_ui.canonical_major_group_bridge_review_service.
# BRIDGE_REVIEW_STATUS_PATH", tmp_path)`로 임시 경로를 주입하면, 실제 data/reviews/
# 파일을 전혀 건드리지 않고 저장 동작을 검증할 수 있다.
BRIDGE_REVIEW_STATUS_PATH = _bridge_review_path()
# 2026-08-24 지시서(a/bridge-scope-final-review-ui) — Scope 검수 상태는 위
# Mapping 검수 상태와 물리적으로 다른 파일에 저장한다(같은 이유로 같은 patch 관례).
BRIDGE_SCOPE_REVIEW_STATUS_PATH = _bridge_scope_review_path()

# Scope 판단이 Group 전체를 그대로 쓰지 않고 실제로 좁힌 두 값 — "우선 검토 카드"
# 판정 기준. 하드코딩된 (group_id, major_id) 목록이 아니라 scope_type 값 자체로
# 판정한다(Migration 스크립트가 REVISE 6건에만 이 두 값을 부여했으므로 결과적으로
# 지금은 정확히 그 6행과 같지만, 이 계산 자체는 그 사실에 의존하지 않는다).
_PRIORITY_SCOPE_TYPES = frozenset({"INCLUDED_SMALL_SERIES_ONLY", "DEPARTMENT_REVIEW_REQUIRED"})


class UnknownBridgeReviewKeyError(ValueError):
    """PATCH 요청의 review_key가 현재 44행 Bridge Draft 어디에도 대응하지 않을 때.
    존재하지 않는 Key로 검수 상태를 새로 만들어 저장하지 않는다 — Draft에 실제로
    있는 행만 검수 대상이다."""


def _department_counts_by_group_label(dry_run_path: Path | None = None) -> dict[str, int]:
    resolved = dry_run_path or DEFAULT_CLASSIFICATION_DRY_RUN_PATH
    if not resolved.exists():
        return {}
    data = json.loads(resolved.read_text(encoding="utf-8"))
    return dict(data.get("departments_per_canonical_group", {}))


def _bridge_row_review_view(entry: CanonicalMajorGroupBridgeReview | None) -> QuestionReviewView:
    entry = entry or CanonicalMajorGroupBridgeReview(canonical_major_group_id="")
    return QuestionReviewView(
        reviewer_1_status=entry.reviewer_1_status, reviewer_1_comment=entry.reviewer_1_comment,
        reviewer_2_status=entry.reviewer_2_status, reviewer_2_comment=entry.reviewer_2_comment,
        final_status=entry.final_status, resolution_note=entry.resolution_note,
    )


def _bridge_row_scope_review_view(entry: CanonicalMajorGroupBridgeScopeReview | None) -> QuestionReviewView:
    """Mapping 검수 View 조립 함수(위)와 나란한 형태지만, 완전히 다른 Store에서 읽은
    값이다 — 이 함수는 `load_bridge_scope_review_entries_by_key()`가 돌려준 값만
    받고, Mapping 검수 store는 아예 import하지 않는다(모듈 상단 import 목록에서
    확인 가능)."""

    entry = entry or CanonicalMajorGroupBridgeScopeReview(canonical_major_group_id="")
    return QuestionReviewView(
        reviewer_1_status=entry.reviewer_1_status, reviewer_1_comment=entry.reviewer_1_comment,
        reviewer_2_status=entry.reviewer_2_status, reviewer_2_comment=entry.reviewer_2_comment,
        final_status=entry.final_status, resolution_note=entry.resolution_note,
    )


def build_bridge_review_list(
    *, bridge_path: Path | None = None, group_draft_path: Path | None = None, majors_path: Path | None = None,
    dry_run_path: Path | None = None, review_status_path: Path | None = None,
    scope_review_status_path: Path | None = None, small_series_code_table_path: Path | None = None,
) -> BridgeReviewListResponse:
    """§2/§4 — 44행 전체를 Group/Major 라벨·전국 학과 후보 개수·Mapping 검수 상태·
    Scope 정보·Scope 검수 상태와 조인해서 돌려주고, 요약 개수는 이 함수가 실제로
    센 값이다(하드코딩 없음). 이 함수는 어떤 파일도 쓰지 않는다 — GET·필터만으로는
    Mapping 검수 파일도 Scope 검수 파일도 절대 생성·수정되지 않는다."""

    report = load_canonical_major_group_bridge(
        bridge_path or DEFAULT_BRIDGE_DRAFT_PATH,
        group_draft_path=group_draft_path or DEFAULT_CANONICAL_MAJOR_GROUPS_DRAFT_PATH,
        majors_path=majors_path or DEFAULT_CANONICAL_MAJORS_PATH,
        small_series_code_table_path=small_series_code_table_path,
    )
    group_labels = {g.canonical_major_id: g.label for g in load_canonical_major_groups_draft(group_draft_path)}
    major_labels = {m.major_id: m.label for m in load_canonical_majors(majors_path or DEFAULT_CANONICAL_MAJORS_PATH)}
    dept_counts = _department_counts_by_group_label(dry_run_path)
    review_by_key = load_bridge_review_entries_by_key(review_status_path)
    scope_review_by_key = load_bridge_scope_review_entries_by_key(scope_review_status_path)
    official_code_names = load_official_small_series_codes(
        small_series_code_table_path or DEFAULT_SMALL_SERIES_CODE_TABLE_PATH
    )

    def _names(codes: list[str]) -> list[str]:
        # Loader가 이미 Fail-Fast로 "158개 공식 코드표에 없는 코드"를 걸렀으므로
        # 여기 도달한 코드는 항상 official_code_names에 있다 — .get() 기본값은
        # 방어적으로만 남긴다(코드 자체를 그대로 보여줘 최소한 뭔가는 보이게).
        return [official_code_names.get(c, c) for c in codes]

    rows: list[BridgeReviewRowView] = []
    for e in report.entries:
        key = bridge_review_key(e.canonical_major_group_id, e.canonical_major_id)
        group_label = group_labels.get(e.canonical_major_group_id, e.canonical_major_group_id)
        rows.append(
            BridgeReviewRowView(
                review_key=key,
                canonical_major_group_id=e.canonical_major_group_id,
                canonical_major_group_label=group_label,
                canonical_major_id=e.canonical_major_id,
                canonical_major_label=major_labels.get(e.canonical_major_id) if e.canonical_major_id else None,
                mapping_status=e.mapping_status,
                evidence=e.evidence,
                decision_reason=e.decision_reason,
                boundary_notes=e.boundary_notes,
                is_boundary_case=bool(e.boundary_notes.strip()),
                national_department_candidate_count=dept_counts.get(group_label),
                review=_bridge_row_review_view(review_by_key.get(key)),
                scope_type=e.scope_type,
                included_small_series_codes=e.included_small_series_codes,
                included_small_series_names=_names(e.included_small_series_codes),
                excluded_small_series_codes=e.excluded_small_series_codes,
                excluded_small_series_names=_names(e.excluded_small_series_codes),
                scope_decision_reason=e.scope_decision_reason,
                is_priority_scope_review=e.scope_type in _PRIORITY_SCOPE_TYPES,
                scope_review=_bridge_row_scope_review_view(scope_review_by_key.get(key)),
            )
        )
    rows.sort(key=lambda r: r.review_key)

    reviewer_statuses = [r.review.reviewer_1_status for r in rows]
    scope_reviewer_statuses = [r.scope_review.reviewer_1_status for r in rows]
    summary = BridgeReviewSummary(
        total=len(rows),
        evidenced_count=sum(1 for r in rows if r.mapping_status == "EVIDENCED"),
        review_required_count=sum(1 for r in rows if r.mapping_status == "REVIEW_REQUIRED"),
        excluded_recommendation_count=sum(1 for r in rows if r.mapping_status == "EXCLUDED_RECOMMENDATION"),
        unmapped_count=sum(1 for r in rows if r.mapping_status == "UNMAPPED"),
        reviewer_tbd_count=reviewer_statuses.count("TBD"),
        reviewer_approve_count=reviewer_statuses.count("APPROVE"),
        reviewer_revise_count=reviewer_statuses.count("REVISE"),
        reviewer_hold_count=reviewer_statuses.count("HOLD"),
        reviewed_count=sum(1 for s in reviewer_statuses if s != "TBD"),
        unreviewed_count=reviewer_statuses.count("TBD"),
        priority_scope_review_count=sum(1 for r in rows if r.is_priority_scope_review),
        scope_reviewer_tbd_count=scope_reviewer_statuses.count("TBD"),
        scope_reviewer_approve_count=scope_reviewer_statuses.count("APPROVE"),
        scope_reviewer_revise_count=scope_reviewer_statuses.count("REVISE"),
        scope_reviewer_hold_count=scope_reviewer_statuses.count("HOLD"),
        scope_reviewed_count=sum(1 for s in scope_reviewer_statuses if s != "TBD"),
        scope_unreviewed_count=scope_reviewer_statuses.count("TBD"),
    )
    return BridgeReviewListResponse(rows=rows, summary=summary)


def update_bridge_review(
    review_key: str, *, status: str | None, comment: str | None, resolution_note: str | None,
    bridge_path: Path | None = None, group_draft_path: Path | None = None, majors_path: Path | None = None,
    review_status_path: Path | None = None,
) -> UpdateReviewResponse:
    """§1/§5 — `review_key`가 실제 44행 중 하나에 대응하는지부터 확인한다(존재하지
    않는 Key로 새 행을 만들지 않는다). `status`/`comment`/`resolution_note`는 전부
    None이면 기존 값을 그대로 두는 부분 저장 규칙을 따른다
    (`update_shared_probe_review`와 동일 원칙, 2.9.1단계 §1-3의 버그 수정을 그대로
    승계) — 이 규칙 덕분에 "필터만 바꿨는데 저장됨" 류의 사고와 별개로, 저장 버튼을
    눌러도 명시적으로 건드리지 않은 필드가 암묵적으로 바뀌지 않는다.

    이 함수는 어떤 인자 조합으로도 스스로 `status`를 "APPROVE"로 정하지 않는다 —
    호출자가 명시적으로 "APPROVE"를 보낸 경우에만 그 값이 저장된다(자동 승인 금지)."""

    report = load_canonical_major_group_bridge(
        bridge_path or DEFAULT_BRIDGE_DRAFT_PATH,
        group_draft_path=group_draft_path or DEFAULT_CANONICAL_MAJOR_GROUPS_DRAFT_PATH,
        majors_path=majors_path or DEFAULT_CANONICAL_MAJORS_PATH,
    )
    valid_keys = {bridge_review_key(e.canonical_major_group_id, e.canonical_major_id) for e in report.entries}
    if review_key not in valid_keys:
        raise UnknownBridgeReviewKeyError(f"review_key {review_key!r}가 현재 Bridge Draft 44행 중 어디에도 없다")

    entry_by_group_major = {
        bridge_review_key(e.canonical_major_group_id, e.canonical_major_id): e for e in report.entries
    }
    draft_entry = entry_by_group_major[review_key]

    by_key = load_bridge_review_entries_by_key(review_status_path)
    existing = by_key.get(review_key) or CanonicalMajorGroupBridgeReview(
        canonical_major_group_id=draft_entry.canonical_major_group_id,
        canonical_major_id=draft_entry.canonical_major_id,
    )

    merged = existing.model_dump()
    if status is not None:
        merged["reviewer_1_status"] = status
    if comment is not None:
        merged["reviewer_1_comment"] = comment
    if resolution_note is not None:
        merged["resolution_note"] = resolution_note
    merged["revision"] = str(int(existing.revision) + 1 if existing.revision.isdigit() else 1)

    updated = CanonicalMajorGroupBridgeReview.model_validate(merged)
    by_key[review_key] = updated
    save_bridge_review_entries([by_key[k] for k in sorted(by_key)], review_status_path)
    return UpdateReviewResponse(ok=True, final_status=updated.final_status, new_revision=updated.revision)


def update_bridge_scope_review(
    review_key: str, *, status: str | None, comment: str | None, resolution_note: str | None,
    bridge_path: Path | None = None, group_draft_path: Path | None = None, majors_path: Path | None = None,
    scope_review_status_path: Path | None = None,
) -> UpdateReviewResponse:
    """2026-08-24 지시서(a/bridge-scope-final-review-ui) §2 — `update_bridge_review()`
    와 같은 형태의 함수지만, 완전히 다른 파일(Scope 검수 Store)에만 쓴다. 이 함수는
    Mapping 검수 Store(`canonical_major_group_bridge_review_store`)를 import하지도
    않는다 — "Scope APPROVE가 Mapping 상태를 바꾸면 안 됨"을 코드 경로 자체로
    보장한다(실수로 같은 파일을 두 번 쓸 방법이 없다).

    `review_key`가 현재 44행 중 하나에 대응하는지 확인하는 로직, None="변경 없음"
    부분 저장 규칙, "호출자가 명시적으로 APPROVE를 보낸 경우에만 저장" 원칙은
    `update_bridge_review()`와 동일하게 유지한다."""

    report = load_canonical_major_group_bridge(
        bridge_path or DEFAULT_BRIDGE_DRAFT_PATH,
        group_draft_path=group_draft_path or DEFAULT_CANONICAL_MAJOR_GROUPS_DRAFT_PATH,
        majors_path=majors_path or DEFAULT_CANONICAL_MAJORS_PATH,
    )
    valid_keys = {bridge_review_key(e.canonical_major_group_id, e.canonical_major_id) for e in report.entries}
    if review_key not in valid_keys:
        raise UnknownBridgeReviewKeyError(f"review_key {review_key!r}가 현재 Bridge Draft 44행 중 어디에도 없다")

    entry_by_group_major = {
        bridge_review_key(e.canonical_major_group_id, e.canonical_major_id): e for e in report.entries
    }
    draft_entry = entry_by_group_major[review_key]

    by_key = load_bridge_scope_review_entries_by_key(scope_review_status_path)
    existing = by_key.get(review_key) or CanonicalMajorGroupBridgeScopeReview(
        canonical_major_group_id=draft_entry.canonical_major_group_id,
        canonical_major_id=draft_entry.canonical_major_id,
    )

    merged = existing.model_dump()
    if status is not None:
        merged["reviewer_1_status"] = status
    if comment is not None:
        merged["reviewer_1_comment"] = comment
    if resolution_note is not None:
        merged["resolution_note"] = resolution_note
    merged["revision"] = str(int(existing.revision) + 1 if existing.revision.isdigit() else 1)

    updated = CanonicalMajorGroupBridgeScopeReview.model_validate(merged)
    by_key[review_key] = updated
    save_bridge_scope_review_entries([by_key[k] for k in sorted(by_key)], scope_review_status_path)
    return UpdateReviewResponse(ok=True, final_status=updated.final_status, new_revision=updated.revision)
