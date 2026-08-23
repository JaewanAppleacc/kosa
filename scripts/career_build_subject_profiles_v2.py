"""Vertical Slice 3개 전공에 연결된 과목 6개의 v2(24-Trait) SubjectProfile 정본 —
2026-08-23 Trait Ontology v2(2.6단계) §8.

과목 정체성(subject_id·label·related_major_ids·source_id)은 이미 확정된 정본
`data/master/subjects.jsonl`(Legacy)에서 그대로 가져온다 — 새로 만들지 않는다.
`trait_vector`만 `data/master/subject_trait_mapping_evidence_v2.jsonl`(EVIDENCED/
NO_DIRECT_EVIDENCE)로 다시 계산해 24-Trait 범위로 넓힌다. `activity_summary`도
Legacy `subjects.jsonl`에 이미 있는 값을 그대로 재사용한다(§8 "관찰되지 않은 학생
Trait는 불일치가 아니라 미관찰"과 같은 정신으로, 이미 검토된 요약 문구를 새로 지어내지
않는다).

기존 `data/master/subjects.jsonl`은 전혀 건드리지 않는다 — 별도 정본
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
from src.schemas.course import SubjectProfile  # noqa: E402
from src.services.subject_trait_mapping_evidence import (  # noqa: E402
    SubjectTraitMappingRecord,
    load_subject_trait_mapping_evidence,
)
from src.services.trait_ontology_v2 import load_trait_ontology_v2  # noqa: E402

SUBJECTS_PATH = ROOT / "data" / "master" / "subjects.jsonl"
V2_EVIDENCE_PATH = ROOT / "data" / "master" / "subject_trait_mapping_evidence_v2.jsonl"
OUTPUT_PATH = ROOT / "data" / "master" / "subject_profiles_v2.jsonl"


def _load_legacy_identities(path: Path = SUBJECTS_PATH) -> dict[str, dict]:
    return {
        s["subject_id"]: s
        for s in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    }


def build(
    evidence_records: list[SubjectTraitMappingRecord] | None = None,
    legacy_identities: dict[str, dict] | None = None,
    known_trait_ids: set[str] | None = None,
) -> list[SubjectProfile]:
    records = (
        evidence_records if evidence_records is not None
        else load_subject_trait_mapping_evidence(V2_EVIDENCE_PATH)
    )
    identities = legacy_identities if legacy_identities is not None else _load_legacy_identities()
    known_trait_ids = known_trait_ids if known_trait_ids is not None else {t.trait_id for t in load_trait_ontology_v2()}

    by_subject: dict[str, list[SubjectTraitMappingRecord]] = defaultdict(list)
    for record in records:
        if record.subject_id not in identities:
            raise SystemExit(f"{V2_EVIDENCE_PATH.name}: {record.subject_id!r}가 subjects.jsonl에 없다")
        if record.trait_id not in known_trait_ids:
            raise SystemExit(
                f"{V2_EVIDENCE_PATH.name}: {record.subject_id}/{record.trait_id} — 현재 v2 Trait "
                "Ontology(24개)에 없는 trait_id다"
            )
        by_subject[record.subject_id].append(record)

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

        identity = identities[subject_id]
        profiles.append(
            SubjectProfile(
                subject_id=subject_id, label=identity["label"], trait_vector=trait_vector,
                related_major_ids=identity.get("related_major_ids", []), source_id=identity["source_id"],
                # Legacy 정본의 activity_summary를 그대로 재사용한다 — 새로 지어내지 않는다.
                activity_summary=identity.get("activity_summary", ""),
            )
        )
    return profiles


def main() -> None:
    profiles = build()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("".join(p.model_dump_json() + "\n" for p in profiles), encoding="utf-8")
    print(f"{OUTPUT_PATH.relative_to(ROOT)}: SubjectProfile {len(profiles)}개 생성")
    for p in profiles:
        print(f"  {p.subject_id}({p.label}): Vector에 담긴 Trait {len(p.trait_vector)}개(24개 중)")


if __name__ == "__main__":
    use_utf8_stdout()
    main()
