# business(창업·비즈니스) Context Pack — Mapping 감사 초안

담당 브랜치: `context-pack-technical`. 이 문서는 `src/data/context_packs/business.py`의
질문·Trait Mapping을 사람이 검수할 수 있도록 요약한 초안이다. **자동 승인된 항목은
없다** — `data/reviews/context_packs/business_review_status.json`의 11개 Key는
전부 `reviewer_1_status: "TBD"`다.

## 1. Anchor 5개

| anchor_id | label | 상황 | forbidden_assumptions |
|---|---|---|---|
| idea_shaping | 아이디어 구상 | 새 아이디어를 떠올리고 다듬는 상황 | 실제 창업 경험, 투자 유치 경험 |
| feedback_reading | 반응·피드백 확인 | 사람들의 반응을 확인하는 상황 | 실제 판매·거래 경험, 투자자 앞 발표 |
| resource_budgeting | 자원·예산 배분 | 제한된 시간·예산을 배분하는 상황 | 실제 자금 운용 경험, 큰 규모의 예산 |
| plan_decision | 방향 결정 | 여러 대안 중 하나를 정하는 상황 | 정답이 정해진 결정 |
| team_role_share | 팀 역할 나누기 | 팀에서 역할을 나누는 상황 | 리더 역할을 기본으로 맡는 것, 이미 완성된 팀 구성 |

## 2. Trait Mapping 요약

Seed 5문항 + Backup 5문항 = 10문항 × 5선택지 = 50 Option. 이 중 **NO_SIGNAL 10개**
(문항당 정확히 1개) — "정해진 방식을 그대로 따른다", "특별히 신경 쓰지 않는다"류의
행동은 특정 Trait 근거로 보기 약하다고 판단해 억지로 매핑하지 않았다.

사용한 Trait(13개, 24개 Ontology 중 business 상황에 자연스럽게 관찰되는 것만
선택 — 전부 사용할 필요는 없다):
`novelty_seeking`, `creative_ideation`, `audience_response_prediction`, `planning`,
`change_adaptation`, `collaboration_preference`, `information_comparison`,
`causal_analysis`, `opinion_expression`, `independent_judgment`,
`uncertainty_tolerance`, `persistence_completion`, `opinion_mediation`.

## 3. 지시문 준수 확인

- **창업 관심 → 리더십/모험성 자동 연결 금지**: `team_role_share` Anchor에
  `opinion_expression`(제안)·`opinion_mediation`(조율)·`collaboration_preference`
  (필요한 역할 채우기)를 배분했고 "리더 역할"을 직접 관찰하는 Option은 없다.
  Anchor forbidden_assumptions에도 "리더 역할을 기본으로 맡는 것"을 명시했다.
- **실제 창업 경험 전제 금지**: 전 문항이 "동아리", "친구들과 아이디어 회의",
  "팀 활동" 수준으로만 서술된다. 투자·매출·법인 등록 언급 없음
  (`tests/test_context_pack_business.py::ForbiddenAssumptionTextTest`로 문자열
  검사 자동화).
- **돈을 많이 벌고 싶은지 묻지 않기**: 금전적 목표를 묻는 문항 없음(동일 테스트로
  확인).
- **아이디어·고객 반응·자원 배분·의사결정 상황 활용**: 5개 Anchor가 각각
  아이디어 구상/반응 확인/자원 배분/방향 결정/역할 나누기에 대응한다.

## 4. 검수자가 특히 봐야 할 지점

1. `resource_budgeting` Backup의 `try_alternative` → `uncertainty_tolerance` 매핑이
   자연스러운지("결과가 어떻게 될지 몰라도 다른 방법을 시도"가 causal_analysis가
   아니라 uncertainty_tolerance로 가는 게 맞는지) 재검토 필요.
2. `feedback_reading` Seed의 NO_SIGNAL(`just_check_count`, "얼마나 많은 사람이
   좋아했는지부터 확인한다")이 실제로는 information_comparison에 가깝다고 볼
   여지가 있다 — 초안에서는 "숫자 확인만으로는 비교·판단 행동이라 보기 약하다"고
   판단했지만 이견이 있을 수 있다.

## 5. Direct Probe 후보(미구현, 아이디어만)

- `personal_goal_priority`(개인 목표 우선)를 `resource_budgeting` Anchor에서 더
  직접적으로 관찰하는 Direct Probe 후보 — "정해진 팀 목표와 내가 원하는 방향이
  다를 때 자원을 어디에 먼저 쓰는가" 같은 질문이 후보가 될 수 있다. 실제
  `V2DirectProbeBlueprint` 작성은 이번 범위 밖이라 만들지 않았다.
