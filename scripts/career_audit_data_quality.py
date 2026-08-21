"""데이터 품질 자동 검사 (작업자 C 소유) — C 지시서 §3·§5.

"데이터 누락, 중복, 타입, 출처, 기준일을 자동 검사한다"와 "데이터 품질 검사 결과"를
A에게 제출하기 위한 스크립트. 검사 결과는 ERROR / WARN / INFO 세 등급으로 나눈다.

    ERROR  계약 위반. 이대로 A에게 넘기면 안 된다. 스크립트가 종료 코드 1로 끝난다.
    WARN   지금은 통과하지만 확인이 필요한 것.
    INFO   의도적으로 그렇게 둔 것. 기록만 남긴다.

출력:
    data/audit/data_quality.json
    data/audit/data_quality.md

실행:
    python scripts/career_audit_data_quality.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pydantic import ValidationError  # noqa: E402

from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAITS  # noqa: E402
from src.engines.admission_filter import validate_group_field  # noqa: E402
from src.engines.canonical_mapper import normalize_department_name  # noqa: E402
from src.engines.trait_normalizer import normalize_grade  # noqa: E402
from src.ids import generate_department_id, generate_subject_id  # noqa: E402
from src.schemas.course import SubjectProfile  # noqa: E402
from src.schemas.major import AdmissionReference, Department, MajorProfile  # noqa: E402
from src.schemas.retrieval import DocumentManifestEntry, DocumentManifestStatus  # noqa: E402
from src.schemas.review import DraftEntry  # noqa: E402

DATA_DIR = ROOT / "data"
AUDIT_DIR = DATA_DIR / "audit"
KNOWN_TRAIT_IDS = {t.trait_id for t in VERTICAL_SLICE_TRAITS}
ALLOWED_VECTOR_VALUES = {normalize_grade(g) for g in range(4)}
CURRICULUM_CODE = "2022-33"


class Findings:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, severity: str, check: str, message: str, subject: str = "") -> None:
        self.items.append(
            {"severity": severity, "check": check, "subject": subject, "message": message}
        )

    def counts(self) -> Counter[str]:
        return Counter(item["severity"] for item in self.items)

    def has_error(self) -> bool:
        return any(item["severity"] == "ERROR" for item in self.items)


def _rel(path: Path) -> str:
    """보고서에는 저장소 기준 상대 경로만 적는다 — 절대 경로는 사람마다 달라 비교가 안 된다."""

    return str(path.relative_to(ROOT)).replace("\\", "/")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def audit_departments(findings: Findings) -> list[Department]:
    path = DATA_DIR / "master" / "departments.jsonl"
    rows = _read_jsonl(path)
    if not rows:
        findings.add("ERROR", "source_missing", "departments.jsonl이 비었거나 없다", _rel(path))
        return []

    departments: list[Department] = []
    for index, row in enumerate(rows, start=1):
        try:
            departments.append(Department.model_validate(row))
        except ValidationError as exc:
            findings.add("ERROR", "type_invalid", f"{index}행 Schema 위반: {exc.error_count()}건", _rel(path))

    ids = Counter(d.department_id for d in departments)
    for department_id, count in ids.items():
        if count > 1:
            findings.add("ERROR", "duplicate_department_id", f"{count}회 중복", department_id)

    for department in departments:
        if not department.source_url.strip():
            findings.add("ERROR", "source_url_missing", "출처 URL이 비었다", department.department_id)
        if department.department_name != normalize_department_name(department.department_name):
            findings.add(
                "ERROR",
                "name_not_normalized",
                f"정규화되지 않은 학과명: {department.department_name!r}",
                department.department_id,
            )
        if department.source_svy_year < 2000 or department.source_svy_year > date.today().year + 1:
            findings.add(
                "WARN", "svy_year_suspicious", f"조사년도 {department.source_svy_year}", department.department_id
            )

    # schl_id는 raw에만 있으므로 raw와 대조해 ID 재생성이 재현되는지 본다.
    raw_by_key = {}
    for row in _read_jsonl(DATA_DIR / "raw" / "departments.raw.jsonl"):
        key = (
            normalize_department_name(row["university_name"]),
            normalize_department_name(row["department_name"]),
            normalize_department_name(row["college_name"]),
        )
        raw_by_key[key] = row["schl_id"]
    for department in departments:
        key = (department.university_name, department.department_name, department.college_name)
        schl_id = raw_by_key.get(key)
        if schl_id is None:
            findings.add("WARN", "raw_row_missing", "정제본에 대응하는 원본 행을 못 찾았다", department.department_id)
            continue
        expected = generate_department_id(schl_id, department.department_name, department.college_name)
        if expected != department.department_id:
            findings.add(
                "ERROR",
                "department_id_not_reproducible",
                f"원본에서 다시 만든 ID {expected}와 다르다",
                department.department_id,
            )

    placeholder = [d for d in departments if "ACADEMYINFO_PENDING" in raw_by_key.get(
        (d.university_name, d.department_name, d.college_name), ""
    )]
    if placeholder:
        findings.add(
            "INFO",
            "schl_id_placeholder",
            f"{len(placeholder)}개 학과의 schl_id가 임시값이다 — 대학알리미 API Key 발급 시 "
            "전부 재생성되며 department_id도 바뀐다",
            "data/raw/departments.raw.jsonl",
        )
    return departments


def audit_canonical_mapping(findings: Findings, departments: list[Department]) -> None:
    results = _read_jsonl(DATA_DIR / "master" / "canonical_mapping_results.jsonl")
    major_ids = {row["major_id"] for row in _read_jsonl(DATA_DIR / "master" / "canonical_majors.jsonl")}
    by_department = {row["department_id"]: row for row in results}

    for department in departments:
        result = by_department.get(department.department_id)
        if result is None:
            findings.add("ERROR", "mapping_missing", "Canonical Mapping 결과가 없다", department.department_id)
            continue
        if result["primary_candidate"] and result["primary_candidate"] not in major_ids:
            findings.add(
                "ERROR",
                "unknown_major_id",
                f"목록에 없는 major_id {result['primary_candidate']}",
                department.department_id,
            )
        if result["mapping_status"] != "AUTO_MAPPED" and department.canonical_major_id is not None:
            findings.add(
                "ERROR",
                "unconfirmed_mapping_promoted",
                f"{result['mapping_status']}인데 canonical_major_id가 채워져 있다",
                department.department_id,
            )
        if result["mapping_status"] == "AUTO_MAPPED" and department.canonical_major_id is None:
            findings.add(
                "WARN",
                "auto_mapped_not_applied",
                "AUTO_MAPPED인데 canonical_major_id가 비어 있다",
                department.department_id,
            )

    review_required = [r for r in results if r["mapping_status"] == "REVIEW_REQUIRED"]
    if review_required:
        findings.add(
            "INFO",
            "review_required_present",
            f"{len(review_required)}건이 REVIEW_REQUIRED로 남아 있다 — A 검토 대상",
            "data/master/canonical_mapping_review_required.jsonl",
        )


def audit_admissions(findings: Findings, departments: list[Department]) -> None:
    path = DATA_DIR / "admissions" / "admission_references.jsonl"
    rows = _read_jsonl(path)
    if not rows:
        findings.add("WARN", "source_missing", "입결 자료가 없다", _rel(path))
        return

    references: list[AdmissionReference] = []
    for index, row in enumerate(rows, start=1):
        try:
            references.append(AdmissionReference.model_validate(row))
        except ValidationError as exc:
            findings.add("ERROR", "type_invalid", f"{index}행 Schema 위반: {exc.error_count()}건", _rel(path))

    known_ids = {d.department_id for d in departments}
    for reference in references:
        if reference.department_id not in known_ids:
            findings.add(
                "ERROR", "dangling_department_id", "학과 Master에 없는 department_id", reference.department_id
            )
        if not reference.source_url.strip():
            findings.add("ERROR", "source_url_missing", "출처 URL이 비었다", reference.department_id)
        if reference.verified_at is None:
            findings.add("ERROR", "as_of_missing", "기준일(verified_at)이 없다", reference.department_id)

    for problem in validate_group_field(references):
        findings.add("ERROR", "comparability_group_mismatch", problem)

    duplicates = Counter(
        (r.department_id, r.data_comparability_group, r.admission_track) for r in references
    )
    for key, count in duplicates.items():
        if count > 1:
            findings.add("ERROR", "duplicate_admission_row", f"{count}회 중복", " / ".join(map(str, key)))

    unfilled = [r for r in references if r.score_50_cut is None and r.score_70_cut is None]
    if unfilled:
        findings.add(
            "INFO",
            "admission_cut_pending",
            f"{len(unfilled)}행의 컷 점수가 비어 있다 — 출처 미확정 상태에서 숫자를 채우지 않는다",
            _rel(path),
        )
    drafts = [r for r in references if r.review_status == "draft"]
    if drafts:
        findings.add(
            "WARN",
            "admission_draft_only",
            f"{len(drafts)}행이 draft다 — 화면 비교에 쓰려면 verified 승격이 필요하다",
            _rel(path),
        )


def audit_subjects(findings: Findings) -> None:
    path = DATA_DIR / "master" / "subjects.jsonl"
    rows = _read_jsonl(path)
    if not rows:
        findings.add("ERROR", "source_missing", "subjects.jsonl이 비었거나 없다", _rel(path))
        return

    profiles: list[SubjectProfile] = []
    for index, row in enumerate(rows, start=1):
        try:
            profiles.append(SubjectProfile.model_validate(row))
        except ValidationError as exc:
            findings.add("ERROR", "type_invalid", f"{index}행 Schema 위반: {exc.error_count()}건", _rel(path))

    ids = Counter(p.subject_id for p in profiles)
    for subject_id, count in ids.items():
        if count > 1:
            findings.add("ERROR", "duplicate_subject_id", f"{count}회 중복", subject_id)

    for profile in profiles:
        expected = generate_subject_id(CURRICULUM_CODE, profile.label)
        if expected != profile.subject_id:
            findings.add(
                "ERROR",
                "subject_id_not_reproducible",
                f"정규화 과목명으로 다시 만든 ID {expected}와 다르다",
                profile.subject_id,
            )
        unknown = set(profile.trait_vector) - KNOWN_TRAIT_IDS
        if unknown:
            findings.add("ERROR", "unknown_trait_id", f"Ontology에 없는 {sorted(unknown)}", profile.subject_id)
        bad_values = [v for v in profile.trait_vector.values() if v not in ALLOWED_VECTOR_VALUES]
        if bad_values:
            findings.add(
                "ERROR",
                "vector_value_off_scale",
                f"0/.33/.67/1.00이 아닌 값 {bad_values}",
                profile.subject_id,
            )
        if not profile.source_id.strip():
            findings.add("ERROR", "source_url_missing", "source_id가 비었다", profile.subject_id)

    alias_rows = _read_jsonl(DATA_DIR / "master" / "subject_aliases.jsonl")
    alias_targets: dict[str, set[str]] = {}
    for row in alias_rows:
        alias_targets.setdefault(row["alias"], set()).add(row["subject_id"])
    for alias, targets in alias_targets.items():
        if len(targets) > 1:
            findings.add("ERROR", "alias_collision", f"{len(targets)}개 과목을 동시에 가리킨다", alias)


def audit_major_profiles(findings: Findings) -> None:
    path = DATA_DIR / "master" / "major_profiles.jsonl"
    rows = _read_jsonl(path)
    if not rows:
        findings.add("ERROR", "source_missing", "major_profiles.jsonl이 비었거나 없다", _rel(path))
        return

    for index, row in enumerate(rows, start=1):
        try:
            profile = MajorProfile.model_validate(row)
        except ValidationError as exc:
            findings.add("ERROR", "type_invalid", f"{index}행 Schema 위반: {exc.error_count()}건", _rel(path))
            continue

        merged: dict[str, float] = {}
        for vector in (
            profile.interest_vector,
            profile.cognitive_vector,
            profile.work_style_vector,
            profile.environment_vector,
        ):
            merged.update(vector)
        missing = KNOWN_TRAIT_IDS - set(merged)
        if missing:
            findings.add("ERROR", "trait_missing", f"등급이 빠진 Trait {sorted(missing)}", profile.major_id)
        unknown = set(merged) - KNOWN_TRAIT_IDS
        if unknown:
            findings.add("ERROR", "unknown_trait_id", f"Ontology에 없는 {sorted(unknown)}", profile.major_id)
        bad_values = [v for v in merged.values() if v not in ALLOWED_VECTOR_VALUES]
        if bad_values:
            findings.add("ERROR", "vector_value_off_scale", f"허용 밖 값 {bad_values}", profile.major_id)
        if not profile.source_ids:
            findings.add("ERROR", "source_url_missing", "source_ids가 비었다", profile.major_id)
        if profile.review_status == "draft":
            findings.add("INFO", "major_profile_draft", "A 검토 전 초안이다", profile.major_id)


def audit_rag(findings: Findings) -> None:
    sources = _read_jsonl(DATA_DIR / "rag" / "sources.jsonl")
    if not sources:
        findings.add("WARN", "source_missing", "RAG 수집 대상이 없다", "data/rag/sources.jsonl")
        return

    for row in sources:
        if not row.get("source_url"):
            findings.add("ERROR", "source_url_missing", "수집 대상에 출처 URL이 없다", row.get("title", ""))
        if not row.get("as_of_date"):
            findings.add("ERROR", "as_of_missing", "기준일이 없다", row.get("source_url", ""))

    sample = [r for r in sources if str(r.get("source_url", "")).startswith("sample://")]
    if sample:
        findings.add(
            "INFO",
            "rag_sample_documents",
            f"{len(sample)}건이 공식 자료가 아니라 파이프라인 검증용 샘플이다 "
            "(source_url이 sample://로 시작해 공식 출처와 섞이지 않는다)",
            "data/rag/sources.jsonl",
        )

    manifest_rows = _read_jsonl(DATA_DIR / "rag" / "manifest.jsonl")
    for index, row in enumerate(manifest_rows, start=1):
        try:
            entry = DocumentManifestEntry.model_validate(row)
        except ValidationError as exc:
            findings.add("ERROR", "type_invalid", f"manifest {index}행 Schema 위반: {exc.error_count()}건")
            continue
        if entry.status is DocumentManifestStatus.RAG_INDEXED and entry.as_of_date is None:
            findings.add("ERROR", "as_of_missing", "색인된 문서에 기준일이 없다", entry.document_id)
        if entry.status is DocumentManifestStatus.TEXT_EMPTY and not entry.error_message:
            findings.add("WARN", "empty_without_reason", "TEXT_EMPTY인데 사유가 없다", entry.document_id)


def audit_drafts(findings: Findings) -> None:
    root = DATA_DIR / "drafts"
    for path in sorted(root.rglob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        entry = payload.get("draft_entry")
        if entry is None:
            findings.add("WARN", "draft_entry_missing", "DraftEntry 메타데이터가 없다", _rel(path))
            continue
        try:
            parsed = DraftEntry.model_validate(entry)
        except ValidationError as exc:
            findings.add("ERROR", "type_invalid", f"DraftEntry Schema 위반: {exc.error_count()}건", _rel(path))
            continue
        if parsed.as_of_date is None:
            findings.add("ERROR", "as_of_missing", "as_of_date가 없다", parsed.draft_id)
        if not parsed.author_id:
            findings.add("ERROR", "author_missing", "author_id가 없다", parsed.draft_id)


def write_report(findings: Findings) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    counts = findings.counts()
    payload = {
        "generated_on": str(date.today()),
        "summary": {level: counts.get(level, 0) for level in ("ERROR", "WARN", "INFO")},
        "findings": findings.items,
    }
    (AUDIT_DIR / "data_quality.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "# 데이터 품질 검사 결과 (작업자 C)",
        "",
        f"생성 {payload['generated_on']} · "
        f"ERROR {payload['summary']['ERROR']} / WARN {payload['summary']['WARN']} / "
        f"INFO {payload['summary']['INFO']}",
        "",
        "| 등급 | 검사 | 대상 | 내용 |",
        "|---|---|---|---|",
    ]
    order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    for item in sorted(findings.items, key=lambda i: (order[i["severity"]], i["check"])):
        lines.append(
            f"| {item['severity']} | {item['check']} | {item['subject'] or '-'} | {item['message']} |"
        )
    (AUDIT_DIR / "data_quality.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run() -> Findings:
    findings = Findings()
    departments = audit_departments(findings)
    audit_canonical_mapping(findings, departments)
    audit_admissions(findings, departments)
    audit_subjects(findings)
    audit_major_profiles(findings)
    audit_rag(findings)
    audit_drafts(findings)
    return findings


if __name__ == "__main__":
    result = run()
    write_report(result)
    counts = result.counts()
    print(
        f"ERROR {counts.get('ERROR', 0)} / WARN {counts.get('WARN', 0)} / INFO {counts.get('INFO', 0)}"
        " — data/audit/data_quality.md"
    )
    for item in result.items:
        if item["severity"] != "INFO":
            print(f"  {item['severity']:5s} {item['check']}: {item['subject']} {item['message']}")
    if result.has_error():
        raise SystemExit(1)
