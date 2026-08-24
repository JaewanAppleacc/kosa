"""department_id Identity-Key 충돌 16 Group·32행 — 완료된 사람 판정 정본 —
2026-08-25 지시서(a/offering-identity-v2) §1.

`data/academyinfo_work/2025/packets/department_identity_collision_review.jsonl`
(worker-c 산출, 32행, `review.decision`/`review.reviewer_1_status`가 전부
TBD인 Draft — `a/department-identity-collision-audit`가 만든 감사 패킷)와
완전히 별개의 축이다. 이 파일은 그 32행 각각에 대해 사람이 실제로 내린 최종
판정을 보존한다 — Draft 파일 자체는 절대 수정하지 않는다.

`source_record_id`가 이 Store의 유일 Key다(`department_id`는 두 행이
공유하는 값이라 Key로 쓸 수 없다 — 바로 이 사실이 충돌의 원인이다).

**자동 판정 결과를 덮어쓰지 않는다** — `department_status`·`major_character`·
`recommendation_scope_decision`은 이 Store가 별도로 기록하는 사람 판정값이고,
원본 Draft의 자동 계산 필드(`classification_result.eligibility_status`·
`recommendation_scope`·`dry_run_evaluation_audit`)는 그대로 남아 있다(둘 다
조회 가능, 서로 겹쳐 쓰지 않는다).

**판정 근거(2026-08-25, 사용자 확인)**: 원래 지시서의 "일반과정 추천 노출
7건·계약학과·산업체위탁 추천 제외 8건"은 실제 32행 전수 계산과 어긋났다
(EXISTING+일반과정 8행 중 2행은 공식 소계열이 N.C.E로 완전히 미분류돼
애초에 42개 Group 어디에도 속하지 않는다 — 서경대 코스메틱뷰티매니지먼트학과·
헤어디자인학과, 둘 다 미용예술대학). 사용자가 실측값을 정본으로 확정했다 —
분류 가능한 6건만 노출, EXISTING 계약학과 7건만 명시적 제외(ABOLISHED는
별도 사유로 이미 제외되므로 중복 집계하지 않음)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

from src.schemas.department_offering_identity import DepartmentStatus, MajorCharacter
from src.schemas.v2_direct_probe_review import ReviewerStatus

RecommendationScopeDecision = Literal["IN_RECOMMENDATION_SCOPE", "OUT_OF_RECOMMENDATION_SCOPE"]
ExclusionReason = Literal["ABOLISHED", "CONTRACT_OR_INDUSTRY_COMMISSIONED", "UNCLASSIFIED_SMALL_SERIES"]


class DepartmentIdentityCollisionRowReview(BaseModel):
    """32행 중 한 행에 대한 완료된 사람 판정. `source_record_id`가 Key다."""

    source_record_id: str
    department_id: str
    offering_id: str
    schl_id: str
    source_schl_mjr_id: str
    major_character: MajorCharacter
    department_status: DepartmentStatus
    recommendation_scope_decision: RecommendationScopeDecision
    exclusion_reason: ExclusionReason | None = None
    is_recommendation_representative: bool
    decision_basis_url: str
    reviewer_1_status: ReviewerStatus = "TBD"
    decided_at: str
    reviewer_1_comment: str = ""

    @field_validator(
        "source_record_id", "department_id", "offering_id", "schl_id", "source_schl_mjr_id",
        "decision_basis_url", "decided_at",
    )
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("빈 값은 허용하지 않는다")
        return value

    @model_validator(mode="after")
    def _scope_exclusion_representative_consistent(self) -> "DepartmentIdentityCollisionRowReview":
        """`is_recommendation_representative`(대표 선택 결과)·
        `recommendation_scope_decision`·`exclusion_reason` 세 필드가 서로
        다른 판단을 나타내는 조합을 막는다 — Group Review Schema(§3, 2026-08-25
        `canonical_major_group_review.py` 수정)와 같은 원칙이다.

        - 대표로 노출(True) → scope는 반드시 IN, exclusion_reason은 반드시 None.
        - 대표에서 제외(False) → scope는 반드시 OUT, exclusion_reason은 반드시
          지정돼야 한다(왜 제외됐는지 근거 없이 "그냥 제외"를 허용하지 않는다)."""

        if self.is_recommendation_representative:
            if self.recommendation_scope_decision != "IN_RECOMMENDATION_SCOPE":
                raise ValueError("대표로 선택된 행(is_recommendation_representative=True)의 scope는 IN_RECOMMENDATION_SCOPE여야 한다")
            if self.exclusion_reason is not None:
                raise ValueError("대표로 선택된 행에는 exclusion_reason이 있으면 안 된다")
        else:
            if self.recommendation_scope_decision != "OUT_OF_RECOMMENDATION_SCOPE":
                raise ValueError("대표에서 제외된 행의 scope는 OUT_OF_RECOMMENDATION_SCOPE여야 한다")
            if self.exclusion_reason is None:
                raise ValueError("대표에서 제외된 행은 exclusion_reason을 반드시 지정해야 한다")
        return self

    @property
    def key(self) -> str:
        return self.source_record_id
