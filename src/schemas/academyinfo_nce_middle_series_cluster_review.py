"""대학알리미 N.C.E 중계열 검수 상태 Schema — 2026-08-24 지시서
(a/academyinfo-review-ui-p1-nce) §2.

`AcademyInfoNceMiddleSeriesClusterEntry`(24개 클러스터, Read-Only)와 완전히
별개의 사람 검수 축이다. 저장 정본은
`data/reviews/academyinfo_nce_middle_series_review_status.jsonl`뿐이다.

모듈 파일명 참고: 같은 저장소에 `cluster_id` 단위로 별도 Group 승인 흐름을
다루는 다른 작업(`c/national-master-promotion-dry-run`)이 존재해, 이름 충돌을
피하려고 파일명에 `_cluster_`를 명시했다(클래스 이름 자체는 원래 계획대로
`AcademyInfoNceMiddleSeriesReview`, Key는 `official_middle_series_code`)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# "ACCEPT_GROUP_AS_REVIEW_CANDIDATE"는 절대 "이 중계열의 584개 학과 중 이 클러스터에
# 속한 학과들을 자동 승인한다"는 뜻이 아니다 — "이 중계열에서 후보로 제시된 전공군을
# 검토 후보로 계속 쓸 수 있다"는 사람의 1차 판단일 뿐이며, 실제 학과 개별 승격은
# 이 파일과 전혀 무관한 별도 학과 단위 Gate를 통과해야 한다(어떤 코드도 이 값을
# Department 승격 로직에 연결하지 않는다 — Runtime 미연결 테스트로 확인한다).
NceMiddleSeriesDecision = Literal[
    "TBD",
    "ACCEPT_GROUP_AS_REVIEW_CANDIDATE",
    "REQUIRE_DEPARTMENT_LEVEL_REVIEW",
    "INSUFFICIENT_OFFICIAL_EVIDENCE",
    "HOLD",
]


class AcademyInfoNceMiddleSeriesReview(BaseModel):
    """`official_middle_series_code`가 Key다(24개 클러스터의 유일 Key와 동일).
    `revision`은 P1 검수와 같은 방식의 행 단위 낙관적 잠금 카운터다."""

    official_middle_series_code: str
    decision: NceMiddleSeriesDecision = "TBD"
    reviewer_comment: str = ""
    resolution_note: str = ""
    revision: int = 0

    @property
    def key(self) -> str:
        return self.official_middle_series_code
