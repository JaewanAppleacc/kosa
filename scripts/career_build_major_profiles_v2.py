"""Vertical Slice 3개 전공의 v2(24-Trait) MajorProfile 정본 — 2026-08-23 Trait Ontology
v2(2.6단계) §6.

`data/master/major_trait_mapping_evidence_v2.jsonl`(EVIDENCED/NO_DIRECT_EVIDENCE만)을
읽어 `data/master/major_profiles_v2.jsonl`을 만든다. 기존
`data/master/major_profiles.jsonl`(Legacy, 12-Trait)은 전혀 건드리지 않는다 — 완전히
별도 정본이다.

Legacy `career_build_major_profiles.py::build_evidence_based_profiles()`와 다른 점
(§6 "24개 Trait를 억지로 모두 채우지 않음"): Legacy는 "Ontology의 모든 Trait에 대한
Mapping 레코드가 있어야 한다"만 강제하고 빌드는 그대로 진행하지만, 이 스크립트는 그
전제를 유지하면서도(v2 evidence 파일이 24개 모두를 명시적으로 REVIEW_REQUIRED/UNMAPPED/
EVIDENCED 중 하나로 갖고 있어야 한다) Vector 자체에는 EVIDENCED/NO_DIRECT_EVIDENCE만
넣는다 — v2 Ontology가 12개 더 크기 때문에 이 전공들 Vector가 24개를 다 채우지 못하는
것이 정상이다(UNMAPPED/REVIEW_REQUIRED는 grade가 아예 없으므로 0.00으로 채우지 않는다).

실행: PYTHONPATH=. ./.venv/bin/python scripts/career_build_major_profiles_v2.py
"""

from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402

from src.engines.trait_normalizer import normalize_grade  # noqa: E402
from src.schemas.major import MajorProfile  # noqa: E402
from src.services.major_trait_mapping_evidence import (  # noqa: E402
    MajorTraitMappingRecord,
    load_major_trait_mapping_evidence,
)
from src.services.trait_ontology_v2 import load_trait_ontology_v2  # noqa: E402

V2_EVIDENCE_PATH = ROOT / "data" / "master" / "major_trait_mapping_evidence_v2.jsonl"
OUTPUT_PATH = ROOT / "data" / "master" / "major_profiles_v2.jsonl"
PROFILE_VERSION = "major_profile_v2.0"

MAJOR_LABELS: dict[str, str] = {
    "media_communication": "미디어·커뮤니케이션",
    "hci_ux": "HCI·UX",
    "industrial_engineering": "산업공학",
}


def build(
    evidence_records: list[MajorTraitMappingRecord] | None = None,
    trait_definitions: dict[str, str] | None = None,
    updated_at: datetime | None = None,
) -> list[MajorProfile]:
    records = (
        evidence_records if evidence_records is not None
        else load_major_trait_mapping_evidence(V2_EVIDENCE_PATH)
    )
    vector_group_by_trait = (
        trait_definitions if trait_definitions is not None
        else {t.trait_id: t.primary_vector_group for t in load_trait_ontology_v2()}
    )
    now = updated_at or datetime(2026, 8, 23, tzinfo=timezone.utc)

    by_major: dict[str, list[MajorTraitMappingRecord]] = defaultdict(list)
    for record in records:
        if record.major_id not in MAJOR_LABELS:
            raise SystemExit(
                f"{V2_EVIDENCE_PATH.name}: {record.major_id!r}는 v2 Vertical Slice 대표 전공 3개"
                f"({sorted(MAJOR_LABELS)})에 없다"
            )
        if record.trait_id not in vector_group_by_trait:
            raise SystemExit(
                f"{V2_EVIDENCE_PATH.name}: {record.major_id}/{record.trait_id} — 현재 v2 Trait "
                "Ontology(24개)에 없는 trait_id다"
            )
        by_major[record.major_id].append(record)

    profiles: list[MajorProfile] = []
    for major_id in sorted(MAJOR_LABELS):
        major_records = by_major.get(major_id, [])
        duplicated = {
            t for t in {r.trait_id for r in major_records}
            if sum(1 for r in major_records if r.trait_id == t) > 1
        }
        if duplicated:
            raise SystemExit(f"{major_id}: trait_id 중복 Mapping 레코드 {sorted(duplicated)}")

        vectors: dict[str, dict[str, float]] = {
            "interest": {}, "cognitive": {}, "work_style": {}, "environment": {},
        }
        source_urls: set[str] = set()
        for record in major_records:
            if record.mapping_status not in ("EVIDENCED", "NO_DIRECT_EVIDENCE"):
                continue  # UNMAPPED/REVIEW_REQUIRED — §6 "억지로 모두 채우지 않음".
            group = vector_group_by_trait[record.trait_id]
            vectors[group][record.trait_id] = normalize_grade(record.grade)  # type: ignore[arg-type]
            for evidence in record.evidence:
                source_urls.add(evidence.source_url)

        profiles.append(
            MajorProfile(
                major_id=major_id, label=MAJOR_LABELS[major_id],
                interest_vector=vectors["interest"], cognitive_vector=vectors["cognitive"],
                work_style_vector=vectors["work_style"], environment_vector=vectors["environment"],
                source_ids=sorted(source_urls), extraction_method="rule",
                # 2인 교차검토 전이라 draft로 유지한다(§6 "자동 승격 금지").
                review_status="draft", profile_version=PROFILE_VERSION, updated_at=now,
            )
        )
    return profiles


def main() -> None:
    profiles = build()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("".join(p.model_dump_json() + "\n" for p in profiles), encoding="utf-8")
    print(f"{OUTPUT_PATH.relative_to(ROOT)}: MajorProfile {len(profiles)}개 생성")
    for p in profiles:
        total_traits = len(p.interest_vector) + len(p.cognitive_vector) + len(p.work_style_vector) + len(p.environment_vector)
        print(f"  {p.major_id}: Vector에 담긴 Trait {total_traits}개(24개 중)")


if __name__ == "__main__":
    use_utf8_stdout()
    main()
