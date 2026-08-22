"""§24 LangSmith Observability 테스트 — 실제 네트워크 호출은 하지 않는다. Fake로
TraceClient Protocol을 만족시켜서 Tracer의 fail-open·Sanitizer 적용을 검증한다.
"""

from __future__ import annotations

import unittest

from src.tracing.protocols import TraceError
from src.tracing.sanitizer import ALLOWED_TRACE_ATTRIBUTE_KEYS, sanitize_trace_attributes
from src.tracing.settings import TracingSettingsError, load_tracing_settings, tracing_enabled
from src.tracing.tracer import Tracer


class LoadTracingSettingsTest(unittest.TestCase):
    def test_missing_env_vars_raises(self) -> None:
        with self.assertRaises(TracingSettingsError):
            load_tracing_settings(env={})

    def test_partial_env_vars_raises(self) -> None:
        with self.assertRaises(TracingSettingsError):
            load_tracing_settings(env={"LANGSMITH_API_KEY": "ls-test"})

    def test_complete_env_vars_loads(self) -> None:
        settings = load_tracing_settings(
            env={"LANGSMITH_API_KEY": "ls-test", "LANGSMITH_PROJECT": "career-agent"}
        )
        self.assertEqual(settings.api_key, "ls-test")
        self.assertEqual(settings.project, "career-agent")


class TracingEnabledTest(unittest.TestCase):
    def test_unset_is_disabled(self) -> None:
        self.assertFalse(tracing_enabled(env={}))

    def test_true_variants_enable(self) -> None:
        for value in ["1", "true", "True", "yes"]:
            self.assertTrue(tracing_enabled(env={"LANGSMITH_TRACING": value}), msg=value)

    def test_false_or_garbage_disables(self) -> None:
        for value in ["0", "false", "", "nope"]:
            self.assertFalse(tracing_enabled(env={"LANGSMITH_TRACING": value}), msg=value)


class SanitizeTraceAttributesTest(unittest.TestCase):
    def test_allowed_keys_pass_through(self) -> None:
        attributes = {
            "context_id": "game",
            "trait_id": "causal_analysis",
            "graph_node": "target_planner",
            "planner_decision_reason": "관심 지점 심화 확인",
            "stop_reason": "CONTINUE",
            "latency_ms": 120,
        }
        self.assertEqual(sanitize_trace_attributes(attributes), attributes)

    def test_denylisted_pii_fields_are_dropped(self) -> None:
        """CLAUDE.md: "이름, 학교, 연락처, 자유서술 원문, 성적 원문, 상세 Career Profile
        문장을 LangSmith에 보내지 않는다" — 설계안 §24 금지 목록을 그대로 넣어도 걸러져야 한다."""

        attributes = {
            "student_name": "홍길동",
            "school_name": "OO고등학교",
            "phone_number": "010-1234-5678",
            "free_text_answer": "저는 게임에서 전략을 짜는 게 재밌어요",
            "grade_raw": "국어 1등급",
            "career_profile_sentence": "구조를 읽고 사람의 반응까지 생각하는 학생이에요",
            "context_id": "game",  # 허용된 필드도 같이 넣어서 "전부 삭제"가 아님을 확인
        }
        sanitized = sanitize_trace_attributes(attributes)
        self.assertEqual(sanitized, {"context_id": "game"})

    def test_unknown_field_is_dropped_by_default(self) -> None:
        """Allowlist 방식 확인: 목록에 없는 새 필드는 위험 여부와 무관하게 기본적으로 거부."""

        sanitized = sanitize_trace_attributes({"some_new_field_nobody_reviewed": "x"})
        self.assertEqual(sanitized, {})

    def test_none_values_for_allowed_keys_are_preserved(self) -> None:
        # main.py 계측 지점에서 값이 없을 때(예: decision이 None) None을 그대로 넘기는
        # 경우가 있다 — Sanitizer가 그 자체를 걸러내면 안 된다(값 검사가 아니라 키 검사).
        sanitized = sanitize_trace_attributes({"frame_id": None})
        self.assertEqual(sanitized, {"frame_id": None})

    def test_allowlist_does_not_include_free_text_shaped_keys(self) -> None:
        """허용 목록 자체에 원문성 필드 이름이 실수로 들어가 있지 않은지 방어적으로 확인."""

        forbidden_key_fragments = ["name", "school", "phone", "answer_text", "grade", "profile_sentence"]
        for key in ALLOWED_TRACE_ATTRIBUTE_KEYS:
            for fragment in forbidden_key_fragments:
                self.assertNotIn(fragment, key, msg=f"{key!r}에 금지 필드 조각 {fragment!r} 포함")


class _FakeTraceClient:
    """TraceClient Protocol을 만족하는 테스트용 대역 — 실제 LangSmith 호출 없음."""

    def __init__(self, should_fail: bool = False) -> None:
        self._should_fail = should_fail
        self.calls: list[dict[str, object]] = []

    def record_run(self, *, trace_id, name, run_type, attributes) -> None:
        if self._should_fail:
            raise TraceError("모의 LangSmith 장애")
        self.calls.append(
            {"trace_id": trace_id, "name": name, "run_type": run_type, "attributes": attributes}
        )


class TracerTest(unittest.TestCase):
    def test_none_client_is_a_safe_no_op(self) -> None:
        tracer = Tracer(client=None)
        # 예외 없이 조용히 넘어가야 한다 — assertRaises가 아니라 "호출해도 안 터짐"이 검증 대상.
        tracer.record_stage(trace_id="trace_1", stage_name="Target Planner", attributes={"stop_reason": "CONTINUE"})

    def test_records_run_with_sanitized_attributes(self) -> None:
        fake = _FakeTraceClient()
        tracer = Tracer(client=fake)
        tracer.record_stage(
            trace_id="trace_1",
            stage_name="Evidence Update",
            attributes={"context_id": "game", "free_text_answer": "학생이 실제로 쓴 문장"},
        )
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(fake.calls[0]["attributes"], {"context_id": "game"})
        self.assertNotIn("free_text_answer", fake.calls[0]["attributes"])

    def test_client_failure_does_not_propagate_fail_open(self) -> None:
        """CLAUDE.md: "LangSmith 장애는 로컬 로그만 남기고 사용자 Session을 중단하지
        않는다" — Client가 예외를 던져도 Tracer 밖으로 전파되면 안 된다."""

        fake = _FakeTraceClient(should_fail=True)
        tracer = Tracer(client=fake)
        try:
            tracer.record_stage(trace_id="trace_1", stage_name="Question Generator", attributes={})
        except Exception as exc:  # pragma: no cover - 실패하면 바로 테스트 실패로 보고
            self.fail(f"Tracer가 Client 예외를 삼키지 않고 전파함(fail-open 위반): {exc}")


if __name__ == "__main__":
    unittest.main()
