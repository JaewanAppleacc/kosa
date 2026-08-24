# Trait Evidence Coverage — Adaptive Target Planner Gap 진단

브랜치 `a/trait-evidence-coverage-planner-gap`. 별도 Worktree·별도 브랜치, 읽기 중심 Shadow 진단만 수행했다 — Runtime·Stop Condition·질문·Mapping·Review JSON은 전혀 바꾸지 않았다.

## 0. 구조적 불일치 요약

- 실제 Adaptive Target Planner(`select_pack_adaptive_target`)는 한 Context 안에서 `support_count>=2`가 되면 그 Trait를 더 이상 Gap으로 보지 않는다.
- Coverage SUFFICIENT는 `weight>=3.0`·`Context>=2`·`Frame>=2`를 요구한다.
- Primary 2개(같은 Context) = weight 2.0 → 3.0 문턱 미달. 다른 Context에서 다시 목표가 되지 않는 한 그 Trait는 SUPPORTED에 머문다.

## 1. Baseline(실제 Planner) — Persona별 Trait 종료 순간

| Persona | Trait 질문 | Backup | UNOBS·LIM·SUP·SUFF·CONF | 상위5 SUFF | 상위8 SUFF | Planner가 멈췄지만 최종 SUFFICIENT 아닌 Trait 수 |
|---|---|---|---|---|---|---|
| 분석형 | 35 | 0 | 19·2·2·1·0 | ❌ | ❌ | 1 |
| 혼합·교차형 | 35 | 0 | 16·3·2·3·0 | ❌ | ❌ | 0 |
| 니치 관심형 | 35 | 0 | 16·5·3·0·0 | ❌ | ❌ | 1 |
| Coverage 최대화형 | 35 | 0 | 3·13·8·0·0 | ❌ | ❌ | 1 |

## 2. Persona별 상세 — Planner가 멈췄지만 SUFFICIENT에 못 미친 Trait

### 분석형 (Context: ['science', 'business', 'sports', 'law_politics', 'making'])

| Trait | 멈춘 Context | 멈춘 시점(질문 순번) | 다른 Context서 재목표됨 | 그 순간 Coverage | 최종 Coverage | 최종 weight | 최종 Context 수 | 최종 Frame 수 |
|---|---|---|---|---|---|---|---|---|
| detail_orientation | making | 4 | 아니오 | SUPPORTED | SUPPORTED | 2.0 | 2 | 2 |

### 혼합·교차형 (Context: ['game', 'cooking', 'law_politics', 'art_design', 'science'])

(없음 — 이 Persona는 Planner가 멈춘 모든 Trait가 최종 SUFFICIENT에 도달했다)

### 니치 관심형 (Context: ['fashion_beauty', 'travel', 'cooking', 'art_design', 'making'])

| Trait | 멈춘 Context | 멈춘 시점(질문 순번) | 다른 Context서 재목표됨 | 그 순간 Coverage | 최종 Coverage | 최종 weight | 최종 Context 수 | 최종 Frame 수 |
|---|---|---|---|---|---|---|---|---|
| detail_orientation | fashion_beauty | 3 | 예 | SUPPORTED | SUPPORTED | 2.0 | 1 | 2 |

### Coverage 최대화형 (Context: ['science', 'media', 'school_life', 'business', 'making'])

| Trait | 멈춘 Context | 멈춘 시점(질문 순번) | 다른 Context서 재목표됨 | 그 순간 Coverage | 최종 Coverage | 최종 weight | 최종 Context 수 | 최종 Frame 수 |
|---|---|---|---|---|---|---|---|---|
| creative_ideation | business | 2 | 예 | LIMITED | LIMITED | 1.0 | 1 | 1 |

## 3. 대안 A/B/C/D 비교

상위5·8 SUFFICIENT '비율'은 상위 N개 중 실제로 SUFFICIENT인 개수의 비율을 Persona 평균한 값이다(0.0~1.0) — 전부-아니면-말고(All-or-nothing) 지표는 질문 예산이 작아 네 대안 모두 0.00이 나와 차이를 구분할 수 없었다(§ 아래 4개 Persona 실측, All-or-nothing 값도 참고용으로 함께 남긴다).

| 대안 | 상위5 비율 | 상위8 비율 | 상위5 All-or-nothing | 상위8 All-or-nothing | 총 Trait 질문 수 | 낭비 슬롯(§0 정의) |
|---|---|---|---|---|---|---|
| Baseline(오늘 실제 Planner) | 0.100 | 0.094 | 0.00 | 0.00 | 140 | (해당 없음) |
| D(SUPPORTED 중심 재표현, 재실행 없음) | 0.450 | 0.375 | (해당 없음, SUPPORTED 기준) | (해당 없음, SUPPORTED 기준) | 140 | (해당 없음, Baseline과 동일 실행) |
| A | 0.100 | 0.125 | 0.00 | 0.00 | 140 | 0 |
| B | 0.100 | 0.094 | 0.00 | 0.00 | 140 | 0 |
| C | 0.150 | 0.125 | 0.00 | 0.00 | 140 | 38 |

질문 수가 대안마다 거의 같은 이유: `decide_stop_or_continue()`(Context당 최소 4·최대 6, 수정 안 함)가 모든 대안에서 그대로 적용된다 — 대안은 그 고정 슬롯을 '어떤 Trait에 쓸지'만 바꾼다.

## 4. 추천안

**선택: C**

(상위5 비율+상위8 비율)/2 결합 점수 실측값은 baseline(상위5 0.100/상위8 0.094/평균 0.097) → A(상위5 0.100/상위8 0.125/평균 0.113) → B(상위5 0.100/상위8 0.094/평균 0.097) → C(상위5 0.150/상위8 0.125/평균 0.138) 순으로, C가 가장 높다. Coverage 기준(weight>=3.0·Context>=2·Frame>=2) 자체는 세 대안 모두 전혀 완화하지 않았다 — 대안마다 바뀌는 건 Planner가 '무엇을 목표로 삼을지'뿐이고, 그 결과 같은 질문 예산(Context당 4~6개, Stop Condition 불변) 안에서 C가 상위 5~8개 Trait에 더 효과적으로 슬롯을 배분했다.

C도 24개 전체를 SUFFICIENT로 만들지 못한다(애초에 그게 목표가 아니다) — 상위 8개 밖의 Trait는 이 세션에서 UNOBSERVED/LIMITED에 머무를 수 있고, 이는 의도된 결과다(§5 '24개 전체를 SUFFICIENT로 만드는 것을 목표로 삼지 말 것'). 다만 낭비 슬롯 수는 C=38로 다른 대안보다 많다(§0 정의 — top_traits 안에서도 이미 SUFFICIENT인 Trait에 슬롯이 배정된 경우를 낭비로 센다. 참고: A=0, B=0) — 상위 Trait 안에서의 재확인 비용이 더 든다는 뜻이지, top_traits 밖으로 슬롯이 샌다는 뜻은 아니다.
