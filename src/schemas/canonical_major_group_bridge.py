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
연결하지 않는다.

**Scope 필드(2026-08-24 a/canonical-major-bridge-scope 지시서, Additive)**: 기존
필드 위에 `scope_type`/`included_small_series_codes`/`excluded_small_series_codes`/
`scope_decision_reason`/`scope_review_status` 5개를 새로 추가한다 — 기존 필드는
이름도 의미도 바뀌지 않는다. `mapping_status`(EVIDENCED 등)가 "이 Group과 이 Major를
연결할 근거가 있는가"를 답한다면, `scope_type`은 그 연결을 "전공군 전체"로 볼지
"공식 소계열 일부만"으로 좁힐지 "개별 학과 단위로만 판단"할지를 답한다. 예를 들어
`business` Group(경영학·경영정보학·비서·금융보험학·회계세무학 5개 소계열)이
`business_administration` Major에 EVIDENCED로 연결돼 있어도, 실제로 "경영학" 추천
학과로 써도 되는 건 소계열 '경영학' 하나뿐이다 — 나머지 4개 소계열까지 통째로
연결하면 전공군 전체(1,424건)가 무분별하게 추천 후보가 된다. `scope_type`이 바로 이
과잉 연결을 막는 필드다."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# 시스템이 내린 분류 판단(사람이 아직 검토하지 않았어도 결정론적으로 계산 가능한 값).
MappingStatus = Literal["EVIDENCED", "REVIEW_REQUIRED", "UNMAPPED", "EXCLUDED_RECOMMENDATION"]

# 사람 검토 상태 — `CanonicalMajorGroupDraft.review_status`(src/schemas/canonical_major_group.py)
# 와 같은 관례("draft"/"approved")를 그대로 따른다. mapping_status(시스템 판단)와는
# 별개 축이다 — EVIDENCED라도 review_status는 사람이 실제로 확인하기 전까지 "draft"다.
BridgeReviewStatus = Literal["draft", "approved"]

# ── Scope(2026-08-24 a/canonical-major-bridge-scope 지시서) ──────────────────
# FULL_GROUP: Group의 공식 소계열 전체를 그대로 이 Major의 후보 범위로 쓴다(narrowing 없음).
# INCLUDED_SMALL_SERIES_ONLY: Group 소계열 중 일부만 후보 범위다(included_small_series_codes
#   가 그 부분집합). Group 전체를 그대로 쓰면 안 되는 EVIDENCED/REVIEW_REQUIRED 행에 쓴다.
# DEPARTMENT_REVIEW_REQUIRED: 소계열 단위로도 범위를 확정할 수 없다 — 학과 개별 교육과정을
#   봐야 한다(Group 전체는 물론 특정 소계열조차 자동으로 후보 범위라고 볼 수 없다).
# EXCLUDED_RECOMMENDATION: mapping_status와 동일하게 추천 후보 생성에 전혀 쓸 수 없다.
ScopeType = Literal[
    "FULL_GROUP", "INCLUDED_SMALL_SERIES_ONLY", "DEPARTMENT_REVIEW_REQUIRED", "EXCLUDED_RECOMMENDATION",
]

# scope_type 자체(무엇으로 좁혔는지)와는 별개로, 그 Scope 판단을 사람이 실제로 검토했는지를
# 나타낸다. `review_status`(기존 Bridge Mapping 자체의 검토 상태)와 같은 "draft"/"approved"
# 관례를 그대로 쓰되, 절대 자동으로 "approved"를 채우지 않는다(지시서 §3 — 기존
# reviewer_1_status APPROVE/REVISE 판정을 이 필드에 자동 복사하지 않는다. 사람이 REVISE를
# 통해 요구한 것은 "Scope를 좁혀라"이지 "이 Scope 값을 승인한다"가 아니다).
ScopeReviewStatus = Literal["draft", "approved"]


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

    # ── Scope(Additive, 2026-08-24 a/canonical-major-bridge-scope 지시서) ──
    # None은 "이 행에는 Scope 판단 자체가 성립하지 않는다"는 뜻이다 — UNMAPPED
    # (연결 대상이 아예 없음) 전용. EVIDENCED/REVIEW_REQUIRED/EXCLUDED_RECOMMENDATION은
    # 반드시 값이 있어야 한다(아래 model_validator가 강제).
    scope_type: ScopeType | None = None
    # INCLUDED_SMALL_SERIES_ONLY일 때만 "이 코드들만 후보 범위"라는 뜻으로 최소 1개 이상 채운다.
    included_small_series_codes: list[str] = Field(default_factory=list)
    # 감사용 — "왜 제외했는지"를 명시적으로 남긴다(생략해도 included만으로 범위는 이미
    # 확정되지만, 검토자가 "이 코드를 빠뜨린 게 아니라 의도적으로 뺐다"를 바로 보게 한다).
    excluded_small_series_codes: list[str] = Field(default_factory=list)
    scope_decision_reason: str = ""
    scope_review_status: ScopeReviewStatus = "draft"

    @field_validator("included_small_series_codes", "excluded_small_series_codes")
    @classmethod
    def _small_series_codes_not_blank_and_unique(cls, value: list[str]) -> list[str]:
        if any(not code.strip() for code in value):
            raise ValueError("소계열 코드에 공백/빈 문자열을 넣을 수 없다")
        if len(value) != len(set(value)):
            raise ValueError(f"소계열 코드 목록에 중복이 있다: {value}")
        return value

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

    @model_validator(mode="after")
    def _scope_field_consistency(self) -> "CanonicalMajorGroupBridgeEntry":
        """2026-08-24 a/canonical-major-bridge-scope 지시서 §2 검증 규칙. 여기서
        하는 검증은 이 행 하나만 봐도 판단 가능한 것만이다 — "코드가 실제 대학알리미
        158개 소계열표에 있는가"·"그 코드가 이 Group 소계열 목록의 부분집합인가" 같은
        다른 정본과 대조해야 하는 검증은 Loader 계층
        (`canonical_major_group_bridge_loader.py`)이 한다(기존 계층 분리 원칙 그대로).

        `model_construct()`로 이 검증을 우회해 만든 값이 들어올 가능성에 대비해,
        Loader가 로드 직후 `validate_bridge_scope_row()`로 아래 규칙을 순수 함수로도
        한 번 더 확인한다(§2 "Schema 우회에 대비한 Service 방어 검증") — 이 메서드의
        규칙과 그 함수의 규칙은 반드시 같은 내용을 유지해야 한다."""

        # UNMAPPED는 연결 대상 자체가 없다 — Scope("무엇을 후보로 쓸지")는 연결이
        # 있을 때만 의미가 있으므로 scope_type이 아예 없어야 한다(값을 채우면 마치
        # 연결이 있는 것처럼 보인다).
        if self.mapping_status == "UNMAPPED":
            if self.scope_type is not None:
                raise ValueError("UNMAPPED는 scope_type을 가질 수 없다(연결 대상이 없어 범위를 정할 수 없다)")

        # EXCLUDED_RECOMMENDATION은 mapping_status·scope_type 둘 다 "추천 후보로
        # 절대 쓰지 않는다"는 같은 의미를 1:1로 표현해야 한다 — 둘이 어긋나면(예:
        # mapping_status만 EXCLUDED고 scope_type은 FULL_GROUP) 이 행을 읽는 쪽이
        # 어느 신호를 믿어야 할지 알 수 없다.
        if self.mapping_status == "EXCLUDED_RECOMMENDATION":
            if self.scope_type != "EXCLUDED_RECOMMENDATION":
                raise ValueError(
                    "EXCLUDED_RECOMMENDATION 행의 scope_type은 항상 EXCLUDED_RECOMMENDATION이어야 한다"
                    f"(현재 {self.scope_type!r})"
                )
        elif self.scope_type == "EXCLUDED_RECOMMENDATION":
            raise ValueError(
                f"scope_type=EXCLUDED_RECOMMENDATION은 mapping_status도 EXCLUDED_RECOMMENDATION이어야 한다"
                f"(현재 mapping_status={self.mapping_status!r})"
            )

        # EVIDENCED/REVIEW_REQUIRED는 실제 연결 후보이므로 Scope 판단이 반드시 있어야
        # 한다 — "연결은 있는데 범위는 정하지 않음" 상태를 허용하지 않는다.
        if self.mapping_status in ("EVIDENCED", "REVIEW_REQUIRED") and self.scope_type is None:
            raise ValueError(f"{self.mapping_status}는 scope_type이 있어야 한다(범위 미정 상태를 허용하지 않는다)")

        included = self.included_small_series_codes
        excluded = self.excluded_small_series_codes

        # 코드 목록 자체는 필드 Validator에서 이미 개별로 검사했지만, "겹치지 않는가"는
        # 두 필드를 함께 봐야 하는 규칙이라 여기서 한다.
        overlap = set(included) & set(excluded)
        if overlap:
            raise ValueError(f"included_small_series_codes와 excluded_small_series_codes가 겹친다: {sorted(overlap)}")

        if self.scope_type == "FULL_GROUP":
            # FULL_GROUP은 Group 전체가 그대로 범위다 — included/excluded 둘 다 쓰지
            # 않는다. 둘 중 하나라도 채우면 "전체"라는 주장과 "일부만/일부는 제외"라는
            # 주장이 동시에 성립해 모순이다(그 상태를 표현하려면 scope_type을
            # INCLUDED_SMALL_SERIES_ONLY로 바꿔야 한다).
            if included or excluded:
                raise ValueError(
                    "FULL_GROUP은 included_small_series_codes/excluded_small_series_codes를 "
                    "동시에 사용하지 않는다(둘 다 비어 있어야 한다)"
                )

        if self.scope_type == "INCLUDED_SMALL_SERIES_ONLY" and not included:
            raise ValueError("INCLUDED_SMALL_SERIES_ONLY는 included_small_series_codes가 최소 1개 있어야 한다")

        return self
