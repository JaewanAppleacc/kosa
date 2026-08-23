"""V2 Direct Probe Human Review 상태 Schema — 2026-08-23 Trait Ontology v2(2.3단계)
§4, 2.5.5단계(단일 검토자 정책 전환).

사람이 실제로 채우는 값은 `data/reviews/v2_direct_probe_question_review_status.json`
(Blueprint=질문 14개 단위)과 `data/reviews/v2_direct_probe_option_review_status.json`
(Option=선택지 70개 단위) 두 JSON 파일이다 — Worksheet/Human Review Guide는 이
파일들을 읽어서 만드는 산출물일 뿐, 검토 결과의 정본이 아니다.

2.5.5단계: 사용자 확정으로 이 프로젝트는 2차 검토를 쓰지 않는다 — `final_status`는
`reviewer_1_status`만으로 계산한다. `reviewer_2_status`/`reviewer_2_comment` 필드는
과거 데이터 호환을 위해 그대로 남겨두지만(2.5.4단계 이전에 이미 저장된 값을 깨뜨리지
않는다), 계산에는 전혀 관여하지 않는다 — reviewer_2 값이 뭐든 결과가 달라지지
않는다."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ReviewerStatus = Literal["APPROVE", "REVISE", "HOLD", "TBD"]
FinalReviewStatus = Literal["DRAFT", "REVIEW_REQUIRED", "APPROVED"]


class ReviewEntry(BaseModel):
    """공통 필드. `reviewer_1_status`는 실제 사람이 채우는 값이고, 초기값(모든 항목)은
    항상 "TBD"다 — Claude나 테스트가 이 값을 대신 "APPROVE"로 채우면 안 된다(§4 규칙).
    `reviewer_2_status`/`reviewer_2_comment`는 2.5.5단계 이전(2인 검토 정책 시절)
    데이터와의 호환을 위해 필드 자체는 유지하되, `final_status` 계산에는 쓰지 않는다."""

    reviewer_1_status: ReviewerStatus = "TBD"
    reviewer_1_comment: str = ""
    reviewer_2_status: ReviewerStatus = "TBD"
    reviewer_2_comment: str = ""
    # 사람이 남기는 해소 메모(예: "REVISE 반영해 문구 수정함, 재검토 요청"). final_status
    # 자체는 계산값이라 저장하지 않지만, 이 메모는 Claude가 채우지 않는 사람 전용
    # 자유 기술란이다.
    resolution_note: str = ""

    @property
    def final_status(self) -> FinalReviewStatus:
        """2.5.5단계: 단일 검토자(reviewer_1) 판정만으로 계산한다 — 저장된 값이
        아니다. reviewer_2_status는 어떤 값이어도 결과에 영향을 주지 않는다.

        - reviewer_1_status == "TBD" → DRAFT
        - reviewer_1_status == "APPROVE" → APPROVED
        - reviewer_1_status in ("REVISE", "HOLD") → REVIEW_REQUIRED
        """

        if self.reviewer_1_status in ("REVISE", "HOLD"):
            return "REVIEW_REQUIRED"
        if self.reviewer_1_status == "APPROVE":
            return "APPROVED"
        return "DRAFT"


class QuestionReviewEntry(ReviewEntry):
    """질문(Blueprint) 단위 검토 — Exploration 후보 선택 규칙(해당하는 Trait만), 사회적
    바람직성 위험, 질문/선택지 간 의미 중복, 상황적 Trade-off 존재 여부, Target 선택지
    길이·구체성 편중 같은 '질문 전체'를 봐야 판단할 수 있는 항목을 다룬다."""

    blueprint_id: str


class OptionReviewEntry(ReviewEntry):
    """선택지(Option) 단위 검토 — PRIMARY·RELATED·NO_SIGNAL Mapping이 실제 행동과
    타당하게 연결되는지를 다룬다."""

    blueprint_id: str
    role_id: str
