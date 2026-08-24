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
서로 다른 값을 보고 어긋나는 사고를 막는다.

2026-08-25 정정(a/integrate-department-audit-major-group-review §3): 이전
버전은 "reviewer_1_status는 저장·계산 어디에도 강제로 관여하지 않는다"고
문서화했는데, 그 결과 `decision=APPROVE_AS_CLASSIFICATION_GROUP`으로 저장해도
`reviewer_1_status`는 초기값 "TBD"에 그대로 머무는 모순 상태(검토 진행 상태만
보면 "미검수"인데 실제로는 이미 확정된 결정이 존재하는 상태)가 실제로 만들어질
수 있었다 — Group Review 불변식 감사에서 발견. 이제는 `decision`이 바뀔 때마다
`reviewer_1_status`도 `expected_reviewer_1_status_for_decision()`이 계산하는
값으로 항상 함께 갱신된다(원칙: decision="무엇을 결정했는가", reviewer_1_status=
"검토 진행 상태" — 둘이 서로 다른 판단을 나타내면 안 된다). 아래
`_reviewer_1_status_matches_decision` model_validator가 이 대응을 어긴 값으로는
아예 객체를 만들 수 없게 막는다(Schema 우회·수기 편집 JSONL 대비 방어).
reviewer_2_status/comment는 여전히 이 검증에서 제외된다 — 2차 검토를 요구하지
않는다는 기존 정책(2.5.5단계)은 그대로 유지한다.

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

from pydantic import model_validator

from src.schemas.v2_direct_probe_review import FinalReviewStatus, ReviewEntry, ReviewerStatus

CanonicalMajorGroupReviewDecision = Literal[
    "TBD",
    "APPROVE_AS_CLASSIFICATION_GROUP",
    "REVISE_GROUP_DEFINITION",
    "SPLIT_GROUP",
    "MERGE_WITH_OTHER_GROUP",
    "EXCLUDE_FROM_CLASSIFICATION",
    "HOLD",
]

# §3 "decision은 '무엇을 결정했는가', reviewer_1_status는 '검토 진행 상태' — 둘이
# 서로 다른 판단을 나타내면 안 된다"의 유일한 대응표. HOLD와 TBD는 이름 그대로
# 대응하고, APPROVE_AS_CLASSIFICATION_GROUP만 APPROVE로 대응한다. 나머지 넷
# (REVISE_GROUP_DEFINITION/SPLIT_GROUP/MERGE_WITH_OTHER_GROUP/
# EXCLUDE_FROM_CLASSIFICATION)은 전부 "승인도 보류도 아니고 정의 자체를 다시
# 손봐야 한다"는 같은 진행 상태이므로 REVISE 하나로 묶는다(reviewer_1_status는
# 4개 값밖에 없어 decision의 7개 값을 그대로 표현할 수 없다 — 이 buckets가
# `CanonicalMajorGroupSummary.revise_count`가 이미 쓰는 것과 같은 묶음이다).
_REVIEWER_1_STATUS_FOR_DECISION: dict[str, ReviewerStatus] = {
    "TBD": "TBD",
    "APPROVE_AS_CLASSIFICATION_GROUP": "APPROVE",
    "HOLD": "HOLD",
    "REVISE_GROUP_DEFINITION": "REVISE",
    "SPLIT_GROUP": "REVISE",
    "MERGE_WITH_OTHER_GROUP": "REVISE",
    "EXCLUDE_FROM_CLASSIFICATION": "REVISE",
}


def expected_reviewer_1_status_for_decision(decision: str) -> ReviewerStatus:
    """`decision` 하나에 대응하는 유일한 `reviewer_1_status`. Store 저장 경로
    (`update_canonical_major_group_review`)와 아래 model_validator 둘 다 이
    함수 하나만 쓴다 — 대응표가 두 곳에 따로 있으면 결국 어긋난다."""

    return _REVIEWER_1_STATUS_FOR_DECISION[decision]


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

    @model_validator(mode="after")
    def _reviewer_1_status_matches_decision(self) -> "CanonicalMajorGroupReview":
        """§3 불변식 — `reviewer_1_status`가 `decision`과 모순되는 조합으로는
        이 객체 자체를 만들 수 없다(정상 저장 경로뿐 아니라 수기 편집한 JSONL을
        `model_validate()`로 불러올 때도 걸린다). `reviewer_2_status`는 의도적으로
        검증에서 제외한다 — 2차 검토를 요구하지 않는다는 기존 정책(2.5.5단계)을
        이 도메인에서도 그대로 유지한다."""

        expected = expected_reviewer_1_status_for_decision(self.decision)
        if self.reviewer_1_status != expected:
            raise ValueError(
                f"reviewer_1_status({self.reviewer_1_status!r})가 decision({self.decision!r})과 "
                f"모순된다 — decision={self.decision!r}이면 reviewer_1_status는 반드시 {expected!r}이어야 한다"
            )
        return self

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
