# science(과학탐구) Context Pack — Mapping 감사 초안

담당 브랜치: `context-pack-technical`. `src/data/context_packs/science.py`의
질문·Trait Mapping 요약. **자동 승인된 항목은 없다** —
`data/reviews/context_packs/science_review_status.json`의 11개 Key는 전부
`reviewer_1_status: "TBD"`다.

## 1. Anchor 5개

| anchor_id | label | 상황 | forbidden_assumptions |
|---|---|---|---|
| cause_exploring | 원인 탐색 | 현상이 왜 일어나는지 궁금해하는 상황 | 실험 장비 접근 경험, 정답을 안다는 전제 |
| data_comparing | 자료 비교 | 여러 자료·결과를 비교해 판단하는 상황 | 전문적 통계 지식, 실험 데이터 분석 경험 |
| hypothesis_testing | 가설 확인 | 예상을 세우고 맞는지 확인하는 상황 | 정식 실험 설계 경험 |
| observing | 관찰·기록 | 현상을 꾸준히 지켜보고 기록하는 상황 | 실험 장비를 이용한 정밀 관찰 경험 |
| uncertain_result | 불확실한 결과 다루기 | 결과가 예상과 다르거나 애매한 상황 | 결과가 항상 명확하다는 전제 |

## 2. Trait Mapping 요약

Seed 5문항 + Backup 5문항 = 10문항 × 5선택지 = 50 Option, **NO_SIGNAL 10개**
(문항당 1개).

사용한 Trait(16개): `causal_analysis`, `information_comparison`,
`collaboration_preference`, `pattern_finding`, `change_adaptation`,
`detail_orientation`, `verbal_expression`, `independent_judgment`,
`visual_expression`, `uncertainty_tolerance`, `immediate_execution`, `planning`,
`persistence_completion`, `opinion_mediation`, `opinion_expression`,
`systems_thinking`.

## 3. 지시문 준수 확인

- **과학 지식 정답 문제 금지**: 모든 질문이 "왜/어떻게 반응하는가"를 물을 뿐
  "무엇이 맞는가"를 묻지 않는다 — 정답이 있는 선택지가 없다
  (`tests/test_context_pack_science.py::NoQuizAnswerFormatTest`로 "정답",
  "옳은 것은" 같은 퀴즈 문구 부재를 확인).
- **실험 경험 필수 전제 금지**: "실험", "실험 장비" 대신 "현상", "결과", "자료"처럼
  일상에서도 접할 수 있는 표현만 썼다.
- **원인 탐색·자료 비교·가설·관찰·불확실한 결과 활용**: 5개 Anchor가 그대로
  이 5가지에 대응한다.

## 4. 검수자가 특히 봐야 할 지점

1. `data_comparing` Backup의 `trust_majority`("더 많은 자료가 가리키는 쪽을
   따른다")를 NO_SIGNAL로 처리했는데, 다수를 따르는 것을 `collaboration_preference`
   나 반대로 `independent_judgment` 결여로 볼 여지가 있다 — 초안에서는 "단순
   추종"이라 특정 Trait 근거로 보기 약하다고 판단했다.
2. `uncertain_result` Seed의 `discuss_with_others` → `opinion_mediation` 매핑이
   "결과의 의미를 찾는" 상황에서 opinion_mediation(의견 조정)으로 가는 게
   맞는지, 아니면 `collaboration_preference`가 더 맞는지 재검토 필요.

## 5. Direct Probe 후보(미구현, 아이디어만)

- `uncertainty_tolerance`를 `uncertain_result` Anchor에서 더 직접적으로 관찰하는
  Direct Probe 후보 — "결과가 두 가지로 나뉘어 나올 때 어떻게 결론을 내리는가"
  같은 질문이 후보가 될 수 있다. 실제 Blueprint 작성은 이번 범위 밖.
