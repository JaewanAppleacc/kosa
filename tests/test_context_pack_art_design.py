"""art_design Context Pack 전용 계약 테스트 — context-pack-lifestyle 작업 배정.

`src/schemas/context_pack.py`의 Cross-field 검증은 import 시점에 이미 실행되므로
(Fail-Fast), 여기서는 그 결과가 기대한 모양인지만 다시 확인한다."""

from __future__ import annotations

import unittest

from src.data.context_packs.art_design import CONTEXT_PACK
from src.data.contexts.context_definitions import CONTEXT_IDS
from src.services.context_pack_registry import ContextPackRegistry
from src.services.trait_ontology_v2 import load_trait_ontology_v2

_KNOWN_TRAIT_IDS = frozenset(t.trait_id for t in load_trait_ontology_v2())


class StructureTest(unittest.TestCase):
    def test_context_id(self) -> None:
        self.assertEqual(CONTEXT_PACK.context_id, "art_design")

    def test_exactly_5_anchors(self) -> None:
        self.assertEqual(len(CONTEXT_PACK.anchor_presentations), 5)
        anchor_ids = [a.anchor_id for a in CONTEXT_PACK.anchor_presentations]
        self.assertEqual(len(anchor_ids), len(set(anchor_ids)))

    def test_exactly_5_seed_and_5_backup(self) -> None:
        self.assertEqual(len(CONTEXT_PACK.seed_anchor_variants), 5)
        self.assertEqual(len(CONTEXT_PACK.anchor_backup_questions), 5)

    def test_each_question_has_5_options(self) -> None:
        self.assertEqual(len(CONTEXT_PACK.routing_blueprint.base_question.options), 5)
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


class AppreciationNotMappedToVisualExpressionTest(unittest.TestCase):
    """작업 지시문 핵심 규칙: 작품 감상(visual_appreciation Anchor)을
    visual_expression으로 연결하지 않는다 — visual_expression은 직접 그리기·만들기
    (direct_creation)와 표현 선택 상황에서만 등장해야 한다."""

    def test_visual_appreciation_anchor_never_maps_visual_expression(self) -> None:
        appreciation_question_ids = {
            s.question.question_id for s in CONTEXT_PACK.seed_anchor_variants if s.anchor_id == "visual_appreciation"
        }
        appreciation_question_ids |= {
            b.question.question_id
            for b in CONTEXT_PACK.anchor_backup_questions
            if b.anchor_id == "visual_appreciation"
        }
        for rationale in CONTEXT_PACK.option_mapping_rationales:
            if rationale.question_id in appreciation_question_ids:
                self.assertNotEqual(rationale.trait_id, "visual_expression")

    def test_visual_expression_only_appears_with_direct_action_anchors(self) -> None:
        allowed_anchor_ids = {"direct_creation"}
        allowed_question_ids: set[str] = set()
        for s in CONTEXT_PACK.seed_anchor_variants:
            if s.anchor_id in allowed_anchor_ids:
                allowed_question_ids.add(s.question.question_id)
        for b in CONTEXT_PACK.anchor_backup_questions:
            if b.anchor_id in allowed_anchor_ids:
                allowed_question_ids.add(b.question.question_id)
        for rationale in CONTEXT_PACK.option_mapping_rationales:
            if rationale.trait_id == "visual_expression":
                self.assertIn(rationale.question_id, allowed_question_ids)


class ForbiddenAssumptionTextTest(unittest.TestCase):
    """작업 지시문 art_design 전용 주의사항 — 그림 실력 평가 표현이 없는지 원문을
    훑어 확인한다(휴리스틱 점검, 최종 판단은 사람 검수가 한다)."""

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

    def test_does_not_evaluate_drawing_skill(self) -> None:
        forbidden = ["그림을 잘", "그림 실력이", "미술 실력이", "잘 그리는"]
        for text in self._all_texts():
            for phrase in forbidden:
                self.assertNotIn(phrase, text, f"{phrase!r}가 {text!r}에 포함됨")


class RegistryOntologyValidationTest(unittest.TestCase):
    def test_art_design_pack_registers_without_ontology_errors(self) -> None:
        registry = ContextPackRegistry(
            known_context_ids=frozenset(CONTEXT_IDS),
            _discovered=({CONTEXT_PACK.context_id: CONTEXT_PACK}, {}),
        )
        self.assertIsNotNone(registry.get_pack("art_design"))
        self.assertEqual(registry.ontology_errors(), {})

    def test_not_approved_without_review_status(self) -> None:
        registry = ContextPackRegistry(
            known_context_ids=frozenset(CONTEXT_IDS),
            _discovered=({CONTEXT_PACK.context_id: CONTEXT_PACK}, {}),
        )
        self.assertFalse(registry.is_pack_review_approved("art_design"))


if __name__ == "__main__":
    unittest.main()
