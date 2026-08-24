# 전국 학과 Department Repository/Service 승격 준비도 — 읽기 전용 진단

> 이 보고서의 25,389건은 합성(Synthetic) Fixture 실측이다 — 검증된 운영 Master가 아니다.

이 보고서는 `src/repositories/department_repository.py`·`src/services/major_exploration_service.py`를 **한 줄도 수정하지 않고** 관찰만 한 결과다. 발견된 결함은 코드로 고치지 않고 아래 목록에만 남겼다.

**재현성 범위**: 같은 seed로 만든 Fixture 분포·시나리오 통과/실패·발견된 결함 목록은 재실행해도 항상 같다(`comparable_snapshot()`로 별도 검증). 다만 Wall Time·메모리처럼 실제로 측정한 숫자는 실행마다 미세하게 달라질 수 있다 — 이 값을 고정값으로 조작하지 않고 매 실행의 실측 그대로 기록한다.

## 1. 데이터 크기

- 합성 Fixture 행 수: **25,389건**(실제 커밋된 `data/academyinfo_work/2025/normalization_report.json`의 `included_count` 기준)
- 상태 분포(합성, 실제 보고서 비율 그대로): {'ABOLISHED': 14965, 'EXISTING': 9292, 'NEW': 1041, 'MERGED': 56, 'SPLIT': 35}
- canonical_major_id 분포(상위 10개): {'(UNMAPPED)': 3820, 'foreign_language': 2263, 'fine_arts_design': 2152, 'sports_dance': 1691, 'business_administration': 1631, 'mechanical_engineering': 1474, 'psychology': 1410, 'economics': 1375, 'performing_media_arts': 1323, 'sociology': 1292}
- 주입한 중복 department_id 건수: **588건**(지시서 §3 "588개 중복 상당")

## 2. 초기 로드 시간·메모리

- 행 수: 25,389
- Wall Time: **0.3474초**
- Python 힙 Peak(tracemalloc): **62.45 MB**
- Python 힙 Current(로드 직후): 44.03 MB

## 3. 반복 조회 시간

**같은 major_id 100회 반복**
- 호출 100회 · 평균 2.053ms · 중앙값 2.023ms · p95 2.337ms · 최대 3.560ms · 총 0.2053초
- 100회 반복하는 동안 실제 `Path.read_text()` 호출 횟수: **0회** (0회면 최초 로드 이후 파일을 다시 읽지 않는다는 뜻 — 직접 계측, 코드 추정 아님)
**전공을 돌려가며 100회**
- 호출 100회 · 평균 1.849ms · 중앙값 1.716ms · p95 2.222ms · 최대 11.010ms · 총 0.1849초
- 100회 반복하는 동안 실제 `Path.read_text()` 호출 횟수: **0회** (0회면 최초 로드 이후 파일을 다시 읽지 않는다는 뜻 — 직접 계측, 코드 추정 아님)

## 4. 대략적인 메모리 사용량

- 25,389건 로드 후 Python 힙 사용량 약 **44.03 MB** (tracemalloc 기준, Pydantic 객체·인덱스 dict 포함). 학과 1건당 약 1.78 KB.

## 5. 30개 제한 결과 / 결정론성 결과 / 중복 ID 처리 결과 / Fail-Closed 결과

| 시나리오 | 통과 | 상세 |
|---|---|---|
| 미등록 major_id 조회 | ✅ | 0건 반환(0건 기대) |
| 결과 0건 | ✅ | 0건 반환 |
| 결과 1건 | ✅ | 1건 반환 |
| 결과 30건 초과 → limit 준수 | ✅ | 후보 2263건 중 30건 반환(limit=30) |
| 30건 초과 반복 조회 결정론성 | ✅ | 두 번 조회한 상위 30건의 순서·구성이 동일 |
| 동일 정렬 Key 충돌 시 department_id로 tie-break | ✅ | 반환 순서: ['dept_synthetic_tie_a', 'dept_synthetic_tie_b'] |
| 중복 department_id — get()은 마지막 값으로 조용히 덮어씀 | ✅ | .get()은 2건 중 1건만 반환, .all()/.search()에는 2건 전부 남음(department_id=dept_synthetic_00005022) |
| REVIEW_REQUIRED/UNMAPPED가 canonical_major_id 지정 조회에 절대 안 섞임 | ✅ | Fixture 내 UNMAPPED 3820건, 필터 없는 조회에서도 3820건 그대로 보임(canonical_major_id 필터를 지정하면 이 행들은 구조적으로 매칭 불가) — Repository 계층은 Fail-Closed. 단, `MajorExplorationService.list_departments_for_major()`도 별도로 canonical_major_id 일치를 재확인해 이중 방어선을 이룬다. |
| 예체능 Group 혼입 — fine_arts_design | ✅ | EXCLUDED_RECOMMENDATION_MAJOR_IDS=['design']에 미포함 — 실제 노출 30건 |
| 예체능 Group 혼입 — music | ✅ | EXCLUDED_RECOMMENDATION_MAJOR_IDS=['design']에 미포함 — 실제 노출 30건 |
| 예체능 Group 혼입 — performing_media_arts | ✅ | EXCLUDED_RECOMMENDATION_MAJOR_IDS=['design']에 미포함 — 실제 노출 30건 |
| 예체능 Group 혼입 — sports_dance | ✅ | EXCLUDED_RECOMMENDATION_MAJOR_IDS=['design']에 미포함 — 실제 노출 30건 |
| 빈 URL·공백 URL 방어 필터 | ✅ | 3건 중 1건만 노출(정상 URL 1건 기대) |
| MERGED/SPLIT/ABOLISHED 상태 방어 필터 | ✅ | 입력 5개 상태 중 노출된 상태: ['EXISTING', 'NEW'] (VISIBLE=['EXISTING', 'NEW']) |
| canonical_major_id 정확 일치(대소문자·공백 관대하게 처리하지 않음) | ✅ | 정확 일치 1건, 대소문자 다름 0건, 공백 포함 0건 (뒤 두 값은 0건이어야 Fail-Closed) |

## 6. 운영 승격 전 반드시 수정할 문제

1. JsonlDepartmentRepository.__init__의 `self._by_id = {d.department_id: d for d in self._departments}`가 중복 department_id를 검증·경고 없이 마지막 값으로 조용히 덮어쓴다(Python dict comprehension 특성). `.get(department_id)`는 그 학과의 여러 원본 행 중 무작위 순서(파일 내 등장 순서)로 정해지는 '마지막' 값만 반환하고, 같은 .search()/.all() 호출에는 중복 행이 전부 그대로 남아 있어 두 API가 서로 다른 개수를 보여준다. 대조: `src/services/department_recommendation_scope.py::load_department_recommendation_scope()`는 같은 상황에서 `DuplicateDepartmentScopeRecordError`를 즉시 던진다 — 저장소 계층 안에서도 중복 처리 정책이 서로 다르다.
2. EXCLUDED_RECOMMENDATION_MAJOR_IDS = ['design']는 'design' 하나만 하드코딩돼 있다 — A-1 Canonical Major Group Bridge가 42개 초안 중 예체능 4개(fine_arts_design, music, performing_media_arts, sports_dance)를 새 canonical_major_id로 승격하면, 그 4개는 이 하드코딩 집합에 없으므로 MajorExplorationService가 그대로 노출한다(이번 합성 Fixture로 실측: fine_arts_design(30건), music(30건), performing_media_arts(30건), sports_dance(30건) 노출됨). 예체능 제외가 '집합 안의 항목'에는 Fail-Closed이지만 '집합 밖의 새 항목'에는 Fail-Open이다 — 전국 승격 전에 이 하드코딩을 새 예체능 canonical_major_id까지 덮도록 바꾸거나, 별도의 Fail-Closed 화이트리스트 정책으로 교체해야 한다.

## 7. 현재 구조 그대로 전국 승격 가능한지 여부

**조건부로 가능하지만, 6번 목록을 먼저 고치지 않으면 위험하다.** 성능 자체는 25,389건 규모에서 초기 로드 0.347초·메모리 62.5MB 수준으로 이 서비스의 트래픽 규모(요청마다 새 Repository를 만들지 않고 앱 시작 시 1회 로드)에서는 문제로 보이지 않는다(선형 탐색 O(n) 방식이라 전공 수·요청 빈도가 지금보다 훨씬 커지면 다시 측정해야 한다). 하지만 **정합성 결함(중복 ID 조용한 덮어쓰기, 예체능 하드코딩 Allowlist가 새 canonical_major_id를 못 막음)은 성능과 무관하게 승격 전에 반드시 고쳐야 한다** — 특히 예체능 하드코딩 문제는 A-1 Bridge가 42개 초안 중 예체능 4개를 승격시키는 순간 바로 실제 사용자에게 노출될 수 있는 회귀다.

