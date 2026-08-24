"""department_id(v1) → offering_id(v2) Migration Map — 2026-08-25 지시서
(a/offering-identity-v2) §3.

**기존 35건 Master ID는 이 라운드에서 즉시 변경하지 않는다**(§5) — 이 Map은
"바꿨다"는 기록이 아니라 "언젠가 실제로 마이그레이션할 때 옛 ID가 새 ID
몇 개로 갈라지는지"를 미리 계산해 감사 가능하게 남겨두는 별도 산출물이다.

`old_department_id` 하나가 `new_offering_ids` 여러 개로 갈라지는 one-to-many
구조를 반드시 지원해야 한다(§3) — 16개 identity-key 충돌 Group이 정확히 이
경우다(각 Group당 2개 편제로 분리). Master 35건은 원본 데이터에
`schl_id`/`source_schl_mjr_id`가 없어(§ Master Schema는 Identity v2 이전에
만들어졌다) 이번 라운드에는 실제 offering_id를 계산할 재료 자체가 없다 —
`new_offering_ids=[]`로 정직하게 비워두고 `migration_status`로 그 이유를
명시한다(값을 지어내지 않는다)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

MigrationStatus = Literal[
    "MASTER_UNCHANGED_SOURCE_IDENTIFIERS_UNAVAILABLE",
    "RESOLVED_ONE_TO_MANY_COLLISION",
]


class DepartmentIdMigrationMapEntry(BaseModel):
    """`old_department_id`가 Key다(Master 35건 + 충돌 Group 16건 = 51행,
    서로 겹치지 않음 — `test_department_offering_identity_v2.py`에서 실제
    파일로 겹치지 않음을 확인한다)."""

    old_department_id: str
    new_offering_ids: list[str] = Field(default_factory=list)
    display_group_id: str | None = None
    migration_status: MigrationStatus
    decision_reason: str

    @field_validator("old_department_id", "decision_reason")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("빈 값은 허용하지 않는다")
        return value

    @property
    def key(self) -> str:
        return self.old_department_id
