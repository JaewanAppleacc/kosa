"""business Context Pack 전용 계약 테스트 — context-pack-technical 브랜치.

`src/schemas/context_pack.py`의 Cross-field 검증은 import 시점에 이미
실행되므로(Fail-Fast), 여기서는 그 결과가 기대한 모양인지(개수, NO_SIGNAL 존재,
Trait Ontology 준수, 금지 전제 문구 미포함)만 다시 확인한다."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.data.context_packs.business import CONTEXT_PACK
from src.data.contexts.context_definitions import CONTEXT_IDS
from src.services.context_pack_registry import ContextPackRegistry
from src.services.trait_ontology_v2 import load_trait_ontology_v2

_KNOWN_TRAIT_IDS = frozenset(t.trait_id for t in load_trait_ontology_v2())


class StructureTest(unittest.TestCase):
    def test_context_id(self) -> None:
        self.assertEqual(CONTEXT_PACK.context_id, "business")

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


class ForbiddenAssumptionTextTest(unittest.TestCase):
    """작업 지시문의 business 전용 주의사항 — 돈 액수를 묻지 않는지, 실제 창업
    경험을 전제하는 표현이 없는지 질문·선택지 원문을 훑어 확인한다(휴리스틱
    점검이며 최종 판단은 사람 검수가 한다)."""

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

    def test_does_not_ask_about_money_amount(self) -> None:
        forbidden = ["돈을 얼마나", "돈을 많이", "수익을 얼마나", "얼마를 벌"]
        for text in self._all_texts():
            for phrase in forbidden:
                self.assertNotIn(phrase, text, f"{phrase!r}가 {text!r}에 포함됨")

    def test_does_not_assume_real_investment_experience(self) -> None:
        forbidden = ["투자 유치", "실제 창업", "매출을 올렸"]
        for text in self._all_texts():
            for phrase in forbidden:
                self.assertNotIn(phrase, text, f"{phrase!r}가 {text!r}에 포함됨")


class RoutingReviewFixTest(unittest.TestCase):
    """2026-08-24 사람 검수(reviewer_1) REVISE 반영 — resource_budgeting/plan_decision
    Routing 선택지 문구만 바꾸고 나머지(Anchor 집합·role_id·검수 Key·Mapping)는 전혀
    건드리지 않았는지 확인한다. 실제 검수 JSON(business_review_status.json)은
    읽기만 한다 — 이 테스트가 그 파일을 쓰거나 상태를 바꾸지 않는다."""

    _EXPECTED_ANCHOR_IDS = {"idea_shaping", "feedback_reading", "resource_budgeting", "plan_decision", "team_role_share"}
    _EXPECTED_ROLE_IDS = {"br_idea", "br_feedback", "br_resource", "br_decision", "br_team"}
    _OLD_AMBIGUOUS_TEXTS = ("제한된 시간이나 예산을 어떻게 쓸지 정하는 순간", "여러 방향 중 하나를 결정하는 순간")

    def test_routing_has_exactly_5_options(self) -> None:
        self.assertEqual(len(CONTEXT_PACK.routing_blueprint.base_question.options), 5)

    def test_anchor_id_set_unchanged(self) -> None:
        anchor_ids = {a.anchor_id for a in CONTEXT_PACK.anchor_presentations}
        self.assertEqual(anchor_ids, self._EXPECTED_ANCHOR_IDS)
        routing_anchor_ids = {m.context_anchor for m in CONTEXT_PACK.routing_blueprint.option_mappings}
        self.assertEqual(routing_anchor_ids, self._EXPECTED_ANCHOR_IDS)

    def test_routing_role_ids_unchanged(self) -> None:
        role_ids = {o.role_id for o in CONTEXT_PACK.routing_blueprint.base_question.options}
        self.assertEqual(role_ids, self._EXPECTED_ROLE_IDS)
        mapping_role_ids = {m.role_id for m in CONTEXT_PACK.routing_blueprint.option_mappings}
        self.assertEqual(mapping_role_ids, self._EXPECTED_ROLE_IDS)

    def test_routing_blueprint_and_question_id_unchanged(self) -> None:
        self.assertEqual(CONTEXT_PACK.routing_blueprint.blueprint_id, "business_context_router_v1")
        self.assertEqual(CONTEXT_PACK.routing_blueprint.base_question.question_id, "business_routing_question")

    def test_required_review_key_unchanged(self) -> None:
        registry = ContextPackRegistry(
            known_context_ids=frozenset(CONTEXT_IDS), _discovered=({CONTEXT_PACK.context_id: CONTEXT_PACK}, {}),
        )
        keys = registry.required_review_keys(CONTEXT_PACK)
        self.assertIn("business::routing::business_context_router_v1", keys)

    def test_old_ambiguous_phrasing_no_longer_present(self) -> None:
        option_texts = [o.text for o in CONTEXT_PACK.routing_blueprint.base_question.options]
        for old_text in self._OLD_AMBIGUOUS_TEXTS:
            self.assertNotIn(old_text, option_texts)

    def test_new_phrasing_distinguishes_resource_budgeting_from_plan_decision(self) -> None:
        by_role = {o.role_id: o.text for o in CONTEXT_PACK.routing_blueprint.base_question.options}
        resource_text = by_role["br_resource"]
        decision_text = by_role["br_decision"]
        self.assertIn("시간", resource_text)
        self.assertIn("예산", resource_text)
        self.assertIn("우선", resource_text, "resource_budgeting 문구에 '무엇을 우선할지' 의미가 없다")
        self.assertNotEqual(decision_text.strip(), "여러 방향 중 하나를 결정하는 순간")
        self.assertIn("진행", decision_text, "plan_decision 문구에 '실제로 진행' 의미가 없다")
        self.assertNotEqual(resource_text, decision_text)

    def test_routing_options_still_carry_no_trait_signal_after_fix(self) -> None:
        for option in CONTEXT_PACK.routing_blueprint.base_question.options:
            self.assertEqual(option.primary_trait_delta, {})

    def test_real_review_json_comment_and_revise_status_preserved(self) -> None:
        """실제 검수 파일을 읽기만 한다 — 여기서 쓰지 않는다. 사람이 남긴 REVISE
        코멘트가 그대로 있고, 이 Pack 코드 수정이 검수 상태를 임의로 바꾸지
        않았는지(여전히 REVISE인지) 확인한다."""

        review_path = (
            Path(__file__).resolve().parents[1] / "data" / "reviews" / "context_packs" / "business_review_status.json"
        )
        entries = json.loads(review_path.read_text(encoding="utf-8"))
        routing_entry = next(e for e in entries if e["blueprint_id"] == "business::routing::business_context_router_v1")
        self.assertEqual(routing_entry["reviewer_1_status"], "REVISE")
        self.assertIn("제한된 시간안에", routing_entry["reviewer_1_comment"])
        self.assertIn("너무 모호", routing_entry["reviewer_1_comment"])


class RegistryOntologyValidationTest(unittest.TestCase):
    """Pack 밖 정본(24개 Trait Ontology, CONTEXT_DEFINITIONS) 비교는 Registry
    계층 책임이다 — 실제 서비스와 동일한 방식으로 검증되는지 확인한다. 다른
    Context 제작 에이전트가 동시에 작업 중일 수 있으므로 실제 디렉터리를 훑지
    않고 이 Pack 하나만 주입해 검증한다."""

    def test_business_pack_registers_without_ontology_errors(self) -> None:
        registry = ContextPackRegistry(
            known_context_ids=frozenset(CONTEXT_IDS),
            _discovered=({CONTEXT_PACK.context_id: CONTEXT_PACK}, {}),
        )
        self.assertIsNotNone(registry.get_pack("business"))
        self.assertEqual(registry.ontology_errors(), {})

    def test_not_approved_without_review_status(self) -> None:
        """검수 상태 JSON이 전부 TBD인 동안은 활성화되지 않아야 한다(Fail-Closed).
        실제 저장소의 `data/reviews/context_packs/business_review_status.json`을
        그대로 읽는다."""

        registry = ContextPackRegistry(
            known_context_ids=frozenset(CONTEXT_IDS),
            _discovered=({CONTEXT_PACK.context_id: CONTEXT_PACK}, {}),
        )
        self.assertFalse(registry.is_pack_review_approved("business"))


if __name__ == "__main__":
    unittest.main()
