# 계약학과 추천 범위 분리 보고 — 조사연도 2025

## 결론

중복 `department_id` 6그룹은 대학알리미 공식 `major_character_name`과
`schlMjrId`를 근거로 일반과정 1건과 계약학과 1건의 서로 다른 과정으로 재검증했다.
일반과정 6건은 추천 후보에 유지하고 계약학과 6건은 삭제하지 않은 채
`OUT_OF_RECOMMENDATION_SCOPE / CONTRACT_DEPARTMENT`로 이동했다.

추천 후보의 중복 `department_id`는 0건이다. 관계 검수용 6그룹은
`packets/duplicate_decision_draft.jsonl`과 HTML에 계속 보존하며 사람 승인 상태는 모두
`TBD / PENDING`이다.

## 공식 필드 재검증

| 학교 | 학과 | 일반과정 schlMjrId | 계약학과 schlMjrId | 추가 근거 |
|---|---|---:|---:|---|
| 서경대학교 | 코스메틱뷰티매니지먼트학과 | 0246788 | 0246874 | 학과특성 일반과정/계약학과, 모두 4년제 학사·주간·EXISTING |
| 서경대학교 | 헤어디자인학과 | 0232771 | 0232745 | 학과특성 일반과정/계약학과, 모두 4년제 학사·주간·EXISTING |
| 충남대학교 | 약학과 | 0010025 | 0220559 | 일반과정 6년, 계약학과 4년, 모두 학사·주간·EXISTING |
| 한일장신대학교 | 사회복지학과 | 0224303 | 0019547 | 학과특성 일반과정/계약학과, 모두 4년제 학사·주간·EXISTING |
| 원광대학교 | 약학과(2+4학제) | 0009123 | 0009574 | 학과특성 일반과정/계약학과, 모두 4년제 학사·주간·EXISTING |
| 동신대학교 | 사회복지학과 | 0016970 | 0011969 | 학과특성 일반과정/계약학과, 모두 4년제 학사·주간·EXISTING |

이름이 같다는 사실은 판정 근거로 사용하지 않았다. 여섯 그룹 모두 공식 학과특성이
명확해 `NEEDS_MORE_REVIEW`로 보낼 불명확 행은 없었다.

## 제외된 계약학과 6건

| 학교·학과 | source_record_id | schlMjrId | 수업연한 | 상태 |
|---|---|---:|---:|---|
| 충남대학교 약학과 | src_1c796c51cd964c139da0462e | 0220559 | 4년 | EXISTING |
| 동신대학교 사회복지학과 | src_3ff8c9612cb1b70aee35f965 | 0011969 | 4년 | EXISTING |
| 한일장신대학교 사회복지학과 | src_4fcef86155dfa2d623d0a57c | 0019547 | 4년 | EXISTING |
| 원광대학교 약학과(2+4학제) | src_8609307f9560d236343eae79 | 0009574 | 4년 | EXISTING |
| 서경대학교 코스메틱뷰티매니지먼트학과 | src_9d87dbc9dbfafb35d8605c3e | 0246874 | 4년 | EXISTING |
| 서경대학교 헤어디자인학과 | src_e153ffe8c60d5c9220dbdd22 | 0232745 | 4년 | EXISTING |

모든 행은 `out_of_recommendation_scope.jsonl`에 원본 lineage 식별자인
`source_record_id`와 함께 보존했다. `department_status`는 `EXISTING` 그대로이며
`ABOLISHED`로 바꾸지 않았다.

## 후보 통계 전후

| 지표 | 변경 전 | 변경 후 | 변화 |
|---|---:|---:|---:|
| 주간 학사과정 정규화 전체 | 24,422 | 24,422 | 0 |
| 현재 상태(EXISTING/NEW) 후보 | 10,063 | 10,063 | 0 |
| 계약학과 정책 적용 후 추천 후보 | 10,063 | 10,057 | -6 |
| 승인 가능 후보 | 5,453 | 5,449 | -4 |
| 추천 범위 밖 보존 행 | 967 | 973 | +6 |
| 추천 후보 중복 department_id | 6 | 0 | -6 |

승인 가능 후보는 계약학과 6건 중 기존 N.C.E Queue에 있던 2건을 제외한 4건이
빠져 5,449건이다. 예상값을 생성기에 하드코딩하지 않았으며 생성기는 입력 행의 공식
필드를 기준으로 다시 계산한다.

## Queue 및 검수 통계 전후

| 지표 | 변경 전 | 변경 후 | 변화 |
|---|---:|---:|---:|
| 추천 후보 중복 Queue | 6 | 0 | -6 |
| 관계 검수 패킷 | 6 | 6 | 0 |
| 분류 REVIEW | 1,936 | 1,936 | 0 |
| N.C.E | 1,903 | 1,901 | -2 |
| URL 감사 | 37 | 37 | 0 |
| 추천 승격 검토 Queue 합계 | 3,845 | 3,837 | -8 |
| 사람 검수 패킷 행 합계 | 3,845 | 3,843 | -2 |

관계 검수 패킷 6건은 추천 승격 Queue가 아니라 원본 보존과 과정 관계를 승인하기 위한
Audit이다. 따라서 추천 후보 중복은 0건이지만 관계 권고와 사람 승인 상태는 사라지지 않는다.

## 불변식

- `department_id` 생성 함수와 인자는 변경하지 않았다.
- `day_night`를 ID에 추가하지 않았고 Migration Map도 만들지 않았다.
- 기존 35건 Master SHA-256은
  `afb5a51d55086b07237e16d2914fb065e805cf3a905b3097b2ca06a2610ae37e`로 유지한다.
- Master, 공개 Schema/API, Mock, Frontend, `data/reviews`는 수정하지 않는다.
- 분류 REVIEW 내용은 그대로이며 N.C.E에서는 계약학과 2건만 제거했다.
- 모든 중복 관계 권고의 `reviewer_1_status`는 `TBD`, `resolution_status`는 `PENDING`이다.
- `auto_approved_rows`는 0이다.

## 재현과 검증

전국 정규화·분류 입력은 `.gitignore` 대상이다. 입력이 있는 환경에서는 다음 순서로
재생성한다. 입력이 없는 clean clone에서는 기존 커밋 산출물을 부분 덮어쓰지 않고 명시적으로
중단하거나 전국 재생성 테스트를 skip하며, 작은 fixture로 같은 정책과 byte 결정성을 검증한다.
현재 작업 환경에도 두 전국 입력이 없어 변경 후 입력 SHA-256을 계산할 수 없었다. Manifest에서
변경 전 SHA를 재사용하지 않고 `unavailable_input_hashes`로 명시했으며, 입력 보유 환경에서
패킷 생성기를 실행하면 실제 변경 후 Hash가 자동 기록된다.

```bash
python scripts/career_build_academyinfo_review_queues.py --survey-year 2025
python scripts/career_build_academyinfo_review_packets.py --survey-year 2025
python -m unittest discover -s tests
python -m pip check
python -m compileall src tests scripts
git diff --check
```
