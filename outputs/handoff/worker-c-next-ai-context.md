# Worker C 다음 AI 인수인계 — 현재까지 한 일과 다음 작업

기준 브랜치: `worker-c`

기준 HEAD: `bbc6d287e3ca4065d1279fa9d08c9adec06e81ac`

작성일: 2026-08-24

## 1. 프로젝트를 한 문장으로 이해하기

학생이 좋아하는 활동과 학교생활에 관한 멀티턴 질문에 답하면, 답변 Evidence에서 Trait를
도출하고 관련 전공·실제 대학 학과·고교 선택과목으로 연결하여 **고교학점제의 자기주도적
진로·학업 설계**를 돕는 서비스다.

전체 흐름과 담당 경계는 다음과 같다.

```text
A: 질문 생성·다음 질문 선택·종료 → 답변 Evidence → 학생 Trait → 전공 관련도
C: 공식 전공/과목 근거와 대학알리미 데이터 → 전공군 → 실제 대학·학과·선택과목
B: 위 결과를 학생이 이해할 수 있는 화면으로 표현
```

C는 A의 질문 생성·종료 로직이나 Matching Engine을 임의로 고치지 않는다. 다만 기존 질문과
엔진을 그대로 호출해 C 데이터가 최종 학과 결과까지 연결되는지는 평가할 수 있다.

## 2. C가 완료한 핵심 작업

### 2-1. 대학알리미 API 수집·정규화·분류

대학알리미 API의 공식 필드를 사용해 전국 대학·학과 데이터를 수집하고 정규화했다.

- 대학명, 캠퍼스, 지역, 학과명
- 학교종류와 학위과정
- 수업연한(4~7년 학사과정)
- 주간·야간·기타 과정
- 학과상태(`EXISTING/NEW/ABOLISHED/MERGED/SPLIT`)
- 학과특성(일반과정/계약학과)
- 공식 대·중·소계열
- 원본 식별자 `schlMjrId`, 조사연도, Lineage

학과명만 보고 분야를 추측하지 않고 공식 소계열을 전공군에 연결한다. Raw/Lineage는 보존하고
학생 추천 범위만 별도로 판정한다.

최종 전국 수치:

| 지표 | 값 |
|---|---:|
| 정규화 전체 | 24,422 |
| 현재 상태 후보 | 10,063 |
| 추천 후보 | 10,057 |
| 승인 가능 후보 | 5,449 |
| 추천 범위 밖 | 973 |
| 추천 후보 중복 ID | 0 |
| 분류 REVIEW | 1,936 |
| N.C.E | 1,901 |
| 추천 검토 Queue 합계 | 3,837 |
| 관계 검수 패킷 | 6 |

계약학과 6건은 `OUT_OF_RECOMMENDATION_SCOPE`와
`exclusion_reason=CONTRACT_DEPARTMENT`로 제외했지만 상태 `EXISTING`과 Raw/Lineage는
보존했다. 동일 명칭 일반과정 6건은 추천 범위에 유지했다. 충남대 약학과도 6년 일반과정은
유지하고 4년 계약학과는 제외했다.

### 2-2. 안전성과 재현성

- `department_id` 규칙과 기존 35건 Master를 변경하지 않음
- 공개 API, Schema, Mock, 프론트 무변경
- 자동 승인 0건
- 검수 패킷 `reviewer_1_status=TBD`, `resolution_status=PENDING`
- 입력이 같은 두 번의 생성 결과 byte-identical 확인
- Raw, API Key, `.env`, 대용량 전국 입력은 커밋하지 않음
- Secret 0건, 5MB 이상 신규 Blob 0건

전국 입력 파일 `departments.normalized.jsonl`과 `classification_results.jsonl`은 `.gitignore`
대상이라 clean clone에는 없다. 커밋된 Queue와 Manifest를 전국 입력의 대체물로 오해하지 말 것.

### 2-3. C 단독 개선 감사

커밋 `e827b93`에서 다음을 구현했다.

- `scripts/career_audit_worker_c_improvements.py`
- `data/academyinfo_work/2025/review_priority_draft.jsonl`
- `data/audit/worker_c_improvement_audit.json`
- `tests/worker_c/test_worker_c_improvement_audit.py`

3,837건을 승인 확률이 아닌 **검수 작업 순서**로 정리했다. 원 Queue 상태는 바꾸지 않았고
`auto_approved_rows=0`을 유지했다. Alias 충돌·짧은 키, 실패 유형, RAG smoke fixture의
positive Recall@5와 근거 없음 정답률을 별도로 감사한다.

### 2-4. 개선방안·기대효과 문서

`rationale_c/09-improvement-plan-and-expected-effects.md`에 다음을 정리했다.

- 시행착오 → 문제 → 적용한 개선 → 확인된 효과
- 학생과 운영자 관점의 기대효과
- 고교학점제와 과목 선택의 연결
- 소수 전공을 일반 전공과 같은 방식으로 포함하는 방법
- 학생 프로젝트와 실제 서비스 구축의 범위 차이
- 서비스 단계 교육과정 수집의 규모·인력·저장 비용

현재 학생 프로젝트에서는 기존 대학알리미 공식 소계열을 사용한다. 전국 대학 교육과정 수집은
대학별 홈페이지 구조·파일 형식·URL 변경·연도 갱신을 지속 관리해야 하므로 현재 필수 구현이
아니라 **실서비스 구축 시 정확도와 설명 근거를 높이는 후속 개선**이다.

### 2-5. 질문 → Trait → 소수 전공 진단

커밋 `c384fcb`과 `bbc6d28`에서 관광·호텔 평가용 draft를 만들었다.

- `scripts/career_evaluate_question_major_trace.py`
- `tests/worker_c/test_question_minor_major_trace.py`
- `outputs/evaluation/question_to_minor_major_trace.md`

서로 다른 질문 Context 8개에서 선택한 답변을 Trait로 추적했다. 다음 네 Trait가 각각 서로 다른
Context 두 곳에서 반복 관찰됐다.

- `planning`
- `audience_response_prediction`
- `information_comparison`
- `emotional_interpretation`

현재 Matching Engine 결과는 관광·호텔 draft와 미디어·커뮤니케이션이 모두 0.6700으로
동점이다. 이것은 다음 두 사실을 보여준다.

1. 소수 전공 Profile을 후보에 넣으면 기존 엔진으로 계산할 수 있다.
2. 후보만 추가한다고 전공 간 변별력이 생기지는 않는다.

관광·호텔 Profile은 `REVIEW_REQUIRED` 평가 가설이며 공개 Master가 아니다. 학생 프로젝트에서는
동일 파이프라인의 기술적 동작과 동점 한계를 보여주는 용도로만 사용한다.

## 3. 공식 기준이 무엇인지

발표에서 “공식 기준”이라고 말할 때는 대학알리미 API가 제공하는 학교종류, 학위과정, 수업연한,
주야간, 학과상태, 학과특성, 공식 대·중·소계열, `schlMjrId`, 조사연도를 뜻한다.

예:

```text
호텔경영학과
→ 공식 소계열 039 관광
→ 학사·주간·EXISTING·일반과정
→ 관광 전공군의 실제 학과 후보
```

도메인이 대학 홈페이지라고 해서 학과 공식 페이지로 자동 인정하지 않는다. 실제로 다른 학과,
연구실, 미디어센터로 연결된 URL 후보 3건을 걸러냈다.

## 4. 현재 증명한 성능과 아직 증명하지 않은 성능

### 증명한 것

- 정규화·포함·제외·중복·Queue 수치
- 약학 6년 일반과정 보존과 계약학과 제외
- 추천 후보 중복 ID 0건
- 자동 승인 0건
- 결정론적 재생성
- 답변 부족 시 `insufficient`, Conflict Trait Mask, 동점 동일 처리 등 Matching 회귀
- 질문 선택에서 Trait와 전공 점수까지 행 단위 추적 가능

### 아직 증명하지 않은 것

- 학생에게 맞는 전공을 맞히는 추천 정확도
- LLM이 “충분하다”고 종료했을 때의 전문가 동의율
- 실제 학생의 진로 명확성이나 과목 선택 품질 개선
- 소수 전공과 일반 전공 사이의 추천 성능 격차
- 전국 교육과정 기반 RAG 검색 성능

테스트 통과 수와 전국 학과 건수를 학생 추천 정확도로 표현하면 안 된다.

## 5. 다음 AI가 우선 수행할 작업

### 우선순위 1 — 블라인드 Persona 성능평가

실무자의 “그래서 추천 성능이 몇 퍼센트인가?”에 답하기 위한 다음 단계다. C는 평가셋과 데이터
리포트를 만들 수 있지만 A의 질문·종료·Matching 공식을 수정해서는 안 된다.

권장 최소 평가셋:

- 전공군 6개: 건축, 관광·호텔, 컴퓨터, 디자인, 미디어, 기계공학
- 전공군별 Persona 3개: 18개
- 경계 Persona 6개: 건축↔디자인, 호텔↔경영, 미디어↔디자인 등
- 총 24개 Persona

Persona는 목표 전공명을 답변에 직접 쓰지 않는다. 예를 들어 Gemini 같은 LLM에는 “건축학과
학생을 만들어라”가 아니라 공간 관찰·모형 제작·수학적 구조·시각 표현 경험을 가진 학생의
행동을 작성하되 전공명은 숨기도록 요청한다. LLM은 Persona 다양화 보조로만 쓰고 정답 채점은
사람이 블라인드 검수한다.

측정 지표:

- `Recall@3`, `Recall@5`
- MRR(정답 전공의 평균 순위)
- 충분한 답변인데 `insufficient`가 된 비율
- 틀린 전공을 `관련성 높음`으로 낸 과신 오류율
- 일반 전공과 소수 전공의 Recall 차이
- 경계 전공 혼동률

가능하면 동일 Persona로 이전 방식과 현재 방식을 비교한다.

- cosine vs 가중 Trait 충족도
- 단일 답변 반영 vs 서로 다른 Context의 반복 Evidence
- 소수 전공 후보 제외 vs 포함

평가 결과가 나온 뒤 질문 생성·종료·Matching 공식을 바꾸는 일은 A와 협의해야 한다.

### 우선순위 2 — 학생 프로젝트용 소수 전공군 확대

교육과정 수집 없이 기존 대학알리미 공식 소계열을 일반 전공과 동일하게 연결한다. 관광·호텔
하나만 특별 처리하지 말고 건축·해양·농업·국방·특수교육 등도 같은 규칙을 적용한다.

- 전공군별 Trait Vector 4~6개를 `REVIEW_REQUIRED` draft로 작성
- 분야별 경계 Persona 2~3개 실행
- 동점, 과신 오류, `insufficient`를 기록
- 공개 Master 승격이나 Vertical Slice 후보 변경은 하지 않음

### 우선순위 3 — 서비스 구축용 장기 개선안

현재 마감 작업으로 구현하지 않는다. 서비스화가 결정되면 다음 순서로 진행한다.

1. 분야별 대표 대학 5~10곳의 학과 소개·교육과정 수집
2. 학과별이 아니라 전공군 Trait Vector의 근거를 대조
3. 교육과정 RAG의 Recall@3/5, 근거 없음 정답률, 오출처율 측정
4. 자동 수집 성공률이 높은 분야부터 전국 확대
5. 연도 갱신, URL 변경, 실패 재수집 정책 운영

예상 규모는 `rationale_c/09-improvement-plan-and-expected-effects.md` §4를 따른다. 30~80학과
Pilot은 2~4인일, 전국 1,000~3,000학과는 자동화 5~10인일과 초기 검수 10~30인일 수준의
작업량 추정이다.

## 6. 역할과 변경 금지 경계

다음 AI는 사용자 승인 없이 아래를 변경하지 않는다.

- A 소유: 질문 생성, 다음 질문 선택, 종료 규칙, Prompt, Trait 판정, Matching 공식
- B 소유: 프론트 화면과 문구, 공개 계약 배선
- 팀 계약: 공개 API, Schema, Mock, OpenAPI
- 정본: `data/master/` 승격과 기존 35건 `department_id`

C 단독으로 가능한 범위:

- `rationale_c/`, C handoff와 평가 보고서
- C 데이터 생성기·감사기·테스트
- 대학알리미 공식 분류 기반 draft
- 기존 엔진을 수정하지 않는 블랙박스 평가
- 실패 사례와 Queue 우선순위 작성

## 7. 검증·실행 명령

의존성이 설치된 환경:

```bash
PYTHONPATH=. python scripts/career_audit_worker_c_improvements.py
PYTHONPATH=. python scripts/career_evaluate_question_major_trace.py
python -m unittest tests.worker_c.test_worker_c_improvement_audit -v
python -m unittest tests.worker_c.test_question_minor_major_trace -v
python -m unittest tests.test_major_matching_persona_diagnostics tests.test_matching_engine -v
python -m compileall scripts tests
git diff --check
```

전국 재생성 테스트는 clean clone에서 입력 파일이 없어 Skip되는 것이 정상이다. 기존 검수 패킷
테스트 중 하나는 clean clone에 전국 입력은 없지만 Manifest에는 실제 Hash가 있다는 정책 차이로
실패할 수 있다. 이를 해결한다는 이유로 기존 Manifest Hash를 임의로 `unavailable`로 되돌리지
말 것.

## 8. 프론트 확인 방법

`worker-c`에는 `frontend/`가 없다. 최신 통합 프론트는 `trait-vector-v2`에 있다. 팀 작업물을
건드리지 않으려면 `/tmp`에 별도 clone 후 실행한다.

```bash
git clone --branch trait-vector-v2 https://github.com/JaewanAppleacc/kosa.git /tmp/kosa-preview
cd /tmp/kosa-preview/frontend
npm ci
npm run dev -- --host 127.0.0.1
```

기본 주소는 `http://127.0.0.1:5173/`이다.

## 9. 관련 문서와 최근 커밋

- `rationale_c/08-practical-review-questions.md` — 실무자 Why 질문과 책임 경계
- `rationale_c/09-improvement-plan-and-expected-effects.md` — 개선방안·기대효과·비용
- `outputs/evaluation/question_to_minor_major_trace.md` — 질문→Trait→관광·호텔 진단
- `data/audit/worker_c_improvement_audit.json` — C 단독 개선 감사 결과
- `outputs/handoff/worker-c-계약학과-추천범위-보고.md` — 계약학과 제외 결과
- `outputs/handoff/worker-c-검수패킷-보고.md` — 검수 패킷과 수치

최근 작업 커밋:

```text
bbc6d28 docs(worker-c): scope minor majors for student MVP
c384fcb test(worker-c): trace questions to minor major draft
cc37acf docs(worker-c): outline improvement impact and expansion cost
e827b93 feat(worker-c): add review improvement audits
6c53762 docs(worker-c): scope solo improvement plan
9c21075 docs(worker-c): answer practical validation questions
4785b88 worker-c: regenerate nationwide contract scope outputs
8a835c6 worker-c: exclude contract departments from recommendation scope
```

## 10. 다음 AI가 시작할 때 확인할 것

1. `git fetch --all --prune`
2. `origin/worker-c` 최신 HEAD 확인
3. 작업 디렉터리가 더럽다면 사용자 변경을 덮어쓰지 말고 `/tmp` 격리 clone 사용
4. 전국 입력 존재 여부 확인
5. A/B 파일과 공개 계약을 수정하지 않는지 변경 파일 목록으로 검증
6. 평가 수치를 추천 정확도로 부를 수 있는지 분모·정답 라벨·비교 기준부터 확인

가장 중요한 다음 질문은 이것이다.

> 전공명을 숨긴 동일한 학생 Persona를 이전 방식과 현재 방식에 넣었을 때, 정답 전공의
> Recall@3/5와 과신 오류율이 실제로 얼마나 달라지는가?
