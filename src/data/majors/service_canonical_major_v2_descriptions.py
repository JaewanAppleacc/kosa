"""Service Canonical Major v2 설명 정본 — 2026-08-25 지시서
(a/major-profiles-v2-38).

`src/data/majors/canonical_major_descriptions.py`(Legacy 10개 Canonical Major)와
같은 원칙("`MajorRelevance.description`을 만드는 모든 v2 호출부는 이 딕셔너리
하나만 참조한다")을 39개 Service Canonical Major v2 Catalog에 적용한다. Legacy와
v2는 이제 서로 다른 Major 집합(10개 대 39개)을 다루므로 하나의 딕셔너리를 공유할
수 없다 — 억지로 공유하면 v2의 새 36개 Major에서 `MissingMajorDescriptionError`가
난다.

`data/master/service_canonical_majors_v2.jsonl`(정본)에서 모듈 import 시점에
결정론적으로 한 번만 읽는다. `rank_major_relevance_v2()`를 호출하는 모든 v2
호출부(`main.py`, `course_planning_service_v2.py`)는 반드시 이 딕셔너리만
참조한다."""

from __future__ import annotations

from src.services.service_canonical_major_v2_loader import load_service_canonical_majors_v2

SERVICE_CANONICAL_MAJOR_V2_DESCRIPTIONS_BY_ID: dict[str, str] = {
    entry.major_id: entry.description for entry in load_service_canonical_majors_v2()
}
