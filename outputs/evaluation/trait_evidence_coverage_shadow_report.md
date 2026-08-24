# Trait Evidence Coverage — 실제 4+1/2+1 세션 시뮬레이션 보고서

브랜치 `a/trait-evidence-coverage-shadow`. **이 문서가 주 보고서다** — 이전
라운드의 158문항/52~56문항 권고는 실제 세션이 아니었다(정정 지시 §7). 그
수치는 `trait_evidence_coverage_inventory_ceiling_report.md`로 이름을 바꿔
참고 자료로만 남겼다.

## 0. 이전 권고를 어떻게 정정했는가

- 이전 환경 A/B는 15개 Context와 각 Context의 Anchor 5개 전부를 순회한 뒤
  "질문 수 상한별 SUFFICIENT 개수"를 쟀다 — 한 세션이 실제로 겪는 경로가
  아니었다.
- 이번 라운드는 실제 `src.api.main`의 Endpoint 함수(`submit_interest_rating`/
  `select_contexts`/`confirm_contexts`/`next_question`/`submit_answer`)를
  그대로 호출해서, Context마다 Anchor 정확히 1개·Seed 1개·Adaptive Tail
  4~6개만 쓰는 진짜 세션 하나를 재현한다.
- "최소 52·최대 56"이라는 이전 권고는 폐기한다 — 아래 §7이 실제 세션 기준
  숫자로 대체한다.

## 1. 환경 A — 실제 3 Context, 2+1 세션 (Persona별 질문 수)

| Persona | Trait 질문 | Routing | Backup 사용 | UNOBS·LIM·SUP·SUFF·CONF | 상위5 | 상위8 |
|---|---|---|---|---|---|---|
| 분석형 | 24 | 3 | 0 | 19·3·0·2·0 | ❌ | ❌ |
| 창의·시각형 | 23 | 3 | 0 | 17·4·0·3·0 | ❌ | ❌ |
| 사회·협업형 | 23 | 3 | 0 | 20·2·0·2·0 | ❌ | ❌ |
| 실행·제작형 | 23 | 3 | 0 | 18·3·0·3·0 | ❌ | ❌ |
| 언어·인문형 | 24 | 3 | 0 | 19·2·0·3·0 | ❌ | ❌ |
| 혼합·교차형 | 23 | 3 | 0 | 19·3·0·2·0 | ❌ | ❌ |
| 니치 관심형 | 23 | 3 | 0 | 19·3·0·2·0 | ❌ | ❌ |
| Coverage 최대화형 | 25 | 3 | 0 | 7·14·3·0·0 | ❌ | ❌ |
| Coverage 최소화형(1~2개 Trait 집중) | 24 | 3 | 0 | 18·4·0·2·0 | ❌ | ❌ |

## 2. 환경 B — 실제 15 Context, 4+1 세션 (Persona별 질문 수)

| Persona | Trait 질문 | Routing | Backup 사용 | UNOBS·LIM·SUP·SUFF·CONF | 상위5 | 상위8 |
|---|---|---|---|---|---|---|
| 분석형 | 35 | 5 | 0 | 22·2·0·0·0 | ❌ | ❌ |
| 창의·시각형 | 35 | 5 | 0 | 20·2·2·0·0 | ❌ | ❌ |
| 사회·협업형 | 35 | 5 | 0 | 20·2·0·2·0 | ❌ | ❌ |
| 실행·제작형 | 35 | 5 | 0 | 23·1·0·0·0 | ❌ | ❌ |
| 언어·인문형 | 35 | 5 | 0 | 19·3·0·2·0 | ❌ | ❌ |
| 혼합·교차형 | 35 | 5 | 0 | 21·1·1·1·0 | ❌ | ❌ |
| 니치 관심형 | 35 | 5 | 0 | 24·0·0·0·0 | ❌ | ❌ |
| Coverage 최대화형 | 35 | 5 | 0 | 6·14·4·0·0 | ❌ | ❌ |
| Coverage 최소화형(1~2개 Trait 집중) | 35 | 5 | 0 | 18·4·0·2·0 | ❌ | ❌ |

## 3. 20/25/30/35문항 Checkpoint (환경 B, Persona별)

### 분석형 — Context ['science', 'business', 'sports', 'law_politics', 'making']

Anchor: {'business': 'feedback_reading', 'law_politics': 'differing_claims', 'making': 'assembling', 'science': 'cause_exploring', 'sports': 'individual_training'}

| 질문 수 Checkpoint | UNOBSERVED·LIMITED·SUPPORTED·SUFFICIENT·CONFLICTED |
|---|---|
| 20 | 22·2·0·0·0 |
| 25 | 22·2·0·0·0 |
| 30 | 22·2·0·0·0 |
| 35 | 22·2·0·0·0 |
| 35(전체) | 22·2·0·0·0 |

- 구조적으로 SUFFICIENT 불가능(Context 2개 미달): aesthetic_sensitivity, audience_response_prediction, challenge_seeking, change_adaptation, collaboration_preference, creative_ideation, emotional_interpretation, immediate_execution, independent_judgment, novelty_seeking, opinion_expression, opinion_mediation, persistence_completion, personal_goal_priority, planning, systems_thinking, tool_utilization, uncertainty_tolerance, verbal_expression, visual_expression
- 질문 Mapping 부족(승인된 기회<2): aesthetic_sensitivity, audience_response_prediction, challenge_seeking, change_adaptation, collaboration_preference, creative_ideation, emotional_interpretation, immediate_execution, independent_judgment, novelty_seeking, opinion_expression, opinion_mediation, persistence_completion, personal_goal_priority, planning, systems_thinking, tool_utilization, uncertainty_tolerance, verbal_expression, visual_expression
- Context 선택 때문에 관찰 자체가 없는 Trait: aesthetic_sensitivity, audience_response_prediction, challenge_seeking, change_adaptation, collaboration_preference, creative_ideation, emotional_interpretation, immediate_execution, novelty_seeking, opinion_expression, opinion_mediation, persistence_completion, personal_goal_priority, planning, systems_thinking, tool_utilization, uncertainty_tolerance, verbal_expression, visual_expression

### 창의·시각형 — Context ['art_design', 'media', 'fashion_beauty', 'making', 'writing']

Anchor: {'art_design': 'direct_creation', 'fashion_beauty': 'expression_choice', 'making': 'assembling', 'media': 'animation_webcontent', 'writing': 'expression_style'}

| 질문 수 Checkpoint | UNOBSERVED·LIMITED·SUPPORTED·SUFFICIENT·CONFLICTED |
|---|---|
| 20 | 20·2·2·0·0 |
| 25 | 20·2·2·0·0 |
| 30 | 20·2·2·0·0 |
| 35 | 20·2·2·0·0 |
| 35(전체) | 20·2·2·0·0 |

- 구조적으로 SUFFICIENT 불가능(Context 2개 미달): aesthetic_sensitivity, audience_response_prediction, causal_analysis, challenge_seeking, change_adaptation, collaboration_preference, creative_ideation, emotional_interpretation, immediate_execution, information_comparison, novelty_seeking, opinion_expression, opinion_mediation, pattern_finding, persistence_completion, personal_goal_priority, planning, systems_thinking, tool_utilization, uncertainty_tolerance, verbal_expression
- 질문 Mapping 부족(승인된 기회<2): audience_response_prediction, challenge_seeking, change_adaptation, collaboration_preference, creative_ideation, emotional_interpretation, immediate_execution, information_comparison, novelty_seeking, opinion_expression, opinion_mediation, pattern_finding, persistence_completion, personal_goal_priority, planning, tool_utilization, uncertainty_tolerance, verbal_expression
- Context 선택 때문에 관찰 자체가 없는 Trait: audience_response_prediction, challenge_seeking, collaboration_preference, creative_ideation, emotional_interpretation, immediate_execution, information_comparison, novelty_seeking, opinion_expression, opinion_mediation, pattern_finding, persistence_completion, personal_goal_priority, planning, tool_utilization, uncertainty_tolerance, verbal_expression

### 사회·협업형 — Context ['school_life', 'volunteer', 'sports', 'business', 'game']

Anchor: {'business': 'feedback_reading', 'game': 'building_creation', 'school_life': 'academic_study', 'sports': 'individual_training', 'volunteer': 'cause_selection'}

| 질문 수 Checkpoint | UNOBSERVED·LIMITED·SUPPORTED·SUFFICIENT·CONFLICTED |
|---|---|
| 20 | 20·2·2·0·0 |
| 25 | 20·2·2·0·0 |
| 30 | 20·2·1·1·0 |
| 35 | 20·2·0·2·0 |
| 35(전체) | 20·2·0·2·0 |

- 구조적으로 SUFFICIENT 불가능(Context 2개 미달): aesthetic_sensitivity, audience_response_prediction, causal_analysis, challenge_seeking, change_adaptation, emotional_interpretation, immediate_execution, independent_judgment, information_comparison, novelty_seeking, pattern_finding, persistence_completion, personal_goal_priority, planning, systems_thinking, tool_utilization, uncertainty_tolerance, verbal_expression, visual_expression
- 질문 Mapping 부족(승인된 기회<2): aesthetic_sensitivity, audience_response_prediction, causal_analysis, challenge_seeking, change_adaptation, emotional_interpretation, immediate_execution, independent_judgment, information_comparison, novelty_seeking, pattern_finding, persistence_completion, personal_goal_priority, planning, systems_thinking, tool_utilization, uncertainty_tolerance, verbal_expression, visual_expression
- Context 선택 때문에 관찰 자체가 없는 Trait: aesthetic_sensitivity, audience_response_prediction, causal_analysis, challenge_seeking, emotional_interpretation, independent_judgment, information_comparison, novelty_seeking, pattern_finding, persistence_completion, personal_goal_priority, planning, systems_thinking, tool_utilization, uncertainty_tolerance, verbal_expression, visual_expression

### 실행·제작형 — Context ['making', 'cooking', 'science', 'art_design', 'business']

Anchor: {'art_design': 'direct_creation', 'business': 'feedback_reading', 'cooking': 'food_choice', 'making': 'assembling', 'science': 'cause_exploring'}

| 질문 수 Checkpoint | UNOBSERVED·LIMITED·SUPPORTED·SUFFICIENT·CONFLICTED |
|---|---|
| 20 | 23·1·0·0·0 |
| 25 | 23·1·0·0·0 |
| 30 | 23·1·0·0·0 |
| 35 | 23·1·0·0·0 |
| 35(전체) | 23·1·0·0·0 |

- 구조적으로 SUFFICIENT 불가능(Context 2개 미달): aesthetic_sensitivity, audience_response_prediction, causal_analysis, challenge_seeking, change_adaptation, creative_ideation, emotional_interpretation, information_comparison, novelty_seeking, opinion_expression, opinion_mediation, pattern_finding, persistence_completion, personal_goal_priority, planning, systems_thinking, tool_utilization, uncertainty_tolerance, verbal_expression, visual_expression
- 질문 Mapping 부족(승인된 기회<2): aesthetic_sensitivity, audience_response_prediction, causal_analysis, challenge_seeking, change_adaptation, creative_ideation, emotional_interpretation, information_comparison, novelty_seeking, opinion_expression, opinion_mediation, pattern_finding, persistence_completion, personal_goal_priority, planning, systems_thinking, tool_utilization, uncertainty_tolerance, verbal_expression, visual_expression
- Context 선택 때문에 관찰 자체가 없는 Trait: aesthetic_sensitivity, challenge_seeking, change_adaptation, creative_ideation, emotional_interpretation, information_comparison, novelty_seeking, opinion_expression, opinion_mediation, pattern_finding, personal_goal_priority, planning, systems_thinking, tool_utilization, uncertainty_tolerance, verbal_expression, visual_expression

### 언어·인문형 — Context ['writing', 'history_humanities', 'law_politics', 'media', 'school_life']

Anchor: {'history_humanities': 'cause_effect_chain', 'law_politics': 'differing_claims', 'media': 'animation_webcontent', 'school_life': 'academic_study', 'writing': 'expression_style'}

| 질문 수 Checkpoint | UNOBSERVED·LIMITED·SUPPORTED·SUFFICIENT·CONFLICTED |
|---|---|
| 20 | 24·0·0·0·0 |
| 25 | 21·2·1·0·0 |
| 30 | 21·1·1·1·0 |
| 35 | 19·3·0·2·0 |
| 35(전체) | 19·3·0·2·0 |

- 구조적으로 SUFFICIENT 불가능(Context 2개 미달): aesthetic_sensitivity, audience_response_prediction, causal_analysis, challenge_seeking, change_adaptation, collaboration_preference, immediate_execution, independent_judgment, novelty_seeking, opinion_mediation, pattern_finding, persistence_completion, personal_goal_priority, planning, systems_thinking, tool_utilization, uncertainty_tolerance, verbal_expression, visual_expression
- 질문 Mapping 부족(승인된 기회<2): aesthetic_sensitivity, audience_response_prediction, causal_analysis, challenge_seeking, change_adaptation, collaboration_preference, immediate_execution, independent_judgment, novelty_seeking, opinion_mediation, pattern_finding, persistence_completion, personal_goal_priority, planning, systems_thinking, tool_utilization, uncertainty_tolerance, verbal_expression, visual_expression
- Context 선택 때문에 관찰 자체가 없는 Trait: aesthetic_sensitivity, audience_response_prediction, challenge_seeking, change_adaptation, collaboration_preference, immediate_execution, independent_judgment, novelty_seeking, opinion_mediation, pattern_finding, persistence_completion, personal_goal_priority, planning, tool_utilization, uncertainty_tolerance, visual_expression

### 혼합·교차형 — Context ['game', 'cooking', 'law_politics', 'art_design', 'science']

Anchor: {'art_design': 'direct_creation', 'cooking': 'food_choice', 'game': 'building_creation', 'law_politics': 'differing_claims', 'science': 'cause_exploring'}

| 질문 수 Checkpoint | UNOBSERVED·LIMITED·SUPPORTED·SUFFICIENT·CONFLICTED |
|---|---|
| 20 | 21·1·2·0·0 |
| 25 | 21·1·2·0·0 |
| 30 | 21·1·1·1·0 |
| 35 | 21·1·1·1·0 |
| 35(전체) | 21·1·1·1·0 |

- 구조적으로 SUFFICIENT 불가능(Context 2개 미달): aesthetic_sensitivity, audience_response_prediction, challenge_seeking, change_adaptation, immediate_execution, information_comparison, novelty_seeking, opinion_expression, opinion_mediation, pattern_finding, persistence_completion, personal_goal_priority, planning, systems_thinking, tool_utilization, uncertainty_tolerance, verbal_expression, visual_expression
- 질문 Mapping 부족(승인된 기회<2): aesthetic_sensitivity, challenge_seeking, change_adaptation, immediate_execution, information_comparison, novelty_seeking, opinion_expression, opinion_mediation, pattern_finding, persistence_completion, personal_goal_priority, planning, tool_utilization, uncertainty_tolerance, verbal_expression, visual_expression
- Context 선택 때문에 관찰 자체가 없는 Trait: aesthetic_sensitivity, challenge_seeking, change_adaptation, immediate_execution, information_comparison, novelty_seeking, opinion_expression, opinion_mediation, pattern_finding, persistence_completion, personal_goal_priority, planning, tool_utilization, uncertainty_tolerance, verbal_expression, visual_expression

### 니치 관심형 — Context ['fashion_beauty', 'travel', 'cooking', 'art_design', 'making']

Anchor: {'art_design': 'direct_creation', 'cooking': 'food_choice', 'fashion_beauty': 'expression_choice', 'making': 'assembling', 'travel': 'companion_opinion'}

| 질문 수 Checkpoint | UNOBSERVED·LIMITED·SUPPORTED·SUFFICIENT·CONFLICTED |
|---|---|
| 20 | 24·0·0·0·0 |
| 25 | 24·0·0·0·0 |
| 30 | 24·0·0·0·0 |
| 35 | 24·0·0·0·0 |
| 35(전체) | 24·0·0·0·0 |

- 구조적으로 SUFFICIENT 불가능(Context 2개 미달): aesthetic_sensitivity, audience_response_prediction, causal_analysis, challenge_seeking, change_adaptation, immediate_execution, information_comparison, opinion_expression, opinion_mediation, pattern_finding, persistence_completion, personal_goal_priority, planning, systems_thinking, tool_utilization, uncertainty_tolerance, verbal_expression, visual_expression
- 질문 Mapping 부족(승인된 기회<2): aesthetic_sensitivity, audience_response_prediction, causal_analysis, challenge_seeking, change_adaptation, immediate_execution, information_comparison, opinion_expression, opinion_mediation, pattern_finding, persistence_completion, personal_goal_priority, planning, systems_thinking, tool_utilization, uncertainty_tolerance, verbal_expression, visual_expression
- Context 선택 때문에 관찰 자체가 없는 Trait: aesthetic_sensitivity, audience_response_prediction, causal_analysis, challenge_seeking, immediate_execution, information_comparison, opinion_expression, opinion_mediation, pattern_finding, persistence_completion, planning, systems_thinking, tool_utilization, uncertainty_tolerance, verbal_expression, visual_expression

### Coverage 최대화형 — Context ['science', 'media', 'school_life', 'business', 'making']

Anchor: {'business': 'feedback_reading', 'making': 'assembling', 'media': 'animation_webcontent', 'school_life': 'academic_study', 'science': 'cause_exploring'}

| 질문 수 Checkpoint | UNOBSERVED·LIMITED·SUPPORTED·SUFFICIENT·CONFLICTED |
|---|---|
| 20 | 8·12·4·0·0 |
| 25 | 6·14·4·0·0 |
| 30 | 6·14·4·0·0 |
| 35 | 6·14·4·0·0 |
| 35(전체) | 6·14·4·0·0 |

- 구조적으로 SUFFICIENT 불가능(Context 2개 미달): aesthetic_sensitivity, challenge_seeking, emotional_interpretation, opinion_mediation, personal_goal_priority, systems_thinking, tool_utilization, verbal_expression, visual_expression
- 질문 Mapping 부족(승인된 기회<2): aesthetic_sensitivity, challenge_seeking, emotional_interpretation, opinion_mediation, personal_goal_priority, tool_utilization, verbal_expression, visual_expression
- Context 선택 때문에 관찰 자체가 없는 Trait: challenge_seeking, personal_goal_priority, verbal_expression

### Coverage 최소화형(1~2개 Trait 집중) — Context ['game', 'media', 'school_life', 'business', 'science']

Anchor: {'business': 'feedback_reading', 'game': 'building_creation', 'media': 'animation_webcontent', 'school_life': 'academic_study', 'science': 'cause_exploring'}

| 질문 수 Checkpoint | UNOBSERVED·LIMITED·SUPPORTED·SUFFICIENT·CONFLICTED |
|---|---|
| 20 | 18·4·0·2·0 |
| 25 | 18·4·0·2·0 |
| 30 | 18·4·0·2·0 |
| 35 | 18·4·0·2·0 |
| 35(전체) | 18·4·0·2·0 |

- 구조적으로 SUFFICIENT 불가능(Context 2개 미달): audience_response_prediction, challenge_seeking, change_adaptation, collaboration_preference, emotional_interpretation, immediate_execution, information_comparison, novelty_seeking, opinion_mediation, pattern_finding, persistence_completion, personal_goal_priority, planning, tool_utilization, uncertainty_tolerance, verbal_expression
- 질문 Mapping 부족(승인된 기회<2): audience_response_prediction, challenge_seeking, change_adaptation, collaboration_preference, emotional_interpretation, immediate_execution, information_comparison, novelty_seeking, opinion_mediation, pattern_finding, persistence_completion, personal_goal_priority, planning, tool_utilization, uncertainty_tolerance, verbal_expression
- Context 선택 때문에 관찰 자체가 없는 Trait: audience_response_prediction, challenge_seeking, change_adaptation, collaboration_preference, emotional_interpretation, immediate_execution, information_comparison, novelty_seeking, opinion_mediation, pattern_finding, personal_goal_priority, tool_utilization, uncertainty_tolerance, verbal_expression


## 4. 상위 5·8개 Trait 충족 여부 요약

- 상위 5개 전부 SUFFICIENT인 Persona: 0/9(환경 B 기준)
- 상위 8개 전부 SUFFICIENT인 Persona: 0/9(환경 B 기준)

## 5. 구조적으로 불가능한 Trait

**Coverage 최대화형(의도적으로 Context를 넓히려 한 Persona) 기준**: aesthetic_sensitivity, challenge_seeking, emotional_interpretation, opinion_mediation, personal_goal_priority, systems_thinking, tool_utilization, verbal_expression, visual_expression

참고 — 환경 B 9개 Persona **전부**에서 Context 2개 조건을 못 채운 Trait(교집합, 더 보수적인 기준): challenge_seeking, personal_goal_priority, tool_utilization, verbal_expression

## 6. 현재 기준을 Runtime에 연결해도 되는가

**결론: B** — 9개 Persona 중 상위 5개 Trait가 전부 SUFFICIENT에 도달한 경우는 0건뿐이다 (상위 8개는 0건). 실제 4+1 세션(35문항 상한) 안에서는 현재 구조로 Coverage 기반 종료 조건을 충족하기 어렵다.

**원인.** 네 가지 후보(질문 Mapping 부족/Context 2개 조건 과도/RELATED 가중치 과소/4+1 Context 수 부족) 중 어느 하나로 깔끔히 떨어지지 않는다 — 실측 결과 더 구체적인 원인은 **실제 Adaptive Target Planner(`select_pack_adaptive_target`, 수정 금지)가 'Evidence 부족(Gap)' 판정을 `support_count>=2`에서 멈춘다**는 것이다. 한 Trait가 Primary 2개(서로 다른 Context 포함)를 얻으면 그 Trait는 더 이상 'Gap'이 아니라고 보고 Planner가 다른 Trait로 넘어간다. 그런데 이번 Coverage Policy의 SUFFICIENT는 Primary 2개만으로는 가중치가 정확히 2.0이라 3.0 문턱을 못 넘는다(§ 아래 실측 사례) — **Primary 2개를 요구하는 조건과 가중치 3.0을 요구하는 조건이 서로 다른 것을 요구한다**(실질적으로 가중치 조건이 더 엄격해 Primary 3개 또는 Primary 2개+RELATED 2개 이상이 필요하다). 이건 Persona의 답변 선택 정책 문제가 아니다 — Pack Context Direct Probe 질문은 5개 선택지 중 목표 Trait에 신호가 있는 선택지가 정확히 1개뿐이라 (나머지 4개는 NO_SIGNAL), Persona가 무엇을 고르든 선택의 여지가 사실상 없다.

**구체 사례.** 환경 B `coverage_maximizing` Persona: causal_analysis가 서로 다른 Context 2곳에서 Primary 2개(가중치 2.0)를 얻어 Frame·Context 조건은 통과했지만, SUFFICIENT의 '가중치 3.0 이상' 조건 하나만 미충족으로 SUPPORTED에 머물렀다(missing_requirements: 'effective_evidence_weight>=3.0 미충족(현재 2.0)'만 남고 나머지 조건은 전부 충족).

## 7. 전체 Inventory 상한과 실제 세션 결과 차이

| | 전체 Inventory 상한(참고용, 실제 세션 아님) | 실제 세션(이 보고서) |
|---|---|---|
| 환경 A 최대 질문 수 | 38(고정 콘텐츠 전부) | 25(2+1, 3 Context) |
| 환경 B 최대 질문 수 | 158(15 Context×Anchor 5개 전부) | 35(4+1, 5 Context) |
| 환경 B SUFFICIENT(최선) | 23/24(전체 158문항 다 씀) | 2/24(35문항 상한) |

실제 세션은 한 Context에서 Anchor 1개만 쓰고 Tail도 4~6개로 끝나므로, Inventory
상한의 '몇 번째 문항에서 충분해지는가'라는 숫자를 실제 세션 권장치로 쓸 수 없다.

## 8. 설계 결정과 한계

- LLM은 네트워크를 호출하지 않는 결정론적 Fake Client로 대체했다(§ 위 flow 설명).
  실측 결과 Fake조차 없이 LLM을 끄면 Pack Context Adaptive Tail이 매번 즉시
  Backup으로 빠져 최소 4개도 못 채운다 — 실제 LLM이 붙으면 결과가 달라질 수
  있다(이 진단은 그 차이를 재현하지 않는다).
- 환경 B의 "4+1"은 실제 `/assessment/context-select` Endpoint로 만들 수 없다
  (2/3으로 하드코딩됨, main.py 수정 금지) — 그 Endpoint가 쓰는 순수 함수를
  직접 호출해 우회했다(§ 위 flow 설명).
- Anchor는 모든 Context에서 '알파벳 순 첫 Anchor'로 결정론적으로 골랐다 —
  Persona 주제에 맞는 Anchor를 수작업으로 고르지 않았다(알려진 단순화).
- Pack Context Direct Probe 질문은 선택지 5개 중 신호가 있는 게 1개뿐이라,
  Persona의 답변 선택 정책이 Pack Context에서는 사실상 영향이 없다 — 실제
  영향은 Legacy Tail·Seed·Routing(Anchor) 선택에서만 나타난다.
- 12개 ContextPack·공용 Adaptive Probe 승인은 전부 tempfile Fixture다.
  `data/reviews/`는 이 스크립트 실행 전후로 바이트 하나도 바뀌지 않는다.
