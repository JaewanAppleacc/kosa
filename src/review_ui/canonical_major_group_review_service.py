"""Canonical Major Group(42개) 검수 탭 View 조립 — 2026-08-24 지시서
(a/canonical-major-group-review-ui).

`data/canonical_major_groups.draft.jsonl`(42개, worker-c 산출, Read-Only Draft)를
읽고, 사람이 검수 카드를 판단하는 데 필요한 세 종류의 정보를 곁들인다:

1. 공식 대계열·중계열·소계열 명칭 — Draft 자체에는 없다. 대학알리미 원본 코드표
   (`getCodeByLargeSeries`/`getCodeByMiddleSeries`/`getCodeBySmallSeries`/
   `getCodeBySeriesSystem`, 전부 Read-Only 원본 수집 데이터)를 조인해서 계산한다
   (`middle_series_hint`는 Draft 저자가 미리 적어둔 힌트일 뿐이라 이 계산과 다를 수
   있다 — 둘 다 그대로 보여준다).
2. 전국 학과 후보 수 — worker-c의 2025년도 조사 Dry-Run 결과
   (`data/academyinfo_work/2025/classification_dry_run.json`)에서 Group 라벨로
   조인한다(Bridge 검수 화면과 같은 방식·같은 파일).
3. P1/N.C.E/Bridge 경계 관련 메모 — 세 개의 다른 검수 축(Bridge Mapping Draft의
   `boundary_notes`, N.C.E 클러스터의 `unlinkable_or_too_broad_reason`/
   `additional_official_evidence_needed`, P1 패킷의 `judgment_candidate_reason`
   중 근거 불충분/예체능 제외로 표시된 행)에서 이 Group을 언급하는 메모만 모아
   읽기 전용으로 보여준다. 이 모듈은 그 세 파일 중 어느 것도 쓰지 않는다 — 세
   축의 검수 상태(Bridge Mapping 38 APPROVE/6 REVISE, P1 374건 TBD, N.C.E 24개
   TBD)는 이 모듈이 존재하기 전과 정확히 같은 상태로 남는다.

사람 검수 상태(`data/reviews/canonical_major_group_review_status.jsonl`, 이
지시서에서 새로 만드는 파일)를 덧붙인다. 이 모듈은 Group Draft·세 code
table·Bridge/N.C.E/P1 Draft를 읽기만 하고 절대 쓰지 않는다 — Runtime
Matching·Department 조회 어디에도 연결되지 않는다(§ "Dry Run Gate에 연결하지
않는다")."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from src.review_ui.schemas import (
    CanonicalMajorGroupListResponse,
    CanonicalMajorGroupReviewView,
    CanonicalMajorGroupRowView,
    CanonicalMajorGroupSummary,
    OfficialSeriesView,
    UpdateCanonicalMajorGroupReviewResponse,
)
from src.schemas.canonical_major_group_review import CanonicalMajorGroupReview, expected_reviewer_1_status_for_decision
from src.services.academyinfo_nce_middle_series_cluster_loader import (
    DEFAULT_NCE_CLUSTER_PATH,
    load_nce_middle_series_clusters,
)
from src.services.academyinfo_p1_classification_loader import DEFAULT_P1_PACKET_PATH, load_p1_classification_packet
from src.services.canonical_major_group_bridge_loader import (
    ARTS_EXCLUDED_GROUP_IDS,
    DEFAULT_BRIDGE_DRAFT_PATH,
    DEFAULT_CANONICAL_MAJORS_PATH,
    load_canonical_major_group_bridge,
)
from src.services.canonical_major_group_draft_loader import (
    DEFAULT_CANONICAL_MAJOR_GROUPS_DRAFT_PATH,
    load_canonical_major_groups_draft,
)
from src.services.canonical_major_group_review_store import (
    canonical_major_group_review_path as _canonical_major_group_review_path,
)
from src.services.canonical_major_group_review_store import (
    load_canonical_major_group_review_entries_by_key,
    save_canonical_major_group_review_entries,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CODES_DIR = _REPO_ROOT / "data" / "academyinfo_raw" / "2025" / "codes"
DEFAULT_LARGE_SERIES_CODE_TABLE_PATH = _CODES_DIR / "getCodeByLargeSeries.jsonl.gz"
DEFAULT_MIDDLE_SERIES_CODE_TABLE_PATH = _CODES_DIR / "getCodeByMiddleSeries.jsonl.gz"
DEFAULT_SMALL_SERIES_CODE_TABLE_PATH = _CODES_DIR / "getCodeBySmallSeries.jsonl.gz"
DEFAULT_SERIES_SYSTEM_TABLE_PATH = _CODES_DIR / "getCodeBySeriesSystem.jsonl.gz"
# worker-c 산출물(2025년도 조사 Dry-Run 결과) — Bridge 검수 화면과 동일 파일·동일
# 조인 방식(Group 라벨 기준)이다. Group Draft 자체에는 없는 "전국 학과 후보 개수"의
# 유일한 출처다.
DEFAULT_CLASSIFICATION_DRY_RUN_PATH = _REPO_ROOT / "data" / "academyinfo_work" / "2025" / "classification_dry_run.json"

# 2026-08-24 관례(review_service.QUESTION_REVIEW_PATH와 동일) — 모듈 속성으로
# 노출해서 app.py가 매 요청마다 이 이름을 "그때그때" 다시 읽게 한다. 테스트가
# `unittest.mock.patch("src.review_ui.canonical_major_group_review_service.
# REVIEW_STATUS_PATH", tmp_path)`로 임시 경로를 주입하면, 실제 data/reviews/
# 파일을 전혀 건드리지 않고 저장 동작을 검증할 수 있다.
REVIEW_STATUS_PATH = _canonical_major_group_review_path()

# N.C.E 소계열 센티널(999)은 이 조인에서 제외한다 — "분류 없음" 표시이지 실제
# 소계열이 아니다(src.data_sources.academyinfo_codes.UNCLASSIFIED_SMALL_SERIES와
# 같은 값). Group Draft의 field_validator가 애초에 이 값을 포함하지 못하게
# 막지만, 이 모듈은 원본 코드표를 직접 다시 읽으므로 방어적으로 한 번 더 걸러둔다.
_UNCLASSIFIED_SMALL_SERIES = "999"


class UnknownCanonicalMajorGroupIdError(ValueError):
    """PATCH 요청의 canonical_major_group_id가 현재 42개 Group Draft 어디에도
    대응하지 않을 때. 존재하지 않는 Group으로 검수 상태를 새로 만들어 저장하지
    않는다 — Draft에 실제로 있는 Group만 검수 대상이다."""


class CanonicalMajorGroupStaleRevisionError(ValueError):
    """§3 "expected_revision 낙관적 잠금" — 다른 사람이 그 사이 같은 Group을
    먼저 저장했을 때. Bridge/P1/N.C.E와 같은 원칙."""


def _load_code_table(path: Path) -> dict[str, str]:
    """`{cdid: cdnm}` 공식 코드표. 대계열(6개)·중계열(28개)·소계열(158개) 세
    코드표가 전부 같은 형태(cdid/cdnm)라 이 헬퍼 하나로 셋 다 읽는다."""

    codes: dict[str, str] = {}
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            codes[row["cdid"]] = row["cdnm"]
    return codes


def _load_small_to_parent_series(path: Path) -> dict[str, tuple[str, str]]:
    """`getCodeBySeriesSystem`(소계열→중계열→대계열 대응표)에서
    `{소계열 코드: (중계열 코드, 대계열 코드)}`를 만든다. 실측(2026-08-24): 999를
    제외한 소계열 코드 162개 전부 정확히 하나의 (중계열, 대계열) 조합에만
    대응한다(중복 없음) — 이 전제가 깨지면(향후 코드표 개정 등) 여기서 마지막 값이
    조용히 덮어써지므로, 이 사실은 테스트(`test_canonical_major_group_review.py`)로
    고정해둔다."""

    with gzip.open(path, "rt", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    lookup: dict[str, tuple[str, str]] = {}
    for row in rows:
        small_code = row["srsSclftCd"]
        if small_code == _UNCLASSIFIED_SMALL_SERIES:
            continue
        lookup[small_code] = (row["srsMclftCd"], row["srsLclftCd"])
    return lookup


def _department_counts_by_group_label(dry_run_path: Path | None = None) -> dict[str, int]:
    resolved = dry_run_path or DEFAULT_CLASSIFICATION_DRY_RUN_PATH
    if not resolved.exists():
        return {}
    data = json.loads(resolved.read_text(encoding="utf-8"))
    return dict(data.get("departments_per_canonical_group", {}))


def _official_series_view(
    included_small_series_codes: list[str],
    *,
    small_to_parent: dict[str, tuple[str, str]],
    large_names: dict[str, str],
    middle_names: dict[str, str],
    small_names: dict[str, str],
) -> OfficialSeriesView:
    """이 Group이 포함하는 소계열 코드들이 실제로 걸리는 공식 대계열·중계열
    집합을 계산한다(코드 그 자체가 정본이라 이름 문자열 매칭을 쓰지 않는다).
    Group 하나가 여러 중계열에 걸치는 경우가 실제로 있다(예: 여러 인문계열
    소계열을 하나의 Group으로 묶은 경우) — 그래서 단수가 아니라 목록으로 돌려준다."""

    middle_codes: list[str] = []
    large_codes: list[str] = []
    for code in included_small_series_codes:
        parent = small_to_parent.get(code)
        if parent is None:
            continue
        middle_code, large_code = parent
        if middle_code not in middle_codes:
            middle_codes.append(middle_code)
        if large_code not in large_codes:
            large_codes.append(large_code)
    middle_codes.sort()
    large_codes.sort()
    return OfficialSeriesView(
        large_series_codes=large_codes,
        large_series_names=[large_names.get(c, c) for c in large_codes],
        middle_series_codes=middle_codes,
        middle_series_names=[middle_names.get(c, c) for c in middle_codes],
        included_small_series_names=[small_names.get(c, c) for c in included_small_series_codes],
    )


def _bridge_linked_and_boundary_notes(
    bridge_path: Path | None, group_draft_path: Path | None,
) -> tuple[frozenset[str], dict[str, list[str]]]:
    """Bridge Mapping Draft(44행)에서 이 Group이 최소 1개 Major와 연결돼 있는지
    (§ "Bridge 연결 있음/없음" 필터), 그리고 이 Group을 언급하는 `boundary_notes`를
    모은다. Bridge 검수 상태 파일은 열지 않는다 — 이 함수가 읽는 건 Draft
    원본뿐이다(Bridge 검수 상태를 바꾸지 않는다는 사실을 코드 경로 자체로
    보장한다)."""

    try:
        report = load_canonical_major_group_bridge(
            bridge_path or DEFAULT_BRIDGE_DRAFT_PATH,
            group_draft_path=group_draft_path or DEFAULT_CANONICAL_MAJOR_GROUPS_DRAFT_PATH,
            majors_path=DEFAULT_CANONICAL_MAJORS_PATH,
        )
    except (FileNotFoundError, ValueError):
        return frozenset(), {}
    linked: set[str] = set()
    notes: dict[str, list[str]] = {}
    for e in report.entries:
        linked.add(e.canonical_major_group_id)
        text = e.boundary_notes.strip()
        if not text:
            continue
        bucket = notes.setdefault(e.canonical_major_group_id, [])
        if text not in bucket:
            bucket.append(text)
    return frozenset(linked), notes


def _nce_related_and_boundary_notes(nce_path: Path | None) -> tuple[frozenset[str], dict[str, list[str]]]:
    """N.C.E 재검토 가능 중계열 클러스터(24개)에서 이 Group이 후보로 등장하는지,
    그리고 그 클러스터의 경계 관련 메모(`unlinkable_or_too_broad_reason`/
    `additional_official_evidence_needed`)를 모은다."""

    try:
        clusters = load_nce_middle_series_clusters(nce_path or DEFAULT_NCE_CLUSTER_PATH)
    except (FileNotFoundError, ValueError):
        return frozenset(), {}
    related: set[str] = set()
    notes: dict[str, list[str]] = {}
    for cluster in clusters:
        group_ids = {g.canonical_major_id for g in cluster.candidate_canonical_major_groups}
        related |= group_ids
        texts = []
        if cluster.unlinkable_or_too_broad_reason.strip():
            texts.append(f"N.C.E {cluster.official_middle_series_code}: {cluster.unlinkable_or_too_broad_reason.strip()}")
        for item in cluster.additional_official_evidence_needed:
            if item.strip():
                texts.append(f"N.C.E {cluster.official_middle_series_code} 추가 근거 필요: {item.strip()}")
        if not texts:
            continue
        for gid in group_ids:
            bucket = notes.setdefault(gid, [])
            for t in texts:
                if t not in bucket:
                    bucket.append(t)
    return frozenset(related), notes


def _p1_boundary_notes_by_group(p1_path: Path | None) -> dict[str, list[str]]:
    """P1 분류 REVIEW 패킷(374건)에서 이 Group을 후보로 가리키면서 근거가
    불충분하거나(judgment_evidence_sufficient=False) 예체능 제외로 판정된
    (DESIGN_ARTS_EXCLUDED) 행의 판단 사유만 모은다 — 근거가 충분한 행은 경계
    사례가 아니라 정상 분류이므로 제외한다."""

    try:
        entries = load_p1_classification_packet(p1_path or DEFAULT_P1_PACKET_PATH)
    except (FileNotFoundError, ValueError):
        return {}
    notes: dict[str, list[str]] = {}
    for e in entries:
        if e.judgment_evidence_sufficient and e.judgment_candidate != "DESIGN_ARTS_EXCLUDED":
            continue
        reason = e.judgment_candidate_reason.strip()
        if not reason:
            continue
        text = f"P1({e.judgment_candidate}): {reason}"
        for gid in e.candidate_canonical_major_ids:
            bucket = notes.setdefault(gid, [])
            if text not in bucket:
                bucket.append(text)
    return notes


def _review_view(entry: CanonicalMajorGroupReview | None, group_id: str) -> CanonicalMajorGroupReviewView:
    entry = entry or CanonicalMajorGroupReview(canonical_major_group_id=group_id)
    return CanonicalMajorGroupReviewView(
        decision=entry.decision,
        reviewer_1_status=entry.reviewer_1_status, reviewer_1_comment=entry.reviewer_1_comment,
        reviewer_2_status=entry.reviewer_2_status, reviewer_2_comment=entry.reviewer_2_comment,
        resolution_note=entry.resolution_note, revision=entry.revision, final_status=entry.final_status,
    )


def build_canonical_major_group_review_list(
    *, group_draft_path: Path | None = None, review_status_path: Path | None = None,
    dry_run_path: Path | None = None, bridge_path: Path | None = None, nce_path: Path | None = None,
    p1_path: Path | None = None, large_series_path: Path | None = None, middle_series_path: Path | None = None,
    small_series_path: Path | None = None, series_system_path: Path | None = None,
) -> CanonicalMajorGroupListResponse:
    """42개 Group 전체를 화면이 바로 쓸 수 있는 View로 조립한다. 이 함수는 어떤
    파일도 쓰지 않는다 — GET·필터만으로는 이 검수 파일도, Bridge/N.C.E/P1 Draft·
    검수 파일도 절대 생성·수정되지 않는다(§5)."""

    groups = load_canonical_major_groups_draft(group_draft_path or DEFAULT_CANONICAL_MAJOR_GROUPS_DRAFT_PATH)
    large_names = _load_code_table(large_series_path or DEFAULT_LARGE_SERIES_CODE_TABLE_PATH)
    middle_names = _load_code_table(middle_series_path or DEFAULT_MIDDLE_SERIES_CODE_TABLE_PATH)
    small_names = _load_code_table(small_series_path or DEFAULT_SMALL_SERIES_CODE_TABLE_PATH)
    small_to_parent = _load_small_to_parent_series(series_system_path or DEFAULT_SERIES_SYSTEM_TABLE_PATH)
    dept_counts = _department_counts_by_group_label(dry_run_path)
    review_by_key = load_canonical_major_group_review_entries_by_key(review_status_path)
    bridge_linked_ids, bridge_linked_notes = _bridge_linked_and_boundary_notes(bridge_path, group_draft_path)
    nce_related_ids, nce_notes = _nce_related_and_boundary_notes(nce_path)
    p1_notes = _p1_boundary_notes_by_group(p1_path)

    rows: list[CanonicalMajorGroupRowView] = []
    for g in groups:
        group_id = g.canonical_major_id
        boundary_notes = [*bridge_linked_notes.get(group_id, []), *nce_notes.get(group_id, []), *p1_notes.get(group_id, [])]
        rows.append(
            CanonicalMajorGroupRowView(
                canonical_major_group_id=group_id,
                label=g.label,
                description=g.description,
                official_series=_official_series_view(
                    g.included_official_small_series_codes, small_to_parent=small_to_parent,
                    large_names=large_names, middle_names=middle_names, small_names=small_names,
                ),
                included_official_small_series_codes=g.included_official_small_series_codes,
                middle_series_hint=g.middle_series_hint,
                boundary_cases=g.boundary_cases,
                classification_basis=g.classification_basis,
                official_source_urls=g.official_source_urls,
                draft_review_status=g.review_status,
                is_arts_or_sports_group=group_id in ARTS_EXCLUDED_GROUP_IDS,
                national_department_candidate_count=dept_counts.get(g.label),
                is_bridge_linked=group_id in bridge_linked_ids,
                is_nce_related=group_id in nce_related_ids,
                cross_review_boundary_notes=boundary_notes,
                review=_review_view(review_by_key.get(group_id), group_id),
            )
        )
    rows.sort(key=lambda r: r.canonical_major_group_id)

    decisions = [r.review.decision for r in rows]
    summary = CanonicalMajorGroupSummary(
        total=len(rows),
        tbd_count=decisions.count("TBD"),
        approve_count=decisions.count("APPROVE_AS_CLASSIFICATION_GROUP"),
        revise_count=sum(1 for d in decisions if d in ("REVISE_GROUP_DEFINITION", "SPLIT_GROUP", "MERGE_WITH_OTHER_GROUP")),
        hold_count=decisions.count("HOLD"),
        excluded_count=decisions.count("EXCLUDE_FROM_CLASSIFICATION"),
        arts_or_sports_count=sum(1 for r in rows if r.is_arts_or_sports_group),
        bridge_linked_count=sum(1 for r in rows if r.is_bridge_linked),
        bridge_unlinked_count=sum(1 for r in rows if not r.is_bridge_linked),
        nce_related_count=sum(1 for r in rows if r.is_nce_related),
        reviewed_count=sum(1 for d in decisions if d != "TBD"),
        unreviewed_count=decisions.count("TBD"),
    )
    return CanonicalMajorGroupListResponse(rows=rows, summary=summary)


def update_canonical_major_group_review(
    canonical_major_group_id: str, *, decision: str | None, comment: str | None, resolution_note: str | None,
    expected_revision: int, group_draft_path: Path | None = None, review_status_path: Path | None = None,
) -> UpdateCanonicalMajorGroupReviewResponse:
    """§3 — `canonical_major_group_id`가 실제 42개 Group 중 하나인지부터 확인한다
    (존재하지 않는 Group으로 새 행을 만들지 않는다). `expected_revision`이
    저장된 값과 다르면 저장을 거부한다(낙관적 잠금, Bridge/P1/N.C.E와 같은 원칙).
    `decision`/`comment`/`resolution_note`는 전부 None이면 기존 값을 그대로
    두는 부분 저장 규칙을 따른다 — 저장 버튼을 눌러도 명시적으로 건드리지 않은
    필드가 암묵적으로 바뀌지 않는다.

    이 함수는 어떤 인자 조합으로도 스스로 `decision`을 "APPROVE_AS_CLASSIFICATION_GROUP"
    으로 정하지 않는다 — 호출자가 명시적으로 그 값을 보낸 경우에만 저장된다
    (자동 승인 금지). 이 함수는 Draft 파일도, Bridge/Scope/P1/N.C.E 검수 파일도
    Department Master·Dry Run 결과도 절대 쓰지 않는다 — 이 함수가 쓰는 파일은
    `review_status_path` 하나뿐이다."""

    known_ids = {g.canonical_major_id for g in load_canonical_major_groups_draft(group_draft_path)}
    if canonical_major_group_id not in known_ids:
        raise UnknownCanonicalMajorGroupIdError(
            f"canonical_major_group_id {canonical_major_group_id!r}가 현재 42개 Group Draft 중 어디에도 없다"
        )

    by_key = load_canonical_major_group_review_entries_by_key(review_status_path)
    existing = by_key.get(canonical_major_group_id) or CanonicalMajorGroupReview(
        canonical_major_group_id=canonical_major_group_id,
    )

    if existing.revision != expected_revision:
        raise CanonicalMajorGroupStaleRevisionError(
            f"{canonical_major_group_id!r}의 검수 상태가 그 사이 바뀌었다 "
            f"(기대 revision={expected_revision}, 실제={existing.revision}) — 최신 상태를 다시 불러온 뒤 다시 시도하라"
        )

    merged = existing.model_dump()
    if decision is not None:
        merged["decision"] = decision
    if comment is not None:
        merged["reviewer_1_comment"] = comment
    if resolution_note is not None:
        merged["resolution_note"] = resolution_note
    merged["revision"] = existing.revision + 1
    # §3 불변식 — reviewer_1_status는 이 저장 시점의 decision(방금 바뀌었든 그대로
    # 유지됐든)에서 유일하게 계산되는 값이어야 한다. 이 줄을 지우면 아래
    # model_validate()가 CanonicalMajorGroupReview의 model_validator에서 즉시
    # ValueError로 막는다(Fail-Fast) — 여기서는 애초에 모순된 값을 만들지 않는다.
    merged["reviewer_1_status"] = expected_reviewer_1_status_for_decision(merged["decision"])

    updated = CanonicalMajorGroupReview.model_validate(merged)
    by_key[canonical_major_group_id] = updated
    save_canonical_major_group_review_entries(
        [by_key[k] for k in sorted(by_key)], review_status_path or REVIEW_STATUS_PATH,
    )
    return UpdateCanonicalMajorGroupReviewResponse(ok=True, decision=updated.decision, new_revision=updated.revision)
