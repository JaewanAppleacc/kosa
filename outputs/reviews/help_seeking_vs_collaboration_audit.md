# "질문한다 = 협업" Mapping 전수 감사

2026-08-23 Trait Ontology v2(2.2단계) §8. "친구에게 물어본다"/"도움을 요청한다"/
"의견을 들어본다" 같은 행동이 항상 `collaboration_preference`를 의미하지는 않는다 —
정보만 확인하는 행동과, 역할을 나눠 함께 해결하는 행동은 근거 강도가 다르다.

이번 라운드의 수정 범위는 v2 Direct Probe 14개 질문으로 제한했다(아래 표). Legacy
(Seed/Tail Blueprint/Backup/Conflict Resolution) Mapping은 이번 라운드에서 자동으로
바꾸지 않았다 — 감사 결과만 기록하고 후속 검토 항목으로 남긴다.

## 구분 기준

- **정보만 물어봄** → collaboration 근거 약함(정보 탐색·도움 요청에 가깝다)
- **함께 역할을 나누고 공동으로 해결함** → collaboration 근거 강함
- **피드백을 요청함** → audience(반응 확인)/정보 탐색/협업 중 무엇인지 문맥 검토 필요

## v2 Direct Probe (이번 라운드에 실제로 수정함)

14개 Option을 `collaboration_preference`에서 `NO_SIGNAL`로 바꿨다 — 전부 "정보만
물어봄" 또는 "피드백을 요청함" 패턴이었다(§7 재검토 결과와 동일, `V2ProbeOptionMapping`의
`no_signal_reason`에 각 판단 근거를 남겼다).

| blueprint_id | role_id | 원래 문구 | 유형 |
|---|---|---|---|
| systems_thinking_game_v1 | st_ask_team | 팀원들에게 어떻게 쓸지 물어본다 | 정보만 물어봄 |
| detail_orientation_media_v1 | do_ask_feedback | 친구에게 먼저 보여주고 의견을 듣는다 | 피드백 요청 |
| detail_orientation_school_life_v1 | do_ask_help | 선생님이나 친구에게 확인을 부탁한다 | 정보만 물어봄 |
| persistence_completion_game_v1 | pc_ask_help | 같이 하는 친구에게 도움을 요청한다 | 정보만 물어봄 |
| uncertainty_tolerance_game_v1 | ut_ask_others | 다른 사람 의견을 먼저 들어본다 | 피드백 요청 |
| uncertainty_tolerance_school_life_v1 | ut_ask_teacher | 선생님이나 친구에게 먼저 물어본다 | 정보만 물어봄 |
| opinion_expression_media_v1 | oe_follow_majority | 다수가 원하는 방향을 따른다 | 순응(질문형은 아니지만 같은 이유로 재검토) |
| opinion_expression_school_life_v1 | oe_support_role | 일단 다수가 정한 방향에 맞춘다 | 순응 |
| creative_ideation_game_v1 | ci_get_feedback | 친구들에게 아이디어를 먼저 물어본다 | 피드백 요청 |
| independent_judgment_game_v1 | ij_ask_more | 다른 사람들에게 더 물어본다 | 정보만 물어봄 |
| independent_judgment_school_life_v1 | ij_ask_clarify | 다른 사람에게 먼저 물어보고 기준을 맞춘다 | 정보만 물어봄 |

유지한 collaboration_preference Option은 "함께 역할을 나누고 공동으로 해결함" 근거가
강한 것만 남겼다:

| blueprint_id | role_id | 문구 | 근거 |
|---|---|---|---|
| persistence_completion_school_life_v1 | pc_team_stage | 팀원과 역할을 맞추는 데 가장 오래 매달린다 | 역할 분담·조율이 직접 드러남 |
| creative_ideation_media_v1 | ci_ask_team | 팀원들과 아이디어를 같이 나눈다 | 공동 발상(같이 나눈다)이 직접 드러남 |

## Legacy Seed (`vertical_slice_seed_questions.py`)

`collaboration_preference` PRIMARY로 등록된 Role은 game/media/school_life Seed 각 1개씩
(`team_coordination`/`team_project`)이다. 실제 문구를 확인한 결과 전부 "역할을 나누고
함께 해결"류로, "정보만 물어봄" 패턴이 아니다. 예: game Seed `team_coordination` —
"친구들과 역할을 나누고 함께 해결해가는 순간". 별도 수정 대상 없음.

## Legacy Tail Blueprint (`tail_option_blueprints.py`)

Blueprint 자체의 `next_probe` 메모(예: "역할을 나누는 방식이 다른 협업 상황에서도
이어지는지 확인")도 "역할 분담" 프레이밍을 유지한다. 실제 문장은 LLM이 세션마다
생성하므로 이 감사에서는 정적으로 검토할 수 없다 — Backup Question(Tail 생성 실패 시
쓰는 고정 대체 문항)의 `role_split`/`team_split` Role만 정적으로 확인 가능하다(아래).

## Legacy Backup Question (`vertical_slice_backup_questions.py`)

`collaboration_preference` PRIMARY로 등록된 Role은 `role_split`(game_backup_01)과
`team_split`(media_backup_02)이다. 문구는 각각 "팀원들과 역할을 나눠서 같이 파악한다",
"팀원과 역할을 나눠 함께 만든다" — "역할을 나누고 함께"가 직접 드러나 근거가 강하다.
별도 수정 대상 없음.

## Conflict Resolution 확인 질문 (`vertical_slice_conflict_resolution_questions.py`)

`filler_ask_others` Role(문구: "주변 사람에게 먼저 물어보고 참고한다")이 "정보만
물어봄" 패턴으로 발견됐다. 다만 이 질문 계열은 구조적으로 `resolve_trait_signals()`가
`is_resolution_question=True`일 때 항상 signals=[]를 반환하므로(1.5단계 §3), 어떤
선택지를 골라도 Trait Evidence 계산에 전혀 반영되지 않는다 — 문구 자체는 재검토
후보로 기록하되, Evidence 오염 위험은 없다(구조적으로 무해한 filler).

## 자동 정적 검색 범위와 한계

이 문서는 Seed/Backup/Conflict Resolution처럼 코드에 고정 문자열로 존재하는 질문만
검색했다("물어보/요청/부탁/문의/상담" 등 키워드 기준). Tail Blueprint의 실제 선택지
문장은 매 세션 LLM이 새로 생성하므로 정적 검색 대상이 아니다 — LLM 프롬프트 자체가
Blueprint의 Role 의미(예: `team_coordination` → "역할 분담" 취지)를 그대로 반영하도록
설계돼 있어 구조적으로는 안전하지만, 실제 생성 문구가 이 패턴을 벗어나는지는 사람이
개별 세션에서 확인해야 한다(질문 품질 평가 보고서의 실제 opt-in 실행 Sample도 참고).

## 결론

- v2 Direct Probe: 11개 Option을 이번 라운드에 NO_SIGNAL로 전환 완료(위 표), 2개는
  근거가 강해 유지.
- Legacy Seed/Backup: 정적 문구 검토 결과 문제 패턴 없음 — 수정 불필요.
- Conflict Resolution: 문제 패턴 1건 발견했으나 구조적으로 Evidence에 반영되지 않음
  — 문구 정리는 후속 검토 항목(우선순위 낮음)으로만 남긴다.
- Legacy Tail Blueprint의 실제 LLM 생성 문구는 이 정적 감사 범위 밖이다 — 후속 검토
  필요.
