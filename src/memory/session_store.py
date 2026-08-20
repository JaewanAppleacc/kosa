"""임시 In-Memory Session/Profile Store.

**이건 §22 Long-term Profile Store의 최종 구현이 아니다.** 실제 구현은 PostgreSQL 기반이어야
하고(§22: "user_id 기반 실제 Store를 구현한다"), 이 클래스는 서버 재시작하면 다 날아간다.
지금은 API 계약(Endpoint가 어떤 모양으로 세션을 주고받는지)을 B에게 먼저 보여주기 위한
자리표시자다. CLAUDE.md: "임시 Mock과 실제 구현을 명확히 구분한다."

DB로 교체할 때는 이 클래스가 구현하는 메서드 시그니처(save/load/list_by_user)만 그대로
유지하면 API 코드는 안 바뀐다.
"""

from __future__ import annotations

from src.schemas.assessment_state import AssessmentState


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, AssessmentState] = {}

    def save(self, state: AssessmentState) -> None:
        self._sessions[state.session_id] = state

    def load(self, session_id: str) -> AssessmentState | None:
        return self._sessions.get(session_id)

    def list_by_user(self, user_id: str) -> list[AssessmentState]:
        return [s for s in self._sessions.values() if s.user_id == user_id]
