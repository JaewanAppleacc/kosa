"""Vertical Slice 꼬리질문용 Option Blueprint (설계안 §9). 사람이 미리 검토한
Role→Trait 대응표이며, LLM은 이 Role을 자연스러운 문장으로 표현할 뿐이다.

Frame(§7-4, "말투/상황")과 Blueprint(§9, "무엇을 묻는가")는 서로 다른 축이다 — 하나의
Blueprint를 여러 Frame과 짝지어 쓸 수 있다. Target Planner(§8)는 Frame과 목표 Trait를
각자 정하므로, 여기서는 "이 Trait를 다루는 Blueprint가 뭔가"로 역방향 조회한다
(`blueprint_for_target_trait`).

3개 Blueprint × Role 5개 = 15자리로 12개 Trait를 전부 최소 1번 다루도록 설계했다. 3자리가
남아서 causal_analysis·collaboration_preference·pattern_finding처럼 상황에 상관없이
자연스럽게 등장할 수 있는 Trait를 중복 배정했다(같은 Blueprint 안에서는 중복 없음 — §9-1).
"""

from __future__ import annotations

from src.schemas.question import OptionBlueprint, OptionRole

PROBLEM_RESPONSE_BLUEPRINT = OptionBlueprint(
    blueprint_id="problem_response_v1",
    roles=[
        OptionRole(role_id="cause_analysis", primary_trait_delta={"causal_analysis": 1}),
        OptionRole(role_id="strategy_change", primary_trait_delta={"change_adaptation": 1}),
        OptionRole(role_id="direct_trial", primary_trait_delta={"immediate_execution": 1}),
        OptionRole(role_id="external_research", primary_trait_delta={"information_comparison": 1}),
        OptionRole(role_id="ask_others", primary_trait_delta={"collaboration_preference": 1}),
    ],
)

EXPRESSION_AND_AUDIENCE_BLUEPRINT = OptionBlueprint(
    blueprint_id="expression_and_audience_v1",
    roles=[
        OptionRole(role_id="visual_representation", primary_trait_delta={"visual_expression": 1}),
        OptionRole(role_id="emotional_reading", primary_trait_delta={"emotional_interpretation": 1}),
        OptionRole(role_id="audience_focus", primary_trait_delta={"audience_response_prediction": 1}),
        OptionRole(role_id="opinion_balancing", primary_trait_delta={"opinion_mediation": 1}),
        OptionRole(role_id="pattern_seeking", primary_trait_delta={"pattern_finding": 1}),
    ],
)

PLANNING_AND_EXECUTION_BLUEPRINT = OptionBlueprint(
    blueprint_id="planning_and_execution_v1",
    roles=[
        OptionRole(role_id="advance_planning", primary_trait_delta={"planning": 1}),
        OptionRole(role_id="tool_first", primary_trait_delta={"tool_utilization": 1}),
        OptionRole(role_id="team_coordination", primary_trait_delta={"collaboration_preference": 1}),
        OptionRole(role_id="root_cause_check", primary_trait_delta={"causal_analysis": 1}),
        OptionRole(role_id="pattern_reference", primary_trait_delta={"pattern_finding": 1}),
    ],
)

TAIL_OPTION_BLUEPRINTS: list[OptionBlueprint] = [
    PROBLEM_RESPONSE_BLUEPRINT,
    EXPRESSION_AND_AUDIENCE_BLUEPRINT,
    PLANNING_AND_EXECUTION_BLUEPRINT,
]


def blueprint_for_target_trait(target_trait: str) -> OptionBlueprint:
    """target_trait을 Role 중 하나로 다루는 첫 Blueprint를 결정론적으로 반환한다
    (여러 Blueprint에 걸쳐 있으면 TAIL_OPTION_BLUEPRINTS 순서상 앞선 것을 쓴다)."""

    for blueprint in TAIL_OPTION_BLUEPRINTS:
        for role in blueprint.roles:
            if target_trait in role.primary_trait_delta:
                return blueprint
    raise KeyError(
        f"target_trait {target_trait!r}를 다루는 Blueprint가 없습니다 — "
        "TAIL_OPTION_BLUEPRINTS에 새 Role을 추가해야 합니다."
    )
