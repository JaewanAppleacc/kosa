# art_design(미술·디자인) Context Pack — Mapping 감사 초안

담당 브랜치: `context-pack-lifestyle`. 이 문서는 `src/data/context_packs/art_design.py`의
질문·Trait Mapping을 사람이 검수할 수 있도록 요약한 초안이다. **자동 승인된 항목은
없다** — `data/reviews/context_packs/art_design_review_status.json`의 11개 Key는
전부 `reviewer_1_status: "TBD"`다.

## 1. Anchor 5개

| anchor_id | label | 상황 | forbidden_assumptions |
|---|---|---|---|
| visual_appreciation | 작품 감상 | 그림·디자인 작품을 보는 상황 | 미술관·전시 관람 경험, "좋아한다"→표현 능력 추론 |
| direct_creation | 직접 그리기·만들기 | 직접 그리거나 만들어야 하는 상황 | 미술 학원·전공 교육 경험, 그림 실력 평가 |
| revision_feedback | 구성 수정·피드백 반영 | 결과물에 피드백을 받는 상황 | 공식 발표·전시 경험 |
| planning_composition | 구도·컨셉 기획 | 만들기 전 구도·컨셉을 정하는 상황 | 디자인 정규 교육 경험 |
| tool_material_choice | 도구·재료 활용 | 작업 도구·프로그램·재료를 고르는 상황 | 고가 장비·프로그램 구매 경험 |

## 2. Trait Mapping 요약

Seed 5문항 + Backup 5문항 = 10문항 × 5선택지 = 50 Option. **NO_SIGNAL 14개** —
"눈으로 보고 넘어간다", "손에 익은 방식을 계속 쓴다"류의 반응은 특정 Trait의 직접
근거로 보기 약하다고 판단해 억지로 매핑하지 않았다.

사용한 Trait(14개): `aesthetic_sensitivity`, `information_comparison`,
`creative_ideation`, `visual_expression`, `persistence_completion`,
`novelty_seeking`, `detail_orientation`, `change_adaptation`, `opinion_expression`,
`independent_judgment`, `planning`, `systems_thinking`, `uncertainty_tolerance`,
`tool_utilization`.

## 3. 지시문 준수 확인(핵심 규칙)

- **작품 감상을 visual_expression으로 연결 금지**: `visual_appreciation` Anchor의
  질문 10개(Seed+Backup) 어디에도 `visual_expression`이 등장하지 않는다. 감상
  자체는 `aesthetic_sensitivity`(색·구도를 왜 그렇게 됐는지 뜯어보는 감식)·
  `information_comparison`(비슷한 작품 찾아보기)·`creative_ideation`(아이디어
  떠올리기)까지만 연결했다. "다른 사람에게 설명하고 싶어진다"는 표현하고 싶은
  *마음*은 있지만 실제 표현 행동이 드러나지 않아 NO_SIGNAL로 뒀다.
- **`visual_expression`은 실제 표현 행동이 있을 때만**: `direct_creation`
  Anchor("머릿속 이미지를 실제로 그려서 표현해본다")에서만 등장한다. 이 두 규칙은
  `tests/test_context_pack_art_design.py::AppreciationNotMappedToVisualExpressionTest`
  로 코드 수준에서 강제한다(감상 Anchor는 절대 매핑 못 하고, `visual_expression`은
  `direct_creation` Anchor 밖에서 못 나오게).
- **직접 표현·구성·수정 행동이 있을 때만 관련 Trait 연결**: `revision_feedback`
  Anchor는 "피드백을 반영해서 다시 바꿔본다"(change_adaptation), "세부를 하나하나
  고친다"(detail_orientation)처럼 실제 수정 행동만 다룬다.
- **그림 실력 평가 금지**: "그림을 잘", "그림 실력이" 같은 표현 없음
  (`ForbiddenAssumptionTextTest`로 확인). Trait는 전부 시도·수정·계획 같은 태도이지
  완성도 수준이 아니다.
- **예체능 진로 추천 제외 정책과 Context 질문 유지 혼동 금지**: 이 Pack은 전공
  Matching 정책(A 소유, Pack 밖)과 무관하게 5개 Anchor·질문을 독립적으로 완결한다 —
  Pack 자체에는 "예체능 학과 추천 대상 제외"에 해당하는 로직이나 조건부 게이팅이
  없다(그 정책은 전공 Matching 단계에서 별도로 적용되는 것이지 이 Pack이 관여할
  범위가 아니다).

## 4. 검수자가 특히 봐야 할 지점

1. `expression_choice`류 문구는 이 Pack이 아니라 `fashion_beauty`에 있다(혼동 방지
   메모) — art_design 쪽 `visual_expression`은 `direct_creation` Seed/Backup
   2문항에만 있다. 이 좁은 범위가 실제 서비스에서 충분한 관찰 빈도를 주는지 검토
   필요.
2. `tool_material_choice` Seed의 `care_more_about_result`("도구보다 결과물 자체에
   더 관심이 간다")를 NO_SIGNAL로 뒀는데, 이게 오히려 결과 중심적 태도를 보여주는
   신호로 볼 여지가 있는지 검토 필요.
3. `planning_composition`과 `direct_creation` 둘 다 `novelty_seeking`을 쓴다 —
   Pack 전체에서 이 Trait가 과다 노출되지 않는지(다른 Context Pack과 합쳐졌을 때) A가
   Trait Coverage Matrix 관점에서 확인 필요.

## 5. Direct Probe 후보(미구현, 아이디어만)

- `aesthetic_sensitivity`를 더 직접적으로 관찰하는 Direct Probe 후보 — "비슷해
  보이는 두 이미지 중 어떤 게 더 나은지 이유를 대야 한다면"류 질문이 후보가 될 수
  있다. 실제 `V2DirectProbeBlueprint` 작성은 이번 범위 밖이라 만들지 않았다.
