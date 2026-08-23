# Trait Vector v2 Primary — Legacy/v2 Persona 비교 리포트

2026-08-23 Trait Ontology v2(2.6단계) §11. 각 Persona는 실제 `/assessment/*` API로 세션을 끝까지 진행한 뒤, 같은 세션(같은 evidence_ledger)에 대해 PRIMARY=false(Legacy)와 PRIMARY=true(v2)로 각각 /profile·/majors를 호출해 비교한다 — Trait Summary를 직접 주입하지 않는다.

## 분석·구조화 경향

**설계**: 원인 분석·패턴 탐색·정보 비교 계열 선택지를 일관되게 고른다.

- 세션 ID: `sess_73ad9ac723424720b24cbf509548f728`
- 실제 답변 수(evidence_ledger): 21
- Legacy 상위 Trait: causal_analysis, emotional_interpretation, information_comparison, audience_response_prediction, change_adaptation
- v2 상위 Trait: causal_analysis, emotional_interpretation, information_comparison, detail_orientation, systems_thinking
- Legacy 추천 전공: (없음 — Evidence 부족)
- v2 추천 전공: (없음 — Evidence 부족)
- Evidence 부족 여부(Legacy): 부족
- Evidence 부족 여부(v2): 부족
- 검수 미완료로 제외된 Signal 개수(v2 Primary Fail-Closed 게이트): 0
- 미해소 Explicit Conflict Trait: (없음)

**추천 차이의 근거**: Legacy는 12-Trait 범위에서만 판정하고 v2는 24-Trait 범위(신규 12개 포함)에서 판정하므로 상위 Trait 구성이 달라질 수 있다.

## 시각·사용자 관점 경향

**설계**: 시각 표현·청중 반응 예측 계열 선택지를 일관되게 고른다.

- 세션 ID: `sess_8edcf75eda3b4c9b9e5acbe58e036116`
- 실제 답변 수(evidence_ledger): 21
- Legacy 상위 Trait: audience_response_prediction, causal_analysis, emotional_interpretation, information_comparison, visual_expression
- v2 상위 Trait: audience_response_prediction, causal_analysis, emotional_interpretation, information_comparison, visual_expression
- Legacy 추천 전공: (없음 — Evidence 부족)
- v2 추천 전공: media_communication
- Evidence 부족 여부(Legacy): 부족
- Evidence 부족 여부(v2): 충분
- 검수 미완료로 제외된 Signal 개수(v2 Primary Fail-Closed 게이트): 0
- 미해소 Explicit Conflict Trait: (없음)

**추천 차이의 근거**: v2 Major Matching은 evidence confidence 가중치를 추가로 곱하고 신규 Trait까지 포함된 v2 Major Profile을 쓰므로 추천 구성이 달라질 수 있다.

## 계획·지속 경향

**설계**: 계획·완수 지속 계열 선택지를 일관되게 고른다.

- 세션 ID: `sess_21c5cc9d98764fc1b4557e746315b4d5`
- 실제 답변 수(evidence_ledger): 21
- Legacy 상위 Trait: audience_response_prediction, change_adaptation, causal_analysis, emotional_interpretation, information_comparison
- v2 상위 Trait: audience_response_prediction, change_adaptation, causal_analysis, emotional_interpretation, information_comparison
- Legacy 추천 전공: media_communication, industrial_engineering
- v2 추천 전공: media_communication, industrial_engineering
- Evidence 부족 여부(Legacy): 충분
- Evidence 부족 여부(v2): 충분
- 검수 미완료로 제외된 Signal 개수(v2 Primary Fail-Closed 게이트): 0
- 미해소 Explicit Conflict Trait: (없음)

**추천 차이의 근거**: 이번 실행에서는 Legacy/v2 결과가 관찰 가능한 차이 없이 동일했다.

## 다양한 Trait가 얕게 관찰된 경우

**설계**: 매 턴 서로 다른 Trait 선택지를 골고루 고른다(깊이 없음).

- 세션 ID: `sess_8b7b7a2601644fc3b2165d16d3d2477d`
- 실제 답변 수(evidence_ledger): 21
- Legacy 상위 Trait: audience_response_prediction, change_adaptation, causal_analysis, emotional_interpretation, information_comparison
- v2 상위 Trait: audience_response_prediction, change_adaptation, causal_analysis, emotional_interpretation, information_comparison
- Legacy 추천 전공: media_communication
- v2 추천 전공: media_communication
- Evidence 부족 여부(Legacy): 충분
- Evidence 부족 여부(v2): 충분
- 검수 미완료로 제외된 Signal 개수(v2 Primary Fail-Closed 게이트): 0
- 미해소 Explicit Conflict Trait: (없음)

**추천 차이의 근거**: 이번 실행에서는 Legacy/v2 결과가 관찰 가능한 차이 없이 동일했다.

## Evidence 부족

**설계**: 세션을 아주 짧게(1문항) 종료한다.

- 세션 ID: `sess_af91c30f2647476aab9a8efd391b99fe`
- 실제 답변 수(evidence_ledger): 1
- Legacy 상위 Trait: causal_analysis, audience_response_prediction, change_adaptation, collaboration_preference, emotional_interpretation
- v2 상위 Trait: causal_analysis, systems_thinking, aesthetic_sensitivity, audience_response_prediction, challenge_seeking
- Legacy 추천 전공: (없음 — Evidence 부족)
- v2 추천 전공: (없음 — Evidence 부족)
- Evidence 부족 여부(Legacy): 부족
- Evidence 부족 여부(v2): 부족
- 검수 미완료로 제외된 Signal 개수(v2 Primary Fail-Closed 게이트): 0
- 미해소 Explicit Conflict Trait: (없음)

**추천 차이의 근거**: Legacy는 12-Trait 범위에서만 판정하고 v2는 24-Trait 범위(신규 12개 포함)에서 판정하므로 상위 Trait 구성이 달라질 수 있다.

## Explicit Conflict

**설계**: 짝수 턴엔 planning 계열, 홀수 턴엔 immediate_execution 계열을 고른다(§12-1 사전 정의 Contrast Pair: planning_vs_execution).

- 세션 ID: `sess_664b6a8bde3b4d02b713fc7df5b6aa6c`
- 실제 답변 수(evidence_ledger): 21
- Legacy 상위 Trait: audience_response_prediction, change_adaptation, causal_analysis, emotional_interpretation, information_comparison
- v2 상위 Trait: audience_response_prediction, change_adaptation, causal_analysis, emotional_interpretation, information_comparison
- Legacy 추천 전공: media_communication, industrial_engineering
- v2 추천 전공: media_communication, industrial_engineering
- Evidence 부족 여부(Legacy): 충분
- Evidence 부족 여부(v2): 충분
- 검수 미완료로 제외된 Signal 개수(v2 Primary Fail-Closed 게이트): 0
- 미해소 Explicit Conflict Trait: (없음)

**추천 차이의 근거**: 이번 실행에서는 Legacy/v2 결과가 관찰 가능한 차이 없이 동일했다. 이번 실행에서는 Explicit Conflict가 실제로 발생하지 않았다 — planning_vs_execution Contrast는 comparable_frame_ids=['new_tool']로 제한돼 있는데, Mock 질문 생성이 매번 이 Frame을 고르지는 않아 두 역할이 '비교 가능한 Frame' 조건을 충족하지 못했다(정직하게 보고 — 결과를 지어내지 않는다).

## 검수되지 않은 Direct Probe Signal만 존재하는 경우

**설계**: ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES=true로 세션을 진행해 DRAFT Direct Probe Signal이 섞이게 한다.

- 세션 ID: `sess_a2f65c3ca88d4a2eb391f50629386a3e`
- 실제 답변 수(evidence_ledger): 22
- Legacy 상위 Trait: collaboration_preference, audience_response_prediction, causal_analysis, change_adaptation, emotional_interpretation
- v2 상위 Trait: collaboration_preference, audience_response_prediction, causal_analysis, change_adaptation, emotional_interpretation
- Legacy 추천 전공: media_communication
- v2 추천 전공: media_communication
- Evidence 부족 여부(Legacy): 충분
- Evidence 부족 여부(v2): 충분
- 검수 미완료로 제외된 Signal 개수(v2 Primary Fail-Closed 게이트): 1
- 미해소 Explicit Conflict Trait: (없음)

**추천 차이의 근거**: 이 세션에서 1개 Signal이 검수 미완료로 v2 Primary 계산에서 제외됐다(Shadow 진단에는 남아 있음).
