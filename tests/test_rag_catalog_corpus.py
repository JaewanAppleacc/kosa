"""RAG 코퍼스 확장 — 2026-08-25 지시서(a/subgraph-rag-frontend-38-majors) §2 테스트.

`scripts/career_build_rag_catalog_corpus.py`가 만드는 39개 Major·학과·과목 문서를
확인한다. 다음 세 층위를 본다.

    1. 실제 산출물(`data/rag/sources.jsonl`/`data/rag/manifest.jsonl`/
       `data/rag/documents/catalog/`)이 지시서 불변식을 지키는지
       (RealCorpusInvariantsTest).
    2. 재생성이 byte-identical한지, 그리고 기존 6건(`career_build_rag_corpus.py`
       소유)이 한 바이트도 안 바뀌는지(GenerationDeterminismTest).
    3. 검색이 외부 Embedding 호출 없이(HashingEmbedder만으로) 실제로 근거 있는
       결과를 돌려주는지(OfflineRetrievalTest — 네트워크·OPENAI_API_KEY 불필요)."""

from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path

from src.rag.embed import HashingEmbedder
from src.rag.ingest import load_sources
from src.rag.retrieve import build_retriever
from src.services.service_canonical_major_v2_loader import load_service_canonical_majors_v2

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SOURCES_PATH = _REPO_ROOT / "data" / "rag" / "sources.jsonl"
_MANIFEST_PATH = _REPO_ROOT / "data" / "rag" / "manifest.jsonl"
_CATALOG_DOCS_DIR = _REPO_ROOT / "data" / "rag" / "documents" / "catalog"

# `career_build_rag_corpus.py`가 원래부터 소유한 6줄. 순서·내용을 그대로 옮겨 온다
# (사실이 아니라 "이 스크립트가 손대면 안 된다"는 가드 값이라 재계산하지 않는다).
_BASELINE_DOCUMENT_TYPES = {
    "교육통계",
    "샘플(비공식) 학과 소개",
    "샘플(비공식) 교육과정",
    "샘플(비공식) 졸업요건",
}


def _load_sources() -> list[dict]:
    return [json.loads(line) for line in _SOURCES_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


class RealCorpusInvariantsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.sources = _load_sources()
        self.majors = load_service_canonical_majors_v2()
        self.major_ids = {m.major_id for m in self.majors}

    def test_baseline_six_lines_are_untouched(self) -> None:
        baseline = [s for s in self.sources if s["document_type"] in _BASELINE_DOCUMENT_TYPES]
        self.assertEqual(len(baseline), 6)

    def test_exactly_39_major_documents(self) -> None:
        major_docs = [s for s in self.sources if s["document_type"] == "전공 정보(공식 데이터 포털 재게시)"]
        self.assertEqual(len(major_docs), 39)

    def test_every_active_major_has_a_document(self) -> None:
        major_docs = [s for s in self.sources if s["document_type"] == "전공 정보(공식 데이터 포털 재게시)"]
        covered = {doc["text_path"].rsplit("major_", 1)[1].removesuffix(".txt") for doc in major_docs}
        self.assertEqual(covered, self.major_ids, "39개 활성 Major 중 문서가 없는 Major가 있다")

    def test_design_has_no_major_document(self) -> None:
        major_docs = [s for s in self.sources if s["document_type"] == "전공 정보(공식 데이터 포털 재게시)"]
        covered = {doc["text_path"].rsplit("major_", 1)[1].removesuffix(".txt") for doc in major_docs}
        self.assertNotIn("design", covered, "design은 EXCLUDED_RECOMMENDATION이라 39개 활성 Major에 없다")

    def test_hci_ux_document_does_not_claim_automatic_group_connection(self) -> None:
        text = (_CATALOG_DOCS_DIR / "major_hci_ux.txt").read_text(encoding="utf-8")
        self.assertIn("자동으로 연결되지 않는다", text)
        self.assertIn("DEPARTMENT_LEVEL_ONLY", text)

    def test_department_documents_only_use_real_distinct_urls(self) -> None:
        dept_docs = [s for s in self.sources if s["document_type"] == "학과 정보(대학알리미 공식 데이터)"]
        # 개별 학과 문서는 department_url이 실제로 있는 19곳만 — 없는 1,053곳을 같은
        # 포털 URL로 복제하지 않는다(§ 스크립트 docstring 근거).
        self.assertEqual(len(dept_docs), 19)
        urls = [doc["source_url"] for doc in dept_docs]
        self.assertEqual(len(urls), len(set(urls)), "학과 문서 source_url이 중복되면 document_id가 충돌한다")
        for doc in dept_docs:
            self.assertIsNotNone(doc["related_department_id"])

    def test_department_roster_covers_only_majors_with_real_department_data(self) -> None:
        roster_docs = [s for s in self.sources if s["document_type"] == "학과 목록(대학알리미 공식 데이터)"]
        covered = {doc["title"].split(" ")[0] for doc in roster_docs}
        # 2026-08-25 지시서(a/final-39-major-integration) — c/national-departments-38-majors
        # 병합 이후 departments.jsonl이 8개가 아니라 38개(Group 기반 FULL_GROUP Major
        # 전부)를 커버한다. 하드코딩 대신 실제 마스터 파일에서 그대로 유도해, Master가
        # 또 갱신돼도 이 테스트가 저절로 따라가게 한다.
        departments_path = _REPO_ROOT / "data" / "master" / "departments.jsonl"
        expected = {
            json.loads(line)["canonical_major_id"]
            for line in departments_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
        self.assertEqual(covered, expected)
        self.assertEqual(len(expected), 38)
        self.assertNotIn("hci_ux", covered, "hci_ux는 개별 학과 검토가 없어 학과 목록에 나오면 안 된다")

    def test_exactly_41_subject_documents(self) -> None:
        # 2026-08-25 지시서(a/final-39-major-integration) — subjects.jsonl(18개, Legacy)
        # 대신 subject_profiles_v2.jsonl(41개, v2)을 최종 정본으로 쓴다.
        subject_docs = [s for s in self.sources if s["document_type"] == "과목 정보(교육부 공식 교육과정)"]
        self.assertEqual(len(subject_docs), 41)

    def test_all_source_urls_are_globally_unique(self) -> None:
        urls = [s["source_url"] for s in self.sources]
        self.assertEqual(len(urls), len(set(urls)), "source_url 중복은 document_id 충돌로 이어진다")

    def test_manifest_indexes_every_source(self) -> None:
        manifest_rows = [
            json.loads(line) for line in _MANIFEST_PATH.read_text(encoding="utf-8").splitlines() if line.strip()
        ]
        self.assertEqual(len(manifest_rows), len(self.sources))
        self.assertTrue(all(row["status"] == "RAG_INDEXED" for row in manifest_rows))


class GenerationDeterminismTest(unittest.TestCase):
    """재생성이 byte-identical한지 확인한다. 기존
    `test_service_canonical_major_v2.py::GenerationDeterminismTest`와 같은 패턴이다."""

    def test_regenerating_catalog_corpus_is_byte_identical(self) -> None:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--", "data/rag/"],
            cwd=_REPO_ROOT, capture_output=True, text=True,
        )
        before_status = proc.stdout

        before_sources = _SOURCES_PATH.read_bytes()
        before_manifest = _MANIFEST_PATH.read_bytes()

        result = subprocess.run(
            ["./.venv/bin/python", "scripts/career_build_rag_catalog_corpus.py"],
            cwd=_REPO_ROOT, capture_output=True, text=True, env={"PYTHONPATH": ".", "PATH": "/usr/bin:/bin"},
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        self.assertEqual(before_sources, _SOURCES_PATH.read_bytes(), "재생성 결과가 기존 sources.jsonl과 다르다")
        self.assertEqual(before_manifest, _MANIFEST_PATH.read_bytes(), "재생성 결과가 기존 manifest.jsonl과 다르다")

        proc_after = subprocess.run(
            ["git", "status", "--porcelain", "--", "data/rag/"],
            cwd=_REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(before_status, proc_after.stdout, "재생성이 추적되지 않은 파일 변화를 남겼다")

    def test_regeneration_is_independent_of_pythonhashseed(self) -> None:
        """지시서(a/final-39-major-integration) §5 "서로 다른 PYTHONHASHSEED에서
        byte-identical" — set/dict 순회가 출력 순서에 새어 들어가지 않는지 확인한다."""

        before_sources = _SOURCES_PATH.read_bytes()
        before_manifest = _MANIFEST_PATH.read_bytes()

        result = subprocess.run(
            ["./.venv/bin/python", "scripts/career_build_rag_catalog_corpus.py"],
            cwd=_REPO_ROOT, capture_output=True, text=True,
            env={"PYTHONPATH": ".", "PATH": "/usr/bin:/bin", "PYTHONHASHSEED": "999"},
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before_sources, _SOURCES_PATH.read_bytes())
        self.assertEqual(before_manifest, _MANIFEST_PATH.read_bytes())


class OfflineRetrievalTest(unittest.TestCase):
    """외부 Embedding 호출 없이(HashingEmbedder) 검색이 실제로 동작하는지 확인한다."""

    def setUp(self) -> None:
        # 이 테스트가 우연히라도 네트워크를 치지 않도록 명시적으로 끈다 — default_embedder()의
        # 기존 Flag 정책(ENABLE_OPENAI_EMBEDDING 등 3개 모두 있어야 OpenAI로 간다)을 그대로
        # 신뢰하되, 테스트 환경 변수 오염에 기대지 않는다.
        os.environ.pop("ENABLE_OPENAI_EMBEDDING", None)
        sources = load_sources(_SOURCES_PATH)
        self.retriever = build_retriever(sources, base_dir=_SOURCES_PATH.parent, embedder=HashingEmbedder())

    def test_hci_ux_query_surfaces_the_hci_ux_document(self) -> None:
        results = self.retriever.search("HCI UX 인터랙션 디자인 사용자 경험", top_k=5)
        self.assertTrue(results, "근거 있는 질의인데 결과가 비었다")
        self.assertTrue(any("hci_ux" in r.source_url for r in results))
        for r in results:
            self.assertTrue(r.source_url)
            self.assertTrue(r.excerpt)


if __name__ == "__main__":
    unittest.main()
