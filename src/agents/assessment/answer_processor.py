"""답변 처리 파이프라인 — 설계안 §5-2 Assessment Graph 중 "학생 답변 → ... → 다음 질문
목표 결정" 구간을 순수 함수로 구현한다. LLM 호출은 없다(§10 Question Generator는 별도).

흐름: Option 검증 → EvidenceRecord 생성 → Trait Summary 갱신 → Stop/Continue 판단(§5-3)
→ (CONTINUE면) Target Planner 실행(§8) → 다음 질문의 목표 Trait·Frame 반환.

CLAUDE.md 원칙대로 DB·LLM·LangGraph 없이 AssessmentState를 직접 받아 갱신하는 순수 함수로
만들었다 — 나중에 LangGraph Node로 감쌀 때 이 함수를 그대로 호출하기만 하면 된다.
"""

from __future__ import annotations

from pydantic import BaseModel

from src.agents.assessment.target_planner import PlannerDecision, decide_next_target
from src.engines.conflict_engine import detect_explicit_conflicts
from src.engines.evidence_engine import decide_stop_or_continue, summarize_trait_evidence
from src.ids import generate_evidence_id
from src.schemas.assessment_state import AnsweredQuestion, AssessmentState
from src.schemas.evidence import ContrastDefinition, EvidenceOrigin, EvidenceRecord
from src.schemas.question import FinalizedQuestion


class AnswerSubmissionResult(BaseModel):
    accepted: bool
    rejection_reason: str | None = None
    stop_decision: str | None = None  # "CONTINUE" | "STOP" | None(거부됐으면 None)
    next_planner_decision: PlannerDecision | None = None


def submit_answer(
    state: AssessmentState,
    question: FinalizedQuestion,
    selected_option_id: str,
    all_trait_ids: set[str],
    is_first_context_in_session: bool,
    contrast_definitions: list[ContrastDefinition] | None = None,
) -> AnswerSubmissionResult:
    """`state`를 직접 갱신한다(제자리 mutate) — 호출자가 저장소에 다시 save하면 된다.

    2026-08-21 3단계: 예전에는 unresolved_conflict_trait_ids를 호출자가 직접 계산해서
    넘겼는데(항상 빈 값으로 넘어와 사실상 미구현), 이제는 이 함수가 evidence_ledger로부터
    매번 직접 판정한다(conflict_engine.detect_explicit_conflicts) — 호출자는 Contrast
    Pair 정의(Vertical Slice에서는 VERTICAL_SLICE_CONTRAST_DEFINITIONS)만 넘기면 된다.
    """

    contrast_definitions = contrast_definitions or []

    # 1. Option 검증 — 학생이 실제로 이 질문에 제시된 선택지를 골랐는지 확인한다.
    selected_option = next(
        (o for o in question.options if o.option_id == selected_option_id), None
    )
    if selected_option is None:
        return AnswerSubmissionResult(
            accepted=False,
            rejection_reason=(
                f"selected_option_id {selected_option_id!r}가 질문 "
                f"{question.question_id!r}의 선택지 목록에 없습니다."
            ),
        )

    # 2. EvidenceRecord 생성
    evidence = EvidenceRecord(
        evidence_id=generate_evidence_id(),
        answer_id=f"ans_{question.question_id}_{len(state.answers) + 1:02d}",
        question_id=question.question_id,
        question_frame_id=question.frame_id,
        option_role_id=selected_option.role_id,
        option_text=selected_option.text,
        applied_primary_trait_delta=selected_option.primary_trait_delta,
        evidence_origin=EvidenceOrigin.PRIMARY_BLUEPRINT,
        context=question.context,
        source_type="seed_question" if question.frame_id == "seed_frame" else "generated_question",
        generator_version="v1",
        quality_gate_status="passed",
    )
    state.evidence_ledger.append(evidence)
    # §7-3/§8: 이 Option의 next_probe를 다음 질문 "문구"를 자연스럽게 잇는 재료로 남긴다
    # (목표 Trait 자체는 이 값과 무관하게 Target Planner의 우선순위로 정해진다).
    state.pending_next_probe = selected_option.next_probe
    state.pending_previous_question_text = question.question_text
    state.pending_previous_answer_text = selected_option.text
    state.answers.append(
        AnsweredQuestion(
            question_id=question.question_id,
            selected_option_id=selected_option_id,
            selected_role_id=selected_option.role_id,
        )
    )

    offered_traits: list[str] = []
    for option in question.options:
        offered_traits.extend(option.primary_trait_delta.keys())
    state.offered_trait_ids_by_question[question.question_id] = offered_traits

    if question.target_traits:
        state.recent_target_trait_ids.append(question.target_traits[0])
    state.used_frame_ids_in_current_context.append(question.frame_id)

    state.questions_asked_in_current_context += 1

    # §7-2: 이번이 이 Context의 Seed 답변이면(꼬리질문 0개 → 1개), 이후 DEEPEN 테마가
    # 형제 Trait 후보를 고를 기준으로 삼을 수 있게 선택된 Trait을 남긴다.
    if state.questions_asked_in_current_context == 1:
        state.current_context_seed_trait_id = sorted(selected_option.primary_trait_delta)[0]

    # 3. Trait Summary 갱신 — 이번 한 Trait만이 아니라 전체를 다시 계산한다. opportunity_count가
    # 이 질문이 제시한 다른 4개 Trait에도 영향을 주기 때문이다.
    all_offered_sets = [set(v) for v in state.offered_trait_ids_by_question.values()]
    for trait_id in all_trait_ids:
        state.trait_summaries[trait_id] = summarize_trait_evidence(
            trait_id, state.evidence_ledger, all_offered_sets
        )

    # 3-1. §12-1 Explicit Conflict/Context Dependency 판정 — evidence_ledger 전체를 기준으로
    # 매번 새로 계산한다(누적 상태를 따로 두지 않아 "해결됐는데 플래그만 안 지워짐" 부류의
    # 불일치가 생길 수 없다).
    conflict_result = detect_explicit_conflicts(state.evidence_ledger, contrast_definitions)
    state.unresolved_conflict_trait_ids = conflict_result.unresolved_conflict_trait_ids
    for trait_id, summary in state.trait_summaries.items():
        state.trait_summaries[trait_id] = summary.model_copy(
            update={
                "explicit_conflict_count": conflict_result.explicit_conflict_count_by_trait.get(trait_id, 0),
                "context_dependency_flag": conflict_result.context_dependency_flag_by_trait.get(trait_id, False),
            }
        )

    # 4. Stop/Continue 판단(§5-3). Seed는 꼬리질문이 아니므로 세지 않는다.
    tail_questions_asked = state.questions_asked_in_current_context - 1
    stop_decision = decide_stop_or_continue(
        tail_questions_asked, state.trait_summaries, all_trait_ids, state.unresolved_conflict_trait_ids
    )

    if stop_decision == "STOP":
        state.stop_reason = (
            f"tail_questions_asked={tail_questions_asked}, "
            f"unresolved_conflicts={sorted(state.unresolved_conflict_trait_ids)}"
        )
        return AnswerSubmissionResult(accepted=True, stop_decision="STOP")

    # 5. Target Planner 실행 — 다음 꼬리질문의 목표 Trait·Frame을 정한다.
    next_position = tail_questions_asked + 1
    next_decision = decide_next_target(
        context_id=question.context,
        position=next_position,
        all_trait_ids=all_trait_ids,
        trait_summaries=state.trait_summaries,
        unresolved_conflict_trait_ids=state.unresolved_conflict_trait_ids,
        recent_target_trait_ids=state.recent_target_trait_ids,
        used_frame_ids_in_context=set(state.used_frame_ids_in_current_context),
        is_first_context_in_session=is_first_context_in_session,
        deepen_anchor_trait_id=state.current_context_seed_trait_id,
    )
    return AnswerSubmissionResult(
        accepted=True, stop_decision="CONTINUE", next_planner_decision=next_decision
    )
