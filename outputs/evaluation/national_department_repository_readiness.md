# 전국 학과 Department Repository/Service 승격 준비도 — 읽기 전용 진단

> 이 보고서의 25,389건은 합성(Synthetic) Fixture 실측이다 — 검증된 운영 Master가 아니다.

이 보고서는 `src/repositories/department_repository.py`·`src/services/major_exploration_service.py`를 **한 줄도 수정하지 않고** 관찰만 한 결과다. 발견된 결함은 코드로 고치지 않고 아래 목록에만 남겼다.

**재현성 범위**: 같은 seed로 만든 Fixture 분포·시나리오 통과/실패·발견된 결함 목록은 재실행해도 항상 같다(`comparable_snapshot()`로 별도 검증). 다만 Wall Time·메모리처럼 실제로 측정한 숫자는 실행마다 미세하게 달라질 수 있다 — 이 값을 고정값으로 조작하지 않고 매 실행의 실측 그대로 기록한다.

## 1. 데이터 크기

- 합성 Fixture 행 수: **25,389건**(실제 커밋된 `data/academyinfo_work/2025/normalization_report.json`의 `included_count` 기준)
- 상태 분포(합성, 실제 보고서 비율 그대로): {'ABOLISHED': 14985, 'EXISTING': 9275, 'NEW': 1038, 'SPLIT': 34, 'MERGED': 57}
- canonical_major_id 분포(상위 10개): {'(UNMAPPED)': 3808, 'business_administration': 1734, 'mechanical_engineering': 1705, 'life_science': 1681, 'law': 1560, 'fine_arts_design': 1514, 'economics': 1468, 'hci_ux': 1322, 'chemistry': 1173, 'psychology': 1121}
- 메인 25,389건 Fixture에 주입한 중복 department_id 건수: **0건** — 2026-08-24 수정 후 Repository가 중복을 Fail-Fast로 즉시 거부하므로, 시간·메모리를 실측하는 이 메인 Fixture에는 더 이상 중복을 섞지 않는다(0건이 정상). 중복 Fail-Fast 자체는 §5 표의 별도 2행짜리 시나리오로 확인한다.

## 2. 초기 로드 시간·메모리

- 행 수: 25,389
- Wall Time: **0.3345초**
- Python 힙 Peak(tracemalloc): **62.39 MB**
- Python 힙 Current(로드 직후): 44.01 MB

## 3. 반복 조회 시간

**같은 major_id 100회 반복**
- 호출 100회 · 평균 1.777ms · 중앙값 1.731ms · p95 2.006ms · 최대 3.108ms · 총 0.1777초
- 100회 반복하는 동안 실제 `Path.read_text()` 호출 횟수: **0회** (0회면 최초 로드 이후 파일을 다시 읽지 않는다는 뜻 — 직접 계측, 코드 추정 아님)
**전공을 돌려가며 100회**
- 호출 100회 · 평균 1.736ms · 중앙값 1.728ms · p95 1.958ms · 최대 2.088ms · 총 0.1736초
- 100회 반복하는 동안 실제 `Path.read_text()` 호출 횟수: **0회** (0회면 최초 로드 이후 파일을 다시 읽지 않는다는 뜻 — 직접 계측, 코드 추정 아님)

## 4. 대략적인 메모리 사용량

- 25,389건 로드 후 Python 힙 사용량 약 **44.01 MB** (tracemalloc 기준, Pydantic 객체·인덱스 dict 포함). 학과 1건당 약 1.78 KB.

## 5. 30개 제한 결과 / 결정론성 결과 / 중복 ID 처리 결과 / Fail-Closed 결과

| 시나리오 | 통과 | 상세 |
|---|---|---|
| 미등록 major_id 조회 | ✅ | 0건 반환(0건 기대) |
| 결과 0건 | ✅ | 0건 반환 |
| 결과 1건 | ✅ | 1건 반환 |
| 결과 30건 초과 → limit 준수 | ✅ | 후보 1734건 중 30건 반환(limit=30) |
| 30건 초과 반복 조회 결정론성 | ✅ | 두 번 조회한 상위 30건의 순서·구성이 동일 |
| 동일 정렬 Key 충돌 시 department_id로 tie-break | ✅ | 반환 순서: ['dept_synthetic_tie_a', 'dept_synthetic_tie_b'] |
| 메인 Fixture에 중복 department_id 없음(중복 Fail-Fast 시나리오는 별도) | ✅ | 메인 Fixture 25389건 중 중복 department_id 0건 |
| REVIEW_REQUIRED/UNMAPPED가 canonical_major_id 지정 조회에 절대 안 섞임 | ✅ | Fixture 내 UNMAPPED 3808건, 필터 없는 조회에서도 3808건 그대로 보임(canonical_major_id 필터를 지정하면 이 행들은 구조적으로 매칭 불가) — Repository 계층은 Fail-Closed. 단, `MajorExplorationService.list_departments_for_major()`도 별도로 canonical_major_id 일치를 재확인해 이중 방어선을 이룬다. |
| 예체능 Group 혼입 — fine_arts_design | ✅ | 허용 Major ID 집합(canonical_majors.jsonl 기반 DEFAULT_SERVICE_MAJOR_IDS)에 미포함 — 실제 노출 0건(0건 기대) |
| 예체능 Group 혼입 — music | ✅ | 허용 Major ID 집합(canonical_majors.jsonl 기반 DEFAULT_SERVICE_MAJOR_IDS)에 미포함 — 실제 노출 0건(0건 기대) |
| 예체능 Group 혼입 — performing_media_arts | ✅ | 허용 Major ID 집합(canonical_majors.jsonl 기반 DEFAULT_SERVICE_MAJOR_IDS)에 미포함 — 실제 노출 0건(0건 기대) |
| 예체능 Group 혼입 — sports_dance | ✅ | 허용 Major ID 집합(canonical_majors.jsonl 기반 DEFAULT_SERVICE_MAJOR_IDS)에 미포함 — 실제 노출 0건(0건 기대) |
| 빈 URL·공백 URL 방어 필터 | ✅ | 3건 중 1건만 노출(정상 URL 1건 기대) |
| MERGED/SPLIT/ABOLISHED 상태 방어 필터 | ✅ | 입력 5개 상태 중 노출된 상태: ['EXISTING', 'NEW'] (VISIBLE=['EXISTING', 'NEW']) |
| canonical_major_id 정확 일치(대소문자·공백 관대하게 처리하지 않음) | ✅ | 정확 일치 1건, 대소문자 다름 0건, 공백 포함 0건 (뒤 두 값은 0건이어야 Fail-Closed) |
| 중복 department_id 2건 — Repository 생성 즉시 Fail-Fast | ✅ | DuplicateDepartmentIdError 발생, 메시지='dept_synthetic_00000001' (department_id만 포함=True, 학과명·대학명·URL 미포함=True) |

## 6. 운영 승격 전 반드시 수정할 문제

없음(이번 실측 범위 안에서는 결함이 관찰되지 않았다).

## 7. 현재 구조 그대로 전국 승격 가능한지 여부

**이번 실측 범위(중복 department_id Fail-Fast, 42개 Canonical Major Group ID 직접 조회 차단)에서는 정합성 결함이 관찰되지 않았다.** 성능 자체는 25,389건 규모에서 초기 로드 0.335초·메모리 62.4MB 수준으로 이 서비스의 트래픽 규모(요청마다 새 Repository를 만들지 않고 앱 시작 시 1회 로드)에서는 문제로 보이지 않는다(선형 탐색 O(n) 방식이라 전공 수·요청 빈도가 지금보다 훨씬 커지면 다시 측정해야 한다). 다만 이 결론은 이번 Harness가 실측한 시나리오 범위 안에서만 유효하다 — 588개 실제 중복 department_id 검토·확정, 4,454건 REVIEW_REQUIRED 분류 검토, Bridge draft의 사람 승인 등 `outputs/handoff/academyinfo_a_decisions.md` §7이 정한 나머지 승격 전 필수 항목은 이 Harness 범위 밖이다.

