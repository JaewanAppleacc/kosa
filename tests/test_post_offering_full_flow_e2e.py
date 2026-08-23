"""PRE_SURVEY → POST_OFFERING 전체 실제 흐름 E2E — 2026-08-26 16차 리뷰 §12.

`tests/test_course_planning_full_flow_e2e.py`(15차 리뷰)가 PRE_SURVEY까지 실제 Assessment
Answer Flow로 검증했다 — 이 파일은 그 뒤를 이어 실제 학교 개설과목 파일
(`data/fixtures/course_offerings/demo_school_offerings.xlsx`) 업로드부터 POST_OFFERING
최종 추천, `GET /subjects` 재조회까지 전부 실제 흐름으로 검증한다:

    POST /assessment/session → 관심도·Context 선택·확정 → 실제 질문·답변 반복
    → GET /profile → GET /majors → 추천된 대표 전공 선택(industrial_engineering)
    → PRE_SURVEY 과목 추천 → demo_school_offerings.xlsx 업로드 → Parsed Candidate 확인
    → confirmed_subject_ids 제출 → POST_OFFERING 최종 추천 → GET /subjects 재조회

Trait Summary를 직접 주입하지 않는다 — 관심도·Context 선택과 옵션[0] 고정 선택 패턴은
결정론적으로 항상 industrial_engineering을 고유한 "관련성 높음" 전공으로 만든다는 것을
사전에 직접 실행해 확인했다(억지로 조작한 게 아니라, 이 패턴이 실제로 그렇게 수렴한다).
`_llm_client`/`_tracer`는 강제로 꺼서 실제 LLM·LangSmith 네트워크 호출이 전혀 없다."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.api.main as main_module
from src.api.main import app
from src.repositories.subject_repository import load_subjects
from src.tracing.tracer import Tracer

client = TestClient(app)
_ALL_SUBJECT_IDS = {s.subject_id for s in load_subjects()}
_SUBJECT_LABEL_BY_ID = {s.subject_id: s.label for s in load_subjects()}

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "data" / "fixtures" / "course_offerings" / "demo_school_offerings.xlsx"
)
_XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_MAX_TURNS = 30


def _assert_no_float(node, path: str, test_case: unittest.TestCase) -> None:
    if isinstance(node, float):
        test_case.fail(f"{path}에 float 값이 노출됨: {node}")
    elif isinstance(node, dict):
        for key, value in node.items():
            _assert_no_float(value, f"{path}.{key}", test_case)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            _assert_no_float(value, f"{path}[{i}]", test_case)


class PostOfferingFullFlowEndToEndTest(unittest.TestCase):
    def setUp(self) -> None:
        for patch_target in (
            patch.object(main_module, "_llm_client", None),
            patch.object(main_module, "_tracer", Tracer(client=None)),
        ):
            patch_target.start()
            self.addCleanup(patch_target.stop)

    def test_full_pre_survey_to_post_offering_flow(self) -> None:
        self.assertTrue(_FIXTURE_PATH.exists(), f"Fixture가 없다: {_FIXTURE_PATH}")

        # 1. 세션 생성
        r = client.post("/assessment/session")
        self.assertEqual(r.status_code, 200)
        session_id = r.json()["session_id"]

        # 2~4. 관심도·Context 선택·확정 — school_life를 가장 강하게 준다(아래 옵션[0]
        # 고정 패턴과 합쳐지면 industrial_engineering으로 수렴함을 사전에 확인했다).
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

        # 5~6. 질문↔답변 반복 — 항상 첫 번째 선택지를 고른다(결정론적).
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
                    "session_id": session_id,
                    "question_id": question["question_id"],
                    "selected_option_id": option["option_id"],
                },
            )
            self.assertEqual(ar.status_code, 200, ar.text)
            if ar.json()["next_action"] == "ASSESSMENT_COMPLETE":
                break

        # 7. Profile
        r = client.get(f"/profile/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["session_id"], session_id)

        # 8. Majors — industrial_engineering이 고유한 "관련성 높음"이어야 한다.
        r = client.get(f"/majors/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        majors_body = r.json()
        relevant_ids = [m["major_id"] for m in majors_body["relevant_majors"]]
        self.assertIn(
            "industrial_engineering", relevant_ids,
            f"industrial_engineering이 관련성 높음에 없다 — 실제: {relevant_ids}",
        )
        selected_major_id = "industrial_engineering"

        # 9. PRE_SURVEY 과목 추천
        r = client.get(f"/subjects/{session_id}", params={"selected_major_id": selected_major_id})
        self.assertEqual(r.status_code, 200, r.text)
        pre_survey = r.json()
        self.assertEqual(pre_survey["source"], "PRE_SURVEY")
        self.assertEqual(pre_survey["session_id"], session_id)
        pre_survey_subject_ids = {item["subject_id"] for item in pre_survey["recommendations"]}
        self.assertTrue(pre_survey_subject_ids, "PRE_SURVEY 추천이 비어 있다")
        for item in pre_survey["recommendations"]:
            self.assertIsNone(item["is_actually_offered"])
            self.assertIn(item["subject_id"], _ALL_SUBJECT_IDS)
            self.assertEqual(item["label"], _SUBJECT_LABEL_BY_ID[item["subject_id"]])

        # 10. 학교 개설과목 파일 업로드 (실제 xlsx 바이트, 실제 Parser)
        with open(_FIXTURE_PATH, "rb") as f:
            file_bytes = f.read()
        r = client.post(
            "/course/upload",
            data={"session_id": session_id, "selected_major_id": selected_major_id},
            files={"file": ("demo_school_offerings.xlsx", file_bytes, _XLSX_CONTENT_TYPE)},
        )
        self.assertEqual(r.status_code, 200, r.text)
        upload_body = r.json()
        self.assertEqual(upload_body["session_id"], session_id)
        self.assertEqual(upload_body["selected_major_id"], selected_major_id)
        candidates = upload_body["parsed_candidates"]
        self.assertTrue(candidates)

        # 11. Parsed Candidate 확인 — high/low confidence(=Mock 아닌 실제 과목) 후보 중
        # matched_subject_id가 있는 것만 확정 대상으로 고른다. unmatched는 애초에
        # matched_subject_id가 없어 여기서 제외된다.
        matched_ids = [c["matched_subject_id"] for c in candidates if c["matched_subject_id"]]
        self.assertGreater(len(matched_ids), 0)
        confirmed_ids = sorted(set(matched_ids))

        # 12. confirmed_subject_ids 제출 → POST_OFFERING 최종 추천
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

        # 필수 검증: POST 추천 항목은 모두 실제 개설과목(is_actually_offered=True)이고,
        # 전부 confirmed_ids 안에 있다.
        self.assertTrue(post_offering["recommendations"], "POST_OFFERING 추천이 비어 있다")
        for item in post_offering["recommendations"]:
            self.assertIs(item["is_actually_offered"], True)
            self.assertIn(item["subject_id"], confirmed_ids)
            self.assertIn(item["subject_id"], _ALL_SUBJECT_IDS)
            self.assertEqual(item["label"], _SUBJECT_LABEL_BY_ID[item["subject_id"]])
            self.assertTrue(item["label"])

        # 미개설 희망과목은 unavailable_subjects로 이동했는지 — PRE_SURVEY의 core 과목
        # 중 이번에 개설되지 않은 게 있으면 여기 있어야 한다.
        unavailable_ids = {u["subject_id"] for u in post_offering["unavailable_subjects"]}
        pre_survey_core_ids = {
            item["subject_id"] for item in pre_survey["recommendations"] if item["category"] == "core"
        }
        expected_unavailable = pre_survey_core_ids - set(confirmed_ids)
        self.assertEqual(unavailable_ids, expected_unavailable)
        for item in post_offering["recommendations"]:
            self.assertNotIn(item["subject_id"], unavailable_ids, "미개설 과목이 추천에도 남아있다")

        # alternative는 실제 개설과목이며 replaces_subject_id가 있어야 한다.
        alternatives = [item for item in post_offering["recommendations"] if item["category"] == "alternative"]
        for alt in alternatives:
            self.assertIsNotNone(alt["replaces_subject_id"])
            self.assertIn(alt["replaces_subject_id"], unavailable_ids)
            self.assertIs(alt["is_actually_offered"], True)

        # low/unmatched 후보가 자동으로 개설과목 취급되지 않았는지 — 이번 confirmed_ids에
        # 포함하지 않은 low/unmatched 후보의 subject_id는 추천에 없어야 한다.
        unmatched_or_unconfirmed = {
            c["matched_subject_id"] for c in candidates
            if c["matched_subject_id"] and c["matched_subject_id"] not in confirmed_ids
        }
        for item in post_offering["recommendations"]:
            self.assertNotIn(item["subject_id"], unmatched_or_unconfirmed)

        # 2026-08-27 17차 리뷰 §1: unmatched 후보(matched_subject_id가 없는 것)는
        # Confirm 이후에도 사라지지 않고 unresolved_candidates에 그대로 남아야 한다.
        # 이 Fixture(demo_school_offerings.xlsx)는 "정체불명 과목ABC"라는 실제 unmatched
        # 후보를 포함하도록 만들어졌다.
        unmatched_candidates_from_upload = [c for c in candidates if c["matched_subject_id"] is None]
        self.assertTrue(unmatched_candidates_from_upload, "이 Fixture는 unmatched 후보를 포함해야 한다")
        unresolved_texts = {c["raw_text"] for c in post_offering["unresolved_candidates"]}
        self.assertEqual(unresolved_texts, {c["raw_text"] for c in unmatched_candidates_from_upload})
        for c in post_offering["unresolved_candidates"]:
            self.assertIsNone(c["matched_subject_id"])
            self.assertEqual(c["confidence"], "unmatched")
        # 확정한 high/low 후보는 unresolved에 남지 않는다.
        unresolved_matched_ids = [c["matched_subject_id"] for c in post_offering["unresolved_candidates"]]
        for confirmed_id in confirmed_ids:
            self.assertNotIn(confirmed_id, unresolved_matched_ids)

        # 2026-08-28 18차 리뷰 §1/§5: "교과(군)"은 편제표 열 제목이지 과목이 아니므로
        # Parser 후보 자체에 아예 없어야 한다(unmatched로도 잡히면 안 된다) — high/low/
        # unmatched 어느 confidence로도 존재하지 않는다.
        all_raw_texts = {c["raw_text"] for c in candidates}
        self.assertNotIn("교과(군)", all_raw_texts)
        self.assertIn("정체불명 과목ABC", all_raw_texts, "실제 unmatched 후보는 여전히 노출돼야 한다")

        _assert_no_float(post_offering, "post_offering", self)
        _assert_no_float(upload_body, "upload_body", self)

        # 13. GET /subjects 재조회 — 같은 selected_major_id면 CONFIRMED 상태를 그대로
        # 다시 반환해야 한다(캐시 재계산이든 뭐든, 매번 결과가 같아야 한다).
        r = client.get(f"/subjects/{session_id}", params={"selected_major_id": selected_major_id})
        self.assertEqual(r.status_code, 200, r.text)
        refetched = r.json()
        self.assertEqual(refetched["source"], "POST_OFFERING")
        self.assertEqual(refetched, post_offering)

        # session_id가 끝까지 동일했는지 최종 확인.
        for payload in (pre_survey, upload_body, confirm_body, refetched):
            self.assertEqual(payload["session_id"], session_id)

        # 원본 파일·임시 경로·학생 답변 원문이 응답 어디에도 노출되지 않았는지.
        full_text = str(post_offering) + str(upload_body)
        self.assertNotIn("/tmp/", full_text)
        self.assertNotIn("Traceback", full_text)


if __name__ == "__main__":
    unittest.main()
