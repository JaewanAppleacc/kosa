"""Final Mapping Review 일괄 종결 — 2026-08 지시서 (a/final-mapping-review-closeout).

사용자가 최종 결정을 이미 내렸고("모든 Mapping 검수를 이번 라운드에서 종결한다.
별도의 Priority 검수 패킷이나 추가 사람 검수는 만들지 않는다"), 이 스크립트는 그
결정을 기존 Review UI Store·Schema를 통해서만 기계적으로 기록한다. 새 검수 축을
만들지 않고, Draft·Master·Runtime·공개 API·Mock 어디도 건드리지 않는다 — 아래 5개
Store만 쓴다:

    src.review_ui.canonical_major_group_review_service.update_canonical_major_group_review
    src.review_ui.canonical_major_group_bridge_review_service.update_bridge_review
    src.review_ui.canonical_major_group_bridge_review_service.update_bridge_scope_review
    src.review_ui.academyinfo_p1_classification_review_service.update_p1_classification_review
    src.review_ui.academyinfo_nce_middle_series_review_service.update_nce_middle_series_review

**"승인"의 의미** — 지시서 원문 그대로: Group 승인은 "42개 분류 Ontology로 계속
쓸 수 있다"는 뜻만 갖고, 서비스 추천 노출·전국 자동 승격·예체능 추천 허용·Bridge
Mapping/Scope 승인 중 어느 것도 의미하지 않는다(그 넷은 물리적으로 다른 파일에
있다 — Group Review Schema의 모듈 docstring이 이미 이 사실을 명시한다).

**P1/N.C.E 결정 값 — 지시서 원문과 실제 Schema의 차이를 그대로 밝힌다.** 지시서는
"EXCLUDE_ARTS_SPORTS"/"EXCLUDE_FROM_INITIAL_PROMOTION"이라는 표현을 쓰지만, 실제
`P1ReviewDecision`/`NceMiddleSeriesDecision` Literal에는 그 정확한 문자열이 없다
(각각 EXCLUDE_ARTS_RECOMMENDATION, KEEP_UNMAPPED/NEEDS_OFFICIAL_CURRICULUM/
REQUIRE_DEPARTMENT_LEVEL_REVIEW/INSUFFICIENT_OFFICIAL_EVIDENCE로 나뉜다). 지시서
§4/§5도 "해당 Schema의 제외 결정 사용"이라고 명시적으로 허용한다 — 이 스크립트는
실제 Schema에 있는 값 중 지시서의 의도와 가장 정확히 대응하는 값을 쓴다(아래
`_p1_decision_for`/`_nce_decision_for`에 대응표를 그대로 문서화했다). "
EXCLUDE_FROM_INITIAL_PROMOTION"은 어느 Schema에도 없는 문자열이므로 실제 Review
파일에는 쓰지 않는다 — 대신 8절 Dry Run 보고서에서 "이 결정을 받은 행은 이번
라운드 전국 승격에서 제외된다"는 결과를 그 이름 그대로 보고한다(결정 값이 아니라
결과 분류로).

멱등이다 — 이미 목표 상태(decision/status/resolution_note)와 완전히 같은 행은
건드리지 않는다(다시 실행해도 revision이 불필요하게 늘지 않는다). 이미 다른 값이
있는 행은 그 값이 무엇이든 목표 상태로 덮어쓴다(사용자가 "이번 라운드에서 종결"을
명시했으므로)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.majors.canonical_major_descriptions import CANONICAL_MAJOR_DESCRIPTIONS_BY_ID  # noqa: E402
from src.review_ui.academyinfo_nce_middle_series_review_service import (  # noqa: E402
    update_nce_middle_series_review,
)
from src.review_ui.academyinfo_p1_classification_review_service import (  # noqa: E402
    p1_approve_eligible,
    update_p1_classification_review,
)
from src.review_ui.canonical_major_group_bridge_review_service import (  # noqa: E402
    update_bridge_review,
    update_bridge_scope_review,
)
from src.review_ui.canonical_major_group_review_service import (  # noqa: E402
    update_canonical_major_group_review,
)
from src.schemas.canonical_major_group_bridge_review import bridge_review_key  # noqa: E402
from src.services.academyinfo_nce_middle_series_cluster_loader import (  # noqa: E402
    DEFAULT_NCE_CLUSTER_PATH,
    load_nce_middle_series_clusters,
)
from src.services.academyinfo_p1_classification_loader import (  # noqa: E402
    DEFAULT_P1_PACKET_PATH,
    load_p1_classification_packet,
)
from src.services.academyinfo_nce_middle_series_review_store import (  # noqa: E402
    load_nce_review_entries_by_key,
)
from src.services.academyinfo_p1_classification_review_store import (  # noqa: E402
    load_p1_review_entries_by_key,
)
from src.services.canonical_major_group_bridge_loader import (  # noqa: E402
    DEFAULT_BRIDGE_DRAFT_PATH,
    DEFAULT_CANONICAL_MAJORS_PATH,
    load_canonical_major_group_bridge,
)
from src.services.canonical_major_group_bridge_review_store import (  # noqa: E402
    load_bridge_review_entries_by_key,
)
from src.services.canonical_major_group_bridge_scope_review_store import (  # noqa: E402
    load_bridge_scope_review_entries_by_key,
)
from src.services.canonical_major_group_draft_loader import (  # noqa: E402
    DEFAULT_CANONICAL_MAJOR_GROUPS_DRAFT_PATH,
    load_canonical_major_groups_draft,
)
from src.services.canonical_major_group_review_store import (  # noqa: E402
    load_canonical_major_group_review_entries_by_key,
)

RESOLUTION_NOTE = "사용자 최종 일괄 검수 결정에 따라 기존 근거·범위 결정을 승인"


class ClosureResult(dict):
    """영역 하나(Group/Bridge Mapping/Bridge Scope/P1/N.C.E)의 최종 집계."""


def _apply_group_closure(*, group_draft_path=None, review_status_path=None) -> ClosureResult:
    """§1 — 42개 Group 전부 decision=APPROVE_AS_CLASSIFICATION_GROUP(예체능 4개
    포함 — 분류 Ontology 승인과 추천 노출은 별개 축이라는 지시서 원문 그대로).
    `update_canonical_major_group_review`가 reviewer_1_status를 자동으로 APPROVE와
    맞춰 저장한다(Schema의 model_validator가 강제)."""

    groups = load_canonical_major_groups_draft(group_draft_path or DEFAULT_CANONICAL_MAJOR_GROUPS_DRAFT_PATH)
    by_key = load_canonical_major_group_review_entries_by_key(review_status_path)

    updated, skipped = 0, 0
    for g in groups:
        existing = by_key.get(g.canonical_major_id)
        already_done = (
            existing is not None
            and existing.decision == "APPROVE_AS_CLASSIFICATION_GROUP"
            and existing.resolution_note == RESOLUTION_NOTE
        )
        if already_done:
            skipped += 1
            continue
        expected_revision = existing.revision if existing is not None else 0
        update_canonical_major_group_review(
            g.canonical_major_id, decision="APPROVE_AS_CLASSIFICATION_GROUP", comment=None,
            resolution_note=RESOLUTION_NOTE, expected_revision=expected_revision,
            group_draft_path=group_draft_path, review_status_path=review_status_path,
        )
        updated += 1

    final_by_key = load_canonical_major_group_review_entries_by_key(review_status_path)
    decisions = [e.decision for e in final_by_key.values()]
    return ClosureResult(
        total=len(groups), updated_this_run=updated, unchanged_this_run=skipped,
        approve_count=decisions.count("APPROVE_AS_CLASSIFICATION_GROUP"),
        tbd_count=decisions.count("TBD"),
        hold_count=decisions.count("HOLD"),
        revise_bucket_count=sum(
            1 for d in decisions
            if d in ("REVISE_GROUP_DEFINITION", "SPLIT_GROUP", "MERGE_WITH_OTHER_GROUP", "EXCLUDE_FROM_CLASSIFICATION")
        ),
    )


# §2 REVISE 6건의 최종 Scope(이미 career_add_canonical_major_group_bridge_scope.py가
# Draft에 심어둔 값과 정확히 같다 — 이 스크립트는 Draft를 다시 쓰지 않고, 그 6건의
# Mapping 검수만 REVISE에서 완료로 넘긴다). 키는 bridge_review_key(group_id, major_id).
_REVISE_SIX_GROUP_MAJOR: tuple[tuple[str, str], ...] = (
    ("business", "business_administration"),
    ("education", "education"),
    ("industrial_engineering", "industrial_engineering"),
    ("mechanical_transport", "mechanical_engineering"),
    ("bio_medical_engineering", "life_science"),
    ("computer_science", "hci_ux"),
)


def _apply_bridge_mapping_closure(*, bridge_path=None, group_draft_path=None, majors_path=None, review_status_path=None) -> ClosureResult:
    """§2 — 기존 APPROVE 38개는 절대 건드리지 않는다(재저장하지 않음 — revision도
    코멘트도 그대로 남는다). REVISE 6개만 APPROVE로 완료 처리한다(Scope 결정이
    이미 반영됐으므로) — reviewer_1_comment(기존 REVISE 사유 코멘트)는 그대로
    보존하고 resolution_note만 채운다."""

    report = load_canonical_major_group_bridge(
        bridge_path or DEFAULT_BRIDGE_DRAFT_PATH, group_draft_path=group_draft_path, majors_path=majors_path or DEFAULT_CANONICAL_MAJORS_PATH,
    )
    valid_keys = {bridge_review_key(e.canonical_major_group_id, e.canonical_major_id) for e in report.entries}
    by_key = load_bridge_review_entries_by_key(review_status_path)

    updated, skipped = 0, 0
    for group_id, major_id in _REVISE_SIX_GROUP_MAJOR:
        key = bridge_review_key(group_id, major_id)
        if key not in valid_keys:
            raise RuntimeError(f"REVISE 6건 목록의 Key {key!r}가 현재 44행 Bridge Draft에 없다 — 지시서 §2와 실제 데이터가 어긋난다")
        existing = by_key.get(key)
        already_done = existing is not None and existing.reviewer_1_status == "APPROVE" and existing.resolution_note == RESOLUTION_NOTE
        if already_done:
            skipped += 1
            continue
        update_bridge_review(
            key, status="APPROVE", comment=None, resolution_note=RESOLUTION_NOTE,
            bridge_path=bridge_path, group_draft_path=group_draft_path, majors_path=majors_path,
            review_status_path=review_status_path,
        )
        updated += 1

    final_by_key = load_bridge_review_entries_by_key(review_status_path)
    statuses = [e.reviewer_1_status for e in final_by_key.values()]
    return ClosureResult(
        total=len(valid_keys), reviewed_row_count=len(final_by_key),
        updated_this_run=updated, unchanged_this_run=skipped,
        approve_count=statuses.count("APPROVE"), tbd_count=len(valid_keys) - len(final_by_key) + statuses.count("TBD"),
        revise_count=statuses.count("REVISE"), hold_count=statuses.count("HOLD"),
    )


def _apply_bridge_scope_closure(*, bridge_path=None, group_draft_path=None, majors_path=None, scope_review_status_path=None) -> ClosureResult:
    """§3 — 44행 전부 reviewer_1 APPROVE(Scope *유형 자체*의 승인). Mapping 검수
    Store는 이 함수가 아예 import하지 않는다(위 import 목록 확인) — 실수로 같은
    파일을 두 번 쓸 방법이 없다."""

    report = load_canonical_major_group_bridge(
        bridge_path or DEFAULT_BRIDGE_DRAFT_PATH, group_draft_path=group_draft_path, majors_path=majors_path or DEFAULT_CANONICAL_MAJORS_PATH,
    )
    all_keys = [bridge_review_key(e.canonical_major_group_id, e.canonical_major_id) for e in report.entries]
    by_key = load_bridge_scope_review_entries_by_key(scope_review_status_path)

    updated, skipped = 0, 0
    for key in all_keys:
        existing = by_key.get(key)
        already_done = existing is not None and existing.reviewer_1_status == "APPROVE" and existing.resolution_note == RESOLUTION_NOTE
        if already_done:
            skipped += 1
            continue
        update_bridge_scope_review(
            key, status="APPROVE", comment=None, resolution_note=RESOLUTION_NOTE,
            bridge_path=bridge_path, group_draft_path=group_draft_path, majors_path=majors_path,
            scope_review_status_path=scope_review_status_path,
        )
        updated += 1

    final_by_key = load_bridge_scope_review_entries_by_key(scope_review_status_path)
    statuses = [e.reviewer_1_status for e in final_by_key.values()]
    scope_type_by_key = {
        bridge_review_key(e.canonical_major_group_id, e.canonical_major_id): e.scope_type for e in report.entries
    }
    return ClosureResult(
        total=len(all_keys), updated_this_run=updated, unchanged_this_run=skipped,
        approve_count=statuses.count("APPROVE"), tbd_count=len(all_keys) - len(final_by_key) + statuses.count("TBD"),
        scope_type_breakdown={
            scope_type: sum(1 for k in all_keys if scope_type_by_key.get(k) == scope_type)
            for scope_type in sorted({v for v in scope_type_by_key.values()}, key=lambda v: v or "")
        },
    )


def _p1_decision_for(entry: Any, service_major_ids: frozenset[str]) -> str:
    """§4 대응표(지시서 원문 → 실제 P1ReviewDecision):
        후보 정확히 1개 + 공식 근거 충분 + 서비스 Major 10개 중 하나 (p1_approve_eligible,
            src/review_ui/academyinfo_p1_classification_review_service.py가 이미 이
            조건을 구현한 실제 함수 — 재구현하지 않고 그대로 재사용한다)
            → APPROVE_PROPOSED_CANDIDATE
        judgment_candidate == DESIGN_ARTS_EXCLUDED(예체능으로 명확)
            → EXCLUDE_ARTS_RECOMMENDATION(지시서의 "EXCLUDE_ARTS_SPORTS"에 대응하는
              실제 Schema 값 — 그 정확한 문자열은 Schema에 없다)
        후보 없음(candidate_canonical_major_ids == [])
            → KEEP_UNMAPPED(지시서의 "후보 없음" 케이스)
        그 외(후보는 있지만 근거 불충분·서비스 Major 아님 등 APPROVE 조건 미충족)
            → NEEDS_OFFICIAL_CURRICULUM(지시서의 "공식 근거 부족" 케이스)"""

    if entry.judgment_candidate == "DESIGN_ARTS_EXCLUDED":
        return "EXCLUDE_ARTS_RECOMMENDATION"
    if p1_approve_eligible(entry, service_major_ids):
        return "APPROVE_PROPOSED_CANDIDATE"
    if len(entry.candidate_canonical_major_ids) == 0:
        return "KEEP_UNMAPPED"
    return "NEEDS_OFFICIAL_CURRICULUM"


def _apply_p1_closure(*, packet_path=None, review_status_path=None) -> ClosureResult:
    service_major_ids = frozenset(CANONICAL_MAJOR_DESCRIPTIONS_BY_ID)
    entries = load_p1_classification_packet(packet_path or DEFAULT_P1_PACKET_PATH)
    by_key = load_p1_review_entries_by_key(review_status_path)

    updated, skipped = 0, 0
    for entry in entries:
        target_decision = _p1_decision_for(entry, service_major_ids)
        existing = by_key.get(entry.candidate_id)
        already_done = existing is not None and existing.decision == target_decision and existing.resolution_note == RESOLUTION_NOTE
        if already_done:
            skipped += 1
            continue
        expected_revision = existing.revision if existing is not None else 0
        update_p1_classification_review(
            entry.candidate_id, decision=target_decision, comment=None, resolution_note=RESOLUTION_NOTE,
            expected_revision=expected_revision, packet_path=packet_path, review_status_path=review_status_path,
        )
        updated += 1

    final_by_key = load_p1_review_entries_by_key(review_status_path)
    decisions = [e.decision for e in final_by_key.values()]
    return ClosureResult(
        total=len(entries), updated_this_run=updated, unchanged_this_run=skipped,
        tbd_count=len(entries) - len(final_by_key) + decisions.count("TBD"),
        approve_count=decisions.count("APPROVE_PROPOSED_CANDIDATE"),
        exclude_arts_count=decisions.count("EXCLUDE_ARTS_RECOMMENDATION"),
        keep_unmapped_count=decisions.count("KEEP_UNMAPPED"),
        needs_official_curriculum_count=decisions.count("NEEDS_OFFICIAL_CURRICULUM"),
        revise_candidate_count=decisions.count("REVISE_CANDIDATE"),
        hold_count=decisions.count("HOLD"),
        excluded_from_initial_promotion_count=sum(
            1 for d in decisions if d != "APPROVE_PROPOSED_CANDIDATE"
        ),
    )


def _nce_decision_for(cluster: Any) -> str:
    """§5 대응표(지시서 원문 → 실제 NceMiddleSeriesDecision):
        group_linkage_status == PROPOSED_GROUP_CANDIDATE and 후보 Group 정확히 1개
            → ACCEPT_GROUP_AS_REVIEW_CANDIDATE
        복수 후보 또는 학과 단위 판단 필요(group_linkage_status ==
            DEPARTMENT_LEVEL_REVIEW_REQUIRED)
            → REQUIRE_DEPARTMENT_LEVEL_REVIEW(지시서의 "EXCLUDE_FROM_INITIAL_
              PROMOTION"에 대응하는 실제 Schema 값 — 그 정확한 문자열은 Schema에
              없고, 이 값이 지시서가 말한 "학과 단위 판단이 필요했던 항목"과
              정확히 같은 뜻이다)
        후보 자체가 없음(candidate_canonical_major_groups == [])
            → INSUFFICIENT_OFFICIAL_EVIDENCE(실측 24개 클러스터 중 해당 없음 —
              방어적으로만 남겨둔다)"""

    if not cluster.candidate_canonical_major_groups:
        return "INSUFFICIENT_OFFICIAL_EVIDENCE"
    if cluster.group_linkage_status == "PROPOSED_GROUP_CANDIDATE" and len(cluster.candidate_canonical_major_groups) == 1:
        return "ACCEPT_GROUP_AS_REVIEW_CANDIDATE"
    return "REQUIRE_DEPARTMENT_LEVEL_REVIEW"


def _apply_nce_closure(*, cluster_path=None, review_status_path=None) -> ClosureResult:
    clusters = load_nce_middle_series_clusters(cluster_path or DEFAULT_NCE_CLUSTER_PATH)
    by_key = load_nce_review_entries_by_key(review_status_path)

    updated, skipped = 0, 0
    for cluster in clusters:
        target_decision = _nce_decision_for(cluster)
        existing = by_key.get(cluster.official_middle_series_code)
        already_done = existing is not None and existing.decision == target_decision and existing.resolution_note == RESOLUTION_NOTE
        if already_done:
            skipped += 1
            continue
        expected_revision = existing.revision if existing is not None else 0
        update_nce_middle_series_review(
            cluster.official_middle_series_code, decision=target_decision, comment=None, resolution_note=RESOLUTION_NOTE,
            expected_revision=expected_revision, cluster_path=cluster_path, review_status_path=review_status_path,
        )
        updated += 1

    final_by_key = load_nce_review_entries_by_key(review_status_path)
    decisions = [e.decision for e in final_by_key.values()]
    member_total_by_decision: dict[str, int] = {}
    for cluster in clusters:
        d = final_by_key[cluster.official_middle_series_code].decision
        member_total_by_decision[d] = member_total_by_decision.get(d, 0) + cluster.row_count
    return ClosureResult(
        total=len(clusters), updated_this_run=updated, unchanged_this_run=skipped,
        tbd_count=len(clusters) - len(final_by_key) + decisions.count("TBD"),
        accept_as_candidate_count=decisions.count("ACCEPT_GROUP_AS_REVIEW_CANDIDATE"),
        require_department_review_count=decisions.count("REQUIRE_DEPARTMENT_LEVEL_REVIEW"),
        insufficient_evidence_count=decisions.count("INSUFFICIENT_OFFICIAL_EVIDENCE"),
        hold_count=decisions.count("HOLD"),
        member_department_total_by_decision=member_total_by_decision,
    )


def run_closeout(*, review_root: Path | None = None) -> dict[str, ClosureResult]:
    """다섯 영역을 순서대로 종결한다. `review_root`를 주면(테스트 전용) 그 디렉터리
    아래 5개 검수 파일에만 쓴다 — 실제 `data/reviews/`는 손대지 않는다. 프로덕션
    실행(`review_root=None`)은 실제 `data/reviews/` 경로를 그대로 쓴다 — 이번
    작업의 목적 자체가 그 파일들을 최종 상태로 채우는 것이기 때문이다."""

    if review_root is None:
        group_review_path = None
        bridge_review_path = None
        bridge_scope_review_path = None
        p1_review_path = None
        nce_review_path = None
    else:
        group_review_path = review_root / "canonical_major_group_review_status.jsonl"
        bridge_review_path = review_root / "canonical_major_group_bridge_review_status.json"
        bridge_scope_review_path = review_root / "canonical_major_group_bridge_scope_review_status.jsonl"
        p1_review_path = review_root / "academyinfo_p1_classification_review_status.jsonl"
        nce_review_path = review_root / "academyinfo_nce_middle_series_review_status.jsonl"

    return {
        "canonical_major_group": _apply_group_closure(review_status_path=group_review_path),
        "bridge_mapping": _apply_bridge_mapping_closure(review_status_path=bridge_review_path),
        "bridge_scope": _apply_bridge_scope_closure(scope_review_status_path=bridge_scope_review_path),
        "p1_classification": _apply_p1_closure(review_status_path=p1_review_path),
        "nce_middle_series": _apply_nce_closure(review_status_path=nce_review_path),
    }


def main() -> None:
    results = run_closeout()
    for area, result in results.items():
        print(f"=== {area} ===")
        for k, v in result.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
