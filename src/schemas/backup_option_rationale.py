"""Backup Option Mapping Rationale Draft Schema — 2026-08-23 Trait Ontology
v2(2.5.3단계) §9.

Seed Anchor Variant의 `option_mapping_rationale_draft`와 같은 목적이다 — 사람이
검토할 수 있게 "이 문구가 왜 이 Trait 후보로 연결되는지" 한 문장으로 남기는 초안일
뿐, 검증 완료를 뜻하지 않는다. 학생 API에는 노출하지 않고 검수 UI에서만 보여준다."""

from __future__ import annotations

from pydantic import BaseModel


class BackupOptionRationaleError(ValueError):
    """정본 파일 자체가 구조적으로 잘못됐을 때(중복 Key, 실제 Backup Option 목록과
    불일치, 빈 Rationale)."""


class BackupOptionRationale(BaseModel):
    question_id: str
    role_id: str
    trait_id: str
    mapping_rationale_draft: str
