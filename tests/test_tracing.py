"""§24 LangSmith Observability 테스트 — 실제 네트워크 호출은 하지 않는다. Fake로
TraceClient Protocol을 만족시켜서 Tracer의 fail-open·Sanitizer 적용을 검증한다.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch
from uuid import UUID

from src.ids import generate_trace_id
from src.tracing.protocols import TraceError
from src.tracing.sanitizer import ALLOWED_TRACE_ATTRIBUTE_KEYS, sanitize_trace_attributes
from src.tracing.settings import TracingSettings, TracingSettingsError, load_tracing_settings, tracing_enabled
from src.tracing.tracer import Tracer

_FAKE_TRACE_ID = "9f8b6b0a-9f1a-4b3a-8e77-4b8c2b6a1234"


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

    def test_free_text_value_in_an_allowed_key_is_dropped(self) -> None:
        """2026-08-22 리뷰: 허용된 Key라도 값이 사전 정의된 고정 문구가 아니면 버려야
        한다 — planner_decision_reason에 자유서술 문장을 넣어도 통과하면 안 된다."""

        sanitized = sanitize_trace_attributes(
            {"planner_decision_reason": "학생이 게임에서 전략을 짜는 걸 좋아한다고 답했음"}
        )
        self.assertEqual(sanitized, {})

    def test_error_key_itself_is_no_longer_allowed(self) -> None:
        """2026-08-22 리뷰: 예외 원문이 실릴 수 있던 `error` 필드는 아예 허용 목록에서
        뺐다 — error_type/error_code 같은 구조화 필드로만 오류 정보를 보낸다."""

        sanitized = sanitize_trace_attributes({"error": "LLM 호출 실패: Connection to 10.0.0.5 refused"})
        self.assertEqual(sanitized, {})
        self.assertNotIn("error", ALLOWED_TRACE_ATTRIBUTE_KEYS)

    def test_error_type_only_accepts_fixed_values(self) -> None:
        self.assertEqual(
            sanitize_trace_attributes({"error_type": "llm_call_error"}), {"error_type": "llm_call_error"}
        )
        self.assertEqual(
            sanitize_trace_attributes({"error_type": "Traceback (most recent call last): ..."}), {}
        )

    def test_error_code_accepts_fixed_code_shape_only(self) -> None:
        self.assertEqual(sanitize_trace_attributes({"error_code": "LLM_TIMEOUT"}), {"error_code": "LLM_TIMEOUT"})
        self.assertEqual(sanitize_trace_attributes({"error_code": "학생 답변: 실패"}), {})

    def test_nested_object_with_unexpected_keys_is_dropped_entirely(self) -> None:
        """token_usage처럼 중첩 dict를 허용하는 필드도, 정해진 키 외에 다른 값(이름·
        답변 원문 등)이 섞여 있으면 필드 전체를 버린다 — 일부만 걸러내지 않는다."""

        sanitized = sanitize_trace_attributes(
            {"token_usage": {"prompt_tokens": 120, "student_name": "홍길동"}}
        )
        self.assertEqual(sanitized, {})

    def test_valid_token_usage_dict_is_preserved(self) -> None:
        payload = {"prompt_tokens": 120, "completion_tokens": 40, "total_tokens": 160}
        self.assertEqual(sanitize_trace_attributes({"token_usage": payload}), {"token_usage": payload})

    def test_trait_ids_must_be_a_list_of_slugs(self) -> None:
        self.assertEqual(
            sanitize_trace_attributes({"trait_ids": ["causal_analysis", "planning"]}),
            {"trait_ids": ["causal_analysis", "planning"]},
        )
        self.assertEqual(
            sanitize_trace_attributes({"trait_ids": ["causal_analysis", "학생이 직접 쓴 문장"]}), {}
        )

    def test_valid_context_and_frame_ids_are_preserved(self) -> None:
        attributes = {"context_id": "game", "frame_id": "new_tool", "role_id": "advance_planning"}
        self.assertEqual(sanitize_trace_attributes(attributes), attributes)

    def test_knowledge_subgraph_extractor_counts_are_preserved(self) -> None:
        """2026-08-28 19차 리뷰 §10: Knowledge Subgraph Extractor Stage가 남기는 개수
        요약 메타데이터만 허용한다. 2026-08-29 19차 후속 보완: has_confirmed_course_profile
        (Confirm 여부)과 has_subject_nodes(과목 Node 존재 여부)는 서로 다른 사실이라
        별도 필드로 나뉘었다."""

        attributes = {
            "node_count": 12, "edge_count": 20, "trait_node_count": 4, "major_node_count": 2,
            "department_node_count": 3, "subject_node_count": 2,
            "has_confirmed_course_profile": True, "has_subject_nodes": True,
        }
        self.assertEqual(sanitize_trace_attributes(attributes), attributes)

    def test_knowledge_subgraph_extractor_counts_reject_negative_or_non_int(self) -> None:
        self.assertEqual(sanitize_trace_attributes({"node_count": -1}), {})
        self.assertEqual(sanitize_trace_attributes({"node_count": 1.5}), {})
        self.assertEqual(sanitize_trace_attributes({"node_count": "12"}), {})

    def test_has_confirmed_course_profile_and_has_subject_nodes_strictly_accept_bool_only(self) -> None:
        """2026-08-29 19차 후속 보완: Python은 bool이 int의 하위 타입이라 `1==True`가
        성립하지만, Sanitizer는 `isinstance(value, bool)`로 엄격히 검사해 `1`/`0` 같은
        정수를 bool로 오인해 통과시키지 않는다."""

        for key in ("has_confirmed_course_profile", "has_subject_nodes"):
            with self.subTest(key=key):
                self.assertEqual(sanitize_trace_attributes({key: True}), {key: True})
                self.assertEqual(sanitize_trace_attributes({key: False}), {key: False})
                self.assertEqual(sanitize_trace_attributes({key: "true"}), {})
                self.assertEqual(sanitize_trace_attributes({key: 1}), {})
                self.assertEqual(sanitize_trace_attributes({key: 0}), {})
                self.assertEqual(sanitize_trace_attributes({key: None}), {})
                self.assertEqual(sanitize_trace_attributes({key: []}), {})
                self.assertEqual(sanitize_trace_attributes({key: {}}), {})

    def test_trait_vector_shadow_snapshot_counts_are_preserved(self) -> None:
        """2026-08-23 Trait Ontology v2(1.5단계) §9/§13 — Shadow Snapshot Stage가 남기는
        12개 집계 필드만 허용한다. 학생 답변 원문·Trait Signal 세부 내용(trait_id·weight·
        related_concept_ids)은 Key 자체가 없어 구조적으로 샐 수 없다."""

        attributes = {
            "core_trait_count": 24, "observable_trait_count": 19, "directly_measurable_count": 12,
            "related_only_count": 7, "not_probed_count": 5, "observed_in_session_count": 3,
            "hypothesis_count": 1, "promoted_related_count": 1, "conflict_count": 0,
            "mapping_source_exact_count": 3, "mapping_source_legacy_adapter_count": 0,
            "mapping_missing_count": 0,
        }
        self.assertEqual(sanitize_trace_attributes(attributes), attributes)

    def test_trait_vector_shadow_snapshot_counts_reject_negative_or_non_int(self) -> None:
        for key in ("core_trait_count", "mapping_source_exact_count", "conflict_count"):
            with self.subTest(key=key):
                self.assertEqual(sanitize_trace_attributes({key: -1}), {})
                self.assertEqual(sanitize_trace_attributes({key: 1.5}), {})
                self.assertEqual(sanitize_trace_attributes({key: "3"}), {})

    def test_session_id_and_raw_answer_text_have_no_allowlisted_key(self) -> None:
        """session_id/학생 답변 원문/질문 원문은 Key 자체가 Allowlist에 없어 어떤 값을
        보내도 구조적으로 샐 수 없다."""

        self.assertEqual(
            sanitize_trace_attributes(
                {
                    "session_id": "sess_00000000000000000000000000000000",
                    "user_id": "demo_user_01",
                    "student_answer_text": "학생이 실제로 고른 선택지 문장",
                    "question_text": "질문 원문",
                }
            ),
            {},
        )


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
        tracer.record_stage(trace_id=_FAKE_TRACE_ID, stage_name="Target Planner", attributes={"stop_reason": "CONTINUE"})

    def test_records_run_with_sanitized_attributes(self) -> None:
        fake = _FakeTraceClient()
        tracer = Tracer(client=fake)
        tracer.record_stage(
            trace_id=_FAKE_TRACE_ID,
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
            tracer.record_stage(trace_id=_FAKE_TRACE_ID, stage_name="Question Generator", attributes={})
        except Exception as exc:  # pragma: no cover - 실패하면 바로 테스트 실패로 보고
            self.fail(f"Tracer가 Client 예외를 삼키지 않고 전파함(fail-open 위반): {exc}")


class GenerateTraceIdIsAParsableUuidTest(unittest.TestCase):
    """2026-08-22 리뷰: 예전엔 "trace_<hex>" 접두사 문자열이라 LangSmith SDK의 UUID
    타입 Run.trace_id 검증에 걸릴 수 있었다 — 이제 순수 UUID여야 한다."""

    def test_generated_trace_id_parses_as_uuid(self) -> None:
        trace_id = generate_trace_id()
        parsed = UUID(trace_id)  # 파싱 실패하면 ValueError로 테스트가 바로 실패한다
        self.assertEqual(str(parsed), trace_id)

    def test_generated_trace_id_has_no_prefix(self) -> None:
        trace_id = generate_trace_id()
        self.assertFalse(trace_id.startswith("trace_"))

    def test_two_calls_produce_different_ids(self) -> None:
        self.assertNotEqual(generate_trace_id(), generate_trace_id())


class LangSmithAdapterSendsUuidTraceIdTest(unittest.TestCase):
    """실제 네트워크 호출 없이(langsmith.Client.create_run을 Mock으로 가로채서) Adapter가
    실제로 UUID 형식 trace_id와 Sanitizer를 거친 attributes만 보내는지 확인한다.

    2026-08-22 6차 리뷰: 실제 계정으로 Smoke Test(scripts/langsmith_smoke_test.py)를
    돌려서 확인한 서버 응답 — 예전처럼 매 Stage를 독립된 평행 Run으로 trace_id만 채워
    보내면 서버가 `400 Bad Request: dotted_order is required when trace_id is
    provided`로 전부 거부한다(그동안 이 서비스가 실제 LangSmith에 보낸 Trace는 단 하나도
    기록되지 않았다는 뜻). 이제 세션(trace_id)마다 Root Run 하나 + 각 Stage를 그 Root의
    Child Run으로 묶는다(공식 RunTree가 parent_run_id·dotted_order를 자동 계산)."""

    def test_first_record_run_creates_root_then_child(self) -> None:
        from src.tracing.langsmith_client import LangSmithTraceClient

        settings = TracingSettings(api_key="ls-fake-key-for-test", project="career-agent-test")
        with patch("langsmith.Client.create_run") as mock_create_run:
            client = LangSmithTraceClient(settings)
            trace_id = generate_trace_id()
            sanitized_attributes = sanitize_trace_attributes(
                {"context_id": "game", "free_text_answer": "학생이 실제로 쓴 문장(반드시 걸러졌어야 함)"}
            )
            client.record_run(
                trace_id=trace_id, name="Evidence Update", run_type="chain", attributes=sanitized_attributes
            )

        # 이 trace_id로 처음 기록하는 Stage라 Root Run 1개 + Child Run 1개, 총 2번 전송된다.
        self.assertEqual(mock_create_run.call_count, 2)
        root_kwargs, child_kwargs = (call.kwargs for call in mock_create_run.call_args_list)

        # Root Run: id==trace_id, trace_id==trace_id, parent_run_id 없음(최상위 Run).
        self.assertIsInstance(root_kwargs["trace_id"], UUID)
        self.assertEqual(str(root_kwargs["trace_id"]), trace_id)
        self.assertEqual(root_kwargs["id"], root_kwargs["trace_id"])
        self.assertNotIn("parent_run_id", root_kwargs)
        self.assertEqual(root_kwargs["inputs"], {})  # Root 자체엔 학생 관련 정보를 담지 않는다.

        # Child Run: Stage별 새 UUID, Root와 같은 trace_id, parent_run_id==Root.id,
        # dotted_order는 Root의 dotted_order로 시작한다("."로 이어붙임 — 임의 문자열 아님).
        self.assertEqual(child_kwargs["trace_id"], root_kwargs["trace_id"])
        self.assertNotEqual(child_kwargs["id"], root_kwargs["id"])
        self.assertEqual(child_kwargs["parent_run_id"], root_kwargs["id"])
        self.assertTrue(child_kwargs["dotted_order"].startswith(root_kwargs["dotted_order"] + "."))
        self.assertEqual(child_kwargs["inputs"], {"context_id": "game"})
        self.assertNotIn("free_text_answer", str(child_kwargs["inputs"]))

    def test_second_record_run_same_trace_id_reuses_root(self) -> None:
        """같은 세션(같은 trace_id) 안에서는 Root를 한 번만 만든다 — 여러 Stage가 전부
        같은 Root의 Child로 붙어야 한다."""

        from src.tracing.langsmith_client import LangSmithTraceClient

        settings = TracingSettings(api_key="ls-fake-key-for-test", project="career-agent-test")
        with patch("langsmith.Client.create_run") as mock_create_run:
            client = LangSmithTraceClient(settings)
            trace_id = generate_trace_id()
            client.record_run(trace_id=trace_id, name="Context Selector", run_type="chain", attributes={})
            client.record_run(trace_id=trace_id, name="Evidence Update", run_type="chain", attributes={})
            client.record_run(trace_id=trace_id, name="Target Planner", run_type="chain", attributes={})

        # Root 1개(1번째 호출에서만) + Child 3개 = 총 4번 전송. Root가 다시 만들어지지 않는다.
        self.assertEqual(mock_create_run.call_count, 4)
        all_kwargs = [call.kwargs for call in mock_create_run.call_args_list]
        root_kwargs = all_kwargs[0]
        child_kwargs_list = all_kwargs[1:]

        self.assertEqual(len({k["id"] for k in all_kwargs}), 4)  # id는 전부 서로 다르다(Root+Child 3개)
        for child_kwargs in child_kwargs_list:
            self.assertEqual(child_kwargs["trace_id"], root_kwargs["trace_id"])
            self.assertEqual(child_kwargs["parent_run_id"], root_kwargs["id"])
            self.assertTrue(child_kwargs["dotted_order"].startswith(root_kwargs["dotted_order"] + "."))

    def test_different_trace_ids_get_different_roots(self) -> None:
        """서로 다른 세션(서로 다른 trace_id)은 서로 다른 Root를 써야 한다 — 한 세션의
        Child가 다른 세션의 Root 밑에 잘못 묶이면 안 된다."""

        from src.tracing.langsmith_client import LangSmithTraceClient

        settings = TracingSettings(api_key="ls-fake-key-for-test", project="career-agent-test")
        with patch("langsmith.Client.create_run") as mock_create_run:
            client = LangSmithTraceClient(settings)
            trace_id_a = generate_trace_id()
            trace_id_b = generate_trace_id()
            client.record_run(trace_id=trace_id_a, name="Evidence Update", run_type="chain", attributes={})
            client.record_run(trace_id=trace_id_b, name="Evidence Update", run_type="chain", attributes={})

        # 각 trace_id마다 Root+Child가 새로 생기므로 총 4번 전송(Root 2개 + Child 2개).
        self.assertEqual(mock_create_run.call_count, 4)
        all_kwargs = [call.kwargs for call in mock_create_run.call_args_list]
        root_a, child_a, root_b, child_b = all_kwargs

        self.assertNotEqual(root_a["id"], root_b["id"])
        self.assertEqual(str(root_a["trace_id"]), trace_id_a)
        self.assertEqual(str(root_b["trace_id"]), trace_id_b)
        self.assertEqual(child_a["parent_run_id"], root_a["id"])
        self.assertEqual(child_b["parent_run_id"], root_b["id"])
        self.assertNotEqual(child_a["parent_run_id"], child_b["parent_run_id"])

    def test_invalid_trace_id_raises_trace_error_instead_of_silently_failing(self) -> None:
        from src.tracing.langsmith_client import LangSmithTraceClient

        settings = TracingSettings(api_key="ls-fake-key-for-test", project="career-agent-test")
        client = LangSmithTraceClient(settings)
        with self.assertRaises(TraceError):
            client.record_run(
                trace_id="not-a-uuid", name="Evidence Update", run_type="chain", attributes={}
            )

    def test_root_creation_failure_is_not_cached_and_retried_next_call(self) -> None:
        """Root를 처음 만들 때(.post()) 네트워크 실패로 예외가 나면, 그 실패한 Root를
        캐시에 남겨두지 않아야 한다 — 다음 호출이 다시 Root 생성을 시도할 수 있어야
        한다(예전 실패가 이후 모든 Trace를 영구히 막으면 안 된다)."""

        from src.tracing.langsmith_client import LangSmithTraceClient

        settings = TracingSettings(api_key="ls-fake-key-for-test", project="career-agent-test")
        client = LangSmithTraceClient(settings)
        trace_id = generate_trace_id()

        with patch("langsmith.Client.create_run", side_effect=RuntimeError("모의 네트워크 장애")):
            with self.assertRaises(TraceError):
                client.record_run(trace_id=trace_id, name="Evidence Update", run_type="chain", attributes={})

        self.assertNotIn(trace_id, client._roots)

        with patch("langsmith.Client.create_run") as mock_create_run:
            client.record_run(trace_id=trace_id, name="Evidence Update", run_type="chain", attributes={})
        self.assertEqual(mock_create_run.call_count, 2)  # 이번엔 Root+Child가 정상적으로 다시 만들어진다


if __name__ == "__main__":
    unittest.main()
