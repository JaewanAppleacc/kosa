"""검색 — 설계안 §19 "Keyword/BM25 · Vector Search · 필요 시 RRF".

`RagRetriever`는 A가 정의한 `DocumentRetriever` Protocol(`src/repositories/protocols.py`)을
만족하고, 결과를 `RetrievedDocument`로만 돌려준다. 본문 일부·공식 URL·기준일·점수·순위가
전부 채워지지 않는 결과는 만들지 않는다 — 출처 없는 결과가 나가면 §27 "검색 근거가 없는
내용을 새로 생성하지 않는다"를 상위 계층에서 지킬 방법이 없어진다.

한국어 토큰화에 형태소 분석기를 쓰지 않는다(의존성 추가는 A 결정). 대신 어절 + 문자
bi-gram을 함께 색인한다 — "컴퓨터공학부"와 "컴퓨터공학"처럼 조사·접미가 붙어 어절이
어긋나는 경우를 bi-gram이 잡아준다. 형태소 분석기를 도입하면 `tokenize()`만 교체한다.
"""

from __future__ import annotations

import math
from collections import Counter
from pathlib import Path

from src.rag.embed import Embedder, VectorIndex, default_embedder
from src.rag.ingest import DocumentSource, IndexedChunk, ingest, load_sources
from src.schemas.retrieval import RetrievedDocument

BM25_K1 = 1.5
BM25_B = 0.75
RRF_K = 60  # RRF 상수. 원 논문(Cormack et al., 2009) 권장값
DEFAULT_EXCERPT_CHARS = 220
# 질의어 중 몇 할이 본문에 실제로 나타나야 결과로 인정할지. BM25도 벡터 검색도 "가장 덜
# 안 맞는 문서"를 항상 돌려주기 때문에, 바닥선이 없으면 코퍼스에 근거가 없는 질의에도
# 그럴듯한 결과가 나간다. 상위 계층이 그걸 근거로 문장을 만들면 §27 위반이 된다.
DEFAULT_MIN_QUERY_COVERAGE = 0.3


def query_words(query: str) -> list[str]:
    """질의를 어절 단위로만 쪼갠다 — 바닥선 판정에 bi-gram을 쓰면 우연한 두 글자 겹침으로
    통과해 버려서, 근거 없는 결과를 거르는 목적을 달성하지 못한다."""

    cleaned = "".join(ch if ch.isalnum() else " " for ch in query.lower())
    return [w for w in cleaned.split() if len(w) >= 2]


def query_coverage(query: str, text: str) -> float:
    """질의 어절 중 본문에 실제로 등장하는 비율. 조사가 붙어도 잡히도록 부분 문자열로 본다."""

    words = query_words(query)
    if not words:
        return 0.0
    lowered = text.lower()
    return sum(1 for w in words if w in lowered) / len(words)


def tokenize(text: str) -> list[str]:
    cleaned = "".join(ch if ch.isalnum() else " " for ch in text.lower())
    words = [w for w in cleaned.split() if w]
    tokens: list[str] = list(words)
    for word in words:
        for i in range(len(word) - 1):
            tokens.append(word[i : i + 2])
    return tokens


class BM25Index:
    """표준 BM25 Okapi. 문서 수가 수천 단위라 역색인 없이 전수 계산해도 충분하다."""

    def __init__(self, documents: dict[str, str]) -> None:
        self._tokens: dict[str, Counter[str]] = {
            key: Counter(tokenize(text)) for key, text in documents.items()
        }
        self._lengths = {key: sum(c.values()) for key, c in self._tokens.items()}
        self._average_length = (
            sum(self._lengths.values()) / len(self._lengths) if self._lengths else 0.0
        )
        self._document_frequency: Counter[str] = Counter()
        for counter in self._tokens.values():
            self._document_frequency.update(counter.keys())
        self._count = len(self._tokens)

    def search(self, query: str, top_k: int) -> list[tuple[str, float]]:
        if self._count == 0:
            return []
        query_tokens = set(tokenize(query))
        scored: list[tuple[str, float]] = []
        for key, counter in self._tokens.items():
            score = 0.0
            for token in query_tokens:
                frequency = counter.get(token, 0)
                if frequency == 0:
                    continue
                document_frequency = self._document_frequency[token]
                idf = math.log(
                    1 + (self._count - document_frequency + 0.5) / (document_frequency + 0.5)
                )
                length_norm = 1 - BM25_B + BM25_B * (
                    self._lengths[key] / self._average_length if self._average_length else 1
                )
                score += idf * (frequency * (BM25_K1 + 1)) / (frequency + BM25_K1 * length_norm)
            if score > 0:
                scored.append((key, score))
        scored.sort(key=lambda item: (-item[1], item[0]))
        return scored[:top_k]


def reciprocal_rank_fusion(
    ranked_lists: list[list[str]], k: int = RRF_K
) -> list[tuple[str, float]]:
    """RRF: 서로 스케일이 다른 BM25 점수와 코사인 유사도를 직접 더하지 않고 순위만 합친다.

    점수를 정규화해서 더하는 방식은 한쪽 분포가 바뀌면 가중치가 조용히 틀어진다 —
    순위 기반은 그 문제가 없다.
    """

    fused: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, key in enumerate(ranked, start=1):
            fused[key] = fused.get(key, 0.0) + 1.0 / (k + rank)
    return sorted(fused.items(), key=lambda item: (-item[1], item[0]))


def build_excerpt(text: str, query: str, max_chars: int = DEFAULT_EXCERPT_CHARS) -> str:
    """질의어가 등장하는 위치 주변을 잘라 본문 일부만 보여준다. 전체 본문을 그대로 싣지
    않는 이유는 §19가 "본문 일부"를 요구하기 때문이고, 질의어 주변을 고르는 이유는
    검토자가 왜 이 문서가 걸렸는지 바로 확인할 수 있게 하기 위해서다."""

    if len(text) <= max_chars:
        return text
    lowered = text.lower()
    position = -1
    for token in sorted(set(tokenize(query)), key=len, reverse=True):
        position = lowered.find(token)
        if position >= 0:
            break
    if position < 0:
        return text[:max_chars].rstrip() + "…"
    start = max(0, position - max_chars // 3)
    excerpt = text[start : start + max_chars].strip()
    prefix = "…" if start > 0 else ""
    suffix = "…" if start + max_chars < len(text) else ""
    return f"{prefix}{excerpt}{suffix}"


class RagRetriever:
    """`DocumentRetriever` Protocol 구현체."""

    def __init__(
        self,
        indexed_chunks: list[IndexedChunk],
        vector_index: VectorIndex,
        embedder: Embedder,
    ) -> None:
        self._chunks: dict[str, IndexedChunk] = {c.chunk.chunk_id: c for c in indexed_chunks}
        self._vector_index = vector_index
        self._embedder = embedder
        self._bm25 = BM25Index(
            {
                chunk_id: f"{c.title} {c.chunk.section_title or ''} {c.chunk.text}"
                for chunk_id, c in self._chunks.items()
            }
        )

    def __len__(self) -> int:
        return len(self._chunks)

    def search(
        self,
        query: str,
        filters: dict[str, str] | None = None,
        top_k: int = 5,
        minimum_query_coverage: float = DEFAULT_MIN_QUERY_COVERAGE,
    ) -> list[RetrievedDocument]:
        if not query.strip():
            return []

        # 필터를 먼저 적용하지 않고 넓게 뽑은 뒤 거른다 — 필터가 좁을 때 후보가 top_k보다
        # 적어지는 걸 막기 위해 후보를 넉넉히(top_k의 5배, 최소 20개) 가져온다.
        candidate_size = max(top_k * 5, 20)
        bm25_ranked = [key for key, _ in self._bm25.search(query, candidate_size)]
        query_vector = self._embedder.embed([query])[0]
        vector_ranked = [key for key, _ in self._vector_index.search(query_vector, candidate_size)]

        fused = reciprocal_rank_fusion([bm25_ranked, vector_ranked])

        results: list[RetrievedDocument] = []
        for chunk_id, score in fused:
            indexed = self._chunks.get(chunk_id)
            if indexed is None or not self._passes_filters(indexed, filters):
                continue
            haystack = f"{indexed.title} {indexed.chunk.section_title or ''} {indexed.chunk.text}"
            if query_coverage(query, haystack) < minimum_query_coverage:
                continue
            results.append(
                RetrievedDocument(
                    document_id=indexed.chunk.chunk_id,
                    source_url=indexed.source_url,
                    as_of_date=indexed.as_of_date,
                    document_type=indexed.document_type,
                    excerpt=build_excerpt(indexed.chunk.text, query),
                    relevance_score=round(score, 6),
                    rank=len(results) + 1,
                    related_department_id=indexed.related_department_id,
                )
            )
            if len(results) >= top_k:
                break
        return results

    @staticmethod
    def _passes_filters(indexed: IndexedChunk, filters: dict[str, str] | None) -> bool:
        if not filters:
            return True
        for key, value in filters.items():
            if key == "related_department_id":
                if indexed.related_department_id != value:
                    return False
            elif key == "document_type":
                if indexed.document_type != value:
                    return False
            else:
                raise ValueError(f"지원하지 않는 filter 키: {key!r}")
        return True


def build_retriever(
    sources: list[DocumentSource],
    base_dir: Path,
    embedder: Embedder | None = None,
) -> RagRetriever:
    embedder = embedder or default_embedder()
    result, vector_index = ingest(sources, base_dir=base_dir, embedder=embedder)
    return RagRetriever(result.indexed_chunks, vector_index, embedder)


def build_retriever_from_data_dir(
    data_dir: Path, embedder: Embedder | None = None
) -> RagRetriever:
    """`data/rag/sources.jsonl`을 읽어 바로 쓸 수 있는 Retriever를 만든다.

    수집 원문은 `data/rag/documents/` 아래에 이미 있어야 한다 — 이 함수는 네트워크를
    치지 않는다.
    """

    return build_retriever(
        load_sources(data_dir / "rag" / "sources.jsonl"),
        base_dir=data_dir / "rag",
        embedder=embedder,
    )
