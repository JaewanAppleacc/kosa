"""Backup Option Mapping Rationale Draft Schema — 2026-08-23 Trait Ontology
v2(2.5.3단계) §9, 2.5.4단계 §5.

Seed Anchor Variant의 `option_mapping_rationale_draft`와 같은 목적이다 — 사람이
검토할 수 있게 "이 문구가 왜 이 Trait 후보로 연결되는지(또는 왜 NO_SIGNAL인지)" 한
문장으로 남기는 초안일 뿐, 검증 완료를 뜻하지 않는다. 학생 API에는 노출하지 않고
검수 UI에서만 보여준다.

2.5.4단계 §5: 각 선택지는 "행동과 직접 연결되는 Primary Trait 1개" 또는 "NO_SIGNAL"
중 하나만 쓴다 — `trait_id=None`이면 그 Option이 NO_SIGNAL이라는 뜻이다(2.5.3단계의
기존 6개 Backup은 NO_SIGNAL이 없어 항상 값이 있었다)."""

from __future__ import annotations

from pydantic import BaseModel


class BackupOptionRationaleError(ValueError):
    """정본 파일 자체가 구조적으로 잘못됐을 때(중복 Key, 실제 Backup Option 목록과
    불일치, 빈 Rationale)."""


class BackupOptionRationale(BaseModel):
    question_id: str
    role_id: str
    trait_id: str | None = None
    mapping_rationale_draft: str
