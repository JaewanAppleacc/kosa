# AI 진로·학업설계 Agent — 수정 최종 설계안

> **v1.1 FROZEN** (2026-08-20) — Vertical Slice 구현 착수 시점으로 동결. LangSmith 관찰 계층을 반영했으며, 변경 범위와 재변경 조건은 §31 참고.

## 0. 프로젝트 정의

고등학생이 자신이 좋아하는 관심 Context 안에서 상황형 질문에 답하면, AI가 답변에 나타난 세부 관심·행동·사고 특성을 추출한다. 학생과 대학 전공·고교 선택과목을 동일한 Trait 공간에 벡터화하고 유사도를 계산하여 다음 의사결정을 지원한다.

```text
15개 Context 관심도 평가
→ 사용자 선호 Context 4개 선택
→ Agent가 거리·Coverage를 고려한 Contrast Context 1개 제안
→ 학생 확인·교체 후 최종 Context 5개
→ Context별 Seed Question
→ 선택 답변에 맞는 LLM 꼬리질문 생성
→ 세부 Trait Evidence 누적
→ Student Multi-Vector Profile 생성
→ 대표 전공 및 실제 학과 관련도 계산
→ 학교 개설과목을 반영한 과목 추천
```

이 서비스는 표준화된 심리검사나 학생 선발 도구가 아니다.

> 학생 간 능력을 비교하는 것이 아니라, 한 학생의 답변에서 반복적으로 나타나는 활동 선호와 문제 접근 방식을 탐색해 전공·과목 선택을 지원하는 개인용 진로 탐색 도구다.

---

# 1. 공모전 프로토타입 범위

## 실제 구현

- 단일 데모 사용자 `demo_user_01`
- `user_id` 기반 실제 Profile Store와 Session 복원
- 관심 Context 15개
- 15개 전체에 대한 간단한 관심도 평가
- 학생이 선택한 선호 Context 4개 + Agent가 제안하는 Contrast Context 1개
- Coverage 부족 시 교체 후보를 제시하고 학생이 최종 확정하는 HITL
- 15개 Context의 고정 Seed Question 각 1개
- 핵심 5개 Context의 전용 Question Frame과 검토된 Option Blueprint
- 나머지 10개 Context의 공용 Shared Trait Frame 기반 Fallback 경로
- Context당 LLM 생성 꼬리질문 최소 4개·기본 5개·최대 6개
- 상황형 질문 최소 25개·기본 30개·최대 35개
- 세부 Trait Ontology 실제 구현 12~15개, 후속 확장 20~30개, 장기 확장 50~100개
- 상위 Career Dimension 6~10개
- 대표 전공군 5~8개
- 전국 4년제 대학 실제 학과 Master DB
- 비교 가능한 공식 입결 자료가 있는 실제 학과 15~30개의 성적 필터링 데모
- 특정 고등학교 교육과정 데이터 1개
- 선택적 성적 기준 정렬 샘플
- Education Data MCP 서버 1개
- LangSmith 기반 LangGraph 실행 추적과 평가 메타데이터 기록
- 학생 관련 Subgraph의 Obsidian 시각화
- Evaluation Harness와 발표용 캐시

## 시연 또는 제한 범위로 구현

- 실제 Store에 저장된 1학기 Profile을 새 Session에서 불러와 2학기 Profile과 비교
- API 장애 시 캐시된 질문 경로
- 학교 PDF 또는 Excel에서 추출한 과목의 사용자 확인
- 추천 결과의 학생별 Knowledge Subgraph

## 후속 확장

- 회원가입과 실제 다중 사용자 운영
- 전국 대학 학과 공식 홈페이지 전체 수집·정밀 RAG
- 전국 학교 교육과정 자동 연동
- 대학별 정밀 합격 가능성 예측
- 모든 사용자 대상 Obsidian Vault 제공

---

# 2. 검사 정책

검사 규모는 고정 문항 수 하나가 아니라 최소·기본·최대 범위와 종료 규칙으로 관리한다.

```yaml
assessment_policy:
  available_contexts: 15
  interest_rating_items: 15
  user_selected_contexts: 4
  contrast_contexts: 1
  coverage_replacement_suggestions_max: 2
  selected_contexts_total: 5
  seed_questions_per_context: 1
  adaptive_questions_min_per_context: 4
  adaptive_questions_default_per_context: 5
  adaptive_questions_max_per_context: 6
  scenario_questions_min: 25
  scenario_questions_typical: 30
  scenario_questions_max: 35
  max_regeneration_per_question: 1
  regeneration_budget_per_session: 3
  generation_timeout_seconds: 6
  max_llm_calls_per_session: 40
```

## 질문 구성

```text
15개 Context 관심도 평가
→ 사용자가 선호 Context 4개 선택
→ Agent가 거리·Trait Coverage를 고려한 Contrast Context 1개 제안
→ Coverage 부족 시 교체 후보 최대 2개 제안
→ 학생 확인 후 심층 Context 5개 확정

각 Context:
고정 Seed Question 1개
+ 실시간 생성 꼬리질문 최소 4개·기본 5개·최대 6개

전체 상황형 질문:
최소 5 × (1 + 4) = 25문항
기본 5 × (1 + 5) = 30문항
최대 5 × (1 + 6) = 35문항
```

15개 관심도 평가는 Context 선택용 입력이며 Career Trait 점수로 직접 사용하지 않는다. 상황형 질문은 기본 30개를 목표로 하고, 필수 질문 역할 충족·Primary Evidence 상충 여부·추가 확인 필요성에 따라 25~35개 사이에서 종료한다. 실제 소요시간과 후반부 응답 품질은 파일럿으로 측정한다.

## 2-1. 문항 수 산정 근거

현재 숫자는 논문이 직접 보증한 정답이 아니라, 기존 진로흥미검사와 컴퓨터 적응검사 연구를 제품 구조에 적용한 초기 설정이다.

- O*NET Mini Interest Profiler는 RIASEC 6개 척도에 각 5문항, 총 30문항을 사용했다. 개발진은 너무 적은 문항이 신뢰도와 활동 내용 범위를 제한할 수 있어 척도당 5문항을 선택했다. 5문항 척도의 Cronbach's α는 개발 표본에서 .70~.75(M=.73), 별도 검증 표본에서 .74~.81이었다.
- O*NET Interest Profiler Short Form은 RIASEC 척도당 10문항, 총 60문항을 사용하며 더 높은 신뢰도를 보였다. 문항 수뿐 아니라 내용 범위와 구조 적합성을 함께 고려했다.
- CAT 연구에서는 모든 사용자에게 같은 고정 길이를 강제하기보다 최소·최대 문항 수, 측정 정보량, Content Balancing을 함께 사용하는 방식이 권장된다.

참고 자료:

- [O*NET Mini Interest Profiler 개발·검증 보고서](https://www.onetcenter.org/dl_files/Mini-IP.pdf)
- [O*NET Interest Profiler Short Form 보고서](https://www.onetcenter.org/dl_files/IPSF_Psychometric.pdf)
- [Computerized Adaptive Testing 종료 규칙 비교 연구](https://link.springer.com/article/10.3758/s13428-018-1068-x)
- [다차원 CAT Content Balancing 연구](https://pmc.ncbi.nlm.nih.gov/articles/PMC5841469/)

RIASEC 척도와 본 서비스의 관심 Context는 동일한 개념이 아니므로 `척도당 5문항`을 그대로 과학적 근거라고 주장하지 않는다. 기본 30문항은 연구 사례를 참고한 파일럿 시작점이며 최종값은 25·30·35문항 조건 비교로 결정한다.

---

# 3. 전체 Architecture

```text
                              [ User ]
                                 │
                                 ▼
                      LangGraph Orchestrator
                                 │
             ┌───────────────────┼───────────────────┐
             ▼                   ▼                   ▼
      Assessment Workflow   Major Exploration   Course Planning
           / Agent              Workflow           Workflow
             │                   │                   │
             ▼                   ▼                   ▼
       Evidence Engine      Matching Engine      Course Engine
             │                   │                   │
             └──────────────┬────┴──────────────┬────┘
                            ▼                   ▼
                    Education Data MCP     Student Subgraph
                            │                   │
                 ┌──────────┼──────────┐        ▼
                 ▼          ▼          ▼     Obsidian
              CareerNet  University   RAG DB  Presentation
                           Data

PostgreSQL
├ User / Session / State
├ Profile Snapshot / Evidence Version
├ Question / Answer
├ Trait Ontology / Evidence
├ Student Vector
├ Major / Department Vector
├ Department Master / Admission Reference
├ Subject Vector
├ Canonical Mapping
└ Source / Version

pgvector
├ Department description embeddings
├ Curriculum embeddings
└ Semantic duplicate detection

LangSmith
├ LangGraph Node / Conditional Edge Trace
├ LLM Latency / Token / Error
└ Evaluation Metadata (PII 제외)
```

## 구성 원칙

- LangGraph는 상태 전이와 반복을 관리한다.
- Python Engine은 점수·제약·유사도를 계산한다.
- LLM은 질문 표현, 제한된 Trait 추출, 설명 생성을 담당한다.
- PostgreSQL이 Source of Truth다.
- LangSmith는 Source of Truth가 아니라 실행 관찰·디버깅·실험 비교 계층이다.
- Obsidian은 계산 시스템이 아니라 발표용 Explainability View다.
- RAG는 공식 자료에 근거한 설명을 생성할 때만 사용한다.

---

# 4. Main Orchestrator

사용자의 현재 단계는 LLM이 아니라 State 기반 규칙으로 Routing한다.

```text
CAREER_ASSESSMENT
MAJOR_EXPLORATION
COURSE_PLANNING
PROFILE_REVISIT
```

```python
if not state.career_profile:
    return "assessment"
if not state.selected_major:
    return "major_exploration"
if state.course_planning_requested:
    return "course_planning"
return "profile_result"
```

Major Exploration과 Course Planning은 Agent라는 이름을 사용할 수 있지만, 발표에서는 자율성을 과장하지 않는다.

> LangGraph가 세 전문 Workflow를 조율하며, Assessment Workflow는 현재 Evidence에 따라 다음 질문 목표와 행동을 선택하는 Agent 구조로 동작한다.

---

# 5. Assessment Workflow

## 5-1. Context 선택과 순차 진행

먼저 15개 Context의 관심도를 1~5점으로 빠르게 평가한다.

```text
1: 전혀 관심 없음
2: 별로 관심 없음
3: 보통
4: 관심 있음
5: 매우 관심 있음
```

학생이 선호 Context 4개를 직접 선택한다. Agent는 선택된 4개와 활동 방식의 거리가 멀면서 주요 Shared Trait를 교차 확인할 수 있는 Contrast Context 1개를 제안한다. 강한 비선호를 강제하지 않도록 원칙적으로 관심도 2~3점인 Context를 후보로 사용하고, 1점 Context는 학생이 직접 허용한 경우에만 제안한다.

Agent는 최종 후보 5개의 Trait Coverage도 함께 검사한다. Coverage가 부족하면 Contrast Context 또는 선호 Context 중 하나를 바꿀 수 있는 교체 후보를 최대 2개와 이유를 제시한다. 학생은 기존 선택 유지, 추천 수용, 다른 Context 선택 중 하나를 고르고 최종 5개를 확정한다. Context 거리와 Coverage는 §6-5의 사전 정의 데이터만 사용하며 학생의 전공 순위는 참조하지 않는다.

Context 선택 자체는 Career Trait 점수로 사용하지 않는다. 예를 들어 봉사 Context의 관심도가 낮더라도 공감·협업·책임감 Trait를 낮게 계산하지 않으며, 해당 Trait는 게임·미디어·학교생활 등 선택된 Context에서 별도로 관찰한다.

질문은 Context를 하나씩 완전히 끝내고(Seed와 꼬리질문 전부) 다음 Context로 넘어가는 순차 구조로 진행한다.

```text
처리 순서
= 선호 Context 4개 (학생이 선택한 순서 또는 관심도 높은 순)
→ Contrast Context 1개 (항상 마지막)

Context 하나당
Seed Question 1개
+ 꼬리질문 4~6개
→ 완료 후 다음 Context로 이동
```

Contrast Context를 항상 마지막에 배치하는 이유는, 다른 4개 Context에서 이미 쌓인 Evidence가 있어야 "여기서도 같은 성향이 유지되는가"를 확인하는 Contrast 본연의 목적이 의미를 가지기 때문이다.

처리 순서상 가장 먼저 진행되는 Context는 아직 비교할 다른 Context의 Evidence가 없다. 이 경우에 한해 §7-2의 꼬리질문 3번(교차 확인) 역할을 관심 지점의 추가 심화로 대체하고, 두 번째 Context부터는 정상적으로 교차 확인 역할을 수행한다.

## 5-2. Assessment Graph

```text
START
 ↓
user_id Session 생성 / 이전 Profile Store 조회
 ↓
15개 Context 관심도 평가
 ↓
학생이 선호 Context 4개 선택
 ↓
Agent가 Contrast Context 1개 제안
 ↓
Agent가 최종 후보의 Trait Coverage 검사
 ↓
필요 시 교체 후보 최대 2개와 이유 제안
 ↓
학생 확인·유지·교체 후 Context 5개 확정, 처리 순서 확정(선호 4개 → Contrast 마지막) [HITL]
 ↓
다음 순서의 Context 선택
 ↓
Context Seed Question 출력
 ↓
Initial Evidence Update
 ↓
Question Target Planner
 ↓
Option Blueprint Selector
 ↓
Question Generator — LLM
 ↓
Quality Gate
 ├ PASS → 질문 출력
 └ FAIL → 1회 재생성
              └ FAIL / TIMEOUT → Cache 또는 Backup
 ↓
학생 답변
 ↓
Trait Evidence Update
 ↓
Student Vector Update
 ↓
Context별 최소 꼬리질문 4개 완료?
 ├ NO → Planner
 └ YES → Stop Condition Check
              ├ CONTINUE → Planner
              └ STOP 또는 최대 6개 → 다음 Context
 ↓
전체 Context 완료?
 ├ NO → 다음 순서의 Context로 이동 (해당 Context Seed부터 다시 시작)
 └ YES → Career Profile 생성
 ↓
END
```

## 5-3. Adaptive Stop Condition

정식 IRT 기반 CAT의 표준오차는 보정된 문항 Bank가 필요하므로 프로토타입에서 바로 사용하지 않는다. MVP에서는 임의의 코사인 임계값이나 전공 순위 안정성을 종료 기준으로 사용하지 않고, 질문 역할 충족과 Primary Evidence 상태를 이산 규칙으로 검사한다.

```text
꼬리질문 4개 미만
→ 무조건 CONTINUE

꼬리질문 4개 완료 후
├ Seed와 필수 꼬리질문 역할이 모두 충족됨
├ 해결되지 않은 Explicit Conflict가 없음
└ 추가 확인이 필요한 핵심 Primary Trait가 없음
   → STOP 가능

그 외
→ 기본 5번째 꼬리질문 진행

5번째 이후에도 Explicit Conflict 또는 필수 역할 미충족
→ 6번째 꼬리질문 진행

6번째 완료
→ 강제 STOP
```

`새로운 핵심 Trait`는 LLM이 자유롭게 추출한 Secondary Trait가 아니라 Option Blueprint의 Primary Trait ID를 기준으로 판정한다. 초기 내부 파일럿은 이 규칙의 통계적 타당도를 확정하는 용도가 아니라 조기 종료·무한 반복·역할 누락 같은 UX와 로직 오류를 점검하고 데모용 초기 휴리스틱을 조정하는 용도로 사용한다.

---

# 6. Trait Ontology

학생 답변, 대학 전공, 고교 과목을 같은 의미 공간에서 비교하기 위해 고정 Trait Ontology를 사용한다.

## 6-1. 세부 Trait

MVP Vertical Slice에서는 실제 구현 12~15개의 세부 Trait로 시작하고, 질문·전공 Profile이 안정된 뒤 20~30개(후속 확장)를 거쳐 50~100개(장기 확장)로 넓힌다. 처음부터 많은 Trait를 만드는 것보다 각 Trait의 정의와 선택지 Evidence가 겹치지 않게 만드는 것을 우선한다.

예:

```text
원인 분석
패턴 탐색
정보 분류
순서 구성
우선순위 판단
수치 비교
가설 설정
논리적 검증
아이디어 변형
시각적 표현
서사 구성
사용자 반응 예측
타인의 감정 해석
의견 조정
계획 수립
즉시 실행
도구 활용
반복 수정
정밀 검토
변화 대응
독립 작업 선호
협업 선호
추상 개념 선호
구체적 결과물 선호
```

## 6-2. 상위 Career Dimension

세부 Trait는 사용자에게 설명하기 쉬운 상위 Dimension으로 묶는다.

```text
분석과 구조화
창의적 표현
인간과 관계 탐구
사용자·타인 관점
계획과 실행
도구 활용과 제작
정보 탐색과 비교
협업과 조정
```

O*NET Work Styles, Specific Interest Areas, Holland 등은 Ontology 설계의 Anchor로 사용하되 학생용 표준검사로 직접 사용한다고 주장하지 않는다.

## 6-3. Trait Schema

```python
class TraitDefinition(BaseModel):
    trait_id: str
    label: str
    parent_dimension: str
    definition: str
    positive_indicators: list[str]
    conflicting_indicators: list[str]
    aliases: list[str]
    source_references: list[str]
    trait_scope: Literal["shared", "domain_specific"]
    minimum_context_count: int
    primary_vector_group: Literal["interest", "cognitive", "work_style", "environment"]
```

`primary_vector_group`은 이 Trait가 §13의 어느 Student Multi-Vector(Interest/Cognitive Approach/Work Style/Environment Preference)에 속하는지 지정한다. 이 필드가 있어야 §16의 `interest_similarity`, `cognitive_similarity` 등 벡터별 유사도를 실제로 나눠 계산할 수 있다. Context Preference Vector는 Trait가 아니라 15개 Context 관심도 평가 자체로 구성하므로 이 필드의 대상이 아니다.

LLM은 새로운 Trait를 자유롭게 생성하지 않는다. 기존 Ontology에 없는 후보는 `UNMAPPED_TRAIT`로 저장하고 프로토타입 결과 계산에서는 제외한다.

## 6-4. Context Preference와 Shared Trait 분리

학생이 특정 Context를 좋아하거나 싫어하는 정보와, 여러 Context에서 관찰되는 행동 Trait를 분리한다.

```text
Context Preference
- 게임 관심 높음
- 봉사 관심 낮음

Shared Behavioral Trait
- 협력과 지원
- 공감과 관점 이해
- 분석과 구조화
- 계획과 실행

Domain-Specific Activity Trait
- 게임 시스템 관심
- 사회적 기여 활동 관심
```

봉사 관심이 낮다는 이유로 공감·협력·책임감 점수를 낮추지 않는다. 이러한 Shared Trait는 게임의 초보 팀원 지원, 미디어 제작 협업, 스포츠 역할 조정 등 다른 Context에서도 관찰할 수 있다.

질문이 추출하는 Trait의 권장 구성은 다음과 같다.

```text
Shared Behavioral Trait: 약 70~80%
Domain-Specific Activity Trait: 약 20~30%
```

## 6-5. Context–Trait Coverage Matrix

각 Context가 어떤 Shared Trait를 얼마나 직접적으로 관찰할 수 있는지 등급형 Matrix로 관리한다.

```text
0: 해당 Context에서 관찰하기 어려움
1: 간접적으로 관찰 가능
2: 질문 프레임으로 직접 관찰 가능
3: 해당 Context의 핵심 관찰 영역
```

Matrix는 **Trait 단위**(실제 구현 12~15개)로 만든다. Career Dimension(8개) 단위로는 뒤에 나오는 Coverage Gap 계산("각 Trait의 관찰 가능 횟수")과 맞지 않는다 — 예를 들어 게임 Context가 "분석과 구조화" 전반을 잘 다루더라도, 그 Dimension에 속한 개별 Trait(`가설 설정`, `정밀 검토` 등)까지 전부 잘 관찰된다고 보장할 수는 없다. 열 이름은 각 Trait의 `trait_id`를 그대로 쓰고, `parent_dimension`(§6-3)을 통해 Career Dimension과 연결한다.

예시(핵심 Trait 중 4개만 발췌, 나머지는 §6-6 Trait Definition Table을 확정하면서 채운다):

| Context | 원인 분석 | 협업 선호 | 즉시 실행 | 타인의 감정 해석 |
|---|---:|---:|---:|---:|
| 게임 | 3 | 3 | 2 | 1 |
| 미디어 | 2 | 2 | 2 | 2 |
| 스포츠 | 1 | 3 | 3 | 2 |
| 음악 | 2 | 2 | 2 | 2 |
| 봉사 | 1 | 3 | 2 | 3 |
| 학교생활 | 3 | 3 | 3 | 2 |

Career Dimension 8개 단위 요약이 필요하면 이 Trait 단위 Matrix에서 각 Trait의 `parent_dimension`을 기준으로 평균·최댓값을 집계해 발표용으로만 파생한다. Dimension 단위 값을 별도로 손으로 채우지 않는다.

모든 Context가 모든 Trait를 같은 강도로 측정할 필요는 없다. 다만 주요 Shared Trait는 최소 3개 이상의 서로 다른 Context에서 `coverage_grade >= 2`인 질문 프레임을 갖는 것을 목표로 한다.

Context 간 거리는 단순 단어 임베딩만으로 정하지 않고, 팀이 검토한 활동 축으로 Context Vector를 구성해 계산한다.

```text
개인 활동 ↔ 팀 활동
디지털 ↔ 신체·현장
사람 중심 ↔ 시스템 중심
감상 ↔ 직접 제작
표현 중심 ↔ 분석 중심
자유 탐색 ↔ 규칙·목표 중심
```

Contrast Context 1개는 다음 규칙으로 제안한다.

```text
후보군
= 학생이 선택하지 않은 Context 중 관심도 2~3점

context_distance
= 선택된 선호 Context 4개의 평균 Context Vector와 후보 간 거리

coverage_gain
= 선택된 4개에서 부족한 Shared Trait를 후보가 보완하는 수

contrast_score
= context_distance_normalized × 0.6
 + coverage_gain_normalized × 0.4
```

`0.6/0.4`는 검증된 상수가 아니라 Contrast 목적을 우선하기 위한 MVP 초기값이다. 상위 후보와 선정 이유를 학생에게 보여주고, 학생이 승인하거나 다른 후보·선호 Context를 선택하게 한다. 관심도 1점인 강한 비선호 Context는 자동 제안하지 않는다.

최종 후보 5개의 Coverage는 다음과 같이 검사한다.

```text
각 Trait의 관찰 가능 횟수
= 최종 후보 5개 중 coverage_grade >= 2인 Context 수

Coverage Gap
= max(0, 2 - 관찰 가능 횟수)

Coverage Gap 합계 = 0
→ coverage_sufficient = true
→ 기존 5개 그대로 확정 가능

Coverage Gap 합계 > 0
→ 한 Context를 교체했을 때 Gap을 가장 많이 줄이는 후보 최대 2개 제안
→ 학생이 유지 또는 교체 결정
```

최종 5개 확정은 항상 학생 확인을 거친다. 기본 검사에서는 Context를 추가해 문항 수를 늘리지 않고 교체만 제안하며, 추가 Context 탐색은 검사 종료 후 별도 기능으로 둔다.

전공군 간 사전 판별력은 Coverage와 다른 개념이므로 이 Matrix에 섞지 않는다. 향후 필요하면 `TraitDiscrimination` 별도 테이블로 관리하고, 질문 우선순위가 모두 같은 경우의 동점 결정에만 사용한다. 실시간 학생 전공 순위는 질문 선택에 사용하지 않는다.

## 6-6. 필수 콘텐츠 설계 산출물

기술 구현과 별도로 다음 콘텐츠 표를 작성해야 한다. 전체 규모를 한 번에 완성하지 않고 Vertical Slice용 최소 세트를 먼저 손으로 검산한 뒤 확장한다.

### Context Definition Table

문서 전체가 "15개 Context", "핵심 5개", "나머지 10개"를 계속 언급하지만, 실제 15개 Context의 이름과 정의는 어디에도 나열돼 있지 않다 — Coverage Matrix 예시(§6-5)에 등장하는 게임·미디어·스포츠·음악·봉사·학교생활 6개가 전부이고 나머지 9개는 이름조차 없다. Coverage Matrix, Seed Question, Contrast Context 거리 계산이 전부 이 목록을 전제로 하므로, 다른 산출물보다 먼저 확정해야 한다.

```text
전체 15개 (Vertical Slice보다 먼저 확정)

필수 필드:
context_id / 이름 / 설명 / 예시 활동
핵심 5개 여부 (전용 Frame 대상인지, 공용 Fallback 대상인지)
관심도 평가 문구
```

### Trait Definition Table

```text
Vertical Slice: Trait 10~15개
실제 구현(공모전 MVP): Trait 12~15개
후속 확장: Trait 20~30개
장기 확장: Trait 50~100개

필수 필드:
trait_id / 이름 / 정의 / 상위 Dimension / primary_vector_group
관찰 행동 / 상충 행동 / 유사 Trait와의 차이
shared 또는 domain_specific / minimum_context_count / 근거
```

### Question–Trait Mapping Table

```text
Vertical Slice: Context 2~3개
Seed Question: Context별 1개
Option Blueprint: 5~10개

필수 필드:
question_frame_id / context_id / role_id
학생에게 보이는 Option 예시 / Primary Trait
next_probe / 반대·교차 확인 가능 여부
```

Question–Trait Mapping은 O*NET·Holland 등 근거 체계를 설계 Anchor로 참고하되, 특정 질문이 공식적으로 검증됐다고 주장하지 않는다. 작성자를 포함한 최소 2인이 Option의 Trait 연결, 유도성, 중복성을 독립 검토하고 불일치 항목은 합의 후 반영한다.

MVP 전체 범위에서는 15개 Context의 고정 Seed Question 15개 × Option 5개 = Seed Option 75개 전부에 대해 Option Blueprint를 작성한다. 이 75개는 Vertical Slice 단계의 2~3개보다 늦게 착수하더라도, §9-1 Blueprint Lint와 위 2인 교차검토를 동일하게 거쳐야 한다.

### Major–Trait Mapping Table

```text
Vertical Slice: 대표 전공 3~5개
MVP 전체: 대표 전공 5~8개

필수 필드:
major_id / trait_id / 관련도 등급 0~3
관련 이유 / source_id / 추출 방식
팀 검토 여부 / 버전 / 갱신일
```

Major–Trait Mapping은 공식 학과 교육목표·교육과정·전공과목을 근거로 작성하고 작성자를 포함한 최소 2인이 독립 교차검토한다.

### Subject–Trait Mapping Table

```text
Vertical Slice: 고교과목 5~10개

필수 필드:
subject_id / trait_id / 관련도 등급 0~3
관련 전공 / 추천 근거 / 실제 개설 여부 / source_id
```

### Trait Relation Table

```text
핵심 12~15개 → 확장 Trait 최대 50~100개

필수 필드:
trait_id_a / trait_id_b / relation_weight / rationale
generation_method(ai_offline) / reviewed 여부
```

AI가 오프라인으로 1회 생성하고 팀이 스팟체크한 뒤 고정 테이블로 저장한다(§12-2). 세션 중 실시간 생성이 아니므로 §24 LLM 호출 예산에 포함하지 않는다.

### Hand-Calculated Fixture

`demo_user_01`의 고정 답변을 이용해 다음 연결을 팀이 손으로 검산한다.

```text
학생 답변
→ 선택 Option과 role_id
→ Primary Trait Evidence
→ support_ratio와 Evidence 기반 내부 상태
→ Student Profile
→ 내부 전공 관련도 순위와 사용자용 정성 라벨
→ 과목 추천
```

이 다섯 산출물의 Vertical Slice 버전이 완성돼야 질문·Evidence·전공·과목 담당자가 동일한 의미 기준으로 병렬 개발할 수 있다.

---

# 7. Question Design

## 7-1. 고정 Seed Question

15개 Context에 각 1개의 Seed Question을 수작업으로 설계한다.

```text
15 × 1 = 고정 Seed Question 15개
```

Seed Question의 역할:

- 해당 Context 안에서 학생이 가장 흥미를 느끼는 지점을 넓게 탐색
- 첫 번째 `next_probe`와 Domain-Specific Trait 후보 생성
- 이후 Adaptive 질문의 시작 경로 결정

Seed Question 하나가 이후 경로 전체를 고정하지 않도록, 꼬리질문 Planner는 Global Evidence와 Content Balancing 규칙을 함께 사용한다.

## 7-2. Adaptive 질문 역할

Seed와 꼬리질문의 역할을 다음처럼 구분한다.

```text
Seed Question: 관심의 세부 지점 탐색

꼬리질문 1: Seed 답변의 관심 지점 심화
꼬리질문 2: 실제 행동·문제 해결 방식 확인
꼬리질문 3: 다른 Context Evidence와 교차 확인
꼬리질문 4: 반대·대안 상황 확인
꼬리질문 5: Evidence가 부족하거나 Explicit Conflict가 남은 핵심 Trait 보완
꼬리질문 6: Explicit Conflict 또는 필수 역할 누락 시에만 추가
```

처리 순서상 가장 먼저 진행되는 Context는 비교할 다른 Context의 Evidence가 없으므로, 꼬리질문 3번(교차 확인)을 Seed 관심 지점의 추가 심화로 대체한다. 두 번째 Context부터는 위 역할을 그대로 수행한다.

Seed가 관심 세부 지점 탐색 역할을 담당하므로 `Seed 1개 + 꼬리질문 4개`에서 최소 역할 구성이 완성된다. 꼬리질문 4개 이후 Stop Condition을 검사하고, 기본적으로 5개까지 진행하며 §12-1의 Explicit Conflict 또는 필수 역할 누락이 남으면 여섯 번째 질문을 추가한다.

## 7-3. 선택지마다 저장할 정보

각 보기에 고정된 다음 질문 문장을 저장하지 않는다. 다음 질문의 목적을 저장한다.

```json
{
  "option_id": "media_seed_01_o3",
  "text": "촬영·편집·음악을 감상할 때",
  "role_id": "production_focus",
  "primary_trait_delta": {
    "creative_expression": 1,
    "production_interest": 1
  },
  "secondary_trait_hypotheses": [],
  "next_probe": "제작 요소 중 구체적인 관심 지점 확인",
  "preferred_frames": [
    "focus_selection",
    "activity_preference"
  ]
}
```

이 구조를 Question/Option/Evidence 모듈이 함께 사용하는 정본 Option Schema로 삼는다. 동적 질문에서는 LLM이 `role_id`와 문구만 반환하고, 서버가 검토된 Option Blueprint에서 `primary_trait_delta`를 결합한다.

사용자가 선택한 Option의 `next_probe`만 LLM에 전달한다. 선택되지 않은 네 경로의 질문은 생성하지 않는다.

## 7-4. 질문 프레임

질문 문장을 무작위 생성하지 않고 검토된 프레임을 사용한다.

```text
가장 먼저 무엇을 하고 싶은가?
어떤 부분에 가장 오래 집중하는가?
문제가 생기면 무엇부터 확인하는가?
제한된 시간에는 무엇을 우선하는가?
결과가 예상과 다르면 어떻게 수정하는가?
다른 사람의 반응이 다르면 어떻게 하는가?
여러 의견이 충돌하면 무엇을 기준으로 결정하는가?
새로운 도구가 주어지면 어떻게 접근하는가?
팀 활동에서는 어떤 역할을 맡고 싶은가?
```

---

# 8. Question Target Planner

Planner는 질문 문장을 생성하지 않고 다음 질문의 측정 목적을 결정한다.

## 입력

```text
현재 Student Trait Vector
Trait별 Evidence 수
Context 다양성
사전 정의된 Explicit Conflict Evidence
최근 선택 Option의 next_probe
이미 출제한 질문
남은 질문 수
선택적 사전 Trait 판별력 값
```

## 출력

```json
{
  "target_traits": [
    "tool_execution",
    "iterative_improvement"
  ],
  "question_frame": "new_tool",
  "context": "media",
  "purpose": "직접 제작과 반복 수정 선호 확인",
  "option_blueprint_id": "execution_strategy_v1"
}
```

## 우선순위

Planner의 역할은 두 층으로 나뉜다. **어떤 테마의 질문을 낼지는 §7-2의 위치별 고정 역할이 이미 결정**한다(예: 이번이 꼬리질문 2번이면 테마는 "행동·문제 해결 방식"으로 고정). Planner는 그 테마 **안에서 어떤 Trait를 구체적으로 목표할지**만 정하며, 위치에 따라 후보 풀 자체가 다르다.

```text
꼬리질문 1~4 (심화 / 행동방식 / 교차확인 / 반대·대안)
→ 해당 위치의 테마와 호환되는 Trait만 후보로 삼는다
→ Explicit Conflict Trait라도 지금 테마와 무관하면 이 구간에서는 목표로 삼지 않는다
→ 후보가 여럿이면: ① 다른 Context에서 교차 확인이 필요한 Trait
                    ② 반복 질문 감점(동일 Trait 연속 3회 이상 금지)
                    ③ 동률일 때만 사전 Trait 판별력(static_trait_discrimination)을 tie-break로 사용

꼬리질문 5~6 (Evidence 부족·Conflict 보완 / 조건부)
→ 다음 순서로 보완 대상을 정한다
1. 사전 정의된 Explicit Conflict가 있는 Trait
2. 전체 Profile에서 Evidence가 부족한 핵심 Trait
3. 필수 질문 역할 중 아직 충족되지 않은 역할
4. 다른 Context에서 확인 가능한 미확인 Secondary Hypothesis
```

가중치를 매겨 합산하는 방식은 사용하지 않는다 — 그런 방식은 Conflict처럼 우선순위가 높은 조건이 다른 조건들의 합계에 밀려 뒤로 밀릴 위험이 있기 때문이다.

직전 답변에서 강하게 나타난 관심은 우선순위 조건이 아니라 선택된 Option의 `next_probe`(§7-3)를 통해 질문 문구를 자연스럽게 잇는 재료로만 사용한다. 이렇게 분리해야 "직전 답변에 관심이 있었다"는 이유만으로 같은 Trait를 계속 목표로 삼는 것을 막을 수 있다.

모든 Trait를 억지로 측정하지 않는다. Evidence가 없으면 `INSUFFICIENT`로 남긴다.

## 자기확증 방지 규칙

- 동일 Trait를 연속 3회 이상 묻지 않는다.
- Context별 최소 한 질문은 반대 또는 대안 가능성을 확인한다.
- 두 번째 이후 Context는 각각 최소 한 질문에서 다른 Context의 Evidence를 교차 확인한다. 처리 순서상 첫 번째 Context는 비교할 다른 Context Evidence가 없어 예외로 하며, 세션 전체 기준으로는 5개 Context 중 최소 4개에서 교차 확인이 수행돼야 한다.
- 강한 Trait만 반복 강화하지 않는다.
- 초기 한 답변이 이후 전체 질문을 결정하지 않도록 Global State를 사용한다.
- Secondary Hypothesis 확인 질문은 Context당 최대 1개만 허용한다.

---

# 9. Option Blueprint

LLM이 선택지별 점수를 임의로 만들지 못하게 Option Role과 Trait Vector를 코드로 관리한다.

```json
{
  "blueprint_id": "problem_response_v1",
  "roles": [
    {
      "role_id": "cause_analysis",
      "primary_trait_delta": {
        "causal_analysis": 1,
        "logical_verification": 1
      }
    },
    {
      "role_id": "strategy_change",
      "primary_trait_delta": {
        "adaptability": 1,
        "alternative_generation": 1
      }
    },
    {
      "role_id": "direct_trial",
      "primary_trait_delta": {
        "tool_execution": 1,
        "experimentation": 1
      }
    },
    {
      "role_id": "external_research",
      "primary_trait_delta": {
        "information_search": 1
      }
    },
    {
      "role_id": "ask_others",
      "primary_trait_delta": {
        "collaboration": 1,
        "user_perspective": 1
      }
    }
  ]
}
```

LLM은 각 Role을 학생의 Context에 맞는 자연스러운 선택지로 표현한다. Evidence 계산은 Role의 고정 `primary_trait_delta`를 사용한다.

MVP의 모든 `primary_trait_delta` 값은 `1`로 고정한다. 숫자로 Trait 강도를 임의 조정하지 않고 해당 Trait Evidence가 선택됐는지만 기록한다. 한 질문의 다섯 Option에서 동일 Trait는 최대 한 Option에만 배정한다.

## 9-1. Option Blueprint Lint

다음 규칙은 LLM이 생성한 문구가 아니라 사람이 작성한 Blueprint 자체를 검사하므로, 질문 생성 때마다 실행하는 Quality Gate와 분리한다. 개발·CI·서버 시작 시 전체 Blueprint를 검사하고 하나라도 실패하면 배포 또는 서버 시작을 중단한다.

```text
모든 primary_trait_delta 값이 1임
한 질문의 여러 Option에 동일 Trait가 중복 배정되지 않음
허용된 Trait ID와 Role ID만 사용
Blueprint별 Role ID가 서로 다름
Option Role이 정확히 5개임
빈 primary_trait_delta 없음
```

서버가 Blueprint를 로드할 때도 같은 조건을 가벼운 Assertion으로 재확인할 수 있지만, 이 규칙의 주 책임은 Blueprint Lint에 둔다.

LLM이 답변 문맥에서 추가로 추출한 Secondary Trait는 허용된 Ontology 안에서만 `HYPOTHESIS` 상태로 저장한다. Secondary Trait는 MVP의 Student Vector와 전공 매칭 점수에 직접 반영하지 않는다. 다른 Context의 검토된 Option Blueprint로 최대 한 번 확인하며, 학생이 해당 Primary Option을 선택하면 `CONFIRMED`, 선택하지 않으면 `DISMISSED`, 세션 종료까지 확인하지 못하면 `EXPIRED`로 처리한다. `CONFIRMED`가 된 Primary Evidence만 Profile에 반영한다. 동일 답변에서 Primary Trait와 겹치는 Secondary 후보는 저장하지 않는다.

---

# 10. Question Generator

제공된 LLM API를 백엔드에서 실시간 호출한다. 별도의 질문 생성 모델을 파인튜닝하지 않는다.

```text
기존 LLM
+ System Prompt
+ 질문 프레임
+ Option Blueprint
+ 현재 Evidence State
+ 학생 Context
+ 금지 규칙
= Question Generation Agent
```

## Structured Output

```python
class GeneratedOption(BaseModel):
    role_id: str
    text: str

class GeneratedQuestion(BaseModel):
    context: str
    target_traits: list[str]
    frame_id: str
    question_text: str
    options: list[GeneratedOption]

class QuestionGenerationResult(BaseModel):
    question: GeneratedQuestion
    secondary_trait_hypotheses_from_previous_answer: list[str] = Field(default_factory=list)

class SecondaryTraitHypothesis(BaseModel):
    trait_id: str
    source_answer_id: str
    status: Literal["HYPOTHESIS", "CONFIRMED", "DISMISSED", "EXPIRED"]
    verification_count: int = 0
```

`question_id`와 `option_id`는 LLM Structured Output에 포함하지 않고 서버가 생성한다(`option_id = question_id + 옵션 순번`). LLM이 반환한 Secondary Trait ID는 서버가 Ontology 허용 목록과 Primary 중복 여부를 확인한 뒤 `SecondaryTraitHypothesis`로 저장한다.

## 생성 원칙

- 학생이 선택한 Context 안에서 질문한다.
- 행동 선호를 묻고 능력의 자기평가를 요구하지 않는다.
- 직업명과 학과명을 직접 언급하지 않는다.
- 특정 답변이 도덕적·사회적으로 더 좋아 보이지 않게 한다.
- 선택지 길이와 구체성을 유사하게 맞춘다.
- 앞선 질문을 표현만 바꿔 반복하지 않는다.

---

# 11. Question Quality Gate

`Validator`는 심리측정학적 타당성을 보증하는 모듈이 아니다. 생성 형식과 설계 규칙 준수 여부를 검사하는 Quality Gate다.

## Code Check

```text
JSON Schema 만족
선택지 정확히 5개
허용된 Role ID만 사용
모든 Role ID가 서로 다름
빈 선택지 없음
질문 길이 제한
금지 표현 없음
중복 question_id 없음
질문 횟수 정상
```

## Semantic Check

Semantic Check는 세 층으로 나눠 운영한다. 매 질문마다 LLM을 호출하지 않는다.

```text
Runtime Quality Gate (Code Check, LLM 미사용)
- 선택지 의미 중복, 임베딩 기반 유사 질문 검사

Offline Semantic Evaluation (배치, §26 Evaluation Harness)
- 유도성(특정 선택지가 정답처럼 보이는지)
- 고등학생에게 자연스러운지
- 질문이 지나치게 복합적인지
- 질문과 Target Trait가 의미적으로 일치하는지

Runtime LLM Semantic Check (기본 비활성)
- 세션 중 기본적으로 호출하지 않는다
- 개발·장애 분석 시 표본 질문에만 §24의 3회 예산 안에서 적용
```

## Fallback

```text
Cache 조회
 ├ HIT → 캐시 질문 사용
 └ MISS → 실시간 생성
               ↓ 실패
             1회 재생성
               ↓ 실패 / Timeout
             Backup Question
               ↓ Backup 소진 또는 중복
             해당 Context 조기 종료 후 다음 Context
```

공모전 발표 경로는 최대 길이까지 미리 한 번 실행하여 최대 30개의 꼬리질문을 캐싱한다. 일반 장애에 대응할 최소 Backup Question은 Context별 2~3개 준비한다. Backup은 동일 세션에서 재사용하지 않으며, 최소 꼬리질문 수를 채우기 전에 모두 소진되더라도 시스템을 멈추지 않고 해당 Context를 `Evidence 부족` 상태로 종료한다.

---

# 12. Evidence Ledger

학생의 모든 선택은 원문과 구조화 Evidence를 함께 저장한다.

```json
{
  "evidence_id": "ev_123",
  "answer_id": "ans_123",
  "question_id": "media_tail_04",
  "question_frame_id": "unexpected_result",
  "option_role_id": "cause_analysis",
  "applied_primary_trait_delta": {
    "causal_analysis": 1,
    "logical_verification": 1
  },
  "evidence_origin": "primary_blueprint",
  "secondary_hypotheses": [],
  "context": "media",
  "source_type": "generated_question",
  "generator_version": "qgen_v1",
  "quality_gate_status": "passed",
  "cross_context_group": "problem_response"
}
```

Trait별로 다음을 계산한다.

```text
support_count
opportunity_count
support_ratio
context_count
distinct_frame_count
cross_context_repeat_count
cross_context_consistency
explicit_conflict_count
context_dependency_flag
coverage
source_diversity
```

`applied_primary_trait_delta`는 §9 Option Blueprint의 `primary_trait_delta`가 실제 답변에 적용된 값을 그대로 기록한 것이다 — 같은 구조를 정의(Blueprint)와 기록(Evidence)이라는 다른 레이어에서 쓰기 때문에 필드명으로 그 관계를 드러낸다.

한 답변이 여러 Trait Evidence를 만들 수 있지만, 같은 질문에서 파생된 Evidence를 독립 질문 여러 개처럼 계산하지 않는다. 질문에 제시된 다섯 Option 중 정확히 하나의 Option에 특정 Trait가 포함돼 있었다면 해당 Trait의 `opportunity_count`를 1 증가시킨다. 학생이 그 Option을 실제로 선택했을 때만 `support_count`를 1 증가시킨다.

```text
support_ratio
= support_count / opportunity_count
```

모든 `primary_trait_delta`가 1이므로 `support_ratio`는 0~1 범위다. 하지만 선택하지 않은 Option을 Trait의 부재나 약함으로 단정할 수 없으므로 이를 Trait 강도 점수로 사용하지 않는다. `support_ratio`는 선택 기회 대비 반복 선택 정도를 설명하는 보조 지표로만 저장한다. Profile 상태는 `support_count`, `context_count`, 반복성, 명시적 Conflict를 중심으로 결정한다. Secondary Hypothesis는 이 계산에 포함하지 않는다.

## 12-1. Explicit Conflict와 Context Dependency

다른 Context에서 서로 다른 Trait를 선택했다는 이유만으로 Conflict로 처리하지 않는다. Conflict는 사전에 정의된 동일 구성개념의 명시적 대조 관계에서만 판정한다.

```python
class ContrastDefinition(BaseModel):
    contrast_id: str
    construct_id: str
    positive_role_ids: list[str]
    opposite_role_ids: list[str]
    comparable_frame_ids: list[str]
    condition_scope: str
    minimum_evidence_each_side: int
    description: str
```

```text
같은 construct_id
+ 비교 가능한 question frame
+ 같은 condition_scope
+ 사전 정의된 반대 Role
+ 양쪽 Evidence가 minimum_evidence_each_side 이상
→ EXPLICIT_CONFLICT 후보

상황 차이로 설명 가능한 반대 Evidence
→ Conflict로 계산하지 않음
→ context_dependency_flag = true
```

MVP에서는 역방향 확인 질문 또는 동일 조건의 명시적 반대 선택처럼 좁은 경우에만 `CONFLICTING`을 사용한다. 독립 작업과 협업 선호처럼 동시에 존재할 수 있는 특성은 Contrast Pair로 만들지 않는다.

## 12-2. Trait Relation과 확장 Trait 신호

12~15개 핵심 Trait만으로는 한 학생의 성향을 표현하기에 해상도가 낮을 수 있다. 이를 보완하기 위해 핵심 Trait와 의미적으로 관련된 확장 Trait(최대 50~100개 풀)를 관리하고, 확정된 핵심 Trait 상태에서 관련 Trait로 신호를 전파한다.

```python
class TraitRelation(BaseModel):
    trait_id_a: str
    trait_id_b: str
    relation_weight: float
    rationale: str
    generation_method: Literal["ai_offline"]
    reviewed: bool
```

`TraitRelation`은 AI가 오프라인(콘텐츠 준비 단계)에서 후보를 생성하고 결과를 고정 테이블로 저장한다. 세션 진행 중에는 이 테이블을 조회만 하며 추가 LLM 호출을 만들지 않는다. 생성 직후 핵심 12~15개 Trait와 이름이 겹치지 않는지, 금지 표현이 없는지 자동으로 검사한 뒤, 최소 2인이 관계 의미와 `relation_weight`를 검토한다. 합의되지 않은 관계는 `REVIEW_REQUIRED`로 남기고 발표용 Obsidian Subgraph에서 제외한다. (이 기능 자체가 §28의 "선택적 발표 확장"이므로, 실제로 안 쓰기로 하면 이 검토 절차도 필요 없다.)

```text
association_score[B]
= max( confirmed_state_value[A] × relation_weight[A,B] )
  for A in 학생의 STRONG/MODERATE 확정 Trait 전체
```

`association_score`라는 이름을 쓰는 이유는, 이 값이 학생의 Trait 강도를 추론한 결과가 아니라 이미 확정된 Trait와의 개념적 연관성만으로 정렬한 값이기 때문이다.

`confirmed_state_value`는 §13의 `STRONG → 1.00`, `MODERATE → 0.67`을 그대로 사용한다. 이 전파된 값(Related Trait Signal)은 §14 결과 카드의 핵심 5~8줄과 §16 전공 매칭 점수에는 사용하지 않는다. "왜 이런 결과가 나왔나요?" 상세 근거 화면과 Obsidian Subgraph에서만 "관련 있을 수 있는 특성"으로 참고용으로만 표시한다.

Obsidian Subgraph(§23)에는 이 확장 풀 전체를 넣지 않는다. 확장 Trait는 `Core Trait`와 같은 노드 타입으로 취급하지 않고, `RelatedConcept`이라는 별도 노드로 `Student`가 아니라 그 근거가 된 Trait에서만 점선(`RELATED_CONCEPT`)으로 연결한다. 발표 화면에서 실제로 관찰된 특성과 추론된 관련 개념이 시각적으로 구분되지 않으면, 답변으로 확인하지 않은 성향까지 학생 특성처럼 보여주는 것과 같은 효과가 나기 때문이다. `RelatedConcept` 노드는 `association_score`가 높은 순으로 최대 3~5개까지만 추가한다.

여기서 말하는 "확장 Trait 최대 50~100개 풀"은 §1·§6-1의 Trait Ontology 확장 로드맵(질문·Option Blueprint를 실제로 새로 만들어 측정 대상 Primary Trait를 12~15→20~30→50~100으로 늘리는 계획)과는 다른 축이다. Primary Trait 확장은 질문 설계가 필요한 무거운 작업이고, 이 확장 풀은 AI가 오프라인으로 이름과 관계만 생성하는 가벼운 작업이라 MVP에서 지금 바로 사용 가능하다.

---

# 13. Student Multi-Vector Profile

학생을 하나의 임베딩으로만 표현하지 않고 의미 종류별 다중 벡터로 표현한다.

```text
Context Preference Vector
어떤 Context를 좋아하거나 꺼리는가

Interest Vector
어떤 대상과 활동에 관심을 가지는가

Cognitive Approach Vector
정보를 어떻게 해석하고 문제를 해결하는가

Work Style Vector
어떻게 계획·실행·협업하는가

Environment Preference Vector
어떤 활동 환경과 결과물 형태를 선호하는가
```

Context Preference Vector는 질문 Context 선택과 Domain Interest 해석에 사용하고, 공감·협업·분석 같은 Shared Trait의 대체 점수로 사용하지 않는다.

미측정 Trait와 Evidence 최소 조건을 충족하지 못한 Trait는 0점으로 처리하지 않는다. `INSUFFICIENT`와 Mask로 제외한다.

Student Vector에는 Trait별 `support_count`, `opportunity_count`, `support_ratio`, `context_count`, `distinct_frame_count`, `cross_context_repeat_count`, `explicit_conflict_count`를 함께 저장한다. 전공 매칭에서는 아래 상태 판정에서 `STRONG`, `MODERATE`, `LIMITED`로 확정된 Trait를 상태 기반 내부 값으로 변환해 사용하고, `INSUFFICIENT`와 `CONFLICTING`은 Mask로 제외한다. 결과 카드의 강한 특성은 support_ratio가 아니라 Evidence 횟수·반복 Context 수·명시적 Conflict 여부를 함께 보고 선택한다. §12-2의 Related Trait Signal(전파된 추정값)은 이 저장 대상에 포함하지 않으며, 상세 근거 화면에서만 별도로 표시한다.

내부 상태:

```text
STRONG
MODERATE
LIMITED
CONFLICTING
INSUFFICIENT
```

MVP의 초기 상태 판정 규칙은 다음과 같다.

```text
opportunity_count = 0
→ INSUFFICIENT (NOT_PROBED — 이번 검사에서 이 Trait를 확인할 질문이 없었음)

§12-1의 해결되지 않은 EXPLICIT_CONFLICT 존재
→ CONFLICTING (Evidence 횟수와 무관하게 이 조건을 가장 먼저 확인한다)

opportunity_count > 0, support_count = 0
→ INSUFFICIENT (NO_POSITIVE_EVIDENCE — 선택 기회는 있었지만 한 번도 선택되지 않음. Trait가 약하다는 뜻이 아니라 근거가 아직 없다는 뜻이다)

opportunity_count > 0, support_count = 1
→ INSUFFICIENT (EVIDENCE_LIMITED — 긍정 Evidence가 한 번 나타났지만 재현되지 않음)

support_count >= 3
+ context_count >= TraitDefinition.minimum_context_count
+ distinct_frame_count >= 2
→ STRONG

support_count >= 2
+ context_count >= TraitDefinition.minimum_context_count
→ MODERATE

support_count >= 2지만 최소 Context 다양성 또는 반복성(distinct_frame_count < 2) 부족
→ LIMITED (CONTEXT_LIMITED)
```

`distinct_frame_count`는 해당 Trait의 Evidence가 서로 다른 질문 프레임(§7-4)에서 몇 번 확인됐는지를 센다. 이 값이 있어야 STRONG의 "반복 Evidence 확인"이 같은 프레임을 표현만 바꿔 반복한 결과가 아님을 코드로 보장할 수 있다. `INSUFFICIENT`를 이유별로 세분화하는 것은 상세 근거 화면의 설명 품질을 위한 것이며, 전공 매칭에서는 `NOT_PROBED`·`NO_POSITIVE_EVIDENCE`·`EVIDENCE_LIMITED` 모두 동일하게 Mask 처리한다.

`2회`, `3회`, 최소 Context 수는 검증된 심리측정 기준이 아니라 MVP 데모용 초기 휴리스틱이다. 내부 파일럿에서는 상태 분포가 한쪽으로 쏠리는지와 결과 설명이 Evidence에 부합하는지만 점검하고, 통계적으로 검증된 임계값이라고 주장하지 않는다.

전공 매칭용 내부 Trait 값은 Profile 상태에서 변환한다.

```text
STRONG   → 1.00
MODERATE → 0.67
LIMITED  → 0.33
INSUFFICIENT / CONFLICTING → Mask
```

숫자는 내부 매칭에 사용하고 사용자에게 심리검사 확률처럼 표시하지 않는다.

---

# 14. Career Profile 결과 카드

내부에서는 수십 개 Trait와 Evidence를 계산하지만 첫 화면에는 핵심 특징 5~8줄만 보여준다.

## 화면 예시

### 구조를 읽고 사람의 반응까지 생각하는 탐색형 설계자

1. 복잡한 내용에서 핵심과 흐름을 찾아 정리하는 데 흥미를 느껴요.
2. 단순히 감상하기보다 왜 이런 구조가 되었는지 생각하는 편이에요.
3. 결과물을 만들 때 보는 사람이 어떻게 받아들일지도 중요하게 생각해요.
4. 기존 방식을 그대로 따르기보다 순서나 구성을 바꿔보는 것을 좋아해요.
5. 아이디어에 머무르기보다 도구로 직접 시험해보려는 경향이 있어요.
6. 여러 선택지를 비교한 뒤 납득할 수 있는 기준으로 결정하는 편이에요.
7. 협업 방식은 아직 Evidence가 적어 추가 탐색이 필요해요.

```text
#구조화 #사용자관점 #패턴탐색 #콘텐츠기획 #직접실행
```

제목은 흥미를 위한 임시 요약이며 고정 유형이 아님을 표시한다.

> 현재 답변을 바탕으로 만든 요약이며 새로운 경험과 답변에 따라 달라질 수 있습니다.

## 상세 근거

기본 화면에서는 숨기고 `왜 이런 결과가 나왔나요?`를 펼치면 Context별 Evidence를 보여준다.

```text
구조화 경향

미디어
- 장면 순서를 바꿔 내용을 이해하기 쉽게 만드는 활동 선택

게임
- 여러 전략을 조건별로 비교하는 방식 선택

학교생활
- 발표 내용을 전달 순서에 따라 재구성하는 역할 선택
```

---

# 15. Major / Department Profile

학생과 같은 Trait Ontology를 사용해 대표 전공과 실제 학과를 구조화한다.

## 데이터 출처

- CareerNet 학과 정보
- 대학 관련 공공데이터
- 대학·학과 공식 홈페이지
- 학과 교육목표
- 교육과정과 전공과목
- 졸업 후 진로와 관련 직무
- 필요 시 O*NET 직업 활동

## Major Multi-Vector

```json
{
  "major_id": "media_communication",
  "interest_vector": {},
  "cognitive_vector": {},
  "work_style_vector": {},
  "environment_vector": {},
  "source_ids": [],
  "extraction_method": "rule_llm_hybrid",
  "review_status": "team_reviewed",
  "profile_version": "major_profile_v1",
  "updated_at": "YYYY-MM-DD"
}
```

예:

```text
미디어커뮤니케이션

서사 구성             1.00
사용자 반응 분석       1.00
정보 탐색             0.67
창의적 표현           1.00
도구 활용             0.67
정량 분석             0.33
협업                  0.67
```

전공 Profile의 초기 가중치는 공식 자료와 팀의 Mapping 표를 근거로 만든다. 각 Trait 가중치에는 근거 `source_id`, 추출 방식(`rule`/`LLM`/`manual`), 검토 여부, 갱신일을 남긴다. 내부 파일럿은 오류와 설명 가능성을 점검하는 용도이며, 소규모 결과만으로 가중치의 통계적 타당성이 검증됐다고 주장하지 않는다.

Mapping은 작성자를 포함한 최소 2인이 독립 검토하고, 검토자 간 합의가 이뤄지지 않은 항목은 `REVIEW_REQUIRED`로 남겨 추천 계산에서 제외한다.

```python
class MappingReview(BaseModel):
    mapping_id: str
    author_id: str
    reviewer_ids: list[str]
    agreement_status: Literal["AGREED", "REVIEW_REQUIRED", "REJECTED"]
    review_notes: list[str]
    source_ids: list[str]
    mapping_version: str
    reviewed_at: datetime
```

팀이 검토할 때는 관련도를 0~3 등급으로 작성하고 Matching Engine 입력 시 0~1로 변환한다.

```text
0: 관련성 거의 없음 → 0.00
1: 보조적으로 관련 → 0.33
2: 자주 활용       → 0.67
3: 핵심 학습활동   → 1.00
```

---

# 16. Similarity Matching Engine

학생과 전공을 다중 벡터 단위로 비교한다.

초기 예시:

```text
major_relatedness
= interest_similarity × 0.35
+ cognitive_similarity × 0.30
+ work_style_similarity × 0.20
+ environment_similarity × 0.15
```

가중치는 검증된 상수가 아니며 평가셋을 통해 조정한다.

## Missing Evidence

`INSUFFICIENT`와 `CONFLICTING`은 0으로 계산하지 않는다. 상태가 확정된 Trait만 분모에 포함한다.

```text
score
= 측정된 Trait의 가중 유사도 합
÷ 실제 비교에 사용된 가중치 합
```

특정 Vector(Interest/Cognitive/Work Style/Environment)에서 확정된 Trait가 하나도 없으면 그 Vector는 §16 상단 가중합에서 제외하고 남은 Vector의 가중치를 비례 재분배해 합이 1이 되게 한다.

"확정된 Trait가 부족하다"는 다음 최소 기준으로 판정한다.

```yaml
matching_policy:
  minimum_usable_traits: 3
  minimum_usable_vector_groups: 2
```

이 숫자는 검증된 값이 아니라 MVP 초기 휴리스틱이며, §6-6 Hand-Calculated Fixture에서 조정한다. 이 기준을 만족하지 못하면 순위를 생성하지 않고 "아직 관련도를 계산하기에 답변이 부족합니다, 추가 탐색이 필요합니다"를 반환한다.

## 사용자 표시

```text
관련 전공 탐색

미디어커뮤니케이션  관련성 높음
HCI·UX              함께 탐색해볼 분야
산업공학             비교해볼 만한 분야
데이터사이언스       비교해볼 만한 분야
```

내부 Matching Score는 후보 정렬과 일관성 평가에만 사용하고 사용자 화면에는 숫자를 노출하지 않는다. `84`, `81` 같은 표현은 적성 확률이나 성공 가능성으로 오해될 수 있으므로 사용하지 않는다.

> 관련도는 현재 답변에서 추출된 활동 선호·문제 접근 방식과 전공의 학습 활동을 비교한 상대적 지표입니다.

Raw cosine similarity에 단순히 100을 곱하지 않는다. 내부에서는 후보군 내 분포와 평가 데이터를 기준으로 상대 순위를 계산한다.

관련도와 Evidence 충분성을 분리한다.

```text
미디어커뮤니케이션
관련성 높음
Evidence 충분성: 충분
반복 관찰 Context: 3개

HCI·UX
함께 탐색해볼 분야
Evidence 충분성: 보통
```

---

# 17. Canonical Major와 실제 학과

```text
대표 전공군
→ 유사 학과
→ 대학별 실제 학과
```

예:

```text
컴퓨터·소프트웨어
├ 컴퓨터공학과
├ 소프트웨어학과
├ AI소프트웨어학과
├ 데이터사이언스학과
└ 정보통신공학과
```

## Mapping Pipeline

```text
공식 학문계열
→ Exact / Alias Mapping
→ Metadata Filter
→ Embedding Candidate Search
→ 교육목표·Curriculum 확인
→ LLM Structured Classification
→ Review Status 저장
```

보정되지 않은 `confidence: 0.84`는 사용하지 않는다.

```json
{
  "mapping_status": "REVIEW_REQUIRED",
  "primary_candidate": "데이터·통계",
  "secondary_candidates": ["경영·경제"],
  "mapping_method": "embedding_plus_curriculum",
  "evidence": [
    "데이터 분석 과목 비중",
    "경영 응용 과목 포함"
  ]
}
```

검증된 Mapping은 DB에 저장해 다시 계산하지 않는다.

---

# 18. 대학 학과 탐색과 성적 입력

## 실제 구현 범위

- 대표 전공군 5~8개
- 공공데이터 기반 전국 4년제 대학 실제 학과 Master DB
- 대학명, 캠퍼스, 지역, 실제 학과명, 모집단위, 학과 상태, 기준 연도, 공식 URL 저장
- Canonical Major 자동 후보 생성과 Mapping 상태 저장
- 비교 가능한 공식 입결 자료가 확보된 실제 학과 15~30개의 성적 필터링 데모
- 학생의 성적 유사 범위와 전공·교육과정 관련성이 높은 학과 및 학생이 직접 선택한 학과만 공식 홈페이지 RAG

전국 학과 Master는 한국대학교육협의회 대학 학과 정보 Open API 등 공식 데이터를 Source of Truth로 구축한다. 신설·통합·폐과는 기준 연도와 학과 상태를 보존해 갱신한다. 전국 모든 공식 홈페이지를 수집하거나 모든 학과의 입결을 직접 비교하는 것은 구현 범위에 포함하지 않는다.

### 데이터 수집 파이프라인 (API Schema·샘플 호출 검증 완료, 전국 적재는 구현 예정)

한국대학교육협의회_대학알리미 API(공공데이터포털 서비스 코드 `B340014`)를 실제로 호출해 확인한 구조다.

```text
1단계 — 전국 대학 목록
B340014/BasicInformationService_2
Operation: getComparisonUniversitySearchList (또는 getUniversityCode)
필수 파라미터: serviceKey, svyYr(조사년도), pageNo, numOfRows
결과: schlId, schlKrnNm, schlFullNm, estbDivNm, znNm 등 전국 약 377건(본교·분교·캠퍼스 포함)

2단계 — 학교별 학과 상세
B340014/BasicInformationService_1
Operation: getUniversityMajorCode
필수 파라미터: serviceKey, schlId, svyYr — 이 조합이 없으면 0건 응답
주요 결과 필드: korMjrNm(학과명), clgNm(단과대학), korSrsLclftNm/korSrsMclftNm/korSrsSclftNm(계열 대/중/소분류),
lsnTrmNm(수업연한), pbnfDgriCrseDivNm(학위과정), mjrAreaNm/mjrAreaSignguNm(지역),
edcGoalCtnt(교육목표), edcCrseLtrCtnt(개설과목 목록), pwayEmplLtrCtnt(관련 진로·직무),
schlMjrStatNm(학과상태: 기존/신설/통합/분리 등), svyYr(기준 연도)
```

1단계에서 확보한 약 377개 `schlId`를 순회하며 2단계를 호출해 전국 학과 Master DB를 구축한다. 1단계(대학 목록) API는 활용신청 상세 화면에서 일일 트래픽 한도 1,000회를 직접 확인했다. 2단계(학과 상세, `getUniversityMajorCode`)의 한도는 별도로 확인하지 못했으므로, 377회 호출 전 계정의 실제 일일 한도를 먼저 확인하고 필요하면 여러 날에 나눠 수집한다. `korSrsLclftNm/korSrsMclftNm/korSrsSclftNm`(표준분류 계열)은 §17 Canonical Major 자동 매핑의 1차 후보 생성에, `edcGoalCtnt`·`edcCrseLtrCtnt`·`pwayEmplLtrCtnt`는 §15 Major Multi-Vector의 Trait 가중치 근거 자료로 사용한다.

```text
전국 학과 Master DB
→ 전체 학과 검색·탐색

비교 가능한 입결 Subset
→ 성적 기반 개인화 목록

추천 상위 또는 학생 선택 학과
→ 공식 홈페이지 RAG와 교육과정 상세 설명
```

성적은 Career Profile과 전공 관련도를 변경하지 않는다.

```text
전공 관련도
= 학생 Trait와 전공 학습 활동의 관련성

성적 유사 범위
= 동일 학년도·전형·성적 지표의 공식 입시자료와 입력 성적 비교
```

대학별 산출방식이 다른 입시 결과를 하나의 점수로 섞지 않는다. 다음 조건이 모두 같은 자료만 비교한다.

```text
같은 학년도
같은 전형 유형과 세부 전형
같은 성적 지표
같은 공개 기준(예: 최종등록자 70% Cut)
공식 출처 존재
```

```python
class AdmissionReference(BaseModel):
    department_id: str
    admission_year: int
    admission_type: str
    admission_track: str
    score_metric: str
    score_50_cut: float | None
    score_70_cut: float | None
    minimum_requirement: str | None
    source_url: str
    data_comparability_group: str
    review_status: str
    verified_at: datetime
```

비교 조건을 충족하지 못하면 `지원 범위 비교 불가`로 표시하고 개인화 성적 추천에서 제외한다. 서울대와 제주대처럼 입결 편차가 큰 학과를 한 학생에게 `상향·안정 추천`이라는 같은 추천 목록으로 동시에 보여주지 않는다.

사용자 기본 화면에는 비교 가능한 자료 중 학생 입력 성적과 유사한 범위의 학과만 표시한다. 그 밖의 전국 관련 학과는 `전국 관련 학과 전체 보기`에서 탐색할 수 있지만 개인화 추천으로 표현하지 않는다.

```text
관련 전공군 결정
→ 전국 실제 학과 검색
→ 비교 가능한 입결 자료가 있는 학과 추출
→ 학생 성적 유사 범위 필터
→ 교육과정 관련성과 사용자 지역 선호로 정렬
→ 상위 또는 학생 선택 학과만 공식 홈페이지 RAG
```

성적 유사 범위는 합격 확률이나 합격 보장이 아니다. 화면에는 기준 학년도·전형·지표와 출처를 함께 표시한다.

---

# 19. RAG 구조

```text
공식 홈페이지
CareerNet
대학 공공데이터
        ↓
수집 및 출처 기록
        ↓
정규화
        ↓
Chunking
        ↓
Embedding
        ↓
PostgreSQL + pgvector
```

검색 순서:

```text
1. PostgreSQL Metadata Filter
2. 학과명 Exact / Alias Match
3. Keyword / BM25
4. Vector Search
5. 필요한 경우 RRF
```

대학명·지역·학과명은 SQL과 Exact Match로 검색한다. Vector Search는 학과 설명, 교육목표, Curriculum의 의미 검색에 사용한다.

Chunking 단계는 직접 구현하지 않고 LangChain의 Text Splitter(`langchain-text-splitters`)를 활용한다 — 이미 검증된 재귀적·토큰 기준 분할 로직을 다시 만들 이유가 없는 유일한 지점이라 판단했다. LangChain은 이 용도로만 쓰고 Structured Output·Prompt 조립에는 사용하지 않는다. §10은 Pydantic을 직접 사용하고, §24의 관찰은 LangGraph 실행을 LangSmith로 추적한다.

전국 학과 Master 전체를 RAG 색인하지 않는다. RAG 수집·색인은 다음 학과로 제한한다.

```text
학생의 성적 유사 범위에 포함되고 전공·교육과정 관련성이 높은 학과
학생이 직접 자세히 보기를 선택한 학과
발표용 대표 학과
```

RAG 결과에는 공식 URL, 기준 날짜, 문서 유형을 반드시 포함하고 공식 홈페이지 자료가 없으면 생성 설명을 제공하지 않는다.

---

# 20. Subject Profile과 Course Planning

고교 과목도 학생과 동일한 Trait 공간에 배치한다.

## Subject Vector 구성 자료

- 과목 설명
- 성취기준
- 주요 학습 활동
- 프로젝트·실험·토론 여부
- 평가 방식
- 사용하는 도구
- 관련 전공

예:

```text
데이터 과학

수치 분석       1.00
패턴 탐색       1.00
가설 검증       0.67
도구 활용       0.67
정보 표현       0.67
협업            0.33
```

Subject Vector도 Major Vector(§15)와 동일하게 0~3 등급으로 팀이 검토한 뒤 `0/.33/.67/1.00`으로 변환해 저장한다. 정밀 소수를 직접 입력하지 않는다.

## PRE_SURVEY

```text
Student Vector
+ 관심 전공
+ 현재 학년
+ 기존 이수과목
+ 전체 고교 선택과목 Pool
→ 희망과목 추천
```

## POST_OFFERING

```text
학교 PDF / Excel 업로드
→ 실제 과목 후보 추출
→ 사용자 확인·수정 [HITL]
→ Canonical Subject Mapping
→ 학년·이수·개설 조건 검사
→ 핵심·탐색·대체과목 추천
```

Agent는 학교 파일에 존재하지 않는 과목을 실제 개설과목처럼 추천하지 않는다.

---

# 21. Education Data MCP

MCP 서버는 하나만 구축한다.

```text
Education Data MCP
├ search_career_major()
├ get_career_major()
├ search_university()
├ search_departments()
├ get_department()
├ search_admission_references()
├ search_department_rag()
└ search_high_school_subject()
```

MCP는 외부 교육 데이터와 Agent 사이의 Typed Tool Boundary다. 단순히 로컬 함수를 MCP로 감싼 것처럼 보이지 않도록 각 Tool의 입력·출력 Schema와 출처를 명확히 한다.

학교 PDF/Excel에서 과목 후보를 추출하는 기능(§20 POST_OFFERING)은 외부 교육 데이터 조회가 아니라 사용자가 업로드한 파일을 처리하는 내부 기능이므로 MCP에 넣지 않는다. `course_document_parser.py`(§27)로 분리해 백엔드 내부에서만 호출한다.

---

# 22. Memory 전략

## Short-term

LangGraph Checkpointer에 저장한다.

```text
현재 Context
현재 질문
답변
Evidence
Student Vector
Graph 위치
LLM 호출 수
```

## Long-term Profile Store

정적 S1/S2 JSON 파일을 번갈아 보여주지 않고 `user_id` 기반 실제 Store를 구현한다. 공모전에서는 로그인 UI 없이 `demo_user_01`을 사용하더라도 Session과 Profile은 DB에 실제로 저장하고 새 Session에서 다시 조회한다.

```text
users
- user_id
- created_at

assessment_sessions
- session_id
- user_id
- semester
- status
- started_at
- completed_at

profile_snapshots
- profile_id
- user_id
- session_id
- profile_version
- trait_profile_json
- selected_contexts_json
- interested_majors_json
- selected_subjects_json
- created_at
```

```text
2026년 1학기 Assessment 완료
→ Profile V1을 user_id로 Store 저장
→ 새 2학기 Session 생성
→ user_id의 최신 완료 Profile 조회
→ 이전 Profile을 초기 참고 상태로 Load
→ 추가 Assessment
→ Profile V2 저장
→ V1/V2 변화 비교
```

이전 Profile은 새 답변을 덮어쓰는 확정값이 아니라 변화 비교와 질문 우선순위를 위한 참고 상태로만 사용한다. V1과 V2의 Trait 점수를 자동으로 합산하거나 평균 내지 않는다 — 두 Profile은 항상 독립적으로 계산한 뒤 결과만 비교한다. Session별 원본 Evidence와 Profile Version을 보존하며, 다른 user_id의 데이터가 조회되지 않도록 Repository 계층에서 user_id 조건을 강제한다.

---

# 23. Knowledge Graph와 Obsidian

Obsidian은 DB나 실제 추천 엔진으로 사용하지 않는다.

> 추천 결과가 어떤 Trait·전공·학과·과목·직무와 연결됐는지 시각적으로 보여주는 발표용 Explainability View로 사용한다.

## Source of Truth

```text
PostgreSQL
```

## 발표용 Student Subgraph

전국 데이터를 모두 표시하지 않고 데모 학생과 관련된 24~38개 노드만 Export한다. Core Trait 노드는 Primary 확정 Trait(STRONG/MODERATE)만 사용한다. §12-2의 확장 Trait는 별도의 Related Concept 노드로 최대 3~5개까지만 추가한다.

```text
Student                 1개
Core Trait              5~7개
Related Concept         0~5개 (§12-2, 선택)
Career Dimension        3~4개
Canonical Major         3개
Department              5~7개
High School Subject     4~6개
Occupation              3~5개
```

## Node

```text
Student
Trait
RelatedConcept
CareerDimension
CanonicalMajor
Department
University
HighSchoolSubject
Occupation
```

## Edge

```text
Student ─HAS_TRAIT→ Trait
Trait ┄RELATED_CONCEPT┄→ RelatedConcept   (점선, Student와 직접 연결하지 않음)
Trait ─GROUPED_AS→ CareerDimension
Trait ─RELATED_TO→ CanonicalMajor
CanonicalMajor ─HAS_DEPARTMENT→ Department
Department ─BELONGS_TO→ University
CanonicalMajor ─RECOMMENDS→ HighSchoolSubject
CanonicalMajor ─RELATED_TO→ Occupation
```

각 Edge는 화살표 그 자체가 아니라 다음 필드를 가진 레코드에서 파생된다. 이 필드가 있어야 "이 연결이 어떤 Evidence·공식 자료에서 나왔는지"를 추적할 수 있다.

```python
class SubgraphEdge(BaseModel):
    source_node_id: str
    target_node_id: str
    relation_type: str
    relevance_level: int
    evidence_ids: list[str]
    source_ids: list[str]
    mapping_version: str
    created_at: datetime
```

## Obsidian 역할

```text
추천 완료
→ Student Subgraph 생성
→ Markdown + Wiki Link Export
→ Obsidian Graph View
→ 발표에서 추천 근거 시각화
```

노드 색상 예시:

```text
Student          노랑
Trait            보라
RelatedConcept   회색(점선 테두리)
CareerDimension  분홍
Major            파랑
Department       초록
Subject          주황
Occupation       빨강
```

Obsidian 양방향 동기화, 전체 사용자 Vault 관리, 웹서비스 핵심 UI는 구현하지 않는다. 발표 실패에 대비해 Graph 동작 영상을 미리 녹화한다.

---

# 24. LLM API와 비용 통제

API는 백엔드에서만 호출한다.

```text
Browser
→ Backend
→ LangGraph
→ LLM API
```

키는 `.env`로 관리하며 클라이언트 번들, Git, 로그에 포함하지 않는다.

```env
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=
LLM_TIMEOUT_SECONDS=6
LLM_MAX_RETRIES=1
LLM_MAX_CALLS_PER_SESSION=40
```

비용 통제:

- 동일 State 질문 캐싱
- 질문당 출력 토큰 제한
- 최대 재시도 1회
- Code Quality Gate 우선
- Semantic LLM Check는 필요한 경우에만 호출
- 세션별 호출 수 제한
- 모델명·토큰·Latency·성공 여부만 로깅
- API Key와 Authorization Header는 로깅 금지

세션당 40회는 모든 단계가 제한 없이 호출할 수 있다는 뜻이 아니라 다음 예산 안에서 사용하는 안전 상한이다.

| 호출 구간 | 최대 예약 호출 수 | 비고 |
|---|---:|---|
| 꼬리질문 생성 | 30 | 최대 5 Context × 6개 |
| 재생성·선택적 Semantic Check | 3 | 전역 예산, 초과 시 Cache/Backup |
| 결과 카드 생성 | 1 | Structured Profile을 문장으로 변환 |
| 전공·학과 설명 | 2 | 검색 근거가 있을 때만 호출 |
| 과목 추천 설명 | 1 | 규칙 계산 후 설명만 생성 |
| 예비 여유 | 3 | 총합 40회 |

Primary Evidence 계산은 LLM을 호출하지 않는다. 답변 문맥의 Secondary Hypothesis 추출이 필요하면 다음 질문 생성 호출의 Structured Output에 함께 포함하고 별도 호출을 만들지 않는다. 누적 호출이 예약 한도에 도달하면 남은 과정은 Cache·Backup과 규칙 기반 설명으로 완주한다. 발표용 고정 경로는 사전 캐시를 우선 사용한다. Trait Relation Table(§12-2) 생성도 세션 중 호출이 아니라 콘텐츠 준비 단계의 오프라인 1회성 작업이므로 이 예산에 포함하지 않는다.

## LangSmith Observability

LangGraph 실행과 각 LLM 호출을 LangSmith Trace로 기록해 실제 Node 실행 순서, Conditional Edge 분기, 프롬프트 버전, 비용, 오류와 품질을 관찰한다. §28 [2]번 Vertical Slice 단계부터 Assessment Graph 전체에 연동하며, 질문 생성 함수 하나만 추적하는 구조로 제한하지 않는다. MVP에서는 Langfuse를 중복 도입하지 않는다.

```text
Assessment Session Trace
├ Context Selector
├ Target Planner
├ Question Generator
├ Quality Gate
├ 재생성 또는 Fallback
├ Evidence Update
├ Stop / Continue Decision
├ Profile Summary Generator
├ Major Explanation
└ Course Explanation
```

Assessment Session 하나를 최상위 Trace 하나로 보고, 각 Graph Node와 LLM 호출을 하위 Run으로 연결한다. PostgreSQL의 `session_id`와 LangSmith의 `trace_id`를 매핑하되, LangSmith에는 익명화된 식별자만 전달한다.

기록 항목: `prompt_version`, `model`, `graph_node`, `context_id`, `question_index`, `frame_id`, `blueprint_id`, `target_trait_ids`, `planner_decision_reason`, `stop_reason`, `latency`, `token usage`, `estimated cost`, `schema validation 결과`, `quality gate 결과`, `재생성 여부`, `cache/fallback 여부`.

```text
저장 가능
- 익명 session_id, context_id, trait_id, role_id
- graph_node, planner_decision_reason, stop_reason
- latency, token usage, error
- Quality Gate 결과

저장 금지
- 이름, 학교, 연락처
- 자유서술 답변 원문
- 성적 원문
- 상세 Career Profile 문장
```

백엔드 환경변수로 `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`를 관리하고 API Key를 코드·프론트엔드·Git 저장소에 포함하지 않는다. Trace 전송 직전에 Sanitizer가 저장 금지 필드와 자유서술 원문을 제거한다.

공모전 데모에서는 `demo_user_01`의 가상 답변만 기록한다. LangSmith가 응답 불가 상태여도 질문 생성과 세션 진행은 막히지 않는다(fail-open) — Trace 기록 실패는 로컬 오류 로그만 남기고 넘어간다. PostgreSQL의 사용자 상태와 Evidence가 기준 데이터이며 LangSmith Trace를 복원 데이터로 사용하지 않는다.

Hand-Calculated Fixture와 고정 Persona 실행은 LangSmith Dataset/Experiment에 연결해 프롬프트·모델 버전별 결과를 비교할 수 있다. 단, 점수 계산·정책 준수 여부는 기존 Evaluation Harness가 결정하고 LangSmith에는 결과와 메타데이터만 기록한다. LangSmith는 Trait Ontology의 타당성, Question–Trait Mapping의 정확성, 심리측정학적 신뢰도를 보증하지 않는다.

---

# 25. Guardrails

## 출력 표현

금지:

```text
너는 컴퓨터공학에 적성이 없다.
반드시 이 학과로 가야 한다.
이 대학에 합격할 수 있다.
분석력 92%다.
```

허용:

```text
현재 답변에서는 관련성이 높게 나타났습니다.
여러 Context에서 반복적으로 관찰됐습니다.
추가 탐색이 필요한 영역입니다.
다른 전공과 함께 비교할 수 있습니다.
```

## 데이터와 안전

- 미성년자 개인정보 최소 수집
- 자유서술 답변에서 개인정보 제거
- 업로드 파일 형식·크기 제한
- 외부 문서를 명령이 아닌 데이터로 처리
- 문서 Prompt Injection 방어
- 출처 없는 학과·과목 설명 차단
- 자료의 기준 날짜와 URL 저장
- 생성 질문의 민감 주제 제한
- 질문 원문과 구조화 Evidence 저장 범위 분리

---

# 26. Evaluation Harness

Evaluation은 마지막 단계가 아니라 Schema 확정 시점부터 함께 작성한다.

## 구현 범위 — 코드 vs 사람 확인

이 Section에 나열된 항목을 전부 자동화된 코드로 만들지 않는다. 성격이 다른 두 그룹으로 나눠서 다룬다.

```text
코드로 자동화 (eval/*.py, Vertical Slice 단계부터 구현)
- Quality Gate·policy_guard가 런타임에 이미 검사하는 규칙을 고정 시나리오에 재실행해 회귀 검증
- 예: Structured Output 성공률, 선택지 5개, Role ID 일치, 중복 question_id,
     질문 횟수 분포, 최소/최대 문항 준수, Fallback 성공률, 역할 충족률,
     option_id 서버 생성, support_ratio 범위, UNMAPPED_TRAIT 비율,
     동일 답변 재실행 일관성, policy_guard 6개 규칙, Missing Trait 마스킹, 내부 숫자 미노출

사람이 직접 확인 (코드화하지 않음, 3~5명 내부 파일럿·수기 검토)
- 자연스러움·유도성처럼 주관적 판단이 필요한 항목
- 25/30/35/45문항 비교 파일럿
- 관련도 순위·Mapping의 2인 교차검토
- "학생이 결과를 자신과 유사하다고 평가한 정도"
```

아래 목록의 각 항목이 어느 쪽인지는 §6-6 Hand-Calculated Fixture와 겹치는 것부터 코드로 우선 구현하고, 나머지는 파일럿 체크리스트로 관리한다. 목록 전체를 Vertical Slice 안에서 다 구현하는 것이 목표가 아니다.

## Assessment

```text
Structured Output 성공률
선택지 5개 성공률
Role ID 일치율
질문 의미 중복률
Target Trait 준수율
유도 선택지 발생률
자기확증 방지 규칙 준수율
Fallback 성공률
25~35문항 가변 종료 성공률
Context–Trait Content Balancing 준수율
선호 Context 4개 + Contrast Context 1개 구성 성공률
관심도 1점 Context의 Contrast 후보 제외율
Contrast Context 제안·교체 HITL 반영률
Coverage 부족 시 교체 후보 최대 2개 제한 준수율
최소 4개 이전 조기 종료 방지율
최대 6개 초과 방지율
Seed·필수 꼬리질문 역할 충족률
Explicit Conflict 오탐률·해소율
Context Dependency와 Conflict 구분 정확성
Secondary Hypothesis의 점수 미반영 준수율
Secondary Hypothesis 상태 전이 정확성
동일 질문 내 Trait 중복 배정 방지율
support_ratio 0~1 범위 준수율
support_ratio가 Trait 강도 점수에 사용되지 않는지 확인
option_id 서버 생성 준수율(LLM 미포함 확인)
Planner 우선순위 사전식 규칙 준수율(상위 조건 위반 발생률)
Related Trait Signal의 결과 카드·매칭 점수 미반영 준수율
INSUFFICIENT 세부 사유(NOT_PROBED/EVIDENCE_LIMITED) 분포
15개 Context Seed 정상 출력률
공용 Fallback 완주율과 Role 준수율
핵심 5개와 공용 10개 Context의 Quality Gate 통과율 차이
핵심 5개와 공용 10개 Context의 질문 의미 중복률 차이
핵심 5개와 공용 10개 Context의 Target Trait 준수율 차이
핵심 5개와 공용 10개 Context의 유도 선택지 발생률 차이
핵심 5개와 공용 10개 Context의 평균 재생성 횟수·Latency 차이
평균 Latency와 호출 비용
LangSmith Trace 기록 성공률과 fail-open 동작 확인
LangGraph Node·Conditional Edge 추적 누락률
planner_decision_reason·stop_reason 기록 누락률
저장 금지 데이터의 Trace 포함 여부
```

## 검사 길이 파일럿

다음 네 조건을 비교한다.

```text
A: Context당 꼬리질문 4개 → 상황형 질문 총 25개
B: Context당 꼬리질문 5개 → 상황형 질문 총 30개
C: Context당 꼬리질문 6개 → 상황형 질문 총 35개
D: 비교 기준용 꼬리질문 8개 → 상황형 질문 총 45개
```

평가 항목:

```text
완료시간과 중도이탈
후반부 응답시간 급감
동일 선택지 반복
Student Vector 안정성
질문 역할 Coverage
추가 질문으로 새로 확인된 Primary Trait 수
학생이 결과를 자신과 유사하다고 평가한 정도
```

45문항은 정답이나 Gold Standard가 아니라 긴 조건과 짧은 조건의 결과 변화를 살펴보기 위한 임시 비교 조건이다. 3~5명 내부 파일럿으로 완료시간, 질문 중복, 역할 누락, 조기·지연 종료 같은 UX와 로직 오류를 점검하고 데모용 초기 휴리스틱을 설정한다. 이 규모의 결과로 문항 수·Trait 신뢰도·종료 임계값의 통계적 타당성이 확정됐다고 주장하지 않는다.

## Trait Extraction

```text
허용 Ontology 매핑률
UNMAPPED_TRAIT 비율
동일 답변 재실행 일관성
Context 간 Evidence 중복 집계 여부
사전 정의 Contrast Pair의 Explicit Conflict 탐지율
서로 다른 Context 선택의 Conflict 오탐률
```

## Major

```text
Canonical Mapping 정확도
관련도 순위의 2인 교차검토 결과
Question–Trait / Major–Trait Mapping의 2인 교차검토 완료율
미해결 REVIEW_REQUIRED 항목의 운영 경로 유입 방지율
Missing Trait 처리 정확성
RAG Recall@K
근거 없는 설명 비율
출처 연결 성공률
내부 숫자 관련도의 사용자 화면 노출 방지율
추천 상위·학생 선택 학과 외 공식 홈페이지 RAG 호출 방지율
입결 기준연도·전형·모집단위·지표 비교 가능성 검사 통과율
비교 불가능한 학과의 개인화 성적 목록 제외율
전국 전체 목록과 성적 유사 범위 목록의 UI 구분 여부
```

## Course

```text
존재하지 않는 과목 추천 여부
이수과목 중복 추천 여부
미개설과목 처리 여부
과목 파일 추출 정확도
사용자 확인 후 정정 반영 여부
```

## End-to-End Persona

최소 다음 시나리오를 준비한다.

```text
분석·구조화 중심
창의·표현 중심
인간·관계 중심
실행·제작 중심
관심 분산형
Explicit Conflict 포함형
Context Dependency 포함형
낮은 관심도지만 활동 특성이 드러나는 Contrast Context형
```

## Memory / Session

```text
Profile 저장 후 새 Session 복원 성공률
user_id별 최신 완료 Profile 조회 정확성
다른 user_id Profile 접근 차단 여부
이전 Profile을 확정값으로 덮어쓰지 않는지 여부
Session별 Evidence와 Profile Version 보존 여부
V1/V2 변화 비교 정확성
```

---

# 27. 권장 모듈 구조

```text
src/
├ agents/
│  ├ orchestrator/
│  ├ assessment/
│  │  ├ graph.py
│  │  ├ target_planner.py
│  │  ├ question_generator.py
│  │  └ quality_gate.py
│  ├ major/
│  └ course/
│     └ course_document_parser.py
├ engines/
│  ├ evidence_engine.py
│  ├ conflict_engine.py
│  ├ context_selector.py
│  ├ trait_normalizer.py
│  ├ trait_relation_engine.py
│  ├ profile_vectorizer.py
│  ├ similarity_engine.py
│  ├ canonical_mapper.py
│  ├ admission_filter.py
│  ├ course_engine.py
│  └ policy_guard.py
├ mcp/
│  └ education_server.py
├ rag/
│  ├ ingest.py
│  ├ normalize.py
│  ├ chunk.py
│  ├ embed.py
│  └ retrieve.py
├ memory/
│  ├ checkpoint.py
│  ├ profile_store.py
│  └ session_loader.py
├ observability/
│  ├ langsmith_tracing.py
│  └ trace_sanitizer.py
├ repositories/
│  ├ profile_repository.py
│  ├ department_repository.py
│  └ admission_repository.py
├ graph/
│  ├ subgraph_builder.py
│  └ obsidian_exporter.py
├ schemas/
│  ├ question.py
│  ├ trait.py
│  ├ evidence.py
│  ├ profile.py
│  ├ major.py
│  └ course.py
├ config/
│  └ matching_policy.yaml
├ data/
│  ├ trait_ontology/
│  ├ questions/
│  ├ question_frames/
│  ├ option_blueprints/
│  ├ majors/
│  ├ departments/
│  ├ admissions/
│  ├ trait_relations/
│  └ subjects/
└ eval/
   ├ assessment_eval.py
   ├ trait_eval.py
   ├ matching_eval.py
   ├ retrieval_eval.py
   ├ policy_guard_test.py
   └ end_to_end_eval.py
```

`policy_guard.py`는 이 문서 전체에 흩어진 불변식을 한곳에서 강제하는 모듈이다 — 각 규칙은 이미 다른 Section에서 개별적으로 정의됐지만(§6-3 UNMAPPED_TRAIT, §11 Code Check, §24 호출 예산, §5-1/§8 전공 순위 미참조, §20 미개설과목 금지), 모듈마다 따로 구현하면 어느 하나가 규칙을 빠뜨릴 위험이 있다.

```text
policy_guard.py가 막는 것
- Ontology에 없는 Trait ID는 `UNMAPPED_TRAIT`로 저장하고 결과 계산에서 제외 (§6-3)
- LLM이 반환한 Role ID가 Blueprint와 다르면 거부 (§11)
- Option이 정확히 5개가 아니면 거부 (§11)
- LLM 호출 예산 초과 시 호출 자체를 차단 (§24)
- 전공 관련도·순위를 Assessment Planner 입력으로 전달하지 않음 (§5-1, §8)
- POST_OFFERING 단계에서 학교 개설 목록에 없는 과목을 실제 개설과목처럼 추천하지 않음 (§20)
```

`eval/policy_guard_test.py`는 이 여섯 가지를 위반하는 입력을 의도적으로 넣어 실제로 차단되는지 확인하는 계약 테스트다.

---

# 28. 수정된 구현 순서

```text
[0] Context Definition Table로 15개 Context 이름·정의·핵심 5개 여부 확정 (§6-6)
        ↓
[1] 최소 인터페이스 4종 스켈레톤 확정
통합 Option/Evidence Schema (option_id 서버 생성 포함)
Vertical Slice Trait Ontology 10~15개 (primary_vector_group 포함)
Context 15개 × Shared Trait 12~15개 Coverage Matrix (Career Dimension 요약은 이 Matrix에서 파생)
역할 기반 Stop/Continue 규칙, Planner 우선순위는 사전식 단일 규칙으로 확정
primary_trait_delta=1 저작 규칙과 세분화된 Trait 상태 판정 규칙
§6-6의 필수 콘텐츠 산출물 Vertical Slice 버전
        ↓
[2] Context 2~3개 Vertical Slice
Seed → 질문 생성 → Evidence → Profile → 결과 카드까지 연결
Assessment LangGraph에 LangSmith 최소 Trace 연동
(익명 session_id, graph_node, prompt_version, latency/token/error,
Quality Gate 결과, planner_decision_reason, stop_reason, fail-open 확인)
        ↓
[3] Evidence Engine + support_ratio 보조지표 + 상태 판정 + Student Vectorizer
        ↓
[4] 기본 Seed 1개 + 꼬리질문 5개 흐름
전공 순위를 참조하지 않는 Assessment LangGraph
        ↓
[5] Career Profile 확정 후 전공 3~5개 매칭
        ↓
[6] 결과 카드 UI + 상세 Evidence
        ↓
[7] 핵심 5개 Context 전용 Frame으로 확장
나머지 10개 Context Seed + 공용 Fallback 경로 추가
Trait Ontology를 실제 구현 규모 12~15개로 확정
선택적 발표 확장(시간이 남으면): 검토된 RelatedConcept 최대 3~5개를 Trait Relation Table로 연결
— Student Profile 계산과 전공 Matching에는 사용하지 않으며, 완주 못 해도 핵심 데모에 지장 없음
        ↓
[8] 대표 전공 Profile 5~8개 + Similarity Engine 고도화
        ↓
[9] B340014 API로 전국 대학 목록(약 377개) 수집 → 학교별 학과 상세 순회 적재 + Canonical Mapping
비교 가능한 공식 입결 학과 15~30개 Subset 구축
        ↓
[10] 추천 상위·학생 선택 학과 중심 RAG + Education MCP
        ↓
[11] 특정 학교 과목 데이터 + Course Planning
        ↓
[12] Student Subgraph + Obsidian 발표 화면
        ↓
[13] user_id Profile Store + 새 Session 복원 + 학기 변화 비교
        ↓
[14] 캐시·Fallback·발표 영상·리허설
```

Evaluation Harness와 소형 Persona Set은 각 단계와 동시에 확장한다. Trait 50~100개 전체, 15개 Context 전용 Frame 완성, 전국 학과 공식 홈페이지 전체 수집과 전국 입결 정밀 비교는 Vertical Slice가 안정적으로 완주한 이후의 확장 범위다.

---

# 29. 발표 시연 Flow

메인 발표는 질문 품질과 Cache를 검토한 핵심 5개 Context가 선택되는 `demo_user_01` 시나리오로 진행한다. 화면에서는 15개 Context를 모두 선택할 수 있고, 나머지 10개도 Seed와 공용 Shared Trait Frame으로 완주할 수 있게 한다. 심사위원이 다른 Context를 요청할 때는 공용 Fallback 경로를 보여주되, 핵심 5개는 전용 Frame을 적용한 발표 우선 범위이고 나머지 전용화는 후속 확장임을 명확히 설명한다.

```text
1. 학생이 15개 Context의 관심도를 빠르게 평가
2. 선호 Context 4개 선택
3. Agent가 Contrast Context 1개와 필요 시 Coverage 교체 후보 제안
4. 학생 확인·유지·교체 후 5개 심층 Context 확정
5. Context별 Seed Question으로 초기 Trait Evidence 확보
6. 실시간 LLM이 선택한 보기에 맞는 꼬리질문 생성
7. 최소 4개 이후 필수 질문 역할과 Primary Evidence 상태를 확인해 기본 5개·최대 6개 진행
8. LangGraph State에서 Evidence 상태가 갱신되는 모습 표시
9. 핵심 특징 5~8줄 결과 카드 출력
10. 숫자 없이 관련성 높은 전공과 함께 탐색할 전공 제시
11. 전국 실제 학과 탐색 및 선택적 성적 유사 범위 필터
12. 추천 상위 또는 학생 선택 학과의 공식 홈페이지 RAG
13. 학교 실제 개설과목을 반영한 과목 추천
14. 새 Session에서 이전 Profile Store를 불러와 학기 변화 시연
15. "왜 이런 결과가 나왔을까요?" 이후 Obsidian 전환
16. Student → Trait → Major → Department → Subject → Occupation 관계 시각화
```

발표 메시지:

> 수만 개의 질문을 미리 분기하지 않습니다. 학생이 선택한 선호 Context 4개와 Agent가 제안한 Contrast Context 1개에서 검토된 Seed Question으로 시작한 뒤, Agent가 아직 확인되지 않은 Trait와 명시적 대조 Evidence를 판단하고 LLM이 선택된 경로의 꼬리질문 하나만 실시간 생성합니다. 질문 단계에서는 전공 순위를 참조하지 않으며, Profile 확정 후 전공·과목과의 내부 관련도를 계산합니다. 사용자에게는 숫자 점수 대신 관련성 수준과 답변 근거를 보여주고, 성적을 입력하면 동일 기준의 공식 입결 자료가 있는 학과만 성적 유사 범위로 제시합니다.

---

# 30. 최종 한 문장 구조

> **LangGraph 기반 Assessment Agent가 선호 Context 4개와 HITL Contrast Context 1개에서 학생 답변에 맞는 실시간 꼬리질문을 생성하고, 검토된 Primary Evidence의 횟수·Context 다양성·반복성·명시적 대조 관계로 Career Profile을 만든다. Profile 확정 후 대학 전공과 고교 과목을 같은 Trait 공간에서 비교하고, 전국 실제 학과 Master와 비교 가능한 입결 Subset을 통해 학과를 탐색한다. 결과는 숫자 확률이 아닌 관련성 수준과 핵심 특징으로 설명하며, user_id 기반 Store로 학기별 변화를 이어서 관리한다.**

---

# 31. 버전과 변경 정책

**v1.0 FROZEN — 2026-08-20.** 이 설계안은 Vertical Slice 구현 착수 시점으로 동결한다. 이후 새로운 아이디어가 떠올랐다는 이유만으로 설계를 변경하지 않는다.

## FROZEN CORE

다음은 재변경 조건을 만족하는 실패가 발견되지 않는 한 변경하지 않는다.

```text
Trait 12~15개
선호 Context 4개 + Contrast Context 1개
Context별 Seed 1개 + 꼬리질문 4~6개
질문 역할 1~6 (§7-2)
Planner 우선순위 (§8)
Evidence 상태 판정 순서 (§13)
Explicit Conflict 규칙 (§12-1)
Student/Major/Subject Vector 척도 (1.00/0.67/0.33)
숫자를 노출하지 않는 결과 표현 (§16)
전국 Master DB + 입결 Subset 분리 (§18)
LangGraph·LangChain·MCP·RAG 역할 분리
```

## OPTIONAL / CUTTABLE

일정에 따라 축소 가능하며, 축소해도 FROZEN CORE에는 영향이 없다.

```text
RelatedConcept 3~5개 (§12-2)
Obsidian 실시간 실행 (녹화 영상으로 대체 가능)
2학기 Profile 변화 시연
핵심 5개 외 Context의 전용 Frame
공식 홈페이지 RAG 대상 확대
입결 Subset 15개 초과
```

## 재변경 조건

다음 경우에만 설계를 다시 연다.

```text
Vertical Slice에서 재현 가능한 실패 발생
Hand-Calculated Fixture와 코드 결과 불일치
질문이 반복되거나 역할을 충족하지 못함
Evidence가 대부분 Mask되어 추천이 나오지 않음
공식 API가 설계된 형태로 동작하지 않음
LLM 비용·Latency가 발표 가능한 수준을 초과
공모전 요구사항 변경
```

그 외 아이디어는 이 설계안에 바로 반영하지 않고 `idea_backlog.md`에 기록한다.

## Vertical Slice 완주 기준

```text
Context 2~3개, Trait 10~12개, 대표 전공 3개로
Seed → 꼬리질문 → Evidence Ledger → Profile 상태 판정 → 전공 Matching → 결과 카드 → LangSmith Trace
까지 고정 Persona 하나가 끝까지 통과한다
```

```text
질문 역할 1~4가 빠지지 않음
Evidence 수기 계산(§6-6 Hand-Calculated Fixture)과 코드 결과가 일치
전공 추천 근거를 Evidence까지 역추적 가능
LLM 장애 시 Backup으로 완주
LangSmith 장애가 세션 진행을 막지 않음(fail-open)
Trace에 저장 금지 데이터가 포함되지 않음
```
