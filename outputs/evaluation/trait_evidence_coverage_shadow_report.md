# Trait Evidence Coverage Shadow 진단 보고서

브랜치 `a/trait-evidence-coverage-shadow`. **진단 전용이다** — Runtime Stop
Condition·Matching·학생 API 어디에도 연결하지 않았다. 생성 시각을 담지 않는다
(같은 코드로 재실행하면 이 파일과 byte-identical해야 한다).

## 1. Coverage Policy 최종 기준

**가중치** — PRIMARY 1.0 · 검수 승인된 RELATED 0.5 · NO_SIGNAL 0 · 승인되지 않은 Signal은 계산에서 제외 · 동일 blueprint_id+frame_id 반복은 1회만 인정
(Registry의 실제 저장 weight 0.33/0.67과는 별개 — 이 Policy 전용 고정 상수다).

**SUFFICIENT** — Primary 2개 이상 AND 유효 가중치 합계 3.0 이상 AND 서로 다른 Context 2개 이상 AND 서로 다른 Frame 2개 이상 AND 동일 방향 비율 70% 이상 AND unresolved conflict 없음(전부 동시 충족).

**상태 판정 순서(우선순위)**:

1. Primary·Related 둘 다 0건 → `UNOBSERVED`
2. 미해결 Conflict 존재 또는 방향 일관성 70% 미만 → `CONFLICTED`
3. 위 SUFFICIENT 6개 조건 전부 충족 → `SUFFICIENT`
4. Primary 2개 이상 + Frame 2개 이상(전체 기준 미달) → `SUPPORTED`
5. 그 외(한 Context/한 Frame에만 집중 등) → `LIMITED`

> SUFFICIENT는 Trait가 높다는 뜻이 아니다 — 높음/낮음/상황 의존적을 판단할 만큼
> 근거가 충분하다는 뜻으로만 쓴다.

## 2. 실행 조건 요약

- **환경 A** — A. 현재 3 Context(2+1 상한 기반 정책, Pool은 전체 고정 콘텐츠)
  - Pool 38문항(family: {'seed': 3, 'backup': 21, 'v2_direct_probe': 14}), 승인 18문항
- **환경 B** — B. 임시 승인 Fixture 기반 15 Context(4+1 상한 기반 정책, Pool은 전체 고정 콘텐츠)
  - Pool 158문항(family: {'seed': 63, 'backup': 21, 'pack_backup': 60, 'v2_direct_probe': 14}), 승인 138문항
- Persona 정책: 매 질문마다 '지금까지 누적 가중치가 가장 낮은 Trait'를 가리키는
  선택지를 고르는 결정론적 Coverage 최대화 정책(실제 Adaptive Target Planner와
  다르다 — §설계 결정과 한계 참고).

## 3. 현재 3 Context 결과 (환경 A)

| 질문 수 상한 | UNOBSERVED · LIMITED · SUPPORTED · SUFFICIENT · CONFLICTED |
|---|---|
| 20 | UNOBSERVED 10 · LIMITED 13 · SUPPORTED 1 · SUFFICIENT 0 · CONFLICTED 0 |
| 30 | UNOBSERVED 7 · LIMITED 16 · SUPPORTED 1 · SUFFICIENT 0 · CONFLICTED 0 |
| 38 | UNOBSERVED 7 · LIMITED 16 · SUPPORTED 1 · SUFFICIENT 0 · CONFLICTED 0 |

- 약 20문항(cap=20) 시점 SUFFICIENT 수: 0
- 전체 Pool(38문항) 소진 시점 SUFFICIENT 수: 0
- 원인: V2 Direct Probe 14개 전원 `reviewer_1_status=TBD`(신규 12개 Trait의 유일한
  PRIMARY 출처), 기존 Backup 6개 전원 `REVISE` — 둘 다 승인 Evidence 계산에서
  제외된다(실측, 가정 아님). 실제 승인된 재료는 Seed 3개 + Anchor Backup 15개
  = 18문항뿐이다.
- Context 2개 조건 때문에 구조적으로 SUFFICIENT 불가능한 Trait: aesthetic_sensitivity, challenge_seeking, novelty_seeking, personal_goal_priority, verbal_expression

## 4. 15 Context, 임시 승인 Fixture 결과 (환경 B)

| 질문 수 상한 | UNOBSERVED · LIMITED · SUPPORTED · SUFFICIENT · CONFLICTED |
|---|---|
| 20 | UNOBSERVED 7 · LIMITED 14 · SUPPORTED 3 · SUFFICIENT 0 · CONFLICTED 0 |
| 30 | UNOBSERVED 3 · LIMITED 16 · SUPPORTED 5 · SUFFICIENT 0 · CONFLICTED 0 |
| 40 | UNOBSERVED 2 · LIMITED 15 · SUPPORTED 6 · SUFFICIENT 1 · CONFLICTED 0 |
| 50 | UNOBSERVED 2 · LIMITED 8 · SUPPORTED 10 · SUFFICIENT 4 · CONFLICTED 0 |
| 158 | UNOBSERVED 0 · LIMITED 0 · SUPPORTED 1 · SUFFICIENT 23 · CONFLICTED 0 |

**상위 Trait가 SUFFICIENT에 도달하는 시점(질문 수, 오름차순, 상위 8개):**

| 순위 | Trait | 도달 질문 수 |
|---|---|---|
| 1 | causal_analysis | 38 |
| 2 | collaboration_preference | 47 |
| 3 | change_adaptation | 48 |
| 4 | pattern_finding | 50 |
| 5 | opinion_mediation | 52 |
| 6 | persistence_completion | 53 |
| 7 | planning | 55 |
| 8 | detail_orientation | 56 |

- Context 2개 조건 때문에 구조적으로 SUFFICIENT 불가능한 Trait: challenge_seeking
- 전체 Pool(158문항) 소진해도 SUFFICIENT에 못 이른 Trait: challenge_seeking

## 5. 가장 자주 미관찰(UNOBSERVED)로 남는 Trait

aesthetic_sensitivity, challenge_seeking, independent_judgment, pattern_finding, personal_goal_priority, verbal_expression, visual_expression

## 6. 원인 구분 — 질문 Mapping 부족 vs Persona 특성

`MAPPING_GAP`(승인된 기회 자체가 Primary 2개 미만 — Persona가 무엇을 골라도
SUFFICIENT 불가) / `CONTEXT_GAP`(기회는 있지만 Context가 1개뿐) /
`POLICY_LIMITED`(기회·Context 조건은 충분한데 이 Coverage 최대화 정책으로도
SUFFICIENT까지 못 감 — 실제 Persona 다양성 문제에 더 가깝다) / `SUFFICIENT`.

| Trait | 환경 A | 환경 B |
|---|---|---|
| aesthetic_sensitivity | MAPPING_GAP | SUFFICIENT |
| audience_response_prediction | CONTEXT_GAP | SUFFICIENT |
| causal_analysis | POLICY_LIMITED | SUFFICIENT |
| challenge_seeking | MAPPING_GAP | CONTEXT_GAP |
| change_adaptation | POLICY_LIMITED | SUFFICIENT |
| collaboration_preference | POLICY_LIMITED | SUFFICIENT |
| creative_ideation | POLICY_LIMITED | SUFFICIENT |
| detail_orientation | POLICY_LIMITED | SUFFICIENT |
| emotional_interpretation | POLICY_LIMITED | SUFFICIENT |
| immediate_execution | CONTEXT_GAP | SUFFICIENT |
| independent_judgment | MAPPING_GAP | SUFFICIENT |
| information_comparison | POLICY_LIMITED | SUFFICIENT |
| novelty_seeking | MAPPING_GAP | SUFFICIENT |
| opinion_expression | CONTEXT_GAP | SUFFICIENT |
| opinion_mediation | POLICY_LIMITED | SUFFICIENT |
| pattern_finding | CONTEXT_GAP | SUFFICIENT |
| persistence_completion | POLICY_LIMITED | SUFFICIENT |
| personal_goal_priority | MAPPING_GAP | SUFFICIENT |
| planning | CONTEXT_GAP | SUFFICIENT |
| systems_thinking | CONTEXT_GAP | SUFFICIENT |
| tool_utilization | CONTEXT_GAP | SUFFICIENT |
| uncertainty_tolerance | MAPPING_GAP | SUFFICIENT |
| verbal_expression | MAPPING_GAP | SUFFICIENT |
| visual_expression | MAPPING_GAP | SUFFICIENT |

## 7. 권장 최소·최대 질문 수

- 최소 52문항 — 상위 5개 Trait가 SUFFICIENT에 도달
- 최대 56문항 — 상위 8개 Trait가 SUFFICIENT에 도달
- 근거: B 환경(15 Context, 임시 승인 Fixture) 기준 — 상위 5개 Trait가 전부 SUFFICIENT가 되는 최소 질문 수를 최소값으로, 상위 8개가 전부 SUFFICIENT가 되는 질문 수를 최대값으로 잡았다. A 환경(현재 3 Context)은 현재 승인 상태로는 단 하나의 Trait도 SUFFICIENT에 도달하지 못해 권장 범위의 근거로 쓸 수 없다.

## 8. Coverage 기반 종료를 Runtime에 연결해도 되는가

**아직 이르다**

- A 환경(현재 실제 승인 상태)에서 SUFFICIENT Trait 수가 0이다 — Coverage 기반 종료를 지금 Runtime에 연결하면 거의 모든 세션이 Stop 조건을 영원히 못 만족한다.
- V2 Direct Probe 14개가 전부 reviewer_1_status=TBD라 신규 12개 Trait의 유일한 PRIMARY 출처가 통째로 계산에서 빠진다 — 검수가 먼저 끝나야 한다.
- 12개 ContextPack이 전부 미검수라 B 환경의 결과는 '검수가 끝난다면'이라는 가정 위의 상한일 뿐, 지금 당장 재현되는 상태가 아니다.
- 이 진단은 Adaptive Tail(LLM 생성) 질문을 포함하지 않는다 — 실제 세션에는 이 진단이 보지 못한 질문 유형이 더 있다.

## 9. 설계 결정과 한계

- Adaptive Tail(LLM 생성) 질문은 결정론을 지킬 수 없어 이 진단에 포함하지
  않았다 — 이 보고서의 숫자는 '고정 콘텐츠만으로 도달 가능한' 하한에 가깝다.
- '2+1'/'4+1'은 실제 세션의 Context 개수 상한(수정 금지)이다. 이 진단은 그
  상한을 그대로 재현하지 않고, 해당 Context 풀 전체가 제공하는 재료의 상한을
  본다(§설계 결정, 스크립트 docstring 참고).
- Persona는 '그럴듯한 학생'이 아니라 Coverage를 의도적으로 최대화하는
  결정론적 정책이다 — 실제 Adaptive Target Planner의 Gap 우선순위 로직과
  다르다.
- 환경 B의 12개 ContextPack 승인은 전부 `tempfile` 안의 가짜 Fixture다.
  `data/reviews/`는 이 스크립트 실행 전후로 바이트 하나도 바뀌지 않는다.
