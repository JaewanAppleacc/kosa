"""Department Offering Identity v2 packet Loader — 2026-08-25 지시서
(a/offering-identity-v2) §2/§4. A 소유(얇은 Loader — `trait_ontology_v2.py`/
`canonical_major_group_draft_loader.py`와 같은 "빌드 산출물 JSONL → Pydantic"
패턴).

`data/academyinfo_work/2025/packets/department_offering_identity_v2.jsonl`
(`career_build_department_offering_identity_v2.py`가 만드는 산출물)을 읽기만
한다 — 이 Loader가 그 파일을 쓰는 일은 없다."""

from __future__ import annotations

import json
from pathlib import Path

from src.schemas.department_offering_identity import DepartmentOfferingIdentity

DEFAULT_OFFERING_IDENTITY_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "academyinfo_work"
    / "2025"
    / "packets"
    / "department_offering_identity_v2.jsonl"
)


def load_offering_identities(path: Path | None = None) -> list[DepartmentOfferingIdentity]:
    source = path or DEFAULT_OFFERING_IDENTITY_PATH
    if not source.exists():
        return []
    return [
        DepartmentOfferingIdentity.model_validate(json.loads(line))
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
