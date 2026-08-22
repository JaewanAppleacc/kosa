# data/ — 작업자 C 산출 데이터

`data/drafts/`(초안 저장 규칙)는 [`drafts/README.md`](drafts/README.md)를 따로 본다.

## 디렉터리

```text
raw/            원본 보존. 손으로 관리한다.
master/         정제본. 전부 스크립트가 다시 만든다 — 직접 고치지 말 것.
admissions/     AdmissionReference
rag/            RAG 수집 목록·원문·Manifest
drafts/         A 검토 대기 초안 (Context·Trait 검토, Seed Question, Major/Subject-Trait Mapping)
eval_fixtures/  Persona·Hand-Calculated Fixture, RAG·Mapping 기대값
audit/          데이터 품질 검사 결과
```

전체 재생성:

```bash
python scripts/career_build_all.py
```

**이 규모와 범위를 어떤 기준으로 정했는지는 [`../rationale_c/02-data-scope.md`](../rationale_c/02-data-scope.md)**에
있다 — 개수 자체가 목표가 아니라 "무엇을 확인할 수 있는 최소 집합인가"로 정했다.

## 지금 데이터의 출처 상태 — 반드시 읽을 것

세 종류가 섞여 있고, 어느 것이 무엇인지 파일만 보고 구분할 수 있게 해 뒀다.

| 종류 | 표시 | 해당 데이터 |
|---|---|---|
| 실제 공식 자료 | `source_url`이 `https://` | 학과 Master(대학알리미), 고교 과목(NCIC), 교육통계(KEDI) |
| 검증 전 골격 | `review_status: "draft"` + 수치 필드가 `null` | AdmissionReference |
| 파이프라인 검증용 샘플 | `source_url`이 `sample://` | RAG 문서 5건 |

### 1. 학과 Master — `schl_id`가 아직 임시값이다

`DATA_GO_KR_SERVICE_KEY`(대학알리미 B340014)가 없어 API 수집을 못 했다. 학과명·대학명·
지역·단과대학은 실제 값이지만 `schl_id`는 `ACADEMYINFO_PENDING_*` 임시값이라,
**Key가 나오면 `department_id`가 전부 새로 생성된다**(id 해시가 `schl_id`를 쓴다).
이 사실은 품질 검사에서도 `schl_id_placeholder` INFO로 매번 보고된다.

### 2. 입결 — 숫자를 비워 뒀다

입결 Source가 설계안에 지정돼 있지 않고 대학어디가는 자동 수집이 막혀 있어, **확인할 수
없는 숫자를 채우지 않았다.** `admission_references.jsonl`은 학년도·전형·전형유형·지표
네 축과 `data_comparability_group`만 확정된 골격이고 컷 점수는 `null`이다.

정렬·비교 동작을 확인해야 할 때만 `admission_references.placeholder.jsonl`(합성 숫자,
실제 입결 아님)을 쓴다. 이 파일은 Repository 기본 경로가 아니다.

### 3. RAG 문서 — 5건은 샘플이다

대학 홈페이지 수집이 아직 없어 학과 문서를 지어내는 대신, `source_url`을 `sample://`로
시작하게 두고 `document_type`에 "샘플(비공식)"을 붙였다. 공식 URL을 단 가짜 문서를 만들면
검색 결과가 근거 있는 것처럼 보이게 되고, 그건 설계안 §27을 정면으로 어긴다.
실제 수집이 시작되면 `sample://` 항목만 지우면 된다.

진짜 문서는 `documents/kedi_education_statistics_2024.txt` 하나 —
「2024년 간추린 교육통계」(KEDI) 원문이다.

## 파일별 생성 스크립트

| 파일 | 만드는 스크립트 |
|---|---|
| `master/universities.jsonl`, `master/departments.jsonl`, `master/canonical_mapping_*.jsonl` | `career_build_department_master.py` |
| `master/major_profiles.jsonl`, `drafts/major_trait_mappings/` | `career_build_major_profiles.py` |
| `master/subjects.jsonl`, `master/subject_aliases.jsonl`, `drafts/subject_trait_mappings/` | `career_build_subject_profiles.py` |
| `admissions/*.jsonl` | `career_build_admission_references.py` |
| `rag/sources.jsonl`, `rag/documents/`, `rag/manifest.jsonl` | `career_build_rag_corpus.py` |
| `drafts/question_blueprints/` | `career_build_question_blueprints.py` |
| `drafts/context_trait_reviews/` | `career_build_context_trait_review.py` |
| `eval_fixtures/personas/` | `career_build_persona_fixtures.py` |
| `eval_fixtures/rag_query_expectations.json`, `eval_fixtures/mapping_expectations.json`, `master/question_cache.jsonl` | `career_build_eval_fixtures.py` |
| `audit/threshold_measurements.json` | `career_measure_thresholds.py` |
| `audit/data_quality.*` | `career_audit_data_quality.py` |

## 손으로 고치는 파일

```text
data/raw/universities.raw.jsonl
data/raw/departments.raw.jsonl
```

나머지 표(전공 등급, 과목 등급, Seed Question 문구, Persona 답변, 기대값)는 각 빌드
스크립트 상단 상수에 있다. 산출물 JSON을 직접 고치면 다음 재생성에서 사라진다.

## 품질 검사

```bash
python scripts/career_audit_data_quality.py    # ERROR가 하나라도 있으면 종료 코드 1
```

`data/audit/data_quality.md`가 사람이 읽는 표, `.json`이 기계용이다. ERROR 0을
`tests/worker_c/test_shipped_data.py`가 테스트로도 고정해 둔다.
