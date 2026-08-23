# law_politics(법·정치·시사) Context Pack — Mapping 감사 초안

담당 브랜치: `context-pack-technical`. `src/data/context_packs/law_politics.py`의
질문·Trait Mapping 요약. **가장 검수가 중요한 Context** — 정치 성향·이념 추론,
도덕적 정답 프레이밍 위험이 다른 Context보다 크다. **자동 승인된 항목은 없다** —
`data/reviews/context_packs/law_politics_review_status.json`의 11개 Key는 전부
`reviewer_1_status: "TBD"`다.

## 1. Anchor 5개

| anchor_id | label | 상황 | forbidden_assumptions |
|---|---|---|---|
| rule_conflict | 규칙 충돌 | 서로 다른 규칙·기준이 부딪히는 상황 | 특정 정당·이념 판단, 정치적 올바름의 정답 전제 |
| source_reading | 자료 해석 | 뉴스·자료를 읽고 의미를 해석하는 상황 | 특정 언론사·정치 성향 판단 |
| differing_claims | 다른 주장 다루기 | 의견이 다른 여러 주장을 접하는 상황 | 특정 입장이 도덕적으로 옳다는 전제 |
| public_decision | 공공 의사결정 참여 | 여러 사람에게 영향을 주는 결정(학급 규칙·모의국회 등) | 실제 선거·정당 활동 경험 |
| rule_making | 규칙 만들기 | 새로운 규칙·기준을 정하는 상황 | 법률 제정 실무 경험 |

## 2. Trait Mapping 요약

Seed 5문항 + Backup 5문항 = 10문항 × 5선택지 = 50 Option, **NO_SIGNAL 10개**
(문항당 1개).

사용한 Trait(13개): `causal_analysis`, `opinion_mediation`,
`independent_judgment`, `verbal_expression`, `opinion_expression`,
`systems_thinking`, `collaboration_preference`, `information_comparison`,
`pattern_finding`, `uncertainty_tolerance`, `change_adaptation`,
`persistence_completion`, `detail_orientation`, `emotional_interpretation`.

## 3. 지시문 준수 확인(가장 엄격하게 검토됨)

- **정치 성향·이념·정당 선호 추론 금지**: 정당명·이념 축 단어("보수", "진보",
  "여당", "야당", "좌파", "우파" 등)를 어디에도 쓰지 않았다
  (`tests/test_context_pack_law_politics.py::NoPoliticalOrMoralFramingTest::
  test_no_political_party_or_ideology_words`로 자동 확인). 실제 정치 이슈(특정
  법안·정책 찬반)도 다루지 않고, 전부 "규칙", "자료", "주장", "결정"처럼 일반화된
  상황만 다룬다.
- **도덕적으로 옳은 답 만들지 않기**: "도덕적으로 옳은", "옳은 행동은" 같은 유도
  문구가 없다(동일 테스트로 확인). 선택지 사이에 우열을 매기는 Rationale도
  작성하지 않았다 — 전부 "실제로 있을 법한 행동"으로만 서술.
- **규칙 충돌·자료 해석·서로 다른 주장·공공 의사결정 활용**: 5개 Anchor 중
  4개가 이 항목에 정확히 대응하고, `rule_making`(규칙 만들기)을 5번째로
  추가했다 — 공공 의사결정과 자연스럽게 이어지는 후속 상황이라 판단했다.

## 4. 검수자가 특히 봐야 할 지점

1. `rule_conflict` Backup에서 `find_exception_case`("예외가 인정될 수 있는
   경우인지 살펴본다") → `systems_thinking` 매핑이 causal_analysis와 겹쳐 보일
   여지가 있다 — "예외 상황을 구조적으로 따져보는 것"으로 구분했다.
2. `public_decision` Backup의 `listen_complaint` → `emotional_interpretation`
   매핑이 이 Context에서 자연스러운지(공공 의사결정 상황에서 감정 해석 Trait를
   쓰는 게 다른 매핑 관례와 맞는지) 재검토 필요 — game/media/school_life에서는
   이 Trait가 주로 친구 관계 Anchor에서만 쓰였다.
3. **가장 중요한 검토 항목**: `rule_conflict`·`differing_claims` Anchor의 모든
   질문·선택지가 실제로 "가치중립적으로 읽히는지"는 텍스트 휴리스틱만으로는
   보장할 수 없다 — 사람 검수자가 반드시 전체 문항을 다시 읽고 판단해야 한다.

## 5. Direct Probe 후보(미구현, 아이디어만)

- `emotional_interpretation`을 `public_decision` Anchor에서 더 직접적으로
  관찰하는 Direct Probe 후보 — "결정에 반대하는 사람의 입장에서 무엇이 힘들지
  생각해보는가" 같은 질문이 후보가 될 수 있다. 실제 Blueprint 작성은 이번 범위
  밖.
