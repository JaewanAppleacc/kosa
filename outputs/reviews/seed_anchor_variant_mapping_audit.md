# Seed Anchor Variant Mapping 의미 감사 — 2.5.2단계 §8/§9/§14

2026-08-23 Trait Ontology v2(2.5.2단계) §8/§9. 15개 Seed Anchor Variant × 5개
Option = 75개 전체를 아래 기준으로 감사했다.

```text
1. 문장이 해당 Trait 행동을 직접 나타내는가
2. 단순 관심·감상만으로 능력이나 표현 경향을 추론하지 않는가
3. 다른 Trait에 더 가까운 문구가 아닌가
4. 선택지가 사회적으로 바람직한 정답처럼 보이지 않는가
5. Anchor에 맞추면서 원래 Mapping 의미가 변질되지 않았는가
```

이 문서는 검토 참고자료이며, 실제 검토 상태의 정본은
`data/reviews/v2_seed_anchor_question_review_status.json`/
`v2_seed_anchor_option_review_status.json`이다(전부 `TBD`로 시작한다 — Claude가 이
문서를 근거로 어떤 항목도 스스로 승인하지 않았다).

## 수정한 12개 Option

### media / creative_making → visual_expression (5개 전부, §7)

| Anchor | 수정 전 | 수정 후 |
|---|---|---|
| film_drama | 장면의 색감, 구도, 연출 방식을 살펴보는 것 | 인상 깊었던 장면을 다른 구도나 이미지로 직접 표현해보는 것 |
| online_video | 화면 구성이나 자막·색감 같은 표현 방식을 살펴보는 것 | 인상 깊었던 내용을 화면·자막·이미지로 다시 구성해 표현해보는 것 |
| animation_webcontent | 그림체나 장면 연출 방식을 살펴보는 것 | 인상 깊었던 장면이나 인물을 그림·장면 구성으로 직접 표현해보는 것 |
| stage_performance | 무대·조명·음악이 만들어내는 분위기를 살펴보는 것 | 인상 깊었던 장면을 무대·조명·이미지 구성으로 다르게 표현해보는 것 |
| documentary | 화면 구성이나 자료를 보여주는 방식을 살펴보는 것 | 핵심 내용을 도표·이미지·화면 구성으로 직접 정리해 표현해보는 것 |

**이유**: 기존 문구는 "살펴보는 것"(감상/관찰)이라 관심을 보여줄 뿐 학생이 직접
시각적으로 "표현"했다는 근거가 아니었다(감사 기준 1/2 위반 — 이미
detail_orientation_media_v1의 do_visual_check에서도 같은 문제로 2.5.1단계에서
NO_SIGNAL로 되돌린 전례가 있다). "직접 표현해보는 것"으로 바꿔 실제 산출 행동이
드러나게 했다. `primary_trait_delta={"visual_expression": 1}`은 그대로 유지 —
role_id 자체가 감상이 아니라 원래도 "표현"을 의도한 것이었으므로, 문구를 그
의도에 맞게 고쳤다(Mapping을 바꾼 게 아니라 문구를 Mapping에 맞췄다).

**자동 검사**: `forbidden_assumptions` 위반 없음(각 Anchor의 금지 전제 재확인 완료).
**검토 상태**: TBD(사람 재검토 필요 — "표현해보는 것"이라는 가정법 문구가 실제
학생 행동 강도를 과대평가하지 않는지 확인 필요).

### school_life / team_project → collaboration_preference (2개, §9)

| Anchor | 수정 전 | 수정 후 |
|---|---|---|
| course_career | 같은 고민을 하는 친구와 정보를 나누고 함께 알아보는 것 | 같은 고민을 하는 친구와 역할을 나눠 함께 필요한 정보를 알아보는 것 |
| friendship | 친구와 함께 시간을 보내며 관계를 맞춰가는 것 | 친구와 함께 해결할 일이 생기면 역할을 나눠 같이 진행하는 것 |

**이유**: course_career는 "정보를 나누고"가 정보 공유에 가까워 information_comparison과
경계가 흐릿했다(감사 기준 3). friendship은 "시간을 보내며 관계를 맞춰가는 것"이
collaboration_preference(공동 목표를 위한 협업 선호)가 아니라 단순 친밀감 표현에
가까웠다(작업 지시문 직접 지적). 둘 다 "역할을 나눠"라는 명시적 분업 표현을 추가해
공동 작업·역할 분담이 실제로 드러나게 했다.

**자동 검사**: `forbidden_assumptions` 위반 없음(course_career는 "조별"/"팀원",
friendship은 "조별 과제"/"팀 프로젝트" 금지 — 새 문구 모두 통과).
**검토 상태**: TBD.

### school_life / conflict_mediation → opinion_mediation (5개 전부, §9)

| Anchor | 수정 전 | 수정 후 |
|---|---|---|
| academic_study | 공부 방법에 대해 의견이 다를 때 기준을 세우고 맞춰가는 것 | 함께 공부하는 사람들과 방법이 다를 때 공통으로 맞출 수 있는 기준을 찾아 조율하는 것 |
| assignment_evaluation | 과제 방향에 대해 의견이 다를 때 기준을 세우고 맞춰가는 것 | 과제를 함께 준비하는 사람들과 방향이 다를 때 공통으로 맞출 수 있는 기준을 찾아 조율하는 것 |
| course_career | 주변 의견이 서로 다를 때 내 기준을 세우고 정리하는 것 | 부모·교사·친구 의견이 다를 때 공통으로 중요하게 보는 기준을 찾아 조율하는 것 |
| friendship | 서로 다른 생각 사이에서 기준을 세우고 방향을 맞추는 것 | 나와 친구의 생각이 다를 때 서로 받아들일 수 있는 지점을 찾아 조율하는 것 |
| club_activity | 의견이 다를 때 기준을 세우고 방향을 맞추는 것 | 부원들 사이에 의견이 다를 때 다 같이 받아들일 수 있는 방향을 찾아 조율하는 것 |

**이유**: 기존 문구는 전부 "내 기준을 세우고"라는 표현이 있어, 여러 사람의 의견을
조율하는 opinion_mediation보다 "나 혼자 기준을 정하는" independent_judgment에
더 가까워 보였다(감사 기준 3 — 작업 지시문이 course_career를 명시적으로 지적했고,
"동일한 방식으로 나머지도 대조하라"는 지시에 따라 5개 전부를 같은 기준으로
재작성했다). "여러 주체(함께 공부하는 사람들/과제를 함께 준비하는 사람들/부모·
교사·친구/나와 친구/부원들) 의견이 다를 때 공통점을 찾아 조율"하는 패턴으로
통일했다 — 조정 대상이 되는 "복수의 목소리"가 문장에 명시적으로 드러난다.

**자동 검사**: `forbidden_assumptions` 위반 없음.
**검토 상태**: TBD.

## 나머지 63개 Option — 카테고리별 감사 결과(변경 없음)

Trait-Role 조합별로 5개 Anchor Variant 전체를 대조했다. 아래는 변경이 필요 없다고
판단한 근거를 Trait-Role 단위로 요약한 것이다(개별 문구는
`data/reviews/v2_seed_anchor_option_review_status.json`과 짝지어 Review UI의
"Seed Anchor Variant" 탭에서 실제 문구·중립 문구 비교·Mapping Rationale Draft와
함께 확인할 수 있다).

| Context | role_id | Trait | 감사 결과 |
|---|---|---|---|
| game | strategy_analysis | causal_analysis | 5개 전부 "왜 ~했는지 이유를 짚는" 행동이 직접 드러남. 변경 없음. |
| game | quick_execution | immediate_execution | 5개 전부 "직접 시도해보는" 행동이 직접 드러남. 변경 없음. |
| game | team_coordination | collaboration_preference | 5개 전부 실제 의견 조율·역할 분담·상호 도움이 드러남(cooperative_role만 "팀원" 표현 허용). 변경 없음. |
| game | pattern_recognition | pattern_finding | 5개 전부 "반복되는 규칙/단서를 찾아내는" 행동이 직접 드러남. 변경 없음. |
| game | tool_mastery | tool_utilization | 5개 전부 "새로운 도구·기능을 익혀 활용"이 직접 드러남. 변경 없음. |
| media | structure_analysis | causal_analysis | 5개 전부 "왜 이렇게 구성됐는지" 이유 분석이 직접 드러남. 변경 없음. |
| media | creative_making | visual_expression | **5개 전부 수정(위 참고)**. |
| media | audience_reaction | audience_response_prediction | 5개 전부 "사람들이 어떻게 반응할지 예측"이 직접 드러남. 변경 없음. |
| media | character_empathy | emotional_interpretation | 5개 전부 "그 순간 느꼈을 감정을 이해"가 직접 드러남. 변경 없음. |
| media | trend_research | information_comparison | 5개 전부 "비슷한 사례와 비교"가 직접 드러남. 변경 없음. |
| school_life | task_planning | planning | 5개 전부 "미리 계획하고 정리"가 직접 드러남. 변경 없음. |
| school_life | team_project | collaboration_preference | academic_study/assignment_evaluation/club_activity는 이미 "역할을 나누는" 표현이 있어 유지. **course_career·friendship 2개 수정(위 참고)**. |
| school_life | conflict_mediation | opinion_mediation | **5개 전부 수정(위 참고)**. |
| school_life | peer_understanding | emotional_interpretation | 5개 전부 "친구·부원의 생각·상황을 이해"가 직접 드러남. 변경 없음. |
| school_life | adapting_change | change_adaptation | 5개 전부 "상황이 바뀌면 방법·태도를 바꾸는" 행동이 직접 드러남. 변경 없음. |

사회적 바람직성(감사 기준 4)에 대해서는: Seed Question은 5개 Option 전부가 서로
다른 Trait를 가리키는 탐색형 질문이라(Direct Probe처럼 "Target 1개 + 나머지
Distractor/NO_SIGNAL" 구조가 아니다), 어느 한 Option만 유독 도덕적으로 우월해
보이는 구조적 위험 자체가 낮다 — 다만 이는 자동 판정이 아니라 사람이 검수 페이지의
"학생 화면 모드"로 5개를 나란히 읽어보며 최종 확인해야 한다.
