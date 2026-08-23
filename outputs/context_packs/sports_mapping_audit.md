# sports(스포츠) Context Pack — Mapping 감사 초안

담당 브랜치: `context-pack-lifestyle`. 이 문서는 `src/data/context_packs/sports.py`의
질문·Trait Mapping을 사람이 검수할 수 있도록 요약한 초안이다. **자동 승인된 항목은
없다** — `data/reviews/context_packs/sports_review_status.json`의 11개 Key는 전부
`reviewer_1_status: "TBD"`다.

## 1. Anchor 5개

작업 지시문이 지정한 분리 기준(관람·기록 향상·전략·개인 운동·팀 상황)을 그대로 썼다.

| anchor_id | label | 상황 | forbidden_assumptions |
|---|---|---|---|
| spectating_analysis | 관람·분석 | 중계를 보거나 결과를 접하는 상황 | 경기장 직접 관람 경험, 특정 종목 관람 경력 |
| record_improvement | 개인 기록 향상 | 스스로 정한 목표를 향해 준비하는 상황 | 신체 능력·기록 자체 평가, 특정 종목 숙련도 |
| strategy_tactics | 전략 분석 | 작전·전략을 이야기하거나 판단하는 상황 | 선수·감독 경험 |
| individual_training | 개인 운동 | 혼자 운동 방식·루틴을 정하는 상황 | 특정 기구·시설 접근성, 운동 능력 평가 |
| team_situation | 팀 상황 | 팀 경기를 하게 된다면(가정형)의 의견 조율 상황 | 실제 팀 스포츠 소속 경험, 성별에 따른 참여 기대 |

## 2. Trait Mapping 요약

Seed 5문항 + Backup 5문항 = 10문항 × 5선택지 = 50 Option. **NO_SIGNAL 12개** — "특별히
하는 건 없다", "닥치면 그때 한다", "관심이 적다"류의 반응은 특정 Trait의 직접 근거로
보기 약하다고 판단해 억지로 매핑하지 않았다.

사용한 Trait(17개, 24개 Ontology 중 sports 상황에 자연스럽게 관찰되는 것만 선택):
`pattern_finding`, `causal_analysis`, `information_comparison`, `planning`,
`persistence_completion`, `personal_goal_priority`, `detail_orientation`,
`systems_thinking`, `change_adaptation`, `uncertainty_tolerance`,
`independent_judgment`, `novelty_seeking`, `tool_utilization`, `opinion_mediation`,
`opinion_expression`, `collaboration_preference`, `emotional_interpretation`.

## 3. 지시문 준수 확인

- **스포츠 관심을 경쟁성·협동성으로 자동 연결 금지**: `collaboration_preference`·
  `opinion_mediation`은 `team_situation` Anchor(팀 경기를 "하게 된다면"이라는 가정형
  질문에서 실제로 어떻게 행동하겠다고 답했는지)에서만 나온다 — 관람·전략·개인 운동
  Anchor에는 이 두 Trait가 전혀 등장하지 않는다
  (`tests/test_context_pack_sports.py::NoAutoCompetitionCollaborationLinkTest`로
  자동 확인).
- **선수·팀 스포츠 경험 전제 금지**: 전 문항이 "~한다면/~하게 된다면"류 가정형이거나
  관람·개인 연습처럼 경험 없이도 답할 수 있는 상황으로만 구성했다. "선수 출신",
  "국가대표" 같은 표현 없음(`ForbiddenAssumptionTextTest`로 확인).
- **체력·운동 능력 평가 금지**: Trait Mapping은 전부 준비 방식·판단 방식·태도에
  대한 것이고, "체력이 얼마나", "운동 실력이" 같은 평가성 표현은 없음(동일 테스트로
  확인). `record_improvement`가 다루는 "목표 향한 준비"도 기록의 절대적 수준이 아니라
  계획·지속성·세부 조정 같은 과정만 묻는다.

## 4. 검수자가 특히 봐야 할 지점

1. `strategy_tactics` Seed의 `not_much_interest`("전략 얘기는 잘 모르겠고 관심이
   적다")를 NO_SIGNAL로 뒀는데, "관심이 적다"는 표현 자체가 흥미도 관련 다른 신호로
   오해될 수 있어 문구를 더 중립적으로 다듬을지 검토가 필요하다.
2. `individual_training`의 `tool_utilization`("운동 앱이나 기록 도구를 활용해서
   관리한다")이 스포츠 맥락에서 자연스러운지, 아니면 `making`/`science` Context와
   겹치는 느낌이 있는지 재검토 필요.
3. `team_situation`이 유일하게 가정형("~하게 된다면")으로 서술된 Anchor라 다른
   Anchor와 문체가 약간 다르다 — 검수 시 이 차이가 자연스러운지 확인 필요(팀 스포츠
   경험을 전제하지 않으려는 의도적 선택).

## 5. Direct Probe 후보(미구현, 아이디어만)

- `uncertainty_tolerance`를 `strategy_tactics` Anchor에서 더 직접적으로 관찰하는
  Direct Probe 후보 — "정보가 부족한 상태에서 다음 작전을 바로 정해야 한다면"류 질문이
  후보가 될 수 있다. 실제 `V2DirectProbeBlueprint` 작성은 이번 범위 밖이라 만들지
  않았다(어떤 Trait가 전체 Ontology 관점에서 우선순위가 높은 Direct Probe 대상인지는
  A가 여러 Context를 가로질러 조정할 사안이라 이 Pack 혼자 판단하지 않았다).
