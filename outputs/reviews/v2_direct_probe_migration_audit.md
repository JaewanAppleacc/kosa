# V2 Direct Probe Migration Audit — Context 재정의(2.5단계)

2026-08-23 Trait Ontology v2(2.5단계) §11. `blueprint_id`/`role_id`는 전부 이전과
동일하게 유지했다 — `data/reviews/v2_direct_probe_question_review_status.json`/
`v2_direct_probe_option_review_status.json`에 저장된 사용자의 기존 검토 메모는
그대로 같은 Key에 남아 있다(별도 마이그레이션·삭제·재작성 없음). 이 문서는 "그
메모가 실제로 어떤 문구 변경으로 이어졌는지"를 사람이 한눈에 확인할 수 있도록
수정 전/후를 나란히 기록한 감사 문서다 — Claude가 스스로 `TEAM_REVIEWED`나
`APPROVE`로 표시하지 않는다. 모든 항목의 검토 상태는 여전히
`data/reviews/*.json`의 실제 값(현재 전부 `TBD`)을 따른다.

## game — systems_thinking_game_v1

| role_id | 수정 전 | 수정 후 | 관련 사용자 메모 | 이유 |
|---|---|---|---|---|
| (질문) | 게임에 새로운 아이템이나 규칙이 추가되면 가장 먼저 무엇을 하나요? | 게임을 하다가 예상하지 못한 새로운 상황이나 요소를 마주치면 가장 먼저 무엇을 하나요? | "게임 중에서도 협동형 게임이 있고, 혼자 플레이하는 게임이 있고 장르가 다양해서 한 질문이 모든 장르를 포괄하긴 어려운것같아" | "아이템·규칙 추가"는 RPG·라이브 서비스 장르 전제라 장르 중립 표현으로 넓혔다 |
| st_compare_items | 기존 아이템들과 비교해본다 (information_comparison) | 다른 공략이나 정보를 찾아서 비교해본다 (information_comparison, 유지) | "기존 아이템들과 비교해보는건 개인의 특성에 따라 갈리는 영역이 아닌 당연한 영역이야" | 단순 눈대중 비교(당연한 행동)를 "능동적으로 정보를 찾아 비교"로 구체화 |
| st_ask_team | 팀원들에게 어떻게 쓸지 물어본다 (NO_SIGNAL) | 당장은 넘어가고 나중에 다시 생각해본다 (NO_SIGNAL, 유지) | "팀원들끼리 같이 하는 게임이 아닌 혼자 하는 게임일 수 도 있어" | 팀 전제를 완전히 제거 — 혼자·함께 플레이하는 학생 모두에게 적용 가능한 표현으로 교체 |

## school_life — systems_thinking_school_life_v1

| role_id | 수정 전 | 수정 후 | 관련 사용자 메모 | 이유 |
|---|---|---|---|---|
| (질문) | 조별 프로젝트에서 한 사람의 역할이나 일정이 갑자기 바뀌면 무엇을 가장 먼저 생각하나요? | 이번 주 시험공부 계획을 세워뒀는데 한 과목의 시험 범위가 갑자기 바뀌면 가장 먼저 어떻게 하나요? | (구두 피드백) "조별활동·그룹 프로젝트 상황에 지나치게 집중하지 않는다" | 조별 편중을 줄이고 학업·공부 영역(학교생활 분포 기준)으로 이동 |
| st_map_impact | 이 변화가 다른 역할과 얽혀 영향을 주는지 짚어본다 (systems_thinking) | 이 변화가 다른 과목 공부 계획에 어떻게 영향을 주는지 살펴본다 (systems_thinking, 유지) | — | 학업 도메인에 맞춰 "역할"을 "공부 계획"으로 교체 |
| st_replan | 남은 일정과 순서를 처음부터 다시 짠다 (planning) | 남은 공부 시간과 순서를 처음부터 다시 짠다 (planning, 유지) | "남은 일정과 순서를 처음부터 다시 짜는건 무조건적으로 1번 선택지인 이 변화가 어떤 영향을 주는지 짚어본 후에야 나올 수 있는 생각인것같아" | st_map_impact 없이도 바로 선택 가능한 독립적 행동으로 재작성(순차 의존 제거) |
| st_adapt_now | 일단 상황에 맞게 바로 대응한다 (change_adaptation) | 원래 하려던 계획은 미뤄두고 바뀐 범위부터 바로 공부한다 (change_adaptation, 유지) | "상황에 맞게 바로 대응한다는 모든 답변을 포괄하는 답변이라 애매한것같아" | 포괄 표현을 구체적인 행동(계획 보류 + 즉시 처리)으로 좁힘 |
| st_check_mood | 역할이 바뀐 친구의 기분을 먼저 살핀다 (emotional_interpretation) | 바뀐 범위에서 무엇이 정확히 달라졌는지 하나하나 확인한다 (detail_orientation로 매핑 변경) | — | 학업 도메인에는 "역할이 바뀐 친구"가 더 이상 없어 emotional_interpretation 근거가 사라짐 — detail_orientation(세부 확인)으로 대체 |
| st_state_view | 내 생각을 팀에 분명하게 말한다 (opinion_expression) | 범위가 너무 갑자기 바뀌었다는 내 생각을 선생님께 직접 말씀드린다 (opinion_expression, 유지) | — | "팀"을 "선생님"으로 교체(조별 전제 제거) |

## media — detail_orientation_media_v1

| role_id | 수정 전 | 수정 후 | 관련 사용자 메모 | 이유 |
|---|---|---|---|---|
| (질문) | 영상이나 자료를 편집해서 제출하기 전에 무엇부터 확인하나요? | 영화·드라마·공연 같은 작품을 보고 난 뒤 다시 떠올려보는 부분은 무엇인가요? | "내가 말한 미디어는 이런 편집이나 제출의 느낌보다는 영화,드라마,유튜브,뮤지컬,공연 등의 문화생활을 말한거였어" | 제작·편집 전제를 완전히 제거하고 감상자 관점으로 전면 재작성 |
| do_scan_errors | 시간이 더 들더라도 작은 오탈자나 어긋난 부분까지 하나하나 짚어본다 (detail_orientation) | 대사나 장면 속 작은 단서·복선을 다시 짚어본다 (detail_orientation, 유지) | 〃 | 편집 오류 확인 → 감상 중 세부 단서·복선 짚기로 대체 |
| do_overall_flow | 예전에 만들었던 것과 비슷하게 반복되는 편집 패턴이 있는지 확인한다 (pattern_finding) | 이 감독이나 작가의 다른 작품에서도 비슷하게 반복되는 연출이 있었는지 떠올려본다 (pattern_finding, 유지) | 〃 | 편집 패턴 → 감독/작가의 반복 연출 패턴으로 대체 |
| do_ask_feedback | 친구에게 먼저 보여주고 의견을 듣는다 (NO_SIGNAL) | 같이 본 사람과 어떤 장면이 좋았는지 이야기를 나눈다 (NO_SIGNAL, 유지) | 〃 | 제작물을 보여주는 상황 → 함께 감상 후 대화로 대체 |
| do_visual_check | 화면 구성과 배치를 다시 살펴본다 (NO_SIGNAL) | 화면 구도나 무대·음악 연출이 인상 깊었던 순간을 떠올린다 (**visual_expression으로 승격**) | 〃 | 편집 재확인(근거 약함) → 감상자로서 능동적으로 시청각 연출에 반응하는 행동(근거 있음)으로 바뀌어 NO_SIGNAL에서 TRAIT_SIGNAL로 전환 |
| do_compare_ref | 참고했던 자료와 다시 비교해본다 (information_comparison) | 비슷한 장르의 다른 작품과 어떤 점이 다른지 비교해본다 (information_comparison, 유지) | 〃 | 원본 자료 대조 → 유사 장르 작품 비교로 대체 |

## school_life — detail_orientation_school_life_v1 (경미한 수정)

| role_id | 수정 전 | 수정 후 | 이유 |
|---|---|---|---|
| (질문) | 과제를 제출하기 직전, 시간이 얼마 없을 때 무엇을 우선 확인하나요? | 수행평가 결과물을 제출하기 직전인데 시간이 얼마 없다면 무엇을 우선 확인하나요? | "과제·수행평가" 영역으로 명확히 고정(학교생활 분포 기준) |

선택지 5개 문구는 변경 없음(이미 팀 전제가 없었다).

## game — persistence_completion_game_v1

| role_id | 수정 전 | 수정 후 | 이유 |
|---|---|---|---|
| (질문) | 어려운 스테이지나 목표에서 계속 실패할 때 무엇을 하나요? | 어려운 목표나 도전에서 계속 뜻대로 안 될 때 무엇을 하나요? | "스테이지"(레벨 기반 장르 전제) 제거 |
| pc_analyze_fail | 왜 계속 실패하는지 원인을 분석한다 (causal_analysis) | 왜 잘 안 풀리는지 원인을 분석한다 (causal_analysis, 유지) | "실패" 대신 장르 중립 표현 |
| pc_ask_help | 같이 하는 친구에게 도움을 요청한다 (NO_SIGNAL) | 온라인이나 주변에 도움을 요청한다 (NO_SIGNAL, 유지) | "같이 하는 친구" 팀 전제 제거 |

## school_life — persistence_completion_school_life_v1

| role_id | 수정 전 | 수정 후 | 이유 |
|---|---|---|---|
| (질문) | 길고 지루한 과제를 할 때 어떤 부분에 가장 오래 매달리나요? | 시험공부처럼 길고 지루한 학업 활동을 할 때 어떤 부분에 가장 오래 매달리나요? | "학업·공부" 영역(학교생활 분포 기준)으로 이동 |
| pc_finish_through | 시간이 걸려도 과제를 끝까지 마무리하는 데 가장 오래 매달린다 | 시간이 걸려도 끝까지 마무리하는 데 가장 오래 매달린다 | "과제" 단어를 빼 학업 전반에 적용되게 함 |
| pc_creative_stage | 결과물을 보기 좋게 꾸미는 데 가장 오래 매달린다 | 정리한 내용을 보기 좋게 꾸미는 데 가장 오래 매달린다 | 학업(정리 노트 등) 맥락에 맞춤 |
| pc_team_stage | 팀원과 역할을 맞추는 데 가장 오래 매달린다 (collaboration_preference) | 함께 공부할 사람을 구하고 진도를 맞추는 데 가장 오래 매달린다 (collaboration_preference, 유지) | 이미 팀이 있다고 전제하지 않고 "구하는" 능동적 행동으로 교체 |

## game — uncertainty_tolerance_game_v1

| role_id | 수정 전 | 수정 후 | 이유 |
|---|---|---|---|
| ut_ask_others | 다른 사람 의견을 먼저 들어본다 (NO_SIGNAL) | 다른 사람들의 의견이나 후기를 먼저 찾아본다 (NO_SIGNAL, 유지) | 실시간 팀원 전제를 없애고 후기 등 비동기 정보로 확장 |

## school_life — uncertainty_tolerance_school_life_v1

| role_id | 수정 전 | 수정 후 | 관련 사용자 메모 | 이유 |
|---|---|---|---|---|
| (질문) | 필요한 정보가 다 모이지 않은 상태에서 결정을 내려야 할 때 어떻게 하나요? | 다음 학기 선택과목 신청 마감이 다가왔는데, 관심 학과와 과목에 대한 정보를 아직 충분히 찾지 못했다면 어떻게 하나요? | (구두 피드백) "필요한 정보가 다 모이지 않은 상태에서 결정을 내려야 할 때 같은 추상적인 표현을 그대로 묻지 않는다" | 작업 지시문이 제시한 예시를 그대로 채택 — 과목·진로 선택 영역 |
| ut_decide_now | 확실하지 않아도 불안해하지 않고 일단 결정하고 진행한다 | 확실한 정보가 없어도 불안해하지 않고 지금 아는 것만으로 신청한다 | 〃 | 새 시나리오(선택과목 신청)에 맞춤 |
| ut_wait_more | 정보가 더 모일 때까지 결정을 미룬다 (NO_SIGNAL) | 신청 기한을 최대한 늦추면서 정보를 더 찾아본다 (NO_SIGNAL, 유지) | 〃 | 〃 |
| ut_ask_teacher | 선생님이나 친구에게 먼저 물어본다 (NO_SIGNAL) | 진로 선생님이나 선배에게 먼저 물어본다 (NO_SIGNAL, 유지) | 〃 | 〃 |
| ut_pick_safe | 그나마 확실한 정보를 비교해서 고른다 (information_comparison) | 그나마 확실하게 알려진 과목·학과 정보를 비교해서 고른다 (information_comparison, 유지) | 〃 | 〃 |
| ut_voice_concern | 불확실하다는 내 생각을 팀에 말한다 (opinion_expression) | 정보가 부족해서 걱정된다는 내 생각을 선생님께 말씀드린다 (opinion_expression, 유지) | 〃 | "팀" 전제 제거 |

## media — opinion_expression_media_v1

| role_id | 수정 전 | 수정 후 | 이유 |
|---|---|---|---|
| (질문) | 콘텐츠 방향에 대해 사람들 의견이 갈리면 어떻게 하나요? | 같은 작품을 본 친구와 인물의 선택이나 결말에 대한 생각이 다를 때 어떻게 하나요? | 감상자 관점 전면 재작성(작품 메모 원문 참고) |
| oe_mediate | 서로 다른 의견을 절충할 지점을 찾는다 (opinion_mediation) | 서로 다른 해석을 절충할 지점을 찾아본다 (opinion_mediation, 유지) | 콘텐츠 제작 방향 → 작품 해석으로 대체 |
| oe_gather_data | 관련 사례를 더 찾아서 비교해본다 (information_comparison) | 다른 사람들은 어떻게 해석했는지 리뷰나 반응을 찾아본다 (information_comparison, 유지) | 〃 |
| oe_follow_majority | 다수가 원하는 방향을 따른다 (NO_SIGNAL) | 다수가 동의하는 해석을 따른다 (NO_SIGNAL, 유지) | 〃 |
| oe_read_mood | 사람들이 왜 그렇게 느끼는지 먼저 살핀다 (emotional_interpretation) | 친구가 왜 그렇게 생각하는지 먼저 이해해보려 한다 (emotional_interpretation, 유지) | 〃 |

## school_life — opinion_expression_school_life_v1

변경 없음. §8 기준상 학교생활 6개 중 조별·그룹활동을 대표하는 유일한 Blueprint로
유지했다(이미 2.2/2.3단계에 역할선호형 문구를 실제 행동형으로 재작성해 놓은
상태였다).

## media — creative_ideation_media_v1

| role_id | 수정 전 | 수정 후 | 이유 |
|---|---|---|---|
| (질문) | 새로운 콘텐츠를 기획할 때 가장 먼저 무엇을 하고 싶나요? | 인상 깊게 본 작품의 한 장면이나 결말을 바꿔볼 수 있다면 무엇부터 생각하나요? | 제작 경험 없이도 답할 수 있는 "결말을 바꿔본다면" 가정 질문으로 대체 |
| ci_visual_first | 화면이나 이미지를 어떻게 꾸밀지부터 생각한다 (visual_expression) | 화면이나 무대를 어떻게 다르게 연출할지부터 생각한다 (visual_expression, 유지) | 〃 |
| ci_research_trend | 요즘 인기 있는 콘텐츠를 찾아본다 (information_comparison) | 비슷하게 결말을 바꾼 다른 작품들을 찾아본다 (information_comparison, 유지) | 〃 |
| ci_plan_steps | 전체 제작 순서를 미리 계획한다 (planning) | 바뀐 이야기가 앞뒤로 자연스럽게 이어지도록 순서를 정리한다 (planning, 유지) | 제작 과정 계획 → 이야기 앞뒤 정리로 대체(제작 전제 제거) |
| ci_ask_team | 팀원들과 아이디어를 같이 나눈다 (collaboration_preference) | 친구와 이야기를 나누며 같이 아이디어를 발전시킨다 (collaboration_preference, 유지) | "팀원" 제거 |

## game — creative_ideation_game_v1

| role_id | 수정 전 | 수정 후 | 이유 |
|---|---|---|---|
| ci_get_feedback | 친구들에게 아이디어를 먼저 물어본다 (NO_SIGNAL) | 다른 사람들에게 아이디어를 먼저 이야기해본다 (NO_SIGNAL, 유지) | "친구들" 팀 전제 제거 |

## game — independent_judgment_game_v1

변경 없음(이미 팀 전제가 없었고, 사용자 메모도 없었다).

## school_life — independent_judgment_school_life_v1

| role_id | 수정 전 | 수정 후 | 이유 |
|---|---|---|---|
| (질문) | 선생님이나 팀의 지시가 명확하지 않을 때, 다음 행동의 기준을 어떻게 정하나요? | 친한 친구의 말이나 행동이 평소와 달라졌는데 이유를 확실히 알 수 없다면, 다음 행동의 기준을 어떻게 정하나요? | 조별 편중을 줄이려 "친구 관계" 영역(학교생활 분포 기준)으로 이동 — 작업 지시문이 제시한 예시를 채택 |
| ij_set_own_standard | 스스로 판단한 기준으로 다음 행동을 정한다 | 다른 설명을 듣기 전에 내가 상황을 보고 판단한 기준대로 행동한다 | 새 시나리오에 맞춤 |
| ij_ask_clarify | 다른 사람에게 먼저 물어보고 기준을 맞춘다 (NO_SIGNAL) | 친구에게 무슨 일 있는지 직접 물어본다 (NO_SIGNAL, 유지) | 〃 |
| ij_plan_role | 전체 일정과 순서부터 다시 계획한다 (planning) | 내가 할 수 있는 것과 기다려야 하는 것을 나눠서 계획을 세운다 (planning, 유지) | "팀 일정" 전제 제거 |
| ij_speak_role | 내가 생각한 기준을 다른 사람들에게 먼저 말한다 (opinion_expression) | 내가 느낀 걱정이나 생각을 친구에게 솔직하게 말한다 (opinion_expression, 유지) | 새 시나리오에 맞춤 |
| ij_adapt_role | 상황이 바뀌면 그때그때 기준을 바꾼다 (change_adaptation) | 친구가 먼저 다르게 대하면 그에 맞춰 내 태도도 바로 바꾼다 (change_adaptation, 유지) | 〃 |

## 2.5.1단계 §10 — Mapping 수정 3건

2.5단계 이후 검수에서 발견된 Mapping 문제 3건을 추가로 수정했다. 이번에도
`blueprint_id`/`role_id`는 전부 그대로 유지했다.

### media — detail_orientation_media_v1 / do_visual_check (§10-A)

| 항목 | 수정 전 | 수정 후 |
|---|---|---|
| 문구 | 화면 구도나 무대·음악 연출이 인상 깊었던 순간을 떠올린다 | (문구 변경 없음) |
| Mapping | visual_expression (TRAIT_SIGNAL) | NO_SIGNAL |

이유: "화면 구도·연출이 인상 깊었던 순간을 떠올린다"는 시각·음향 연출에 대한 관심과
감상을 보여줄 뿐, 학생이 직접 시각적으로 "표현"했다는 근거는 아니다(작업 지시문
지적). 새 Trait를 즉시 추가하지 않고 더 정직한 NO_SIGNAL로 되돌렸다. 이 수정으로
NO_SIGNAL 전체 개수가 13 → 14로 바뀌었다.

### school_life — uncertainty_tolerance_school_life_v1 / ut_decide_now (§10-B)

| 항목 | 수정 전 | 수정 후 |
|---|---|---|
| 문구 | 확실한 정보가 없어도 불안해하지 않고 지금 아는 것만으로 신청한다 | 확인하지 못한 부분이 남아 있어도 지금까지 확인된 정보만으로 신청한다 |
| Mapping | uncertainty_tolerance (TRAIT_SIGNAL, 유지) | uncertainty_tolerance (TRAIT_SIGNAL, 유지) |

이유: 기존 문구는 감정 상태("불안해하지 않고")와 행동("신청한다")을 한 문장에 묶고
있었고, "불안해하지 않고"가 사회적으로 바람직해 보이는 표현이라 이 선택지만 유독
성숙한 답처럼 읽힐 위험이 있었다(작업 지시문 지적). 감정 어휘를 빼고 행동 하나만
남겼다.

### school_life — independent_judgment_school_life_v1 (§10-C, 전면 재설계)

| role_id | 수정 전(2.5단계) | 수정 후(2.5.1단계) | Mapping 변경 |
|---|---|---|---|
| (질문) | 친한 친구의 말이나 행동이 평소와 달라졌는데 이유를 확실히 알 수 없다면, 다음 행동의 기준을 어떻게 정하나요? | 친구들이 추천하는 선택과목이나 동아리가 내가 원래 관심 있던 것과 다를 때, 무엇을 기준으로 결정하나요? | — |
| ij_set_own_standard | 다른 설명을 듣기 전에 내가 상황을 보고 판단한 기준대로 행동한다 | 친구들의 추천과 상관없이, 원래 내가 관심 있던 기준대로 정한다 | independent_judgment(TARGET, 유지) |
| ij_ask_clarify | 친구에게 무슨 일 있는지 직접 물어본다 (NO_SIGNAL) | 친구들이 왜 그 과목·동아리를 추천하는지 이유를 물어본다 (NO_SIGNAL, 유지) | 변경 없음 |
| ij_plan_role | 내가 할 수 있는 것과 기다려야 하는 것을 나눠서 계획을 세운다 (planning) | 내 관심사와 친구들의 추천을 각각 장단점으로 정리해서 비교해본다 (information_comparison) | **planning → information_comparison** |
| ij_speak_role | 내가 느낀 걱정이나 생각을 친구에게 솔직하게 말한다 (opinion_expression) | 원래 어떤 과목·동아리에 관심 있었는지 친구들에게 솔직하게 말한다 (opinion_expression, 유지) | 변경 없음 |
| ij_adapt_role | 친구가 먼저 다르게 대하면 그에 맞춰 내 태도도 바로 바꾼다 (change_adaptation) | 친구들 대부분이 추천하는 쪽으로 따라간다 (NO_SIGNAL, "다수 추종") | **change_adaptation → NO_SIGNAL** |

이유: "친한 친구의 말이나 행동이 평소와 달라졌는데 이유를 확실히 알 수 없다면"은
독립적 판단이 무심하거나 성급한 행동처럼 읽힐 위험이 있었다(작업 지시문 지적).
선택과목·동아리를 친구 추천과 다르게 정하는 더 중립적인 상황으로 바꾸고, 5개
선택지가 독립적 판단(Target)·정보 비교·의견 표현·다수 추종(NO_SIGNAL)을 각각
대표하도록 재설계했다. 이 수정으로 NO_SIGNAL 전체 개수가 14 → 15로 바뀌었다(§10-A와
합쳐 13 → 15).

## 상태

이 문서에 나열된 모든 Blueprint의 `review_status`는 코드에서 여전히 `"draft"`다
(변경 없음). `data/reviews/v2_direct_probe_question_review_status.json`/
`v2_direct_probe_option_review_status.json`의 `reviewer_1_status`/`reviewer_2_status`도
전부 `TBD`로 남아 있다 — Claude가 이번 라운드에서 어떤 항목도 승인 처리하지
않았다. 검수 페이지(Review UI)에서 각 role_id를 열어보면 이 문서의 "수정 전" 문구
대신 사용자가 원래 남긴 메모가 여전히 그 role_id에 그대로 붙어 있는 것을 확인할 수
있다 — 새 문구와 나란히 놓고 "메모가 실제로 반영됐는지"를 재확인하면 된다.
