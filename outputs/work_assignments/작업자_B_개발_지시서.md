# 작업자 B 개발 지시서

## 1. 기준 문서

- 설계안: `outputs/AI_진로_학업설계_Agent_수정_최종설계안.md`
- 발표 및 PPT 제작은 이 지시서의 범위에 포함하지 않는다.
- LangGraph 내부 State나 PostgreSQL에 직접 접근하지 않고 A가 제공하는 API JSON만 사용한다.
- 백엔드 완성을 기다리지 않고 A의 Mock JSON으로 먼저 구현한다.

## 2. 공통 구현 순서

전체 화면을 먼저 완성하지 않는다. 다음 Vertical Slice가 A·B·C 구현을 연결해 끝까지 통과한 뒤 전체 화면으로 확장한다.

### 1단계: 공통 계약과 최소 화면

```text
Context 2~3개
Trait 10~12개
대표 전공 3개
고정 Persona 1개
A가 제공한 공통 Schema·API·Mock JSON
```

### 2단계: Vertical Slice 완주

```text
Context 선택 화면
→ Seed·Adaptive 질문 화면
→ 실제 API 응답 반영
→ Profile 결과 카드
→ 전공 Matching 결과
→ LangSmith 실행 결과와 연결 가능한 session_id 유지
```

고정 Persona 하나가 A의 실제 API와 C의 실제 데이터를 사용해 화면에서 끝까지 통과해야 한다.

### 3단계: 전체 범위 확장

```text
Context 15개
전체 결과·학과·과목 화면
Session 비교
관계 그래프와 Obsidian Export
반응형·오류·Fallback UI
```

Vertical Slice가 통과하기 전에는 부가 화면이나 시각 효과를 우선 구현하지 않는다.

## 3. 담당 범위

### 검사 시작 및 Context 선택

- 15개 Context 관심도 평가 화면을 구현한다.
- 선호 Context 4개 선택 화면을 구현한다.
- Contrast Context 제안 이유와 유지·교체 선택 UI를 구현한다.
- Coverage 부족 시 교체 후보를 확인하는 UI를 구현한다.
- 사용자가 최종 Context 5개를 확정하는 흐름을 구현한다.

### Adaptive 질문 화면

- Seed Question과 꼬리질문을 동일한 질문 컴포넌트에서 표시한다.
- 보기 5개, 현재 Context, 검사 진행 상태를 표시한다.
- 답변 중복 제출을 방지한다.
- 다음 질문 생성 중 Loading 상태를 표시한다.
- 재생성, Cache, Backup 사용 시 사용자가 이해할 수 있는 상태를 제공한다.
- 최소·기본·최대 질문 수가 달라져도 진행 UI가 깨지지 않게 한다.

### 결과 및 탐색 화면

- Career Profile 결과 카드를 구현한다.
- 주요 Trait, 반복 관찰 Context, 추가 탐색 필요 영역을 시각화한다.
- 내부 원점수나 정확도처럼 보이는 숫자를 노출하지 않는다.
- 전공 추천과 Evidence 기반 추천 근거를 표시한다.
- 관련성 높은 전공과 함께 탐색할 전공을 구분한다.
- 전국 대학·실제 학과 탐색 화면을 구현한다.
- 성적 유사 범위 필터를 Trait Matching과 분리해 표시한다.
- 학과 공식 출처와 기준일을 표시한다.
- 고교학점제 과목 추천과 미개설·대체과목 상태를 표시한다.
- 학교 PDF·Excel 파일 업로드 화면을 구현한다.
- C의 파싱 결과를 미리보기로 표시하고 학생이 과목명을 수정·확정할 수 있게 한다.
- 확정된 과목 목록을 A의 Course Planning API에 전달한다.
- 이전 Session의 Profile과 현재 Profile 비교 화면을 구현한다.

### 관계 그래프 및 Export

- A의 Subgraph API가 반환한 `SubgraphNode[]`, `SubgraphEdge[]`만 사용한다.
- Trait–전공–학과–과목 관계 그래프를 렌더링한다.
- Evidence와 Source가 있는 Edge를 구분해 표시한다.
- Obsidian에서 열 수 있는 Markdown 또는 Graph 데이터 Export를 구현한다.
- `src/graph/obsidian_exporter.py`를 포함한 Obsidian 관련 구현 전체를 담당한다.
- Python 기반 Exporter가 필요하면 B의 소유 모듈로 구현하고, A의 Subgraph API 계약만 사용한다.
- DB를 직접 조회하거나 Graph Edge를 프론트엔드에서 임의 생성하지 않는다.

### 프론트엔드 기반 구조

- API Client와 요청·응답 타입을 구현한다.
- Session·질문 진행·결과 조회를 위한 프론트엔드 상태 관리를 구현한다.
- 새로고침 후 Session 복원 UI를 구현한다.
- 정상, 빈 결과, 부분 결과, 오류 상태를 구분한다.
- 입력값과 API 응답을 Schema에 맞춰 검증한다.
- Mock API와 실제 API의 전환 지점을 환경설정으로 분리한다.
- 데스크톱과 모바일에서 사용할 수 있는 반응형 UI를 구현한다.
- 질문과 결과 문장의 가독성·접근성을 검토한다.

### 테스트

- 주요 Component 테스트를 구현한다.
- 다음 사용자 Flow의 프론트엔드 E2E 테스트를 구현한다.

```text
Context 평가 및 선택
질문 응답과 다음 질문 이동
결과 카드 조회
전공·실제 학과 탐색
성적 유사 범위 필터
과목 추천
Session 복원
오류·Fallback 상태 표시
관계 그래프 조회 및 Export
```

## 4. 질문 콘텐츠 책임

- A와 C가 작성한 질문이 고등학생에게 이해하기 쉬운지 검토한다.
- 한 문장에 여러 질문이 섞였는지 확인한다.
- 선택지 간 문장 길이와 난이도가 지나치게 차이 나는지 확인한다.
- 특정 선택지를 긍정적으로 보이게 하는 표현이 있는지 확인한다.
- 가독성 개선안을 A에게 전달하되 Trait·Role Mapping을 직접 변경하지 않는다.

## 5. A에게 받을 것

- API 명세와 Mock JSON
- 질문·Profile·전공·학과·과목·Subgraph Schema
- 정상·오류·빈 결과 응답 예시
- Session 복원 방식
- Loading·Fallback·재시도 상태 코드
- 사용자에게 표시할 정성 관련도 Label
- 과목 파일 업로드·파싱·확정 API 계약

API 형식이 확정되기 전에는 임의의 필드를 실제 계약으로 간주하지 않는다. 필요한 필드가 없으면 A에게 Schema 변경을 요청한다.

## 6. C와 연결되는 방식

- C의 CSV, DB, RAG 결과를 직접 읽지 않는다.
- 학과·입결·과목·출처 정보는 A가 제공하는 API를 통해서만 받는다.
- 데이터 표현 오류를 발견하면 C의 파일을 직접 수정하지 않고 재현 가능한 API 응답과 함께 전달한다.
- C의 과목 파싱 결과도 A의 API 계약을 통해 받고 원본 Parser를 직접 호출하지 않는다.

## 7. 파일 소유권

주요 소유 영역:

```text
frontend/
ui/
src/graph/obsidian_exporter.py
frontend tests/
```

- `src/schemas/`를 직접 수정하지 않는다.
- LangGraph State와 Agent Node를 프론트엔드에 복제하지 않는다.
- 백엔드 내부 점수 계산을 프론트엔드에서 다시 구현하지 않는다.
- Obsidian 관련 파일은 B가 최종 수정하며 A와 C는 직접 변경하지 않는다.

## 8. 완료 조건

- Mock API만으로 전체 사용자 Flow를 끝까지 실행할 수 있다.
- 실제 API로 교체한 뒤 컴포넌트 수정 없이 동일한 Flow가 동작한다.
- 최소·최대 질문 수 변화와 부분 Profile을 정상적으로 표현한다.
- 내부 숫자와 저장 금지 개인정보가 화면에 노출되지 않는다.
- Loading·오류·Fallback 상태에서 화면이 멈추지 않는다.
- 관계 그래프는 A의 Subgraph API 결과만으로 생성된다.
- PDF·Excel 과목 파싱 결과를 확인·수정·확정하는 흐름이 동작한다.
- 주요 Component 테스트와 프론트엔드 E2E 테스트가 통과한다.
