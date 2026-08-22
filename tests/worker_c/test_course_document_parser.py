"""course_document_parser — 입력 제한, 추출, Alias 정규화, 확인 대상 구분."""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from src.agents.course.course_document_parser import (
    SubjectAliasIndex,
    normalize_subject_name,
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
