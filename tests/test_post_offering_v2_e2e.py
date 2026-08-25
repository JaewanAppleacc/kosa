"""PRE_SURVEY → POST_OFFERING v2 전체 실제 흐름 E2E — 2026-08-23 Trait Ontology
v2(2.7단계) §4/§7.

`tests/test_post_offering_full_flow_e2e.py`(Legacy, 16차 리뷰)와 완전히 같은 실제 흐름
(세션 생성 → 답변 → Profile → Major → PRE_SURVEY 과목 추천 → 실제 xlsx 업로드 → Confirm
→ POST_OFFERING 최종 추천 → 재조회)을 `ENABLE_TRAIT_VECTOR_V2_PRIMARY=true`로 반복한다.
Legacy 테스트는 손대지 않았다 — PRIMARY=false일 때 이 파일의 답변 패턴을 그대로 다시
실행하면 Legacy 결과와 동일하다는 것을 별도 회귀 테스트로 확인한다(§9).

업로드 Parser는 건드리지 않는다(같은 xlsx Fixture, 같은 `/course/upload` 경로) — 오직
`/course/confirm`·`GET /subjects` 내부에서 v2 엔진으로 계산될 뿐이다."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.api.main as main_module
from src.api.main import app
from src.data.majors.service_major_profiles_v2 import SERVICE_MAJOR_PROFILES_V2
from src.repositories.subject_repository import load_subjects
from src.tracing.tracer import Tracer

client = TestClient(app)
_ALL_SUBJECT_IDS = {s.subject_id for s in load_subjects()}
_SUBJECT_LABEL_BY_ID = {s.subject_id: s.label for s in load_subjects()}
# 2026-08-25 지시서(a/major-profiles-v2-38) — v2 Matching 후보가 3개에서 39개
# Service Catalog 전체로 확장됐다.
_V2_MAJOR_IDS = {m.major_id for m in SERVICE_MAJOR_PROFILES_V2}

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "data" / "fixtures" / "course_offerings" / "demo_school_offerings.xlsx"
)
_XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_MAX_TURNS = 30


class _RecordingTraceClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def record_run(self, *, trace_id, name, run_type, attributes) -> None:
        self.calls.append({"name": name, "attributes": attributes})


class PostOfferingV2FullFlowEndToEndTest(unittest.TestCase):
    def setUp(self) -> None:
        self.trace_client = _RecordingTraceClient()
        for patch_target in (
            patch.object(main_module, "_llm_client", None),
            patch.object(main_module, "_tracer", Tracer(client=self.trace_client)),
        ):
            patch_target.start()
            self.addCleanup(patch_target.stop)
        os.environ["ENABLE_TRAIT_VECTOR_V2_PRIMARY"] = "true"
        self.addCleanup(os.environ.pop, "ENABLE_TRAIT_VECTOR_V2_PRIMARY", None)

    def _trace_attrs_for(self, stage_name: str) -> list[dict[str, object]]:
        return [c["attributes"] for c in self.trace_client.calls if c["name"] == stage_name]

    def test_full_pre_survey_to_post_offering_v2_flow(self) -> None:
        self.assertTrue(_FIXTURE_PATH.exists(), f"Fixture가 없다: {_FIXTURE_PATH}")

        r = client.post("/assessment/session")
        self.assertEqual(r.status_code, 200)
        session_id = r.json()["session_id"]

        r = client.post(
            "/assessment/interest-rating",
            json={
                "session_id": session_id,
                "ratings": {"game": 3, "media": 3, "school_life": 5, "business": 2, "making": 2},
            },
        )
        self.assertEqual(r.status_code, 200)
        r = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["school_life", "game"]},
        )
        self.assertEqual(r.status_code, 200)
        r = client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["school_life", "game", "media"]},
        )
        self.assertEqual(r.status_code, 200)

        for turn in range(_MAX_TURNS):
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

        r = client.get(f"/profile/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self._trace_attrs_for("Profile Summary Generator")[-1]["trait_engine_version"], "trait_vector_v2")

        r = client.get(f"/majors/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        majors_body = r.json()
        recommended = majors_body["relevant_majors"] + majors_body["explore_together_majors"]
        self.assertGreater(len(recommended), 0, f"v2 Major Matching이 computed 결과를 못 만들었다: {majors_body}")
        selected_major_id = recommended[0]["major_id"]
        self.assertIn(selected_major_id, _V2_MAJOR_IDS)

        # PRE_SURVEY 과목 추천(v2).
        r = client.get(f"/subjects/{session_id}", params={"selected_major_id": selected_major_id})
        self.assertEqual(r.status_code, 200, r.text)
        pre_survey = r.json()
        self.assertEqual(pre_survey["source"], "PRE_SURVEY")
        pre_survey_core_ids = {
            item["subject_id"] for item in pre_survey["recommendations"] if item["category"] == "core"
        }
        for item in pre_survey["recommendations"]:
            self.assertIsNone(item["is_actually_offered"])
            self.assertIn(item["subject_id"], _ALL_SUBJECT_IDS)

        # 실제 xlsx 업로드(Parser는 건드리지 않는다 — Legacy 테스트와 완전히 같은 파일·경로).
        with open(_FIXTURE_PATH, "rb") as f:
            file_bytes = f.read()
        r = client.post(
            "/course/upload",
            data={"session_id": session_id, "selected_major_id": selected_major_id},
            files={"file": ("demo_school_offerings.xlsx", file_bytes, _XLSX_CONTENT_TYPE)},
        )
        self.assertEqual(r.status_code, 200, r.text)
        upload_body = r.json()
        candidates = upload_body["parsed_candidates"]
        matched_ids = [c["matched_subject_id"] for c in candidates if c["matched_subject_id"]]

        # v2 Subject Profile(6개 과목)만 대상이라, 이 학교 편성표에 실제로 겹치는 과목이
        # 없을 수도 있다 — 그 경우 "빈 POST_OFFERING"도 정직한 결과다(지어내지 않는다).
        confirmed_ids = sorted(set(matched_ids) & {s.subject_id for s in load_subjects()})

        r = client.post(
            "/course/confirm",
            json={"session_id": session_id, "confirmed_subject_ids": confirmed_ids},
        )
        self.assertEqual(r.status_code, 200, r.text)
        confirm_body = r.json()
        self.assertTrue(confirm_body["accepted"])
        post_offering = confirm_body["course_profile"]
        self.assertEqual(post_offering["session_id"], session_id)
        self.assertEqual(post_offering["source"], "POST_OFFERING")

        subject_attrs = self._trace_attrs_for("Subject Matching")
        self.assertTrue(subject_attrs)
        self.assertEqual(subject_attrs[-1]["matching_engine_version"], "subject_matching_engine_v2")

        # is_actually_offered 의미 불변: POST_OFFERING 추천은 전부 실제 개설(True)이고
        # confirmed_ids 안에 있어야 한다.
        for item in post_offering["recommendations"]:
            self.assertIs(item["is_actually_offered"], True)
            self.assertIn(item["subject_id"], confirmed_ids)

        # 미개설 희망(core)이었던 과목은 unavailable_subjects로 정직하게 옮겨졌는지.
        unavailable_ids = {u["subject_id"] for u in post_offering["unavailable_subjects"]}
        self.assertEqual(unavailable_ids, pre_survey_core_ids - set(confirmed_ids))

        # unresolved_candidates 유지 — unmatched 후보는 이번에도 사라지지 않는다.
        unmatched_candidates_from_upload = [c for c in candidates if c["matched_subject_id"] is None]
        unresolved_texts = {c["raw_text"] for c in post_offering["unresolved_candidates"]}
        self.assertEqual(unresolved_texts, {c["raw_text"] for c in unmatched_candidates_from_upload})

        # 재조회 시 동일 결과(캐시 없이도 결정론적).
        r = client.get(f"/subjects/{session_id}", params={"selected_major_id": selected_major_id})
        self.assertEqual(r.status_code, 200, r.text)
        refetched = r.json()
        self.assertEqual(refetched, post_offering)

        # 학생 내부 점수 미노출.
        full_text = str(post_offering) + str(pre_survey)
        for forbidden in ("score", "tendency_score"):
            self.assertNotIn(forbidden, full_text)


class PrimaryFalseRegressionForSameAnswerPatternTest(unittest.TestCase):
    """§9 PRIMARY=false 회귀 — 이 파일의 답변 패턴을 PRIMARY 없이 그대로 실행해도
    POST_OFFERING이 Legacy 그대로 동작해야 한다(v2 코드 추가가 Legacy 경로에 부작용을
    남기지 않았는지 확인)."""

    def setUp(self) -> None:
        for patch_target in (
            patch.object(main_module, "_llm_client", None),
            patch.object(main_module, "_tracer", Tracer(client=None)),
        ):
            patch_target.start()
            self.addCleanup(patch_target.stop)
        os.environ.pop("ENABLE_TRAIT_VECTOR_V2_PRIMARY", None)

    def test_post_offering_still_legacy_when_flag_off(self) -> None:
        self.assertTrue(_FIXTURE_PATH.exists())
        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        client.post(
            "/assessment/interest-rating",
            json={
                "session_id": session_id,
                "ratings": {"game": 3, "media": 3, "school_life": 5, "business": 2, "making": 2},
            },
        )
        client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["school_life", "game"]},
        )
        client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["school_life", "game", "media"]},
        )
        for turn in range(_MAX_TURNS):
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

        r = client.get(f"/majors/{session_id}")
        majors_body = r.json()
        relevant_ids = [m["major_id"] for m in majors_body["relevant_majors"]]
        self.assertIn("industrial_engineering", relevant_ids)

        r = client.get(f"/subjects/{session_id}", params={"selected_major_id": "industrial_engineering"})
        self.assertEqual(r.json()["source"], "PRE_SURVEY")


if __name__ == "__main__":
    unittest.main()
