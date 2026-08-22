"""임계값 근거 측정 (작업자 C 소유).

코드에 박혀 있는 숫자 세 개는 감으로 정한 값이 아니라 **실제 데이터에서 재서** 정한
값이다. 이 스크립트가 그 측정을 다시 돌려, 지금 데이터에서도 그 숫자가 여전히 맞는지
확인한다. 근거를 문서에만 적어 두면 데이터가 바뀐 뒤에도 옛날 주장이 그대로 남는다.

측정 대상:

1. `course_document_parser._FUZZY_THRESHOLD` (0.82)
   — 붙어야 하는 표기와 붙으면 안 되는 표기의 유사도가 어디서 갈리는가
2. `retrieve.DEFAULT_MIN_QUERY_COVERAGE` (0.3)
   — 근거 있는 질의와 근거 없는 질의의 본문 적중률이 어디서 갈리는가
3. `chunk.DEFAULT_CHUNK_SIZE` (700)
   — 실제 코퍼스에서 Chunk 길이 분포와 문서당 분할 수

실행:
    python scripts/career_measure_thresholds.py
"""

from __future__ import annotations

import difflib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agents.course.course_document_parser import (  # noqa: E402
    _FUZZY_THRESHOLD,
    normalize_subject_name,
)
from src.rag.chunk import DEFAULT_CHUNK_SIZE  # noqa: E402
from src.rag.embed import HashingEmbedder  # noqa: E402
from src.rag.ingest import ingest, load_sources  # noqa: E402
from src.rag.retrieve import DEFAULT_MIN_QUERY_COVERAGE, query_coverage  # noqa: E402

DATA_DIR = ROOT / "data"

# 학교 편제표에서 실제로 나오는 표기 변형. 같은 과목으로 붙어야 한다.
SHOULD_MATCH = [
    "미적분 II", "인공지능기초", "확률과통계", "주제탐구독서", "화법과언어",
    "소프트웨어와생활", "창의공학설계", "미술창작", "인간과심리", "데이터과학",
]

# 표기는 비슷하지만 **다른 과목**이다. 붙으면 학생 편제표가 틀리게 채워진다.
SHOULD_NOT_MATCH = [
    "체육", "진로와 직업", "공통영어1", "한국사1", "미술 감상과 비평",
    "음악 연주와 창작", "기술가정", "심리학 실험", "정보처리기능사",
]

# 코퍼스에 근거가 있는 질의 / 없는 질의
GROUNDED_QUERIES = [
    "컴퓨터공학부 졸업요건",
    "미디어커뮤니케이션 교육과정 수용자 조사",
    "고교에서 준비하면 좋은 과목 물리학 미적분",
    "교육학과 교육실습",
]
UNGROUNDED_QUERIES = [
    "존재하지 않는 학과의 장학금 규정",
    "기숙사 신청 마감일과 보증금 환불 절차",
]


_VERBOSE = True


def _p(*args: object) -> None:
    """측정 로그. 테스트가 이 모듈을 불러 쓸 때는 출력이 테스트 결과를 가리므로 끈다."""

    if _VERBOSE:
        print(*args)


def _alias_keys() -> tuple[list[str], dict[str, str]]:
    rows = [
        json.loads(line)
        for line in (DATA_DIR / "master" / "subject_aliases.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    canonical = {normalize_subject_name(r["alias"]): r["canonical_subject_name"] for r in rows}
    return sorted(canonical), canonical


def _best_ratio(query: str, keys: list[str]) -> tuple[str, float]:
    key = normalize_subject_name(query)
    matches = difflib.get_close_matches(key, keys, n=1, cutoff=0.0)
    if not matches:
        return "", 0.0
    return matches[0], difflib.SequenceMatcher(None, key, matches[0]).ratio()


def measure_fuzzy_threshold() -> dict:
    keys, canonical = _alias_keys()
    positives = [(q, *_best_ratio(q, keys)) for q in SHOULD_MATCH]
    negatives = [(q, *_best_ratio(q, keys)) for q in SHOULD_NOT_MATCH]

    lowest_positive = min(r for _, _, r in positives)
    highest_negative = max(r for _, _, r in negatives)

    _p("\n[1] 과목명 Alias 유사도 문턱")
    _p("  붙어야 하는 표기")
    for query, key, ratio in positives:
        _p(f"    {ratio:.3f}  {query} → {canonical.get(key, key)}")
    _p("  붙으면 안 되는 표기")
    for query, key, ratio in negatives:
        _p(f"    {ratio:.3f}  {query} → {canonical.get(key, key)}")
    _p(f"  참 후보 최저 {lowest_positive:.3f} / 거짓 후보 최고 {highest_negative:.3f}")
    _p(f"  현재 문턱 {_FUZZY_THRESHOLD} — 거짓 후보 최고값보다 위, 참 후보 최저값보다 아래여야 한다")

    ok = highest_negative < _FUZZY_THRESHOLD <= lowest_positive
    _p(f"  판정: {'OK' if ok else '재조정 필요'}")
    return {
        "threshold": _FUZZY_THRESHOLD,
        "lowest_true_positive": lowest_positive,
        "highest_false_positive": highest_negative,
        "separated": ok,
    }


def measure_query_coverage() -> dict:
    result, _ = ingest(
        load_sources(DATA_DIR / "rag" / "sources.jsonl"),
        base_dir=DATA_DIR / "rag",
        embedder=HashingEmbedder(64),  # 문턱 측정에는 벡터가 필요 없다
    )
    haystacks = [
        f"{c.title} {c.chunk.section_title or ''} {c.chunk.text}" for c in result.indexed_chunks
    ]

    grounded = {q: max(query_coverage(q, h) for h in haystacks) for q in GROUNDED_QUERIES}
    ungrounded = {q: max(query_coverage(q, h) for h in haystacks) for q in UNGROUNDED_QUERIES}

    _p("\n[2] 검색 바닥선 — 질의어 본문 적중률")
    _p("  근거 있는 질의 (최고 적중 문서)")
    for query, value in grounded.items():
        _p(f"    {value:.2f}  {query}")
    _p("  근거 없는 질의 (최고 적중 문서)")
    for query, value in ungrounded.items():
        _p(f"    {value:.2f}  {query}")

    lowest_grounded = min(grounded.values())
    highest_ungrounded = max(ungrounded.values())
    _p(f"  근거 있는 질의 최저 {lowest_grounded:.2f} / 근거 없는 질의 최고 {highest_ungrounded:.2f}")
    _p(f"  현재 바닥선 {DEFAULT_MIN_QUERY_COVERAGE}")

    ok = highest_ungrounded < DEFAULT_MIN_QUERY_COVERAGE <= lowest_grounded
    _p(f"  판정: {'OK' if ok else '재조정 필요'}")
    return {
        "threshold": DEFAULT_MIN_QUERY_COVERAGE,
        "lowest_grounded": lowest_grounded,
        "highest_ungrounded": highest_ungrounded,
        "separated": ok,
    }


def measure_chunk_size() -> dict:
    result, _ = ingest(
        load_sources(DATA_DIR / "rag" / "sources.jsonl"),
        base_dir=DATA_DIR / "rag",
        embedder=HashingEmbedder(64),
    )
    lengths = sorted(len(c.chunk.text) for c in result.indexed_chunks)
    per_document = Counter(c.chunk.document_id for c in result.indexed_chunks)
    titled = sum(1 for c in result.indexed_chunks if c.chunk.section_title)

    _p("\n[3] Chunk 크기")
    _p(f"  Chunk {len(lengths)}개, 길이 {lengths}")
    _p(f"  문서당 Chunk 수 {sorted(per_document.values(), reverse=True)}")
    _p(f"  소제목이 붙은 Chunk {titled}/{len(lengths)}")
    _p(f"  현재 chunk_size {DEFAULT_CHUNK_SIZE} — 모든 Chunk가 이 값 이하여야 한다")

    ok = all(length <= DEFAULT_CHUNK_SIZE for length in lengths)
    _p(f"  판정: {'OK' if ok else '초과 Chunk 있음'}")
    return {
        "chunk_size": DEFAULT_CHUNK_SIZE,
        "lengths": lengths,
        "max_length": max(lengths) if lengths else 0,
        "within_limit": ok,
    }


def run(verbose: bool = False) -> dict:
    """세 측정을 한 번에 돌린다. 기본은 조용히 — 테스트에서 그대로 쓰기 위해서다."""

    global _VERBOSE
    _VERBOSE = verbose
    return {
        "fuzzy_threshold": measure_fuzzy_threshold(),
        "query_coverage": measure_query_coverage(),
        "chunk_size": measure_chunk_size(),
    }


if __name__ == "__main__":
    measurements = run(verbose=True)
    output = DATA_DIR / "audit" / "threshold_measurements.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(measurements, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _p(f"\n측정 결과 저장 — {output.relative_to(ROOT)}")

    failed = [name for name, m in measurements.items() if not (m.get("separated") or m.get("within_limit"))]
    if failed:
        raise SystemExit(f"문턱 재조정 필요: {failed}")
