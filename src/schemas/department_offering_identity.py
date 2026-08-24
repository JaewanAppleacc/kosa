"""Department Offering Identity v2 — 2026-08-25 지시서
(a/offering-identity-v2) §2.

표시명(schl_id+college_name+department_name) 하나에 실제로는 서로 다른 두
편제(일반과정/계약학과, 또는 산업체위탁)가 동시에 걸릴 수 있다는 사실이
department_id identity-key 충돌 감사(16 Group·32행,
`department_identity_collision_review.jsonl`)에서 확인됐다. 이 Schema는 그
문제를 구조적으로 푸는 세 축을 정의한다.

1. `offering_id` — 원천 편제 단위 유일 키. `(provider, schl_id,
   source_schl_mjr_id)`로 만든다(`src.ids.generate_offering_id`). 새
   Repository(`department_offering_repository.py`)의 유일 키가 이 값이다.
2. `display_group_id` — 검색·UI 그룹화 전용. `(schl_id, college_name,
   department_name)` 3-tuple(기존 department_id와 같은 재료)로 만들되
   (`src.ids.generate_display_group_id`), Repository의 유일 키나
   department_id로 쓰면 안 된다 — 표시명이 같다는 이유만으로 서로 다른
   편제를 병합하지 않는다.
3. `stable_lineage_id` — 연도 간 동일 편제 판단. 검증된 연결 근거가 있을
   때만 채워진다(`src.ids.generate_offering_lineage_id`, 기본값 None). 이번
   라운드는 2025년 한 해 데이터만 다뤄 실제 값을 계산하지 않는다 — Schema와
   계산 규칙만 갖춘다(§2 "source_schl_mjr_id가 같다는 사실만으로 무조건
   동일 편제라고 단정하지 않음").

기존 `department_id`(`src.ids.generate_department_id`)는 이 Schema가 절대
바꾸지 않는다 — Master 35건은 여전히 그 값을 그대로 쓴다(§5 "기존 35건 즉시
교체 금지"). `old_department_id` 필드로 그 값을 그대로 보존해 Migration
Map과 연결한다.

`major_character_name`/`course_term`은 감사·Fallback 구분 정보로 보존하되,
원천 ID가 존재하는 행에서는 영구 ID(`offering_id`)의 핵심 재료로 쓰지
않는다(§2) — 이미 `offering_id` 계산에서 `source_schl_mjr_id`만 쓰고
`major_character`는 관여하지 않는다는 사실로 코드 구조 자체가 이를
보장한다."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator

MajorCharacter = Literal["일반과정", "계약학과", "산업체위탁"]
DepartmentStatus = Literal["EXISTING", "NEW", "MERGED", "SPLIT", "ABOLISHED"]


class DepartmentOfferingIdentity(BaseModel):
    """편제 하나(=원본 행 하나)의 Identity v2 식별자 묶음. `offering_id`가
    유일 키다(`JsonlDepartmentOfferingRepository`가 이 값 기준으로 중복을
    Fail-Fast 검증한다)."""

    offering_id: str
    display_group_id: str
    stable_lineage_id: str | None = None
    provider: str
    schl_id: str
    source_schl_mjr_id: str
    source_record_id: str
    source_svy_year: int
    old_department_id: str
    university_name: str
    college_name: str
    department_name: str
    major_character: MajorCharacter
    department_status: DepartmentStatus

    @field_validator(
        "offering_id", "display_group_id", "provider", "schl_id", "source_schl_mjr_id",
        "source_record_id", "old_department_id", "university_name", "college_name", "department_name",
    )
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("빈 값은 허용하지 않는다")
        return value

    @property
    def key(self) -> str:
        return self.offering_id
