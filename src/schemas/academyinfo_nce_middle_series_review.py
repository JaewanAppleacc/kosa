"""N.C.E(미분류) 재검토 가능 중계열 클러스터 검수 정본 Schema —
c/national-master-promotion-dry-run.

`data/academyinfo_work/<year>/packets/nce_reexaminable_middle_series_clusters.jsonl`
(worker-c 산출물, `career_build_nce_reexaminable_clusters.py`가 만든다)은 공식
소계열이 미분류(N.C.E, `is_series_unclassified()`)인 학과 중 "공식 중계열 명칭으로
재검토할 근거가 있어 보이는" 것만 클러스터로 묶은 검토 패킷이다. 클러스터 전체가
`decision_status: "PENDING"`·`reviewer_1_status: "TBD"`로 시작하고 재생성해도
그대로다 — 결정을 담지 않는다(다른 검토 패킷과 같은 원칙).

이 파일은 그 사람 결정을 담는 별도 정본이다. `cluster_id`가 Key다 — 학과
(`department_id`) 단위가 아니라 **클러스터 단위**로 승인한다(클러스터 안의
`members`가 전부 같은 공식 중계열을 공유하므로, 사람이 그 중계열 전체를 어느
Canonical Major Group으로 볼지 한 번에 판단한다).

**42개 Group을 임의로 늘리지 않는다** — `resolved_canonical_major_group_id`는
`data/canonical_major_groups.draft.jsonl`에 이미 있는 42개 중 하나를 가리켜야
한다(이 Schema 자체는 그 존재를 검증하지 않는다 — Group Draft 정본과 대조해야
하는 검증이라 Loader/Builder 계층이 한다, 기존 계층 분리 원칙과 동일).
`reviewer_1_status`가 "TBD"인 동안 `resolved_canonical_major_group_id`는 반드시
None이어야 한다."""

from __future__ import annotations

from pydantic import model_validator

from src.schemas.v2_direct_probe_review import ReviewEntry


class NceMiddleSeriesReviewDecision(ReviewEntry):
    """`ReviewEntry`를 그대로 재사용한다 — 단일 검토자 정책과 같은 계산 규칙을
    새로 만들지 않는다."""

    cluster_id: str
    resolved_canonical_major_group_id: str | None = None

    @model_validator(mode="after")
    def _resolved_group_matches_review_status(self) -> "NceMiddleSeriesReviewDecision":
        if self.reviewer_1_status == "APPROVE" and self.resolved_canonical_major_group_id is None:
            raise ValueError(
                f"{self.cluster_id}: reviewer_1_status가 APPROVE인데 "
                "resolved_canonical_major_group_id가 없다 — 무엇을 승인했는지 남겨야 한다"
            )
        if self.reviewer_1_status != "APPROVE" and self.resolved_canonical_major_group_id is not None:
            raise ValueError(
                f"{self.cluster_id}: reviewer_1_status가 APPROVE가 아닌데 "
                "resolved_canonical_major_group_id를 미리 채울 수 없다"
            )
        return self
