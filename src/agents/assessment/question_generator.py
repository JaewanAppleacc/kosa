"""꼬리질문 생성 — 설계안 §10(Question Generator)·§11(Quality Gate·Fallback) 구현.

흐름(§11 Fallback 그대로):
Cache 조회 → HIT면 그대로 사용 / MISS면 실시간 생성 → 실패 시 1회 재생성 →
그래도 실패·Timeout이면 Backup Question → Backup도 소진·중복이면 실패를 그대로 보고한다
(호출자인 API 레이어가 "해당 Context 조기 종료 후 다음 Context"를 결정한다 — 이 함수는
Context 진행 흐름을 모르므로 그 판단을 대신하지 않는다).

Cache는 아직 실제로 채워 넣지 않았다(발표용 사전 캐시 준비는 별도 단계) — 인터페이스만
미리 맞춰뒀고, 기본값은 항상 MISS다.
"""

from __future__ import annotations

from pydantic import BaseModel

from src.data.questions.tail_option_blueprints import blueprint_for_target_trait
from src.engines.question_quality_gate import run_quality_gate
from src.llm.protocols import ChatLLMClient, LLMCallError
from src.schemas.context import ContextDefinition
from src.schemas.question import (
    FinalizedQuestion,
    QuestionGenerationResult,
    finalize_question,
)
from src.schemas.trait import TraitDefinition

SYSTEM_PROMPT = """당신은 고등학생 진로 탐색 설문의 질문 생성기입니다. 다음 규칙을 반드시 지키세요.
- 학생이 선택한 Context(관심 영역) 안에서 질문합니다.
- 행동 선호를 묻습니다. "잘하나요/능력이 있나요" 같은 자기평가를 요구하지 않습니다.
- 직업명이나 학과명을 직접 언급하지 않습니다.
- 특정 선택지가 다른 선택지보다 도덕적으로나 사회적으로 더 좋아 보이게 쓰지 않습니다.
- 선택지 5개의 길이와 구체성을 비슷하게 맞춥니다.
- 주어진 Role마다 정확히 하나의 자연스러운 한국어 선택지 문장을 만듭니다. Role의 순서와
  role_id는 그대로 유지하고, 새 role_id를 만들지 않습니다.
- target_traits와 frame_id는 입력으로 주어진 값을 그대로 반환합니다."""


def _build_user_prompt(
    *,
    context_definition: ContextDefinition,
    trait_definition: TraitDefinition,
    frame_id: str,
    frame_text: str,
    blueprint_roles: list[str],
) -> str:
    role_list = "\n".join(f"- {role_id}" for role_id in blueprint_roles)
    return f"""[Context]
label: {context_definition.label}
description: {context_definition.description}
예시 활동: {', '.join(context_definition.example_activities)}

[목표 Trait — 이 질문이 확인하려는 것]
label: {trait_definition.label}
definition: {trait_definition.definition}
긍정 지표: {', '.join(trait_definition.positive_indicators)}

[질문 Frame — 어떤 상황/말투로 물을지]
frame_id: {frame_id}
문구 힌트: {frame_text}

[Option Role — 이 role_id 순서 그대로, 각각 하나의 선택지 문장을 만들 것]
{role_list}

context 필드에는 "{context_definition.context_id}"를, target_traits 필드에는
["{trait_definition.trait_id}"]를, frame_id 필드에는 "{frame_id}"를 그대로 넣어 반환하세요."""


class QuestionGenerationOutcome(BaseModel):
    question: FinalizedQuestion | None
    source: str  # "cache" | "llm" | "backup" | "exhausted"
    secondary_trait_hypotheses: list[str] = []
    failure_reason: str | None = None


def generate_tail_question(
    *,
    question_id: str,
    context_definition: ContextDefinition,
    trait_definition: TraitDefinition,
    frame_id: str,
    frame_text: str,
    llm_client: ChatLLMClient,
    previous_question_texts: list[str] | None = None,
    backup_questions: list[FinalizedQuestion] | None = None,
    used_backup_question_ids: set[str] | None = None,
    question_cache: dict[str, FinalizedQuestion] | None = None,
    max_regenerations: int = 1,
) -> QuestionGenerationOutcome:
    previous_question_texts = previous_question_texts or []
    backup_questions = backup_questions or []
    used_backup_question_ids = used_backup_question_ids or set()
    question_cache = question_cache or {}

    cache_key = f"{context_definition.context_id}:{frame_id}:{trait_definition.trait_id}"
    cached = question_cache.get(cache_key)
    if cached is not None:
        gate = run_quality_gate(cached, previous_question_texts)
        if gate.passed:
            return QuestionGenerationOutcome(question=cached, source="cache")
        # 캐시된 질문도 Guardrail은 통과해야 한다 — 실패하면 조용히 넘기지 않고 실시간 생성으로 이어간다.

    blueprint = blueprint_for_target_trait(trait_definition.trait_id)
    role_ids = [role.role_id for role in blueprint.roles]
    user_prompt = _build_user_prompt(
        context_definition=context_definition,
        trait_definition=trait_definition,
        frame_id=frame_id,
        frame_text=frame_text,
        blueprint_roles=role_ids,
    )

    last_failure: str | None = None
    for _ in range(max_regenerations + 1):
        try:
            result = llm_client.complete_structured(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_model=QuestionGenerationResult,
            )
        except LLMCallError as exc:
            last_failure = f"LLM 호출 실패: {exc}"
            continue

        try:
            finalized = finalize_question(question_id, result.question, blueprint)
        except ValueError as exc:
            last_failure = f"Role ID 불일치로 거부: {exc}"
            continue

        gate = run_quality_gate(finalized, previous_question_texts)
        if not gate.passed:
            last_failure = f"Quality Gate 실패: {'; '.join(gate.failures)}"
            continue

        return QuestionGenerationOutcome(
            question=finalized,
            source="llm",
            secondary_trait_hypotheses=result.secondary_trait_hypotheses_from_previous_answer,
        )

    for backup in backup_questions:
        if backup.question_id not in used_backup_question_ids:
            return QuestionGenerationOutcome(
                question=backup, source="backup", failure_reason=last_failure
            )

    return QuestionGenerationOutcome(
        question=None,
        source="exhausted",
        failure_reason=last_failure or "Backup Question 소진",
    )
