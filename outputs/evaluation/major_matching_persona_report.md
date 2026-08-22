# 고정 Persona 매칭 진단 리포트

이 리포트는 `src/engines/matching_engine.py`의 매칭 공식을 **수정하지 않고 있는 그대로 호출**한 결과를 기록한다. 2026-08-22 12차 리뷰로 대표 전공 3개의 Trait Vector가 실제 학과 공식 자료 근거로 바뀐 뒤, 고정 Persona 7개에 대해 각 전공이 computed/insufficient 중 어느 쪽인지, 동점이 발생하는지를 사실 그대로 관찰한다. 결과를 원하는 방향으로 만들기 위해 Persona나 가중치를 거꾸로 조정하지 않았다.

재현 방법: `PYTHONPATH=. python scripts/career_generate_major_matching_persona_report.py` — 같은 입력(Vertical Slice MajorProfile 3개 + 아래 Persona 정의)이면 항상 같은 리포트가 나온다(결정론적, LLM 호출 없음).

## 대표 전공 Trait Vector (참고용, 매칭 공식이 실제로 읽는 값)

- **media_communication**(미디어·커뮤니케이션): visual_expression=0.67, causal_analysis=0.67, pattern_finding=1.0, audience_response_prediction=1.0, information_comparison=0.67, planning=1.0, collaboration_preference=1.0, tool_utilization=0.67
- **hci_ux**(HCI·UX): visual_expression=0.67, audience_response_prediction=1.0, tool_utilization=0.67
- **industrial_engineering**(산업공학): causal_analysis=1.0, pattern_finding=0.67, information_comparison=1.0, planning=1.0, tool_utilization=0.67

## Persona별 결과

### analytical — 분석·구조화 중심

**설계 근거**: 원인 분석·패턴 탐색·정보 비교·계획을 반복적으로 강하게 드러내는 학생. industrial_engineering이 1.0 근처 가중치를 두는 Trait 조합과 그대로 겹친다.

- STRONG 입력: ['causal_analysis', 'information_comparison', 'pattern_finding', 'planning']

| major_id | status | score | usable_trait_count | usable_vector_group_count | evidence_sufficiency | relevance_label |
|---|---|---|---|---|---|---|
| media_communication | computed | 1.0000 | 4 | 2 | 충분 | 관련성 높음 |
| hci_ux | insufficient | — | 0 | 0 | — | — |
| industrial_engineering | computed | 1.0000 | 4 | 2 | 충분 | 관련성 높음 |

- 관련성 높음 전공: ['industrial_engineering', 'media_communication']
- 공동 1위(동점) 여부: 예

### visual_user_facing — 시각·사용자 관점 중심

**설계 근거**: 시각적 표현·수용자 반응 예측·도구 활용을 강하게 드러내고 그 외에는 답변이 없는 학생. 이 3개 Trait는 hci_ux Vector 전체와 정확히 일치하고, media_communication Vector에도 '동일한 가중치'로 포함돼 있어 두 전공이 동점을 낼 조건을 그대로 만든다.

- STRONG 입력: ['audience_response_prediction', 'tool_utilization', 'visual_expression']

| major_id | status | score | usable_trait_count | usable_vector_group_count | evidence_sufficiency | relevance_label |
|---|---|---|---|---|---|---|
| media_communication | computed | 1.0000 | 3 | 3 | 충분 | 관련성 높음 |
| hci_ux | computed | 1.0000 | 3 | 3 | 충분 | 관련성 높음 |
| industrial_engineering | insufficient | — | 1 | 1 | — | — |

- 관련성 높음 전공: ['hci_ux', 'media_communication']
- 공동 1위(동점) 여부: 예

### planning_collaboration — 계획·협업 중심

**설계 근거**: 계획·협업 선호·의견 조정을 강하게 드러내는 학생. opinion_mediation은 세 대표 전공 Vector 어디에도 없는 Trait라 매칭에는 반영되지 않고, planning·collaboration_preference만 실제로 반영된다 — 다만 이 둘은 media_communication Vector에서 모두 work_style 그룹 하나에 몰려 있어(usable_trait_count=2), MINIMUM_USABLE_TRAITS(3) 미달로 insufficient가 나올 가능성이 있다. '전공에 유리한 Trait를 답했는데도 관련도를 계산 못하는' 경계 사례를 보여주는 대조군이다.

- STRONG 입력: ['collaboration_preference', 'opinion_mediation', 'planning']

| major_id | status | score | usable_trait_count | usable_vector_group_count | evidence_sufficiency | relevance_label |
|---|---|---|---|---|---|---|
| media_communication | insufficient | — | 2 | 1 | — | — |
| hci_ux | insufficient | — | 0 | 0 | — | — |
| industrial_engineering | insufficient | — | 1 | 1 | — | — |

- 관련성 높음 전공: 없음
- 공동 1위(동점) 여부: 아니오
- 전체 안내 메시지: 아직 관련도를 계산하기에 답변이 부족합니다. 추가 탐색이 필요합니다.

### tool_only — 도구 활용 중심

**설계 근거**: 도구 활용 하나만 강하게 관찰되고 그 외에는 전혀 확인되지 않은 학생. Trait 1개로는 MINIMUM_USABLE_TRAITS(3) 요건을 어느 전공도 못 채워 insufficient가 나올 것으로 예상된다 — '근거 부족'과 '매칭 공식 결함'을 구분하는 대조군.

- STRONG 입력: ['tool_utilization']

| major_id | status | score | usable_trait_count | usable_vector_group_count | evidence_sufficiency | relevance_label |
|---|---|---|---|---|---|---|
| media_communication | insufficient | — | 1 | 1 | — | — |
| hci_ux | insufficient | — | 1 | 1 | — | — |
| industrial_engineering | insufficient | — | 1 | 1 | — | — |

- 관련성 높음 전공: 없음
- 공동 1위(동점) 여부: 아니오
- 전체 안내 메시지: 아직 관련도를 계산하기에 답변이 부족합니다. 추가 탐색이 필요합니다.

### all_limited — 전체 Trait가 LIMITED인 학생

**설계 근거**: 12개 Trait 전부가 LIMITED(약한 근거)로만 관찰된 학생. 가중 충족도는 값이 전부 같으면 가중치 분포와 무관하게 동일한 결과가 나오므로(가중평균 성질), 세 전공이 전부 같은 낮은 점수로 나올 것으로 예상된다.

- LIMITED 입력: ['audience_response_prediction', 'causal_analysis', 'change_adaptation', 'collaboration_preference', 'emotional_interpretation', 'immediate_execution', 'information_comparison', 'opinion_mediation', 'pattern_finding', 'planning', 'tool_utilization', 'visual_expression']

| major_id | status | score | usable_trait_count | usable_vector_group_count | evidence_sufficiency | relevance_label |
|---|---|---|---|---|---|---|
| media_communication | computed | 0.3300 | 8 | 4 | 보통 | 함께 탐색해볼 분야 |
| hci_ux | computed | 0.3300 | 3 | 3 | 보통 | 함께 탐색해볼 분야 |
| industrial_engineering | computed | 0.3300 | 5 | 3 | 보통 | 함께 탐색해볼 분야 |

- 관련성 높음 전공: 없음
- 공동 1위(동점) 여부: 예

### sparse_partial — 일부 Trait만 충분히 관찰된 학생

**설계 근거**: 12개 중 단 2개(causal_analysis STRONG, tool_utilization LIMITED)만 관찰되고 나머지는 전혀 답변 기회가 없었던 학생. 초반 몇 문항만 답한 상태를 흉내낸다 — usable_trait_count가 낮아 insufficient가 나오는 게 정상인지 확인하는 대조군.

- STRONG 입력: ['causal_analysis']
- LIMITED 입력: ['tool_utilization']

| major_id | status | score | usable_trait_count | usable_vector_group_count | evidence_sufficiency | relevance_label |
|---|---|---|---|---|---|---|
| media_communication | insufficient | — | 2 | 2 | — | — |
| hci_ux | insufficient | — | 1 | 1 | — | — |
| industrial_engineering | insufficient | — | 2 | 2 | — | — |

- 관련성 높음 전공: 없음
- 공동 1위(동점) 여부: 아니오
- 전체 안내 메시지: 아직 관련도를 계산하기에 답변이 부족합니다. 추가 탐색이 필요합니다.

### unresolved_conflict — Conflict가 해결되지 않은 학생

**설계 근거**: 분석형 학생과 같은 답변 패턴이지만, planning(=planning_vs_execution Contrast의 한 축)이 아직 해결되지 않은 EXPLICIT_CONFLICT 상태라고 가정한다. judge_trait_state 3순위 규칙에 따라 planning은 CONFLICTING으로 Mask돼 어느 전공 비교에도 안 들어가야 한다(0점 취급이 아니라 완전 제외) — §12 '0점과 다르다'를 Persona 단위로 재확인.

- STRONG 입력: ['causal_analysis', 'information_comparison', 'pattern_finding', 'planning']
- 미해결 Conflict(CONFLICTING Mask) 입력: ['planning']

| major_id | status | score | usable_trait_count | usable_vector_group_count | evidence_sufficiency | relevance_label |
|---|---|---|---|---|---|---|
| media_communication | insufficient | — | 3 | 1 | — | — |
| hci_ux | insufficient | — | 0 | 0 | — | — |
| industrial_engineering | insufficient | — | 3 | 1 | — | — |

- 관련성 높음 전공: 없음
- 공동 1위(동점) 여부: 아니오
- 전체 안내 메시지: 아직 관련도를 계산하기에 답변이 부족합니다. 추가 탐색이 필요합니다.

## 관찰된 현상 분류

### 1. 정상적인 복수 전공 추천
- `all_limited` Persona: 12개 Trait 전부 LIMITED(0.33)로만 관찰되면 세 전공 모두 `computed`이지만 점수가 똑같이 0.33으로 나온다. 가중 충족도 공식은 입력값이 전부 같으면 가중치 분포와 무관하게 같은 결과를 낸다는 성질(가중평균) 때문이며, MINIMUM_SCORE_FOR_HIGH_RELEVANCE(0.6) 미만이라 셋 다 '관련성 높음'이 아니라 '함께 탐색해볼 분야'로 내려간다 — 사용자에게는 '아직 뚜렷한 강점 Trait가 없다'는 정직한 신호로 정상 동작이다.

### 2. Trait Vector가 넓어서 발생하는 과도한 공동 추천 가능성
- `analytical` Persona: industrial_engineering과 media_communication이 둘 다 score=1.0000으로 동점 1위. media_communication Vector가 causal_analysis/pattern_finding/planning/information_comparison을 industrial_engineering과 동일하거나 인접한 가중치로 전부 포함하기 때문이다(§14가 사전에 지적한 '분석 Trait가 강하면 industrial_engineering과 media_communication이 동점 가능').
- `visual_user_facing` Persona: hci_ux와 media_communication이 둘 다 score=1.0000으로 동점 1위. hci_ux Vector 3개(visual_expression/audience_response_prediction/tool_utilization)가 media_communication Vector에 **완전히 같은 가중치(0.67/1.00/0.67)로 그대로 포함**돼 있어, 이 3개 Trait만 관찰된 학생에게는 두 전공이 수학적으로 구분 불가능하다(§14 '동점 가능' 사전 지적과 일치).
- **구조적 원인 분석**: 두 경우 모두 매칭 공식 버그가 아니라, 현재 공식이 '전공이 중요하게 보는 Trait 중 학생이 충족하는 비율'만 계산하고 **'그 전공만의 고유한 Trait 조합인가'는 전혀 고려하지 않기 때문에** 생기는 구조적 결과다. media_communication은 실제 학과 공식 자료상 hci_ux·industrial_engineering 두 전공의 핵심 Trait를 모두 포함하는 폭넓은 커리큘럼(데이터 분석 + UX/시각 + 캠페인 기획)을 갖고 있어, 이 구조적 결과 자체가 근거 데이터를 정직하게 반영한 것이다(예전 손으로 채운 값에서는 이런 겹침이 우연히 가려져 있었을 뿐이다).

### 3. 전공 근거 부족으로 판단할 수 없는 경우
- `tool_only`(Trait 1개만 강함), `sparse_partial`(Trait 2개만 관찰), `unresolved_conflict`(핵심 Trait 중 하나가 Mask돼 usable_vector_group_count가 1로 떨어짐) 세 Persona 모두 세 전공 전부 `insufficient`로 나온다. MINIMUM_USABLE_TRAITS(3)·MINIMUM_USABLE_VECTOR_GROUPS(2) 요건이 정상적으로 '아직 판단하기엔 근거가 부족하다'는 상태를 걸러낸 것이지, 대표 전공 3개 자체의 결함이 아니다.
- `planning_collaboration` Persona는 media_communication이 유리할 만한 Trait 조합(계획+협업 선호)을 답했는데도, 그 2개 Trait가 media_communication Vector에서 work_style 그룹 하나에 몰려 있어(usable_vector_group_count=1) usable_trait_count=2로 여전히 insufficient가 나온다 — '전공에 유리한 Trait를 답했다'와 '그 전공을 계산할 만큼 답했다'가 다를 수 있음을 보여주는 경계 사례다.

### 4. 추가 Trait가 필요한 문제인지
아니다. 위 동점 현상은 Trait 개수·정의 부족 때문이 아니라, hci_ux·industrial_engineering의 핵심 Trait가 이미 media_communication 안에 실제로(공식 커리큘럼상) 포함돼 있기 때문이다. Trait를 더 쪼갠다고 이 구조적 겹침이 사라지지 않는다 — 이번 라운드 범위(§ '기존 12개 trait_id... 임의로 변경하지 마세요')에서도 다루지 않았다.

### 5. 매칭 공식 보완이 필요한 문제인지
판단을 유보한다. 이번 라운드는 '가중치나 Fixture를 억지로 조정해 원하는 순서를 만들지 않는다'는 제약이 있어 공식을 고치지 않았다. 다만 관찰된 사실은 다음과 같이 정리할 수 있다: 현재 공식은 '전공 A의 Trait 충족도'만 독립적으로 계산하고 '학생의 Trait 조합이 전공 A에만 있는 고유한 조합인지, 전공 B와도 겹치는 조합인지'는 계산에 안 들어간다. 동점을 구조적으로 줄이려면(공식을 바꾼다면) 전공 간 Trait 겹침을 패널티로 반영하는 방식이 후보가 될 수 있지만, 이는 §16 '검증된 값이 아니라 MVP 초기 휴리스틱'이라는 기존 가중치 체계 자체를 다시 설계하는 작업이라 이번 라운드 범위를 벗어난다 — 다음 라운드에서 별도로 판단이 필요한 항목으로 남긴다.

## 회귀 관찰 요약 (다음 라운드에서 벡터가 바뀌면 이 표도 다시 생성해서 비교)

| 현상 | Persona | 관찰 결과 |
|---|---|---|
| HCI 관련 Trait 강함 → hci_ux/media_communication 동점 | visual_user_facing | 동점 확인 |
| 분석 Trait 강함 → industrial_engineering/media_communication 동점 | analytical | 동점 확인 |

## 12개 Trait ID (참고 — 이번 라운드에서 변경 없음)

causal_analysis, pattern_finding, planning, immediate_execution, change_adaptation, collaboration_preference, opinion_mediation, emotional_interpretation, audience_response_prediction, visual_expression, information_comparison, tool_utilization

