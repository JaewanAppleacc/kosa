"""RAG 코퍼스 확장 — 39개 서비스 Major·학과·과목 공식 근거 (2026-08-25 지시서
"38개 Major Knowledge Subgraph/RAG 재생성" §2). `career_build_rag_corpus.py`(기존
KEDI 통계 1건 + 학과 샘플 5건)는 건드리지 않는다 — 이 스크립트는 그 파일의 출력을
그대로 읽어 뒤에 새 항목만 더한다.

## 무엇을 새 문서로 만드는가, 무엇을 만들지 않는가

**전공(39개)** — `data/master/service_canonical_majors_v2.jsonl`의 label·description·
keywords·aliases·(canonical_major_group_id 또는 source_group_ids)·official_source_urls를
그대로 재서술한 사실 카드다. 이미 검증을 통과한 정본 필드를 다시 늘어놓을 뿐, 한 문장도
새로 짓지 않는다. source_url은 그 Major의 official_source_urls[0]에 `#{major_id}`
fragment를 붙인다 — 여러 Major가 같은 공공데이터 포털 URL을 공유해서(예:
data.go.kr/data/15158963) fragment 없이 그대로 쓰면 서로 다른 Major 문서가 같은
document_id로 충돌한다(`generate_document_id`는 URL 하나에 문서 하나를 전제한다).
포털 자체는 실제 출처이고, fragment는 "그 포털 안에서 이 Major를 가리킨다"는 앵커일
뿐 새 URL을 지어내는 게 아니다.

**학과** — `data/master/departments.jsonl` 1,072행 중 실제 개별 URL(`department_url`)이
있는 19곳만 학과 단위 문서로 만든다(각 학과의 진짜 고유 출처가 있는 경우만). 나머지
1,053곳은 전부 같은 포털(`https://www.academyinfo.go.kr/`)만 인용하고 있어, 그걸
학과 수만큼 복제하면 "출처가 풍부해 보이지만 실제로는 같은 URL을 붙여넣기한" 상태가
된다 — 그건 §27 정신(근거 없는 걸 있어 보이게 만들지 않는다)에 어긋난다. 대신 실제
canonical_major_id가 잡힌 8개 Major마다 "이 Major에 연결된 학과 목록" 문서 1건을
만든다 — 대학명·학과명·department_id·지역을 있는 그대로 나열만 하고(설명 문장을
새로 짓지 않는다), 포털 URL에 `#{major_id}_departments` fragment를 붙여 Major별로
구분한다. hci_ux는 어느 목록에도 없다 — 개별 학과 검토가 아직 없기 때문이다
(rationale_c/08-service-canonical-major-v2.md의 hci_ux 절과 같은 이유).

**과목(18개)** — `data/master/subjects.jsonl`의 label·activity_summary·trait_vector
키·related_major_ids(39개 활성 Catalog에 있는 것만)를 그대로 옮기고, 같은 과목의
표기 변형은 `data/master/subject_aliases.jsonl`에서 가져온다. source_id가 여러 과목
사이에 겹치는 경우(교육부 같은 게시글 URL)가 있어 major와 같은 이유로 `#{subject_id}`
fragment를 붙인다.

## 재생성

    PYTHONPATH=. ./.venv/bin/python scripts/career_build_rag_catalog_corpus.py

`career_build_rag_corpus.py`가 이미 쓴 `data/rag/sources.jsonl`을 줄 단위 그대로
읽어 보존하고(재직렬화하지 않는다 — 기존 6줄이 한 바이트도 안 바뀐다), 새 문서만
뒤에 덧붙인 뒤 전체 목록으로 `data/rag/manifest.jsonl`을 다시 만든다. 입력이 전부
정적 정본이라 몇 번을 다시 돌려도 byte-identical하다.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_build_rag_corpus import CORPUS_SNAPSHOT_AT, DOCS_DIR, RAG_DIR  # noqa: E402
from scripts.career_console import use_utf8_stdout  # noqa: E402
from src.services.service_canonical_major_v2_loader import (  # noqa: E402
    load_service_canonical_majors_v2,
)

CATALOG_DOCS_DIR = DOCS_DIR / "catalog"
DEPARTMENTS_PATH = ROOT / "data" / "master" / "departments.jsonl"
SUBJECTS_PATH = ROOT / "data" / "master" / "subjects.jsonl"
SUBJECT_ALIASES_PATH = ROOT / "data" / "master" / "subject_aliases.jsonl"
GROUPS_PATH = ROOT / "data" / "canonical_major_groups.draft.jsonl"

CATALOG_SNAPSHOT_DATE = date(2026, 8, 25)  # 지시서 접수일. Major/학과/과목 문서 공통 as_of_date.

MAJOR_DOCUMENT_TYPE = "전공 정보(공식 데이터 포털 재게시)"
DEPARTMENT_DOCUMENT_TYPE = "학과 정보(대학알리미 공식 데이터)"
DEPARTMENT_ROSTER_DOCUMENT_TYPE = "학과 목록(대학알리미 공식 데이터)"
SUBJECT_DOCUMENT_TYPE = "과목 정보(교육부 공식 교육과정)"


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_document(slug: str, header: str, body: str) -> str:
    CATALOG_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    file_name = f"{slug}.txt"
    # 필드 값이 빈 문자열인 행(예: activity_summary 없는 과목)이 "라벨: " 형태로 줄
    # 끝에 공백을 남긴다 — git diff --check가 trailing whitespace로 잡아낸다.
    clean_body = "\n".join(line.rstrip() for line in body.split("\n"))
    (CATALOG_DOCS_DIR / file_name).write_text(header + clean_body + "\n", encoding="utf-8")
    return f"documents/catalog/{file_name}"


def build_major_sources() -> list[dict]:
    majors = load_service_canonical_majors_v2()
    groups_by_id = {row["canonical_major_id"]: row for row in _read_jsonl(GROUPS_PATH)}

    sources: list[dict] = []
    for major in sorted(majors, key=lambda m: m.major_id):
        if major.mapping_scope == "FULL_GROUP":
            group = groups_by_id[major.canonical_major_group_id]
            lineage = (
                f"분류 근거: 대학알리미 표준분류 Group '{group['label']}'"
                f"({major.canonical_major_group_id}), mapping_scope=FULL_GROUP"
            )
        else:
            source_labels = ", ".join(
                f"{gid}({groups_by_id[gid]['label']})" for gid in major.source_group_ids
            )
            lineage = (
                "분류 근거: 특정 Group에 전체 소속되지 않는 융합 전공(mapping_scope="
                f"DEPARTMENT_LEVEL_ONLY). 참고 출처 Group: {source_labels}. 개별 학과가 "
                "검토·승인된 경우에만 그 학과가 이 전공에 연결된다 — Group 전체가 자동으로 "
                "연결되지 않는다."
            )

        body_lines = [
            f"{major.label} 전공",
            "",
            major.description,
            "",
            f"별칭: {', '.join(major.aliases) if major.aliases else '(없음)'}",
            f"관련 키워드(공식 표준분류 소계열 이름): {', '.join(major.keywords)}",
            lineage,
            f"Catalog 버전: {major.catalog_version}",
            f"공식 출처: {', '.join(major.official_source_urls)}",
        ]
        header = f"※ 서비스 Major 정본 재게시 문서입니다({major.catalog_version}).\n\n"
        text_path = _write_document(f"major_{major.major_id}", header, "\n".join(body_lines))

        source_url = f"{major.official_source_urls[0]}#{major.major_id}"
        sources.append(
            {
                "source_url": source_url,
                "document_type": MAJOR_DOCUMENT_TYPE,
                "as_of_date": CATALOG_SNAPSHOT_DATE.isoformat(),
                "related_department_id": None,
                "text_path": text_path,
                "title": f"{major.label} 전공 정보",
            }
        )
    return sources


def build_department_sources() -> list[dict]:
    departments = _read_jsonl(DEPARTMENTS_PATH)

    individual_sources: list[dict] = []
    for dept in departments:
        if not dept.get("department_url"):
            continue
        body_lines = [
            f"{dept['university_name']} {dept['department_name']}",
            "",
            f"소속 대학: {dept['college_name']}",
            f"캠퍼스: {dept['campus'] or '(정보 없음)'}",
            f"지역: {dept['region']}",
            f"연결 서비스 Major: {dept['canonical_major_id']}",
            f"학과 상태: {dept['department_status']}",
            f"조사 기준연도: {dept['source_svy_year']}",
            f"department_id: {dept['department_id']}",
            f"공식 출처: {dept['department_url']}",
        ]
        header = "※ 학과 정본 재게시 문서입니다(대학알리미 공식 데이터).\n\n"
        text_path = _write_document(
            f"department_{dept['department_id']}", header, "\n".join(body_lines)
        )
        individual_sources.append(
            {
                "source_url": f"{dept['department_url']}#{dept['department_id']}",
                "document_type": DEPARTMENT_DOCUMENT_TYPE,
                "as_of_date": CATALOG_SNAPSHOT_DATE.isoformat(),
                "related_department_id": dept["department_id"],
                "text_path": text_path,
                "title": f"{dept['university_name']} {dept['department_name']}",
            }
        )

    roster_by_major: dict[str, list[dict]] = {}
    for dept in departments:
        roster_by_major.setdefault(dept["canonical_major_id"], []).append(dept)

    roster_sources: list[dict] = []
    for major_id in sorted(roster_by_major):
        rows = sorted(
            roster_by_major[major_id],
            key=lambda d: (d["university_name"], d["department_name"], d["department_id"]),
        )
        body_lines = [
            f"{major_id} 전공에 연결된 학과 목록 ({len(rows)}개, 대학알리미 2025년 조사 기준)",
            "",
        ]
        for row in rows:
            body_lines.append(
                f"- {row['university_name']} {row['department_name']} "
                f"({row['region']}, {row['department_id']})"
            )
        header = "※ 학과 목록 정본 재게시 문서입니다(대학알리미 공식 데이터).\n\n"
        text_path = _write_document(
            f"department_roster_{major_id}", header, "\n".join(body_lines)
        )
        roster_sources.append(
            {
                "source_url": f"https://www.academyinfo.go.kr/#{major_id}_departments",
                "document_type": DEPARTMENT_ROSTER_DOCUMENT_TYPE,
                "as_of_date": CATALOG_SNAPSHOT_DATE.isoformat(),
                "related_department_id": None,
                "text_path": text_path,
                "title": f"{major_id} 전공 학과 목록",
            }
        )

    return individual_sources + roster_sources


def build_subject_sources() -> list[dict]:
    subjects = _read_jsonl(SUBJECTS_PATH)
    aliases_by_subject: dict[str, list[str]] = {}
    for row in _read_jsonl(SUBJECT_ALIASES_PATH):
        aliases_by_subject.setdefault(row["subject_id"], []).append(row["alias"])

    active_major_ids = {m.major_id for m in load_service_canonical_majors_v2()}

    sources: list[dict] = []
    for subject in sorted(subjects, key=lambda s: s["subject_id"]):
        related = sorted(
            mid for mid in subject["related_major_ids"] if mid in active_major_ids
        )
        aliases = sorted(set(aliases_by_subject.get(subject["subject_id"], [])) - {subject["label"]})
        body_lines = [
            f"{subject['label']} 과목",
            "",
            f"활동 요약: {subject['activity_summary']}",
            f"Trait 연관: {', '.join(sorted(subject['trait_vector'])) or '(없음)'}",
            f"관련 서비스 Major: {', '.join(related) if related else '(없음)'}",
            f"대체 표기(별칭): {', '.join(aliases) if aliases else '(없음)'}",
            f"공식 출처: {subject['source_id']}",
        ]
        header = "※ 과목 정본 재게시 문서입니다(교육부 공식 교육과정).\n\n"
        text_path = _write_document(f"subject_{subject['subject_id']}", header, "\n".join(body_lines))
        sources.append(
            {
                "source_url": f"{subject['source_id']}#{subject['subject_id']}",
                "document_type": SUBJECT_DOCUMENT_TYPE,
                "as_of_date": CATALOG_SNAPSHOT_DATE.isoformat(),
                "related_department_id": None,
                "text_path": text_path,
                "title": f"{subject['label']} 과목 정보",
            }
        )
    return sources


def build() -> list[str]:
    """기존 sources.jsonl 줄 중 `career_build_rag_corpus.py`가 만든 원래 줄만 그대로
    보존하고, 이 스크립트가 만든 줄(text_path가 `documents/catalog/`로 시작)은 다시
    계산해 덧붙인다. 이렇게 걸러내지 않으면 두 번째 실행부터 직전 실행이 남긴 내
    항목을 "기존 줄"로 착각해 그 위에 또 붙여 매번 늘어난다 — 재실행이 반드시
    byte-identical해야 한다는 요구(§ 결정론적 재생성)를 이 필터가 지킨다."""

    sources_path = RAG_DIR / "sources.jsonl"
    existing_lines = [
        line
        for line in sources_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("text_path", "").split("/")[:2] != ["documents", "catalog"]
    ]

    new_sources = build_major_sources() + build_department_sources() + build_subject_sources()
    new_sources.sort(key=lambda s: s["source_url"])
    new_lines = [json.dumps(s, ensure_ascii=False, sort_keys=True) for s in new_sources]

    all_lines = existing_lines + new_lines
    sources_path.write_text("".join(line + "\n" for line in all_lines), encoding="utf-8")
    return all_lines


if __name__ == "__main__":
    use_utf8_stdout()
    from src.rag.ingest import DocumentManifest, load_sources  # noqa: E402
    from src.rag.retrieve import build_retriever  # noqa: E402

    lines = build()
    print(f"data/rag/sources.jsonl 총 {len(lines)}건(기존 포함) — data/rag/sources.jsonl")

    sources = load_sources(RAG_DIR / "sources.jsonl")
    retriever = build_retriever(sources, base_dir=RAG_DIR)
    print(f"색인 Chunk {len(retriever)}개")

    from src.rag.ingest import ingest  # noqa: E402

    manifest = DocumentManifest()
    ingest(sources, base_dir=RAG_DIR, manifest=manifest, now=CORPUS_SNAPSHOT_AT)
    manifest.save(RAG_DIR / "manifest.jsonl")
    print(f"data/rag/manifest.jsonl {len(manifest)}건")
