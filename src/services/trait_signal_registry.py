"""Sparse Trait Signal Registry — A 소유, 2026-08-23 Trait Ontology v2(1.5단계) §2/§4/§5/§6.

1.5단계 §2 수정 배경: 1단계는 role_id 하나만으로 Signal을 조회했다(`signals_for_role`).
role_id는 Blueprint/Seed/Backup 사이에서 우연히 재사용될 수 있는데("team_coordination"이
Tail Blueprint `planning_and_execution_v1`과 game Seed 양쪽에 등장), role_id 하나만 Key로
쓰면 두 자리가 우연히 같은 값을 넣어야만 충돌을 피할 수 있었다 — 구조적으로 안전하지 않다.
이제는 `TraitSignalRegistryKey(question_family_id, blueprint_id, role_id)` 복합 Key로
등록·조회한다. 같은 role_id라도 blueprint_id가 다르면 완전히 다른 등록이라, 값이 우연히
같은지 신경 쓸 필요가 없다(1단계의 "team_coordination 두 자리가 동일한 값인지 테스트로
확인" 방식은 이제 애초에 필요 없다 — 서로 다른 Key라 비교 대상 자체가 아니다).

기존 `OptionRole.primary_trait_delta`(legacy, dict[str, int])는 손대지 않는다 — 이
Registry는 "이 (질문 계열, Blueprint, Role)을 고른 답변이 실제로 어떤 Trait Signal
(PRIMARY+RELATED)을 발생시키는가"를 서버 내부에서만 조회하는 별도 표다(1단계 지시서
§5 "질문 ID·Role ID 기반 서버 내부 Mapping"). API 공개 Schema(FinalizedOption 등)에는
이 표의 내용이 전혀 노출되지 않는다.

LLM은 이 표를 만들지도, 참조해서 값을 바꾸지도 않는다 — 전부 검토된(사람이 직접 작성한)
고정 Mapping이다. EXACT_BLUEPRINT PRIMARY는 기존 legacy `primary_trait_delta`와 항상 같은
Trait·값(weight=1.0)이다(중복 계산 방지를 위해 legacy와 다른 값을 절대 넣지 않는다). RELATED는
실제 질문 문구·다음 확인(next_probe)에서 근거를 찾을 수 있는 경우에만 보수적으로 추가했다
— 대부분의 Role은 RELATED가 아예 없다.

1.5단계 §4 수정: Registry에 없는 (family, blueprint_id, role_id) 조합은 더 이상 조용히
빈 목록을 반환하지 않는다 — `resolve_trait_signals()`가 그 자리에서 legacy
`primary_trait_delta`를 PRIMARY Signal로 변환하는 LEGACY_PRIMARY_ADAPTER로 넘어간다.
"정상 질문인데 v2 Signal이 하나도 없는" 경로 자체를 없애는 게 목적이다.
"""

from __future__ import annotations

from pydantic import ValidationError

from src.data.questions.tail_option_blueprints import TAIL_OPTION_BLUEPRINTS
from src.data.questions.trait_v2_direct_probe_blueprints import V2_DIRECT_PROBE_BLUEPRINTS
from src.data.questions.vertical_slice_backup_questions import VERTICAL_SLICE_BACKUP_QUESTIONS
from src.data.questions.vertical_slice_seed_questions import VERTICAL_SLICE_SEED_QUESTIONS
from src.schemas.question import seed_question_to_blueprint
from src.schemas.trait_signal import (
    PRIMARY_WEIGHT,
    QuestionFamilyId,
    TraitSignal,
    TraitSignalRegistryKey,
    TraitSignalResolution,
)


class TraitSignalRegistryError(ValueError):
    """Registry 등록 자체가 잘못됐을 때(중복 Key, 실제 Blueprint에 없는 role_id 등록
    시도) 또는 §4 Sparse Signal 규칙을 어길 때, 또는 알려지지 않은 Trait/Concept id를
    참조할 때."""


_REGISTRY: dict[TraitSignalRegistryKey, tuple[TraitSignal, ...]] = {}


def _register(
    question_family_id: QuestionFamilyId,
    blueprint_id: str,
    role_signals: dict[str, list[TraitSignal]],
    *,
    known_role_ids: set[str],
) -> None:
    """Key 중복은 즉시 오류로 막는다(Fail-Fast) — 예전처럼 여러 dict를 `**`로 병합해
    나중 값이 앞 값을 조용히 덮어쓰는 경로 자체를 없앤다. 실제 Blueprint/Seed/Backup
    구조에 없는 role_id를 등록하려 하면(오타 등) 그 자리에서 막는다."""

    unknown_roles = sorted(set(role_signals) - known_role_ids)
    if unknown_roles:
        raise TraitSignalRegistryError(
            f"{question_family_id}/{blueprint_id}: 실제 구조에 없는 role_id를 등록하려 했다: "
            f"{unknown_roles} (실제 role_id: {sorted(known_role_ids)})"
        )
    for role_id, signals in role_signals.items():
        key = TraitSignalRegistryKey(
            question_family_id=question_family_id, blueprint_id=blueprint_id, role_id=role_id
        )
        if key in _REGISTRY:
            raise TraitSignalRegistryError(f"중복 등록(Key 충돌): {key!r}")
        _REGISTRY[key] = tuple(signals)


# --- Tail Option Blueprint 3개 × Role 5개 ---

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

for _blueprint, _signals in (
    (TAIL_OPTION_BLUEPRINTS[0], _PROBLEM_RESPONSE_SIGNALS),
    (TAIL_OPTION_BLUEPRINTS[1], _EXPRESSION_AND_AUDIENCE_SIGNALS),
    (TAIL_OPTION_BLUEPRINTS[2], _PLANNING_AND_EXECUTION_SIGNALS),
):
    _register(
        "tail_blueprint",
        _blueprint.blueprint_id,
        _signals,
        known_role_ids={r.role_id for r in _blueprint.roles},
    )


# --- Seed Question 3개 × Role 5개 ---

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
    "team_coordination": [
        TraitSignal(trait_id="collaboration_preference", signal_role="PRIMARY", weight=1.0),
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

for _seed, _signals in (
    (VERTICAL_SLICE_SEED_QUESTIONS["game"], _GAME_SEED_SIGNALS),
    (VERTICAL_SLICE_SEED_QUESTIONS["media"], _MEDIA_SEED_SIGNALS),
    (VERTICAL_SLICE_SEED_QUESTIONS["school_life"], _SCHOOL_LIFE_SEED_SIGNALS),
):
    _seed_blueprint = seed_question_to_blueprint(_seed)
    _register(
        "seed",
        _seed_blueprint.blueprint_id,
        _signals,
        known_role_ids={r.role_id for r in _seed_blueprint.roles},
    )


# --- Backup Question 6개 × Role 5개 ---
#
# 1.5단계 §2/§4 신규: 1단계에서는 Backup Question 자체가 Registry에 전혀 등록돼 있지
# 않았다 — role_id가 등록 안 됐으므로 LLM 연동 상태에서 재생성·Quality Gate가 모두
# 실패해 Backup으로 전환되면 v2 Signal이 하나도 안 남았다(§1 감사 결과 3번째 원인).
# 여기 RELATED Signal은 전부 이미 검토된 기존 규칙("이 PRIMARY Trait에는 이 RELATED
# Trait/Concept이 근거가 있다")을 그대로 재적용한 것이다 — 새로운 판단을 추가하지
# 않는다(1단계 §16 금지 "근거 없는 Related Signal 추가"를 지킨다). 아래 표는 그
# 재사용 규칙을 그대로 나열한다:
#   causal_analysis PRIMARY      → systems_thinking RELATED(whole_system_view)
#   change_adaptation PRIMARY    → novelty_seeking RELATED(trying_new_approach_on_own)
#   immediate_execution PRIMARY  → uncertainty_tolerance RELATED(proceeding_without_certainty)
#   information_comparison PRIMARY → detail_orientation RELATED(comparing_details_across_sources)
#   visual_expression PRIMARY    → aesthetic_sensitivity RELATED(visual_aesthetic_response)
#   opinion_mediation PRIMARY    → opinion_expression RELATED(assertive_mediation)
#   pattern_finding PRIMARY      → systems_thinking RELATED(pattern_in_structure)
#   planning PRIMARY             → persistence_completion RELATED(plan_through_to_completion)
#   collaboration_preference / emotional_interpretation / audience_response_prediction /
#   tool_utilization PRIMARY     → RELATED 없음(Tail·Seed에서도 이 4개 Trait에는 RELATED를
#                                  추가한 적이 없다 — 근거 없이 새로 만들지 않는다).

_GAME_BACKUP_01_SIGNALS: dict[str, list[TraitSignal]] = {
    "rule_reasoning": [
        TraitSignal(trait_id="causal_analysis", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="systems_thinking", signal_role="RELATED", weight=0.33,
            related_concept_ids=["whole_system_view"],
        ),
    ],
    "trial_and_error": [TraitSignal(trait_id="immediate_execution", signal_role="PRIMARY", weight=1.0)],
    "guide_comparison": [
        TraitSignal(trait_id="information_comparison", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="detail_orientation", signal_role="RELATED", weight=0.33,
            related_concept_ids=["comparing_details_across_sources"],
        ),
    ],
    "role_split": [TraitSignal(trait_id="collaboration_preference", signal_role="PRIMARY", weight=1.0)],
    "pattern_watch": [
        TraitSignal(trait_id="pattern_finding", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="systems_thinking", signal_role="RELATED", weight=0.33,
            related_concept_ids=["pattern_in_structure"],
        ),
    ],
}

_GAME_BACKUP_02_SIGNALS: dict[str, list[TraitSignal]] = {
    "screen_review": [
        TraitSignal(trait_id="visual_expression", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="aesthetic_sensitivity", signal_role="RELATED", weight=0.33,
            related_concept_ids=["visual_aesthetic_response"],
        ),
    ],
    "reaction_check": [TraitSignal(trait_id="audience_response_prediction", signal_role="PRIMARY", weight=1.0)],
    "strategy_switch": [
        TraitSignal(trait_id="change_adaptation", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="novelty_seeking", signal_role="RELATED", weight=0.33,
            related_concept_ids=["trying_new_approach_on_own"],
        ),
    ],
    "plan_ahead": [
        TraitSignal(trait_id="planning", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="persistence_completion", signal_role="RELATED", weight=0.33,
            related_concept_ids=["plan_through_to_completion"],
        ),
    ],
    "new_tool_first": [TraitSignal(trait_id="tool_utilization", signal_role="PRIMARY", weight=1.0)],
}

_MEDIA_BACKUP_01_SIGNALS: dict[str, list[TraitSignal]] = {
    "reason_for_split": [
        TraitSignal(trait_id="causal_analysis", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="systems_thinking", signal_role="RELATED", weight=0.33,
            related_concept_ids=["whole_system_view"],
        ),
    ],
    "opinion_bridge": [
        TraitSignal(trait_id="opinion_mediation", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="opinion_expression", signal_role="RELATED", weight=0.33,
            related_concept_ids=["assertive_mediation"],
        ),
    ],
    "comment_reading": [TraitSignal(trait_id="emotional_interpretation", signal_role="PRIMARY", weight=1.0)],
    "cross_content_compare": [
        TraitSignal(trait_id="information_comparison", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="detail_orientation", signal_role="RELATED", weight=0.33,
            related_concept_ids=["comparing_details_across_sources"],
        ),
    ],
    "predict_next_reaction": [
        TraitSignal(trait_id="audience_response_prediction", signal_role="PRIMARY", weight=1.0)
    ],
}

_MEDIA_BACKUP_02_SIGNALS: dict[str, list[TraitSignal]] = {
    "sequence_plan": [
        TraitSignal(trait_id="planning", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="persistence_completion", signal_role="RELATED", weight=0.33,
            related_concept_ids=["plan_through_to_completion"],
        ),
    ],
    "visual_layout": [
        TraitSignal(trait_id="visual_expression", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="aesthetic_sensitivity", signal_role="RELATED", weight=0.33,
            related_concept_ids=["visual_aesthetic_response"],
        ),
    ],
    "new_editing_tool": [TraitSignal(trait_id="tool_utilization", signal_role="PRIMARY", weight=1.0)],
    "reference_pattern": [
        TraitSignal(trait_id="pattern_finding", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="systems_thinking", signal_role="RELATED", weight=0.33,
            related_concept_ids=["pattern_in_structure"],
        ),
    ],
    "team_split": [TraitSignal(trait_id="collaboration_preference", signal_role="PRIMARY", weight=1.0)],
}

_SCHOOL_LIFE_BACKUP_01_SIGNALS: dict[str, list[TraitSignal]] = {
    "disagreement_reason": [
        TraitSignal(trait_id="causal_analysis", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="systems_thinking", signal_role="RELATED", weight=0.33,
            related_concept_ids=["whole_system_view"],
        ),
    ],
    "find_middle_ground": [
        TraitSignal(trait_id="opinion_mediation", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="opinion_expression", signal_role="RELATED", weight=0.33,
            related_concept_ids=["assertive_mediation"],
        ),
    ],
    "other_group_compare": [
        TraitSignal(trait_id="information_comparison", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="detail_orientation", signal_role="RELATED", weight=0.33,
            related_concept_ids=["comparing_details_across_sources"],
        ),
    ],
    "just_start": [TraitSignal(trait_id="immediate_execution", signal_role="PRIMARY", weight=1.0)],
    "feelings_care": [TraitSignal(trait_id="emotional_interpretation", signal_role="PRIMARY", weight=1.0)],
}

_SCHOOL_LIFE_BACKUP_02_SIGNALS: dict[str, list[TraitSignal]] = {
    "schedule_plan": [
        TraitSignal(trait_id="planning", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="persistence_completion", signal_role="RELATED", weight=0.33,
            related_concept_ids=["plan_through_to_completion"],
        ),
    ],
    "prepare_tools": [TraitSignal(trait_id="tool_utilization", signal_role="PRIMARY", weight=1.0)],
    "recall_pattern": [
        TraitSignal(trait_id="pattern_finding", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="systems_thinking", signal_role="RELATED", weight=0.33,
            related_concept_ids=["pattern_in_structure"],
        ),
    ],
    "adjust_on_change": [
        TraitSignal(trait_id="change_adaptation", signal_role="PRIMARY", weight=1.0),
        TraitSignal(
            trait_id="novelty_seeking", signal_role="RELATED", weight=0.33,
            related_concept_ids=["trying_new_approach_on_own"],
        ),
    ],
    "anticipate_reaction": [
        TraitSignal(trait_id="audience_response_prediction", signal_role="PRIMARY", weight=1.0)
    ],
}

_BACKUP_SIGNALS_BY_QUESTION_ID: dict[str, dict[str, list[TraitSignal]]] = {
    "game_backup_01": _GAME_BACKUP_01_SIGNALS,
    "game_backup_02": _GAME_BACKUP_02_SIGNALS,
    "media_backup_01": _MEDIA_BACKUP_01_SIGNALS,
    "media_backup_02": _MEDIA_BACKUP_02_SIGNALS,
    "school_life_backup_01": _SCHOOL_LIFE_BACKUP_01_SIGNALS,
    "school_life_backup_02": _SCHOOL_LIFE_BACKUP_02_SIGNALS,
}

for _backup_list in VERTICAL_SLICE_BACKUP_QUESTIONS.values():
    for _backup in _backup_list:
        _register(
            "backup",
            _backup.question_id,
            _BACKUP_SIGNALS_BY_QUESTION_ID[_backup.question_id],
            known_role_ids={o.role_id for o in _backup.options},
        )


# --- V2 Direct Probe Blueprint 14개 × Role 5개 ---
#
# 2026-08-24 2단계 §5/§8/§13: 5개 Role 전부 자기 Blueprint의 `primary_trait_delta`와
# 정확히 같은 PRIMARY Signal을 그대로 등록한다(Target Role뿐 아니라 나머지 4개 Role도
# 등록한다 — Direct Probe는 어떤 선택지를 답해도 EXACT_BLUEPRINT여야 하고
# LEGACY_PRIMARY_ADAPTER에 의존하면 안 된다, §13). RELATED Signal은 추가하지 않는다 —
# 근거 없이 Target Trait를 여러 선택지에 걸치게 만들지 않기 위해서다(§8).
for _v2_bp in V2_DIRECT_PROBE_BLUEPRINTS:
    _v2_role_signals = {
        role.role_id: [
            TraitSignal(trait_id=next(iter(role.primary_trait_delta)), signal_role="PRIMARY", weight=1.0)
        ]
        for role in _v2_bp.blueprint.roles
    }
    _register(
        "v2_direct_probe",
        _v2_bp.blueprint.blueprint_id,
        _v2_role_signals,
        known_role_ids={r.role_id for r in _v2_bp.blueprint.roles},
    )


def validate_role_signals(
    role_id: str,
    signals: list[TraitSignal],
    *,
    known_trait_ids: set[str],
    known_concept_ids: set[str],
) -> None:
    """1단계 §4 Sparse Signal 검증 규칙 전체. Registry 정의 직후(모듈 import 시점)와
    실제 운영 중(Ontology/Concept Registry가 나중에 바뀔 수 있으므로) 둘 다에서 호출할
    수 있게 순수 함수로 둔다."""

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
            raise TraitSignalRegistryError(f"{role_id}/{signal.trait_id}: PRIMARY Signal에는 related_concept_ids를 두지 않는다")


def validate_full_registry(known_trait_ids: set[str], known_concept_ids: set[str]) -> None:
    for key, signals in _REGISTRY.items():
        validate_role_signals(
            key.role_id, list(signals), known_trait_ids=known_trait_ids, known_concept_ids=known_concept_ids
        )


def all_registrations() -> dict[TraitSignalRegistryKey, tuple[TraitSignal, ...]]:
    """읽기 전용 열람용(Coverage 계산 등) — 방어적으로 복사해서 반환한다."""

    return {key: tuple(s.model_copy(deep=True) for s in signals) for key, signals in _REGISTRY.items()}


def resolve_trait_signals(
    *,
    question_family_id: str,
    blueprint_id: str,
    role_id: str,
    legacy_primary_trait_delta: dict[str, int],
    is_resolution_question: bool,
) -> TraitSignalResolution:
    """1.5단계 §2 권장 조회 인터페이스. 정상 질문(Conflict Resolution이 아닌 질문)은
    절대 signals=[]로 끝나지 않는다 — Registry에 정확히 일치하는 등록이 있으면
    EXACT_BLUEPRINT, 없으면 legacy `primary_trait_delta`를 그대로 PRIMARY Signal로
    바꾸는 LEGACY_PRIMARY_ADAPTER로 넘어간다. Legacy Adapter는 RELATED Signal을
    추측해서 추가하지 않는다 — 근거 없는 Related Signal 추가 금지(1단계 §16)를 그대로
    지킨다. `legacy_primary_trait_delta`는 클라이언트가 보낸 값이 아니라 서버가 이미
    Pydantic 검증을 통과시킨 selected_option.primary_trait_delta만 받는다(클라이언트가
    보낸 Trait ID·weight는 신뢰하지 않는다)."""

    if is_resolution_question:
        return TraitSignalResolution(signals=[], mapping_source="NONE_CONFLICT_RESOLUTION")

    try:
        key: TraitSignalRegistryKey | None = TraitSignalRegistryKey(
            question_family_id=question_family_id, blueprint_id=blueprint_id, role_id=role_id
        )
    except ValidationError:
        key = None

    registered = _REGISTRY.get(key) if key is not None else None
    if registered is not None:
        return TraitSignalResolution(
            signals=[s.model_copy(deep=True) for s in registered], mapping_source="EXACT_BLUEPRINT"
        )

    primary_signals = [
        TraitSignal(trait_id=trait_id, signal_role="PRIMARY", weight=PRIMARY_WEIGHT)
        for trait_id in legacy_primary_trait_delta
    ]
    return TraitSignalResolution(signals=primary_signals, mapping_source="LEGACY_PRIMARY_ADAPTER")
