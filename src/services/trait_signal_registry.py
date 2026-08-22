"""Sparse Trait Signal Registry — A 소유, 2026-08-31 Trait Ontology v2(1단계) §4/§5/§6.

기존 `OptionRole.primary_trait_delta`(legacy, dict[str, int])는 손대지 않는다 — 이
Registry는 role_id를 키로 "이 Role을 고른 답변이 실제로 어떤 Trait Signal(PRIMARY+
RELATED)을 발생시키는가"를 서버 내부에서만 조회하는 별도 표다(지시서 §5 "질문 ID·
Role ID 기반 서버 내부 Mapping"). API 공개 Schema(FinalizedOption 등)에는 이 표의
내용이 전혀 노출되지 않는다 — `_evidence_update()`가 EvidenceRecord를 만들 때 이
Registry로 role_id를 조회해 `applied_trait_signals_v2`에만 채운다.

LLM은 이 표를 만들지도, 참조해서 값을 바꾸지도 않는다 — 전부 검토된(사람이 직접 작성한)
고정 Mapping이다. PRIMARY는 기존 legacy `primary_trait_delta`와 항상 같은 Trait·값
(weight=1.0)이다(중복 계산 방지를 위해 legacy와 다른 값을 절대 넣지 않는다 — 이
Registry의 PRIMARY는 "같은 사실을 새 Schema로 다시 표현한 것"이지 "새로운 판단"이 아니다).
RELATED는 실제 질문 문구·다음 확인(next_probe)에서 근거를 찾을 수 있는 경우에만
보수적으로 추가했다(§4 "실제로는 관련 Trait가 1~2개뿐인 선택지라면 억지로 3개 이상
만들지 마세요") — 대부분의 Role은 RELATED가 아예 없다.
"""

from __future__ import annotations

from src.schemas.trait_signal import TraitSignal

# --- Tail Option Blueprint 15 Role ---

_PROBLEM_RESPONSE_SIGNALS: dict[str, list[TraitSignal]] = {
    "cause_analysis": [
        TraitSignal(trait_id="causal_analysis", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="systems_thinking", signal_role="RELATED", weight=0.33,
            related_concept_ids=["whole_system_view"],
        ),
    ],
    "strategy_change": [
        TraitSignal(trait_id="change_adaptation", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="novelty_seeking", signal_role="RELATED", weight=0.33,
            related_concept_ids=["trying_new_approach_on_own"],
        ),
    ],
    "direct_trial": [
        TraitSignal(trait_id="immediate_execution", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="uncertainty_tolerance", signal_role="RELATED", weight=0.33,
            related_concept_ids=["proceeding_without_certainty"],
        ),
    ],
    "external_research": [
        TraitSignal(trait_id="information_comparison", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="detail_orientation", signal_role="RELATED", weight=0.33,
            related_concept_ids=["comparing_details_across_sources"],
        ),
    ],
    "ask_others": [
        TraitSignal(trait_id="collaboration_preference", signal_role="PRIMARY", weight=1.0),
    ],
}

_EXPRESSION_AND_AUDIENCE_SIGNALS: dict[str, list[TraitSignal]] = {
    "visual_representation": [
        TraitSignal(trait_id="visual_expression", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="aesthetic_sensitivity", signal_role="RELATED", weight=0.33,
            related_concept_ids=["visual_aesthetic_response"],
        ),
    ],
    "emotional_reading": [
        TraitSignal(trait_id="emotional_interpretation", signal_role="PRIMARY", weight=1.0),
    ],
    "audience_focus": [
        TraitSignal(trait_id="audience_response_prediction", signal_role="PRIMARY", weight=1.0),
    ],
    "opinion_balancing": [
        TraitSignal(trait_id="opinion_mediation", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="opinion_expression", signal_role="RELATED", weight=0.33,
            related_concept_ids=["assertive_mediation"],
        ),
    ],
    "pattern_seeking": [
        TraitSignal(trait_id="pattern_finding", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="systems_thinking", signal_role="RELATED", weight=0.33,
            related_concept_ids=["pattern_in_structure"],
        ),
    ],
}

_PLANNING_AND_EXECUTION_SIGNALS: dict[str, list[TraitSignal]] = {
    "advance_planning": [
        TraitSignal(trait_id="planning", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="persistence_completion", signal_role="RELATED", weight=0.33,
            related_concept_ids=["plan_through_to_completion"],
        ),
    ],
    "tool_first": [
        TraitSignal(trait_id="tool_utilization", signal_role="PRIMARY", weight=1.0),
    ],
    "team_coordination": [
        # 2026-08-31: 이 role_id는 vertical_slice_seed_questions.py(GAME_SEED_01)에도
        # 같은 이름으로 등장한다 — 둘 다 legacy에서 collaboration_preference 하나로만
        # 매핑돼 있어(동일 Trait) 이 Registry도 두 자리에 완전히 동일한 값을 넣는다
        # (role_id를 Registry Key로 쓰는 전제 — "역할이 같으면 Signal도 같다"가 깨지지
        # 않는지 tests/test_trait_signal_registry.py가 확인한다).
        TraitSignal(trait_id="collaboration_preference", signal_role="PRIMARY", weight=1.0),
    ],
    "root_cause_check": [
        TraitSignal(trait_id="causal_analysis", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="systems_thinking", signal_role="RELATED", weight=0.33,
            related_concept_ids=["whole_system_view"],
        ),
    ],
    "pattern_reference": [
        TraitSignal(trait_id="pattern_finding", signal_role="PRIMARY", weight=1.0),
    ],
}

# --- Seed Question 15 Role ---

_GAME_SEED_SIGNALS: dict[str, list[TraitSignal]] = {
    "strategy_analysis": [
        TraitSignal(trait_id="causal_analysis", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="systems_thinking", signal_role="RELATED", weight=0.33,
            related_concept_ids=["whole_system_view"],
        ),
    ],
    "quick_execution": [
        TraitSignal(trait_id="immediate_execution", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="uncertainty_tolerance", signal_role="RELATED", weight=0.33,
            related_concept_ids=["proceeding_without_certainty"],
        ),
    ],
    "pattern_recognition": [
        TraitSignal(trait_id="pattern_finding", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="systems_thinking", signal_role="RELATED", weight=0.33,
            related_concept_ids=["pattern_in_structure"],
        ),
    ],
    "tool_mastery": [
        TraitSignal(trait_id="tool_utilization", signal_role="PRIMARY", weight=1.0),
    ],
}

_MEDIA_SEED_SIGNALS: dict[str, list[TraitSignal]] = {
    "structure_analysis": [
        TraitSignal(trait_id="causal_analysis", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="systems_thinking", signal_role="RELATED", weight=0.33,
            related_concept_ids=["whole_system_view"],
        ),
    ],
    "creative_making": [
        TraitSignal(trait_id="visual_expression", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="aesthetic_sensitivity", signal_role="RELATED", weight=0.33,
            related_concept_ids=["visual_aesthetic_response"],
        ),
    ],
    "audience_reaction": [
        TraitSignal(trait_id="audience_response_prediction", signal_role="PRIMARY", weight=1.0),
    ],
    "character_empathy": [
        TraitSignal(trait_id="emotional_interpretation", signal_role="PRIMARY", weight=1.0),
    ],
    "trend_research": [
        TraitSignal(trait_id="information_comparison", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="detail_orientation", signal_role="RELATED", weight=0.33,
            related_concept_ids=["comparing_details_across_sources"],
        ),
    ],
}

_SCHOOL_LIFE_SEED_SIGNALS: dict[str, list[TraitSignal]] = {
    "task_planning": [
        TraitSignal(trait_id="planning", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="persistence_completion", signal_role="RELATED", weight=0.33,
            related_concept_ids=["plan_through_to_completion"],
        ),
    ],
    "team_project": [
        TraitSignal(trait_id="collaboration_preference", signal_role="PRIMARY", weight=1.0),
    ],
    "conflict_mediation": [
        TraitSignal(trait_id="opinion_mediation", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="opinion_expression", signal_role="RELATED", weight=0.33,
            related_concept_ids=["assertive_mediation"],
        ),
    ],
    "peer_understanding": [
        TraitSignal(trait_id="emotional_interpretation", signal_role="PRIMARY", weight=1.0),
    ],
    "adapting_change": [
        TraitSignal(trait_id="change_adaptation", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="novelty_seeking", signal_role="RELATED", weight=0.33,
            related_concept_ids=["trying_new_approach_on_own"],
        ),
    ],
}

ROLE_ID_TO_TRAIT_SIGNALS: dict[str, list[TraitSignal]] = {
    **_PROBLEM_RESPONSE_SIGNALS,
    **_EXPRESSION_AND_AUDIENCE_SIGNALS,
    **_PLANNING_AND_EXECUTION_SIGNALS,
    **_GAME_SEED_SIGNALS,
    **_MEDIA_SEED_SIGNALS,
    **_SCHOOL_LIFE_SEED_SIGNALS,
}


class TraitSignalRegistryError(ValueError):
    """Registry 자체가 §4 Sparse Signal 규칙을 어길 때(role_id별 검증) 또는 알려지지
    않은 Trait/Concept id를 참조할 때."""


def validate_role_signals(
    role_id: str,
    signals: list[TraitSignal],
    *,
    known_trait_ids: set[str],
    known_concept_ids: set[str],
) -> None:
    """§4 Sparse Signal 검증 규칙 전체. Registry 정의 직후(모듈 import 시점)와 실제
    운영 중(Ontology/Concept Registry가 나중에 바뀔 수 있으므로) 둘 다에서 호출할 수
    있게 순수 함수로 둔다."""

    primary = [s for s in signals if s.signal_role == "PRIMARY"]
    related = [s for s in signals if s.signal_role == "RELATED"]

    if not (1 <= len(primary) <= 2):
        raise TraitSignalRegistryError(f"{role_id}: PRIMARY Signal은 1~2개여야 한다(got {len(primary)})")
    if len(related) > 3:
        raise TraitSignalRegistryError(f"{role_id}: RELATED Signal은 최대 3개여야 한다(got {len(related)})")
    if len(signals) > 5:
        raise TraitSignalRegistryError(f"{role_id}: 전체 Signal은 최대 5개여야 한다(got {len(signals)})")

    trait_ids = [s.trait_id for s in signals]
    if len(set(trait_ids)) != len(trait_ids):
        raise TraitSignalRegistryError(f"{role_id}: 같은 Trait가 여러 Signal에 중복 등장할 수 없다: {trait_ids}")

    unknown_traits = sorted({t for t in trait_ids if t not in known_trait_ids})
    if unknown_traits:
        raise TraitSignalRegistryError(f"{role_id}: 등록되지 않은 Trait id: {unknown_traits}")

    for signal in signals:
        unknown_concepts = sorted(set(signal.related_concept_ids) - known_concept_ids)
        if unknown_concepts:
            raise TraitSignalRegistryError(
                f"{role_id}/{signal.trait_id}: 등록되지 않은 Related Concept id: {unknown_concepts}"
            )
        if signal.signal_role == "PRIMARY" and signal.related_concept_ids:
            # PRIMARY는 legacy primary_trait_delta와 그대로 대응하는 값이라 Concept 연결이
            # 필요 없다 — Concept은 RELATED Signal의 근거(왜 이 Trait도 살짝 걸리는지)를
            # 설명하는 용도다.
            raise TraitSignalRegistryError(f"{role_id}/{signal.trait_id}: PRIMARY Signal에는 related_concept_ids를 두지 않는다")


def validate_full_registry(known_trait_ids: set[str], known_concept_ids: set[str]) -> None:
    for role_id, signals in ROLE_ID_TO_TRAIT_SIGNALS.items():
        validate_role_signals(
            role_id, signals, known_trait_ids=known_trait_ids, known_concept_ids=known_concept_ids
        )


def signals_for_role(role_id: str) -> list[TraitSignal]:
    """등록되지 않은 role_id(예: Conflict Resolution 확인 질문의 role_id)는 조용히 빈
    목록을 반환한다 — v2 Signal은 "있으면 풍부하게 기록"하는 보조 데이터이지, 없다고
    기존 흐름을 막는 필수 데이터가 아니다."""

    return list(ROLE_ID_TO_TRAIT_SIGNALS.get(role_id, []))
