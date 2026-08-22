"""AdmissionRepository 구현 (작업자 C 소유) — 설계안 §18.

A의 `AdmissionRepository` Protocol을 만족한다. 정책은 전부
`src/engines/admission_filter.py`에 있고 이 파일은 저장소 읽기 + 그 정책 적용만 한다.

## 계약 해석 한 가지 — A 확인 요청

Protocol의 `find_comparable()`은 반환 타입이 `list[AdmissionReference]` 하나인데,
docstring은 "비교 가능한 자료끼리만 묶어서 **여러 그룹을 반환**한다"고 적혀 있다.
평평한 리스트 하나로 여러 그룹을 담으면 곧바로 "서로 다른 그룹을 하나의 리스트로 섞어서
반환하지 않는다"는 뒤 문장과 충돌한다.

C는 **섞지 않는다** 쪽을 지켰다.

- `find_comparable()`은 **항상 한 그룹만** 반환한다. `criteria.data_comparability_group`이
  주어지면 그 그룹, 없으면 가장 최근 학년도의 그룹.
- 여러 그룹을 봐야 하는 호출자를 위해 `find_comparable_groups()`를 따로 뒀다. 이건
  Protocol에 없는 추가 메서드라 A의 코드에는 영향이 없다.

Protocol을 바꿔야 한다면 A가 결정한다 — C가 Schema·Protocol을 직접 고치지 않는다(지시서 §7).
"""

from __future__ import annotations

import json
from pathlib import Path

from src.engines.admission_filter import (
    assert_single_group,
    group_by_comparability,
    select_group,
)
from src.schemas.major import AdmissionReference
from src.schemas.mcp_contracts import AdmissionSearchCriteria

DEFAULT_MASTER_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "admissions" / "admission_references.jsonl"
)


def load_admission_references(path: Path | None = None) -> list[AdmissionReference]:
    source = path or DEFAULT_MASTER_PATH
    if not source.exists():
        return []
    return [
        AdmissionReference.model_validate(json.loads(line))
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class JsonlAdmissionRepository:
    def __init__(
        self,
        references: list[AdmissionReference] | None = None,
        path: Path | None = None,
    ) -> None:
        self._references = (
            references if references is not None else load_admission_references(path)
        )
        self._by_department: dict[str, list[AdmissionReference]] = {}
        for reference in self._references:
            self._by_department.setdefault(reference.department_id, []).append(reference)

    def __len__(self) -> int:
        return len(self._references)

    def has_department(self, department_id: str) -> bool:
        """자료가 아예 없는 학과와 "조건에 맞는 자료가 없는" 학과를 구분하기 위한 것.

        MCP Tool이 `empty`와 `source_missing` 중 무엇을 반환할지 이 값으로 가른다.
        """

        return department_id in self._by_department

    def find_comparable(self, criteria: AdmissionSearchCriteria) -> list[AdmissionReference]:
        """항상 한 그룹만 반환한다 (파일 상단 계약 해석 참고)."""

        candidates = self._candidates(criteria)
        if not candidates:
            return []
        _, rows = select_group(candidates, criteria.data_comparability_group)
        assert_single_group(rows)
        return sorted(rows, key=lambda r: (r.department_id, r.admission_track))

    def find_comparable_groups(
        self, criteria: AdmissionSearchCriteria
    ) -> dict[str, list[AdmissionReference]]:
        """Protocol 밖의 보조 메서드 — 그룹별로 나눠서 전부 돌려준다."""

        grouped = group_by_comparability(self._candidates(criteria))
        return {
            name: sorted(rows, key=lambda r: (r.department_id, r.admission_track))
            for name, rows in sorted(grouped.items())
        }

    def available_groups(self, department_id: str) -> list[str]:
        return sorted(
            {r.data_comparability_group for r in self._by_department.get(department_id, [])}
        )

    def _candidates(self, criteria: AdmissionSearchCriteria) -> list[AdmissionReference]:
        rows = self._by_department.get(criteria.department_id, [])
        if criteria.admission_year is not None:
            rows = [r for r in rows if r.admission_year == criteria.admission_year]
        return rows
