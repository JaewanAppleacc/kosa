# 작업자 C 개발 지시서

## 1. 기준 문서

- 설계안: `/Users/jaewan/Downloads/AI_진로_학업설계_Agent_수정_최종설계안.md`
- 발표 및 PPT 제작은 이 지시서의 범위에 포함하지 않는다.
- A가 확정한 Schema와 함수 Signature를 기준으로 데이터를 제공한다.
- Agent의 호출 여부, 다음 질문, Stop Condition, 최종 추천 판단은 구현하지 않는다.

## 2. 공통 구현 순서

전체 데이터 수집을 먼저 끝내려 하지 않는다. 다음 Vertical Slice에 필요한 최소 데이터를 우선 제공하고 A·B·C 연결이 끝까지 통과한 뒤 전체 범위로 확장한다.

### 1단계: 최소 데이터 확정

```text
Context 2~3개
Trait 10~12개
대표 전공 3개
고정 Persona 1개
대표 실제 학과와 과목의 소형 Fixture
```

### 2단계: Vertical Slice 완주

```text
질문·Option Blueprint
→ Evidence 계산용 Fixture
→ 대표 전공 Profile
→ 실제 학과 Repository 응답
→ RAG 검색 결과와 공식 출처
```

고정 Persona 하나가 A의 실제 API와 B의 실제 화면에서 끝까지 통과하는 데 필요한 실제 데이터를 제공한다.

### 3단계: 전체 범위 확장

```text
Context 15개
Trait 12~15개
대표 전공 5~8개
전국 실제 학과 Master
입결·과목·RAG 확장
```

Vertical Slice가 통과하기 전에는 전국 데이터의 세부 정제나 RAG 대상 확대를 우선하지 않는다.

## 3. 담당 범위

### Context·Trait 및 질문 콘텐츠 초안

- 15개 Context Definition 초안을 작성한다.
- Trait 12~15개 Definition 초안을 작성한다.
- 각 Context가 Shared Trait를 관찰할 수 있도록 Coverage를 확인한다.
- A가 담당하는 핵심 Context 5개를 제외한 나머지 Context의 Seed Question과 Option Blueprint 초안을 작성한다.
- Question–Trait Mapping에 근거와 작성자를 기록한다.
- A의 최종 검증과 B의 가독성 검토 결과를 반영한다.

### 대학·학과 Master 데이터

- 전국 4년제 대학 목록을 공식 데이터로 수집한다.
- 대학별 실제 학과 Master DB를 구축한다.
- 대학명과 학과명을 정규화한다.
- 중복, 명칭 변경, 폐지, 출처 불명 학과를 구분한다.
- 모든 데이터에 공식 출처 URL과 기준일을 기록한다.
- 원본 데이터와 정제 데이터를 분리해 보존한다.

### Canonical Major Mapping

- Exact Match와 Alias Match를 구현한다.
- 미매핑 학과에 대한 Embedding Candidate Search를 구현한다.
- 필요한 경우 LLM Structured Classification을 구현한다.
- 낮은 확신 결과는 자동 확정하지 않고 `REVIEW_REQUIRED`로 남긴다.
- Mapping 결정 근거와 버전을 저장한다.

### 입결 데이터

- 공식 비교 자료가 존재하는 학과 15~30개의 AdmissionReference를 구축한다.
- 같은 학년도, 전형, 지표, 공개 기준인지 확인하는 비교 가능성 필터를 구현한다.
- 비교할 수 없는 자료를 하나의 성적 순위로 합치지 않는다.
- 합격 가능성을 단정하는 값은 생성하지 않는다.

### 전공·과목 Profile

- 대표 전공 Profile 5~8개를 구축한다.
- Major–Trait Mapping 초안을 작성하고 공식 근거를 연결한다.
- 특정 고등학교의 실제 개설과목 데이터를 구축한다.
- 과목명을 정규화하고 유사 과목 Alias를 관리한다.
- Subject–Trait Mapping 초안을 작성한다.
- 미개설과목, 대체과목, 공동교육과정 여부를 구분할 수 있게 한다.

### 학교 과목 문서 파싱

- `course_document_parser.py`를 구현한다.
- 학교 교육과정 PDF·Excel에서 과목명과 관련 필드를 추출한다.
- 추출한 과목명을 Canonical Course와 Alias 기준으로 정규화한다.
- 확신이 낮거나 매핑되지 않은 값은 사용자 확인 대상으로 표시한다.
- A가 확정한 Schema로 파싱 결과, 오류, 확인 필요 항목을 반환한다.
- Agent 판단이나 최종 과목 추천은 Parser 안에서 수행하지 않는다.

### RAG Pipeline

- 대학·학과 공식 홈페이지 자료를 수집한다.
- 문서를 정제하고 출처 URL, 기준일, 문서 유형 Metadata를 부여한다.
- LangChain Text Splitter를 사용해 Chunk를 생성한다.
- Embedding과 pgvector 색인을 구현한다.
- Keyword/BM25, Vector Search, 필요한 경우 RRF Retriever를 구현한다.
- 검색 결과를 A가 확정한 `RetrievedDocument[]` 형식으로 반환한다.
- 검색 결과에 본문 일부, 공식 URL, 기준일, 점수·순위 Metadata를 포함한다.
- 검색 근거가 없는 내용을 새로 생성하지 않는다.

### Repository 및 MCP

- 다음 Repository를 구현한다.

```text
src/repositories/department_repository.py
src/repositories/admission_repository.py
```

- Education Data MCP Tool의 실제 데이터 조회 기능을 구현한다.
- Tool 이름과 입력·출력 타입은 A가 확정한 계약을 따른다.
- MCP Tool은 조회 결과를 반환할 뿐 Agent의 다음 행동을 결정하지 않는다.
- 오류, 빈 결과, 출처 누락 상태를 명시적으로 반환한다.

### 검증 입력과 데이터 테스트

- 고정 Persona 답변 데이터를 작성한다.
- Hand-Calculated Fixture 초안을 작성한다.
- RAG 검색 Query별 기대 문서와 허용 가능한 결과를 작성한다.
- Major–Trait·Subject–Trait Mapping 기대값을 작성한다.
- LLM 장애 대비 질문 Cache 데이터를 준비한다.
- 데이터 누락, 중복, 타입, 출처, 기준일을 자동 검사한다.
- A의 Evaluation Harness가 사용할 Fixture를 고정된 파일 형식으로 제공한다.

## 4. A에게 받을 것

- Context·Trait Definition 최종본
- Department·AdmissionReference·CourseProfile Schema
- Canonical Mapping 입력·출력 계약
- Repository 함수 Signature
- `RetrievedDocument` Schema
- MCP Tool Schema
- Major–Trait·Subject–Trait Mapping 검증 규칙
- Persona와 Fixture 파일 형식
- `course_document_parser.py`의 입력 파일 조건과 파싱 결과 Schema

계약에 없는 필드가 필요하면 독자적으로 추가하지 않고 A에게 변경을 요청한다.

## 5. A에게 제공할 것

- 정규화된 대학·학과 Master 데이터
- Canonical Mapping 결과와 `REVIEW_REQUIRED` 목록
- 비교 가능한 AdmissionReference
- MajorProfile과 CourseProfile 데이터
- 출처가 포함된 `RetrievedDocument[]`
- 계약을 준수하는 MCP Tool
- Persona·Hand-Calculated Fixture·검색 기대값
- 데이터 품질 검사 결과
- 정규화된 학교 과목 파싱 결과와 사용자 확인 필요 항목

## 6. B와 연결되는 방식

- B에게 CSV·DB 접근 권한이나 내부 데이터 구조를 직접 의존하게 하지 않는다.
- 화면에 필요한 필드가 누락되면 A의 API Schema를 통해 추가한다.
- 문구 가독성 피드백은 반영하되 Trait Mapping 변경은 A의 승인을 받는다.
- B가 과목 파싱 결과를 확인할 수 있도록 A가 확정한 응답 Schema를 준수한다.
- Obsidian 관련 파일은 수정하지 않는다.

## 7. 파일 소유권

주요 소유 영역:

```text
data/
datasets/
sources/
src/rag/
src/mcp/
src/repositories/department_repository.py
src/repositories/admission_repository.py
src/engines/canonical_mapper.py
src/engines/admission_filter.py
src/agents/course/course_document_parser.py
data/eval_fixtures/
```

- `src/schemas/`와 LangGraph 파일을 직접 수정하지 않는다.
- A가 소유한 Matching과 Agent 판단 로직을 데이터 모듈에 복제하지 않는다.
- `trait_relation_engine.py`가 구현되는 경우 Relation 데이터 초안만 제공하고 Engine은 수정하지 않는다.

## 8. 완료 조건

- 대학·학과·입결·과목 데이터가 A의 Schema Validation을 통과한다.
- Canonical Mapping의 미확정 결과가 자동 확정되지 않고 별도로 표시된다.
- 비교 불가능한 입결 데이터가 같은 정렬 결과에 섞이지 않는다.
- Retriever가 공식 출처와 기준일을 포함한 결과를 반환한다.
- MCP Tool이 계약된 입력·출력과 오류 형식을 준수한다.
- Persona와 Hand-Calculated Fixture를 A의 Evaluation Harness에서 바로 읽을 수 있다.
- PDF·Excel 과목 문서가 계약된 Schema로 파싱되고 불확실한 값이 확인 대상으로 구분된다.
- B가 데이터 원본이나 DB에 직접 접근하지 않아도 필요한 정보를 API로 받을 수 있다.
