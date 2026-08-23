# Anchor Backup 전환 감사 — 2.5.4단계 §1/§2/§3

2026-08-23 Trait Ontology v2(2.5.4단계). 사용자가 기존 Backup 6개(Context당 2개,
모든 Anchor 공통)를 검수 페이지에서 전부 `REVISE`(reviewer_1) 판정했다 — "Backup
질문이 전반적으로 부자연스러워 재작성이 필요함". Context 전체를 억지로 포괄하려던
설계 자체가 문제였다고 보고, Context 공통 2개 대신 15개 Anchor마다 자연스러운
Backup 질문 1개로 다시 설계했다.

## §2 — 기존 6개가 Runtime에서 쓰이던 경로 조사 결과

`VERTICAL_SLICE_BACKUP_QUESTIONS`를 참조하는 곳을 전수 조사했다.

```text
src/api/main.py:1011(수정 전)
  → generate_tail_question(..., backup_questions=VERTICAL_SLICE_BACKUP_QUESTIONS.get(current_context, []))
  → 이 호출이 유일한 실제 Runtime 소비 경로다.
  → LLM Client가 켜져 있고(ENABLE 여부와 무관, _llm_client is not None) 재생성까지
    실패했을 때만 도달한다.
  → 이 호출 지점은 Anchor 유무를 구분하지 않았다 — v2 Anchor Flow(Context Routing을
    거쳐 Anchor가 정해진 상태)와 Legacy Flow(Anchor가 아예 없는 상태) 둘 다 똑같이
    이 6개를 후보로 받았다.

그 외 참조(src/review_ui/review_service.py, src/data/trait_ontology/
trait_probe_capabilities_v2.py, src/services/trait_signal_registry.py,
src/services/backup_question_review_store.py, src/data/questions/
backup_question_applicability.py, src/data/questions/backup_mapping_rationale.py)는
전부 검수 UI·Trait Signal Registry·진단용 조회일 뿐, 학생에게 실제로 질문을
내보내는 경로가 아니다.
```

수정 후 `src/api/main.py`는 Anchor 유무로 후보 목록 자체를 분기한다.

```python
if tail_anchor is not None:
    anchor_backup = ANCHOR_BACKUP_QUESTIONS_BY_KEY.get((current_context, tail_anchor.anchor_id))
    backup_candidates = [anchor_backup] if anchor_backup is not None else []
else:
    backup_candidates = VERTICAL_SLICE_BACKUP_QUESTIONS.get(current_context, [])
```

**결과**: v2 Anchor Flow(Anchor가 있는 모든 세션 — 즉 v2 기능 Flag가 켜져 있고
Context Routing을 거친 세션)에서는 기존 6개가 후보 목록에 아예 들어가지 않는다.
Anchor가 없는 Legacy Flow(v2 Flag가 꺼져 있거나, 이론상 Anchor 설정 전 극히 짧은
순간)만 기존 정책을 그대로 유지한다 — 이번 단계에서 Legacy 정책 자체를 바꾸지
않았다(§6 명시적 요구).

**남은 위험(§6 "현재 동작과 위험만 보고")**: Legacy Flow(v2 Flag OFF)에서 LLM
장애가 나면 여전히 사용자가 REVISE 판정한 6개 문항이 그대로 나간다. 이 6개는
`data/reviews/v2_backup_question_review_status.json`에서 REVISE로 표시돼 있어 검수
페이지에서 계속 보이지만, 코드가 자동으로 막지는 않는다 — Legacy Flow 자체를 이번
단계에서 변경 대상으로 삼지 않았기 때문이다(v2 기능이 기본 OFF이므로 학생용 실제
배포 경로에서는 v2 Flag가 켜진 v2 Anchor Flow만 쓰인다는 전제 하에 낮은 위험으로
분류했다 — 다만 Legacy Flow를 실제로 켜서 쓰는 시나리오가 생기면 재검토가 필요하다).

## §3 — Anchor Backup 15개 vs 기존 6개

| Context | 기존(REVISE, Runtime 제외) | 신규(Anchor 전용, Runtime 후보) |
|---|---|---|
| game | game_backup_01, game_backup_02 | game_backup_story_exploration_v2, game_backup_strategy_puzzle_v2, game_backup_competition_mastery_v2, game_backup_cooperative_role_v2, game_backup_building_creation_v2 |
| media | media_backup_01, media_backup_02 | media_backup_film_drama_v2, media_backup_online_video_v2, media_backup_animation_webcontent_v2, media_backup_stage_performance_v2, media_backup_documentary_v2 |
| school_life | school_life_backup_01, school_life_backup_02 | school_life_backup_academic_study_v2, school_life_backup_assignment_evaluation_v2, school_life_backup_course_career_v2, school_life_backup_friendship_v2, school_life_backup_club_activity_v2 |

각 신규 질문은 `BackupQuestionApplicability(allowed_anchor_ids={그 anchor_id 1개})`로
제한된다(all-permissive 아님) — `check_backup_candidate()`가 다른 Anchor에서는
구조적으로 거부한다(테스트로 확인).

## 상태

15개 질문·75개 선택지 전부 `data/reviews/v2_anchor_backup_question_review_status.json`/
`v2_anchor_backup_option_review_status.json`에서 `TBD`다. 기존 6개의 REVISE 판정과
`game_backup_02/screen_review`의 "이런 경우는 너무 드문 경우같아" 메모는 별도 파일에
그대로 남아 있고 이번 라운드에서 전혀 수정하지 않았다.
