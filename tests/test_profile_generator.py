"""Career Profile 생성기(§14) 테스트 — 실제 네트워크 호출 없이 Fake LLM Client로 검증한다."""

from __future__ import annotations

import unittest

from src.agents.assessment.profile_generator import generate_career_profile
from src.llm.protocols import LLMCallError
from src.schemas.evidence import EvidenceOrigin, EvidenceRecord, TraitEvidenceSummary
from src.schemas.profile import GeneratedCareerProfile, GeneratedProfileHighlight
from src.schemas.trait import TraitDefinition


def _trait(trait_id: str, dimension: str = "테스트 차원") -> TraitDefinition:
    return TraitDefinition(
        trait_id=trait_id,
        label=trait_id,
        parent_dimension=dimension,
        definition=f"{trait_id}의 정의",
        positive_indicators=["테스트 긍정 지표"],
        conflicting_indicators=["테스트 상충 지표"],
        source_references=["팀 정의 — 테스트"],
        trait_scope="shared",
        minimum_context_count=2,
        primary_vector_group="cognitive",
    )


def _strong(trait_id: str) -> TraitEvidenceSummary:
    return TraitEvidenceSummary(
        trait_id=trait_id, support_count=3, opportunity_count=3, context_count=2, distinct_frame_count=2
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


class GenerateCareerProfileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.trait_ids = [f"trait_{i:02d}" for i in range(5)]
        self.definitions = {tid: _trait(tid) for tid in self.trait_ids}
        self.summaries = {tid: _strong(tid) for tid in self.trait_ids}
        self.ledger = [
            EvidenceRecord(
                evidence_id=f"ev_{tid}",
                answer_id=f"ans_{tid}",
                question_id=f"q_{tid}",
                question_frame_id="problem_check",
                option_role_id="some_role",
                option_text=f"{tid} 관련 실제 선택 문장",
                applied_primary_trait_delta={tid: 1},
                evidence_origin=EvidenceOrigin.PRIMARY_BLUEPRINT,
                context="game",
                source_type="generated_question",
                generator_version="v1",
                quality_gate_status="passed",
            )
            for tid in self.trait_ids
        ]

    def _generate(self, client):
        return generate_career_profile(
            session_id="sess_test",
            user_id="demo_user_01",
            trait_summaries=self.summaries,
            all_trait_definitions=self.definitions,
            evidence_ledger=self.ledger,
            unresolved_conflict_trait_ids=set(),
            llm_client=client,
        )

    def test_happy_path_uses_llm_generated_content(self) -> None:
        result = GeneratedCareerProfile(
            title="구조를 읽는 탐색형",
            highlights=[GeneratedProfileHighlight(trait_id=tid, text=f"{tid} 문장") for tid in self.trait_ids],
            hashtags=["#구조화", "#탐색"],
        )
        client = _ScriptedFakeLLMClient([result])
        profile = self._generate(client)
        self.assertEqual(profile.title, "구조를 읽는 탐색형")
        self.assertEqual(len(profile.highlights), 5)
        self.assertEqual(profile.highlights[0].supporting_trait_ids, ["trait_00"])
        self.assertEqual(client.call_count, 1)

    def test_detailed_evidence_included_regardless_of_llm_outcome(self) -> None:
        result = GeneratedCareerProfile(
            title="제목",
            highlights=[GeneratedProfileHighlight(trait_id=tid, text=f"{tid} 문장") for tid in self.trait_ids],
            hashtags=["#태그"],
        )
        client = _ScriptedFakeLLMClient([result])
        profile = self._generate(client)
        self.assertIn("테스트 차원", profile.detailed_evidence_by_dimension)
        self.assertEqual(len(profile.detailed_evidence_by_dimension["테스트 차원"]), 5)

    def test_mismatched_trait_ids_fall_back_after_retry(self) -> None:
        bad = GeneratedCareerProfile(
            title="제목",
            highlights=[GeneratedProfileHighlight(trait_id="wrong_trait", text="x")] * 1
            + [GeneratedProfileHighlight(trait_id=tid, text=f"{tid} 문장") for tid in self.trait_ids[1:]],
            hashtags=["#태그"],
        )
        client = _ScriptedFakeLLMClient([bad, bad])
        profile = self._generate(client)
        # Fallback 경로 — 실제 Trait definition 기반 문장이어야 한다(다른 학생 Mock 아님).
        self.assertEqual(profile.title, "지금까지의 답변을 바탕으로 한 요약")
        self.assertEqual({s for h in profile.highlights for s in h.supporting_trait_ids}, set(self.trait_ids))
        self.assertEqual(client.call_count, 2)

    def test_llm_call_error_falls_back(self) -> None:
        client = _ScriptedFakeLLMClient([LLMCallError("실패"), LLMCallError("실패")])
        profile = self._generate(client)
        self.assertEqual(profile.title, "지금까지의 답변을 바탕으로 한 요약")
        self.assertEqual(len(profile.highlights), 5)

    def test_fallback_marks_insufficient_traits_honestly(self) -> None:
        summaries = {tid: TraitEvidenceSummary(trait_id=tid, support_count=0, opportunity_count=0) for tid in self.trait_ids}
        client = _ScriptedFakeLLMClient([LLMCallError("실패"), LLMCallError("실패")])
        profile = generate_career_profile(
            session_id="sess_test",
            user_id="demo_user_01",
            trait_summaries=summaries,
            all_trait_definitions=self.definitions,
            evidence_ledger=[],
            unresolved_conflict_trait_ids=set(),
            llm_client=client,
        )
        self.assertTrue(all("추가 탐색이 필요해요" in h.text for h in profile.highlights))


if __name__ == "__main__":
    unittest.main()
