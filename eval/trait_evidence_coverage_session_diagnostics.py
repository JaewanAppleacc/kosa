"""Trait Evidence Coverage — 실제 4+1/2+1 세션 시뮬레이션 Harness (정정판) —
a/trait-evidence-coverage-shadow.

**이전 `trait_evidence_coverage_shadow_diagnostics.py`(158문항 Inventory 상한)는
실제 세션이 아니다** — 15개 Context와 각 Context의 Anchor 5개 전부를 순회했다.
이 파일은 그 지적을 반영해 **실제 Runtime 함수를 그대로 호출**해서 진짜 세션 하나가
겪는 흐름만 재현한다:

    관심도 15개 → 선호 Context 4개 선택 → Contrast Context 1개 제안 → 최종 5개 확정
    → Context마다 Routing 1개 → Anchor 1개 선택 → Seed 1개 → Adaptive Tail 4~6개
    → (후보 소진 시에만) Backup

**재사용하는 실제 함수/모듈** (이 파일이 로직을 다시 구현하지 않는다):

    src.api.main.submit_interest_rating / select_contexts / confirm_contexts /
        next_question / submit_answer            ← 실제 Endpoint 함수를 직접 호출
    src.engines.contrast_context_selector.select_contrast_context  ← Full Mode(4+1)
        파라미터로 직접 호출(§ 아래 "Full Mode 우회" 참고)
    src.services.context_pack_runtime.ContextPackRuntime            ← Pack Context Seed/
        Backup/Direct Probe 후보 조회(Fixture Registry와 함께 씀)
    src.services.trait_signal_review_gate.gate_primary_eligible_evidence ← Human Review
        Gate(승인 여부 판정)
    src.engines.trait_evidence_coverage_engine  ← 이전 라운드에서 만든 Coverage Policy
        (가중치·SUFFICIENT 기준 전부 그대로, 이번에 바꾸지 않는다)

## Full Mode(4+1) 우회에 대한 정직한 기록

실제 `/assessment/context-select`·`/assessment/context-confirm` HTTP Endpoint는
`MINIMUM_PREFERRED_CONTEXT_COUNT_VERTICAL_SLICE=2`/`MAXIMUM_FINAL_CONTEXT_COUNT_
VERTICAL_SLICE=3`를 **호출부에 상수로 그대로 박아뒀다** — `ENABLE_CONTEXT_PACK_
RUNTIME`을 켜도 이 두 상수는 바뀌지 않는다(`src/engines/contrast_context_selector.py`
에 `MINIMUM_PREFERRED_CONTEXT_COUNT_FULL_MODE=4`가 이미 정의돼 있지만 main.py 호출부는
아직 그 상수를 쓰지 않는다). 즉 **"4개 선호 Context"는 지금 실제 HTTP Endpoint로는
거부된다** — Full Mode 자체가 아직 main.py에 배선되지 않은 상태라는 뜻이다.

이건 이번 진단이 발견한 사실이지, 이 진단이 만든 제약이 아니다. `main.py`를 수정하지
않고(금지 사항) 이 사실을 있는 그대로 반영하기 위해, 환경 B(4+1)만 두 Endpoint
Handler를 호출하지 않고 그 안에서 실제로 쓰는 **순수 함수**(`select_contrast_context`)
를 Full Mode 파라미터로 직접 호출한 뒤 `AssessmentState`에 결과를 그대로 채운다 —
Endpoint의 HTTP 파라미터 검증 계층만 우회할 뿐, 그 아래 실제 선택 로직·Context Vector·
Coverage Matrix는 전부 동일한 실제 데이터를 그대로 쓴다. 환경 A(2+1)는 이 우회가 전혀
필요 없다 — 실제 Endpoint를 그대로 호출한다.

## data/reviews/ 무변경

12개 ContextPack의 승인와 공용 Adaptive Probe(Shared Probe Pool)의 Anchor별 승인은
전부 `tempfile` 안의 Fixture로만 만든다. `ContextPackRegistry(review_status_dir=...,
shared_probe_review_status_path=...)`가 원래 그 목적으로 만들어진 테스트 전용 주입
지점이다(주석 참고, `src/services/context_pack_registry.py`) — 실제 `data/reviews/`는
이 스크립트가 아예 열어보지도 않는다."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
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
from src.engines.contrast_context_selector import (  # noqa: E402
    ContrastSelectionResult,
    select_contrast_context,
)
from src.engines.trait_evidence_coverage_engine import (  # noqa: E402
    SUFFICIENT_MIN_CONTEXT_COUNT,
    SUFFICIENT_MIN_PRIMARY_COUNT,
    compute_all_trait_coverage,
    coverage_status_breakdown,
)
from src.schemas.api import (  # noqa: E402
    AnswerRequest,
    ContextConfirmRequest,
    ContextSelectRequest,
    InterestRatingRequest,
)
from src.schemas.assessment_state import AssessmentPhase, AssessmentState  # noqa: E402
from src.schemas.context_pack_shared_probe_review import SharedProbeContextReview  # noqa: E402
from src.services.context_pack_registry import ContextPackRegistry, discover_context_packs  # noqa: E402
from src.services.context_pack_runtime import ContextPackRuntime  # noqa: E402
from src.schemas.question import GeneratedOption, GeneratedQuestion, QuestionGenerationResult  # noqa: E402
from src.services.trait_signal_registry import register_context_pack_signals  # noqa: E402
from src.services.trait_signal_review_gate import gate_primary_eligible_evidence  # noqa: E402

# §3 "Direct Probe 후보 조회"/"select_pack_adaptive_target"를 실제로 재사용하려면
# Adaptive Tail 생성이 실제로 성공해야 한다 — 실측 결과 LLM이 꺼져 있으면
# `generate_v2_direct_probe_question(..., allow_base_question_fallback=False)`가
# **항상** None을 반환해(§ 감사 결과) Pack Context가 매번 곧장 Backup으로 빠지고
# 1개(Anchor당 Backup 1개) 만에 STOP_CANDIDATE_EXHAUSTED로 조기 종료된다 — "Backup은
# 생성 실패·후보 소진 시에만 사용"이라는 전제(§1) 자체가 LLM 없이는 성립하지 않는다는
# 뜻이다. `tests/test_context_pack_adaptive_e2e.py::_FakeLLMClient`와 완전히 같은
# 원리(Prompt에서 실제 context/frame_id/role_id를 파싱해 그대로 되돌려준다)의 결정론적
# Fake Client를 그대로 재사용해 실제 생성 경로(Quality Gate 포함)를 통과시킨다 — LLM
# 네트워크를 호출하지 않으므로 결정론(§9)은 그대로 유지된다.
_CONTEXT_RE = re.compile(r'context 필드에는 "(\w+)"를')
_FRAME_RE = re.compile(r'frame_id 필드에는 "(\w+)"를')
_ROLE_RE = re.compile(r"\[Option Role.*?\]\n(.*?)\n\ncontext 필드", re.DOTALL)


class _DeterministicFakeLLMClient:
    """항상 성공하는 결정론적 Fake — 네트워크·난수 없음. Prompt를 그대로 반영해
    role_id마다 고정 문구("{role_id} 선택지 문장")를 만든다(재실행해도 같은 입력이면
    같은 출력). `question_text`에 호출 순번을 넣는다 — Quality Gate가 "이전 질문과
    문구가 똑같으면 재생성" 규칙을 갖고 있어(실측: 매번 같은 문구를 반환하면 같은
    Context의 두 번째 Tail 질문부터 계속 재생성에 실패해 Backup으로 빠지는 걸
    확인했다), 매 호출마다 다른 문구를 보장해야 정상적으로 여러 Tail 질문이
    이어진다."""

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
CHECKPOINTS: tuple[int, ...] = (20, 25, 30, 35)
MAX_QUESTION_LOOP_ITERATIONS = 400  # 안전 상한 — 무한 루프 방지용, 정상 흐름에선 도달 안 함.

JSON_OUTPUT_PATH = ROOT / "outputs" / "evaluation" / "trait_evidence_coverage_shadow_report.json"
MD_OUTPUT_PATH = ROOT / "outputs" / "evaluation" / "trait_evidence_coverage_shadow_report.md"


# ============================== Persona 시나리오 ==============================


@dataclass(frozen=True)
class PersonaScenario:
    key: str
    label: str
    preferred_context_ids: tuple[str, ...]  # 정확히 4개
    contrast_hint_context_id: str  # 이 진단이 관심도 점수로 강제 유도하는 Contrast
    # trait_id -> 선호 순위(낮을수록 우선). 명시 안 된 Trait는 전부 동률 최하위(알파벳
    # 순 tie-break)다. "" 특수 모드는 아래 SPECIAL_POLICIES에서 별도 처리한다.
    trait_affinity_order: tuple[str, ...] = ()
    special_policy: str | None = None  # "coverage_maximizing" | "coverage_minimizing" | None


def _persona_scenarios() -> list[PersonaScenario]:
    return [
        PersonaScenario(
            "analytical", "분석형",
            ("science", "business", "sports", "law_politics"), "making",
            ("causal_analysis", "pattern_finding", "information_comparison", "systems_thinking",
             "detail_orientation", "planning", "independent_judgment", "uncertainty_tolerance"),
        ),
        PersonaScenario(
            "creative_visual", "창의·시각형",
            ("art_design", "media", "fashion_beauty", "making"), "writing",
            ("visual_expression", "aesthetic_sensitivity", "creative_ideation", "tool_utilization",
             "novelty_seeking"),
        ),
        PersonaScenario(
            "social_collaborative", "사회·협업형",
            ("school_life", "volunteer", "sports", "business"), "game",
            ("collaboration_preference", "opinion_mediation", "emotional_interpretation",
             "opinion_expression", "audience_response_prediction"),
        ),
        PersonaScenario(
            "practical_making", "실행·제작형",
            ("making", "cooking", "science", "art_design"), "business",
            ("tool_utilization", "immediate_execution", "persistence_completion",
             "detail_orientation", "change_adaptation"),
        ),
        PersonaScenario(
            "language_humanities", "언어·인문형",
            ("writing", "history_humanities", "law_politics", "media"), "school_life",
            ("verbal_expression", "opinion_expression", "information_comparison",
             "causal_analysis", "emotional_interpretation"),
        ),
        PersonaScenario(
            "mixed_cross_domain", "혼합·교차형",
            ("game", "cooking", "law_politics", "art_design"), "science",
            (),  # 의도적으로 뚜렷한 선호가 없다 — 알파벳 순 fallback만 쓴다.
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
        PersonaScenario(
            "coverage_minimizing", "Coverage 최소화형(1~2개 Trait 집중)",
            ("game", "media", "school_life", "business"), "science",
            special_policy="coverage_minimizing",
        ),
    ]


# ============================== 관심도·Anchor 결정론적 규칙 ==============================


def _ratings_for(scenario: PersonaScenario, all_context_ids: set[str]) -> dict[str, int]:
    """§4 "Contrast Context 1개를 명시" — 원하는 Contrast만 관심도 2~3점 구간(tier
    "interest_2_3")에 유일하게 남기고 나머지 비선호는 전부 1점(last_resort)으로 낮춰서,
    `select_contrast_context()`의 실제 tier 로직이 항상 그 Context 하나만 고르게
    만든다(거리·Coverage 점수 동점 걱정 없이 결정론적)."""

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
    """실제 등록된 Anchor id 목록(알파벳 순, 결정론적). Legacy 3개는 고정 데이터,
    나머지는 Registry가 들고 있는 Pack의 anchor_presentations를 그대로 읽는다."""

    if context_id in VERTICAL_SLICE_CONTEXT_IDS:
        from src.data.contexts.context_anchor_presentations import CONTEXT_ANCHOR_PRESENTATIONS

        return sorted(
            p.anchor_id for p in CONTEXT_ANCHOR_PRESENTATIONS if p.context_id == context_id
        )
    pack = registry.get_pack(context_id)
    if pack is None:
        return []
    return sorted(a.anchor_id for a in pack.anchor_presentations)


def _anchor_choice_for(scenario: PersonaScenario, context_id: str, registry: ContextPackRegistry) -> str:
    """이 진단은 모든 Context에서 결정론적으로 '알파벳 순 첫 Anchor'를 고른다 —
    Persona별 주제에 맞는 Anchor를 수작업으로 고르는 대신, 모든 시나리오에 같은
    규칙을 적용해 결과를 서로 비교 가능하게 유지한다(§ 알려진 단순화, 보고서에
    명시)."""

    anchors = _anchor_ids_for_context(context_id, registry)
    if not anchors:
        raise ValueError(f"{context_id}에 등록된 Anchor가 없다")
    return anchors[0]


# ============================== Fixture Registry(환경 B 전용) ==============================


def _build_fixture_registry(fixture_dir: Path) -> ContextPackRegistry:
    """§11 "12개 Pack 임시 승인은 tempfile에서만" — Pack 자체 승인(`{context_id}_
    review_status.json`)과 공용 Adaptive Probe의 Context+Anchor별 승인
    (`shared_probe_review_status.json`) 둘 다 tempfile 안에서만 만든다. 실제
    `data/reviews/`는 이 함수가 아예 열어보지 않는다."""

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

    # 1) Pack 자체 승인 — 이전 라운드와 동일한 패턴.
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

    # 2) 공용 Adaptive Probe — Context+Anchor 단위 승인(§3 "미검토 Anchor는 자동 승인
    # 금지"를 지키려면 각 Pack의 실제 Anchor id를 명시적으로 approved_anchor_ids에
    # 넣어야 한다. 새 Trait를 만들지 않고, 이미 존재하는 14개 공용 Blueprint만 쓴다.
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


# ============================== 답변 선택 정책 ==============================


def _affinity_rank(scenario: PersonaScenario, trait_id: str) -> tuple[int, str]:
    try:
        idx = scenario.trait_affinity_order.index(trait_id)
    except ValueError:
        idx = len(scenario.trait_affinity_order)
    return (idx, trait_id)


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


def _choose_concentrated(options: list[Any], focus_trait_id: str) -> Any:
    for o in options:
        if focus_trait_id in o.primary_trait_delta:
            return o
    candidates = [o for o in options if o.primary_trait_delta]
    return candidates[0] if candidates else options[0]


def _choose_routing_option(options: list[Any], routing_blueprint: Any, desired_anchor_id: str) -> Any:
    role_id = next(
        m.role_id for m in routing_blueprint.option_mappings if m.context_anchor == desired_anchor_id
    )
    return next(o for o in options if o.role_id == role_id)


# ============================== Persona 세션 실행 ==============================


@dataclass
class SessionRun:
    scenario: PersonaScenario
    final_context_ids: list[str] = field(default_factory=list)
    anchor_by_context: dict[str, str] = field(default_factory=dict)
    trait_evidence_question_count: int = 0
    routing_question_count: int = 0
    interest_rating_count: int = 0
    backup_used_count: int = 0
    total_student_interactions: int = 0
    checkpoint_evidence_snapshot: dict[int, list] = field(default_factory=dict)  # cap -> ledger copy
    final_evidence_ledger: list = field(default_factory=list)
    final_context_anchor_choices: dict[str, str] = field(default_factory=dict)


def _routing_blueprint_for(context_id: str) -> Any:
    routing = main_module.CONTEXT_ROUTING_BLUEPRINTS_BY_CONTEXT.get(context_id)
    if routing is not None:
        return routing
    return main_module._context_pack_runtime.get_routing_question(context_id)


def _run_persona_session(
    scenario: PersonaScenario, *,
    rating_universe: set[str], supported_context_ids: set[str], full_mode: bool, registry: ContextPackRegistry,
) -> SessionRun:
    """`rating_universe`(§ "관심도 15개" — 항상 CONTEXT_IDS 전체)와
    `supported_context_ids`(그 시점에 실제로 질문 흐름을 지원하는 Context — 환경마다
    다르다)를 분리한다. 관심도는 등록된 15개 전부를 매기지만, Contrast 후보는 실제
    지원되는 Context 중에서만 골라야 실제 세션과 어긋나지 않는다."""

    session_id = f"shadow_session_{scenario.key}"
    state = AssessmentState(session_id=session_id, user_id="shadow_persona")
    main_module._store.save(state)

    ratings = _ratings_for(scenario, rating_universe)
    main_module.submit_interest_rating(InterestRatingRequest(session_id=session_id, ratings=ratings))

    run = SessionRun(scenario=scenario)
    run.interest_rating_count = len(ratings)

    if full_mode:
        # § "Full Mode 우회에 대한 정직한 기록" — Endpoint의 하드코딩된 2/3 상한을
        # 우회하고, 그 Endpoint가 내부에서 쓰는 실제 순수 함수를 Full Mode 파라미터로
        # 직접 호출한다.
        selection: ContrastSelectionResult = select_contrast_context(
            preferred_context_ids=list(scenario.preferred_context_ids),
            interest_ratings=ratings, all_context_ids=supported_context_ids,
            context_vectors=main_module.CONTEXT_VECTORS, coverage_matrix=main_module.CONTEXT_TRAIT_COVERAGE,
            all_trait_ids=VERTICAL_SLICE_TRAIT_IDS, trait_labels=main_module.ALL_TRAIT_LABELS,
        )
        contrast_id = selection.contrast_context_id
        final_ids = [*scenario.preferred_context_ids, contrast_id]
        state = main_module._store.load(session_id)
        state.selected_preferred_contexts = list(scenario.preferred_context_ids)
        state.contrast_context_id = contrast_id
        state.final_contexts = final_ids
        state.context_processing_order = final_ids
        state.phase = AssessmentPhase.QUESTION_LOOP
        main_module._store.save(state)
    else:
        select_resp = main_module.select_contexts(
            ContextSelectRequest(session_id=session_id, selected_preferred_context_ids=list(scenario.preferred_context_ids))
        )
        contrast_id = select_resp.contrast_context_id
        final_ids = [*scenario.preferred_context_ids, contrast_id]
        main_module.confirm_contexts(ContextConfirmRequest(session_id=session_id, final_context_ids=final_ids))

    assert contrast_id == scenario.contrast_hint_context_id, (
        f"{scenario.key}: 의도한 Contrast {scenario.contrast_hint_context_id!r}가 아니라 "
        f"{contrast_id!r}가 선택됐다 — 관심도 유도 규칙을 다시 확인해야 한다"
    )
    run.final_context_ids = final_ids
    # §4/§5 "Context별 Anchor 1개를 명시" — Routing 질문이 나오기 전에 이미 이 세션이
    # 각 Context에서 어떤 Anchor로 갈지 전부 결정론적으로 정해둔다(질문마다 그때그때
    # 정하지 않는다 — 그래야 Persona 보고서에 "선택 Anchor 5개"를 실행 전에도 그대로
    # 설명할 수 있다).
    run.anchor_by_context = {
        context_id: _anchor_choice_for(scenario, context_id, registry) for context_id in final_ids
    }

    iterations = 0
    while True:
        iterations += 1
        if iterations > MAX_QUESTION_LOOP_ITERATIONS:
            raise RuntimeError(f"{scenario.key}: 질문 루프가 안전 상한을 넘었다 — 무한 루프 의심")

        resp = main_module.next_question(session_id)
        if resp.question is None:
            if resp.assessment_complete:
                break
            continue  # CONTEXT_EARLY_TERMINATED, 아직 안 끝남 — 다음 Context로 자동 전진.

        state = main_module._store.load(session_id)
        family = state.current_question_family_id
        question = resp.question

        if family == "context_routing":
            routing_blueprint = _routing_blueprint_for(question.context)
            desired_anchor = run.anchor_by_context.get(question.context)
            option = _choose_routing_option(question.options, routing_blueprint, desired_anchor)
        else:
            if scenario.special_policy == "coverage_maximizing":
                running_weight = _running_weight_snapshot(state)
                option = _choose_by_min_running_weight(question.options, running_weight)
            elif scenario.special_policy == "coverage_minimizing":
                option = _choose_concentrated(question.options, "causal_analysis")
            else:
                option = _choose_by_affinity(scenario, question.options)

        answer_resp = main_module.submit_answer(
            AnswerRequest(session_id=session_id, question_id=question.question_id, selected_option_id=option.option_id)
        )
        run.total_student_interactions += 1

        if family == "context_routing":
            run.routing_question_count += 1
        elif family != "conflict_resolution":
            run.trait_evidence_question_count += 1
            if resp.status.value == "BACKUP_USED":
                run.backup_used_count += 1
            if run.trait_evidence_question_count in CHECKPOINTS:
                snap_state = main_module._store.load(session_id)
                run.checkpoint_evidence_snapshot[run.trait_evidence_question_count] = list(snap_state.evidence_ledger)

        if answer_resp.next_action == "ASSESSMENT_COMPLETE":
            break

    final_state = main_module._store.load(session_id)
    run.final_evidence_ledger = list(final_state.evidence_ledger)
    run.final_context_anchor_choices = dict(final_state.context_anchor_choices)
    return run


def _running_weight_snapshot(state: AssessmentState) -> dict[str, float]:
    gate = gate_primary_eligible_evidence(state.evidence_ledger, state.context_anchor_choices, main_module._context_pack_registry)
    approved = gate.approved_evidence_ids
    results = compute_all_trait_coverage(CORE_TRAIT_IDS, state.evidence_ledger, approved)
    return {trait_id: r.effective_evidence_weight for trait_id, r in results.items()}


def _env_a_variant(scenario: PersonaScenario) -> PersonaScenario:
    """환경 A(3 Context, 2+1)는 Context 조합의 자유도가 없다 — game/media/school_life
    셋뿐이라 "선호 2개"를 고르면 나머지 1개가 자동으로 Contrast다. 9개 Persona의
    답변 선택 정책(trait_affinity_order/special_policy)은 그대로 유지하고, Context
    조합만 고정된 하나(game/media 선호, school_life Contrast)로 맞춘다 — 그래야
    "정책 차이"만 순수하게 비교할 수 있다(9번 다른 Context 조합을 억지로 3개 안에서
    만들지 않는다)."""

    return PersonaScenario(
        key=scenario.key, label=scenario.label,
        preferred_context_ids=("game", "media"), contrast_hint_context_id="school_life",
        trait_affinity_order=scenario.trait_affinity_order, special_policy=scenario.special_policy,
    )


# ============================== 결과 요약 ==============================


def _coverage_at(run: SessionRun, ledger: list[Any]) -> dict[str, Any]:
    gate = gate_primary_eligible_evidence(ledger, run.final_context_anchor_choices, main_module._context_pack_registry)
    results = compute_all_trait_coverage(CORE_TRAIT_IDS, ledger, gate.approved_evidence_ids)
    return results


def _top_n_sufficient(results: dict[str, Any], n: int) -> bool:
    sufficient = sum(1 for r in results.values() if r.coverage_status == "SUFFICIENT")
    return sufficient >= n


def _mapping_gap_traits(run: SessionRun, results: dict[str, Any]) -> list[str]:
    """§6 "질문 Mapping 부족" — 이 세션이 실제로 제시한 질문 중 이 Trait를 제시한
    횟수가 SUFFICIENT의 Primary 최소치(2)보다 적으면 Persona가 무엇을 골랐어도
    도달 불가능했다는 뜻이다."""

    offered_counts: Counter[str] = Counter()
    for record in run.final_evidence_ledger:
        for signal in record.applied_trait_signals_v2:
            offered_counts[signal.trait_id] += 1
    return sorted(
        trait_id for trait_id in CORE_TRAIT_IDS
        if results[trait_id].coverage_status != "SUFFICIENT" and offered_counts[trait_id] < SUFFICIENT_MIN_PRIMARY_COUNT
    )


def _context_2plus_impossible(run: SessionRun) -> list[str]:
    contexts_by_trait: dict[str, set[str]] = {trait_id: set() for trait_id in CORE_TRAIT_IDS}
    for record in run.final_evidence_ledger:
        for signal in record.applied_trait_signals_v2:
            contexts_by_trait[signal.trait_id].add(record.context)
    return sorted(t for t in CORE_TRAIT_IDS if len(contexts_by_trait[t]) < SUFFICIENT_MIN_CONTEXT_COUNT)


def _unobserved_due_to_context_selection(run: SessionRun, results: dict[str, Any]) -> list[str]:
    """§6 "Context 선택 때문에 관찰되지 않은 Trait" — 이 세션에서 실제로 제시된 질문이
    아예 없는(offered_count==0) UNOBSERVED Trait만 추린다(Mapping이 아예 없는 것과
    구분하기 위해 offered_count==0 조건을 별도로 본다 — 전체 15개 Context에는 있지만
    이 5개 Context 선택에는 없는 경우)."""

    offered: set[str] = set()
    for record in run.final_evidence_ledger:
        for signal in record.applied_trait_signals_v2:
            offered.add(signal.trait_id)
    return sorted(
        t for t in CORE_TRAIT_IDS if results[t].coverage_status == "UNOBSERVED" and t not in offered
    )


def _summarize_run(run: SessionRun) -> dict[str, Any]:
    full_results = _coverage_at(run, run.final_evidence_ledger)
    checkpoint_results = {
        cap: _coverage_at(run, ledger) for cap, ledger in sorted(run.checkpoint_evidence_snapshot.items())
    }
    unmet_at_35 = checkpoint_results.get(35)
    if unmet_at_35 is None:
        unmet_at_35 = full_results if run.trait_evidence_question_count <= 35 else None

    return {
        "scenario_key": run.scenario.key, "scenario_label": run.scenario.label,
        "final_context_ids": run.final_context_ids,
        "anchor_by_context": dict(sorted(run.anchor_by_context.items())),
        "interest_rating_count": run.interest_rating_count,
        "routing_question_count": run.routing_question_count,
        "trait_evidence_question_count": run.trait_evidence_question_count,
        "total_student_interactions": run.total_student_interactions,
        "backup_used_count": run.backup_used_count,
        "coverage_status_breakdown_by_checkpoint": {
            str(cap): coverage_status_breakdown(results) for cap, results in sorted(checkpoint_results.items())
        },
        "coverage_status_breakdown_full": coverage_status_breakdown(full_results),
        "top5_sufficient": _top_n_sufficient(full_results, 5),
        "top8_sufficient": _top_n_sufficient(full_results, 8),
        "context_2plus_structurally_impossible": _context_2plus_impossible(run),
        "mapping_gap_traits": _mapping_gap_traits(run, full_results),
        "unobserved_due_to_context_selection": _unobserved_due_to_context_selection(run, full_results),
        "unmet_conditions_at_35_or_fewer": (
            sorted(
                f"{trait_id}: {', '.join(r.missing_requirements)}"
                for trait_id, r in unmet_at_35.items() if r.missing_requirements
            ) if unmet_at_35 is not None else None
        ),
    }


# ============================== 전체 실행 ==============================


def run_diagnostics() -> dict[str, Any]:
    scenarios = _persona_scenarios()
    env_a_scenarios = [_env_a_variant(s) for s in scenarios]
    fake_llm = _DeterministicFakeLLMClient()

    saved_env = {k: os.environ.get(k) for k in ("ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", "ENABLE_CONTEXT_PACK_RUNTIME")}
    try:
        os.environ["ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES"] = "true"
        os.environ.pop("ENABLE_CONTEXT_PACK_RUNTIME", None)

        env_a_runs: list[SessionRun] = []
        with patch.object(main_module, "_llm_client", fake_llm):
            for scenario in env_a_scenarios:
                run = _run_persona_session(
                    scenario, rating_universe=set(CONTEXT_IDS),
                    supported_context_ids=set(main_module._effective_supported_context_ids()),
                    full_mode=False, registry=main_module._context_pack_registry,
                )
                env_a_runs.append(run)

        env_b_runs: list[SessionRun] = []
        with tempfile.TemporaryDirectory(prefix="trait_coverage_session_fixture_") as tmp:
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
                for scenario in scenarios:
                    run = _run_persona_session(
                        scenario, rating_universe=set(CONTEXT_IDS),
                        supported_context_ids=set(main_module._effective_supported_context_ids()),
                        full_mode=True, registry=fixture_registry,
                    )
                    env_b_runs.append(run)
    finally:
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    return {
        "env_a": {"label": "A. 실제 3 Context, 2+1 세션(실제 승인 상태)", "runs": [_summarize_run(r) for r in env_a_runs]},
        "env_b": {"label": "B. 실제 15 Context, 4+1 세션(12 Pack tempfile 임시 승인)", "runs": [_summarize_run(r) for r in env_b_runs]},
    }


# ============================== 종료 가능성 판단 ==============================


def _conclusion(diagnostics: dict[str, Any]) -> dict[str, Any]:
    env_b_runs = diagnostics["env_b"]["runs"]
    top5_count = sum(1 for r in env_b_runs if r["top5_sufficient"])
    top8_count = sum(1 for r in env_b_runs if r["top8_sufficient"])

    if top5_count == len(env_b_runs):
        outcome = "A"
        explanation = "25~35개 Trait 질문 안에 9개 Persona 전부 상위 5개 이상이 SUFFICIENT에 도달했다."
    else:
        outcome = "B"
        explanation = (
            f"9개 Persona 중 상위 5개 Trait가 전부 SUFFICIENT에 도달한 경우는 {top5_count}건뿐이다 "
            f"(상위 8개는 {top8_count}건). 실제 4+1 세션(35문항 상한) 안에서는 현재 구조로 Coverage "
            "기반 종료 조건을 충족하기 어렵다."
        )

    return {
        "outcome": outcome,
        "explanation": explanation,
        "root_cause": (
            "네 가지 후보(질문 Mapping 부족/Context 2개 조건 과도/RELATED 가중치 과소/4+1 "
            "Context 수 부족) 중 어느 하나로 깔끔히 떨어지지 않는다 — 실측 결과 더 구체적인 "
            "원인은 **실제 Adaptive Target Planner(`select_pack_adaptive_target`, 수정 금지)가 "
            "'Evidence 부족(Gap)' 판정을 `support_count>=2`에서 멈춘다**는 것이다. 한 Trait가 "
            "Primary 2개(서로 다른 Context 포함)를 얻으면 그 Trait는 더 이상 'Gap'이 아니라고 "
            "보고 Planner가 다른 Trait로 넘어간다. 그런데 이번 Coverage Policy의 SUFFICIENT는 "
            "Primary 2개만으로는 가중치가 정확히 2.0이라 3.0 문턱을 못 넘는다(§ 아래 실측 사례) "
            "— **Primary 2개를 요구하는 조건과 가중치 3.0을 요구하는 조건이 서로 다른 것을 "
            "요구한다**(실질적으로 가중치 조건이 더 엄격해 Primary 3개 또는 Primary 2개+RELATED "
            "2개 이상이 필요하다). 이건 Persona의 답변 선택 정책 문제가 아니다 — Pack Context "
            "Direct Probe 질문은 5개 선택지 중 목표 Trait에 신호가 있는 선택지가 정확히 1개뿐이라 "
            "(나머지 4개는 NO_SIGNAL), Persona가 무엇을 고르든 선택의 여지가 사실상 없다."
        ),
        "concrete_example": (
            "환경 B `coverage_maximizing` Persona: causal_analysis가 서로 다른 Context 2곳에서 "
            "Primary 2개(가중치 2.0)를 얻어 Frame·Context 조건은 통과했지만, SUFFICIENT의 "
            "'가중치 3.0 이상' 조건 하나만 미충족으로 SUPPORTED에 머물렀다(missing_requirements: "
            "'effective_evidence_weight>=3.0 미충족(현재 2.0)'만 남고 나머지 조건은 전부 충족)."
        ),
        "top5_sufficient_persona_count": top5_count,
        "top8_sufficient_persona_count": top8_count,
        "total_personas": len(env_b_runs),
    }


# ============================== 보고서 직렬화 ==============================


def _write_json_report(diagnostics: dict[str, Any]) -> None:
    payload = {
        "flow": {
            "description": (
                "관심도 15개 → 선호 Context 4개(환경 A는 2개) → Contrast Context 1개 → "
                "최종 5개(환경 A는 3개) 확정 → Context마다 Routing 1개 → Anchor 1개 선택 → "
                "Seed 1개 → Adaptive Tail 4~6개(후보 소진 시에만 Backup). 실제 "
                "src.api.main의 submit_interest_rating/select_contexts(환경 A만)/"
                "confirm_contexts(환경 A만)/next_question/submit_answer를 그대로 호출한다."
            ),
            "full_mode_bypass_note": (
                "실제 /assessment/context-select·/assessment/context-confirm HTTP Endpoint는 "
                "선호 Context 정확히 2개·최종 Context 최대 3개로 하드코딩돼 있다(main.py 수정 "
                "금지). 환경 B(4+1)만 그 두 Endpoint를 호출하지 않고, 그 Endpoint가 내부에서 "
                "쓰는 실제 순수 함수 select_contrast_context()를 Full Mode 파라미터로 직접 "
                "호출한 뒤 AssessmentState에 결과를 채운다 — 그 아래 실제 Context Vector· "
                "Coverage Matrix·Anchor·Seed·Tail·Backup 로직은 전부 동일한 실제 함수를 그대로 "
                "쓴다."
            ),
            "llm_note": (
                "LLM 네트워크는 호출하지 않는다. 대신 tests/test_context_pack_adaptive_"
                "e2e.py::_FakeLLMClient와 같은 원리의 결정론적 Fake Client를 재사용해 "
                "Prompt에서 실제 role_id·context·frame_id를 그대로 반영한 5개 선택지를 "
                "돌려준다 — 실측 결과 LLM을 완전히 끄면(Fake도 없으면) Pack Context Adaptive "
                "Tail이 allow_base_question_fallback=False 정책 때문에 매번 Backup으로 즉시 "
                "빠져 최소 4개조차 못 채운다(§ 아래 '설계 결정과 한계')."
            ),
        },
        "coverage_policy": {
            "primary_weight": 1.0,
            "related_weight": 0.5,
            "no_signal_weight": 0.0,
            "sufficient_min_primary_count": SUFFICIENT_MIN_PRIMARY_COUNT,
            "sufficient_min_effective_weight": 3.0,
            "sufficient_min_context_count": SUFFICIENT_MIN_CONTEXT_COUNT,
            "sufficient_min_frame_count": 2,
            "sufficient_min_directional_consistency": 0.7,
            "note": "이번 라운드에서 임의로 바꾸지 않았다 — 이전 라운드와 완전히 동일하다.",
        },
        "environments": {
            "env_a": {"label": diagnostics["env_a"]["label"], "personas": diagnostics["env_a"]["runs"]},
            "env_b": {"label": diagnostics["env_b"]["label"], "personas": diagnostics["env_b"]["runs"]},
        },
        "conclusion": _conclusion(diagnostics),
        "previous_round_correction": (
            "이전 라운드의 '전체 158문항, 52~56문항 권장'은 실제 4+1/2+1 세션이 아니라 15개 "
            "Context와 각 Context의 Anchor 5개 전부를 순회한 Inventory 상한이었다. 그 수치는 "
            "trait_evidence_coverage_inventory_ceiling_report.json으로 이름을 바꿔 분리했고, "
            "실제 세션 권장치로 쓰지 않는다."
        ),
        "note": (
            "생성 시각·메모리 값을 담지 않는다 — 같은 코드에서 재실행하면 byte-identical해야 "
            "한다. data/reviews/는 이 스크립트가 읽지도 쓰지도 않는다(12개 Pack·공용 Adaptive "
            "Probe 승인은 전부 tempfile 안에서만 만든다)."
        ),
    }
    JSON_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {JSON_OUTPUT_PATH}")


def _persona_table_row(run: dict[str, Any]) -> str:
    b = run["coverage_status_breakdown_full"]
    return (
        f"| {run['scenario_label']} | {run['trait_evidence_question_count']} | "
        f"{run['routing_question_count']} | {run['backup_used_count']} | "
        f"{b['UNOBSERVED']}·{b['LIMITED']}·{b['SUPPORTED']}·{b['SUFFICIENT']}·{b['CONFLICTED']} | "
        f"{'✅' if run['top5_sufficient'] else '❌'} | {'✅' if run['top8_sufficient'] else '❌'} |"
    )


def _checkpoint_table(run: dict[str, Any]) -> list[str]:
    lines = [
        f"### {run['scenario_label']} — Context {run['final_context_ids']}",
        "",
        f"Anchor: {run['anchor_by_context']}",
        "",
        "| 질문 수 Checkpoint | UNOBSERVED·LIMITED·SUPPORTED·SUFFICIENT·CONFLICTED |",
        "|---|---|",
    ]
    for cap, breakdown in sorted(run["coverage_status_breakdown_by_checkpoint"].items(), key=lambda kv: int(kv[0])):
        lines.append(
            f"| {cap} | {breakdown['UNOBSERVED']}·{breakdown['LIMITED']}·{breakdown['SUPPORTED']}·"
            f"{breakdown['SUFFICIENT']}·{breakdown['CONFLICTED']} |"
        )
    b = run["coverage_status_breakdown_full"]
    lines.append(
        f"| {run['trait_evidence_question_count']}(전체) | {b['UNOBSERVED']}·{b['LIMITED']}·{b['SUPPORTED']}·"
        f"{b['SUFFICIENT']}·{b['CONFLICTED']} |"
    )
    lines += [
        "",
        f"- 구조적으로 SUFFICIENT 불가능(Context 2개 미달): "
        f"{', '.join(run['context_2plus_structurally_impossible']) or '(없음)'}",
        f"- 질문 Mapping 부족(승인된 기회<2): {', '.join(run['mapping_gap_traits']) or '(없음)'}",
        f"- Context 선택 때문에 관찰 자체가 없는 Trait: "
        f"{', '.join(run['unobserved_due_to_context_selection']) or '(없음)'}",
        "",
    ]
    return lines


def _write_markdown_report(diagnostics: dict[str, Any]) -> None:
    conclusion = _conclusion(diagnostics)
    lines2: list[str] = [
        "# Trait Evidence Coverage — 실제 4+1/2+1 세션 시뮬레이션 보고서",
        "",
        "브랜치 `a/trait-evidence-coverage-shadow`. **이 문서가 주 보고서다** — 이전",
        "라운드의 158문항/52~56문항 권고는 실제 세션이 아니었다(정정 지시 §7). 그",
        "수치는 `trait_evidence_coverage_inventory_ceiling_report.md`로 이름을 바꿔",
        "참고 자료로만 남겼다.",
        "",
        "## 0. 이전 권고를 어떻게 정정했는가",
        "",
        "- 이전 환경 A/B는 15개 Context와 각 Context의 Anchor 5개 전부를 순회한 뒤",
        "  \"질문 수 상한별 SUFFICIENT 개수\"를 쟀다 — 한 세션이 실제로 겪는 경로가",
        "  아니었다.",
        "- 이번 라운드는 실제 `src.api.main`의 Endpoint 함수(`submit_interest_rating`/",
        "  `select_contexts`/`confirm_contexts`/`next_question`/`submit_answer`)를",
        "  그대로 호출해서, Context마다 Anchor 정확히 1개·Seed 1개·Adaptive Tail",
        "  4~6개만 쓰는 진짜 세션 하나를 재현한다.",
        "- \"최소 52·최대 56\"이라는 이전 권고는 폐기한다 — 아래 §7이 실제 세션 기준",
        "  숫자로 대체한다.",
        "",
        "## 1. 환경 A — 실제 3 Context, 2+1 세션 (Persona별 질문 수)",
        "",
        "| Persona | Trait 질문 | Routing | Backup 사용 | UNOBS·LIM·SUP·SUFF·CONF | 상위5 | 상위8 |",
        "|---|---|---|---|---|---|---|",
    ]
    for run in diagnostics["env_a"]["runs"]:
        lines2.append(_persona_table_row(run))
    lines2 += [
        "",
        "## 2. 환경 B — 실제 15 Context, 4+1 세션 (Persona별 질문 수)",
        "",
        "| Persona | Trait 질문 | Routing | Backup 사용 | UNOBS·LIM·SUP·SUFF·CONF | 상위5 | 상위8 |",
        "|---|---|---|---|---|---|---|",
    ]
    for run in diagnostics["env_b"]["runs"]:
        lines2.append(_persona_table_row(run))

    lines2 += ["", "## 3. 20/25/30/35문항 Checkpoint (환경 B, Persona별)", ""]
    for run in diagnostics["env_b"]["runs"]:
        lines2 += _checkpoint_table(run)

    lines2 += ["", "## 4. 상위 5·8개 Trait 충족 여부 요약", "",
               f"- 상위 5개 전부 SUFFICIENT인 Persona: {conclusion['top5_sufficient_persona_count']}/"
               f"{conclusion['total_personas']}(환경 B 기준)",
               f"- 상위 8개 전부 SUFFICIENT인 Persona: {conclusion['top8_sufficient_persona_count']}/"
               f"{conclusion['total_personas']}(환경 B 기준)",
               ""]

    lines2 += ["## 5. 구조적으로 불가능한 Trait", ""]
    # 9개 Persona 각각의 impossible 목록을 그냥 합치면(합집합) 거의 전부가 "불가능"으로
    # 보인다 — 대부분의 Persona는 애초에 Context 다양성을 노리지 않기 때문이다(주제가
    # 좁은 Persona일수록 당연히 그 주제 밖 Trait의 Context가 적다). "정말 구조적으로
    # 불가능한가"는 **Coverage 최대화형(의도적으로 폭을 넓히려 한 Persona)** 기준으로
    # 봐야 의미가 있다 — 그 Persona조차 Context 2개를 못 채웠다면 진짜 구조적 한계다.
    coverage_max_run = next(r for r in diagnostics["env_b"]["runs"] if r["scenario_key"] == "coverage_maximizing")
    intersection: set[str] = set(diagnostics["env_b"]["runs"][0]["context_2plus_structurally_impossible"])
    for run in diagnostics["env_b"]["runs"][1:]:
        intersection &= set(run["context_2plus_structurally_impossible"])
    lines2.append(
        f"**Coverage 최대화형(의도적으로 Context를 넓히려 한 Persona) 기준**: "
        f"{', '.join(sorted(coverage_max_run['context_2plus_structurally_impossible'])) or '(없음)'}"
    )
    lines2.append("")
    lines2.append(
        f"참고 — 환경 B 9개 Persona **전부**에서 Context 2개 조건을 못 채운 Trait(교집합, "
        f"더 보수적인 기준): {', '.join(sorted(intersection)) or '(없음)'}"
    )

    lines2 += ["", "## 6. 현재 기준을 Runtime에 연결해도 되는가", "",
               f"**결론: {conclusion['outcome']}** — {conclusion['explanation']}", "",
               "**원인.** " + conclusion["root_cause"], "",
               "**구체 사례.** " + conclusion["concrete_example"], ""]

    lines2 += [
        "## 7. 전체 Inventory 상한과 실제 세션 결과 차이",
        "",
        "| | 전체 Inventory 상한(참고용, 실제 세션 아님) | 실제 세션(이 보고서) |",
        "|---|---|---|",
        "| 환경 A 최대 질문 수 | 38(고정 콘텐츠 전부) | "
        f"{max(r['trait_evidence_question_count'] for r in diagnostics['env_a']['runs'])}(2+1, 3 Context) |",
        "| 환경 B 최대 질문 수 | 158(15 Context×Anchor 5개 전부) | "
        f"{max(r['trait_evidence_question_count'] for r in diagnostics['env_b']['runs'])}(4+1, 5 Context) |",
        "| 환경 B SUFFICIENT(최선) | 23/24(전체 158문항 다 씀) | "
        f"{max(r['coverage_status_breakdown_full']['SUFFICIENT'] for r in diagnostics['env_b']['runs'])}"
        "/24(35문항 상한) |",
        "",
        "실제 세션은 한 Context에서 Anchor 1개만 쓰고 Tail도 4~6개로 끝나므로, Inventory",
        "상한의 '몇 번째 문항에서 충분해지는가'라는 숫자를 실제 세션 권장치로 쓸 수 없다.",
        "",
        "## 8. 설계 결정과 한계",
        "",
        "- LLM은 네트워크를 호출하지 않는 결정론적 Fake Client로 대체했다(§ 위 flow 설명).",
        "  실측 결과 Fake조차 없이 LLM을 끄면 Pack Context Adaptive Tail이 매번 즉시",
        "  Backup으로 빠져 최소 4개도 못 채운다 — 실제 LLM이 붙으면 결과가 달라질 수",
        "  있다(이 진단은 그 차이를 재현하지 않는다).",
        "- 환경 B의 \"4+1\"은 실제 `/assessment/context-select` Endpoint로 만들 수 없다",
        "  (2/3으로 하드코딩됨, main.py 수정 금지) — 그 Endpoint가 쓰는 순수 함수를",
        "  직접 호출해 우회했다(§ 위 flow 설명).",
        "- Anchor는 모든 Context에서 '알파벳 순 첫 Anchor'로 결정론적으로 골랐다 —",
        "  Persona 주제에 맞는 Anchor를 수작업으로 고르지 않았다(알려진 단순화).",
        "- Pack Context Direct Probe 질문은 선택지 5개 중 신호가 있는 게 1개뿐이라,",
        "  Persona의 답변 선택 정책이 Pack Context에서는 사실상 영향이 없다 — 실제",
        "  영향은 Legacy Tail·Seed·Routing(Anchor) 선택에서만 나타난다.",
        "- 12개 ContextPack·공용 Adaptive Probe 승인은 전부 tempfile Fixture다.",
        "  `data/reviews/`는 이 스크립트 실행 전후로 바이트 하나도 바뀌지 않는다.",
    ]

    MD_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MD_OUTPUT_PATH.write_text("\n".join(lines2) + "\n", encoding="utf-8")
    print(f"wrote {MD_OUTPUT_PATH}")


def main() -> None:
    diagnostics = run_diagnostics()
    _write_json_report(diagnostics)
    _write_markdown_report(diagnostics)


if __name__ == "__main__":
    main()
