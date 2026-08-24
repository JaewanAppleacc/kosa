# Canonical Major Group Bridge Scope — Migration/Audit 문서

2026-08-24, `a/canonical-major-bridge-scope` 지시서. A-1의 B·C 통합 작업과 병렬로
진행한 작업이며, `origin/trait-vector-v2` 최신 커밋(`a3781f5`)을 기준으로 별도
브랜치에서만 진행했다.

## 1. 왜 이 작업이 필요했는가

기존 44개 Canonical Major Group Bridge Draft는 "이 Group과 이 Major를 연결해도
되는가"(`mapping_status`)만 답했다. 사람 검수 결과(단일 검토자, APPROVE 38 /
REVISE 6) 중 REVISE 6건은 전부 "연결 자체는 맞지만, Group 전체를 그대로 쓰면
범위가 너무 넓다"는 같은 종류의 문제를 지적했다 — 예를 들어 `business` Group은
경영학·경영정보학·비서·금융보험학·회계세무학 5개 공식 소계열(1,424개 학과)을
묶은 것인데, `business_administration` Major에는 그중 '경영학' 소계열 학과만
경영학 추천 후보로 적절하다.

## 2. 추가한 Scope Schema

`src/schemas/canonical_major_group_bridge.py`의 `CanonicalMajorGroupBridgeEntry`에
5개 필드를 Additive로 추가했다(기존 7개 필드는 이름·타입·의미 전부 그대로):

| 필드 | 타입 | 의미 |
|---|---|---|
| `scope_type` | `Literal["FULL_GROUP", "INCLUDED_SMALL_SERIES_ONLY", "DEPARTMENT_REVIEW_REQUIRED", "EXCLUDED_RECOMMENDATION"] \| None` | Group 전체/소계열 일부/학과 개별 검토/추천 후보 아님 |
| `included_small_series_codes` | `list[str]` | `INCLUDED_SMALL_SERIES_ONLY`일 때만 채우는, 포함 범위 소계열 코드(공식 3자리 코드) |
| `excluded_small_series_codes` | `list[str]` | 감사용 — 왜 뺐는지 명시적으로 남기는 제외 소계열 코드 |
| `scope_decision_reason` | `str` | Scope를 이렇게 정한 이유 |
| `scope_review_status` | `Literal["draft", "approved"]` | 이 Scope 값 자체를 사람이 검토했는지(기존 `review_status`와 별개 축) |

## 3. 상태별 검증 규칙

**Schema 계층(`CanonicalMajorGroupBridgeEntry._scope_field_consistency`, 행 단위)**

- `UNMAPPED` → `scope_type`은 반드시 `None`(연결 대상이 없어 범위 자체가 성립하지 않음).
- `EXCLUDED_RECOMMENDATION` ↔ `scope_type == "EXCLUDED_RECOMMENDATION"` — 양방향 1:1 강제.
- `EVIDENCED`/`REVIEW_REQUIRED` → `scope_type`이 반드시 있어야 함(범위 미정 금지).
- `included`/`excluded` 소계열 코드 목록: 공백·중복 금지(field_validator), 두 목록 간 교집합 금지.
- `scope_type == "FULL_GROUP"` → `included`/`excluded` 둘 다 비어 있어야 함.
- `scope_type == "INCLUDED_SMALL_SERIES_ONLY"` → `included_small_series_codes`가 최소 1개.

**Loader 계층(`canonical_major_group_bridge_loader.py`, 파일 전체·다른 정본과 대조)**

- 코드가 실제 대학알리미 158개 공식 소계열 코드표(`data/academyinfo_raw/2025/codes/
  getCodeBySmallSeries.jsonl.gz`)에 존재하는가.
- 코드가 그 행이 속한 Group 자신의 `included_official_small_series_codes` 부분집합인가
  (다른 Group의 코드를 잘못 넣는 실수 차단 — 지시서에 명시되지 않았지만 방어적으로 추가).
- **Schema 우회 방어**: `validate_bridge_scope_row()`(순수 함수)가 위 행 단위 규칙
  전부를 Pydantic 검증에 의존하지 않고 다시 확인한다. `model_construct()`로 Pydantic
  검증을 건너뛴 값도 이 함수가 잡는다 — 실제로
  `tests/test_canonical_major_group_bridge_scope.py::SchemaBypassDefenseTest`가
  `model_construct()`로 모순된 값(FULL_GROUP인데 코드가 있음)을 만들고, 그 값이
  예외 없이 만들어진다는 것과 `validate_bridge_scope_row()`가 그래도 거부한다는 것을
  둘 다 확인한다.
- 오류 메시지는 `group_id`/`major_id`/코드값만 담고, 질문 원문·사용자 데이터·API Key는
  이 Loader가 다루는 데이터 자체에 존재하지 않는다(순수 분류 메타데이터).
- `DEPARTMENT_REVIEW_REQUIRED`는 Group 전체 자동 승격을 막는다 — Runtime 소비자가
  아직 없으므로(§4 "Runtime 미연결") 지금은 "이 값을 Group 전체 승인으로 해석하는
  코드가 없다"가 곧 그 보장이다. 나중에 Runtime이 이 필드를 읽게 되면 그 소비 코드가
  `scope_type in ("FULL_GROUP", "INCLUDED_SMALL_SERIES_ONLY")`일 때만 후보를 만들고
  `DEPARTMENT_REVIEW_REQUIRED`/`EXCLUDED_RECOMMENDATION`은 항상 건너뛰어야 한다 — 이
  계약을 위 표와 테스트로 고정해뒀다.
- `EXCLUDED_RECOMMENDATION`은 Schema가 `mapping_status`와의 1:1 대응을 강제하므로
  "추천 후보 생성에 사용할 수 없음"이 이미 기존 `mapping_status == EXCLUDED_RECOMMENDATION`
  Fail-Closed 정책(예체능 4개 Group)과 같은 강도로 보장된다.

## 4. 공식 소계열 코드 확인 방법

**추측하지 않고 원본 코드표에서 직접 찾았다.** 대학알리미 표준분류 소계열 158개
공식 코드표는 `data/academyinfo_raw/2025/codes/getCodeBySmallSeries.jsonl.gz`
(`{cdid, cdnm}` 158행)이며, 이미 `data/canonical_major_groups.draft.jsonl`(worker-c
산출물)이 참조하는 바로 그 정본이다. 확인 절차:

```python
import gzip, json
with gzip.open("data/academyinfo_raw/2025/codes/getCodeBySmallSeries.jsonl.gz", "rt", encoding="utf-8") as f:
    rows = [json.loads(l) for l in f if l.strip()]
# {'cdid': '033', 'cdnm': '경영학'} 처럼 정확히 158행이 나온다.
```

이름이 여러 코드에 대응하는지도 확인했다 — 158개 전부 `cdnm`이 유일했다(중단할
모호 사례 없음). 각 REVISE 대상 Group의 `included_official_small_series_codes`
(그 Group에 실제로 속한 소계열)와 대조해, 지시서가 지목한 한글 명칭이 정확히
어느 코드인지 1:1로 확인했다:

| 명칭 | 코드 | 소속 Group |
|---|---|---|
| 경영학 | 033 | business |
| 경영정보학 | 035 | business |
| 비서 | 041 | business |
| 금융·보험학 | 151 | business |
| 회계·세무학 | 152 | business |
| 교육학 | 042 | education |
| 언어교육 | 043 | education |
| 초등교육 | 046 | education |
| 유아교육 | 154 | education |
| 특수교육 | 155 | education |
| 산업공학 | 102 | industrial_engineering |
| 안전공학 | 103 | industrial_engineering |
| 방재공학 | 104 | industrial_engineering |
| 기계공학 | 078 | mechanical_transport |
| 조선·해양공학 | 080 | mechanical_transport |
| 항공·우주공학 | 081 | mechanical_transport |
| 철도공학 | 082 | mechanical_transport |
| 자동차공학 | 083 | mechanical_transport |

**"명칭이 여러 코드에 대응하면 중단하고 보고" 조건은 발생하지 않았다** — 위 18개
명칭 전부 코드표에서 유일하게 일치했다.

## 5. REVISE 6건의 최종 Scope

| Group → Major | scope_type | included | excluded |
|---|---|---|---|
| business → business_administration | INCLUDED_SMALL_SERIES_ONLY | 033(경영학) | 035, 041, 151, 152 |
| education → education | INCLUDED_SMALL_SERIES_ONLY | 042(교육학) | 043, 046, 154, 155 |
| industrial_engineering → industrial_engineering | INCLUDED_SMALL_SERIES_ONLY | 102(산업공학) | 103, 104 |
| mechanical_transport → mechanical_engineering | INCLUDED_SMALL_SERIES_ONLY | 078(기계공학) | 080, 081, 082, 083 |
| bio_medical_engineering → life_science | DEPARTMENT_REVIEW_REQUIRED | (없음) | (없음) |
| computer_science → hci_ux | DEPARTMENT_REVIEW_REQUIRED | (없음) | (없음) |

`bio_medical_engineering`/`computer_science → hci_ux`는 소계열 단위로도 확정할 수
없다는 지시서 근거(의공학은 응용 공학으로 별도 유지, HCI·UX에 정확히 대응하는
공식 코드 없음)를 그대로 반영해 `DEPARTMENT_REVIEW_REQUIRED`로 두고
included/excluded 코드를 비워뒀다 — 학과 개별 교육과정 검토가 필요하다는 뜻을
소계열 코드로 흉내 내지 않는다.

**나머지 38개 APPROVE 행**은 재해석하지 않았다 — `mapping_status`에서 기계적으로
결정되는 기본값만 채웠다: EVIDENCED/REVIEW_REQUIRED(REVISE 대상 아님) 4건은
`FULL_GROUP`, EXCLUDED_RECOMMENDATION 5건은 `scope_type=EXCLUDED_RECOMMENDATION`,
UNMAPPED 29건은 `scope_type=None`.

**44행 전부 `scope_review_status="draft"`다** — 기존 `reviewer_1_status`
(APPROVE/REVISE)를 이 새 필드의 승인 상태로 자동 복사하지 않았다. REVISE 판정이
요구한 것은 "Scope를 좁혀라"이지 "이 Scope 값을 승인한다"가 아니기 때문이다.

## 6. 44개 Mapping 상태 보존 결과

| mapping_status | 이전 | 이후 |
|---|---|---|
| EVIDENCED | 8 | 8 |
| REVIEW_REQUIRED | 2 | 2 |
| EXCLUDED_RECOMMENDATION | 5 | 5 |
| UNMAPPED | 29 | 29 |
| **합계** | 44 | 44 |

기존 필드(`mapping_status`/`evidence`/`decision_reason`/`boundary_notes`/
`review_status`/`reviewer_id`/`reviewed_at`) 값과 JSON 키 순서는 44행 전체에서
byte 단위로 그대로다 — 새 5개 필드만 각 행 끝에 추가됐다(프로그램적으로 검증,
`tests/test_canonical_major_group_bridge_scope.py`).

## 7. 수정/추가 파일

- `src/schemas/canonical_major_group_bridge.py` — Scope 필드 5개 + 검증 규칙 추가(Additive).
- `src/services/canonical_major_group_bridge_loader.py` — 공식 코드표 Loader
  (`load_official_small_series_codes`), 방어 검증 함수(`validate_bridge_scope_row`),
  로더 본체에 Scope 교차 검증 통합.
- `scripts/career_add_canonical_major_group_bridge_scope.py`(신규) — 결정론적
  마이그레이션 스크립트. REVISE 6건 Scope는 지시서 원문을 그대로 하드코딩했고,
  `data/reviews/canonical_major_group_bridge_review_status.json`을 읽지 않는다.
- `scripts/career_generate_canonical_major_group_bridge_review.py` — 검수 Markdown에
  "4. Scope 상세" 절 추가(§2 표에도 Scope 열 추가).
- `data/master/canonical_major_group_bridge.draft.jsonl` — 44행에 Scope 필드 추가
  (마이그레이션 스크립트 실행 결과).
- `outputs/reviews/canonical_major_group_bridge_review.md` — 재생성.
- `tests/test_canonical_major_group_bridge.py` — 기존 3개 테스트가 새로 필수가 된
  `scope_type`을 넣도록 갱신, Schema 신규 검증 규칙 테스트 11개 추가.
- `tests/test_canonical_major_group_bridge_scope.py`(신규) — 이 작업 전용 테스트 44개.

## 8. 이 작업이 손대지 않은 것(안전 규칙 확인)

- `data/reviews/canonical_major_group_bridge_review_status.json` — 이 브랜치의 기준
  (`origin/trait-vector-v2` @ `a3781f5`)에는 이 파일이 아예 없다(A-1 B·C 통합
  브랜치에서 별도로 진행 중). 이 작업은 이 파일을 만들지도, 읽지도 않았다 —
  REVISE 6건 목록은 지시서 본문에서 직접 가져왔다.
- `src/repositories/department_repository.py`, `src/services/major_exploration_service.py`,
  `data/master/departments.jsonl` — 무변경(git diff 확인).
- `canonical_majors.jsonl`, `major_profiles_v2.jsonl` — 무변경.
- `outputs/mock_api/*`, OpenAPI 생성 결과 — 재생성 후 byte-identical.
- 전국 Master 승격·Runtime 연결 — 여전히 없음(`RuntimeNotWiredTest`로 확인, 기존
  Bridge 작업과 동일한 정책 계승).
- Department 4/3/1/0/10(media_communication/industrial_engineering/hci_ux/design/
  Major 총수) 결과 — 실제 `MajorExplorationService`로 재확인, 변화 없음.
- 프론트엔드 — 손대지 않음.

## 9. `trait-vector-v2` 병합 시 예상 충돌

- **높은 확률로 충돌**: `data/master/canonical_major_group_bridge.draft.jsonl`.
  A-1의 B·C 통합 작업이 같은 파일의 다른 부분(또는 44행 자체의 재작성)을 건드릴
  가능성이 크다 — 특히 A-1이 이미 committed한
  `data/reviews/canonical_major_group_bridge_review_status.json`(로컬 `trait-vector-v2`
  브랜치에는 있지만 이 작업 브랜치 기준인 `origin/trait-vector-v2`에는 없던 파일)이
  merge 시점에 함께 들어오면, 이 스크립트가 만든 Scope 값과 그 파일의 REVISE 판정이
  실제로 다시 대조돼야 한다. 병합 전략: Scope 5개 필드(이 작업)와 기존 7개 필드(A-1
  또는 그 이전 값) 양쪽을 행 단위로 합치는 수작업 병합이 필요할 가능성이 높다 —
  자동 병합에 맡기지 않는 것을 권장한다.
- **낮은 확률**: `src/schemas/canonical_major_group_bridge.py`,
  `src/services/canonical_major_group_bridge_loader.py` — A-1이 같은 파일의 다른
  영역(예: Group/Major 참조 검증 로직)을 동시에 수정했다면 충돌 가능성이 있다.
  이 작업은 기존 코드 블록을 삭제하지 않고 끝에 추가하는 방식이라 충돌이 나더라도
  해석은 쉬울 것으로 예상한다.
- **충돌 없음 예상**: `scripts/career_add_canonical_major_group_bridge_scope.py`
  (신규 파일), `tests/test_canonical_major_group_bridge_scope.py`(신규 파일) —
  A-1이 같은 이름의 파일을 만들지 않았다면 충돌 없이 그대로 추가된다.
- **권장 병합 순서**: A-1의 B·C 통합 브랜치가 먼저 `trait-vector-v2`에 들어간 뒤,
  이 브랜치를 그 위에 rebase하며 Bridge Draft 44행을 수작업으로 재대조하는 편이
  안전하다 — 두 작업 모두 같은 파일(Bridge Draft)의 서로 다른 축(연결 여부 vs
  범위)을 동시에 넓히고 있기 때문이다.
