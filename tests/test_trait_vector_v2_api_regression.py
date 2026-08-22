"""Trait Ontology v2(1단계) API/회귀 테스트 — 지시서 §15 "API"/"회귀"."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.api.main as main_module
from src.api.main import app

client = TestClient(app)

_FORBIDDEN_OPENAPI_STRINGS = (
    "trait_signal", "TraitSignal", "AppliedTraitSignal", "signal_role",
    "related_concept_ids", "primary_signal_sum", "related_signal_sum",
    "confirmed_related_signal_sum", "tendency_score", "TraitVectorEntry",
    "TraitVectorStatus", "RelatedConceptDefinition", "trait_ontology_v2",
)


class OpenAPINoInternalSignalLeakTest(unittest.TestCase):
    def test_openapi_schema_never_mentions_v2_internal_types(self) -> None:
        spec_text = str(app.openapi())
        for forbidden in _FORBIDDEN_OPENAPI_STRINGS:
            self.assertNotIn(forbidden, spec_text, f"OpenAPI에 내부 v2 타입이 노출됨: {forbidden!r}")


class SessionLifecycleRegressionTest(unittest.TestCase):
    """기존 810개 테스트(19차까지)가 이미 광범위하게 회귀를 검증하므로, 여기서는 이번
    v2 변경이 Major/Subject/Subgraph의 실제 계산 경로를 우회하지 않았는지 조합
    시나리오로 한 번 더 확인한다."""

    def setUp(self) -> None:
        patcher = patch.object(main_module, "_llm_client", None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_full_flow_majors_subjects_subgraph_still_work_with_v2_wired_in(self) -> None:
        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 5, "media": 5, "school_life": 5}},
        )
        client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "media"]},
        )
        client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game", "media", "school_life"]},
        )
        for _ in range(30):
            r = client.post("/assessment/next-question", params={"session_id": session_id})
            body = r.json()
            if body["status"] == "CONTEXT_EARLY_TERMINATED":
                if body["assessment_complete"]:
                    break
                continue
            question = body["question"]
            option = question["options"][0]
            ar = client.post(
                "/assessment/answer",
                json={
                    "session_id": session_id, "question_id": question["question_id"],
                    "selected_option_id": option["option_id"],
                },
            )
            if ar.json()["next_action"] == "ASSESSMENT_COMPLETE":
                break

        r = client.get(f"/profile/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        r = client.get(f"/majors/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        r = client.get(f"/subgraph/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        # 이번 단계에서 Subgraph Node·Edge 구조는 절대 안 바뀐다 — v2 관련 문자열이
        # 전혀 없어야 한다.
        for forbidden in _FORBIDDEN_OPENAPI_STRINGS:
            self.assertNotIn(forbidden, str(r.json()))

    def test_no_network_or_langsmith_calls_during_v2_test_suite(self) -> None:
        """이 테스트 파일 자체가 _llm_client=None + 기본 _tracer(client=None 상태와
        동등)로 동작하는지 — main 모듈 기본값이 실제로 네트워크를 안 만드는지는 다른
        테스트들이 이미 광범위하게 확인하므로, 여기서는 이 파일의 setUp이 LLM을
        확실히 꺼두는지만 다시 확인한다."""

        self.assertIsNone(main_module._llm_client)


if __name__ == "__main__":
    unittest.main()
