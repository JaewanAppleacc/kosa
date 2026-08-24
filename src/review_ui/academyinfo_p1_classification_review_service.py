"""대학알리미 P1 분류 REVIEW 검수 탭 View 조립 — 2026-08-24 지시서
(a/academyinfo-review-ui-p1-nce) §1.

`academyinfo_p1_classification_loader.load_p1_classification_packet()`(374행,
Fail-Fast 검증 포함)가 돌려주면, 이 모듈은 그 결과에 사람 검수 상태
(`data/reviews/academyinfo_p1_classification_review_status.jsonl`)를 조인해서
화면이 바로 쓸 수 있는 View로 바꾼다. Draft 패킷도 검수 파일도 GET 경로에서는
절대 쓰지 않는다."""

from __future__ import annotations

from pathlib import Path

from src.data.majors.canonical_major_descriptions import CANONICAL_MAJOR_DESCRIPTIONS_BY_ID
from src.review_ui.schemas import (
    P1ClassificationListResponse,
    P1ClassificationRowView,
    P1ClassificationSummary,
    P1ReviewView,
    UpdateP1ClassificationReviewResponse,
)
from src.schemas.academyinfo_p1_classification_candidate_review import AcademyInfoP1ClassificationReview
from src.services.academyinfo_p1_classification_loader import (
    DEFAULT_P1_PACKET_PATH,
    load_p1_classification_packet,
)
from src.services.academyinfo_p1_classification_review_store import (
    p1_review_path as _p1_review_path,
)
from src.services.academyinfo_p1_classification_review_store import (
    load_p1_review_entries_by_key,
    save_p1_review_entries,
)

# 2026-08-24 관례(canonical_major_group_bridge_review_service.BRIDGE_REVIEW_STATUS_PATH
# 와 동일) — 모듈 속성으로 노출해서 app.py가 매 요청마다 다시 읽게 한다. 테스트가
# `unittest.mock.patch(..., "P1_REVIEW_STATUS_PATH", tmp_path)`로 임시 경로를
# 주입하면 실제 data/reviews/ 파일을 전혀 건드리지 않고 검증할 수 있다.
P1_REVIEW_STATUS_PATH = _p1_review_path()

# 서비스 추천 10개 Major의 실제 ID 집합 — APPROVE_PROPOSED_CANDIDATE가 가리키는
# candidate_canonical_major_ids[0]이 진짜 서비스 Major인지(42개 Group ID 같은
# 다른 종류의 ID가 섞여 들어오지 않는지) 검증하는 데 쓴다.
_REAL_SERVICE_MAJOR_IDS: frozenset[str] = frozenset(CANONICAL_MAJOR_DESCRIPTIONS_BY_ID)


class UnknownP1CandidateError(ValueError):
    """PATCH 요청의 candidate_id가 현재 374행 P1 패킷 어디에도 대응하지 않을 때."""


class P1StaleRevisionError(ValueError):
    """§4 "revision 기반 낙관적 잠금" — 호출자가 보낸 expected_revision이 현재
    저장된 값과 다를 때(다른 검토자가 그 사이 먼저 저장했다)."""


class P1ApproveNotEligibleError(ValueError):
    """§1 "APPROVE_PROPOSED_CANDIDATE는 candidate_canonical_major_ids가 정확히
    1개이고, 공식 소계열 근거가 있는 행에만 허용" — 이 조건을 만족하지 못하는
    행에 APPROVE_PROPOSED_CANDIDATE를 저장하려 할 때. 학과명 문자열만으로 승인하지
    못하게 막는 Fail-Closed 방어선이라 메시지에 candidate_id와 사유만 담는다."""


def _approve_eligible(entry) -> bool:
    """§1 APPROVE_PROPOSED_CANDIDATE 허용 조건 — 셋 다 만족해야 한다.

    1. candidate_canonical_major_ids가 정확히 1개(0개=UNMAPPED, 2개 이상은 원본
       데이터에 없지만 구조적으로 가능성을 남기지 않는다).
    2. judgment_evidence_sufficient == True(공식 소계열 코드로 실제 분류된
       근거가 있다 — 학과명·단과대학명 키워드만으로 표시된 후보는 False다).
    3. 그 1개가 실제 10개 서비스 Major ID 중 하나(42개 Group ID인
       "fine_arts_design" 같은 값이 섞여 들어오는 걸 막는다 — DESIGN_ARTS_EXCLUDED
       판정이 정확히 이 경우다)."""

    if len(entry.candidate_canonical_major_ids) != 1:
        return False
    if not entry.judgment_evidence_sufficient:
        return False
    return entry.candidate_canonical_major_ids[0] in _REAL_SERVICE_MAJOR_IDS


def _p1_review_view(entry: AcademyInfoP1ClassificationReview | None) -> P1ReviewView:
    entry = entry or AcademyInfoP1ClassificationReview(candidate_id="")
    return P1ReviewView(
        decision=entry.decision, reviewer_comment=entry.reviewer_comment,
        resolution_note=entry.resolution_note, revision=entry.revision,
    )


def build_p1_classification_list(
    *, packet_path: Path | None = None, review_status_path: Path | None = None,
) -> P1ClassificationListResponse:
    entries = load_p1_classification_packet(packet_path or DEFAULT_P1_PACKET_PATH)
    review_by_key = load_p1_review_entries_by_key(review_status_path)

    rows: list[P1ClassificationRowView] = []
    for e in entries:
        review = review_by_key.get(e.candidate_id)
        rows.append(
            P1ClassificationRowView(
                candidate_id=e.candidate_id,
                university_name=e.university_name,
                college_name=e.college_name,
                department_name=e.department_name,
                official_large_series_name=e.official_large_series_name,
                official_middle_series_name=e.official_middle_series_name,
                official_small_series_name=e.official_small_series_name,
                p1_cluster=e.p1_cluster,
                judgment_candidate=e.judgment_candidate,
                judgment_candidate_reason=e.judgment_candidate_reason,
                judgment_evidence_sufficient=e.judgment_evidence_sufficient,
                candidate_canonical_major_ids=e.candidate_canonical_major_ids,
                arts_sports_possibility=e.arts_sports_possibility,
                official_curriculum_available=e.official_curriculum_available,
                official_curriculum_summary=e.official_curriculum_summary,
                official_evidence_needed=e.official_evidence_needed,
                approve_eligible=_approve_eligible(e),
                review=_p1_review_view(review),
            )
        )
    rows.sort(key=lambda r: r.candidate_id)

    judgment_counts: dict[str, int] = {}
    decision_counts: dict[str, int] = {}
    for r in rows:
        judgment_counts[r.judgment_candidate] = judgment_counts.get(r.judgment_candidate, 0) + 1
        decision_counts[r.review.decision] = decision_counts.get(r.review.decision, 0) + 1

    summary = P1ClassificationSummary(
        total=len(rows),
        content_media_count=sum(1 for r in rows if r.p1_cluster == "CONTENT_MEDIA"),
        design_hci_ux_count=sum(1 for r in rows if r.p1_cluster == "DESIGN_HCI_UX"),
        judgment_candidate_counts=judgment_counts,
        evidence_sufficient_count=sum(1 for r in rows if r.judgment_evidence_sufficient),
        evidence_insufficient_count=sum(1 for r in rows if not r.judgment_evidence_sufficient),
        decision_counts=decision_counts,
        reviewed_count=sum(1 for r in rows if r.review.decision != "TBD"),
        unreviewed_count=sum(1 for r in rows if r.review.decision == "TBD"),
    )
    return P1ClassificationListResponse(rows=rows, summary=summary)


def update_p1_classification_review(
    candidate_id: str, *, decision: str | None, comment: str | None, resolution_note: str | None,
    expected_revision: int, packet_path: Path | None = None, review_status_path: Path | None = None,
) -> UpdateP1ClassificationReviewResponse:
    """§1/§4 — candidate_id가 실제 374행 중 하나인지 먼저 확인하고, revision 낙관적
    잠금을 확인한 뒤, APPROVE_PROPOSED_CANDIDATE를 저장하려는 경우에만 원본 행을
    다시 대조해 허용 조건을 재확인한다(호출자가 명시적으로 이 값을 보낸 경우에만
    검사 — 다른 decision이나 코멘트만 바꾸는 저장은 이 검사를 거치지 않는다)."""

    entries_by_id = {e.candidate_id: e for e in load_p1_classification_packet(packet_path or DEFAULT_P1_PACKET_PATH)}
    draft_entry = entries_by_id.get(candidate_id)
    if draft_entry is None:
        raise UnknownP1CandidateError(f"candidate_id {candidate_id!r}가 현재 P1 패킷 374행 중 어디에도 없다")

    if decision == "APPROVE_PROPOSED_CANDIDATE" and not _approve_eligible(draft_entry):
        raise P1ApproveNotEligibleError(
            f"candidate_id {candidate_id!r}는 APPROVE_PROPOSED_CANDIDATE 허용 조건을 만족하지 않는다 "
            f"(candidate_canonical_major_ids={draft_entry.candidate_canonical_major_ids}, "
            f"judgment_evidence_sufficient={draft_entry.judgment_evidence_sufficient})"
        )

    by_key = load_p1_review_entries_by_key(review_status_path)
    existing = by_key.get(candidate_id) or AcademyInfoP1ClassificationReview(candidate_id=candidate_id)

    if existing.revision != expected_revision:
        raise P1StaleRevisionError(
            f"candidate_id {candidate_id!r}의 검수 상태가 그 사이 바뀌었다 "
            f"(기대 revision={expected_revision}, 실제={existing.revision}) — 최신 상태를 다시 불러온 뒤 다시 시도하라"
        )

    merged = existing.model_dump()
    if decision is not None:
        merged["decision"] = decision
    if comment is not None:
        merged["reviewer_comment"] = comment
    if resolution_note is not None:
        merged["resolution_note"] = resolution_note
    merged["revision"] = existing.revision + 1

    updated = AcademyInfoP1ClassificationReview.model_validate(merged)
    by_key[candidate_id] = updated
    save_p1_review_entries([by_key[k] for k in sorted(by_key)], review_status_path)
    return UpdateP1ClassificationReviewResponse(ok=True, decision=updated.decision, new_revision=updated.revision)
