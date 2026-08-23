# making(만들기·코딩) Context Pack — Mapping 감사 초안

담당 브랜치: `context-pack-technical`. `src/data/context_packs/making.py`의
질문·Trait Mapping 요약. **자동 승인된 항목은 없다** —
`data/reviews/context_packs/making_review_status.json`의 11개 Key는 전부
`reviewer_1_status: "TBD"`다.

## 1. Anchor 5개

| anchor_id | label | 상황 | forbidden_assumptions |
|---|---|---|---|
| assembling | 조립·구성 | 부품·재료를 맞춰 완성하는 상황 | 코딩 경험, 전자기기 조립 경험 |
| tool_using | 도구 다루기 | 새 도구·프로그램의 기능을 익히는 상황 | 특정 프로그래밍 언어 경험 |
| error_fixing | 오류 해결 | 뜻대로 안 될 때 원인을 찾는 상황 | 프로그래밍 디버깅 경험, 전문적 오류 해결 능력 |
| improving | 개선하기 | 완성한 것을 다시 살펴보고 고치는 상황 | 완벽주의 성향을 기본으로 전제 |
| user_perspective | 사용자 관점 | 다른 사람이 쓴다고 생각해보는 상황 | 실제 사용자 테스트 경험 |

## 2. Trait Mapping 요약

Seed 5문항 + Backup 5문항 = 10문항 × 5선택지 = 50 Option, **NO_SIGNAL 10개**
(문항당 1개).

사용한 Trait(15개): `planning`, `immediate_execution`, `detail_orientation`,
`change_adaptation`, `causal_analysis`, `collaboration_preference`,
`persistence_completion`, `information_comparison`, `novelty_seeking`,
`creative_ideation`, `pattern_finding`, `uncertainty_tolerance`,
`systems_thinking`, `visual_expression`, `audience_response_prediction`.

## 3. 지시문 준수 확인

- **코딩 경험 필수 전제 금지**: 질문·선택지 어디에도 "코딩"이라는 단어를 쓰지
  않았다(`tests/test_context_pack_making.py::ForbiddenAssumptionTextTest::
  test_does_not_mention_coding_directly`). "도구", "프로그램"처럼 물리적 만들기와
  소프트웨어 둘 다에 적용 가능한 표현만 썼다.
- **코딩 → 분석적 자동 연결 금지**: `error_fixing` Anchor에도 causal_analysis
  외에 `pattern_finding`·`immediate_execution`·`information_comparison`·
  `systems_thinking`을 배분했고, `improving`·`user_perspective` Anchor에는
  `visual_expression`·`creative_ideation`·`audience_response_prediction`처럼
  분석과 무관한 Trait를 배정해 특정 Trait로의 쏠림을 피했다.
- **조립·도구·오류·개선·사용자 관점 다양성**: 5개 Anchor가 그대로 이 5가지에
  대응한다.

## 4. 검수자가 특히 봐야 할 지점

1. `error_fixing` Backup의 `rebuild_part`("그 부분을 처음부터 다시 만들어본다")를
   `uncertainty_tolerance`로 매핑했는데, `persistence_completion`(포기하지 않고
   다시 시도)과 겹쳐 보일 수 있다 — 같은 문항에 `keep_trying`이 이미
   persistence_completion을 쓰고 있어 구분을 위해 uncertainty_tolerance를
   선택했으나 재검토 필요.
2. `improving` Seed의 `change_look`("겉모습이나 디자인을 다르게 바꿔본다") →
   `visual_expression` 매핑이 "만들기" 맥락에서 자연스러운지(미술/디자인 Context와
   겹치는 행동인지) 확인 필요.

## 5. Direct Probe 후보(미구현, 아이디어만)

- `tool_utilization`(도구 활용)을 `error_fixing`이나 `tool_using` Anchor에서 더
  직접적으로 관찰하는 Direct Probe 후보 — 현재 Pack에는 이 Trait가 전혀 쓰이지
  않았다. "여러 디버깅 도구 중 어떤 것을 골라 쓰는가" 같은 질문이 후보가 될 수
  있다. 실제 Blueprint 작성은 이번 범위 밖.
