# 최종 모델 활성화 전 Readiness Audit

브랜치 `a/final-activation-readiness-audit`. 읽기 전용 진단 — Runtime·Review·Master·Feature Flag·Mock·질문·Mapping 무엇도 바꾸지 않았다.

## 최종 판정: **BLOCKED_BY_MAPPING**

| 영역 | 상태 |
|---|---|
| context_readiness | READY_AFTER_HUMAN_REVIEW |
| trait_readiness | BLOCKED_BY_MAPPING |
| question_flow_readiness | SHADOW_ONLY |
| major_department_readiness | BLOCKED_BY_DATA |
| subject_readiness | BLOCKED_BY_DATA |
| frontend_readiness | READY_AFTER_HUMAN_REVIEW |

## 1. Context 준비도 (15개)

| Context | Legacy | Pack | Anchor/Seed/Backup | 검수 Key | 승인 상태 | Runtime 활성화 | 상태 |
|---|---|---|---|---|---|---|---|
| art_design | 아니오 | 있음 | 5/5/5 | 11 | TBD:11 | 불가 | READY_AFTER_HUMAN_REVIEW |
| business | 아니오 | 있음 | 5/5/5 | 11 | APPROVE:10, REVISE:1 | 불가 | READY_AFTER_HUMAN_REVIEW |
| cooking | 아니오 | 있음 | 5/5/5 | 11 | TBD:11 | 불가 | READY_AFTER_HUMAN_REVIEW |
| fashion_beauty | 아니오 | 있음 | 5/5/5 | 11 | TBD:11 | 불가 | READY_AFTER_HUMAN_REVIEW |
| game | 예 | Legacy 고정 데이터 | 5/5/5 | - | N/A | 가능 | READY |
| history_humanities | 아니오 | 있음 | 5/5/5 | 11 | TBD:11 | 불가 | READY_AFTER_HUMAN_REVIEW |
| law_politics | 아니오 | 있음 | 5/5/5 | 11 | TBD:11 | 불가 | READY_AFTER_HUMAN_REVIEW |
| making | 아니오 | 있음 | 5/5/5 | 11 | TBD:11 | 불가 | READY_AFTER_HUMAN_REVIEW |
| media | 예 | Legacy 고정 데이터 | 5/5/5 | - | N/A | 가능 | READY |
| school_life | 예 | Legacy 고정 데이터 | 5/5/5 | - | N/A | 가능 | READY |
| science | 아니오 | 있음 | 5/5/5 | 11 | APPROVE:11 | 가능 | READY |
| sports | 아니오 | 있음 | 5/5/5 | 11 | APPROVE:11 | 가능 | READY |
| travel | 아니오 | 있음 | 5/5/5 | 11 | TBD:11 | 불가 | READY_AFTER_HUMAN_REVIEW |
| volunteer | 아니오 | 있음 | 5/5/5 | 11 | TBD:11 | 불가 | READY_AFTER_HUMAN_REVIEW |
| writing | 아니오 | 있음 | 5/5/5 | 11 | TBD:11 | 불가 | READY_AFTER_HUMAN_REVIEW |

## 2. Trait 준비도 (24개)

| Trait | Signal 수 | Primary | Related | Context 수 | Frame 수 | 승인된 Signal | 구조적 SUFFICIENT 가능 | Mapping Gap | 상태 |
|---|---|---|---|---|---|---|---|---|---|
| aesthetic_sensitivity | 0 | 0 | 0 | 0 | 0 | 0 | 아니오 | 예 | BLOCKED_BY_MAPPING |
| audience_response_prediction | 0 | 0 | 0 | 0 | 0 | 0 | 아니오 | 예 | BLOCKED_BY_MAPPING |
| causal_analysis | 0 | 0 | 0 | 0 | 0 | 0 | 아니오 | 예 | BLOCKED_BY_MAPPING |
| challenge_seeking | 0 | 0 | 0 | 0 | 0 | 0 | 아니오 | 예 | BLOCKED_BY_MAPPING |
| change_adaptation | 0 | 0 | 0 | 0 | 0 | 0 | 아니오 | 예 | BLOCKED_BY_MAPPING |
| collaboration_preference | 0 | 0 | 0 | 0 | 0 | 0 | 아니오 | 예 | BLOCKED_BY_MAPPING |
| creative_ideation | 4 | 4 | 0 | 14 | 2 | 0 | 예 | 아니오 | READY_AFTER_HUMAN_REVIEW |
| detail_orientation | 4 | 4 | 0 | 14 | 2 | 0 | 예 | 아니오 | READY_AFTER_HUMAN_REVIEW |
| emotional_interpretation | 0 | 0 | 0 | 0 | 0 | 0 | 아니오 | 예 | BLOCKED_BY_MAPPING |
| immediate_execution | 0 | 0 | 0 | 0 | 0 | 0 | 아니오 | 예 | BLOCKED_BY_MAPPING |
| independent_judgment | 4 | 4 | 0 | 14 | 2 | 0 | 예 | 아니오 | READY_AFTER_HUMAN_REVIEW |
| information_comparison | 0 | 0 | 0 | 0 | 0 | 0 | 아니오 | 예 | BLOCKED_BY_MAPPING |
| novelty_seeking | 0 | 0 | 0 | 0 | 0 | 0 | 아니오 | 예 | BLOCKED_BY_MAPPING |
| opinion_expression | 4 | 4 | 0 | 14 | 2 | 0 | 예 | 아니오 | READY_AFTER_HUMAN_REVIEW |
| opinion_mediation | 0 | 0 | 0 | 0 | 0 | 0 | 아니오 | 예 | BLOCKED_BY_MAPPING |
| pattern_finding | 0 | 0 | 0 | 0 | 0 | 0 | 아니오 | 예 | BLOCKED_BY_MAPPING |
| persistence_completion | 4 | 4 | 0 | 14 | 2 | 0 | 예 | 아니오 | READY_AFTER_HUMAN_REVIEW |
| personal_goal_priority | 0 | 0 | 0 | 0 | 0 | 0 | 아니오 | 예 | BLOCKED_BY_MAPPING |
| planning | 0 | 0 | 0 | 0 | 0 | 0 | 아니오 | 예 | BLOCKED_BY_MAPPING |
| systems_thinking | 4 | 4 | 0 | 14 | 2 | 0 | 예 | 아니오 | READY_AFTER_HUMAN_REVIEW |
| tool_utilization | 0 | 0 | 0 | 0 | 0 | 0 | 아니오 | 예 | BLOCKED_BY_MAPPING |
| uncertainty_tolerance | 4 | 4 | 0 | 14 | 2 | 0 | 예 | 아니오 | READY_AFTER_HUMAN_REVIEW |
| verbal_expression | 0 | 0 | 0 | 0 | 0 | 0 | 아니오 | 예 | BLOCKED_BY_MAPPING |
| visual_expression | 0 | 0 | 0 | 0 | 0 | 0 | 아니오 | 예 | BLOCKED_BY_MAPPING |

## 3. 질문 흐름 준비도

- 2+1(Flag OFF): 최종 2~3개 — READY
- 4+1(Flag ON): 오늘 활성 Context 5개(최소 5) — 기준 충족: 예 — READY
- Context당 질문 수: 4~6개 — READY
- Backup 안전성: READY
- Planner Baseline: READY
- Coverage-focused Planner 대안(A/B/C/D): SHADOW_ONLY
- Coverage Stop Condition 연결: SHADOW_ONLY

## 4. 전공·학과 준비도

- 서비스 Canonical Major: 10개 — READY
- Major-Trait Evidence: legacy 36행 · v2 72행 — SHADOW_ONLY
- Canonical Major Group: 42개, {'draft': 42} — BLOCKED_BY_MAPPING
- Bridge Mapping: 44개, 검토 {'APPROVE': 38, 'REVISE': 6} — READY_AFTER_HUMAN_REVIEW
- Bridge Scope: {'DEPARTMENT_REVIEW_REQUIRED': 2, 'EXCLUDED_RECOMMENDATION': 5, 'FULL_GROUP': 4, 'INCLUDED_SMALL_SERIES_ONLY': 4, 'None': 29} — READY_AFTER_HUMAN_REVIEW
- P1: 374건, {'TBD': 374} — BLOCKED_BY_MAPPING
- N.C.E: 24개 클러스터·584행, {'TBD': 24} — BLOCKED_BY_MAPPING
- Identity 충돌: 16 Group·32행, {'TBD': 16} — BLOCKED_BY_MAPPING
- 현재 Master: 35건 — READY
- 전국 Dry Run: scripts/career_build_national_department_promotion_dry_run.py는 존재하고 정상 작동하지만, 이 Worktree에 departments.normalized.jsonl/classification_results.jsonl(둘 다 Git 제외 로컬 입력)이 없어 이번 Audit 에서는 실행하지 않았다 — 실행해도 Canonical Major Group Draft·P1·N.C.E가 전부 미승인이라 구조적으로 BLOCKED_GROUP_DRAFT/BLOCKED_P1_REVIEW_UNRESOLVED/BLOCKED_NCE_UNRESOLVED에 걸린다. — BLOCKED_BY_DATA
- 차단 사유: BLOCKED_BY_DATA: departments.normalized.jsonl/classification_results.jsonl 이 이 Worktree 로컬에 없음(Git 제외 입력); BLOCKED_BY_MAPPING: Canonical Major Group 42개 전부 review_status=draft; BLOCKED_BY_MAPPING: P1 분류 검토 374건 중 미승인 374건; BLOCKED_BY_MAPPING: N.C.E 클러스터 24개 중 미승인 24개; BLOCKED_BY_MAPPING: Identity-key 충돌 16 Group 미해결

## 5. 과목 준비도

| 전공 | Subject-Major Link 수 | 상태 |
|---|---|---|
| business_administration | 0 | BLOCKED_BY_DATA |
| computer_science | 0 | BLOCKED_BY_DATA |
| design | 0 | BLOCKED_BY_DATA |
| education | 0 | BLOCKED_BY_DATA |
| hci_ux | 6 | READY_AFTER_HUMAN_REVIEW |
| industrial_engineering | 6 | READY_AFTER_HUMAN_REVIEW |
| life_science | 0 | BLOCKED_BY_DATA |
| mechanical_engineering | 0 | BLOCKED_BY_DATA |
| media_communication | 4 | READY_AFTER_HUMAN_REVIEW |
| psychology | 0 | BLOCKED_BY_DATA |

- PRE_SURVEY/POST_OFFERING: READY
- PDF·Excel Parsing: 실제 구현됨(C 소유) — .xlsx는 stdlib zipfile/ElementTree, .pdf는 pypdf 있으면 사용·없으면 최소 FlateDecode 추출기로 폴백, .xls는 명시적으로 미지원(ParseError). — READY
- 실제 개설 과목 확인: data/fixtures/course_offerings/demo_school_offerings.xlsx 1건 — 시연용 Fixture뿐, 실 서비스 규모의 POST_OFFERING 확인 데이터는 없음. — BLOCKED_BY_DATA
- 미지원 전공: business_administration, computer_science, design, education, life_science, mechanical_engineering, psychology

## 6. Frontend 준비도

| 항목 | 상태 |
|---|---|
| context_catalog_15_display | READY |
| assessment_supported_gate | READY |
| policy_4plus1_ui | READY |
| major_description_display | READY |
| department_modal_real_data | READY_AFTER_HUMAN_REVIEW |
| source_url_not_clickable_department_url_conditional | READY |
| empty_insufficient_error_states | READY |
| refresh_session_restore_limits | READY |

- npm scripts: {'dev': 'vite', 'build': 'tsc -b && vite build', 'preview': 'vite preview', 'typecheck': 'tsc -b --noEmit', 'test': 'vitest run', 'test:watch': 'vitest'}
- node_modules 설치됨: 예

## 7. Feature Flag 표

| Flag | 기본값 | 현재값 | 오늘 활성화 가능 | 권장 순서 | 차단 사유 |
|---|---|---|---|---|---|
| ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES | False | False | 가능 | 1 | v2_direct_probe_question_review_status.json 14건 전부 TBD — Evidence는 나가지만 계산에서 제외됨 |
| ENABLE_CONTEXT_PACK_RUNTIME | False | False | 가능 | 2 | (없음) |
| ENABLE_CONTEXT_SELECTION_4_PLUS_1 | False | False | 가능 | 3 | (없음) |
| ENABLE_TRAIT_VECTOR_V2_PRIMARY | False | False | 가능 | 4 | (없음) |

## 8. 최종 상태 판정

**BLOCKED_BY_MAPPING**

질문·Mapping·Runtime·Review 파일은 이 진단이 만들지도 바꾸지도 않았다 — 위 표는 전부 현재 저장소·로컬 데이터를 있는 그대로 읽은 결과다.
