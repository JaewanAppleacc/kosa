# A 결정 기록 — 대학알리미 전국 수집 파이프라인 단계 통합 (2026-08-24)

담당 브랜치: `integration/academyinfo-pipeline` (기준: `origin/trait-vector-v2` da23fa9,
worker-c `641912a`에서 필요한 경로만 선별 반입). 이 문서는 A가 이번 라운드에서
확정한 정책과 그 근거를 기록한다 — 코드가 아니라 "무엇을 왜 그렇게 결정했는지"의
정본이다.

## 1. 조사연도 — 2025를 최신 전국 학과 후보로 승인

- **학과 API(`BasicInformationService_1/getUniversityMajorCode`)의 실제 지원연도는
  2025다.** `getComparisonPubYear`(대학 비교통계 서비스)가 광고하는 지원연도
  `[2025, 2024, 2023]`과 실제로 학과 데이터를 내려주는 연도는 다르다 — 2024로
  전국 수집을 돌려 대학 376개·API 호출 398회를 쓰고서야 학과 0건을 확인했다
  (`data/academyinfo_raw/2024/collection_manifest.json`의
  `department_count: 0`, `rationale_c/07-academyinfo-collection.md` 참고). 그래서
  **2025 데이터를 최신 전국 학과 후보로 승인한다.**
- **2024 파일 데이터(`data/academyinfo_work/2024/file_dataset_import_report.json`,
  data.go.kr 파일 데이터셋 원본 기반)는 학과 후보가 아니라 ID 안정성·Lineage
  비교 전용으로만 쓴다.** `data/academyinfo_work/2025/year_comparison_report.json`이
  2024(파일)↔2025(API) 비교로 `schl_mjr_id_retention_rate: 0.996`(99.6%)을
  계산하는 데만 쓰였다 — 2024 데이터 자체를 Master 후보로 승격하지 않는다.
- **공공데이터포털의 API 상품·명세 수정일(`2026-05-04`)은 조사연도로 해석하지
  않는다.** 이 값은 "API 명세를 마지막으로 손본 날짜"일 뿐 "데이터가 조사된
  연도"가 아니다. 수집기(`src/data_sources/academyinfo_year.py`)는 이 값을
  `PUBLIC_API_METADATA_MODIFIED_AT` 상수로 조사연도와 분리해 Manifest에 함께
  남기되, 실제 연도 선택에는 `getComparisonPubYear`의 실제 응답만 쓴다
  (`tests/test_academyinfo_collection_safety.py::
  SurveyYearManifestConsistencyTest`로 확인).

## 2. 대표 전공군 42개 — Draft 그대로 유지

- **42개 초안(`data/canonical_major_groups.draft.jsonl`)을 그대로 유지한다.**
  손대지 않았고, 42개 전부 `review_status: "draft"`다
  (`tests/test_canonical_major_groups_draft.py::
  ExactlyFortyTwoGroupsTest.test_all_review_status_are_draft`).
- **"20~40개"는 엄격한 상한이 아니라 초기 목표 범위였다.** 42개로 확정된 이유는
  숫자를 맞추기 위해서가 아니라, 치의학·한의학·수의학처럼 진로 경로가 뚜렷이
  다른 소계열을 억지로 합치지 않았기 때문이다 — 예: 의학계열 안에서도 의학/한의학/
  치의학/수의학을 각각 별도 전공군으로 분리했다(`departments_per_canonical_group`
  기준 각각 48/17/11/13건, `data/academyinfo_work/2025/classification_dry_run.json`).
  숫자를 줄이려고 이 네 계열을 하나로 합치지 않는다.
- **42개는 "분류 후보 Ontology"이지 "검증된 추천 전공 42개"가 아니다.** 소계열
  코드를 전공군으로 묶는 분류 작업은 끝났지만, 그 묶음이 실제로 학생에게
  추천할 만한 단위인지는 아직 사람이 검토하지 않았다 — `review_status`가
  "approved"로 바뀌기 전까지는 어떤 Matching 코드도 이 42개를 입력으로 쓰지
  않는다(현재는 그런 Matching 코드 자체가 없다).

## 3. 예체능 분류 — Ontology에는 보존, 추천에서는 계속 제외

- 미술·디자인(`fine_arts_design`)·음악(`music`)·연극·영화·영상콘텐츠
  (`performing_media_arts`)·체육·무용(`sports_dance`) 4개 예체능 전공군은
  **분류 Ontology(42개 초안)에는 그대로 남아 있다** — 대학알리미 표준분류 소계열
  158개 전부를 어딘가에 배정해야 분류가 완결되고, 예체능도 실제 학과가 존재하는
  분야이기 때문이다.
- 그러나 **이 4개는 여전히 실제 추천 정본(`data/master/canonical_majors.jsonl`
  10개, `data/master/major_profiles_v2.jsonl` 3개)에 자동으로 들어가지 않는다**
  — 이미 확정된 기존 정책(`design` Canonical Major를 추천 대상에서 통째로 제외하는
  `EXCLUDED_RECOMMENDATION_MAJOR_IDS`, `src/services/major_exploration_service.py`)
  과 같은 방향이다. "분류에 존재"와 "추천에 노출"은 서로 다른 질문이고, 이번
  라운드는 전자만 끝냈다(`tests/test_canonical_major_groups_draft.py::
  ArtsAndSportsGroupsTest`로 이 분리 자체를 회귀 테스트로 고정했다).
- 분류 단계에서 예체능 계열은 3,667건으로 별도 집계됐다(`eligibility_breakdown.
  EXCLUDED_ARTS_SPORTS`, `large_series_breakdown.예체능계열`
  — `data/academyinfo_work/2025/classification_dry_run.json`).

## 4. Master 승격 — 이번 라운드는 보류

- **현재 시연 Master(`data/master/departments.jsonl`) 35개를 그대로 유지한다.**
  전국 25,389건(정규화 완료 기준, `data/academyinfo_work/2025/
  normalization_report.json`의 `included_count`)으로 교체하지 않았다 — `git diff
  --exit-code HEAD -- data/master/departments.jsonl`이 빈 결과임을
  `tests/test_canonical_major_groups_draft.py::
  ExistingMasterFilesUnchangedTest.test_departments_jsonl_unchanged`와
  `tests/test_department_url_promotion.py::
  DemoMasterNotRegeneratedTest.test_departments_jsonl_unchanged_since_head`
  둘 다로 확인했다. `/departments/{major_id}` API 응답 개수(media_communication=4,
  industrial_engineering=3, hci_ux=1, design=0)도 이전과 동일하다.
- **588개 중복(`duplicate_department_id_count`)과 검토 대기 학과를 사람이 처리한
  뒤에야 별도로 승격을 재검토한다.** 같은 `department_id`에 원본 행이 여러 개
  붙는 경우(`build_resolution_review_queue()`, `src/data_sources/
  academyinfo_identity.py`)는 재학생 수 같은 값으로 자동으로 하나를 고르지
  않는다 — 신설 학과는 재학생이 0명이라 그 기준 자체가 반례를 만든다. 588건
  전부 `review_status: "REVIEW_REQUIRED"`로 대기 상태다.
- **4,454건의 `REVIEW_REQUIRED`(분류 단계, `eligibility_breakdown.
  REVIEW_REQUIRED`)는 Fail-Closed로 둔다.** 사람이 검토해 명시적으로 승인하기
  전까지는 승격 후보에서 제외된 것과 동일하게 취급한다 — 다른 검수 흐름(Trait
  Ontology v2의 reviewer_1 정책)과 같은 원칙이다.
- **3,657건의 N.C.E(표준분류 미분류, `unclassified_nce_count`)는 UNMAPPED로
  유지한다.** N.C.E는 "분류명"이 아니라 "분류 없음" 센티널이다
  (`src/data_sources/academyinfo_codes.py::is_series_unclassified`) — 억지로
  42개 전공군 중 하나에 배정하지 않는다.

## 5. 학과 홈페이지 URL — Scope로 공개 여부를 가른다

- 기존 A의 `Department.department_url` Schema(`src/schemas/major.py`, http/https만
  허용·API Key 쿼리 파라미터 금지)를 그대로 재사용한다 — 이번 라운드에서 그
  Schema 자체를 바꾸지 않았다(`git diff -- src/schemas/` 무변경 확인).
- **`department_url_scope == "department"`인 원본만 공개 `department_url`로
  넘긴다.** 실제로 그 학과 홈페이지를 가리키는 URL만 학생 화면의 "학과 홈페이지"
  버튼에 쓰일 수 있다.
- **`department_url_scope == "college"`(단과대학 URL, 실측 3건)는 공개 값을
  항상 `None`으로 만든다.** 단과대학 홈페이지를 그 학과의 공식 홈페이지로
  위장하지 않는다 — 단과대학 URL과 그 사유(note)는 버리지 않고 내부 Raw/Audit
  레코드에 그대로 보존한다. 이 규칙은 `src/services/department_url_promotion.py::
  resolve_department_url_for_promotion()`으로 고정해 뒀다(`tests/
  test_department_url_promotion.py`로 검증) — 다만 이 함수는 **아직 어떤
  Builder에서도 호출되지 않는다.** 현재 시연 Master 35개의 URL도 이번 브랜치에서
  자동으로 바뀌지 않았다(전부 여전히 `department_url=None`).
- `source_url`(대학알리미 공식 URL, 출처 표시용 — "대학알리미 {source_svy_year}년
  공시 기준" 문구에 씀)과 `department_url`(학과 공식 홈페이지, 있으면 "학과
  홈페이지 보기" 버튼)의 역할을 섞지 않는다. `source_dataset` 같은 필드는 공개
  Schema에 추가하지 않았다.

## 6. 이번 라운드에서 하지 않은 것 (명시적 보류)

- worker-c 브랜치 전체 merge — 필요한 경로만 선별 반입했다.
- 25,389건을 공개 API에 연결 — 아직 어떤 Endpoint도 이 데이터를 참조하지 않는다.
- 136MB 전국 Raw 원본 파일을 Git에 추가 —애초에 worker-c 브랜치 히스토리에도
  커밋된 적이 없다(확인함, 아래 §8 참고). `.gitignore`에 재수집 원본 제외 규칙을
  worker-c 버전에서 필요한 부분만 수동 병합했다.
- API Key 문자열을 어디에도 복사·출력·커밋하지 않았다 — `.env.example`에는 변수
  이름(`DATA_GO_KR_SERVICE_KEY`, `ACADEMYINFO_SURVEY_YEAR`)만 추가했다.

## 7. 나중에 Master 승격 전에 반드시 해결할 항목

1. 588개 중복 `department_id`(원본 행 여럿) 검토·확정 — 자동 대표 선정 금지 원칙
   유지.
2. 4,454건 REVIEW_REQUIRED(분류 근거 불충분) 사람 검토.
3. 예체능 4개 전공군을 실제로 추천 정본에 넣을지(넣는다면 추천 제외 정책과
   어떻게 공존시킬지)는 이번 문서의 결정 범위 밖 — 별도 논의 필요.
4. `department_url_scope == "department"` 판정 로직 자체(원본에서 이 Scope를
   어떻게 판별하는지)는 이번 라운드에서 아직 감사하지 않았다 — 실제 3건의
   college-scope 사례를 표본으로 사람이 확인해야 한다.
5. 42개 전공군의 `review_status`를 "approved"로 승격할 때, `data/master/
   canonical_majors.jsonl`(현재 10개, 자유서술형 Alias·Keyword 구조)과의 관계를
   어떻게 재구성할지(대체/병합/공존) 결정 필요 — 이번 라운드는 둘을 완전히
   분리된 상태로 남겨뒀다.
