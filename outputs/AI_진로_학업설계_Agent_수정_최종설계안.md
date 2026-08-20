# AI 진로·학업설계 Agent — 수정 최종 설계안

## 0. 프로젝트 정의

고등학생이 자신이 좋아하는 관심 Context 안에서 상황형 질문에 답하면, AI가 답변에 나타난 세부 관심·행동·사고 특성을 추출한다. 학생과 대학 전공·고교 선택과목을 동일한 Trait 공간에 벡터화하고 유사도를 계산하여 다음 의사결정을 지원한다.

```text
관심 Context 선택
→ 고정 공통질문
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
- 관심 카테고리 15개
- 카테고리 5개 선택
- 카테고리당 고정 공통질문 3개
- 카테고리당 LLM 생성 꼬리질문 8개
- 사용자 총 응답 55개
- 세부 Trait Ontology 50~100개
- 상위 Career Dimension 6~10개
- 대표 전공군 5~8개
- 실제 대학 학과 샘플 30~50개
- 특정 고등학교 교육과정 데이터 1개
- 선택적 성적 기준 정렬 샘플
- Education Data MCP 서버 1개
- 학생 관련 Subgraph의 Obsidian 시각화
- Evaluation Harness와 발표용 캐시

## 시연 또는 Snapshot으로 구현

- 1학기 Profile과 2학기 Profile 변화
- API 장애 시 캐시된 질문 경로
- 학교 PDF 또는 Excel에서 추출한 과목의 사용자 확인
- 추천 결과의 학생별 Knowledge Subgraph

## 후속 확장

- 회원가입과 실제 다중 사용자 운영
- 전국 대학 학과 공식 홈페이지 전체 수집
- 전국 학교 교육과정 자동 연동
- 실제 사용자 단위 Long-term Memory
- 대학별 정밀 합격 가능성 예측
- 모든 사용자 대상 Obsidian Vault 제공

---

# 2. 검사 정책

검사 규모는 코드 설정으로 고정한다.

```yaml
assessment_policy:
  available_contexts: 15
  selected_contexts: 5
  common_questions_per_context: 3
  adaptive_questions_per_context: 8
  total_questions: 55
  max_regeneration: 1
  generation_timeout_seconds: 6
  max_llm_calls_per_session: 55
```

## 질문 구성

```text
선택 Context 5개

각 Context:
고정 공통질문 3개
+ 실시간 생성 꼬리질문 8개
= 11개

전체:
5 × 11 = 55문항
```

질문 55개가 모두 상황형이므로 실제 사용자 테스트를 통해 소요시간을 측정한다. 프로토타입에서는 검사 시간을 약 25~35분 범위로 가정하되, 측정 결과에 따라 꼬리질문 개수를 설정값으로 변경할 수 있게 한다.

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
├ Session / State
├ Question / Answer
├ Trait Ontology / Evidence
├ Student Vector
├ Major / Department Vector
├ Subject Vector
├ Canonical Mapping
└ Source / Version

pgvector
├ Department description embeddings
├ Curriculum embeddings
└ Semantic duplicate detection
```

## 구성 원칙

- LangGraph는 상태 전이와 반복을 관리한다.
- Python Engine은 점수·제약·유사도를 계산한다.
- LLM은 질문 표현, 제한된 Trait 추출, 설명 생성을 담당한다.
- PostgreSQL이 Source of Truth다.
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

## 5-1. 2-Pass 질문 진행

먼저 선택한 5개 Context의 공통질문을 모두 진행한 뒤, 전체 초기 Evidence를 바탕으로 꼬리질문을 생성한다.

```text
PASS 1 — Initial Exploration

Context A 공통질문 3개
Context B 공통질문 3개
Context C 공통질문 3개
Context D 공통질문 3개
Context E 공통질문 3개
→ 초기 Global Evidence 생성

PASS 2 — Adaptive Exploration

Context A 꼬리질문 8개
Context B 꼬리질문 8개
Context C 꼬리질문 8개
Context D 꼬리질문 8개
Context E 꼬리질문 8개
→ 최종 Student Profile 생성
```

이 방식은 첫 Context의 질문부터 다른 Context에서 관찰된 패턴을 교차 확인할 수 있게 한다.

## 5-2. Assessment Graph

```text
START
 ↓
Demo Snapshot / Session Load
 ↓
Context 5개 선택
 ↓
모든 Context 공통질문 15개
 ↓
Initial Evidence Update
 ↓
Adaptive Context 선택
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
Context별 꼬리질문 8개?
 ├ NO → Planner
 └ YES → 다음 Context
 ↓
전체 Context 완료?
 ├ NO → 다음 Context
 └ YES → Career Profile 생성
 ↓
END
```

---

# 6. Trait Ontology

학생 답변, 대학 전공, 고교 과목을 같은 의미 공간에서 비교하기 위해 고정 Trait Ontology를 사용한다.

## 6-1. 세부 Trait

내부 매칭에는 50~100개의 세부 Trait를 사용한다.

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
```

LLM은 새로운 Trait를 자유롭게 생성하지 않는다. 기존 Ontology에 없는 후보는 `UNMAPPED_TRAIT`로 저장하고 프로토타입 결과 계산에서는 제외한다.

---

# 7. Question Design

## 7-1. 고정 공통질문

15개 Context에 각 3개의 공통질문을 수작업으로 설계한다.

```text
15 × 3 = 고정 공통질문 45개
```

세 질문의 공통 역할:

1. 어떤 부분에서 흥미를 느끼는가
2. 무엇을 기준으로 판단하는가
3. 어떤 활동이나 역할을 선호하는가

## 7-2. 선택지마다 저장할 정보

각 보기에 고정된 다음 질문 문장을 저장하지 않는다. 다음 질문의 목적을 저장한다.

```json
{
  "option_id": "media_common_01_o3",
  "text": "촬영·편집·음악을 감상할 때",
  "primary_trait_roles": [
    "creative_expression",
    "production_interest"
  ],
  "secondary_trait_roles": [
    "sensory_attention"
  ],
  "next_probe": "제작 요소 중 구체적인 관심 지점 확인",
  "preferred_frames": [
    "focus_selection",
    "activity_preference"
  ]
}
```

사용자가 선택한 Option의 `next_probe`만 LLM에 전달한다. 선택되지 않은 네 경로의 질문은 생성하지 않는다.

## 7-3. 질문 프레임

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
상충 Evidence
최근 선택 Option의 next_probe
현재 상위 전공 후보
이미 출제한 질문
남은 질문 수
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

```text
1. 직전 답변에서 강하게 나타난 관심의 세부 탐색
2. 현재 상위 전공 후보를 구분하는 Trait
3. 상충 Evidence가 있는 Trait
4. 다른 Context에서 교차 확인이 필요한 Trait
5. 전체 Profile에서 Evidence가 부족한 핵심 Trait
6. 반복 질문 감점
```

```text
priority
= recent_answer_relevance
+ major_discrimination_value
+ conflict_need
+ cross_context_need
+ coverage_gap
- repetition_penalty
```

모든 Trait를 억지로 측정하지 않는다. Evidence가 없으면 `INSUFFICIENT`로 남긴다.

## 자기확증 방지 규칙

- 동일 Trait를 연속 3회 이상 묻지 않는다.
- Context별 최소 한 질문은 반대 또는 대안 가능성을 확인한다.
- Context별 최소 한 질문은 다른 Context의 Evidence를 교차 확인한다.
- 강한 Trait만 반복 강화하지 않는다.
- 초기 한 답변이 이후 전체 질문을 결정하지 않도록 Global State를 사용한다.

---

# 9. Option Blueprint

LLM이 선택지별 점수를 임의로 만들지 못하게 Option Role과 Trait Vector를 코드로 관리한다.

```json
{
  "blueprint_id": "problem_response_v1",
  "roles": [
    {
      "role_id": "cause_analysis",
      "trait_delta": {
        "causal_analysis": 2,
        "logical_verification": 1
      }
    },
    {
      "role_id": "strategy_change",
      "trait_delta": {
        "adaptability": 2,
        "alternative_generation": 1
      }
    },
    {
      "role_id": "direct_trial",
      "trait_delta": {
        "tool_execution": 2,
        "experimentation": 1
      }
    },
    {
      "role_id": "external_research",
      "trait_delta": {
        "information_search": 2
      }
    },
    {
      "role_id": "ask_others",
      "trait_delta": {
        "collaboration": 1,
        "user_perspective": 1
      }
    }
  ]
}
```

LLM은 각 Role을 학생의 Context에 맞는 자연스러운 선택지로 표현한다. Evidence 계산은 Role의 고정 `trait_delta`를 사용한다.

LLM이 답변 문맥에서 추가로 추출한 Secondary Trait는 허용된 Ontology 안에서만 저장하고, Primary Evidence보다 낮은 가중치를 적용한다.

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
    option_id: str
    role_id: str
    text: str

class GeneratedQuestion(BaseModel):
    question_id: str
    context: str
    target_traits: list[str]
    frame_id: str
    question_text: str
    options: list[GeneratedOption]
```

`question_id`는 LLM이 결정하지 않고 서버가 생성한다.

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

```text
선택지 의미 중복
특정 선택지가 정답처럼 보이는지
고등학생에게 자연스러운지
질문이 지나치게 복합적인지
질문과 Target Trait가 일치하는지
기존 질문과 의미적으로 지나치게 유사한지
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
```

공모전 발표 경로는 미리 한 번 실행하여 40개의 꼬리질문을 캐싱한다. 일반 장애에 대응할 최소 Backup Question은 Context별 2~3개 준비한다.

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
  "trait_scores": {
    "causal_analysis": 2,
    "logical_verification": 1
  },
  "context": "media",
  "source_type": "generated_question",
  "generator_version": "qgen_v1",
  "quality_gate_status": "passed",
  "cross_context_group": "problem_response"
}
```

Trait별로 다음을 계산한다.

```text
raw_score
evidence_count
context_count
cross_context_consistency
conflict_count
coverage
source_diversity
```

한 답변이 여러 Trait Evidence를 만들 수 있지만, 같은 질문에서 파생된 Evidence를 독립 질문 여러 개처럼 계산하지 않는다.

---

# 13. Student Multi-Vector Profile

학생을 하나의 임베딩으로만 표현하지 않고 의미 종류별 다중 벡터로 표현한다.

```text
Interest Vector
어떤 대상과 활동에 관심을 가지는가

Cognitive Approach Vector
정보를 어떻게 해석하고 문제를 해결하는가

Work Style Vector
어떻게 계획·실행·협업하는가

Environment Preference Vector
어떤 활동 환경과 결과물 형태를 선호하는가
```

미측정 Trait는 0점으로 처리하지 않는다. `UNKNOWN` 또는 Mask로 제외한다.

내부 상태:

```text
STRONG
MODERATE
LIMITED
CONFLICTING
INSUFFICIENT
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
  "source_ids": []
}
```

예:

```text
미디어커뮤니케이션

서사 구성             0.78
사용자 반응 분석       0.85
정보 탐색             0.70
창의적 표현           0.78
도구 활용             0.52
정량 분석             0.43
협업                  0.68
```

전공 Profile의 초기 가중치는 공식 자료와 팀의 Mapping 표를 근거로 만들고, 파일럿 평가를 통해 조정한다.

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

`INSUFFICIENT`는 0으로 계산하지 않는다. 실제로 측정된 Trait만 분모에 포함한다.

```text
score
= 측정된 Trait의 가중 유사도 합
÷ 실제 비교에 사용된 가중치 합
```

## 사용자 표시

```text
전공 관련도

1. 미디어커뮤니케이션  84
2. HCI·UX             81
3. 산업공학            77
4. 데이터사이언스      72
```

점수는 적성 확률이나 성공 가능성이 아니다.

> 관련도는 현재 답변에서 추출된 활동 선호·문제 접근 방식과 전공의 학습 활동을 비교한 상대적 지표입니다.

Raw cosine similarity에 단순히 100을 곱하지 않는다. 후보군 내 분포와 평가 데이터에 기반해 관련도 지수로 변환한다.

관련도와 Evidence 충분성을 분리한다.

```text
미디어커뮤니케이션
관련도 84
Evidence 충분성: 충분

HCI·UX
관련도 81
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

## 프로토타입

- 대표 전공군 5~8개
- 실제 학과 30~50개
- 출처와 기준 연도 표시
- 대학명, 지역, 실제 학과명, 학습내용 제공

## 서비스 비전

- 전국 4년제 대학 실제 학과 Master
- 정기적인 신설·통합·폐과 갱신
- 추천 상위 학과의 공식 홈페이지 RAG

성적은 Career Profile과 전공 관련도를 변경하지 않는다.

```text
전공 관련도
= 학생 Trait와 전공 학습 활동의 관련성

지원 참고도
= 특정 연도·전형의 공개 입시자료와 입력 성적 비교
```

사용자에게는 `합격 확률` 대신 `도전·적정·안정 참고 범위`로 표시한다.

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

수치 분석       0.91
패턴 탐색       0.88
가설 검증       0.79
도구 활용       0.73
정보 표현       0.67
협업            0.42
```

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
├ search_department_rag()
├ search_high_school_subject()
└ parse_school_curriculum()
```

MCP는 외부 교육 데이터와 Agent 사이의 Typed Tool Boundary다. 단순히 로컬 함수를 MCP로 감싼 것처럼 보이지 않도록 각 Tool의 입력·출력 Schema와 출처를 명확히 한다.

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

## Long-term Demo

실제 인증 시스템 대신 Snapshot 두 개를 사용한다.

```text
demo_user_01
├ 2026_S1_Profile.json
└ 2026_S2_Profile.json
```

```text
1학기 Profile V1
→ 과목 추천
→ 2학기 Snapshot Load
→ 추가 Assessment
→ Profile V2
→ 변화 비교
```

실제 사용자별 장기 저장과 계정 격리는 후속 구현으로 둔다.

---

# 23. Knowledge Graph와 Obsidian

Obsidian은 DB나 실제 추천 엔진으로 사용하지 않는다.

> 추천 결과가 어떤 Trait·전공·학과·과목·직무와 연결됐는지 시각적으로 보여주는 발표용 Explainability View로 사용한다.

## Source of Truth

```text
PostgreSQL
```

## 발표용 Student Subgraph

전국 데이터를 모두 표시하지 않고 데모 학생과 관련된 20~30개 노드만 Export한다.

```text
Student                 1개
Core Trait              5~7개
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
Trait ─GROUPED_AS→ CareerDimension
Trait ─RELATED_TO→ CanonicalMajor
CanonicalMajor ─HAS_DEPARTMENT→ Department
Department ─BELONGS_TO→ University
CanonicalMajor ─RECOMMENDS→ HighSchoolSubject
CanonicalMajor ─RELATED_TO→ Occupation
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
LLM_MAX_CALLS_PER_SESSION=55
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
55문항 종료 성공률
평균 Latency와 호출 비용
```

## Trait Extraction

```text
허용 Ontology 매핑률
UNMAPPED_TRAIT 비율
동일 답변 재실행 일관성
Context 간 Evidence 중복 집계 여부
상충 Evidence 탐지율
```

## Major

```text
Canonical Mapping 정확도
관련도 순위의 전문가 검토 결과
Missing Trait 처리 정확성
RAG Recall@K
근거 없는 설명 비율
출처 연결 성공률
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
상충 Evidence 포함형
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
├ engines/
│  ├ evidence_engine.py
│  ├ trait_normalizer.py
│  ├ profile_vectorizer.py
│  ├ similarity_engine.py
│  ├ canonical_mapper.py
│  └ course_engine.py
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
│  └ demo_snapshots.py
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
├ data/
│  ├ trait_ontology/
│  ├ questions/
│  ├ question_frames/
│  ├ option_blueprints/
│  ├ majors/
│  ├ departments/
│  └ subjects/
└ eval/
   ├ assessment_eval.py
   ├ trait_eval.py
   ├ matching_eval.py
   ├ retrieval_eval.py
   └ end_to_end_eval.py
```

---

# 28. 수정된 구현 순서

```text
[1] 검사 정책 확정
15개 Context / 5개 선택 / 3개 공통 / 8개 꼬리
        ↓
[2] Trait Ontology와 상위 Dimension 확정
        ↓
[3] Question / Option / Evidence Schema 확정
        ↓
[4] 소형 Evaluation Set과 Persona 작성
        ↓
[5] Evidence Engine + Student Vectorizer
        ↓
[6] 공통질문 45개 + Question Frame + Option Blueprint
        ↓
[7] Assessment LangGraph + LLM Generator + Quality Gate
        ↓
[8] 대표 전공 Profile 5~8개 + Similarity Engine
        ↓
[9] 실제 학과 샘플 30~50개 + Canonical Mapping
        ↓
[10] RAG + Education MCP
        ↓
[11] 특정 학교 과목 데이터 + Course Planning
        ↓
[12] 결과 카드 UI + 상세 Evidence
        ↓
[13] Student Subgraph + Obsidian 발표 화면
        ↓
[14] 2학기 Snapshot + 전체 통합
        ↓
[15] 캐시·Fallback·발표 영상·리허설
```

Evaluation Harness는 각 단계와 동시에 확장한다.

---

# 29. 발표 시연 Flow

```text
1. 학생이 관심 Context 5개 선택
2. 공통질문을 통해 초기 Trait Evidence 확보
3. 실시간 LLM이 선택한 보기에 맞는 꼬리질문 생성
4. LangGraph State에서 Trait Vector가 갱신되는 모습 표시
5. 핵심 특징 5~8줄 결과 카드 출력
6. 전공 관련도 순위 제시
7. 추천 전공의 실제 대학 학과 탐색
8. 학교 실제 개설과목을 반영한 과목 추천
9. "왜 이런 결과가 나왔을까요?" 이후 Obsidian 전환
10. Student → Trait → Major → Department → Subject → Occupation 관계 시각화
```

발표 메시지:

> 수만 개의 질문을 미리 분기하지 않습니다. 검토된 공통질문으로 기본 Evidence를 확보한 뒤, Agent가 선택된 답변 경로에서 확인할 Trait를 결정하고 LLM이 해당 Context의 꼬리질문 하나만 실시간 생성합니다. 답변에서 추출한 수십 개의 세부 Trait와 전공·과목의 Trait Vector를 비교해 관련도를 계산하고, 학생에게는 핵심 특징 몇 줄과 추천 근거만 이해하기 쉽게 제공합니다.

---

# 30. 최종 한 문장 구조

> **LangGraph 기반 Assessment Agent가 학생 답변에 따라 실시간 꼬리질문을 생성하고, 각 답변에서 추출한 세부 Trait를 Student Multi-Vector로 누적한다. 대학 전공과 고교 과목 역시 같은 Trait 공간에 벡터화해 관련도를 계산하며, 결과는 핵심 특징 5~8줄로 요약하고 추천의 전체 연결 관계는 발표용 Obsidian Student Subgraph로 시각화한다.**
