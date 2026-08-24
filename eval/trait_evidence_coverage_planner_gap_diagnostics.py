"""Trait Evidence Coverage — Adaptive Target Planner Gap 진단 (읽기 중심 Shadow, v2) —
a/planner-gap-9persona-diagnostics.

**이전 라운드(ca82f1f, `a/trait-evidence-coverage-planner-gap`) 대비 무엇을 고쳤는가.**

1. **Persona 9개로 확장.** 이전엔 4개만 썼다(§ 이전 문서 "가볍게 유지한 선택"). 이번
   지시는 Coverage 실제 세션 진단(`trait_evidence_coverage_session_diagnostics.py`,
   이미 병합됨)과 같은 9개 Persona를 전부 쓴다 — 새로 정의하지 않고 그 모듈에서 그대로
   가져온다(Persona/관심도 규칙에 두 벌의 정본을 만들지 않기 위해, 아래 import 참고).
2. **Anchor를 항상 알파벳 첫 번째로 고정하지 않는다.** 이전 라운드는 "모든 시나리오에
   같은 규칙"이라는 이유로 `anchors[0]`을 항상 썼다(§ 이전 문서 "알려진 단순화"). 이번엔
   (a) Pack Context는 그 Anchor가 실제로 열어주는 Direct Probe 후보 Trait 집합과 Persona
   의 관심 Trait 상위 8개의 교집합이 가장 큰 Anchor를 고르고(§ `_anchor_choice_for_persona`),
   (b) Legacy 3개 Context(Anchor가 후보 Blueprint 풀에 영향을 주지 않는다 — 증거 게이팅
   에만 관여)는 Persona별로 결정론적으로 다른 Anchor가 나오도록 안정 해시로 고른다.
   별도로 "동일 Context, Anchor만 다름" 통제 비교 실험(§ `run_anchor_sensitivity_
   experiment`)에서 Coverage 최대/최소 Anchor 조합도 명시적으로 비교한다.
3. **대안 C의 순환성을 없앤다.** 이전 구현은 `top_traits`를 Persona의 고정
   `trait_affinity_order`(테스트 저자가 미리 정한 "진짜" 선호 순위 — 실제 시스템은 절대
   알 수 없는 값)에서 그대로 가져왔다. 이 값은 같은 Persona의 답변 선택 정책
   (`_choose_by_affinity`)이 참조하는 바로 그 순위이기도 해서, C가 "그 세션이 어떤 답을
   고를지 미리 알고" 질문을 배정하는 자기충족적 구조였다 — 엄밀히 "세션 종료 후 결과"는
   아니었지만 실제 시스템에 없는 외부 정보(오라클)를 미리 쓴다는 점에서 같은 종류의
   반칙이다. 이번 버전은 `_provisional_top_traits()`로 **그 시점까지 실제로 쌓인
   evidence_ledger의 weight만으로** 상위 8개를 다시 계산한다 — Persona의 숨은 선호도,
   세션 최종 결과 어느 쪽도 참조하지 않는다.
4. **Exploration 보장을 대안 C2로 분리한다.** 순수 C(진짜 provisional 계산이라도)는
   세션 초반 증거가 하나도 없을 때 알파벳 순 동점 처리로 상위 8개가 자의적으로 고정될
   위험이 있다. C2는 "서로 다른 Trait 최소 8개가 증거를 얻기 전까지는 A와 동일하게
   넓게 탐색한다"는 명시적 Exploration 예산을 추가한 혼합형이다(§5 요구사항 그대로).
   C/C2 둘 다 매 turn마다 provisional 상위 집합을 기록해 Trait의 진입·탈락을 추적한다
   (§ `provisional_top_traits_history`, `misidentified_trait_lockin_turns`).

**금지 사항 준수.** Runtime Planner(`select_pack_adaptive_target`, 소스 파일 자체)·
Stop Condition(`decide_stop_or_continue`)·질문 Blueprint·Trait Mapping·Review JSON
어느 것도 수정하지 않는다 — A/B/C/C2는 이 스크립트 프로세스 안에서만
`unittest.mock.patch.object(main_module, "select_pack_adaptive_target", ...)`로
갈아끼운다(세션이 끝나면 원상복구). Coverage 기준(weight>=3.0·Context>=2·Frame>=2)도
`src.engines.trait_evidence_coverage_engine`에서 그대로 가져와 한 바이트도 바꾸지
않는다. 24개 전체를 SUFFICIENT로 만드는 것을 목표로 삼지 않는다(§7) — 상위 5~8개
충족률이 baseline 대비 뚜렷하게 개선되지 않으면 "구현 권고"가 아니라 "질문 Mapping/
Planner 구조 재설계 필요"로 결론 낸다(§ `_recommendation`).

**재사용하는 실제 함수** (다시 구현하지 않는다):
`src.api.main`의 실제 Endpoint 5개, `src.engines.context_pack_adaptive_planner`의
실제 Planner 함수, `src.engines.evidence_engine.decide_stop_or_continue`,
`src.engines.trait_evidence_coverage_engine`(Coverage Policy, 이식·미변경),
`src.services.trait_signal_review_gate.gate_primary_eligible_evidence`,
`src.services.context_pack_runtime.ContextPackRuntime`/`context_pack_registry` —
전부 이전 라운드와 동일. Persona 정의·관심도 규칙·답변 선택 정책은
`eval.trait_evidence_coverage_session_diagnostics`에서 그대로 가져온다(새로 만들지
않는다, 이 모듈이 이미 병합돼 있고 9개 Persona의 유일한 정본이다).

## data/reviews/ 무변경

12개 ContextPack·공용 Adaptive Probe 승인은 전부 `tempfile` Fixture 안에서만 만든다
(이전 라운드와 동일한 `_build_fixture_registry` 패턴).

실행:
    PYTHONPATH=. ./.venv/bin/python eval/trait_evidence_coverage_planner_gap_diagnostics.py
"""

from __future__ import annotations

import hashlib
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

# Persona 정의·관심도 규칙·답변 선택 정책은 새로 만들지 않고 이미 병합된 9-Persona
# 진단(§ 위 docstring)에서 그대로 가져온다 — 두 벌의 정본이 생기면 시나리오가
# 어긋난다.
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

import re  # noqa: E402

_CONTEXT_RE = re.compile(r'context 필드에는 "(\w+)"를')
_FRAME_RE = re.compile(r'frame_id 필드에는 "(\w+)"를')
_ROLE_RE = re.compile(r"\[Option Role.*?\]\n(.*?)\n\ncontext 필드", re.DOTALL)


class _DeterministicFakeLLMClient:
    """`session_diagnostics.py::_DeterministicFakeLLMClient`와 동일 원리 — Prompt에서
    실제 context/frame_id/role_id를 파싱해 되돌려준다. `question_text`에 호출 순번을
    넣는다(Quality Gate의 "이전 질문과 문구가 같으면 재생성" 규칙 때문에 필요, 이전
    라운드에서 실측)."""

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
MAX_QUESTION_LOOP_ITERATIONS = 400

JSON_OUTPUT_PATH = ROOT / "outputs" / "evaluation" / "trait_evidence_coverage_planner_gap_report.json"
MD_OUTPUT_PATH = ROOT / "outputs" / "evaluation" / "trait_evidence_coverage_planner_gap_report.md"

# 대안 C2의 Exploration 예산 — 서로 다른 Trait 최소 이 개수가 증거(weight>0)를 얻기
# 전까지는 A와 동일한 "세션 전체 미충족" 기준으로 넓게 탐색한다(§4 "초기 Evidence가
# 부족한 동안 Exploration 슬롯을 보장").
C2_EXPLORATION_MIN_DISTINCT_TRAITS_WITH_EVIDENCE = 8
# C/C2가 좁히는 "상위 Trait" 크기 — 판단 기준(§7)이 "상위 5~8개"를 함께 말하므로 더 넓은
# 쪽인 8을 쓴다(상위 5개는 이 8개의 부분집합이라 5개 지표도 그대로 계산된다).
PROVISIONAL_TOP_N = 8

# 이전 라운드(ca82f1f)의 실측값 — §"이전 4-Persona 결과와 새 9-Persona 결과 비교"에
# 그대로 인용한다(다시 실행하지 않는다, 그 라운드는 이미 완료됐고 재현 불가능한 이유가
# 없지만 "비교 대상"으로는 그 시점의 고정 스냅샷을 쓰는 게 더 정직하다 — 이번 라운드가
# Persona·Anchor·C의 정의 자체를 바꿨으므로 재실행하면 "같은 조건 재현"이 아니라
# "다른 조건으로 새로 측정"이 된다).
PREVIOUS_ROUND_4_PERSONA_KEYS = ("analytical", "mixed_cross_domain", "niche_interest", "coverage_maximizing")
PREVIOUS_ROUND_COMPARISON: dict[str, Any] = {
    "source": "ca82f1f(a/trait-evidence-coverage-planner-gap), 4개 Persona만, top_traits가 "
    "Persona 고정 trait_affinity_order(오라클)에서 나온 순환적 정의의 C",
    "baseline": {"top5_fraction_avg": 0.100, "top8_fraction_avg": 0.09375, "total_trait_evidence_questions": 140},
    "A": {"top5_fraction_avg": 0.100, "top8_fraction_avg": 0.125, "total_wasted_slots": 0},
    "B": {"top5_fraction_avg": 0.100, "top8_fraction_avg": 0.09375, "total_wasted_slots": 0},
    "C_circular": {
        "top5_fraction_avg": 0.150, "top8_fraction_avg": 0.125, "total_wasted_slots": 38,
        "caveat": "이 C는 순환적 정의였다 — 이번 라운드의 C(§ 위 3번)와 직접 비교하면 안 된다.",
    },
}


# ============================== Anchor 선택 — 알파벳 첫 Anchor 고정 폐기 ==============================


def _anchor_ids_for_context(context_id: str, registry: ContextPackRegistry) -> list[str]:
    if context_id in VERTICAL_SLICE_CONTEXT_IDS:
        from src.data.contexts.context_anchor_presentations import CONTEXT_ANCHOR_PRESENTATIONS

        return sorted(p.anchor_id for p in CONTEXT_ANCHOR_PRESENTATIONS if p.context_id == context_id)
    pack = registry.get_pack(context_id)
    if pack is None:
        return []
    return sorted(a.anchor_id for a in pack.anchor_presentations)


def _anchor_candidate_trait_ids(context_id: str, anchor_id: str, runtime: ContextPackRuntime) -> frozenset[str]:
    """이 Context+Anchor 조합이 실제로 열어주는 Direct Probe 후보 Trait 집합. Legacy
    3개 Context는 Anchor가 후보 Blueprint 풀에 영향을 주지 않는다(증거 게이팅에만
    관여, `context_anchor_choices` → `gate_primary_eligible_evidence`) — 그래서 빈
    집합을 돌려준다(호출부가 이 사실을 알고 Legacy는 별도 규칙을 쓴다)."""

    if context_id in VERTICAL_SLICE_CONTEXT_IDS:
        return frozenset()
    candidates = runtime.get_direct_probe_candidates(context_id, anchor_id)
    return frozenset(bp.trait_id for bp in candidates)


def _stable_index(*parts: str, modulo: int) -> int:
    """결정론적이지만 "항상 0"은 아닌 인덱스. Legacy Context Anchor처럼 후보 Trait
    풀에 영향을 주지 않아 점수화할 기준이 없는 경우에도 Persona마다 다른 Anchor가
    나오게 한다(§2 "모든 Context에서 알파벳 첫 Anchor만 사용하지 말 것")."""

    if modulo <= 0:
        return 0
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % modulo


def _anchor_choice_for_persona(
    scenario: PersonaScenario, context_id: str, registry: ContextPackRegistry, runtime: ContextPackRuntime,
) -> str:
    """§2 — Persona별 의미 있는 Anchor 선택.

    **실측으로 확인한 사실(§4 Anchor 민감도 실험 참고)**: 지금 실제 Pack Context는
    Anchor가 달라도 `get_direct_probe_candidates()`가 돌려주는 후보 Trait 집합이
    Context 안에서 완전히 동일하다 — Anchor는 후보 Blueprint 풀이 아니라 증거
    게이팅(`context_anchor_choices` → `gate_primary_eligible_evidence`)에만 관여한다.
    그래서 "Persona 관심 Trait와 후보 Trait 교집합" 점수는 그 Context의 모든 Anchor가
    항상 동점이다 — 이 점수만으로 고르면 tuple 비교의 두 번째 요소(anchor_id 문자열)
    때문에 매번 알파벳 순으로 "가장 마지막" Anchor가 조용히 고정 선택된다(§ 이전
    버전에서 실측으로 발견한 회귀 — "항상 첫 Anchor"와 근본적으로 같은 문제였다).
    그래서 동점일 때는(현재 사실상 항상 동점) 알파벳 순으로 고정하지 않고 Persona별
    안정 해시로 고른다 — 이 점수화 로직 자체는 남겨둔다(나중에 Anchor가 실제로 후보
    Trait 풀을 가르는 Pack이 생기면 그때는 이 점수가 실제로 갈린다)."""

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


# ============================== Fixture Registry(이전 라운드와 동일) ==============================


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


def _provisional_top_traits(session_id: str, registry: ContextPackRegistry, n: int) -> set[str]:
    """§4 순환성 차단 — 그 시점까지 실제로 쌓인 evidence_ledger의 weight만으로 상위 n개를
    계산한다. Persona의 숨은 trait_affinity_order도, 세션 최종 결과도 참조하지 않는다.
    아직 증거가 없는 Trait는 weight=0으로 전부 동률이고 Trait id 알파벳 순으로만
    갈린다 — "미리 안다"는 요소가 전혀 없다."""

    coverage = _session_coverage_snapshot(session_id, registry)
    ranked = sorted(
        CORE_TRAIT_IDS,
        key=lambda t: (-(coverage[t].effective_evidence_weight if t in coverage else 0.0), t),
    )
    return set(ranked[:n])


def _distinct_traits_with_any_evidence(session_id: str, registry: ContextPackRegistry) -> int:
    coverage = _session_coverage_snapshot(session_id, registry)
    return sum(1 for t in CORE_TRAIT_IDS if t in coverage and coverage[t].effective_evidence_weight > 0)


# ============================== Planner Gap 대안 A/B/C/C2(Shadow 전용) ==============================


@dataclass
class _AltDecisionLog:
    """이 세션 실행 동안 실제로 벌어진 target 선택 하나하나를 기록."""

    turn_target_trait_ids: list[str] = field(default_factory=list)
    turn_was_gap_at_assignment: list[bool] = field(default_factory=list)
    # None이면 낭비 아님. 낭비면 원인 category 문자열(§6 "낭비 슬롯의 정확한 정의와 발생 원인").
    turn_wasted_reason: list[str | None] = field(default_factory=list)
    # C/C2 전용 — 매 turn 실제로 사용한 provisional 상위 집합의 스냅샷(정렬된 tuple).
    provisional_top_traits_history: list[tuple[str, ...]] = field(default_factory=list)
    # C2 전용 — 그 turn이 Exploration 예산 안이었는지(True) Exploitation 단계였는지(False).
    turn_was_exploration_phase: list[bool] = field(default_factory=list)


def _make_alt_selector(
    alt: str, session_id: str, log: _AltDecisionLog, registry: ContextPackRegistry,
):
    """§ 대안 A/B/C/C2. `trait_summaries`는 실제 main.py가 넘기는 그 Context 전용
    요약(support_count 등)이고, 세션 전체 Coverage 상태가 필요하면
    `_session_coverage_snapshot`으로 그때그때 새로 읽는다."""

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

        is_exploration_phase = False
        provisional: set[str] | None = None

        if alt == "A":
            def gap(trait_id: str) -> bool:
                return not is_sufficient(trait_id)
        elif alt == "B":
            def gap(trait_id: str) -> bool:
                return local_gap(trait_id) or not is_sufficient(trait_id)
        elif alt == "C":
            provisional = _provisional_top_traits(session_id, registry, PROVISIONAL_TOP_N)

            def gap(trait_id: str) -> bool:
                return trait_id in provisional and not is_sufficient(trait_id)
        elif alt == "C2":
            # §4 "초기 Evidence가 부족한 동안 Exploration 슬롯을 보장" — 서로 다른 Trait
            # 최소 C2_EXPLORATION_MIN_DISTINCT_TRAITS_WITH_EVIDENCE개가 증거를 얻기
            # 전까지는 A와 동일하게 넓게 탐색한다.
            is_exploration_phase = (
                _distinct_traits_with_any_evidence(session_id, registry)
                < C2_EXPLORATION_MIN_DISTINCT_TRAITS_WITH_EVIDENCE
            )
            if is_exploration_phase:
                def gap(trait_id: str) -> bool:
                    return not is_sufficient(trait_id)
            else:
                provisional = _provisional_top_traits(session_id, registry, PROVISIONAL_TOP_N)

                def gap(trait_id: str) -> bool:
                    return trait_id in provisional and not is_sufficient(trait_id)
        else:
            raise ValueError(f"알 수 없는 대안: {alt}")

        def sort_key(trait_id: str) -> tuple[bool, bool, bool, str]:
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

        was_gap = gap(chosen_trait_id)
        wasted_reason: str | None = None
        if not was_gap:
            if all(not gap(t) for t in candidate_trait_ids):
                wasted_reason = "all_candidates_already_satisfied_but_stop_condition_forced_a_slot"
            elif chosen_trait_id == recent_target_trait_id:
                wasted_reason = "gap_false_but_repeated_recent_target"
            else:
                wasted_reason = "gap_false_but_non_gap_alternatives_existed"

        log.turn_target_trait_ids.append(chosen_trait_id)
        log.turn_was_gap_at_assignment.append(was_gap)
        log.turn_wasted_reason.append(wasted_reason)
        log.turn_was_exploration_phase.append(is_exploration_phase)
        if provisional is not None:
            log.provisional_top_traits_history.append(tuple(sorted(provisional)))
        return PackAdaptiveTargetDecision(trait_id=chosen_trait_id, blueprint=chosen_blueprint)

    return selector


# ============================== 실제 세션 실행 ==============================


@dataclass
class TraitTerminationRecord:
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
    per_turn_target_trait_ids: list[str | None] = field(default_factory=list)


def _run_persona_session(
    scenario: PersonaScenario, *, session_id: str, registry: ContextPackRegistry, runtime: ContextPackRuntime,
) -> SessionRun:
    """§3 — 실제 세션 그대로: 관심도 15개 → 선호 4개 → Contrast 1개 → 최종 5개
    확정(전부 실제 Endpoint, `ENABLE_CONTEXT_SELECTION_4_PLUS_1`이 네이티브로 배선돼
    있어 우회 없음) → Context마다 Routing 1개·Anchor 1개·Seed 1개·Adaptive Tail 4~6개
    (후보 소진 시에만 Backup). Trait 질문은 Context 5개 × 최대 6개 = 최대 30개가
    Adaptive Tail 몫이고, Seed 5개를 더하면 세션 전체 Trait 질문 상한은 35개다."""

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
    run.anchor_by_context = {
        cid: _anchor_choice_for_persona(scenario, cid, registry, runtime) for cid in final_ids
    }

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


def _coverage_results(run: SessionRun, ledger: list[Any], registry: ContextPackRegistry) -> dict[str, Any]:
    gate = gate_primary_eligible_evidence(ledger, run.final_context_anchor_choices, registry)
    return compute_all_trait_coverage(CORE_TRAIT_IDS, ledger, gate.approved_evidence_ids)


_STATUS_ORDER = {"UNOBSERVED": 0, "LIMITED": 1, "SUPPORTED": 2, "SUFFICIENT": 3, "CONFLICTED": 1}


def _top_n_sufficient(results: dict[str, Any], ranked_traits: list[str], n: int, *, min_status: str = "SUFFICIENT") -> bool:
    threshold = _STATUS_ORDER[min_status]
    top = ranked_traits[:n]
    return all(_STATUS_ORDER.get(results[t].coverage_status, 0) >= threshold for t in top)


def _top_n_sufficient_fraction(results: dict[str, Any], ranked_traits: list[str], n: int, *, min_status: str = "SUFFICIENT") -> float:
    threshold = _STATUS_ORDER[min_status]
    top = ranked_traits[:n]
    if not top:
        return 0.0
    return sum(1 for t in top if _STATUS_ORDER.get(results[t].coverage_status, 0) >= threshold) / len(top)


def _ranked_traits_for(scenario: PersonaScenario) -> list[str]:
    return sorted(CORE_TRAIT_IDS, key=lambda t: _affinity_rank(scenario, t))


def _ledger_length_after_nth_trait_question(run: SessionRun, n: int) -> int:
    trait_evidence_origins = {"PRIMARY_BLUEPRINT", "V2_DIRECT_PROBE"}
    count = 0
    for idx, record in enumerate(run.final_evidence_ledger, start=1):
        if record.evidence_origin.value in trait_evidence_origins:
            count += 1
            if count == n:
                return idx
    return len(run.final_evidence_ledger)


def _rebuild_offered_map(run: SessionRun, upto_turn: int) -> dict[str, list[str]]:
    offered: dict[str, list[str]] = {}
    for idx, trait_id in enumerate(run.per_turn_target_trait_ids[:upto_turn], start=1):
        if trait_id is not None:
            offered[f"turn_{idx}"] = [trait_id]
    remapped: dict[str, list[str]] = {}
    trait_evidence_records = [
        r for r in run.final_evidence_ledger[: _ledger_length_after_nth_trait_question(run, upto_turn)]
        if r.evidence_origin.value in {"PRIMARY_BLUEPRINT", "V2_DIRECT_PROBE"}
    ]
    for record, (_, trait_ids) in zip(trait_evidence_records, offered.items()):
        remapped[record.question_id] = trait_ids
    return remapped


def _termination_records(
    scenario: PersonaScenario, run: SessionRun, registry: ContextPackRegistry,
) -> dict[str, TraitTerminationRecord]:
    records = {t: TraitTerminationRecord(trait_id=t) for t in CORE_TRAIT_IDS}
    final_results = _coverage_results(run, run.final_evidence_ledger, registry)

    ledger = run.final_evidence_ledger
    contexts_seen_order = run.final_context_ids

    already_stopped: dict[str, str] = {}
    for turn_index, target_trait_id in enumerate(run.per_turn_target_trait_ids, start=1):
        if target_trait_id is None:
            continue
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


# ============================== 측정값(§6) ==============================


def _repetition_stats(run: SessionRun) -> dict[str, Any]:
    """§6 "동일 Trait 반복 수"."""

    targeted = [t for t in run.per_turn_target_trait_ids if t is not None]
    counts = Counter(targeted)
    return {
        "distinct_traits_targeted": len(counts),
        "max_repeat_count_for_a_single_trait": max(counts.values()) if counts else 0,
        "total_repeated_targeting_turns": sum(c - 1 for c in counts.values() if c > 1),
    }


def _diversity_stats(results: dict[str, Any]) -> dict[str, Any]:
    """§6 "Context·Frame 다양성" — UNOBSERVED가 아닌(즉 질문을 한 번이라도 받은) Trait만
    평균에 포함한다(UNOBSERVED는 Context/Frame 수가 항상 0이라 평균을 인위적으로
    낮춘다)."""

    observed = [r for r in results.values() if r.coverage_status != "UNOBSERVED"]
    if not observed:
        return {"avg_distinct_context_count": 0.0, "avg_distinct_frame_count": 0.0, "observed_trait_count": 0}
    return {
        "avg_distinct_context_count": sum(r.distinct_context_count for r in observed) / len(observed),
        "avg_distinct_frame_count": sum(r.distinct_frame_count for r in observed) / len(observed),
        "observed_trait_count": len(observed),
    }


def _unobserved_count(results: dict[str, Any]) -> int:
    return sum(1 for r in results.values() if r.coverage_status == "UNOBSERVED")


def _wasted_slot_breakdown(log: _AltDecisionLog) -> dict[str, Any]:
    """§6 "낭비 슬롯의 정확한 정의와 발생 원인" — 낭비 슬롯을 "그 turn에 배정된 Trait가
    배정 당시 그 대안 자신의 gap() 기준으로 이미 False였던 turn"으로 정의한다(모든
    대안에 같은 정의를 적용해야 비교가 공정하다). 원인은 세 범주로 나눈다:

    - all_candidates_already_satisfied_but_stop_condition_forced_a_slot: 그 turn의
      후보 Trait 전부가 이미 gap()==False였다(Stop Condition이 강제로 슬롯을 채움).
    - gap_false_but_repeated_recent_target: 바로 직전과 같은 Trait를 다시 배정.
    - gap_false_but_non_gap_alternatives_existed: 위 두 경우가 아닌 나머지."""

    reasons = [r for r in log.turn_wasted_reason if r is not None]
    return {
        "total_wasted_slots": len(reasons),
        "by_reason": dict(Counter(reasons)),
    }


def _provisional_top_traits_transitions(log: _AltDecisionLog) -> dict[str, Any]:
    """§4 "Trait가 상위 후보에서 탈락하거나 진입하는 과정을 기록" + §6 "초반 잘못
    선정된 Trait에 질문이 고착된 횟수". `provisional_top_traits_history`는 C/C2에서만
    채워진다(turn마다 그 시점의 provisional 상위 집합 스냅샷)."""

    history = log.provisional_top_traits_history
    if not history:
        return {"transitions": [], "misidentified_trait_lockin_turns": 0, "distinct_provisional_sets_seen": 0}

    transitions: list[dict[str, Any]] = []
    prev: set[str] = set()
    for turn_index, snapshot in enumerate(history, start=1):
        current = set(snapshot)
        entered = sorted(current - prev)
        exited = sorted(prev - current)
        if entered or exited:
            transitions.append({"turn_index": turn_index, "entered": entered, "exited": exited})
        prev = current

    # 고착 비용 — 어떤 Trait가 top 집합에 있는 동안(진입~탈락 구간) 실제로 그 Trait가
    # target으로 배정된 turn 수를 전부 더한 뒤, 결국 탈락한(=최종까지 top에 남지 못한)
    # Trait들의 몫만 센다.
    ever_exited = {t for tr in transitions for t in tr["exited"]}
    lockin_turns = 0
    for turn_index, target_trait_id in enumerate(log.turn_target_trait_ids, start=1):
        if target_trait_id in ever_exited and turn_index <= len(history) and target_trait_id in history[turn_index - 1]:
            lockin_turns += 1

    return {
        "transitions": transitions,
        "misidentified_trait_lockin_turns": lockin_turns,
        "distinct_provisional_sets_seen": len({s for s in history}),
    }


# ============================== 전체 실행 ==============================


def run_and_summarize(scenarios: list[PersonaScenario]) -> dict[str, Any]:
    fake_llm = _DeterministicFakeLLMClient()

    saved_env = {
        k: os.environ.get(k)
        for k in ("ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", "ENABLE_CONTEXT_PACK_RUNTIME", "ENABLE_CONTEXT_SELECTION_4_PLUS_1")
    }
    baseline_summaries: list[dict[str, Any]] = []
    alt_summaries: dict[str, list[dict[str, Any]]] = {"A": [], "B": [], "C": [], "C2": []}

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
                        scenario, session_id=f"planner_gap_baseline_{scenario.key}",
                        registry=fixture_registry, runtime=fixture_runtime,
                    )
                    baseline_summaries.append(_summarize_baseline(scenario, run, fixture_registry))

                for alt in ("A", "B", "C", "C2"):
                    for scenario in scenarios:
                        log = _AltDecisionLog()
                        session_id = f"planner_gap_{alt}_{scenario.key}"
                        selector = _make_alt_selector(alt, session_id, log, fixture_registry)
                        with patch.object(main_module, "select_pack_adaptive_target", selector):
                            run = _run_persona_session(
                                scenario, session_id=session_id, registry=fixture_registry, runtime=fixture_runtime,
                            )
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
    ranked = _ranked_traits_for(scenario)
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
        "top5_supported_or_better_fraction": _top_n_sufficient_fraction(results, ranked, 5, min_status="SUPPORTED"),
        "top8_supported_or_better_fraction": _top_n_sufficient_fraction(results, ranked, 8, min_status="SUPPORTED"),
        "unobserved_trait_count": _unobserved_count(results),
        "repetition_stats": _repetition_stats(run),
        "diversity_stats": _diversity_stats(results),
        "trait_termination": {
            t: {
                "stopped_in_context": r.stopped_in_context,
                "stopped_at_turn_index": r.stopped_at_turn_index,
                "retargeted_in_other_context_after_stop": r.retargeted_in_other_context_after_stop,
                "coverage_status_at_stop_moment": r.coverage_status_at_stop_moment,
                "coverage_status_final": r.coverage_status_final,
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
    ranked = _ranked_traits_for(scenario)
    return {
        "scenario_key": scenario.key,
        "trait_evidence_question_count": run.trait_evidence_question_count,
        "backup_used_count": run.backup_used_count,
        "coverage_status_breakdown": coverage_status_breakdown(results),
        "top5_sufficient": _top_n_sufficient(results, ranked, 5),
        "top8_sufficient": _top_n_sufficient(results, ranked, 8),
        "top5_sufficient_fraction": _top_n_sufficient_fraction(results, ranked, 5),
        "top8_sufficient_fraction": _top_n_sufficient_fraction(results, ranked, 8),
        "unobserved_trait_count": _unobserved_count(results),
        "repetition_stats": _repetition_stats(run),
        "diversity_stats": _diversity_stats(results),
        "wasted_slots": _wasted_slot_breakdown(log),
        "provisional_top_traits": _provisional_top_traits_transitions(log),
        "exploration_turns": sum(1 for x in log.turn_was_exploration_phase if x),
        # C2 전용 진단 — 후보 Blueprint 풀이 너무 좁으면(§ 실측: 일부 Persona는 5개
        # Context 전부에서 서로 다른 Trait를 3~4개밖에 제시하지 않는다) Exploration
        # 예산(distinct >= 8)을 세션 안에서 끝내 못 채워 C2가 사실상 A와 동일하게
        # 동작한다 — 이 사실을 숨기지 않고 그대로 남긴다(§7 정직성 원칙).
        "exploitation_phase_ever_reached": (
            len(log.turn_was_exploration_phase) > 0 and not all(log.turn_was_exploration_phase)
        ),
        "total_targeted_turns": len(log.turn_target_trait_ids),
    }


# ============================== Anchor 민감도 실험(§2) ==============================


def _pack_context_with_widest_anchor_spread(registry: ContextPackRegistry, runtime: ContextPackRuntime) -> str:
    """Coverage 최대/최소 Anchor 조합을 비교하기에 가장 뜻있는 Pack Context —
    Anchor별 후보 Trait 수 차이가 가장 큰 Context를 고른다(결정론적, 동점이면
    context_id 알파벳 순)."""

    from src.data.contexts.context_definitions import CONTEXT_IDS as ALL_CONTEXT_IDS

    best_context: str | None = None
    best_spread = -1
    for context_id in sorted(ALL_CONTEXT_IDS):
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


def run_anchor_sensitivity_experiment(
    base_scenario: PersonaScenario, registry: ContextPackRegistry, runtime: ContextPackRuntime,
) -> dict[str, Any]:
    """§2 "Coverage 최대/최소 Anchor 조합" + "동일 Context에서 Anchor 변화에 따른 결과
    비교" — 한 Persona·같은 Context 5개를 고정하고, 그중 Anchor 스프레드가 가장 큰
    Pack Context 하나만 Anchor를 바꿔가며 재실행한다.

    **실측 결과(정직하게 보고)**: 지금 실제 12개 Pack Context는 전부 Anchor별 후보
    Trait 수 스프레드가 0이다 — 어느 Anchor를 고르든 그 Context가 여는 Direct Probe
    후보 Trait 집합이 완전히 같다(§ `_anchor_choice_for_persona` docstring). 그래서
    "Coverage 최대/최소 Anchor"라는 이름을 쓰되, 실제로는 (a) 후보 Trait 수 기준
    최댓값을 주는 Anchor, (b) 최솟값을 주는 Anchor를 각각 고르고 — 스프레드가 0이면
    둘 다 같은 값일 수 있으므로 그 경우 알파벳 순 첫 Anchor/마지막 Anchor로 명시적으로
    갈라서 "Anchor 자체를 다르게 강제했을 때 결과가 실제로 갈리는지"를 여전히 검증할
    수 있게 한다(그래야 이 실험이 "셋 다 우연히 같은 Anchor를 골라서 당연히 같은
    결과"가 되는 걸 막는다)."""

    target_context = _pack_context_with_widest_anchor_spread(registry, runtime)
    anchors = _anchor_ids_for_context(target_context, registry)
    trait_counts = {a: len(_anchor_candidate_trait_ids(target_context, a, runtime)) for a in anchors}
    candidate_pool_varies_by_anchor = max(trait_counts.values()) > min(trait_counts.values())

    max_anchor = max(anchors, key=lambda a: (trait_counts[a], a))
    min_anchor = min(anchors, key=lambda a: (trait_counts[a], a))
    if max_anchor == min_anchor and len(anchors) > 1:
        # 스프레드 0(§ 위 실측) — Anchor 자체는 다르게 강제하되, 그 사실을 잃지 않는다.
        max_anchor, min_anchor = anchors[0], anchors[-1]
    default_anchor = _anchor_choice_for_persona(base_scenario, target_context, registry, runtime)

    variants = {"max_coverage_anchor": max_anchor, "min_coverage_anchor": min_anchor, "persona_default": default_anchor}
    results_by_variant: dict[str, Any] = {}
    for variant_name, forced_anchor in variants.items():
        session_id = f"anchor_sensitivity_{base_scenario.key}_{variant_name}"
        results_by_variant[variant_name] = _run_forced_anchor_session(
            base_scenario, target_context, forced_anchor, registry, runtime, session_id,
        )

    return {
        "target_context": target_context,
        "anchor_candidate_trait_counts": trait_counts,
        "candidate_pool_varies_by_anchor": candidate_pool_varies_by_anchor,
        "finding": (
            "후보 Trait 풀이 Anchor에 따라 갈리지 않는다 — Anchor는 증거 게이팅에만 영향을 "
            "준다(이 실험의 Fixture는 모든 Anchor를 승인해 게이팅 차이도 제거했으므로, 결과가 "
            "같다면 그건 이 두 경로 모두에서 Anchor가 실제로 결과에 영향을 주지 않는다는 뜻이다)."
            if not candidate_pool_varies_by_anchor else
            "이 Context는 Anchor에 따라 후보 Trait 풀이 실제로 달라진다 — 아래 결과 차이는 그 "
            "차이를 그대로 반영한다."
        ),
        "variants": variants,
        "results": results_by_variant,
    }


def _run_forced_anchor_session(
    scenario: PersonaScenario, forced_context_id: str, forced_anchor_id: str,
    registry: ContextPackRegistry, runtime: ContextPackRuntime, session_id: str,
) -> dict[str, Any]:
    real_choice = _anchor_choice_for_persona

    def patched(scn: PersonaScenario, context_id: str, reg: ContextPackRegistry, rt: ContextPackRuntime) -> str:
        if context_id == forced_context_id:
            return forced_anchor_id
        return real_choice(scn, context_id, reg, rt)

    module_globals = sys.modules[__name__]
    with patch.object(module_globals, "_anchor_choice_for_persona", patched):
        run = _run_persona_session(scenario, session_id=session_id, registry=registry, runtime=runtime)
    results = _coverage_results(run, run.final_evidence_ledger, registry)
    ranked = _ranked_traits_for(scenario)
    return {
        "anchor_by_context": dict(sorted(run.anchor_by_context.items())),
        "trait_evidence_question_count": run.trait_evidence_question_count,
        "coverage_status_breakdown": coverage_status_breakdown(results),
        "top5_sufficient_fraction": _top_n_sufficient_fraction(results, ranked, 5),
        "top8_sufficient_fraction": _top_n_sufficient_fraction(results, ranked, 8),
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
            "avg_unobserved_trait_count": avg(baseline_rows, "unobserved_trait_count"),
        },
        "D_supported_headline": {
            "note": "재실행 없음 — Baseline과 완전히 동일한 실행, SUPPORTED 이상을 헤드라인으로 재집계.",
            "top5_fraction_avg": avg(baseline_rows, "top5_supported_or_better_fraction"),
            "top8_fraction_avg": avg(baseline_rows, "top8_supported_or_better_fraction"),
            "total_trait_evidence_questions": sum(r["trait_evidence_question_count"] for r in baseline_rows),
        },
    }
    for alt in ("A", "B", "C", "C2"):
        rows = summary["alternatives"][alt]
        comparison[alt] = {
            "top5_sufficient_rate": rate(rows, "top5_sufficient"),
            "top8_sufficient_rate": rate(rows, "top8_sufficient"),
            "top5_sufficient_fraction_avg": avg(rows, "top5_sufficient_fraction"),
            "top8_sufficient_fraction_avg": avg(rows, "top8_sufficient_fraction"),
            "total_trait_evidence_questions": sum(r["trait_evidence_question_count"] for r in rows),
            "total_wasted_slots": sum(r["wasted_slots"]["total_wasted_slots"] for r in rows),
            "avg_unobserved_trait_count": avg(rows, "unobserved_trait_count"),
            "total_misidentified_trait_lockin_turns": sum(
                r["provisional_top_traits"]["misidentified_trait_lockin_turns"] for r in rows
            ),
        }
        if alt == "C2":
            comparison[alt]["personas_that_ever_reached_exploitation_phase"] = sum(
                1 for r in rows if r.get("exploitation_phase_ever_reached")
            )
            comparison[alt]["persona_count"] = len(rows)
    return comparison


# §7 "결과를 맞추기 위해 기준을 완화하지 않는다" — 구현을 권고하려면 baseline 대비
# 결합 점수((상위5+상위8)/2)가 이 값 이상 개선돼야 한다. 이 문턱값 자체는 회로가
# 아니라 판단 기준을 미리 문서화해 사후에 숫자에 맞춰 문턱을 고치지 못하게 하기
# 위한 것이다 — 0.05(상위 5~8개 중 평균 약 0.3~0.4개 이상의 실질적 개선)를 "뚜렷한
# 개선"의 최소선으로 잡는다.
MINIMUM_MEANINGFUL_IMPROVEMENT = 0.05


def _recommendation(comparison: dict[str, Any]) -> dict[str, Any]:
    order = ["baseline", "A", "B", "C", "C2"]
    top5 = {alt: comparison[alt]["top5_sufficient_fraction_avg"] for alt in order}
    top8 = {alt: comparison[alt]["top8_sufficient_fraction_avg"] for alt in order}
    fractions = {alt: (top5[alt] + top8[alt]) / 2 for alt in order}
    best_alt = max(order[1:], key=lambda a: (fractions[a], -comparison[a].get("total_wasted_slots", 0)))
    improvement = fractions[best_alt] - fractions["baseline"]
    ranking_text = " → ".join(
        f"{alt}(상위5 {top5[alt]:.3f}/상위8 {top8[alt]:.3f}/평균 {fractions[alt]:.3f})" for alt in order
    )

    meaningfully_better = improvement >= MINIMUM_MEANINGFUL_IMPROVEMENT

    if not meaningfully_better:
        chosen = "NONE"
        implementation_recommended = False
        justification = (
            f"(상위5 비율+상위8 비율)/2 결합 점수 실측값은 {ranking_text} 순이다. 가장 나은 대안"
            f"({best_alt})도 baseline 대비 {improvement:+.3f}밖에 개선하지 못했다 — 이 진단이 미리 "
            f"정한 '뚜렷한 개선' 기준({MINIMUM_MEANINGFUL_IMPROVEMENT:.2f}) 미달이다. Coverage "
            "기준(weight>=3.0·Context>=2·Frame>=2)은 전혀 완화하지 않았다 — 완화했다면 이 수치는 "
            "더 높게 나왔겠지만 그건 '기준을 낮춰 통과시킨 것'이지 '실제로 더 나은 질문 배분'이 "
            "아니다."
        )
        caveat = (
            "결론: 대안 A/B/C/C2 중 어느 것도 구현을 권고할 만큼 baseline을 개선하지 못했다 — "
            "'대안 C 구현 권고'가 아니라 **질문 Mapping/Planner 구조 재설계 필요**로 판단한다. "
            "근본 원인은 대안이 '무엇을 목표로 삼을지'만 바꿀 뿐, 후보 Blueprint 풀 자체(각 "
            "Context가 어떤 Trait에 대해 서로 다른 Frame·서로 다른 Context 조합을 실제로 제공할 "
            "수 있는지)가 Coverage의 Context>=2·Frame>=2 조건을 만족시킬 만큼 다양하지 않다는 "
            "것이다 — Planner 목표 재정의로는 존재하지 않는 후보를 만들어낼 수 없다."
        )
    else:
        chosen = best_alt
        implementation_recommended = True
        justification = (
            f"(상위5 비율+상위8 비율)/2 결합 점수 실측값은 {ranking_text} 순으로, {best_alt}가 "
            f"baseline 대비 {improvement:+.3f} 개선해 뚜렷한 개선 기준"
            f"({MINIMUM_MEANINGFUL_IMPROVEMENT:.2f}) 이상이다. Coverage 기준 자체는 전혀 완화하지 "
            "않았다."
        )
        caveat = (
            f"{best_alt}도 24개 전체를 SUFFICIENT로 만들지 못한다(애초에 그게 목표가 아니다) — "
            "상위 8개 밖의 Trait는 UNOBSERVED/LIMITED에 머무를 수 있고, 이는 의도된 결과다."
        )

    return {
        "chosen": chosen,
        "implementation_recommended": implementation_recommended,
        "justification": justification,
        "caveat": caveat,
        "minimum_meaningful_improvement_threshold": MINIMUM_MEANINGFUL_IMPROVEMENT,
        "best_alt_improvement_over_baseline": improvement,
        "combined_top5_top8_fraction_avg_by_alt": fractions,
        "top5_sufficient_fraction_avg_by_alt": top5,
        "top8_sufficient_fraction_avg_by_alt": top8,
    }


# ============================== 보고서 직렬화 ==============================


def _write_json_report(
    summary: dict[str, Any], comparison: dict[str, Any], recommendation: dict[str, Any],
    anchor_experiment: dict[str, Any], persona_keys_used: list[str],
) -> None:
    new_4persona_subset = {
        "baseline": [r for r in summary["baseline"] if r["scenario_key"] in PREVIOUS_ROUND_4_PERSONA_KEYS],
    }
    for alt in ("A", "B", "C", "C2"):
        new_4persona_subset[alt] = [
            r for r in summary["alternatives"][alt] if r["scenario_key"] in PREVIOUS_ROUND_4_PERSONA_KEYS
        ]

    def subset_avg(rows: list[dict[str, Any]], key: str) -> float:
        return sum(r[key] for r in rows) / len(rows) if rows else 0.0

    new_4persona_comparison = {
        "baseline": {
            "top5_fraction_avg": subset_avg(new_4persona_subset["baseline"], "top5_sufficient_fraction"),
            "top8_fraction_avg": subset_avg(new_4persona_subset["baseline"], "top8_sufficient_fraction"),
        },
    }
    for alt in ("A", "B", "C", "C2"):
        new_4persona_comparison[alt] = {
            "top5_fraction_avg": subset_avg(new_4persona_subset[alt], "top5_sufficient_fraction"),
            "top8_fraction_avg": subset_avg(new_4persona_subset[alt], "top8_sufficient_fraction"),
            "total_wasted_slots": sum(r["wasted_slots"]["total_wasted_slots"] for r in new_4persona_subset[alt]),
        }

    payload = {
        "persona_count": len(persona_keys_used),
        "persona_keys": persona_keys_used,
        "flow": (
            "실제 4+1 세션(관심도 15개 → 선호 4개 → Contrast 1개 → 최종 5개 → Context마다 "
            "Routing 1개·Anchor 1개·Seed 1개·Adaptive Tail 4~6개, 후보 소진 시에만 Backup). "
            "ENABLE_CONTEXT_SELECTION_4_PLUS_1이 네이티브로 배선돼 있어 실제 Endpoint를 "
            "우회 없이 그대로 호출한다."
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
        },
        "circularity_fix": (
            "이전 라운드(ca82f1f)의 대안 C는 top_traits를 Persona의 고정 trait_affinity_order"
            "(테스트 저자가 미리 정한 오라클, 답변 선택 정책과 동일한 값)에서 가져왔다 — 실제 "
            "시스템은 세션 시작 전에 그 값을 알 수 없다. 이번 C/C2는 그 시점까지 실제로 쌓인 "
            "evidence_ledger의 weight만으로 provisional_top_traits를 매 turn 다시 계산한다"
            "(`_provisional_top_traits`) — Persona의 숨은 선호도도, 세션 최종 결과도 참조하지 "
            "않는다."
        ),
        "anchor_diversification": (
            "이전 라운드는 모든 Context에서 알파벳 순 첫 Anchor만 썼다. 이번엔 Pack Context는 "
            "그 Anchor가 실제로 여는 Direct Probe 후보 Trait 집합과 Persona 관심 상위 8개의 "
            "교집합이 가장 큰 Anchor를 고르고, Legacy 3개 Context(Anchor가 후보 풀에 영향을 "
            "주지 않음)는 Persona별 안정 해시로 다양화했다. Coverage 최대/최소 Anchor 조합 및 "
            "동일 Context 내 Anchor 변화 비교는 별도 실험(anchor_sensitivity_experiment)으로 "
            "수행했다."
        ),
        "baseline_personas": summary["baseline"],
        "alternatives": summary["alternatives"],
        "comparison": comparison,
        "recommendation": recommendation,
        "anchor_sensitivity_experiment": anchor_experiment,
        "previous_round_4_persona_comparison": {
            "previous_round": PREVIOUS_ROUND_COMPARISON,
            "this_round_same_4_persona_subset": new_4persona_comparison,
            "note": (
                "이전 라운드 수치는 재실행하지 않고 그 라운드의 고정 스냅샷을 그대로 인용한다"
                "(이번 라운드는 Persona 정의·Anchor 선택·C의 정의 자체를 바꿔서, 재실행하면 "
                "'같은 조건 재현'이 아니라 '다른 조건의 새 측정'이 된다). 이전 C는 순환적 "
                "정의였다는 사실을 반드시 함께 읽어야 한다 — 숫자만 비교하면 '이번 C가 이전보다 "
                "나빠졌다'로 오해하기 쉽지만, 이전 수치는애초에 정당하게 얻어진 값이 아니다."
            ),
        },
        "note": (
            "생성 시각·메모리 값 없음 — byte-identical 재실행. data/reviews/는 이 스크립트가 "
            "읽지도 쓰지도 않는다(12개 Pack·공용 Adaptive Probe 승인은 전부 tempfile Fixture). "
            "Runtime Planner·Stop Condition·질문 Blueprint·Trait Mapping·Review JSON 어느 "
            "것도 수정하지 않았다."
        ),
    }
    JSON_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {JSON_OUTPUT_PATH}")


def _write_markdown_report(
    summary: dict[str, Any], comparison: dict[str, Any], recommendation: dict[str, Any],
    anchor_experiment: dict[str, Any], persona_keys_used: list[str],
) -> None:
    lines: list[str] = [
        "# Trait Evidence Coverage — Adaptive Target Planner Gap 진단 (v2, 9-Persona)",
        "",
        "브랜치 `a/planner-gap-9persona-diagnostics`. 별도 Worktree·별도 브랜치, 읽기 중심 "
        "Shadow 진단만 수행했다 — Runtime·Stop Condition·질문·Mapping·Review JSON은 전혀 "
        "바꾸지 않았다.",
        "",
        f"Persona {len(persona_keys_used)}개(이전 라운드 4개 → 이번 9개 전부): "
        f"{', '.join(persona_keys_used)}.",
        "",
        "## 0. 이전 라운드 대비 수정 사항",
        "",
        "1. **대안 C의 순환성 제거** — 이전엔 top_traits를 Persona의 고정 답변 선택 정책과 "
        "같은 오라클(trait_affinity_order)에서 가져왔다. 이번 C/C2는 그 시점까지 실제로 쌓인 "
        "증거(weight)만으로 매 turn 다시 계산한다.",
        "2. **Anchor 다양화** — 이전엔 모든 Context에서 알파벳 순 첫 Anchor만 썼다. 이번엔 "
        "Pack Context는 후보 Trait-Persona 관심사 교집합 기준, Legacy Context는 안정 해시 "
        "기준으로 고른다. Coverage 최대/최소 Anchor 비교는 별도 실험으로 수행했다(§5).",
        "3. **Persona 9개 전부 사용, 대안 C2 추가**(Exploration 예산 + 상위 Trait 집중 혼합).",
        "",
        "## 1. Baseline(실제 Planner) — Persona별 요약",
        "",
        "| Persona | Context | Trait 질문 | Backup | UNOBS·LIM·SUP·SUFF·CONF | 상위5 SUFF | 상위8 SUFF | 반복 최대 | 미관찰 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in summary["baseline"]:
        b = row["coverage_status_breakdown"]
        lines.append(
            f"| {row['scenario_label']} | {len(row['final_context_ids'])} | {row['trait_evidence_question_count']} | "
            f"{row['backup_used_count']} | {b['UNOBSERVED']}·{b['LIMITED']}·{b['SUPPORTED']}·"
            f"{b['SUFFICIENT']}·{b['CONFLICTED']} | {'✅' if row['top5_sufficient'] else '❌'} | "
            f"{'✅' if row['top8_sufficient'] else '❌'} | "
            f"{row['repetition_stats']['max_repeat_count_for_a_single_trait']} | "
            f"{row['unobserved_trait_count']} |"
        )

    lines += ["", "## 2. 대안 Baseline/A/B/C/C2/D 비교(9-Persona 평균)", ""]
    lines.append(
        "| 대안 | 상위5 비율 | 상위8 비율 | 결합 점수 | 총 Trait 질문 수 | 낭비 슬롯 | 고착 turn |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    lines.append(
        f"| Baseline | {comparison['baseline']['top5_sufficient_fraction_avg']:.3f} | "
        f"{comparison['baseline']['top8_sufficient_fraction_avg']:.3f} | "
        f"{recommendation['combined_top5_top8_fraction_avg_by_alt']['baseline']:.3f} | "
        f"{comparison['baseline']['total_trait_evidence_questions']} | (해당 없음) | (해당 없음) |"
    )
    lines.append(
        f"| D(SUPPORTED 중심 재표현) | {comparison['D_supported_headline']['top5_fraction_avg']:.3f} | "
        f"{comparison['D_supported_headline']['top8_fraction_avg']:.3f} | (해당 없음, SUPPORTED 기준) | "
        f"{comparison['D_supported_headline']['total_trait_evidence_questions']} | (재실행 없음) | (해당 없음) |"
    )
    for alt in ("A", "B", "C", "C2"):
        c = comparison[alt]
        lines.append(
            f"| {alt} | {c['top5_sufficient_fraction_avg']:.3f} | {c['top8_sufficient_fraction_avg']:.3f} | "
            f"{recommendation['combined_top5_top8_fraction_avg_by_alt'][alt]:.3f} | "
            f"{c['total_trait_evidence_questions']} | {c['total_wasted_slots']} | "
            f"{c['total_misidentified_trait_lockin_turns']} |"
        )

    lines += [
        "",
        "## 3. 이전 4-Persona 결과와 이번 9-Persona(및 같은 4-Persona 부분집합) 비교",
        "",
        f"- 이전 라운드(ca82f1f, 4-Persona, 순환적 C): baseline 결합 "
        f"{(PREVIOUS_ROUND_COMPARISON['baseline']['top5_fraction_avg'] + PREVIOUS_ROUND_COMPARISON['baseline']['top8_fraction_avg']) / 2:.3f}, "
        f"C(순환적) 결합 "
        f"{(PREVIOUS_ROUND_COMPARISON['C_circular']['top5_fraction_avg'] + PREVIOUS_ROUND_COMPARISON['C_circular']['top8_fraction_avg']) / 2:.3f}",
        f"- 이번 라운드 9-Persona 전체: baseline 결합 {recommendation['combined_top5_top8_fraction_avg_by_alt']['baseline']:.3f}, "
        f"C(비순환) 결합 {recommendation['combined_top5_top8_fraction_avg_by_alt']['C']:.3f}, "
        f"C2 결합 {recommendation['combined_top5_top8_fraction_avg_by_alt']['C2']:.3f}",
        "- 이전 C의 수치는 순환적 정의(오라클 사용)로 얻은 값이라 이번 C와 액면가로 비교하면 "
        "안 된다 — 위 §0-1 참고. JSON의 `previous_round_4_persona_comparison`에 같은 4개 "
        "Persona만 뽑은 이번 라운드 부분집합도 함께 남겼다.",
        "",
        "## 4. Anchor 민감도 실험(§5 — Coverage 최대/최소 Anchor 조합)",
        "",
        f"대상 Context: `{anchor_experiment['target_context']}` (Anchor별 후보 Trait 수: "
        f"{anchor_experiment['anchor_candidate_trait_counts']})",
        "",
        f"**실측 발견**: {anchor_experiment['finding']}",
        "",
        "| Anchor 변형 | 실제 Anchor | 상위5 비율 | 상위8 비율 | Trait 질문 수 |",
        "|---|---|---|---|---|",
    ]
    for variant_name, forced_anchor in anchor_experiment["variants"].items():
        r = anchor_experiment["results"][variant_name]
        lines.append(
            f"| {variant_name} | {forced_anchor} | {r['top5_sufficient_fraction']:.3f} | "
            f"{r['top8_sufficient_fraction']:.3f} | {r['trait_evidence_question_count']} |"
        )

    lines += ["", "## 5. 최종 판정", "", f"**구현 권고: {'예' if recommendation['implementation_recommended'] else '아니오'}**"]
    if recommendation["implementation_recommended"]:
        lines.append(f"**선택: {recommendation['chosen']}**")
    lines += ["", recommendation["justification"], "", recommendation["caveat"]]

    MD_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MD_OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {MD_OUTPUT_PATH}")


def main() -> None:
    scenarios = _persona_scenarios()
    persona_keys_used = [s.key for s in scenarios]
    summary = run_and_summarize(scenarios)
    comparison = _compare_alternatives(summary)
    recommendation = _recommendation(comparison)

    # Anchor 민감도 실험은 별도의 짧은 세션 3회만 추가로 돈다(9-Persona x 5-대안 본 실행과
    # 독립) — 첫 Persona를 대표로 쓴다(결정론적).
    saved_env = {
        k: os.environ.get(k)
        for k in ("ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", "ENABLE_CONTEXT_PACK_RUNTIME", "ENABLE_CONTEXT_SELECTION_4_PLUS_1")
    }
    fake_llm = _DeterministicFakeLLMClient()
    try:
        os.environ["ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES"] = "true"
        with tempfile.TemporaryDirectory(prefix="trait_coverage_planner_gap_anchor_fixture_") as tmp:
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
                anchor_experiment = run_anchor_sensitivity_experiment(scenarios[0], fixture_registry, fixture_runtime)
    finally:
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    _write_json_report(summary, comparison, recommendation, anchor_experiment, persona_keys_used)
    _write_markdown_report(summary, comparison, recommendation, anchor_experiment, persona_keys_used)


if __name__ == "__main__":
    main()
