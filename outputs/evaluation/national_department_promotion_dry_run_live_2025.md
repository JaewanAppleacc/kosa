# 전국 학과 Master 승격 Dry Run — 실측(2025년 조사) — 2026-08-25 (2026-08-24 정정)

**이 문서는 실측 결과 보고서다.** `data/master/departments.jsonl`(35건)·공개
API·`data/reviews/*`는 이 실행으로 전혀 바뀌지 않았다. 이 문서 자체도
`career_build_national_department_promotion_dry_run.py`의 산출물이 아니라
그 실행 결과를 정리한 수기 보고서다(대형 산출물 `promotion_candidates.jsonl`·
`promotion_blocked.jsonl`은 Git에 올리지 않는다 — `promotion_blocked.jsonl`만
약 16MB).

## 정정 사항(a/department-identity-collision-audit, 2026-08-24)

최초 작성본(브랜치 `report/national-department-promotion-dryrun-live-2025`)이
`department_id` 충돌을 **"SHA-256 Hash Collision"**으로 표현한 것은 부정확한
용어였다 — 이번 정정판에서 전부 **"department_id identity-key 충돌"**로
고쳤다. 이유는 §1 참고: `department_id`는 우연히 부딪힌 암호학적 Hash가
아니라, `src/ids.py::generate_department_id(schl_id, department_name,
college_name)`가 **의도적으로 schlMjrId(원본 행 식별자)를 배제**하고 만드는
identity-key다. 서로 다른 `source_record_id`(다른 schlMjrId, 다른 이수연한·
학과특성)가 이 3-tuple만 같으면 구조적으로 같은 `department_id`를 받는다 —
확률적 사고가 아니라 이 키 설계 자체의 한계다.

16 Group·32행 전체의 필드별 비교(같음/다름), `source_record_id`/`schlMjrId`
동일 여부, Raw Snapshot 대조, 계약학과 6건 전체 회계는 별도 감사 패킷으로
정리했다 — 이 문서의 §1·§4는 그 패킷의 요약이고, 원본 상세는 다음을 정본으로
본다(전부 `reviewer_1_status=TBD`, `decision=TBD`, 자동 판정 0건):

- 생성 스크립트: `scripts/career_build_department_identity_collision_review.py`
- 패킷(16 Group·32행): `data/academyinfo_work/2025/packets/department_identity_collision_review.jsonl`
- 사람이 읽는 화면: `data/academyinfo_work/2025/packets/department_identity_collision_review.html`
- Manifest(24,422행 전체 회계 + 계약학과 6건 회계): `data/academyinfo_work/2025/packets/department_identity_collision_review_manifest.json`
- 테스트: `tests/worker_c/test_department_identity_collision_review.py`(24개, 전부 통과)

## 0. 실행 성격 — Fixture 아님, 실제 전국 데이터

이 실행은 `academyinfo-data-restore` Worktree에 복원된 **실제 전국 조사
데이터**(2025년, 대학알리미 공식 API 재수집 없이 기존 수집분을 복원)를 그대로
사용했다. `tests/worker_c/test_national_department_promotion_dry_run.py`의
합성 Fixture 테스트(50개)와는 완전히 다른 층위다 — 그 테스트들은 소수 합성
학과로 Gate 로직 자체를 검증하고, 이 문서는 실제 24,406건에 그 로직을 적용한
실측값이다.

## 1. 사전 검증 — 6개 ID 대조 결과

| # | 조건 | 결과 |
|---|---|---|
| 1 | `departments.normalized.jsonl` 24,422행 | ✅ 정확히 일치 |
| 2 | `classification_results.jsonl` 24,416행 | ✅ 정확히 일치 |
| 3 | 양쪽 `department_id` 중복 0건 | ❌ **불일치** — normalized 24,422행이 `department_id` 기준 24,406개 고유값으로 뭉쳐진다(**identity-key 충돌** 16개 Group·32행, classification 쪽도 같은 16개 Group에서 10개가 겹쳐 보임). **이것은 SHA-256 Hash Collision이 아니다** — `department_id`는 `(schl_id, department_name, college_name)` identity-key이고(§ 정정 사항 참고), 서로 다른 `source_record_id`가 이 3-tuple만 같으면 구조적으로 같은 `department_id`를 받는다(예: 서경대 코스메틱뷰티매니지먼트학과/헤어디자인학과 — 각각 계약학과·일반과정 쌍; 충남대 약학과 — 6년 일반과정/4년 계약학과 쌍. 35건 소규모 Demo에서는 드러나지 않던 문제). 진짜 고유 키인 `source_record_id`(schl_id+schlMjrId+연도 해시)는 24,422건 전부 고유함을 직접 확인. 정규화 단계가 이미 `duplicate_group_size` 필드로 이 충돌을 정확히 표시해뒀고(값이 실제 충돌 수와 100% 일치 확인), Dry Run의 `BLOCKED_DUPLICATE_ID` Gate가 대응한다. 16 Group·32행 전체 상세는 `department_identity_collision_review.jsonl` 참고.
| 4 | classification에 없는 normalized ID 정확히 6개 | `department_id` 기준(Set 연산이 identity-key 충돌을 뭉개 우연히 0으로 나온다): 0개(왜곡된 값) / **`source_record_id` 기준(정본): 정확히 6개 ✅**
| 5 | 그 6개가 전부 계약학과 | ✅ 6개 전부 `exclusion_reason=CONTRACT_DEPARTMENT`
| 6 | OUT_OF_RECOMMENDATION_SCOPE·CONTRACT_DEPARTMENT·Raw 보존 | ✅ 6개 전부 두 필드 일치. Raw Snapshot(`departments.raw.jsonl.gz`, 36,866행)에서 6개 전부 `(schlId, schlMjrId)` 조합으로 확인
| 7 | classification에만 있고 normalized엔 없는 ID 0개 | ✅ 0개(department_id·source_record_id 둘 다)

**사용자 확인 후 진행 결정**: 조건 3의 `department_id` 충돌은 정규화 단계가
이미 `duplicate_group_size`로 정확히 표시해뒀고 Dry Run의 기존
`BLOCKED_DUPLICATE_ID` Gate가 Fail-Closed로 대응하므로, 이 상태 그대로
진행하기로 결정했다(2026-08-25 사용자 확인).

**부수 효과(투명하게 기록, 감사 패킷으로 재확인·정정)**: `load_inputs()`는
`{row["department_id"]: row for row in departments}` 방식으로 학과 목록을
만든다 — `department_id`가 충돌하는 두 행 중 파일에서 나중에 나오는 행만
평가 대상에 남는다(먼저 나온 행은 조용히 빠진다). 원본 계약학과는 6건이고
전부 identity-key 충돌 Group의 당사자다(`duplicate_group_size=2`) — 하지만
6건이 균등하게 "4는 평가/2는 중첩"으로 나뉘는 게 아니라, 정확히 다음 두
그룹으로 나뉜다(`department_identity_collision_review_manifest.json`의
`contract_department_accounting`으로 확인):

- **평가 대상에 남아 실제로 `BLOCKED_CONTRACT_DEPARTMENT`로 집계된 4건** —
  이 4건은 자기 자신이 그 Group의 evaluated representative이기도 해서,
  전부 **동시에** `BLOCKED_DUPLICATE_ID`도 갖는다(완전히 겹친다, "2건만
  겹친다"가 아니다).
  예: 충남대학교 약학과(계약학과, 4년) — 대표로 남아 두 사유 모두 부여됨.
- **평가 대상에서 아예 빠져 `BLOCKED_CONTRACT_DEPARTMENT` 사유 자체가
  계산되지 않은 2건** — 서경대학교 헤어디자인학과·코스메틱뷰티매니지먼트학과.
  이 둘은 "겹치는" 게 아니라 **애초에 Dry Run의 평가 대상에 들어가지도
  않은** 제3의 범주다. 두 학과 모두 `normalized.jsonl` 원본과 새 감사
  패킷(§ 정정 사항)에는 그대로 남아 있다 — Dry Run 평가 목록 구성 방식이
  identity-key 충돌 상황에서 한쪽만 대표로 뽑는다는 사실을 그대로 보여준다.

그래서 `BLOCKED_CONTRACT_DEPARTMENT`는 원본 6건이 아니라 **4**로 집계된다
(§4 통계에 그대로 반영). 충남대학교 약학과의 **일반과정(6년) 대응 행**은
계약학과가 아니라서 이 6건 집계에는 들어가지 않지만, 그 행 역시 삭제되지
않고 감사 패킷에 dropped 후보로 보존돼 있음을 재검증했다(§4 계약학과 표
참고).

## 2. Snapshot Hash

| 파일 | SHA-256 | 사전 제공 값과 일치 |
|---|---|---|
| `departments.normalized.jsonl` | `eb51a8fbfa063916d135fdead4e179d436f424e4abc2d6502e11128198931ca7` | ✅ 일치 |
| `classification_results.jsonl` | `7a4fb73743bbee5af360619ed6b6f01e130d2e954244e26217d6b6aacb924fd1` | ✅ 일치 |
| `departments.raw.jsonl.gz`(새로 계산) | `3b93a14c254d58c5b0dad50d0aad8cbc3082962c0452f30e82171cc23005290b` | (사전 제공값 없음 — 이번에 처음 계산) |

- 조사연도(survey_year): **2025**
- 수집 시각(`collection_manifest.json`): `collected_at=2026-08-24T18:58:41+09:00`, `finished_at=2026-08-24T19:09:15+09:00`
- 이전 Snapshot과 byte-identical이라고 표현하지 않는다 — 이번이 이 실측 계열의
  **첫 번째** 실제 전국 규모 Hash 기록이다(비교 대상이 되는 "이전 실제 전국
  Snapshot"이 존재하지 않는다).
- 두 입력 파일(`departments.normalized.jsonl`/`classification_results.jsonl`)
  실행 전후 Hash 재확인 — 실행 전후 완전히 동일(읽기 전용 사용 증명).

## 3. 실행 방식 — 입력 격리

`career_build_national_department_promotion_dry_run.py`는 `--data-dir`
하나로 여러 정본 파일 경로를 한꺼번에 정한다. 저장소에 이미 커밋된
**과거(더 작은 규모) `out_of_recommendation_scope.jsonl`**(973행,
`f7dd584` 커밋, 이번 전국 복원과 다른 시점의 산출물)이 기본 경로에
남아 있어서, `--data-dir`를 저장소 그대로 쓰면 오늘 복원한 24,422건과
그 옛 파일이 섞여 "평가 대상 24,794건"처럼 왜곡된 숫자가 나왔다(1차 실행에서
발견 즉시 폐기).

이를 피하려고 별도 임시 데이터 디렉터리를 만들어 실행했다:
- `departments.normalized.jsonl`/`classification_results.jsonl` — 지정된
  두 경로에서 **복사**(원본 무변경 확인)
- `data/canonical_major_groups.draft.jsonl`·
  `data/master/canonical_major_group_bridge.draft.jsonl`·
  `data/master/canonical_majors.jsonl`·
  `data/academyinfo_raw/2025/codes/getCodeBySmallSeries.jsonl.gz`·
  `data/reviews/`·P1/N.C.E Draft 패킷 — 이 Worktree의 실제 파일을
  **읽기 전용 Symlink**로 연결(대학알리미 API 재호출 없음, 이 저장소의 실제
  검수 상태를 그대로 사용)
- `out_of_recommendation_scope.jsonl`(야간·원격 제외 목록)과
  `department_url_scope_audit.jsonl`(URL 감사)은 **이번에 명시적으로
  제공되지 않은 입력**이라 포함하지 않았다 — §4의 "야간·원격 제외 수"가
  0으로 나오는 것은 "야간·원격 학과가 없다"가 아니라 "이번 라운드에는 그
  판정에 필요한 파일이 인가되지 않아 애초에 평가 대상에 없다"는 뜻이다(과소
  집계, 숨기지 않고 명시).

## 4. 필수 결과 집계

### 4-1. 전체·상태·범위(원본 24,422행 기준)

- 전체 입력(normalized 원본 행 수): **24,422**
- 현재 상태 EXISTING+NEW(원본 기준): **10,063**(EXISTING 9,051 + NEW 1,012)
  - 참고: ABOLISHED 14,268 / SPLIT 34 / MERGED 57
- 추천 범위 안(IN_RECOMMENDATION_SCOPE): **24,416**
- 추천 범위 밖(OUT_OF_RECOMMENDATION_SCOPE): **6**(전부 CONTRACT_DEPARTMENT — §1 참고)

### 4-2. Dry Run 평가 결과(department_id 충돌로 24,406건 평가 — §1 참고)

- 평가 대상: **24,406**
- READY_FOR_PROMOTION: **0**
- BLOCKED: **24,406**
- 현재 검수 상태(Group Draft·Bridge Mapping·Bridge Scope·P1·N.C.E)만으로 막힌 건: **3,232**

### 4-3. 차단 사유별 행 수(중복 집계 — 한 행이 여러 사유를 가질 수 있음)

| 사유 | 건수 |
|---|---:|
| BLOCKED_GROUP_DRAFT | 20,733 |
| BLOCKED_NO_SERVICE_CANONICAL_MAJOR | 11,856 |
| BLOCKED_INACTIVE_STATUS | 14,352 |
| BLOCKED_P1_REVIEW_UNRESOLVED | 4,257 |
| BLOCKED_BRIDGE_SCOPE_REVIEW | 5,844 |
| BLOCKED_NCE_UNRESOLVED | 3,534 |
| BLOCKED_ARTS_RECOMMENDATION | 3,637 |
| BLOCKED_BRIDGE_MAPPING_REVIEW | 3,443 |
| BLOCKED_OUTSIDE_SMALL_SERIES_SCOPE | 1,822 |
| BLOCKED_DUPLICATE_ID | 16 |
| BLOCKED_CONTRACT_DEPARTMENT | 4(원본 6건 중 4건이 평가 대상 — 전부 BLOCKED_DUPLICATE_ID와 완전히 겹침. 나머지 2건은 identity-key 충돌로 평가 자체가 안 됨 — §1·§4-8 참고) |
| BLOCKED_AMBIGUOUS_SERVICE_CANONICAL_MAJOR | 0 |
| BLOCKED_BRIDGE_EXCLUDED_RECOMMENDATION | 0 |
| BLOCKED_CLASSIFICATION_REVIEW | 0 |
| BLOCKED_MISSING_CLASSIFICATION | 0 |
| BLOCKED_MISSING_LINEAGE | 0 |
| BLOCKED_NIGHT_OR_REMOTE | 0(§3 — 입력 미제공으로 측정 불가, "0건 존재"가 아님) |
| BLOCKED_OUT_OF_RECOMMENDATION_SCOPE | 0 |
| BLOCKED_URL_POLICY | 0(URL 감사 입력 미제공) |

### 4-4. 복수 차단 사유 조합 — 상위 15개(전체 38개 조합 중)

| 건수 | 조합 |
|---:|---|
| 6,268 | GROUP_DRAFT, INACTIVE_STATUS, NO_SERVICE_CANONICAL_MAJOR |
| 3,676 | GROUP_DRAFT, NO_SERVICE_CANONICAL_MAJOR |
| 1,965 | ARTS_RECOMMENDATION, GROUP_DRAFT, INACTIVE_STATUS |
| 1,198 | NCE_UNRESOLVED (단독) |
| 1,188 | ARTS_RECOMMENDATION, GROUP_DRAFT |
| 1,002 | GROUP_DRAFT, INACTIVE_STATUS, NO_SERVICE_CANONICAL_MAJOR, P1_REVIEW_UNRESOLVED |
| 983 | BRIDGE_SCOPE_REVIEW, GROUP_DRAFT, INACTIVE_STATUS |
| 976 | INACTIVE_STATUS, NCE_UNRESOLVED |
| 807 | BRIDGE_MAPPING_REVIEW, BRIDGE_SCOPE_REVIEW, GROUP_DRAFT, INACTIVE_STATUS |
| 769 | GROUP_DRAFT, NO_SERVICE_CANONICAL_MAJOR, P1_REVIEW_UNRESOLVED |
| 765 | BRIDGE_MAPPING_REVIEW, BRIDGE_SCOPE_REVIEW, GROUP_DRAFT, OUTSIDE_SMALL_SERIES_SCOPE |
| 759 | BRIDGE_MAPPING_REVIEW, BRIDGE_SCOPE_REVIEW, GROUP_DRAFT, INACTIVE_STATUS, OUTSIDE_SMALL_SERIES_SCOPE |
| 539 | BRIDGE_SCOPE_REVIEW, GROUP_DRAFT, INACTIVE_STATUS, P1_REVIEW_UNRESOLVED |
| 526 | BRIDGE_MAPPING_REVIEW, BRIDGE_SCOPE_REVIEW, GROUP_DRAFT |
| 499 | NCE_UNRESOLVED, P1_REVIEW_UNRESOLVED |

가장 작은 조합(1건)은 `DUPLICATE_ID, GROUP_DRAFT, INACTIVE_STATUS,
NO_SERVICE_CANONICAL_MAJOR, P1_REVIEW_UNRESOLVED` 등 §1의 department_id
충돌 사례와 겹치는 행들이다.

### 4-5. Canonical Major Group별 — Group까지는 해결됐지만 아직 READY는 아닌 건수

READY_FOR_PROMOTION이 0건이므로 **Group별 READY 수는 42개 전부 0**이다.
아래는 참고용으로, "이 Group으로 후보가 좁혀졌지만 아직 Group Draft가
`approved`가 아니라 막힌 행 수"(상위 10개, 42개 Group 전부가 여전히
`review_status=draft`이므로 사실상 전부 여기 해당):

| Group | 건수 |
|---|---:|
| computer_science | 1,284 |
| business | 1,270 |
| fine_arts_design | 1,262 |
| electrical_electronic | 1,136 |
| civil_architecture | 1,119 |
| foreign_language | 1,083 |
| mechanical_transport | 1,047 |
| sports_dance | 916 |
| education | 810 |
| social_welfare | 630 |
| (그 외 32개 Group 생략, 합계 20,733) |  |

### 4-6. 서비스 Canonical Major(10개)별 — READY 수 / Bridge까지 해결된 건수

**서비스 Canonical Major 10개별 READY 수는 전부 0**이다. 아래는 참고용으로
"Bridge Mapping까지 EVIDENCED 1개로 해결됐지만(Mapping/Scope 검수 미승인 등
다른 이유로) 아직 READY가 아닌 건수":

| 서비스 Major | 건수 |
|---|---:|
| computer_science | 1,284 |
| business_administration | 1,270 |
| mechanical_engineering | 1,047 |
| education | 810 |
| life_science | 595 |
| media_communication | 351 |
| industrial_engineering | 316 |
| psychology | 171 |
| **design** | **0**(Bridge EVIDENCED 후보로 한 번도 해결되지 않음) |
| **hci_ux** | **0**(Bridge EVIDENCED 후보로 한 번도 해결되지 않음 — DEPARTMENT_REVIEW_REQUIRED Scope라 애초에 자동 해결 대상이 아님) |

### 4-7. 검수·정책 차단 수(§4-3과 동일 값, 재정리)

- P1 미검수 차단 수: **4,257**
- N.C.E 미해결 차단 수: **3,534**
- Bridge Mapping 미승인 차단 수: **3,443**
- Bridge Scope 미승인 차단 수: **5,844**
- 예체능 제외 수: **3,637**
- 계약학과 제외 수: **4**(BLOCKED_CONTRACT_DEPARTMENT로 실제 집계된 건수. 원본
  계약학과는 6건 — §4-8 전체 회계 참고)
- 야간·원격 제외 수: **측정 안 함**(§3 — 입력 미제공)
- 후보 없음(BLOCKED_NO_SERVICE_CANONICAL_MAJOR): **11,856**
- 복수 후보(BLOCKED_AMBIGUOUS_SERVICE_CANONICAL_MAJOR): **0**
- Lineage `ROW_IDENTITY_ONLY`: **24,406**(평가된 행 전부 — `CROSS_YEAR_LINEAGE_VERIFIED`는 한 건도 없음)

### 4-8. identity-key 충돌 16 Group·32행 / 계약학과 6건 전체 회계

`department_identity_collision_review_manifest.json`(정본)에서 그대로 가져온
행수 회계 — 단위를 섞지 않도록 명확히 분리한다:

| 단위 | 값 |
|---|---:|
| normalized 입력 행 | 24,422 |
| classification 행 | 24,416 |
| 고유 `department_id` 수 | 24,406 |
| identity-key 충돌 Group 수 | 16 |
| 충돌 Group 소속 원본 행(32 = 16×2) | 32 |
| 파일 순서상 나중 행 이외 — 평가 대상에서 빠진 행 | 16 |
| classification 누락 행(`source_record_id` 기준, 정본) | 6 |
| 누락 6건 전부 계약학과인가 | 예 |
| classification에만 있고 normalized엔 없는 ID | 0 |

**계약학과 6건 전체 회계**(department_id 기준 Set 연산이 아니라 각 행을
개별적으로 추적한 값):

| 구분 | 건수 |
|---|---:|
| 원본 계약학과(전체) | 6 |
| Dry Run 평가 대상에 남아 `BLOCKED_CONTRACT_DEPARTMENT`로 나타난 행 | 4 |
| identity-key 충돌로 평가 대상에서 아예 빠진 행 | 2 |
| 최종 추천 노출(READY_FOR_PROMOTION) | 0 |
| `departments.normalized.jsonl` 원본 + 감사 패킷에 보존된 행 | 6 |

4건은 `BLOCKED_CONTRACT_DEPARTMENT`와 `BLOCKED_DUPLICATE_ID`를 동시에
갖는다(완전히 겹침). 2건(서경대 헤어디자인학과·코스메틱뷰티매니지먼트학과)은
"차단 사유가 겹치는" 게 아니라 evaluate_department() 자체가 호출되지 않는
제3의 범주다 — 6건 전부 사라지지 않았다는 것이 두 저장소(원본 normalized·
감사 패킷) 모두에서 확인된다. 충남대학교 약학과의 **일반과정(6년) 대응 행**
(계약학과 아님)도 삭제되지 않고 dropped 후보로 감사 패킷에 남아 있음을
재검증했다.

## 5. 검수 상태 해석 확인

- P1 검수 파일(`academyinfo_p1_classification_review_status.jsonl`) —
  Manifest에 `MISSING` 기록. 미검수 Fail-Closed로 4,257건 차단.
- N.C.E 검수 파일 — Manifest에 `MISSING` 기록. 미해결 Fail-Closed로 3,534건 차단.
- Bridge Scope 검수 파일 — Manifest에 `MISSING` 기록(아직 사람이 검토한
  Scope 승인이 없음). 5,844건 차단.
- N.C.E `ACCEPT_GROUP_AS_REVIEW_CANDIDATE`는 애초에 파일이 없어 해당 없음
  — 있었더라도 승격 근거로 해석되지 않는다(코드 구조상
  `resolved_canonical_major_group_id`를 만들 방법이 없음, 이전 라운드 확인 완료).
- Bridge Scope draft는 승인으로 해석하지 않았다(`scope_review_status`
  필드가 아니라 실제 검수 파일 존재 여부·`reviewer_1_status`로 판정).
- READY_FOR_PROMOTION=0은 정상 결과로 그대로 기록했다 — Fixture나 임시
  승인을 주입해 숫자를 늘리지 않았다.

## 6. 2회 실행 재현성

같은 입력(같은 임시 데이터 디렉터리)으로 별도 임시 출력 디렉터리 2곳에
각각 실행 → 5개 산출물(`promotion_candidates.jsonl`·`promotion_blocked.jsonl`·
`promotion_summary.json`·`promotion_summary.md`·`promotion_manifest.json`)
전부 **byte-identical** 확인(`diff -rq` 결과 차이 없음). 입력 파일
Hash는 실행 전후 동일(§2).

## 7. Master·Review·Mock 무변경

- `data/master/departments.jsonl`: **35행**, 이 실행 전후 `git status`
  변화 없음.
- `data/reviews/`: `git status --porcelain` 변화 없음(이 실행이 어떤
  검수 파일도 생성·수정하지 않았다 — P1/N.C.E/Bridge Scope 검수 파일이
  여전히 `MISSING`인 채로 남아 있음).
- `outputs/mock_api/`·`openapi.json`: 재생성 후 byte-identical(git diff
  없음).
- 공개 API Schema·`frontend/`·Context/Coverage 관련 파일: 이 세션에서
  전혀 건드리지 않음(`git status --porcelain` 완전히 비어 있음).

## 8. 실제 실행 vs Fixture 실행 구분

- **이 문서는 실제 실행 결과다** — 복원된 국가 규모 조사 데이터(24,422행)를
  실제로 읽어 계산했다.
- `tests/worker_c/test_national_department_promotion_dry_run.py`의 50개
  테스트는 여전히 **소수 합성 Fixture** 검증이다(Gate 로직 자체의 정확성을
  빠르게 검증하는 용도) — 이번 실제 실행과는 독립적이며, 이번 실행이 그
  테스트 결과를 대체하지 않는다.
- 이번 실행에 사용한 정규화·분류 결과는 **API 재호출 없이** 기존에 수집된
  Raw 스냅샷을 복원해 만든 것이다(§0/§2).

## 9. 전국 Master 승격 가능 여부 판단

**현재 상태로는 전국 승격이 불가능하다.** READY_FOR_PROMOTION 0건의 근본
원인은 데이터 품질이 아니라 **사람 검수가 아직 하나도 완료되지 않았다는
것**이다:

- 42개 Canonical Major Group Draft 전부 `review_status=draft`(0개 approved)
  → 어떤 학과도 이 Gate를 통과할 수 없음(20,733건이 여기서 막힘).
- Bridge Scope 검수 파일 자체가 없음(5,844건 차단).
- P1(4,257건)·N.C.E(3,534건) 검수도 파일 자체가 없음.

반대로 **구조적으로 막힌 학과 수(BLOCKED_NO_SERVICE_CANONICAL_MAJOR
11,856건, BLOCKED_INACTIVE_STATUS 14,352건 등)는 검수와 무관하게 이미
정해진 값**이라, 검수를 전부 완료해도 전체 24,406건이 다 승격 대상이
되지는 않는다. "현재 검수 상태만으로 막힌 건"(3,232건, §4-2)이 검수
완료 시 최대로 늘어날 수 있는 상한에 가장 가까운 근사치다 — 다만 이 값도
그 학과들이 검수를 통과한다고 가정한 것이지, 실제 승인 여부를 예측하지
않는다.

department_id identity-key 충돌(§1·§4-8, 16 Group·32행)은 정규화 단계의
근본적인 재작업 없이도 `BLOCKED_DUPLICATE_ID` Gate가 안전하게 처리하고
있으나, `load_inputs()`가 충돌 쌍 중 한쪽만 평가 목록에 남기는 부수 효과가
있다는 점은 향후 승격 전 반드시 해소해야 할 별도 과제로 남긴다(이번 라운드의
코드 수정 범위 밖 — `department_id` 생성 규칙 자체를 바꾸지 않았다). 16
Group 전부 사람 검수 대기(`reviewer_1_status=TBD`, `decision=TBD`) 상태로
`a/department-identity-collision-audit` 브랜치에 감사 패킷으로 넘겼다.

## 10. Commit/Push

최초 버전은 `report/national-department-promotion-dryrun-live-2025` 브랜치에
결정론적 소형 보고서로 커밋됐다. 이 정정판은 `a/department-identity-
collision-audit` 브랜치(base `origin/trait-vector-v2 @ aff7159`)에 감사
패킷(16 Group·32행, HTML, Manifest)·스크립트·테스트와 함께 커밋한다(대형
산출물 `promotion_candidates.jsonl`·`promotion_blocked.jsonl`과 원본
정규화·분류·Raw Snapshot은 Git에 올리지 않음). `trait-vector-v2`에는
병합·Push하지 않았다.
