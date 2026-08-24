"""Coverage-focused Target Selector — a/coverage-focused-planner-shadow.

**Shadow 전용, 절대 Runtime에 연결하지 않는다.** 이 모듈이 반환하는
`CoverageFocusedSelectorDecision`은 어떤 API Handler도 소비하지 않고,
`src/api/main.py`·`src/engines/context_pack_adaptive_planner.py`(실제 Runtime
Planner, `select_pack_adaptive_target`)·`evidence_engine.decide_stop_or_continue`
(Stop Condition)는 이 파일이 전혀 Import하지 않는다 — 방향이 거꾸로다:
`eval/coverage_focused_planner_shadow_harness.py`가 실제 세션을 그대로 실행하며
이 함수를 "곁에서 관찰"만 하려고 부른다(§ 그 파일의 docstring 참고).

## 무엇을 구현하는가 — 진단 보고서(`origin/a/planner-gap-9persona-diagnostics
@ 7f0637e`, `outputs/evaluation/trait_evidence_coverage_planner_gap_report.md`)의
"대안 C"

그 진단은 Baseline/A/B/C/C2를 9-Persona로 비교했고, (상위5+상위8 SUFFICIENT
비율)/2 결합 점수가 baseline 0.181 → **C 0.260**(+0.079, 사전 문턱 0.05
이상)으로 가장 크게 개선됐다 — "선택: C"가 결론이었다. C의 핵심 규칙은
`_provisional_top_traits()`: **그 시점까지 실제로 쌓인 evidence_ledger의
weight만으로**(Persona의 숨은 선호도도, 세션 최종 결과도 참조하지 않는다)
상위 `PROVISIONAL_TOP_N`(=8)개를 다시 계산하고, 그중 아직 SUFFICIENT가 아닌
Trait만 "Gap"으로 본다. 이 모듈은 그 규칙을 그대로 이식한다(임의로 숫자를
바꾸지 않는다 — 진단 스크립트의 `PROVISIONAL_TOP_N=8`과 동일).

같은 진단이 §3에서 이미 밝힌 문제도 함께 반영한다 — 순수 C는 세션 초반
Evidence가 하나도 없을 때 알파벳 순 동점 처리로 상위 8개가 자의적으로 고정될
위험이 있다(고착 turn 31, 낭비 슬롯 54). 진단이 그 대응으로 이미 만든 대안
C2의 Exploration 예산(서로 다른 Trait 최소 8개가 증거를 얻기 전까지는 넓게
탐색) 상수를 **그대로** 재사용한다
(`EXPLORATION_MIN_DISTINCT_TRAITS_WITH_EVIDENCE = 8`, 진단의
`C2_EXPLORATION_MIN_DISTINCT_TRAITS_WITH_EVIDENCE`와 동일값 — 이 숫자를
임의로 조정하지 않았다). 그래서 이 모듈의 동작은 "Exploration 예산 동안은
넓게 탐색(A와 동일한 넓은 Gap 정의) → 예산을 채우면 C의 provisional
상위-8-Gap 규칙으로 집중"이라는 두 단계 혼합이다 — 이름은 "Coverage-focused"
지만 내부 전환 조건과 두 상수 전부 진단 보고서의 실측값을 그대로 가져온
것이지 새로 지어낸 값이 아니다.

## 비순환성(진단 §3이 발견한 반칙을 다시 만들지 않는다)

이 함수는 다음을 **절대** 입력으로 받지 않는다 — 파라미터 목록 자체에
존재하지 않는다:

- 세션 종료 후의 최종 Top Trait
- 미래 답변
- Persona/학생의 "진짜" 선호 순위(오라클)
- Trait Inventory 전체를 다 답했을 때의 결과

`CoverageFocusedSelectorInput`은 오직 "지금 이 Turn까지 실제로 관찰된 것"만
담는다: Evidence Ledger, 질문 기회 이력, 사용한 Context·Frame, 현재 Context,
남은 질문 예산, 검수 승인된 후보 Signal, Conflict 상태. 이 필드들 이상을
계산에 쓰지 않는다(`tests/test_coverage_focused_target_selector.py::
FutureEvidenceIndependenceTest`가 이를 기계적으로 검증한다).

## 우선순위(과제 §4)

Gap Trait 후보를 다음 순서로 우선한다 — 전부 `trait_evidence_coverage_engine`
의 실제 SUFFICIENT 기준 상수(`SUFFICIENT_MIN_PRIMARY_COUNT` 등, 여기서
재정의하지 않는다)로 판정한다:

1. Primary Evidence 부족(`primary_evidence_count < SUFFICIENT_MIN_PRIMARY_COUNT`)
2. 누적 Weight 부족(`effective_evidence_weight < SUFFICIENT_MIN_EFFECTIVE_WEIGHT`)
3. Context 다양성 부족(`distinct_context_count < SUFFICIENT_MIN_CONTEXT_COUNT`)
4. Frame 다양성 부족(`distinct_frame_count < SUFFICIENT_MIN_FRAME_COUNT`)
5. Conflict 확인 필요(`trait_id in conflicted_trait_ids`)

그리고 Trait를 고른 뒤, 그 Trait의 승인된 후보 Signal 중에서는 이미 같은
(blueprint_id, frame_id) 조합으로 Evidence나 질문 기회가 있었던 Signal의
우선순위를 낮춘다(제외하지 않는다 — 그것밖에 없으면 그래도 제안한다)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from src.engines.trait_evidence_coverage_engine import (
    SUFFICIENT_MIN_CONTEXT_COUNT,
    SUFFICIENT_MIN_EFFECTIVE_WEIGHT,
    SUFFICIENT_MIN_FRAME_COUNT,
    SUFFICIENT_MIN_PRIMARY_COUNT,
    compute_all_trait_coverage,
)
from src.schemas.evidence import EvidenceRecord, V2ProbeOpportunity

# 진단 보고서(§ 위 docstring)의 실측 상수 — 새 값을 지어내지 않고 그대로 가져왔다.
PROVISIONAL_TOP_N = 8
EXPLORATION_MIN_DISTINCT_TRAITS_WITH_EVIDENCE = 8

SelectionMode = Literal["EXPLORATION", "TOP_TRAIT_FOCUS"]


@dataclass(frozen=True)
class ApprovedCandidateSignal:
    """검수 승인된 후보 Signal 하나 — "지금 이 Trait를, 이 Context에서, 이 Frame으로
    물어볼 수 있는 실제 검수 통과 경로가 있다"는 사실만 담는다. Blueprint 객체 전체를
    받지 않는다 — 이 Selector는 Trait+Frame 수준까지만 제안하고(§ 출력), 실제
    Blueprint 인스턴스 선택은 이 모듈의 책임이 아니다(Runtime의
    `select_blueprint_for_trait`가 이미 한다 — 다시 만들지 않는다)."""

    trait_id: str
    context_id: str
    frame_id: str
    blueprint_id: str


@dataclass(frozen=True)
class CoverageFocusedSelectorInput:
    """이 시점까지 실제로 관찰된 것만 담는다(§ 비순환성). 어떤 필드도 세션 종료
    이후 정보나 오라클을 담지 않는다."""

    evidence_ledger: tuple[EvidenceRecord, ...]
    approved_evidence_ids: frozenset[str]
    opportunity_history: tuple[V2ProbeOpportunity, ...]
    used_context_ids: frozenset[str]
    used_frame_ids: frozenset[str]
    current_context_id: str
    remaining_question_budget: int
    approved_candidate_signals: tuple[ApprovedCandidateSignal, ...]
    conflicted_trait_ids: frozenset[str]
    core_trait_ids: frozenset[str]


@dataclass(frozen=True)
class CoverageFocusedSelectorDecision:
    proposed_trait_id: str
    proposed_frame_id: str
    selection_mode: SelectionMode
    provisional_rank: int
    evidence_gap: bool
    decision_reason: str
    exploration_slot_used: bool
    shadow_only: bool = True


def _dedup_keys_already_seen(
    evidence_ledger: tuple[EvidenceRecord, ...], opportunity_history: tuple[V2ProbeOpportunity, ...],
) -> frozenset[tuple[str, str]]:
    """이미 같은 (blueprint_id, frame_id) 조합으로 Evidence가 쌓였거나 질문 기회가
    있었던 조합. `trait_evidence_coverage_engine.evidence_dedup_key`와 같은
    정의(blueprint_id, frame_id)를 Evidence 쪽에 쓰고, 질문 기회 이력(응답이
    Target Signal을 고르지 못한 경우도 포함)도 같은 키로 더한다 — "이미 물어본
    조합"이라는 사실 자체가 중요하지, 그 답변이 이 Trait를 실제로 지지했는지는
    이 판정에서는 상관없다."""

    keys: set[tuple[str, str]] = set()
    for record in evidence_ledger:
        blueprint_key = record.source_blueprint_id or f"__no_blueprint__:{record.question_id}"
        keys.add((blueprint_key, record.question_frame_id))
    for opportunity in opportunity_history:
        keys.add((opportunity.blueprint_id, opportunity.frame_id))
    return frozenset(keys)


def _trait_priority_key(
    trait_id: str, coverage: dict, conflicted_trait_ids: frozenset[str],
) -> tuple[bool, bool, bool, bool, bool, str]:
    """§4 우선순위 5축 — 실제 Coverage Engine의 SUFFICIENT 기준 상수로만 판정한다.
    `False`가 먼저 정렬되므로(오름차순 튜플 비교), "아직 부족하다"(True 조건)를
    `not (...)`로 뒤집어 앞쪽에 오게 만든다."""

    result = coverage[trait_id]
    return (
        not (result.primary_evidence_count < SUFFICIENT_MIN_PRIMARY_COUNT),
        not (result.effective_evidence_weight < SUFFICIENT_MIN_EFFECTIVE_WEIGHT),
        not (result.distinct_context_count < SUFFICIENT_MIN_CONTEXT_COUNT),
        not (result.distinct_frame_count < SUFFICIENT_MIN_FRAME_COUNT),
        not (trait_id in conflicted_trait_ids),
        trait_id,
    )


def _priority_reason(trait_id: str, coverage: dict, conflicted_trait_ids: frozenset[str]) -> str:
    result = coverage[trait_id]
    missing: list[str] = []
    if result.primary_evidence_count < SUFFICIENT_MIN_PRIMARY_COUNT:
        missing.append("primary_evidence")
    if result.effective_evidence_weight < SUFFICIENT_MIN_EFFECTIVE_WEIGHT:
        missing.append("cumulative_weight")
    if result.distinct_context_count < SUFFICIENT_MIN_CONTEXT_COUNT:
        missing.append("context_diversity")
    if result.distinct_frame_count < SUFFICIENT_MIN_FRAME_COUNT:
        missing.append("frame_diversity")
    if trait_id in conflicted_trait_ids:
        missing.append("conflict_check")
    return ", ".join(missing) if missing else "no_specific_gap_dimension"


def select_coverage_focused_target(
    inputs: CoverageFocusedSelectorInput,
) -> CoverageFocusedSelectorDecision | None:
    """§1 순수 Selector — 부작용 없음, LLM/DB/Runtime State 변경 없음. 제안할 것이
    없으면(예산 소진, 현재 Context에 승인된 후보가 없음, 모든 후보가 이미
    SUFFICIENT) `None`을 돌려준다 — 억지로 제안을 만들지 않는다(§8 "질문 예산
    초과 없음"과 대칭인 "빈 제안도 정상"이라는 원칙, 실제 Runtime Planner의
    `select_pack_adaptive_target`이 `None`을 돌려주는 것과 같은 관례)."""

    if inputs.remaining_question_budget <= 0:
        return None

    candidates_here = [s for s in inputs.approved_candidate_signals if s.context_id == inputs.current_context_id]
    if not candidates_here:
        return None

    coverage = compute_all_trait_coverage(
        set(inputs.core_trait_ids), list(inputs.evidence_ledger), set(inputs.approved_evidence_ids),
    )

    def is_sufficient(trait_id: str) -> bool:
        # 외부에서 넘어온 conflicted_trait_ids는 이 Selector가 만든 `coverage`
        # 스냅샷에 반영돼 있지 않다(§ Conflict 상태는 별도 입력, `compute_all_
        # trait_coverage`에 contrast_definitions를 넘기지 않는다 — 클래스 docstring
        # 참고). 그래서 원시 수치상 SUFFICIENT처럼 보여도, 아직 풀리지 않은 Conflict가
        # 있는 Trait는 "다 됐다"고 보지 않는다 — 그래야 §4 "Conflict 확인" 우선순위
        # 축이 실제로 후보 Pool에 남는다.
        if trait_id in inputs.conflicted_trait_ids:
            return False
        result = coverage.get(trait_id)
        return result is not None and result.coverage_status == "SUFFICIENT"

    ranked_by_weight = sorted(
        inputs.core_trait_ids,
        key=lambda t: (-(coverage[t].effective_evidence_weight if t in coverage else 0.0), t),
    )
    rank_of = {trait_id: idx + 1 for idx, trait_id in enumerate(ranked_by_weight)}
    provisional_top = set(ranked_by_weight[:PROVISIONAL_TOP_N])

    distinct_traits_with_evidence = sum(
        1 for t in inputs.core_trait_ids if t in coverage and coverage[t].effective_evidence_weight > 0
    )
    exploration_phase = distinct_traits_with_evidence < EXPLORATION_MIN_DISTINCT_TRAITS_WITH_EVIDENCE
    mode: SelectionMode = "EXPLORATION" if exploration_phase else "TOP_TRAIT_FOCUS"

    candidate_trait_ids = {s.trait_id for s in candidates_here}

    if exploration_phase:
        eligible = {t for t in candidate_trait_ids if not is_sufficient(t)}
    else:
        eligible = {t for t in candidate_trait_ids if t in provisional_top and not is_sufficient(t)}
        if not eligible:
            # 진단 §7의 대안 C 낭비-슬롯 완화와 같은 취지 — provisional 상위 8개
            # 안에 이 Context가 지금 낼 수 있는 Gap Trait가 하나도 없으면(전부
            # SUFFICIENT이거나 이 Context 후보 밖), 상위 8개 밖이라도 아직
            # SUFFICIENT가 아닌 Trait로 넓혀서 빈 슬롯을 만들지 않는다.
            eligible = {t for t in candidate_trait_ids if not is_sufficient(t)}

    if not eligible:
        return None

    chosen_trait_id = min(eligible, key=lambda t: _trait_priority_key(t, coverage, inputs.conflicted_trait_ids))

    already_seen = _dedup_keys_already_seen(inputs.evidence_ledger, inputs.opportunity_history)
    signals_for_trait = [s for s in candidates_here if s.trait_id == chosen_trait_id]

    def signal_priority(signal: ApprovedCandidateSignal) -> tuple[bool, bool, str, str]:
        repeated = (signal.blueprint_id, signal.frame_id) in already_seen
        frame_already_used = signal.frame_id in inputs.used_frame_ids
        return (repeated, frame_already_used, signal.frame_id, signal.blueprint_id)

    chosen_signal = min(signals_for_trait, key=signal_priority)

    return CoverageFocusedSelectorDecision(
        proposed_trait_id=chosen_trait_id,
        proposed_frame_id=chosen_signal.frame_id,
        selection_mode=mode,
        provisional_rank=rank_of[chosen_trait_id],
        evidence_gap=not is_sufficient(chosen_trait_id),
        decision_reason=(
            f"mode={mode}; gap_dimensions=[{_priority_reason(chosen_trait_id, coverage, inputs.conflicted_trait_ids)}]"
        ),
        exploration_slot_used=exploration_phase,
    )
