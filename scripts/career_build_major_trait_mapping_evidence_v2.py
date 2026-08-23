"""Vertical Slice 3개 전공(media_communication/hci_ux/industrial_engineering)의
v2(24-Trait) Major-Trait Mapping Evidence 정본 — 2026-08-23 Trait Ontology
v2(2.6단계) §6.

기존 `data/master/major_trait_mapping_evidence.jsonl`(12-Trait, A 소유, 12차 리뷰)을
**덮어쓰지 않는다** — 이 스크립트는 완전히 별도 정본
`data/master/major_trait_mapping_evidence_v2.jsonl`을 만든다.

내용:
1. 기존 12-Trait 매핑(3개 전공 × 12개 = 36행)을 그대로 재사용한다(§6 "기존
   Major–Trait Evidence URL 재사용 가능") — mapping_status·grade·evidence·note를
   전혀 바꾸지 않고 mapping_version만 "major_trait_mapping_v2"로 옮긴다.
2. v2 신규 12-Trait(3개 전공 × 12개 = 36행)은 전부 REVIEW_REQUIRED로 남긴다(§6
   "새 v2 Trait에 대한 직접 근거가 없다면 REVIEW_REQUIRED 유지", "자동 승격 금지").
   이 스크립트(A)가 실제 학과 공식 자료를 다시 열어 확인하지 않은 이상 EVIDENCED로
   자동 승격시키지 않는다 — grade를 매기려면 사람이 직접 그 학과 페이지를 재검토해야
   한다(CLAUDE.md "검증되지 않은 Trait·전공 Mapping을 확정 데이터로 처리" 금지와 동일한
   이유).

review_status는 기존 major.py의 값 그대로("draft") 쓴다 — 2.5.5단계에서 도입한
reviewer_1 단일 검토 정책(APPROVED/REVIEW_REQUIRED/DRAFT)은 검수 UI(질문·선택지)
전용이고, 이 Major-Trait Mapping의 2인 교차검토 요구와는 별개다(§6 "기존 2인 검토
요구는 이번 검수 UI 정책과 별개이므로 임의 변경하지 않음").

실행: PYTHONPATH=. ./.venv/bin/python scripts/career_build_major_trait_mapping_evidence_v2.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402

from src.services.major_trait_mapping_evidence import (  # noqa: E402
    MajorTraitMappingRecord,
    load_major_trait_mapping_evidence,
)
from src.services.trait_ontology_v2 import load_trait_ontology_v2  # noqa: E402

TARGET_MAJOR_IDS = ("media_communication", "hci_ux", "industrial_engineering")
V2_MAPPING_VERSION = "major_trait_mapping_v2"
OUTPUT_PATH = ROOT / "data" / "master" / "major_trait_mapping_evidence_v2.jsonl"

_NEW_TRAIT_NOTE = (
    "v2 신규 Trait — 공식 자료를 아직 직접 재확인하지 않았다. 2.6단계 §6 규칙대로 "
    "REVIEW_REQUIRED로 유지하며 자동 승격하지 않는다. grade를 매기려면 사람이 이 "
    "전공의 공식 교육과정·교육목표 자료를 다시 검토해야 한다."
)


def build(
    legacy_records: list[MajorTraitMappingRecord] | None = None,
    all_trait_ids: list[str] | None = None,
) -> list[MajorTraitMappingRecord]:
    legacy_records = legacy_records if legacy_records is not None else load_major_trait_mapping_evidence()
    all_trait_ids = all_trait_ids if all_trait_ids is not None else [t.trait_id for t in load_trait_ontology_v2()]

    legacy_by_key = {
        (r.major_id, r.trait_id): r for r in legacy_records if r.major_id in TARGET_MAJOR_IDS
    }
    legacy_trait_ids = {trait_id for (_, trait_id) in legacy_by_key}
    new_v2_trait_ids = sorted(set(all_trait_ids) - legacy_trait_ids)

    records: list[MajorTraitMappingRecord] = []
    for major_id in TARGET_MAJOR_IDS:
        for trait_id in sorted(legacy_trait_ids):
            legacy = legacy_by_key.get((major_id, trait_id))
            if legacy is None:
                raise SystemExit(
                    f"{major_id}/{trait_id}: 기존 major_trait_mapping_evidence.jsonl에 레코드가 없다"
                    " — 재사용할 값이 없으므로 v2 파일을 만들 수 없다"
                )
            records.append(legacy.model_copy(update={"mapping_version": V2_MAPPING_VERSION}))

        for trait_id in new_v2_trait_ids:
            records.append(
                MajorTraitMappingRecord(
                    major_id=major_id, trait_id=trait_id, mapping_status="REVIEW_REQUIRED",
                    grade=None, evidence=[], author_id="worker_a", review_status="draft",
                    mapping_version=V2_MAPPING_VERSION, note=_NEW_TRAIT_NOTE,
                )
            )
    return records


def main() -> None:
    records = build()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        "".join(r.model_dump_json() + "\n" for r in records), encoding="utf-8"
    )
    reused = sum(1 for r in records if r.mapping_status != "REVIEW_REQUIRED" or r.evidence)
    print(f"{OUTPUT_PATH.relative_to(ROOT)}: {len(records)}행 생성")
    print(f"  기존 재사용(EVIDENCED/NO_DIRECT_EVIDENCE/UNMAPPED): {sum(1 for r in records if r.mapping_status != 'REVIEW_REQUIRED')}행")
    print(f"  신규 v2 Trait REVIEW_REQUIRED: {sum(1 for r in records if r.mapping_status == 'REVIEW_REQUIRED')}행")


if __name__ == "__main__":
    use_utf8_stdout()
    main()
