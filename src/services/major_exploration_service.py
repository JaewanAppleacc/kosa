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

from src.data.majors.canonical_major_descriptions import CANONICAL_MAJOR_DESCRIPTIONS_BY_ID
from src.repositories.protocols import DepartmentRepository
from src.schemas.major import Department
from src.schemas.mcp_contracts import DepartmentSearchCriteria
from src.services.department_recommendation_scope import DepartmentRecommendationScopePolicy

# §17: Canonical Mapping·학과 상태 이력 중 "지금 지원 가능한 학과"로 보여줘도 되는 상태만
# 일반 탐색 결과에 노출한다. MERGED/SPLIT/ABOLISHED는 과거·통합·폐지 이력이라 이번
# Vertical Slice(학과 탐색 1단계) 범위에서는 제외한다 — 이력 조회는 후속 통합 단계다.
VISIBLE_DEPARTMENT_STATUSES = frozenset({"EXISTING", "NEW"})

# 2026-08-25 지시서 §5: 전국 학과 1,072건 승격 후 Major별 최대 학과 수는
# business_administration 271건이다 — 기존 30은 결과를 조용히 잘라낸다(공개 API
# 계약은 그대로 두고 노출 개수 한도만 넉넉하게 올린다).
DEFAULT_DEPARTMENT_LIMIT = 500

# 2026-08-22 9차: 사용자가 프로젝트 범위를 확정 — 예체능 계열(음악·미술·회화·조소,
# 시각/산업/커뮤니케이션 디자인, 실기 중심 패션디자인, 연극·영화·무용, 체육 실기 계열,
# 예술대학·미술대학·디자인대학·체육대학 소속 학과)은 교육과정에 다른 근거(예: UX)가
# 있어도 추천·탐색 대상에서 제외한다. `design` Canonical Major는 정의상 예체능(디자인)
# 계열이라 통째로 제외한다 — 관심 Context(미술·디자인 등)는 그대로 유지하고 Shared
# Trait 추출에는 계속 쓴다(§16 "관심 Context와 추천 학과 범위는 별개다"). 학과명
# 문자열로 개별 학과를 자동 분류하는 방식은 쓰지 않는다 — major_id 단위의 명시적
# 제외 집합만 쓴다(Canonical Mapping·Repository 데이터는 그대로 두고 노출만 막는다).
EXCLUDED_RECOMMENDATION_MAJOR_IDS = frozenset({"design"})

# 2026-08-24 national-department-readiness Harness §6-2: EXCLUDED_RECOMMENDATION_MAJOR_IDS
# 하나만으로는 "새로 생긴 major_id"를 못 막는다 — A-1 Canonical Major Group Bridge가
# 42개 초안 중 예체능 4개(fine_arts_design/music/performing_media_arts/sports_dance)를
# 나중에 실제 canonical_major_id로 승격해도, 그 4개는 이 제외 집합에 없으므로 그대로
# 노출됐다(예체능 제외가 "집합 안"에는 Fail-Closed, "집합 밖의 새 항목"에는 Fail-Open).
# 그래서 방향을 뒤집는다 — "알려진 나쁜 것만 막기"가 아니라 "허용된 것만 통과"다.
# 허용 집합의 정본은 `data/master/canonical_majors.jsonl`(10개 서비스 추천 전공)
# 하나뿐이다 — `CANONICAL_MAJOR_DESCRIPTIONS_BY_ID`가 모듈 import 시점에 그 파일을
# 이미 한 번만 읽어 뒀으므로(A3 지시서 §1) 여기서 파일을 다시 읽지 않고 그 key
# 집합을 그대로 재사용한다. `data/canonical_major_groups.draft.jsonl`(42개 Group)과
# `canonical_major_group_bridge.draft.jsonl`은 둘 다 review_status="draft"라 이
# 허용 집합에 전혀 들어오지 않는다 — Bridge가 실제로 승인되기 전까지 Group ID는
# 이 Service를 통해 학과를 조회할 수 없다.
DEFAULT_SERVICE_MAJOR_IDS: frozenset[str] = frozenset(CANONICAL_MAJOR_DESCRIPTIONS_BY_ID)

# Repository.search()가 상태 필터를 모르므로, 먼저 이 major_id에 걸리는 후보를 넉넉히
# 받아온 뒤(현재 시연 데이터는 학과 30개뿐이라 사실상 "전부") 여기서 상태로 거르고 다시
# limit을 적용한다 — 그래야 "상태 필터링 때문에 결과가 실제보다 적게 나오는" 일이 없다.
_CANDIDATE_OVERFETCH_LIMIT = 10_000


class MajorExplorationService:
    """대표 전공(major_id) 하나에 실제로 연결된 학과 목록을, 노출 정책에 맞게 걸러
    결정론적 순서로 반환한다.

    2026-08-22 10차: `EXCLUDED_RECOMMENDATION_MAJOR_IDS`(major_id 통째로 차단)만으로는
    "다른 major_id로 잘못 Mapping된 예체능 학과"를 못 막는다 — 그래서 `major_id`가
    `fail_closed_major_ids`(실제로 추천 가능한 대표 전공들, 지금은 VERTICAL_SLICE_
    MAJOR_PROFILES의 3개)에 속하면 학과(department_id) 단위로
    `recommendation_scope_policy.is_approved(department_id, canonical_major_id=major_id)`
    가 명시적으로 APPROVED라고 확인해 준 것만 통과시킨다(Fail-Closed — 검토 기록이
    없거나 다른 전공으로 검토된 기록이면 거부). 2026-08-22 11차: department_id만으로
    판정하지 않는다 — 같은 학과가 나중에 다른 major_id로 잘못 Mapping돼도 그 조합이
    실제로 검토·승인된 적이 있는지까지 확인해야 하기 때문이다(요청 major_id ==
    Department.canonical_major_id == ScopeRecord.canonical_major_id 세 값이 전부
    같아야 통과한다). `fail_closed_major_ids` 밖의 major_id(예: computer_science)는
    이번 MVP 범위 밖이라 기존 동작(상태·출처 필터만) 그대로 유지한다 — 전국 학과 전체
    예체능 분류는 후속 확장이다.

    2026-08-24 national-department-readiness Harness §6-2 수정: 위 두 방어선보다도
    먼저, `major_id`가 `allowed_major_ids`(기본값 DEFAULT_SERVICE_MAJOR_IDS =
    canonical_majors.jsonl의 10개 major_id)에 없으면 무조건 빈 목록이다. 42개
    Canonical Major Group ID(`data/canonical_major_groups.draft.jsonl`)와 Bridge
    draft(`canonical_major_group_bridge.draft.jsonl`)는 review_status="draft"인
    동안 이 허용 집합에 들어오지 않는다 — 사람이 실제로 승인하기 전까지 42개 Group
    이름으로는 이 Service를 통해 학과를 조회할 수 없다."""

    def __init__(
        self,
        department_repository: DepartmentRepository,
        recommendation_scope_policy: DepartmentRecommendationScopePolicy | None = None,
        fail_closed_major_ids: frozenset[str] = frozenset(),
        allowed_major_ids: frozenset[str] | None = None,
    ) -> None:
        self._department_repository = department_repository
        self._recommendation_scope_policy = recommendation_scope_policy
        self._fail_closed_major_ids = fail_closed_major_ids
        # None이면 DEFAULT_SERVICE_MAJOR_IDS(canonical_majors.jsonl 10개)를 쓴다 — 이
        # 매개변수를 생략해도 42개 Group ID 직접 조회가 자동으로 막힌다(안전한 기본값).
        self._allowed_major_ids = allowed_major_ids if allowed_major_ids is not None else DEFAULT_SERVICE_MAJOR_IDS

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
        상관없는 학과까지 전부 반환되는 사고를 막는다.

        2026-08-22 9차: `major_id`가 EXCLUDED_RECOMMENDATION_MAJOR_IDS(예: design)에
        속하면 기존 "매칭되는 학과 없음"과 동일하게 200 + 빈 목록을 반환한다 — 새로운
        오류나 API 계약 변경 없이, 이미 있는 "미등록 major_id" 응답 형태를 그대로
        재사용한다. Repository의 실제 데이터는 그대로 두고 노출만 막는다."""

        # 2026-08-24 Harness §6-2 수정: EXCLUDED_RECOMMENDATION_MAJOR_IDS(알려진 나쁜
        # 것만 막기)만으로는 42개 Canonical Major Group ID(예: fine_arts_design) 같은
        # "허용 목록에 없는 새 ID"를 못 막는다 — `major_id not in self._allowed_major_ids`
        # 를 함께 확인해 허용된 서비스 Major ID만 통과시킨다(Fail-Closed).
        if (
            not major_id
            or limit <= 0
            or major_id in EXCLUDED_RECOMMENDATION_MAJOR_IDS
            or major_id not in self._allowed_major_ids
        ):
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
            # Repository가 criteria.canonical_major_id 필터를 무시하는 오작동을 해도
            # (교체·버그 가능성) 여기서 다시 허용 집합을 확인한다 — major_id 자체는
            # 위에서 이미 걸렀지만, 이 줄은 그 가정이 깨져도 마지막 노출 시점에 한 번
            # 더 막는 방어선이다.
            and d.canonical_major_id in self._allowed_major_ids
            and d.department_status in VISIBLE_DEPARTMENT_STATUSES
            and d.source_url.strip()
        ]

        # 2026-08-22 10차: 실제로 추천 가능한 대표 전공(fail_closed_major_ids)이면, 학과
        # 하나하나가 사람이 공식 자료로 검토해 APPROVED라고 확정한 것인지 다시 확인한다
        # (Fail-Closed) — Repository가 canonical_major_id를 정확히 채워도, 그 Mapping
        # 자체가 예체능 학과를 잘못 담고 있을 수 있어 major_id 필터만으로는 못 막는다.
        if major_id in self._fail_closed_major_ids:
            policy = self._recommendation_scope_policy
            visible = [
                d
                for d in visible
                if policy is not None and policy.is_approved(d.department_id, major_id)
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
