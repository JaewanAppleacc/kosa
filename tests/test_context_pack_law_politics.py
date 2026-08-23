"""law_politics Context Pack 전용 계약 테스트 — context-pack-technical 브랜치.

가장 검수가 중요한 Context다 — 정치 성향·이념·정당 선호 추론, 도덕적 정답 프레이밍
금지 항목을 텍스트 휴리스틱으로 우선 점검한다(최종 판단은 사람 검수)."""

from __future__ import annotations

import unittest

from src.data.context_packs.law_politics import CONTEXT_PACK
from src.data.contexts.context_definitions import CONTEXT_IDS
from src.services.context_pack_registry import ContextPackRegistry
from src.services.trait_ontology_v2 import load_trait_ontology_v2

_KNOWN_TRAIT_IDS = frozenset(t.trait_id for t in load_trait_ontology_v2())


class StructureTest(unittest.TestCase):
    def test_context_id(self) -> None:
        self.assertEqual(CONTEXT_PACK.context_id, "law_politics")

    def test_exactly_5_anchors(self) -> None:
        self.assertEqual(len(CONTEXT_PACK.anchor_presentations), 5)
        anchor_ids = [a.anchor_id for a in CONTEXT_PACK.anchor_presentations]
        self.assertEqual(len(anchor_ids), len(set(anchor_ids)))

    def test_exactly_5_seed_and_5_backup(self) -> None:
        self.assertEqual(len(CONTEXT_PACK.seed_anchor_variants), 5)
        self.assertEqual(len(CONTEXT_PACK.anchor_backup_questions), 5)

    def test_each_question_has_5_options(self) -> None:
        for seed in CONTEXT_PACK.seed_anchor_variants:
            self.assertEqual(len(seed.question.options), 5)
        for backup in CONTEXT_PACK.anchor_backup_questions:
            self.assertEqual(len(backup.question.options), 5)

    def test_no_direct_probe_candidates_yet(self) -> None:
        self.assertEqual(CONTEXT_PACK.direct_probe_candidates, [])


class IdUniquenessTest(unittest.TestCase):
    def test_question_ids_unique(self) -> None:
        question_ids = [CONTEXT_PACK.routing_blueprint.base_question.question_id]
        question_ids += [s.question.question_id for s in CONTEXT_PACK.seed_anchor_variants]
        question_ids += [b.question.question_id for b in CONTEXT_PACK.anchor_backup_questions]
        self.assertEqual(len(question_ids), len(set(question_ids)))

    def test_option_ids_unique(self) -> None:
        option_ids: list[str] = list(o.option_id for o in CONTEXT_PACK.routing_blueprint.base_question.options)
        for seed in CONTEXT_PACK.seed_anchor_variants:
            option_ids.extend(o.option_id for o in seed.question.options)
        for backup in CONTEXT_PACK.anchor_backup_questions:
            option_ids.extend(o.option_id for o in backup.question.options)
        self.assertEqual(len(option_ids), len(set(option_ids)))


class RationaleAndSignalTest(unittest.TestCase):
    def test_rationale_exists_for_every_seed_and_backup_option(self) -> None:
        expected = 5 * 5 + 5 * 5
        self.assertEqual(len(CONTEXT_PACK.option_mapping_rationales), expected)

    def test_no_signal_options_present(self) -> None:
        no_signal = [r for r in CONTEXT_PACK.option_mapping_rationales if r.trait_id is None]
        self.assertGreater(len(no_signal), 0, "관련 없는 선택지는 NO_SIGNAL로 표시해야 한다")

    def test_all_trait_ids_in_24_trait_ontology(self) -> None:
        used_trait_ids = {r.trait_id for r in CONTEXT_PACK.option_mapping_rationales if r.trait_id is not None}
        self.assertTrue(used_trait_ids.issubset(_KNOWN_TRAIT_IDS), used_trait_ids - _KNOWN_TRAIT_IDS)

    def test_routing_options_carry_no_trait_signal(self) -> None:
        for option in CONTEXT_PACK.routing_blueprint.base_question.options:
            self.assertEqual(option.primary_trait_delta, {})


class NoPoliticalOrMoralFramingTest(unittest.TestCase):
    """작업 지시문의 law_politics 전용 주의사항 — 정치 성향·정당 선호를 추론할
    단서(정당명·이념 축 단어)가 없는지, 도덕적으로 옳은 답을 유도하는 문구가
    없는지 확인한다."""

    def _all_texts(self) -> list[str]:
        texts = [CONTEXT_PACK.routing_blueprint.base_question.question_text]
        texts += [o.text for o in CONTEXT_PACK.routing_blueprint.base_question.options]
        for seed in CONTEXT_PACK.seed_anchor_variants:
            texts.append(seed.question.question_text)
            texts += [o.text for o in seed.question.options]
        for backup in CONTEXT_PACK.anchor_backup_questions:
            texts.append(backup.question.question_text)
            texts += [o.text for o in backup.question.options]
        return texts

    def test_no_political_party_or_ideology_words(self) -> None:
        forbidden = [
            "보수", "진보", "여당", "야당", "국민의힘", "민주당", "정의당",
            "좌파", "우파", "이념",
        ]
        for text in self._all_texts():
            for phrase in forbidden:
                self.assertNotIn(phrase, text, f"{phrase!r}가 {text!r}에 포함됨(정치 성향 추론 위험)")

    def test_no_explicit_moral_correctness_phrasing(self) -> None:
        forbidden = ["도덕적으로 옳은", "정의로운 선택은", "옳은 행동은"]
        for text in self._all_texts():
            for phrase in forbidden:
                self.assertNotIn(phrase, text, f"{phrase!r}가 {text!r}에 포함됨")


class RegistryOntologyValidationTest(unittest.TestCase):
    def test_law_politics_pack_registers_without_ontology_errors(self) -> None:
        registry = ContextPackRegistry(
            known_context_ids=frozenset(CONTEXT_IDS),
            _discovered=({CONTEXT_PACK.context_id: CONTEXT_PACK}, {}),
        )
        self.assertIsNotNone(registry.get_pack("law_politics"))
        self.assertEqual(registry.ontology_errors(), {})

    def test_not_approved_without_review_status(self) -> None:
        registry = ContextPackRegistry(
            known_context_ids=frozenset(CONTEXT_IDS),
            _discovered=({CONTEXT_PACK.context_id: CONTEXT_PACK}, {}),
        )
        self.assertFalse(registry.is_pack_review_approved("law_politics"))


if __name__ == "__main__":
    unittest.main()
