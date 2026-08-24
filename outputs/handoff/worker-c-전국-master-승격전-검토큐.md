# 작업자 C 완료 보고 ③ — Master 승격 전 검토 Queue

작성 2026-08-24 · 브랜치 `worker-c` · 기준 커밋 `7436af7`
정본 정책: `outputs/handoff/academyinfo_a_decisions.md`
이전 보고: `worker-c-완료보고-전국수집분류.md`

---

# A가 판단해야 할 것 — 3건

## ① 중복 588건의 97%가 주야간이다 — `department_id` 규칙 문제일 수 있다

중복 원인을 갈라 보니 한쪽으로 쏠렸다.

| 원인 | 그룹 수 |
|---|---|
| **주야간이 갈림** | **573** (97.4%) |
| 학과 상태가 갈림(폐지 이력) | 112 |
| 수업연한이 갈림 | 2 |
| 검사 필드에서 차이 없음 | 12 |

*(한 그룹이 여러 원인에 걸릴 수 있어 합계는 588을 넘는다)*

`generate_department_id(schl_id, 학과명, 단과대학)`에 **주야간이 들어가지 않는다.** 그래서
같은 대학·같은 학과명·같은 단과대학의 **주간 과정과 야간 과정이 같은 id를 받는다.**

**이건 데이터 문제가 아니라 id 규칙 문제로 보인다.** 주간과 야간은 대학알리미가 별도
`schlMjrId`로 관리하는 서로 다른 편제단위다. 588건 중 573건이 이 한 가지 이유다.

**C는 `src/ids.py`를 고치지 않았다** — A 소유이고, A 결정 §7-1이 "자동 대표 선정 금지
원칙 유지"라고만 했지 id 규칙 변경은 범위 밖이다. **판단을 요청한다.**

| 선택지 | 결과 |
|---|---|
| **A. id 해시에 주야간 추가** | 중복 573건이 사라진다. 단 **기존 35건 Master의 `department_id`가 전부 재생성**되고 canonical 매핑 34건이 재검수 대상이 된다 |
| B. 그대로 두고 573건을 사람이 확정 | id 규칙은 안정적이지만 검토 573건이 실제로는 "같은 학과의 주/야간"이라 판정이 기계적이다 |
| C. 주야간 과정을 아예 수집 범위에서 제외 | 야간 학과를 지망하는 학생을 놓친다 |

C 권고는 **A**다. 다만 Master 재생성을 동반하므로 A 결정 §4(승격 보류)와 함께 판단해야 한다.

**나머지 15건**(상태 이력·수업연한·차이 없음)은 성격이 달라 사람이 봐야 한다.

## ② N.C.E와 분류 REVIEW가 984건 겹친다 — 없애지 않고 표시했다

```
N.C.E UNMAPPED     3,657
분류 REVIEW         4,454
겹치는 행             984
```

**버그가 아니라 축이 다르기 때문이다.** "어느 전공군인가"(분류)와 "추천해도 되나"(적격성)는
별개 질문이고 둘 다 미결일 수 있다. 예: 가천대 미술·디자인학부(패션디자인)는 공식 소계열이
`N.C.E.`(분류 없음)이면서 동시에 명칭이 `디자인`이라 예체능 확인이 필요하다.

겹침을 없애면 한쪽 근거가 사라지므로, **상호 참조 플래그를 붙여 드러냈다.**

```
classification_review_queue.jsonl  →  also_in_unmapped_nce_queue: true/false
unmapped_nce_queue.jsonl           →  also_in_classification_review_queue: true/false
```

**A가 정할 것:** 검토 순서. 984건을 한 번에 처리할지(분류 근거가 생기면 적격성 판정도
쉬워진다), 아니면 두 흐름을 따로 돌릴지.

## ③ HTTP만 지원하는 학과 홈페이지 3건 — 우리가 못 고친다

A 지시 §4의 "HTTPS 사용 가능 여부"를 실측했다.

```
http://cse.hanyang.ac.kr/                                한양대 컴퓨터소프트웨어학부
http://idesign.hanyang.ac.kr/page/?pid=dep_communication  한양대 커뮤니케이션디자인학과
http://me.pusan.ac.kr/new/main/                          부산대 기계공학부
```

셋 다 `https://`로 바꿔 접속하면 **`ConnectError`** — 학교 서버가 HTTPS를 아예 열지 않는다.
우리가 URL을 잘못 넣은 게 아니라 **그 학교가 아직 HTTP만 쓴다**는 사실이다.

**C 판정: `DEPARTMENT_SCOPE_CONFIRMED`로 뒀다.** HTTP라는 이유만으로 보류하면 그 학과
학생은 영영 홈페이지 링크를 못 본다. 다만 `findings`에 사실을 기록했다.

**A가 정할 것:** 공개 시 HTTP 링크를 그대로 쓸지. 브라우저가 "안전하지 않음"을 표시한다.

---

# A 지시 §7 보고 항목

## 1. 중복 Queue 실제 그룹 수

**588 그룹 / 원본 행 1,183건.** 보고 수치와 일치(테스트로 고정).

각 그룹에 담은 것: `department_id` · `source_record_ids` 목록 · 대학 · 캠퍼스 · 학과명 ·
단과대학 · 모집단위 · 주야간 · 학위과정 · 조사연도 · `differing_fields` ·
`duplicate_cause_candidates` · `decision_status` · `reviewer_comment`.

**자동 대표 행을 고르지 않았다.** `selected_source_record_id`는 전부 `null`이다.
재학생 수는 **보여주되 선택 근거로 쓰지 않았다** — 신설 학과는 0명이라 그 기준이 즉시
반례를 만든다. 재학생 0명 행과 85명 행이 섞인 그룹이 실제로 존재하며, 테스트가 그런
그룹에서도 대표가 선정되지 않았음을 확인한다.

**원본 전체를 복제하지 않았다** — 교육목표·교과목 해시 같은 무거운 필드는 Queue에 넣지
않았고, 테스트가 이를 검사한다.

## 2. REVIEW_REQUIRED 원인별 개수

**총 4,454건.**

| 원인 | 건수 | 뜻 |
|---|---|---|
| `CONVERGENCE` | 3,515 | 융합·자유전공·연계·통합 명칭 |
| `MEDIA_CONTENT` | 694 | 미디어·콘텐츠·영상·게임·애니 명칭 |
| `DESIGN` | 241 | 디자인 명칭 |
| `HCI_UX` | 4 | HCI·UX·인터랙션 명칭 |

`SERIES_NAME_CONFLICT`(공식 소계열과 학과명 충돌)와 `OTHER`는 0건이다 — 4,454건 전부가
명칭 신호로 걸렸다. **원인은 하나만 붙인다.** 우선순위는 `HCI_UX > DESIGN >
MEDIA_CONTENT > CONVERGENCE` 순이며, 한 학과가 여러 신호에 걸려도 "어느 근거로
보류됐는지"가 하나로 정해져야 검토자가 헷갈리지 않기 때문이다.

**예체능 가능성**(판정이 아니라 확인 대상 표시):

```
POSSIBLE_NEEDS_CHECK   939    디자인·미디어·HCI 명칭 → 공식 교육과정 확인 필요
UNLIKELY             3,515    융합 명칭이지만 예체능 신호는 없음
```

각 행에 `official_evidence_needed`로 **무엇을 확인해야 하는지** 넣었다 —
공식 교육과정 / 공식 단과대학 소속 / 공식 입학전형의 실기·실적 전형 여부.

**LLM·문자열 유사도만으로 APPROVE한 행은 0건이다.** 전부 `REVIEW_REQUIRED`이고
`reviewer_id`가 `null`이다.

## 3. N.C.E Queue 개수

**3,657건.** 전부 `mapping_status: UNMAPPED`, `candidate_canonical_major_ids: []`.

**42개 Group에 강제 배정한 행이 0건**임을 테스트로 고정했다. 각 행에
`promotion_condition`을 넣어, 공식 소계열이 채워지거나 공식 교육과정·교육목표 근거가
확보될 때만 분류 후보를 만들 수 있게 했다 — **학과명 유사도로 배정하지 않는다.**

## 4. URL 37건 최종 판정

| 상태 | 건수 |
|---|---|
| `DEPARTMENT_SCOPE_CONFIRMED` (공개 후보) | **34** |
| `COLLEGE_SCOPE_KEEP_INTERNAL` (공개 시 `None`) | **3** |
| `REVIEW_REQUIRED` | 0 |

감사 항목별 결과:

- **공식 대학 도메인** — 37건 전부 `.ac.kr`
- **API Key 포함 URL** — 0건
- **대학알리미·공공데이터포털 URL** — 0건
- **HTTPS** — 34건 사용, 3건 HTTP만(실측상 학교 서버가 HTTPS 미지원 → ③)
- **리다이렉트 최종 목적지** — URL 수집 시점에 `follow_redirects`로 최종 도착지를 확인해
  기록한 값이다(예: `cs.yonsei.ac.kr` → `/csai/index.do`)

**college scope 3건은 공개 후보에서 제외**되며, **값과 사유(`department_url_note`)는
버리지 않고 보존**한다. 테스트가 이 둘을 함께 검사한다.

## 5. 자동 처리하지 않은 항목과 이유

| 항목 | 왜 자동으로 안 했나 |
|---|---|
| 중복 588건 대표 행 | 재학생 수로 고르면 신설 학과(0명)가 탈락한다. 주야간이 원인인 573건도 "어느 쪽이 대표인가"는 기획 판단이다 |
| 분류 REVIEW 4,454건 | 명칭 신호만으로는 예체능 여부를 알 수 없다. 공식 교육과정이 근거다 |
| N.C.E 3,657건 | N.C.E는 분류명이 아니라 "분류 없음" 센티널이다. 유사도로 배정하면 근거 없는 추천이 된다 |
| 주야간 id 규칙 | `src/ids.py`는 A 소유다. 비교 근거만 제출한다(①) |
| college URL 3건 | A 결정 §5대로 공개에서 제외했을 뿐, 데이터에서 지우지 않았다 |
| Master 승격 | A 결정 §4대로 보류. 35건 그대로다 |

## 6. 수정 파일

**신규**
```
scripts/career_build_academyinfo_review_queues.py       Queue 4종 생성
tests/worker_c/test_academyinfo_review_queues.py        35 tests
data/academyinfo_work/2025/duplicate_department_review_queue.jsonl    588행 · 976KB
data/academyinfo_work/2025/classification_review_queue.jsonl        4,454행 · 4.7MB
data/academyinfo_work/2025/unmapped_nce_queue.jsonl                 3,657행 · 3.2MB
data/academyinfo_work/2025/department_url_scope_audit.jsonl             37행 · 19KB
data/academyinfo_work/2025/review_queue_report.json
```

**수정**
```
scripts/career_normalize_academyinfo.py   주야간(day_night_name)·본분교(campus_division_name)
                                          필드 추가 — A 지시 §1이 요구한 Queue 필드다
.gitignore                                Queue 4종을 커밋 대상으로 예외 처리
```

## 7. 테스트 결과

```
python -m unittest discover -s tests -t .
Ran 943 tests — OK        (이번 작업 신규 35개)
```

신규 35개가 검사하는 것: Queue 행 수가 기존 보고와 일치 · 중복 그룹 id 중복 없음 ·
자동 대표 선정 없음 · 재학생 0명 그룹에서도 미선정 · 원본 전체 복제 없음 ·
REVIEW 원인 4종 분리 · 자동 APPROVE 없음 · N.C.E 강제 매핑 없음 · N.C.E를 학문 분야로
해석하지 않음 · URL 37건 보존 · college scope가 공개 후보에 없음 · college URL·사유 보존 ·
API Key 미포함 · HTTP-only를 사실로 기록 · **결정론적 재생성(재실행 후 Byte-identical)** ·
Master 35건 무변경.

## 8. 대용량·Secret 검사

**Queue 총 9MB.** GitHub 파일당 100MB 제한에 한참 못 미치고, 최대 파일이 4.7MB다.

**압축하지 않고 커밋한다.** 이유:

- Queue는 **사람이 처리할 작업 목록**이다. gz로 묶으면 1MB로 줄지만 검토자가 `grep`·열람을
  못 한다.
- **생성 입력(`departments.normalized.jsonl`·`classification_results.jsonl`)이 `.gitignore`
  대상**이라, 클론한 사람은 Queue를 재생성할 수 없다. 커밋하지 않으면 검토 자체가 불가능하다.
- JSONL은 텍스트라 git 델타 압축이 먹는다(gz는 안 먹는다 — `rationale_c/07` §7-14).

**136MB 전국 Raw 원본은 계속 제외**한다. `data/academyinfo_raw/file_dataset/`(6MB xlsx)도
제외 상태다.

**Secret 검사:** Queue 4종 전문에서 `serviceKey`·`DATA_GO_KR_SERVICE_KEY`·`apikey`·
`access_token` 문자열 0건(테스트로 고정). 스테이지 diff에서 실제 Key 문자열 0건.

## 9. 기존 Master/API 무변경 증명

```bash
git diff --exit-code -- data/master/departments.jsonl src/schemas/ outputs/mock_api/
→ 변경 없음
```

- `data/master/departments.jsonl` **35행 그대로**(테스트가 행 수를 고정)
- `src/schemas/major.py` 무변경 — 공개 Department Schema를 건드리지 않았다
- `outputs/mock_api/` 무변경
- Master 행에 `department_url_scope`가 들어가지 않았음을 테스트로 확인

**A 결정 문서가 참조하는 파일 중 worker-c에 없는 것이 있다.** 아래 4개는 A의
`integration/academyinfo-pipeline` 브랜치에만 있다.

```
src/services/department_url_promotion.py
tests/test_canonical_major_groups_draft.py
tests/test_department_url_promotion.py
tests/test_academyinfo_collection_safety.py
```

C 작업엔 지장이 없지만, 나중에 두 브랜치를 합칠 때 **같은 기능이 두 벌 존재할 수 있다** —
예를 들어 URL scope 판정이 A의 `resolve_department_url_for_promotion()`과 C의
`department_url_scope_audit.jsonl` 양쪽에 있다. 통합 시 어느 쪽을 정본으로 할지 정해야 한다.

## 10. A에게 필요한 다음 판단

1. **주야간 id 규칙** (①) — 중복 588건의 97%가 여기서 나온다. 고치면 Master 재생성 동반
2. **N.C.E ↔ 분류 REVIEW 984건 겹침** (②) — 한 번에 볼지 따로 볼지
3. **HTTP-only 3건 공개 여부** (③)
4. **검토 인력·순서** — 총 8,111건(중복 588 + 분류 4,454 + N.C.E 3,657, 겹침 984 제외 시
   7,127건)이 대기 중이다. 원인별로 성격이 달라 한 사람이 다 볼 일은 아니다
5. **A/C 중복 구현 정리** (§9) — 통합 시 정본을 어느 쪽으로 할지

---

## 실행 방법

```bash
python scripts/career_build_academyinfo_review_queues.py --survey-year 2025
```

정규화·분류 결과가 있어야 한다. 없으면 앞 단계를 먼저 돌린다.

```bash
python scripts/career_collect_academyinfo_departments.py          # 연도 자동 선택
python scripts/career_normalize_academyinfo.py --survey-year 2025
python scripts/career_classify_academyinfo.py --survey-year 2025
```

---

# 보완 라운드 (2026-08-24, `d26213a` 기준)

A 결정 3건을 반영했다. 정책·근거는 `academyinfo_a_decisions.md` §10~§12.

## 1. 24,422건 상태별 구성

```
주간 학사과정 정규화 데이터   24,422
  ABOLISHED  14,268   (58.4%)
  EXISTING    9,051
  NEW         1,012
  MERGED         57
  SPLIT          34
```

**24,422는 승격 후보 수가 아니다.** "주간 학사과정 정규화 데이터"다.

## 2. EXISTING+NEW 후보 수

```
현재 상태 1차 후보    10,063
실제 승인 가능 후보    5,453
```

`5,453`은 10,063에서 예체능 제외·분류 REVIEW·N.C.E를 걸러낸 수다. **사람 검토 전이므로
"승인된 수"가 아니라 "승인 가능 후보 수"**다.

세 층을 따로 세는 이유: 하나로 뭉치면 "몇 건을 학생에게 추천할 수 있나"에 답할 수 없다.

## 3. Queue별 수정 전후

| Queue | 전 | 후 | 감소 |
|---|---|---|---|
| 중복 그룹 | 16 | **6** | −10 |
| 분류 REVIEW | 4,258 | **1,936** | −2,322 |
| N.C.E | 3,539 | **1,903** | −1,636 |
| URL 감사 | 37 | 37 | 0 (상태 무관) |
| **검토 대기 합계** | 7,813 | **3,845** | **−3,968** |

폐지·통합·분리 학과가 검토 대기의 절반이었다. 어차피 승격 대상이 아니라 **검토자가 고를
이유가 없던 행들**이다. Raw·Lineage·Audit에는 그대로 있다.

### 누적 감소

```
최초        중복 588 · 분류 4,454 · N.C.E 3,657   합계 8,111 (겹침 984 제외 시 7,127)
야간 제외   중복  16 · 분류 4,258 · N.C.E 3,539   합계 7,813
상태 필터   중복   6 · 분류 1,936 · N.C.E 1,903   합계 3,845
```

## 4. Clean clone 테스트 결과

`tests/worker_c/test_academyinfo_queue_clean_clone.py` — **12 tests, 전부 통과.**

| 구분 | 항목 | 입력 필요 |
|---|---|---|
| 항상 수행 | 커밋된 Queue 존재·행 수·JSONL 유효성·Hash 안정성 | ❌ |
| 항상 수행 | 모든 행이 미결 상태(승인된 행 없음)·reviewer 미기입 | ❌ |
| 항상 수행 | Secret 문자열 미포함 | ❌ |
| 항상 수행 | Queue 보고서 수치와 커밋된 파일 일치 | ❌ |
| 항상 수행 | **Fixture 4행으로 생성 결정론성 검증** | ❌ |
| 항상 수행 | Fixture에서 ABOLISHED 제외 동작 확인 | ❌ |
| 항상 수행 | 격리 실행이 저장소 Queue를 안 건드림 | ❌ |
| 항상 수행 | **입력 누락 시 종료코드≠0, 파일 미생성** (부분 덮어쓰기 방지) | ❌ |
| Skip 가능 | 전국 입력으로 재생성해 Byte 비교 | ✅ 있을 때만 |

- **API를 재수집하는 테스트는 없다.**
- 전국 입력이 없으면 사유를 출력하며 명시적으로 Skip한다.
- Fixture 실행은 `--data-dir`로 격리해 커밋된 Queue의 Hash가 변하지 않음을 검사한다.

### 중복·충돌 테스트 제거 (A 지적 반영)

기존 `test_academyinfo_review_queues.py`의 `DeterminismTest`가 생성기를 **무조건**
실행하고 `check=True`였다. clean clone에서는 생성기가 0이 아닌 코드로 끝나면서
**Skip이 아니라 오류로 실패**했다 — "입력이 없으면 명시적으로 Skip한다"는 이번 정책과
정면으로 어긋난다. 게다가 `NationwideRegenerationTest`가 같은 검사를 이미 한다.

**제거했다.** 결정론성 검증은 두 곳으로 나뉜다.

```
FixtureDeterminismTest       작은 Fixture로 항상 검증 (입력 불필요)
NationwideRegenerationTest   전국 입력이 있을 때만, 없으면 사유 출력 후 Skip
```

제거 사유는 해당 위치에 주석으로 남겨, 나중에 "왜 여기 결정론성 테스트가 없지"를
되짚을 수 있게 했다.

**실제 clean clone 환경으로 검증했다.** 생성 입력 2개를 치우고 전체 테스트를 돌렸다.

```
입력 없음 (clean clone)   978 통과 · 1 Skip   ← Skip은 전국 재생성 1건뿐
입력 있음                 978 통과 · 0 Skip
```

입력이 없어도 **Fixture 결정론성·커밋 Queue 검사·입력누락 방어는 그대로 돈다.**

### 테스트가 잡아낸 것

상태 필터를 넣자 기존 대조 테스트 4개가 깨졌다. **Queue는 승격 후보만 담는데 정규화·분류
보고서는 전체를 세기 때문**이었다. 숫자를 맞추는 대신 **대조 기준을 바로잡았다** —
Queue 보고서에 후보 기준 수치(`promotion_pool_nce_count` 등)를 추가하고 그것과 비교한다.
전체 수치와는 "후보가 전체보다 많을 수 없다"만 검사한다.

## 5. Master/API/Mock 무변경

```bash
git diff --exit-code -- data/master/ src/schemas/ outputs/mock_api/
→ 변경 없음
```

- `data/master/departments.jsonl` 35행 그대로
- `src/schemas/major.py` 무변경 — **`department_url`을 추가하지 않았다** (A 결정 §12)
- `outputs/mock_api/` 무변경

### `department_url` 정본 — worker-c 아님

A 결정 §12에 따라 **`origin/trait-vector-v2`의 Department Schema가 정본**이다.
worker-c에 Schema를 추가하지 않고 **값과 감사 결과만 보존**한다.

```
data/raw/departments.raw.jsonl                            37건 + scope + note
data/academyinfo_work/2025/department_url_scope_audit.jsonl   34 department / 3 college
```

Builder 배선은 trait-vector-v2 기반 통합 브랜치에서 진행한다.
**C가 앞서 요청했던 "worker-c에 필드 추가"는 철회한다**(`worker-c-A승인대기-변경안.md` §2).

## 6. Commit/Push 해시

```
96979bb  worker-c: limit promotion queues to current-status departments and add clean-clone tests
d26213a  worker-c: restrict recommendation scope to daytime bachelor courses
33d8616  worker-c: batch the duplicate review queue and prepare A-approval change proposals
cf5bfee  worker-c: build pre-promotion review queues for nationwide master
```

`origin/worker-c` 동기화 완료. `main`·`worker-b`·`trait-vector-v2` 무변경.
