"""v2 Career Profile 생성기 테스트 — 2026-08-23 Trait Ontology v2(2.6단계) §5.

Legacy `tests/test_profile_generator.py`와 같은 패턴(Fake LLM Client, 실제 네트워크
호출 없음)을 v2 입력(TraitVectorEntry)에 대해 적용한다. 핵심 확인 대상: LLM이 꺼지거나
실패해도 항상 이 세션의 실제 v2 Evidence 기반 Fallback을 쓴다(Legacy Mock Profile로
빠지지 않는다)."""

from __future__ import annotations

import unittest

from src.agents.assessment.profile_generator_v2 import generate_career_profile_v2
from src.llm.protocols import LLMCallError
from src.schemas.evidence import EvidenceOrigin, EvidenceRecord
from src.schemas.profile import GeneratedCareerProfile, GeneratedProfileHighlight
from src.schemas.trait import TraitDefinition
from src.schemas.trait_vector_snapshot import TraitVectorEntry


def _trait(trait_id: str) -> TraitDefinition:
    return TraitDefinition(
        trait_id=trait_id, label=trait_id, parent_dimension="테스트 차원", definition=f"{trait_id} 정의",
        positive_indicators=["a"], conflicting_indicators=["b"], source_references=["c"],
        trait_scope="shared", minimum_context_count=1, primary_vector_group="cognitive",
    )


def _entry(trait_id: str, status: str = "STRONG", tendency: float | None = 1.0) -> TraitVectorEntry:
    return TraitVectorEntry(
        trait_id=trait_id, primary_signal_sum=1.0, related_signal_sum=0.0,
        confirmed_related_signal_sum=0.0, primary_evidence_count=3, related_evidence_count=0,
        context_count=2, frame_count=2, question_count=3, tendency_score=tendency,
        evidence_confidence="primary_evidence", status=status,
        supporting_evidence_ids=[f"ev_{trait_id}"],
    )


class _ScriptedFakeLLMClient:
    def __init__(self, scripted_results: list[object]) -> None:
        self._scripted_results = scripted_results
        self.call_count = 0

    def complete_structured(self, *, system_prompt, user_prompt, response_model):
        result = self._scripted_results[self.call_count]
        self.call_count += 1
        if isinstance(result, Exception):
            raise result
        return result


class GenerateCareerProfileV2Test(unittest.TestCase):
    def setUp(self) -> None:
        self.trait_ids = [f"t{i:02d}" for i in range(5)]
        self.definitions = {tid: _trait(tid) for tid in self.trait_ids}
        self.entries = {tid: _entry(tid) for tid in self.trait_ids}
        self.ledger = [
            EvidenceRecord(
                evidence_id=f"ev_{tid}", answer_id=f"ans_{tid}", question_id=f"q_{tid}",
                question_frame_id="problem_check", option_role_id="some_role",
                option_text=f"{tid} 관련 실제 선택 문장", applied_primary_trait_delta={tid: 1},
                evidence_origin=EvidenceOrigin.PRIMARY_BLUEPRINT, context="game",
                source_type="generated_question", generator_version="v1", quality_gate_status="passed",
            )
            for tid in self.trait_ids
        ]

    def _generate(self, client):
        return generate_career_profile_v2(
            session_id="sess_test", user_id="demo_user_01", snapshot_entries=self.entries,
            all_trait_definitions=self.definitions, evidence_ledger=self.ledger, llm_client=client,
        )

    def test_llm_none_uses_deterministic_fallback(self) -> None:
        profile = self._generate(None)
        self.assertEqual(profile.session_id, "sess_test")
        self.assertGreaterEqual(len(profile.highlights), 5)
        # Fallback은 이 세션의 실제 Trait definition을 그대로 인용한다(다른 세션·고정
        # Mock 문구가 섞이지 않는다).
        supporting_ids = {tid for h in profile.highlights for tid in h.supporting_trait_ids}
        self.assertTrue(supporting_ids.issubset(set(self.trait_ids)))

    def test_llm_success_returns_llm_content(self) -> None:
        highlights = [GeneratedProfileHighlight(trait_id=tid, text=f"{tid} 문장이 관찰돼요") for tid in self.trait_ids]
        # select_profile_highlight_traits_v2가 5개(STRONG 5개)를 고르므로 5개만 스크립트에 담는다.
        result = GeneratedCareerProfile(title="이런 경향이 보여요", highlights=highlights[:5], hashtags=["#테스트"])
        client = _ScriptedFakeLLMClient([result])
        profile = self._generate(client)
        self.assertEqual(profile.title, "이런 경향이 보여요")
        self.assertEqual(client.call_count, 1)

    def test_llm_failure_falls_back_to_v2_evidence_not_legacy_mock(self) -> None:
        client = _ScriptedFakeLLMClient([LLMCallError("모의 실패"), LLMCallError("모의 실패")])
        profile = self._generate(client)
        # Fallback 경로로 갔는지 확인 — 이 세션의 실제 Trait만 supporting_trait_ids에 등장.
        supporting_ids = {tid for h in profile.highlights for tid in h.supporting_trait_ids}
        self.assertTrue(supporting_ids.issubset(set(self.trait_ids)))
        self.assertGreater(client.call_count, 0)

    def test_llm_returning_wrong_trait_order_falls_back(self) -> None:
        wrong_order = list(reversed(self.trait_ids))
        highlights = [GeneratedProfileHighlight(trait_id=tid, text=f"{tid} 문장") for tid in wrong_order]
        result = GeneratedCareerProfile(title="문장이 나타났어요", highlights=highlights, hashtags=["#테스트"])
        client = _ScriptedFakeLLMClient([result, result])
        profile = self._generate(client)
        # 순서가 안 맞으면 재시도 후에도 실패 → Fallback.
        supporting_ids = {tid for h in profile.highlights for tid in h.supporting_trait_ids}
        self.assertTrue(supporting_ids.issubset(set(self.trait_ids)))

    def test_not_probed_trait_gets_honest_wording_not_deficiency(self) -> None:
        entries = {tid: _entry(tid, status="NOT_PROBED", tendency=None) for tid in self.trait_ids}
        profile = generate_career_profile_v2(
            session_id="sess_test", user_id="demo_user_01", snapshot_entries=entries,
            all_trait_definitions=self.definitions, evidence_ledger=[], llm_client=None,
        )
        for h in profile.highlights:
            self.assertIn("충분히 확인되지 않았", h.text)
            for banned in ("경험이 부족", "능력이 부족", "약하다", "소질이 없"):
                self.assertNotIn(banned, h.text)


if __name__ == "__main__":
    unittest.main()
