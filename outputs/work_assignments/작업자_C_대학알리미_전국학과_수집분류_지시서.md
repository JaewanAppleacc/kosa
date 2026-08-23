# 작업자 C — 대학알리미 전국 4년제 학과 수집·분류 지시서

## 0. 작업 목표

대학알리미 Open API의 공식 대학·학과 정보를 수집해 기존 시연용 소규모 데이터와 분리된 **전국 4년제 대학 학과 원본 데이터셋**을 구축한다.

이번 작업의 완료 기준은 다음과 같다.

```text
공식 API 호출
→ 대학 목록 수집
→ 대학별 학과 수집
→ 원본 보존 및 정규화
→ Canonical Major 후보 분류
→ 예체능 추천 제외 여부 판정
→ REVIEW_REQUIRED 분리
→ 품질 보고서 생성
```

대학 서열화, 입결 기반 정렬, 학생 성적에 따른 상향·적정·안정 판정은 이번 작업에 포함하지 않는다.

## 1. 시작 전 필수 확인

- 작업 브랜치는 `worker-c`만 사용한다.
- 현재 저장소의 C 작업 경계와 기존 계약은 `README_C.md`를 따른다.
- 기존 빌더 `scripts/career_build_department_master.py`, ID 함수 `src/ids.py`, Repository Schema를 먼저 읽는다.
- A 소유 파일인 공개 API Schema, LangGraph, Matching Engine, Agent 판단 로직은 수정하지 않는다.
- 기존 `data/raw/`와 `data/master/` 파일을 곧바로 덮어쓰지 않는다. 별도 수집 디렉터리에서 감사 후 승격한다.

## 2. API Key 보안 규칙

API Key는 저장소에 절대 기록하지 않는다.

```bash
export DATA_GO_KR_SERVICE_KEY="재발급받은_키"
```

- 로컬 `.env` 사용은 가능하지만 `.gitignore` 대상이어야 한다.
- `.env.example`에는 값 없이 변수명만 기록한다.
- 코드·테스트·Fixture·README·커밋 메시지·로그에 실제 Key를 남기지 않는다.
- 요청 URL 전체를 로그에 출력하지 않는다. Query String에 Key가 포함될 수 있기 때문이다.
- 오류 메시지에는 Key 앞부분도 남기지 않는다.
- 기존에 채팅이나 출력에 노출된 Key가 있다면 사용하지 말고 재발급한 Key로 진행한다.
- `KOCES_API_KEY`를 로컬 호환용 별칭으로 읽을 수는 있으나, 정식 환경변수명은 `DATA_GO_KR_SERVICE_KEY`로 통일한다.

## 3. 사용할 공식 API와 최소 검증

설계안에 기록된 대학알리미 BasicInformationService를 기준으로 실제 응답을 다시 확인한다.

1. 대학 목록: `BasicInformationService_2`의 `getComparisonUniversitySearchList` 또는 실제 서비스 문서상 동일 역할 Operation
2. 대학별 학과: `BasicInformationService_1`의 `getUniversityMajorCode`

필수 입력 후보:

```text
serviceKey
svyYr
pageNo
numOfRows
schlId   # 대학별 학과 조회
```

전체 수집 전에 다음 Smoke Test부터 수행한다.

```text
대학 목록 1~5건 조회
→ 응답에서 schlId·대학명 확인
→ 그중 대학 1개의 학과 목록 조회
→ 학과명·단과대학·조사연도·분류 필드 확인
```

실패는 최소한 다음 상태로 구분한다.

- 인증 실패
- 호출 한도 초과
- 정상 빈 응답
- API 응답 Schema 변경
- 일시적 서버·네트워크 오류

## 4. 구현할 수집기

권장 파일:

```text
scripts/career_collect_academyinfo_departments.py
src/data_sources/academyinfo_client.py
tests/worker_c/test_academyinfo_client.py
tests/worker_c/test_academyinfo_department_collector.py
```

CLI는 최소한 다음 옵션을 지원한다.

```text
--survey-year
--page-size
--max-universities
--request-delay-ms
--resume
--dry-run
--output-dir
```

필수 구현 규칙:

- 대학 목록은 Pagination이 끝날 때까지 수집한다.
- `schlId`를 기준으로 중복을 방지하되 캠퍼스 정보는 임의로 합치지 않는다.
- 대학별 학과 호출이 끝날 때마다 Checkpoint를 저장한다.
- 중단 후 `--resume`으로 이미 완료한 대학을 건너뛰고 이어서 수집할 수 있어야 한다.
- 호출 제한을 고려해 요청 간격과 제한된 재시도·지수 Backoff를 둔다.
- 병렬 대량 호출로 API를 압박하지 않는다.
- 같은 원본과 옵션으로 정규화 결과를 재생성하면 Byte-identical해야 한다.
- 테스트는 Fake Client/Fixture를 사용하고 실제 네트워크나 실제 Key에 의존하지 않는다.

## 5. 원본·정규화 데이터 저장 구조

권장 구조:

```text
data/academyinfo_raw/<survey_year>/universities.raw.jsonl
data/academyinfo_raw/<survey_year>/departments.raw.jsonl
data/academyinfo_raw/<survey_year>/collection_manifest.json
data/academyinfo_raw/<survey_year>/collection_checkpoint.json
data/academyinfo_raw/<survey_year>/collection_errors.jsonl
data/academyinfo_work/<survey_year>/universities.normalized.jsonl
data/academyinfo_work/<survey_year>/departments.normalized.jsonl
data/academyinfo_work/<survey_year>/classification_results.jsonl
data/academyinfo_work/<survey_year>/classification_review_queue.jsonl
```

원본 Snapshot에는 응답 원문 또는 원문을 손실 없이 복원할 수 있는 필드를 보존한다. Manifest에는 다음을 기록한다.

- 수집 기준일과 조사연도
- Endpoint와 Operation 이름
- 페이지·대학별 수집 성공/실패 수
- 응답 Hash
- 수집기 Version 또는 Git SHA
- API Key를 제거한 공식 출처 URL

## 6. 기존 Raw Schema와의 매핑

기존 빌더가 기대하는 필드를 유지한다.

대학:

```text
schl_id
name
region
establishment_type
homepage
```

학과:

```text
schl_id
university_name
campus
region
department_name
college_name
admission_unit
status_raw
svy_year
source_url
```

- `department_id`는 반드시 `src.ids.generate_department_id()`로 만든다.
- 조사연도는 ID에 넣지 않고 `source_svy_year` 또는 원본 필드로 보존한다.
- API Key가 포함된 호출 URL을 `source_url`로 저장하지 않는다.
- `source_url`은 대학알리미 또는 대학 공식 홈페이지의 Key 없는 공식 URL만 사용한다.
- Placeholder ID, 임의 대학명, 추측한 홈페이지를 만들지 않는다.

## 7. 전국 4년제 대학 범위 판정

이번 데이터셋은 전국 4년제 대학의 실제 학과 탐색이 목적이다.

- 공식 응답의 학교 종류·과정·설립 정보로 4년제 여부를 판정한다.
- 학교명 문자열만 보고 4년제 여부를 추측하지 않는다.
- 제외된 학교·과정도 원본에서 삭제하지 말고 `excluded_records.jsonl`에 제외 근거와 공식 필드를 남긴다.
- 본교·분교·캠퍼스를 API 식별자와 공식 필드에 따라 구분하고 임의 통합하지 않는다.
- 폐지·통합·분리 학과는 삭제하지 말고 상태와 조사연도를 보존한다.

## 8. 학과 분류 기준

학과 한 행을 곧바로 추천 전공으로 확정하지 않는다. 다음 순서로 Candidate를 만든다.

### 8-1. Canonical Major 후보

1. 대학알리미의 공식 표준 대·중·소계열 분류
2. 정규화된 학과명과 검토된 Alias의 Exact Match
3. 학과 교육목표·교육과정·졸업 후 진로 공식 자료
4. 위 근거가 서로 충돌하거나 여러 전공에 걸치면 `REVIEW_REQUIRED`

금지 사항:

- 학과명에 특정 단어가 있다는 이유만으로 자동 확정
- LLM이 근거 URL 없이 Canonical Major를 확정
- 결과 개수를 채우기 위해 유사도가 낮은 학과를 억지로 편입
- 기존 추천 전공 3개에 전국 학과를 강제로 끼워 맞추기

권장 결과 필드:

```text
department_id
candidate_canonical_major_ids
mapping_status
mapping_method
official_classification
evidence_urls
decision_reason
review_status
```

### 8-2. 예체능 추천 제외 판정

예체능 학과는 데이터에서 삭제하지 않고 **추천 노출 정책만 분리**한다.

```text
academic_field:
  STEM | HUMANITIES_SOCIAL | INTERDISCIPLINARY | ARTS | SPORTS | UNKNOWN

eligibility_status:
  APPROVED | EXCLUDED_ARTS_SPORTS | REVIEW_REQUIRED
```

판정 우선순위:

1. 대학알리미 공식 계열 분류
2. 공식 단과대학·학부 소속
3. 공식 교육과정과 학과 소개
4. 공식 입학전형 자료의 실기·실적 전형 여부는 보조 근거

단, 디자인·콘텐츠·미디어라는 단어만으로 예체능 또는 비예체능을 확정하지 않는다. 융합 학과는 공식 교육과정 근거가 충분하지 않으면 `REVIEW_REQUIRED`로 둔다.

### 8-3. 대학 수준·입결 분류

이번 작업에서는 하지 않는다.

- 서울대·제주대처럼 입결 편차가 큰 대학을 단순 학과 적합도로 함께 정렬하지 않는다.
- 대학알리미 학과 Master DB는 전공 탐색용 목록이다.
- 성적 기반 지원 범위는 추후 공식 입결 데이터와 비교 가능성 그룹이 준비된 뒤 별도 Admission Pipeline에서 처리한다.

## 9. 분류 검토 정책

- 자동 분류는 `candidate` 또는 `draft` 상태다.
- 불확실한 항목은 반드시 `REVIEW_REQUIRED`로 남긴다.
- 사람이 검토하지 않은 Mapping을 `APPROVED`로 승격하지 않는다.
- 자동 분류 결과와 사람의 수정 이력을 별도 감사 파일에 보존한다.
- 원본 API 행은 사람의 판정 때문에 수정하거나 삭제하지 않는다.

우선 검토 대상:

- 동일 학과명이 여러 표준 계열에 나타나는 경우
- 자유전공·융합·미디어·콘텐츠·디자인·HCI·UX 관련 학과
- 예체능과 공학/인문사회가 혼합된 학과
- 학과명이 변경·통합·분리된 경우
- 공식 분류와 교육과정 근거가 충돌하는 경우

## 10. 기존 Master DB 승격 전 품질 검사

처음에는 기존 `data/master/`를 덮어쓰지 말고 별도 결과를 만든다. 다음 검사가 모두 통과한 뒤 A에게 승격을 요청한다.

- 대학·학과 수, 조사연도, 캠퍼스별 수
- 대학 `schlId` 중복·누락
- `department_id` 중복
- 대학이 없는 고아 학과
- 학과명·대학명·출처 URL 누락
- 상태별 학과 수
- 공식 계열별 학과 수
- Canonical Major별 확정·검토필요·미매핑 수
- 예체능 제외·승인·검토필요 수
- 기존 30개 시연 데이터와의 중복·변경 Diff
- `media_communication`, `industrial_engineering`, `hci_ux` 후보 수와 근거
- 동일 입력 재빌드 Byte-identical 여부
- Secret 문자열이 산출물·Git Diff에 없는지 검사

## 11. 필수 테스트

실제 API 호출 없이 다음을 재현한다.

- 대학 목록 Pagination
- 대학별 학과 수집
- 같은 `schlId` 중복 응답
- 빈 페이지와 정상 종료
- 인증 오류·Quota 오류·일시 오류 구분
- 재시도 횟수와 Backoff
- 중간 실패 후 Resume
- 응답 Schema Drift 시 Fail-Fast 또는 구조화 오류
- Key와 요청 Query가 로그에 남지 않음
- 4년제 포함·제외 근거 보존
- Canonical Major Candidate와 `REVIEW_REQUIRED`
- 예체능 행 원본 보존 + 추천 제외
- 결정론적 정규화·ID 생성

## 12. 완료 보고 형식

다음 항목을 빠짐없이 보고한다.

1. 실제 사용한 공식 Endpoint·Operation·조사연도
2. Key 노출 방지 방식
3. Smoke Test 결과(비밀값 제외)
4. 수집 대학 수·학과 수·실패 대학 수
5. 4년제 범위 판정 기준과 제외 수
6. 원본·정규화·Checkpoint 파일 경로
7. Canonical Major 분류 규칙
8. 예체능 추천 제외 규칙
9. 확정 후보·REVIEW_REQUIRED·미매핑 개수
10. 기존 시연 데이터와의 Diff
11. 중복·결측·고아 레코드 검사 결과
12. 추가·수정한 코드와 테스트
13. 전체 테스트·`pip check`·`compileall`·`git diff --check` 결과
14. A/B API 계약 영향 여부
15. 아직 사람이 검토해야 할 항목과 남은 한계

## 13. Git 및 인계 규칙

- 작업은 `worker-c`에만 커밋·푸시한다.
- 실제 Key와 로컬 `.env`는 어떤 경우에도 Stage하지 않는다.
- A 소유 중앙 파일을 임의 수정하지 않는다.
- `worker-c`의 루트 `CLAUDE.md`는 브랜치 전용이므로 `main`에 병합하지 않는다.
- 대규모 원본 데이터는 저장소 용량을 확인하고, 필요하면 압축 Snapshot/Manifest와 재현 가능한 수집 스크립트를 우선 인계한다.
- A는 완료 보고와 품질 검사를 확인한 뒤 필요한 구현 커밋만 선택적으로 통합한다.
