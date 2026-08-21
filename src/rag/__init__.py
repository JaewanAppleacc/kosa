"""RAG Pipeline (작업자 C 소유) — 설계안 §19.

공식 홈페이지 자료 수집 → 정규화 → Chunking → Embedding → 색인 → 검색까지를 담당하며,
검색 결과는 A가 확정한 `src/schemas/retrieval.py`의 `RetrievedDocument`로만 반환한다.

모듈 구성:
    normalize.py  수집한 원문 텍스트 정규화
    chunk.py      Chunk 분할 (문단·문장 경계 우선, 겹침 허용)
    embed.py      Embedder 프로토콜 + 오프라인 기본 구현 + OpenAI 구현
    ingest.py     DocumentManifestEntry 기반 수집 이력 관리
    retrieve.py   BM25 + Vector + RRF 검색, DocumentRetriever Protocol 구현
"""
