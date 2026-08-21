"""학교 교육과정 문서 Parser (작업자 C 소유) — 설계안 §20, C 지시서 §3.

입력은 **PDF(`application/pdf`)와 Excel(`.xlsx`, `.xls`)만** 받는다. 출력은 A가 확정한
`ParsedSubjectCandidate`다.

여기서 하지 않는 것 (지시서 §3, §7):
- Agent 판단, 최종 과목 추천 — 추출과 정규화까지만 한다.
- 확신이 낮은 값을 임의로 확정 — `confidence="low"` 또는 `"unmatched"`로 두고
  `requires_user_confirmation=True`를 붙여 B의 확인 UI로 넘긴다.

## 외부 라이브러리를 쓰지 않는 이유

`requirements-lock.txt`에 PDF·Excel 파서가 없다(의존성 추가는 A 결정). 그래서

- `.xlsx`는 표준 라이브러리만으로 읽는다 — xlsx는 실제로는 XML이 든 zip이라
  `zipfile`+`xml.etree`로 셀 문자열을 꺼낼 수 있다.
- PDF는 `pypdf`가 설치돼 있으면 그걸 쓰고, 없으면 내장 최소 추출기(FlateDecode 스트림의
  텍스트 연산자만 읽는다)로 떨어진다. 내장 추출기는 이미지 스캔 PDF나 폰트 인코딩이
  특수한 PDF에서 본문을 못 뽑는다 — 그럴 때는 빈 결과가 아니라 `ParseError`를 남긴다.
  같은 이름의 `.txt` 사이드카 파일이 옆에 있으면(이미 추출해 둔 원문) 그걸 우선 쓴다.
- `.xls`(97-2003 이진 형식)는 표준 라이브러리로 읽을 수 없다. 입력으로 받되
  `ParseError`를 명시적으로 남긴다 — 조용히 빈 결과를 돌려주면 "개설과목이 없는 학교"로
  오해된다.
"""

from __future__ import annotations

import difflib
import json
import re
import unicodedata
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from pydantic import BaseModel

from src.schemas.course import ParsedSubjectCandidate

SUPPORTED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "application/vnd.ms-excel",  # .xls
}
SUPPORTED_SUFFIXES = {".pdf", ".xlsx", ".xls"}

_XLSX_NAMESPACE = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_FUZZY_THRESHOLD = 0.82

# 편제표에서 과목명 칸이 아닌 게 확실한 값들. 이걸 후보로 올리면 확인 UI가 쓰레기로 찬다.
_NON_SUBJECT_TOKENS = {
    "교과", "교과군", "과목", "과목명", "구분", "학년", "학기", "단위", "이수단위",
    "이수", "계", "합계", "소계", "비고", "필수", "선택", "공통", "일반선택",
    "진로선택", "융합선택", "전문교과", "학점", "총계", "학년도", "학교",
    "1학년", "2학년", "3학년", "1학기", "2학기",
}
_NUMBER_ONLY = re.compile(r"^[\d\s./%()-]+$")
# 로마숫자 접미 → 아라비아 숫자. **긴 것부터** 대조해야 한다 — "II"를 "I"로 먼저 잘라내면
# "미적분II"가 "미적분I1"이 된다. NFKC 정규화가 "Ⅱ"을 "II"로 바꾸므로 ASCII 표기만 있으면 된다.
_ROMAN_SUFFIXES: tuple[tuple[str, str], ...] = (("IV", "4"), ("III", "3"), ("II", "2"), ("I", "1"))


class ParseError(BaseModel):
    """읽지 못한 원인. 빈 결과와 실패를 구분하기 위해 결과와 함께 돌려준다."""

    stage: str  # "input" | "extract" | "normalize"
    message: str
    detail: str = ""


class CourseDocumentParseResult(BaseModel):
    """지시서 §3 "파싱 결과, 오류, 확인 필요 항목을 반환한다"의 반환 형태.

    `candidates`는 A가 확정한 `ParsedSubjectCandidate` 그대로다. 이 래퍼는 오류와
    확인 대상을 함께 담기 위한 것이고, `CourseProfile.unresolved_candidates`에는
    `requires_confirmation()` 결과를 그대로 넣으면 된다.
    """

    source_name: str
    candidates: list[ParsedSubjectCandidate] = []
    errors: list[ParseError] = []

    @property
    def succeeded(self) -> bool:
        return not any(e.stage in {"input", "extract"} for e in self.errors)

    def matched(self) -> list[ParsedSubjectCandidate]:
        return [c for c in self.candidates if c.matched_subject_id is not None]

    def requires_confirmation(self) -> list[ParsedSubjectCandidate]:
        return [c for c in self.candidates if c.requires_user_confirmation]


# --- Alias 정규화 ---


def normalize_subject_name(raw: str) -> str:
    """과목명 표기 정규화. 학교마다 "미적분Ⅱ"/"미적분2"/"미적분 II"로 적는다."""

    text = unicodedata.normalize("NFKC", raw).strip()
    text = re.sub(r"\s+", "", text)
    for roman, arabic in _ROMAN_SUFFIXES:
        if text.endswith(roman):
            text = text[: -len(roman)] + arabic
            break
    text = text.replace("·", "").replace("・", "").replace("-", "")
    return text


class SubjectAliasIndex:
    """`data/master/subject_aliases.jsonl`을 읽어 표기 → subject_id로 바꾼다."""

    def __init__(self, rows: list[dict]) -> None:
        self._by_key: dict[str, tuple[str, str]] = {}
        for row in rows:
            key = normalize_subject_name(row["alias"])
            self._by_key.setdefault(key, (row["subject_id"], row["canonical_subject_name"]))
        self._keys = list(self._by_key)

    def __len__(self) -> int:
        return len(self._by_key)

    @classmethod
    def load(cls, path: Path) -> "SubjectAliasIndex":
        return cls(
            [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        )

    def exact(self, raw: str) -> tuple[str, str] | None:
        return self._by_key.get(normalize_subject_name(raw))

    def closest(self, raw: str) -> tuple[str, str] | None:
        """표기가 조금 어긋난 경우의 후보 하나. 확정이 아니라 "확인해 달라"는 뜻이다."""

        key = normalize_subject_name(raw)
        if not key:
            return None
        matches = difflib.get_close_matches(key, self._keys, n=1, cutoff=_FUZZY_THRESHOLD)
        return self._by_key[matches[0]] if matches else None


# --- 텍스트 추출 ---


def _looks_like_subject(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 2 or len(stripped) > 30:
        return False
    if stripped in _NON_SUBJECT_TOKENS:
        return False
    if _NUMBER_ONLY.match(stripped):
        return False
    return any(ch.isalpha() for ch in stripped)


def extract_xlsx_cells(path: Path) -> list[str]:
    """xlsx의 모든 시트에서 문자열 셀 값을 순서대로 꺼낸다."""

    values: list[str] = []
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall(f"{_XLSX_NAMESPACE}si"):
                shared.append("".join(t.text or "" for t in item.iter(f"{_XLSX_NAMESPACE}t")))

        sheets = sorted(n for n in archive.namelist() if n.startswith("xl/worksheets/sheet"))
        for sheet in sheets:
            root = ElementTree.fromstring(archive.read(sheet))
            for cell in root.iter(f"{_XLSX_NAMESPACE}c"):
                cell_type = cell.get("t")
                value_node = cell.find(f"{_XLSX_NAMESPACE}v")
                if cell_type == "s" and value_node is not None:
                    index = int(value_node.text or "0")
                    if 0 <= index < len(shared):
                        values.append(shared[index])
                elif cell_type == "inlineStr":
                    values.append(
                        "".join(t.text or "" for t in cell.iter(f"{_XLSX_NAMESPACE}t"))
                    )
                elif value_node is not None and value_node.text:
                    values.append(value_node.text)
    return values


_PDF_TEXT_SHOW = re.compile(rb"\((?P<text>(?:[^()\\]|\\.)*)\)\s*Tj")
_PDF_ARRAY_SHOW = re.compile(rb"\[(?P<array>.*?)\]\s*TJ", re.S)
_PDF_ARRAY_ITEM = re.compile(rb"\((?P<text>(?:[^()\\]|\\.)*)\)")


def _decode_pdf_string(raw: bytes) -> str:
    unescaped = re.sub(rb"\\([nrtbf()\\])", lambda m: m.group(1), raw)
    if unescaped.startswith(b"\xfe\xff"):
        return unescaped.decode("utf-16-be", errors="ignore")
    return unescaped.decode("utf-8", errors="ignore")


def extract_pdf_text(path: Path) -> str:
    """PDF 본문 텍스트. 사이드카 .txt → pypdf → 내장 최소 추출기 순으로 시도한다."""

    sidecar = path.with_suffix(".txt")
    if sidecar.exists():
        return sidecar.read_text(encoding="utf-8", errors="ignore")

    try:  # pypdf가 있으면 그게 정확하다
        from pypdf import PdfReader  # type: ignore

        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    except ImportError:
        pass

    import zlib

    data = path.read_bytes()
    chunks: list[str] = []
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", data, re.S):
        payload = match.group(1)
        try:
            payload = zlib.decompress(payload)
        except zlib.error:
            continue
        for show in _PDF_TEXT_SHOW.finditer(payload):
            chunks.append(_decode_pdf_string(show.group("text")))
        for array in _PDF_ARRAY_SHOW.finditer(payload):
            chunks.append(
                "".join(
                    _decode_pdf_string(item.group("text"))
                    for item in _PDF_ARRAY_ITEM.finditer(array.group("array"))
                )
            )
    return "\n".join(chunks)


def _split_candidates(text: str) -> list[str]:
    parts: list[str] = []
    for line in text.splitlines():
        for token in re.split(r"[,\t|/]| {2,}", line):
            token = token.strip(" .()[]{}")
            if token:
                parts.append(token)
    return parts


# --- 진입점 ---


def parse_course_document(
    path: Path,
    alias_index: SubjectAliasIndex,
    content_type: str | None = None,
) -> CourseDocumentParseResult:
    """PDF·Excel 하나를 읽어 `ParsedSubjectCandidate` 목록으로 바꾼다."""

    result = CourseDocumentParseResult(source_name=path.name)
    suffix = path.suffix.lower()

    if content_type is not None and content_type not in SUPPORTED_CONTENT_TYPES:
        result.errors.append(
            ParseError(
                stage="input",
                message="지원하지 않는 파일 형식",
                detail=f"content_type={content_type!r} — PDF와 Excel만 받는다",
            )
        )
        return result
    if suffix not in SUPPORTED_SUFFIXES:
        result.errors.append(
            ParseError(
                stage="input",
                message="지원하지 않는 파일 확장자",
                detail=f"{suffix!r} — .pdf/.xlsx/.xls만 받는다",
            )
        )
        return result
    if not path.exists():
        result.errors.append(
            ParseError(stage="input", message="파일을 찾을 수 없다", detail=str(path))
        )
        return result

    raw_values: list[str]
    if suffix == ".xlsx":
        try:
            raw_values = extract_xlsx_cells(path)
        except (zipfile.BadZipFile, ElementTree.ParseError) as exc:
            result.errors.append(
                ParseError(stage="extract", message="xlsx를 읽지 못했다", detail=str(exc))
            )
            return result
    elif suffix == ".xls":
        result.errors.append(
            ParseError(
                stage="extract",
                message=".xls(97-2003 이진 형식)는 아직 읽지 못한다",
                detail="xlsx로 다시 저장해 올리거나, xls 파서 도입을 A와 정한다",
            )
        )
        return result
    else:
        text = extract_pdf_text(path)
        if not text.strip():
            result.errors.append(
                ParseError(
                    stage="extract",
                    message="PDF에서 본문 텍스트를 뽑지 못했다",
                    detail="이미지 스캔 PDF이거나 내장 추출기가 다루지 못하는 인코딩이다",
                )
            )
            return result
        raw_values = _split_candidates(text)

    seen: set[str] = set()
    for raw in raw_values:
        if not _looks_like_subject(raw):
            continue
        key = normalize_subject_name(raw)
        if key in seen:
            continue
        seen.add(key)

        exact = alias_index.exact(raw)
        if exact is not None:
            result.candidates.append(
                ParsedSubjectCandidate(
                    raw_text=raw.strip(),
                    matched_subject_id=exact[0],
                    confidence="high",
                    requires_user_confirmation=False,
                )
            )
            continue

        close = alias_index.closest(raw)
        if close is not None:
            result.candidates.append(
                ParsedSubjectCandidate(
                    raw_text=raw.strip(),
                    matched_subject_id=close[0],
                    confidence="low",
                    requires_user_confirmation=True,
                )
            )
            continue

        result.candidates.append(
            ParsedSubjectCandidate(
                raw_text=raw.strip(),
                matched_subject_id=None,
                confidence="unmatched",
                requires_user_confirmation=True,
            )
        )

    return result
