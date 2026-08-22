"""수집·색인 파이프라인 — 설계안 §19.

문서 하나의 처리 이력을 A의 `DocumentManifestEntry`로 기록한다
(LISTED → TEXT_AVAILABLE 또는 TEXT_EMPTY → RAG_INDEXED). 상태를 남기는 이유는
"검색 결과가 비어 있다"와 "애초에 수집이 안 됐다"를 구분하기 위해서다 — 구분이 없으면
MCP Tool이 `empty`와 `source_missing` 중 무엇을 반환해야 할지 알 수 없다.

이 모듈은 네트워크를 직접 치지 않는다. 수집 자체(HTTP fetch)는 별도 스크립트가 하고
원문을 `data/rag/documents/`에 파일로 남기며, 여기서는 그 파일을 읽어 정규화·Chunking·
Embedding까지 진행한다. 원본과 정제본을 분리해 보존하라는 지시서 §3 요구를 파일 단위로
지킨 것이고, 덕분에 재색인이 네트워크 없이 재현된다.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from src.rag.chunk import Chunk, chunk_document, deduplicate
from src.rag.embed import Embedder, VectorIndex, default_embedder
from src.rag.normalize import has_usable_text, normalize_document_text
from src.schemas.retrieval import DocumentManifestEntry, DocumentManifestStatus


def generate_document_id(source_url: str) -> str:
    """source_url 하나가 문서 하나다. 같은 URL을 다시 수집해도 같은 id를 받아야
    Manifest의 이력이 이어진다 — department_id에 조사년도를 넣지 않는 것과 같은 이유다."""

    digest = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:20]
    return f"doc_{digest}"


class DocumentSource(BaseModel):
    """수집 대상 문서 하나의 출처 기록. `data/rag/sources.jsonl`의 한 행."""

    source_url: str
    document_type: str
    as_of_date: date
    related_department_id: str | None = None
    text_path: str | None = None  # data/rag/documents/ 아래 상대 경로
    title: str = ""

    @property
    def document_id(self) -> str:
        return generate_document_id(self.source_url)


class IndexedChunk(BaseModel):
    """색인이 끝난 Chunk 하나 + 검색 결과에 그대로 실어야 하는 출처 메타데이터.

    출처를 Chunk에 붙여 두는 이유는 검색 결과를 만들 때 문서 테이블을 다시 join하지 않아도
    `RetrievedDocument`의 source_url·as_of_date를 채울 수 있게 하기 위해서다. 출처가 빠진
    검색 결과를 반환할 여지를 구조적으로 없앤다."""

    chunk: Chunk
    source_url: str
    document_type: str
    as_of_date: date
    related_department_id: str | None = None
    title: str = ""


class DocumentManifest:
    """`DocumentManifestEntry` 모음. JSONL로 읽고 쓴다."""

    def __init__(self, entries: list[DocumentManifestEntry] | None = None) -> None:
        self._entries: dict[str, DocumentManifestEntry] = {
            e.document_id: e for e in (entries or [])
        }

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self):
        return iter(self._entries.values())

    def get(self, document_id: str) -> DocumentManifestEntry | None:
        return self._entries.get(document_id)

    def entries(self) -> list[DocumentManifestEntry]:
        return list(self._entries.values())

    def by_status(self, status: DocumentManifestStatus) -> list[DocumentManifestEntry]:
        return [e for e in self._entries.values() if e.status is status]

    def upsert(self, entry: DocumentManifestEntry) -> DocumentManifestEntry:
        self._entries[entry.document_id] = entry
        return entry

    def mark_listed(self, source: DocumentSource) -> DocumentManifestEntry:
        return self.upsert(
            DocumentManifestEntry(
                document_id=source.document_id,
                source_url=source.source_url,
                document_type=source.document_type,
                status=DocumentManifestStatus.LISTED,
                related_department_id=source.related_department_id,
            )
        )

    def mark_text_available(
        self, source: DocumentSource, fetched_at: datetime | None = None
    ) -> DocumentManifestEntry:
        entry = self.mark_listed(source).model_copy(
            update={
                "status": DocumentManifestStatus.TEXT_AVAILABLE,
                "as_of_date": source.as_of_date,
                "fetched_at": fetched_at or datetime.now(timezone.utc),
                "error_message": None,
            }
        )
        return self.upsert(entry)

    def mark_text_empty(
        self, source: DocumentSource, reason: str, fetched_at: datetime | None = None
    ) -> DocumentManifestEntry:
        entry = self.mark_listed(source).model_copy(
            update={
                "status": DocumentManifestStatus.TEXT_EMPTY,
                "fetched_at": fetched_at or datetime.now(timezone.utc),
                "error_message": reason,
            }
        )
        return self.upsert(entry)

    def mark_indexed(
        self, source: DocumentSource, indexed_at: datetime | None = None
    ) -> DocumentManifestEntry:
        current = self.get(source.document_id)
        if current is None or current.status is not DocumentManifestStatus.TEXT_AVAILABLE:
            raise ValueError(
                f"{source.document_id}: TEXT_AVAILABLE을 거치지 않고 RAG_INDEXED로 갈 수 없다 "
                f"(현재 {current.status.value if current else 'None'})"
            )
        entry = current.model_copy(
            update={
                "status": DocumentManifestStatus.RAG_INDEXED,
                "indexed_at": indexed_at or datetime.now(timezone.utc),
            }
        )
        return self.upsert(entry)

    # --- 파일 입출력 ---

    @classmethod
    def load(cls, path: Path) -> "DocumentManifest":
        if not path.exists():
            return cls()
        entries = [
            DocumentManifestEntry.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return cls(entries)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(self._entries.values(), key=lambda e: e.document_id)
        path.write_text(
            "".join(e.model_dump_json() + "\n" for e in ordered), encoding="utf-8"
        )


def load_sources(path: Path) -> list[DocumentSource]:
    return [
        DocumentSource.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def read_source_text(source: DocumentSource, base_dir: Path) -> str:
    """수집해 둔 원문 파일을 읽는다. 파일이 없으면 빈 문자열 — 예외를 던지지 않는 이유는
    한 문서를 못 읽었다고 전체 색인을 멈추면 안 되기 때문이다. 호출자가 TEXT_EMPTY로 기록한다."""

    if not source.text_path:
        return ""
    path = base_dir / source.text_path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


class IngestResult(BaseModel):
    indexed_chunks: list[IndexedChunk]
    manifest_entries: list[DocumentManifestEntry]

    @property
    def indexed_document_count(self) -> int:
        return sum(
            1 for e in self.manifest_entries if e.status is DocumentManifestStatus.RAG_INDEXED
        )

    @property
    def empty_document_count(self) -> int:
        return sum(
            1 for e in self.manifest_entries if e.status is DocumentManifestStatus.TEXT_EMPTY
        )


def ingest(
    sources: list[DocumentSource],
    base_dir: Path,
    manifest: DocumentManifest | None = None,
    embedder: Embedder | None = None,
    vector_index: VectorIndex | None = None,
    now: datetime | None = None,
) -> tuple[IngestResult, VectorIndex]:
    """원문 파일 → 정규화 → Chunking → 중복 제거 → Embedding → 색인.

    embedder를 주지 않으면 `default_embedder()`가 정해진다(Key 없으면 오프라인 구현).
    vector_index를 주지 않으면 새로 만든다.
    """

    # `or`로 기본값을 주면 안 된다 — DocumentManifest/VectorIndex 둘 다 __len__을 정의해
    # 비어 있을 때 falsy가 되고, 호출자가 넘긴 빈 객체가 조용히 버려진다.
    if manifest is None:
        manifest = DocumentManifest()
    embedder = embedder or default_embedder()
    if vector_index is None:
        vector_index = VectorIndex(embedder.dimension)
    stamp = now or datetime.now(timezone.utc)

    indexed: list[IndexedChunk] = []
    for source in sources:
        manifest.mark_listed(source)
        raw = read_source_text(source, base_dir)
        if not has_usable_text(raw):
            manifest.mark_text_empty(
                source,
                reason="본문 추출 결과가 비었거나 쓸 수 있는 분량이 아니다",
                fetched_at=stamp,
            )
            continue

        manifest.mark_text_available(source, fetched_at=stamp)
        text = normalize_document_text(raw)
        chunks: list[Chunk] = deduplicate(chunk_document(source.document_id, text))
        if not chunks:
            manifest.mark_text_empty(source, reason="Chunk가 하나도 생성되지 않았다", fetched_at=stamp)
            continue

        vectors = embedder.embed([c.text for c in chunks])
        for chunk, vector in zip(chunks, vectors):
            vector_index.upsert(chunk.chunk_id, vector)
            indexed.append(
                IndexedChunk(
                    chunk=chunk,
                    source_url=source.source_url,
                    document_type=source.document_type,
                    as_of_date=source.as_of_date,
                    related_department_id=source.related_department_id,
                    title=source.title,
                )
            )
        manifest.mark_indexed(source, indexed_at=stamp)

    return (
        IngestResult(indexed_chunks=indexed, manifest_entries=manifest.entries()),
        vector_index,
    )
