"""Trait Evidence Coverage — Adaptive Target Planner Gap 진단 (읽기 중심 Shadow) —
a/trait-evidence-coverage-planner-gap.

**목표.** 실제 Pack Context Adaptive Target Planner(`select_pack_adaptive_target`,
`src/engines/context_pack_adaptive_planner.py`, 수정 금지)는 한 Context 안에서
`support_count>=2`가 되면 그 Trait를 더 이상 "부족(Gap)"으로 보지 않고 다른 Trait로
넘어간다(`_is_evidence_gap`). 반면 Trait Evidence Coverage Policy(`src/engines/
trait_evidence_coverage_engine.py`, a/trait-evidence-coverage-shadow에서 이식,
이번에도 수정하지 않는다)의 SUFFICIENT는 `weight>=3.0`·`Context>=2`·`Frame>=2`를
요구한다. Primary 2개만으로는 weight가 정확히 2.0이라 3.0 문턱을 못 넘는다 — 두 조건이
서로 다른 것을 요구하는 구조적 불일치다. 이 스크립트는 그 불일치를 실제 4+1 세션에서
정량적으로 기록하고, Runtime을 건드리지 않는 Shadow 대안 4개(A/B/C/D)를 비교한다.

**재사용하는 실제 함수** (다시 구현하지 않는다):

    src.api.main.submit_interest_rating / select_contexts / confirm_contexts /
        next_question / submit_answer        ← 실제 Endpoint. 이번 Base는
        `ENABLE_CONTEXT_SELECTION_4_PLUS_1`이 네이티브로 배선돼 있어(§ 2026-08-24
        지시서) 이전 라운드(a/trait-evidence-coverage-shadow)처럼 Endpoint를 우회해
        `select_contrast_context()`를 직접 부를 필요가 없다 — 이번엔 우회가 전혀 없다.
    src.engines.context_pack_adaptive_planner.compute_pack_context_trait_summaries /
        _is_evidence_gap / select_pack_adaptive_target  ← 실제 Planner. Baseline은
        그대로 호출하고, A/B/C Shadow 대안은 `select_pack_adaptive_target`**만**
        `unittest.mock.patch.object(main_module, ...)`로 세션마다 새로 갈아 끼운다
        (같은 이름을 참조하는 main.py 호출부는 그대로 실제 함수다 — 소스 파일 자체는
        한 바이트도 바뀌지 않는다). Blueprint 선택 자체는 A/B/C도 전부 실제
        `select_blueprint_for_trait`를 그대로 쓴다 — 바뀌는 건 "어떤 Trait를 먼저
        고를지"뿐이다.
    src.engines.evidence_engine.decide_stop_or_continue  ← 최소 4·최대 6 Stop
        Condition. A/B/C도 이 함수를 그대로 통과한다 — 즉 Context당 질문 수 상한
        자체는 대안에 따라 바뀌지 않는다(§ 아래 "질문 수가 대안마다 거의 같은 이유").
    src.engines.trait_evidence_coverage_engine.compute_all_trait_coverage /
        coverage_status_breakdown  ← Coverage Policy(이식, 미변경).
    src.services.trait_signal_review_gate.gate_primary_eligible_evidence ← Human
        Review Gate.
    src.services.context_pack_runtime.ContextPackRuntime / context_pack_registry ←
        Pack Context Seed/Backup/Direct Probe 후보 조회(Fixture Registry와 함께).

## data/reviews/ 무변경

12개 ContextPack·공용 Adaptive Probe 승인은 전부 `tempfile` Fixture 안에서만 만든다
(a/trait-evidence-coverage-shadow와 동일한 패턴, `_build_fixture_registry`).

## 가볍게 유지한 선택 — 9개 Persona가 아니라 4개만 쓴다

이전 라운드(a/trait-evidence-coverage-shadow)는 9개 Persona × 2 환경(3/15 Context)을
전부 순회했다. 이번 지시는 "읽기 중심 Shadow 진단만" — 24개 전체 Trait를 관찰하려고
검사 시간을 늘리지 말라는 원칙(§5)과 같은 이유로, Persona도 다양성을 잃지 않는 선에서
줄인다. 이전 9개 중 Pack Context 비중이 크고 서로 다른 성격(광범위/좁음/혼합/의도적
Coverage 확장)을 대표하는 4개만 그대로 재사용한다(정의는 완전히 동일 — 새로 만들지
않는다): `coverage_maximizing`(의도적 Context 다양화), `analytical`(Pack Context
4개 전부), `niche_interest`(Pack Context 4개 전부, 좁은 주제), `mixed_cross_domain`
(뚜렷한 선호 없음, Legacy+Pack 혼합).

## 대안 A/B/C/D — 무엇을 바꾸고 무엇을 안 바꾸는가

네 대안 모두 실제 Runtime 소스 파일을 바꾸지 않는다. A/B/C는 이 스크립트 안에서만
`select_pack_adaptive_target`을 세션 실행 중에 몽키패치해 "다음에 어떤 Trait를
목표로 삼을지" 판단 로직만 바꿔 낀다(Blueprint 선택·Stop Condition은 그대로 실제
함수). D는 아예 아무것도 바꾸지 않는다 — Baseline 결과를 SUFFICIENT 대신 SUPPORTED
이상 기준으로 다시 집계할 뿐이다.

    A. Planner 목표를 Coverage SUFFICIENT와 동일하게 조정
       gap(trait) := (세션 전체 Coverage 상태가 SUFFICIENT가 아니다)
    B. Primary 2개를 먼저 채우고, 그 다음에만 부족분(Related/Context/Frame)을 보충
       gap(trait) := (그 Context 안 support_count<2) 가 최우선이고, 그것도 없으면
       (세션 전체가 SUFFICIENT가 아니다)를 2순위 tier로 — 즉 "누구도 아직 못
       받아본 Trait"가 먼저다.
    C. 상위 Trait 5~8개만 SUFFICIENT 목표로 삼음
       gap(trait) := trait가 top_traits(그 Persona의 선호 순위 상위 8개)에 속하고
       세션 전체 Coverage가 SUFFICIENT가 아니다. top_traits 밖의 Trait는 절대
       목표가 되지 않는다.
    D. Coverage 기준은 그대로 두고, 결과를 SUPPORTED 중심으로 표현
       재실행하지 않는다 — Baseline의 Coverage 결과를 "SUFFICIENT뿐 아니라
       SUPPORTED 이상도 상위 5·8개 충족으로 센다"는 표현 방식만 바꾼다.

## 질문 수가 대안마다 거의 같은 이유

CLAUDE.md·이번 지시 §6은 Stop/Continue를 LLM이나 이 진단이 바꾸지 못하게 한다 —
`decide_stop_or_continue()`가 강제하는 "Context당 최소 4·최대 6"은 A/B/C에서도
그대로다. 즉 어떤 대안도 Context 하나에 배정된 질문 "개수"를 늘리거나 줄이지
못한다 — 바뀌는 건 그 고정된 4~6개 슬롯을 "어떤 Trait에 쓸지"뿐이다(후보 소진으로
Context가 4개 미만에서 Backup으로 조기 종료되는 경우는 예외적으로 대안마다 갈릴 수
있다 — 실측 결과로 보고한다). "반복 질문 증가량"은 그래서 총 질문 수 차이가 아니라
"이미 그 대안 자신의 기준으로 더 이상 필요 없는 Trait에 슬롯이 배정된 횟수"로
정의한다(§ 아래 `_wasted_slot_count`)."""

from __future__ import annotations

import json
import os
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
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAIT_IDS  # noqa: E402
from src.engines.context_pack_adaptive_planner import (  # noqa: E402
    PackAdaptiveTargetDecision,
    _is_evidence_gap,
    compute_pack_context_trait_summaries,
)
from src.engines.trait_evidence_coverage_engine import (  # noqa: E402
    SUFFICIENT_MIN_CONTEXT_COUNT,
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

import re  # noqa: E402

_CONTEXT_RE = re.compile(r'context 필드에는 "(\w+)"를')
_FRAME_RE = re.compile(r'frame_id 필드에는 "(\w+)"를')
_ROLE_RE = re.compile(r"\[Option Role.*?\]\n(.*?)\n\ncontext 필드", re.DOTALL)


class _DeterministicFakeLLMClient:
    """tests/test_context_pack_adaptive_e2e.py::_FakeLLMClient와 동일 원리 —
    Prompt에서 실제 context/frame_id/role_id를 파싱해 되돌려준다. `question_text`에
    호출 순번을 넣어야 한다 — 실측 결과 Quality Gate가 "이전 질문과 문구가 같으면
    재생성" 규칙을 갖고 있어, 매번 같은 문구를 돌려주면 두 번째 Tail 질문부터
    재생성 실패 → Backup으로 빠진다(a/trait-evidence-coverage-shadow에서 실측)."""

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


VERTICAL_SLICE_CONTEXT_IDS: tuple[str, ...] = ("game", "media", "school_life")
MAX_QUESTION_LOOP_ITERATIONS = 200

JSON_OUTPUT_PATH = ROOT / "outputs" / "evaluation" / "trait_evidence_coverage_planner_gap_report.json"
MD_OUTPUT_PATH = ROOT / "outputs" / "evaluation" / "trait_evidence_coverage_planner_gap_report.md"


# ============================== Persona 시나리오(9개 중 4개 재사용) ==============================


@dataclass(frozen=True)
class PersonaScenario:
    key: str
    label: str
    preferred_context_ids: tuple[str, ...]  # 정확히 4개
    contrast_hint_context_id: str
    trait_affinity_order: tuple[str, ...] = ()
    special_policy: str | None = None  # "coverage_maximizing" | None


def _persona_scenarios() -> list[PersonaScenario]:
    return [
        PersonaScenario(
            "analytical", "분석형",
            ("science", "business", "sports", "law_politics"), "making",
            ("causal_analysis", "pattern_finding", "information_comparison", "systems_thinking",
             "detail_orientation", "planning", "independent_judgment", "uncertainty_tolerance"),
        ),
        PersonaScenario(
            "mixed_cross_domain", "혼합·교차형",
            ("game", "cooking", "law_politics", "art_design"), "science",
            (),
        ),
        PersonaScenario(
            "niche_interest", "니치 관심형",
            ("fashion_beauty", "travel", "cooking", "art_design"), "making",
            ("aesthetic_sensitivity", "novelty_seeking", "challenge_seeking",
             "personal_goal_priority", "independent_judgment"),
        ),
        PersonaScenario(
            "coverage_maximizing", "Coverage 최대화형",
            ("science", "media", "school_life", "business"), "making",
            special_policy="coverage_maximizing",
        ),
    ]


def _ratings_for(scenario: PersonaScenario, all_context_ids: set[str]) -> dict[str, int]:
    ratings: dict[str, int] = {}
    for context_id in sorted(all_context_ids):
        if context_id in scenario.preferred_context_ids:
            ratings[context_id] = 5
        elif context_id == scenario.contrast_hint_context_id:
            ratings[context_id] = 2
        else:
            ratings[context_id] = 1
    return ratings


def _anchor_ids_for_context(context_id: str, registry: ContextPackRegistry) -> list[str]:
    if context_id in VERTICAL_SLICE_CONTEXT_IDS:
        from src.data.contexts.context_anchor_presentations import CONTEXT_ANCHOR_PRESENTATIONS

        return sorted(p.anchor_id for p in CONTEXT_ANCHOR_PRESENTATIONS if p.context_id == context_id)
    pack = registry.get_pack(context_id)
    if pack is None:
        return []
    return sorted(a.anchor_id for a in pack.anchor_presentations)


def _anchor_choice_for(context_id: str, registry: ContextPackRegistry) -> str:
    anchors = _anchor_ids_for_context(context_id, registry)
    if not anchors:
        raise ValueError(f"{context_id}에 등록된 Anchor가 없다")
    return anchors[0]


def _build_fixture_registry(fixture_dir: Path) -> ContextPackRegistry:
    """§ "data/reviews/ 무변경" — 실제 data/reviews/는 이 함수가 열어보지 않는다."""

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


# ============================== 답변 선택 정책(이전 라운드와 동일) ==============================


def _affinity_rank(scenario: PersonaScenario, trait_id: str) -> tuple[int, str]:
    try:
        idx = scenario.trait_affinity_order.index(trait_id)
    except ValueError:
        idx = len(scenario.trait_affinity_order)
    return (idx, trait_id)


def _top_traits_for(scenario: PersonaScenario, n: int) -> set[str]:
    ranked = sorted(CORE_TRAIT_IDS, key=lambda t: _affinity_rank(scenario, t))
    return set(ranked[:n])


def _choose_by_affinity(scenario: PersonaScenario, options: list[Any]) -> Any:
    candidates = [o for o in options if o.primary_trait_delta]
    if not candidates:
        return options[0]
    return min(candidates, key=lambda o: _affinity_rank(scenario, next(iter(o.primary_trait_delta))))


def _choose_by_min_running_weight(options: list[Any], running_weight: dict[str, float]) -> Any:
    candidates = [o for o in options if o.primary_trait_delta]
    if not candidates:
        return options[0]
    return min(
        candidates,
        key=lambda o: (running_weight.get(next(iter(o.primary_trait_delta)), 0.0), next(iter(o.primary_trait_delta))),
    )


def _choose_routing_option(options: list[Any], routing_blueprint: Any, desired_anchor_id: str) -> Any:
    role_id = next(m.role_id for m in routing_blueprint.option_mappings if m.context_anchor == desired_anchor_id)
    return next(o for o in options if o.role_id == role_id)


def _routing_blueprint_for(context_id: str) -> Any:
    routing = main_module.CONTEXT_ROUTING_BLUEPRINTS_BY_CONTEXT.get(context_id)
    if routing is not None:
        return routing
    return main_module._context_pack_runtime.get_routing_question(context_id)


def _running_weight_snapshot(state: AssessmentState) -> dict[str, float]:
    gate = gate_primary_eligible_evidence(state.evidence_ledger, state.context_anchor_choices, main_module._context_pack_registry)
    results = compute_all_trait_coverage(CORE_TRAIT_IDS, state.evidence_ledger, gate.approved_evidence_ids)
    return {trait_id: r.effective_evidence_weight for trait_id, r in results.items()}


def _session_coverage_snapshot(session_id: str, registry: ContextPackRegistry) -> dict[str, Any]:
    state = main_module._store.load(session_id)
    gate = gate_primary_eligible_evidence(state.evidence_ledger, state.context_anchor_choices, registry)
    return compute_all_trait_coverage(CORE_TRAIT_IDS, state.evidence_ledger, gate.approved_evidence_ids)


# ============================== Planner Gap 대안 A/B/C(Shadow 전용) ==============================
#
# 셋 다 실제 select_pack_adaptive_target과 완전히 같은 시그니처의 drop-in이다 — 실제
# 소스 파일은 바꾸지 않고, 이 세션 실행 동안만 main_module.select_pack_adaptive_target을
# 몽키패치한다. 후보 Blueprint 선택은 전부 실제 select_blueprint_for_trait를 그대로
# 쓴다 — 바뀌는 건 "어떤 Trait를 먼저 고를지"의 gap() 정의뿐이다.


@dataclass
class _AltDecisionLog:
    """이 세션 실행 동안 실제로 벌어진 target 선택 하나하나를 기록 — "낭비된 슬롯"
    계산에 쓴다."""

    turn_target_trait_ids: list[str] = field(default_factory=list)
    turn_was_gap_at_assignment: list[bool] = field(default_factory=list)


def _make_alt_selector(
    alt: str, session_id: str, top_traits: set[str] | None, log: _AltDecisionLog, registry: ContextPackRegistry,
):
    """§ 대안 A/B/C. `trait_summaries`는 실제 main.py가 넘기는 그 Context 전용 요약
    (support_count 등)이고, 세션 전체 Coverage 상태가 필요하면 `_session_coverage_snapshot`
    으로 그때그때 새로 읽는다(이미 저장된 실제 State 그대로, 다시 계산하지 않는다)."""

    def selector(
        *,
        candidate_pool: list[V2DirectProbeBlueprint],
        trait_summaries: dict[str, Any],
        already_used_blueprint_ids: set[str],
        recent_target_trait_id: str | None,
        used_frame_ids: set[str],
        final_contexts: list[str],
    ) -> PackAdaptiveTargetDecision | None:
        candidate_trait_ids = sorted({bp.trait_id for bp in candidate_pool})
        coverage = _session_coverage_snapshot(session_id, registry)

        def is_sufficient(trait_id: str) -> bool:
            result = coverage.get(trait_id)
            return result is not None and result.coverage_status == "SUFFICIENT"

        def local_gap(trait_id: str) -> bool:
            return _is_evidence_gap(trait_id, trait_summaries)

        if alt == "A":
            def gap(trait_id: str) -> bool:
                return not is_sufficient(trait_id)
        elif alt == "B":
            def gap(trait_id: str) -> bool:
                # 1순위: 이 Context에서 아직 support_count<2인 Trait(오늘의 실제 동작과
                # 동일). 2순위(그것도 없을 때만): 세션 전체가 아직 SUFFICIENT가 아닌
                # Trait(부족분 보충).
                return local_gap(trait_id) or not is_sufficient(trait_id)
        elif alt == "C":
            assert top_traits is not None
            def gap(trait_id: str) -> bool:
                return trait_id in top_traits and not is_sufficient(trait_id)
        else:
            raise ValueError(f"알 수 없는 대안: {alt}")

        def sort_key(trait_id: str) -> tuple[bool, bool, bool, str]:
            # B는 "아직 아무것도 못 받은 Trait"를 "부족분만 보충"보다 항상 우선한다 —
            # 그래서 local_gap 여부를 별도 tier로 앞에 둔다(A/C는 이 tier가 의미 없어
            # local_gap이 항상 True인 것처럼 취급되게 gap()과 동일값을 넣는다).
            first_tier = local_gap(trait_id) if alt == "B" else gap(trait_id)
            overall_gap = gap(trait_id)
            same_as_recent = trait_id == recent_target_trait_id
            return (not first_tier, not overall_gap, same_as_recent, trait_id)

        chosen_trait_id: str | None = None
        chosen_blueprint: V2DirectProbeBlueprint | None = None
        for trait_id in sorted(candidate_trait_ids, key=sort_key):
            pool_for_trait = [
                bp for bp in candidate_pool
                if bp.trait_id == trait_id and bp.blueprint_id not in already_used_blueprint_ids
            ]
            if not pool_for_trait:
                continue
            blueprint = select_blueprint_for_trait(
                trait_id, related_context_ids=set(), preferred_context_ids=[],
                final_contexts=final_contexts, used_v2_probe_frame_ids=used_frame_ids,
                candidate_pool=pool_for_trait,
            )
            if blueprint is not None:
                chosen_trait_id, chosen_blueprint = trait_id, blueprint
                break

        if chosen_trait_id is None:
            return None
        log.turn_target_trait_ids.append(chosen_trait_id)
        log.turn_was_gap_at_assignment.append(gap(chosen_trait_id))
        return PackAdaptiveTargetDecision(trait_id=chosen_trait_id, blueprint=chosen_blueprint)

    return selector


# ============================== 실제 세션 실행 ==============================


@dataclass
class TraitTerminationRecord:
    """Trait 하나가 어느 Context에서, 몇 번째 Trait-Evidence 질문에서 실제 Planner의
    `support_count>=2` 판정을 처음 만족했는지(그 Context 안에서 더 이상 Gap이 아니게
    된 순간) — Coverage Policy가 요구하는 조건과 별개다."""

    trait_id: str
    stopped_in_context: str | None = None
    stopped_at_turn_index: int | None = None
    retargeted_in_other_context_after_stop: bool = False
    coverage_status_at_stop_moment: str | None = None
    coverage_status_final: str = "UNOBSERVED"
    final_primary_count: int = 0
    final_related_count: int = 0
    final_weight: float = 0.0
    final_context_count: int = 0
    final_frame_count: int = 0


@dataclass
class SessionRun:
    scenario: PersonaScenario
    final_context_ids: list[str] = field(default_factory=list)
    anchor_by_context: dict[str, str] = field(default_factory=dict)
    trait_evidence_question_count: int = 0
    routing_question_count: int = 0
    backup_used_count: int = 0
    final_evidence_ledger: list = field(default_factory=list)
    final_context_anchor_choices: dict[str, str] = field(default_factory=dict)
    per_turn_target_trait_ids: list[str | None] = field(default_factory=list)  # None = seed/backup 미지정


def _run_persona_session(
    scenario: PersonaScenario, *, session_id: str, registry: ContextPackRegistry,
) -> SessionRun:
    """실제 Endpoint(`submit_interest_rating`/`select_contexts`/`confirm_contexts`/
    `next_question`/`submit_answer`)만 호출한다 — 우회 없음. `ENABLE_CONTEXT_SELECTION_
    4_PLUS_1=true`가 이미 이 프로세스에 켜져 있다는 전제로, "선호 4개 확정" 또는
    "선호 4개+제안된 Contrast 1개"만 허용하는 실제 검증(§ main.py confirm_contexts)을
    그대로 통과시킨다."""

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
    run.anchor_by_context = {cid: _anchor_choice_for(cid, registry) for cid in final_ids}

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
            running_weight = _running_weight_snapshot(state)
            option = _choose_by_min_running_weight(question.options, running_weight)
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


def _coverage_results(run: SessionRun, ledger: list[Any], registry: ContextPackRegistry) -> dict[str, Any]:
    gate = gate_primary_eligible_evidence(ledger, run.final_context_anchor_choices, registry)
    return compute_all_trait_coverage(CORE_TRAIT_IDS, ledger, gate.approved_evidence_ids)


_STATUS_ORDER = {"UNOBSERVED": 0, "LIMITED": 1, "SUPPORTED": 2, "SUFFICIENT": 3, "CONFLICTED": 1}


def _top_n_sufficient(results: dict[str, Any], ranked_traits: list[str], n: int, *, min_status: str = "SUFFICIENT") -> bool:
    """전부-아니면-말고(All-or-nothing) — 상위 n개가 '한 명이라도' 기준 미달이면 False.
    질문 예산이 작을수록(§ 이 지시서 자체가 "불필요하게 늘리지 말라") 거의 항상 False가
    나오는 거친 지표다 — 그래서 `_top_n_sufficient_fraction`을 주 비교 지표로 함께 쓴다."""

    threshold = _STATUS_ORDER[min_status]
    top = ranked_traits[:n]
    return all(_STATUS_ORDER.get(results[t].coverage_status, 0) >= threshold for t in top)


def _top_n_sufficient_fraction(results: dict[str, Any], ranked_traits: list[str], n: int, *, min_status: str = "SUFFICIENT") -> float:
    """상위 n개 중 기준을 충족한 비율(0.0~1.0) — All-or-nothing보다 세밀하게 대안 간
    차이를 드러낸다(§ 실측: All-or-nothing만 쓰면 네 대안 전부 0.00으로 나와 차이를
    구분할 수 없었다)."""

    threshold = _STATUS_ORDER[min_status]
    top = ranked_traits[:n]
    if not top:
        return 0.0
    return sum(1 for t in top if _STATUS_ORDER.get(results[t].coverage_status, 0) >= threshold) / len(top)


def _termination_records(
    scenario: PersonaScenario, run: SessionRun, registry: ContextPackRegistry,
) -> dict[str, TraitTerminationRecord]:
    """Trait별로 (a) 실제 Planner가 각 Context 안에서 언제 `support_count>=2`가 됐는지
    (b) 그 이후 다른 Context에서 다시 목표가 됐는지 (c) 그 순간의 세션 전체 Coverage
    상태 (d) 최종 Coverage 상태를 전부 실제 함수(`compute_pack_context_trait_summaries`,
    `compute_all_trait_coverage`)로만 계산한다."""

    records = {t: TraitTerminationRecord(trait_id=t) for t in CORE_TRAIT_IDS}
    final_results = _coverage_results(run, run.final_evidence_ledger, registry)

    # Context별 offered_trait_ids_by_question을 재구성할 필요 없이, evidence_ledger를
    # 그대로 다시 쓰는 compute_pack_context_trait_summaries는 "지금까지 쌓인 ledger"
    # 만 있으면 되므로, ledger를 그때그때 프리픽스로 잘라 재계산한다(실제 함수 재사용,
    # 재구현 없음).
    ledger = run.final_evidence_ledger
    contexts_seen_order = run.final_context_ids

    already_stopped: dict[str, str] = {}  # trait_id -> stopped_in_context
    for turn_index, target_trait_id in enumerate(run.per_turn_target_trait_ids, start=1):
        if target_trait_id is None:
            continue
        # 이 turn까지의 ledger 접두(같은 개수만큼의 PRIMARY/V2_DIRECT_PROBE 레코드) —
        # context_routing/conflict_resolution도 ledger에 섞여 있을 수 있어 turn_index를
        # 그대로 ledger 길이로 쓰지 않고, "Trait-Evidence 질문 turn_index개를 실제로
        # 답했을 때까지의 전체 ledger"를 다시 계산해 스냅샷을 만든다.
        prefix_ledger = ledger[: _ledger_length_after_nth_trait_question(run, turn_index)]
        for context_id in contexts_seen_order:
            summaries = compute_pack_context_trait_summaries(
                prefix_ledger, _rebuild_offered_map(run, turn_index), context_id=context_id, trait_ids=CORE_TRAIT_IDS,
            )
            summary = summaries.get(target_trait_id)
            if summary is None or summary.support_count < 2:
                continue
            if target_trait_id in already_stopped:
                if already_stopped[target_trait_id] != context_id:
                    records[target_trait_id].retargeted_in_other_context_after_stop = True
                continue
            already_stopped[target_trait_id] = context_id
            records[target_trait_id].stopped_in_context = context_id
            records[target_trait_id].stopped_at_turn_index = turn_index
            snapshot_results = _coverage_results(run, prefix_ledger, registry)
            records[target_trait_id].coverage_status_at_stop_moment = snapshot_results[target_trait_id].coverage_status

    for trait_id, record in records.items():
        result = final_results[trait_id]
        record.coverage_status_final = result.coverage_status
        record.final_primary_count = result.primary_evidence_count
        record.final_related_count = result.related_evidence_count
        record.final_weight = result.effective_evidence_weight
        record.final_context_count = result.distinct_context_count
        record.final_frame_count = result.distinct_frame_count

    return records


def _ledger_length_after_nth_trait_question(run: SessionRun, n: int) -> int:
    """`per_turn_target_trait_ids`의 n번째 항목까지 실제로 답했을 때 ledger에 쌓여
    있었을 레코드 개수. Trait-Evidence 질문 1개당 evidence_ledger에 정확히 레코드
    1개가 쌓인다(Routing/Conflict는 이 카운터에서 이미 제외했다, `_run_persona_session`
    참고) — Routing 질문은 evidence_ledger에 별도로 안 쌓이지 않으므로, 전체 ledger에서
    "Trait-Evidence 레코드"만 순서대로 세어 n개가 될 때까지의 전체 길이를 구한다."""

    trait_evidence_origins = {"PRIMARY_BLUEPRINT", "V2_DIRECT_PROBE"}
    count = 0
    for idx, record in enumerate(run.final_evidence_ledger, start=1):
        if record.evidence_origin.value in trait_evidence_origins:
            count += 1
            if count == n:
                return idx
    return len(run.final_evidence_ledger)


def _rebuild_offered_map(run: SessionRun, upto_turn: int) -> dict[str, list[str]]:
    """`compute_pack_context_trait_summaries`는 opportunity_count 계산에 offered map이
    필요하다 — 이 진단은 "제시된 기회"를 "그 turn에 실제로 target으로 선택된 Trait
    하나"로 근사한다(Pack Direct Probe는 선택지 5개 중 신호 있는 게 1개뿐이라 이
    근사가 실제와 정확히 일치한다 — a/trait-evidence-coverage-shadow에서 이미 확인한
    사실)."""

    offered: dict[str, list[str]] = {}
    for idx, trait_id in enumerate(run.per_turn_target_trait_ids[:upto_turn], start=1):
        if trait_id is not None:
            offered[f"turn_{idx}"] = [trait_id]
    # question_id 키가 실제와 다르지만 compute_pack_context_trait_summaries는 ledger의
    # question_id 집합과 교집합만 본다 — 아래에서 실제 question_id로 다시 맞춘다.
    remapped: dict[str, list[str]] = {}
    trait_evidence_records = [
        r for r in run.final_evidence_ledger[: _ledger_length_after_nth_trait_question(run, upto_turn)]
        if r.evidence_origin.value in {"PRIMARY_BLUEPRINT", "V2_DIRECT_PROBE"}
    ]
    for record, (_, trait_ids) in zip(trait_evidence_records, offered.items()):
        remapped[record.question_id] = trait_ids
    return remapped


def _wasted_slot_count(log: _AltDecisionLog) -> int:
    return sum(1 for was_gap in log.turn_was_gap_at_assignment if not was_gap)


# ============================== 전체 실행 ==============================


def run_and_summarize() -> dict[str, Any]:
    """§ 버그 수정 — Coverage 재계산(`_coverage_results`/`_termination_records`)은
    Fixture Registry가 실제로 `main_module._context_pack_registry`에 꽂혀 있는
    `with patch.object(...)` 블록 **안에서** 끝내야 한다. 이전 버전은 Baseline/Alt
    실행을 전부 마친 뒤(블록을 빠져나온 뒤) 요약을 계산해서, 그 시점엔 이미 패치가
    풀려 실제(비-Fixture) Registry를 참조했다 — Pack Context 승인이 전부 실패한 것처럼
    보여 Coverage가 전부 UNOBSERVED로 무너지는 버그였다(실측으로 발견, § 완료 보고서
    참고). 이제 요약까지 전부 같은 블록 안에서 끝낸다."""

    scenarios = _persona_scenarios()
    fake_llm = _DeterministicFakeLLMClient()

    saved_env = {
        k: os.environ.get(k)
        for k in ("ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", "ENABLE_CONTEXT_PACK_RUNTIME", "ENABLE_CONTEXT_SELECTION_4_PLUS_1")
    }
    baseline_summaries: list[dict[str, Any]] = []
    alt_summaries: dict[str, list[dict[str, Any]]] = {"A": [], "B": [], "C": []}

    try:
        os.environ["ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES"] = "true"
        with tempfile.TemporaryDirectory(prefix="trait_coverage_planner_gap_fixture_") as tmp:
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

                for scenario in scenarios:
                    run = _run_persona_session(
                        scenario, session_id=f"planner_gap_baseline_{scenario.key}", registry=fixture_registry,
                    )
                    baseline_summaries.append(_summarize_baseline(scenario, run, fixture_registry))

                for alt in ("A", "B", "C"):
                    for scenario in scenarios:
                        log = _AltDecisionLog()
                        top_traits = _top_traits_for(scenario, 8) if alt == "C" else None
                        session_id = f"planner_gap_{alt}_{scenario.key}"
                        selector = _make_alt_selector(alt, session_id, top_traits, log, fixture_registry)
                        with patch.object(main_module, "select_pack_adaptive_target", selector):
                            run = _run_persona_session(scenario, session_id=session_id, registry=fixture_registry)
                        alt_summaries[alt].append(_summarize_alt(scenario, run, log, fixture_registry))
    finally:
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    return {"baseline": baseline_summaries, "alternatives": alt_summaries}


def _summarize_baseline(scenario: PersonaScenario, run: SessionRun, registry: ContextPackRegistry) -> dict[str, Any]:
    results = _coverage_results(run, run.final_evidence_ledger, registry)
    ranked = sorted(CORE_TRAIT_IDS, key=lambda t: _affinity_rank(scenario, t))
    terminations = _termination_records(scenario, run, registry)

    stopped_but_not_sufficient = sorted(
        t for t, r in terminations.items()
        if r.stopped_at_turn_index is not None and r.coverage_status_final != "SUFFICIENT"
    )

    return {
        "scenario_key": scenario.key, "scenario_label": scenario.label,
        "final_context_ids": run.final_context_ids,
        "anchor_by_context": dict(sorted(run.anchor_by_context.items())),
        "trait_evidence_question_count": run.trait_evidence_question_count,
        "routing_question_count": run.routing_question_count,
        "backup_used_count": run.backup_used_count,
        "coverage_status_breakdown": coverage_status_breakdown(results),
        "top5_sufficient": _top_n_sufficient(results, ranked, 5),
        "top8_sufficient": _top_n_sufficient(results, ranked, 8),
        "top5_sufficient_fraction": _top_n_sufficient_fraction(results, ranked, 5),
        "top8_sufficient_fraction": _top_n_sufficient_fraction(results, ranked, 8),
        "top5_supported_or_better": _top_n_sufficient(results, ranked, 5, min_status="SUPPORTED"),
        "top8_supported_or_better": _top_n_sufficient(results, ranked, 8, min_status="SUPPORTED"),
        "top5_supported_or_better_fraction": _top_n_sufficient_fraction(results, ranked, 5, min_status="SUPPORTED"),
        "top8_supported_or_better_fraction": _top_n_sufficient_fraction(results, ranked, 8, min_status="SUPPORTED"),
        "wasted_slot_count_baseline_definition": sum(
            1 for t in run.per_turn_target_trait_ids
            if t is not None and terminations[t].stopped_at_turn_index is not None
            and run.per_turn_target_trait_ids.index(t) + 1 > terminations[t].stopped_at_turn_index
        ),
        "trait_termination": {
            t: {
                "stopped_in_context": r.stopped_in_context,
                "stopped_at_turn_index": r.stopped_at_turn_index,
                "retargeted_in_other_context_after_stop": r.retargeted_in_other_context_after_stop,
                "coverage_status_at_stop_moment": r.coverage_status_at_stop_moment,
                "coverage_status_final": r.coverage_status_final,
                "final_primary_count": r.final_primary_count,
                "final_related_count": r.final_related_count,
                "final_weight": r.final_weight,
                "final_context_count": r.final_context_count,
                "final_frame_count": r.final_frame_count,
            }
            for t, r in sorted(terminations.items())
        },
        "stopped_by_planner_but_final_status_not_sufficient": stopped_but_not_sufficient,
    }


def _summarize_alt(scenario: PersonaScenario, run: SessionRun, log: _AltDecisionLog, registry: ContextPackRegistry) -> dict[str, Any]:
    results = _coverage_results(run, run.final_evidence_ledger, registry)
    ranked = sorted(CORE_TRAIT_IDS, key=lambda t: _affinity_rank(scenario, t))
    return {
        "scenario_key": scenario.key,
        "trait_evidence_question_count": run.trait_evidence_question_count,
        "backup_used_count": run.backup_used_count,
        "coverage_status_breakdown": coverage_status_breakdown(results),
        "top5_sufficient": _top_n_sufficient(results, ranked, 5),
        "top8_sufficient": _top_n_sufficient(results, ranked, 8),
        "top5_sufficient_fraction": _top_n_sufficient_fraction(results, ranked, 5),
        "top8_sufficient_fraction": _top_n_sufficient_fraction(results, ranked, 8),
        "wasted_slot_count": _wasted_slot_count(log),
        "total_targeted_turns": len(log.turn_target_trait_ids),
    }


# ============================== 대안 비교·추천 ==============================


def _compare_alternatives(summary: dict[str, Any]) -> dict[str, Any]:
    n = len(summary["baseline"])

    def rate(rows: list[dict[str, Any]], key: str) -> float:
        return sum(1 for r in rows if r[key]) / n

    def avg(rows: list[dict[str, Any]], key: str) -> float:
        return sum(r[key] for r in rows) / n

    baseline_rows = summary["baseline"]
    comparison = {
        "baseline": {
            "top5_sufficient_rate": rate(baseline_rows, "top5_sufficient"),
            "top8_sufficient_rate": rate(baseline_rows, "top8_sufficient"),
            "top5_sufficient_fraction_avg": avg(baseline_rows, "top5_sufficient_fraction"),
            "top8_sufficient_fraction_avg": avg(baseline_rows, "top8_sufficient_fraction"),
            "top5_supported_or_better_fraction_avg": avg(baseline_rows, "top5_supported_or_better_fraction"),
            "top8_supported_or_better_fraction_avg": avg(baseline_rows, "top8_supported_or_better_fraction"),
            "total_trait_evidence_questions": sum(r["trait_evidence_question_count"] for r in baseline_rows),
        },
        "D_supported_headline": {
            "note": "재실행 없음 — Baseline과 완전히 동일한 실행, SUPPORTED 이상을 헤드라인으로 재집계.",
            "top5_fraction_avg": avg(baseline_rows, "top5_supported_or_better_fraction"),
            "top8_fraction_avg": avg(baseline_rows, "top8_supported_or_better_fraction"),
            "total_trait_evidence_questions": sum(r["trait_evidence_question_count"] for r in baseline_rows),
        },
    }
    for alt in ("A", "B", "C"):
        rows = summary["alternatives"][alt]
        comparison[alt] = {
            "top5_sufficient_rate": rate(rows, "top5_sufficient"),
            "top8_sufficient_rate": rate(rows, "top8_sufficient"),
            "top5_sufficient_fraction_avg": avg(rows, "top5_sufficient_fraction"),
            "top8_sufficient_fraction_avg": avg(rows, "top8_sufficient_fraction"),
            "total_trait_evidence_questions": sum(r["trait_evidence_question_count"] for r in rows),
            "total_wasted_slots": sum(r["wasted_slot_count"] for r in rows),
        }
    return comparison


def _recommendation(comparison: dict[str, Any]) -> dict[str, Any]:
    """§ 정직성 원칙 — "결과를 맞추기 위해 기준을 완화하지 않는다"를 추천 문구에도
    적용한다. 판단 원칙이 "상위 5~8개"를 함께 언급하므로 top8 하나만으로 순위를 매기지
    않고 (상위5 비율 + 상위8 비율)/2를 결합 점수로 써서 실측값 그대로 비교한다 — 미리
    정해둔 답을 향해 숫자를 짜맞추지 않는다."""

    order = ["baseline", "A", "B", "C"]
    top5 = {alt: comparison[alt]["top5_sufficient_fraction_avg"] for alt in order}
    top8 = {alt: comparison[alt]["top8_sufficient_fraction_avg"] for alt in order}
    fractions = {alt: (top5[alt] + top8[alt]) / 2 for alt in order}
    best_alt = max(order, key=lambda a: (fractions[a], -comparison[a].get("total_wasted_slots", 0)))
    ranking_text = " → ".join(
        f"{alt}(상위5 {top5[alt]:.3f}/상위8 {top8[alt]:.3f}/평균 {fractions[alt]:.3f})" for alt in order
    )

    wasted = {alt: comparison[alt].get("total_wasted_slots") for alt in order}

    if best_alt == "baseline":
        chosen = "D"
        justification = (
            f"(상위5 비율+상위8 비율)/2 결합 점수 실측값은 {ranking_text} 순이다 — A/B/C "
            "중 어느 것도 Baseline보다 이 결합 점수를 실제로 끌어올리지 못했다(구조적 원인: "
            "후보 Blueprint 풀 자체가 Trait당 Context 다양성을 제공할 만큼 크지 않은 경우, "
            "Planner의 목표 재정의만으로는 Context>=2 조건을 못 채운다 — § 아래 §2 실측 사례 "
            "참고). 목표 재정의(A/B/C)가 실질적 이득을 주지 못하는 상황에서 무리하게 Planner를 "
            "바꾸는 대신, Coverage 기준·Baseline 결과는 그대로 두고 **화면에 SUPPORTED 이상을 "
            "함께 보여주는 D**를 권한다 — 이미 얻은 Evidence(예: weight 2.0 SUPPORTED 상태)를 "
            "'판단 근거 있음'으로 정직하게 보여줄 수 있다(SUFFICIENT라고 과장하지 않는다)."
        )
        caveat = (
            "D는 Coverage 기준 자체를 낮추는 게 아니라 '무엇을 헤드라인으로 보여줄지'만 "
            "바꾼다 — 학생 화면에는 SUFFICIENT/SUPPORTED 상태를 있는 그대로 구분해 보여줘야 "
            "하며, SUPPORTED를 SUFFICIENT처럼 포장해서는 안 된다."
        )
    else:
        chosen = best_alt
        tie_break_note = (
            f" 결합 점수가 {best_alt}와 동률인 대안이 있었으나, 낭비 슬롯 수"
            f"(§0 정의, {best_alt}={wasted[best_alt]})가 더 적어 {best_alt}를 우선했다."
            if any(abs(fractions[a] - fractions[best_alt]) < 1e-9 and a != best_alt for a in order if a != "baseline")
            else ""
        )
        justification = (
            f"(상위5 비율+상위8 비율)/2 결합 점수 실측값은 {ranking_text} 순으로, "
            f"{best_alt}가 가장 높다.{tie_break_note} Coverage 기준(weight>=3.0·Context>=2·"
            "Frame>=2) 자체는 세 대안 모두 전혀 완화하지 않았다 — 대안마다 바뀌는 건 "
            "Planner가 '무엇을 목표로 삼을지'뿐이고, 그 결과 같은 질문 예산(Context당 4~6개, "
            f"Stop Condition 불변) 안에서 {best_alt}가 상위 5~8개 Trait에 더 효과적으로 슬롯을 "
            "배분했다."
        )
        wasted_note = (
            f" 다만 낭비 슬롯 수는 {best_alt}={wasted[best_alt]}로 다른 대안보다 많다(§0 정의 "
            "— top_traits 안에서도 이미 SUFFICIENT인 Trait에 슬롯이 배정된 경우를 낭비로 센다. "
            f"참고: A={wasted['A']}, B={wasted['B']}) — 상위 Trait 안에서의 재확인 비용이 "
            "더 든다는 뜻이지, top_traits 밖으로 슬롯이 샌다는 뜻은 아니다."
            if wasted[best_alt] and wasted[best_alt] == max(wasted[a] for a in ("A", "B", "C"))
            else ""
        )
        caveat = (
            f"{best_alt}도 24개 전체를 SUFFICIENT로 만들지 못한다(애초에 그게 목표가 아니다) "
            "— 상위 8개 밖의 Trait는 이 세션에서 UNOBSERVED/LIMITED에 머무를 수 있고, 이는 "
            f"의도된 결과다(§5 '24개 전체를 SUFFICIENT로 만드는 것을 목표로 삼지 말 것')." + wasted_note
        )

    return {
        "chosen": chosen, "justification": justification, "caveat": caveat,
        "combined_top5_top8_fraction_avg_by_alt": fractions,
        "top5_sufficient_fraction_avg_by_alt": top5,
        "top8_sufficient_fraction_avg_by_alt": top8,
        "total_wasted_slots_by_alt": wasted,
    }


# ============================== 보고서 직렬화 ==============================


def _write_json_report(summary: dict[str, Any], comparison: dict[str, Any], recommendation: dict[str, Any]) -> None:
    payload = {
        "flow": (
            "실제 4+1 세션(관심도 15개 → 선호 4개 → Contrast 1개 → 최종 5개 → Context마다 "
            "Routing 1개·Anchor 1개·Seed 1개·Adaptive Tail 4~6개). ENABLE_CONTEXT_SELECTION_"
            "4_PLUS_1이 네이티브로 배선돼 있어 실제 /assessment/context-select·/assessment/"
            "context-confirm Endpoint를 우회 없이 그대로 호출한다(a/trait-evidence-coverage-"
            "shadow 라운드와 다른 점 — 그때는 main.py가 아직 2/3 하드코딩이라 순수 함수를 "
            "직접 불러야 했다)."
        ),
        "planner_and_coverage_definitions": {
            "planner_gap_condition": "opportunity_count==0 또는 support_count<2 (Context 단위, select_pack_adaptive_target._is_evidence_gap, 수정 안 함)",
            "coverage_sufficient_condition": {
                "min_primary_count": SUFFICIENT_MIN_PRIMARY_COUNT,
                "min_effective_weight": 3.0,
                "min_context_count": SUFFICIENT_MIN_CONTEXT_COUNT,
                "min_frame_count": 2,
                "min_directional_consistency": 0.7,
            },
            "structural_mismatch": (
                "Primary 2개만으로는 weight가 정확히 2.0 — SUFFICIENT의 weight>=3.0을 "
                "못 넘는다. Planner는 support_count>=2에서 그 Context 안 목표를 내려놓으므로, "
                "다른 Context에서 같은 Trait를 다시 목표 삼지 않는 한 weight는 2.0에서 멈춘다."
            ),
        },
        "baseline_personas": summary["baseline"],
        "alternatives": {
            "A": summary["alternatives"]["A"],
            "B": summary["alternatives"]["B"],
            "C": summary["alternatives"]["C"],
        },
        "comparison": comparison,
        "recommendation": recommendation,
        "note": (
            "생성 시각·메모리 값 없음 — byte-identical 재실행. data/reviews/는 이 스크립트가 "
            "읽지도 쓰지도 않는다(12개 Pack·공용 Adaptive Probe 승인은 전부 tempfile Fixture)."
        ),
    }
    JSON_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {JSON_OUTPUT_PATH}")


def _write_markdown_report(summary: dict[str, Any], comparison: dict[str, Any], recommendation: dict[str, Any]) -> None:
    lines: list[str] = [
        "# Trait Evidence Coverage — Adaptive Target Planner Gap 진단",
        "",
        "브랜치 `a/trait-evidence-coverage-planner-gap`. 별도 Worktree·별도 브랜치, 읽기 중심 "
        "Shadow 진단만 수행했다 — Runtime·Stop Condition·질문·Mapping·Review JSON은 전혀 "
        "바꾸지 않았다.",
        "",
        "## 0. 구조적 불일치 요약",
        "",
        "- 실제 Adaptive Target Planner(`select_pack_adaptive_target`)는 한 Context 안에서 "
        "`support_count>=2`가 되면 그 Trait를 더 이상 Gap으로 보지 않는다.",
        "- Coverage SUFFICIENT는 `weight>=3.0`·`Context>=2`·`Frame>=2`를 요구한다.",
        "- Primary 2개(같은 Context) = weight 2.0 → 3.0 문턱 미달. 다른 Context에서 다시 "
        "목표가 되지 않는 한 그 Trait는 SUPPORTED에 머문다.",
        "",
        "## 1. Baseline(실제 Planner) — Persona별 Trait 종료 순간",
        "",
        "| Persona | Trait 질문 | Backup | UNOBS·LIM·SUP·SUFF·CONF | 상위5 SUFF | 상위8 SUFF | Planner가 멈췄지만 최종 SUFFICIENT 아닌 Trait 수 |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in summary["baseline"]:
        b = row["coverage_status_breakdown"]
        lines.append(
            f"| {row['scenario_label']} | {row['trait_evidence_question_count']} | "
            f"{row['backup_used_count']} | {b['UNOBSERVED']}·{b['LIMITED']}·{b['SUPPORTED']}·"
            f"{b['SUFFICIENT']}·{b['CONFLICTED']} | {'✅' if row['top5_sufficient'] else '❌'} | "
            f"{'✅' if row['top8_sufficient'] else '❌'} | "
            f"{len(row['stopped_by_planner_but_final_status_not_sufficient'])} |"
        )

    lines += ["", "## 2. Persona별 상세 — Planner가 멈췄지만 SUFFICIENT에 못 미친 Trait", ""]
    for row in summary["baseline"]:
        lines.append(f"### {row['scenario_label']} (Context: {row['final_context_ids']})")
        lines.append("")
        stopped = row["stopped_by_planner_but_final_status_not_sufficient"]
        if not stopped:
            lines.append("(없음 — 이 Persona는 Planner가 멈춘 모든 Trait가 최종 SUFFICIENT에 도달했다)")
        else:
            lines.append("| Trait | 멈춘 Context | 멈춘 시점(질문 순번) | 다른 Context서 재목표됨 | 그 순간 Coverage | 최종 Coverage | 최종 weight | 최종 Context 수 | 최종 Frame 수 |")
            lines.append("|---|---|---|---|---|---|---|---|---|")
            for trait_id in stopped:
                t = row["trait_termination"][trait_id]
                lines.append(
                    f"| {trait_id} | {t['stopped_in_context']} | {t['stopped_at_turn_index']} | "
                    f"{'예' if t['retargeted_in_other_context_after_stop'] else '아니오'} | "
                    f"{t['coverage_status_at_stop_moment']} | {t['coverage_status_final']} | "
                    f"{t['final_weight']} | {t['final_context_count']} | {t['final_frame_count']} |"
                )
        lines.append("")

    lines += [
        "## 3. 대안 A/B/C/D 비교",
        "",
        "상위5·8 SUFFICIENT '비율'은 상위 N개 중 실제로 SUFFICIENT인 개수의 비율을 Persona "
        "평균한 값이다(0.0~1.0) — 전부-아니면-말고(All-or-nothing) 지표는 질문 예산이 작아 "
        "네 대안 모두 0.00이 나와 차이를 구분할 수 없었다(§ 아래 4개 Persona 실측, All-or-"
        "nothing 값도 참고용으로 함께 남긴다).",
        "",
        "| 대안 | 상위5 비율 | 상위8 비율 | 상위5 All-or-nothing | 상위8 All-or-nothing | 총 Trait 질문 수 | 낭비 슬롯(§0 정의) |",
        "|---|---|---|---|---|---|---|",
    ]
    lines.append(
        f"| Baseline(오늘 실제 Planner) | {comparison['baseline']['top5_sufficient_fraction_avg']:.3f} | "
        f"{comparison['baseline']['top8_sufficient_fraction_avg']:.3f} | "
        f"{comparison['baseline']['top5_sufficient_rate']:.2f} | {comparison['baseline']['top8_sufficient_rate']:.2f} | "
        f"{comparison['baseline']['total_trait_evidence_questions']} | (해당 없음) |"
    )
    lines.append(
        f"| D(SUPPORTED 중심 재표현, 재실행 없음) | {comparison['D_supported_headline']['top5_fraction_avg']:.3f} | "
        f"{comparison['D_supported_headline']['top8_fraction_avg']:.3f} | (해당 없음, SUPPORTED 기준) | (해당 없음, SUPPORTED 기준) | "
        f"{comparison['D_supported_headline']['total_trait_evidence_questions']} | (해당 없음, Baseline과 동일 실행) |"
    )
    for alt in ("A", "B", "C"):
        c = comparison[alt]
        lines.append(
            f"| {alt} | {c['top5_sufficient_fraction_avg']:.3f} | {c['top8_sufficient_fraction_avg']:.3f} | "
            f"{c['top5_sufficient_rate']:.2f} | {c['top8_sufficient_rate']:.2f} | "
            f"{c['total_trait_evidence_questions']} | {c['total_wasted_slots']} |"
        )
    lines.append("")
    lines.append(
        "질문 수가 대안마다 거의 같은 이유: `decide_stop_or_continue()`(Context당 최소 4·"
        "최대 6, 수정 안 함)가 모든 대안에서 그대로 적용된다 — 대안은 그 고정 슬롯을 "
        "'어떤 Trait에 쓸지'만 바꾼다."
    )

    lines += ["", "## 4. 추천안", "", f"**선택: {recommendation['chosen']}**", "", recommendation["justification"], "", recommendation["caveat"]]

    MD_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MD_OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {MD_OUTPUT_PATH}")


def main() -> None:
    summary = run_and_summarize()
    comparison = _compare_alternatives(summary)
    recommendation = _recommendation(comparison)
    _write_json_report(summary, comparison, recommendation)
    _write_markdown_report(summary, comparison, recommendation)


if __name__ == "__main__":
    main()
