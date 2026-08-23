"""§5-2 Assessment Graph 중 "Question Generator → Quality Gate → 재생성 또는 Fallback"
구간을 실제 LangGraph StateGraph로 구현한다 — 6단계.

CLAUDE.md "질문 생성 실패 시 Cache, 재생성, Backup 순서로 완주 가능한 경로를 제공한다"를
Conditional Edge로 그대로 표현한다: `generate_attempt` Node에서 실패하면 재시도 횟수가
남았을 때는 자기 자신으로 되돌아가는 Edge(재생성 루프), 소진되면 `use_backup`으로 가는
Edge를 탄다 — 예전에는 이 흐름이 for 루프 안에 숨어 있었는데, 이제 그래프 구조로 드러난다.

이 파일이 `generate_tail_question()`의 유일한 실제 구현이다. §10 System Prompt·User
Prompt 조립 로직은 그대로 옮겨왔다(문구 변경 없음) — question_generator.py는 이 함수를
재노출(re-export)하기만 한다.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from langgraph.graph import END, START, StateGraph
from langsmith.run_helpers import tracing_context

from src.data.questions.anchor_backup_applicability import ANCHOR_BACKUP_APPLICABILITY_BY_QUESTION_ID
from src.data.questions.backup_question_applicability import BACKUP_APPLICABILITY_BY_QUESTION_ID

# 2026-08-23 Trait Ontology v2(2.5.4단계) §3 — 기존 6개(all-permissive)와 새 15개
# (Anchor 하나로 제한)를 한 조회 표로 합친다. question_id가 서로 겹치지 않아 병합
# 순서는 결과에 영향이 없다.
_ALL_BACKUP_APPLICABILITY_BY_QUESTION_ID = {
    **BACKUP_APPLICABILITY_BY_QUESTION_ID, **ANCHOR_BACKUP_APPLICABILITY_BY_QUESTION_ID,
}
from src.data.questions.tail_option_blueprints import TAIL_OPTION_BLUEPRINTS_BY_ID
from src.engines.backup_applicability_check import check_backup_candidate
from src.engines.question_quality_gate import run_quality_gate
from src.llm.protocols import ChatLLMClient, LLMCallError
from src.schemas.context import ContextDefinition
from src.schemas.context_anchor_presentation import ContextAnchorPresentation
from src.schemas.question import (
    FinalizedQuestion,
    QuestionGenerationResult,
    finalize_question,
)
from src.schemas.trait import TraitDefinition

SYSTEM_PROMPT = """당신은 고등학생 진로 탐색 설문의 질문 생성기입니다. 다음 규칙을 반드시 지키세요.
- 학생이 선택한 Context(관심 영역) 안에서만 질문합니다. 예를 들어 Context가 "게임"이면
  질문의 행동 무대는 항상 게임이어야 합니다 — "새로운 작품을 만들 때"처럼 다른 활동(제작,
  미디어 편집 등)으로 슬쩍 옮겨가지 않습니다. 5개 Trait에 맞게 상황을 넓힐 때도 이 Context
  범위 밖으로 나가면 안 됩니다.
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
- 질문의 상황 설정은 [Option Role] 목록에 있는 Trait 5개 전부가 그 상황에서 자연스러운
  답이 될 수 있을 만큼 넓게 잡습니다. [Context]의 "예시 활동"은 참고용일 뿐, 5개 Trait
  중 일부와 안 맞으면 억지로 쓰지 않습니다.
  나쁜 예: "게임 전략을 세울 때 어디에 집중하나요?" — "전략"은 승부를 위한 활동이라
  원인 분석·계획 같은 Trait에는 맞지만, 시각적 표현("화면 디자인을 살펴본다")이나
  감정 해석 같은 Trait는 전략과 아예 무관한 별개의 활동이라 억지스럽습니다.
  좋은 예: "게임을 할 때 어디에 가장 오래 집중하나요?"처럼 Context 자체를 아우르는
  넓은 활동으로 잡으면, 전략 분석·화면 감상·감정 이입·패턴 분석이 전부 자연스러운
  답이 됩니다. 이 예시처럼, 목표 Trait만 보고 좁은 활동(전략/승부/경쟁 등)을 먼저
  떠올리지 말고, 반드시 5개 Trait를 모두 훑어본 뒤 그중 가장 안 맞는 Trait 기준으로
  상황을 넓히세요.
- 상황을 넓힐 때도 표현은 항상 고등학생이 실제로 쓸 법한 자연스러운 말투여야 합니다.
  "게임"을 "게임 관련 작업"·"게임 활동"처럼 딱딱하고 사무적인 말로 바꿔 부르지
  않습니다. 나쁜 예: "제한된 시간 내에 게임 관련 작업을 할 때 무엇에 가장 먼저
  집중하나요?" — "게임 관련 작업"은 실제 대화에서 안 쓰는 어색한 표현입니다.
  좋은 예: "시간이 별로 없을 때 게임에서 뭘 가장 먼저 하나요?"처럼 짧고 구어체에
  가깝게 씁니다. 넓히는 것과 어색하게 딱딱한 말로 바꾸는 것은 다릅니다.
- target_traits와 frame_id는 입력으로 주어진 값을 그대로 반환합니다.
- 질문은 그 자체로 자연스럽게 읽히는 완결된 한 문장이어야 합니다. "~을 이어서",
  "~하는 성향을 이어", "~인지 확인하기 위해", "~에 이어" 같이 이전 질문·답변을
  요약하거나 언급하는 표현은 절대 쓰지 않습니다 — 설문지가 아니라 자연스러운 대화처럼
  읽혀야 합니다.
- "직전 질문·답변"과 "참고용 배경 정보"가 주어지면, 그 내용을 문장에 직접 언급·요약·인용
  하지 않습니다. 직전에 이 학생이 무엇을 물어봤고 무엇을 선택했는지 아는 상태에서, 자연스럽게
  이어지는 다음 상황을 고르는 데만 참고합니다(예: 같은 소재를 다른 각도에서 다루기, 방금
  나온 소재를 반복하지 않기). 무엇을 측정할지(목표 Trait, Option Role 구성)는 이 정보와
  무관하게 입력값 그대로 유지합니다.
- "이번 질문의 목적"이 주어지면 내부 참고용입니다 — 그 표현(예: "심화 확인", "교차 확인"
  같은 평가 용어)을 질문 문장에 그대로 쓰지 않습니다."""


def _build_user_prompt(
    *,
    context_definition: ContextDefinition,
    trait_definition: TraitDefinition,
    frame_id: str,
    frame_text: str,
    blueprint_role_trait_labels: list[tuple[str, str]],
    purpose: str | None = None,
    previous_question_text: str | None = None,
    previous_answer_text: str | None = None,
    previous_next_probe: str | None = None,
    anchor: ContextAnchorPresentation | None = None,
) -> str:
    role_list = "\n".join(
        f"- {role_id} (측정 대상: {trait_label})"
        for role_id, trait_label in blueprint_role_trait_labels
    )
    anchor_block = ""
    if anchor is not None:
        # 2026-08-23 Trait Ontology v2(2.5.2단계) §3 — v2_direct_probe_generator.py의
        # 같은 원칙을 그대로 따른다: role_id·Trait 이름을 언급하지 않는다(LLM이
        # Anchor에서 새 Trait를 추론할 실마리를 주지 않기 위해서), 내부 점수·Profile·
        # 전공 추천값도 넣지 않는다.
        anchor_block = f"""
[학생이 선택한 세부 Context — 상황과 단어 선택에만 참고할 것, 여기서 새로운 성향을
추론하지 말 것]
상황 이름: {anchor.label}
사용 가능한 상황 표현: {", ".join(anchor.situation_terms)}
우선적으로 활용할 장면: {", ".join(anchor.preferred_scenarios)}
절대 전제하면 안 되는 상황: {", ".join(anchor.forbidden_assumptions) if anchor.forbidden_assumptions else "(없음)"}
"""
    continuity_lines: list[str] = []
    if previous_question_text:
        continuity_lines.append(f"직전 질문: {previous_question_text}")
    if previous_answer_text:
        continuity_lines.append(f"학생이 고른 답: {previous_answer_text}")
    if previous_next_probe:
        continuity_lines.append(f"그 답이 보여준 성향(참고용 메모): {previous_next_probe}")
    continuity_block = ""
    if continuity_lines:
        continuity_block = (
            "\n[직전 질문·답변 — 문장에 직접 언급·인용하지 말 것. 자연스러운 흐름 참고용]\n"
            + "\n".join(continuity_lines)
            + "\n"
        )

    purpose_block = ""
    if purpose:
        purpose_block = f"\n[이번 질문의 목적 — 내부 참고용, 문장에 노출하지 말 것]\n{purpose}\n"

    return f"""[Context — 질문의 행동 무대는 항상 이 안에 있어야 함]
label: {context_definition.label}
description: {context_definition.description}
예시 활동(참고용 — 아래 5개 Trait와 안 맞으면 무시해도 되지만, Context 자체를 벗어나면 안 됨): {', '.join(context_definition.example_activities)}
{anchor_block}
[이번 질문이 다뤄야 할 Trait 5개 — 질문 상황을 잡기 전에 반드시 전부 확인할 것]
{role_list}

[목표 Trait — 이 중 실제로 Evidence로 기록되는 것]
label: {trait_definition.label}
definition: {trait_definition.definition}
긍정 지표: {', '.join(trait_definition.positive_indicators)}

[질문 Frame — 어떤 상황/말투로 물을지. 위 5개 Trait와 안 맞으면 아래 힌트보다
5개 Trait에 맞는 넓은 상황을 우선할 것]
frame_id: {frame_id}
문구 힌트: {frame_text}
{purpose_block}{continuity_block}
[Option Role — 위와 같은 role_id 순서 그대로, 각각 하나의 선택지 문장을 만들 것]
{role_list}

context 필드에는 "{context_definition.context_id}"를, target_traits 필드에는
["{trait_definition.trait_id}"]를, frame_id 필드에는 "{frame_id}"를 그대로 넣어 반환하세요."""


class QuestionGenerationOutcome(BaseModel):
    question: FinalizedQuestion | None
    source: str  # "cache" | "llm" | "backup" | "exhausted"
    secondary_trait_hypotheses: list[str] = []
    failure_reason: str | None = None
    # 2026-08-23 Trait Ontology v2(2.5.3단계) §2/§12 — Backup 후보 중 몇 개를
    # 검사했고 몇 개를 거부했는지(질문·선택지 원문은 담지 않는다 — Trace로 안전하게
    # 보낼 수 있는 숫자만).
    backup_candidates_checked: int = 0
    backup_candidates_rejected: int = 0


def classify_generation_failure(failure_reason: str | None) -> str | None:
    """2026-08-22 리뷰: failure_reason 원문(예외 메시지 포함 가능)을 LangSmith Trace에
    그대로 보내지 않는다 — 이 함수가 만드는 고정된 error_type만 Sanitizer의 허용 목록을
    통과한다(src/tracing/sanitizer.py `_ALLOWED_ERROR_TYPES`와 반드시 맞춰서 유지한다)."""

    if failure_reason is None:
        return None
    if failure_reason.startswith("LLM 호출 실패"):
        return "llm_call_error"
    if failure_reason.startswith("Role ID 불일치로 거부"):
        return "role_id_mismatch"
    if failure_reason.startswith("Quality Gate 실패"):
        return "quality_gate_failure"
    return "unknown_error"


class QuestionGenerationGraphState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    question_id: str
    context_definition: ContextDefinition
    trait_definition: TraitDefinition
    all_trait_labels: dict[str, str]
    option_blueprint_id: str
    frame_id: str
    frame_text: str
    # ChatLLMClient는 Protocol이라(런타임 체크 불가) Pydantic 필드 타입으로 쓰면
    # is-instance 검증이 깨진다 — Any로 두고, 실제 타입 계약은 generate_tail_question()의
    # 함수 시그니처(순수 타입 힌트, 검증 없음)가 담당한다.
    llm_client: Any
    purpose: str | None = None
    previous_question_texts: list[str] = Field(default_factory=list)
    previous_answer_text: str | None = None
    previous_next_probe: str | None = None
    backup_questions: list[FinalizedQuestion] = Field(default_factory=list)
    used_backup_question_ids: set[str] = Field(default_factory=set)
    question_cache: dict[str, FinalizedQuestion] = Field(default_factory=dict)
    max_regenerations: int = 1
    # 2.5.2단계 §2/§5 — 없으면(None) 기존 동작과 완전히 동일하다(중립 질문).
    anchor: ContextAnchorPresentation | None = None

    # Node 간 전달용 중간 결과
    user_prompt: str | None = None
    attempt_count: int = 0
    last_failure: str | None = None
    outcome: QuestionGenerationOutcome | None = None


def _check_cache(g: QuestionGenerationGraphState) -> dict:
    # 2.5.2단계 §5 — Anchor를 Cache Key에 포함한다. anchor_id가 없으면 "neutral"을 써서
    # (아무 Anchor도 선택하지 않은) 중립 요청과 특정 Anchor 요청이 같은 Key를 쓰지
    # 않게 한다 — Anchor A로 생성된 질문이 Anchor B(또는 중립) 학생에게 재사용되지
    # 않아야 한다(§5 요구사항).
    anchor_key = g.anchor.anchor_id if g.anchor is not None else "neutral"
    cache_key = (
        f"{g.context_definition.context_id}:{anchor_key}:{g.option_blueprint_id}:"
        f"{g.frame_id}:{g.trait_definition.trait_id}"
    )
    cached = g.question_cache.get(cache_key)
    if cached is not None:
        forbidden_anchor_phrases = tuple(g.anchor.forbidden_assumptions) if g.anchor is not None else ()
        gate = run_quality_gate(
            cached, g.previous_question_texts, forbidden_anchor_assumption_phrases=forbidden_anchor_phrases,
        )
        if gate.passed:
            return {"outcome": QuestionGenerationOutcome(question=cached, source="cache")}
        # 캐시된 질문도 Guardrail은 통과해야 한다 — 실패하면 조용히 넘기지 않고 실시간 생성으로 이어간다.
    return {}


def _route_after_cache(g: QuestionGenerationGraphState) -> str:
    return "hit" if g.outcome is not None else "miss"


def _prepare_prompt(g: QuestionGenerationGraphState) -> dict:
    blueprint = TAIL_OPTION_BLUEPRINTS_BY_ID[g.option_blueprint_id]
    role_trait_labels: list[tuple[str, str]] = []
    for role in blueprint.roles:
        role_trait_id = next(iter(role.primary_trait_delta))
        role_trait_labels.append((role.role_id, g.all_trait_labels.get(role_trait_id, role_trait_id)))
    previous_question_text = g.previous_question_texts[-1] if g.previous_question_texts else None
    user_prompt = _build_user_prompt(
        context_definition=g.context_definition,
        trait_definition=g.trait_definition,
        frame_id=g.frame_id,
        frame_text=g.frame_text,
        blueprint_role_trait_labels=role_trait_labels,
        purpose=g.purpose,
        previous_question_text=previous_question_text,
        previous_answer_text=g.previous_answer_text,
        previous_next_probe=g.previous_next_probe,
        anchor=g.anchor,
    )
    return {"user_prompt": user_prompt}


def _generate_attempt(g: QuestionGenerationGraphState) -> dict:
    """§10 LLM 호출 1회 + Role ID 검증 + §11 Quality Gate. target_traits는 LLM이 그대로
    반환한 값을 신뢰하지 않는다 — 무엇을 목표할지는 서버(Target Planner)가 이미 정한
    값이므로 여기서 강제로 덮어쓴다(CLAUDE.md "다음 질문 목표... 를 LLM에게 맡기지 않는다")."""

    blueprint = TAIL_OPTION_BLUEPRINTS_BY_ID[g.option_blueprint_id]
    try:
        result = g.llm_client.complete_structured(
            system_prompt=SYSTEM_PROMPT, user_prompt=g.user_prompt, response_model=QuestionGenerationResult
        )
    except LLMCallError as exc:
        return {"attempt_count": g.attempt_count + 1, "last_failure": f"LLM 호출 실패: {exc}"}

    try:
        finalized = finalize_question(g.question_id, result.question, blueprint)
    except ValueError as exc:
        return {"attempt_count": g.attempt_count + 1, "last_failure": f"Role ID 불일치로 거부: {exc}"}

    finalized = finalized.model_copy(update={"target_traits": [g.trait_definition.trait_id]})
    forbidden_anchor_phrases = tuple(g.anchor.forbidden_assumptions) if g.anchor is not None else ()
    gate = run_quality_gate(
        finalized, g.previous_question_texts, forbidden_anchor_assumption_phrases=forbidden_anchor_phrases,
    )
    if not gate.passed:
        return {
            "attempt_count": g.attempt_count + 1,
            "last_failure": f"Quality Gate 실패: {'; '.join(gate.failures)}",
        }

    return {
        "outcome": QuestionGenerationOutcome(
            question=finalized,
            source="llm",
            secondary_trait_hypotheses=result.secondary_trait_hypotheses_from_previous_answer,
        )
    }


def _route_after_attempt(g: QuestionGenerationGraphState) -> str:
    if g.outcome is not None:
        return "success"
    if g.attempt_count <= g.max_regenerations:
        return "retry"  # 재생성 Edge — generate_attempt로 되돌아간다
    return "backup"


def _use_backup(g: QuestionGenerationGraphState) -> dict:
    """2026-08-23 Trait Ontology v2(2.5.3단계) §1/§2 — 이전에는 이 함수가 사용하지
    않은 첫 Backup을 검증 없이 그대로 반환했다(재현: Anchor가 "팀원"을 금지해도
    "팀원들과"가 들어간 Backup이 그대로 나갔다). 이제 LLM·Cache 질문과 동일한
    Quality Gate(§2)와 Applicability(§3)를 통과한 후보만 반환한다 — 부적합한 후보는
    건너뛰고 다음 후보를 검사하며, 호환되는 후보가 하나도 없으면 잘못된 질문을 그냥
    반환하는 대신 `exhausted`로 끝낸다. 후보 순서는 `g.backup_questions`(호출자가
    고정된 리스트로 넘긴다)를 그대로 따르므로 같은 State에 대해 항상 결정론적이다."""

    checked = 0
    rejected = 0
    for backup in g.backup_questions:
        if backup.question_id in g.used_backup_question_ids:
            continue
        checked += 1

        applicability = _ALL_BACKUP_APPLICABILITY_BY_QUESTION_ID.get(backup.question_id)
        gate = check_backup_candidate(
            backup, anchor=g.anchor, applicability=applicability,
            previous_question_texts=g.previous_question_texts,
        )
        if not gate.passed:
            rejected += 1
            continue

        return {
            "outcome": QuestionGenerationOutcome(
                question=backup, source="backup", failure_reason=g.last_failure,
                backup_candidates_checked=checked, backup_candidates_rejected=rejected,
            )
        }

    return {
        "outcome": QuestionGenerationOutcome(
            question=None, source="exhausted", failure_reason=g.last_failure or "Backup Question 소진",
            backup_candidates_checked=checked, backup_candidates_rejected=rejected,
        )
    }


def build_question_generation_graph():
    graph = StateGraph(QuestionGenerationGraphState)
    graph.add_node("check_cache", _check_cache)
    graph.add_node("prepare_prompt", _prepare_prompt)
    graph.add_node("generate_attempt", _generate_attempt)
    graph.add_node("use_backup", _use_backup)

    graph.add_edge(START, "check_cache")
    graph.add_conditional_edges("check_cache", _route_after_cache, {"hit": END, "miss": "prepare_prompt"})
    graph.add_edge("prepare_prompt", "generate_attempt")
    graph.add_conditional_edges(
        "generate_attempt",
        _route_after_attempt,
        {"success": END, "retry": "generate_attempt", "backup": "use_backup"},
    )
    graph.add_edge("use_backup", END)
    return graph.compile()


_COMPILED_QUESTION_GENERATION_GRAPH = build_question_generation_graph()


def generate_tail_question(
    *,
    question_id: str,
    context_definition: ContextDefinition,
    trait_definition: TraitDefinition,
    all_trait_labels: dict[str, str],
    option_blueprint_id: str,
    frame_id: str,
    frame_text: str,
    llm_client: ChatLLMClient,
    purpose: str | None = None,
    previous_question_texts: list[str] | None = None,
    previous_answer_text: str | None = None,
    previous_next_probe: str | None = None,
    backup_questions: list[FinalizedQuestion] | None = None,
    used_backup_question_ids: set[str] | None = None,
    question_cache: dict[str, FinalizedQuestion] | None = None,
    max_regenerations: int = 1,
    anchor: ContextAnchorPresentation | None = None,
) -> QuestionGenerationOutcome:
    """예전 question_generator.generate_tail_question과 시그니처·반환값이 동일하다 —
    내부만 LangGraph 실행(check_cache → prepare_prompt → generate_attempt[재생성 루프]
    → use_backup)으로 바뀌었다.

    2026-08-23 Trait Ontology v2(2.5.2단계) §2 — `anchor`가 None이면 기존 동작과
    완전히 동일하다(중립 질문, 기존 Prompt·Cache Key 그대로)."""

    graph_input = QuestionGenerationGraphState(
        question_id=question_id,
        context_definition=context_definition,
        trait_definition=trait_definition,
        all_trait_labels=all_trait_labels,
        option_blueprint_id=option_blueprint_id,
        frame_id=frame_id,
        frame_text=frame_text,
        llm_client=llm_client,
        purpose=purpose,
        previous_question_texts=previous_question_texts or [],
        previous_answer_text=previous_answer_text,
        previous_next_probe=previous_next_probe,
        backup_questions=backup_questions or [],
        used_backup_question_ids=used_backup_question_ids or set(),
        question_cache=question_cache or {},
        max_regenerations=max_regenerations,
        anchor=anchor,
    )
    # answer_graph.py와 동일한 이유로 LangChain/LangGraph의 자동(비Sanitizer) LangSmith
    # 전송을 명시적으로 끈다 — 여기엔 LLM이 생성한 질문·선택지 원문이 그대로 담긴다.
    with tracing_context(enabled=False):
        result = _COMPILED_QUESTION_GENERATION_GRAPH.invoke(graph_input)
    return result["outcome"]
