"""RAG 수집 대상 목록과 원문 파일 생성 (작업자 C 소유) — 설계안 §19.

## 지금 코퍼스에 진짜 대학 홈페이지 문서가 없는 이유

학과 소개·교육과정·졸업요건 페이지를 수집하려면 대학별 홈페이지를 실제로 가져와야 하는데,
그 수집은 아직 승인되지 않았고 이 저장소에는 저장된 원문이 없다. **없는 문서를 지어내서
공식 URL을 달면** 검색 결과가 근거 있는 것처럼 보이게 되고, 그건 §27 "검색 근거가 없는
내용을 새로 생성하지 않는다"를 정면으로 어긴다.

그래서 두 종류를 명확히 갈라 둔다.

1. **진짜 문서** — `work/education2024.txt` (교육부·KEDI 「2024년 간추린 교육통계」에서
   추출한 원문. 저장소에 원본 PDF와 함께 이미 있다). `source_url`은 실제 출처를 쓴다.
2. **샘플 문서** — 파이프라인(정규화·Chunk·검색·출처 표시)이 도는지 확인하기 위한 것.
   `source_url`을 `sample://`로 시작하게 두고 `document_type`에 "샘플(비공식)"을 붙인다.
   이렇게 하면 어느 계층에서도 이걸 공식 출처로 착각할 수 없고, 실제 수집이 시작되면
   `sample://` 항목만 지우면 된다.

실행:
    python scripts/career_build_rag_corpus.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RAG_DIR = ROOT / "data" / "rag"
DOCS_DIR = RAG_DIR / "documents"
AS_OF = "2026-08-21"

REAL_SOURCE = {
    "source_url": "https://kess.kedi.re.kr/publ/view?survSeq=2024&publSeq=2&menuSeq=0&itemCode=02",
    "document_type": "교육통계",
    "as_of_date": "2024-04-01",
    "title": "2024년 간추린 교육통계",
    "text_path": "documents/kedi_education_statistics_2024.txt",
    "related_department_id": None,
}

# (대학명, 학과명, 문서 유형, 제목, 본문)
SAMPLES: list[tuple[str, str, str, str, str]] = [
    (
        "서울대학교",
        "컴퓨터공학부",
        "학과 소개",
        "컴퓨터공학부 학과 소개 (샘플)",
        """1. 학부 소개
컴퓨터공학부는 계산의 원리와 소프트웨어 시스템의 설계를 다룬다. 자료구조와 알고리즘을
기반으로 문제를 정의하고, 운영체제·네트워크·데이터베이스 같은 시스템 계층을 이해한 뒤,
인공지능과 데이터 분야로 확장한다.

2. 교육과정
1학년은 프로그래밍 기초와 이산수학, 2학년은 자료구조·알고리즘·컴퓨터구조를 듣는다.
3학년부터 운영체제, 데이터베이스, 소프트웨어공학, 기계학습 중에서 진로에 맞춰 고른다.
4학년에는 팀 단위 졸업 프로젝트를 수행하며 설계-구현-개선 주기를 직접 돈다.

3. 졸업요건
전공 필수 학점을 이수하고 졸업 프로젝트를 통과해야 한다. 영어 요건이 별도로 있다.

4. 고교에서 준비하면 좋은 과목
정보, 인공지능 기초, 공통수학1, 미적분Ⅱ를 이수하면 1학년 전공 기초를 따라가기 쉽다.""",
    ),
    (
        "중앙대학교",
        "미디어커뮤니케이션학부",
        "교육과정",
        "미디어커뮤니케이션학부 교육과정 (샘플)",
        """1. 교육 목표
매체를 통한 정보 전달과 수용 과정을 분석하고, 콘텐츠를 기획·제작할 수 있는 역량을 기른다.

2. 교육과정
저널리즘, 미디어 효과 이론, 영상 콘텐츠 기획, 광고·홍보, 미디어 데이터 분석으로 구성된다.
3학년에는 수용자 조사 방법론을 배우고, 실제 콘텐츠를 만들어 반응을 측정하는 실습을 한다.

3. 졸업요건
전공 학점 이수와 함께 졸업 작품 또는 졸업 논문 중 하나를 제출한다.

4. 고교에서 준비하면 좋은 과목
화법과 언어, 매체 의사소통, 주제 탐구 독서, 사회문제 탐구가 도움이 된다.""",
    ),
    (
        "중앙대학교",
        "디자인학부",
        "학과 소개",
        "디자인학부 학과 소개 (샘플)",
        """1. 학부 소개
사용자와 상황을 관찰해 시각적·기능적 결과물을 만드는 과정을 배운다. 시각디자인, 산업디자인,
공간디자인 전공으로 나뉜다.

2. 교육과정
1~2학년은 조형 기초, 색채, 타이포그래피 등 표현 기초를 공통으로 듣는다. 3학년부터 전공을
정해 사용자 조사, 프로토타이핑, 브랜드 시스템을 다룬다.

3. 졸업요건
졸업 전시를 통해 포트폴리오를 공개한다.

4. 고교에서 준비하면 좋은 과목
미술 창작, 매체 의사소통, 창의 공학 설계가 연결된다.""",
    ),
    (
        "부산대학교",
        "교육학과",
        "졸업요건",
        "교육학과 졸업요건 (샘플)",
        """1. 졸업요건
전공 필수와 선택 학점을 채우고 교육실습을 이수해야 한다. 교직 과정을 함께 이수하면
중등학교 정교사 2급 자격 취득을 준비할 수 있다.

2. 교육과정
교육과정론, 교육심리, 교육사회학, 교육행정, 수업 설계와 평가를 다룬다.

3. 고교에서 준비하면 좋은 과목
인간과 심리, 사회문제 탐구, 화법과 언어가 도움이 된다.""",
    ),
    (
        "서울대학교",
        "기계공학부",
        "교육과정",
        "기계공학부 교육과정 (샘플)",
        """1. 교육과정
고체역학, 열역학, 유체역학, 동역학을 4대 역학으로 배운 뒤 설계·제작 실습으로 이어진다.
3학년에는 CAD와 제어 실습이, 4학년에는 캡스톤 설계가 있다.

2. 졸업요건
캡스톤 설계 이수와 전공 학점 요건을 충족해야 한다.

3. 고교에서 준비하면 좋은 과목
물리학, 미적분Ⅱ, 창의 공학 설계가 직접 연결된다.""",
    ),
]


def _department_index() -> dict[tuple[str, str], str]:
    path = ROOT / "data" / "master" / "departments.jsonl"
    index: dict[tuple[str, str], str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            index[(row["university_name"], row["department_name"])] = row["department_id"]
    return index


def build() -> list[dict]:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    index = _department_index()
    sources: list[dict] = []

    real_text = ROOT / "work" / "education2024.txt"
    if real_text.exists():
        shutil.copyfile(real_text, DOCS_DIR / "kedi_education_statistics_2024.txt")
        sources.append(dict(REAL_SOURCE))

    for university, department, document_type, title, body in SAMPLES:
        department_id = index.get((university, department))
        if department_id is None:
            raise SystemExit(f"master에 없는 학과: {university} {department}")
        slug = f"sample_{department_id}"
        file_name = f"{slug}.txt"
        header = f"※ 파이프라인 검증용 샘플 문서입니다. 공식 자료가 아닙니다. ({university} {department})\n\n"
        (DOCS_DIR / file_name).write_text(header + body + "\n", encoding="utf-8")
        sources.append(
            {
                "source_url": f"sample://{university}/{department}/{document_type}",
                "document_type": f"샘플(비공식) {document_type}",
                "as_of_date": AS_OF,
                "related_department_id": department_id,
                "text_path": f"documents/{file_name}",
                "title": title,
            }
        )

    (RAG_DIR / "sources.jsonl").write_text(
        "".join(json.dumps(s, ensure_ascii=False) + "\n" for s in sources), encoding="utf-8"
    )
    return sources


if __name__ == "__main__":
    from src.rag.ingest import DocumentManifest, load_sources  # noqa: E402
    from src.rag.retrieve import build_retriever  # noqa: E402

    rows = build()
    print(f"수집 대상 {len(rows)}건 — data/rag/sources.jsonl")

    sources = load_sources(RAG_DIR / "sources.jsonl")
    retriever = build_retriever(sources, base_dir=RAG_DIR)
    print(f"색인 Chunk {len(retriever)}개")

    # Manifest를 파일로 남긴다 — 어느 문서가 어느 단계에서 멈췄는지 A가 바로 본다.
    from src.rag.ingest import ingest  # noqa: E402

    manifest = DocumentManifest()
    ingest(sources, base_dir=RAG_DIR, manifest=manifest)
    manifest.save(RAG_DIR / "manifest.jsonl")
    for entry in sorted(manifest.entries(), key=lambda e: e.document_id):
        print(f"  {entry.status.value:15s} {entry.source_url}")
