"""수집 원문 정규화 — 설계안 §19 "공식 홈페이지 → 수집 및 출처 기록 → 정규화" 단계.

여기서 하는 일은 표기 정리뿐이다. 내용을 요약하거나 바꾸지 않는다 — RAG 결과는 원문
근거로 쓰이므로 정규화 단계가 문장을 만들어내면 §27 "검색 근거가 없는 내용을 새로 생성하지
않는다"가 깨진다.
"""

from __future__ import annotations

import re
import unicodedata

# PDF에서 자주 섞여 들어오는 것들
_SOFT_HYPHEN = "­"  # 표시되지 않는 하이픈
_ZERO_WIDTH = re.compile("[\u200b-\u200f\ufeff]")  # zero-width, BOM
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_MULTI_SPACE = re.compile("[ \t\u3000]+")  # 　 = 전각 공백
_MULTI_NEWLINE = re.compile(r"\n{3,}")
# "- 3 -", "3 / 12", "페이지 3" 형태의 쪽 번호 줄
_PAGE_NUMBER_LINE = re.compile(r"^\s*(?:-\s*\d+\s*-|\d+\s*/\s*\d+|(?:page|페이지)\s*\d+)\s*$", re.I)
# 줄 끝에서 단어가 잘린 흔적 (영문 하이픈 줄바꿈)
_HYPHEN_LINEBREAK = re.compile(r"([A-Za-z])-\n([A-Za-z])")


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _ZERO_WIDTH.sub("", text)
    text = _CONTROL.sub("", text)
    text = text.replace(_SOFT_HYPHEN, "")
    text = _MULTI_SPACE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = _MULTI_NEWLINE.sub("\n\n", text)
    return text.strip()


def drop_page_furniture(text: str, repeated_line_threshold: int = 3) -> str:
    """쪽 번호와 모든 쪽에 반복되는 머리말·꼬리말을 제거한다.

    같은 줄이 문서 전체에서 `repeated_line_threshold`번 이상 나오고 그 줄이 짧으면
    (본문 문장이라기엔 너무 짧으면) 머리말·꼬리말로 본다. 긴 문장이 여러 번 반복되는 건
    실제 본문일 수 있어 건드리지 않는다.
    """

    lines = text.split("\n")
    counts: dict[str, int] = {}
    for line in lines:
        if line:
            counts[line] = counts.get(line, 0) + 1

    kept: list[str] = []
    for line in lines:
        if _PAGE_NUMBER_LINE.match(line):
            continue
        if line and counts[line] >= repeated_line_threshold and len(line) <= 30:
            continue
        kept.append(line)
    return _MULTI_NEWLINE.sub("\n\n", "\n".join(kept)).strip()


def normalize_document_text(text: str) -> str:
    """수집 직후 원문에 적용하는 표준 정규화."""

    text = unicodedata.normalize("NFKC", text)
    text = _HYPHEN_LINEBREAK.sub(r"\1\2", text)
    text = normalize_whitespace(text)
    return drop_page_furniture(text)


def has_usable_text(text: str, minimum_characters: int = 40) -> bool:
    """`DocumentManifestStatus.TEXT_AVAILABLE` / `TEXT_EMPTY`를 가르는 기준.

    "가져오긴 했는데 쓸 수 있는 본문이 없다"를 판정한다 — 추출 실패한 PDF가 공백과 쪽
    번호만 남기는 경우가 흔해서, 길이가 아니라 정규화 후 길이로 본다.
    """

    return len(normalize_document_text(text)) >= minimum_characters
