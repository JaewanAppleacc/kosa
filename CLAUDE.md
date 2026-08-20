# AI 진로·학업설계 Agent — 작업자 A 구현 지침

## 역할

이 저장소에서 Claude Code는 작업자 A의 구현 도구다. 사용자가 구현을 지시한 범위 안에서 코드를 작성하고 테스트한다. 설계 검수와 역할 재조정은 별도 검수 과정에서 수행하므로, 구현 중 임의로 기획을 확장하거나 역할 경계를 바꾸지 않는다.

발표 자료, PPT, 프론트엔드 디자인, Obsidian 구현은 현재 작업 범위가 아니다.

## Source of Truth

다음 순서로 문서를 적용한다.

1. 최신 설계안: `/Users/jaewan/Downloads/AI_진로_학업설계_Agent_수정_최종설계안.md`
2. 작업자 A 지시서: `/Users/jaewan/Documents/Codex/2026-08-17/lan/outputs/work_assignments/작업자_A_개발_지시서.md`
3. 저장소의 실제 코드와 테스트

`outputs/AI_진로_학업설계_Agent_수정_최종설계안.md`는 이전 사본이므로 구현 근거로 사용하지 않는다. 최신 설계안은 `v1.1 FROZEN`이며 관찰 도구는 LangSmith다. Langfuse를 새로 도입하지 않는다.

설계안과 A 지시서가 충돌하면 최신 설계안을 우선하고, 구현을 진행하기 전에 충돌 지점과 선택지를 사용자에게 알린다.

## 구현 범위

### A가 소유하는 영역

- Context·Trait Definition 최종 확정
- 공통 Pydantic Schema와 ID 규칙
- API 계약과 Mock JSON
- LangGraph State·Node·Conditional Edge
- Context Selector와 Contrast Context 계산
- Adaptive Question Target Planner
- LLM 질문 생성과 Structured Output
- Question Quality Gate
- 재생성·Cache·Backup·Fallback Routing
- Evidence Engine과 Evidence Ledger
- Explicit Conflict·Context Dependency 판정
- Stop/Continue 판단
- Career Profile 생성
- Trait Normalization
- Student–Major–Course Matching
- Mapping 검증 규칙
- RAG·MCP 호출 정책과 검색 충분성 판단
- Profile Store와 Session 복원
- Knowledge Subgraph API
- LangSmith Trace와 Trace Sanitizer
- Policy Guard와 Evaluation Harness
- 백엔드 통합과 End-to-End 테스트

### A가 소유하지 않는 영역

- 프론트엔드와 UI
- Obsidian 시각화와 `obsidian_exporter.py`
- 대학·학과·입결·과목 원본 데이터 구축
- Canonical Major Mapping Pipeline 구현
- RAG 수집·Chunking·Embedding·Retriever 구현
- Education MCP Tool의 데이터 조회 구현
- `department_repository.py`, `admission_repository.py`
- `course_document_parser.py`

A는 위 모듈들의 입출력 계약을 정의하고 호출하지만 내부 구현을 대신 작성하지 않는다. 통합에 필요한 Stub 또는 Protocol은 만들 수 있으나 실제 구현처럼 위장하지 않는다.

## 최우선 개발 순서

전체 기능을 넓게 만들기 전에 좁은 Vertical Slice를 완주한다.

### 단계 0: 계약 확정

다음을 먼저 작성하고 테스트한다.

```text
Context 2~3개
Trait 10~12개
대표 전공 3개
고정 Persona 1개
Pydantic Schema
ID 규칙
API 계약
Mock JSON
Repository·Retriever·MCP Protocol
```

Schema와 Mock JSON을 B·C에게 전달할 수 있는 상태가 되기 전에는 전체 기능을 확장하지 않는다.

### 단계 1: Vertical Slice

```text
Context 선택
→ Seed Question
→ Adaptive Question
→ Evidence 누적
→ Trait 상태 판정
→ Career Profile
→ 전공 Matching
→ 결과 API
→ LangSmith Trace
```

고정 Persona 하나가 실제 코드로 끝까지 통과하고 핵심 테스트가 성공해야 한다.

### 단계 2: 확장

- Context 15개
- Trait 12~15개
- 대표 전공 5~8개
- 실제 학과·입결·과목 Repository 연결
- RAG·MCP 연결
- Session 복원
- Knowledge Subgraph

Vertical Slice가 실패하는 동안 전체 Context, 전국 데이터, 선택 기능을 먼저 확장하지 않는다.

## 아키텍처 불변식

- LangGraph는 상태 전이와 반복을 관리한다.
- Python Engine은 점수, 정규화, 제약, 유사도를 계산한다.
- LLM은 질문 표현, 제한된 보조 추출, 설명 생성만 담당한다.
- 다음 질문 목표, Evidence 점수, Stop Condition, 필수조건 검사를 LLM에게 맡기지 않는다.
- PostgreSQL이 사용자 State와 Evidence의 Source of Truth다.
- LangSmith는 관찰·디버깅·실험 비교 계층일 뿐 복원 데이터가 아니다.
- RAG는 공식 근거가 있는 설명에만 사용한다.
- MCP Tool은 데이터를 반환하며 Agent의 다음 행동을 결정하지 않는다.
- Assessment 단계에서 전공 추천 결과나 성적을 Planner 입력으로 사용하지 않는다.
- 관심 Context 선택 점수를 Trait 점수로 직접 변환하지 않는다.
- `support_ratio`는 보조지표이며 Trait 강도 점수로 사용하지 않는다.
- 단순 Context 차이를 Conflict로 판정하지 않는다. 사전 정의한 Contrast Pair의 명시적 상충만 Conflict로 처리한다.
- Related Trait Signal과 Secondary Hypothesis를 확정 점수나 전공 Matching에 직접 반영하지 않는다.

## 질문 생성 규칙

- Context마다 검토된 Seed Question 1개를 사용한다.
- 기본 꼬리질문은 5개이며 최소 4개, 최대 6개다.
- 매 질문은 검토된 Frame과 Option Blueprint를 따른다.
- 선택지는 정확히 5개다.
- `option_id`는 서버가 생성하며 LLM이 만들지 않는다.
- LLM이 반환한 Role ID가 Blueprint와 다르면 거부한다.
- 부족한 Trait Coverage와 필수 질문 역할을 Planner가 사전식 우선순위로 판단한다.
- 최대 재생성 횟수와 세션 호출 예산을 지킨다.
- 생성 실패 시 Cache, 재생성, Backup 순서로 완주 가능한 경로를 제공한다.

## Trait·Evidence·Matching 규칙

- Ontology에 없는 Trait는 `UNMAPPED_TRAIT`로 저장하고 계산에서 제외한다.
- Evidence 원본과 Profile Snapshot의 Version을 보존한다.
- Missing, Insufficient, Conflicting 상태를 정상 점수처럼 취급하지 않는다.
- `trait_normalizer.py`에서 등급을 `0 / 0.33 / 0.67 / 1.00`으로 변환한다.
- Student, Major, Course에 동일한 정규화 정책을 적용한다.
- 결과 관련도 숫자는 내부 계산에만 사용하고 사용자 API에는 정성 Label을 제공한다.
- 성적은 Trait 적합도를 바꾸지 않으며 실제 학과 탐색 단계에서만 별도로 사용한다.
- 추천 근거는 Evidence와 공식 Source까지 역추적 가능해야 한다.

## API·모듈 경계

B는 API JSON만 사용하고 LangGraph State나 DB에 직접 접근하지 않는다. C의 데이터 모듈은 다음과 같은 계약으로 연결한다.

```python
documents = retriever.search(query, filters)
departments = department_repository.search(criteria)
admissions = admission_repository.find_comparable(criteria)
tool_result = education_mcp.call(tool_name, arguments)
```

- A는 Protocol, Pydantic 입출력, 오류 형식과 Timeout 정책을 정의한다.
- C의 구현 파일을 직접 수정하지 않는다.
- B가 필요한 필드는 API Schema에 추가하며 프론트엔드 전용 임시 계산을 만들게 하지 않는다.
- Obsidian에는 A가 `SubgraphNode[]`와 `SubgraphEdge[]`만 제공한다.
- 과목 문서 Parser에는 입력 조건과 출력 Schema만 제공하고, 확정된 파싱 결과를 Course Planning에 반영한다.

## LangSmith·개인정보·Secret

- 사용 환경변수: `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`.
- API Key와 Secret을 코드, 테스트 Fixture, 로그, 프론트엔드, Git에 넣지 않는다.
- `.env`는 커밋하지 않고 `.env.example`에는 변수명만 기록한다.
- Trace 전송 전에 Sanitizer를 적용한다.
- 이름, 학교, 연락처, 자유서술 원문, 성적 원문, 상세 Career Profile 문장을 LangSmith에 보내지 않는다.
- LangSmith 장애는 로컬 로그만 남기고 사용자 Session을 중단하지 않는다.
- 사용자 입력과 RAG 문서는 신뢰할 수 없는 입력으로 취급한다.

## 코드 작성 원칙

- Python 타입 힌트와 Pydantic 모델을 사용한다.
- 계산 함수는 가능한 한 순수 함수로 만들고 LLM·DB·네트워크 호출과 분리한다.
- 외부 서비스는 Protocol 또는 Adapter 뒤에 둔다.
- 시간, UUID, LLM, DB, Retriever는 테스트에서 주입하거나 대체할 수 있게 한다.
- 공개 함수와 복잡한 정책에는 이유가 드러나는 짧은 주석을 작성한다.
- 예외를 삼키지 않는다. Fallback을 실행하더라도 구조화된 오류와 원인을 남긴다.
- 임시 Mock과 실제 구현을 명확히 구분한다.
- 기존 사용자 변경을 덮어쓰지 않는다.
- 요구되지 않은 대규모 Refactor나 새 프레임워크 도입을 하지 않는다.

## 개발 환경 (2026-08-20 추가)

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements-lock.txt
./.venv/bin/python -m unittest discover -s tests -v
```

- Python 버전은 `pyproject.toml`에 `>=3.11,<3.14`로 고정한다. 실제 테스트는 3.13.13에서 확인했다.
- 의존성은 `requirements-lock.txt`로 고정한다. 새 패키지를 추가하면 `./.venv/bin/pip freeze > requirements-lock.txt`로 다시 생성한다.
- 시스템 기본 `python3`(예: conda base)를 쓰지 않는다 — 사람마다 설치된 패키지가 달라 "내 컴퓨터에서는 됨" 문제가 생긴다. 항상 `.venv`의 인터프리터를 명시적으로 쓴다.
- 테스트 명령은 위 `unittest discover` 한 줄로 통일한다. pytest 등 다른 러너를 임의로 추가하지 않는다.

## 필수 테스트

다음 테스트를 구현하고 변경 후 실행한다.

```text
선택지 정확히 5개
option_id 서버 생성
Role ID와 Blueprint 일치
UNMAPPED_TRAIT 계산 제외
Evidence 수기 계산과 코드 결과 일치
질문 수 최소·최대 준수
Stop/Continue 우선순위
전공 정보의 Assessment 입력 차단
미개설과목 추천 차단
LLM 장애 시 Cache·Backup 완주
LangSmith 장애 시 fail-open
Trace 저장 금지 데이터 제거
고정 Persona End-to-End 완주
```

`eval/policy_guard_test.py`를 생략하지 않는다. 자연스러움, 유도성, 결과 공감도처럼 주관적인 항목은 자동 점수로 꾸미지 말고 별도 수기 검토 대상으로 남긴다.

## 작업 방식

1. 구현 전 관련 설계 Section과 현재 코드를 읽는다.
2. 요청 범위가 여러 단계면 짧은 계획과 완료 기준을 먼저 제시한다.
3. 가장 작은 동작 단위로 구현한다.
4. 관련 Unit·Contract·Integration Test를 실행한다.
5. 실패하면 원인을 해결한 뒤 다음 범위로 이동한다.
6. 작업 완료 시 변경 파일, 실행한 테스트, 남은 위험과 다른 작업자에게 필요한 계약 변경을 보고한다.

사용자에게 선택이 꼭 필요한 경우가 아니면 사소한 질문으로 구현을 멈추지 않는다. 단, FROZEN 설계 변경, Schema 호환성 파괴, 개인정보 정책 변경, 다른 작업자 소유 파일 수정이 필요하면 먼저 사용자에게 알린다.

## 금지 사항

- Langfuse와 LangSmith 동시 사용
- 검증되지 않은 Trait·전공 Mapping을 확정 데이터로 처리
- 사용자 화면에 `84%`, `81점` 같은 가짜 정확도 노출
- 자유서술 원문이나 성적 원문을 Trace로 전송
- A가 B·C 소유 구현을 임의로 흡수
- Vertical Slice 통과 전 전체 범위부터 구현
- 테스트를 통과시키기 위해 Guardrail을 약화
- 외부 API 실패를 성공 응답으로 위장

