"""department_id Identity-Key 충돌 32행 사람 판정 규칙(순수 함수) — 2026-08-25
지시서(a/offering-identity-v2) §1.

한 행(row)의 자동 계산 필드(department_status, major_character, 공식 소계열
분류 가능 여부)만 보고 다음 세 값을 결정한다:

- `recommendation_scope_decision` — 이 편제를 추천 범위 안/밖 중 어디에 둘지
- `exclusion_reason` — 범위 밖이라면 왜(폐과/계약·위탁/미분류)
- `is_recommendation_representative` — 이 편제를 그 표시명 그룹의 "추천
  대표"로 노출할지

우선순위(§1 최종 회계, 2026-08-25 사용자 확인 — 원 지시서의 "7건/8건"은 32행
전수 계산과 어긋나 사용자가 실측값으로 확정했다):

1. `department_status == "ABOLISHED"` → 제외(ABOLISHED). 운영이 끝난 편제는
   일반과정이든 계약학과든 무조건 제외한다.
2. `major_character in ("계약학과", "산업체위탁")` → 제외
   (CONTRACT_OR_INDUSTRY_COMMISSIONED). 계약·위탁 편제는 일반 학생 추천
   대상이 아니다(기존 `CONTRACT_DEPARTMENT` 정책과 같은 원칙).
3. `major_character == "일반과정"`이지만 공식 소계열이 분류 불가(N.C.E,
   42개 Canonical Major Group 후보가 하나도 없음) → 제외
   (UNCLASSIFIED_SMALL_SERIES). 분류 근거가 없으면 추천할 수 없다(서경대
   코스메틱뷰티매니지먼트학과·헤어디자인학과, 둘 다 미용예술대학 소속으로
   공식 소계열이 "N.C.E(뷰티아트)"라 42개 Group 어디에도 속하지 않는다).
4. 나머지(일반과정 + EXISTING + 분류 가능) → 대표로 노출.

32행 전체에 이 함수를 적용하면 실측값(2026-08-25 사용자 확인)과 정확히
일치한다: 노출 6건 / 계약·위탁 제외 7건(EXISTING만) / ABOLISHED 제외 17건
(8+1+8) / 미결 0건 — `tests/test_department_identity_collision_classifier.py`
가 실제 감사 패킷 32행으로 이 값을 고정한다."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DepartmentStatusInput = Literal["EXISTING", "NEW", "MERGED", "SPLIT", "ABOLISHED"]
MajorCharacterInput = Literal["일반과정", "계약학과", "산업체위탁"]


@dataclass(frozen=True)
class RowClassificationInput:
    department_status: DepartmentStatusInput
    major_character: MajorCharacterInput
    has_classifiable_canonical_group: bool


@dataclass(frozen=True)
class RowClassificationResult:
    recommendation_scope_decision: Literal["IN_RECOMMENDATION_SCOPE", "OUT_OF_RECOMMENDATION_SCOPE"]
    exclusion_reason: Literal["ABOLISHED", "CONTRACT_OR_INDUSTRY_COMMISSIONED", "UNCLASSIFIED_SMALL_SERIES"] | None
    is_recommendation_representative: bool


def classify_row(row: RowClassificationInput) -> RowClassificationResult:
    if row.department_status == "ABOLISHED":
        return RowClassificationResult("OUT_OF_RECOMMENDATION_SCOPE", "ABOLISHED", False)
    if row.major_character in ("계약학과", "산업체위탁"):
        return RowClassificationResult("OUT_OF_RECOMMENDATION_SCOPE", "CONTRACT_OR_INDUSTRY_COMMISSIONED", False)
    if not row.has_classifiable_canonical_group:
        return RowClassificationResult("OUT_OF_RECOMMENDATION_SCOPE", "UNCLASSIFIED_SMALL_SERIES", False)
    return RowClassificationResult("IN_RECOMMENDATION_SCOPE", None, True)
