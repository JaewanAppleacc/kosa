"""임시 In-Memory Course Planning Store — 2026-08-26 16차 리뷰, 설계안 §20 보조.

`src/memory/session_store.py`(§22 Session/Profile Store)와 같은 성격의 자리표시자다.
서버 재시작하면 다 날아간다 — DB 저장소로 교체할 때는 `save`/`load` 시그니처만 유지하면
Service·API 코드는 안 바뀐다.

**AssessmentState와 완전히 분리된 저장소다.** Assessment 질문 Planner는 이 Store에
전혀 접근하지 않는다(CLAUDE.md "Assessment 단계에서 전공 추천 결과나 성적을 Planner
입력으로 사용하지 않는다") — `src/engines/policy_guard.py::guard_no_major_signal_in_
assessment_state`가 AssessmentState 필드 목록만 검사하므로, 이 Store가 완전히 별도
클래스·모듈로 존재하는 것 자체가 그 불변식을 구조적으로 지키는 방법이다.
"""

from __future__ import annotations

from typing import Protocol

from src.schemas.course import CoursePlanningSessionState


class CoursePlanningStore(Protocol):
    def save(self, state: CoursePlanningSessionState) -> None: ...

    def load(self, session_id: str) -> CoursePlanningSessionState | None: ...


class InMemoryCoursePlanningStore:
    def __init__(self) -> None:
        self._states: dict[str, CoursePlanningSessionState] = {}

    def save(self, state: CoursePlanningSessionState) -> None:
        # §4: 새 파일을 다시 업로드하면 이전 미확정 결과를 명시적으로 교체한다 —
        # 병합하지 않고 session_id 키의 값을 통째로 덮어쓴다.
        self._states[state.session_id] = state

    def load(self, session_id: str) -> CoursePlanningSessionState | None:
        return self._states.get(session_id)
