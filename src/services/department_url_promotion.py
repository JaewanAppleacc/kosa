"""Department URL 승격 준비 — A-2 지시서(integration/academyinfo-pipeline,
2026-08-24) §1/§6.

전국 데이터를 실제 `data/master/departments.jsonl`로 승격하는 Builder는 아직 없다
(§3 "Master 승격 보류"). 이 모듈은 그 Builder가 나중에 생겼을 때 반드시 따라야 할
`department_url` 결정 규칙을 지금 고정해 둘 뿐이다 — 이번 라운드에서 현재 시연
Master(35개)를 재생성하거나 그 URL을 바꾸지 않는다.

규칙(A 결정사항 §1 "학과 홈페이지 URL"):
- `department_url_scope == "department"`(원본이 실제 그 학과 홈페이지를 가리킴)만
  공개 `Department.department_url`로 넘긴다.
- `department_url_scope == "college"`(원본이 단과대학 홈페이지 — 실제 3건)는 URL이
  있어도 공개 값은 항상 `None`이다. 단과대학 URL을 학과 공식 홈페이지로 위장하지
  않는다(`src/schemas/major.py::Department.department_url`의 기존 검증 규칙과
  같은 정신 — "대학 메인 홈페이지·연구실·미디어센터를 학과 홈페이지로 위장하지
  않는다").
- 단과대학 URL과 그 이유(note)는 이 함수가 버리지 않는다 — 호출자가 내부 Raw/Audit
  레코드에 그대로 남겨야 한다(공개 Department 객체에만 넣지 않을 뿐이다)."""

from __future__ import annotations

from typing import Literal

DepartmentUrlScope = Literal["department", "college"]


def resolve_department_url_for_promotion(
    department_url_scope: DepartmentUrlScope, validated_department_url: str | None,
) -> str | None:
    """공개 `Department.department_url`에 실제로 넣을 값을 계산한다.

    `validated_department_url`은 이미 `Department.department_url`의 field_validator
    (http/https만, API Key 쿼리 파라미터 금지 등)를 통과한 값이어야 한다 — 이 함수는
    URL 형식 자체를 다시 검증하지 않고 오직 scope 규칙만 적용한다."""

    if department_url_scope == "department":
        return validated_department_url
    return None
