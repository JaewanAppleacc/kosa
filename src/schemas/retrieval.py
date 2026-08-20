"""RAG 검색 결과 Schema — 설계안 §19 구현. C의 RAG Pipeline(src/rag/)이 반환하는 계약."""

from __future__ import annotations

from datetime import date

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
