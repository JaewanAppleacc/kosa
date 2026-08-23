"""V2 Direct Probe 질문 생성 — 2026-08-23 Trait Ontology v2(2단계) §13.

검토된 Direct Probe Blueprint → LLM은 Context에 맞게 문장 표현만 생성 → Structured
Output → Quality Gate → 실패 시 재생성 → 계속 실패하면 `blueprint.base_question`(사람이
직접 검토한 고정 문항)을 그대로 쓴다. LLM이 꺼져 있으면 처음부터 `base_question`을
쓴다 — "LLM OFF에서도 Direct Probe가 정상 작동하고 EXACT_BLUEPRINT Mapping을 사용해야
한다"(§13)는 요구를 만족한다: `base_question`은 이미 `blueprint.blueprint`의 실제
role_id로 만들어져 있으므로 Registry에서 항상 EXACT_BLUEPRINT로 조회된다 —
LEGACY_PRIMARY_ADAPTER를 거치지 않는다.

`generate_tail_question()`처럼 별도 LangGraph로 만들지 않고 단순 재시도 루프로 둔다 —
Direct Probe Blueprint는 Cache가 필요 없고(Trait당 세션에 최대 1번만 쓰인다), 재생성
분기도 §10/§11의 LangGraph 패턴과 달리 상태 전이가 다양하지 않아 그래프로 표현할
이점이 적다(main.py의 Context 이동 orchestration과 같은 이유로 일반 함수를 그대로 쓴다)."""

from __future__ import annotations

from pydantic import BaseModel

from src.engines.question_quality_gate import V2_DIRECT_PROBE_TRAIT_LABEL_PHRASES, run_quality_gate
from src.llm.protocols import ChatLLMClient, LLMCallError
from src.schemas.context import ContextDefinition
from src.schemas.question import FinalizedQuestion, QuestionGenerationResult, finalize_question
from src.schemas.v2_direct_probe import V2DirectProbeBlueprint

V2_DIRECT_PROBE_SYSTEM_PROMPT = """당신은 고등학생 진로 탐색 설문의 질문 생성기입니다. 다음 규칙을 반드시 지키세요.
- 학생이 선택한 Context(관심 영역) 안에서만 질문합니다.
- 행동 선호를 묻습니다. "잘하나요/능력이 있나요" 같은 자기평가를 요구하지 않습니다.
- 어떤 성향·기질의 이름도 문장에 직접 언급하지 않습니다("구조적으로 사고하는 편인가요?"
  같은 표현 금지) — 항상 구체적인 상황과 행동으로만 묻습니다.
- 직업명이나 학과명을 직접 언급하지 않습니다.
- 특정 선택지가 다른 선택지보다 도덕적으로나 사회적으로 더 좋아 보이게 쓰지 않습니다
  ("가장 올바른 행동"을 묻지 않습니다). 학생을 도덕적으로 평가하는 표현도 쓰지 않습니다.
- 선택지 5개의 길이와 구체성을 비슷하게 맞춥니다. 한 선택지가 두세 행동을 동시에
  말하지 않게 합니다.
- 주어진 Role마다 정확히 하나의 자연스러운 한국어 선택지 문장을 만듭니다. Role의
  순서와 role_id는 그대로 유지하고, 새 role_id를 만들지 않습니다.
- 참고용 기준 질문과 같은 상황·같은 Role 구성을 유지하되, 문장 표현만 자연스럽게
  바꿉니다 — 의미나 난이도를 바꾸지 않습니다.
- target_traits와 frame_id는 입력으로 주어진 값을 그대로 반환합니다."""


def _build_user_prompt(*, context_definition: ContextDefinition, blueprint: V2DirectProbeBlueprint) -> str:
    role_list = "\n".join(f"- {role.role_id}" for role in blueprint.blueprint.roles)
    reference_lines = "\n".join(f"- {opt.role_id}: {opt.text}" for opt in blueprint.base_question.options)
    return f"""[Context — 질문의 행동 무대는 항상 이 안에 있어야 함]
label: {context_definition.label}
description: {context_definition.description}

[참고용 기준 질문 — 그대로 베끼지 말고, 같은 상황·같은 Role 구성을 자연스러운 다른 표현으로 바꿔 쓸 것]
질문: {blueprint.base_question.question_text}
{reference_lines}

[Option Role — 위와 같은 role_id 순서 그대로, 각각 하나의 선택지 문장을 만들 것]
{role_list}

context 필드에는 "{context_definition.context_id}"를, target_traits 필드에는 []를,
frame_id 필드에는 "{blueprint.question_frame_id}"를 그대로 넣어 반환하세요."""


class V2DirectProbeGenerationOutcome(BaseModel):
    question: FinalizedQuestion
    source: str  # "llm" | "backup"


def generate_v2_direct_probe_question(
    *,
    question_id: str,
    context_definition: ContextDefinition,
    blueprint: V2DirectProbeBlueprint,
    llm_client: ChatLLMClient | None,
    max_regenerations: int = 1,
) -> V2DirectProbeGenerationOutcome:
    """LLM이 결정하면 안 되는 것(target_trait_id/Blueprint ID/Option Role/Trait
    Signal/weight/Related Concept/질문 종료 여부/다음 Trait 선택) 중 이 함수가 다루는
    부분(Option Role)은 `finalize_question()`이 이미 강제한다 — LLM이 반환한 role_id가
    `blueprint.blueprint`에 없으면 거부한다."""

    fallback = blueprint.base_question.model_copy(update={"question_id": question_id})

    if llm_client is None:
        return V2DirectProbeGenerationOutcome(question=fallback, source="backup")

    user_prompt = _build_user_prompt(context_definition=context_definition, blueprint=blueprint)
    attempt = 0
    while attempt <= max_regenerations:
        attempt += 1
        try:
            result = llm_client.complete_structured(
                system_prompt=V2_DIRECT_PROBE_SYSTEM_PROMPT, user_prompt=user_prompt,
                response_model=QuestionGenerationResult,
            )
        except LLMCallError:
            continue
        try:
            finalized = finalize_question(question_id, result.question, blueprint.blueprint)
        except ValueError:
            continue
        finalized = finalized.model_copy(update={"target_traits": []})
        gate = run_quality_gate(finalized, forbidden_trait_label_phrases=V2_DIRECT_PROBE_TRAIT_LABEL_PHRASES)
        if gate.passed:
            return V2DirectProbeGenerationOutcome(question=finalized, source="llm")

    return V2DirectProbeGenerationOutcome(question=fallback, source="backup")
