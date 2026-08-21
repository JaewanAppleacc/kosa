# 작업자 A 개발 지시서

## 1. 기준 문서

- 설계안: `outputs/AI_진로_학업설계_Agent_수정_최종설계안.md`
- 현재 기준은 `v1.1 FROZEN`(설계안 §31)과 LangSmith다. (2026-08-21: 설계안 첫머리는 v1.1인데 §31만 v1.0으로 남아있던 내부 불일치를 v1.1로 통일해 바로잡았다 — 별도의 v1.1 문서가 있는 게 아니라, 이 설계안 자체가 v1.1이다)
- 발표 및 PPT 제작은 이 지시서의 범위에 포함하지 않는다.
- 설계 변경이 필요하면 먼저 변경 이유와 B·C에 미치는 영향을 기록한 뒤 합의한다.

## 2. 공통 구현 순서

전체 범위를 각자 먼저 완성하지 않는다. 다음 Vertical Slice가 A·B·C 구현을 연결해 끝까지 통과한 뒤 전체 범위로 확장한다.

### 1단계: 공통 계약 확정

```text
Context 2~3개
Trait 10~12개
대표 전공 3개
고정 Persona 1개
공통 Schema·API·Mock JSON
```

### 2단계: Vertical Slice 완주

```text
Context 선택
→ Seed·Adaptive 질문
→ Evidence 누적
→ Profile 생성
→ 전공 Matching
→ 결과 카드
→ LangSmith Trace
```

완료 조건은 고정 Persona 하나가 A의 실제 API, B의 실제 화면, C의 실제 데이터를 사용해 중단 없이 끝까지 통과하는 것이다.

### 3단계: 전체 범위 확장

```text
Context 15개
Trait 12~15개
대표 전공 5~8개
전국 실제 학과 Master
입결·과목·RAG 확장
```

Vertical Slice가 통과하기 전에는 전체 Context 전용화나 선택 기능을 먼저 확장하지 않는다.

## 3. 담당 범위

### 공통 계약 확정

- Context·Trait Definition의 최종본을 확정한다.
- 공통 Pydantic Schema를 정의한다.
- API 요청·응답 계약과 Mock JSON을 확정한다.
- `trait_id`, `context_id`, `major_id`, `department_id`, `subject_id`, `session_id` 명명 규칙을 확정한다. (설계안 §6-6·§20이 일관되게 `subject_id`를 쓰므로 이를 정본으로 하고, `CourseProfile`은 여러 `subject_id`를 담는 결과 집계 객체명으로 구분한다.)
- 결측값, 오류 응답, 정성 관련도 Label의 표현 형식을 확정한다.
- B와 C가 실제 구현을 기다리지 않고 작업할 수 있도록 Mock 응답을 먼저 제공한다.

최소 확정 Schema:

```text
GeneratedQuestion
GeneratedOption
Evidence
AssessmentState
CareerProfile
MajorProfile
Department
AdmissionReference
CourseProfile
RetrievedDocument
SubgraphNode
SubgraphEdge
```

### Assessment 및 LangGraph

- LangGraph State·Node·Conditional Edge를 구성한다.
- Context Selector와 Contrast Context 계산을 구현한다.
- Coverage 부족 시 교체 후보를 제안하는 HITL 흐름을 구현한다.
- Adaptive Question Target Planner를 구현한다.
- LLM 질문 생성과 Structured Output 검증을 구현한다.
- Question Quality Gate를 구현한다.
- 질문 재생성, Cache, Backup, Fallback Routing을 구현한다.
- Evidence Engine과 Evidence Ledger 갱신을 구현한다.
- Explicit Conflict와 Context Dependency를 구분한다.
- Stop/Continue 조건과 `stop_reason`을 구현한다.
- Career Profile 생성과 불충분 Evidence Masking을 구현한다.
- `trait_normalizer.py`를 구현하고 Trait 등급을 `0 / 0.33 / 0.67 / 1.00`으로 변환한다.
- Missing·Insufficient·Conflicting 상태의 Vector 반영 규칙을 구현한다.
- Student·Major·Course에 동일한 정규화 정책을 적용한다.

### 추천 및 데이터 사용 정책

- Student–Major–Course Matching을 구현한다.
- Major–Trait·Subject–Trait Mapping 검증 규칙을 구현한다.
- 성적은 Trait Matching과 분리하고 실제 학과 탐색 단계에서만 사용한다.
- AdmissionReference 비교 결과를 사용자에게 어떻게 노출할지 결정한다.
- RAG와 MCP를 언제 호출할지 결정한다.
- 검색 Query, Metadata Filter, 검색 충분성 판단, 근거 없는 설명 생성 금지 정책을 구현한다.
- C가 제공한 Retriever와 MCP Tool의 반환값을 LangGraph Node에서 사용한다.
- C가 반환한 PDF·Excel 과목 파싱 결과와 사용자의 확인 결과를 Course Planning Workflow에 반영한다.

### 저장·관찰·그래프

- Profile Repository와 Session 저장·복원을 구현한다.
- PostgreSQL을 사용자 상태와 Evidence의 Source of Truth로 유지한다.
- Knowledge Subgraph 추출 API를 구현한다.
- LangSmith Trace를 Assessment Graph에 연결한다.
- `planner_decision_reason`, `stop_reason`, Node·Edge 실행, Token·Latency·Error를 기록한다.
- Trace Sanitizer와 LangSmith fail-open을 구현한다.
- 이름, 학교, 연락처, 자유서술 원문, 성적 원문, 상세 Profile 문장을 Trace에 전송하지 않는다.

### 정책 및 평가 코드

- `policy_guard.py`를 구현한다.
- Evaluation Harness의 공통 실행 구조를 구현한다.
- 다음 평가 코드를 소유한다.

```text
eval/assessment_eval.py
eval/trait_eval.py
eval/matching_eval.py
eval/retrieval_eval.py
eval/policy_guard_test.py
eval/end_to_end_eval.py
```

- C가 제공하는 Persona, Hand-Calculated Fixture, 검색 기대값을 테스트 입력으로 사용한다.
- 최소한 다음 항목은 자동 검증한다.

```text
선택지 5개
option_id 서버 생성
Role ID와 Blueprint 일치
UNMAPPED_TRAIT 결과 계산 제외
Evidence 수기 계산과 코드 결과 일치
질문 수 최소·최대 준수
전공 순위의 Assessment 입력 차단
미개설과목 추천 차단
LLM 장애 시 Cache·Backup 완주
LangSmith 장애 시 세션 완주
Trace 저장 금지 데이터 차단
고정 Persona End-to-End 완주
```

### 통합

- B의 프론트엔드와 C의 데이터 모듈을 공통 계약에 맞춰 통합한다.
- 다른 작업자의 내부 파일을 직접 참조하지 않고 API·Repository·Tool Interface를 통해 연결한다.
- Schema 변경이 필요하면 B와 C에게 변경 내용과 새로운 Mock JSON을 동시에 제공한다.

## 4. 질문 콘텐츠 책임

- Question Schema, Role 체계, Trait Mapping 규칙을 정의한다.
- 발표 우선 핵심 Context 5개의 Seed Question과 Option Blueprint를 작성한다.
- C가 작성한 나머지 Context의 질문 초안을 검토한다.
- B의 가독성 검토를 반영한 뒤 최종 Mapping을 승인한다.
- 질문 표현이 자연스럽다는 이유만으로 Trait Mapping을 변경하지 않는다.

## 5. B에게 제공할 것

- OpenAPI 또는 동일 수준의 API 명세
- Endpoint별 정상·오류·빈 결과 Mock JSON
- Profile·전공·학과·과목·Subgraph 응답 Schema
- Session 복원 방식
- Loading·Fallback·재시도 상태 코드
- 내부 점수 대신 사용자에게 표시할 정성 Label
- 과목 파일 업로드·파싱·사용자 확인 API 계약

권장 Endpoint:

```text
POST /assessment/interest-rating
POST /assessment/context-select
POST /assessment/next-question
POST /assessment/answer
GET  /profile/{session_id}
GET  /majors/{session_id}
GET  /departments/{major_id}
GET  /subjects/{session_id}
GET  /subgraph/{session_id}
```

## 6. C에게 제공할 것

- Department·AdmissionReference·CourseProfile Schema
- Canonical Mapping 입출력 계약
- Repository 함수 Signature
- `RetrievedDocument` Schema와 RAG 검색 계약
- MCP Tool 이름과 입출력 타입
- Major–Trait·Subject–Trait Mapping 검증 규칙
- Persona·Fixture가 충족해야 할 필드
- `course_document_parser.py`의 입력 파일 조건과 파싱 결과 Schema

## 7. 파일 소유권

주요 소유 영역:

```text
src/agents/
src/engines/evidence_engine.py
src/engines/conflict_engine.py
src/engines/context_selector.py
src/engines/trait_normalizer.py
src/engines/profile_vectorizer.py
src/engines/similarity_engine.py
src/engines/course_engine.py
src/engines/policy_guard.py
src/schemas/
src/memory/
src/observability/
src/repositories/profile_repository.py
src/graph/subgraph_builder.py
eval/
```

- `trait_relation_engine.py`는 OPTIONAL/CUTTABLE이다. 구현하는 경우 A가 Engine을 담당하고 C의 Trait Relation 데이터 초안을 입력으로 사용한다.
- Obsidian 관련 구현과 `obsidian_exporter.py`는 B가 소유한다. A는 Subgraph API만 제공한다.
- `src/agents/` 중 `src/agents/course/course_document_parser.py`는 C가 소유한다. A는 Parser의 출력 계약과 Course Planning 연결만 담당한다.

- B 또는 C의 소유 파일은 직접 수정하지 말고 Interface 변경 요청을 전달한다.
- 공통 Schema와 설정 파일의 최종 수정 책임은 A에게 둔다.

## 8. 완료 조건

```text
고정 Persona가 Context 선택
→ Seed와 Adaptive 질문
→ Evidence 누적
→ Profile 생성
→ 전공·실제 학과 탐색
→ 과목 추천
→ Knowledge Subgraph 반환
까지 중단 없이 완료된다.
```

- B가 Mock API에서 실제 API로 교체해도 화면 데이터 구조가 깨지지 않는다.
- C의 Repository·Retriever·MCP를 구현체 교체만으로 연결할 수 있다.
- LLM, LangSmith 또는 외부 데이터 조회가 실패해도 정의된 Fallback으로 종료된다.
- 핵심 Evaluation Harness와 `policy_guard_test.py`가 통과한다.
