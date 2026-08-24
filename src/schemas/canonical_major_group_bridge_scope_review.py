"""Canonical Major Group Bridge Scope 사람 검수 상태 Schema — 2026-08-24 지시서
(a/bridge-scope-final-review-ui).

`src/schemas/canonical_major_group_bridge.py`의 `scope_type`(FULL_GROUP/
INCLUDED_SMALL_SERIES_ONLY/DEPARTMENT_REVIEW_REQUIRED/EXCLUDED_RECOMMENDATION)은
`career_add_canonical_major_group_bridge_scope.py`가 결정론적으로 채운 시스템
초안일 뿐, 사람이 그 범위 판단을 실제로 검토했는지는 전혀 모른다(그 필드
`scope_review_status`도 44행 전부 "draft"인 값 그대로 Draft 파일 안에 있다 —
사람이 검수했다는 신호가 아니다).

이 파일은 Mapping 검수(`CanonicalMajorGroupBridgeReview`, "이 Group과 이 Major를
연결할 근거가 있는가"를 사람이 판단)와 물리적으로 완전히 분리된 두 번째 검수
축이다 — "그 연결의 범위(전체 Group인지, 소계열 일부인지, 개별 학과 검토가
필요한지)가 맞는가"를 사람이 판단한다. 두 축은 서로 다른 질문에 답하므로:

- Mapping reviewer_1_status가 APPROVE라고 이 Scope 검수가 자동으로 APPROVE되지
  않는다(Mapping을 승인해도 그 범위 판단까지 승인한 것은 아니다).
- 이 Scope 검수가 APPROVE돼도 Mapping reviewer_1_status는 전혀 바뀌지 않는다.

이 독립성은 저장 위치로 강제한다 — 이 Schema의 값은
`data/reviews/canonical_major_group_bridge_scope_review_status.jsonl`에만
저장되고, Mapping 검수 파일(`.../canonical_major_group_bridge_review_status.json`)
이나 Master Draft(`data/master/canonical_major_group_bridge.draft.jsonl`)는
이 파일을 쓰는 어떤 코드도 절대 열지 않는다."""

from __future__ import annotations

from src.schemas.canonical_major_group_bridge_review import bridge_review_key
from src.schemas.v2_direct_probe_review import ReviewEntry


class CanonicalMajorGroupBridgeScopeReview(ReviewEntry):
    """`ReviewEntry`(reviewer_1_status/reviewer_1_comment/resolution_note/
    final_status)를 그대로 재사용한다 — Mapping 검수(`CanonicalMajorGroupBridgeReview`)
    와 같은 단일 검토자 계산 규칙을 새로 만들지 않는다. Key 생성도 같은
    `bridge_review_key()`를 그대로 써서 Mapping 검수와 같은 (group_id, major_id)
    행을 가리킬 때 항상 같은 문자열이 나오게 한다(두 파일을 나란히 놓고 조인하기
    쉽게).

    `reviewer_1_status`의 기본값은 `ReviewEntry`에서 물려받은 "TBD"다 — 이 Schema를
    만드는 어떤 코드도(Claude 포함) 이 필드를 "APPROVE"로 미리 채우면 안 된다."""

    canonical_major_group_id: str
    canonical_major_id: str | None = None
    revision: str = ""

    @property
    def key(self) -> str:
        return bridge_review_key(self.canonical_major_group_id, self.canonical_major_id)
