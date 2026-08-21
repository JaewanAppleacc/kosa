"""RAG 검색 결과 Schema — 설계안 §19 구현. C의 RAG Pipeline(src/rag/)이 반환하는 계약."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel


class RetrievedDocument(BaseModel):
    """§19: "검색 결과에 본문 일부, 공식 URL, 기준일, 점수·순위 Metadata를 포함한다."
    근거 없는 설명을 생성하지 않기 위해, 이 문서가 없으면 RAG 기반 설명 자체를 만들지 않는다.
    """

    document_id: str
    source_url: str
    as_of_date: date
    document_type: str  # 예: "학과 소개", "교육과정", "졸업요건"
    excerpt: str  # 본문 일부(전체 아님)
    relevance_score: float
    rank: int
    related_department_id: str | None = None


class DocumentManifestStatus(str, Enum):
    """§19 수집 파이프라인("공식 홈페이지 → 수집 및 출처 기록 → 정규화 → Chunking →
    Embedding → PostgreSQL+pgvector")에서 원본 문서 하나가 지금 어느 단계에 있는지 추적한다.
    RetrievedDocument와는 다른 개념이다 — RetrievedDocument는 이미 색인이 끝나 검색에 쓸 수
    있는 결과물이고, 이건 그 색인이 끝나기 *전까지*의 처리 상태를 본다."""

    LISTED = "LISTED"  # URL만 발견됨, 아직 가져오지 않음
    TEXT_AVAILABLE = "TEXT_AVAILABLE"  # 본문 추출 성공
    TEXT_EMPTY = "TEXT_EMPTY"  # 가져왔지만 쓸 수 있는 본문이 없음(추출 실패 포함)
    RAG_INDEXED = "RAG_INDEXED"  # Chunking·Embedding까지 끝나 pgvector에 색인됨


class DocumentManifestEntry(BaseModel):
    """수집 대상 문서 하나의 처리 이력. `src/rag/ingest.py`가 만들고 갱신한다."""

    document_id: str
    source_url: str
    document_type: str
    status: DocumentManifestStatus
    related_department_id: str | None = None
    as_of_date: date | None = None  # LISTED 단계에서는 아직 없을 수 있다
    fetched_at: datetime | None = None
    indexed_at: datetime | None = None
    error_message: str | None = None  # TEXT_EMPTY일 때 실패 사유를 남긴다
