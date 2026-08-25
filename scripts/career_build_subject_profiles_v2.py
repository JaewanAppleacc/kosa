"""v2(24-Trait) SubjectProfile 정본 — 2026-08-23 Trait Ontology v2(2.6단계) §8,
2026-08-25 a/subject-mapping-38-majors 지시서 확장.

**2026-08-25 확장 전**: Vertical Slice 대표 전공 3개(media_communication/hci_ux/
industrial_engineering)에 연결된 과목 6개만 다뤘다 — 39개 서비스 Major
(`data/master/service_canonical_majors_v2.jsonl`) 중 33개는 v2 후보 과목이 0건이라
희망과목 화면이 비어 있었다.

**2026-08-25 확장 후**: `related_major_ids`를 두 소스의 합집합으로 계산한다.

    1. Legacy `data/master/subjects.jsonl`의 기존 `related_major_ids`(이미 검토된
       과거 연결 — 그대로 보존한다, 재검토하지 않는다)
    2. `data/master/subject_major_link_evidence_v2.jsonl`(신규, 39개 서비스 Major
       전부 대상 — `career_build_subject_major_mapping_v2_expansion.py`가 만든다)의
       RELATED 항목

과목 정체성(label·source_id)도 두 소스에서 온다 — Legacy `subjects.jsonl`에 있는
과목(subject_id가 이미 존재)은 그 정체성을 그대로 쓰고, 신규 과목(2026-08-25
확장분, Legacy에 없음)은 `NEW_SUBJECT_IDENTITIES`에서 가져온다(하드코딩된 상수 —
`career_build_subject_profiles.py`의 `TOUCHED_SUBJECTS` 관례와 동일하게, 새 과목의
공식 명칭·교과군은 사람이 직접 검토해 채워 넣는다).

`activity_summary`는 이제 Legacy 재사용이 아니라 v2 Trait Evidence 자체에서
계산한다(EVIDENCED 중 grade가 가장 높은 것, 동점이면 trait_id 알파벳순 — 12차
리뷰 `career_build_subject_profiles.py`와 같은 결정론적 규칙) — 확장분 과목은
Legacy `activity_summary`가 아예 없으므로 이 방식이 유일하게 일관된 소스다.

`related_major_ids`에 쓰인 major_id는 39개 서비스 Major Catalog에 실제 존재하는지
Fail-Fast로 검증한다(§3 "hci_ux는 DEPARTMENT_LEVEL_ONLY... 과목 단위 자동 연결 금지"
— `subject_major_link_evidence_v2.jsonl`에 hci_ux를 대상으로 하는 행이 있으면 실패한다.
Legacy `subjects.jsonl`에 이미 있던 hci_ux 연결 2개[정보·소프트웨어와 생활]는 예외다 —
이번 라운드 이전에 이미 개별 검토를 거친 기존 연결이라 보존하되, 새로 자동 추가하지
않는다).

기존 `data/master/subjects.jsonl`은 전혀 건드리지 않는다(읽기 전용) — 별도 정본
`data/master/subject_profiles_v2.jsonl`을 만든다.

실행: PYTHONPATH=. ./.venv/bin/python scripts/career_build_subject_profiles_v2.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402

from src.engines.trait_normalizer import normalize_grade  # noqa: E402
from src.ids import generate_subject_id  # noqa: E402
from src.schemas.course import SubjectProfile  # noqa: E402
from src.services.service_canonical_major_v2_loader import load_service_canonical_majors_v2  # noqa: E402
from src.services.subject_major_link_evidence import (  # noqa: E402
    SubjectMajorLinkRecord,
    load_subject_major_link_evidence,
)
from src.services.subject_trait_mapping_evidence import (  # noqa: E402
    SubjectTraitMappingRecord,
    load_subject_trait_mapping_evidence,
)
from src.services.trait_ontology_v2 import load_trait_ontology_v2  # noqa: E402

SUBJECTS_PATH = ROOT / "data" / "master" / "subjects.jsonl"
V2_EVIDENCE_PATH = ROOT / "data" / "master" / "subject_trait_mapping_evidence_v2.jsonl"
V2_MAJOR_LINK_EVIDENCE_PATH = ROOT / "data" / "master" / "subject_major_link_evidence_v2.jsonl"
OUTPUT_PATH = ROOT / "data" / "master" / "subject_profiles_v2.jsonl"

# hci_ux는 mapping_scope=DEPARTMENT_LEVEL_ONLY다 — 이번 확장 라운드가 과목 단위로
# 새로 만든 연결이 아니라, Legacy `subjects.jsonl`에 이미 있던 2개(정보/소프트웨어와
# 생활, 2026-08-24 14차 리뷰가 개별 검토해 확정)만 그대로 보존한다. 새 v2 Link
# Evidence 파일에 hci_ux를 대상으로 하는 행이 있으면 Fail-Fast(§3 "computer_science
# Group 전체를 hci_ux로 연결 금지"의 재발 방지).
DEPARTMENT_LEVEL_ONLY_MAJOR_IDS = frozenset({"hci_ux"})

# 2026-08-25 확장분 신규 과목 24개 정체성 — 전부 2022 개정 교육과정(교육부 고시
# 제2022-33호) 보통교과 실제 과목명이다. `data/master/subjects.jsonl`(Legacy)에는
# 없으므로 여기서 선언한다(subject_id·label·source_id만 필요 — trait_vector·
# related_major_ids는 각각 Evidence 파일에서 별도로 계산된다).
MOE_URL = "https://www.moe.go.kr/boardCnts/viewRenew.do?boardID=141&lev=0&statusYN=W&s=moe&m=0404&opType=N&boardSeq=93458"
NEW_SUBJECT_LABELS: tuple[str, ...] = (
    "화학", "지구과학", "행성우주과학", "기후변화와 지속가능한 세계", "융합과학 탐구",
    "대수", "기하", "인공지능 수학", "경제 수학",
    "정치", "법과 사회", "경제", "국제 관계의 이해", "여행지리", "인문학과 윤리",
    "사회와 문화", "한국지리 탐구",
    "로봇과 공학세계", "생활과학 탐구",
    "문학", "문학과 영상",
    "영어 발표와 토론", "중국어", "보건",
)
CURRICULUM_CODE = "2022-33"
NEW_SUBJECT_IDENTITIES: dict[str, dict[str, str]] = {
    generate_subject_id(CURRICULUM_CODE, label): {"label": label, "source_id": MOE_URL}
    for label in NEW_SUBJECT_LABELS
}


def _load_legacy_identities(path: Path = SUBJECTS_PATH) -> dict[str, dict]:
    if not path.exists():
        return {}
    return {
        s["subject_id"]: s
        for s in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    }


def _build_related_major_ids(
    link_records: list[SubjectMajorLinkRecord],
    legacy_identities: dict[str, dict],
    *,
    known_major_ids: set[str],
) -> dict[str, list[str]]:
    """subject_id -> 39개 서비스 Major 중 RELATED로 확정된 major_id 목록(정렬됨).
    Legacy `related_major_ids`(이미 검토된 과거 연결)와 신규 v2 Link Evidence의
    합집합이다."""

    by_subject: dict[str, set[str]] = defaultdict(set)
    for identity in legacy_identities.values():
        for major_id in identity.get("related_major_ids", []):
            by_subject[identity["subject_id"]].add(major_id)

    for record in link_records:
        if record.major_id not in known_major_ids:
            raise SystemExit(
                f"{V2_MAJOR_LINK_EVIDENCE_PATH.name}: {record.major_id!r}가 39개 서비스 Major "
                "Catalog에 없다"
            )
        if record.major_id in DEPARTMENT_LEVEL_ONLY_MAJOR_IDS:
            raise SystemExit(
                f"{V2_MAJOR_LINK_EVIDENCE_PATH.name}: {record.subject_id}는 DEPARTMENT_LEVEL_ONLY "
                f"Major {record.major_id!r}를 새로 자동 연결할 수 없다(§3 Group 전체 자동 연결 금지) "
                "— Legacy subjects.jsonl에 이미 있던 연결만 보존한다"
            )
        if record.link_status == "RELATED":
            by_subject[record.subject_id].add(record.major_id)

    return {subject_id: sorted(majors) for subject_id, majors in by_subject.items()}


def _build_activity_summaries(trait_records: list[SubjectTraitMappingRecord]) -> dict[str, str]:
    """subject_id -> 대표 학습 활동 한 줄. EVIDENCED 중 grade가 가장 높은 것, 동점이면
    trait_id 알파벳순으로 결정론적으로 고른다(career_build_subject_profiles.py와
    동일 규칙)."""

    by_subject: dict[str, list[SubjectTraitMappingRecord]] = defaultdict(list)
    for record in trait_records:
        if record.mapping_status == "EVIDENCED":
            by_subject[record.subject_id].append(record)

    summaries: dict[str, str] = {}
    for subject_id, records in by_subject.items():
        best = min(records, key=lambda r: (-r.grade, r.trait_id))
        summaries[subject_id] = best.activity_summary
    return summaries


def build(
    evidence_records: list[SubjectTraitMappingRecord] | None = None,
    link_records: list[SubjectMajorLinkRecord] | None = None,
    legacy_identities: dict[str, dict] | None = None,
    new_identities: dict[str, dict[str, str]] | None = None,
    known_trait_ids: set[str] | None = None,
    known_major_ids: set[str] | None = None,
) -> list[SubjectProfile]:
    records = (
        evidence_records if evidence_records is not None
        else load_subject_trait_mapping_evidence(V2_EVIDENCE_PATH)
    )
    links = (
        link_records if link_records is not None
        else load_subject_major_link_evidence(V2_MAJOR_LINK_EVIDENCE_PATH)
    )
    identities = legacy_identities if legacy_identities is not None else _load_legacy_identities()
    new_ids = new_identities if new_identities is not None else NEW_SUBJECT_IDENTITIES
    known_trait_ids = known_trait_ids if known_trait_ids is not None else {t.trait_id for t in load_trait_ontology_v2()}
    known_major_ids = (
        known_major_ids if known_major_ids is not None
        else {m.major_id for m in load_service_canonical_majors_v2()}
    )

    all_identities: dict[str, dict] = {**identities}
    for subject_id, identity in new_ids.items():
        if subject_id in all_identities:
            continue  # Legacy에 이미 있으면 그 정체성을 우선한다(중복 선언 방지).
        all_identities[subject_id] = {"subject_id": subject_id, **identity}

    by_subject: dict[str, list[SubjectTraitMappingRecord]] = defaultdict(list)
    for record in records:
        if record.subject_id not in all_identities:
            raise SystemExit(
                f"{V2_EVIDENCE_PATH.name}: {record.subject_id!r}의 정체성(label/source_id)이 "
                "subjects.jsonl에도 NEW_SUBJECT_IDENTITIES에도 없다"
            )
        if record.trait_id not in known_trait_ids:
            raise SystemExit(
                f"{V2_EVIDENCE_PATH.name}: {record.subject_id}/{record.trait_id} — 현재 v2 Trait "
                "Ontology(24개)에 없는 trait_id다"
            )
        by_subject[record.subject_id].append(record)

    related_major_ids = _build_related_major_ids(links, identities, known_major_ids=known_major_ids)
    activity_summaries = _build_activity_summaries(records)

    profiles: list[SubjectProfile] = []
    for subject_id in sorted(by_subject):
        subject_records = by_subject[subject_id]
        duplicated = {
            t for t in {r.trait_id for r in subject_records}
            if sum(1 for r in subject_records if r.trait_id == t) > 1
        }
        if duplicated:
            raise SystemExit(f"{subject_id}: trait_id 중복 Mapping 레코드 {sorted(duplicated)}")

        trait_vector: dict[str, float] = {}
        for record in subject_records:
            if record.mapping_status not in ("EVIDENCED", "NO_DIRECT_EVIDENCE"):
                continue
            trait_vector[record.trait_id] = normalize_grade(record.grade)  # type: ignore[arg-type]

        identity = all_identities[subject_id]
        profiles.append(
            SubjectProfile(
                subject_id=subject_id, label=identity["label"], trait_vector=trait_vector,
                related_major_ids=related_major_ids.get(subject_id, []), source_id=identity["source_id"],
                activity_summary=activity_summaries.get(subject_id, ""),
            )
        )
    return profiles


def main() -> None:
    profiles = build()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("".join(p.model_dump_json() + "\n" for p in profiles), encoding="utf-8")
    print(f"{OUTPUT_PATH.relative_to(ROOT)}: SubjectProfile {len(profiles)}개 생성")
    covered_majors: set[str] = set()
    for p in profiles:
        covered_majors.update(p.related_major_ids)
        print(f"  {p.subject_id}({p.label}): Trait {len(p.trait_vector)}개, Major {len(p.related_major_ids)}개")
    print(f"커버된 서비스 Major: {len(covered_majors)}개")


if __name__ == "__main__":
    use_utf8_stdout()
    main()
