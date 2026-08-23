# Backup Question 전면 감사 — 2.5.3단계 §1/§2/§4/§5/§6/§7/§14

2026-08-23 Trait Ontology v2(2.5.3단계). `_use_backup()`이 Anchor 검증 없이 첫
Backup을 그대로 반환하던 문제(§1/§2)를 고치면서, 6개 Backup 전부를 §4의 9개 기준으로
전수 감사했다. `blueprint_id`/`role_id`(Backup은 `question_id`/`role_id`)는 전부
그대로 유지했다 — 이 문서 작성 시점에 사용자 검토 메모는 아직 이 6개 Backup에는
없었으므로(신규 검수 대상) 보존해야 할 기존 메모는 없다.

## 재현 결과(§1)

수정 전 `_use_backup()`은 Quality Gate를 전혀 거치지 않고 `used_backup_question_ids`에
없는 첫 후보를 그대로 반환했다.

| 사례 | Anchor 금지 전제 | 반환된 Backup | 실제 포함된 금지 표현 |
|---|---|---|---|
| game/story_exploration | 팀원, 경기 순위, 협동 역할 | game_backup_01 | "팀원들과"(질문 문구) |
| media/stage_performance(media_backup_01 사용 후) | 영상 편집, 촬영본 편집 | media_backup_02 | "편집 도구"(문자열 완전 일치는 아니었지만 제작 전제 자체가 미디어 재정의와 충돌) |
| school_life/friendship | 조별 과제, 팀 프로젝트 | school_life_backup_01 | "조별 과제"(질문 문구) |

## 6개 Backup 감사 결과

### game_backup_01

| role_id | 수정 전 | 수정 후 | 이유 |
|---|---|---|---|
| (질문) | 새로운 게임 규칙을 팀원들과 처음 접했을 때, 가장 먼저 하고 싶은 행동은? | 게임에서 새로운 규칙이나 방식을 처음 접했을 때 무엇을 가장 먼저 하나요? | "팀원들과" 전제 제거(§5) |
| role_split | 팀원들과 역할을 나눠서 같이 파악한다 | 다른 사람과 정보나 역할을 나눠 함께 파악한다 | 팀 전제 없이도 collaboration_preference 근거 유지 |

**검토 대상으로 남긴 항목**: role_split이 story_exploration처럼 혼자 플레이하는
상황을 우선하는 Anchor에서는 다소 자연스럽지 않을 수 있다 — 자동 검사로는 걸리지
않는다(금지어를 포함하지 않음). `BackupQuestionApplicability.applicability_reason_draft`에
기록해뒀다.

### game_backup_02

| role_id | 수정 전 | 수정 후 | 이유 |
|---|---|---|---|
| screen_review | 화면 구성을 다시 살펴보며 놓친 게 있는지 본다 (visual_expression) | 그 상황을 그림이나 도표로 직접 표현해서 정리해본다 (visual_expression, 유지) | "살펴본다"는 감상이지 표현 행동이 아니었다(§5·§9) — Mapping은 유지하고 직접 표현 행동으로 재작성 |

### media_backup_01

| role_id | 수정 전 | 수정 후 | 이유 |
|---|---|---|---|
| comment_reading | 댓글이나 반응을 보며 감정을 읽어본다 (emotional_interpretation) | 댓글 속에 담긴 사람들의 감정을 헤아려본다 (emotional_interpretation, 유지) | "댓글을 읽는 행위"와 "감정을 해석하는 행위"를 구분(§6) — 헤아려본다(해석)로 명확화 |

### media_backup_02 (전면 재작성)

| role_id | 수정 전 | 수정 후 | 이유 |
|---|---|---|---|
| (질문) | 콘텐츠를 기획할 때 어떤 부분에 가장 신경 쓰나요? | 인상 깊은 문화 콘텐츠를 본 뒤 더 깊이 알아보고 싶을 때 무엇을 하나요? | 제작·기획 전제가 재정의된 media Context(감상)와 충돌(§6) |
| sequence_plan | 전체 진행 순서를 미리 계획한다 (planning) | 관련 정보를 어떤 순서로 더 찾아볼지 계획한다 (planning, 유지) | 제작 순서 → 탐색 순서로 재구성 |
| visual_layout | 화면 구성과 시각적 배치를 신경 쓴다 (visual_expression) | 인상 깊었던 장면을 직접 그림이나 이미지로 표현해본다 (visual_expression, 유지) | 감상 후 표현 행동으로 재구성 |
| new_editing_tool | 편집 도구의 새로운 기능을 먼저 써본다 (tool_utilization) | 새로운 검색이나 정리 도구를 써서 자료를 모아본다 (tool_utilization, 유지) | "편집" 제거 — 재현 사례의 근본 원인 |
| reference_pattern | 반복되는 좋은 패턴을 참고한다 (pattern_finding) | 비슷한 작품들에서 반복되는 패턴을 찾아본다 (pattern_finding, 유지) | 제작 참고 → 감상 비교로 재구성 |
| team_split | 팀원과 역할을 나눠 함께 만든다 (collaboration_preference) | 친구와 함께 이야기를 나누며 궁금한 점을 알아본다 (collaboration_preference, 유지) | "팀원"·제작 전제 제거 |

### school_life_backup_01

| role_id | 수정 전 | 수정 후 | 이유 |
|---|---|---|---|
| (질문) | 조별 과제에서 의견이 갈릴 때 가장 먼저 하는 행동은? | 학교에서 다른 사람과 생각이 달라 결정을 내려야 할 때 무엇을 가장 먼저 하나요? | 조별 과제 전제를 학교생활 전체로 일반화하지 않도록(§7) |
| other_group_compare | 다른 조는 어떻게 하는지 비교해본다 (information_comparison) | 다른 사람들은 이럴 때 어떻게 하는지 비교해본다 (information_comparison, 유지) | "다른 조" 표현 제거 |
| feelings_care | 친구들의 감정이 상하지 않게 신경 쓴다 (emotional_interpretation) | 함께하는 사람들의 감정이 상하지 않게 신경 쓴다 (emotional_interpretation, 유지) | 친구 관계로 국한하지 않고 동아리·과제 등 다양한 상황을 포괄 |

### school_life_backup_02

| role_id | 수정 전 | 수정 후 | 이유 |
|---|---|---|---|
| anticipate_reaction | 다른 사람들 반응을 미리 예상해본다 (audience_response_prediction) | 이 활동을 발표하거나 공유했을 때 사람들이 어떻게 반응할지 미리 예상해본다 (audience_response_prediction, 유지) | 행동 Context를 더 구체화(§7) |

## Anchor별 Quality Gate 재검사 결과

6개 Backup × (5개 Anchor + 중립) 전부를 `check_backup_candidate()`로 재검사한 결과,
모든 조합이 통과했다(위반 없음) — 6개 Backup 모두
`BackupQuestionApplicability(allowed_anchor_ids=None, excluded_anchor_ids=set())`로
중립 처리했다.

## 상태

이 문서에 나열된 모든 항목의 검토 상태는 `data/reviews/v2_backup_question_review_status.json`/
`v2_backup_option_review_status.json`에서 전부 `TBD`다 — Claude가 이번 라운드에서
어떤 항목도 승인 처리하지 않았다.
