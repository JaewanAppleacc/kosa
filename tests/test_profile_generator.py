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
            title="구조를 읽고 이유를 탐색하는 모습이 보여요",
            highlights=[GeneratedProfileHighlight(trait_id=tid, text=f"{tid} 문장") for tid in self.trait_ids],
            hashtags=["#구조화", "#탐색"],
        )
        client = _ScriptedFakeLLMClient([result])
        profile = self._generate(client)
        self.assertEqual(profile.title, "구조를 읽고 이유를 탐색하는 모습이 보여요")
        self.assertEqual(len(profile.highlights), 5)
        self.assertEqual(profile.highlights[0].supporting_trait_ids, ["trait_00"])
        self.assertEqual(client.call_count, 1)

    def test_detailed_evidence_included_regardless_of_llm_outcome(self) -> None:
        result = GeneratedCareerProfile(
            title="여러 관점을 비교하려는 경향이 확인됐어요",
            highlights=[GeneratedProfileHighlight(trait_id=tid, text=f"{tid} 문장") for tid in self.trait_ids],
            hashtags=["#태그"],
        )
        client = _ScriptedFakeLLMClient([result])
        profile = self._generate(client)
        self.assertIn("테스트 차원", profile.detailed_evidence_by_dimension)
        self.assertEqual(len(profile.detailed_evidence_by_dimension["테스트 차원"]), 5)

    def test_mismatched_trait_ids_fall_back_after_retry(self) -> None:
        bad = GeneratedCareerProfile(
            title="여러 관점을 비교하려는 경향이 확인됐어요",
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
        self.assertTrue(all("충분히 확인되지 않았어요" in h.text for h in profile.highlights))
        self.assertTrue(all("경험이 부족" not in h.text for h in profile.highlights))


class GeneratedCareerProfileGuardTest(unittest.TestCase):
    """2026-08-21 리뷰: "학생을 유형으로 규정하지 않는다"와 "Evidence 부족을 학생의
    결핍처럼 표현하지 않는다"를 기계적으로도 막는지 확인한다."""

    def test_rejects_title_ending_with_type_suffix(self) -> None:
        with self.assertRaises(ValueError):
            GeneratedCareerProfile(
                title="생각을 시각적으로 풀어내고 이유를 파헤치는 탐구자형",
                highlights=[GeneratedProfileHighlight(trait_id="a", text="문장")],
                hashtags=["#태그"],
            )

    def test_rejects_title_containing_유형_or_타입(self) -> None:
        with self.assertRaises(ValueError):
            GeneratedCareerProfile(
                title="탐구 유형에 가까운 학생",
                highlights=[GeneratedProfileHighlight(trait_id="a", text="문장")],
                hashtags=["#태그"],
            )

    def test_rejects_role_noun_titles_without_type_suffix(self) -> None:
        """2026-08-21 재리뷰: "~형"이 없어도 "꼼꼼한 탐색자"처럼 사람을 가리키는 명사로
        끝나면 정체성 명명이다 — 기획자가 준 금지 예시 4개를 그대로 검증한다."""

        for bad_title in ["꼼꼼한 탐색자", "논리적인 분석가", "창의적인 설계자", "세심한 관찰자"]:
            with self.assertRaises(ValueError, msg=bad_title):
                GeneratedCareerProfile(
                    title=bad_title,
                    highlights=[GeneratedProfileHighlight(trait_id="a", text="문장")],
                    hashtags=["#태그"],
                )

    def test_rejects_copula_ending_even_though_it_ends_with_요(self) -> None:
        """"~예요/~이에요"는 "요"로 끝나지만 "당신은 OO다"라는 계사 서술이라 여전히
        정체성 명명이다 — 단순히 "요로 끝나는지"만 보면 이 경우를 놓친다."""

        with self.assertRaises(ValueError):
            GeneratedCareerProfile(
                title="논리적인 탐색가예요",
                highlights=[GeneratedProfileHighlight(trait_id="a", text="문장")],
                hashtags=["#태그"],
            )

    def test_accepts_all_four_recommended_example_titles(self) -> None:
        recommended = [
            "원인을 깊이 파악하려는 모습이 보여요",
            "시각적으로 표현하려는 경향이 두드러졌어요",
            "답변에서 계획적으로 접근하는 모습이 나타났어요",
            "여러 관점을 비교하려는 경향이 확인됐어요",
        ]
        for title in recommended:
            profile = GeneratedCareerProfile(
                title=title,
                highlights=[GeneratedProfileHighlight(trait_id="a", text="문장")],
                hashtags=["#태그"],
            )
            self.assertEqual(profile.title, title)

    def test_accepts_non_typed_title(self) -> None:
        profile = GeneratedCareerProfile(
            title="생각을 시각적으로 풀어내고 이유를 탐색하는 모습이 보여요",
            highlights=[GeneratedProfileHighlight(trait_id="a", text="문장")],
            hashtags=["#태그"],
        )
        self.assertTrue(profile.title.endswith("보여요"))

    def test_rejects_deficiency_phrasing_in_highlight(self) -> None:
        with self.assertRaises(ValueError):
            GeneratedProfileHighlight(trait_id="planning", text="계획을 세우는 데는 아직 경험이 부족해요")

    def test_accepts_observation_gap_phrasing_in_highlight(self) -> None:
        highlight = GeneratedProfileHighlight(
            trait_id="planning", text="이번 답변에서는 계획을 세우는 방식이 충분히 확인되지 않았어요"
        )
        self.assertIn("충분히 확인되지 않았어요", highlight.text)


if __name__ == "__main__":
    unittest.main()
