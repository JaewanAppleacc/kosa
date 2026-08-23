"""Context Anchor Presentation Schema — 2026-08-23 Trait Ontology v2(2.5.1단계) §3.

2.5단계에서 만든 Context Routing은 학생의 Anchor 선택(`context_anchor_choices`)을
State에 저장하기만 했고, 이후 질문 생성·선택 어디에서도 읽지 않았다(2.5.1단계 §1/§2
재현 결과). 이 파일은 그 문제를 고치는 핵심 계약이다 — 다만 Anchor마다 Trait Mapping을
새로 만들지 않는다(§2 금지 구조). `ContextAnchorPresentation`은 오직 "학생에게 보여줄
상황 표현"만 담고, Trait Target·role_id·PRIMARY/RELATED/NO_SIGNAL·Signal Weight는
여전히 기존 Blueprint(`V2DirectProbeBlueprint`)와 Seed Question이 그대로 소유한다."""

from __future__ import annotations

from pydantic import BaseModel


class ContextAnchorPresentationError(ValueError):
    """Anchor Presentation 정본 파일 자체가 구조적으로 잘못됐을 때(중복 Anchor ID,
    미등록 Context, Routing Blueprint의 실제 Anchor 집합과 불일치)."""


class ContextAnchorPresentation(BaseModel):
    """Anchor 하나에 대한 "상황 표현" 정본. `forbidden_assumptions`는 이 Anchor를 고른
    학생에게 전제하면 안 되는 경험/상황(예: 혼자 플레이하는 학생에게 팀원 전제) —
    결정론적 Variant 문구를 검토할 때도, LLM Prompt에 넘겨서 재생성 판정에 쓸 때도
    같은 목록을 참조한다(단일 정본)."""

    context_id: str
    anchor_id: str
    label: str
    situation_terms: list[str]
    preferred_scenarios: list[str]
    forbidden_assumptions: list[str]
