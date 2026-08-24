"""Coverage-focused Target Selector — Shadow 평가 Harness — a/coverage-focused-
planner-shadow.

**무엇을 하는가.** 실제 Runtime Planner(`select_pack_adaptive_target`,
`src/engines/context_pack_adaptive_planner.py`)를 소스 파일 자체는 한 Byte도
고치지 않는다. 대신 두 단계로 비교한다:

1. **Baseline 관찰(Pass 1)** — 실제 세션을 실제 Planner 그대로 돌리되,
   `select_pack_adaptive_target`을 얇은 관찰용 Wrapper로 감싼다. Wrapper는
   그 Turn의 실제 결정을 **그대로** 돌려주고(세션 흐름·학생에게 나가는 질문
   순서를 전혀 바꾸지 않는다), 곁에서 `src/engines/coverage_focused_target_
   selector.py::select_coverage_focused_target()`을 같은 State 스냅샷으로
   호출해 "이 Turn에 Coverage-focused Selector라면 뭘 제안했을까"만 기록한다.
   이 Pass의 산출물이 "실제 Target vs 제안 Target 나란히 기록"(§5)이다.
2. **Shadow 대체 실행(Pass 2)** — Baseline과 완전히 분리된 별도 세션 ID로,
   이번엔 `select_pack_adaptive_target`을 Coverage-focused Selector로 실제
   교체해 처음부터 다시 돌린다(진단 스크립트 `eval/trait_evidence_coverage_
   planner_gap_diagnostics.py`의 대안 A/B/C/C2 비교와 같은 기법 — 그 스크립트가
   이미 "프로세스 안에서만 patch.object로 갈아끼운다" 원칙으로 승인받은 패턴을
   그대로 재사용한다). 이렇게 해야 "질문 종료 시 Coverage·상위5·8 비율" 같은
   **끝난 세션의 결과** 지표를 Baseline과 같은 기준으로 비교할 수 있다 — Pass 1의
   관찰만으로는 "그 제안대로 실제로 진행됐다면 세션이 어떻게 끝났을지"를 알 수
   없다.

**Pass 2도 "Runtime 연결"이 아니다.** 이 스크립트 프로세스 밖으로 나가는 순간
(스크립트 종료 시) `patch.object`가 자동 복원되고, `src/api/main.py`·
`context_pack_adaptive_planner.py` 파일 자체는 전혀 수정되지 않는다 — 실제
서비스가 받는 요청은 이 스크립트를 전혀 거치지 않는다. Persona도 실제 학생이
아니라 `eval/trait_evidence_coverage_session_diagnostics.py`의 결정론적 Fake
답변 정책이다.

**금지 사항 재확인**: Runtime Planner 소스·`src/api/main.py`·Stop Condition
(`evidence_engine.decide_stop_or_continue`)·Coverage 기준
(`trait_evidence_coverage_engine`의 상수) 어느 것도 이 파일이 수정하지 않는다
— 전부 원본 그대로 Import해서 쓴다. `data/reviews/`도 이 스크립트가 열어보지
않는다(12개 Pack·공용 Adaptive Probe 승인은 전부 `tempfile` Fixture 안에서만
만든다, `_build_fixture_registry` 참고).

실행:
    PYTHONPATH=. ./.venv/bin/python eval/coverage_focused_planner_shadow_harness.py
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import src.api.main as main_module  # noqa: E402
from src.data.contexts.context_definitions import CONTEXT_IDS  # noqa: E402
from src.data.questions.context_pack_shared_probe_blueprints import (  # noqa: E402
    CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS,
)
from src.data.trait_ontology.trait_probe_capabilities_v2 import CORE_TRAIT_IDS  # noqa: E402
from src.engines.context_pack_adaptive_planner import (  # noqa: E402
    PackAdaptiveTargetDecision,
    compute_pack_context_trait_summaries,
    select_pack_adaptive_target as real_select_pack_adaptive_target,
)
from src.engines.coverage_focused_target_selector import (  # noqa: E402
    PROVISIONAL_TOP_N,
    ApprovedCandidateSignal,
    CoverageFocusedSelectorInput,
    select_coverage_focused_target,
)
from src.engines.trait_evidence_coverage_engine import (  # noqa: E402
    SUFFICIENT_MIN_CONTEXT_COUNT,
    SUFFICIENT_MIN_EFFECTIVE_WEIGHT,
    SUFFICIENT_MIN_FRAME_COUNT,
    SUFFICIENT_MIN_PRIMARY_COUNT,
    compute_all_trait_coverage,
    coverage_status_breakdown,
)
from src.engines.v2_direct_probe_selector import select_blueprint_for_trait  # noqa: E402
from src.schemas.api import (  # noqa: E402
    AnswerRequest,
    ContextConfirmRequest,
    ContextSelectRequest,
    InterestRatingRequest,
)
from src.schemas.assessment_state import AssessmentState  # noqa: E402
from src.schemas.context_pack_shared_probe_review import SharedProbeContextReview  # noqa: E402
from src.schemas.question import GeneratedOption, GeneratedQuestion, QuestionGenerationResult  # noqa: E402
from src.schemas.v2_direct_probe import V2DirectProbeBlueprint  # noqa: E402
from src.services.context_pack_registry import ContextPackRegistry, discover_context_packs  # noqa: E402
from src.services.context_pack_runtime import ContextPackRuntime  # noqa: E402
from src.services.trait_signal_registry import register_context_pack_signals  # noqa: E402
from src.services.trait_signal_review_gate import gate_primary_eligible_evidence  # noqa: E402

# 기존 9-Persona 정본을 그대로 가져온다 — 새로 정의하지 않는다(과제 §6 "기존 9개
# Persona 전부 사용").
from eval.trait_evidence_coverage_session_diagnostics import (  # noqa: E402
    PersonaScenario,
    _affinity_rank,
    _choose_by_affinity,
    _choose_by_min_running_weight,
    _choose_concentrated,
    _choose_routing_option,
    _persona_scenarios,
    _ratings_for,
)

_CONTEXT_RE = re.compile(r'context 필드에는 "(\w+)"를')
_FRAME_RE = re.compile(r'frame_id 필드에는 "(\w+)"를')
_ROLE_RE = re.compile(r"\[Option Role.*?\]\n(.*?)\n\ncontext 필드", re.DOTALL)

VERTICAL_SLICE_CONTEXT_IDS: tuple[str, ...] = ("game", "media", "school_life")
MAX_QUESTION_LOOP_ITERATIONS = 400
# Persona 4+1 세션의 실제 Trait 질문 상한(Context 5개 × Adaptive Tail 최대 6 +
# Seed 5 = 최대 35, `trait_evidence_coverage_planner_gap_diagnostics.py`의 실측
# 흐름 설명과 동일값 — 새로 지어내지 않았다).
TRAIT_QUESTION_BUDGET_PER_SESSION = 35

JSON_OUTPUT_PATH = ROOT / "outputs" / "evaluation" / "coverage_focused_planner_shadow_report.json"
MD_OUTPUT_PATH = ROOT / "outputs" / "evaluation" / "coverage_focused_planner_shadow_report.md"

# §7 판정 문턱 — 진단 보고서(7f0637e)가 이미 확립한 "뚜렷한 개선" 기준
# (MINIMUM_MEANINGFUL_IMPROVEMENT=0.05, (상위5+상위8)/2 결합 점수)을 그대로
# 재사용한다. 숫자를 새로 지어내지 않는다.
MINIMUM_MEANINGFUL_IMPROVEMENT = 0.05
# READY_FOR_RUNTIME_FLAG로 판정하려면 결합 점수 개선에 더해, Turn 단위 일치율도
# 너무 낮지 않아야 한다(전혀 다른 순서로 질문했는데 우연히 같은 최종 Coverage에
# 도달한 경우까지 "Runtime에 켤 준비 됨"으로 보지 않기 위한 보조 조건). 임의
# 조정 방지를 위해 "절반 이상은 실제 Planner와 같은 Turn에 같은 Trait를
# 골랐다"는 값(0.5)을 최소선으로 둔다 — 이 값 미만이면 결합 점수가 좋아도
# "왜 좋아졌는지"를 사람이 다시 봐야 한다.
MINIMUM_TURN_AGREEMENT_RATE_FOR_READY = 0.5


class _DeterministicFakeLLMClient:
    """`session_diagnostics.py`와 동일 원리 — Prompt에서 실제 context/frame_id/
    role_id를 파싱해 결정론적으로 되돌려준다."""

    def __init__(self) -> None:
        self.call_count = 0

    def complete_structured(self, *, system_prompt: str, user_prompt: str, response_model: type) -> Any:
        self.call_count += 1
        context = _CONTEXT_RE.search(user_prompt).group(1)
        frame_id = _FRAME_RE.search(user_prompt).group(1)
        role_block = _ROLE_RE.search(user_prompt).group(1)
        role_ids = [line.removeprefix("- ").strip().split(" ")[0] for line in role_block.strip().splitlines()]
        return QuestionGenerationResult(
            question=GeneratedQuestion(
                context=context, target_traits=[], frame_id=frame_id,
                question_text=f"[{frame_id}/{self.call_count:04d}] 지금 상황에서 무엇을 가장 먼저 하나요?",
                options=[GeneratedOption(role_id=r, text=f"{r} 선택지 문장") for r in role_ids],
            )
        )


# ============================== Anchor 다양화(7f0637e 진단에서 선택적으로 이식) ==============================
#
# 병합 대상 브랜치(origin/a/planner-gap-9persona-diagnostics @ 7f0637e)는 통째로
# 가져오지 않는다(과제 §0 "필요한 진단 파일만 선택적으로 가져올 것") — 이 저장소
# 기본 브랜치의 session_diagnostics.py는 아직 "모든 Context 알파벳 순 첫
# Anchor"라는 단순화를 쓰고, 7f0637e가 그 단순화를 없앤 로직만 여기 그대로
# 옮겨온다(과제 §6 "Coverage 최대/기본/최소 Anchor 민감도도 유지").


def _anchor_ids_for_context(context_id: str, registry: ContextPackRegistry) -> list[str]:
    if context_id in VERTICAL_SLICE_CONTEXT_IDS:
        from src.data.contexts.context_anchor_presentations import CONTEXT_ANCHOR_PRESENTATIONS

        return sorted(p.anchor_id for p in CONTEXT_ANCHOR_PRESENTATIONS if p.context_id == context_id)
    pack = registry.get_pack(context_id)
    if pack is None:
        return []
    return sorted(a.anchor_id for a in pack.anchor_presentations)


def _anchor_candidate_trait_ids(context_id: str, anchor_id: str, runtime: ContextPackRuntime) -> frozenset[str]:
    if context_id in VERTICAL_SLICE_CONTEXT_IDS:
        return frozenset()
    candidates = runtime.get_direct_probe_candidates(context_id, anchor_id)
    return frozenset(bp.trait_id for bp in candidates)


def _stable_index(*parts: str, modulo: int) -> int:
    if modulo <= 0:
        return 0
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % modulo


def _anchor_choice_for_persona(
    scenario: PersonaScenario, context_id: str, registry: ContextPackRegistry, runtime: ContextPackRuntime,
) -> str:
    anchors = _anchor_ids_for_context(context_id, registry)
    if not anchors:
        raise ValueError(f"{context_id}에 등록된 Anchor가 없다")

    if context_id in VERTICAL_SLICE_CONTEXT_IDS or not scenario.trait_affinity_order:
        idx = _stable_index(scenario.key, context_id, modulo=len(anchors))
        return anchors[idx]

    affinity_set = set(scenario.trait_affinity_order[:PROVISIONAL_TOP_N])
    scores = {a: len(_anchor_candidate_trait_ids(context_id, a, runtime) & affinity_set) for a in anchors}
    best_score = max(scores.values())
    tied = sorted(a for a in anchors if scores[a] == best_score)
    if len(tied) == 1:
        return tied[0]
    return tied[_stable_index(scenario.key, context_id, modulo=len(tied))]


def _pack_context_with_widest_anchor_spread(registry: ContextPackRegistry, runtime: ContextPackRuntime) -> str:
    best_context: str | None = None
    best_spread = -1
    for context_id in sorted(CONTEXT_IDS):
        if context_id in VERTICAL_SLICE_CONTEXT_IDS:
            continue
        anchors = _anchor_ids_for_context(context_id, registry)
        if len(anchors) < 2:
            continue
        counts = [len(_anchor_candidate_trait_ids(context_id, a, runtime)) for a in anchors]
        spread = max(counts) - min(counts)
        if spread > best_spread:
            best_spread, best_context = spread, context_id
    if best_context is None:
        raise RuntimeError("Anchor 수 2개 이상인 Pack Context가 없다 — 민감도 실험 불가")
    return best_context


def anchor_sensitivity_variants(
    base_scenario: PersonaScenario, registry: ContextPackRegistry, runtime: ContextPackRuntime,
) -> dict[str, Any]:
    """§6 "Coverage 최대/기본/최소 Anchor 민감도" — Baseline 세션이 실제로 어떤
    Anchor 조합을 썼는지와 별개로, "Coverage 최대/최소를 강제로 골랐다면 후보
    Trait 풀이 어떻게 달라지는지"를 3-way(max/min/persona_default)로 기록만
    한다(세션을 다시 돌리지 않는다 — 이 값 자체가 Anchor→후보 Trait 풀 매핑이
    Persona와 무관한 구조적 사실이라, 7f0637e 진단이 이미 실측으로 확인한 대로
    "Anchor가 후보 Trait 풀을 가르지 않는다"는 사실을 매 실행마다 다시 세션을
    돌려 재확인할 필요가 없다)."""

    target_context = _pack_context_with_widest_anchor_spread(registry, runtime)
    anchors = _anchor_ids_for_context(target_context, registry)
    trait_counts = {a: len(_anchor_candidate_trait_ids(target_context, a, runtime)) for a in anchors}
    varies = max(trait_counts.values()) > min(trait_counts.values())
    max_anchor = max(anchors, key=lambda a: (trait_counts[a], a))
    min_anchor = min(anchors, key=lambda a: (trait_counts[a], a))
    if max_anchor == min_anchor and len(anchors) > 1:
        max_anchor, min_anchor = anchors[0], anchors[-1]
    default_anchor = _anchor_choice_for_persona(base_scenario, target_context, registry, runtime)
    return {
        "target_context": target_context,
        "anchor_candidate_trait_counts": trait_counts,
        "candidate_pool_varies_by_anchor": varies,
        "max_coverage_anchor": max_anchor,
        "min_coverage_anchor": min_anchor,
        "persona_default_anchor": default_anchor,
    }


# ============================== Fixture Registry(기존 패턴 재사용) ==============================


def _build_fixture_registry(fixture_dir: Path) -> ContextPackRegistry:
    packs, discovery_errors = discover_context_packs()
    if discovery_errors:
        raise RuntimeError(f"ContextPack 발견 중 오류: {discovery_errors}")

    shared_probe_path = fixture_dir / "shared_probe_review_status.json"
    registry = ContextPackRegistry(
        known_context_ids=frozenset(CONTEXT_IDS),
        review_status_dir=fixture_dir,
        shared_probe_review_status_path=shared_probe_path,
        shared_probe_pool=list(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS),
        _discovered=(packs, {}),
    )

    for context_id, pack in packs.items():
        keys = sorted(registry.required_review_keys(pack))
        rows = [
            {
                "blueprint_id": key, "reviewer_1_status": "APPROVE", "reviewer_1_comment": "",
                "reviewer_2_status": "TBD", "reviewer_2_comment": "", "resolution_note": "",
            }
            for key in keys
        ]
        (fixture_dir / f"{context_id}_review_status.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        register_context_pack_signals(pack)

    shared_rows: list[dict[str, Any]] = []
    for bp in CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS:
        for context_id in bp.allowed_context_ids:
            pack = packs.get(context_id)
            if pack is None:
                continue
            anchor_ids = sorted(a.anchor_id for a in pack.anchor_presentations)
            entry = SharedProbeContextReview(
                blueprint_id=bp.blueprint_id, context_id=context_id,
                reviewer_1_status="APPROVE", reviewer_1_comment="", resolution_note="",
                approved_anchor_ids=anchor_ids, excluded_anchor_ids=[],
            )
            shared_rows.append(json.loads(entry.model_dump_json()))
    shared_probe_path.parent.mkdir(parents=True, exist_ok=True)
    shared_probe_path.write_text(json.dumps(shared_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return registry


def _routing_blueprint_for(context_id: str) -> Any:
    routing = main_module.CONTEXT_ROUTING_BLUEPRINTS_BY_CONTEXT.get(context_id)
    if routing is not None:
        return routing
    return main_module._context_pack_runtime.get_routing_question(context_id)


# ============================== Shadow 스냅샷 도우미 ==============================


def _session_coverage_snapshot(session_id: str, registry: ContextPackRegistry) -> dict[str, Any]:
    state = main_module._store.load(session_id)
    gate = gate_primary_eligible_evidence(state.evidence_ledger, state.context_anchor_choices, registry)
    return compute_all_trait_coverage(CORE_TRAIT_IDS, state.evidence_ledger, gate.approved_evidence_ids)


def _provisional_top_n_snapshot(session_id: str, registry: ContextPackRegistry) -> tuple[str, ...]:
    """Harness 쪽에서 독립적으로 다시 계산한 상위 N — Selector 내부 계산과 같은
    정의를 쓰지만(§ `coverage_focused_target_selector.PROVISIONAL_TOP_N`), 이
    값은 보고서의 "Trait 진입·탈락 이력"을 만드는 데만 쓰고 Selector 자신의
    의사결정에는 관여하지 않는다(관찰 전용 중복 계산 — 7f0637e 진단의 같은
    관례)."""

    coverage = _session_coverage_snapshot(session_id, registry)
    ranked = sorted(CORE_TRAIT_IDS, key=lambda t: (-(coverage[t].effective_evidence_weight if t in coverage else 0.0), t))
    return tuple(sorted(ranked[:PROVISIONAL_TOP_N]))


def _build_shadow_input(
    *,
    session_id: str,
    registry: ContextPackRegistry,
    current_context_id: str,
    candidate_pool: list[V2DirectProbeBlueprint],
    already_used_blueprint_ids: set[str],
    used_frame_ids: set[str],
    remaining_budget: int,
) -> CoverageFocusedSelectorInput:
    state = main_module._store.load(session_id)
    gate = gate_primary_eligible_evidence(state.evidence_ledger, state.context_anchor_choices, registry)
    signals = tuple(
        ApprovedCandidateSignal(
            trait_id=bp.trait_id, context_id=current_context_id,
            frame_id=bp.question_frame_id, blueprint_id=bp.blueprint_id,
        )
        for bp in candidate_pool
        if bp.blueprint_id not in already_used_blueprint_ids
    )
    return CoverageFocusedSelectorInput(
        evidence_ledger=tuple(state.evidence_ledger),
        approved_evidence_ids=frozenset(gate.approved_evidence_ids),
        opportunity_history=tuple(state.v2_probe_opportunities),
        used_context_ids=frozenset(r.context for r in state.evidence_ledger),
        used_frame_ids=frozenset(used_frame_ids),
        current_context_id=current_context_id,
        remaining_question_budget=remaining_budget,
        approved_candidate_signals=signals,
        conflicted_trait_ids=frozenset(state.unresolved_conflict_trait_ids),
        core_trait_ids=frozenset(CORE_TRAIT_IDS),
    )


# ============================== Pass 1 — 관찰 전용 Wrapper(실제 결정 불변) ==============================


@dataclass
class _TurnComparisonLog:
    turn_index: list[int] = field(default_factory=list)
    real_target_trait_id: list[str | None] = field(default_factory=list)
    shadow_proposed_trait_id: list[str | None] = field(default_factory=list)
    shadow_selection_mode: list[str | None] = field(default_factory=list)
    shadow_decision_reason: list[str | None] = field(default_factory=list)
    match: list[bool] = field(default_factory=list)


def _make_observing_selector(session_id: str, registry: ContextPackRegistry, log: _TurnComparisonLog):
    """실제 결정을 계산해서(`real_select_pack_adaptive_target`, 원본 함수 그대로)
    **그대로 돌려준다** — 이 Wrapper는 반환값을 절대 바꾸지 않는다. 곁에서 같은
    State 스냅샷으로 Shadow Selector를 불러 기록만 남긴다."""

    turn_counter = {"n": 0}

    def observing_selector(
        *,
        candidate_pool: list[V2DirectProbeBlueprint],
        trait_summaries: dict[str, Any],
        already_used_blueprint_ids: set[str],
        recent_target_trait_id: str | None,
        used_frame_ids: set[str],
        final_contexts: list[str],
    ) -> PackAdaptiveTargetDecision | None:
        real_decision = real_select_pack_adaptive_target(
            candidate_pool=candidate_pool, trait_summaries=trait_summaries,
            already_used_blueprint_ids=already_used_blueprint_ids, recent_target_trait_id=recent_target_trait_id,
            used_frame_ids=used_frame_ids, final_contexts=final_contexts,
        )

        turn_counter["n"] += 1
        state = main_module._store.load(session_id)
        current_context_id = state.current_context_id or (final_contexts[0] if final_contexts else "")
        remaining_budget = TRAIT_QUESTION_BUDGET_PER_SESSION - turn_counter["n"] + 1
        shadow_input = _build_shadow_input(
            session_id=session_id, registry=registry, current_context_id=current_context_id,
            candidate_pool=candidate_pool, already_used_blueprint_ids=already_used_blueprint_ids,
            used_frame_ids=used_frame_ids, remaining_budget=remaining_budget,
        )
        shadow_decision = select_coverage_focused_target(shadow_input)

        real_trait = real_decision.trait_id if real_decision is not None else None
        shadow_trait = shadow_decision.proposed_trait_id if shadow_decision is not None else None

        log.turn_index.append(turn_counter["n"])
        log.real_target_trait_id.append(real_trait)
        log.shadow_proposed_trait_id.append(shadow_trait)
        log.shadow_selection_mode.append(shadow_decision.selection_mode if shadow_decision is not None else None)
        log.shadow_decision_reason.append(shadow_decision.decision_reason if shadow_decision is not None else None)
        log.match.append(real_trait == shadow_trait)

        return real_decision

    return observing_selector


# ============================== Pass 2 — Shadow 대체 실행(별도 세션) ==============================


@dataclass
class _ShadowSteeredLog:
    turn_target_trait_ids: list[str] = field(default_factory=list)
    turn_selection_mode: list[str] = field(default_factory=list)
    turn_exploration_slot_used: list[bool] = field(default_factory=list)
    provisional_top_n_history: list[tuple[str, ...]] = field(default_factory=list)


def _make_shadow_steered_selector(session_id: str, registry: ContextPackRegistry, log: _ShadowSteeredLog):
    turn_counter = {"n": 0}

    def steered_selector(
        *,
        candidate_pool: list[V2DirectProbeBlueprint],
        trait_summaries: dict[str, Any],
        already_used_blueprint_ids: set[str],
        recent_target_trait_id: str | None,
        used_frame_ids: set[str],
        final_contexts: list[str],
    ) -> PackAdaptiveTargetDecision | None:
        turn_counter["n"] += 1
        state = main_module._store.load(session_id)
        current_context_id = state.current_context_id or (final_contexts[0] if final_contexts else "")
        remaining_budget = TRAIT_QUESTION_BUDGET_PER_SESSION - turn_counter["n"] + 1
        shadow_input = _build_shadow_input(
            session_id=session_id, registry=registry, current_context_id=current_context_id,
            candidate_pool=candidate_pool, already_used_blueprint_ids=already_used_blueprint_ids,
            used_frame_ids=used_frame_ids, remaining_budget=remaining_budget,
        )
        decision = select_coverage_focused_target(shadow_input)
        if decision is None:
            return None

        pool_for_trait = [
            bp for bp in candidate_pool
            if bp.trait_id == decision.proposed_trait_id and bp.blueprint_id not in already_used_blueprint_ids
        ]
        blueprint = select_blueprint_for_trait(
            decision.proposed_trait_id, related_context_ids=set(), preferred_context_ids=[],
            final_contexts=final_contexts, used_v2_probe_frame_ids=used_frame_ids, candidate_pool=pool_for_trait,
        )
        if blueprint is None:
            return None

        log.turn_target_trait_ids.append(decision.proposed_trait_id)
        log.turn_selection_mode.append(decision.selection_mode)
        log.turn_exploration_slot_used.append(decision.exploration_slot_used)
        log.provisional_top_n_history.append(_provisional_top_n_snapshot(session_id, registry))
        return PackAdaptiveTargetDecision(trait_id=decision.proposed_trait_id, blueprint=blueprint)

    return steered_selector


# ============================== 세션 실행(4+1, 실제 Endpoint 그대로) ==============================


@dataclass
class SessionRun:
    scenario: PersonaScenario
    final_context_ids: list[str] = field(default_factory=list)
    anchor_by_context: dict[str, str] = field(default_factory=dict)
    trait_evidence_question_count: int = 0
    routing_question_count: int = 0
    backup_used_count: int = 0
    per_turn_target_trait_ids: list[str | None] = field(default_factory=list)
    final_evidence_ledger: list = field(default_factory=list)
    final_context_anchor_choices: dict[str, str] = field(default_factory=dict)


def _run_persona_session(
    scenario: PersonaScenario, *, session_id: str, registry: ContextPackRegistry, runtime: ContextPackRuntime,
) -> SessionRun:
    state = AssessmentState(session_id=session_id, user_id="shadow_persona")
    main_module._store.save(state)

    ratings = _ratings_for(scenario, set(CONTEXT_IDS))
    main_module.submit_interest_rating(InterestRatingRequest(session_id=session_id, ratings=ratings))

    select_resp = main_module.select_contexts(
        ContextSelectRequest(session_id=session_id, selected_preferred_context_ids=list(scenario.preferred_context_ids))
    )
    contrast_id = select_resp.contrast_context_id
    assert contrast_id == scenario.contrast_hint_context_id, (
        f"{scenario.key}: 의도한 Contrast {scenario.contrast_hint_context_id!r}가 아니라 {contrast_id!r}"
    )
    final_ids = [*scenario.preferred_context_ids, contrast_id]
    main_module.confirm_contexts(ContextConfirmRequest(session_id=session_id, final_context_ids=final_ids))

    run = SessionRun(scenario=scenario, final_context_ids=final_ids)
    run.anchor_by_context = {cid: _anchor_choice_for_persona(scenario, cid, registry, runtime) for cid in final_ids}

    iterations = 0
    while True:
        iterations += 1
        if iterations > MAX_QUESTION_LOOP_ITERATIONS:
            raise RuntimeError(f"{scenario.key}: 질문 루프가 안전 상한을 넘었다")

        resp = main_module.next_question(session_id)
        if resp.question is None:
            if resp.assessment_complete:
                break
            continue

        state = main_module._store.load(session_id)
        family = state.current_question_family_id
        question = resp.question

        if family == "context_routing":
            routing_blueprint = _routing_blueprint_for(question.context)
            desired_anchor = run.anchor_by_context.get(question.context)
            option = _choose_routing_option(question.options, routing_blueprint, desired_anchor)
        elif scenario.special_policy == "coverage_maximizing":
            gate = gate_primary_eligible_evidence(state.evidence_ledger, state.context_anchor_choices, registry)
            results = compute_all_trait_coverage(CORE_TRAIT_IDS, state.evidence_ledger, gate.approved_evidence_ids)
            running_weight = {t: r.effective_evidence_weight for t, r in results.items()}
            option = _choose_by_min_running_weight(question.options, running_weight)
        elif scenario.special_policy == "coverage_minimizing":
            option = _choose_concentrated(question.options, "causal_analysis")
        else:
            option = _choose_by_affinity(scenario, question.options)

        target_trait_id = state.current_v2_probe_target_trait_id if family == "pack_direct_probe" else None

        answer_resp = main_module.submit_answer(
            AnswerRequest(session_id=session_id, question_id=question.question_id, selected_option_id=option.option_id)
        )

        if family == "context_routing":
            run.routing_question_count += 1
        elif family != "conflict_resolution":
            run.trait_evidence_question_count += 1
            run.per_turn_target_trait_ids.append(target_trait_id)
            if resp.status.value == "BACKUP_USED":
                run.backup_used_count += 1

        if answer_resp.next_action == "ASSESSMENT_COMPLETE":
            break

    final_state = main_module._store.load(session_id)
    run.final_evidence_ledger = list(final_state.evidence_ledger)
    run.final_context_anchor_choices = dict(final_state.context_anchor_choices)
    return run


# ============================== 측정값(§5) ==============================

_STATUS_ORDER = {"UNOBSERVED": 0, "LIMITED": 1, "SUPPORTED": 2, "SUFFICIENT": 3, "CONFLICTED": 1}


def _coverage_results(ledger: list[Any], anchor_choices: dict[str, str], registry: ContextPackRegistry) -> dict[str, Any]:
    gate = gate_primary_eligible_evidence(ledger, anchor_choices, registry)
    return compute_all_trait_coverage(CORE_TRAIT_IDS, ledger, gate.approved_evidence_ids)


def _ranked_traits_for(scenario: PersonaScenario) -> list[str]:
    return sorted(CORE_TRAIT_IDS, key=lambda t: _affinity_rank(scenario, t))


def _top_n_fraction(results: dict[str, Any], ranked: list[str], n: int, *, min_status: str = "SUFFICIENT") -> float:
    threshold = _STATUS_ORDER[min_status]
    top = ranked[:n]
    if not top:
        return 0.0
    return sum(1 for t in top if _STATUS_ORDER.get(results[t].coverage_status, 0) >= threshold) / len(top)


def _repetition_stats(per_turn_targets: list[str | None]) -> dict[str, Any]:
    targeted = [t for t in per_turn_targets if t is not None]
    counts = Counter(targeted)
    return {
        "distinct_traits_targeted": len(counts),
        "max_repeat_count_for_a_single_trait": max(counts.values()) if counts else 0,
        "total_repeated_targeting_turns": sum(c - 1 for c in counts.values() if c > 1),
    }


def _diversity_stats(results: dict[str, Any]) -> dict[str, Any]:
    observed = [r for r in results.values() if r.coverage_status != "UNOBSERVED"]
    if not observed:
        return {"avg_distinct_context_count": 0.0, "avg_distinct_frame_count": 0.0, "observed_trait_count": 0}
    return {
        "avg_distinct_context_count": sum(r.distinct_context_count for r in observed) / len(observed),
        "avg_distinct_frame_count": sum(r.distinct_frame_count for r in observed) / len(observed),
        "observed_trait_count": len(observed),
    }


def _supported_or_better_count(results: dict[str, Any]) -> int:
    return sum(1 for r in results.values() if _STATUS_ORDER.get(r.coverage_status, 0) >= _STATUS_ORDER["SUPPORTED"])


def _unobserved_count(results: dict[str, Any]) -> int:
    return sum(1 for r in results.values() if r.coverage_status == "UNOBSERVED")


def _lockin_turns(log: _ShadowSteeredLog) -> int:
    """§5 "고착 Turn" — Shadow가 상위 N에 있다고 보고 배정했지만 나중에 그 Trait가
    상위 N에서 탈락한 경우, 탈락 전까지 그 Trait에 배정된 Turn 수(7f0637e 진단의
    `misidentified_trait_lockin_turns`와 같은 정의)."""

    history = log.provisional_top_n_history
    if not history:
        return 0
    ever_exited: set[str] = set()
    prev: set[str] = set()
    for snapshot in history:
        current = set(snapshot)
        ever_exited |= prev - current
        prev = current

    lockin = 0
    for idx, trait_id in enumerate(log.turn_target_trait_ids):
        if trait_id in ever_exited and idx < len(history) and trait_id in history[idx]:
            lockin += 1
    return lockin


# ============================== 전체 실행 ==============================


def run_and_summarize(scenarios: list[PersonaScenario]) -> dict[str, Any]:
    fake_llm = _DeterministicFakeLLMClient()
    saved_env = {
        k: os.environ.get(k)
        for k in ("ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", "ENABLE_CONTEXT_PACK_RUNTIME", "ENABLE_CONTEXT_SELECTION_4_PLUS_1")
    }
    baseline_summaries: list[dict[str, Any]] = []
    turn_comparisons: list[dict[str, Any]] = []
    shadow_summaries: list[dict[str, Any]] = []

    try:
        os.environ["ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES"] = "true"
        with tempfile.TemporaryDirectory(prefix="coverage_focused_shadow_fixture_") as tmp:
            fixture_dir = Path(tmp)
            fixture_registry = _build_fixture_registry(fixture_dir)
            fixture_runtime = ContextPackRuntime(
                fixture_registry, main_module.context_pack_runtime_enabled, frozenset(VERTICAL_SLICE_CONTEXT_IDS)
            )
            with (
                patch.object(main_module, "_llm_client", fake_llm),
                patch.object(main_module, "_context_pack_registry", fixture_registry),
                patch.object(main_module, "_context_pack_runtime", fixture_runtime),
            ):
                os.environ["ENABLE_CONTEXT_PACK_RUNTIME"] = "true"
                os.environ["ENABLE_CONTEXT_SELECTION_4_PLUS_1"] = "true"

                anchor_experiment = anchor_sensitivity_variants(scenarios[0], fixture_registry, fixture_runtime)

                # Pass 1 — Baseline 관찰(실제 결정 불변).
                for scenario in scenarios:
                    session_id = f"shadow_baseline_{scenario.key}"
                    log = _TurnComparisonLog()
                    observer = _make_observing_selector(session_id, fixture_registry, log)
                    with patch.object(main_module, "select_pack_adaptive_target", observer):
                        run = _run_persona_session(
                            scenario, session_id=session_id, registry=fixture_registry, runtime=fixture_runtime,
                        )
                    results = _coverage_results(run.final_evidence_ledger, run.final_context_anchor_choices, fixture_registry)
                    ranked = _ranked_traits_for(scenario)
                    match_count = sum(1 for m in log.match if m)
                    baseline_summaries.append({
                        "scenario_key": scenario.key, "scenario_label": scenario.label,
                        "final_context_ids": run.final_context_ids,
                        "trait_evidence_question_count": run.trait_evidence_question_count,
                        "backup_used_count": run.backup_used_count,
                        "coverage_status_breakdown": coverage_status_breakdown(results),
                        "top5_sufficient_fraction": _top_n_fraction(results, ranked, 5),
                        "top8_sufficient_fraction": _top_n_fraction(results, ranked, 8),
                        "supported_or_better_count": _supported_or_better_count(results),
                        "unobserved_trait_count": _unobserved_count(results),
                        "repetition_stats": _repetition_stats(run.per_turn_target_trait_ids),
                        "diversity_stats": _diversity_stats(results),
                    })
                    turn_comparisons.append({
                        "scenario_key": scenario.key,
                        "total_turns": len(log.turn_index),
                        "match_count": match_count,
                        "turn_agreement_rate": (match_count / len(log.turn_index)) if log.turn_index else 0.0,
                        "turns": [
                            {
                                "turn_index": log.turn_index[i],
                                "real_target_trait_id": log.real_target_trait_id[i],
                                "shadow_proposed_trait_id": log.shadow_proposed_trait_id[i],
                                "shadow_selection_mode": log.shadow_selection_mode[i],
                                "shadow_decision_reason": log.shadow_decision_reason[i],
                                "match": log.match[i],
                            }
                            for i in range(len(log.turn_index))
                        ],
                    })

                # Pass 2 — Shadow 대체 실행(별도 세션, 완전히 분리).
                for scenario in scenarios:
                    session_id = f"shadow_steered_{scenario.key}"
                    steered_log = _ShadowSteeredLog()
                    steered_selector = _make_shadow_steered_selector(session_id, fixture_registry, steered_log)
                    with patch.object(main_module, "select_pack_adaptive_target", steered_selector):
                        run = _run_persona_session(
                            scenario, session_id=session_id, registry=fixture_registry, runtime=fixture_runtime,
                        )
                    results = _coverage_results(run.final_evidence_ledger, run.final_context_anchor_choices, fixture_registry)
                    ranked = _ranked_traits_for(scenario)
                    shadow_summaries.append({
                        "scenario_key": scenario.key,
                        "trait_evidence_question_count": run.trait_evidence_question_count,
                        "backup_used_count": run.backup_used_count,
                        "coverage_status_breakdown": coverage_status_breakdown(results),
                        "top5_sufficient_fraction": _top_n_fraction(results, ranked, 5),
                        "top8_sufficient_fraction": _top_n_fraction(results, ranked, 8),
                        "supported_or_better_count": _supported_or_better_count(results),
                        "unobserved_trait_count": _unobserved_count(results),
                        "repetition_stats": _repetition_stats(steered_log.turn_target_trait_ids),
                        "diversity_stats": _diversity_stats(results),
                        "exploration_turns": sum(1 for x in steered_log.turn_exploration_slot_used if x),
                        "lockin_turns": _lockin_turns(steered_log),
                        "total_targeted_turns": len(steered_log.turn_target_trait_ids),
                    })
    finally:
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    return {
        "baseline": baseline_summaries, "turn_comparisons": turn_comparisons,
        "shadow_steered": shadow_summaries, "anchor_experiment": anchor_experiment,
    }


def _compare(summary: dict[str, Any]) -> dict[str, Any]:
    n = len(summary["baseline"])

    def avg(rows: list[dict[str, Any]], key: str) -> float:
        return sum(r[key] for r in rows) / n

    baseline_top5 = avg(summary["baseline"], "top5_sufficient_fraction")
    baseline_top8 = avg(summary["baseline"], "top8_sufficient_fraction")
    shadow_top5 = avg(summary["shadow_steered"], "top5_sufficient_fraction")
    shadow_top8 = avg(summary["shadow_steered"], "top8_sufficient_fraction")
    baseline_combined = (baseline_top5 + baseline_top8) / 2
    shadow_combined = (shadow_top5 + shadow_top8) / 2

    total_turns = sum(t["total_turns"] for t in summary["turn_comparisons"])
    total_matches = sum(t["match_count"] for t in summary["turn_comparisons"])
    turn_agreement_rate = (total_matches / total_turns) if total_turns else 0.0

    return {
        "baseline": {
            "top5_fraction_avg": baseline_top5, "top8_fraction_avg": baseline_top8,
            "combined_fraction_avg": baseline_combined,
            "total_trait_evidence_questions": sum(r["trait_evidence_question_count"] for r in summary["baseline"]),
            "avg_unobserved_trait_count": avg(summary["baseline"], "unobserved_trait_count"),
            "avg_supported_or_better_count": avg(summary["baseline"], "supported_or_better_count"),
        },
        "shadow_steered": {
            "top5_fraction_avg": shadow_top5, "top8_fraction_avg": shadow_top8,
            "combined_fraction_avg": shadow_combined,
            "total_trait_evidence_questions": sum(r["trait_evidence_question_count"] for r in summary["shadow_steered"]),
            "avg_unobserved_trait_count": avg(summary["shadow_steered"], "unobserved_trait_count"),
            "avg_supported_or_better_count": avg(summary["shadow_steered"], "supported_or_better_count"),
            "total_lockin_turns": sum(r["lockin_turns"] for r in summary["shadow_steered"]),
            "total_exploration_turns": sum(r["exploration_turns"] for r in summary["shadow_steered"]),
        },
        "combined_improvement_over_baseline": shadow_combined - baseline_combined,
        "turn_agreement_rate": turn_agreement_rate,
        "persona_count": n,
    }


def _conclusion(comparison: dict[str, Any]) -> dict[str, Any]:
    improvement = comparison["combined_improvement_over_baseline"]
    agreement = comparison["turn_agreement_rate"]
    meaningfully_better = improvement >= MINIMUM_MEANINGFUL_IMPROVEMENT

    if not meaningfully_better and improvement < 0:
        verdict = "REJECTED"
        justification = (
            f"Shadow 대체 실행 결합 점수({comparison['shadow_steered']['combined_fraction_avg']:.3f})가 "
            f"Baseline({comparison['baseline']['combined_fraction_avg']:.3f})보다 낮다"
            f"({improvement:+.3f}) — Coverage-focused Selector가 현재 정의로는 Baseline보다 못하다."
        )
    elif not meaningfully_better:
        verdict = "NEEDS_MORE_SHADOW_EVIDENCE"
        justification = (
            f"결합 점수 개선({improvement:+.3f})이 사전 문턱({MINIMUM_MEANINGFUL_IMPROVEMENT:.2f}) "
            "미달이다 — Baseline보다 나쁘지는 않지만 Runtime Flag를 켤 만큼 뚜렷하지도 않다."
        )
    elif agreement < MINIMUM_TURN_AGREEMENT_RATE_FOR_READY:
        verdict = "NEEDS_MORE_SHADOW_EVIDENCE"
        justification = (
            f"결합 점수는 {improvement:+.3f} 개선했지만 Turn 단위 일치율({agreement:.3f})이 최소선"
            f"({MINIMUM_TURN_AGREEMENT_RATE_FOR_READY:.2f}) 미만이다 — 실제 Planner와 판이하게 다른 "
            "순서로 질문했는데 결과만 우연히 좋아졌을 가능성을 배제할 수 없다. 더 많은 Persona·"
            "실제 세션 관찰이 필요하다."
        )
    else:
        verdict = "READY_FOR_RUNTIME_FLAG"
        justification = (
            f"결합 점수가 Baseline 대비 {improvement:+.3f} 개선(문턱 {MINIMUM_MEANINGFUL_IMPROVEMENT:.2f} "
            f"이상)했고, Turn 단위 일치율도 {agreement:.3f}로 최소선 이상이다 — Runtime Feature Flag "
            "도입을 검토할 근거가 된다(이 판정 자체가 Flag를 켜지는 않는다)."
        )

    return {
        "verdict": verdict,
        "justification": justification,
        "minimum_meaningful_improvement_threshold": MINIMUM_MEANINGFUL_IMPROVEMENT,
        "minimum_turn_agreement_rate_for_ready": MINIMUM_TURN_AGREEMENT_RATE_FOR_READY,
        "note": (
            "이 판정은 자동으로 어떤 Feature Flag도 켜지 않는다 — 기본 Planner를 자동 교체하지 "
            "않는다(과제 §7). data/master·API·Stop Condition·Runtime Planner는 이 스크립트로 "
            "전혀 바뀌지 않았다."
        ),
    }


def _write_json_report(summary: dict[str, Any], comparison: dict[str, Any], conclusion: dict[str, Any], persona_keys: list[str]) -> None:
    payload = {
        "persona_count": len(persona_keys),
        "persona_keys": persona_keys,
        "shadow_only": True,
        "selector_constants": {
            "provisional_top_n": PROVISIONAL_TOP_N,
            "coverage_sufficient_min_primary_count": SUFFICIENT_MIN_PRIMARY_COUNT,
            "coverage_sufficient_min_effective_weight": SUFFICIENT_MIN_EFFECTIVE_WEIGHT,
            "coverage_sufficient_min_context_count": SUFFICIENT_MIN_CONTEXT_COUNT,
            "coverage_sufficient_min_frame_count": SUFFICIENT_MIN_FRAME_COUNT,
        },
        "baseline_personas": summary["baseline"],
        "turn_comparisons": summary["turn_comparisons"],
        "shadow_steered_personas": summary["shadow_steered"],
        "anchor_sensitivity": summary["anchor_experiment"],
        "comparison": comparison,
        "conclusion": conclusion,
        "note": (
            "생성 시각 없음 — byte-identical 재실행. data/reviews/는 이 스크립트가 읽지도 쓰지도 "
            "않는다(Fixture만 사용). Runtime Planner·Stop Condition·질문 Blueprint·Trait "
            "Mapping·Review JSON 어느 것도 수정하지 않았다. 학생 답변·질문 원문은 이 보고서에 "
            "포함하지 않았다 — Trait id·통계만 남긴다."
        ),
    }
    JSON_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {JSON_OUTPUT_PATH}")


def _write_markdown_report(summary: dict[str, Any], comparison: dict[str, Any], conclusion: dict[str, Any], persona_keys: list[str]) -> None:
    lines: list[str] = [
        "# Coverage-focused Target Selector — Shadow 평가 (a/coverage-focused-planner-shadow)",
        "",
        "별도 Worktree·별도 브랜치, 읽기 중심 Shadow 평가만 수행했다 — Runtime Planner·"
        "Stop Condition·질문·Mapping·Review JSON은 전혀 바꾸지 않았다. 학생 답변·질문 "
        "원문은 이 보고서에 없다.",
        "",
        f"Persona {len(persona_keys)}개(기존 9개 전부): {', '.join(persona_keys)}.",
        "",
        "## 1. Baseline vs Shadow 대체 실행 — Persona별",
        "",
        "| Persona | Baseline 상위5 | Baseline 상위8 | Shadow 상위5 | Shadow 상위8 | Turn 일치율 |",
        "|---|---|---|---|---|---|",
    ]
    turn_by_key = {t["scenario_key"]: t for t in summary["turn_comparisons"]}
    shadow_by_key = {s["scenario_key"]: s for s in summary["shadow_steered"]}
    for b in summary["baseline"]:
        key = b["scenario_key"]
        s = shadow_by_key[key]
        t = turn_by_key[key]
        lines.append(
            f"| {b['scenario_label']} | {b['top5_sufficient_fraction']:.3f} | {b['top8_sufficient_fraction']:.3f} | "
            f"{s['top5_sufficient_fraction']:.3f} | {s['top8_sufficient_fraction']:.3f} | "
            f"{t['turn_agreement_rate']:.3f} |"
        )

    lines += [
        "",
        "## 2. 요약",
        "",
        f"- Baseline 결합 점수: {comparison['baseline']['combined_fraction_avg']:.3f}",
        f"- Shadow 대체 실행 결합 점수: {comparison['shadow_steered']['combined_fraction_avg']:.3f}"
        f"({comparison['combined_improvement_over_baseline']:+.3f})",
        f"- Turn 단위 일치율(전체): {comparison['turn_agreement_rate']:.3f}",
        f"- Shadow 고착 Turn(총): {comparison['shadow_steered']['total_lockin_turns']}",
        f"- Shadow Exploration Turn(총): {comparison['shadow_steered']['total_exploration_turns']}",
        f"- Baseline 평균 SUPPORTED 이상 Trait 수: {comparison['baseline']['avg_supported_or_better_count']:.2f}",
        f"- Shadow 평균 SUPPORTED 이상 Trait 수: {comparison['shadow_steered']['avg_supported_or_better_count']:.2f}",
        f"- Baseline 평균 미관찰 Trait 수: {comparison['baseline']['avg_unobserved_trait_count']:.2f}",
        f"- Shadow 평균 미관찰 Trait 수: {comparison['shadow_steered']['avg_unobserved_trait_count']:.2f}",
        "",
        "## 3. Anchor 민감도(Coverage 최대/기본/최소)",
        "",
        f"대상 Context: `{summary['anchor_experiment']['target_context']}` "
        f"(후보 Trait 수: {summary['anchor_experiment']['anchor_candidate_trait_counts']}, "
        f"Anchor에 따라 후보 풀이 갈리는가: {summary['anchor_experiment']['candidate_pool_varies_by_anchor']})",
        f"- 최대: `{summary['anchor_experiment']['max_coverage_anchor']}` · "
        f"최소: `{summary['anchor_experiment']['min_coverage_anchor']}` · "
        f"기본(Persona별): `{summary['anchor_experiment']['persona_default_anchor']}`",
        "",
        "## 4. 판정",
        "",
        f"**결론: {conclusion['verdict']}**",
        "",
        conclusion["justification"],
        "",
        conclusion["note"],
    ]
    MD_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MD_OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {MD_OUTPUT_PATH}")


def main() -> None:
    scenarios = _persona_scenarios()
    persona_keys = [s.key for s in scenarios]
    summary = run_and_summarize(scenarios)
    comparison = _compare(summary)
    conclusion = _conclusion(comparison)
    _write_json_report(summary, comparison, conclusion, persona_keys)
    _write_markdown_report(summary, comparison, conclusion, persona_keys)


if __name__ == "__main__":
    raise SystemExit(main() or 0)
