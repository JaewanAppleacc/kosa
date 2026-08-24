"""4개 Flag 전부 ON(PRIMARY 포함) 상태에서 5종 결정론적 Persona 회귀 테스트 —
2026-08-25 지시서(a/final-runtime-v2-primary) §4/§7.

각 Persona는 서로 다른 4개 선호 Context(+ 시스템이 고른 Contrast 1개, 최종 5개)에
집중한 결정론적 답변 패턴(항상 첫 번째 선택지)이다. 검사 완료 후 `/majors`가 최소
1개 이상 반환해야 하고, 같은 Persona를 2회 실행하면(다른 session_id라도) 결과 순서가
동일해야 한다.

NO_SIGNAL만 의도적으로 고른 극단 Fixture(§4 "별도로 유지할 수 있다")는 여기 5종
Persona에 섞지 않는다 — 이 파일의 모든 Persona는 특정 Context에 뚜렷하게 집중한
"정상" 패턴이다."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)

_ALL_FOUR_FLAGS_ON = {
    "ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES": "true",
    "ENABLE_TRAIT_VECTOR_V2_PRIMARY": "true",
    "ENABLE_CONTEXT_PACK_RUNTIME": "true",
    "ENABLE_CONTEXT_SELECTION_4_PLUS_1": "true",
}

# §4가 요구한 5종 — 분석·계획형 / 창작·표현형 / 사람·협업형 / 실행·도구형 /
# 선택지가 분산된 혼합형. 실제 `/contexts` 15개 중 서로 겹치지 않는 4개씩 고른다.
PERSONAS: dict[str, set[str]] = {
    "analytical_planning": {"school_life", "business", "science", "law_politics"},
    "creative_expression": {"art_design", "writing", "fashion_beauty", "travel"},
    "people_collaboration": {"volunteer", "media", "cooking", "history_humanities"},
    "execution_tools": {"making", "sports", "game"} | {"cooking"},
    "mixed_scattered": {"history_humanities", "game", "fashion_beauty", "science"},
}


def _run_full_assessment(user_id: str, high_contexts: set[str]) -> tuple[str, set[str]]:
    """15개 Context → 관심도 → 선호 4개+Contrast 1개(최종 5개) → 질문 완료까지
    실제 TestClient로 끝까지 진행한다. `(session_id, final_context_ids)`를 돌려준다."""

    contexts = client.get("/contexts").json()
    context_ids = [c["context_id"] for c in contexts["contexts"]]
    assert len(context_ids) == 15, f"expected 15 contexts, got {len(context_ids)}"

    session_id = client.post("/assessment/session", json={"user_id": user_id}).json()["session_id"]

    ratings = {cid: (5 if cid in high_contexts else 1) for cid in context_ids}
    r = client.post("/assessment/interest-rating", json={"session_id": session_id, "ratings": ratings})
    assert r.status_code == 200, r.text

    preferred = [c for c in high_contexts if c in context_ids][:4]
    if len(preferred) < 4:
        preferred += [c for c in context_ids if c not in preferred][: 4 - len(preferred)]
    sel = client.post(
        "/assessment/context-select",
        json={"session_id": session_id, "selected_preferred_context_ids": preferred},
    ).json()
    contrast_id = sel["contrast_context_id"]

    final_ids = preferred + [contrast_id]
    r = client.post("/assessment/context-confirm", json={"session_id": session_id, "final_context_ids": final_ids})
    assert r.status_code == 200, r.text

    for _ in range(500):
        resp = client.post("/assessment/next-question", params={"session_id": session_id}).json()
        if resp.get("question") is None:
            if resp.get("assessment_complete"):
                return session_id, set(final_ids)
            continue
        question = resp["question"]
        option = question["options"][0]
        ans = client.post(
            "/assessment/answer",
            json={"session_id": session_id, "question_id": question["question_id"], "selected_option_id": option["option_id"]},
        ).json()
        if ans.get("next_action") == "ASSESSMENT_COMPLETE":
            return session_id, set(final_ids)
    raise AssertionError(f"{user_id}: assessment did not complete within 500 questions")


class FiveDeterministicPersonaRegressionTest(unittest.TestCase):
    """§4 — 5종 Persona 전부 최종 Context 5개·질문 완료·`/majors` 1개 이상."""

    def _for_each_persona(self, check):
        with patch.dict("os.environ", _ALL_FOUR_FLAGS_ON):
            for name, contexts in PERSONAS.items():
                with self.subTest(persona=name):
                    check(name, contexts)

    def test_each_persona_reaches_five_final_contexts(self) -> None:
        def check(name: str, contexts: set[str]) -> None:
            _, final_contexts = _run_full_assessment(f"persona_{name}_contexts", contexts)
            self.assertEqual(len(final_contexts), 5, f"{name}: 최종 Context가 5개가 아니다 — {final_contexts}")

        self._for_each_persona(check)

    def test_each_persona_returns_at_least_one_major(self) -> None:
        def check(name: str, contexts: set[str]) -> None:
            session_id, _ = _run_full_assessment(f"persona_{name}_majors", contexts)
            majors = client.get(f"/majors/{session_id}").json()
            total = len(majors["relevant_majors"]) + len(majors["explore_together_majors"])
            self.assertGreaterEqual(total, 1, f"{name}: 반환된 전공이 없다 — {majors}")
            self.assertIsNone(majors["insufficient_evidence_message"], f"{name}: insufficient_evidence_message가 남아 있다")

        self._for_each_persona(check)

    def test_each_persona_repeated_run_returns_identical_major_order(self) -> None:
        def check(name: str, contexts: set[str]) -> None:
            sid1, _ = _run_full_assessment(f"persona_{name}_repeat_a", contexts)
            majors1 = client.get(f"/majors/{sid1}").json()
            sid2, _ = _run_full_assessment(f"persona_{name}_repeat_b", contexts)
            majors2 = client.get(f"/majors/{sid2}").json()

            ids1 = [m["major_id"] for m in majors1["relevant_majors"] + majors1["explore_together_majors"]]
            ids2 = [m["major_id"] for m in majors2["relevant_majors"] + majors2["explore_together_majors"]]
            self.assertEqual(ids1, ids2, f"{name}: 같은 Persona 2회 실행 결과 순서가 다르다")

        self._for_each_persona(check)


if __name__ == "__main__":
    unittest.main()
