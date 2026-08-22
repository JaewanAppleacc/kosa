"""Major Exploration Service — A 소유 통합 계층, 설계안 §18.

2026-08-22 7차: C의 Repository·RAG·MCP·데이터 구현이 `main`에 병합된 뒤 첫 번째 실제
연결 단계. 한 번에 전공·입결·RAG·과목을 전부 연결하지 않고, 다음 Vertical Slice
하나만 완성한다:

    검사 답변 → Career Profile → 대표 전공 추천 → DepartmentRepository 조회
    → 그 대표 전공과 연결된 학과 목록

CLAUDE.md 책임 분리:
- Repository(`src.repositories.department_repository`, C 소유)는 데이터 조회만 한다.
- 이 Service는 "어떤 조건으로 조회하고, 어떤 결과를 노출할지" 정책만 담당한다
  (상태 필터·정렬·개수 제한) — Repository 구현을 직접 손대지 않는다.
- FastAPI(`src.api.main`)는 요청·응답 변환만 한다.

이 Service가 반환하는 Department 목록은 "이미 확정된 대표 전공"에 딸린 참고 정보다.
Matching Engine(§16)이 계산한 전공 관련도나 Assessment 질문에 다시 입력되지 않는다
(단방향 흐름 — CLAUDE.md "Assessment 단계에서 전공 추천 결과나 성적을 Planner 입력으로
사용하지 않는다"와 같은 방향).
"""

from __future__ import annotations

from src.repositories.protocols import DepartmentRepository
from src.schemas.major import Department
from src.schemas.mcp_contracts import DepartmentSearchCriteria

# §17: Canonical Mapping·학과 상태 이력 중 "지금 지원 가능한 학과"로 보여줘도 되는 상태만
# 일반 탐색 결과에 노출한다. MERGED/SPLIT/ABOLISHED는 과거·통합·폐지 이력이라 이번
# Vertical Slice(학과 탐색 1단계) 범위에서는 제외한다 — 이력 조회는 후속 통합 단계다.
VISIBLE_DEPARTMENT_STATUSES = frozenset({"EXISTING", "NEW"})

DEFAULT_DEPARTMENT_LIMIT = 30

# Repository.search()가 상태 필터를 모르므로, 먼저 이 major_id에 걸리는 후보를 넉넉히
# 받아온 뒤(현재 시연 데이터는 학과 30개뿐이라 사실상 "전부") 여기서 상태로 거르고 다시
# limit을 적용한다 — 그래야 "상태 필터링 때문에 결과가 실제보다 적게 나오는" 일이 없다.
_CANDIDATE_OVERFETCH_LIMIT = 10_000


class MajorExplorationService:
    """대표 전공(major_id) 하나에 실제로 연결된 학과 목록을, 노출 정책에 맞게 걸러
    결정론적 순서로 반환한다."""

    def __init__(self, department_repository: DepartmentRepository) -> None:
        self._department_repository = department_repository

    def list_departments_for_major(
        self, major_id: str, limit: int = DEFAULT_DEPARTMENT_LIMIT
    ) -> list[Department]:
        """§17: `major_id`와 `Department.canonical_major_id`가 일치하는 학과만, 그 중에서도
        VISIBLE_DEPARTMENT_STATUSES에 속하고 `source_url`이 실제로 채워진 것만 반환한다.
        Repository.search()가 이미 이 조건 대부분을 걸러주지만, 이 메서드는 Repository
        구현을 신뢰하지 않고(교체·버그 가능성) 마지막 노출 시점에 4가지를 전부 다시
        검증한다 — canonical_major_id 정확히 일치, 상태 EXISTING/NEW, source_url이
        비어 있지 않음(공백만으로 구성된 값도 제외).

        `major_id`가 비어 있으면 빈 목록을 반환한다 — 빈 문자열을 Repository에 그대로
        넘기면 "필터 없음"으로 해석돼(criteria.canonical_major_id가 falsy) 아무 전공과도
        상관없는 학과까지 전부 반환되는 사고를 막는다."""

        if not major_id or limit <= 0:
            return []

        criteria = DepartmentSearchCriteria(canonical_major_id=major_id)
        candidates = self._department_repository.search(criteria, limit=_CANDIDATE_OVERFETCH_LIMIT)

        # 2026-08-22 8차 리뷰: 예전에는 Repository가 이미 canonical_major_id를 정확히
        # 걸러준다고 신뢰하고 여기서는 상태만 다시 확인했다 — Repository 구현이 바뀌거나
        # (JSONL → PostgreSQL 등) 버그로 다른 전공 학과가 섞여 와도 이 Service가 방어막
        # 없이 그대로 내보내는 구조였다. Repository를 신뢰하지 않고 이 Service의 마지막
        # 노출 시점에 4가지를 전부 다시 확인한다 — Repository 구현(C 소유)은 건드리지
        # 않고 Service의 "사용자에게 실제로 보여줄 것" 정책만 강화한다.
        visible = [
            d
            for d in candidates
            if d.canonical_major_id == major_id
            and d.department_status in VISIBLE_DEPARTMENT_STATUSES
            and d.source_url.strip()
        ]
        # 결정론적 정렬 — region → university_name → campus → department_name →
        # department_id. Repository 자체 정렬(university_name 우선)과 다른 이유는, 이건
        # "저장소 조회 순서"가 아니라 "학생에게 보여줄 노출 순서" 정책이라 Service가 정한다.
        visible.sort(
            key=lambda d: (
                d.region,
                d.university_name,
                d.campus or "",
                d.department_name,
                d.department_id,
            )
        )
        return visible[:limit]
