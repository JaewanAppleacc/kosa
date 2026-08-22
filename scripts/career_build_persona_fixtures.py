"""Persona + Hand-Calculated Fixture 작성 (작업자 C 소유) — 설계안 §26, C 지시서 §3.

`src/data/personas/demo_user_01.py`(A가 만든 본보기, 분석·구조화 중심)를 그대로 따라
나머지 유형을 채운다. 이 스크립트가 **작성 원본**이고, 산출물은
`data/eval_fixtures/personas/<persona_id>.json` 한 파일로 자기완결적이다 — Persona,
Hand-Calculated Fixture, 그 계산에 필요한 Option Blueprint가 한 파일에 다 들어 있어서
A의 Evaluation Harness가 다른 모듈을 import하지 않고 읽을 수 있다.

## 기대값은 코드가 계산한 게 아니다

`TRAIT_EXPECTATIONS`의 숫자는 답변 시퀀스를 보고 **손으로 센 값**이다. Evidence Engine을
불러 계산한 값을 그대로 적으면 "코드와 손계산이 일치하는지" 확인하는 의미가 사라진다
(§26). 이 스크립트는 손으로 적은 값을 실제 엔진 결과와 비교해서, 어긋나면 파일을 쓰지
않고 멈춘다.

## 제시 횟수(opportunity_count) 계산의 기준

Seed 3개와 꼬리질문 6개(공용 Blueprint 재사용)가 제시하는 Trait는 고정돼 있다.

    game_seed_01        causal_analysis / immediate_execution / collaboration_preference
                        / pattern_finding / tool_utilization
    media_seed_01       causal_analysis / visual_expression / audience_response_prediction
                        / emotional_interpretation / information_comparison
    school_life_seed_01 planning / collaboration_preference / opinion_mediation
                        / emotional_interpretation / change_adaptation
    꼬리질문(6회 공통)   causal_analysis / change_adaptation / immediate_execution
                        / information_comparison / collaboration_preference

따라서 9문항 기준 제시 횟수는 Persona와 무관하게 항상 아래와 같다(합계 45 = 9문항 × 5선택지).

    causal_analysis 8 · collaboration_preference 8 · immediate_execution 7
    information_comparison 7 · change_adaptation 7 · emotional_interpretation 2
    pattern_finding 1 · tool_utilization 1 · visual_expression 1
    audience_response_prediction 1 · planning 1 · opinion_mediation 1

실행:
    python scripts/career_build_persona_fixtures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402

from eval.trait_eval import evaluate_persona_against_fixture  # noqa: E402
from src.data.personas.demo_user_01 import BLUEPRINT_BY_QUESTION_ID  # noqa: E402
from src.schemas.persona import (  # noqa: E402
    HandCalculatedFixture,
    HandCalculatedTraitExpectation,
    Persona,
    PersonaAnswer,
)

OUT_DIR = ROOT / "data" / "eval_fixtures" / "personas"

# 제시 횟수 — 위 docstring 표 그대로. Persona마다 다시 세지 않는다.
OPPORTUNITY: dict[str, int] = {
    "causal_analysis": 8,
    "collaboration_preference": 8,
    "immediate_execution": 7,
    "information_comparison": 7,
    "change_adaptation": 7,
    "emotional_interpretation": 2,
    "pattern_finding": 1,
    "tool_utilization": 1,
    "visual_expression": 1,
    "audience_response_prediction": 1,
    "planning": 1,
    "opinion_mediation": 1,
}

# (question_id, context_id, frame_id, role_id, option_id)
AnswerRow = tuple[str, str, str, str, str]

# 손계산 기대값: trait_id -> (support, context_count, distinct_frame_count, state, reason, note)
Expectation = tuple[str, int, int, int, str, str | None, str]

PERSONAS: list[dict] = [
    {
        "persona_id": "persona_demo_user_02_expression_focused",
        "user_id": "demo_user_02",
        "label": "표현·창작 중심",
        "description": "직접 만들어 보고, 상황이 바뀌면 방식을 바꿔 다시 시도하는 경향이 반복 관찰되는 페르소나",
        "answers": [
            ("game_seed_01", "game", "seed_frame", "tool_mastery", "game_seed_01_o5"),
            ("media_seed_01", "media", "seed_frame", "creative_making", "media_seed_01_o2"),
            ("school_life_seed_01", "school_life", "seed_frame", "adapting_change", "school_life_seed_01_o5"),
            ("game_tail_01", "game", "first_action", "direct_trial", "game_tail_01_o3"),
            ("game_tail_02", "game", "unexpected_result", "strategy_change", "game_tail_02_o2"),
            ("media_tail_01", "media", "others_reaction", "external_research", "media_tail_01_o4"),
            ("media_tail_02", "media", "new_tool", "strategy_change", "media_tail_02_o2"),
            ("school_life_tail_01", "school_life", "conflicting_opinions", "direct_trial", "school_life_tail_01_o3"),
            ("school_life_tail_02", "school_life", "limited_time_priority", "external_research", "school_life_tail_02_o4"),
        ],
        "expectations": [
            ("change_adaptation", 3, 3, 3, "STRONG", None,
             "school_life Seed(seed_frame) 1회 + game 꼬리(unexpected_result) 1회 + media 꼬리(new_tool) 1회 = 3회 선택. "
             "Context 3개, Frame 3종이라 최소 Context 2개·Frame 2종 조건을 넘어 STRONG."),
            ("immediate_execution", 2, 2, 2, "MODERATE", None,
             "game 꼬리(first_action)와 school_life 꼬리(conflicting_opinions)에서 2회. "
             "Context 2개·Frame 2종을 채우지만 support가 3에 못 미쳐 MODERATE."),
            ("information_comparison", 2, 2, 2, "MODERATE", None,
             "media 꼬리(others_reaction)와 school_life 꼬리(limited_time_priority)에서 2회. "
             "domain_specific이라 최소 Context가 1개인데 실제 2개를 채웠고 Frame도 2종이라 MODERATE."),
            ("tool_utilization", 1, 1, 1, "INSUFFICIENT", "EVIDENCE_LIMITED",
             "game Seed에서만 1회 선택. 제시 자체가 1회뿐이라 반복 확인이 불가능했다."),
            ("visual_expression", 1, 1, 1, "INSUFFICIENT", "EVIDENCE_LIMITED",
             "media Seed에서만 1회 선택. 제시 1회, 지지 1회로 근거가 한 번뿐이다."),
            ("causal_analysis", 0, 0, 0, "INSUFFICIENT", "NO_POSITIVE_EVIDENCE",
             "8회 제시됐지만 한 번도 고르지 않았다 — 물어봤는데 지지 근거가 없는 경우다."),
            ("collaboration_preference", 0, 0, 0, "INSUFFICIENT", "NO_POSITIVE_EVIDENCE",
             "꼬리질문 6회와 game·school_life Seed에서 총 8회 제시됐지만 한 번도 고르지 않았다."),
            ("pattern_finding", 0, 0, 0, "INSUFFICIENT", "NO_POSITIVE_EVIDENCE", "game Seed의 5개 선택지 중 하나로 1회 제시됐지만 고르지 않았다."),
            ("audience_response_prediction", 0, 0, 0, "INSUFFICIENT", "NO_POSITIVE_EVIDENCE", "media Seed의 5개 선택지 중 하나로 1회 제시됐지만 고르지 않았다."),
            ("emotional_interpretation", 0, 0, 0, "INSUFFICIENT", "NO_POSITIVE_EVIDENCE", "media·school_life Seed에서 2회 제시됐지만 두 번 다 다른 선택지를 골랐다."),
            ("planning", 0, 0, 0, "INSUFFICIENT", "NO_POSITIVE_EVIDENCE", "school_life Seed의 5개 선택지 중 하나로 1회 제시됐지만 고르지 않았다."),
            ("opinion_mediation", 0, 0, 0, "INSUFFICIENT", "NO_POSITIVE_EVIDENCE", "school_life Seed의 5개 선택지 중 하나로 1회 제시됐지만 고르지 않았다."),
        ],
        "major_order": ["design", "computer_science", "media_communication"],
        "notes": "표현·제작 축(visual_expression·tool_utilization)이 Seed에서 각각 1회씩만 제시되는 구조라, "
                 "이 유형은 정작 자기 축에서 STRONG이 나오지 않는다. Contrast Context 제안(§5-1)이 필요한 대표 사례.",
    },
    {
        "persona_id": "persona_demo_user_03_relationship_focused",
        "user_id": "demo_user_03",
        "label": "관계·조정 중심",
        "description": "혼자 판단하기보다 사람들과 맞춰 가며 정하는 선택이 반복 관찰되는 페르소나",
        "answers": [
            ("game_seed_01", "game", "seed_frame", "team_coordination", "game_seed_01_o3"),
            ("media_seed_01", "media", "seed_frame", "character_empathy", "media_seed_01_o4"),
            ("school_life_seed_01", "school_life", "seed_frame", "conflict_mediation", "school_life_seed_01_o3"),
            ("game_tail_01", "game", "team_role", "ask_others", "game_tail_01_o5"),
            ("game_tail_02", "game", "conflicting_opinions", "ask_others", "game_tail_02_o5"),
            ("media_tail_01", "media", "others_reaction", "ask_others", "media_tail_01_o5"),
            ("media_tail_02", "media", "first_action", "external_research", "media_tail_02_o4"),
            ("school_life_tail_01", "school_life", "team_role", "ask_others", "school_life_tail_01_o5"),
            ("school_life_tail_02", "school_life", "problem_check", "cause_analysis", "school_life_tail_02_o1"),
        ],
        "expectations": [
            ("collaboration_preference", 5, 3, 4, "STRONG", None,
             "game Seed(seed_frame) 1회 + game 꼬리 2회(team_role·conflicting_opinions) + media 꼬리 1회(others_reaction) "
             "+ school_life 꼬리 1회(team_role) = 5회. Context 3개, Frame 4종(seed_frame·team_role·conflicting_opinions·"
             "others_reaction)이라 STRONG. team_role이 두 번 나오지만 Frame 종류는 한 번만 센다."),
            ("emotional_interpretation", 1, 1, 1, "INSUFFICIENT", "EVIDENCE_LIMITED",
             "media Seed에서 1회. 2회 제시됐지만 school_life Seed에서는 조정(opinion_mediation)을 골랐다."),
            ("opinion_mediation", 1, 1, 1, "INSUFFICIENT", "EVIDENCE_LIMITED", "school_life Seed에서만 제시됐고 그 한 번을 골랐다 — 반복 확인 기회가 없었다."),
            ("information_comparison", 1, 1, 1, "INSUFFICIENT", "EVIDENCE_LIMITED", "media 꼬리질문(first_action)에서만 1회 선택. 7회 제시 중 한 번이다."),
            ("causal_analysis", 1, 1, 1, "INSUFFICIENT", "EVIDENCE_LIMITED", "school_life 꼬리질문(problem_check)에서만 1회 선택. 8회 제시 중 한 번이다."),
            ("change_adaptation", 0, 0, 0, "INSUFFICIENT", "NO_POSITIVE_EVIDENCE", "꼬리질문 6회와 Seed 1회로 총 7회 제시됐지만 한 번도 고르지 않았다."),
            ("immediate_execution", 0, 0, 0, "INSUFFICIENT", "NO_POSITIVE_EVIDENCE", "꼬리질문 6회와 Seed 1회로 총 7회 제시됐지만 한 번도 고르지 않았다."),
            ("pattern_finding", 0, 0, 0, "INSUFFICIENT", "NO_POSITIVE_EVIDENCE", "game Seed의 5개 선택지 중 하나로 1회 제시됐지만 고르지 않았다."),
            ("tool_utilization", 0, 0, 0, "INSUFFICIENT", "NO_POSITIVE_EVIDENCE", "game Seed의 5개 선택지 중 하나로 1회 제시됐지만 고르지 않았다."),
            ("visual_expression", 0, 0, 0, "INSUFFICIENT", "NO_POSITIVE_EVIDENCE", "media Seed의 5개 선택지 중 하나로 1회 제시됐지만 고르지 않았다."),
            ("audience_response_prediction", 0, 0, 0, "INSUFFICIENT", "NO_POSITIVE_EVIDENCE", "media Seed의 5개 선택지 중 하나로 1회 제시됐지만 고르지 않았다."),
            ("planning", 0, 0, 0, "INSUFFICIENT", "NO_POSITIVE_EVIDENCE", "school_life Seed의 5개 선택지 중 하나로 1회 제시됐지만 고르지 않았다."),
        ],
        "major_order": ["education", "psychology", "business_administration"],
        "notes": "STRONG이 collaboration_preference 하나뿐이고 나머지가 전부 INSUFFICIENT다. "
                 "한 축만 강하게 나오는 Persona에서 전공 변별이 실제로 되는지 확인하는 용도.",
    },
    {
        "persona_id": "persona_demo_user_04_execution_focused",
        "user_id": "demo_user_04",
        "label": "실행 중심",
        "description": "따져 보기 전에 일단 해 보고 결과를 보고 고치는 선택이 반복 관찰되는 페르소나",
        "answers": [
            ("game_seed_01", "game", "seed_frame", "quick_execution", "game_seed_01_o2"),
            ("media_seed_01", "media", "seed_frame", "trend_research", "media_seed_01_o5"),
            ("school_life_seed_01", "school_life", "seed_frame", "task_planning", "school_life_seed_01_o1"),
            ("game_tail_01", "game", "first_action", "direct_trial", "game_tail_01_o3"),
            ("game_tail_02", "game", "first_action", "direct_trial", "game_tail_02_o3"),
            ("media_tail_01", "media", "first_action", "direct_trial", "media_tail_01_o3"),
            ("media_tail_02", "media", "limited_time_priority", "external_research", "media_tail_02_o4"),
            ("school_life_tail_01", "school_life", "problem_check", "cause_analysis", "school_life_tail_01_o1"),
            ("school_life_tail_02", "school_life", "problem_check", "cause_analysis", "school_life_tail_02_o1"),
        ],
        "expectations": [
            ("immediate_execution", 4, 2, 2, "STRONG", None,
             "game Seed(seed_frame) 1회 + game 꼬리 2회(둘 다 first_action) + media 꼬리 1회(first_action) = 4회. "
             "Context 2개(game·media), Frame 2종(seed_frame·first_action)이라 STRONG. first_action이 세 번 쓰였지만 "
             "Frame 종류는 1로 센다."),
            ("information_comparison", 2, 1, 2, "MODERATE", None,
             "media Seed(seed_frame)와 media 꼬리(limited_time_priority)에서 2회. Context는 media 하나뿐인데 "
             "domain_specific Trait라 최소 Context가 1이라 조건을 만족하고, Frame 2종이라 MODERATE."),
            ("causal_analysis", 2, 1, 1, "LIMITED", None,
             "school_life 꼬리 2회 모두 같은 Frame(problem_check), 같은 Context에서 나왔다. 2회 이상이지만 "
             "Context 2개(shared Trait 최소치)와 Frame 2종을 못 채워 LIMITED — 같은 상황에서만 반복된 근거다."),
            ("planning", 1, 1, 1, "INSUFFICIENT", "EVIDENCE_LIMITED", "school_life Seed에서만 제시됐고 그 한 번을 골랐다 — 반복 확인 기회가 없었다."),
            ("collaboration_preference", 0, 0, 0, "INSUFFICIENT", "NO_POSITIVE_EVIDENCE", "꼬리질문 6회와 game·school_life Seed에서 총 8회 제시됐지만 한 번도 고르지 않았다."),
            ("change_adaptation", 0, 0, 0, "INSUFFICIENT", "NO_POSITIVE_EVIDENCE", "꼬리질문 6회와 Seed 1회로 총 7회 제시됐지만 한 번도 고르지 않았다."),
            ("pattern_finding", 0, 0, 0, "INSUFFICIENT", "NO_POSITIVE_EVIDENCE", "game Seed의 5개 선택지 중 하나로 1회 제시됐지만 고르지 않았다."),
            ("tool_utilization", 0, 0, 0, "INSUFFICIENT", "NO_POSITIVE_EVIDENCE", "game Seed의 5개 선택지 중 하나로 1회 제시됐지만 고르지 않았다."),
            ("visual_expression", 0, 0, 0, "INSUFFICIENT", "NO_POSITIVE_EVIDENCE", "media Seed의 5개 선택지 중 하나로 1회 제시됐지만 고르지 않았다."),
            ("audience_response_prediction", 0, 0, 0, "INSUFFICIENT", "NO_POSITIVE_EVIDENCE", "media Seed의 5개 선택지 중 하나로 1회 제시됐지만 고르지 않았다."),
            ("emotional_interpretation", 0, 0, 0, "INSUFFICIENT", "NO_POSITIVE_EVIDENCE", "media·school_life Seed에서 2회 제시됐지만 두 번 다 다른 선택지를 골랐다."),
            ("opinion_mediation", 0, 0, 0, "INSUFFICIENT", "NO_POSITIVE_EVIDENCE", "school_life Seed의 5개 선택지 중 하나로 1회 제시됐지만 고르지 않았다."),
        ],
        "major_order": ["computer_science", "mechanical_engineering", "business_administration"],
        "notes": "LIMITED 상태를 재현하는 Fixture다 — 같은 Context·같은 Frame에서만 반복된 근거가 "
                 "STRONG으로 올라가지 않는지 확인한다(§13, 2026-08-20 Frame 다양성 결정).",
    },
    {
        "persona_id": "persona_demo_user_05_dispersed_interest",
        "user_id": "demo_user_05",
        "label": "관심 분산형",
        "description": "매 문항 다른 축을 고르는, 아직 한 방향으로 모이지 않은 페르소나",
        "answers": [
            ("game_seed_01", "game", "seed_frame", "pattern_recognition", "game_seed_01_o4"),
            ("media_seed_01", "media", "seed_frame", "audience_reaction", "media_seed_01_o3"),
            ("school_life_seed_01", "school_life", "seed_frame", "peer_understanding", "school_life_seed_01_o4"),
            ("game_tail_01", "game", "problem_check", "cause_analysis", "game_tail_01_o1"),
            ("game_tail_02", "game", "unexpected_result", "strategy_change", "game_tail_02_o2"),
            ("media_tail_01", "media", "first_action", "direct_trial", "media_tail_01_o3"),
            ("media_tail_02", "media", "limited_time_priority", "external_research", "media_tail_02_o4"),
            ("school_life_tail_01", "school_life", "team_role", "ask_others", "school_life_tail_01_o5"),
            ("school_life_tail_02", "school_life", "problem_check", "cause_analysis", "school_life_tail_02_o1"),
        ],
        "expectations": [
            ("causal_analysis", 2, 2, 1, "LIMITED", None,
             "game 꼬리와 school_life 꼬리에서 2회지만 둘 다 같은 Frame(problem_check)이다. Context는 2개로 충분한데 "
             "Frame 2종 조건을 못 채워 LIMITED."),
            ("pattern_finding", 1, 1, 1, "INSUFFICIENT", "EVIDENCE_LIMITED", "game Seed에서만 제시됐고 그 한 번을 골랐다 — 반복 확인 기회가 없었다."),
            ("audience_response_prediction", 1, 1, 1, "INSUFFICIENT", "EVIDENCE_LIMITED", "media Seed에서만 제시됐고 그 한 번을 골랐다 — 반복 확인 기회가 없었다."),
            ("emotional_interpretation", 1, 1, 1, "INSUFFICIENT", "EVIDENCE_LIMITED", "media·school_life Seed에서 2회 제시됐고 school_life에서 1회 선택했다."),
            ("change_adaptation", 1, 1, 1, "INSUFFICIENT", "EVIDENCE_LIMITED", "game 꼬리질문(unexpected_result)에서만 1회 선택. 7회 제시 중 한 번이다."),
            ("immediate_execution", 1, 1, 1, "INSUFFICIENT", "EVIDENCE_LIMITED", "media 꼬리질문(first_action)에서만 1회 선택. 7회 제시 중 한 번이다."),
            ("information_comparison", 1, 1, 1, "INSUFFICIENT", "EVIDENCE_LIMITED", "media 꼬리질문(limited_time_priority)에서만 1회 선택. 7회 제시 중 한 번이다."),
            ("collaboration_preference", 1, 1, 1, "INSUFFICIENT", "EVIDENCE_LIMITED", "school_life 꼬리질문(team_role)에서만 1회 선택. 8회 제시 중 한 번이다."),
            ("visual_expression", 0, 0, 0, "INSUFFICIENT", "NO_POSITIVE_EVIDENCE", "media Seed의 5개 선택지 중 하나로 1회 제시됐지만 고르지 않았다."),
            ("tool_utilization", 0, 0, 0, "INSUFFICIENT", "NO_POSITIVE_EVIDENCE", "game Seed의 5개 선택지 중 하나로 1회 제시됐지만 고르지 않았다."),
            ("planning", 0, 0, 0, "INSUFFICIENT", "NO_POSITIVE_EVIDENCE", "school_life Seed의 5개 선택지 중 하나로 1회 제시됐지만 고르지 않았다."),
            ("opinion_mediation", 0, 0, 0, "INSUFFICIENT", "NO_POSITIVE_EVIDENCE", "school_life Seed의 5개 선택지 중 하나로 1회 제시됐지만 고르지 않았다."),
        ],
        "major_order": [],
        "notes": "STRONG이 하나도 없다. §14 '추가 탐색이 필요하다'는 화면 문구가 실제로 나오는 조건을 "
                 "만들어 두기 위한 Fixture이고, 전공 순위를 단정하지 않는지 확인하는 용도라 "
                 "expected_top_major_relevance_order를 비워 뒀다.",
    },
]


def _build(spec: dict) -> tuple[Persona, HandCalculatedFixture]:
    persona = Persona(
        persona_id=spec["persona_id"],
        user_id=spec["user_id"],
        label=spec["label"],
        description=spec["description"],
        final_context_ids=["game", "media", "school_life"],
        answers=[
            PersonaAnswer(
                context_id=context_id,
                question_id=question_id,
                question_frame_id=frame_id,
                selected_option_id=option_id,
                selected_role_id=role_id,
            )
            for question_id, context_id, frame_id, role_id, option_id in spec["answers"]
        ],
    )

    expectations: list[HandCalculatedTraitExpectation] = []
    for trait_id, support, contexts, frames, state, reason, note in spec["expectations"]:
        if trait_id not in OPPORTUNITY:
            raise SystemExit(f"{spec['persona_id']}: 제시 횟수 표에 없는 trait_id {trait_id}")
        expectations.append(
            HandCalculatedTraitExpectation(
                trait_id=trait_id,
                expected_support_count=support,
                expected_opportunity_count=OPPORTUNITY[trait_id],
                expected_context_count=contexts,
                expected_distinct_frame_count=frames,
                expected_state=state,
                expected_insufficient_reason=reason,
                calculation_notes=note,
            )
        )
    if len(expectations) != len(OPPORTUNITY):
        missing = set(OPPORTUNITY) - {e.trait_id for e in expectations}
        raise SystemExit(f"{spec['persona_id']}: 기대값이 빠진 Trait {sorted(missing)}")

    fixture = HandCalculatedFixture(
        fixture_id=f"fixture_{spec['persona_id']}",
        persona_id=spec["persona_id"],
        trait_expectations=expectations,
        expected_top_major_relevance_order=spec["major_order"],
        notes=spec["notes"],
    )
    return persona, fixture


def build_all(write: bool = True) -> list[tuple[Persona, HandCalculatedFixture]]:
    built: list[tuple[Persona, HandCalculatedFixture]] = []
    if write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)

    for spec in PERSONAS:
        persona, fixture = _build(spec)
        result = evaluate_persona_against_fixture(persona, fixture, BLUEPRINT_BY_QUESTION_ID)
        if not result.passed:
            lines = "\n".join(
                f"  {m.trait_id}.{m.field}: 손계산 {m.expected} vs 코드 {m.actual}"
                for m in result.mismatches
            )
            raise SystemExit(f"{spec['persona_id']} 손계산이 코드 결과와 다르다:\n{lines}")

        if write:
            used_questions = {a.question_id for a in persona.answers}
            payload = {
                "format_version": "persona_fixture_v1",
                "persona": json.loads(persona.model_dump_json()),
                "hand_calculated_fixture": json.loads(fixture.model_dump_json()),
                "option_blueprints": {
                    question_id: json.loads(BLUEPRINT_BY_QUESTION_ID[question_id].model_dump_json())
                    for question_id in sorted(used_questions)
                },
            }
            (OUT_DIR / f"{persona.persona_id}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        built.append((persona, fixture))
    return built


if __name__ == "__main__":
    use_utf8_stdout()
    results = build_all()
    print(f"Persona·Fixture {len(results)}쌍 생성 — 전부 Evidence Engine 결과와 일치")
    for persona, _ in results:
        print(f"  {persona.persona_id} ({persona.label})")
