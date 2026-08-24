"""전국 학과 → `data/master/departments.jsonl` 승격 Dry Run — c/national-master-promotion-dry-run.

**이 스크립트는 실제 Master(`data/master/departments.jsonl`)도 공개 API/Mock도 절대
바꾸지 않는다.** 어떤 학과가 어떤 이유로 승격 가능하거나 차단되는지 **계산만** 한다
(Fail-Closed — 검수 파일이 없으면 자동 승인하지 않고 해당 Gate를 BLOCKED로 계산한다).

## 입력

- `data/academyinfo_work/<year>/departments.normalized.jsonl` (필수 — 없으면 종료 코드 2,
  아무것도 쓰지 않는다)
- `data/academyinfo_work/<year>/classification_results.jsonl` (필수 — 위와 동일)
- `data/academyinfo_work/<year>/out_of_recommendation_scope.jsonl` (선택 — 있으면 야간·원격
  학과를 승격 후보 전체 집합에 합친다. `career_normalize_academyinfo.py::normalize()`는 야간·
  원격 학과를 `departments.normalized.jsonl`에 아예 넣지 않고 이 파일에만 남기므로, 이 파일이
  없으면 야간·원격 차단 사유를 계산할 수 없다 — 없어도 실패하지 않지만 그만큼 덜 본다)
- `data/canonical_major_groups.draft.jsonl` (42개 Canonical Major Group Draft)
- `data/master/canonical_major_group_bridge.draft.jsonl` (Bridge Mapping, Scope 필드 포함)
- `data/master/canonical_majors.jsonl` (10개 서비스 Canonical Major)
- `data/academyinfo_raw/<year>/codes/getCodeBySmallSeries.jsonl.gz` (Bridge Scope 소계열
  코드 교차검증용 공식 코드표 — `canonical_major_group_bridge_loader.py`와 동일)
- `data/reviews/canonical_major_group_bridge_review_status.json` (Bridge Mapping 사람 검수)
- `data/reviews/canonical_major_group_bridge_scope_review_status.jsonl` (Bridge Scope 사람
  검수 — 2026-08-24 시점 아직 존재하지 않는다. 없으면 전부 BLOCKED_BRIDGE_SCOPE_REVIEW)
- `data/academyinfo_work/<year>/packets/p1_classification_review.jsonl` (P1 분류 REVIEW
  Draft 패킷, 374행, `academyinfo_p1_classification_loader.py`가 Fail-Fast로 읽는다 —
  검수 UI GET Endpoint와 같은 정본. 필수 — 없으면 종료 코드 2)
- `data/reviews/academyinfo_p1_classification_review_status.jsonl` (P1 사람 검수 — 검수 UI
  (a/academyinfo-review-ui-p1-nce)의 PATCH가 저장하는 바로 그 파일, candidate_id 키.
  없으면 전부 BLOCKED_P1_REVIEW_UNRESOLVED. APPROVE_PROPOSED_CANDIDATE로 저장돼 있어도
  이 Dry Run은 그 값을 그대로 믿지 않고 Draft 패킷과 대조해
  `p1_approve_eligible()`을 다시 실행한다)
- `data/academyinfo_work/<year>/packets/nce_reexaminable_middle_series_clusters.jsonl`
  (N.C.E 중계열 클러스터 Draft, 24개, `academyinfo_nce_middle_series_cluster_loader.py`가
  읽는다 — 검수 UI GET Endpoint와 같은 정본. 필수 — 없으면 종료 코드 2)
- `data/reviews/academyinfo_nce_middle_series_review_status.jsonl` (N.C.E 사람 검수 — 검수
  UI의 PATCH가 저장하는 바로 그 파일, official_middle_series_code 키. 이 파일에 무엇이
  적혀 있든(ACCEPT_GROUP_AS_REVIEW_CANDIDATE 포함) N.C.E로 분류된 학과는 절대
  READY_FOR_PROMOTION으로 풀리지 않는다 — §Gate 참고)
- `data/academyinfo_work/<year>/department_url_scope_audit.jsonl` (선택 — Department URL
  감사. `department_id`가 없는 원본이라 (university_name, department_name, college_name)
  3-tuple로 정규화 결과와 조인한다)
- `data/reviews/academyinfo_duplicate_scope_review_status.jsonl` (계약학과 승인 정본 — 이번
  Gate 판정에 직접 쓰지 않는다. `CONTRACT_DEPARTMENT` 제외는 이미 정규화 단계에서 공식
  필드로 결정론적으로 계산됐다 — 이 파일은 그 결정이 실제로 사람 승인을 받았는지 대조
  검증용으로만 읽고, 요약에 정합성 통계로 남긴다)

## Gate(전부 충족해야 READY_FOR_PROMOTION, 지시서 §2)

department_status ∈ {EXISTING, NEW} · recommendation_scope=IN_RECOMMENDATION_SCOPE ·
야간·원격·계약학과 아님 · 예체능 추천 제외 정책 통과 · N.C.E 미해결 아님 ·
classification REVIEW 미해결 아님(그룹 충돌 + P1 예체능 애매 둘 다) · Canonical Major
Group 검수 승인 · Bridge Mapping 승인 · Bridge Scope 승인 · Scope에 포함된 공식 소계열 ·
서비스 Canonical Major 10개 중 하나로 연결 · 중복 department_id 없음 · 필수 대학알리미
Lineage 존재 · URL 정책 통과.

하나라도 어긋나면 `promotion_blocked.jsonl`로 가고, **적용되는 모든 사유**를 보존한다
(첫 번째 사유만 남기지 않는다). 다음 두 가지는 지시서가 준 12개 예시 밖에 추가한
Gate다(지시서 §3 "예:"가 예시일 뿐이라고 명시했으므로, 실제 검증 가능한 축을 놓치지
않기 위해 추가했다) — 필요하면 사람이 검토한다:

- `BLOCKED_INACTIVE_STATUS`: department_status가 EXISTING/NEW가 아님(ABOLISHED 등).
- `BLOCKED_MISSING_CLASSIFICATION`: 추천범위 안인데 classification_results에 대응 행이
  없다(정상 파이프라인에서는 발생하지 않아야 하는 데이터 정합성 방어).
- `BLOCKED_P1_REVIEW_UNRESOLVED`: eligibility_status=REVIEW_REQUIRED(예체능 애매)인데 P1
  검수가 승인되지 않음 — `BLOCKED_CLASSIFICATION_REVIEW`(그룹 충돌)와 구분해 어느 검수
  트랙이 막았는지 명확히 남긴다.
- `BLOCKED_OUT_OF_RECOMMENDATION_SCOPE`: 야간·원격·계약학과 외의 알 수 없는 추천범위
  제외 사유(방어적 Fallback, 현재 데이터에서는 등장하지 않는다).
- `BLOCKED_BRIDGE_EXCLUDED_RECOMMENDATION`: Bridge mapping_status가
  EXCLUDED_RECOMMENDATION인데 예체능 4개 Group이 아닌 경우(방어적 Fallback).
- `BLOCKED_URL_POLICY`: URL 감사에서 API Key 포함이 확인됐거나 `Department.department_url`
  자체 검증(§18)을 통과하지 못하는 URL.
- `BLOCKED_AMBIGUOUS_SERVICE_CANONICAL_MAJOR`: 2026-08-24 지시서(a/academyinfo-review-ui-
  p1-nce 정본 채택) §8 — "Bridge 후보 없음"과 "복수 후보"를 구분한다. 아래 "설계상 명시적
  한계" 참고.

## Bridge 후보 없음 vs 복수 후보(지시서 §8, 2026-08-24)

같은 Group에 서비스 Major로 이어지는 EVIDENCED Bridge 행이 몇 개인지에 따라 사유가
갈린다 — 둘 다 자동으로 후보를 고르지 않고 막지만, 사람이 봐야 할 일이 다르다.

- **0개** → `BLOCKED_NO_SERVICE_CANONICAL_MAJOR`: 이 Group을 어떤 서비스 Major에도
  연결한 EVIDENCED 행이 아직 없다(UNMAPPED 전용이거나 Bridge가 이 Group을 다루지
  않았다) — Bridge 자체를 새로 만들어야 한다.
- **2개 이상** → `BLOCKED_AMBIGUOUS_SERVICE_CANONICAL_MAJOR`(예: 실제 데이터의
  `computer_science` Group이 `computer_science`/`hci_ux` 두 Major 후보를 가짐 — 다만
  실제로는 `hci_ux`가 REVIEW_REQUIRED라 지금 데이터에서는 해당 없음) — Bridge는 이미
  있지만 이 Dry Run이 어느 쪽이 맞는지 자동으로 고르지 않는다. 개별 학과 교육과정
  검토(`department_recommendation_scope.jsonl`류)로 넘긴다 — 이 Dry Run은 그 정본을
  입력으로 쓰지 않는다(지시서가 나열한 입력 목록에 없다).

`classification_results.jsonl`의 `mapping_status == "AUTO_CANDIDATE"`가 애초에 후보
0개/2개 이상을 반환하는 경우도 같은 두 사유로 나눈다(분류 단계 자체의 모호함).

## 설계상 명시적 한계(감사 필요 항목)

- `BLOCKED_MISSING_LINEAGE`는 연도 간 비교 파일(`department_lineage.jsonl`, 직전 연도
  정규화 결과가 있어야만 생성된다 — 조건부)이 아니라, 각 행 자체가 대학알리미 원본
  식별자(`source_record_id`·`schl_id`·`source_schl_mjr_id`/`source_mjr_id`)를 갖고
  있는지로 판정한다. 연도 간 lineage는 선택 입력이 아니고 첫 수집 연도에는 아예 생성되지
  않아, 이를 필수로 삼으면 첫 수집 연도 전체가 영구히 막혀 "필수" 의미가 왜곡된다. 그래서
  각 출력 행의 `lineage_level`은 항상 `"ROW_IDENTITY_ONLY"`다 — 실제 여러 조사연도를
  비교해 같은 학과인지 확인하는 코드(`"CROSS_YEAR_LINEAGE_VERIFIED"`)는 이 저장소에
  아직 없고, 이 파일도 그 값을 만들지 않는다(2026-08-24 지시서 §9).
- N.C.E(공식 소계열 미분류)로 걸린 학과는 N.C.E 검수 상태가 무엇이든(TBD든
  `ACCEPT_GROUP_AS_REVIEW_CANDIDATE`든) 이 Dry Run 혼자서는 절대 READY_FOR_PROMOTION에
  도달할 수 없다(2026-08-24 지시서 §7). `ACCEPT_GROUP_AS_REVIEW_CANDIDATE`는 "이
  중계열에서 이 전공군을 검토 후보로 쓸 수 있다"는 1차 판단일 뿐, 그 중계열에 속한
  학과들의 승격 승인이 아니다 — 학과 단위로 실제 교육과정을 확인하는 별도 Gate가
  이 저장소에 생기기 전까지는 `BLOCKED_NCE_UNRESOLVED`가 항상 남는다(출력 행의
  `nce_middle_series_code`/`nce_review_decision`은 감사·추적용 참고 필드일 뿐, 이
  Gate 결과에 영향을 주지 않는다).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402
from src.review_ui.academyinfo_p1_classification_review_service import p1_approve_eligible  # noqa: E402
from src.schemas.academyinfo_nce_middle_series_cluster import AcademyInfoNceMiddleSeriesClusterEntry  # noqa: E402
from src.schemas.academyinfo_nce_middle_series_cluster_review import AcademyInfoNceMiddleSeriesReview  # noqa: E402
from src.schemas.academyinfo_p1_classification import AcademyInfoP1ClassificationEntry  # noqa: E402
from src.schemas.academyinfo_p1_classification_candidate_review import AcademyInfoP1ClassificationReview  # noqa: E402
from src.schemas.canonical_major_group import CanonicalMajorGroupDraft  # noqa: E402
from src.schemas.canonical_major_group_bridge_review import (  # noqa: E402
    CanonicalMajorGroupBridgeReview,
    bridge_review_key,
)
from src.schemas.canonical_major_group_bridge_scope_review import CanonicalMajorGroupBridgeScopeReview  # noqa: E402
from src.schemas.major import Department  # noqa: E402
from src.services.academyinfo_nce_middle_series_cluster_loader import (  # noqa: E402
    DEFAULT_NCE_CLUSTER_PATH,
    load_nce_middle_series_clusters,
)
from src.services.academyinfo_nce_middle_series_review_store import (  # noqa: E402
    load_nce_review_entries_by_key,
    nce_review_path as default_nce_review_path,
)
from src.services.academyinfo_p1_classification_loader import (  # noqa: E402
    DEFAULT_P1_PACKET_PATH,
    load_p1_classification_packet,
)
from src.services.academyinfo_p1_classification_review_store import (  # noqa: E402
    load_p1_review_entries_by_key,
    p1_review_path as default_p1_review_path,
)
from src.services.canonical_major_group_bridge_loader import (  # noqa: E402
    ARTS_EXCLUDED_GROUP_IDS,
    BridgeValidationError,
    load_canonical_major_group_bridge,
)
from src.services.canonical_major_group_draft_loader import load_canonical_major_groups_draft  # noqa: E402
from src.services.department_url_promotion import resolve_department_url_for_promotion  # noqa: E402
from src.services.major_exploration_service import EXCLUDED_RECOMMENDATION_MAJOR_IDS  # noqa: E402
from src.engines.canonical_mapper import load_canonical_majors  # noqa: E402

# 지시서(a/academyinfo-review-ui-p1-nce, 이후 이 Dry Run이 그 정본을 채택하기로 한
# 지시서) §9 — 연도 간 실제 대조 없이 이 값을 절대 쓰지 않는다. 지금 계산하는 것은
# "이 행 자체가 안정적인 원본 식별자를 갖고 있는가"(ROW_IDENTITY_ONLY)뿐이다 —
# 여러 조사연도의 정규화 결과를 실제로 비교하는 코드가 이 저장소에 생기기 전까지
# CROSS_YEAR_LINEAGE_VERIFIED를 만드는 코드는 이 파일 어디에도 없어야 한다.
LINEAGE_LEVEL_ROW_IDENTITY_ONLY = "ROW_IDENTITY_ONLY"
LINEAGE_LEVEL_CROSS_YEAR_VERIFIED = "CROSS_YEAR_LINEAGE_VERIFIED"

_NCE_UNMAPPED_REASON_PREFIX = "공식 소계열이 미분류"

_NIGHT_REMOTE_EXCLUSION_REASONS = frozenset(
    {"EXCLUDED_NIGHT_COURSE", "EXCLUDED_DISTANCE_UNIVERSITY", "EXCLUDED_UNKNOWN_DAY_NIGHT"}
)

# 결정론적 산출물이라 값을 셋으로 모았다가 정렬해서 쓴다(같은 입력이면 항상 같은 순서).
ALL_BLOCKED_REASONS = (
    "BLOCKED_AMBIGUOUS_SERVICE_CANONICAL_MAJOR",
    "BLOCKED_ARTS_RECOMMENDATION",
    "BLOCKED_BRIDGE_EXCLUDED_RECOMMENDATION",
    "BLOCKED_BRIDGE_MAPPING_REVIEW",
    "BLOCKED_BRIDGE_SCOPE_REVIEW",
    "BLOCKED_CLASSIFICATION_REVIEW",
    "BLOCKED_CONTRACT_DEPARTMENT",
    "BLOCKED_DUPLICATE_ID",
    "BLOCKED_GROUP_DRAFT",
    "BLOCKED_INACTIVE_STATUS",
    "BLOCKED_MISSING_CLASSIFICATION",
    "BLOCKED_MISSING_LINEAGE",
    "BLOCKED_NCE_UNRESOLVED",
    "BLOCKED_NIGHT_OR_REMOTE",
    "BLOCKED_NO_SERVICE_CANONICAL_MAJOR",
    "BLOCKED_OUTSIDE_SMALL_SERIES_SCOPE",
    "BLOCKED_OUT_OF_RECOMMENDATION_SCOPE",
    "BLOCKED_P1_REVIEW_UNRESOLVED",
    "BLOCKED_URL_POLICY",
)


# ============================== 파일 IO 도우미 ==============================


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"{path}: JSON 배열이어야 한다(got {type(raw).__name__})")
    return raw


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hash_or_missing(path: Path) -> str:
    return sha256_file(path) if path.exists() else "MISSING"


def canonical_dumps(row: dict[str, Any]) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True)


def write_jsonl_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    """`data/academyinfo_work/2025/*.jsonl` 관례와 같은 정렬된 UTF-8 JSONL. 임시
    경로에 전부 쓴 뒤 `Path.replace()`로 한 번에 교체한다(지시서 §8 "임시 경로에
    완성 후 원자적 교체") — 중간에 실패해도 기존 파일이 절반만 덮이지 않는다."""

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(canonical_dumps(row) + "\n")
    tmp.replace(path)


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(path)


# ============================== 입력 로딩 ==============================


@dataclass
class DryRunInputs:
    survey_year: int
    departments: list[dict[str, Any]]
    classification_by_department: dict[str, dict[str, Any]]
    groups_by_id: dict[str, CanonicalMajorGroupDraft]
    bridge_entries_by_group: dict[str, list[Any]]
    bridge_mapping_reviews: dict[str, CanonicalMajorGroupBridgeReview]
    bridge_scope_reviews: dict[str, CanonicalMajorGroupBridgeScopeReview]
    # 2026-08-24 지시서(a/academyinfo-review-ui-p1-nce 정본 채택) — Key를
    # candidate_id(P1)/official_middle_series_code(N.C.E)로 통일했다. 검수 UI의
    # PATCH Endpoint가 저장하는 파일과 정확히 같은 Key 규칙이라, 사람이 UI에서
    # 저장한 결과를 이 Dry Run이 그대로 소비할 수 있다.
    p1_draft_by_candidate_id: dict[str, AcademyInfoP1ClassificationEntry]
    p1_draft_by_department_id: dict[str, AcademyInfoP1ClassificationEntry]
    p1_reviews: dict[str, AcademyInfoP1ClassificationReview]
    nce_clusters_by_code: dict[str, AcademyInfoNceMiddleSeriesClusterEntry]
    nce_middle_series_code_by_department: dict[str, str]
    nce_reviews: dict[str, AcademyInfoNceMiddleSeriesReview]
    url_audit_by_department: dict[str, dict[str, Any]]
    service_major_ids: frozenset[str]
    input_hashes: dict[str, str] = field(default_factory=dict)


class MissingRequiredInputError(RuntimeError):
    """필수 생성 입력(정규화·분류 결과)이 없을 때 — 종료 코드 2로 이어진다. 이
    Dry Run은 입력이 없다고 0건짜리 결과를 만들지 않는다(§5 "0건이 나오더라도
    정상일 수 있다"는 건 계산된 0건을 말하지, 계산을 못 한 상태와는 다르다)."""


def _department_url_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (row.get("university_name") or "", row.get("department_name") or "", row.get("college_name") or "")


def load_inputs(
    *,
    data_dir: Path,
    survey_year: int,
    reviews_dir: Path | None = None,
    group_draft_path: Path | None = None,
    bridge_draft_path: Path | None = None,
    small_series_code_table_path: Path | None = None,
    canonical_majors_path: Path | None = None,
    bridge_mapping_review_path: Path | None = None,
    bridge_scope_review_path: Path | None = None,
    p1_packet_path: Path | None = None,
    p1_review_path: Path | None = None,
    nce_clusters_path: Path | None = None,
    nce_review_path: Path | None = None,
    url_audit_path: Path | None = None,
    normalized_path: Path | None = None,
    classification_path: Path | None = None,
    out_of_scope_path: Path | None = None,
) -> DryRunInputs:
    work_dir = data_dir / "academyinfo_work" / str(survey_year)
    reviews = reviews_dir or (data_dir / "reviews")

    normalized_path = normalized_path or (work_dir / "departments.normalized.jsonl")
    classification_path = classification_path or (work_dir / "classification_results.jsonl")
    out_of_scope_path = out_of_scope_path or (work_dir / "out_of_recommendation_scope.jsonl")

    input_hashes = {
        "departments.normalized.jsonl": hash_or_missing(normalized_path),
        "classification_results.jsonl": hash_or_missing(classification_path),
        "out_of_recommendation_scope.jsonl": hash_or_missing(out_of_scope_path),
    }

    if not normalized_path.exists():
        raise MissingRequiredInputError(f"정규화 결과가 없다: {normalized_path}")
    if not classification_path.exists():
        raise MissingRequiredInputError(f"분류 결과가 없다: {classification_path}")

    departments = read_jsonl(normalized_path)
    by_department_id = {row["department_id"]: row for row in departments}
    # 야간·원격 학과는 departments.normalized.jsonl에 아예 없다(정규화 단계에서
    # out_of_recommendation_scope.jsonl에만 보존한다) — 있으면 합쳐서 본다.
    for row in read_jsonl(out_of_scope_path):
        by_department_id.setdefault(row["department_id"], row)
    departments = sorted(by_department_id.values(), key=lambda r: r["department_id"])

    classification_rows = read_jsonl(classification_path)
    classification_by_department = {row["department_id"]: row for row in classification_rows}

    try:
        groups = load_canonical_major_groups_draft(group_draft_path)
    except Exception as exc:  # noqa: BLE001 — Fail-Fast를 그대로 전파하되 원인을 남긴다.
        raise MissingRequiredInputError(f"42개 Canonical Major Group Draft 로딩 실패: {exc}") from exc
    groups_by_id = {g.canonical_major_id: g for g in groups}

    try:
        bridge_report = load_canonical_major_group_bridge(
            bridge_draft_path,
            group_draft_path=group_draft_path,
            majors_path=canonical_majors_path,
            small_series_code_table_path=small_series_code_table_path,
        )
    except BridgeValidationError as exc:
        raise MissingRequiredInputError(f"Bridge Mapping/Scope 로딩·검증 실패: {exc}") from exc
    bridge_entries_by_group: dict[str, list[Any]] = {}
    for entry in bridge_report.entries:
        bridge_entries_by_group.setdefault(entry.canonical_major_group_id, []).append(entry)

    bridge_mapping_review_path = bridge_mapping_review_path or (
        reviews / "canonical_major_group_bridge_review_status.json"
    )
    bridge_mapping_reviews = {
        bridge_review_key(row["canonical_major_group_id"], row.get("canonical_major_id")):
            CanonicalMajorGroupBridgeReview.model_validate(row)
        for row in read_json_list(bridge_mapping_review_path)
    }
    input_hashes["bridge_mapping_review"] = hash_or_missing(bridge_mapping_review_path)

    bridge_scope_review_path = bridge_scope_review_path or (
        reviews / "canonical_major_group_bridge_scope_review_status.jsonl"
    )
    bridge_scope_reviews = {
        bridge_review_key(row["canonical_major_group_id"], row.get("canonical_major_id")):
            CanonicalMajorGroupBridgeScopeReview.model_validate(row)
        for row in read_jsonl(bridge_scope_review_path)
    }
    input_hashes["bridge_scope_review"] = hash_or_missing(bridge_scope_review_path)

    # 2026-08-24 지시서(a/academyinfo-review-ui-p1-nce 정본 채택) — P1은 검수 UI가
    # 쓰는 바로 그 Loader/Store를 그대로 재사용한다(candidate_id 키, .jsonl 파일,
    # Fail-Fast 중복 Key 검증까지 전부 그 Store가 이미 한다 — 이 Dry Run이 따로
    # 다시 구현하지 않는다). Draft 패킷(374행)도 함께 읽어야 한다 — 검수 파일
    # 자체에는 candidate_canonical_major_ids/judgment_evidence_sufficient가 없어서
    # (그 값은 원본 패킷에만 있다) APPROVE_PROPOSED_CANDIDATE 조건을 재검증하려면
    # 원본 행이 필요하다.
    p1_packet_path = p1_packet_path or DEFAULT_P1_PACKET_PATH
    if not p1_packet_path.exists():
        raise MissingRequiredInputError(f"P1 분류 REVIEW Draft 패킷이 없다: {p1_packet_path}")
    p1_draft_entries = load_p1_classification_packet(p1_packet_path)
    p1_draft_by_candidate_id = {e.candidate_id: e for e in p1_draft_entries}
    p1_draft_by_department_id = {e.department_id: e for e in p1_draft_entries}
    input_hashes["p1_classification_packet"] = hash_or_missing(p1_packet_path)

    p1_review_path = p1_review_path or default_p1_review_path()
    p1_reviews = load_p1_review_entries_by_key(p1_review_path)
    input_hashes["p1_review"] = hash_or_missing(p1_review_path)

    # N.C.E도 마찬가지로 검수 UI의 정본 Loader/Store를 그대로 쓴다
    # (official_middle_series_code 키). `AcademyInfoNceMiddleSeriesReview`에는
    # "이 전공군을 확정 승인한다"는 필드 자체가 없다 — ACCEPT_GROUP_AS_REVIEW_
    # CANDIDATE는 구조적으로 어떤 department_id도 resolved_canonical_major_group_id
    # 로 이어줄 수 없다(지시서 §7 "모든 N.C.E 행은 별도 학과 단위 승인 전까지
    # 차단" — evaluate_department()가 이 Gate를 무조건 막는 근거이자, "42개 Group
    # 임의 추가" 위험 자체가 이 Schema에서 원천적으로 사라졌다는 뜻이기도 하다).
    nce_clusters_path = nce_clusters_path or DEFAULT_NCE_CLUSTER_PATH
    if not nce_clusters_path.exists():
        raise MissingRequiredInputError(f"N.C.E 중계열 클러스터 Draft가 없다: {nce_clusters_path}")
    nce_cluster_entries = load_nce_middle_series_clusters(nce_clusters_path)
    nce_clusters_by_code = {c.official_middle_series_code: c for c in nce_cluster_entries}
    nce_middle_series_code_by_department: dict[str, str] = {}
    for cluster in nce_cluster_entries:
        for member in cluster.members:
            nce_middle_series_code_by_department[member.department_id] = cluster.official_middle_series_code
    input_hashes["nce_clusters"] = hash_or_missing(nce_clusters_path)

    nce_review_path = nce_review_path or default_nce_review_path()
    nce_reviews = load_nce_review_entries_by_key(nce_review_path)
    input_hashes["nce_review"] = hash_or_missing(nce_review_path)

    url_audit_path = url_audit_path or (work_dir / "department_url_scope_audit.jsonl")
    url_audit_by_key = {_department_url_key(row): row for row in read_jsonl(url_audit_path)}
    url_audit_by_department: dict[str, dict[str, Any]] = {}
    for row in departments:
        audit = url_audit_by_key.get(_department_url_key(row))
        if audit is not None:
            url_audit_by_department[row["department_id"]] = audit
    input_hashes["department_url_scope_audit"] = hash_or_missing(url_audit_path)

    majors = load_canonical_majors(canonical_majors_path or (data_dir / "master" / "canonical_majors.jsonl"))
    service_major_ids = frozenset(m.major_id for m in majors)

    return DryRunInputs(
        survey_year=survey_year,
        departments=departments,
        classification_by_department=classification_by_department,
        groups_by_id=groups_by_id,
        bridge_entries_by_group=bridge_entries_by_group,
        bridge_mapping_reviews=bridge_mapping_reviews,
        bridge_scope_reviews=bridge_scope_reviews,
        p1_draft_by_candidate_id=p1_draft_by_candidate_id,
        p1_draft_by_department_id=p1_draft_by_department_id,
        p1_reviews=p1_reviews,
        nce_clusters_by_code=nce_clusters_by_code,
        nce_middle_series_code_by_department=nce_middle_series_code_by_department,
        nce_reviews=nce_reviews,
        url_audit_by_department=url_audit_by_department,
        service_major_ids=service_major_ids,
        input_hashes=input_hashes,
    )


# ============================== Gate 계산 ==============================


def _validated_department_url(row: dict[str, Any], candidate_url: str) -> str | None:
    """`Department.department_url`의 기존 검증(§18 — http/https만, API Key 쿼리
    파라미터 금지, 대학알리미 OpenAPI 호출 URL 금지)을 그대로 재사용한다. 새
    URL 검증 규칙을 다시 만들지 않는다(지시서 §7 "기존 Department URL 정책 재사용"
    과 같은 원칙)."""

    try:
        department = Department(
            department_id=row["department_id"],
            university_name=row.get("university_name") or "?",
            region=row.get("region") or "",
            department_name=row.get("department_name") or "?",
            college_name=row.get("college_name") or "?",
            department_status=row.get("department_status") or "EXISTING",
            source_svy_year=int(row.get("source_svy_year") or 0),
            source_url=row.get("source_url") or "https://academyinfo.go.kr",
            department_url=candidate_url,
        )
    except Exception:  # noqa: BLE001 — 검증 실패는 "이 URL은 못 쓴다"는 뜻이지 Dry Run을 죽이지 않는다.
        return None
    return department.department_url


def evaluate_department(row: dict[str, Any], inputs: DryRunInputs) -> dict[str, Any]:
    department_id = row["department_id"]
    reasons: set[str] = set()
    resolved_group_id: str | None = None
    resolved_major_id: str | None = None

    if row.get("department_status") not in ("EXISTING", "NEW"):
        reasons.add("BLOCKED_INACTIVE_STATUS")

    in_scope = row.get("recommendation_scope") == "IN_RECOMMENDATION_SCOPE"
    if not in_scope:
        exclusion_reason = row.get("exclusion_reason")
        if exclusion_reason in _NIGHT_REMOTE_EXCLUSION_REASONS:
            reasons.add("BLOCKED_NIGHT_OR_REMOTE")
        elif exclusion_reason == "CONTRACT_DEPARTMENT":
            reasons.add("BLOCKED_CONTRACT_DEPARTMENT")
        else:
            reasons.add("BLOCKED_OUT_OF_RECOMMENDATION_SCOPE")

    if int(row.get("duplicate_group_size") or 1) > 1:
        reasons.add("BLOCKED_DUPLICATE_ID")

    has_basic_lineage = bool(row.get("source_record_id")) and bool(row.get("schl_id"))
    has_official_major_id = bool(row.get("source_schl_mjr_id")) or bool(row.get("source_mjr_id"))
    if not has_basic_lineage or not has_official_major_id:
        reasons.add("BLOCKED_MISSING_LINEAGE")

    nce_middle_series_code: str | None = None
    nce_review_decision: str | None = None
    p1_candidate_id: str | None = None
    p1_review_decision: str | None = None

    classification_row = inputs.classification_by_department.get(department_id) if in_scope else None
    if in_scope:
        if classification_row is None:
            reasons.add("BLOCKED_MISSING_CLASSIFICATION")
        else:
            eligibility_status = classification_row.get("eligibility_status")
            if eligibility_status == "EXCLUDED_ARTS_SPORTS":
                reasons.add("BLOCKED_ARTS_RECOMMENDATION")
            elif eligibility_status == "REVIEW_REQUIRED":
                # 2026-08-24 지시서(a/academyinfo-review-ui-p1-nce) §6 — "APPROVE_
                # PROPOSED_CANDIDATE만 조건부 통과, 나머지 Decision은 모두 차단".
                # 검수 UI의 PATCH가 이미 저장 시점에 p1_approve_eligible()로
                # 막았어도(§1), 이 파일이 그 파일을 그대로 신뢰하지 않고
                # p1_approve_eligible()을 원본 Draft 행에 다시 적용해 재확인한다
                # (Bridge Scope의 "Schema 우회 대비 Service 방어 검증"과 같은 원칙 —
                # 검수 파일이 외부에서 수동으로 손상됐어도 이 Gate가 막는다).
                p1_draft = inputs.p1_draft_by_department_id.get(department_id)
                if p1_draft is None:
                    reasons.add("BLOCKED_P1_REVIEW_UNRESOLVED")
                else:
                    p1_candidate_id = p1_draft.candidate_id
                    p1_review = inputs.p1_reviews.get(p1_candidate_id)
                    p1_review_decision = p1_review.decision if p1_review is not None else "TBD"
                    approve_and_eligible = (
                        p1_review_decision == "APPROVE_PROPOSED_CANDIDATE"
                        and p1_approve_eligible(p1_draft, inputs.service_major_ids)
                    )
                    if not approve_and_eligible:
                        reasons.add("BLOCKED_P1_REVIEW_UNRESOLVED")

            mapping_status = classification_row.get("mapping_status")
            if mapping_status == "AUTO_CANDIDATE":
                candidates = classification_row.get("candidate_canonical_major_ids") or []
                if len(candidates) == 1:
                    resolved_group_id = candidates[0]
                elif len(candidates) == 0:
                    reasons.add("BLOCKED_NO_SERVICE_CANONICAL_MAJOR")
                else:
                    reasons.add("BLOCKED_AMBIGUOUS_SERVICE_CANONICAL_MAJOR")
            elif mapping_status == "REVIEW_REQUIRED":
                reasons.add("BLOCKED_CLASSIFICATION_REVIEW")
            elif mapping_status == "UNMAPPED":
                decision_reason = classification_row.get("decision_reason") or ""
                if decision_reason.startswith(_NCE_UNMAPPED_REASON_PREFIX):
                    # 2026-08-24 지시서 §7 — "ACCEPT_GROUP_AS_REVIEW_CANDIDATE도
                    # 학과 승격 승인이 아니다. 모든 N.C.E 행은 별도 학과 단위 승인
                    # 전까지 차단한다." N.C.E 검수 상태가 무엇이든(TBD든
                    # ACCEPT_GROUP_AS_REVIEW_CANDIDATE든) resolved_group_id를 절대
                    # 채우지 않는다 — 무조건 BLOCKED_NCE_UNRESOLVED다. 클러스터 코드·
                    # 검수 판단은 감사용으로만 출력 행에 남긴다(왜 막혔는지 추적
                    # 가능하도록. §7이 요구한 학과 단위 Gate는 아직 이 저장소에
                    # 없다 — 이 Dry Run이 대신 만들지 않는다).
                    nce_middle_series_code = inputs.nce_middle_series_code_by_department.get(department_id)
                    nce_review = inputs.nce_reviews.get(nce_middle_series_code) if nce_middle_series_code else None
                    nce_review_decision = nce_review.decision if nce_review is not None else "TBD"
                    reasons.add("BLOCKED_NCE_UNRESOLVED")
                else:
                    reasons.add("BLOCKED_NO_SERVICE_CANONICAL_MAJOR")
            else:
                reasons.add("BLOCKED_NO_SERVICE_CANONICAL_MAJOR")

    if resolved_group_id is not None:
        group = inputs.groups_by_id.get(resolved_group_id)
        if group is None or group.review_status != "approved":
            reasons.add("BLOCKED_GROUP_DRAFT")

        entries = inputs.bridge_entries_by_group.get(resolved_group_id, [])
        evidenced = [e for e in entries if e.mapping_status == "EVIDENCED"]
        excluded_entries = [e for e in entries if e.mapping_status == "EXCLUDED_RECOMMENDATION"]

        if excluded_entries:
            if resolved_group_id in ARTS_EXCLUDED_GROUP_IDS:
                reasons.add("BLOCKED_ARTS_RECOMMENDATION")
            else:
                reasons.add("BLOCKED_BRIDGE_EXCLUDED_RECOMMENDATION")
        elif len(evidenced) == 1:
            entry = evidenced[0]
            resolved_major_id = entry.canonical_major_id
            key = bridge_review_key(resolved_group_id, resolved_major_id)

            mapping_review = inputs.bridge_mapping_reviews.get(key)
            if mapping_review is None or mapping_review.reviewer_1_status != "APPROVE":
                reasons.add("BLOCKED_BRIDGE_MAPPING_REVIEW")

            scope_review = inputs.bridge_scope_reviews.get(key)
            if scope_review is None or scope_review.reviewer_1_status != "APPROVE":
                reasons.add("BLOCKED_BRIDGE_SCOPE_REVIEW")

            dept_small_series = (classification_row or {}).get("official_small_series_code")
            if entry.scope_type == "INCLUDED_SMALL_SERIES_ONLY":
                if dept_small_series not in entry.included_small_series_codes:
                    reasons.add("BLOCKED_OUTSIDE_SMALL_SERIES_SCOPE")
            elif entry.scope_type == "DEPARTMENT_REVIEW_REQUIRED":
                reasons.add("BLOCKED_OUTSIDE_SMALL_SERIES_SCOPE")
            # FULL_GROUP: classify()가 Group의 공식 소계열로만 후보를 만들었으므로
            # 구조적으로 항상 포함된다 — 별도 확인이 필요 없다.

            if resolved_major_id in EXCLUDED_RECOMMENDATION_MAJOR_IDS:
                reasons.add("BLOCKED_ARTS_RECOMMENDATION")
            elif resolved_major_id not in inputs.service_major_ids:
                reasons.add("BLOCKED_NO_SERVICE_CANONICAL_MAJOR")
        elif len(evidenced) == 0:
            # 2026-08-24 지시서 §8 — "Bridge 후보 없음"과 "복수 후보"를 구분한다.
            # 0개: 이 Group을 어떤 서비스 Major에도 연결한 EVIDENCED 행이 없다
            # (UNMAPPED 전용 행만 있거나 아직 Bridge가 이 Group을 다루지 않았다).
            reasons.add("BLOCKED_NO_SERVICE_CANONICAL_MAJOR")
        else:
            # 2개 이상: 이 Dry Run은 어느 Major가 맞는지 자동으로 고르지 않는다
            # (모듈 docstring "설계상 명시적 한계" 참고) — "후보가 없다"와는 다른
            # 사유라 따로 구분해 사람이 무엇을 검토해야 하는지 명확히 남긴다.
            reasons.add("BLOCKED_AMBIGUOUS_SERVICE_CANONICAL_MAJOR")

    resolved_department_url: str | None = None
    audit_row = inputs.url_audit_by_department.get(department_id)
    if audit_row is not None:
        if audit_row.get("contains_api_key"):
            reasons.add("BLOCKED_URL_POLICY")
        else:
            scope = audit_row.get("department_url_scope")
            candidate_url = audit_row.get("department_url")
            validated_url = _validated_department_url(row, candidate_url) if candidate_url else None
            if candidate_url and validated_url is None:
                reasons.add("BLOCKED_URL_POLICY")
            elif scope in ("department", "college"):
                resolved_department_url = resolve_department_url_for_promotion(scope, validated_url)

    status = "READY_FOR_PROMOTION" if not reasons else "BLOCKED"
    return {
        "department_id": department_id,
        "university_name": row.get("university_name"),
        "department_name": row.get("department_name"),
        "college_name": row.get("college_name"),
        "department_status": row.get("department_status"),
        "status": status,
        "blocked_reasons": sorted(reasons),
        "resolved_canonical_major_group_id": resolved_group_id,
        "resolved_canonical_major_id": resolved_major_id,
        "resolved_department_url": resolved_department_url,
        "official_small_series_code": (classification_row or {}).get("official_small_series_code"),
        # 2026-08-24 지시서 §9 — 지금 계산 가능한 것은 "이 행 자체가 안정적인
        # 원본 식별자를 갖고 있는가"뿐이다. 실제 연도 간 대조 코드가 생기기 전까지
        # 이 값은 항상 ROW_IDENTITY_ONLY다 — CROSS_YEAR_LINEAGE_VERIFIED를 여기서
        # 만드는 분기 자체가 없다(테스트가 이 사실을 직접 확인한다).
        "lineage_level": LINEAGE_LEVEL_ROW_IDENTITY_ONLY,
        # 감사용 참고 필드 — §7 "N.C.E는 절대 승격 승인이 아님"의 증거를 출력에도
        # 남긴다. None이 아니어도(예: nce_review_decision="ACCEPT_GROUP_AS_REVIEW_
        # CANDIDATE") blocked_reasons에는 항상 BLOCKED_NCE_UNRESOLVED가 있다 —
        # 이 두 필드가 승격 여부에 영향을 준 적이 없다.
        "p1_candidate_id": p1_candidate_id,
        "p1_review_decision": p1_review_decision,
        "nce_middle_series_code": nce_middle_series_code,
        "nce_review_decision": nce_review_decision,
        "survey_year": inputs.survey_year,
    }


# ============================== 요약/Manifest ==============================


def build_summary(rows: list[dict[str, Any]], inputs: DryRunInputs) -> dict[str, Any]:
    ready = [r for r in rows if r["status"] == "READY_FOR_PROMOTION"]
    blocked = [r for r in rows if r["status"] == "BLOCKED"]

    reason_counts: dict[str, int] = {reason: 0 for reason in ALL_BLOCKED_REASONS}
    for row in blocked:
        for reason in row["blocked_reasons"]:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    # 현재 검수 상태(전부 TBD/미존재) 때문에만 막힌 건 — Group Draft·Bridge Mapping·
    # Bridge Scope·P1·N.C.E 검수 관련 사유만 걸리고 다른 구조적 사유가 없는 행.
    review_only_reasons = {
        "BLOCKED_GROUP_DRAFT", "BLOCKED_BRIDGE_MAPPING_REVIEW", "BLOCKED_BRIDGE_SCOPE_REVIEW",
        "BLOCKED_P1_REVIEW_UNRESOLVED", "BLOCKED_NCE_UNRESOLVED", "BLOCKED_CLASSIFICATION_REVIEW",
    }
    blocked_only_by_review_state = sum(
        1 for r in blocked if set(r["blocked_reasons"]) and set(r["blocked_reasons"]).issubset(review_only_reasons)
    )

    return {
        "survey_year": inputs.survey_year,
        "evaluated_department_count": len(rows),
        "ready_for_promotion_count": len(ready),
        "blocked_count": len(blocked),
        "blocked_reason_counts": reason_counts,
        "blocked_only_by_current_review_state_count": blocked_only_by_review_state,
        "note": (
            "0건이 정상일 수 있다 — Canonical Major Group Draft 42개가 전부 review_status="
            "'draft'이고 Bridge Scope/P1/N.C.E 검수 정본이 아직 없어(Fail-Closed) 현재 "
            "검수 상태로는 어떤 학과도 자동 승격되지 않는다. Master·API는 이 Dry Run으로 "
            "바뀌지 않는다."
        ),
    }


def build_summary_markdown(summary: dict[str, Any], rows: list[dict[str, Any]], regenerate_cmd: str) -> str:
    lines = [
        f"# 전국 학과 Master 승격 Dry Run — {summary['survey_year']}년",
        "",
        "**이 문서는 계산 결과 보고서다. `data/master/departments.jsonl`·공개 API는",
        "바뀌지 않았다.**",
        "",
        "## 요약",
        "",
        f"- 평가 대상: {summary['evaluated_department_count']}건",
        f"- READY_FOR_PROMOTION: {summary['ready_for_promotion_count']}건",
        f"- BLOCKED: {summary['blocked_count']}건",
        f"- 현재 검수 상태(TBD/미존재)만으로 막힌 건: {summary['blocked_only_by_current_review_state_count']}건",
        "",
        "## 차단 사유별 개수",
        "",
        "| 사유 | 개수 |",
        "|---|---|",
    ]
    for reason, count in sorted(summary["blocked_reason_counts"].items()):
        lines.append(f"| {reason} | {count} |")

    lines += ["", "## 상태별 표본(최대 10건)", ""]
    ready_samples = [r for r in rows if r["status"] == "READY_FOR_PROMOTION"][:10]
    blocked_samples = [r for r in rows if r["status"] == "BLOCKED"][:10]
    lines.append("### READY_FOR_PROMOTION 표본")
    lines.append("")
    if ready_samples:
        for r in ready_samples:
            lines.append(
                f"- {r['department_id']} — {r['university_name']} {r['department_name']} → "
                f"{r['resolved_canonical_major_id']}"
            )
    else:
        lines.append("- (없음)")
    lines.append("")
    lines.append("### BLOCKED 표본")
    lines.append("")
    if blocked_samples:
        for r in blocked_samples:
            lines.append(
                f"- {r['department_id']} — {r['university_name']} {r['department_name']}: "
                f"{', '.join(r['blocked_reasons'])}"
            )
    else:
        lines.append("- (없음)")

    lines += ["", "## 재생성 명령", "", "```", regenerate_cmd, "```", ""]
    return "\n".join(lines) + "\n"


# ============================== main ==============================


def main(argv: list[str] | None = None) -> int:
    use_utf8_stdout()
    parser = argparse.ArgumentParser(description="전국 학과 → Master 승격 Fail-Closed Dry Run")
    parser.add_argument("--survey-year", type=int, default=2025)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument(
        "--output-dir", type=Path, default=None,
        help="기본값: <data-dir>/academyinfo_work/<survey-year>/promotion_dry_run",
    )
    args = parser.parse_args(argv)

    output_dir = args.output_dir or (
        args.data_dir / "academyinfo_work" / str(args.survey_year) / "promotion_dry_run"
    )

    try:
        inputs = load_inputs(data_dir=args.data_dir, survey_year=args.survey_year)
    except MissingRequiredInputError as exc:
        print(f"필수 입력이 없어 Dry Run을 계산할 수 없습니다: {exc}", file=sys.stderr)
        print("기존 Dry Run 산출물은 그대로 둡니다(아무것도 쓰지 않았습니다).", file=sys.stderr)
        return 2

    rows = [evaluate_department(row, inputs) for row in inputs.departments]
    rows.sort(key=lambda r: r["department_id"])

    candidates = [r for r in rows if r["status"] == "READY_FOR_PROMOTION"]
    blocked = [r for r in rows if r["status"] == "BLOCKED"]
    summary = build_summary(rows, inputs)

    regenerate_cmd = (
        f"PYTHONPATH=. ./.venv/bin/python scripts/career_build_national_department_promotion_dry_run.py "
        f"--survey-year {args.survey_year} --data-dir {args.data_dir}"
    )
    summary_md = build_summary_markdown(summary, rows, regenerate_cmd)

    candidates_path = output_dir / "promotion_candidates.jsonl"
    blocked_path = output_dir / "promotion_blocked.jsonl"
    summary_path = output_dir / "promotion_summary.json"
    summary_md_path = output_dir / "promotion_summary.md"
    manifest_path = output_dir / "promotion_manifest.json"

    # 전부 계산이 끝난 뒤에만 디스크에 쓴다 — 계산 중 예외가 나면 아무 파일도 건드리지
    # 않는다(지시서 §8 "중간 실패 시 기존 Dry Run 산출물 보존").
    write_jsonl_atomic(candidates_path, candidates)
    write_jsonl_atomic(blocked_path, blocked)
    write_text_atomic(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    write_text_atomic(summary_md_path, summary_md)

    manifest = {
        "survey_year": args.survey_year,
        # 생성 시각을 넣지 않는다 — 같은 입력이면 항상 같은 Byte가 나와야 한다(§8).
        "input_hashes": dict(sorted(inputs.input_hashes.items())),
        "output_hashes": {
            "promotion_candidates.jsonl": sha256_file(candidates_path),
            "promotion_blocked.jsonl": sha256_file(blocked_path),
            "promotion_summary.json": sha256_file(summary_path),
            "promotion_summary.md": sha256_file(summary_md_path),
        },
        "counts": {
            "evaluated": len(rows),
            "ready_for_promotion": len(candidates),
            "blocked": len(blocked),
        },
        "auto_approved_rows": 0,
        "note": (
            "auto_approved_rows가 0이라는 것이 이 Dry Run이 어떤 검수도 자동으로 채우거나 "
            "승인하지 않았다는 증명이다. data/master/departments.jsonl과 공개 API는 이 "
            "실행으로 전혀 바뀌지 않았다."
        ),
    }
    write_text_atomic(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    print(f"승격 Dry Run 완료 — 조사연도 {args.survey_year}")
    print(f"  평가 대상 {summary['evaluated_department_count']}건")
    print(f"  READY_FOR_PROMOTION {summary['ready_for_promotion_count']}건")
    print(f"  BLOCKED {summary['blocked_count']}건")
    print(f"  현재 검수 상태만으로 막힌 건 {summary['blocked_only_by_current_review_state_count']}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
