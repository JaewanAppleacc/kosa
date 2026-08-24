# 작업자 C 완료 보고 ④ — 검수 패킷

작성 2026-08-24 · 브랜치 `worker-c` · 기준 `f1f270b`
정본 정책: `outputs/handoff/academyinfo_a_decisions.md`

> **"승인 가능 후보 5,453"은 승인 완료 데이터가 아니다.** 사람 검토 전 상태다.

## 0. 입력 통계 재확인 — 10개 항목 전부 일치

```
주간 학사과정 정규화   24,422    EXISTING  9,051    NEW  1,012
1차 후보              10,063    승인 가능 후보  5,453
중복 6 · 분류 REVIEW 1,936 · N.C.E 1,903 · URL 37 · 합계 3,845
```

---

## 1. 중복 6건 권고 결정

**6건 전부 `DISTINCT_DEPARTMENTS_KEEP_SEPARATE`.**

| 대학 | 학과 | 갈리는 축 |
|---|---|---|
| 서경대 | 코스메틱뷰티매니지먼트학과 | 일반과정 / 계약학과 |
| 서경대 | 헤어디자인학과 | 일반과정 / 계약학과 |
| 충남대 | 약학과 | 일반과정(6년) / **계약학과(4년)** |
| 한일장신대 | 사회복지학과 | 일반과정 / 계약학과 |
| 원광대 | 약학과(2+4학제) | 일반과정 / 계약학과 |
| 동신대 | 사회복지학과 | 일반과정 / 계약학과 |

**근거.** 6건 모두 `schlMjrId`가 서로 다르고, 공식 학과특성이 `일반과정`과 `계약학과`로
갈린다. 계약학과는 대학알리미가 별도 편제단위로 관리하는 다른 과정이고 **학생 지원 경로도
다르다**(산업체 재직자 대상). 학과명이 같다는 이유로 합치면 서로 다른 모집 단위가 하나로 보인다.

충남대 약학과는 **수업연한까지 다르다**(6년 vs 4년) — 교육과정 자체가 다르다는 뜻이다.

**하지 않은 것.** 이름이 같다고 합치지 않았고, `source_record_id`가 다르다는 이유만으로
별도라고 단정하지도 않았다. 판단 근거는 **공식 필드가 실제로 다른지**다. ID 규칙은
변경하지 않았고, Migration Map도 만들지 않았다.

**권고일 뿐 확정이 아니다.** 6건 전부 `reviewer_1_status: TBD` · `resolution_status: PENDING`.

## 2. 분류 REVIEW 1,936건 군집별 개수

A가 지정한 축은 **0건이어도 표에 남겼다** — "검토했는데 없었다"와 "안 봤다"는 다른 사실이다.

| 우선순위 | 군집 | 건수 |
|---|---|---|
| P1 | 콘텐츠·미디어 경계 | 275 |
| P1 | 디자인·HCI·UX 경계 | 99 |
| P2 | 공식 소계열과 학과명 충돌 | **0** |
| P3 | 생명과학·생명공학·의공학 경계 | 133 |
| P3 | 경영·회계·금융·경영정보 경계 | 104 |
| P4 | 기계·자동차·항공·조선 경계 | 60 |
| P4 | 교육학·교원양성 경계 | 13 |
| P4 | 산업공학·안전·방재 경계 | 13 |
| P5 | 융합·복합 학과명 | 1,239 |
| P5 | 기타 | **0** |

`review_priority`는 **자동 확정 가능성이 아니라 "먼저 봐야 하는 정도"**다. P1이 앞선 이유는
예체능 제외 여부가 걸려 추천 노출에 직접 영향이 가기 때문이다. 건수가 가장 많은
`융합·복합`(1,239)이 P5인 것은 대부분 예체능과 무관해 급하지 않아서다.

각 군집에 `required_official_evidence`(무엇을 확인해야 하는지)를 붙였다.

## 3. N.C.E 1,903건 3분류

```
REEXAMINABLE_BY_OFFICIAL_EVIDENCE     584   공식 중계열이 살아 있다
NAME_ALONE_INSUFFICIENT               896   대계열까지만 또는 근거 전무
NEEDS_CANONICAL_GROUP_EXPANSION       423   복수 전공 포괄 단위
```

**근거 강도 순으로 갈랐다.**

1. **공식 중계열이 유효**(584) — 소계열만 미분류라 중계열 범위 안에서 후보를 좁힐 수 있다.
   다만 중계열이 곧 전공군은 아니므로 사람이 확정한다.
2. **복수 전공 포괄**(423) — 자유전공·융합·학부대학 등. 기존 42개 전공군 중 하나로 담기
   어려워 **전공군 확장 여부를 A가 판단**해야 한다. C가 임의로 늘리지 않았다.
3. **학과명만으로 판단 불가**(896) — 대계열까지만 있거나 아무 근거도 없다.

**같은 학교의 다른 학과 소계열은 판정 근거로 쓰지 않았다.** 참고로만 붙이고
`"참고(판정 근거 아님)"`이라고 명시했다 — 그걸 근거로 삼으면 "같은 학교니까 비슷할 것"이라는
추측이 된다. 테스트가 이 표기를 강제한다.

**금지 항목을 각 행에 기록했다**: 검색 스니펫만으로 확정 · 비공식 위키 · LLM 추측으로 소계열
생성 · N.C.E를 0점/무관 처리 · 42개 전공군 임의 확장.

### 작업 중 발견한 버그 (수정함)

`classify()`가 대계열·중계열의 **코드만 내보내고 이름을 안 내보냈다.** 그래서 하위 Queue와
패킷이 이름을 읽으려다 **전부 `None`**을 받았고, 첫 시도의 N.C.E 판정이 엉뚱한 근거(같은 학교
동료 학과)만 쓰게 됐다 — 1,896/1,903이 한 그룹에 몰렸다.

필드를 보강하고 다시 돌리자 584/896/423으로 갈렸다. **분포가 한쪽에 쏠리면 분류 로직이
아니라 입력을 의심해야 한다**는 사례로 남긴다.

## 4. 사람이 검토해야 할 최종 행 수

```
중복            6
분류 REVIEW  1,936
N.C.E        1,903
합계         3,845
```

N.C.E와 분류 REVIEW는 축이 달라 일부 겹친다(상호 참조 플래그로 표시).

## 5. 자동 승인하지 않았다는 증명

```json
"auto_approved_rows": 0
```

- 모든 검수 행이 `reviewer_1_status: "TBD"` · `resolution_status: "PENDING"` ·
  `reviewer_1_comment: ""`
- **권고(`recommended_decision`)와 승인(`reviewer_1_status`)이 다른 필드**임을 테스트가 검사
- `APPROVED`/`EVIDENCED`/`CONFIRMED` 문자열이 어느 행에도 없음을 테스트가 검사
- N.C.E 전 행의 `candidate_canonical_major_ids`가 빈 목록

## 6. 생성한 검수 패킷

```
data/academyinfo_work/2025/packets/
  duplicate_decision_draft.jsonl        13KB   중복 6건 결정 초안
  duplicate_review_packet.html          12KB   중복 6건 (사람이 읽는 표)
  classification_cluster_summary.json   23KB   군집 요약
  classification_cluster_summary.md     10KB   같은 내용 Markdown
  nce_triage_queue.jsonl               2.2MB   N.C.E 3분류
  nce_review_packet.html                55KB   N.C.E (그룹별 표)
  review_packet_manifest.json          1.9KB   입력·출력 Hash
```

Manifest에 **생성 시각을 넣지 않았다** — 넣으면 재생성 결과가 매번 달라져 Byte 비교를 못 한다.
`candidate_id`도 내용 해시라 재생성해도 같다.

## 7. 수정 파일

**신규**
```
scripts/career_build_academyinfo_review_packets.py
tests/worker_c/test_academyinfo_review_packets.py        33 tests
data/academyinfo_work/2025/packets/*                      7 files
```

**수정**
```
scripts/career_classify_academyinfo.py   대계열·중계열 이름 필드 추가 (§3 버그)
.gitignore                               packets/ 커밋 예외
```

**변경하지 않음**: `data/master/*` · `src/schemas/major.py` · `src/api/main.py` ·
`outputs/mock_api/*` · worker-b frontend · trait-vector-v2 · 기존 검수 파일 ·
Raw/Lineage 원본. 전국 Master 승격 없음. API 재호출 없음.

## 8. 테스트 결과

```
입력 있음        1,011 통과 · 0 Skip
clean clone      1,011 통과 · 3 Skip   (전국 재생성 3건만)
compileall       OK
git diff --check OK
```

## 9. 결정론성

- 임시 디렉터리에서 두 번 실행해 **7개 산출물 전부 byte-identical** 확인
- 격리 실행이 저장소의 커밋된 패킷 Hash를 바꾸지 않음을 확인
- 입력 누락 시 종료코드≠0 + `packets/` 디렉터리 자체를 만들지 않음
- API 재수집 테스트 없음

## 10. Master/Schema/Mock 무변경 증명

```
git diff --exit-code -- data/master/ src/schemas/ src/api/ outputs/mock_api/   → 변경 없음
data/master/departments.jsonl  SHA-256
  5bbbd856bf60d2d71545ba8156ac60aabb9953c0d91dbb6cb254604ae9c8fbfe   (35행)
```

## 11. Secret/Raw/Blob 검사

```
Key 문자열 스테이지 diff        0건
패킷 내 serviceKey 등 패턴      0건 (테스트로 고정)
5MB 이상 Blob                   0건 (최대 2.2MB)
136MB 전국 Raw                  계속 제외
.env                            계속 제외
```

## 12. Commit/Push 해시

```
a9ec9e7  worker-c: build human-reviewable packets for duplicate, classification and N.C.E queues
f1f270b  worker-c: drop duplicate determinism test

`origin/worker-c` 동기화 완료. `main`·`worker-b`·`trait-vector-v2` 무변경.
```

## 13. A가 다음에 판단해야 할 사항

1. **중복 6건 승인** — 6건 모두 별도 학과 권고. 승인하면 중복 문제가 종결된다.
2. **N.C.E `NEEDS_CANONICAL_GROUP_EXPANSION` 423건** — 자유전공·융합 등 복수 전공을 포괄하는
   단위다. 42개 전공군을 늘릴지, 아니면 이들을 추천 대상에서 제외할지 판단이 필요하다.
   C는 임의로 늘리지 않았다.
3. **검토 순서·인력** — P1(374건)부터 볼지, 건수가 많은 융합(1,239건)을 먼저 쳐낼지.
   P1이 추천 노출에 직접 영향이 가지만 건수는 적다.
4. **`REEXAMINABLE` 584건 처리 방식** — 공식 중계열이 있어 범위는 좁혀지지만 중계열이 곧
   전공군은 아니다. 중계열→전공군 매핑 표를 만들지, 개별 판단할지.
