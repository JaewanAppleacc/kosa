"""대학알리미 P1 분류 REVIEW 검수 상태 Schema — 2026-08-24 지시서
(a/academyinfo-review-ui-p1-nce) §1.

`AcademyInfoP1ClassificationEntry`(374행 Draft, Read-Only)와 완전히 별개의 사람
검수 축이다. 저장 정본은 `data/reviews/academyinfo_p1_classification_review_status.
jsonl`뿐이다 — Bridge Mapping/Scope 검수 파일과 물리적으로 다른 파일이고, 이
Schema를 쓰는 어떤 Store/Service도 그 파일들을 열지 않는다.

`ReviewEntry`(APPROVE/REVISE/HOLD/TBD)를 재사용하지 않는다 — P1 판단은 4지선다가
아니라 6가지 서로 다른 의미를 가진 결론(승인/예체능 제외/미분류 유지/공식
교육과정 필요/후보 재검토/보류)이라 범용 상태로는 표현이 안 된다.

모듈 파일명 참고: 이 파일이 담당하는 Key는 `candidate_id`(P1 패킷의 학과 행
하나)다 — 같은 저장소에 `department_id` 단위로 별도 승인 흐름을 다루는 다른
작업(`c/national-master-promotion-dry-run`)이 존재해, 이름 충돌을 피하려고
파일명에 `_candidate_`를 명시했다(클래스 이름 자체는 원래 계획대로
`AcademyInfoP1ClassificationReview`)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# "TBD"는 사람이 아직 아무 판단도 내리지 않은 초기값이다(자동으로 다른 값을 채우지
# 않는다). 다음 6개가 지시서 §1이 명시한 "P1 판단 선택지"다.
# 2026-08-25 후속 지시(a/final-mapping-closure §6, Final Mapping Closure 종결) —
# "EXCLUDE_FROM_INITIAL_PROMOTION"을 Additive로 추가한다. 근거 불충분(judgment_
# evidence_sufficient=False)인 행을 특정 Major로 추측 연결하지 않으면서도 검수
# 자체는 종결하기 위한 값이다 — 승격 승인이 아니라 "1차 전국 Master 승격에서는
# 제외하되, 원본·감사 데이터는 보존하고 추후 공식 교육과정 근거가 확보되면 재검토
# 가능하다"는 뜻이다. 이 값이 저장돼도 Dry Run(`career_build_national_department_
# promotion_dry_run.py`)은 READY_FOR_PROMOTION으로 풀지 않는다 — 별도 사유
# (BLOCKED_EXCLUDED_FROM_INITIAL_PROMOTION)로 명확히 표시할 뿐이다.
P1ReviewDecision = Literal[
    "TBD",
    "APPROVE_PROPOSED_CANDIDATE",
    "EXCLUDE_ARTS_RECOMMENDATION",
    "KEEP_UNMAPPED",
    "NEEDS_OFFICIAL_CURRICULUM",
    "REVISE_CANDIDATE",
    "HOLD",
    "EXCLUDE_FROM_INITIAL_PROMOTION",
]


class AcademyInfoP1ClassificationReview(BaseModel):
    """`candidate_id`가 Key다(P1 패킷 자체의 유일 Key와 동일). `revision`은 행
    단위 낙관적 잠금 카운터다 — 이 행이 없으면(사람이 아직 검토 전) 0으로 취급하고,
    저장할 때마다 1씩 늘린다. 호출자가 보낸 `expected_revision`이 현재 저장된 값과
    다르면 저장을 거부한다(다른 검토자가 그 사이 먼저 저장한 경우를 감지)."""

    candidate_id: str
    decision: P1ReviewDecision = "TBD"
    reviewer_comment: str = ""
    resolution_note: str = ""
    revision: int = 0

    @property
    def key(self) -> str:
        return self.candidate_id
