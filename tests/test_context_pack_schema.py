"""ContextPack Schema 계약 테스트 — 2026-08-23 Trait Ontology v2(2.7단계) §1/§7.

Schema 계층(자기 완결적 구조)만 검증한다 — 24개 Trait Ontology 존재·검수 상태는
`tests/test_context_pack_registry.py`(서비스 계층)에서 다룬다(계층 분리 원칙)."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from src.data.context_packs._example_pack_builder import build_example_context_pack
from src.schemas.context_pack import ContextPack


class ValidPackLoadsTest(unittest.TestCase):
    def test_example_pack_loads_successfully(self) -> None:
        pack = build_example_context_pack()
        self.assertEqual(pack.context_id, "example_context")
        self.assertEqual(len(pack.anchor_presentations), 5)
        self.assertEqual(len(pack.seed_anchor_variants), 5)
        self.assertEqual(len(pack.anchor_backup_questions), 5)
        self.assertEqual(len(pack.option_mapping_rationales), 50)  # (5+5)질문 x 5선택지


class ContextIdConsistencyTest(unittest.TestCase):
    def test_routing_blueprint_context_id_mismatch_fails_fast(self) -> None:
        pack = build_example_context_pack()
        kwargs = pack.model_dump()
        kwargs["routing_blueprint"]["context_id"] = "other_context"
        with self.assertRaises(ValidationError):
            ContextPack(**kwargs)

    def test_anchor_presentation_context_id_mismatch_fails_fast(self) -> None:
        pack = build_example_context_pack()
        kwargs = pack.model_dump()
        kwargs["anchor_presentations"][0]["context_id"] = "other_context"
        with self.assertRaises(ValidationError):
            ContextPack(**kwargs)

    def test_direct_probe_not_in_allowed_context_ids_fails_fast(self) -> None:
        pack = build_example_context_pack()
        kwargs = pack.model_dump()
        kwargs["direct_probe_candidates"] = [
            {
                "trait_id": "causal_analysis", "blueprint_id": "probe_1",
                "option_mappings": [
                    {
                        "role_id": f"role_{i}",
                        "mapping_type": "TRAIT_SIGNAL" if i == 1 else "NO_SIGNAL",
                        "trait_signals": (
                            [{"trait_id": "causal_analysis", "signal_role": "PRIMARY", "weight": 1.0}]
                            if i == 1 else []
                        ),
                        "no_signal_reason": None if i == 1 else "예제",
                    }
                    for i in range(1, 6)
                ],
                "allowed_context_ids": ["some_other_context"],  # Pack context_id 없음
                "question_frame_id": "problem_check", "purpose": "예제",
                "base_question": {
                    "question_id": "probe_1_question", "context": "example_context",
                    "target_traits": [], "frame_id": "problem_check", "question_text": "예제",
                    "options": [
                        {"option_id": f"probe_1_o{i}", "role_id": f"role_{i}",
                         "primary_trait_delta": ({"causal_analysis": 1} if i == 1 else {}), "text": f"옵션 {i}"}
                        for i in range(1, 6)
                    ],
                },
            }
        ]
        with self.assertRaises(ValidationError):
            ContextPack(**kwargs)


class AnchorCountAndDuplicationTest(unittest.TestCase):
    def test_fewer_than_5_anchors_fails_fast(self) -> None:
        pack = build_example_context_pack()
        kwargs = pack.model_dump()
        kwargs["anchor_presentations"] = kwargs["anchor_presentations"][:4]
        with self.assertRaises(ValidationError):
            ContextPack(**kwargs)

    def test_duplicate_anchor_id_fails_fast(self) -> None:
        pack = build_example_context_pack()
        kwargs = pack.model_dump()
        kwargs["anchor_presentations"][1]["anchor_id"] = kwargs["anchor_presentations"][0]["anchor_id"]
        with self.assertRaises(ValidationError):
            ContextPack(**kwargs)

    def test_routing_anchor_set_must_equal_presentation_anchor_set(self) -> None:
        pack = build_example_context_pack()
        kwargs = pack.model_dump()
        kwargs["routing_blueprint"]["option_mappings"][0]["context_anchor"] = "unregistered_anchor"
        with self.assertRaises(ValidationError):
            ContextPack(**kwargs)

    def test_seed_variant_missing_for_one_anchor_fails_fast(self) -> None:
        pack = build_example_context_pack()
        kwargs = pack.model_dump()
        kwargs["seed_anchor_variants"] = kwargs["seed_anchor_variants"][:4]
        with self.assertRaises(ValidationError):
            ContextPack(**kwargs)

    def test_seed_variant_duplicate_anchor_fails_fast(self) -> None:
        pack = build_example_context_pack()
        kwargs = pack.model_dump()
        dup = dict(kwargs["seed_anchor_variants"][1])
        dup["anchor_id"] = kwargs["seed_anchor_variants"][0]["anchor_id"]
        kwargs["seed_anchor_variants"][1] = dup
        with self.assertRaises(ValidationError):
            ContextPack(**kwargs)

    def test_anchor_backup_missing_for_one_anchor_fails_fast(self) -> None:
        pack = build_example_context_pack()
        kwargs = pack.model_dump()
        kwargs["anchor_backup_questions"] = kwargs["anchor_backup_questions"][:4]
        with self.assertRaises(ValidationError):
            ContextPack(**kwargs)


class GlobalIdUniquenessTest(unittest.TestCase):
    def test_duplicate_question_id_across_pack_fails_fast(self) -> None:
        pack = build_example_context_pack()
        kwargs = pack.model_dump()
        kwargs["anchor_backup_questions"][0]["question"]["question_id"] = (
            kwargs["seed_anchor_variants"][0]["question"]["question_id"]
        )
        with self.assertRaises(ValidationError):
            ContextPack(**kwargs)

    def test_duplicate_option_id_across_pack_fails_fast(self) -> None:
        pack = build_example_context_pack()
        kwargs = pack.model_dump()
        kwargs["anchor_backup_questions"][0]["question"]["options"][0]["option_id"] = (
            kwargs["seed_anchor_variants"][0]["question"]["options"][0]["option_id"]
        )
        with self.assertRaises(ValidationError):
            ContextPack(**kwargs)

    def test_duplicate_role_id_within_one_question_fails_fast(self) -> None:
        pack = build_example_context_pack()
        kwargs = pack.model_dump()
        kwargs["seed_anchor_variants"][0]["question"]["options"][1]["role_id"] = (
            kwargs["seed_anchor_variants"][0]["question"]["options"][0]["role_id"]
        )
        with self.assertRaises(ValidationError):
            ContextPack(**kwargs)


class MappingRationaleTest(unittest.TestCase):
    def test_missing_rationale_fails_fast(self) -> None:
        pack = build_example_context_pack()
        kwargs = pack.model_dump()
        kwargs["option_mapping_rationales"] = kwargs["option_mapping_rationales"][:-1]
        with self.assertRaises(ValidationError):
            ContextPack(**kwargs)

    def test_extra_rationale_fails_fast(self) -> None:
        pack = build_example_context_pack()
        kwargs = pack.model_dump()
        extra = dict(kwargs["option_mapping_rationales"][0])
        extra["role_id"] = "role_does_not_exist"
        kwargs["option_mapping_rationales"].append(extra)
        with self.assertRaises(ValidationError):
            ContextPack(**kwargs)

    def test_blank_rationale_text_fails_fast(self) -> None:
        pack = build_example_context_pack()
        kwargs = pack.model_dump()
        kwargs["option_mapping_rationales"][0]["mapping_rationale_draft"] = "   "
        with self.assertRaises(ValidationError):
            ContextPack(**kwargs)

    def test_rationale_trait_id_mismatch_with_option_delta_fails_fast(self) -> None:
        pack = build_example_context_pack()
        kwargs = pack.model_dump()
        kwargs["option_mapping_rationales"][0]["trait_id"] = "pattern_finding"
        kwargs["option_mapping_rationales"][0]["question_id"] = kwargs["seed_anchor_variants"][0]["question"]["question_id"]
        kwargs["option_mapping_rationales"][0]["role_id"] = kwargs["seed_anchor_variants"][0]["question"]["options"][0]["role_id"]
        with self.assertRaises(ValidationError):
            ContextPack(**kwargs)

    def test_no_signal_option_allows_none_trait_id_rationale(self) -> None:
        """§1 "NO_SIGNAL 허용" — Rationale의 trait_id=None은 정상이다."""

        pack = build_example_context_pack()
        no_signal_rationale = next(r for r in pack.option_mapping_rationales if r.trait_id is None)
        self.assertIsNotNone(no_signal_rationale.mapping_rationale_draft.strip())


if __name__ == "__main__":
    unittest.main()
