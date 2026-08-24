"""JsonlDepartmentOfferingRepository — Identity v2 Repository — 2026-08-25
지시서(a/offering-identity-v2) §4.

기존 `src/repositories/department_repository.py`(작업자 C 소유,
`department_id`/Master 35건 전용)와 완전히 분리된, 새 `offering_id` 공간
전용 Repository다. 이 파일은 `department_repository.py`를 import하지 않고
Master(`data/master/departments.jsonl`)도 읽지 않는다 — Identity v2가 안착할
때까지 기존 Repository·Master 어느 것도 건드리지 않는다는 사실을 코드
구조로 보장한다(§5 "기존 35건 Master 즉시 교체 금지").

`JsonlDepartmentRepository`가 이미 확립한 원칙(2026-08-24
`fix: 전국 승격 정합성 결함 2건 수정`)을 새 ID 공간에 그대로 적용한다 —
`{o.offering_id: o for o in offerings}` 같은 dict comprehension은 중복
offering_id를 검증 없이 마지막 값으로 조용히 덮어쓴다. 여기서는 첫 중복을
만나는 즉시 던진다."""

from __future__ import annotations

from pathlib import Path

from src.schemas.department_offering_identity import DepartmentOfferingIdentity
from src.services.department_offering_identity_loader import (
    DEFAULT_OFFERING_IDENTITY_PATH,
    load_offering_identities,
)


class DuplicateOfferingIdError(ValueError):
    """같은 offering_id를 가진 행이 두 번 이상 등장할 때 — 어느 원본 행이
    맞는지 알 수 없으므로 조용히 뒤 항목으로 덮어쓰지 않고 즉시 실패시킨다
    (`department_repository.py::DuplicateDepartmentIdError`와 같은 원칙).
    메시지에는 offering_id만 담는다 — 학과명·대학명·URL·원본 JSON은 절대
    담지 않는다."""


class JsonlDepartmentOfferingRepository:
    """`data/academyinfo_work/2025/packets/department_offering_identity_v2.jsonl`
    을 읽는 Offering Repository. `display_group_id`는 유일 키가 아니다 — 한
    표시명 그룹 안에 여러 offering이 정상적으로 공존한다(§2 "표시명이 같다는
    이유만으로 병합하지 않는다")."""

    def __init__(
        self, offerings: list[DepartmentOfferingIdentity] | None = None, path: Path | None = None,
    ):
        loaded = offerings if offerings is not None else load_offering_identities(path or DEFAULT_OFFERING_IDENTITY_PATH)
        by_id: dict[str, DepartmentOfferingIdentity] = {}
        for offering in loaded:
            if offering.offering_id in by_id:
                raise DuplicateOfferingIdError(offering.offering_id)
            by_id[offering.offering_id] = offering
        self._offerings = loaded
        self._by_id = by_id

    def __len__(self) -> int:
        return len(self._offerings)

    def all(self) -> list[DepartmentOfferingIdentity]:
        return list(self._offerings)

    def get(self, offering_id: str) -> DepartmentOfferingIdentity | None:
        return self._by_id.get(offering_id)

    def by_display_group(self, display_group_id: str) -> list[DepartmentOfferingIdentity]:
        """표시명 그룹 하나에 속한 offering 전부(0개, 1개, 또는 그 이상). 이
        목록이 2개 이상이어도 오류가 아니다 — 그것이 바로 이 Repository가
        존재하는 이유다(§2, 16 Group 32행)."""

        return [o for o in self._offerings if o.display_group_id == display_group_id]

    def by_old_department_id(self, old_department_id: str) -> list[DepartmentOfferingIdentity]:
        """기존(v1) department_id 하나가 새 Identity v2에서 몇 개의 offering
        으로 갈라졌는지 조회한다(Migration Map과 같은 질문을 Repository
        레벨에서도 답할 수 있게 한다)."""

        return [o for o in self._offerings if o.old_department_id == old_department_id]
