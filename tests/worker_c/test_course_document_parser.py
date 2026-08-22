"""course_document_parser — 입력 제한, 추출, Alias 정규화, 확인 대상 구분."""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from src.agents.course.course_document_parser import (
    SubjectAliasIndex,
    _looks_like_subject,
    normalize_subject_name,
    normalize_table_header_token,
    parse_course_document,
)

ALIAS_ROWS = [
    {"alias": "정보", "canonical_subject_name": "정보", "subject_id": "subj_info", "curriculum_code": "2022-33"},
    {"alias": "미적분Ⅱ", "canonical_subject_name": "미적분Ⅱ", "subject_id": "subj_calc2", "curriculum_code": "2022-33"},
    {"alias": "미적분2", "canonical_subject_name": "미적분Ⅱ", "subject_id": "subj_calc2", "curriculum_code": "2022-33"},
    {"alias": "인공지능 기초", "canonical_subject_name": "인공지능 기초", "subject_id": "subj_ai", "curriculum_code": "2022-33"},
    {"alias": "화법과 언어", "canonical_subject_name": "화법과 언어", "subject_id": "subj_speech", "curriculum_code": "2022-33"},
]

SHARED_STRINGS = """<?xml version="1.0" encoding="UTF-8"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="7" uniqueCount="7">
<si><t>교과</t></si><si><t>과목명</t></si><si><t>단위</t></si>
<si><t>정보</t></si><si><t>미적분 II</t></si><si><t>인공지능기초</t></si><si><t>진로와 직업</t></si>
</sst>"""

SHEET = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>2</v></c></row>
<row r="2"><c r="A2" t="s"><v>3</v></c><c r="B2" t="s"><v>4</v></c><c r="C2"><v>4</v></c></row>
<row r="3"><c r="A3" t="s"><v>5</v></c><c r="B3" t="s"><v>6</v></c><c r="C3"><v>2</v></c></row>
</sheetData></worksheet>"""


def write_xlsx(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("xl/sharedStrings.xml", SHARED_STRINGS)
        archive.writestr("xl/worksheets/sheet1.xml", SHEET)


class NormalizeSubjectNameTest(unittest.TestCase):
    def test_roman_and_arabic_numerals_collapse(self) -> None:
        self.assertEqual(normalize_subject_name("미적분Ⅱ"), normalize_subject_name("미적분2"))
        self.assertEqual(normalize_subject_name("미적분 II"), normalize_subject_name("미적분2"))

    def test_spaces_and_separators_are_ignored(self) -> None:
        self.assertEqual(normalize_subject_name("인공지능 기초"), normalize_subject_name("인공지능기초"))
        self.assertEqual(normalize_subject_name("기술·가정"), normalize_subject_name("기술가정"))


class TableHeaderTokenExclusionTest(unittest.TestCase):
    """2026-08-28 18차 리뷰(A가 진행, 지시서 §1): 편제표 열 제목("교과(군)" 등)이
    원문 그대로 `_NON_SUBJECT_TOKENS`와 비교돼 실제 과목처럼 unmatched 후보로 노출되던
    문제를 고친다. 먼저 실패를 재현한 뒤 수정을 확인한다."""

    def test_bug_reproduction_before_normalization_would_have_failed(self) -> None:
        """§1: 지시서가 요구한 재현 — 괄호 없는 표기는 이미 걸러졌지만, 괄호가 붙은
        실제 표기("교과(군)")는 정규화 없이는 걸러지지 않았다는 사실을 그대로 보인다."""

        self.assertFalse(_looks_like_subject("교과군"))
        # 정규화 함수를 거치지 않은 순수 문자열 비교는 이 값을 걸러내지 못했다 — 이제는
        # `_looks_like_subject` 내부에서 `normalize_table_header_token`을 거치므로 걸러진다.
        self.assertNotIn("교과(군)", {"교과", "교과군"})  # 재현: 원문 그대로는 다른 문자열이다.
        self.assertFalse(_looks_like_subject("교과(군)"))  # 수정 후: 이제는 걸러진다.

    def test_normalize_table_header_token_examples(self) -> None:
        cases = {
            "교과(군)": "교과군",
            "교과 (군)": "교과군",
            "과목(명)": "과목명",
            "과목 (명)": "과목명",
            "이수 단위": "이수단위",
            "이수(단위)": "이수단위",
            "선택 구분": "선택구분",
            "학년(학기)": "학년학기",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_table_header_token(raw), expected)

    def test_table_header_variants_are_excluded(self) -> None:
        for text in ("교과(군)", "교과 (군)", "과목(명)", "이수 단위", "학년(학기)", "선택 구분"):
            with self.subTest(text=text):
                self.assertFalse(_looks_like_subject(text))

    def test_normal_subjects_are_still_protected(self) -> None:
        for text in (
            "확률과 통계", "화법과 언어", "소프트웨어와 생활", "매체 의사소통",
            "정체불명 과목ABC", "데이터 과학", "인공지능 기초",
        ):
            with self.subTest(text=text):
                self.assertTrue(_looks_like_subject(text))

    def test_substring_containing_forbidden_word_is_not_blocked(self) -> None:
        """§3: "과목"이 들어 있다는 이유만으로 부분 문자열 차단을 하면 안 된다."""

        self.assertTrue(_looks_like_subject("정체불명 과목ABC"))

    def test_table_header_normalization_does_not_change_alias_matching(self) -> None:
        """§2: `normalize_subject_name`(Alias Matching용)의 의미는 바뀌지 않는다."""

        self.assertEqual(normalize_subject_name("확률과 통계"), "확률과통계")
        self.assertEqual(normalize_subject_name("미적분Ⅱ"), normalize_subject_name("미적분2"))

    def test_parenthesized_real_subject_name_is_not_blanket_excluded(self) -> None:
        """괄호가 있다는 이유만으로 전부 제외하지 않는다 — 표 제목 토큰 집합과 정확히
        일치할 때만 제외한다."""

        self.assertTrue(_looks_like_subject("음악(전공실기)"))


class AliasIndexTest(unittest.TestCase):
    def setUp(self) -> None:
        self.index = SubjectAliasIndex(ALIAS_ROWS)

    def test_exact_match_ignores_notation(self) -> None:
        self.assertEqual(self.index.exact("미적분 II")[0], "subj_calc2")

    def test_close_match_is_a_suggestion_not_a_match(self) -> None:
        self.assertIsNone(self.index.exact("화법과언어론"))
        close = self.index.closest("화법과언어론")
        self.assertIsNotNone(close)
        self.assertEqual(close[0], "subj_speech")

    def test_unrelated_name_has_no_candidate(self) -> None:
        self.assertIsNone(self.index.closest("체육"))


class ParseXlsxTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.index = SubjectAliasIndex(ALIAS_ROWS)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_extracts_and_classifies_candidates(self) -> None:
        path = self.dir / "curriculum.xlsx"
        write_xlsx(path)
        result = parse_course_document(path, self.index)

        self.assertTrue(result.succeeded)
        self.assertEqual(result.errors, [])

        by_raw = {c.raw_text: c for c in result.candidates}
        self.assertIn("정보", by_raw)
        self.assertEqual(by_raw["정보"].confidence, "high")
        self.assertFalse(by_raw["정보"].requires_user_confirmation)

        self.assertEqual(by_raw["미적분 II"].matched_subject_id, "subj_calc2")
        self.assertEqual(by_raw["미적분 II"].confidence, "high")

        self.assertEqual(by_raw["진로와 직업"].confidence, "unmatched")
        self.assertIsNone(by_raw["진로와 직업"].matched_subject_id)
        self.assertTrue(by_raw["진로와 직업"].requires_user_confirmation)

    def test_header_cells_are_not_candidates(self) -> None:
        path = self.dir / "curriculum.xlsx"
        write_xlsx(path)
        result = parse_course_document(path, self.index)
        raw_texts = {c.raw_text for c in result.candidates}
        self.assertNotIn("교과", raw_texts)
        self.assertNotIn("과목명", raw_texts)
        self.assertNotIn("단위", raw_texts)

    def test_parenthesized_header_cell_is_not_a_candidate(self) -> None:
        """2026-08-28 18차 리뷰: "교과(군)"처럼 괄호가 붙은 실제 열 제목도 xlsx 추출
        경로 전체에서 후보로 올라오지 않아야 한다(단위 테스트뿐 아니라 실제 파싱
        경로에서도 재현·검증)."""

        path = self.dir / "curriculum_with_paren_header.xlsx"
        shared_strings = """<?xml version="1.0" encoding="UTF-8"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="4" uniqueCount="4">
<si><t>교과(군)</t></si><si><t>과목(명)</t></si>
<si><t>정보</t></si><si><t>정체불명 과목ABC</t></si>
</sst>"""
        sheet = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>
<row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2" t="s"><v>3</v></c></row>
</sheetData></worksheet>"""
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("xl/sharedStrings.xml", shared_strings)
            archive.writestr("xl/worksheets/sheet1.xml", sheet)

        result = parse_course_document(path, self.index)
        raw_texts = {c.raw_text for c in result.candidates}
        self.assertNotIn("교과(군)", raw_texts)
        self.assertNotIn("과목(명)", raw_texts)
        self.assertIn("정보", raw_texts)
        self.assertIn("정체불명 과목ABC", raw_texts)
        unmatched = {c.raw_text for c in result.candidates if c.confidence == "unmatched"}
        self.assertEqual(unmatched, {"정체불명 과목ABC"})

    def test_requires_confirmation_list_matches_flags(self) -> None:
        path = self.dir / "curriculum.xlsx"
        write_xlsx(path)
        result = parse_course_document(path, self.index)
        self.assertEqual(
            {c.raw_text for c in result.requires_confirmation()},
            {c.raw_text for c in result.candidates if c.requires_user_confirmation},
        )

    def test_broken_xlsx_reports_extract_error(self) -> None:
        path = self.dir / "broken.xlsx"
        path.write_bytes(b"not a zip file")
        result = parse_course_document(path, self.index)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.errors[0].stage, "extract")


class ParseInputGuardTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.index = SubjectAliasIndex(ALIAS_ROWS)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_unsupported_extension_is_rejected(self) -> None:
        path = self.dir / "notes.docx"
        path.write_text("과목", encoding="utf-8")
        result = parse_course_document(path, self.index)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.errors[0].stage, "input")

    def test_unsupported_content_type_is_rejected(self) -> None:
        path = self.dir / "curriculum.xlsx"
        write_xlsx(path)
        result = parse_course_document(path, self.index, content_type="text/csv")
        self.assertFalse(result.succeeded)
        self.assertEqual(result.errors[0].stage, "input")

    def test_missing_file_is_reported(self) -> None:
        result = parse_course_document(self.dir / "없음.pdf", self.index)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.errors[0].stage, "input")

    def test_legacy_xls_is_explicitly_unsupported_not_silently_empty(self) -> None:
        """.xls는 빈 결과가 아니라 사유가 붙은 오류로 돌려준다."""

        path = self.dir / "old.xls"
        path.write_bytes(b"\xd0\xcf\x11\xe0")  # OLE2 시그니처
        result = parse_course_document(path, self.index)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.errors[0].stage, "extract")
        self.assertIn("xls", result.errors[0].message)
        self.assertEqual(result.candidates, [])


class ParsePdfTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.index = SubjectAliasIndex(ALIAS_ROWS)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_sidecar_text_is_used_when_present(self) -> None:
        pdf = self.dir / "edu.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        pdf.with_suffix(".txt").write_text(
            "교과\t과목명\t단위\n수학\t미적분2\t4\n정보\t인공지능기초\t2\n", encoding="utf-8"
        )
        result = parse_course_document(pdf, self.index, content_type="application/pdf")

        self.assertTrue(result.succeeded)
        matched = {c.matched_subject_id for c in result.matched()}
        self.assertIn("subj_calc2", matched)
        self.assertIn("subj_ai", matched)

    def test_unreadable_pdf_reports_extract_error(self) -> None:
        pdf = self.dir / "scan.pdf"
        pdf.write_bytes(b"%PDF-1.4\n% no extractable text\n")
        result = parse_course_document(pdf, self.index, content_type="application/pdf")
        self.assertFalse(result.succeeded)
        self.assertEqual(result.errors[0].stage, "extract")


if __name__ == "__main__":
    unittest.main()
