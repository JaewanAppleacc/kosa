# Context 재정의 — 사용자 검수 피드백 보존 문서

2026-08-23 Trait Ontology v2(2.5단계) §1. 이 문서는 사용자가 검수 페이지
(`data/reviews/v2_direct_probe_question_review_status.json`/
`v2_direct_probe_option_review_status.json`)에 직접 남긴 미커밋 메모의 원문과, 이번
라운드 작업 지시문에서 추가로 전달된 구두 피드백을 그대로 보존한다. 사용자 표현의
의미를 바꾸지 않았다 — 아래는 전부 원문 그대로다.

## 작업 시작 시점 Snapshot

작업 시작 직전 두 파일의 SHA-256(git 미커밋 상태):

```text
data/reviews/v2_direct_probe_question_review_status.json
  a66d084e36030b0c6e535d5cb4a14c24a82a980783f6aa0e71f3dd9da85478cd
data/reviews/v2_direct_probe_option_review_status.json
  fe6580611a80573b83d9efd3f52447332e11649ae50dde71b82ce557245ebeed
```

이 두 파일은 이번 라운드에서 전혀 재작성하지 않았다(git reset/checkout/restore
없음, Review JSON 재생성 없음) — 사용자 메모는 그대로 남아 있다.

## 검수 페이지에 직접 저장된 사용자 메모 (JSON 원문)

### 질문 단위 (`v2_direct_probe_question_review_status.json`)

| blueprint_id | reviewer_1_comment (원문) |
|---|---|
| systems_thinking_game_v1 | 게임이나 드라마 영화같이 장르가 나뉘는 카테고리들은 선호하는 장르를 먼저 물어보고 장르에 따라 질문을 달리해야될 것같아 게임 중에서도 협동형 게임이 있고, 혼자 플레이하는 게임이 있고 장르가 다양해서 한 질문이 모든 장르를 포괄하긴 어려운것같아 |
| detail_orientation_media_v1 | 내가 말한 미디어는 이런 편집이나 제출의 느낌보다는 영화,드라마,유튜브,뮤지컬,공연 등의 문화생활을 말한거였어 |

### 선택지 단위 (`v2_direct_probe_option_review_status.json`)

| blueprint_id | role_id | reviewer_1_comment (원문) |
|---|---|---|
| systems_thinking_game_v1 | st_compare_items | 기존 아이템들과 비교해보는건 개인의 특성에 따라 갈리는 영역이 아닌 당연한 영역이야 |
| systems_thinking_game_v1 | st_ask_team | 팀원들끼리 같이 하는 게임이 아닌 혼자 하는 게임일 수 도 있어 |
| systems_thinking_school_life_v1 | st_replan | 남은 일정과 순서를 처음부터 다시 짜는건 무조건적으로 1번 선택지인 이 변화가 어떤 영향을 주는지 짚어본 후에야 나올 수 있는 생각인것같아 |
| systems_thinking_school_life_v1 | st_adapt_now | 상황에 맞게 바로 대응한다는 모든 답변을 포괄하는 답변이라 애매한것같아 |

위 6건 외에는 어떤 항목도 `reviewer_1_comment`/`reviewer_2_comment`/`resolution_note`가
비어 있지 않은 항목이 없었다(전수 확인). `reviewer_1_status`/`reviewer_2_status`는
70개 선택지·14개 질문 전부 `TBD`였다 — 어떤 항목도 승인되지 않은 상태에서 작업을
시작했다.

## 작업 지시문으로 추가 전달된 구두 피드백

검수 페이지 메모 외에, 이번 라운드 작업 지시문 자체에 사용자가 구두로 정리해 전달한
피드백은 다음과 같다(문서 §1 원문 그대로):

### 게임

- 게임은 협동형·개인형·전략·스토리·창작 등 플레이 방식이 다양하다.
- 하나의 팀 게임 상황이 모든 게임 이용자를 포괄할 수 없다.
- "팀원에게 물어본다"는 선택지는 혼자 플레이하는 학생에게 적용되지 않는다.
- "기존 아이템과 비교한다"처럼 누구나 당연히 할 법한 행동은 Trait 변별력이 약하다.
- 게임의 선호 장르 또는 플레이 방식을 먼저 파악한 뒤 질문 Context를 달리할 필요가 있다.

### 미디어

- 사용자가 의도한 미디어는 영상 편집·제작·제출 중심이 아니다.
- 영화·드라마·유튜브·애니메이션·뮤지컬·공연 등 문화생활의 감상과 해석이 중심이다.
- 콘텐츠 제작 경험이 없는 학생도 자연스럽게 답할 수 있어야 한다.
- 제작·편집 상황은 학생이 별도로 제작 경험을 선택한 경우에만 사용할 수 있다.

### 학교생활

- 조별활동·그룹 프로젝트 상황에 지나치게 집중하지 않는다.
- 학업, 공부 방법, 수행평가, 과목 선택, 진로 고민, 친구 관계 등 학생들이 실제로
  고민하는 상황을 더 많이 사용한다.
- "필요한 정보가 다 모이지 않은 상태에서 결정을 내려야 할 때" 같은 추상적인 표현을
  그대로 묻지 않는다.
- 실제 고등학생 상황으로 바꾼다.
- "영향을 파악한다 → 계획을 다시 짠다"처럼 순차적으로 이어지는 행동을 서로 독립된
  선택지로 두지 않는다.
- "상황에 맞게 바로 대응한다"처럼 다른 선택지를 모두 포괄하는 표현을 사용하지 않는다.

## 영향받는 Blueprint와 개선 방향 (요약)

| 피드백 출처 | 영향받는 Blueprint | 개선 방향 |
|---|---|---|
| 게임 장르 다양성(질문 메모) | game 5개 전체 | Context Routing Question으로 선호 방식(Anchor)을 먼저 물은 뒤, 고정 Fallback 문구는 장르 중립으로 재작성 |
| st_compare_items "당연한 행동" | systems_thinking_game_v1 | Trait 변별력 있는 다른 표현으로 교체하거나 NO_SIGNAL 검토 |
| st_ask_team "혼자 하는 게임일 수도" | systems_thinking_game_v1 | 팀 전제를 제거(이미 2.2단계에 NO_SIGNAL로 전환됐으나 문구 자체도 재검토) |
| st_replan 순차 의존 | systems_thinking_school_life_v1 | st_map_impact의 결과로만 나올 수 있는 표현을 제거하고 독립적인 계획 행동으로 재작성 |
| st_adapt_now 포괄 표현 | systems_thinking_school_life_v1 | "상황에 맞게 바로 대응한다"를 구체적인 change_adaptation 행동으로 재작성 |
| 미디어 = 제작이 아니라 감상(질문 메모 + 구두) | detail_orientation_media_v1, opinion_expression_media_v1, creative_ideation_media_v1 | 감상자 관점으로 전면 재작성, 제작·편집은 선택적 하위 경험으로만 남김 |
| 학교생활 = 조별활동 편중 금지(구두) | school_life 6개 전체 | 학업/과제/과목·진로/친구관계로 재분산, 조별활동은 최대 1개로 제한 |

이 표는 실제 수정 내역(문구·Mapping)의 세부 근거를 대신하지 않는다 — 각 Blueprint의
구체적인 수정 전/후 문구는 `outputs/reviews/v2_direct_probe_migration_audit.md`(신규,
§11)에 별도로 기록한다.
