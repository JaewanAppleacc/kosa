"""sports Context Pack 전용 계약 테스트 — context-pack-lifestyle 작업 배정.

`src/schemas/context_pack.py`의 Cross-field 검증은 import 시점에 이미 실행되므로
(Fail-Fast), 여기서는 그 결과가 기대한 모양인지(개수, NO_SIGNAL 존재, Trait Ontology
준수, 금지 전제 문구 미포함)만 다시 확인한다. `tests/test_context_pack_business.py`와
동일한 구조를 그대로 따른다(다른 Context 제작 에이전트가 만든 관례)."""

from __future__ import annotations

import unittest

from src.data.context_packs.sports import CONTEXT_PACK
from src.data.contexts.context_definitions import CONTEXT_IDS
from src.services.context_pack_registry import ContextPackRegistry
from src.services.trait_ontology_v2 import load_trait_ontology_v2

_KNOWN_TRAIT_IDS = frozenset(t.trait_id for t in load_trait_ontology_v2())


class StructureTest(unittest.TestCase):
    def test_context_id(self) -> None:
        self.assertEqual(CONTEXT_PACK.context_id, "sports")

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

    def test_anchor_ids_match_instruction(self) -> None:
        """작업 지시문 sports 주의사항: 관람·기록 향상·전략·개인 운동·팀 상황 분리."""

        anchor_ids = {a.anchor_id for a in CONTEXT_PACK.anchor_presentations}
        self.assertEqual(
            anchor_ids,
            {"spectating_analysis", "record_improvement", "strategy_tactics", "individual_training", "team_situation"},
        )


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
        expected = 5 * 5 + 5 * 5  # 5 anchors x (seed 5 options + backup 5 options)
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


class NoAutoCompetitionCollaborationLinkTest(unittest.TestCase):
    """작업 지시문: 스포츠 관심을 경쟁성·협동성으로 자동 연결하지 않는다. 관람·전략·
    개인 운동 Anchor에는 collaboration_preference/opinion_mediation이 등장하지
    않아야 한다 — 그 두 Trait는 실제로 팀 상황에서 행동을 물었을 때만 등장한다."""

    def test_collaboration_traits_only_from_team_situation_anchor(self) -> None:
        team_question_ids = {
            s.question.question_id for s in CONTEXT_PACK.seed_anchor_variants if s.anchor_id == "team_situation"
        }
        team_question_ids |= {
            b.question.question_id for b in CONTEXT_PACK.anchor_backup_questions if b.anchor_id == "team_situation"
        }
        for rationale in CONTEXT_PACK.option_mapping_rationales:
            if rationale.trait_id in ("collaboration_preference", "opinion_mediation"):
                self.assertIn(rationale.question_id, team_question_ids)


class ForbiddenAssumptionTextTest(unittest.TestCase):
    """작업 지시문 sports 전용 주의사항 — 선수·팀 경험 전제, 체력/운동 능력 평가
    표현이 없는지 원문을 훑어 확인한다(휴리스틱 점검, 최종 판단은 사람 검수가 한다)."""

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

    def test_does_not_assume_athlete_or_team_membership(self) -> None:
        forbidden = ["선수 출신", "선수로 뛰", "팀 소속으로", "국가대표"]
        for text in self._all_texts():
            for phrase in forbidden:
                self.assertNotIn(phrase, text, f"{phrase!r}가 {text!r}에 포함됨")

    def test_does_not_evaluate_physical_ability(self) -> None:
        forbidden = ["체력이 얼마나", "운동 실력이", "몸이 얼마나", "신체 능력이"]
        for text in self._all_texts():
            for phrase in forbidden:
                self.assertNotIn(phrase, text, f"{phrase!r}가 {text!r}에 포함됨")


class RegistryOntologyValidationTest(unittest.TestCase):
    """Pack 밖 정본(24개 Trait Ontology, CONTEXT_DEFINITIONS) 비교는 Registry
    계층 책임이다. 다른 Context 제작 에이전트가 동시에 작업 중일 수 있으므로 실제
    디렉터리를 훑지 않고 이 Pack 하나만 주입해 검증한다."""

    def test_sports_pack_registers_without_ontology_errors(self) -> None:
        registry = ContextPackRegistry(
            known_context_ids=frozenset(CONTEXT_IDS),
            _discovered=({CONTEXT_PACK.context_id: CONTEXT_PACK}, {}),
        )
        self.assertIsNotNone(registry.get_pack("sports"))
        self.assertEqual(registry.ontology_errors(), {})

    def test_not_approved_without_review_status(self) -> None:
        """검수 상태 JSON이 전부 TBD인 동안은 활성화되지 않아야 한다(Fail-Closed).
        실제 저장소의 `data/reviews/context_packs/sports_review_status.json`을
        그대로 읽는다."""

        registry = ContextPackRegistry(
            known_context_ids=frozenset(CONTEXT_IDS),
            _discovered=({CONTEXT_PACK.context_id: CONTEXT_PACK}, {}),
        )
        self.assertFalse(registry.is_pack_review_approved("sports"))


if __name__ == "__main__":
    unittest.main()
