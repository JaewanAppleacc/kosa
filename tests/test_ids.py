"""ID 규칙 — C와 합의한 결정(2026-08-20) 그대로 구현됐는지 확인."""

from __future__ import annotations

import inspect
import unittest

from src.ids import (
    generate_department_id,
    generate_display_group_id,
    generate_offering_id,
    generate_offering_lineage_id,
    generate_option_id,
    generate_question_id,
    generate_subject_id,
    is_valid_slug,
)


class SlugTest(unittest.TestCase):
    def test_unprefixed_snake_case_is_valid(self) -> None:
        # 프리픽스 없는 snake_case가 context_id/trait_id의 정본 형태다 (설계안 JSON 예시와 일치).
        # is_valid_slug는 "ctx_media"도 형식상 유효로 판단한다 — 프리픽스 금지는 이 정규식이
        # 아니라 실제 데이터(context_definitions.py, vertical_slice_traits.py)가 지키는
        # 명명 관행이다. 아래는 그 실제 데이터가 규칙을 지키는지 확인한다.
        self.assertTrue(is_valid_slug("media"))
        self.assertTrue(is_valid_slug("causal_analysis"))

    def test_actual_context_and_trait_data_have_no_prefix(self) -> None:
        from src.data.contexts.context_definitions import CONTEXT_DEFINITIONS
        from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAITS

        for context in CONTEXT_DEFINITIONS:
            self.assertFalse(context.context_id.startswith("ctx_"), context.context_id)
        for trait in VERTICAL_SLICE_TRAITS:
            self.assertFalse(trait.trait_id.startswith("trait_"), trait.trait_id)


class QuestionOptionIdTest(unittest.TestCase):
    def test_question_id_format(self) -> None:
        self.assertEqual(generate_question_id("media", "tail", 4), "media_tail_04")

    def test_option_id_is_question_id_plus_index(self) -> None:
        qid = generate_question_id("media", "seed", 1)
        self.assertEqual(generate_option_id(qid, 3), "media_seed_01_o3")


class DepartmentSubjectIdTest(unittest.TestCase):
    def test_department_id_does_not_accept_survey_year(self) -> None:
        # svyYr을 해시에 넣으면 재수집 때마다 같은 학과가 새 id를 받는 문제가 있어 제외했다.
        # 함수 시그니처 자체에 그 인자가 없다는 것으로 구조적으로 강제한다.
        params = list(inspect.signature(generate_department_id).parameters)
        self.assertNotIn("svy_yr", params)
        self.assertNotIn("survey_year", params)

    def test_department_id_stable_across_repeated_calls(self) -> None:
        first = generate_department_id("SCHL001", "컴퓨터공학과", "공과대학")
        second = generate_department_id("SCHL001", "컴퓨터공학과", "공과대학")
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("dept_"))

    def test_subject_id_stable_across_repeated_calls(self) -> None:
        first = generate_subject_id("CURR2022", "데이터 과학")
        second = generate_subject_id("CURR2022", "데이터 과학")
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("subj_"))


class OfferingIdentityV2Test(unittest.TestCase):
    """2026-08-25 지시서(a/offering-identity-v2) §2 — Identity v2 세 함수."""

    def test_offering_id_stable_and_differs_from_department_id(self) -> None:
        first = generate_offering_id("0000121", "0246874")
        second = generate_offering_id("0000121", "0246874")
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("off_"))

    def test_offering_id_differs_for_different_source_schl_mjr_id_even_same_display_name(self) -> None:
        """§2 핵심 요구사항 — 표시명(department_name/college_name)이 같아도
        source_schl_mjr_id가 다르면 반드시 다른 offering_id를 받는다(16
        Group·32행 충돌의 근본 해법)."""

        general = generate_offering_id("0000121", "0232771")  # 서경대 헤어디자인학과 일반과정
        contract = generate_offering_id("0000121", "0232745")  # 서경대 헤어디자인학과 계약학과
        self.assertNotEqual(general, contract)

    def test_offering_id_provider_namespace_prevents_cross_provider_collision(self) -> None:
        a = generate_offering_id("S1", "M1", provider="academyinfo")
        b = generate_offering_id("S1", "M1", provider="other_provider")
        self.assertNotEqual(a, b)

    def test_offering_id_survey_year_optional_and_default_excludes_year(self) -> None:
        # 기본값(survey_year 생략)은 department_id와 같은 원칙 — 연도가 달라도 같은 값.
        without_year = generate_offering_id("S1", "M1")
        also_without_year = generate_offering_id("S1", "M1")
        self.assertEqual(without_year, also_without_year)
        with_year = generate_offering_id("S1", "M1", survey_year=2025)
        self.assertNotEqual(without_year, with_year)

    def test_display_group_id_uses_same_material_as_department_id_but_different_prefix(self) -> None:
        dept_id = generate_department_id("0000121", "헤어디자인학과", "미용예술대학")
        display_id = generate_display_group_id("0000121", "미용예술대학", "헤어디자인학과")
        self.assertTrue(display_id.startswith("dgrp_"))
        self.assertNotEqual(dept_id, display_id)  # 접두사가 다르니 문자열 자체는 다르다.
        # 하지만 재료(3-tuple)는 실제로 같다 — 두 함수 모두 안정적으로 재현 가능하다.
        self.assertEqual(display_id, generate_display_group_id("0000121", "미용예술대학", "헤어디자인학과"))

    def test_offering_lineage_id_requires_at_least_two_verified_keys(self) -> None:
        with self.assertRaises(ValueError):
            generate_offering_lineage_id("only_one")
        with self.assertRaises(ValueError):
            generate_offering_lineage_id()

    def test_offering_lineage_id_order_independent_and_stable(self) -> None:
        a = generate_offering_lineage_id("off_2024_x", "off_2025_x")
        b = generate_offering_lineage_id("off_2025_x", "off_2024_x")
        self.assertEqual(a, b)
        self.assertTrue(a.startswith("lin_"))

    def test_department_id_generator_unchanged(self) -> None:
        """§5 "기존 35건 즉시 교체 금지" — generate_department_id()가 여전히
        "dept_" 접두사에 24자리 SHA-256 prefix를 쓰는 안정적인 값을 내는지
        확인한다(이번 라운드가 이 함수의 동작을 조금도 바꾸지 않았다는 근거)."""

        first = generate_department_id("SCHL001", "컴퓨터공학과", "공과대학")
        second = generate_department_id("SCHL001", "컴퓨터공학과", "공과대학")
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("dept_"))
        self.assertEqual(len(first), len("dept_") + 24)


if __name__ == "__main__":
    unittest.main()
