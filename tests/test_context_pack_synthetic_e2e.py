"""ContextPack 합성(Synthetic) Context E2E — 2026-08-23 Trait Ontology v2(2.8단계) §10.

실제 T·S·L Pack 파일을 건드리거나 그 디렉터리에 새 파일을 놓지 않는다 — `main.py`의
`_context_pack_registry`/`_context_pack_runtime` 전역을 테스트 전용 값으로 주입해서
(dependency injection) 실제 배치 Context id("business")를 재사용하는 합성 Pack 하나로
전체 흐름을 검증한다. 검수 상태 파일도 임시 디렉터리에만 쓴다 — 공유
`data/reviews/context_packs/business_review_status.json`(아직 전부 TBD)은 전혀
건드리지 않는다."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.api.main as main_module
from src.api.main import app
from src.data.context_packs._example_pack_builder import build_example_context_pack
from src.data.contexts.context_definitions import VERTICAL_SLICE_CONTEXT_IDS
from src.services.context_pack_registry import ContextPackRegistry
from src.services.context_pack_runtime import ContextPackRuntime
from src.tracing.tracer import Tracer

client = TestClient(app)
_MAX_TURNS = 20


class ContextPackSyntheticEndToEndTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        review_dir = Path(self.tmpdir.name)

        self.pack = build_example_context_pack("business")  # 실제 배치-1 Context id 재사용
        self.test_registry = ContextPackRegistry(
            known_context_ids=frozenset({"business"}),
            known_trait_ids=frozenset({"causal_analysis", "pattern_finding"}),
            review_status_dir=review_dir,
            _discovered=({"business": self.pack}, {}),
        )
        required_keys = sorted(self.test_registry.required_review_keys(self.pack))
        (review_dir / "business_review_status.json").write_text(
            json.dumps([{"blueprint_id": k, "reviewer_1_status": "APPROVE"} for k in required_keys], ensure_ascii=False),
            encoding="utf-8",
        )
        self.test_runtime = ContextPackRuntime(
            self.test_registry, lambda: main_module.context_pack_runtime_enabled(), frozenset(VERTICAL_SLICE_CONTEXT_IDS),
        )

        for patch_target in (
            patch.object(main_module, "_context_pack_registry", self.test_registry),
            patch.object(main_module, "_context_pack_runtime", self.test_runtime),
            patch.object(main_module, "_llm_client", None),
            patch.object(main_module, "_tracer", Tracer(client=None)),
        ):
            patch_target.start()
            self.addCleanup(patch_target.stop)
        import os
        os.environ["ENABLE_CONTEXT_PACK_RUNTIME"] = "true"
        self.addCleanup(os.environ.pop, "ENABLE_CONTEXT_PACK_RUNTIME", None)

    def test_synthetic_business_context_flows_through_routing_seed_backup_to_profile(self) -> None:
        # 1. 세션 생성.
        r = client.post("/assessment/session")
        self.assertEqual(r.status_code, 200)
        session_id = r.json()["session_id"]

        # 1-1. /contexts가 실제로 business를 지원 목록에 포함하는지(§3-1/§8).
        r = client.get("/contexts")
        self.assertEqual(r.status_code, 200)
        catalog = {c["context_id"]: c for c in r.json()["contexts"]}
        self.assertIn("business", catalog)
        self.assertTrue(catalog["business"]["assessment_supported"])

        # 2~4. 관심도·Context 선택·확정 — business + game.
        r = client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 4, "business": 5}},
        )
        self.assertEqual(r.status_code, 200, r.text)
        r = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "business"]},
        )
        self.assertEqual(r.status_code, 200, r.text)
        r = client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["business", "game"]},
        )
        self.assertEqual(r.status_code, 200, r.text)

        # 5. Routing 질문이 business에서 먼저 나온다.
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["current_context_id"], "business")
        state = main_module._store.load(session_id)
        self.assertEqual(state.current_question_family_id, "context_routing")
        routing_question = body["question"]
        self.assertEqual(len(routing_question["options"]), 5)

        # 6. Routing 답변 — Anchor 선택만 저장되고 Evidence Ledger는 그대로 비어 있어야 한다.
        chosen_option = routing_question["options"][0]
        r = client.post(
            "/assessment/answer",
            json={
                "session_id": session_id, "question_id": routing_question["question_id"],
                "selected_option_id": chosen_option["option_id"],
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        state = main_module._store.load(session_id)
        self.assertEqual(len(state.evidence_ledger), 0)
        self.assertIn("business", state.context_anchor_choices)
        chosen_anchor_id = state.context_anchor_choices["business"]

        # 7. Seed 질문 — 그 Anchor 전용이어야 한다.
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        self.assertEqual(r.status_code, 200, r.text)
        seed_body = r.json()
        seed_question = seed_body["question"]
        self.assertEqual(seed_question["question_id"], f"business_seed_{chosen_anchor_id}")

        seed_option = seed_question["options"][0]
        r = client.post(
            "/assessment/answer",
            json={
                "session_id": session_id, "question_id": seed_question["question_id"],
                "selected_option_id": seed_option["option_id"],
            },
        )
        self.assertEqual(r.status_code, 200, r.text)

        # 8. Seed 다음 — Direct Probe 후보가 없는 Pack이므로 같은 Anchor의 Backup이 나와야 한다.
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        self.assertEqual(r.status_code, 200, r.text)
        second_body = r.json()
        if second_body["status"] != "CONTEXT_EARLY_TERMINATED":
            second_question = second_body["question"]
            self.assertEqual(second_question["question_id"], f"business_backup_{chosen_anchor_id}")
            second_option = second_question["options"][0]
            r = client.post(
                "/assessment/answer",
                json={
                    "session_id": session_id, "question_id": second_question["question_id"],
                    "selected_option_id": second_option["option_id"],
                },
            )
            self.assertEqual(r.status_code, 200, r.text)

        # 9. business Evidence가 실제로 쌓였는지 — question_id 접두사로 그 Context 것만 확인한다.
        state = main_module._store.load(session_id)
        business_evidence = [e for e in state.evidence_ledger if e.context == "business"]
        self.assertTrue(business_evidence, "business Context에서 Evidence가 하나도 안 쌓였다")
        for e in business_evidence:
            self.assertTrue(e.question_id.startswith("business_"))

        # 10. 나머지(game 포함) 질문을 옵션[0] 고정으로 완주한다.
        for _turn in range(_MAX_TURNS):
            r = client.post("/assessment/next-question", params={"session_id": session_id})
            self.assertEqual(r.status_code, 200, r.text)
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
            self.assertEqual(ar.status_code, 200, ar.text)
            if ar.json()["next_action"] == "ASSESSMENT_COMPLETE":
                break

        # 11. Profile/Majors/Subjects까지 깨지지 않고 끝까지 조회된다.
        r = client.get(f"/profile/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        r = client.get(f"/majors/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        relevant = r.json()["relevant_majors"]
        if relevant:
            selected_major_id = relevant[0]["major_id"]
            r = client.get(f"/subjects/{session_id}", params={"selected_major_id": selected_major_id})
            self.assertEqual(r.status_code, 200, r.text)


if __name__ == "__main__":
    unittest.main()
