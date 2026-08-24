"""대학알리미 P1 분류 REVIEW 검수 패킷(374건) 원본 Schema — 2026-08-24 지시서
(a/academyinfo-review-ui-p1-nce).

`data/academyinfo_work/2025/packets/p1_classification_review.jsonl`(worker-c 산출,
Read-Only Draft)을 읽어 검증하는 Schema다 — Bridge Draft와 같은 원칙: 이 파일 자체를
절대 수정하지 않는다. 사람 검수 결과는 완전히 별도 파일
(`data/reviews/academyinfo_p1_classification_review_status.jsonl`,
`academyinfo_p1_classification_candidate_review.py` 참고)에만 저장한다.

패킷 원본 행에도 `reviewer_1_status`/`reviewer_comment`/`resolution_status` 필드가
있지만(worker-c가 만든 자리 표시자, 전부 TBD/PENDING 고정값) 이 Schema는 그
필드들을 의도적으로 모델링하지 않는다 — 실제 사람 검수 결과의 유일한 정본은
이 파일이 아니라 별도 검수 Store다(Pydantic 기본 동작상 모델에 없는 필드는
조용히 무시되므로, 로드 자체는 실패하지 않는다)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# 원본 P1 산출물의 실측 분포(2026-08-24): CONTENT_MEDIA 275 / DESIGN_HCI_UX 99.
P1Cluster = Literal["CONTENT_MEDIA", "DESIGN_HCI_UX"]

# 원본 데이터에서 실제로 관측된 5개 값(judgment_candidate_breakdown 기준) —
# MEDIA_COMMUNICATION_CANDIDATE 96 / UNMAPPED 68 / NEEDS_OFFICIAL_CURRICULUM 207 /
# DESIGN_ARTS_EXCLUDED 1 / HCI_UX_CANDIDATE 2.
P1JudgmentCandidate = Literal[
    "MEDIA_COMMUNICATION_CANDIDATE", "HCI_UX_CANDIDATE", "DESIGN_ARTS_EXCLUDED",
    "NEEDS_OFFICIAL_CURRICULUM", "UNMAPPED",
]

ArtsSportsPossibility = Literal["POSSIBLE_NEEDS_CHECK", "UNLIKELY"]


class AcademyInfoP1ClassificationEntry(BaseModel):
    """P1 패킷 한 행(학과 하나). `candidate_id`가 이 패킷 전체의 유일 Key다."""

    candidate_id: str
    source_record_id: str
    department_id: str
    university_name: str
    college_name: str
    department_name: str

    official_large_series_name: str
    official_middle_series_name: str
    official_small_series_name: str

    p1_cluster: P1Cluster
    judgment_candidate: P1JudgmentCandidate
    judgment_candidate_reason: str
    # True여야 "공식 소계열 코드로 실제 분류된 근거"가 있다는 뜻이다 — 학과명·
    # 단과대학명 키워드만으로 후보를 표시한 행(예: HCI_UX_CANDIDATE 상당수)은
    # False다. APPROVE_PROPOSED_CANDIDATE 승인 조건의 핵심 필드
    # (academyinfo_p1_classification_candidate_review.py 참고).
    judgment_evidence_sufficient: bool
    # 0개(UNMAPPED) 또는 1개(후보 하나 특정)만 실제로 관측된다. 이 필드가 가리키는
    # ID는 항상 "서비스 추천 10개 Major" ID라고 가정하면 안 된다 — DESIGN_ARTS_EXCLUDED
    # 판정에서는 42개 Group ID(예: fine_arts_design)가 들어온다(예체능 제외 정책
    # 대상임을 나타내는 표시일 뿐, 승인 가능한 서비스 Major 추천이 아니다).
    candidate_canonical_major_ids: list[str] = Field(default_factory=list)

    arts_sports_possibility: ArtsSportsPossibility
    official_curriculum_available: bool
    official_curriculum_summary: str | None = None
    official_evidence_needed: list[str] = Field(default_factory=list)

    @field_validator("candidate_id", "source_record_id", "department_id")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("빈 ID는 허용하지 않는다")
        return value
