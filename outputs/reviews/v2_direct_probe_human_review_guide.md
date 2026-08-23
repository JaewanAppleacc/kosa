# V2 Direct Probe Human Review Guide

2026-08-23 Trait Ontology v2(2.2단계 §17, 2.3단계 §4). 70행 Worksheet(`v2_direct_probe_question_review.md`)를 대신하지 않는다 — 그 Worksheet는 Option 단위(PRIMARY·RELATED·NO_SIGNAL Mapping 타당성)로 더 세밀하게 검토할 때 쓰고, 이 문서는 질문(Trait) 단위로 빠르게 훑어보는 용도다(Exploration 후보 선택 규칙, 사회적 바람직성, 질문 간 의미 중복, 상황적 Trade-off, Target 길이·구체성). `reviewer_1_status`/`reviewer_2_status`/`final_status`는 `data/reviews/v2_direct_probe_question_review_status.json`을 그대로 읽어온 값이다 — 이 스크립트는 그 파일을 절대 쓰지 않는다(사람이 직접 그 JSON을 채워야 값이 바뀐다). `final_status`는 두 검토자 상태로부터 항상 다시 계산한다: 둘 다 APPROVE일 때만 TEAM_REVIEWED, 하나라도 REVISE/HOLD면 REVIEW_REQUIRED, 그 외(TBD 남음)는 DRAFT다. 두 명 모두 APPROVE인 질문만 `team_reviewed`로 승격하고, 그다음에만 v2 Career Profile 표시를 진행한다.

## systems_thinking (구조적 사고)

**정의**: 어떤 요소 하나가 바뀌었을 때, 그 변화가 다른 요소·역할과 어떻게 서로 얽혀 영향을 주는지 살펴보는 성향. 원인 하나를 깊게 파는 것(causal_analysis)이 아니라 '여러 요소 사이의 관계'를 본다.

**인접 Trait와의 차이**:
- causal_analysis: '왜 이 일이 일어났는가'(원인 하나)에 집중 — systems_thinking은 '이 변화가 다른 곳에 어떤 영향을 주는가'(관계망)에 집중한다.
- planning: '앞으로 어떻게 할지 순서를 짠다'는 행동이지, 요소 간 영향 관계를 짚어보는 행동이 아니다.
- pattern_finding: '반복되는 규칙'을 찾는 행동이지, '지금 이 변화의 파급 효과'를 보는 행동이 아니다.

**질문 2개**:

**systems_thinking_game_v1** (Context: game, Frame: new_tool)

> 게임을 하다가 예상하지 못한 새로운 상황이나 요소를 마주치면 가장 먼저 무엇을 하나요?

| role_id | 선택지 | Mapping | NO_SIGNAL 이유 |
|---|---|---|---|
| st_ripple_check | 그 요소가 다른 부분과 어떻게 연결되어 영향을 주는지 살펴본다 | **TARGET(systems_thinking)** | - |
| st_reason_first | 왜 이런 상황이 생겼는지 이유부터 생각해본다 | TRAIT_SIGNAL(causal_analysis) | - |
| st_try_it | 일단 직접 부딪혀보면서 알아간다 | TRAIT_SIGNAL(immediate_execution) | - |
| st_compare_items | 다른 공략이나 정보를 찾아서 비교해본다 | TRAIT_SIGNAL(information_comparison) | - |
| st_ask_team | 당장은 넘어가고 나중에 다시 생각해본다 | NO_SIGNAL | 지금 판단을 미루는 행동일 뿐 특정 Core Trait를 직접 확인할 만큼 근거가 명확하지 않다 |

**systems_thinking_school_life_v1** (Context: school_life, Frame: unexpected_result)

> 이번 주 시험공부 계획을 세워뒀는데 한 과목의 시험 범위가 갑자기 바뀌면 가장 먼저 어떻게 하나요?

| role_id | 선택지 | Mapping | NO_SIGNAL 이유 |
|---|---|---|---|
| st_map_impact | 이 변화가 다른 과목 공부 계획에 어떻게 영향을 주는지 살펴본다 | **TARGET(systems_thinking)** | - |
| st_replan | 남은 공부 시간과 순서를 처음부터 다시 짠다 | TRAIT_SIGNAL(planning) | - |
| st_adapt_now | 원래 하려던 계획은 미뤄두고 바뀐 범위부터 바로 공부한다 | TRAIT_SIGNAL(change_adaptation) | - |
| st_check_mood | 바뀐 범위에서 무엇이 정확히 달라졌는지 하나하나 확인한다 | TRAIT_SIGNAL(detail_orientation) | - |
| st_state_view | 범위가 너무 갑자기 바뀌었다는 내 생각을 선생님께 직접 말씀드린다 | TRAIT_SIGNAL(opinion_expression) | - |

**검토자가 확인할 질문**:
- Target 선택지가 '영향을 주고받는 관계'를 실제로 묻고 있는가, 아니면 단순히 '전체를 본다'는 막연한 표현에 그치는가?
- distractor 중 planning/causal_analysis로 매핑된 선택지가 실제로 systems_thinking으로도 읽힐 만큼 표현이 겹치지는 않는가?

**검토 상태** (`data/reviews/v2_direct_probe_question_review_status.json`에서 읽음, reviewer_*_status는 APPROVE/REVISE/HOLD/TBD 중 하나):

| blueprint_id | reviewer_1_status | reviewer_1_comment | reviewer_2_status | reviewer_2_comment | final_status | resolution_note |
|---|---|---|---|---|---|---|
| systems_thinking_game_v1 | TBD | 게임이나 드라마 영화같이 장르가 나뉘는 카테고리들은 선호하는 장르를 먼저 물어보고 장르에 따라 질문을 달리해야될 것같아 게임 중에서도 협동형 게임이 있고, 혼자 플레이하는 게임이 있고 장르가 다양해서 한 질문이 모든 장르를 포괄하긴 어려운것같아 | TBD | - | DRAFT | - |
| systems_thinking_school_life_v1 | TBD | - | TBD | - | DRAFT | - |

---

## detail_orientation (세부 주의)

**정의**: 작은 오류·조건·차이까지 하나하나 확인하는 성향. '전체적으로 훑어본다'가 아니라 '세부 하나하나를 놓치지 않는다'는 행동으로 드러난다.

**인접 Trait와의 차이**:
- information_comparison: 여러 정보를 비교하는 행동이지, 하나의 결과물 안에서 세부 오류를 찾는 행동과는 다르다.
- planning: 우선순위를 정하는 행동이지, 세부 정확성을 확인하는 행동이 아니다.
- pattern_finding: '반복되는 패턴'을 찾는 것과 '세부 오류'를 찾는 것은 둘 다 '자세히 본다'는 인상을 주지만 목적이 다르다 — 전자는 규칙성, 후자는 정확성이다.

**질문 2개**:

**detail_orientation_media_v1** (Context: media, Frame: problem_check)

> 영화·드라마·공연 같은 작품을 보고 난 뒤 다시 떠올려보는 부분은 무엇인가요?

| role_id | 선택지 | Mapping | NO_SIGNAL 이유 |
|---|---|---|---|
| do_scan_errors | 대사나 장면 속 작은 단서·복선을 다시 짚어본다 | **TARGET(detail_orientation)** | - |
| do_overall_flow | 이 감독이나 작가의 다른 작품에서도 비슷하게 반복되는 연출이 있었는지 떠올려본다 | TRAIT_SIGNAL(pattern_finding) | - |
| do_ask_feedback | 같이 본 사람과 어떤 장면이 좋았는지 이야기를 나눈다 | NO_SIGNAL | 의견이나 반응을 구하는 행동으로, 협업 선호인지 단순한 반응 확인인지 문맥만으로 구분하기 어렵다 |
| do_visual_check | 화면 구도나 무대·음악 연출이 인상 깊었던 순간을 떠올린다 | TRAIT_SIGNAL(visual_expression) | - |
| do_compare_ref | 비슷한 장르의 다른 작품과 어떤 점이 다른지 비교해본다 | TRAIT_SIGNAL(information_comparison) | - |

**detail_orientation_school_life_v1** (Context: school_life, Frame: limited_time_priority)

> 수행평가 결과물을 제출하기 직전인데 시간이 얼마 없다면 무엇을 우선 확인하나요?

| role_id | 선택지 | Mapping | NO_SIGNAL 이유 |
|---|---|---|---|
| do_check_conditions | 촉박해도 조건을 하나하나 놓치지 않는지 확인한다 | **TARGET(detail_orientation)** | - |
| do_finish_first | 일단 끝까지 마무리부터 한다 | TRAIT_SIGNAL(persistence_completion) | - |
| do_priority_pick | 가장 중요한 부분부터 순서를 정한다 | TRAIT_SIGNAL(planning) | - |
| do_quick_submit | 지금 상태로 바로 제출한다 | TRAIT_SIGNAL(immediate_execution) | - |
| do_ask_help | 선생님이나 친구에게 확인을 부탁한다 | NO_SIGNAL | 정보를 묻거나 확인하는 행동일 뿐, 역할을 나눠 함께 해결하는 협업 행동이라는 근거가 약하다 |

**검토자가 확인할 질문**:
- Target 선택지가 '시간이 더 들어도'/'촉박해도' 같은 Trade-off를 포함해 무조건 좋은 답처럼 보이지 않는가?
- NO_SIGNAL로 바뀐 선택지(예: do_visual_check)가 정말 detail_orientation도 visual_expression도 아닌 애매한 확인 행동으로 읽히는가, 아니면 실제로는 다른 Trait가 강하게 느껴지는가?

**검토 상태** (`data/reviews/v2_direct_probe_question_review_status.json`에서 읽음, reviewer_*_status는 APPROVE/REVISE/HOLD/TBD 중 하나):

| blueprint_id | reviewer_1_status | reviewer_1_comment | reviewer_2_status | reviewer_2_comment | final_status | resolution_note |
|---|---|---|---|---|---|---|
| detail_orientation_media_v1 | TBD | 내가 말한 미디어는 이런 편집이나 제출의 느낌보다는 영화,드라마,유튜브,뮤지컬,공연 등의 문화생활을 말한거였어 | TBD | - | DRAFT | - |
| detail_orientation_school_life_v1 | TBD | - | TBD | - | DRAFT | - |

---

## persistence_completion (지속·완수)

**정의**: 결과가 잘 안 나와도 같은 목표를 포기하지 않고 끝까지 이어가는 성향. '방법을 바꾼다'가 아니라 '목표 자체를 그대로 유지한 채 시도를 계속한다'는 행동이다.

**인접 Trait와의 차이**:
- planning: 계획을 세우는 행동과 그 계획을 끝까지 밀어붙이는 행동은 다르다.
- change_adaptation: persistence_completion의 반대 방향처럼 보일 수 있지만, 이 두 Trait를 직접 대립시키는 문항은 만들지 않는다(단순 목표 포기는 NO_SIGNAL로 처리했다).

**질문 2개**:

**persistence_completion_game_v1** (Context: game, Frame: unexpected_result)

> 어려운 목표나 도전에서 계속 뜻대로 안 될 때 무엇을 하나요?

| role_id | 선택지 | Mapping | NO_SIGNAL 이유 |
|---|---|---|---|
| pc_keep_going | 잘 안 나와도 다른 목표로 넘어가지 않고 끝까지 이어간다 | **TARGET(persistence_completion)** | - |
| pc_analyze_fail | 왜 잘 안 풀리는지 원인을 분석한다 | TRAIT_SIGNAL(causal_analysis) | - |
| pc_take_break | 그 목표 대신 지금 상황에 맞는 다른 목표로 바꾼다 | NO_SIGNAL | 목표를 다른 것으로 바꾸는 행동으로, 상황에 맞춰 방식을 능동적으로 바꾸는 change_adaptation의 직접 근거로 보기엔 단순한 목표 포기·교체에 가깝다 |
| pc_watch_others | 다른 사람들은 어떻게 하는지 찾아본다 | TRAIT_SIGNAL(information_comparison) | - |
| pc_ask_help | 온라인이나 주변에 도움을 요청한다 | NO_SIGNAL | 정보를 묻거나 확인하는 행동일 뿐, 역할을 나눠 함께 해결하는 협업 행동이라는 근거가 약하다 |

**persistence_completion_school_life_v1** (Context: school_life, Frame: longest_focus)

> 시험공부처럼 길고 지루한 학업 활동을 할 때 어떤 부분에 가장 오래 매달리나요?

| role_id | 선택지 | Mapping | NO_SIGNAL 이유 |
|---|---|---|---|
| pc_finish_through | 시간이 걸려도 끝까지 마무리하는 데 가장 오래 매달린다 | **TARGET(persistence_completion)** | - |
| pc_plan_stage | 처음 계획을 세우는 데 가장 오래 매달린다 | TRAIT_SIGNAL(planning) | - |
| pc_detail_stage | 세부 내용을 확인하는 데 가장 오래 매달린다 | TRAIT_SIGNAL(detail_orientation) | - |
| pc_creative_stage | 정리한 내용을 보기 좋게 꾸미는 데 가장 오래 매달린다 | TRAIT_SIGNAL(visual_expression) | - |
| pc_team_stage | 함께 공부할 사람을 구하고 진도를 맞추는 데 가장 오래 매달린다 | TRAIT_SIGNAL(collaboration_preference) | - |

**검토자가 확인할 질문**:
- Target 선택지('결과가 잘 안 나오고... 시간이 늦어져도')가 여전히 자연스러운 한국어 문장으로 읽히는가, Trade-off 문구가 어색하게 붙지는 않았는가?
- pc_take_break(NO_SIGNAL)이 실제로 change_adaptation의 근거가 되기엔 약하다는 판단에 동의하는가?

**검토 상태** (`data/reviews/v2_direct_probe_question_review_status.json`에서 읽음, reviewer_*_status는 APPROVE/REVISE/HOLD/TBD 중 하나):

| blueprint_id | reviewer_1_status | reviewer_1_comment | reviewer_2_status | reviewer_2_comment | final_status | resolution_note |
|---|---|---|---|---|---|---|
| persistence_completion_game_v1 | TBD | - | TBD | - | DRAFT | - |
| persistence_completion_school_life_v1 | TBD | - | TBD | - | DRAFT | - |

---

## uncertainty_tolerance (불확실성 감내)

**정의**: 결과를 예측할 수 없는 상태 자체를 크게 불안해하지 않고 받아들이며 진행하는 성향. '일단 빠르게 시도한다'(속도, immediate_execution)와는 다른 축이다.

**인접 Trait와의 차이**:
- immediate_execution: '정보가 부족해도 빠르게 움직인다'는 속도의 문제이지, '결과를 몰라도 괜찮다'는 감내의 문제와는 다르다.
- change_adaptation: 상황이 바뀐 뒤 대응하는 행동이지, 애초에 불확실한 상태를 받아들이는 행동과는 다르다.

**질문 2개**:

**uncertainty_tolerance_game_v1** (Context: game, Frame: new_tool)

> 결과를 전혀 예측할 수 없는 새로운 선택지가 주어지면 어떻게 하나요?

| role_id | 선택지 | Mapping | NO_SIGNAL 이유 |
|---|---|---|---|
| ut_proceed_calm | 결과가 어떻게 나올지 몰라도 그 상태를 그대로 받아들이고 계속 진행한다 | **TARGET(uncertainty_tolerance)** | - |
| ut_try_now | 정보가 충분히 모이기 전이라도 일단 지금 바로 움직인다 | TRAIT_SIGNAL(immediate_execution) | - |
| ut_research_first | 먼저 관련 정보를 찾아본다 | TRAIT_SIGNAL(information_comparison) | - |
| ut_ask_others | 다른 사람들의 의견이나 후기를 먼저 찾아본다 | NO_SIGNAL | 의견이나 반응을 구하는 행동으로, 협업 선호인지 단순한 반응 확인인지 문맥만으로 구분하기 어렵다 |
| ut_plan_ahead | 선택하기 전에 여러 경우를 미리 따져보고 계획을 세운다 | TRAIT_SIGNAL(planning) | - |

**uncertainty_tolerance_school_life_v1** (Context: school_life, Frame: conflicting_opinions)

> 다음 학기 선택과목 신청 마감이 다가왔는데, 관심 학과와 과목에 대한 정보를 아직 충분히 찾지 못했다면 어떻게 하나요?

| role_id | 선택지 | Mapping | NO_SIGNAL 이유 |
|---|---|---|---|
| ut_decide_now | 확실한 정보가 없어도 불안해하지 않고 지금 아는 것만으로 신청한다 | **TARGET(uncertainty_tolerance)** | - |
| ut_wait_more | 신청 기한을 최대한 늦추면서 정보를 더 찾아본다 | NO_SIGNAL | 기한을 늦추는 행동일 뿐 일정을 짜거나 순서를 정하는 것 같은 실제 계획 행동이 드러나지 않아 planning의 직접 근거로 보기 어렵다 |
| ut_ask_teacher | 진로 선생님이나 선배에게 먼저 물어본다 | NO_SIGNAL | 정보를 묻거나 확인하는 행동일 뿐, 역할을 나눠 함께 해결하는 협업 행동이라는 근거가 약하다 |
| ut_pick_safe | 그나마 확실하게 알려진 과목·학과 정보를 비교해서 고른다 | TRAIT_SIGNAL(information_comparison) | - |
| ut_voice_concern | 정보가 부족해서 걱정된다는 내 생각을 선생님께 말씀드린다 | TRAIT_SIGNAL(opinion_expression) | - |

**검토자가 확인할 질문**:
- ut_plan_ahead(재작성 후 '여러 경우를 미리 따져보고 계획을 세운다')가 순수한 planning 행동으로 읽히는가, 여전히 불확실성 회피처럼 읽히지는 않는가?
- ut_wait_more(NO_SIGNAL)이 실제로는 계획 행동(planning)에 더 가깝다고 보이지는 않는가?

**검토 상태** (`data/reviews/v2_direct_probe_question_review_status.json`에서 읽음, reviewer_*_status는 APPROVE/REVISE/HOLD/TBD 중 하나):

| blueprint_id | reviewer_1_status | reviewer_1_comment | reviewer_2_status | reviewer_2_comment | final_status | resolution_note |
|---|---|---|---|---|---|---|
| uncertainty_tolerance_game_v1 | TBD | - | TBD | - | DRAFT | - |
| uncertainty_tolerance_school_life_v1 | TBD | - | TBD | - | DRAFT | - |

---

## opinion_expression (의견 표명)

**정의**: 생각이 다를 때 자신의 의견을 분명하게 말로 표현하는 성향. '표현 여부'를 보는 것이지 '그 판단이 옳은가'를 보지 않는다.

**인접 Trait와의 차이**:
- opinion_mediation: 서로 다른 의견 사이에서 절충점을 찾는 행동이지, 자기 의견을 표명하는 행동과는 다르다.
- independent_judgment: '스스로 판단의 기준을 정하는가'를 보는 Trait이고, opinion_expression은 '그 생각을 실제로 말로 표현하는가'를 본다 — 판단과 표현은 별개다.

**질문 2개**:

**opinion_expression_media_v1** (Context: media, Frame: conflicting_opinions)

> 같은 작품을 본 친구와 인물의 선택이나 결말에 대한 생각이 다를 때 어떻게 하나요?

| role_id | 선택지 | Mapping | NO_SIGNAL 이유 |
|---|---|---|---|
| oe_state_view | 분위기가 어색해져도 내 생각을 먼저 분명하게 말한다 | **TARGET(opinion_expression)** | - |
| oe_mediate | 서로 다른 해석을 절충할 지점을 찾아본다 | TRAIT_SIGNAL(opinion_mediation) | - |
| oe_gather_data | 다른 사람들은 어떻게 해석했는지 리뷰나 반응을 찾아본다 | TRAIT_SIGNAL(information_comparison) | - |
| oe_follow_majority | 다수가 동의하는 해석을 따른다 | NO_SIGNAL | 다수 해석을 따르는 행동으로, 협업 선호인지 단순한 순응·갈등 회피인지 문맥만으로 구분하기 어렵다 |
| oe_read_mood | 친구가 왜 그렇게 생각하는지 먼저 이해해보려 한다 | TRAIT_SIGNAL(emotional_interpretation) | - |

**opinion_expression_school_life_v1** (Context: school_life, Frame: others_reaction)

> 조별 활동에서 내 생각이 다른 사람들과 다르면 실제로 어떻게 하나요?

| role_id | 선택지 | Mapping | NO_SIGNAL 이유 |
|---|---|---|---|
| oe_speak_role | 다른 사람들 반응이 걱정되더라도 내 생각을 먼저 분명하게 말한다 | **TARGET(opinion_expression)** | - |
| oe_listen_role | 다른 사람이 왜 그렇게 생각하는지 먼저 들어본다 | TRAIT_SIGNAL(emotional_interpretation) | - |
| oe_organize_role | 전체 의견을 정리해서 다음 단계를 계획한다 | TRAIT_SIGNAL(planning) | - |
| oe_bridge_role | 서로 다른 의견을 절충할 지점을 찾는다 | TRAIT_SIGNAL(opinion_mediation) | - |
| oe_support_role | 일단 다수가 정한 방향에 맞춘다 | NO_SIGNAL | 다수가 정한 방향에 맞추는 행동으로, 협업 선호인지 단순한 순응인지 문맥만으로 구분하기 어렵다 |

**검토자가 확인할 질문**:
- Target 선택지에 추가한 Trade-off('분위기가 어색해질 수 있어도' 등)가 다른 선택지보다 지나치게 길거나 튀어 보이지 않는가?
- oe_follow_majority/oe_support_role(NO_SIGNAL)이 실제로는 collaboration_preference의 근거로 쓸 수 있다고 보이지는 않는가(단순 순응과 협업 선호의 경계 판단)?

**검토 상태** (`data/reviews/v2_direct_probe_question_review_status.json`에서 읽음, reviewer_*_status는 APPROVE/REVISE/HOLD/TBD 중 하나):

| blueprint_id | reviewer_1_status | reviewer_1_comment | reviewer_2_status | reviewer_2_comment | final_status | resolution_note |
|---|---|---|---|---|---|---|
| opinion_expression_media_v1 | TBD | - | TBD | - | DRAFT | - |
| opinion_expression_school_life_v1 | TBD | - | TBD | - | DRAFT | - |

---

## creative_ideation (아이디어 발상)

**정의**: 기존 요소들을 새롭게 조합하거나 새로운 아이디어를 스스로 만들어내는 성향. '새로운 것을 좋아한다'(novelty_seeking, 선호)가 아니라 '새로운 것을 만든다'(생성 행동)는 차이가 있다.

**인접 Trait와의 차이**:
- novelty_seeking: 새로운 것을 '선호'하는 태도이지, 직접 '만들어내는' 행동이 아니다 — 이번 라운드에서 Target 문구를 '조합·생성'으로 명확히 좁혔다.
- pattern_finding: 기존 규칙에서 반복을 찾아 다듬는 행동이지, 새로운 조합을 스스로 만들어내는 행동과는 다르다.

**질문 2개**:

**creative_ideation_media_v1** (Context: media, Frame: first_action)

> 인상 깊게 본 작품의 한 장면이나 결말을 바꿔볼 수 있다면 무엇부터 생각하나요?

| role_id | 선택지 | Mapping | NO_SIGNAL 이유 |
|---|---|---|---|
| ci_new_format | 그 장면을 완전히 다른 전개로 새롭게 상상해본다 | **TARGET(creative_ideation)** | - |
| ci_visual_first | 화면이나 무대를 어떻게 다르게 연출할지부터 생각한다 | TRAIT_SIGNAL(visual_expression) | - |
| ci_research_trend | 비슷하게 결말을 바꾼 다른 작품들을 찾아본다 | TRAIT_SIGNAL(information_comparison) | - |
| ci_plan_steps | 바뀐 이야기가 앞뒤로 자연스럽게 이어지도록 순서를 정리한다 | TRAIT_SIGNAL(planning) | - |
| ci_ask_team | 친구와 이야기를 나누며 같이 아이디어를 발전시킨다 | TRAIT_SIGNAL(collaboration_preference) | - |

**creative_ideation_game_v1** (Context: game, Frame: new_tool)

> 새로운 게임 규칙이나 콘텐츠를 직접 만들 수 있다면 무엇을 하고 싶나요?

| role_id | 선택지 | Mapping | NO_SIGNAL 이유 |
|---|---|---|---|
| ci_invent_rule | 여러 요소를 새롭게 엮어서 다른 방식을 스스로 만들어본다 | **TARGET(creative_ideation)** | - |
| ci_improve_existing | 기존 규칙 중 반복되는 부분을 찾아 다듬는다 | TRAIT_SIGNAL(pattern_finding) | - |
| ci_test_it | 일단 만들어서 바로 실험해본다 | TRAIT_SIGNAL(immediate_execution) | - |
| ci_visual_design | 어떻게 보여줄지 화면 디자인부터 생각한다 | TRAIT_SIGNAL(visual_expression) | - |
| ci_get_feedback | 다른 사람들에게 아이디어를 먼저 이야기해본다 | NO_SIGNAL | 의견이나 반응을 구하는 행동으로, 협업 선호인지 단순한 반응 확인인지 문맥만으로 구분하기 어렵다 |

**검토자가 확인할 질문**:
- ci_invent_rule Target 문구('여러 요소를 새롭게 엮어서')가 pattern_finding(ci_improve_existing, '반복되는 부분을 찾아 다듬는다')과 충분히 구분되는가?
- ci_get_feedback(NO_SIGNAL)이 실제로 collaboration_preference에 가깝다고 보이지는 않는가?

**검토 상태** (`data/reviews/v2_direct_probe_question_review_status.json`에서 읽음, reviewer_*_status는 APPROVE/REVISE/HOLD/TBD 중 하나):

| blueprint_id | reviewer_1_status | reviewer_1_comment | reviewer_2_status | reviewer_2_comment | final_status | resolution_note |
|---|---|---|---|---|---|---|
| creative_ideation_media_v1 | TBD | - | TBD | - | DRAFT | - |
| creative_ideation_game_v1 | TBD | - | TBD | - | DRAFT | - |

---

## independent_judgment (독립적 판단)

**정의**: 지시나 다른 사람의 의견이 모호하거나 자신과 다를 때, 스스로 판단 기준을 세워 행동을 결정하는 성향. '의견을 말하는가'(opinion_expression)가 아니라 '누구의 판단을 따르는가'를 본다.

**인접 Trait와의 차이**:
- opinion_expression: 판단 기준을 세우는 것과 그 생각을 말로 표현하는 것은 다른 행동이다 — 같은 상황에서 둘 다 나올 수 있어 2차 검토 시 특히 비교가 필요하다.
- collaboration_preference: 다른 사람에게 묻고 맞추는 행동은 판단의 주체가 자신이 아니라는 뜻이라 independent_judgment와 반대 방향에 가깝다 — 이번 라운드에 이런 선택지는 collaboration_preference로 억지로 매핑하지 않고 NO_SIGNAL로 처리했다.

**질문 2개**:

**independent_judgment_game_v1** (Context: game, Frame: others_reaction)

> 게임 공략이나 다른 사람의 조언과 내 생각이 다를 때 어떻게 하나요?

| role_id | 선택지 | Mapping | NO_SIGNAL 이유 |
|---|---|---|---|
| ij_own_call | 다른 사람 의견과 달라도 내가 판단한 방식대로 한다 | **TARGET(independent_judgment)** | - |
| ij_follow_guide | 공략을 참고해서 비교한 뒤 따른다 | TRAIT_SIGNAL(information_comparison) | - |
| ij_ask_more | 다른 사람들에게 더 물어본다 | NO_SIGNAL | 정보를 묻거나 확인하는 행동일 뿐, 역할을 나눠 함께 해결하는 협업 행동이라는 근거가 약하다 |
| ij_say_thoughts | 내 생각이 다르다고 먼저 말한다 | TRAIT_SIGNAL(opinion_expression) | - |
| ij_stay_calm | 결과가 확실하지 않아도 크게 신경 쓰지 않고 진행한다 | TRAIT_SIGNAL(uncertainty_tolerance) | - |

**independent_judgment_school_life_v1** (Context: school_life, Frame: problem_check)

> 친한 친구의 말이나 행동이 평소와 달라졌는데 이유를 확실히 알 수 없다면, 다음 행동의 기준을 어떻게 정하나요?

| role_id | 선택지 | Mapping | NO_SIGNAL 이유 |
|---|---|---|---|
| ij_set_own_standard | 다른 설명을 듣기 전에 내가 상황을 보고 판단한 기준대로 행동한다 | **TARGET(independent_judgment)** | - |
| ij_ask_clarify | 친구에게 무슨 일 있는지 직접 물어본다 | NO_SIGNAL | 직접 물어보고 확인하는 행동으로, 협업 선호가 직접 드러난다고 보기보다는 단순한 확인 행동에 가깝다 |
| ij_plan_role | 내가 할 수 있는 것과 기다려야 하는 것을 나눠서 계획을 세운다 | TRAIT_SIGNAL(planning) | - |
| ij_speak_role | 내가 느낀 걱정이나 생각을 친구에게 솔직하게 말한다 | TRAIT_SIGNAL(opinion_expression) | - |
| ij_adapt_role | 친구가 먼저 다르게 대하면 그에 맞춰 내 태도도 바로 바꾼다 | TRAIT_SIGNAL(change_adaptation) | - |

**검토자가 확인할 질문**:
- ij_own_call/ij_set_own_standard(Target)와 ij_say_thoughts/ij_speak_role(opinion_expression) 이 실제로 다른 행동으로 구분돼 읽히는가?
- ij_ask_more/ij_ask_clarify(NO_SIGNAL)를 collaboration_preference로 되돌려야 한다고 보이는 지점이 있는가?

**검토 상태** (`data/reviews/v2_direct_probe_question_review_status.json`에서 읽음, reviewer_*_status는 APPROVE/REVISE/HOLD/TBD 중 하나):

| blueprint_id | reviewer_1_status | reviewer_1_comment | reviewer_2_status | reviewer_2_comment | final_status | resolution_note |
|---|---|---|---|---|---|---|
| independent_judgment_game_v1 | TBD | - | TBD | - | DRAFT | - |
| independent_judgment_school_life_v1 | TBD | - | TBD | - | DRAFT | - |

---

