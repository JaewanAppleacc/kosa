"""대학알리미 N.C.E 중계열 검수 탭 View 조립 — 2026-08-24 지시서
(a/academyinfo-review-ui-p1-nce) §2.

`academyinfo_nce_middle_series_cluster_loader.load_nce_middle_series_clusters()`
(24개 클러스터, Fail-Fast 검증 포함)가 돌려주면, 이 모듈은 그 결과에 사람 검수
상태(`data/reviews/academyinfo_nce_middle_series_review_status.jsonl`)를 조인해서
화면이 바로 쓸 수 있는 View로 바꾼다. 이 모듈 어디에도 Department Repository나
승격 로직을 호출하는 코드가 없다 — ACCEPT_GROUP_AS_REVIEW_CANDIDATE를 저장해도
학과가 자동으로 승격되지 않는다는 사실을 코드 구조 자체로 보장한다."""

from __future__ import annotations

from pathlib import Path

from src.review_ui.schemas import (
    NceCandidateGroupView,
    NceClusterRowView,
    NceMemberView,
    NceMiddleSeriesListResponse,
    NceMiddleSeriesSummary,
    NceReviewView,
    UpdateNceMiddleSeriesReviewResponse,
)
from src.schemas.academyinfo_nce_middle_series_cluster_review import AcademyInfoNceMiddleSeriesReview
from src.services.academyinfo_nce_middle_series_cluster_loader import (
    DEFAULT_NCE_CLUSTER_PATH,
    load_nce_middle_series_clusters,
)
from src.services.academyinfo_nce_middle_series_review_store import (
    load_nce_review_entries_by_key,
    nce_review_path as _nce_review_path,
    save_nce_review_entries,
)

NCE_REVIEW_STATUS_PATH = _nce_review_path()

_SAMPLE_MEMBER_LIMIT = 5


class UnknownNceMiddleSeriesCodeError(ValueError):
    """PATCH 요청의 middle_series_code가 현재 24개 클러스터 어디에도 대응하지
    않을 때."""


class NceStaleRevisionError(ValueError):
    """§4 "revision 기반 낙관적 잠금" — Bridge/P1과 같은 원칙."""


def _member_view(m) -> NceMemberView:
    return NceMemberView(
        candidate_id=m.candidate_id, university_name=m.university_name,
        college_name=m.college_name, department_name=m.department_name,
    )


def _nce_review_view(entry: AcademyInfoNceMiddleSeriesReview | None) -> NceReviewView:
    entry = entry or AcademyInfoNceMiddleSeriesReview(official_middle_series_code="")
    return NceReviewView(
        decision=entry.decision, reviewer_comment=entry.reviewer_comment,
        resolution_note=entry.resolution_note, revision=entry.revision,
    )


def build_nce_middle_series_list(
    *, cluster_path: Path | None = None, review_status_path: Path | None = None,
) -> NceMiddleSeriesListResponse:
    entries = load_nce_middle_series_clusters(cluster_path or DEFAULT_NCE_CLUSTER_PATH)
    review_by_key = load_nce_review_entries_by_key(review_status_path)

    clusters: list[NceClusterRowView] = []
    for e in entries:
        review = review_by_key.get(e.official_middle_series_code)
        all_members = [_member_view(m) for m in e.members]
        clusters.append(
            NceClusterRowView(
                official_middle_series_code=e.official_middle_series_code,
                official_middle_series_name=e.official_middle_series_name,
                official_middle_series_code_source=e.official_middle_series_code_source,
                group_linkage_status=e.group_linkage_status,
                candidate_canonical_major_groups=[
                    NceCandidateGroupView(canonical_major_group_id=g.canonical_major_id, label=g.label)
                    for g in e.candidate_canonical_major_groups
                ],
                is_single_candidate=len(e.candidate_canonical_major_groups) == 1,
                candidate_canonical_major_group_basis=e.candidate_canonical_major_group_basis,
                unlinkable_or_too_broad_reason=e.unlinkable_or_too_broad_reason,
                additional_official_evidence_needed=e.additional_official_evidence_needed,
                row_count=e.row_count,
                sample_members=all_members[:_SAMPLE_MEMBER_LIMIT],
                all_members=all_members,
                review=_nce_review_view(review),
            )
        )
    clusters.sort(key=lambda c: c.official_middle_series_code)

    decision_counts: dict[str, int] = {}
    for c in clusters:
        decision_counts[c.review.decision] = decision_counts.get(c.review.decision, 0) + 1

    proposed = [c for c in clusters if c.group_linkage_status == "PROPOSED_GROUP_CANDIDATE"]
    dept_review = [c for c in clusters if c.group_linkage_status == "DEPARTMENT_LEVEL_REVIEW_REQUIRED"]
    summary = NceMiddleSeriesSummary(
        cluster_total=len(clusters),
        department_total=sum(c.row_count for c in clusters),
        proposed_group_candidate_cluster_count=len(proposed),
        proposed_group_candidate_department_count=sum(c.row_count for c in proposed),
        department_level_review_required_cluster_count=len(dept_review),
        department_level_review_required_department_count=sum(c.row_count for c in dept_review),
        decision_counts=decision_counts,
        reviewed_count=sum(1 for c in clusters if c.review.decision != "TBD"),
        unreviewed_count=sum(1 for c in clusters if c.review.decision == "TBD"),
    )
    return NceMiddleSeriesListResponse(clusters=clusters, summary=summary)


def update_nce_middle_series_review(
    middle_series_code: str, *, decision: str | None, comment: str | None, resolution_note: str | None,
    expected_revision: int, cluster_path: Path | None = None, review_status_path: Path | None = None,
) -> UpdateNceMiddleSeriesReviewResponse:
    known_codes = {
        e.official_middle_series_code for e in load_nce_middle_series_clusters(cluster_path or DEFAULT_NCE_CLUSTER_PATH)
    }
    if middle_series_code not in known_codes:
        raise UnknownNceMiddleSeriesCodeError(
            f"official_middle_series_code {middle_series_code!r}가 현재 24개 클러스터 중 어디에도 없다"
        )

    by_key = load_nce_review_entries_by_key(review_status_path)
    existing = by_key.get(middle_series_code) or AcademyInfoNceMiddleSeriesReview(
        official_middle_series_code=middle_series_code,
    )

    if existing.revision != expected_revision:
        raise NceStaleRevisionError(
            f"{middle_series_code!r}의 검수 상태가 그 사이 바뀌었다 "
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

    updated = AcademyInfoNceMiddleSeriesReview.model_validate(merged)
    by_key[middle_series_code] = updated
    save_nce_review_entries([by_key[k] for k in sorted(by_key)], review_status_path)
    return UpdateNceMiddleSeriesReviewResponse(ok=True, decision=updated.decision, new_revision=updated.revision)
