# Final Mapping Closure — 최종 검수 대상 축소

**이 문서는 계산 결과 보고서다.** `data/reviews/`·`data/master/departments.jsonl`·공개 API는 이 실행으로 전혀 바뀌지 않았다. `auto_approved_rows`는 항상 0이다.

## 0. 시작 시 미검수·차단 상태

- Group 검수 파일 존재: False(42개 전부 미검수)
- Bridge Mapping 기존 검수: APPROVE 38 / REVISE 6(§4 보존)
- Bridge Scope 검수 파일 존재: False
- P1 검수 파일 존재: False
- N.C.E 검수 파일 존재: False

## 1. 분류 단위 안내

PROPOSE_APPROVE/PROPOSE_EXCLUDE/HUMAN_REVIEW_REQUIRED 건수는 각 항목의 자연스러운 검수 결정 단위로 센다 — Group 42개(Group 단위), Bridge Mapping 44개(Group×Major 쌍 단위), Bridge Scope는 Mapping이 UNMAPPED가 아닌 15개만(29개는 Scope 질문 자체가 성립하지 않아 not_applicable), P1 374개(학과 단위), N.C.E는 클러스터 24개(학과 584건은 세부 개수로 별도 표시 — 사람이 실제로 판단하는 단위가 클러스터이기 때문이다).

## 2. 카테고리별 세부 개수

| 카테고리 | 전체 | PROPOSE_APPROVE | PROPOSE_EXCLUDE | HUMAN_REVIEW_REQUIRED |
|---|---:|---:|---:|---:|
| Group | 42 | 39 | 0 | 3 |
| Bridge Mapping | 44 | 33 | 5 | 6 |
| Bridge Scope(적용 15/전체 44, 미적용 29) | 15 | 8 | 5 | 2 |
| P1 | 374 | 96 | 1 | 277 |
| N.C.E 클러스터 | 24 | 0 | 0 | 24 |
| N.C.E 학과(세부, 584건) | 584 | PROPOSED_GROUP_CANDIDATE 208 | DEPARTMENT_LEVEL_REVIEW_REQUIRED 376 | (클러스터 단위로 전부 HUMAN_REVIEW_REQUIRED) |

## 3. 합계

- PROPOSE_APPROVE 총 176건
- PROPOSE_EXCLUDE 총 11건
- HUMAN_REVIEW_REQUIRED 총 312건(Priority HTML에 전부 수록)
- auto_approved_rows = 0

## 4. 예상 READY_FOR_PROMOTION(가정 계산)

- 평가 대상 24406건 중 READY_FOR_PROMOTION 예상 **347건**
- BLOCKED 예상 24059건

| 차단 사유 | 예상 잔존 건수 |
|---|---:|
| BLOCKED_ARTS_RECOMMENDATION | 3637 |
| BLOCKED_BRIDGE_MAPPING_REVIEW | 3443 |
| BLOCKED_CONTRACT_DEPARTMENT | 4 |
| BLOCKED_DUPLICATE_ID | 16 |
| BLOCKED_GROUP_DRAFT | 2819 |
| BLOCKED_INACTIVE_STATUS | 14352 |
| BLOCKED_NCE_UNRESOLVED | 3534 |
| BLOCKED_NO_SERVICE_CANONICAL_MAJOR | 11856 |
| BLOCKED_OUTSIDE_SMALL_SERIES_SCOPE | 1822 |
| BLOCKED_P1_REVIEW_UNRESOLVED | 4161 |

이 스크립트가 PROPOSE_APPROVE로 분류한 Group/Bridge Scope/P1 항목만 승인됐다고 가정한 임시(tempfile) Fixture 계산이다 — 실제 data/reviews/·Master·API는 전혀 바뀌지 않았다. 야간·원격 제외(out_of_recommendation_scope.jsonl)와 URL 정책 감사는 이번 계산 범위에 포함하지 않았다(이 Worktree의 해당 파일이 이번 복원 Snapshot과 다른 시점의 것이라 섞으면 왜곡된다).

## 5. 검수가 끝나도 구조적으로 차단되는 사유(영구 구조적)

| 사유 | 건수 |
|---|---:|
| BLOCKED_ARTS_RECOMMENDATION | 3637 |
| BLOCKED_CONTRACT_DEPARTMENT | 4 |
| BLOCKED_DUPLICATE_ID | 16 |
| BLOCKED_INACTIVE_STATUS | 14352 |
| BLOCKED_NCE_UNRESOLVED | 3534 |
| BLOCKED_NO_SERVICE_CANONICAL_MAJOR | 11856 |
| BLOCKED_OUTSIDE_SMALL_SERIES_SCOPE | 1822 |

## 재생성 명령

```
PYTHONPATH=. ./.venv/bin/python scripts/career_build_final_mapping_closure.py --restore-normalized-path <departments.normalized.jsonl> --restore-classification-path <classification_results.jsonl>  # 두 옵션 생략 시 예상 READY_FOR_PROMOTION 계산은 건너뛴다
```
