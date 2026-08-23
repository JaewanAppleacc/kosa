"""career_build_trait_ontology_v2.py — 2026-08-23 Trait Ontology v2(1단계).

data/master/trait_ontology_v2.jsonl(24개, Shadow Mode 정본)을 만든다.

입력:
    src/data/trait_ontology/vertical_slice_traits.py::VERTICAL_SLICE_TRAITS (기존 12개,
        review_status="team_reviewed"로 채워 저장한다 — 2026-08-20 확정 상태를 그대로
        반영한다. 이 12개의 ID·정의·행동 지표는 이 스크립트가 절대 바꾸지 않는다.)
    src/data/trait_ontology/new_traits_v2_draft.py::NEW_TRAITS_V2_DRAFT (신규 12개, 이미
        review_status="draft"로 정의돼 있다)

출력: data/master/trait_ontology_v2.jsonl — trait_id 오름차순 정렬, 결정론적.

재실행하면 항상 바이트 동일한 파일이 나와야 한다(다른 career_build_*.py 스크립트와
같은 계약).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # noqa: E402

from src.data.trait_ontology.new_traits_v2_draft import NEW_TRAITS_V2_DRAFT  # noqa: E402
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAITS  # noqa: E402
from src.schemas.trait import TraitDefinition  # noqa: E402

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "master" / "trait_ontology_v2.jsonl"


def _existing_as_v2(trait: TraitDefinition) -> TraitDefinition:
    """기존 12개는 ID·정의·행동 지표를 전혀 바꾸지 않고 review_status만 확정 상태로
    채운다(2026-08-20 확정 문서 그대로) — neighboring_trait_ids/distinction_notes는
    아직 v2 검토 대상이 아니라 빈 값으로 둔다(v2 신규 12개만 이번에 채운다)."""

    return trait.model_copy(update={"review_status": "team_reviewed"})


def build() -> list[TraitDefinition]:
    existing = [_existing_as_v2(t) for t in VERTICAL_SLICE_TRAITS]
    combined = existing + list(NEW_TRAITS_V2_DRAFT)

    ids = [t.trait_id for t in combined]
    if len(set(ids)) != len(ids):
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        raise ValueError(f"trait_id가 중복됐다: {duplicates}")
    if len(combined) != 24:
        raise ValueError(f"Core Trait는 정확히 24개여야 한다, got {len(combined)}")

    return sorted(combined, key=lambda t: t.trait_id)


def main() -> None:
    traits = build()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for trait in traits:
            f.write(json.dumps(trait.model_dump(mode="json"), ensure_ascii=False) + "\n")
    print(f"wrote {len(traits)} traits to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
