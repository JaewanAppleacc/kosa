# Trait Evidence Coverage — Adaptive Target Planner Gap 진단 (v2, 9-Persona)

브랜치 `a/planner-gap-9persona-diagnostics`. 별도 Worktree·별도 브랜치, 읽기 중심 Shadow 진단만 수행했다 — Runtime·Stop Condition·질문·Mapping·Review JSON은 전혀 바꾸지 않았다.

Persona 9개(이전 라운드 4개 → 이번 9개 전부): analytical, creative_visual, social_collaborative, practical_making, language_humanities, mixed_cross_domain, niche_interest, coverage_maximizing, coverage_minimizing.

## 0. 이전 라운드 대비 수정 사항

1. **대안 C의 순환성 제거** — 이전엔 top_traits를 Persona의 고정 답변 선택 정책과 같은 오라클(trait_affinity_order)에서 가져왔다. 이번 C/C2는 그 시점까지 실제로 쌓인 증거(weight)만으로 매 turn 다시 계산한다.
2. **Anchor 다양화** — 이전엔 모든 Context에서 알파벳 순 첫 Anchor만 썼다. 이번엔 Pack Context는 후보 Trait-Persona 관심사 교집합 기준, Legacy Context는 안정 해시 기준으로 고른다. Coverage 최대/최소 Anchor 비교는 별도 실험으로 수행했다(§5).
3. **Persona 9개 전부 사용, 대안 C2 추가**(Exploration 예산 + 상위 Trait 집중 혼합).

## 1. Baseline(실제 Planner) — Persona별 요약

| Persona | Context | Trait 질문 | Backup | UNOBS·LIM·SUP·SUFF·CONF | 상위5 SUFF | 상위8 SUFF | 반복 최대 | 미관찰 |
|---|---|---|---|---|---|---|---|---|
| 분석형 | 5 | 35 | 0 | 18·4·2·0·0 | ❌ | ❌ | 10 | 18 |
| 창의·시각형 | 5 | 35 | 0 | 15·4·3·2·0 | ❌ | ❌ | 8 | 15 |
| 사회·협업형 | 5 | 35 | 0 | 17·3·1·3·0 | ❌ | ❌ | 6 | 17 |
| 실행·제작형 | 5 | 35 | 0 | 17·3·3·1·0 | ❌ | ❌ | 10 | 17 |
| 언어·인문형 | 5 | 35 | 0 | 17·3·1·3·0 | ❌ | ❌ | 6 | 17 |
| 혼합·교차형 | 5 | 35 | 0 | 15·5·3·1·0 | ❌ | ❌ | 8 | 15 |
| 니치 관심형 | 5 | 35 | 0 | 17·4·2·1·0 | ❌ | ❌ | 10 | 17 |
| Coverage 최대화형 | 5 | 35 | 0 | 3·15·6·0·0 | ❌ | ❌ | 6 | 3 |
| Coverage 최소화형(1~2개 Trait 집중) | 5 | 35 | 0 | 13·7·2·2·0 | ❌ | ❌ | 4 | 13 |

## 2. 대안 Baseline/A/B/C/C2/D 비교(9-Persona 평균)

| 대안 | 상위5 비율 | 상위8 비율 | 결합 점수 | 총 Trait 질문 수 | 낭비 슬롯 | 고착 turn |
|---|---|---|---|---|---|---|
| Baseline | 0.222 | 0.139 | 0.181 | 315 | (해당 없음) | (해당 없음) |
| D(SUPPORTED 중심 재표현) | 0.467 | 0.389 | (해당 없음, SUPPORTED 기준) | 315 | (재실행 없음) | (해당 없음) |
| A | 0.222 | 0.139 | 0.181 | 315 | 0 | 0 |
| B | 0.222 | 0.139 | 0.181 | 315 | 0 | 0 |
| C | 0.311 | 0.208 | 0.260 | 315 | 54 | 31 |
| C2 | 0.222 | 0.153 | 0.188 | 315 | 4 | 1 |

## 3. 이전 4-Persona 결과와 이번 9-Persona(및 같은 4-Persona 부분집합) 비교

- 이전 라운드(ca82f1f, 4-Persona, 순환적 C): baseline 결합 0.097, C(순환적) 결합 0.138
- 이번 라운드 9-Persona 전체: baseline 결합 0.181, C(비순환) 결합 0.260, C2 결합 0.188
- 이전 C의 수치는 순환적 정의(오라클 사용)로 얻은 값이라 이번 C와 액면가로 비교하면 안 된다 — 위 §0-1 참고. JSON의 `previous_round_4_persona_comparison`에 같은 4개 Persona만 뽑은 이번 라운드 부분집합도 함께 남겼다.

## 4. Anchor 민감도 실험(§5 — Coverage 최대/최소 Anchor 조합)

대상 Context: `art_design` (Anchor별 후보 Trait 수: {'direct_creation': 7, 'planning_composition': 7, 'revision_feedback': 7, 'tool_material_choice': 7, 'visual_appreciation': 7})

**실측 발견**: 후보 Trait 풀이 Anchor에 따라 갈리지 않는다 — Anchor는 증거 게이팅에만 영향을 준다(이 실험의 Fixture는 모든 Anchor를 승인해 게이팅 차이도 제거했으므로, 결과가 같다면 그건 이 두 경로 모두에서 Anchor가 실제로 결과에 영향을 주지 않는다는 뜻이다).

| Anchor 변형 | 실제 Anchor | 상위5 비율 | 상위8 비율 | Trait 질문 수 |
|---|---|---|---|---|
| max_coverage_anchor | visual_appreciation | 0.000 | 0.000 | 35 |
| min_coverage_anchor | direct_creation | 0.000 | 0.000 | 35 |
| persona_default | revision_feedback | 0.000 | 0.000 | 35 |

## 5. 최종 판정

**구현 권고: 예**
**선택: C**

(상위5 비율+상위8 비율)/2 결합 점수 실측값은 baseline(상위5 0.222/상위8 0.139/평균 0.181) → A(상위5 0.222/상위8 0.139/평균 0.181) → B(상위5 0.222/상위8 0.139/평균 0.181) → C(상위5 0.311/상위8 0.208/평균 0.260) → C2(상위5 0.222/상위8 0.153/평균 0.188) 순으로, C가 baseline 대비 +0.079 개선해 뚜렷한 개선 기준(0.05) 이상이다. Coverage 기준 자체는 전혀 완화하지 않았다.

C도 24개 전체를 SUFFICIENT로 만들지 못한다(애초에 그게 목표가 아니다) — 상위 8개 밖의 Trait는 UNOBSERVED/LIMITED에 머무를 수 있고, 이는 의도된 결과다.
