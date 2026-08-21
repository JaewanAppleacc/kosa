"""Embedding — 설계안 §19 "Embedding → PostgreSQL + pgvector" 단계.

두 가지 구현을 둔다.

1. `HashingEmbedder` — 기본값. 외부 호출 없이 결정적으로 벡터를 만든다. 문자 n-gram을
   해싱해 고정 차원에 누적하는 방식(feature hashing)이라 같은 입력에 항상 같은 벡터가
   나오고, 네트워크·API Key 없이 테스트가 돈다. 의미 유사도 품질은 실제 임베딩 모델보다
   낮다 — 철자가 겹치는 한국어 학과명·과목명 매칭에는 쓸 만하지만, 문장 의미가 다른데
   표기만 비슷한 경우를 구분하지 못한다. 운영 검색 품질을 이걸로 주장하지 않는다.
2. `OpenAIEmbedder` — `OPENAI_API_KEY`와 `OPENAI_EMBEDDING_MODEL`이 있을 때만 쓴다.
   `.env.example`에 이미 변수명이 잡혀 있다.

pgvector 색인은 아직 붙이지 않았다 — `requirements-lock.txt`에 DB 드라이버가 없고 DB
기동은 A 소유 결정이다. 대신 `VectorIndex`가 같은 인터페이스(upsert/search)를 제공하고,
pgvector가 들어오면 이 클래스만 교체하면 retrieve.py는 바뀌지 않는다.
"""

from __future__ import annotations

import hashlib
import math
import os
from typing import Protocol

DEFAULT_DIMENSION = 512
_NGRAM_SIZES = (2, 3)


class Embedder(Protocol):
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _character_ngrams(text: str) -> list[str]:
    cleaned = "".join(ch if ch.isalnum() else " " for ch in text.lower())
    tokens = [t for t in cleaned.split() if t]
    grams: list[str] = list(tokens)
    joined = " ".join(tokens)
    for size in _NGRAM_SIZES:
        for i in range(len(joined) - size + 1):
            gram = joined[i : i + size]
            if gram.strip():
                grams.append(gram)
    return grams


def l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0:
        return vector
    return [v / norm for v in vector]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"dimension mismatch: {len(a)} vs {len(b)}")
    return sum(x * y for x, y in zip(a, b))


class HashingEmbedder:
    """외부 호출 없는 결정적 임베더. 기본 구현이자 테스트 기준선."""

    def __init__(self, dimension: int = DEFAULT_DIMENSION) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be > 0")
        self.dimension = dimension
        self.model_name = f"hashing_ngram_v1_d{dimension}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for gram in _character_ngrams(text):
            digest = hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[bucket] += sign
        return l2_normalize(vector)


class OpenAIEmbedder:
    """OpenAI 호환 Embedding API. Key가 없으면 생성 시점에 바로 실패시킨다 —
    검색 도중에 조용히 빈 벡터를 돌려주면 원인을 찾기 어렵다."""

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        dimension: int = 1536,
    ) -> None:
        from openai import OpenAI  # 지연 import — 오프라인 경로에서는 필요 없다

        resolved_key = api_key or os.getenv("OPENAI_API_KEY")
        if not resolved_key:
            raise RuntimeError("OPENAI_API_KEY가 없다 — HashingEmbedder를 쓰거나 Key를 설정한다")
        self.model_name = model or os.getenv("OPENAI_EMBEDDING_MODEL") or "text-embedding-3-small"
        self.dimension = dimension
        self._client = OpenAI(
            api_key=resolved_key,
            base_url=base_url or os.getenv("OPENAI_EMBEDDING_BASE_URL") or None,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(model=self.model_name, input=texts)
        return [l2_normalize(list(item.embedding)) for item in response.data]


def default_embedder() -> Embedder:
    """환경변수가 갖춰졌으면 OpenAI, 아니면 오프라인 기본값.

    §10 질문 생성이 `ENABLE_LLM_QUESTION_GENERATION`으로 실수 호출을 막는 것과 같은
    이유로, Key가 없으면 조용히 오프라인 임베더로 떨어진다 — 테스트가 네트워크를
    치지 않게 하려는 안전장치다.
    """

    if os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_EMBEDDING_MODEL"):
        try:
            return OpenAIEmbedder()
        except Exception:  # noqa: BLE001 — 임베더 하나 못 만든 걸로 파이프라인을 멈추지 않는다
            return HashingEmbedder()
    return HashingEmbedder()


class VectorIndex:
    """메모리 벡터 색인. pgvector가 들어오기 전까지의 자리를 지킨다.

    검색 규모(대학 홈페이지 문서 수백~수천 Chunk)에서는 완전 탐색으로 충분하다.
    전국 확장 시 pgvector로 교체하되 `upsert()`/`search()` 시그니처는 유지한다.
    """

    def __init__(self, dimension: int) -> None:
        self.dimension = dimension
        self._vectors: dict[str, list[float]] = {}

    def __len__(self) -> int:
        return len(self._vectors)

    def upsert(self, key: str, vector: list[float]) -> None:
        if len(vector) != self.dimension:
            raise ValueError(f"dimension mismatch: expected {self.dimension}, got {len(vector)}")
        self._vectors[key] = vector

    def search(self, query_vector: list[float], top_k: int) -> list[tuple[str, float]]:
        scored = [(key, cosine_similarity(query_vector, v)) for key, v in self._vectors.items()]
        scored.sort(key=lambda item: (-item[1], item[0]))
        return scored[:top_k]
