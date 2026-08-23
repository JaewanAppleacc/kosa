"""실제 Assessment Answer Flow를 사용하는 진짜 End-to-End 테스트 — 2026-08-25 15차 리뷰 §6.

`tests/test_course_planning_api_integration.py`는 `AssessmentState.trait_summaries`를
세션에 직접 주입한다 — Assessment 질문·답변 구간 자체는 검증하지 않는다. 이 파일은 그
구간까지 포함한 진짜 흐름이다:

    POST /assessment/session
    → POST /assessment/interest-rating
    → POST /assessment/context-select
    → POST /assessment/context-confirm
    → POST /assessment/next-question (반복)
    → POST /assessment/answer (반복)
    → GET /profile/{session_id}
    → GET /majors/{session_id}
    → 추천된 대표 전공 하나 선택
    → GET /subjects/{session_id}?selected_major_id=...

`_llm_client`/`_tracer`를 강제로 끄고(`scripts/generate_mock_json.py`와 같은 패턴) 실제
LLM·LangSmith 네트워크 호출 없이 고정 Seed Question + Backup Question 경로만 타도록
한다 — 꼬리질문 문구는 결정론적 Mock이지만, Evidence·Trait·Matching 계산 자체는 항상
실제 로직이다(다른 테스트와 동일). 옵션 선택은 `(turn * 2) % 5`로 골고루 고르는데,
`scripts/generate_mock_json.py`가 이미 이 패턴으로 최소 1개 대표 전공을 "관련성 높음"
으로 만들 수 있음을 실증했다 — 그 패턴을 그대로 재사용한다(이 테스트를 통과시키기 위해
새로 지어낸 패턴이 아니다).

이 파일이 언젠가 Question Fixture나 Threshold 변경으로 더 이상 computed 결과를 만들지
못하게 되면, Trait Summary를 직접 주입해 억지로 통과시키지 말고 실패로 남겨 원인을
드러내야 한다(§6) — 그래서 이 테스트는 재시도나 예외 삼킴 없이 그대로 단언한다.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.api.main as main_module
from src.api.main import app
from src.repositories.subject_repository import load_subjects
from src.tracing.tracer import Tracer

client = TestClient(app)
_ALL_SUBJECT_IDS = {s.subject_id for s in load_subjects()}
_SUBJECT_LABEL_BY_ID = {s.subject_id: s.label for s in load_subjects()}

_MAX_TURNS = 30


class RealAnswerFlowEndToEndTest(unittest.TestCase):
    def setUp(self) -> None:
        # 로컬 .env 설정과 무관하게 강제로 끈다 — 이 테스트는 항상 결정론적 Mock/Backup
        # 질문 경로만 타야 하고, 실제 LLM·LangSmith 네트워크 호출을 하면 안 된다.
        for patch_target in (
            patch.object(main_module, "_llm_client", None),
            patch.object(main_module, "_tracer", Tracer(client=None)),
        ):
            patch_target.start()
            self.addCleanup(patch_target.stop)

    def test_full_assessment_flow_then_real_subject_recommendation(self) -> None:
        # 1. 세션 생성
        r = client.post("/assessment/session")
        self.assertEqual(r.status_code, 200)
        session_id = r.json()["session_id"]
        self.assertTrue(session_id.startswith("sess_"))

        # 2. 관심도 입력
        r = client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 5, "media": 5, "school_life": 4}},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["session_id"], session_id)

        # 3. Context 선택
        r = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "media"]},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["session_id"], session_id)

        # 4. Context 확정 (Vertical Slice 3개)
        r = client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game", "media", "school_life"]},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["session_id"], session_id)
        self.assertEqual(r.json()["final_context_ids"], ["game", "media", "school_life"])

        # 5~6. 질문↔답변 반복 — 옵션을 골고루 고른다(scripts/generate_mock_json.py와 동일
        # 패턴). 세션이 끝날 때까지, 또는 상한(_MAX_TURNS)까지 반복한다.
        for turn in range(_MAX_TURNS):
            r = client.post("/assessment/next-question", params={"session_id": session_id})
            self.assertEqual(r.status_code, 200, r.text)
            body = r.json()
            self.assertEqual(r.json().get("session_id", session_id), session_id)
            if body["status"] == "CONTEXT_EARLY_TERMINATED":
                if body["assessment_complete"]:
                    break
                continue
            question = body["question"]
            self.assertEqual(len(question["options"]), 5)
            option = question["options"][(turn * 2) % 5]
            ar = client.post(
                "/assessment/answer",
                json={
                    "session_id": session_id,
                    "question_id": question["question_id"],
                    "selected_option_id": option["option_id"],
                },
            )
            self.assertEqual(ar.status_code, 200, ar.text)
            self.assertEqual(ar.json()["session_id"], session_id)
            if ar.json()["next_action"] == "ASSESSMENT_COMPLETE":
                break

        # 7. Profile — 이 시점에 답변이 쌓였으니 EVIDENCE_NOT_READY가 아니라 실제 계산
        # 결과가 나와야 한다.
        r = client.get(f"/profile/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["session_id"], session_id)

        # 8. Majors — 최소 1개 대표 전공이 computed(관련성 높음 또는 함께 탐색해볼 분야)
        # 여야 다음 단계(과목 선택)로 넘어갈 수 있다. 여기서 computed 결과가 하나도 없으면
        # Trait Summary를 직접 주입해 억지로 통과시키지 않고 그대로 실패시킨다(§6).
        r = client.get(f"/majors/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        majors_body = r.json()
        self.assertEqual(majors_body["session_id"], session_id)
        recommended = majors_body["relevant_majors"] + majors_body["explore_together_majors"]
        self.assertGreater(
            len(recommended), 0,
            "실제 Answer Flow로는 이번 실행에서 computed 대표 전공이 하나도 안 나왔다 — "
            "Question Fixture나 옵션 선택 패턴을 다시 봐야 한다(Trait Summary를 직접 "
            "주입해 억지로 통과시키지 않는다).",
        )

        # 9. 추천된 대표 전공 하나 선택 → 과목 추천
        selected_major_id = recommended[0]["major_id"]
        r = client.get(f"/subjects/{session_id}", params={"selected_major_id": selected_major_id})
        self.assertEqual(r.status_code, 200, r.text)
        subjects_body = r.json()

        # session_id가 끝까지 동일해야 한다.
        self.assertEqual(subjects_body["session_id"], session_id)
        self.assertEqual(subjects_body["source"], "PRE_SURVEY")

        # 마지막 과목 추천이 실제 subject_id와 label을 반환해야 한다.
        self.assertGreater(len(subjects_body["recommendations"]), 0)
        for item in subjects_body["recommendations"]:
            self.assertIn(item["subject_id"], _ALL_SUBJECT_IDS)
            self.assertEqual(item["label"], _SUBJECT_LABEL_BY_ID[item["subject_id"]])
            self.assertTrue(item["label"])
            self.assertIsNone(item["is_actually_offered"])


if __name__ == "__main__":
    unittest.main()
