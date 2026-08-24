"""Canonical Major Group ↔ Canonical Major Bridge Schema — 2026-08-24 지시서
(Bridge 계약).

두 층을 명시적으로 연결하는 얇은 다리다 — 어느 쪽도 대체하지 않는다.

- `data/canonical_major_groups.draft.jsonl`(42개, worker-c 산출물): 대학알리미
  표준분류 소계열 158개를 전국 학과 분류용으로 묶은 중간 Ontology. 각 행의
  기본 키는 `canonical_major_id`라는 필드명을 쓰지만(원본 파일의 명명), 의미상
  "Group"이다 — 이 Bridge Schema에서는 그 혼동을 피하려고 항상
  `canonical_major_group_id`로 부른다.
- `data/master/canonical_majors.jsonl`(10개, A 소유): 학생에게 실제로 보여주는
  서비스 추천 전공. 기본 키는 `major_id`다 — 이 Bridge Schema에서는
  `canonical_major_id`로 부른다.

**두 ID 공간은 우연히 문자열이 겹친다** — 예: Group `computer_science`(라벨
"컴퓨터·소프트웨어·AI")와 Major `computer_science`(라벨 "컴퓨터·소프트웨어"),
Group `psychology`와 Major `psychology`, Group `education`과 Major `education`이
전부 같은 문자열이다. 이 우연의 일치를 "같은 ID 공간"으로 착각해 두 필드를
합치거나 문자열 비교만으로 연결을 확정하면 안 된다(지시서 §2 "42개 Group과
기존 10개 Major를 같은 ID 공간으로 합치지 마세요" / "문자열 유사도만으로
EVIDENCED 승격하지 마세요") — 그래서 이 Schema는 두 필드를 항상 분리해서
갖고, `evidence`(대학알리미 공식 소계열 코드·명칭 등 실제 근거)와
`decision_reason`(그 근거로 왜 이 판단을 내렸는지)을 EVIDENCED에 필수로
요구한다.

**Runtime 미연결(지시서 §3)**: 이 Schema를 소비하는 Matching·Runtime 코드는
아직 없다. `mapping_status`가 무엇이든 이 파일은 학생 API·Matching 점수에
전혀 영향을 주지 않는다 — Loader와 검증기까지만 만들고, 실제 조회 경로에는
연결하지 않는다."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# 시스템이 내린 분류 판단(사람이 아직 검토하지 않았어도 결정론적으로 계산 가능한 값).
MappingStatus = Literal["EVIDENCED", "REVIEW_REQUIRED", "UNMAPPED", "EXCLUDED_RECOMMENDATION"]

# 사람 검토 상태 — `CanonicalMajorGroupDraft.review_status`(src/schemas/canonical_major_group.py)
# 와 같은 관례("draft"/"approved")를 그대로 따른다. mapping_status(시스템 판단)와는
# 별개 축이다 — EVIDENCED라도 review_status는 사람이 실제로 확인하기 전까지 "draft"다.
BridgeReviewStatus = Literal["draft", "approved"]


class CanonicalMajorGroupBridgeEntry(BaseModel):
    # `data/canonical_major_groups.draft.jsonl`의 canonical_major_id(=Group ID)를 가리킨다.
    canonical_major_group_id: str
    # `data/master/canonical_majors.jsonl`의 major_id(=서비스 추천 전공 ID)를 가리킨다.
    # None은 "이 Group에 대응하는 서비스 전공 후보가 아예 없다"는 뜻이다(UNMAPPED 전용,
    # 또는 서비스 전공 대응 없이 정책상 제외되는 예체능 Group의 EXCLUDED_RECOMMENDATION).
    canonical_major_id: str | None = None

    mapping_status: MappingStatus

    # 실제 근거 — 대학알리미 공식 소계열 코드·명칭, 별칭·키워드 일치 등 구체적 사실만
    # 담는다("의미상 비슷해 보인다" 같은 인상 평가는 evidence가 아니라 decision_reason에서
    # 설명한다).
    evidence: list[str] = Field(default_factory=list)
    decision_reason: str = ""
    # 선택: 범위 불일치·모호한 지점 등 사람이 검토할 때 바로 봐야 하는 경계 사례.
    boundary_notes: str = ""

    review_status: BridgeReviewStatus = "draft"
    reviewer_id: str | None = None
    reviewed_at: str | None = None  # ISO 8601 날짜 문자열. 실제 검토 전까지 None.

    @field_validator("canonical_major_group_id")
    @classmethod
    def _group_id_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("canonical_major_group_id는 빈 값일 수 없다")
        return value

    @field_validator("canonical_major_id")
    @classmethod
    def _major_id_not_blank_if_present(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("canonical_major_id는 빈 문자열일 수 없다(연결 없음은 None으로 표현)")
        return value

    @model_validator(mode="after")
    def _status_field_consistency(self) -> "CanonicalMajorGroupBridgeEntry":
        # EVIDENCED: 근거 없는 확정 금지(지시서 §2 "근거 없음은 UNMAPPED").
        if self.mapping_status == "EVIDENCED":
            if self.canonical_major_id is None:
                raise ValueError("EVIDENCED는 canonical_major_id가 있어야 한다(대응하는 서비스 전공 필수)")
            if not self.evidence:
                raise ValueError("EVIDENCED는 evidence가 최소 1개 이상이어야 한다")
            if not self.decision_reason.strip():
                raise ValueError("EVIDENCED는 decision_reason이 있어야 한다")

        # UNMAPPED: "근거 없음"의 정본 표현 — 특정 서비스 전공을 가리키면 안 된다
        # (가리키는 순간 그건 REVIEW_REQUIRED 후보이지 UNMAPPED가 아니다).
        if self.mapping_status == "UNMAPPED" and self.canonical_major_id is not None:
            raise ValueError("UNMAPPED는 canonical_major_id를 가질 수 없다(근거 없음은 특정 전공을 가리키지 않는다)")

        # REVIEW_REQUIRED: 검토 대상 후보가 명확해야 한다(어느 전공을 검토할지조차
        # 불명확한 행은 만들지 않는다).
        if self.mapping_status == "REVIEW_REQUIRED" and self.canonical_major_id is None:
            raise ValueError("REVIEW_REQUIRED는 canonical_major_id(검토 대상 후보 전공)가 있어야 한다")

        return self
