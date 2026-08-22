"""§5-2 Assessment Graph 중 "학생 답변 → Evidence Update → Stop/Continue → Target Planner"
구간을 실제 LangGraph StateGraph로 구현한다 — 6단계: 순수 함수(evidence_engine,
conflict_engine, target_planner)를 LangGraph Node로 감싼다.

CLAUDE.md "LangGraph는 상태 전이와 반복을 관리한다"를 그대로 따른다 — 이 파일은 어떤
계산도 직접 하지 않는다. Node는 전부 기존 §12/§12-1/§8 순수 함수를 그대로 호출할 뿐이고,
이 파일이 새로 추가하는 건 Node 사이의 흐름(Conditional Edge)뿐이다.

`submit_answer()`는 예전 answer_processor.submit_answer와 정확히 같은 시그니처·반환
타입·"state를 제자리에서 mutate한다" 계약을 유지한다 — main.py는 이 파일이 LangGraph를
쓰는지 몰라도 된다(API 응답 계약 유지, 6단계 지시사항).
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from langgraph.graph import END, START, StateGraph
from langsmith.run_helpers import tracing_context

from src.agents.assessment.target_planner import PlannerDecision, decide_next_target
from src.engines.conflict_engine import detect_explicit_conflicts
from src.engines.evidence_engine import decide_stop_or_continue, summarize_trait_evidence
from src.ids import generate_evidence_id
from src.schemas.assessment_state import AnsweredQuestion, AssessmentState
from src.schemas.evidence import (
    ContrastDefinition,
    ContrastResolutionQuestionSpec,
    ContrastResolutionRecord,
    ContrastResolutionStatus,
    EvidenceOrigin,
    EvidenceRecord,
)
from src.schemas.question import FinalizedQuestion


class AnswerSubmissionResult(BaseModel):
    accepted: bool
    rejection_reason: str | None = None
    stop_decision: str | None = None  # "CONTINUE" | "STOP" | None(거부됐으면 None)
    next_planner_decision: PlannerDecision | None = None


class AnswerGraphState(BaseModel):
    """Graph 실행 동안만 쓰는 상태. `state` 필드 하나에 세션 전체 AssessmentState를
    담아 넘긴다("호환 가능한 Graph State" — AssessmentState 스키마 자체를 바꾸지 않는다).
    나머지 필드는 이번 호출의 입력값과, Node들이 서로 주고받는 중간 결과다."""

    state: AssessmentState
    question: FinalizedQuestion
    selected_option_id: str
    all_trait_ids: set[str]
    contrast_definitions: list[ContrastDefinition] = Field(default_factory=list)
    is_first_context_in_session: bool = False
    # contrast_id -> 확인 질문 Spec(어느 Role이 어떤 해소 결과인지 + 어느 Trait이 positive/
    # opposite인지). 2026-08-22 §12-1 확장.
    resolution_specs: dict[str, ContrastResolutionQuestionSpec] = Field(default_factory=dict)

    # Node 간 전달용 중간 결과 — 그래프 실행이 끝나면 AnswerSubmissionResult로 변환한다.
    accepted: bool = True
    rejection_reason: str | None = None
    stop_decision: str | None = None
    next_planner_decision: PlannerDecision | None = None
    contrast_ids_needing_resolution_question: set[str] = Field(default_factory=set)


def _validate_option(g: AnswerGraphState) -> dict:
    """§5-2 "Option 검증" — 학생이 실제로 이 질문에 제시된 선택지를 골랐는지 확인한다."""

    selected = next((o for o in g.question.options if o.option_id == g.selected_option_id), None)
    if selected is None:
        return {
            "accepted": False,
            "rejection_reason": (
                f"selected_option_id {g.selected_option_id!r}가 질문 "
                f"{g.question.question_id!r}의 선택지 목록에 없습니다."
            ),
        }
    return {"accepted": True}


def _route_after_validate(g: AnswerGraphState) -> str:
    return "continue" if g.accepted else "end"


def _evidence_update(g: AnswerGraphState) -> dict:
    """§12 Evidence Ledger 갱신 + §12-1 Explicit Conflict 판정. 기존
    answer_processor.submit_answer의 2~3단계를 그대로 옮긴 것이다 — 계산 로직 변경 없음."""

    state = g.state
    question = g.question
    selected_option = next(o for o in question.options if o.option_id == g.selected_option_id)
    # 2026-08-22 2차 리뷰: 확인 질문 답변은 일반 꼬리질문과 별도로 센다 — §5-3 4~6개
    # 상한은 일반 문항에만 적용되고, 확인 질문이 끼어들어도 다음 일반 질문의 §7-2
    # 위치·테마 계산이 밀리면 안 된다(위치는 questions_asked_in_current_context 기준).
    is_resolution_answer = question.contrast_id is not None

    evidence = EvidenceRecord(
        evidence_id=generate_evidence_id(),
        answer_id=f"ans_{question.question_id}_{len(state.answers) + 1:02d}",
        question_id=question.question_id,
        question_frame_id=question.frame_id,
        option_role_id=selected_option.role_id,
        option_text=selected_option.text,
        applied_primary_trait_delta=selected_option.primary_trait_delta,
        # 2026-08-22 4차 리뷰: 확인 질문 답변은 일반 Trait Evidence와 구분해서 남긴다 —
        # evidence_engine.summarize_trait_evidence/conflict_engine.detect_explicit_conflicts/
        # profile_engine.build_detailed_evidence_by_dimension이 전부 이미 PRIMARY_BLUEPRINT만
        # 걸러 쓰므로, 이 값만 바꾸면 세 계산에서 자동으로 제외된다(Evidence Ledger에서
        # 삭제하진 않는다 — 역추적·감사용으로는 그대로 남아있어야 한다).
        evidence_origin=(
            EvidenceOrigin.CONFLICT_RESOLUTION if is_resolution_answer else EvidenceOrigin.PRIMARY_BLUEPRINT
        ),
        context=question.context,
        source_type="seed_question" if question.frame_id == "seed_frame" else "generated_question",
        generator_version="v1",
        quality_gate_status="passed",
    )
    state.evidence_ledger.append(evidence)
    state.pending_next_probe = selected_option.next_probe
    state.pending_previous_question_text = question.question_text
    state.pending_previous_answer_text = selected_option.text
    state.answers.append(
        AnsweredQuestion(
            question_id=question.question_id,
            selected_option_id=g.selected_option_id,
            selected_role_id=selected_option.role_id,
        )
    )

    # 2026-08-22 4차 리뷰: opportunity_count(§12: "선택 가능했던 횟수")는 이
    # offered_trait_ids_by_question에서 계산된다 — 확인 질문에 나온 5개 선택지도 그대로
    # 넣으면, 답변 자체는 CONFLICT_RESOLUTION으로 분리해도 "planning을 볼 기회가 있었다"는
    # 흔적은 여전히 남아 opportunity_count가 늘어난다. 확인 질문은 §12-1 별도 정보이므로
    # 일반 기회 집계에서도 제외한다.
    if not is_resolution_answer:
        offered_traits: list[str] = []
        for option in question.options:
            offered_traits.extend(option.primary_trait_delta.keys())
        state.offered_trait_ids_by_question[question.question_id] = offered_traits

    if question.target_traits:
        state.recent_target_trait_ids.append(question.target_traits[0])
    state.used_frame_ids_in_current_context.append(question.frame_id)

    if is_resolution_answer:
        state.resolution_questions_asked_in_current_context += 1
    else:
        state.questions_asked_in_current_context += 1
        # §7-2: 이번이 이 Context의 Seed 답변이면, DEEPEN 테마가 참고할 Trait을 남긴다.
        if state.questions_asked_in_current_context == 1:
            state.current_context_seed_trait_id = sorted(selected_option.primary_trait_delta)[0]

    all_offered_sets = [set(v) for v in state.offered_trait_ids_by_question.values()]
    for trait_id in g.all_trait_ids:
        state.trait_summaries[trait_id] = summarize_trait_evidence(
            trait_id, state.evidence_ledger, all_offered_sets
        )

    # 2026-08-22 §12-1 확장: 이번 답변이 Explicit Conflict 확인 질문(question.contrast_id)에
    # 대한 답이면, Evidence Ledger는 그대로 두고 별도의 Resolution Record만 저장한다 —
    # 과거 Evidence를 지우거나 고치지 않는다("Evidence는 관찰된 답변 기록이고, Conflict
    # Resolution은 상충 Evidence의 해석 정보다").
    if is_resolution_answer:
        spec = g.resolution_specs.get(question.contrast_id)
        resolution_status = spec.role_resolution_map.get(selected_option.role_id) if spec else None
        if spec is not None and resolution_status is not None:
            preferred_trait_id: str | None = None
            opposite_trait_id: str | None = None
            context_dependent_trait_ids: list[str] = []
            if resolution_status == ContrastResolutionStatus.RESOLVED_POSITIVE:
                preferred_trait_id, opposite_trait_id = spec.positive_trait_id, spec.opposite_trait_id
            elif resolution_status == ContrastResolutionStatus.RESOLVED_OPPOSITE:
                preferred_trait_id, opposite_trait_id = spec.opposite_trait_id, spec.positive_trait_id
            elif resolution_status == ContrastResolutionStatus.RESOLVED_CONTEXT_DEPENDENT:
                context_dependent_trait_ids = [spec.positive_trait_id, spec.opposite_trait_id]
            # UNRESOLVED: 셋 다 비워둔다 — 이미 unresolved_conflict_trait_ids로 Mask되므로
            # Profile/Matching에서 확정적 추천 근거로 쓰이지 않는다.
            state.contrast_resolutions[question.contrast_id] = ContrastResolutionRecord(
                contrast_id=question.contrast_id,
                status=resolution_status,
                resolved_at_answer_id=evidence.answer_id,
                context_id=question.context,
                reason_option_id=g.selected_option_id,
                preferred_trait_id=preferred_trait_id,
                opposite_trait_id=opposite_trait_id,
                context_dependent_trait_ids=context_dependent_trait_ids,
            )
        state.pending_resolution_contrast_id = None

    conflict_result = detect_explicit_conflicts(
        state.evidence_ledger, g.contrast_definitions, state.contrast_resolutions
    )
    state.unresolved_conflict_trait_ids = conflict_result.unresolved_conflict_trait_ids
    state.unresolved_contrast_ids = {
        r.contrast_id for r in conflict_result.pair_results if r.status == "explicit_conflict"
    }
    for trait_id, summary in state.trait_summaries.items():
        state.trait_summaries[trait_id] = summary.model_copy(
            update={
                "explicit_conflict_count": conflict_result.explicit_conflict_count_by_trait.get(trait_id, 0),
                "context_dependency_flag": conflict_result.context_dependency_flag_by_trait.get(trait_id, False),
            }
        )
    return {"contrast_ids_needing_resolution_question": conflict_result.contrast_ids_needing_resolution_question}


def _stop_or_continue(g: AnswerGraphState) -> dict:
    """§5-3 Adaptive Stop Condition.

    2026-08-22 2차 리뷰 버그 수정: 예전에는 일반 꼬리질문이 6개(강제 STOP 경계)에 정확히
    도달한 시점에 Explicit Conflict가 "처음" 감지되면, decide_stop_or_continue가 개수만
    보고 무조건 STOP을 반환해서 확인 질문을 한 번도 못 물어보고 세션이 끝나버렸다(그
    Contrast는 영원히 미해결로 남는다). Conflict 확인 질문은 §5-3의 4~6개 상한과 분리된
    별도 문항이므로, 아직 한 번도 물어보지 않은 확인 질문이 있으면(g.contrast_ids_
    needing_resolution_question) 개수 상한과 무관하게 무조건 CONTINUE한다 — 이미 한 번
    물어봤다면(UNRESOLVED 포함) 이 집합에 다시 안 나타나므로 무한 반복은 안 생긴다."""

    state = g.state
    if g.contrast_ids_needing_resolution_question:
        return {"stop_decision": "CONTINUE"}

    tail_questions_asked = state.questions_asked_in_current_context - 1
    decision = decide_stop_or_continue(
        tail_questions_asked, state.trait_summaries, g.all_trait_ids, state.unresolved_conflict_trait_ids
    )
    if decision == "STOP":
        state.stop_reason = (
            f"tail_questions_asked={tail_questions_asked}, "
            f"unresolved_conflicts={sorted(state.unresolved_conflict_trait_ids)}"
        )
    return {"stop_decision": decision}


def _route_after_stop_check(g: AnswerGraphState) -> str:
    return "continue" if g.stop_decision == "CONTINUE" else "end"


def _target_planner(g: AnswerGraphState) -> dict:
    """§8 Question Target Planner — 다음 꼬리질문의 목표 Trait·Frame을 정한다."""

    state = g.state
    tail_questions_asked = state.questions_asked_in_current_context - 1
    next_position = tail_questions_asked + 1
    decision = decide_next_target(
        context_id=g.question.context,
        position=next_position,
        all_trait_ids=g.all_trait_ids,
        trait_summaries=state.trait_summaries,
        unresolved_conflict_trait_ids=state.unresolved_conflict_trait_ids,
        recent_target_trait_ids=state.recent_target_trait_ids,
        used_frame_ids_in_context=set(state.used_frame_ids_in_current_context),
        is_first_context_in_session=g.is_first_context_in_session,
        deepen_anchor_trait_id=state.current_context_seed_trait_id,
        contrast_ids_needing_resolution_question=g.contrast_ids_needing_resolution_question,
    )
    state.pending_resolution_contrast_id = decision.contrast_resolution_id
    return {"next_planner_decision": decision}


def build_answer_graph():
    graph = StateGraph(AnswerGraphState)
    graph.add_node("validate_option", _validate_option)
    graph.add_node("evidence_update", _evidence_update)
    graph.add_node("stop_or_continue", _stop_or_continue)
    graph.add_node("target_planner", _target_planner)

    graph.add_edge(START, "validate_option")
    graph.add_conditional_edges(
        "validate_option", _route_after_validate, {"continue": "evidence_update", "end": END}
    )
    graph.add_edge("evidence_update", "stop_or_continue")
    graph.add_conditional_edges(
        "stop_or_continue", _route_after_stop_check, {"continue": "target_planner", "end": END}
    )
    graph.add_edge("target_planner", END)
    return graph.compile()


_COMPILED_ANSWER_GRAPH = build_answer_graph()


def submit_answer(
    state: AssessmentState,
    question: FinalizedQuestion,
    selected_option_id: str,
    all_trait_ids: set[str],
    is_first_context_in_session: bool,
    contrast_definitions: list[ContrastDefinition] | None = None,
    resolution_specs: dict[str, ContrastResolutionQuestionSpec] | None = None,
) -> AnswerSubmissionResult:
    """예전 answer_processor.submit_answer와 시그니처·반환값·"state를 제자리 mutate"
    계약이 동일하다(신규 `resolution_specs`는 기본값 None인 Optional 추가 파라미터라
    기존 호출자는 그대로 동작한다) — 내부만 LangGraph 실행으로 바뀌었다."""

    graph_input = AnswerGraphState(
        state=state,
        question=question,
        selected_option_id=selected_option_id,
        all_trait_ids=all_trait_ids,
        contrast_definitions=contrast_definitions or [],
        is_first_context_in_session=is_first_context_in_session,
        resolution_specs=resolution_specs or {},
    )
    # LangGraph/LangChain은 LANGSMITH_TRACING 환경변수만 보고 원본 Node 입출력(학생 답변
    # 원문 포함)을 자동으로 LangSmith에 전송하려 한다 — 이건 §24 Sanitizer를 거치지 않은
    # 경로라 CLAUDE.md("자유서술 원문을 LangSmith에 보내지 않는다")를 어긴다. 이 자동
    # 전송을 명시적으로 끄고, main.py의 Tracer.record_stage()(Sanitizer 적용됨)만 실제
    # 전송 경로로 쓴다.
    with tracing_context(enabled=False):
        result = _COMPILED_ANSWER_GRAPH.invoke(graph_input)

    if not result["accepted"]:
        return AnswerSubmissionResult(accepted=False, rejection_reason=result["rejection_reason"])
    if result["stop_decision"] == "STOP":
        return AnswerSubmissionResult(accepted=True, stop_decision="STOP")
    return AnswerSubmissionResult(
        accepted=True, stop_decision="CONTINUE", next_planner_decision=result["next_planner_decision"]
    )
