# Context × Trait Coverage 검토표 (C 초안)

작성 2026-08-21 · 작성자 worker_c · 검토 단계 DRAFT

판정 기준: 그 Context의 Seed Question 선택지에 해당 Trait가 실제로 배정돼 있는가.
`O`=관찰 가능 · `-`=배정 없음 · `?`=Seed Question 미작성

| Context | causal_analysis | pattern_finding | planning | immediate_execution | change_adaptation | collaboration_preference | opinion_mediation | emotional_interpretation | audience_response_prediction | visual_expression | information_comparison | tool_utilization |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 게임 | O | O | - | O | - | O | - | - | - | - | - | O |
| 미디어 | O | - | - | - | - | - | - | O | O | O | O | - |
| 학교생활 | - | - | O | - | O | O | O | O | - | - | - | - |
| 창업·비즈니스 | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? |
| 만들기·코딩 | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? |
| 봉사·사회참여 | - | - | O | O | - | O | O | O | - | - | - | - |
| 스포츠 | O | O | - | O | O | O | - | - | - | - | - | - |
| 과학탐구 | O | O | O | - | - | - | - | - | - | - | O | O |
| 글쓰기·독서 | O | - | O | - | - | - | - | O | O | - | O | - |
| 미술·디자인 | - | - | O | - | O | - | - | - | O | O | - | O |
| 여행·문화탐방 | - | - | O | O | O | - | - | O | - | - | O | - |
| 요리·음식 | - | O | O | O | - | - | - | - | O | - | - | O |
| 패션·뷰티 | - | - | - | - | O | O | - | - | O | O | O | - |
| 역사·인문학 | O | O | - | - | - | - | O | O | - | - | O | - |
| 법·정치·시사 | O | - | - | - | O | O | O | - | - | - | O | - |

## Trait별 관찰 가능 Context 수

| trait_id | 관찰 가능 Context 수 | 최소 요구 | 부족분 |
|---|---|---|---|
| causal_analysis | 7 | 2 | - |
| pattern_finding | 5 | 2 | - |
| planning | 7 | 2 | - |
| immediate_execution | 5 | 2 | - |
| change_adaptation | 6 | 2 | - |
| collaboration_preference | 6 | 2 | - |
| opinion_mediation | 4 | 2 | - |
| emotional_interpretation | 6 | 2 | - |
| audience_response_prediction | 5 | 2 | - |
| visual_expression | 3 | 1 | - |
| information_comparison | 7 | 1 | - |
| tool_utilization | 4 | 1 | - |

## C가 A에게 확인 요청하는 것

1. Seed Question이 아직 없는 Context: business, making. A 지시서 §4가 핵심 Context 5개의 Seed Question을 A 책임으로 두므로 C가 대신 쓰지 않았다. 작성되면 이 표를 다시 돌려야 한다.
2. 이 표는 Seed Question 1개 기준이다. 꼬리질문(§7-2)까지 포함하면 관찰 가능 범위가 넓어지지만, 꼬리질문은 세션마다 달라져 사전 Coverage로 셀 수 없다. 사전 Coverage를 Seed 기준으로만 보는 게 맞는지 확인이 필요하다.
3. `visual_expression`은 비핵심 10개 중 2개(미술·디자인, 패션·뷰티)에서만 관찰된다. domain_specific이라 최소 Context가 1개여서 규칙은 만족하지만, 이 Trait를 고른 학생이 적은 근거로 판정될 여지가 있다.
