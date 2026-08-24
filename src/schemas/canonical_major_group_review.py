"""Canonical Major Group 사람 검수 상태 Schema — 2026-08-24 지시서
(a/canonical-major-group-review-ui).

`data/canonical_major_groups.draft.jsonl`(42개, worker-c 산출물, `review_status`가
전부 "draft"인 Read-Only Master)와 완전히 별개의 축이다. Draft 파일 자체는 절대
수정하지 않고, 사람 검수 결과는 여기 정의한 별도 파일
(`data/reviews/canonical_major_group_review_status.jsonl`)에만 저장한다.

`ReviewEntry`(reviewer_1_status/reviewer_1_comment/reviewer_2_status/
reviewer_2_comment/resolution_note)를 그대로 상속해 이 프로젝트의 검수 파일들과
필드 이름을 맞춘다 — 2.5.5단계(단일 검토자 전환) 정책과 동일하게, 이 도메인의
실제 판단은 `reviewer_1_status`가 아니라 아래 `decision`(이 Group에 특화된
7개 값)이 대표한다. 그래서 `final_status`도 `ReviewEntry`의 기본 계산(reviewer_1_status
기준)을 그대로 쓰지 않고 `decision` 기준으로 다시 계산하도록 재정의한다 —
UI가 실제로 채우는 필드(decision)와 배지로 보여주는 상태(final_status)가
서로 다른 값을 보고 어긋나는 사고를 막는다. reviewer_1/2_status·comment
필드는 다른 검수 파일과의 구조 일관성을 위해 남겨두되(이 도메인에서는 UI가
채우지 않는다), 저장·계산 어디에도 강제로 관여하지 않는다.

**`APPROVE_AS_CLASSIFICATION_GROUP`이 의미하는 것은 정확히 하나다: "이 Group을
42개 중간 분류 Ontology로 계속 쓸 수 있다"는 사람의 1차 판단.** 다음을 전혀
의미하지 않는다(호출하는 어떤 코드도 이 값을 아래 목적에 연결하지 않는다):
학생에게 추천되는 서비스 전공(`canonical_majors.jsonl`) 승인, 전국 학과 자동
승격, 예체능 추천 허용, Bridge Mapping 승인, Bridge Scope 승인. 이 네 가지는
전부 물리적으로 다른 파일·다른 검수 축(각각
`canonical_major_group_bridge_review_status.json`,
`canonical_major_group_bridge_scope_review*.json`, Department Master, Dry Run
결과)에 속하며, 이 모듈의 어떤 함수도 그 파일들을 열지 않는다."""

from __future__ import annotations

from typing import Literal

from src.schemas.v2_direct_probe_review import FinalReviewStatus, ReviewEntry

CanonicalMajorGroupReviewDecision = Literal[
    "TBD",
    "APPROVE_AS_CLASSIFICATION_GROUP",
    "REVISE_GROUP_DEFINITION",
    "SPLIT_GROUP",
    "MERGE_WITH_OTHER_GROUP",
    "EXCLUDE_FROM_CLASSIFICATION",
    "HOLD",
]


class CanonicalMajorGroupReview(ReviewEntry):
    """`canonical_major_group_id`가 Key다(42개 Group Draft의 `canonical_major_id`와
    같은 값 — Bridge Review Schema와 같은 관례로, 이 Schema는 그 값을 항상
    `canonical_major_group_id`로 부른다). `revision`은 정수 낙관적 잠금 카운터다
    (N.C.E/P1 검수와 같은 방식 — 문자열 감사용 카운터인 Bridge Review와는 다르다.
    PATCH가 `expected_revision`을 요구해야 하는 이 지시서의 요구사항 때문에
    비교 가능한 정수가 필요하다)."""

    canonical_major_group_id: str
    decision: CanonicalMajorGroupReviewDecision = "TBD"
    revision: int = 0

    @property
    def key(self) -> str:
        return self.canonical_major_group_id

    @property
    def final_status(self) -> FinalReviewStatus:
        """`ReviewEntry.final_status`(reviewer_1_status 기준)를 재정의한다 — 이
        도메인은 `decision`이 유일한 실제 판단 축이다.

        - decision == "TBD" → DRAFT
        - decision == "APPROVE_AS_CLASSIFICATION_GROUP" → APPROVED
        - 그 외(REVISE_GROUP_DEFINITION/SPLIT_GROUP/MERGE_WITH_OTHER_GROUP/
          EXCLUDE_FROM_CLASSIFICATION/HOLD) → REVIEW_REQUIRED
        """

        if self.decision == "APPROVE_AS_CLASSIFICATION_GROUP":
            return "APPROVED"
        if self.decision == "TBD":
            return "DRAFT"
        return "REVIEW_REQUIRED"
