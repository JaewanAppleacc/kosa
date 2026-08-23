"""V2 Direct Probe 2인 Human Review 상태 Schema — 2026-08-23 Trait Ontology v2(2.3단계)
§4.

사람이 실제로 채우는 값은 `data/reviews/v2_direct_probe_question_review_status.json`
(Blueprint=질문 14개 단위)과 `data/reviews/v2_direct_probe_option_review_status.json`
(Option=선택지 70개 단위) 두 JSON 파일이다 — Worksheet/Human Review Guide는 이
파일들을 읽어서 만드는 산출물일 뿐, 검토 결과의 정본이 아니다. `final_status`는 이
파일에 직접 저장되는 값이 아니라 두 검토자 상태로부터 항상 다시 계산한다("한쪽만
승인했는데 TEAM_REVIEWED로 저장돼 있는" 상태 자체가 애초에 존재할 수 없게 만든다)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ReviewerStatus = Literal["APPROVE", "REVISE", "HOLD", "TBD"]
FinalReviewStatus = Literal["DRAFT", "REVIEW_REQUIRED", "TEAM_REVIEWED"]


class ReviewEntry(BaseModel):
    """공통 필드. `reviewer_1_status`/`reviewer_2_status`는 실제 사람이 채우는 값이고,
    초기값(모든 항목)은 항상 "TBD"다 — Claude나 테스트가 이 값을 대신 "APPROVE"로
    채우면 안 된다(§4 규칙)."""

    reviewer_1_status: ReviewerStatus = "TBD"
    reviewer_1_comment: str = ""
    reviewer_2_status: ReviewerStatus = "TBD"
    reviewer_2_comment: str = ""
    # 사람이 두 검토자 상태를 보고 남기는 해소 메모(예: "REVISE 반영해 문구 수정함,
    # 재검토 요청"). final_status 자체는 계산값이라 저장하지 않지만, 이 메모는
    # Claude가 채우지 않는 사람 전용 자유 기술란이다.
    resolution_note: str = ""

    @property
    def final_status(self) -> FinalReviewStatus:
        """두 검토자 상태로부터만 계산한다 — 저장된 값이 아니다.

        - 둘 다 APPROVE일 때만 TEAM_REVIEWED.
        - 어느 한쪽이라도 REVISE/HOLD면 REVIEW_REQUIRED(TBD와 무관하게 우선한다 —
          "일단 문제가 있다고 표시된 것"이 "아직 검토 안 함"보다 더 확정적인 정보다).
        - 그 외(TBD가 하나라도 남아 있고 REVISE/HOLD가 없음)는 DRAFT.
        """

        if self.reviewer_1_status in ("REVISE", "HOLD") or self.reviewer_2_status in ("REVISE", "HOLD"):
            return "REVIEW_REQUIRED"
        if self.reviewer_1_status == "APPROVE" and self.reviewer_2_status == "APPROVE":
            return "TEAM_REVIEWED"
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
