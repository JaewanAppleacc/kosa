"""science Context Pack 전용 계약 테스트 — context-pack-technical 브랜치."""

from __future__ import annotations

import unittest

from src.data.context_packs.science import CONTEXT_PACK
from src.data.contexts.context_definitions import CONTEXT_IDS
from src.services.context_pack_registry import ContextPackRegistry
from src.services.trait_ontology_v2 import load_trait_ontology_v2

_KNOWN_TRAIT_IDS = frozenset(t.trait_id for t in load_trait_ontology_v2())


class StructureTest(unittest.TestCase):
    def test_context_id(self) -> None:
        self.assertEqual(CONTEXT_PACK.context_id, "science")

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


class NoQuizAnswerFormatTest(unittest.TestCase):
    """science 전용 주의사항 — 정답이 있는 과학 지식 퀴즈 형태가 아닌지 확인한다.
    "정답", "옳은 것은", "맞는 것을 고르시오" 같은 퀴즈 문구가 없어야 한다."""

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

    def test_does_not_use_quiz_answer_phrasing(self) -> None:
        forbidden = ["정답", "옳은 것은", "맞는 것을 고르", "틀린 것을 고르"]
        for text in self._all_texts():
            for phrase in forbidden:
                self.assertNotIn(phrase, text, f"{phrase!r}가 {text!r}에 포함됨(퀴즈 형태 금지)")

    def test_does_not_assume_lab_equipment_access(self) -> None:
        forbidden = ["실험실에서", "실험 장비를 이용해"]
        for text in self._all_texts():
            for phrase in forbidden:
                self.assertNotIn(phrase, text, f"{phrase!r}가 {text!r}에 포함됨")


class RegistryOntologyValidationTest(unittest.TestCase):
    def test_science_pack_registers_without_ontology_errors(self) -> None:
        registry = ContextPackRegistry(
            known_context_ids=frozenset(CONTEXT_IDS),
            _discovered=({CONTEXT_PACK.context_id: CONTEXT_PACK}, {}),
        )
        self.assertIsNotNone(registry.get_pack("science"))
        self.assertEqual(registry.ontology_errors(), {})

    def test_not_approved_without_review_status(self) -> None:
        registry = ContextPackRegistry(
            known_context_ids=frozenset(CONTEXT_IDS),
            _discovered=({CONTEXT_PACK.context_id: CONTEXT_PACK}, {}),
        )
        self.assertFalse(registry.is_pack_review_approved("science"))


if __name__ == "__main__":
    unittest.main()
