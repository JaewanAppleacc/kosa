"""ID 규칙 — C와 합의한 결정(2026-08-20) 그대로 구현됐는지 확인."""

from __future__ import annotations

import inspect
import unittest

from src.ids import (
    generate_department_id,
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


if __name__ == "__main__":
    unittest.main()
