# Coverage-focused Target Selector — Shadow 평가 (a/coverage-focused-planner-shadow)

별도 Worktree·별도 브랜치, 읽기 중심 Shadow 평가만 수행했다 — Runtime Planner·Stop Condition·질문·Mapping·Review JSON은 전혀 바꾸지 않았다. 학생 답변·질문 원문은 이 보고서에 없다.

Persona 9개(기존 9개 전부): analytical, creative_visual, social_collaborative, practical_making, language_humanities, mixed_cross_domain, niche_interest, coverage_maximizing, coverage_minimizing.

## 1. Baseline vs Shadow 대체 실행 — Persona별

| Persona | Baseline 상위5 | Baseline 상위8 | Shadow 상위5 | Shadow 상위8 | Turn 일치율 |
|---|---|---|---|---|---|
| 분석형 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 |
| 창의·시각형 | 0.200 | 0.125 | 0.200 | 0.250 | 0.208 |
| 사회·협업형 | 0.600 | 0.375 | 0.600 | 0.375 | 0.722 |
| 실행·제작형 | 0.000 | 0.000 | 0.000 | 0.000 | 0.733 |
| 언어·인문형 | 0.600 | 0.375 | 0.600 | 0.375 | 0.833 |
| 혼합·교차형 | 0.200 | 0.125 | 0.200 | 0.125 | 0.458 |
| 니치 관심형 | 0.200 | 0.125 | 0.400 | 0.250 | 0.533 |
| Coverage 최대화형 | 0.000 | 0.000 | 0.000 | 0.000 | 0.278 |
| Coverage 최소화형(1~2개 Trait 집중) | 0.200 | 0.125 | 0.200 | 0.125 | 0.333 |

## 2. 요약

- Baseline 결합 점수: 0.181
- Shadow 대체 실행 결합 점수: 0.206(+0.025)
- Turn 단위 일치율(전체): 0.593
- Shadow 고착 Turn(총): 31
- Shadow Exploration Turn(총): 123
- Baseline 평균 SUPPORTED 이상 Trait 수: 4.00
- Shadow 평균 SUPPORTED 이상 Trait 수: 5.00
- Baseline 평균 미관찰 Trait 수: 14.67
- Shadow 평균 미관찰 Trait 수: 14.89

## 3. Anchor 민감도(Coverage 최대/기본/최소)

대상 Context: `art_design` (후보 Trait 수: {'direct_creation': 7, 'planning_composition': 7, 'revision_feedback': 7, 'tool_material_choice': 7, 'visual_appreciation': 7}, Anchor에 따라 후보 풀이 갈리는가: False)
- 최대: `visual_appreciation` · 최소: `direct_creation` · 기본(Persona별): `revision_feedback`

## 4. 판정

**결론: NEEDS_MORE_SHADOW_EVIDENCE**

결합 점수 개선(+0.025)이 사전 문턱(0.05) 미달이다 — Baseline보다 나쁘지는 않지만 Runtime Flag를 켤 만큼 뚜렷하지도 않다.

이 판정은 자동으로 어떤 Feature Flag도 켜지 않는다 — 기본 Planner를 자동 교체하지 않는다(과제 §7). data/master·API·Stop Condition·Runtime Planner는 이 스크립트로 전혀 바뀌지 않았다.
