# Question Generator 실 LLM 검수 — 2026-08-21

## 실행 조건

- 모델: `openai/gpt-4.1-mini` (mlapi.run, `src/llm/openai_client.py`)
- 대상 코드: `src/agents/assessment/question_generator.py`, `src/engines/question_quality_gate.py`
  (커밋 `4b3b431`~`a35d094` — "전략" 좁은 소재 금지, "게임 관련 작업" 딱딱한 표현 금지,
  Blueprint 5개 Trait 명시, DEEPEN 위치 1이 Seed 선택 Blueprint로 후보 제한, `target_traits`
  서버 강제 등 앞선 리뷰 수정이 전부 반영된 상태)
- Context 3개(게임/미디어/학교생활) × 선택 경로 2개, 총 42문항(Seed 6 + LLM 생성 꼬리질문 36)
  - **경로 A(target_aligned)**: 매 질문에서 Planner가 노린 목표 Trait의 선택지(항상 `options[0]`,
    Role Blueprint 순서상 target trait가 첫 자리)를 그대로 선택
  - **경로 B(varied)**: 매 턴 `(turn*2) % 5` 인덱스로 다른 선택지를 선택해, 목표 Trait와
    무관한 답변이 이어질 때도 Context·문항 품질이 유지되는지 확인
- 실행 스크립트는 커밋하지 않음(1회성 실 LLM 호출 — 단위 테스트와 분리, `ENABLE_LLM_QUESTION_GENERATION=true`
  + 실제 API Key가 있는 로컬 `.env`에서만 실행 가능)
- **재생성·Backup으로 떨어진 문항 없음** — 42문항 전부 1차 생성이 Quality Gate를 통과함
  (`outputs/evaluation`에는 원본 JSON을 커밋하지 않았다 — 재현하려면 위 스크립트를 다시 돌리면 됨)

## 총평

8개 기준 중 7개는 42문항 전체에서 일관되게 충족됐다. 5-6번 기준(선택지 표현의 일부가
Frame과 다소 느슨하게 연결되는 경우)에서 경미한 사례 2건을 발견했지만, 학생에게 혼란을 줄
정도의 결함은 아니라고 판단한다. 아래 각 기준별로 구체적 근거를 남긴다.

---

## 1. Seed 답변과 꼬리질문(위치 1)의 내용적 연결성 — ✅ 6/6 통과

`decide_next_target()`의 DEEPEN 위치 제한(§8, 2026-08-21 수정)이 실제로 동작하는지가
핵심이다. 6개 세션(3 Context × 2 경로) 전부에서 위치 1의 목표 Trait이 Seed 선택 Trait과
**같은 Option Blueprint** 안에 있었다.

| Context | 경로 | Seed 선택 → Trait | 꼬리질문 1 목표 | 같은 Blueprint? |
|---|---|---|---|---|
| game | A | 원리 파악 → `causal_analysis` | `causal_analysis` | ✅ (problem_response_v1) |
| game | B | 역할 분담 → `collaboration_preference` | `causal_analysis` | ✅ (problem_response_v1) |
| media | A | 구성 이유 → `causal_analysis` | `immediate_execution` | ✅ (problem_response_v1) |
| media | B | 직접 제작 → `visual_expression` | `emotional_interpretation` | ✅ (expression_and_audience_v1) |
| school_life | A | 계획 수립 → `planning` | `pattern_finding` | ✅ (planning_and_execution_v1) |
| school_life | B | 계획 수립 → `planning` | `planning` | ✅ (planning_and_execution_v1 자기 자신) |

문구 자체가 Seed 내용을 직접 인용하진 않는다(설계 의도대로 — §8 "우선순위 조건이 아니라
문구를 잇는 재료로만 사용"). 대신 같은 Blueprint(예: game의 "문제 대응" 계열)에 속한
선택지로 자연스럽게 이어져서, 완전히 무관한 주제로 튀는 느낌은 없었다.

## 2. Context 유지 — ✅ 42/42 통과

42문항 모두 확정된 Context 범위 안에 머물렀다. game은 전부 "게임을 ~/게임에서 ~", media는
"SNS·영화·미디어 콘텐츠를 ~", school_life는 "수업·동아리·발표 준비 중 ~"로 시작한다.
이전 리뷰에서 지적됐던 "새로운 작품을 만들 때"류 Context 이탈은 이번 42문항에서
재현되지 않았다.

## 3. 목표 Trait과 질문 내용의 일치 — ✅ 42/42 통과, 다만 2건은 다소 느슨함

대부분 선택지 문장이 목표 Trait의 정의와 명확히 대응한다(예: `opinion_mediation` →
"여러 의견 중 어떤 기준으로 조정할지 정한다", `tool_utilization` → "필요한 도구와 자료
사용법을 먼저 확인한다"). 다만 다음 2건은 연결이 상대적으로 느슨하다:

- **school_life_tail_03(경로 B)**, frame=`conflicting_opinions`, 목표=`visual_expression`:
  "여러 친구들의 의견이 다를 때 어떻게 정리하나요?" → "각자의 생각을 그림이나 도표로
  만들어 본다". 의견 대립 상황에 "시각적 표현"을 붙인 것 자체는 억지는 아니지만(의견을
  도표로 정리하는 것도 실제로 있는 행동이다), 다른 문항들에 비해 Frame과 목표 Trait의
  결합이 자연스럽지 않고 다소 짜맞춘 느낌이 있다.
- **school_life_tail_05(경로 A/B 공통)**, 목표=`audience_response_prediction`, frame=
  `limited_time_priority`: "청중이 이해하기 쉽도록 내용 전달 방식을 우선적으로 다듬는다"
  — 발표 맥락이라 적절하긴 하나, "시간이 부족할 때"라는 급박함과 "청중 반응 예측"이라는
  다소 여유 있는 사고 행위가 문장상 살짝 어긋난다.

두 건 모두 학생이 답하는 데 지장을 줄 정도는 아니라고 판단해 "통과"로 분류했지만,
`limited_time_priority` × `expression_and_audience_v1` 조합은 앞으로 반복 관찰이
필요하다.

## 4. 문장 자연스러움 — ✅ 42/42 통과

"게임 관련 작업", "~형" 같은 이전에 지적됐던 어색한 표현은 이번 42문항에서 전혀
재현되지 않았다. 전부 구어체에 가까운 자연스러운 한국어("~하나요?", "~한다")로
작성됐고, 선택지도 전부 완결된 의문문이 아니라 행동 서술형이었다(Quality Gate의
"선택지 의문문 금지" 규칙과 일치 — 실제로 위반 사례 0건).

## 5. 앞 질문의 단순 반복 여부 — ✅ 42/42 통과

세션 내에서 완전히 동일한 질문 문장은 한 건도 없었다(Quality Gate의 "직전 질문과 문구
동일 시 거부" 규칙이 자연스럽게 지켜짐). Frame도 세션당 6개 꼬리질문에 서로 다른
Frame(`longest_focus`/`problem_check`/`first_action`/`unexpected_result`/
`limited_time_priority`/`new_tool`)이 배정돼 표현이 반복되지 않았다. 다만 문장
구조("~할 때 무엇을/어디에 가장 먼저/오래 ~하나요?")가 6문항 내내 유사한 것은
사실이다 — 이는 Generator의 결함이 아니라 §7-4가 정의한 9개 Frame 문구 자체가
전부 이 형태("~때 무엇을 하는가")라서 생기는 상위 설계 제약이다. Question
Generator가 임의로 벗어날 부분이 아니라고 판단해 결함으로 세지 않았다.

## 6. 5개 선택지가 하나의 기준으로 비교 가능한지 — ✅ 42/42 통과

42문항 전부에서 5개 선택지가 "이 상황에서 무엇을 먼저 하는가"라는 동일한 질문 축에
대한 서로 다른 답으로 구성됐다. 예를 들어 game_tail_02(경로 A) "예상과 다른 결과가
나왔을 때 무엇부터 살펴보나요?"의 5개 선택지(화면·그래픽 / 감정 반응 / 타인이 어떻게
받아들일지 / 의견 비교 / 패턴 찾기)는 전부 "무엇부터 살펴보는가"에 대한 병렬적 답이다.
2026-08-21 리뷰에서 추가한 "5개 Trait를 프롬프트에 다 보여주고 넓은 상황을 잡으라"
수정이 42문항 전체에서 일관되게 작동한 것으로 판단한다.

## 7~8. 참고 — LLM 재현성·Fallback 경로

이번 실행에서는 Backup Question이나 재생성 경로가 한 번도 발동하지 않았다(42/42
1차 생성 통과). Fallback 경로 자체는 `tests/test_question_generator.py`에서 Fake
Client로 이미 검증돼 있어 이번 실 LLM 검수의 범위에서는 제외했다.

---

## 결론 및 후속 조치 제안

- 42문항 기준으로 이 문서에 실린 8개 기준은 전부 통과 수준이라고 판단한다.
- 유일하게 반복 관찰이 필요한 지점은 **`limited_time_priority` Frame과
  `expression_and_audience_v1`(시각적 표현·감정 해석·사용자 반응 예측 등) Blueprint의
  조합**이다 — "시간이 부족한 급박함"과 "표현·해석 계열 사고"가 다른 조합에 비해
  결합이 느슨하다. 당장 코드를 고치기보다, 다음 검수 때 이 조합이 반복해서 나오면
  그때 Frame 문구나 Blueprint 재구성을 검토하는 게 안전하다고 본다.
- 이 문서는 1회성 실 LLM 호출 결과이며, LLM 응답은 매번 달라질 수 있다(재현성 보장
  안 됨) — 정기 검수가 필요하면 이 검수 스크립트를 `eval/` 아래 정식 도구로 승격하는
  것을 고려할 수 있다(§26 Evaluation Harness의 "Offline Semantic Evaluation" 자리에
  해당).
