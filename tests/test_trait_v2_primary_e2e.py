"""ENABLE_TRAIT_VECTOR_V2_PRIMARY 실제 Answer Flow End-to-End 테스트 — 2026-08-23
Trait Ontology v2(2.6단계) §12.

`tests/test_course_planning_full_flow_e2e.py`와 같은 원칙(진짜 세션 생성→답변→Profile→
전공→과목 흐름, Mock/Backup 질문 경로만 타도록 LLM·LangSmith를 결정론적으로 고정)을
따르되, ENABLE_TRAIT_VECTOR_V2_PRIMARY(및 필요할 때 ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES)
Flag를 켠 상태에서 v2 Profile·Major Matching·Subject Matching이 실제로 쓰이는지,
검수 미완료(DRAFT) Direct Probe Signal이 Primary 계산에서 제외되는지, 학생 내부 점수가
API에 노출되지 않는지를 확인한다."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from pathlib import Path

import src.api.main as main_module
from src.api.main import app
from src.data.majors.service_major_profiles_v2 import SERVICE_MAJOR_PROFILES_V2
from src.repositories.subject_repository import load_subjects
from src.tracing.tracer import Tracer

client = TestClient(app)
# v2 Primary 경로는 subject_profiles_v2.jsonl(2026-08-25 a/subject-mapping-38-majors
# 확장분 포함)에서 후보를 뽑는다 — Legacy subjects.jsonl만 보면 확장분 신규 과목이
# 빠져 오탐(False positive AssertionError)이 난다.
_V2_SUBJECT_PROFILES_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "master" / "subject_profiles_v2.jsonl"
)
_ALL_SUBJECT_IDS = {s.subject_id for s in load_subjects()} | {
    s.subject_id for s in load_subjects(_V2_SUBJECT_PROFILES_PATH)
}
_MAX_TURNS = 40

_FORBIDDEN_KEY_SUBSTRINGS = ("score", "tendency", "confidence", "weight")
# API 응답에 정상적으로 존재하는, 위 부분 문자열과 우연히 겹치는 안전한 Key는 예외로 둔다.
_ALLOWED_KEYS_DESPITE_SUBSTRING_MATCH = {"evidence_sufficiency"}


class _RecordingTraceClient:
    """`tests/test_tracing.py::_FakeTraceClient`와 같은 대역 — 실제 LangSmith 호출 없이
    Sanitizer를 통과한 뒤의 최종 attributes만 기록한다."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def record_run(self, *, trace_id, name, run_type, attributes) -> None:
        self.calls.append({"name": name, "attributes": attributes})


def _scan_for_forbidden_keys(obj: object, path: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_lower = str(key).lower()
            if key not in _ALLOWED_KEYS_DESPITE_SUBSTRING_MATCH and any(
                s in key_lower for s in _FORBIDDEN_KEY_SUBSTRINGS
            ):
                hits.append(f"{path}.{key}")
            hits.extend(_scan_for_forbidden_keys(value, f"{path}.{key}"))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            hits.extend(_scan_for_forbidden_keys(item, f"{path}[{i}]"))
    return hits


class TraitV2PrimaryE2ETestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.trace_client = _RecordingTraceClient()
        for patch_target in (
            patch.object(main_module, "_llm_client", None),
            patch.object(main_module, "_tracer", Tracer(client=self.trace_client)),
        ):
            patch_target.start()
            self.addCleanup(patch_target.stop)
        self._env_keys_to_restore: dict[str, str | None] = {}

    def _set_env(self, **kwargs: str) -> None:
        for key, value in kwargs.items():
            self._env_keys_to_restore.setdefault(key, os.environ.get(key))
            os.environ[key] = value
            self.addCleanup(self._restore_env, key)

    def _restore_env(self, key: str) -> None:
        original = self._env_keys_to_restore.get(key)
        if original is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original

    def _drive_session_to_completion(self, context_ids: list[str]) -> str:
        r = client.post("/assessment/session")
        self.assertEqual(r.status_code, 200)
        session_id = r.json()["session_id"]

        r = client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 5, "media": 5, "school_life": 4}},
        )
        self.assertEqual(r.status_code, 200)

        r = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": context_ids[:2]},
        )
        self.assertEqual(r.status_code, 200)

        r = client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": context_ids},
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
        return session_id

    def _trace_attrs_for(self, stage_name: str) -> list[dict[str, object]]:
        return [c["attributes"] for c in self.trace_client.calls if c["name"] == stage_name]


class PrimaryFalseLegacyRegressionTest(TraitV2PrimaryE2ETestBase):
    """§9 "PRIMARY=false: 현재 Legacy Profile·Matching 결과와 완전히 동일"."""

    def test_primary_false_uses_legacy_engine(self) -> None:
        os.environ.pop("ENABLE_TRAIT_VECTOR_V2_PRIMARY", None)
        session_id = self._drive_session_to_completion(["game", "media", "school_life"])

        r = client.get(f"/profile/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)

        profile_attrs = self._trace_attrs_for("Profile Summary Generator")
        self.assertTrue(profile_attrs)
        self.assertEqual(profile_attrs[-1].get("trait_engine_version"), "legacy")
        self.assertEqual(profile_attrs[-1].get("profile_generation_path"), "legacy")

        r = client.get(f"/majors/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        # PRIMARY=false일 때는 "Major Matching" Trace Stage 자체가 없어야 한다(v2 경로
        # 진입 자체를 안 함).
        self.assertEqual(self._trace_attrs_for("Major Matching"), [])


class PrimaryTrueV2PathTest(TraitV2PrimaryE2ETestBase):
    """§9 "PRIMARY=true: Profile·Major·Subject가 모두 v2 입력을 사용"."""

    def setUp(self) -> None:
        super().setUp()
        self._set_env(ENABLE_TRAIT_VECTOR_V2_PRIMARY="true")

    def test_v2_profile_major_subject_full_flow(self) -> None:
        session_id = self._drive_session_to_completion(["game", "media", "school_life"])

        r = client.get(f"/profile/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        profile_body = r.json()
        self.assertGreaterEqual(len(profile_body["highlights"]), 5)
        profile_attrs = self._trace_attrs_for("Profile Summary Generator")
        self.assertTrue(profile_attrs)
        self.assertEqual(profile_attrs[-1]["trait_engine_version"], "trait_vector_v2")
        self.assertEqual(profile_attrs[-1]["profile_generation_path"], "v2_primary")

        r = client.get(f"/majors/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        majors_body = r.json()
        recommended = majors_body["relevant_majors"] + majors_body["explore_together_majors"]
        self.assertGreater(
            len(recommended), 0,
            "v2 Major Matching으로 computed 대표 전공이 하나도 안 나왔다 — Trait Summary를 "
            "직접 주입해 억지로 통과시키지 않는다(§12).",
        )
        major_attrs = self._trace_attrs_for("Major Matching")
        self.assertTrue(major_attrs)
        self.assertEqual(major_attrs[-1]["matching_engine_version"], "matching_engine_v2")

        # 2026-08-25 지시서(a/major-profiles-v2-38) — v2 Matching 후보가 3개
        # (media_communication/hci_ux/industrial_engineering)에서 39개 Service
        # Catalog 전체로 확장됐다. 이 E2E는 "v2 Major Matching이 실제로 동작해
        # 무언가를 추천한다"를 확인하는 것이 목적이지 특정 3개로 제한하는 것이
        # 목적이 아니었다 — 39개 Catalog 전체를 허용 집합으로 넓힌다.
        selected_major_id = recommended[0]["major_id"]
        self.assertIn(selected_major_id, {m.major_id for m in SERVICE_MAJOR_PROFILES_V2})

        r = client.get(f"/subjects/{session_id}", params={"selected_major_id": selected_major_id})
        self.assertEqual(r.status_code, 200, r.text)
        subjects_body = r.json()
        self.assertEqual(subjects_body["source"], "PRE_SURVEY")
        for item in subjects_body["recommendations"]:
            self.assertIn(item["subject_id"], _ALL_SUBJECT_IDS)
        subject_attrs = self._trace_attrs_for("Subject Matching")
        self.assertTrue(subject_attrs)
        self.assertEqual(subject_attrs[-1]["matching_engine_version"], "subject_matching_engine_v2")

        # §12 "학생 내부 점수 API 미노출" — Profile/Majors/Subjects 응답 어디에도
        # score·tendency·confidence·weight류 내부 값이 새면 안 된다.
        for body, label in ((profile_body, "profile"), (majors_body, "majors"), (subjects_body, "subjects")):
            with self.subTest(endpoint=label):
                self.assertEqual(_scan_for_forbidden_keys(body), [])

    def test_evidence_insufficient_returns_honest_result_not_legacy_substitute(self) -> None:
        """§9 "v2 Evidence가 부족하면 Legacy로 조용히 대체하지 않는다 — 정직하게
        EVIDENCE_NOT_READY 또는 insufficient 결과 제공"."""

        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 5, "media": 5, "school_life": 4}},
        )
        client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "media"]},
        )
        client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game", "media", "school_life"]},
        )
        # 딱 1개 질문에만 답한다 — Major Matching이 computed에 도달하기엔 근거가 부족해야 한다.
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        question = r.json()["question"]
        client.post(
            "/assessment/answer",
            json={
                "session_id": session_id, "question_id": question["question_id"],
                "selected_option_id": question["options"][0]["option_id"],
            },
        )

        r = client.get(f"/majors/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        recommended = body["relevant_majors"] + body["explore_together_majors"]
        self.assertEqual(recommended, [])
        self.assertIsNotNone(body["insufficient_evidence_message"])

        r = client.get(f"/subjects/{session_id}", params={"selected_major_id": "media_communication"})
        self.assertEqual(r.status_code, 422)
        self.assertIn(
            r.json()["detail"]["error_code"], ("EVIDENCE_NOT_READY", "MAJOR_NOT_SELECTABLE"),
        )


class PrimaryTrueDirectProbeExclusionTest(TraitV2PrimaryE2ETestBase):
    """§3/§12 "DRAFT Direct Probe Signal Primary 제외"."""

    def setUp(self) -> None:
        super().setUp()
        self._set_env(ENABLE_TRAIT_VECTOR_V2_PRIMARY="true", ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES="true")

    def test_draft_direct_probe_signal_excluded_from_primary_but_visible_in_gate_diagnostics(self) -> None:
        session_id = self._drive_session_to_completion(["game", "media", "school_life"])

        r = client.get(f"/profile/{session_id}")
        self.assertEqual(r.status_code, 200, r.text)

        # V2 Direct Probe 질문이 최소 1개는 답변됐어야 이 테스트가 의미가 있다 — 실제
        # 커밋된 v2_direct_probe_question_review_status.json은 전부 DRAFT이므로, Direct
        # Probe가 하나라도 답변됐다면 그 Signal은 반드시 Primary 계산에서 빠져야 한다.
        probe_opportunities = main_module._store.load(session_id).v2_probe_opportunities
        if not probe_opportunities:
            self.skipTest("이번 실행에서 V2 Direct Probe 질문이 서빙되지 않았다(Mock 조건 의존)")

        profile_attrs = self._trace_attrs_for("Profile Summary Generator")[-1]
        self.assertEqual(profile_attrs["trait_engine_version"], "trait_vector_v2")
        self.assertGreaterEqual(
            profile_attrs["excluded_unreviewed_signal_count"], 1,
            "Direct Probe 질문이 답변됐는데도 검수 미완료로 제외된 Signal이 0개다 — "
            "Fail-Closed 게이트가 실제로 걸러내는지 확인해야 한다.",
        )


if __name__ == "__main__":
    unittest.main()
