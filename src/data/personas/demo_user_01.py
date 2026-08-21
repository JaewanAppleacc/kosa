"""demo_user_01 — Vertical Slice용 고정 Persona + Hand-Calculated Fixture 예시.

C가 나머지 §26 Persona(창의·표현 중심, 인간·관계 중심 등)를 만들 때 그대로 따라 쓸 수 있는
템플릿이다. Seed 3개(game_seed_01/media_seed_01/school_life_seed_01)는 실제 확정된
Seed Question(src/data/questions/vertical_slice_seed_questions.py)을 그대로 쓰고,
꼬리질문 6개는 아직 실제 Adaptive 질문 생성이 없어 시험용 공용 Blueprint를 재사용한다.

이 조합으로 5가지 상태(STRONG/MODERATE/LIMITED/INSUFFICIENT의 NO_POSITIVE_EVIDENCE·
EVIDENCE_LIMITED 2가지 세부 사유)가 전부 나오도록 설계했다.

**2026-08-21 갱신**: 실제 Seed Question 3개는 15개 선택지로 12개 Trait를 전부 최소 1번씩
"제시"한다(§6-6, 15개 선택지 vs 12개 Trait). 그 결과 이 Persona로는 opportunity_count=0인
Trait(INSUFFICIENT/NOT_PROBED)를 더 이상 재현할 수 없다 — Seed만으로 이미 모든 Trait가
"물어봄" 상태가 되기 때문이다. 이건 버그가 아니라 Seed 커버리지 설계가 의도한 결과다.
NOT_PROBED 케이스는 `tests/test_evidence_engine.py::test_insufficient_not_probed`가
Evidence Engine 단위 테스트 수준에서 계속 검증한다.

손계산 과정은 각 HandCalculatedTraitExpectation.calculation_notes에 적어뒀다.
"""

from __future__ import annotations

from src.data.questions.vertical_slice_seed_questions import (
    GAME_SEED_01,
    MEDIA_SEED_01,
    SCHOOL_LIFE_SEED_01,
)
from src.schemas.persona import HandCalculatedFixture, HandCalculatedTraitExpectation, Persona, PersonaAnswer
from src.schemas.question import OptionBlueprint, OptionRole, seed_question_to_blueprint

# 꼬리질문 6개가 재사용하는 시험용 공용 Blueprint. 실제 Adaptive 질문 생성(§10)이 아직
# 없어서 단순화한 것이며, 실제 LLM 연동이 붙으면 이 부분만 다시 계산하면 된다.
_TAIL_TEST_BLUEPRINT = OptionBlueprint(
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
    "game_seed_01": seed_question_to_blueprint(GAME_SEED_01),
    "media_seed_01": seed_question_to_blueprint(MEDIA_SEED_01),
    "school_life_seed_01": seed_question_to_blueprint(SCHOOL_LIFE_SEED_01),
    "game_tail_01": _TAIL_TEST_BLUEPRINT,
    "game_tail_02": _TAIL_TEST_BLUEPRINT,
    "media_tail_01": _TAIL_TEST_BLUEPRINT,
    "media_tail_02": _TAIL_TEST_BLUEPRINT,
    "school_life_tail_01": _TAIL_TEST_BLUEPRINT,
    "school_life_tail_02": _TAIL_TEST_BLUEPRINT,
}

DEMO_USER_01_PERSONA = Persona(
    persona_id="persona_demo_user_01_analysis_focused",
    user_id="demo_user_01",
    label="분석·구조화 중심",
    description="원인을 파고들고 상황이 바뀌면 유연하게 접근을 바꾸는 경향이 반복 관찰되는 페르소나",
    final_context_ids=["game", "media", "school_life"],
    answers=[
        # --- Seed 3개 (실제 확정 콘텐츠) ---
        PersonaAnswer(
            context_id="game",
            question_id="game_seed_01",
            question_frame_id="seed_frame",
            selected_option_id="game_seed_01_o1",
            selected_role_id="strategy_analysis",  # causal_analysis
        ),
        PersonaAnswer(
            context_id="media",
            question_id="media_seed_01",
            question_frame_id="seed_frame",
            selected_option_id="media_seed_01_o1",
            selected_role_id="structure_analysis",  # causal_analysis
        ),
        PersonaAnswer(
            context_id="school_life",
            question_id="school_life_seed_01",
            question_frame_id="seed_frame",
            selected_option_id="school_life_seed_01_o1",
            selected_role_id="task_planning",  # planning
        ),
        # --- 꼬리질문 6개 (시험용 공용 Blueprint) ---
        PersonaAnswer(
            context_id="game",
            question_id="game_tail_01",
            question_frame_id="problem_check",
            selected_option_id="game_tail_01_o1",
            selected_role_id="cause_analysis",  # causal_analysis
        ),
        PersonaAnswer(
            context_id="game",
            question_id="game_tail_02",
            question_frame_id="unexpected_result",
            selected_option_id="game_tail_02_o2",
            selected_role_id="strategy_change",  # change_adaptation
        ),
        PersonaAnswer(
            context_id="media",
            question_id="media_tail_01",
            question_frame_id="new_tool",
            selected_option_id="media_tail_01_o2",
            selected_role_id="strategy_change",  # change_adaptation
        ),
        PersonaAnswer(
            context_id="media",
            question_id="media_tail_02",
            question_frame_id="limited_time_priority",
            selected_option_id="media_tail_02_o4",
            selected_role_id="external_research",  # information_comparison
        ),
        PersonaAnswer(
            context_id="school_life",
            question_id="school_life_tail_01",
            question_frame_id="conflicting_opinions",
            selected_option_id="school_life_tail_01_o5",
            selected_role_id="ask_others",  # collaboration_preference
        ),
        PersonaAnswer(
            context_id="school_life",
            question_id="school_life_tail_02",
            question_frame_id="team_role",
            selected_option_id="school_life_tail_02_o5",
            selected_role_id="ask_others",  # collaboration_preference
        ),
    ],
)

DEMO_USER_01_FIXTURE = HandCalculatedFixture(
    fixture_id="fixture_demo_user_01_v2",
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
                "game_seed_01(strategy_analysis), game_tail_01(cause_analysis), "
                "media_seed_01(structure_analysis) 3번 선택(support=3). causal_analysis를 "
                "Option으로 제시한 질문: game_seed_01, game_tail_01, game_tail_02, "
                "media_seed_01, media_tail_01, media_tail_02, school_life_tail_01, "
                "school_life_tail_02 = 8개(school_life_seed_01만 이 Trait가 없음) → "
                "opportunity=8. 선택된 3건의 Context={game, media}=2개, "
                "Frame={seed_frame(게임), problem_check}=2개(media_seed_01도 seed_frame이라 "
                "game_seed_01과 겹침). support>=3, context>=min(2), frame>=2 → STRONG."
            ),
        ),
        HandCalculatedTraitExpectation(
            trait_id="change_adaptation",
            expected_support_count=2,
            expected_opportunity_count=7,
            expected_context_count=2,
            expected_distinct_frame_count=2,
            expected_state="MODERATE",
            calculation_notes=(
                "game_tail_02, media_tail_01 2번 선택(support=2). change_adaptation을 제시한 "
                "질문: game_tail_01, game_tail_02, media_tail_01, media_tail_02, "
                "school_life_seed_01(adapting_change), school_life_tail_01, "
                "school_life_tail_02 = 7개(game_seed_01·media_seed_01엔 이 Trait가 없음) → "
                "opportunity=7. Context={game, media}=2개, Frame={unexpected_result, "
                "new_tool}=2개. support>=2, context>=min(2), frame>=2 → 2026-08-20 팀 결정에 "
                "따라 MODERATE."
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
                "school_life_tail_01, school_life_tail_02 2번 선택(support=2). "
                "collaboration_preference를 제시한 질문: game_seed_01(team_coordination), "
                "game_tail_01, game_tail_02, media_tail_01, media_tail_02, "
                "school_life_seed_01(team_project), school_life_tail_01, "
                "school_life_tail_02 = 8개(media_seed_01엔 이 Trait가 없음) → opportunity=8. "
                "선택된 2건 전부 school_life Context뿐이라 context_count=1 < min(2). "
                "Frame은 2개로 다양하지만 Context 다양성 미충족이라 MODERATE 자격이 안 되고 "
                "LIMITED로 강등."
            ),
        ),
        HandCalculatedTraitExpectation(
            trait_id="immediate_execution",
            expected_support_count=0,
            expected_opportunity_count=7,
            expected_context_count=0,
            expected_distinct_frame_count=0,
            expected_state="INSUFFICIENT",
            expected_insufficient_reason="NO_POSITIVE_EVIDENCE",
            calculation_notes=(
                "immediate_execution을 제시한 질문: game_seed_01(quick_execution), "
                "game_tail_01, game_tail_02, media_tail_01, media_tail_02, "
                "school_life_tail_01, school_life_tail_02 = 7개(media_seed_01·"
                "school_life_seed_01엔 이 Trait가 없음) → opportunity=7. 한 번도 선택되지 "
                "않아 support=0 → INSUFFICIENT / NO_POSITIVE_EVIDENCE."
            ),
        ),
        HandCalculatedTraitExpectation(
            trait_id="information_comparison",
            expected_support_count=1,
            expected_opportunity_count=7,
            expected_context_count=1,
            expected_distinct_frame_count=1,
            expected_state="INSUFFICIENT",
            expected_insufficient_reason="EVIDENCE_LIMITED",
            calculation_notes=(
                "media_tail_02(external_research)에서 1번만 선택(support=1). "
                "information_comparison을 제시한 질문: media_seed_01(trend_research), "
                "game_tail_01, game_tail_02, media_tail_01, media_tail_02, "
                "school_life_tail_01, school_life_tail_02 = 7개(game_seed_01·"
                "school_life_seed_01엔 이 Trait가 없음) → opportunity=7. support_count==1이면 "
                "context/frame 다양성과 무관하게 INSUFFICIENT / EVIDENCE_LIMITED "
                "(§13 판정 순서상 STRONG/MODERATE 검사보다 먼저 적용)."
            ),
        ),
    ],
    expected_top_major_relevance_order=[],  # Matching Engine 미구현 — 다음 Fixture 버전에서 채움
    notes=(
        "2026-08-21: 실제 Seed Question 3개(game_seed_01/media_seed_01/school_life_seed_01) "
        "적용 후 재계산. 15개 Seed 선택지가 12개 Trait를 전부 최소 1번씩 제시하도록 설계된 "
        "결과, 이 Persona로는 INSUFFICIENT/NOT_PROBED(opportunity=0)를 더 이상 재현할 수 "
        "없다 — Seed만으로 이미 모든 Trait에 opportunity>=1이 생기기 때문이다. 그 케이스는 "
        "tests/test_evidence_engine.py의 단위 테스트가 계속 커버한다. "
        "전공 매칭까지 검증하려면 대표 전공 Profile이 먼저 확정돼야 한다(다음 단계)."
    ),
)
