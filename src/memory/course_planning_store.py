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
        # 2026-08-27 17차 리뷰 §5: 방어적 깊은 복사. 호출자가 넘긴 객체 참조를 그대로
        # 들고 있으면, 저장 뒤 호출자가 그 객체를 손으로 고칠 때 Store 값까지 같이
        # 바뀌어버린다(Confirm 원자성이 이 위에서 성립하므로, Store 내부 상태가 외부
        # 코드에 의해 몰래 바뀌지 않는다는 보장이 필요하다).
        self._states[state.session_id] = state.model_copy(deep=True)

    def load(self, session_id: str) -> CoursePlanningSessionState | None:
        # 2026-08-27 17차 리뷰 §5: 반환값도 깊은 복사본이다 — 호출자가 load()로 받은
        # 객체를 자유롭게 수정해도, 그 시점에 save()를 다시 부르기 전까지는 Store 원본이
        # 절대 바뀌지 않는다.
        state = self._states.get(session_id)
        return state.model_copy(deep=True) if state is not None else None
