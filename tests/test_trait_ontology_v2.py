"""Trait Ontology v2(1단계) 테스트 — 지시서 §15 "Ontology"."""

from __future__ import annotations

import unittest

from src.data.trait_ontology.new_traits_v2_draft import NEW_TRAITS_V2_DRAFT, NEW_TRAIT_IDS_V2
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAIT_IDS
from src.schemas.trait import GroundingType
from src.services.related_concept_registry import load_related_concepts_v2
from src.services.trait_ontology_v2 import load_trait_ontology_v2


class CoreTraitCountTest(unittest.TestCase):
    def test_exactly_24_core_traits(self) -> None:
        self.assertEqual(len(load_trait_ontology_v2()), 24)

    def test_no_duplicate_trait_ids(self) -> None:
        ids = [t.trait_id for t in load_trait_ontology_v2()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_existing_12_trait_ids_are_preserved(self) -> None:
        v2_ids = {t.trait_id for t in load_trait_ontology_v2()}
        self.assertTrue(VERTICAL_SLICE_TRAIT_IDS.issubset(v2_ids))

    def test_new_traits_are_exactly_12(self) -> None:
        self.assertEqual(len(NEW_TRAIT_IDS_V2), 12)
        self.assertEqual(NEW_TRAIT_IDS_V2 & VERTICAL_SLICE_TRAIT_IDS, set())

    def test_existing_trait_fields_unchanged_in_v2(self) -> None:
        """기존 12개의 ID·정의·행동 지표를 v2 빌드가 바꾸지 않았는지 확인한다."""

        from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAITS

        legacy_by_id = {t.trait_id: t for t in VERTICAL_SLICE_TRAITS}
        v2_by_id = {t.trait_id: t for t in load_trait_ontology_v2()}
        for trait_id, legacy in legacy_by_id.items():
            v2 = v2_by_id[trait_id]
            self.assertEqual(v2.definition, legacy.definition)
            self.assertEqual(v2.positive_indicators, legacy.positive_indicators)
            self.assertEqual(v2.conflicting_indicators, legacy.conflicting_indicators)
            self.assertEqual(v2.label, legacy.label)


class TraitDefinitionFieldsTest(unittest.TestCase):
    def test_definitions_and_indicators_are_not_blank(self) -> None:
        for trait in load_trait_ontology_v2():
            with self.subTest(trait_id=trait.trait_id):
                self.assertTrue(trait.definition.strip())
                self.assertTrue(trait.positive_indicators)
                self.assertTrue(trait.conflicting_indicators)

    def test_grounding_type_is_an_allowed_value(self) -> None:
        allowed = set(GroundingType.__args__)
        for trait in load_trait_ontology_v2():
            with self.subTest(trait_id=trait.trait_id):
                self.assertIn(trait.grounding_type, allowed)

    def test_new_traits_without_direct_official_evidence_stay_team_defined(self) -> None:
        team_defined_expected = {
            "creative_ideation", "novelty_seeking", "uncertainty_tolerance",
            "opinion_expression", "personal_goal_priority",
        }
        by_id = {t.trait_id: t for t in NEW_TRAITS_V2_DRAFT}
        for trait_id in team_defined_expected:
            with self.subTest(trait_id=trait_id):
                self.assertEqual(by_id[trait_id].grounding_type, "TEAM_DEFINED")

    def test_no_new_trait_overclaims_onet_strong(self) -> None:
        """§2 원칙 5: O*NET과 부분적으로만 연결되는 Trait를 ONET_STRONG으로 과장하지 않는다."""

        for trait in NEW_TRAITS_V2_DRAFT:
            with self.subTest(trait_id=trait.trait_id):
                self.assertNotEqual(trait.grounding_type, "ONET_STRONG")

    def test_new_traits_have_neighboring_trait_ids_and_distinction_notes(self) -> None:
        for trait in NEW_TRAITS_V2_DRAFT:
            with self.subTest(trait_id=trait.trait_id):
                self.assertTrue(trait.neighboring_trait_ids, f"{trait.trait_id}: neighboring_trait_ids 비어 있음")
                self.assertTrue(trait.distinction_notes.strip(), f"{trait.trait_id}: distinction_notes 비어 있음")

    def test_personal_goal_priority_definition_is_neutral_not_selfish_label(self) -> None:
        """§2 원칙 3: '이기적임'을 중립적으로 표현 — 부정적 성격 단정 문구가 없어야 한다."""

        trait = next(t for t in NEW_TRAITS_V2_DRAFT if t.trait_id == "personal_goal_priority")
        forbidden = ["이기적", "배려하지 않", "나쁜", "부정적인 성격"]
        for phrase in forbidden:
            self.assertNotIn(phrase, trait.definition)
            for indicator in trait.positive_indicators + trait.conflicting_indicators:
                self.assertNotIn(phrase, indicator)


class RelatedConceptTest(unittest.TestCase):
    def test_concepts_load_without_error(self) -> None:
        concepts = load_related_concepts_v2()
        self.assertTrue(concepts)

    def test_no_duplicate_concept_ids(self) -> None:
        ids = [c.concept_id for c in load_related_concepts_v2()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_all_linked_trait_ids_exist_in_ontology(self) -> None:
        known_trait_ids = {t.trait_id for t in load_trait_ontology_v2()}
        for concept in load_related_concepts_v2():
            for link in concept.trait_links:
                with self.subTest(concept_id=concept.concept_id, trait_id=link.trait_id):
                    self.assertIn(link.trait_id, known_trait_ids)

    def test_concepts_can_link_multiple_traits(self) -> None:
        multi = [c for c in load_related_concepts_v2() if len(c.trait_links) >= 2]
        self.assertTrue(multi, "적어도 하나는 여러 Trait와 연결된 Concept이어야 한다")

    def test_all_concepts_are_draft(self) -> None:
        for concept in load_related_concepts_v2():
            with self.subTest(concept_id=concept.concept_id):
                self.assertEqual(concept.review_status, "draft")


if __name__ == "__main__":
    unittest.main()
