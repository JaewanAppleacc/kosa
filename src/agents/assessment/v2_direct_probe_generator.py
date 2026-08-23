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
from src.schemas.context_anchor_presentation import ContextAnchorPresentation
from src.schemas.question import FinalizedQuestion, QuestionGenerationResult
from src.schemas.v2_direct_probe import V2DirectProbeBlueprint, finalize_v2_probe_question

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


def _build_user_prompt(
    *, context_definition: ContextDefinition, blueprint: V2DirectProbeBlueprint,
    anchor: ContextAnchorPresentation | None = None,
) -> str:
    role_list = "\n".join(f"- {mapping.role_id}" for mapping in blueprint.option_mappings)
    reference_lines = "\n".join(f"- {opt.role_id}: {opt.text}" for opt in blueprint.base_question.options)
    anchor_block = ""
    if anchor is not None:
        # 2026-08-23 Trait Ontology v2(2.5.1단계) §6 — Anchor는 "상황 배경"만 조정하는
        # 정보다. 여기서 role_id·Trait를 언급하지 않는다 — LLM이 Anchor에서 새 Trait를
        # 추론할 실마리를 아예 주지 않기 위해서다.
        anchor_block = f"""

[학생이 고른 세부 상황(Anchor) — 질문의 배경 설정에만 참고할 것, 여기서 새로운 성향을
추론하지 말 것]
상황 이름: {anchor.label}
상황에서 쓸 수 있는 표현: {", ".join(anchor.situation_terms)}
선호하는 장면: {", ".join(anchor.preferred_scenarios)}
절대 전제하면 안 되는 것: {", ".join(anchor.forbidden_assumptions) if anchor.forbidden_assumptions else "(없음)"}"""
    return f"""[Context — 질문의 행동 무대는 항상 이 안에 있어야 함]
label: {context_definition.label}
description: {context_definition.description}
{anchor_block}

[참고용 기준 질문 — 그대로 베끼지 말고, 같은 상황·같은 Role 구성을 자연스러운 다른 표현으로 바꿔 쓸 것]
질문: {blueprint.base_question.question_text}
{reference_lines}

[Option Role — 위와 같은 role_id 순서 그대로, 각각 하나의 선택지 문장을 만들 것]
{role_list}

context 필드에는 "{context_definition.context_id}"를, target_traits 필드에는 []를,
frame_id 필드에는 "{blueprint.question_frame_id}"를 그대로 넣어 반환하세요."""


class V2DirectProbeGenerationOutcome(BaseModel):
    # 2026-08-23 Trait Ontology v2(2.9.1단계) §4: `allow_base_question_fallback=False`로
    # 호출했는데 LLM이 끝내 실패하면 question이 None이다 — 호출부가 다른 대체 경로
    # (Pack Anchor Backup)를 찾아야 한다는 신호다. Legacy 호출(allow_base_question_
    # fallback=True, 기본값)에서는 여전히 None이 되지 않는다(회귀 없음).
    question: FinalizedQuestion | None
    source: str  # "llm" | "backup" | "fallback_disallowed"


def generate_v2_direct_probe_question(
    *,
    question_id: str,
    context_definition: ContextDefinition,
    blueprint: V2DirectProbeBlueprint,
    llm_client: ChatLLMClient | None,
    max_regenerations: int = 1,
    anchor: ContextAnchorPresentation | None = None,
    allow_base_question_fallback: bool = True,
) -> V2DirectProbeGenerationOutcome:
    """LLM이 결정하면 안 되는 것(target_trait_id/Blueprint ID/Option Role/Trait
    Signal/weight/Related Concept/질문 종료 여부/다음 Trait 선택) 중 이 함수가 다루는
    부분(Option Role)은 `finalize_v2_probe_question()`이 이미 강제한다 — LLM이 반환한
    role_id가 `blueprint.option_mappings`에 없으면 거부한다. LLM은 NO_SIGNAL/TRAIT_SIGNAL
    구분 자체를 아예 모른다(프롬프트에 role_id와 참고 문구만 전달한다) — role마다 문장
    표현만 자연스럽게 바꿀 뿐이므로 Mapping을 다른 Trait 행동으로 바꿔치기할 수 없다.

    2026-08-23 Trait Ontology v2(2.5.1단계) §6/§10 — `anchor`는 이 Context에서 학생이
    고른 Anchor 정보다(없으면 기존과 동일하게 중립 문구로 생성). Anchor가 있으면
    `forbidden_assumptions`가 생성된 문장에 남아 있는지도 Quality Gate로 추가 검사하고,
    걸리면 재생성한다 — 재생성도 실패하면 Anchor를 반영하지 않은 중립
    Fallback(`blueprint.base_question`)을 그대로 쓴다(§6 "재생성 실패 시 ... 중립
    Fallback 사용"). Fallback 자체는 Anchor별로 미리 써 둔 문구가 아니다 — 14개
    Blueprint × 5개 Anchor로 Mapping을 늘리지 않기 위한 의도적 선택이다(§2 금지 구조,
    한계는 §24에 기록).

    2026-08-23 Trait Ontology v2(2.9.1단계) §4: `allow_base_question_fallback=False`면
    LLM이 꺼져 있거나 재생성까지 전부 실패했을 때 `blueprint.base_question`을 절대
    돌려주지 않는다(question=None, source="fallback_disallowed") — ContextPack 공용
    Adaptive Probe의 `base_question`은 Legacy game/media/school_life 문구를 그대로
    복제한 것이라(§5, `context_pack_shared_probe_blueprints.py`), 신규 Context 학생에게
    노출하면 안 되는 원본 그대로다. Legacy 3-Context 호출은 기본값 True를 그대로 쓰므로
    이 함수의 기존 Fallback 동작(LLM OFF에서도 EXACT_BLUEPRINT로 완주)은 회귀하지
    않는다."""

    fallback = blueprint.base_question.model_copy(update={"question_id": question_id})

    if llm_client is None:
        if not allow_base_question_fallback:
            return V2DirectProbeGenerationOutcome(question=None, source="fallback_disallowed")
        return V2DirectProbeGenerationOutcome(question=fallback, source="backup")

    user_prompt = _build_user_prompt(context_definition=context_definition, blueprint=blueprint, anchor=anchor)
    forbidden_anchor_phrases = tuple(anchor.forbidden_assumptions) if anchor is not None else ()
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
            finalized = finalize_v2_probe_question(question_id, result.question, blueprint)
        except ValueError:
            continue
        finalized = finalized.model_copy(update={"target_traits": []})
        gate = run_quality_gate(
            finalized, forbidden_trait_label_phrases=V2_DIRECT_PROBE_TRAIT_LABEL_PHRASES,
            forbidden_anchor_assumption_phrases=forbidden_anchor_phrases,
        )
        if gate.passed:
            return V2DirectProbeGenerationOutcome(question=finalized, source="llm")

    if not allow_base_question_fallback:
        return V2DirectProbeGenerationOutcome(question=None, source="fallback_disallowed")
    return V2DirectProbeGenerationOutcome(question=fallback, source="backup")
