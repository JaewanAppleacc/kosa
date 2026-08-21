"""RAG Manifest·초안 검토 상태 Schema 테스트."""

from __future__ import annotations

import unittest
from datetime import date, datetime

import pydantic

from src.schemas.major import MappingReview
from src.schemas.retrieval import DocumentManifestEntry, DocumentManifestStatus
from src.schemas.review import DraftEntry, DraftReviewStage


class DocumentManifestTest(unittest.TestCase):
    def test_listed_entry_allows_missing_dates(self) -> None:
        entry = DocumentManifestEntry(
            document_id="doc_1",
            source_url="https://example.ac.kr/media-comm",
            document_type="학과 소개",
            status=DocumentManifestStatus.LISTED,
        )
        self.assertIsNone(entry.as_of_date)
        self.assertIsNone(entry.fetched_at)

    def test_indexed_entry_with_full_timeline(self) -> None:
        entry = DocumentManifestEntry(
            document_id="doc_2",
            source_url="https://example.ac.kr/curriculum",
            document_type="교육과정",
            status=DocumentManifestStatus.RAG_INDEXED,
            as_of_date=date(2025, 3, 1),
            fetched_at=datetime(2026, 8, 21, 9, 0),
            indexed_at=datetime(2026, 8, 21, 9, 5),
        )
        self.assertEqual(entry.status, DocumentManifestStatus.RAG_INDEXED)

    def test_text_empty_can_record_error(self) -> None:
        entry = DocumentManifestEntry(
            document_id="doc_3",
            source_url="https://example.ac.kr/broken",
            document_type="학과 소개",
            status=DocumentManifestStatus.TEXT_EMPTY,
            error_message="PDF 파싱 실패: 스캔본이라 텍스트 레이어 없음",
        )
        self.assertIn("파싱 실패", entry.error_message)

    def test_invalid_status_rejected(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            DocumentManifestEntry(
                document_id="doc_4",
                source_url="https://example.ac.kr",
                document_type="학과 소개",
                status="NOT_A_REAL_STATUS",  # type: ignore[arg-type]
            )


class DraftReviewStageNoCollisionTest(unittest.TestCase):
    """DraftReviewStage와 MappingReview.agreement_status는 서로 다른 이름 체계를 써야 한다."""

    def test_draft_review_stage_values_do_not_collide_with_mapping_review(self) -> None:
        draft_values = {s.value for s in DraftReviewStage}
        mapping_review_values = {"AGREED", "REVIEW_REQUIRED", "REJECTED"}
        self.assertEqual(draft_values & mapping_review_values, set())

    def test_mapping_review_still_uses_its_own_vocabulary(self) -> None:
        review = MappingReview(
            mapping_id="m1",
            author_id="c1",
            reviewer_ids=["a1"],
            agreement_status="REVIEW_REQUIRED",
            source_ids=["src1"],
            mapping_version="v1",
            reviewed_at=datetime.now(),
        )
        self.assertEqual(review.agreement_status, "REVIEW_REQUIRED")


class DraftEntryTest(unittest.TestCase):
    def test_draft_entry_full_metadata(self) -> None:
        entry = DraftEntry(
            draft_id="draft_1",
            draft_type="major_trait_mapping",
            author_id="worker_c",
            review_stage=DraftReviewStage.STAGED,
            source_url="https://example.ac.kr/curriculum",
            as_of_date=date(2026, 8, 21),
            notes="미디어커뮤니케이션 전공 Trait 매핑 초안",
        )
        self.assertEqual(entry.review_stage, DraftReviewStage.STAGED)

    def test_draft_entry_minimal_metadata(self) -> None:
        entry = DraftEntry(
            draft_id="draft_2",
            draft_type="context_trait_review",
            author_id="worker_c",
            review_stage=DraftReviewStage.DRAFT,
        )
        self.assertIsNone(entry.source_url)

    def test_invalid_draft_type_rejected(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            DraftEntry(
                draft_id="draft_3",
                draft_type="not_a_real_type",  # type: ignore[arg-type]
                author_id="worker_c",
                review_stage=DraftReviewStage.DRAFT,
            )


if __name__ == "__main__":
    unittest.main()
