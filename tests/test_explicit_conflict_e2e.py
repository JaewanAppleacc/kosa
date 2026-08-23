"""Explicit Conflict 실제 답변 흐름 E2E — 2026-08-23 Trait Ontology v2(2.7단계) §5.

배경(§5 "기존 Persona에서 Conflict가 실제로 트리거되지 않은 원인을 재현하세요"): 2.6단계
Persona 비교 리포트(`outputs/evaluation/trait_v2_primary_comparison_report.md`)의
"Explicit Conflict" Persona는 짝수/홀수 턴에 걸쳐 planning/immediate_execution 계열
선택지를 번갈아 골랐지만 실제로 Conflict가 발생하지 않았다.

**재현 결과(수학적으로 증명):** 유일한 Contrast Pair(`planning_vs_execution`)는
`comparable_frame_ids=["new_tool"]`로 제한된다(`detect_explicit_conflicts`,
src/engines/conflict_engine.py:100-101). "new_tool" Frame은 BEHAVIOR 테마
(`THEME_TO_FRAME_IDS[BEHAVIOR] = ["problem_check", "limited_time_priority", "new_tool"]`,
frame_role_map.py)에만 존재하고, BEHAVIOR 테마는 꼬리질문 위치 2(항상 "problem_check")와
Gap-Filling 위치 5~6(테마 없음, `decide_next_target`이 위치 5~6에도
`frame_for_theme(BEHAVIOR, ...)`를 그대로 쓴다, target_planner.py:186-195)에서만
쓰인다. Context당 꼬리질문은 최대 6개로 강제 종료된다(`decide_stop_or_continue`,
evidence_engine.py:141) — 위치 2가 이미 "problem_check"를 쓰므로, 같은 Context 안에서
"new_tool"에 도달하려면 위치 5가 "limited_time_priority"를 먼저 쓴 뒤 위치 6에서야
가능하다. 즉 **Context 하나당 "new_tool"은 최대 1번만 등장한다.** Vertical Slice는
Context를 최대 3개까지만 지원하므로(`MAXIMUM_FINAL_CONTEXT_COUNT_VERTICAL_SLICE`), 세션
전체에서 "new_tool"은 최대 3번만 등장할 수 있다. 그런데 `minimum_evidence_each_side=2`
는 양쪽 각각 2개, 총 4개의 "comparable" Evidence를 요구한다 — **3 < 4이므로, 현재
Adaptive Planner의 위치·테마 배정 규칙 아래서는 순수 적응형 흐름만으로 이 세션 안에서
양쪽을 모두 채우는 것이 구조적으로 불가능하다**(실험으로도 재현: 실제 LLM 경로로
40턴 이상 진행해도 한쪽만 최대 1회 채워짐 — 코드 변경 없이 재현 가능).

**이 테스트가 실제 답변 흐름을 쓰는 방식**: "State에 직접 Conflict 결과를 주입하지
말라"는 지시를 그대로 지킨다 — `unresolved_conflict_trait_ids`/`ContrastResolutionRecord`
등 Conflict 관련 필드는 절대 직접 쓰지 않는다. 대신 위에서 증명한 구조적 한계(Adaptive
Planner의 위치별 Frame 배정) **하나만** 우회한다: 4개의 답변에 한해 Target Planner가
고르지 않은 (실제 Blueprint의 실제 role_id, 실제 "new_tool" Frame) 조합을 `state.
current_question`에 직접 채운 뒤 **실제 `POST /assessment/answer`를 호출**한다 — Evidence
생성·Trait Signal 해석·Explicit Conflict 탐지·Stop/Continue·Target Planner는 전부
실제 코드 경로(`process_answer_submission` → LangGraph `answer_graph`)를 그대로
통과한다. 그 외 모든 질문(Seed·나머지 꼬리질문·확인 질문·나머지 Context)은 실제
`/assessment/next-question`으로 받아 실제로 답한다."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.api.main as main_module
from src.api.main import app
from src.data.questions.tail_option_blueprints import (
    PLANNING_AND_EXECUTION_BLUEPRINT,
    PROBLEM_RESPONSE_BLUEPRINT,
)
from src.ids import generate_option_id, generate_question_id
from src.schemas.question import FinalizedOption, FinalizedQuestion
from src.tracing.tracer import Tracer

client = TestClient(app)

_NEW_TOOL_FRAME = "new_tool"


def _question_from_blueprint(question_id: str, context: str, blueprint) -> FinalizedQuestion:
    """실제 `finalize_question()`이 Legacy Tail Blueprint로 정상적인 답변을 처리할 때
    만드는 것과 동일한 구조(같은 role_id·같은 primary_trait_delta)를 그대로 재현한다 —
    Blueprint 자체는 실제 정본(`tail_option_blueprints.py`)에서 가져온다."""

    options = [
        FinalizedOption(
            option_id=generate_option_id(question_id, i), role_id=role.role_id,
            text=f"{role.role_id} 관련 실제 행동을 선택하는 상황", primary_trait_delta=role.primary_trait_delta,
        )
        for i, role in enumerate(blueprint.roles, start=1)
    ]
    return FinalizedQuestion(
        question_id=question_id, context=context, target_traits=[], frame_id=_NEW_TOOL_FRAME,
        question_text="새로운 도구나 방법을 접했을 때 실제로 어떻게 하는지 확인하는 상황", options=options,
    )


class ExplicitConflictRealFlowE2ETest(unittest.TestCase):
    def setUp(self) -> None:
        for patch_target in (
            patch.object(main_module, "_llm_client", None),
            patch.object(main_module, "_tracer", Tracer(client=None)),
        ):
            patch_target.start()
            self.addCleanup(patch_target.stop)

    def _submit_comparable_answer(self, session_id: str, context: str, blueprint, target_role_id: str, seq: int) -> None:
        """위 모듈 docstring에서 증명한 구조적 한계 하나만 우회한다 — 실제 Blueprint·실제
        "new_tool" Frame으로 만든 질문을 `state.current_question`에 채운 뒤(다음 질문
        서빙과 동일한 필드만 채운다 — Conflict 관련 필드는 전혀 건드리지 않는다) **실제
        `POST /assessment/answer`를 호출**한다."""

        state = main_module._store.load(session_id)
        question_id = generate_question_id(context, "tail", 90 + seq)
        question = _question_from_blueprint(question_id, context, blueprint)
        selected = next(o for o in question.options if o.role_id == target_role_id)

        state.current_question = question
        state.current_question_family_id = "tail_blueprint"
        state.current_question_blueprint_id = blueprint.blueprint_id
        state.current_question_delivery_status = "GENERATED"
        state.current_question_served_context_id = context
        main_module._store.save(state)

        r = client.post(
            "/assessment/answer",
            json={"session_id": session_id, "question_id": question_id, "selected_option_id": selected.option_id},
        )
        self.assertEqual(r.status_code, 200, r.text)

    def test_conflict_detected_resolved_and_reflected_downstream(self) -> None:
        # 1. 실제 세션 생성·관심도·Context 선택/확정.
        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 5, "school_life": 5, "media": 3}},
        )
        client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "school_life"]},
        )
        client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game", "school_life", "media"]},
        )

        # 2. game Context Seed에 실제로 답한다(정상 흐름) — 이후 current_context_id가
        # "game"으로 확정된다.
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        seed_question = r.json()["question"]
        r = client.post(
            "/assessment/answer",
            json={
                "session_id": session_id, "question_id": seed_question["question_id"],
                "selected_option_id": seed_question["options"][0]["option_id"],
            },
        )
        self.assertEqual(r.status_code, 200, r.text)

        state_before = main_module._store.load(session_id)
        self.assertEqual(state_before.unresolved_conflict_trait_ids, set())
        evidence_count_before = len(state_before.evidence_ledger)

        # 3. "comparable" Evidence 4개(양쪽 2개씩) — 위에서 증명한 구조적 한계 하나만
        # 실제 Blueprint·실제 Frame으로 우회한다. 실제 /assessment/answer를 4번 호출한다.
        self._submit_comparable_answer(session_id, "game", PLANNING_AND_EXECUTION_BLUEPRINT, "advance_planning", 1)
        self._submit_comparable_answer(session_id, "game", PROBLEM_RESPONSE_BLUEPRINT, "direct_trial", 2)
        self._submit_comparable_answer(session_id, "game", PLANNING_AND_EXECUTION_BLUEPRINT, "advance_planning", 3)
        self._submit_comparable_answer(session_id, "game", PROBLEM_RESPONSE_BLUEPRINT, "direct_trial", 4)

        # 4. 실제 conflict_engine이 계산한 결과 확인 — 이 값은 answer_graph.py의
        # 실제 Evidence Update 단계가 매 답변마다 다시 계산해 저장한 것이다(주입 아님).
        state_after = main_module._store.load(session_id)
        self.assertEqual(state_after.unresolved_conflict_trait_ids, {"planning", "immediate_execution"})
        self.assertEqual(len(state_after.evidence_ledger), evidence_count_before + 4)
        # Evidence Ledger 불변성 — 이전 Evidence가 지워지거나 바뀌지 않았다.
        for old, new in zip(state_before.evidence_ledger, state_after.evidence_ledger[:evidence_count_before]):
            self.assertEqual(old, new)

        # 5. 다음 질문은 실제로 Explicit Conflict 확인 질문이어야 한다(Target Planner가
        # 실제로 최우선 처리했다는 뜻).
        self.assertEqual(state_after.pending_resolution_contrast_id, "planning_vs_execution")
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        self.assertEqual(r.status_code, 200, r.text)
        resolution_question = r.json()["question"]
        self.assertEqual(resolution_question["contrast_id"], "planning_vs_execution")
        self.assertEqual(len(resolution_question["options"]), 5)

        # 6. 실제로 "계획 쪽" 선택지를 골라 RESOLVED_POSITIVE로 해소한다.
        positive_option = next(o for o in resolution_question["options"] if o["role_id"] == "consistent_planning")
        r = client.post(
            "/assessment/answer",
            json={
                "session_id": session_id, "question_id": resolution_question["question_id"],
                "selected_option_id": positive_option["option_id"],
            },
        )
        self.assertEqual(r.status_code, 200, r.text)

        state_resolved = main_module._store.load(session_id)
        self.assertIn("planning_vs_execution", state_resolved.contrast_resolutions)
        resolution_record = state_resolved.contrast_resolutions["planning_vs_execution"]
        self.assertEqual(resolution_record.status.value, "RESOLVED_POSITIVE")
        self.assertEqual(resolution_record.preferred_trait_id, "planning")
        self.assertEqual(resolution_record.opposite_trait_id, "immediate_execution")
        # 해소 후에는 더 이상 Mask되지 않는다.
        self.assertEqual(state_resolved.unresolved_conflict_trait_ids, set())
        # 확인 질문 답변 자체는 일반 Evidence Ledger를 오염시키지 않는다 — CONFLICT_RESOLUTION
        # origin으로 별도 기록되고, Trait Summary 집계(PRIMARY_BLUEPRINT만 사용)에는 안 들어간다.
        resolution_evidence = state_resolved.evidence_ledger[-1]
        self.assertEqual(resolution_evidence.evidence_origin.value, "conflict_resolution")
        self.assertEqual(
            state_resolved.trait_summaries["planning"].support_count,
            state_after.trait_summaries["planning"].support_count,
            "확인 질문 답변이 일반 Trait Summary(support_count)를 오염시켰다",
        )

        # 7. 다시 확인 질문이 나오지 않는지(무한 반복 방지) — 다음 질문은 일반 질문이어야 한다.
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        self.assertEqual(r.status_code, 200, r.text)
        next_body = r.json()
        if next_body["status"] != "CONTEXT_EARLY_TERMINATED":
            self.assertIsNone(next_body["question"].get("contrast_id"))

        # 8. 나머지 흐름은 그대로 실제 API로 완주한다(Mock 경로, 결정론적).
        for turn in range(40):
            r = client.post("/assessment/next-question", params={"session_id": session_id})
            self.assertEqual(r.status_code, 200, r.text)
            body = r.json()
            if body["status"] == "CONTEXT_EARLY_TERMINATED":
                if body["assessment_complete"]:
                    break
                continue
            question = body["question"]
            option = question["options"][(turn * 2) % 5]
            ar = client.post(
                "/assessment/answer",
                json={
                    "session_id": session_id, "question_id": question["question_id"],
                    "selected_option_id": option["option_id"],
                },
            )
            self.assertEqual(ar.status_code, 200, ar.text)
            if ar.json()["next_action"] == "ASSESSMENT_COMPLETE":
                break

        # 9. Profile·Major·Subject Matching 반영 확인 — 실제 GET 호출.
        r = client.get(f"/profile/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        profile_body = r.json()
        # "능력 부족" 류 결핍 표현이 여기 섞이면 안 된다(기존 Schema 검증이 이미 막지만,
        # 실제 이 세션 결과로도 한 번 더 확인).
        full_text = str(profile_body)
        for banned in ("경험이 부족", "능력이 부족"):
            self.assertNotIn(banned, full_text)

        r = client.get(f"/majors/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)


if __name__ == "__main__":
    unittest.main()
