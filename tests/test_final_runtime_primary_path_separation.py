"""ENABLE_TRAIT_VECTOR_V2_PRIMARY OFF/ON 경로 분리 회귀 테스트 — 2026-08-25
지시서(a/final-runtime-v2-primary) §1/§3/§7.

§1 실측 재현: `ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES`·`ENABLE_CONTEXT_PACK_RUNTIME`·
`ENABLE_CONTEXT_SELECTION_4_PLUS_1`만 켜고 `ENABLE_TRAIT_VECTOR_V2_PRIMARY`가 빠지면,
검사 자체는 15개 Context·4+1 정책으로 정상 완료되지만 `/majors`가 Legacy Matching
경로(matching_engine.py::compute_major_match)로 계산돼 특정 Persona(예술/창작 계열
Context에 집중)에서 검사 완료 후에도 `insufficient_evidence_message`가 반환된다.
네 번째 Flag(PRIMARY)를 마저 켜면 같은 Persona·같은 답변 패턴이 v2 24-Trait 경로
(matching_engine_v2.py::compute_major_match_v2)로 다시 계산돼 정상적으로 추천이
나온다 — 이 파일은 그 대조를 실제 TestClient(FastAPI 앱을 그대로 구동, Mock 없음)
호출로 고정한다."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api import main as main_module
from src.api.main import app

client = TestClient(app)

# 세 Flag는 항상 켜 둔다(§2 최종 실행 환경의 기본 배선) — PRIMARY만 토글해 그 Flag
# 하나만의 영향을 분리해서 본다.
_BASE_FLAGS = {
    "ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES": "true",
    "ENABLE_CONTEXT_PACK_RUNTIME": "true",
    "ENABLE_CONTEXT_SELECTION_4_PLUS_1": "true",
}
# 빈 문자열로 명시한다 — `_flag_on()`은 "" 를 OFF로 판정하므로, 실행 셸의 실제
# 환경에 이 이름이 우연히 켜져 있어도(clear=True로 PATH/HOME 등 전체를 지우는
# 위험한 방법 없이) 이 테스트 안에서는 항상 확실히 꺼진다.
_PRIMARY_OFF = dict(_BASE_FLAGS, ENABLE_TRAIT_VECTOR_V2_PRIMARY="")
_PRIMARY_ON = dict(_BASE_FLAGS, ENABLE_TRAIT_VECTOR_V2_PRIMARY="true")

# §1 실측 재현 Fixture — 예술·창작 계열 Context에 집중한 결정론적 답변 패턴(항상 첫
# 번째 선택지). Legacy 엔진에서는 usable_trait/usable_vector_group 요건을 못 채워
# insufficient가 나오고, v2 PRIMARY 엔진에서는 나오지 않는 실측 사례다.
_CREATIVE_PERSONA_CONTEXTS = {"art_design", "writing", "fashion_beauty", "travel"}


def _run_full_assessment(user_id: str, high_contexts: set[str]) -> str:
    """15개 Context → 관심도 → 선호 4개+Contrast 1개 → 질문 완료까지 실제 TestClient로
    끝까지 진행하고 session_id를 돌려준다."""

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
                return session_id
            continue
        question = resp["question"]
        option = question["options"][0]
        ans = client.post(
            "/assessment/answer",
            json={"session_id": session_id, "question_id": question["question_id"], "selected_option_id": option["option_id"]},
        ).json()
        if ans.get("next_action") == "ASSESSMENT_COMPLETE":
            return session_id
    raise AssertionError(f"{user_id}: assessment did not complete within 500 questions")


class PrimaryOffReproducesInsufficientEvidenceTest(unittest.TestCase):
    """§1 재현 — PRIMARY만 빠진 상태에서 실제로 무엇이 깨지는지 고정한다."""

    def test_primary_flag_is_off_when_not_set(self) -> None:
        with patch.dict("os.environ", _PRIMARY_OFF):
            from src.services.feature_flags import trait_vector_v2_primary_enabled

            self.assertFalse(trait_vector_v2_primary_enabled())

    def test_creative_persona_reproduces_insufficient_evidence_with_primary_off(self) -> None:
        with patch.dict("os.environ", _PRIMARY_OFF):
            session_id = _run_full_assessment("primary_off_repro", _CREATIVE_PERSONA_CONTEXTS)
            majors = client.get(f"/majors/{session_id}").json()
        total = len(majors["relevant_majors"]) + len(majors["explore_together_majors"])
        # §1 실측: 검사는 정상 완료되지만 Legacy 엔진으로는 이 Persona가 usable_trait/
        # usable_vector_group 요건을 못 채워 insufficient가 반환된다.
        self.assertEqual(total, 0)
        self.assertIsNotNone(majors["insufficient_evidence_message"])

    def test_majors_endpoint_never_records_v2_engine_trace_when_primary_off(self) -> None:
        """Legacy `/majors` 경로(PRIMARY OFF) 자체는 Major Matching Trace Stage를
        전혀 기록하지 않는다(PRIMARY 분기 안에서만 그 기록이 있다, main.py:1878-1891)
        — 그래서 "Legacy 엔진 사용"은 v2 전용 속성(matching_engine_version=
        matching_engine_v2·trait_engine_version)이 단 하나도 기록되지 않는 것으로
        확인한다."""
        with (
            patch.dict("os.environ", _PRIMARY_OFF),
            patch.object(main_module._tracer, "record_stage") as mock_record_stage,
        ):
            session_id = _run_full_assessment("primary_off_engine_check", {"school_life", "business", "science", "law_politics"})
            client.get(f"/majors/{session_id}")
        recorded_stages = [c.kwargs for c in mock_record_stage.call_args_list]
        for stage in recorded_stages:
            attrs = stage.get("attributes", {})
            self.assertNotEqual(attrs.get("matching_engine_version"), "matching_engine_v2")
            self.assertNotIn("trait_engine_version", attrs)


class PrimaryOnUsesV2EngineTest(unittest.TestCase):
    """§3 — 네 Flag를 전부 켜면 같은 Persona가 v2 24-Trait 경로로 정상 계산된다."""

    def test_primary_flag_is_on(self) -> None:
        with patch.dict("os.environ", _PRIMARY_ON):
            from src.services.feature_flags import trait_vector_v2_primary_enabled

            self.assertTrue(trait_vector_v2_primary_enabled())

    def test_creative_persona_no_longer_insufficient_with_primary_on(self) -> None:
        """§1에서 재현한 바로 그 Persona·같은 답변 패턴이 PRIMARY ON에서는 정상
        추천을 반환한다."""
        with patch.dict("os.environ", _PRIMARY_ON):
            session_id = _run_full_assessment("primary_on_fix", _CREATIVE_PERSONA_CONTEXTS)
            majors = client.get(f"/majors/{session_id}").json()
        total = len(majors["relevant_majors"]) + len(majors["explore_together_majors"])
        self.assertIsNone(majors["insufficient_evidence_message"])
        self.assertGreaterEqual(total, 1)
        for m in majors["relevant_majors"] + majors["explore_together_majors"]:
            self.assertTrue(m["description"].strip())
            # §3 "내부 점수는 공개 API에 없음"
            self.assertEqual(
                set(m.keys()),
                {"major_id", "label", "description", "relevance_label", "evidence_sufficiency", "repeated_context_count"},
            )

    def test_majors_and_profile_endpoints_use_v2_engine_when_primary_on(self) -> None:
        with (
            patch.dict("os.environ", _PRIMARY_ON),
            patch.object(main_module._tracer, "record_stage") as mock_record_stage,
        ):
            session_id = _run_full_assessment("primary_on_engine_check", {"school_life", "business", "science", "law_politics"})
            client.get(f"/profile/{session_id}")
            client.get(f"/majors/{session_id}")

        recorded_stages = [c.kwargs for c in mock_record_stage.call_args_list]
        profile_stages = [s for s in recorded_stages if s.get("attributes", {}).get("graph_node") == "profile_summary_generator"]
        matching_stages = [s for s in recorded_stages if s.get("attributes", {}).get("graph_node") == "major_matching"]
        self.assertTrue(profile_stages, "Profile Summary Generator stage가 기록되지 않았다")
        self.assertTrue(matching_stages, "Major Matching stage가 기록되지 않았다")

        for attrs in (s["attributes"] for s in profile_stages):
            self.assertEqual(attrs.get("trait_engine_version"), "trait_vector_v2")
            self.assertEqual(attrs.get("profile_generation_path"), "v2_primary")
            self.assertIsInstance(attrs.get("usable_trait_count"), int)

        for attrs in (s["attributes"] for s in matching_stages):
            self.assertEqual(attrs.get("trait_engine_version"), "trait_vector_v2")
            self.assertEqual(attrs.get("matching_engine_version"), "matching_engine_v2")
            self.assertIsInstance(attrs.get("usable_trait_count"), int)

    def test_repeated_run_of_same_persona_returns_identical_major_order(self) -> None:
        with patch.dict("os.environ", _PRIMARY_ON):
            sid1 = _run_full_assessment("primary_on_repeat_1", {"school_life", "business", "science", "law_politics"})
            majors1 = client.get(f"/majors/{sid1}").json()
            sid2 = _run_full_assessment("primary_on_repeat_2", {"school_life", "business", "science", "law_politics"})
            majors2 = client.get(f"/majors/{sid2}").json()

        ids1 = [m["major_id"] for m in majors1["relevant_majors"] + majors1["explore_together_majors"]]
        ids2 = [m["major_id"] for m in majors2["relevant_majors"] + majors2["explore_together_majors"]]
        self.assertEqual(ids1, ids2)


if __name__ == "__main__":
    unittest.main()
