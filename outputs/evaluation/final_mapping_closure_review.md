# Final Mapping Closure — 최종 검수 대상 축소

**이 문서는 계산 결과 보고서다.** `data/reviews/`·`data/master/departments.jsonl`·공개 API는 이 실행으로 전혀 바뀌지 않았다. `auto_approved_rows`는 항상 0이다.

## 0. 검수 상태 — 이전 라운드 시작 시점 대비 이번 실행 시점

이전 라운드(commit `2d6f831`, 브랜치 동일)가 끝난 시점의 기록값(고정, 재계산하지
않는다 — 그 라운드는 이미 커밋됐고 재실행 대상이 아니다):

- Group 검수 파일 존재: False(42개 전부 미검수) · Bridge Mapping 기존 검수 APPROVE 38/REVISE 6 · Bridge Scope/P1/N.C.E 검수 파일 존재: False(전부 미검수)
- 분류: PROPOSE_APPROVE 176 / PROPOSE_EXCLUDE 11 / HUMAN_REVIEW_REQUIRED 312

**이번 실행 시점(이 문서 생성 직전)의 실제 현재 상태**(이 스크립트가 매번 그때그때
다시 읽는 값 — 사용자 최종 결정에 따라 §1~§9 종결 스크립트를 먼저 실행한 뒤 이
보고서를 재생성했다면 아래는 '종결 후' 상태를 보여준다):

- Group 검수 파일 존재: True
- Bridge Mapping 기존 검수: APPROVE 44 / REVISE 0
- Bridge Scope 검수 파일 존재: True
- P1 검수 파일 존재: True
- N.C.E 검수 파일 존재: True

## 1. 분류 단위 안내

PROPOSE_APPROVE/PROPOSE_EXCLUDE/HUMAN_REVIEW_REQUIRED 건수는 각 항목의 자연스러운 검수 결정 단위로 센다 — Group 42개(Group 단위), Bridge Mapping 44개(Group×Major 쌍 단위), Bridge Scope는 Mapping이 UNMAPPED가 아닌 15개만(29개는 Scope 질문 자체가 성립하지 않아 not_applicable), P1 374개(학과 단위), N.C.E는 클러스터 24개(학과 584건은 세부 개수로 별도 표시 — 사람이 실제로 판단하는 단위가 클러스터이기 때문이다).

## 2. 카테고리별 세부 개수

| 카테고리 | 전체 | PROPOSE_APPROVE | PROPOSE_EXCLUDE | HUMAN_REVIEW_REQUIRED |
|---|---:|---:|---:|---:|
| Group | 42 | 42 | 0 | 0 |
| Bridge Mapping | 44 | 39 | 5 | 0 |
| Bridge Scope(적용 15/전체 44, 미적용 29) | 15 | 8 | 7 | 0 |
| P1 | 374 | 96 | 278 | 0 |
| N.C.E 클러스터 | 24 | 0 | 24 | 0 |
| N.C.E 학과(세부, 584건) | 584 | PROPOSED_GROUP_CANDIDATE 208 | DEPARTMENT_LEVEL_REVIEW_REQUIRED 376 | (클러스터 단위로 전부 HUMAN_REVIEW_REQUIRED) |

## 3. 합계

- PROPOSE_APPROVE 총 185건
- PROPOSE_EXCLUDE 총 314건
- HUMAN_REVIEW_REQUIRED 총 0건(Priority HTML에 전부 수록)
- auto_approved_rows = 0

## 4. 예상 READY_FOR_PROMOTION(가정 계산)

- 평가 대상 24406건 중 READY_FOR_PROMOTION 예상 **1084건**
- BLOCKED 예상 23322건

| 차단 사유 | 예상 잔존 건수 |
|---|---:|
| BLOCKED_ARTS_RECOMMENDATION | 3637 |
| BLOCKED_CONTRACT_DEPARTMENT | 4 |
| BLOCKED_DUPLICATE_ID | 16 |
| BLOCKED_EXCLUDED_FROM_INITIAL_PROMOTION | 277 |
| BLOCKED_INACTIVE_STATUS | 14352 |
| BLOCKED_NCE_EXCLUDED_FROM_INITIAL_PROMOTION | 584 |
| BLOCKED_NCE_UNRESOLVED | 2950 |
| BLOCKED_NO_SERVICE_CANONICAL_MAJOR | 11856 |
| BLOCKED_OUTSIDE_SMALL_SERIES_SCOPE | 1822 |
| BLOCKED_P1_REVIEW_UNRESOLVED | 3884 |

실제 Review 정본(Bridge Mapping·Bridge Scope·P1·N.C.E — §4/§5/§6/§7로 이번 라운드에 전부 종결)을 그대로 읽어 계산했다. Group만 예외 — BLOCKED_GROUP_DRAFT Gate가 별도 검수 Store가 아니라 Group Draft 파일 자체의 review_status 필드를 읽는 기존 설계라, 실제 검수 결정(canonical_major_group_review_status.jsonl)을 반영한 임시 사본으로 그 필드만 대신한다 — 실제 data/canonical_major_groups.draft.jsonl(Read-Only 원본)·data/reviews/·Master·API는 전혀 바뀌지 않았다. 야간·원격 제외(out_of_recommendation_scope.jsonl)와 URL 정책 감사는 이번 계산 범위에 포함하지 않았다(이 Worktree의 해당 파일이 이번 복원 Snapshot과 다른 시점의 것이라 섞으면 왜곡된다).

### 4-1. 검수 범위 경계 확인(§11 'P1_REVIEW_UNRESOLVED/NCE_UNRESOLVED 0' 검증)

- P1(374건 범위 안) 미해결 잔존: **1건** · 범위 밖(원래 대상 아님): 3883건
- N.C.E(24개 클러스터 범위 안) 미해결 잔존: **0건** · 범위 밖(원래 대상 아님): 2950건

이번 Final Mapping Closure는 P1 374건·N.C.E 24개 클러스터(584건)만 다뤘다 — 분류 REVIEW_REQUIRED 전체(약 1,936건)·N.C.E 미분류 전체(약 3,534건) 중 나머지는 애초에 이 검수 패킷의 대상이 아니었다. *_within_*이 0이면 이번 라운드가 다룬 범위 안에서는 '검수 상태로 인한' 차단이 실제로 전부 해소됐다는 뜻이다. p1_review_unresolved_within_374_packet가 1인 이유: 대전대학교 뷰티디자인학과(candidate_id=p1cls_77f2cdbc4b2211a30ebc, judgment_candidate=DESIGN_ARTS_EXCLUDED)는 이번에 EXCLUDE_ARTS_RECOMMENDATION으로 실제 검수 종결됐지만, Dry Run Gate가 그 Decision 값 자체를(EXCLUDE_FROM_INITIAL_PROMOTION이 아닌 기존 5개 값 중 하나로) BLOCKED_P1_REVIEW_UNRESOLVED로 라벨링하는 기존 동작을 이번 라운드에서 바꾸지 않았다(a/academyinfo-review-ui-p1-nce 지시서 §6 '나머지 Decision은 모두 차단'을 그대로 보존 — 기존 테스트가 이 동작을 이미 고정하고 있다). 검수 자체는 완료됐고(EXCLUDE_ARTS_RECOMMENDATION), 추천에 포함되지도 않는다 — 라벨만 'UNRESOLVED'로 남아 숫자가 1이라는 사실을 그대로 밝힌다.

## 5. 검수가 끝나도 구조적으로 차단되는 사유(영구 구조적)

| 사유 | 건수 |
|---|---:|
| BLOCKED_ARTS_RECOMMENDATION | 3637 |
| BLOCKED_CONTRACT_DEPARTMENT | 4 |
| BLOCKED_DUPLICATE_ID | 16 |
| BLOCKED_INACTIVE_STATUS | 14352 |
| BLOCKED_NCE_UNRESOLVED | 2950 |
| BLOCKED_NO_SERVICE_CANONICAL_MAJOR | 11856 |
| BLOCKED_OUTSIDE_SMALL_SERIES_SCOPE | 1822 |

## 재생성 명령

```
PYTHONPATH=. ./.venv/bin/python scripts/career_build_final_mapping_closure.py --restore-normalized-path <departments.normalized.jsonl> --restore-classification-path <classification_results.jsonl>  # 두 옵션 생략 시 예상 READY_FOR_PROMOTION 계산은 건너뛴다
```
