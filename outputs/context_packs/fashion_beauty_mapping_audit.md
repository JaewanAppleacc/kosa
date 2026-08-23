# fashion_beauty(패션·뷰티) Context Pack — Mapping 감사 초안

담당 브랜치: `context-pack-lifestyle`. 이 문서는
`src/data/context_packs/fashion_beauty.py`의 질문·Trait Mapping을 사람이 검수할 수
있도록 요약한 초안이다. **자동 승인된 항목은 없다** —
`data/reviews/context_packs/fashion_beauty_review_status.json`의 11개 Key는 전부
`reviewer_1_status: "TBD"`다.

## 1. Anchor 5개

작업 지시문이 예시로 든 네 축(스타일 조합·정보 비교·상황 적합성·표현 선택)에
`trend_adaptation`(유행 변화 대응)을 더해 5개를 채웠다.

| anchor_id | label | 상황 | forbidden_assumptions |
|---|---|---|---|
| style_combination | 스타일 조합 | 옷차림·스타일을 조합하는 상황 | 특정 브랜드·고가 아이템 소유 |
| info_comparison | 정보 비교·트렌드 탐색 | 옷·뷰티 관련 정보를 찾아보는 상황 | SNS·특정 플랫폼 이용 경험 |
| situational_fit | 상황 적합성 | 행사·면접·모임 등에 맞춰 옷차림을 정하는 상황 | 특정 행사·모임 참석 경험 |
| expression_choice | 표현 선택 | 기분·느낌을 스타일로 표현하는 상황 | 메이크업 등 특정 뷰티 행위 경험, 성별에 따른 표현 방식 |
| trend_adaptation | 유행 변화 대응 | 유행이 계속 바뀌는 상황 | 유행을 따라갈 경제적 여유 |

## 2. Trait Mapping 요약

Seed 5문항 + Backup 5문항 = 10문항 × 5선택지 = 50 Option. **NO_SIGNAL 16개**(5개
Anchor 중 가장 높은 비율) — "특별히 신경 쓰지 않는다", "다른 사람 의견을 참고해서
정한다"류의 반응은 스스로 비교·판단한 행동이 드러나지 않는다고 보아 억지로 매핑하지
않았다.

사용한 Trait(13개): `novelty_seeking`, `creative_ideation`, `detail_orientation`,
`independent_judgment`, `information_comparison`, `causal_analysis`, `planning`,
`change_adaptation`, `uncertainty_tolerance`, `visual_expression`,
`opinion_expression`, `emotional_interpretation`, `personal_goal_priority`.

## 3. 지시문 준수 확인

- **성별·외모·체형 고정관념 금지**: "남자는/여자는/남학생은/여학생은" 같은 표현이
  어디에도 없다(`tests/test_context_pack_fashion_beauty.py::
  ForbiddenAssumptionTextTest.test_does_not_assume_gender`로 확인). `expression_choice`
  Anchor의 forbidden_assumptions에도 "성별에 따라 다른 표현 방식을 기대하지 않는다"를
  명시했다.
- **고가 제품 구매 경험 전제 금지**: "산다/구매한다"가 아니라 "고른다/찾아본다/
  조합한다"로만 물었다. "명품을 사", "비싼 옷을 사" 같은 표현 없음(동일 파일
  `test_does_not_assume_expensive_purchase`로 확인).
- **스타일 조합·정보 비교·상황 적합성·표현 선택 상황 활용**: 4개 Anchor가 정확히
  이 축에 대응하고, 다섯 번째 `trend_adaptation`을 추가로 뒀다.
- **외모 자신감·인기 여부를 Trait로 추론 금지**: "예쁘다", "잘생겼", "몸매가",
  "인기가 많" 같은 표현이 없다(`test_does_not_evaluate_appearance_or_popularity`로
  확인). Trait Mapping은 전부 "어떻게 판단·표현·비교하는가"에 대한 것이지 사회적
  평가를 묻지 않는다 — 예를 들어 `expression_choice`의 `visual_expression`은
  "느낌에 맞게 직접 골라 표현한다"는 행동만 관찰하고, 그 결과가 남에게 어떻게
  받아들여지는지는 묻지 않는다(`emotional_interpretation`은 "다른 사람 반응을
  살피며 조정한다"는 자신의 관찰·조정 행동이지, 인기나 호감도를 스스로 평가하는
  것이 아니다).

## 4. 검수자가 특히 봐야 할 지점

1. `expression_choice`의 `visual_expression` 매핑이 art_design Context의 같은
   Trait와 겹치는 느낌을 주는지 검토 필요 — 두 Context는 서로 다른 Anchor
   (fashion_beauty는 "그날의 느낌을 스타일로 표현", art_design은 "머릿속 이미지를
   그려서 표현")로 구분했지만, Trait Coverage Matrix에서 두 Context가 같은 Trait를
   중복 관찰하는 게 의도된 설계인지 A가 확인해야 한다.
2. NO_SIGNAL 비율(16/50)이 다섯 Pack 중 가장 높다 — "성별·외모 고정관념을 피하려는
   보수적 판단"이 신호 밀도를 낮춘 것인지, 아니면 Anchor·문구를 더 다듬을 여지가
   있는지 검토 필요(특히 `situational_fit`·`info_comparison`은 NO_SIGNAL이 2개씩).
3. `trend_adaptation`은 지시문이 예시로 들지 않은 다섯 번째 Anchor라 검수자가
   범위 적합성을 별도로 판단해야 한다.

## 5. Direct Probe 후보(미구현, 아이디어만)

- `independent_judgment`를 `style_combination` Anchor에서 더 직접적으로 관찰하는
  Direct Probe 후보 — "다른 사람이 안 어울린다고 했는데도 그 조합을 유지할지"류
  질문이 후보가 될 수 있다. 실제 `V2DirectProbeBlueprint` 작성은 이번 범위 밖이라
  만들지 않았다.
