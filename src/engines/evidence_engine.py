"""Evidence Engine — 설계안 §12, §13 순수 계산 로직.

CLAUDE.md 원칙: "계산 함수는 가능한 한 순수 함수로 만들고 LLM·DB·네트워크 호출과 분리한다."
이 파일은 DB·LLM을 전혀 참조하지 않는다 — 입력은 EvidenceRecord 리스트, 출력은 요약/상태다.

2026-08-20 리뷰 반영:
- summarize_trait_evidence가 evidence_origin을 확인하지 않아 SECONDARY_HYPOTHESIS 레코드까지
  support_count에 들어가던 버그를 고쳤다 (CLAUDE.md "Related Trait Signal과 Secondary
  Hypothesis를 확정 점수나 전공 Matching에 직접 반영하지 않는다" 위반).
- judge_trait_state가 TraitState만 반환해 INSUFFICIENT 세부 사유(NOT_PROBED 등)가 사라지던
  문제를 TraitStateJudgment로 감싸 해결했다.
- MODERATE 판정 기준을 팀 결정(2026-08-20)에 따라 STRONG과 동일하게 distinct_frame_count>=2를
  요구하도록 바꿨다 — 같은 질문 프레임만 반복해서 나온 증거는 자기확증(§8)에 가깝다고 판단.
"""

from __future__ import annotations

from src.schemas.evidence import (
    EvidenceOrigin,
    EvidenceRecord,
    TraitEvidenceSummary,
    TraitState,
    TraitStateJudgment,
)


def summarize_trait_evidence(
    trait_id: str,
    records: list[EvidenceRecord],
    all_offered_trait_ids_per_question: list[set[str]],
) -> TraitEvidenceSummary:
    """§12: opportunity_count는 "선택 가능했던" 횟수, support_count는 "실제로 선택된" 횟수다.

    Primary Evidence만 계산한다 — SECONDARY_HYPOTHESIS 상태의 레코드는 CONFIRMED되기 전까지는
    별도 취급되며(§9-1), CONFIRMED된 순간 새로운 PRIMARY_BLUEPRINT 레코드로 기록되는 것을
    전제로 한다. 이 함수에 SECONDARY_HYPOTHESIS 레코드가 섞여 들어와도 무시한다.

    all_offered_trait_ids_per_question: 학생에게 실제로 제시된 질문마다, 5개 Option 중
    이 trait_id가 어느 하나의 Option에라도 포함돼 있었으면 그 질문의 trait 집합에 넣는다.
    (질문에 노출되지 않았으면 기회 자체가 없었던 것이므로 opportunity_count에 안 들어간다.)
    """

    primary_records = [r for r in records if r.evidence_origin == EvidenceOrigin.PRIMARY_BLUEPRINT]

    support_count = sum(1 for r in primary_records if trait_id in r.applied_primary_trait_delta)
    opportunity_count = sum(1 for offered in all_offered_trait_ids_per_question if trait_id in offered)

    contexts = {r.context for r in primary_records if trait_id in r.applied_primary_trait_delta}
    frames = {
        r.question_frame_id for r in primary_records if trait_id in r.applied_primary_trait_delta
    }

    return TraitEvidenceSummary(
        trait_id=trait_id,
        support_count=support_count,
        opportunity_count=opportunity_count,
        context_count=len(contexts),
        distinct_frame_count=len(frames),
    )


def judge_trait_state(
    summary: TraitEvidenceSummary,
    minimum_context_count: int,
    has_unresolved_explicit_conflict: bool,
) -> TraitStateJudgment:
    """§13의 상태 판정 순서를 그대로 코드로 옮긴다. 순서를 바꾸면 결과가 달라지므로 그대로 유지한다.

    1. opportunity_count == 0                                  -> INSUFFICIENT (NOT_PROBED)
    2. 해결되지 않은 EXPLICIT_CONFLICT 존재                      -> CONFLICTING
    3. opportunity_count > 0, support_count == 0                -> INSUFFICIENT (NO_POSITIVE_EVIDENCE)
    4. opportunity_count > 0, support_count == 1                -> INSUFFICIENT (EVIDENCE_LIMITED)
    5. support_count>=3, context>=min, frame>=2                 -> STRONG
    6. support_count>=2, context>=min, frame>=2 (2026-08-20 결정) -> MODERATE
    7. support_count>=2 이지만 5·6 조건 미충족                    -> LIMITED
    """

    if summary.opportunity_count == 0:
        return TraitStateJudgment(state=TraitState.INSUFFICIENT, insufficient_reason="NOT_PROBED")

    if has_unresolved_explicit_conflict:
        return TraitStateJudgment(state=TraitState.CONFLICTING)

    if summary.support_count == 0:
        return TraitStateJudgment(
            state=TraitState.INSUFFICIENT, insufficient_reason="NO_POSITIVE_EVIDENCE"
        )

    if summary.support_count == 1:
        return TraitStateJudgment(
            state=TraitState.INSUFFICIENT, insufficient_reason="EVIDENCE_LIMITED"
        )

    diverse_enough = (
        summary.context_count >= minimum_context_count and summary.distinct_frame_count >= 2
    )

    if summary.support_count >= 3 and diverse_enough:
        return TraitStateJudgment(state=TraitState.STRONG)

    if summary.support_count >= 2 and diverse_enough:
        return TraitStateJudgment(state=TraitState.MODERATE)

    # support_count >= 2 이지만 context 다양성 또는 frame 다양성(§13, 2026-08-20 결정) 부족
    return TraitStateJudgment(state=TraitState.LIMITED)


def has_coverage_gap(trait_summaries: dict[str, TraitEvidenceSummary], all_trait_ids: set[str]) -> bool:
    """§5-3 "추가 확인이 필요한 핵심 Primary Trait가 없음"의 반대 조건. Target Planner의
    위치 5-6 Gap 판정(§8)과 같은 기준(opportunity=0 또는 support<2)을 재사용한다 — 같은
    "이 Trait는 아직 부족하다"는 판단을 Stop 여부와 다음 질문 목표 선정 양쪽에서 일관되게
    쓰기 위함이다."""

    for trait_id in all_trait_ids:
        summary = trait_summaries.get(trait_id)
        if summary is None or summary.opportunity_count == 0 or summary.support_count < 2:
            return True
    return False


def decide_stop_or_continue(
    tail_questions_asked_in_current_context: int,
    trait_summaries: dict[str, TraitEvidenceSummary],
    all_trait_ids: set[str],
    unresolved_conflict_trait_ids: set[str],
) -> str:
    """§5-3 Adaptive Stop Condition을 그대로 코드로 옮긴다.

    꼬리질문 "위치 1~4가 필수 역할(§7-2 DEEPEN/BEHAVIOR/CROSS_CONTEXT/ALTERNATIVE)을 전부
    충족했는지"는 별도로 검사하지 않는다 — Target Planner(§8)가 위치 1~4에서 항상 그 테마의
    Frame만 쓰도록 구조적으로 강제하므로, 정확히 4개가 끝난 시점에는 4개 역할이 이미 전부
    충족돼 있다는 게 설계로 보장된다.

    반환값은 "CONTINUE" 또는 "STOP" 문자열이다(§13 TraitState와 겹치지 않게 별도 타입을
    쓰지 않고 단순 리터럴로 둔다 — 이 결정을 저장하는 별도 Enum이 아직 필요하지 않다).
    """

    if tail_questions_asked_in_current_context < 4:
        return "CONTINUE"

    if tail_questions_asked_in_current_context >= 6:
        return "STOP"  # 6개 완료 시 강제 STOP

    # 4~5개 사이: 조건부 — Conflict도 없고 Coverage Gap도 없어야 STOP 가능
    if unresolved_conflict_trait_ids:
        return "CONTINUE"
    if has_coverage_gap(trait_summaries, all_trait_ids):
        return "CONTINUE"
    return "STOP"
