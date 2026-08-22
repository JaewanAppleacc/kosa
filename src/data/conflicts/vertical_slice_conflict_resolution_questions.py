"""Explicit Conflict 확인 질문 — planning_vs_execution Contrast Pair 전용, 1차 초안
(DRAFT, 2인 교차검토 전). §12-1 확장.

Contrast Pair가 EXPLICIT_CONFLICT로 판정되면(양쪽 Evidence가 comparable_frame_ids
안에서 충분히 쌓이면), LLM에게 즉흥적으로 맡기지 않고 사람이 미리 검토한 고정 문항을
한 번 물어 같은 조건에서 직접 대조한다 — Backup Question과 같은 성격(신뢰도가 중요한
판정용 질문은 즉흥 생성에 맡기지 않는다).

선택지 5개는 세 그룹이다:
- positive(계획) 쪽으로 명확히 답함 → RESOLVED_POSITIVE
- opposite(즉시 실행) 쪽으로 명확히 답함 → RESOLVED_OPPOSITE
- "상황에 따라 다르다"로 명확히 답함 → RESOLVED_CONTEXT_DEPENDENT
- 대조와 무관한 답(정보 탐색·협업 등 다른 Trait) → UNRESOLVED — 판정 불가지만 그 자체로도
  유효한 Evidence(다른 Trait)라서 무의미한 선택지가 아니다.

`question.context`는 세션마다 실제 진행 중인 Context로 채워 넣어야 한다(그래야
EvidenceRecord.context가 정확해서 §13 context_count 계산이 왜곡되지 않는다) —
그래서 고정 인스턴스가 아니라 `build_planning_vs_execution_resolution_question()`
함수로 만든다.
"""

from __future__ import annotations

from pydantic import BaseModel

from src.schemas.evidence import ContrastResolutionStatus
from src.schemas.question import FinalizedOption, FinalizedQuestion

PLANNING_VS_EXECUTION_RESOLUTION_QUESTION_ID = "conflict_resolution_planning_vs_execution"

# comparable_frame_ids=["new_tool"]와 동일한 Frame을 써서, 이 확인 질문 자체도 원래
# Contrast 정의가 요구하는 "같은 상황에서 직접 대조"라는 조건을 그대로 만족시킨다.
_FRAME_ID = "new_tool"

_ROLE_RESOLUTION_MAP: dict[str, ContrastResolutionStatus] = {
    "consistent_planning": ContrastResolutionStatus.RESOLVED_POSITIVE,
    "context_dependent_approach": ContrastResolutionStatus.RESOLVED_CONTEXT_DEPENDENT,
    "consistent_execution": ContrastResolutionStatus.RESOLVED_OPPOSITE,
    "filler_ask_others": ContrastResolutionStatus.UNRESOLVED,
    "filler_research_first": ContrastResolutionStatus.UNRESOLVED,
}


def build_planning_vs_execution_resolution_question(context_id: str) -> FinalizedQuestion:
    qid = PLANNING_VS_EXECUTION_RESOLUTION_QUESTION_ID
    return FinalizedQuestion(
        question_id=qid,
        context=context_id,
        target_traits=["planning", "immediate_execution"],
        frame_id=_FRAME_ID,
        question_text="새로운 과제나 도구를 접했을 때 실제로 가장 자주 하는 방식은 무엇인가요?",
        contrast_id="planning_vs_execution",
        options=[
            FinalizedOption(
                option_id=f"{qid}_o1",
                role_id="consistent_planning",
                text="전체 절차를 먼저 계획한 뒤 시작한다",
                primary_trait_delta={"planning": 1},
            ),
            FinalizedOption(
                option_id=f"{qid}_o2",
                role_id="context_dependent_approach",
                text="상황에 따라 미리 계획할 때도 있고 바로 시도할 때도 있다",
                primary_trait_delta={"planning": 1, "immediate_execution": 1},
            ),
            FinalizedOption(
                option_id=f"{qid}_o3",
                role_id="consistent_execution",
                text="일단 시작해보면서 방법을 찾아간다",
                primary_trait_delta={"immediate_execution": 1},
            ),
            FinalizedOption(
                option_id=f"{qid}_o4",
                role_id="filler_ask_others",
                text="주변 사람에게 먼저 물어보고 참고한다",
                primary_trait_delta={"collaboration_preference": 1},
            ),
            FinalizedOption(
                option_id=f"{qid}_o5",
                role_id="filler_research_first",
                text="비슷한 사례나 자료를 먼저 찾아본다",
                primary_trait_delta={"information_comparison": 1},
            ),
        ],
    )


class ContrastResolutionQuestionSpec(BaseModel):
    contrast_id: str
    role_resolution_map: dict[str, ContrastResolutionStatus]


VERTICAL_SLICE_RESOLUTION_QUESTION_BUILDERS = {
    "planning_vs_execution": build_planning_vs_execution_resolution_question,
}

VERTICAL_SLICE_RESOLUTION_SPECS: dict[str, ContrastResolutionQuestionSpec] = {
    "planning_vs_execution": ContrastResolutionQuestionSpec(
        contrast_id="planning_vs_execution", role_resolution_map=_ROLE_RESOLUTION_MAP
    ),
}
