"""Canonical Major Group Bridge 사람 검수 상태 Schema — 2026-08-24 지시서
(a/canonical-major-bridge-review-ui).

`src/schemas/canonical_major_group_bridge.py`의 `CanonicalMajorGroupBridgeEntry`
(44행 Draft)는 시스템이 계산한 `mapping_status`(EVIDENCED/REVIEW_REQUIRED/UNMAPPED/
EXCLUDED_RECOMMENDATION)만 담을 뿐, 사람이 그 판단을 실제로 확인했는지는 전혀
모른다. 이 파일은 그 사람 검수 결과를 담는 완전히 별개의 축이다 — Draft 파일
자체를 절대 수정하지 않고(Master Draft는 Read-Only), 별도 파일
(`data/reviews/canonical_major_group_bridge_review_status.json`)에 저장한다.

`canonical_major_group_id` 하나만으로는 Key가 유일하지 않다(예: `computer_science`
Group이 `computer_science`/`hci_ux` 두 Major 후보를 동시에 가진다) — 그래서 이
프로젝트의 기존 관례(`SharedProbeContextReview.key = f"{blueprint_id}::{context_id}"`)
와 같은 방식으로 `canonical_major_group_id + canonical_major_id` 복합 Key를 쓴다.
`canonical_major_id`가 None(UNMAPPED/일부 EXCLUDED_RECOMMENDATION 행)이면 명시적
센티널 문자열 "UNMAPPED"를 대신 쓴다 — 빈 문자열이나 "None" 같은 암묵적 값으로
얼버무리지 않는다."""

from __future__ import annotations

from src.schemas.v2_direct_probe_review import ReviewEntry

# `canonical_major_id`가 None일 때 Key에 쓰는 명시적 센티널. 실제 Major ID로는 쓰일 수
# 없는 문자열이어야 한다(`data/master/canonical_majors.jsonl`의 10개 major_id는 전부
# snake_case 실제 전공명이라 "UNMAPPED"와 절대 겹치지 않는다 — 이 사실은
# `test_canonical_major_group_bridge_review.py`에서 실제 파일로 확인한다).
UNMAPPED_MAJOR_SENTINEL = "UNMAPPED"


def bridge_review_key(canonical_major_group_id: str, canonical_major_id: str | None) -> str:
    """`CanonicalMajorGroupBridgeEntry` 한 행에 대응하는 안정적 복합 Key를 만든다.
    이 함수가 유일한 생성 지점이다 — Service/Store/테스트 모두 이 함수를 통해서만
    Key를 만들어서, Key 형식이 여러 곳에서 따로 재구현되며 어긋나는 일을 막는다."""

    return f"{canonical_major_group_id}::{canonical_major_id or UNMAPPED_MAJOR_SENTINEL}"


class CanonicalMajorGroupBridgeReview(ReviewEntry):
    """`ReviewEntry`(reviewer_1_status/reviewer_1_comment/resolution_note/
    final_status)를 그대로 재사용한다 — 단일 검토자 정책(2.5.5단계)과 같은 계산
    규칙을 새로 만들지 않는다. `reviewer_1_comment`가 사용자 코멘트 역할을 겸한다.

    `reviewer_1_status`의 기본값은 `ReviewEntry`에서 물려받은 "TBD"다 — 이 Schema를
    만드는 어떤 코드도(Claude 포함) 이 필드를 "APPROVE"로 미리 채우면 안 된다(안전
    규칙 "어떤 항목도 자동 APPROVE하지 않음")."""

    canonical_major_group_id: str
    canonical_major_id: str | None = None
    # 사람이 몇 번째로 이 행을 갱신했는지 감사용으로만 남긴다(낙관적 잠금이 아니다 —
    # `SharedProbeContextReview.revision`과 같은 단순화된 정책을 그대로 따른다).
    revision: str = ""

    @property
    def key(self) -> str:
        return bridge_review_key(self.canonical_major_group_id, self.canonical_major_id)
