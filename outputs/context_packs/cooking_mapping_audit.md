# cooking(요리·음식) Context Pack — Mapping 감사 초안

담당 브랜치: `context-pack-lifestyle`. 이 문서는 `src/data/context_packs/cooking.py`의
질문·Trait Mapping을 사람이 검수할 수 있도록 요약한 초안이다. **자동 승인된 항목은
없다** — `data/reviews/context_packs/cooking_review_status.json`의 11개 Key는 전부
`reviewer_1_status: "TBD"`다.

## 1. Anchor 5개

작업 지시문이 예시로 든 다섯 축(음식 선택·레시피 이해·재료 대체·과정 계획·맛 조정)을
그대로 Anchor로 썼다.

| anchor_id | label | 상황 | forbidden_assumptions |
|---|---|---|---|
| food_choice | 음식 선택 | 먹을 음식·메뉴를 고르는 상황 | 외식·배달 등 특정 소비 여건 |
| recipe_understanding | 레시피 이해 | 레시피·요리 방법을 보는 상황 | 레시피 앱·요리책 특정 매체 이용 경험 |
| ingredient_substitution | 재료 대체 | 필요한 재료가 없는 상황 | 실제로 재료를 사서 요리해본 경험 |
| process_planning | 과정 계획 | 여러 음식을 한 번에·시간 안에 준비하는 상황 | 여러 명 분 식사를 준비해본 경험 |
| taste_adjustment | 맛 조정 | 맛을 보고 간을 조절하는 상황 | 요리를 직접 맛보며 조절해본 경험 |

## 2. Trait Mapping 요약

Seed 5문항 + Backup 5문항 = 10문항 × 5선택지 = 50 Option. **NO_SIGNAL 14개** —
"그때그때 끌리는 대로 고른다", "그냥 포기한다"류의 반응은 특정 Trait의 직접 근거로
보기 약하다고 판단해 억지로 매핑하지 않았다.

사용한 Trait(14개): `novelty_seeking`, `information_comparison`,
`personal_goal_priority`, `collaboration_preference`, `causal_analysis`, `planning`,
`systems_thinking`, `detail_orientation`, `creative_ideation`,
`uncertainty_tolerance`, `change_adaptation`, `persistence_completion`,
`independent_judgment`, `opinion_mediation`.

## 3. 지시문 준수 확인

- **실제 요리 경험 전제 금지**: 모든 질문을 "~한다면/~해야 한다면" 가정형으로
  묻거나 "레시피를 보게 될 때"처럼 직접 조리 없이도 답할 수 있는 상황으로 구성했다.
  "요리를 해본 적이", "직접 요리해 본" 같은 표현 없음
  (`tests/test_context_pack_cooking.py::ForbiddenAssumptionTextTest`로 확인).
- **음식 선택·레시피 이해·재료 대체·과정 계획·맛 조정 상황 활용**: 5개 Anchor가
  정확히 이 다섯 축에 대응한다(`StructureTest.test_anchor_ids_match_instruction`으로
  확인).
- **가정환경·조리도구 보유 전제 금지**: "집에 있는", "우리 집 부엌", "조리도구를
  갖추" 같은 표현이 어디에도 없다(동일 테스트로 확인). `food_choice`는 "먹을 음식을
  고른다"처럼 조리 여부와 무관한 선택 상황으로, `recipe_understanding`은 "보는"
  행동으로만 구성해 실제 조리 자원 접근성을 요구하지 않는다.

## 4. 검수자가 특히 봐야 할 지점

1. `food_choice` Seed의 `ask_others_and_match`("다른 사람들 의견을 물어보고
   맞춘다") → `collaboration_preference` 매핑이 자연스러운지("음식을 정할 때
   맞추는 것"이 스포츠 `team_situation`이 다루는 협업 선호와 같은 강도의 신호인지)
   재검토 필요.
2. `process_planning` Seed에 NO_SIGNAL이 2개(`feel_burdened_just_thinking`,
   `rarely_such_situation`)라 다른 Anchor보다 신호 밀도가 낮다 — 이 Anchor의
   질문을 더 뾰족하게 다듬을지 검토 필요.
3. `taste_adjustment`의 `opinion_mediation`("다른 사람 입맛도 물어보고 맞추려
   한다")이 요리 맥락에서 "의견 조정"으로 보기에 충분한 강도인지, 아니면 단순
   `collaboration_preference`에 가까운지 재검토 필요.

## 5. Direct Probe 후보(미구현, 아이디어만)

- `causal_analysis`를 `ingredient_substitution` Anchor에서 더 직접적으로 관찰하는
  Direct Probe 후보 — "대체한 재료 때문에 결과가 달라졌다면 무엇이 원인인지"류
  질문이 후보가 될 수 있다. 실제 `V2DirectProbeBlueprint` 작성은 이번 범위 밖이라
  만들지 않았다.
