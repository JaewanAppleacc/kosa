"""Vertical Slice 3개 전공에 연결된 과목 6개의 v2(24-Trait) Subject-Trait Mapping
Evidence 정본 — 2026-08-23 Trait Ontology v2(2.6단계) §8.

`career_build_major_trait_mapping_evidence_v2.py`와 완전히 같은 원칙을 과목 단위로
적용한다. 대상 과목은 `data/master/subjects.jsonl`에서 `related_major_ids`에
media_communication/hci_ux/industrial_engineering 중 하나라도 포함된 6개뿐이다
(§8 "Vertical Slice 과목만 대상으로 한다").

기존 `data/master/subject_trait_mapping_evidence.jsonl`(12-Trait)은 건드리지 않고,
별도 정본 `data/master/subject_trait_mapping_evidence_v2.jsonl`을 만든다. 기존
12-Trait 레코드는 그대로 재사용(mapping_version만 교체)하고, v2 신규 12-Trait는 전부
REVIEW_REQUIRED로 남긴다(자동 승격 금지, career_build_major_trait_mapping_evidence_v2.py
와 동일 이유).

실행: PYTHONPATH=. ./.venv/bin/python scripts/career_build_subject_trait_mapping_evidence_v2.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402

from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAIT_IDS  # noqa: E402
from src.services.subject_trait_mapping_evidence import (  # noqa: E402
    SubjectTraitMappingRecord,
    load_subject_trait_mapping_evidence,
)
from src.services.trait_ontology_v2 import load_trait_ontology_v2  # noqa: E402

TARGET_MAJOR_IDS = ("media_communication", "hci_ux", "industrial_engineering")
V2_MAPPING_VERSION = "subject_trait_mapping_v2"
SUBJECTS_PATH = ROOT / "data" / "master" / "subjects.jsonl"
OUTPUT_PATH = ROOT / "data" / "master" / "subject_trait_mapping_evidence_v2.jsonl"

_NEW_TRAIT_NOTE = (
    "v2 신규 Trait — 공식 성취기준을 아직 직접 재확인하지 않았다. 2.6단계 §8 규칙대로 "
    "REVIEW_REQUIRED로 유지하며 자동 승격하지 않는다."
)


def _target_subject_ids(subjects_path: Path = SUBJECTS_PATH) -> list[str]:
    subjects = [json.loads(line) for line in subjects_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = [
        s["subject_id"] for s in subjects
        if any(m in s.get("related_major_ids", []) for m in TARGET_MAJOR_IDS)
    ]
    return sorted(ids)


def build(
    legacy_records: list[SubjectTraitMappingRecord] | None = None,
    all_trait_ids: list[str] | None = None,
    target_subject_ids: list[str] | None = None,
) -> list[SubjectTraitMappingRecord]:
    legacy_records = legacy_records if legacy_records is not None else load_subject_trait_mapping_evidence()
    all_trait_ids = all_trait_ids if all_trait_ids is not None else [t.trait_id for t in load_trait_ontology_v2()]
    target_subject_ids = target_subject_ids if target_subject_ids is not None else _target_subject_ids()

    # 2026-08-23: Major와 달리 과목-Trait 매핑은 애초에 희소하다(과목 하나가 보통
    # 2~4개 Trait만 EVIDENCED/UNMAPPED로 다룬다) — Major처럼 "12개 전부 있어야 한다"는
    # 완전성 요구를 걸지 않는다. 이 6개 과목이 기존 파일에서 실제로 갖고 있는 레코드만
    # 그대로 재사용한다.
    legacy_by_subject: dict[str, list[SubjectTraitMappingRecord]] = {}
    for record in legacy_records:
        if record.subject_id in target_subject_ids:
            legacy_by_subject.setdefault(record.subject_id, []).append(record)
    for subject_id in target_subject_ids:
        if subject_id not in legacy_by_subject:
            raise SystemExit(
                f"{subject_id}: 기존 subject_trait_mapping_evidence.jsonl에 레코드가 "
                "하나도 없다 — 재사용할 값이 없다"
            )

    # "신규 v2 Trait"의 기준은 "이 과목 파일에 실제로 등장한 적이 있는가"가 아니라
    # "Legacy 12-Trait Ontology(VERTICAL_SLICE_TRAIT_IDS)에 있는가"다 — 과목-Trait
    # 매핑은 원래 희소해서(예: collaboration_preference/immediate_execution은 어느
    # 과목에도 아직 안 쓰였다) 파일에 등장한 적 없는 Legacy Trait까지 "신규 v2"로
    # 잘못 분류하면 안 된다.
    new_v2_trait_ids = sorted(set(all_trait_ids) - VERTICAL_SLICE_TRAIT_IDS)

    records: list[SubjectTraitMappingRecord] = []
    for subject_id in target_subject_ids:
        for legacy in sorted(legacy_by_subject.get(subject_id, []), key=lambda r: r.trait_id):
            records.append(legacy.model_copy(update={"mapping_version": V2_MAPPING_VERSION}))

        for trait_id in new_v2_trait_ids:
            records.append(
                SubjectTraitMappingRecord(
                    subject_id=subject_id, trait_id=trait_id, mapping_status="REVIEW_REQUIRED",
                    grade=None, curriculum_evidence=[], activity_summary="", author_id="worker_a",
                    review_status="draft", mapping_version=V2_MAPPING_VERSION, note=_NEW_TRAIT_NOTE,
                )
            )
    return records


def main() -> None:
    records = build()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("".join(r.model_dump_json() + "\n" for r in records), encoding="utf-8")
    print(f"{OUTPUT_PATH.relative_to(ROOT)}: {len(records)}행 생성")


if __name__ == "__main__":
    use_utf8_stdout()
    main()
