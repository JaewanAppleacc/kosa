"""demo_user_01 — Vertical Slice용 고정 Persona + Hand-Calculated Fixture 예시.

C가 나머지 §26 Persona(창의·표현 중심, 인간·관계 중심 등)를 만들 때 그대로 따라 쓸 수 있는
템플릿이다. 8개 답변 모두 같은 Option Blueprint(5개 Role)를 재사용해서 일부러 5개 상태
(STRONG/MODERATE/LIMITED/INSUFFICIENT의 3가지 세부 사유)가 전부 나오도록 설계했다 —
Evaluation Harness가 상태 판정 로직 전체를 한 Fixture로 검증할 수 있게 하기 위함이다.

손계산 과정은 각 HandCalculatedTraitExpectation.calculation_notes에 적어뒀다.
"""

from __future__ import annotations

from src.schemas.persona import HandCalculatedFixture, HandCalculatedTraitExpectation, Persona, PersonaAnswer
from src.schemas.question import OptionBlueprint, OptionRole

# 8개 질문 전부가 재사용하는 단일 Blueprint. 실제로는 질문마다 다른 Blueprint를 쓸 수 있지만,
# 이 Fixture는 상태 판정 로직 자체를 검증하는 게 목적이라 하나로 고정해 단순화했다.
_SHARED_BLUEPRINT = OptionBlueprint(
    blueprint_id="problem_response_v1",
    roles=[
        OptionRole(role_id="cause_analysis", primary_trait_delta={"causal_analysis": 1}),
        OptionRole(role_id="strategy_change", primary_trait_delta={"change_adaptation": 1}),
        OptionRole(role_id="direct_trial", primary_trait_delta={"immediate_execution": 1}),
        OptionRole(role_id="external_research", primary_trait_delta={"information_comparison": 1}),
        OptionRole(role_id="ask_others", primary_trait_delta={"collaboration_preference": 1}),
    ],
)

BLUEPRINT_BY_QUESTION_ID: dict[str, OptionBlueprint] = {
    qid: _SHARED_BLUEPRINT
    for qid in [
        "game_seed_01",
        "game_tail_01",
        "game_tail_02",
        "media_seed_01",
        "media_tail_01",
        "school_life_seed_01",
        "school_life_tail_01",
        "school_life_tail_02",
    ]
}

DEMO_USER_01_PERSONA = Persona(
    persona_id="persona_demo_user_01_analysis_focused",
    user_id="demo_user_01",
    label="분석·구조화 중심",
    description="원인을 파고들고 상황이 바뀌면 유연하게 접근을 바꾸는 경향이 반복 관찰되는 페르소나",
    final_context_ids=["game", "media", "school_life"],
    answers=[
        PersonaAnswer(
            context_id="game",
            question_id="game_seed_01",
            question_frame_id="seed_frame",
            selected_option_id="game_seed_01_o1",
            selected_role_id="cause_analysis",
        ),
        PersonaAnswer(
            context_id="game",
            question_id="game_tail_01",
            question_frame_id="problem_check",
            selected_option_id="game_tail_01_o1",
            selected_role_id="cause_analysis",
        ),
        PersonaAnswer(
            context_id="game",
            question_id="game_tail_02",
            question_frame_id="unexpected_result",
            selected_option_id="game_tail_02_o2",
            selected_role_id="strategy_change",
        ),
        PersonaAnswer(
            context_id="media",
            question_id="media_seed_01",
            question_frame_id="seed_frame",
            selected_option_id="media_seed_01_o1",
            selected_role_id="cause_analysis",
        ),
        PersonaAnswer(
            context_id="media",
            question_id="media_tail_01",
            question_frame_id="new_tool",
            selected_option_id="media_tail_01_o2",
            selected_role_id="strategy_change",
        ),
        PersonaAnswer(
            context_id="school_life",
            question_id="school_life_seed_01",
            question_frame_id="seed_frame",
            selected_option_id="school_life_seed_01_o4",
            selected_role_id="external_research",
        ),
        PersonaAnswer(
            context_id="school_life",
            question_id="school_life_tail_01",
            question_frame_id="conflicting_opinions",
            selected_option_id="school_life_tail_01_o5",
            selected_role_id="ask_others",
        ),
        PersonaAnswer(
            context_id="school_life",
            question_id="school_life_tail_02",
            question_frame_id="team_role",
            selected_option_id="school_life_tail_02_o5",
            selected_role_id="ask_others",
        ),
    ],
)

DEMO_USER_01_FIXTURE = HandCalculatedFixture(
    fixture_id="fixture_demo_user_01_v1",
    persona_id=DEMO_USER_01_PERSONA.persona_id,
    trait_expectations=[
        HandCalculatedTraitExpectation(
            trait_id="causal_analysis",
            expected_support_count=3,
            expected_opportunity_count=8,
            expected_context_count=2,
            expected_distinct_frame_count=2,
            expected_state="STRONG",
            calculation_notes=(
                "game_seed_01, game_tail_01, media_seed_01 3번 선택(support=3). "
                "8개 질문 모두 이 Trait를 Option으로 제시했으므로 opportunity=8. "
                "선택된 3건의 Context={game, media}=2개, Frame={seed_frame, problem_check}=2개. "
                "support>=3, context>=min(2), frame>=2 → STRONG."
            ),
        ),
        HandCalculatedTraitExpectation(
            trait_id="change_adaptation",
            expected_support_count=2,
            expected_opportunity_count=8,
            expected_context_count=2,
            expected_distinct_frame_count=2,
            expected_state="MODERATE",
            calculation_notes=(
                "game_tail_02, media_tail_01 2번 선택(support=2). Context={game, media}=2개, "
                "Frame={unexpected_result, new_tool}=2개. support>=2, context>=min(2), frame>=2 "
                "→ 2026-08-20 팀 결정에 따라 MODERATE."
            ),
        ),
        HandCalculatedTraitExpectation(
            trait_id="collaboration_preference",
            expected_support_count=2,
            expected_opportunity_count=8,
            expected_context_count=1,
            expected_distinct_frame_count=2,
            expected_state="LIMITED",
            calculation_notes=(
                "school_life_tail_01, school_life_tail_02 2번 선택(support=2), 전부 school_life "
                "Context뿐이라 context_count=1 < min(2). Frame은 2개로 다양하지만 Context 다양성 "
                "미충족이라 MODERATE 자격이 안 되고 LIMITED로 강등."
            ),
        ),
        HandCalculatedTraitExpectation(
            trait_id="immediate_execution",
            expected_support_count=0,
            expected_opportunity_count=8,
            expected_context_count=0,
            expected_distinct_frame_count=0,
            expected_state="INSUFFICIENT",
            expected_insufficient_reason="NO_POSITIVE_EVIDENCE",
            calculation_notes=(
                "8개 질문 모두 direct_trial(immediate_execution) Option이 있었지만 한 번도 "
                "선택되지 않음. opportunity=8, support=0 → INSUFFICIENT / NO_POSITIVE_EVIDENCE."
            ),
        ),
        HandCalculatedTraitExpectation(
            trait_id="information_comparison",
            expected_support_count=1,
            expected_opportunity_count=8,
            expected_context_count=1,
            expected_distinct_frame_count=1,
            expected_state="INSUFFICIENT",
            expected_insufficient_reason="EVIDENCE_LIMITED",
            calculation_notes=(
                "school_life_seed_01에서 1번만 선택(support=1). opportunity=8. "
                "support_count==1이면 context/frame 다양성과 무관하게 INSUFFICIENT / "
                "EVIDENCE_LIMITED (§13 판정 순서 4번째, STRONG/MODERATE 검사보다 먼저 적용)."
            ),
        ),
        HandCalculatedTraitExpectation(
            trait_id="visual_expression",
            expected_support_count=0,
            expected_opportunity_count=0,
            expected_context_count=0,
            expected_distinct_frame_count=0,
            expected_state="INSUFFICIENT",
            expected_insufficient_reason="NOT_PROBED",
            calculation_notes=(
                "이 Blueprint의 5개 Role 중 어디에도 visual_expression이 없어 애초에 "
                "한 번도 제시되지 않음. opportunity=0 → INSUFFICIENT / NOT_PROBED."
            ),
        ),
    ],
    expected_top_major_relevance_order=[],  # Matching Engine 미구현 — 다음 Fixture 버전에서 채움
    notes=(
        "이 Persona는 5가지 상태(STRONG/MODERATE/LIMITED/NO_POSITIVE_EVIDENCE/"
        "EVIDENCE_LIMITED/NOT_PROBED)를 한 번에 검증하도록 의도적으로 설계했다. "
        "전공 매칭까지 검증하려면 대표 전공 Profile이 먼저 확정돼야 한다(다음 단계)."
    ),
)
