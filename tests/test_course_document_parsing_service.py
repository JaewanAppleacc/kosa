"""CourseDocumentParsingService 단위 테스트 — 2026-08-26 16차 리뷰 §1/§2/§3/§5/§6.

Fake SubjectRepository + 진짜 CoursePlanningService(§8 원칙과 동일: Fake Repository를
주입할 수 있어야 한다)로 구성한다. xlsx 파일 bytes는 표준 라이브러리만으로 직접 만든다
(`data/fixtures/course_offerings/demo_school_offerings.xlsx`를 만든 것과 같은 방식) —
openpyxl 등 새 의존성을 추가하지 않는다.
"""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from xml.sax.saxutils import escape

from src.agents.course.course_document_parser import SubjectAliasIndex
from src.data.majors.vertical_slice_major_profiles import VERTICAL_SLICE_MAJOR_PROFILES
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAITS
from src.engines.policy_guard import PolicyViolation
from src.memory.course_planning_store import InMemoryCoursePlanningStore
from src.schemas.assessment_state import AssessmentState
from src.schemas.course import ParsedSubjectCandidate, SubjectProfile
from src.schemas.evidence import TraitEvidenceSummary
from src.services.course_document_parsing_service import (
    MAX_UPLOAD_SIZE_BYTES,
    CourseConfirmValidationError,
    CourseDocumentParsingService,
    CourseParsingFailedError,
    CourseUploadNotFoundError,
    EmptyFileError,
    FileTooLargeError,
    UnsupportedFileTypeError,
    _validate_suffix_and_content_type,
    read_upload_with_limit,
)
from src.services.course_planning_service import CoursePlanningService

_TRAIT_DEFS = {t.trait_id: t for t in VERTICAL_SLICE_TRAITS}

_XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _build_xlsx_bytes(rows: list[str]) -> bytes:
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""
    workbook = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>"""
    workbook_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
</Relationships>"""
    shared_items = "".join(f'<si><t xml:space="preserve">{escape(s)}</t></si>' for s in rows)
    shared_strings = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'count="{len(rows)}" uniqueCount="{len(rows)}">{shared_items}</sst>'
    )
    rows_xml = "".join(f'<row r="{i + 1}"><c r="A{i + 1}" t="s"><v>{i}</v></c></row>' for i in range(len(rows)))
    sheet1 = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{rows_xml}</sheetData></worksheet>'
    )

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", content_types)
            z.writestr("_rels/.rels", rels)
            z.writestr("xl/workbook.xml", workbook)
            z.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
            z.writestr("xl/worksheets/sheet1.xml", sheet1)
            z.writestr("xl/sharedStrings.xml", shared_strings)
        return tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)


class FakeSubjectRepository:
    def __init__(self, subjects: list[SubjectProfile]) -> None:
        self._subjects = subjects

    def all(self) -> list[SubjectProfile]:
        return list(self._subjects)

    def related_to_major(self, major_id: str) -> list[SubjectProfile]:
        return [s for s in self._subjects if major_id in s.related_major_ids]

    def get(self, subject_id: str) -> SubjectProfile | None:
        return next((s for s in self._subjects if s.subject_id == subject_id), None)


def _strong(trait_id: str) -> TraitEvidenceSummary:
    return TraitEvidenceSummary(
        trait_id=trait_id, support_count=3, opportunity_count=3, context_count=2, distinct_frame_count=2
    )


def _state_with_ie_evidence() -> AssessmentState:
    strong_set = {"causal_analysis", "pattern_finding", "information_comparison", "planning"}
    summaries = {
        t: (_strong(t) if t in strong_set else TraitEvidenceSummary(trait_id=t, support_count=0, opportunity_count=0))
        for t in _TRAIT_DEFS
    }
    return AssessmentState(session_id="sess_upload_test", user_id="user_test", trait_summaries=summaries)


class CourseDocumentParsingServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.subject_a = SubjectProfile(
            subject_id="subj_offered_a", label="확률과 통계",
            trait_vector={"causal_analysis": 1.0}, related_major_ids=["industrial_engineering"],
            source_id="https://example.moe.go.kr/",
        )
        self.subject_b = SubjectProfile(
            subject_id="subj_offered_b", label="데이터 과학",
            trait_vector={"information_comparison": 1.0}, related_major_ids=["industrial_engineering"],
            source_id="https://example.moe.go.kr/",
        )
        self.repository = FakeSubjectRepository([self.subject_a, self.subject_b])
        self.course_planning_store = InMemoryCoursePlanningStore()
        self.course_planning_service = CoursePlanningService(
            self.repository, major_profiles=VERTICAL_SLICE_MAJOR_PROFILES,
            trait_definitions=_TRAIT_DEFS, course_planning_store=self.course_planning_store,
        )
        self.alias_index = SubjectAliasIndex(
            [
                {"alias": "확률과 통계", "canonical_subject_name": "확률과 통계", "subject_id": "subj_offered_a", "curriculum_code": "test"},
                {"alias": "데이터 과학", "canonical_subject_name": "데이터 과학", "subject_id": "subj_offered_b", "curriculum_code": "test"},
            ]
        )
        self.parsing_service = CourseDocumentParsingService(
            self.alias_index, self.repository, self.course_planning_service, self.course_planning_store
        )
        self.state = _state_with_ie_evidence()

    # --- §3 파일 보안 ---

    def test_empty_file_is_rejected(self) -> None:
        with self.assertRaises(EmptyFileError):
            self.parsing_service.parse_upload(
                self.state, "industrial_engineering", b"", "empty.xlsx", _XLSX_CONTENT_TYPE
            )

    def test_oversized_file_is_rejected(self) -> None:
        oversized = b"0" * (MAX_UPLOAD_SIZE_BYTES + 1)
        with self.assertRaises(FileTooLargeError):
            self.parsing_service.parse_upload(
                self.state, "industrial_engineering", oversized, "big.xlsx", _XLSX_CONTENT_TYPE
            )

    def test_xls_is_explicitly_rejected_with_helpful_message(self) -> None:
        with self.assertRaises(UnsupportedFileTypeError) as ctx:
            self.parsing_service.parse_upload(
                self.state, "industrial_engineering", b"fake xls bytes", "old.xls",
                "application/vnd.ms-excel",
            )
        self.assertIn("XLSX로 다시 저장", str(ctx.exception))

    def test_unsupported_extension_is_rejected(self) -> None:
        with self.assertRaises(UnsupportedFileTypeError):
            self.parsing_service.parse_upload(
                self.state, "industrial_engineering", b"hello", "notes.txt", "text/plain"
            )

    def test_content_type_and_extension_mismatch_is_rejected(self) -> None:
        with self.assertRaises(UnsupportedFileTypeError):
            self.parsing_service.parse_upload(
                self.state, "industrial_engineering", b"%PDF-1.4", "curriculum.pdf",
                _XLSX_CONTENT_TYPE,  # .pdf 확장자인데 xlsx Content-Type
            )

    def test_path_traversal_filename_only_contributes_its_suffix(self) -> None:
        """사용자가 보낸 파일명에 경로 조작 문자열이 있어도, 실제로 쓰이는 값은
        확장자(suffix)뿐이다 — 로컬 경로 조립에 파일명 전체가 쓰이지 않는다."""

        suffix = _validate_suffix_and_content_type("../../etc/passwd.pdf", "application/pdf")
        self.assertEqual(suffix, ".pdf")

    def test_no_temp_file_left_after_successful_parse(self) -> None:
        before = set(Path(tempfile.gettempdir()).glob("tmp*"))
        content = _build_xlsx_bytes(["확률과 통계"])
        self.parsing_service.parse_upload(
            self.state, "industrial_engineering", content, "offerings.xlsx", _XLSX_CONTENT_TYPE
        )
        after = set(Path(tempfile.gettempdir()).glob("tmp*"))
        self.assertEqual(before, after, "임시 파일이 처리 후에도 남아있다")

    def test_no_temp_file_left_after_parse_failure(self) -> None:
        before = set(Path(tempfile.gettempdir()).glob("tmp*"))
        with self.assertRaises(CourseParsingFailedError):
            self.parsing_service.parse_upload(
                self.state, "industrial_engineering", b"%PDF-1.4 not real pdf content",
                "scanned.pdf", "application/pdf",
            )
        after = set(Path(tempfile.gettempdir()).glob("tmp*"))
        self.assertEqual(before, after, "파싱 실패 후에도 임시 파일이 남아있다")

    # --- §3 문서 파싱 실패 vs 개설과목 0개 구분 ---

    def test_unreadable_pdf_raises_parse_failed_not_empty_list(self) -> None:
        with self.assertRaises(CourseParsingFailedError):
            self.parsing_service.parse_upload(
                self.state, "industrial_engineering", b"%PDF-1.4 no extractable text here",
                "scanned.pdf", "application/pdf",
            )

    # --- §2 selected_major_id 검증 재사용 ---

    def test_no_evidence_session_is_rejected_before_parsing(self) -> None:
        from src.services.course_planning_service import CourseEvidenceNotReadyError

        empty_state = AssessmentState(session_id="sess_empty", user_id="user_test")
        content = _build_xlsx_bytes(["확률과 통계"])
        with self.assertRaises(CourseEvidenceNotReadyError):
            self.parsing_service.parse_upload(
                empty_state, "industrial_engineering", content, "offerings.xlsx", _XLSX_CONTENT_TYPE
            )

    # --- §1/§5 성공 파싱 + 중복 정규화 ---

    def test_successful_parse_stores_planning_state(self) -> None:
        content = _build_xlsx_bytes(["확률과 통계", "데이터 과학"])
        candidates, warnings = self.parsing_service.parse_upload(
            self.state, "industrial_engineering", content, "offerings.xlsx", _XLSX_CONTENT_TYPE
        )
        self.assertEqual(warnings, [])
        matched_ids = {c.matched_subject_id for c in candidates}
        self.assertEqual(matched_ids, {"subj_offered_a", "subj_offered_b"})

        planning_state = self.course_planning_store.load(self.state.session_id)
        self.assertIsNotNone(planning_state)
        self.assertEqual(planning_state.selected_major_id, "industrial_engineering")
        self.assertEqual(planning_state.upload_status, "PARSED")  # 전부 high, 모호함 없음

    def test_duplicate_subject_id_candidates_are_deduped_to_one(self) -> None:
        content = _build_xlsx_bytes(["확률과 통계", "확률과 통계", "확률과 통계"])
        candidates, _warnings = self.parsing_service.parse_upload(
            self.state, "industrial_engineering", content, "offerings.xlsx", _XLSX_CONTENT_TYPE
        )
        matched = [c for c in candidates if c.matched_subject_id == "subj_offered_a"]
        self.assertEqual(len(matched), 1, "같은 subject_id가 여러 번 남았다")

    def test_reupload_replaces_previous_unconfirmed_state(self) -> None:
        """§4: 새 파일을 다시 업로드하면 이전 미확정 결과를 명시적으로 교체한다."""

        first_content = _build_xlsx_bytes(["확률과 통계"])
        self.parsing_service.parse_upload(
            self.state, "industrial_engineering", first_content, "first.xlsx", _XLSX_CONTENT_TYPE
        )
        second_content = _build_xlsx_bytes(["데이터 과학"])
        self.parsing_service.parse_upload(
            self.state, "industrial_engineering", second_content, "second.xlsx", _XLSX_CONTENT_TYPE
        )
        planning_state = self.course_planning_store.load(self.state.session_id)
        matched_ids = {c.matched_subject_id for c in planning_state.parsed_candidates}
        self.assertEqual(matched_ids, {"subj_offered_b"})  # 첫 업로드(확률과 통계)는 사라짐

    # --- §6 confirm 검증 ---

    def test_confirm_without_prior_upload_is_rejected(self) -> None:
        never_uploaded_state = AssessmentState(session_id="sess_never_uploaded", user_id="user_test")
        with self.assertRaises(CourseUploadNotFoundError):
            self.parsing_service.confirm(never_uploaded_state, ["subj_offered_a"])

    def test_confirm_rejects_subject_id_not_in_master_data(self) -> None:
        self.parsing_service.parse_upload(
            self.state, "industrial_engineering", _build_xlsx_bytes(["확률과 통계"]),
            "offerings.xlsx", _XLSX_CONTENT_TYPE,
        )
        with self.assertRaises(CourseConfirmValidationError):
            self.parsing_service.confirm(self.state, ["subj_does_not_exist"])
        planning_state = self.course_planning_store.load(self.state.session_id)
        self.assertEqual(planning_state.upload_status, "PARSED", "실패했는데 상태가 바뀌었다")
        self.assertEqual(planning_state.confirmed_offered_subject_ids, [])

    def test_confirm_rejects_subject_id_not_from_this_upload(self) -> None:
        """다른 세션·업로드에서 나온 후보를 가져와 확정할 수 없다 — subject_b는 정본에는
        있지만 이번 업로드 후보에는 없다."""

        self.parsing_service.parse_upload(
            self.state, "industrial_engineering", _build_xlsx_bytes(["확률과 통계"]),
            "offerings.xlsx", _XLSX_CONTENT_TYPE,
        )
        with self.assertRaises(CourseConfirmValidationError):
            self.parsing_service.confirm(self.state, ["subj_offered_b"])
        planning_state = self.course_planning_store.load(self.state.session_id)
        self.assertEqual(planning_state.upload_status, "PARSED", "실패했는데 상태가 바뀌었다")

    def test_confirm_normalizes_duplicate_ids_in_request(self) -> None:
        self.parsing_service.parse_upload(
            self.state, "industrial_engineering", _build_xlsx_bytes(["확률과 통계"]),
            "offerings.xlsx", _XLSX_CONTENT_TYPE,
        )
        course_profile = self.parsing_service.confirm(
            self.state, ["subj_offered_a", "subj_offered_a"]
        )
        self.assertEqual(course_profile.source, "POST_OFFERING")
        planning_state = self.course_planning_store.load(self.state.session_id)
        self.assertEqual(planning_state.confirmed_offered_subject_ids, ["subj_offered_a"])
        self.assertEqual(planning_state.upload_status, "CONFIRMED")

    def test_confirm_allows_empty_confirmed_list(self) -> None:
        self.parsing_service.parse_upload(
            self.state, "industrial_engineering", _build_xlsx_bytes(["확률과 통계"]),
            "offerings.xlsx", _XLSX_CONTENT_TYPE,
        )
        course_profile = self.parsing_service.confirm(self.state, [])
        self.assertEqual(course_profile.recommendations, [])
        planning_state = self.course_planning_store.load(self.state.session_id)
        self.assertEqual(planning_state.confirmed_offered_subject_ids, [])
        self.assertEqual(planning_state.upload_status, "CONFIRMED")

    # --- 2026-08-27 17차 리뷰 §1: unresolved_candidates 보존 ---

    def test_confirm_preserves_unmatched_candidates_in_course_profile(self) -> None:
        content = _build_xlsx_bytes(["확률과 통계", "정체불명 과목ABC"])
        self.parsing_service.parse_upload(
            self.state, "industrial_engineering", content, "offerings.xlsx", _XLSX_CONTENT_TYPE,
        )
        course_profile = self.parsing_service.confirm(self.state, ["subj_offered_a"])
        self.assertEqual(len(course_profile.unresolved_candidates), 1)
        self.assertIsNone(course_profile.unresolved_candidates[0].matched_subject_id)
        self.assertEqual(course_profile.unresolved_candidates[0].confidence, "unmatched")
        # 확정한 high 후보는 unresolved에 남지 않는다.
        self.assertNotIn(
            "subj_offered_a",
            [c.matched_subject_id for c in course_profile.unresolved_candidates],
        )

    def test_get_course_profile_after_confirm_keeps_unmatched_candidates(self) -> None:
        content = _build_xlsx_bytes(["확률과 통계", "정체불명 과목ABC"])
        self.parsing_service.parse_upload(
            self.state, "industrial_engineering", content, "offerings.xlsx", _XLSX_CONTENT_TYPE,
        )
        confirmed = self.parsing_service.confirm(self.state, ["subj_offered_a"])
        refetched = self.course_planning_service.get_course_profile(
            self.state, "industrial_engineering"
        )
        self.assertEqual(refetched.model_dump(), confirmed.model_dump())
        self.assertEqual(len(refetched.unresolved_candidates), 1)

    # --- 2026-08-27 17차 리뷰 §2: Confirm 원자성 ---

    def test_confirm_failure_in_recommendation_computation_keeps_previous_state(self) -> None:
        self.parsing_service.parse_upload(
            self.state, "industrial_engineering", _build_xlsx_bytes(["확률과 통계"]),
            "offerings.xlsx", _XLSX_CONTENT_TYPE,
        )
        before = self.course_planning_store.load(self.state.session_id)
        with patch.object(
            self.course_planning_service,
            "build_post_offering_course_profile",
            side_effect=RuntimeError("추천 계산 중 예상하지 못한 오류"),
        ):
            with self.assertRaises(RuntimeError):
                self.parsing_service.confirm(self.state, ["subj_offered_a"])
        after = self.course_planning_store.load(self.state.session_id)
        self.assertEqual(after.upload_status, before.upload_status)
        self.assertEqual(after.confirmed_offered_subject_ids, before.confirmed_offered_subject_ids)

    def test_confirm_failure_in_policy_guard_keeps_previous_state(self) -> None:
        self.parsing_service.parse_upload(
            self.state, "industrial_engineering", _build_xlsx_bytes(["확률과 통계"]),
            "offerings.xlsx", _XLSX_CONTENT_TYPE,
        )
        before = self.course_planning_store.load(self.state.session_id)
        with patch.object(
            self.course_planning_service,
            "build_post_offering_course_profile",
            side_effect=PolicyViolation("의도적으로 재현한 Policy Guard 위반"),
        ):
            with self.assertRaises(PolicyViolation):
                self.parsing_service.confirm(self.state, ["subj_offered_a"])
        after = self.course_planning_store.load(self.state.session_id)
        self.assertEqual(after.upload_status, before.upload_status)
        self.assertNotEqual(after.upload_status, "CONFIRMED")

    def test_confirm_success_does_not_affect_other_sessions(self) -> None:
        other_state = AssessmentState(
            session_id="sess_other", user_id="user_other", trait_summaries=self.state.trait_summaries
        )
        self.parsing_service.parse_upload(
            self.state, "industrial_engineering", _build_xlsx_bytes(["확률과 통계"]),
            "offerings.xlsx", _XLSX_CONTENT_TYPE,
        )
        self.parsing_service.parse_upload(
            other_state, "industrial_engineering", _build_xlsx_bytes(["데이터 과학"]),
            "offerings.xlsx", _XLSX_CONTENT_TYPE,
        )
        self.parsing_service.confirm(self.state, ["subj_offered_a"])

        other_planning_state = self.course_planning_store.load(other_state.session_id)
        self.assertEqual(other_planning_state.upload_status, "PARSED")
        self.assertEqual(other_planning_state.confirmed_offered_subject_ids, [])


class ReadUploadWithLimitTest(unittest.IsolatedAsyncioTestCase):
    class _FakeAsyncFile:
        def __init__(self, data: bytes) -> None:
            self._data = data
            self._pos = 0
            self.read_calls = 0

        async def read(self, size: int = -1) -> bytes:
            self.read_calls += 1
            if size < 0:
                chunk = self._data[self._pos:]
                self._pos = len(self._data)
                return chunk
            chunk = self._data[self._pos : self._pos + size]
            self._pos += len(chunk)
            return chunk

    async def test_exactly_at_limit_is_allowed(self) -> None:
        data = b"a" * 10
        result = await read_upload_with_limit(self._FakeAsyncFile(data), max_bytes=10, chunk_size=4)
        self.assertEqual(result, data)

    async def test_one_byte_over_limit_is_rejected_during_read(self) -> None:
        data = b"a" * 11
        with self.assertRaises(FileTooLargeError):
            await read_upload_with_limit(self._FakeAsyncFile(data), max_bytes=10, chunk_size=4)

    async def test_multi_chunk_file_is_reassembled_correctly(self) -> None:
        data = b"0123456789" * 5  # 50 bytes, chunk_size 7이라 여러 조각으로 나뉜다.
        result = await read_upload_with_limit(self._FakeAsyncFile(data), max_bytes=1000, chunk_size=7)
        self.assertEqual(result, data)

    async def test_empty_file_returns_empty_bytes(self) -> None:
        result = await read_upload_with_limit(self._FakeAsyncFile(b""), max_bytes=10, chunk_size=4)
        self.assertEqual(result, b"")

    async def test_oversized_file_stops_reading_before_completion(self) -> None:
        """§3: 초과가 확인되면 그 즉시 멈춘다 — 전체를 다 읽고 나서 검사하지 않는다."""

        fake_file = self._FakeAsyncFile(b"a" * 100)
        with self.assertRaises(FileTooLargeError):
            await read_upload_with_limit(fake_file, max_bytes=10, chunk_size=4)
        # 100 bytes를 chunk_size 4로 전부 읽으려면 25번 read()가 필요하다 — 상한(10)을
        # 넘는 순간(3번째 chunk, 12 bytes 누적) 멈췄다면 훨씬 적게 호출됐어야 한다.
        self.assertLess(fake_file.read_calls, 25)


class DedupeCandidatesConfidencePriorityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.subject_a = SubjectProfile(
            subject_id="subj_offered_a", label="확률과 통계",
            trait_vector={"causal_analysis": 1.0}, related_major_ids=["industrial_engineering"],
            source_id="https://example.moe.go.kr/",
        )
        self.repository = FakeSubjectRepository([self.subject_a])
        self.course_planning_store = InMemoryCoursePlanningStore()
        self.course_planning_service = CoursePlanningService(
            self.repository, major_profiles=VERTICAL_SLICE_MAJOR_PROFILES,
            trait_definitions=_TRAIT_DEFS, course_planning_store=self.course_planning_store,
        )
        self.alias_index = SubjectAliasIndex(
            [
                {"alias": "확률과 통계", "canonical_subject_name": "확률과 통계", "subject_id": "subj_offered_a", "curriculum_code": "test"},
                {"alias": "확률통계", "canonical_subject_name": "확률과 통계", "subject_id": "subj_offered_a", "curriculum_code": "test"},
            ]
        )
        self.parsing_service = CourseDocumentParsingService(
            self.alias_index, self.repository, self.course_planning_service, self.course_planning_store
        )
        self.state = _state_with_ie_evidence()

    def _confidences_for(self, subject_id: str, texts: list[str]) -> list[ParsedSubjectCandidate]:
        content = _build_xlsx_bytes(texts)
        candidates, _warnings = self.parsing_service.parse_upload(
            self.state, "industrial_engineering", content, "offerings.xlsx", _XLSX_CONTENT_TYPE,
        )
        return candidates

    def test_low_then_high_keeps_high(self) -> None:
        # "확률통계"는 alias 표에 정확히 등록돼 있어 실제로는 high로 잡힌다 — 우선순위
        # 로직 자체를 직접 검증하기 위해 _dedupe_candidates를 단위로 호출한다.
        from src.schemas.course import ParsedSubjectCandidate as PSC
        from src.services.course_document_parsing_service import _dedupe_candidates

        low_first = PSC(raw_text="확율과 통계", matched_subject_id="subj_offered_a", confidence="low", requires_user_confirmation=True)
        high_second = PSC(raw_text="확률과 통계", matched_subject_id="subj_offered_a", confidence="high", requires_user_confirmation=False)
        result = _dedupe_candidates([low_first, high_second])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].confidence, "high")

    def test_high_then_low_keeps_high(self) -> None:
        from src.schemas.course import ParsedSubjectCandidate as PSC
        from src.services.course_document_parsing_service import _dedupe_candidates

        high_first = PSC(raw_text="확률과 통계", matched_subject_id="subj_offered_a", confidence="high", requires_user_confirmation=False)
        low_second = PSC(raw_text="확율과 통계", matched_subject_id="subj_offered_a", confidence="low", requires_user_confirmation=True)
        result = _dedupe_candidates([high_first, low_second])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].confidence, "high")

    def test_low_duplicated_keeps_first_low(self) -> None:
        from src.schemas.course import ParsedSubjectCandidate as PSC
        from src.services.course_document_parsing_service import _dedupe_candidates

        first = PSC(raw_text="확율과 통계1", matched_subject_id="subj_offered_a", confidence="low", requires_user_confirmation=True)
        second = PSC(raw_text="확율과 통계2", matched_subject_id="subj_offered_a", confidence="low", requires_user_confirmation=True)
        result = _dedupe_candidates([first, second])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].raw_text, "확율과 통계1")

    def test_identical_unmatched_duplicate_keeps_one(self) -> None:
        from src.schemas.course import ParsedSubjectCandidate as PSC
        from src.services.course_document_parsing_service import _dedupe_candidates

        first = PSC(raw_text="정체불명 과목ABC", matched_subject_id=None, confidence="unmatched", requires_user_confirmation=True)
        second = PSC(raw_text="정체불명 과목ABC", matched_subject_id=None, confidence="unmatched", requires_user_confirmation=True)
        result = _dedupe_candidates([first, second])
        self.assertEqual(len(result), 1)

    def test_different_unmatched_both_kept(self) -> None:
        from src.schemas.course import ParsedSubjectCandidate as PSC
        from src.services.course_document_parsing_service import _dedupe_candidates

        first = PSC(raw_text="정체불명 과목A", matched_subject_id=None, confidence="unmatched", requires_user_confirmation=True)
        second = PSC(raw_text="정체불명 과목B", matched_subject_id=None, confidence="unmatched", requires_user_confirmation=True)
        result = _dedupe_candidates([first, second])
        self.assertEqual(len(result), 2)

    def test_result_order_is_deterministic_across_runs(self) -> None:
        from src.schemas.course import ParsedSubjectCandidate as PSC
        from src.services.course_document_parsing_service import _dedupe_candidates

        candidates = [
            PSC(raw_text="정체불명 과목A", matched_subject_id=None, confidence="unmatched", requires_user_confirmation=True),
            PSC(raw_text="확율과 통계", matched_subject_id="subj_offered_a", confidence="low", requires_user_confirmation=True),
            PSC(raw_text="정체불명 과목B", matched_subject_id=None, confidence="unmatched", requires_user_confirmation=True),
            PSC(raw_text="확률과 통계", matched_subject_id="subj_offered_a", confidence="high", requires_user_confirmation=False),
        ]
        first_run = _dedupe_candidates(candidates)
        second_run = _dedupe_candidates(list(candidates))
        self.assertEqual([c.raw_text for c in first_run], [c.raw_text for c in second_run])
        self.assertEqual([c.raw_text for c in first_run], ["정체불명 과목A", "확률과 통계", "정체불명 과목B"])
        self.assertEqual(first_run[1].confidence, "high")


if __name__ == "__main__":
    unittest.main()
