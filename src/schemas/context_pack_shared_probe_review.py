"""ContextPack 공용 Adaptive Probe 검수 상태 Schema — 2026-08-23 Trait Ontology
v2(2.9.1단계) §3.

2.9단계는 공용 Probe 14개를 `blueprint_id` 하나로만 검수했다 — 그 결과 "business에서
승인"이 "law_politics 등 나머지 11개 Context에서도 자동 승인"으로 새는 문제가 있었다
(같은 Blueprint라도 Context마다, 그리고 Anchor마다 실제로 적절한지는 다를 수 있다).
이 파일은 검수 최소 단위를 `(blueprint_id, context_id)`로 좁히고, 그 안에서도
`approved_anchor_ids`로 Anchor 단위까지 명시적으로 승인해야만 실제로 쓰이게 한다 —
"미검토 Anchor는 자동 승인 금지"(Fail-Closed)."""

from __future__ import annotations

from pydantic import Field, model_validator

from src.schemas.v2_direct_probe_review import ReviewEntry


class SharedProbeContextReviewValidationError(ValueError):
    """§1-2(2.9.1단계 감사) — Anchor 목록 자체의 구조적 정합성이 깨졌을 때. 실제
    ContextPack/Blueprint 정본과 비교해야 하는 검증(미등록 Anchor, 미지원 Context)은
    이 Schema가 모르는 정보라 여기서 하지 않는다 — 그건 `src/review_ui/
    context_pack_review_service.py::update_shared_probe_review()`(Service 계층)가
    한다(계층 분리, `context_pack.py`/`v2_direct_probe.py`와 동일 원칙)."""


class SharedProbeContextReview(ReviewEntry):
    """`ReviewEntry`(reviewer_1_status/reviewer_1_comment/resolution_note/final_status)를
    그대로 재사용한다 — 단일 검토자 정책(2.5.5단계)과 같은 계산 규칙을 새로 만들지
    않는다. `reviewer_1_comment`가 사용자 메모(§5 "사용자 메모") 역할을 겸한다.

    `reviewer_1_status=="APPROVE"`(Context 단위 승인)이어도, 그 자체만으로는 어떤
    Anchor에도 쓰이지 않는다 — `approved_anchor_ids`에 명시적으로 들어간 Anchor만
    실제 후보가 된다(§3 정책 "미검토 Anchor는 자동 승인 금지"). `excluded_anchor_ids`는
    "명시적으로 부적합 판정"을 감사 목적으로 별도 기록한다(승인 목록에 없는 것과 의미가
    다르다 — 하나는 "아직 안 봄", 하나는 "봤는데 안 됨")."""

    blueprint_id: str
    context_id: str
    approved_anchor_ids: list[str] = Field(default_factory=list)
    excluded_anchor_ids: list[str] = Field(default_factory=list)
    # 사람이 이 판정을 몇 번째로 갱신했는지 감사용으로만 남긴다(낙관적 잠금이 아니다 —
    # 2.9/2.9.1단계 Review UI는 File Revision 기반 CAS를 쓰지 않는 단순화된 정책을
    # 그대로 유지한다, 알려진 한계로 보고).
    revision: str = ""

    @property
    def key(self) -> str:
        return f"{self.blueprint_id}::{self.context_id}"

    @model_validator(mode="after")
    def _anchor_id_lists_are_structurally_valid(self) -> "SharedProbeContextReview":
        """§1-2(2.9.1단계 감사) — Pack/Blueprint 정본을 몰라도 판단할 수 있는 구조적
        규칙만 여기서 강제한다: 빈 문자열·공백 ID 금지, 각 목록 내부 중복 금지, 두
        목록 사이 교집합 금지(승인과 제외를 동시에 주장할 수 없다). `model_copy()`는
        Pydantic이 재검증을 건너뛰므로, 저장 Service는 이 규칙을 반드시 우회하지 않는
        경로(`model_validate`)로 갱신해야 한다(Service 쪽 주석 참고)."""

        for field_name, ids in (
            ("approved_anchor_ids", self.approved_anchor_ids),
            ("excluded_anchor_ids", self.excluded_anchor_ids),
        ):
            if any(not anchor_id.strip() for anchor_id in ids):
                raise SharedProbeContextReviewValidationError(
                    f"{self.key}: {field_name}에 빈 문자열이나 공백만 있는 Anchor ID를 넣을 수 없다"
                )
            if len(ids) != len(set(ids)):
                raise SharedProbeContextReviewValidationError(
                    f"{self.key}: {field_name}에 중복된 Anchor ID가 있다"
                )

        overlap = set(self.approved_anchor_ids) & set(self.excluded_anchor_ids)
        if overlap:
            raise SharedProbeContextReviewValidationError(
                f"{self.key}: approved_anchor_ids와 excluded_anchor_ids가 겹친다 — "
                f"같은 Anchor를 동시에 승인·제외할 수 없다: {sorted(overlap)}"
            )
        return self
