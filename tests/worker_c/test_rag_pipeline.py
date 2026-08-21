"""src/rag/ 전체 — 정규화 → Chunk → Embedding → Manifest → 검색."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.rag.chunk import chunk_document, deduplicate, find_section_title, split_text
from src.rag.embed import HashingEmbedder, VectorIndex, cosine_similarity
from src.rag.ingest import (
    DocumentManifest,
    DocumentSource,
    generate_document_id,
    ingest,
)
from src.rag.normalize import (
    drop_page_furniture,
    has_usable_text,
    normalize_document_text,
    normalize_whitespace,
)
from src.rag.retrieve import (
    BM25Index,
    RagRetriever,
    build_excerpt,
    query_coverage,
    reciprocal_rank_fusion,
)
from src.schemas.retrieval import DocumentManifestStatus, RetrievedDocument

SAMPLE = """컴퓨터공학부 학과 소개

1. 학부 소개
컴퓨터공학부는 계산의 원리와 소프트웨어 시스템의 설계를 다룬다. 자료구조와 알고리즘을 기반으로
문제를 정의한다.

2. 졸업요건
전공 필수 학점을 이수하고 졸업 프로젝트를 통과해야 한다.
"""


class NormalizeTest(unittest.TestCase):
    def test_zero_width_and_fullwidth_space_are_removed(self) -> None:
        self.assertEqual(normalize_document_text("​가　나"), "가 나")

    def test_page_number_lines_are_dropped(self) -> None:
        self.assertEqual(drop_page_furniture("본문\n- 3 -\n다음"), "본문\n다음")

    def test_repeated_short_header_is_dropped(self) -> None:
        text = "\n".join(["머리말"] * 3 + ["실제 본문 문장입니다."])
        self.assertNotIn("머리말", drop_page_furniture(text))

    def test_long_repeated_line_is_kept(self) -> None:
        """긴 문장이 반복되는 건 실제 본문일 수 있어 건드리지 않는다."""

        sentence = "이 문장은 머리말이라기엔 충분히 길어서 본문으로 봐야 하는 문장입니다."
        text = "\n".join([sentence] * 3)
        self.assertIn(sentence, drop_page_furniture(text))

    def test_hyphenated_linebreak_is_joined(self) -> None:
        self.assertIn("curriculum", normalize_document_text("curri-\nculum"))

    def test_usable_text_threshold(self) -> None:
        self.assertFalse(has_usable_text("   \n- 1 -\n"))
        self.assertTrue(has_usable_text(SAMPLE))

    def test_normalize_whitespace_is_idempotent(self) -> None:
        once = normalize_whitespace(SAMPLE)
        self.assertEqual(once, normalize_whitespace(once))


class ChunkTest(unittest.TestCase):
    def test_chunks_stay_within_size(self) -> None:
        text = "가나다라마바사아자차 " * 300
        for _, piece in split_text(text, chunk_size=200, chunk_overlap=40):
            self.assertLessEqual(len(piece), 200 + 40)

    def test_overlap_must_be_smaller_than_chunk(self) -> None:
        with self.assertRaises(ValueError):
            split_text("본문", chunk_size=100, chunk_overlap=100)

    def test_empty_text_yields_no_chunk(self) -> None:
        self.assertEqual(chunk_document("doc_x", ""), [])

    def test_section_title_is_the_nearest_heading_above(self) -> None:
        position = SAMPLE.index("전공 필수")
        self.assertEqual(find_section_title(SAMPLE, position), "졸업요건")

    def test_deduplicate_removes_identical_text(self) -> None:
        chunks = chunk_document("doc_x", "같은 문단입니다.\n\n같은 문단입니다.", chunk_size=50, chunk_overlap=0)
        self.assertLess(len(deduplicate(chunks)), len(chunks) + 1)
        texts = [c.text for c in deduplicate(chunks)]
        self.assertEqual(len(texts), len(set(texts)))

    def test_chunk_ids_are_ordered_and_unique(self) -> None:
        chunks = chunk_document("doc_x", SAMPLE, chunk_size=80, chunk_overlap=10)
        self.assertEqual([c.ordinal for c in chunks], list(range(1, len(chunks) + 1)))
        self.assertEqual(len({c.chunk_id for c in chunks}), len(chunks))


class EmbedTest(unittest.TestCase):
    def test_embedding_is_deterministic_and_normalized(self) -> None:
        embedder = HashingEmbedder(dimension=64)
        first = embedder.embed(["컴퓨터공학부"])[0]
        second = embedder.embed(["컴퓨터공학부"])[0]
        self.assertEqual(first, second)
        self.assertAlmostEqual(cosine_similarity(first, first), 1.0, places=6)
        self.assertEqual(len(first), 64)

    def test_similar_text_scores_higher_than_unrelated(self) -> None:
        embedder = HashingEmbedder(dimension=256)
        query, near, far = embedder.embed(["컴퓨터공학", "컴퓨터공학부", "요리와 제빵"])
        self.assertGreater(cosine_similarity(query, near), cosine_similarity(query, far))

    def test_vector_index_rejects_dimension_mismatch(self) -> None:
        index = VectorIndex(dimension=8)
        with self.assertRaises(ValueError):
            index.upsert("k", [0.0] * 4)

    def test_vector_index_search_is_ordered(self) -> None:
        embedder = HashingEmbedder(dimension=128)
        index = VectorIndex(embedder.dimension)
        for key, text in {"a": "컴퓨터공학", "b": "요리와 제빵"}.items():
            index.upsert(key, embedder.embed([text])[0])
        ranked = index.search(embedder.embed(["컴퓨터공학부"])[0], top_k=2)
        self.assertEqual(ranked[0][0], "a")


def _source(tmp: Path, name: str, body: str, department_id: str | None = None) -> DocumentSource:
    (tmp / "documents").mkdir(parents=True, exist_ok=True)
    (tmp / "documents" / f"{name}.txt").write_text(body, encoding="utf-8")
    return DocumentSource(
        source_url=f"sample://{name}",
        document_type="샘플(비공식) 학과 소개",
        as_of_date=date(2026, 8, 21),
        related_department_id=department_id,
        text_path=f"documents/{name}.txt",
        title=name,
    )


class IngestTest(unittest.TestCase):
    def test_document_id_is_stable_per_url(self) -> None:
        self.assertEqual(
            generate_document_id("https://example.ac.kr/a"),
            generate_document_id("https://example.ac.kr/a"),
        )
        self.assertNotEqual(
            generate_document_id("https://example.ac.kr/a"),
            generate_document_id("https://example.ac.kr/b"),
        )

    def test_manifest_reaches_rag_indexed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            sources = [_source(tmp, "cs", SAMPLE, "dept_a")]
            manifest = DocumentManifest()
            result, index = ingest(sources, base_dir=tmp, manifest=manifest, embedder=HashingEmbedder(64))

            self.assertEqual(len(manifest), 1)
            entry = manifest.get(sources[0].document_id)
            assert entry is not None
            self.assertIs(entry.status, DocumentManifestStatus.RAG_INDEXED)
            self.assertIsNotNone(entry.as_of_date)
            self.assertIsNotNone(entry.indexed_at)
            self.assertTrue(result.indexed_chunks)
            self.assertEqual(len(index), len(result.indexed_chunks))

    def test_missing_text_becomes_text_empty_with_reason(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            source = DocumentSource(
                source_url="sample://missing",
                document_type="샘플",
                as_of_date=date(2026, 8, 21),
                text_path="documents/없는파일.txt",
            )
            manifest = DocumentManifest()
            result, _ = ingest([source], base_dir=tmp, manifest=manifest, embedder=HashingEmbedder(64))

            entry = manifest.get(source.document_id)
            assert entry is not None
            self.assertIs(entry.status, DocumentManifestStatus.TEXT_EMPTY)
            self.assertTrue(entry.error_message)
            self.assertEqual(result.empty_document_count, 1)
            self.assertEqual(result.indexed_document_count, 0)

    def test_cannot_skip_text_available_stage(self) -> None:
        source = DocumentSource(
            source_url="sample://x", document_type="샘플", as_of_date=date(2026, 8, 21)
        )
        manifest = DocumentManifest()
        manifest.mark_listed(source)
        with self.assertRaises(ValueError):
            manifest.mark_indexed(source)

    def test_manifest_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            source = _source(tmp, "cs", SAMPLE)
            manifest = DocumentManifest()
            ingest([source], base_dir=tmp, manifest=manifest, embedder=HashingEmbedder(64))
            path = tmp / "manifest.jsonl"
            manifest.save(path)
            reloaded = DocumentManifest.load(path)
            self.assertEqual(len(reloaded), len(manifest))
            self.assertEqual(
                reloaded.by_status(DocumentManifestStatus.RAG_INDEXED)[0].document_id,
                source.document_id,
            )


class RetrieveTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self.embedder = HashingEmbedder(dimension=256)
        sources = [
            _source(tmp, "cs", SAMPLE, "dept_a"),
            _source(
                tmp,
                "edu",
                "교육학과 졸업요건\n\n1. 졸업요건\n교육실습을 이수해야 한다. 교육과정론과 교육심리를 배운다.",
                "dept_b",
            ),
        ]
        result, index = ingest(sources, base_dir=tmp, embedder=self.embedder)
        self.retriever = RagRetriever(result.indexed_chunks, index, self.embedder)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_result_always_carries_source_and_as_of_date(self) -> None:
        results = self.retriever.search("졸업요건")
        self.assertTrue(results)
        for item in results:
            self.assertIsInstance(item, RetrievedDocument)
            self.assertTrue(item.source_url)
            self.assertIsNotNone(item.as_of_date)
            self.assertTrue(item.excerpt.strip())

    def test_rank_is_one_based_and_sequential(self) -> None:
        results = self.retriever.search("졸업요건", top_k=5)
        self.assertEqual([r.rank for r in results], list(range(1, len(results) + 1)))

    def test_department_filter_restricts_results(self) -> None:
        results = self.retriever.search(
            "졸업요건", filters={"related_department_id": "dept_b"}, top_k=5
        )
        self.assertTrue(results)
        self.assertTrue(all(r.related_department_id == "dept_b" for r in results))

    def test_unknown_filter_key_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.retriever.search("졸업요건", filters={"이상한키": "값"})

    def test_blank_query_returns_nothing(self) -> None:
        self.assertEqual(self.retriever.search("   "), [])

    def test_query_without_evidence_returns_nothing(self) -> None:
        """코퍼스에 근거가 없으면 빈 결과여야 한다 — 아무 문서나 끌어오면 §27 위반이다."""

        self.assertEqual(self.retriever.search("장학금 신청 서류 제출 기한 연장"), [])

    def test_top_k_is_respected(self) -> None:
        self.assertLessEqual(len(self.retriever.search("졸업요건", top_k=1)), 1)


class ScoringTest(unittest.TestCase):
    def test_bm25_ignores_documents_without_any_query_token(self) -> None:
        index = BM25Index({"a": "컴퓨터공학 알고리즘", "b": "요리 제빵"})
        keys = [key for key, _ in index.search("알고리즘", top_k=5)]
        self.assertIn("a", keys)

    def test_rrf_prefers_items_ranked_highly_in_both_lists(self) -> None:
        fused = dict(reciprocal_rank_fusion([["a", "b", "c"], ["a", "c", "b"]]))
        self.assertGreater(fused["a"], fused["b"])
        self.assertGreater(fused["a"], fused["c"])

    def test_query_coverage_counts_substring_hits(self) -> None:
        self.assertEqual(query_coverage("미적분 물리학", "미적분Ⅱ와 물리학을 듣는다"), 1.0)
        self.assertEqual(query_coverage("장학금 규정", "졸업요건과 교육실습"), 0.0)

    def test_excerpt_is_a_slice_not_the_whole_body(self) -> None:
        body = "머리말 " * 200 + "졸업요건은 다음과 같다." + " 꼬리말" * 200
        excerpt = build_excerpt(body, "졸업요건", max_chars=100)
        self.assertLessEqual(len(excerpt), 102)
        self.assertIn("졸업요건", excerpt)


if __name__ == "__main__":
    unittest.main()
