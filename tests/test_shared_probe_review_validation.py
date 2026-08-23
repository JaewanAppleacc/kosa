"""SharedProbeContextReview Anchor 정합성 검증 — 2026-08-23 Trait Ontology v2
(2.9.1단계) §1-2 감사 반영.

두 층으로 나눠 검증한다:
- Schema 계층(`SharedProbeContextReview`): Pack/Blueprint를 몰라도 판단 가능한 구조
  규칙 — 중복 Anchor ID, 공백 ID, 승인/제외 교집합.
- Service 계층(`update_shared_probe_review`): 실제 Pack 정본과 대조해야 하는 규칙 —
  미등록 Anchor ID, Blueprint가 허용하지 않는 Context.

§1-3(검수 UI의 암묵적 Context 승인 제거)도 이 파일에서 함께 확인한다 — 저장
Service가 status/comment를 None으로 받으면 기존 reviewer_1_status를 절대 바꾸지
않아야 한다는 계약이 §1-2 저장 경로와 같은 함수(`update_shared_probe_review`)에
있기 때문이다."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from src.data.context_packs._example_pack_builder import build_example_context_pack
from src.data.questions.context_pack_shared_probe_blueprints import CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS
from src.review_ui.context_pack_review_service import (
    SharedProbeAnchorListValidationError,
    UnknownAnchorIdError,
    UnknownSharedProbeContextError,
    UnknownSharedProbeError,
    update_shared_probe_review,
)
from src.schemas.context_pack_shared_probe_review import SharedProbeContextReview
from src.services.context_pack_registry import ContextPackRegistry
from src.services.context_pack_shared_probe_review_store import load_shared_probe_review_entries


class SchemaStructuralValidationTest(unittest.TestCase):
    """Pack/Blueprint 없이도 판단 가능한 구조 규칙 — Schema 계층."""

    def test_valid_disjoint_lists_ok(self) -> None:
        review = SharedProbeContextReview(
            blueprint_id="bp1", context_id="business",
            approved_anchor_ids=["anchor_a", "anchor_b"], excluded_anchor_ids=["anchor_c"],
        )
        self.assertEqual(review.approved_anchor_ids, ["anchor_a", "anchor_b"])

    def test_duplicate_in_approved_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            SharedProbeContextReview(
                blueprint_id="bp1", context_id="business",
                approved_anchor_ids=["anchor_a", "anchor_a"],
            )

    def test_duplicate_in_excluded_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            SharedProbeContextReview(
                blueprint_id="bp1", context_id="business",
                excluded_anchor_ids=["anchor_a", "anchor_a"],
            )

    def test_overlap_between_approved_and_excluded_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            SharedProbeContextReview(
                blueprint_id="bp1", context_id="business",
                approved_anchor_ids=["anchor_a"], excluded_anchor_ids=["anchor_a"],
            )

    def test_blank_string_in_approved_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            SharedProbeContextReview(blueprint_id="bp1", context_id="business", approved_anchor_ids=[""])

    def test_whitespace_only_in_excluded_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            SharedProbeContextReview(blueprint_id="bp1", context_id="business", excluded_anchor_ids=["   "])


class _ServiceTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.review_dir = Path(self.tmpdir.name)
        self.shared_path = self.review_dir / "shared.json"
        self.pack = build_example_context_pack("business")
        self.anchor_ids = [a.anchor_id for a in self.pack.anchor_presentations]
        self.registry = ContextPackRegistry(
            known_context_ids=frozenset({"business"}),
            known_trait_ids=frozenset({"causal_analysis", "pattern_finding"}),
            review_status_dir=self.review_dir,
            shared_probe_review_status_path=self.shared_path,
            _discovered=({"business": self.pack}, {}),
        )
        self.blueprint = CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS[0]
        self.assertIn("business", self.blueprint.allowed_context_ids)

    def _entries_by_key(self) -> dict[str, SharedProbeContextReview]:
        return {e.key: e for e in load_shared_probe_review_entries(self.shared_path)}


class UnregisteredAnchorRejectionTest(_ServiceTestBase):
    def test_unknown_anchor_id_in_approved_list_rejected(self) -> None:
        with self.assertRaises(UnknownAnchorIdError):
            update_shared_probe_review(
                self.registry, list(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS), self.blueprint.blueprint_id, "business",
                status=None, comment=None, approved_anchor_ids=["not_a_real_anchor"], excluded_anchor_ids=None,
                resolution_note=None,
            )

    def test_unknown_anchor_id_in_excluded_list_rejected(self) -> None:
        with self.assertRaises(UnknownAnchorIdError):
            update_shared_probe_review(
                self.registry, list(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS), self.blueprint.blueprint_id, "business",
                status=None, comment=None, approved_anchor_ids=None, excluded_anchor_ids=["not_a_real_anchor"],
                resolution_note=None,
            )

    def test_rejected_save_leaves_store_untouched(self) -> None:
        """§1-2 "잘못된 데이터는... 명시적으로 거부" — 거부된 저장은 기존 Store
        값을 조금도 바꾸지 않는다(부분 반영 없음)."""

        # 먼저 정상 저장을 하나 만들어 둔다.
        update_shared_probe_review(
            self.registry, list(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS), self.blueprint.blueprint_id, "business",
            status="APPROVE", comment="정상 승인", approved_anchor_ids=[self.anchor_ids[0]], excluded_anchor_ids=[],
            resolution_note=None,
        )
        before = self._entries_by_key()

        with self.assertRaises(UnknownAnchorIdError):
            update_shared_probe_review(
                self.registry, list(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS), self.blueprint.blueprint_id, "business",
                status="APPROVE", comment="이 값은 저장되면 안 된다",
                approved_anchor_ids=["not_a_real_anchor"], excluded_anchor_ids=None, resolution_note=None,
            )
        after = self._entries_by_key()
        self.assertEqual(before, after)


class UnsupportedContextRejectionTest(_ServiceTestBase):
    def test_context_not_in_allowed_context_ids_rejected(self) -> None:
        with self.assertRaises(UnknownSharedProbeContextError):
            update_shared_probe_review(
                self.registry, list(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS), self.blueprint.blueprint_id,
                "not_an_allowed_context",
                status="APPROVE", comment="", approved_anchor_ids=None, excluded_anchor_ids=None,
                resolution_note=None,
            )

    def test_unknown_blueprint_id_rejected(self) -> None:
        with self.assertRaises(UnknownSharedProbeError):
            update_shared_probe_review(
                self.registry, list(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS), "not_a_real_blueprint", "business",
                status="APPROVE", comment="", approved_anchor_ids=None, excluded_anchor_ids=None,
                resolution_note=None,
            )


class InvalidAnchorListRejectionAtServiceLayerTest(_ServiceTestBase):
    """Schema Validator가 Service 저장 경로에서도 실제로 실행되는지 확인한다
    (`model_copy`가 아니라 `model_validate`를 쓰는지가 핵심 — 우회하면 이 테스트가
    실패한다)."""

    def test_duplicate_anchor_id_rejected_through_service(self) -> None:
        with self.assertRaises(SharedProbeAnchorListValidationError):
            update_shared_probe_review(
                self.registry, list(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS), self.blueprint.blueprint_id, "business",
                status=None, comment=None,
                approved_anchor_ids=[self.anchor_ids[0], self.anchor_ids[0]], excluded_anchor_ids=None,
                resolution_note=None,
            )

    def test_overlap_rejected_through_service(self) -> None:
        with self.assertRaises(SharedProbeAnchorListValidationError):
            update_shared_probe_review(
                self.registry, list(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS), self.blueprint.blueprint_id, "business",
                status=None, comment=None,
                approved_anchor_ids=[self.anchor_ids[0]], excluded_anchor_ids=[self.anchor_ids[0]],
                resolution_note=None,
            )


class ImplicitApprovalRemovedTest(_ServiceTestBase):
    """§1-3 — Anchor 저장(status=None)은 reviewer_1_status를 절대 바꾸지 않는다."""

    def test_saving_anchors_with_status_none_keeps_tbd(self) -> None:
        update_shared_probe_review(
            self.registry, list(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS), self.blueprint.blueprint_id, "business",
            status=None, comment=None, approved_anchor_ids=[self.anchor_ids[0]], excluded_anchor_ids=[],
            resolution_note=None,
        )
        entry = self._entries_by_key()[f"{self.blueprint.blueprint_id}::business"]
        self.assertEqual(entry.reviewer_1_status, "TBD")
        self.assertEqual(entry.approved_anchor_ids, [self.anchor_ids[0]])

    def test_saving_anchors_with_status_none_does_not_overwrite_existing_approve(self) -> None:
        update_shared_probe_review(
            self.registry, list(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS), self.blueprint.blueprint_id, "business",
            status="APPROVE", comment="사람이 명시적으로 승인함", approved_anchor_ids=[self.anchor_ids[0]],
            excluded_anchor_ids=[], resolution_note=None,
        )
        update_shared_probe_review(
            self.registry, list(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS), self.blueprint.blueprint_id, "business",
            status=None, comment=None, approved_anchor_ids=[self.anchor_ids[0], self.anchor_ids[1]],
            excluded_anchor_ids=[], resolution_note=None,
        )
        entry = self._entries_by_key()[f"{self.blueprint.blueprint_id}::business"]
        self.assertEqual(entry.reviewer_1_status, "APPROVE")
        self.assertEqual(entry.reviewer_1_comment, "사람이 명시적으로 승인함")
        self.assertEqual(set(entry.approved_anchor_ids), {self.anchor_ids[0], self.anchor_ids[1]})

    def test_explicit_approve_status_still_works(self) -> None:
        """§1-3은 "명시적 APPROVE 동작"까지 막지 않는다 — 사용자가 select에서
        실제로 APPROVE를 골라 보내면 정상 반영된다."""

        update_shared_probe_review(
            self.registry, list(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS), self.blueprint.blueprint_id, "business",
            status="APPROVE", comment="명시적 승인", approved_anchor_ids=None, excluded_anchor_ids=None,
            resolution_note=None,
        )
        entry = self._entries_by_key()[f"{self.blueprint.blueprint_id}::business"]
        self.assertEqual(entry.reviewer_1_status, "APPROVE")

    def test_existing_approve_revise_status_not_overwritten_by_anchor_only_save(self) -> None:
        update_shared_probe_review(
            self.registry, list(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS), self.blueprint.blueprint_id, "business",
            status="REVISE", comment="수정 필요", approved_anchor_ids=None, excluded_anchor_ids=None,
            resolution_note=None,
        )
        update_shared_probe_review(
            self.registry, list(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS), self.blueprint.blueprint_id, "business",
            status=None, comment=None, approved_anchor_ids=[self.anchor_ids[0]], excluded_anchor_ids=[],
            resolution_note=None,
        )
        entry = self._entries_by_key()[f"{self.blueprint.blueprint_id}::business"]
        self.assertEqual(entry.reviewer_1_status, "REVISE")
        self.assertEqual(entry.reviewer_1_comment, "수정 필요")


class NormalSaveAndReloadTest(_ServiceTestBase):
    def test_normal_save_and_reload_round_trip(self) -> None:
        update_shared_probe_review(
            self.registry, list(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS), self.blueprint.blueprint_id, "business",
            status="APPROVE", comment="정상 승인", approved_anchor_ids=[self.anchor_ids[0], self.anchor_ids[1]],
            excluded_anchor_ids=[self.anchor_ids[2]], resolution_note="검토 완료",
        )
        reloaded = self._entries_by_key()[f"{self.blueprint.blueprint_id}::business"]
        self.assertEqual(reloaded.reviewer_1_status, "APPROVE")
        self.assertEqual(set(reloaded.approved_anchor_ids), {self.anchor_ids[0], self.anchor_ids[1]})
        self.assertEqual(reloaded.excluded_anchor_ids, [self.anchor_ids[2]])
        self.assertEqual(reloaded.resolution_note, "검토 완료")
        self.assertTrue(
            self.registry.is_shared_probe_approved_for_anchor(self.blueprint.blueprint_id, "business", self.anchor_ids[0])
        )


if __name__ == "__main__":
    unittest.main()
