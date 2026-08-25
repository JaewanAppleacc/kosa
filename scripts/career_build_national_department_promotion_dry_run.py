"""전국 학과 → `data/master/departments.jsonl` 승격 Dry Run — c/national-master-promotion-dry-run.

**이 스크립트는 실제 Master(`data/master/departments.jsonl`)도 공개 API/Mock도 절대
바꾸지 않는다.** 어떤 학과가 어떤 이유로 승격 가능하거나 차단되는지 **계산만** 한다
(Fail-Closed — 검수 파일이 없으면 자동 승인하지 않고 해당 Gate를 BLOCKED로 계산한다).

## 2026-08-25 지시서(c/national-departments-38-majors) 변경 요약

기존 8개 서비스 Major(`data/master/canonical_majors.jsonl`)에만 연결되던 Group→Major
Bridge를 39개 Service Canonical Major v2(`data/master/service_canonical_majors_v2.jsonl`
FULL_GROUP 38 + DEPARTMENT_LEVEL_ONLY `hci_ux` 1) + 그 42개 Group 전부의 확정 Bridge
(`data/master/canonical_major_group_to_service_major_v2.jsonl`, ACTIVE 38 + EXCLUDED_
RECOMMENDATION 4, Group 누락 0)로 바꾼다. 이 v2 Bridge는 **이미 확정된 정본**이라
(Schema에 `reviewer_1_status`/`TBD` 같은 필드 자체가 없다) 옛 Bridge Mapping/Scope
사람 검수 두 단계(`canonical_major_group_bridge_review_status.json`/
`..._scope_review_status.jsonl`, Key마다 EVIDENCED 후보가 몇 개인지 세던 방식)가 전부
사라진다 — Group 하나당 정확히 한 행(ACTIVE엔 `service_major_id` 필수, EXCLUDED_
RECOMMENDATION엔 금지)이라 "후보 0개/2개 이상" 모호함 자체가 구조적으로 없다.
`hci_ux`는 어느 Group의 "기본 서비스 Major"도 아니므로(source_group_ids는 참고용 출처일
뿐 소속 선언이 아니다) 이 Group 기반 파이프라인으로는 절대 도달하지 않는다 — 이번
라운드는 그 개별 학과 단위 판정을 하지 않으므로 hci_ux는 항상 0건이다(지시서 "hci_ux는
DEPARTMENT_LEVEL_ONLY" "computer_science Group 전체를 hci_ux로 연결 금지" "fine_arts_
design 자동 연결 금지" 요구를 이 구조 자체가 만족한다 — 별도 코드가 필요 없다).

## 2026-08-25 지시서(a/final-integration-master-promotion) §3/§4 변경 요약

1. **행 유일 Key가 `department_id`에서 `offering_id`로 바뀌었다**
   (`src.ids.generate_offering_id(schl_id, source_schl_mjr_id)`, Offering Identity v2).
   기존 16 Group·32행 identity-key 충돌(같은 department_id, 다른 실제 편제)이 서로 다른
   offering_id를 받아 더 이상 하나로 뭉개지지 않는다. `department_id`는 `old_department_id`
   로, 옛 표시명 그룹은 `display_group_id`로 출력에 남는다(UI 그룹화 전용, 유일 키 아님).
2. **Canonical Major Group 승인 정본이 Draft의 정적 `review_status`에서
   `canonical_major_group_review_status.jsonl`의 `decision`으로 바뀌었다** — 그 Store가
   없거나 이 Group 항목이 없으면 여전히 Fail-Closed(`BLOCKED_GROUP_DRAFT`).
3. **P1/N.C.E가 실제 검수 완료 상태를 반영한다.** 검토가 끝났지만 이번 1차 승격 범위
   밖으로 결론난 행(P1의 NEEDS_OFFICIAL_CURRICULUM/KEEP_UNMAPPED, N.C.E의
   REQUIRE_DEPARTMENT_LEVEL_REVIEW, 그리고 이번 연도 분류가 P1/N.C.E로 표시했지만 374/584
   행 검수 범위 밖인 행)는 새 사유 `BLOCKED_EXCLUDED_FROM_INITIAL_PROMOTION`으로 집계한다
   (정책상 정상 차단 — TBD/HOLD 같은 진짜 미결과 구분한다). N.C.E의
   ACCEPT_GROUP_AS_REVIEW_CANDIDATE는 그 클러스터의 후보 Group에 이미 Bridge Mapping이
   승인한 EVIDENCED 서비스 Major가 **정확히 1개**일 때만(그 뒤로도 AUTO_CANDIDATE와 완전히
   같은 Group/Bridge/Scope Gate를 통과해야 한다 — 추측 Mapping 없음) READY로 이어질 수
   있다 — 그 외에는 여전히 차단된다("N.C.E로 분류된 학과는 절대 READY로 풀리지 않는다"던
   이전 설명은 이제 정확하지 않다, 이 조건부 예외가 그 이후 추가됐다).
4. **계약학과·산업체위탁 제외가 넓어졌다** — 기존 `exclusion_reason==CONTRACT_DEPARTMENT`
   (정규화 단계가 좁게 잡은 6건)에 더해, 각 행의 실제 `major_character_name`(Offering
   Identity v2가 보존)이 "계약학과"/"산업체위탁"이면 직접 `BLOCKED_CONTRACT_DEPARTMENT`로
   막는다(실측: 154건 추가 검출).

## 입력

- `data/academyinfo_work/<year>/departments.normalized.jsonl` (필수 — 없으면 종료 코드 2,
  아무것도 쓰지 않는다)
- `data/academyinfo_work/<year>/classification_results.jsonl` (필수 — 위와 동일)
- `data/academyinfo_work/<year>/out_of_recommendation_scope.jsonl` (선택 — 있으면 야간·원격
  학과를 승격 후보 전체 집합에 합친다. `career_normalize_academyinfo.py::normalize()`는 야간·
  원격 학과를 `departments.normalized.jsonl`에 아예 넣지 않고 이 파일에만 남기므로, 이 파일이
  없으면 야간·원격 차단 사유를 계산할 수 없다 — 없어도 실패하지 않지만 그만큼 덜 본다)
- `data/canonical_major_groups.draft.jsonl` (42개 Canonical Major Group Draft)
- `data/master/service_canonical_majors_v2.jsonl` (39개 Service Canonical Major v2 — 38
  FULL_GROUP ACTIVE + `hci_ux` DEPARTMENT_LEVEL_ONLY ACTIVE)
- `data/master/canonical_major_group_to_service_major_v2.jsonl` (42개 Group 전부의 확정
  Bridge — ACTIVE 38 + EXCLUDED_RECOMMENDATION 4, Group 누락 0. 이미 확정된 정본이라
  이 파일 자체에는 사람 검수 대기 상태가 없다)
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
Group 검수 승인 · Service Canonical Major v2 Bridge가 이 Group을 ACTIVE로 확정(EXCLUDED_
RECOMMENDATION이면 예체능 제외) · 39개 Service Canonical Major v2(ACTIVE) 중 하나로
연결 · 중복 offering_id 없음 · 필수 대학알리미 Lineage 존재 · URL 정책 통과.

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
- `BLOCKED_URL_POLICY`: URL 감사에서 API Key 포함이 확인됐거나 `Department.department_url`
  자체 검증(§18)을 통과하지 못하는 URL.
- `BLOCKED_AMBIGUOUS_SERVICE_CANONICAL_MAJOR`: `classification_results.jsonl`의
  `mapping_status == "AUTO_CANDIDATE"`가 애초에 후보 Group을 2개 이상 반환하는 경우
  (분류 단계 자체의 모호함 — Group Bridge V2는 Group 하나당 정확히 한 행이라 이 모호함이
  Bridge 단계에서는 더 이상 발생하지 않는다, 아래 참고).

## Group→Service Major Bridge V2는 후보 모호함이 없다

옛 Bridge(`canonical_major_group_bridge.draft.jsonl`, `mapping_status` 여러 개 가능)와
달리, `canonical_major_group_to_service_major_v2.jsonl`은 42개 Group 전부가 정확히 한
행만 가진다 — ACTIVE는 `service_major_id` 정확히 1개, EXCLUDED_RECOMMENDATION은 0개.
그래서 "Bridge 후보 0개/2개 이상"이라는 옛 구분 자체가 이 단계에서는 사라졌다(Group 자체가
Bridge에 없는 경우만 방어적으로 `BLOCKED_NO_SERVICE_CANONICAL_MAJOR`로 남는다 — 42개
Group 완전성 불변식이 지켜지는 한 실제로는 발생하지 않아야 한다). 남은 유일한 모호함은
분류(classify) 단계 자체가 "이 학과가 어느 Group인지" 확신하지 못하는 경우
(`BLOCKED_AMBIGUOUS_SERVICE_CANONICAL_MAJOR`, Group 후보 자체가 2개 이상)뿐이다.

## 설계상 명시적 한계(감사 필요 항목)

- `BLOCKED_MISSING_LINEAGE`는 연도 간 비교 파일(`department_lineage.jsonl`, 직전 연도
  정규화 결과가 있어야만 생성된다 — 조건부)이 아니라, 각 행 자체가 대학알리미 원본
  식별자(`source_record_id`·`schl_id`·`source_schl_mjr_id`/`source_mjr_id`)를 갖고
  있는지로 판정한다. 연도 간 lineage는 선택 입력이 아니고 첫 수집 연도에는 아예 생성되지
  않아, 이를 필수로 삼으면 첫 수집 연도 전체가 영구히 막혀 "필수" 의미가 왜곡된다. 그래서
  각 출력 행의 `lineage_level`은 항상 `"ROW_IDENTITY_ONLY"`다 — 실제 여러 조사연도를
  비교해 같은 학과인지 확인하는 코드(`"CROSS_YEAR_LINEAGE_VERIFIED"`)는 이 저장소에
  아직 없고, 이 파일도 그 값을 만들지 않는다(2026-08-24 지시서 §9).
- N.C.E(공식 소계열 미분류)로 걸린 학과는 N.C.E 검수 상태가 TBD/HOLD/
  INSUFFICIENT_OFFICIAL_EVIDENCE(진짜 미결)나 REQUIRE_DEPARTMENT_LEVEL_REVIEW(검토는
  끝났지만 이번 라운드는 제외)면 여전히 절대 READY_FOR_PROMOTION에 도달하지 않는다.
  유일한 예외는 §3에 적은 대로 `ACCEPT_GROUP_AS_REVIEW_CANDIDATE`이면서 그 클러스터의
  후보 Group 중 실제로 Group 승인·Bridge V2 ACTIVE까지 전부 통과하는 Group이 정확히
  1개인 경우뿐이다(추측 없이 같은 Gate를 그대로 통과해야 한다) — "N.C.E는 절대
  READY로 풀리지 않는다"는 예전 설명은 이제 정확하지 않다(위 §3 참고).
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
from src.ids import generate_display_group_id, generate_offering_id  # noqa: E402
from src.review_ui.academyinfo_p1_classification_review_service import p1_approve_eligible  # noqa: E402
from src.schemas.academyinfo_nce_middle_series_cluster import AcademyInfoNceMiddleSeriesClusterEntry  # noqa: E402
from src.schemas.academyinfo_nce_middle_series_cluster_review import AcademyInfoNceMiddleSeriesReview  # noqa: E402
from src.schemas.academyinfo_p1_classification import AcademyInfoP1ClassificationEntry  # noqa: E402
from src.schemas.academyinfo_p1_classification_candidate_review import AcademyInfoP1ClassificationReview  # noqa: E402
from src.schemas.canonical_major_group import CanonicalMajorGroupDraft  # noqa: E402
from src.schemas.canonical_major_group_review import CanonicalMajorGroupReview  # noqa: E402
from src.schemas.major import Department  # noqa: E402
from src.schemas.service_canonical_major_v2 import CanonicalMajorGroupServiceMajorBridgeV2  # noqa: E402
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
from src.services.canonical_major_group_draft_loader import load_canonical_major_groups_draft  # noqa: E402
from src.services.canonical_major_group_review_store import (  # noqa: E402
    load_canonical_major_group_review_entries_by_key,
)
from src.services.department_url_promotion import resolve_department_url_for_promotion  # noqa: E402
from src.services.service_canonical_major_v2_loader import (  # noqa: E402
    DEFAULT_CANONICAL_MAJOR_GROUP_BRIDGE_V2_PATH,
    DEFAULT_SERVICE_CANONICAL_MAJORS_V2_PATH,
    load_canonical_major_group_to_service_major_bridge_v2,
    load_service_canonical_majors_v2,
)

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
#
# 2026-08-25 지시서(a/final-integration-master-promotion) §3 — 검수가 실제로 끝난
# 항목(P1 EXCLUDE 계열 결정 96/208/69/1건, N.C.E REQUIRE_DEPARTMENT_LEVEL_REVIEW
# 9개)을 "아직 검수 중"인 BLOCKED_P1_REVIEW_UNRESOLVED/BLOCKED_NCE_UNRESOLVED로
# 잘못 집계하지 않기 위해 새 사유를 추가한다 — "검수는 끝났지만 이번 1차 승격
# 범위에서는 제외"라는 뜻이다(정책상 정상 차단, §5 "정상적으로 남을 수 있는 차단").
ALL_BLOCKED_REASONS = (
    "BLOCKED_AMBIGUOUS_SERVICE_CANONICAL_MAJOR",
    "BLOCKED_ARTS_RECOMMENDATION",
    "BLOCKED_CLASSIFICATION_REVIEW",
    "BLOCKED_CONTRACT_DEPARTMENT",
    "BLOCKED_DUPLICATE_ID",
    "BLOCKED_EXCLUDED_FROM_INITIAL_PROMOTION",
    "BLOCKED_GROUP_DRAFT",
    "BLOCKED_INACTIVE_STATUS",
    "BLOCKED_MISSING_CLASSIFICATION",
    "BLOCKED_MISSING_LINEAGE",
    "BLOCKED_NCE_UNRESOLVED",
    "BLOCKED_NIGHT_OR_REMOTE",
    "BLOCKED_NO_SERVICE_CANONICAL_MAJOR",
    "BLOCKED_OUT_OF_RECOMMENDATION_SCOPE",
    "BLOCKED_P1_REVIEW_UNRESOLVED",
    "BLOCKED_URL_POLICY",
)

# P1 Schema의 6개 decision 중 "검토는 끝났지만 이번 라운드는 승격하지 않는다"에
# 해당하는 값들 — TBD/REVISE_CANDIDATE/HOLD(진짜 미결)와 구분한다.
_P1_EXCLUDED_FROM_INITIAL_PROMOTION_DECISIONS = frozenset({"NEEDS_OFFICIAL_CURRICULUM", "KEEP_UNMAPPED"})
_P1_ARTS_DECISIONS = frozenset({"EXCLUDE_ARTS_RECOMMENDATION"})
_P1_UNRESOLVED_DECISIONS = frozenset({"TBD", "REVISE_CANDIDATE", "HOLD"})

# N.C.E Schema의 5개 decision 중 REQUIRE_DEPARTMENT_LEVEL_REVIEW(학과 단위 판단
# 필요)는 "검토는 끝났지만 이번 라운드는 승격하지 않는다"에 해당한다 —
# TBD/HOLD/INSUFFICIENT_OFFICIAL_EVIDENCE(진짜 미결·근거 없음)와 구분한다.
_NCE_UNRESOLVED_DECISIONS = frozenset({"TBD", "HOLD", "INSUFFICIENT_OFFICIAL_EVIDENCE"})

_CONTRACT_MAJOR_CHARACTERS = frozenset({"계약학과", "산업체위탁"})


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
    group_reviews: dict[str, CanonicalMajorGroupReview]
    # 2026-08-25 지시서(c/national-departments-38-majors) — Group 하나당 정확히 한 행
    # (canonical_major_group_id를 Key로 하는 dict, list가 아니다 — 옛 Bridge와 달리
    # 후보가 여럿일 수 없다).
    service_major_bridge_by_group: dict[str, CanonicalMajorGroupServiceMajorBridgeV2]
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
    # 2026-08-25 지시서(a/final-integration-master-promotion) §4 — 행 유일 Key를
    # department_id에서 offering_id로 바꾼다. offering_id_counts는 evaluate_department()
    # 가 BLOCKED_DUPLICATE_ID를 department_id 기반 duplicate_group_size 대신 이
    # 새 Key 기준으로 판정하는 데 쓴다(§4 "기존 16개 identity-key 충돌로 행을
    # 버리지 않음" — offering_id는 설계상 그 16개도 서로 다른 값을 받는다).
    offering_id_counts: dict[str, int] = field(default_factory=dict)
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
    group_review_path: Path | None = None,
    service_canonical_majors_v2_path: Path | None = None,
    canonical_major_group_bridge_v2_path: Path | None = None,
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

    # 2026-08-25 지시서(a/final-integration-master-promotion) §4 — 24,422행 전부에
    # offering_id/display_group_id를 계산해 붙인다(a/offering-identity-v2가 검수한
    # 32행 Packet과 같은 공식(`generate_offering_id(schl_id, source_schl_mjr_id)`)을
    # 그대로 재사용 — 실측 결과 두 계산이 정확히 같은 값을 낸다, 그 32행을 별도
    # 취급하지 않아도 된다는 뜻이다). department_id 자체는 old_department_id로
    # 보존해 Migration Map·기존 분류/N.C.E/URL 감사 파일과의 조인 Key로 계속 쓴다
    # (그 파일들은 Identity v2 이전에 만들어져 department_id 키만 안다).
    offering_id_counts: dict[str, int] = {}
    for row in departments:
        offering_id = generate_offering_id(row["schl_id"], row["source_schl_mjr_id"])
        row["offering_id"] = offering_id
        row["display_group_id"] = generate_display_group_id(
            row["schl_id"], row.get("college_name") or "", row.get("department_name") or "",
        )
        row["old_department_id"] = row["department_id"]
        offering_id_counts[offering_id] = offering_id_counts.get(offering_id, 0) + 1

    classification_rows = read_jsonl(classification_path)
    classification_by_department = {row["department_id"]: row for row in classification_rows}

    try:
        groups = load_canonical_major_groups_draft(group_draft_path)
    except Exception as exc:  # noqa: BLE001 — Fail-Fast를 그대로 전파하되 원인을 남긴다.
        raise MissingRequiredInputError(f"42개 Canonical Major Group Draft 로딩 실패: {exc}") from exc
    groups_by_id = {g.canonical_major_id: g for g in groups}

    # 2026-08-25 지시서 §3 — Group 승인 정본은 Draft의 정적 review_status가 아니라
    # 사람이 실제로 검수 UI에 저장한 이 Store다(canonical_major_group_review_status.
    # jsonl, decision=APPROVE_AS_CLASSIFICATION_GROUP). 파일이 없거나 그 Group의
    # 항목이 없으면 Fail-Closed(빈 dict — evaluate_department()가 "None"으로 취급해
    # BLOCKED_GROUP_DRAFT를 그대로 유지한다).
    #
    # bridge_mapping_review_path/bridge_scope_review_path와 같은 원칙으로 reviews_dir
    # 아래를 기본값으로 쓴다(전역 기본 경로로 조용히 떨어지면, 이 함수를 격리된 tmp
    # reviews_dir로 호출하는 테스트가 실제 data/reviews/를 의도치 않게 읽는다 —
    # a/final-mapping-review-closeout에서 P1/N.C.E가 겪은 것과 같은 격리 버그를
    # 여기서는 처음부터 만들지 않는다).
    group_review_path = group_review_path or (reviews / "canonical_major_group_review_status.jsonl")
    group_reviews = load_canonical_major_group_review_entries_by_key(group_review_path)

    # 2026-08-25 지시서(c/national-departments-38-majors) — 옛 Bridge Mapping/Scope
    # 사람 검수 두 단계를 이미 확정된 Service Canonical Major v2 Bridge로 대체한다(모듈
    # docstring 참고). 이 Loader가 이미 Fail-Fast로 공식 Group 존재·중복 Key·예체능
    # ACTIVE 금지를 강제하므로 여기서 다시 검증하지 않는다.
    service_canonical_majors_v2_path = service_canonical_majors_v2_path or DEFAULT_SERVICE_CANONICAL_MAJORS_V2_PATH
    canonical_major_group_bridge_v2_path = (
        canonical_major_group_bridge_v2_path or DEFAULT_CANONICAL_MAJOR_GROUP_BRIDGE_V2_PATH
    )
    valid_group_ids = frozenset(groups_by_id)
    majors_v2 = load_service_canonical_majors_v2(service_canonical_majors_v2_path, valid_group_ids=valid_group_ids)
    service_major_bridge_by_group = load_canonical_major_group_to_service_major_bridge_v2(
        canonical_major_group_bridge_v2_path
    )
    input_hashes["service_canonical_majors_v2"] = hash_or_missing(service_canonical_majors_v2_path)
    input_hashes["canonical_major_group_to_service_major_v2"] = hash_or_missing(canonical_major_group_bridge_v2_path)

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
    input_hashes["canonical_major_group_review"] = hash_or_missing(group_review_path)

    service_major_ids = frozenset(m.major_id for m in majors_v2 if m.recommendation_status == "ACTIVE")

    return DryRunInputs(
        survey_year=survey_year,
        departments=departments,
        classification_by_department=classification_by_department,
        groups_by_id=groups_by_id,
        group_reviews=group_reviews,
        service_major_bridge_by_group=service_major_bridge_by_group,
        p1_draft_by_candidate_id=p1_draft_by_candidate_id,
        p1_draft_by_department_id=p1_draft_by_department_id,
        p1_reviews=p1_reviews,
        nce_clusters_by_code=nce_clusters_by_code,
        nce_middle_series_code_by_department=nce_middle_series_code_by_department,
        nce_reviews=nce_reviews,
        url_audit_by_department=url_audit_by_department,
        service_major_ids=service_major_ids,
        offering_id_counts=offering_id_counts,
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
    # 2026-08-25 지시서 §4 — 행 유일 Key는 이제 department_id가 아니라 offering_id다
    # (load_inputs()가 이미 모든 행에 계산해 붙였다). department_id는
    # old_department_id로만 남아 classification/N.C.E/URL 감사처럼 아직
    # department_id 키만 아는 다른 파일과의 조인에 계속 쓰인다 — 그 파일들은 Identity
    # v2 이전에 만들어져 바꾸지 않는다(§4 "기존 Master 35건의 department_id는
    # Migration 완료 전까지 그대로 유지"). `generate_offering_id()`는 순수 함수라 이
    # 함수가 직접 계산한다 — `load_inputs()`가 미리 채워둔 값이 있으면 그대로 쓰고
    # (재계산 낭비 없음), 없으면(예: 이 함수를 직접 호출하는 단위 테스트) 그 자리에서
    # 계산한다 — 둘 다 같은 함수·같은 입력이라 항상 같은 값이 나온다.
    offering_id = row.get("offering_id") or generate_offering_id(row["schl_id"], row["source_schl_mjr_id"])
    department_id = row.get("old_department_id") or row["department_id"]
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

    # 2026-08-25 지시서 §6 "계약학과·산업체위탁 제외" — 기존 exclusion_reason=
    # CONTRACT_DEPARTMENT는 정규화 단계가 "같은 department_id로 들어온 일반과정/
    # 계약학과 쌍"만 좁게 잡은 것이었다(실측: 159개 계약학과·1개 산업체위탁 행 중
    # 6개만 그 경로로 잡혔다). Offering Identity v2가 매 행의 실제 편제 성격
    # (`major_character_name`)을 그대로 보존하므로, 이 필드로 직접 한 번 더 막아
    # 나머지 154개도 놓치지 않는다(위 in_scope 분기와 같은 사유 이름을 그대로 쓴다 —
    # "왜 막혔나"의 축이 다를 뿐 결과 의미는 같다).
    if row.get("major_character_name") in _CONTRACT_MAJOR_CHARACTERS:
        reasons.add("BLOCKED_CONTRACT_DEPARTMENT")

    # 2026-08-25 지시서 §4 — department_id 기반 duplicate_group_size 대신 offering_id
    # 중복 여부로 판정한다(§4 "기존 16개 identity-key 충돌로 행을 버리지 않음" —
    # 그 32행은 offering_id가 서로 달라 이 검사를 그대로 통과한다).
    if inputs.offering_id_counts.get(offering_id, 1) > 1:
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
                # 2026-08-25 지시서(a/final-integration-master-promotion) §3 — P1
                # Schema의 6개 decision을 실제 뜻대로 구분한다("검수 완료 항목을
                # P1_REVIEW_UNRESOLVED로 집계하지 않는다"):
                #   APPROVE_PROPOSED_CANDIDATE(+ eligible 재검증) → 통과, resolved_
                #     group_id는 아래 mapping_status 분기가 그대로 채운다.
                #   EXCLUDE_ARTS_RECOMMENDATION → BLOCKED_ARTS_RECOMMENDATION.
                #   NEEDS_OFFICIAL_CURRICULUM/KEEP_UNMAPPED → BLOCKED_EXCLUDED_FROM_
                #     INITIAL_PROMOTION(검토는 끝났지만 이번 라운드는 승격 대상 아님).
                #   TBD/REVISE_CANDIDATE/HOLD(진짜 미결) → BLOCKED_P1_REVIEW_UNRESOLVED.
                # p1_draft가 아예 없는 행(이번 연도 분류 REVIEW_REQUIRED 4,258건 중
                # 374행 P1 패킷 범위 밖 — 실측 3,883건)도 "검토 대상에 없다"는 뜻이지
                # "검토 중"이 아니므로 같은 EXCLUDED_FROM_INITIAL_PROMOTION으로 묶는다
                # (P1_REVIEW_UNRESOLVED로 잘못 집계하지 않는다).
                p1_draft = inputs.p1_draft_by_department_id.get(department_id)
                if p1_draft is None:
                    reasons.add("BLOCKED_EXCLUDED_FROM_INITIAL_PROMOTION")
                else:
                    p1_candidate_id = p1_draft.candidate_id
                    p1_review = inputs.p1_reviews.get(p1_candidate_id)
                    p1_review_decision = p1_review.decision if p1_review is not None else "TBD"
                    if (
                        p1_review_decision == "APPROVE_PROPOSED_CANDIDATE"
                        and p1_approve_eligible(p1_draft, inputs.service_major_ids)
                    ):
                        pass  # 통과 — resolved_group_id는 mapping_status 분기가 채운다.
                    elif p1_review_decision in _P1_ARTS_DECISIONS:
                        reasons.add("BLOCKED_ARTS_RECOMMENDATION")
                    elif p1_review_decision in _P1_EXCLUDED_FROM_INITIAL_PROMOTION_DECISIONS:
                        reasons.add("BLOCKED_EXCLUDED_FROM_INITIAL_PROMOTION")
                    elif p1_review_decision in _P1_UNRESOLVED_DECISIONS:
                        reasons.add("BLOCKED_P1_REVIEW_UNRESOLVED")
                    else:
                        # decision==APPROVE_PROPOSED_CANDIDATE인데 p1_approve_eligible()
                        # 재검증에 실패한 경우(검수 파일 손상 등 방어적 경로) — 자동
                        # 승인하지 않고 미결로 되돌린다.
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
                    # 2026-08-25 지시서(a/final-integration-master-promotion) §3 —
                    # N.C.E Schema의 5개 decision을 실제 뜻대로 구분한다("검수 완료
                    # 항목을 NCE_UNRESOLVED로 집계하지 않는다". "추측 Mapping 금지"):
                    #   ACCEPT_GROUP_AS_REVIEW_CANDIDATE → 그 클러스터의 후보 Group(들)
                    #     중 Service Canonical Major v2 Bridge가 ACTIVE로 확정한 Group이
                    #     정확히 1개일 때만 resolved_group_id를 채운다(그 뒤로는
                    #     AUTO_CANDIDATE와 완전히 같은 Group/Bridge Gate를 그대로
                    #     통과해야 한다 — 지름길 없음, "추측 Mapping 금지").
                    #     0개 또는 2개 이상이면 BLOCKED_EXCLUDED_FROM_INITIAL_PROMOTION
                    #     ("후보 없음 또는 복수 ACTIVE Group이면 초기 승격 제외").
                    #   REQUIRE_DEPARTMENT_LEVEL_REVIEW → BLOCKED_EXCLUDED_FROM_
                    #     INITIAL_PROMOTION(학과 단위 판단이 필요하다는 사람의 결론 —
                    #     이 Dry Run은 그 개별 판단을 대신하지 않는다).
                    #   TBD/HOLD/INSUFFICIENT_OFFICIAL_EVIDENCE(진짜 미결·근거 없음)
                    #     → BLOCKED_NCE_UNRESOLVED.
                    #
                    # 실측(2026-08-25): 이번 연도 분류가 N.C.E로 표시한 3,537건 중
                    # 24개 검수 완료 클러스터(584건)에 속하는 건 584건뿐이다 — 나머지
                    # 2,953건은 클러스터 자체가 없어 "검토가 아직 안 끝났다"가 아니라
                    # "이번 라운드 검토 범위 밖"이다(P1 패킷 범위 밖 3,883건과 같은
                    # 성격의 격차, §4 완료 보고에서 그대로 밝힌다). 그래서 이 두 경우를
                    # 구분한다: 클러스터 자체를 못 찾으면 BLOCKED_EXCLUDED_FROM_INITIAL_
                    # PROMOTION(검토 범위 밖), 클러스터는 있는데 decision이 TBD/HOLD/
                    # INSUFFICIENT_OFFICIAL_EVIDENCE면 BLOCKED_NCE_UNRESOLVED(진짜 미결).
                    nce_middle_series_code = inputs.nce_middle_series_code_by_department.get(department_id)
                    cluster = inputs.nce_clusters_by_code.get(nce_middle_series_code) if nce_middle_series_code else None

                    if cluster is None:
                        reasons.add("BLOCKED_EXCLUDED_FROM_INITIAL_PROMOTION")
                    else:
                        nce_review = inputs.nce_reviews.get(nce_middle_series_code)
                        nce_review_decision = nce_review.decision if nce_review is not None else "TBD"

                        if nce_review_decision == "ACCEPT_GROUP_AS_REVIEW_CANDIDATE":
                            active_candidate_groups = [
                                candidate.canonical_major_id
                                for candidate in cluster.candidate_canonical_major_groups
                                if (bridge_entry := inputs.service_major_bridge_by_group.get(candidate.canonical_major_id))
                                is not None
                                and bridge_entry.recommendation_status == "ACTIVE"
                            ]
                            if len(active_candidate_groups) == 1:
                                resolved_group_id = active_candidate_groups[0]
                            else:
                                reasons.add("BLOCKED_EXCLUDED_FROM_INITIAL_PROMOTION")
                        elif nce_review_decision == "REQUIRE_DEPARTMENT_LEVEL_REVIEW":
                            reasons.add("BLOCKED_EXCLUDED_FROM_INITIAL_PROMOTION")
                        else:
                            reasons.add("BLOCKED_NCE_UNRESOLVED")
                else:
                    reasons.add("BLOCKED_NO_SERVICE_CANONICAL_MAJOR")
            else:
                reasons.add("BLOCKED_NO_SERVICE_CANONICAL_MAJOR")

    if resolved_group_id is not None:
        # 2026-08-25 지시서 §3 — 승인 정본은 Draft 파일의 정적 review_status(worker-c
        # 산출물, 이 저장소 어떤 코드도 "approved"로 바꾸지 않는다 — 영원히 "draft")가
        # 아니라 사람이 검수 UI에서 실제로 저장한 canonical_major_group_review_status.
        # jsonl의 decision이다. Group Review가 없거나 decision이 APPROVE_AS_
        # CLASSIFICATION_GROUP이 아니면 Fail-Closed로 그대로 막는다(사유 이름은
        # BLOCKED_GROUP_DRAFT를 유지 — "이 Group이 아직 분류 Ontology로 승인되지
        # 않았다"는 뜻은 그대로다, 판정 근거만 바뀌었다).
        group_review = inputs.group_reviews.get(resolved_group_id)
        if group_review is None or group_review.decision != "APPROVE_AS_CLASSIFICATION_GROUP":
            reasons.add("BLOCKED_GROUP_DRAFT")

        # 2026-08-25 지시서(c/national-departments-38-majors) — Service Canonical
        # Major v2 Bridge는 Group 하나당 정확히 한 행이다(옛 Bridge의 EVIDENCED
        # 0개/1개/2개 이상 구분이 이 단계에서는 더 이상 존재하지 않는다, 모듈
        # docstring "Group→Service Major Bridge V2는 후보 모호함이 없다" 참고).
        bridge_entry = inputs.service_major_bridge_by_group.get(resolved_group_id)
        if bridge_entry is None:
            # 42개 Group 완전성 불변식이 지켜지는 한 실제로는 도달하지 않아야
            # 하는 방어적 경로다 — Group이 Bridge에 아예 없으면 이 Group을 어떤
            # 서비스 Major에도 연결할 수 없다.
            reasons.add("BLOCKED_NO_SERVICE_CANONICAL_MAJOR")
        elif bridge_entry.recommendation_status == "EXCLUDED_RECOMMENDATION":
            reasons.add("BLOCKED_ARTS_RECOMMENDATION")
        else:
            resolved_major_id = bridge_entry.service_major_id
            if resolved_major_id not in inputs.service_major_ids:
                reasons.add("BLOCKED_NO_SERVICE_CANONICAL_MAJOR")

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
        # 2026-08-25 지시서 §4 — 행 유일 Key. old_department_id/display_group_id는
        # 감사·UI 그룹화 전용 참고 필드일 뿐 유일성이나 Gate 판정에 쓰이지 않는다.
        "offering_id": offering_id,
        "old_department_id": department_id,
        "display_group_id": row.get("display_group_id") or generate_display_group_id(
            row["schl_id"], row.get("college_name") or "", row.get("department_name") or "",
        ),
        "university_name": row.get("university_name"),
        "department_name": row.get("department_name"),
        "college_name": row.get("college_name"),
        "department_status": row.get("department_status"),
        "major_character_name": row.get("major_character_name"),
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
        # CANDIDATE") resolved_group_id가 채워졌더라도 그 뒤 Group/Bridge/Scope
        # Gate를 전부 통과해야만 READY가 된다 — 이 두 필드 자체가 승격을 보장한
        # 적은 없다.
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

    # 현재 검수 상태(전부 TBD/미존재) 때문에만 막힌 건 — Group Draft·P1·N.C.E 검수
    # 관련 사유만 걸리고 다른 구조적 사유가 없는 행. Bridge V2는 이미 확정된 정본이라
    # (사람 검수 대기 상태 자체가 없다) 더 이상 이 집합에 없다.
    review_only_reasons = {
        "BLOCKED_GROUP_DRAFT",
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
            "2026-08-25(c/national-departments-38-majors) 이후: Group→Major 연결은 "
            "canonical_major_group_to_service_major_v2.jsonl(42개 Group 전부, ACTIVE 38 + "
            "EXCLUDED_RECOMMENDATION 4, 이미 확정된 정본)만 쓴다 — 옛 Bridge Mapping/Scope "
            "사람 검수 두 단계는 더 이상 이 Gate에 없다. Group 승인 정본은 여전히 "
            "canonical_major_group_review_status.jsonl의 decision(Draft의 정적 "
            "review_status가 아니다), P1/N.C.E는 각 검수 UI Store가 실제로 저장한 값을 "
            "그대로 쓴다 — 검수가 실제로 끝나면 READY_FOR_PROMOTION이 0보다 클 수 있다"
            "(0건도 여전히 계산 결과로서는 정상일 수 있다 — 그 경우 차단 사유별 실제 "
            "원인을 이 요약에서 확인한다). Master·API는 이 Dry Run으로 바뀌지 않는다."
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
                f"- {r['offering_id']} — {r['university_name']} {r['department_name']} → "
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
                f"- {r['offering_id']} — {r['university_name']} {r['department_name']}: "
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
    rows.sort(key=lambda r: r["offering_id"])

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
