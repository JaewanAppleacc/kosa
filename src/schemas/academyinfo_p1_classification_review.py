"""P1(예체능 애매 판정) 학과 단위 검수 정본 Schema — c/national-master-promotion-dry-run.

`data/academyinfo_work/<year>/packets/p1_classification_review.jsonl`(worker-c 산출물,
`career_build_academyinfo_p1_classification_review.py`가 만든다)은 매번 다시 만들 수 있는
검토 패킷이다 — `career_classify_academyinfo.py`가 계산한 `eligibility_status ==
"REVIEW_REQUIRED"`(융합·디자인·콘텐츠 등 이름만으로는 예체능 여부를 확정할 수 없는 학과)
학과 목록을 사람이 보기 좋게 재포장했을 뿐, 모든 행이 `resolution_status: "PENDING"`·
`reviewer_1_status: "TBD"`로 시작하고 재생성해도 그대로다 — 결정을 담지 않는다.

이 파일은 그 사람 결정을 담는 별도 정본이다(다른 검수 정본과 같은 원칙 —
`academyinfo_duplicate_scope_review.py`/`canonical_major_group_bridge_review.py`와
동일하게, 패킷 자체를 절대 수정하지 않고 별도 파일에 저장한다). `department_id` 하나가
Key다 — P1 패킷은 학과 하나당 한 행만 만든다(같은 학과가 두 candidate_id를 갖지 않는다).

`reviewer_1_status`가 "TBD"인 동안(기본값, 새 Schema를 만드는 어떤 코드도 미리
"APPROVE"로 채우지 않는다) `resolved_eligibility_status`는 반드시 None이어야 한다 —
결정하지 않았는데 결과만 채워 넣는 모순을 막는다. "APPROVE"면 반드시 값이 있어야 한다
(무엇을 승인했는지 없이 승인 상태만 있는 행은 의미가 없다)."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from src.schemas.v2_direct_probe_review import ReviewEntry

# `career_classify_academyinfo.py`의 ELIGIBILITY_APPROVED/ELIGIBILITY_EXCLUDED와 정확히
# 같은 문자열을 쓴다 — 새 이름을 만들지 않는다(같은 의미의 새 필드명을 만들지 말라는
# 기존 관례, career_classify_academyinfo.py 상단 주석과 동일 원칙).
P1ResolvedEligibilityStatus = Literal["APPROVED", "EXCLUDED_ARTS_SPORTS"]


class P1ClassificationReviewDecision(ReviewEntry):
    """`ReviewEntry`(reviewer_1_status/reviewer_1_comment/resolution_note/final_status)를
    그대로 재사용한다 — 단일 검토자 정책과 같은 계산 규칙을 새로 만들지 않는다."""

    department_id: str
    resolved_eligibility_status: P1ResolvedEligibilityStatus | None = None

    @model_validator(mode="after")
    def _resolved_status_matches_review_status(self) -> "P1ClassificationReviewDecision":
        if self.reviewer_1_status == "APPROVE" and self.resolved_eligibility_status is None:
            raise ValueError(
                f"{self.department_id}: reviewer_1_status가 APPROVE인데 "
                "resolved_eligibility_status가 없다 — 무엇을 승인했는지 남겨야 한다"
            )
        if self.reviewer_1_status != "APPROVE" and self.resolved_eligibility_status is not None:
            raise ValueError(
                f"{self.department_id}: reviewer_1_status가 APPROVE가 아닌데 "
                "resolved_eligibility_status를 미리 채울 수 없다"
            )
        return self
