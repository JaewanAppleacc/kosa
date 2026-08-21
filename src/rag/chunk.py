"""Chunking — 설계안 §19 "Chunking" 단계.

지시서는 "LangChain Text Splitter를 사용해 Chunk를 생성한다"고 적었지만,
`requirements-lock.txt`에 langchain이 없다(설치 대상 확정은 A 소유). 그래서 LangChain의
RecursiveCharacterTextSplitter와 **같은 규칙**(문단 → 줄 → 문장 → 공백 → 글자 순으로
가장 큰 경계부터 쪼개고, 겹침을 두는 방식)을 표준 라이브러리로 구현했다. langchain이
의존성에 추가되면 `split_text()` 내부만 교체하면 되고, 이 모듈의 반환 타입은 그대로다.

Chunk 크기는 글자 수 기준이다. 한국어는 토큰:글자 비가 대략 1:1~1:1.5라 글자 수로 잡아도
임베딩 모델 입력 한도를 넘지 않는다.
"""

from __future__ import annotations

import hashlib
import re

from pydantic import BaseModel

DEFAULT_CHUNK_SIZE = 700
DEFAULT_CHUNK_OVERLAP = 120

# 큰 경계부터. 마지막 ""는 "그래도 안 줄면 글자 단위로 자른다"는 뜻이다.
_SEPARATORS: tuple[str, ...] = ("\n\n", "\n", ". ", "다. ", " ", "")

_SECTION_HEADING = re.compile(
    r"^(?:\s*(?:\d+\s*[.)]|[가-힣]\s*[.)]|[■□▶●○·※]|#{1,6})\s*)(?P<title>\S.{0,60})$"
)


class Chunk(BaseModel):
    """색인 단위 하나. document_id는 원본 문서, chunk_id는 그 안에서의 순번까지 포함한다."""

    chunk_id: str
    document_id: str
    ordinal: int
    text: str
    section_title: str | None = None
    char_start: int
    char_end: int

    @property
    def content_hash(self) -> str:
        """같은 본문이 여러 문서에서 반복될 때 중복 색인을 걸러내기 위한 키."""
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()[:16]


def split_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[tuple[int, str]]:
    """(시작 offset, 조각) 목록을 돌려준다. offset은 excerpt 재확인용이라 함께 보존한다."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if not 0 <= chunk_overlap < chunk_size:
        raise ValueError("chunk_overlap must satisfy 0 <= overlap < chunk_size")
    if not text:
        return []

    pieces = _recursive_split(text, 0, chunk_size)
    return _merge_with_overlap(pieces, chunk_size, chunk_overlap)


def _recursive_split(text: str, offset: int, chunk_size: int) -> list[tuple[int, str]]:
    if len(text) <= chunk_size:
        return [(offset, text)] if text.strip() else []

    for separator in _SEPARATORS:
        if separator == "":
            return [
                (offset + i, text[i : i + chunk_size])
                for i in range(0, len(text), chunk_size)
            ]
        if separator not in text:
            continue

        parts: list[tuple[int, str]] = []
        cursor = 0
        for raw in text.split(separator):
            start = offset + cursor
            cursor += len(raw) + len(separator)
            if len(raw) > chunk_size:
                parts.extend(_recursive_split(raw, start, chunk_size))
            elif raw.strip():
                parts.append((start, raw))
        if parts:
            return parts

    return [(offset, text)]


def _merge_with_overlap(
    pieces: list[tuple[int, str]], chunk_size: int, chunk_overlap: int
) -> list[tuple[int, str]]:
    """작은 조각들을 chunk_size 한도 안에서 다시 붙이고, 이웃 Chunk에 꼬리를 겹쳐 둔다."""

    merged: list[tuple[int, str]] = []
    buffer_start: int | None = None
    buffer: list[str] = []
    length = 0

    def flush() -> None:
        nonlocal buffer_start, buffer, length
        if buffer_start is not None and buffer:
            merged.append((buffer_start, " ".join(buffer).strip()))
        buffer_start, buffer, length = None, [], 0

    for start, piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        if buffer and length + len(piece) + 1 > chunk_size:
            tail = " ".join(buffer)[-chunk_overlap:] if chunk_overlap else ""
            flush()
            if tail:
                buffer.append(tail)
                length = len(tail)
                buffer_start = max(start - len(tail), 0)
        if buffer_start is None:
            buffer_start = start
        buffer.append(piece)
        length += len(piece) + 1

    flush()
    return merged


def find_section_title(text: str, upto: int) -> str | None:
    """Chunk 시작 지점 이전에 나온 가장 가까운 소제목을 찾는다.

    번호 목록("1."), 글머리표("■"), 마크다운 헤딩을 소제목으로 본다. 없으면 None —
    억지로 첫 줄을 제목이라고 부르지 않는다.
    """

    title: str | None = None
    cursor = 0
    for line in text[: upto + 1].split("\n"):
        cursor += len(line) + 1
        match = _SECTION_HEADING.match(line)
        if match:
            title = match.group("title").strip()
    return title


def chunk_document(
    document_id: str,
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for ordinal, (start, piece) in enumerate(
        split_text(text, chunk_size, chunk_overlap), start=1
    ):
        chunks.append(
            Chunk(
                chunk_id=f"{document_id}#c{ordinal:03d}",
                document_id=document_id,
                ordinal=ordinal,
                text=piece,
                section_title=find_section_title(text, start),
                char_start=start,
                char_end=start + len(piece),
            )
        )
    return chunks


def deduplicate(chunks: list[Chunk]) -> list[Chunk]:
    """본문이 완전히 같은 Chunk를 하나만 남긴다 — 대학 홈페이지는 같은 안내문을 여러
    페이지에 그대로 싣는 경우가 많아, 걸러내지 않으면 검색 결과 상위가 같은 문장으로 찬다."""

    seen: set[str] = set()
    kept: list[Chunk] = []
    for chunk in chunks:
        key = chunk.content_hash
        if key in seen:
            continue
        seen.add(key)
        kept.append(chunk)
    return kept
