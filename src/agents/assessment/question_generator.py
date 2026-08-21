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
- 질문 문장은 상황을 한 번만 제시하는 의문문으로 씁니다. 선택지는 그 상황에서 "무엇을
  할지"를 짧게 서술하는 행동 문장으로 씁니다("~한다", "~살펴본다", "~찾아본다" 등) —
  선택지를 "~하는 편인가요?", "~인가요?" 같은 완결된 의문문으로 쓰지 않습니다. 질문
  문장을 선택지 안에서 그대로 반복하지 않습니다(질문과 선택지가 같은 문장이 되면 안
  됩니다).
- 주어진 Role마다 정확히 하나의 자연스러운 한국어 선택지 문장을 만듭니다. Role의 순서와
  role_id는 그대로 유지하고, 새 role_id를 만들지 않습니다.
- "문구 힌트"는 상황의 전체적인 느낌만 참고하는 재료입니다. 목표 Trait의 실제 내용과
  안 어울리면 힌트 문구를 그대로 베끼지 말고, 그 Trait에 자연스럽게 맞는 구체적 상황으로
  바꿔서 씁니다 — 억지로 끼워 맞춘 듯한 질문보다, 고등학생이 실제로 마주칠 법한 자연스러운
  상황을 우선합니다.
- 질문의 상황 설정은 아래 [Option Role] 목록에 있는 Trait 5개 전부가 그 상황에서 자연스러운
  답이 될 수 있을 만큼 넓게 잡습니다. 예를 들어 "전략을 세울 때"처럼 특정 Trait(원인 분석,
  계획 등)에만 맞고 다른 Trait(시각적 표현, 감정 해석 등)에는 억지스러운 좁은 상황을
  만들지 않습니다. 5개 Trait를 모두 훑어본 뒤, 다섯 답이 전부 말이 되는 더 일반적인
  질문으로 잡으세요.
- target_traits와 frame_id는 입력으로 주어진 값을 그대로 반환합니다.
- 질문은 그 자체로 자연스럽게 읽히는 완결된 한 문장이어야 합니다. "~을 이어서",
  "~하는 성향을 이어", "~인지 확인하기 위해", "~에 이어" 같이 이전 질문·답변을
  요약하거나 언급하는 표현은 절대 쓰지 않습니다 — 설문지가 아니라 자연스러운 대화처럼
  읽혀야 합니다.
- "참고용 배경 정보"가 주어지면, 그 내용을 문장에 직접 언급하거나 요약하지 않습니다.
  이 학생이 방금 어떤 것에 흥미를 보였는지 알려주는 힌트일 뿐이며, 상황이나 소재를
  고를 때 은근히만 참고합니다. 무엇을 측정할지(목표 Trait, Option Role 구성)는
  이 정보와 무관하게 그대로 유지합니다."""


def _build_user_prompt(
    *,
    context_definition: ContextDefinition,
    trait_definition: TraitDefinition,
    frame_id: str,
    frame_text: str,
    blueprint_role_trait_labels: list[tuple[str, str]],
    previous_next_probe: str | None = None,
) -> str:
    role_list = "\n".join(
        f"- {role_id} (측정 대상: {trait_label})"
        for role_id, trait_label in blueprint_role_trait_labels
    )
    continuity_block = ""
    if previous_next_probe:
        continuity_block = f"""
[참고용 배경 정보 — 질문 문장에 직접 언급·요약하지 말 것. 소재 선택에만 은근히 참고]
{previous_next_probe}
"""
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
{continuity_block}
[Option Role — 이 role_id 순서 그대로, 각각 하나의 선택지 문장을 만들 것. 괄호 안은 이
Role이 실제로 측정하는 Trait이니 질문 상황을 잡을 때 5개 전부를 참고할 것]
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
    all_trait_labels: dict[str, str],
    frame_id: str,
    frame_text: str,
    llm_client: ChatLLMClient,
    previous_question_texts: list[str] | None = None,
    previous_next_probe: str | None = None,
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
    role_trait_labels: list[tuple[str, str]] = []
    for role in blueprint.roles:
        role_trait_id = next(iter(role.primary_trait_delta))
        role_trait_labels.append((role.role_id, all_trait_labels.get(role_trait_id, role_trait_id)))
    user_prompt = _build_user_prompt(
        context_definition=context_definition,
        trait_definition=trait_definition,
        frame_id=frame_id,
        frame_text=frame_text,
        blueprint_role_trait_labels=role_trait_labels,
        previous_next_probe=previous_next_probe,
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
