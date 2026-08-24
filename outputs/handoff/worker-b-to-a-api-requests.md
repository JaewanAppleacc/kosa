# B → A 요청 — 프론트가 막혀 있는 API 4건

작성: 2026-08-24 (worker-b)
기준: `worker-b` @ a7f348e / 백엔드 `src/api/main.py` 엔드포인트 15개 확인

프론트는 지시서 §3 담당 범위를 대부분 구현했습니다. 아래 4건은 **API가 없어서
화면을 만들 수 없는 것들**이라, 프론트에서 임의로 값을 만들지 않고 그대로 두었습니다.

우선순위는 B가 본 "발표에서 드러나는 정도" 기준입니다. A가 다르게 판단하시면 그대로
따르겠습니다.

---

## 1. [P1] 전공 설명 — `MajorRelevance`에 설명 필드

### 무엇이 문제인가

전공 카드에 **전공 이름만** 나옵니다. 학생이 "미디어·커뮤니케이션"을 보고 그게 뭘
배우는 곳인지 알 방법이 화면에 없습니다.

현재 계약(`src/schemas/major.py`):

```python
class MajorRelevance(BaseModel):
    major_id: str
    label: str
    relevance_label: RelevanceLabel
    evidence_sufficiency: EvidenceSufficiencyLabel
    repeated_context_count: int
```

### 요청

`MajorRelevance`에 아래 중 하나를 추가해 주세요.

```python
    description: str | None = None      # 또는
    keywords: list[str] = []
```

### 왜 A가 해야 하는가

**데이터는 이미 있습니다.** `data/master/canonical_majors.jsonl`에 전공마다
`keywords`가 들어 있는데 API가 싣지 않습니다.

```jsonc
{"major_id":"media_communication","label":"미디어·커뮤니케이션",
 "keywords":["미디어","콘텐츠","저널리즘","영상","여론","커뮤니케이션"], ...}
```

프론트가 설명문을 하드코딩하면 "프론트엔드는 API JSON만 쓴다"는 아키텍처 불변식을
깨는 것이라 하지 않았습니다.

### 받으면 바로 되는 것

전공 카드에 한 줄 설명이 붙습니다. 화면 작업은 10분이면 끝납니다.

---

## 2. [P2] 답변 이력 조회 — `GET /assessment/history/{session_id}`

### 무엇이 문제인가

지금 질문 화면의 **"지나온 질문"은 브라우저 메모리에만 쌓입니다.** 새로고침하거나
"이어서 하기"로 복원하면 빈 목록이 됩니다.

현재 답변 관련 엔드포인트는 앞으로만 갑니다.

```
POST /assessment/answer          답을 기록하고 다음으로
POST /assessment/next-question   다음 질문
(이력 조회·수정 없음)
```

### 요청

```python
class AnsweredQuestionItem(BaseModel):
    question_id: str
    context_id: str
    question_text: str
    selected_option_id: str
    selected_option_text: str
    answered_at: datetime

class AssessmentHistoryResponse(BaseModel):
    session_id: str
    answers: list[AnsweredQuestionItem]   # 답한 순서대로
```

`GET /assessment/history/{session_id}`

**`selected_option_text`가 꼭 필요합니다.** `selected_option_id`만 오면 프론트가
질문 본문을 다시 찾아야 하는데, 지나간 질문은 다시 받을 방법이 없습니다.

### 함께 검토 부탁

지시서에는 없지만, 진학사·메이저맵 같은 검사는 **"이전" 버튼으로 답을 고칠 수
있습니다.** 그걸 하려면 되돌리기 API가 따로 필요합니다.

```
POST /assessment/answer/revise   { session_id, question_id, selected_option_id }
```

되돌리면 그 답에서 파생된 꼬리질문·Evidence를 어떻게 처리할지가 설계 문제라
**B가 판단할 수 없습니다.** 필요 없다고 보시면 지금처럼 조회 전용으로 두겠습니다.
그 경우 화면 버튼은 계속 "지나온 질문"(보기 전용)으로 둡니다 — "이전"이라고 쓰면
학생이 고칠 수 있다고 오해합니다.

---

## 3. [P2] 이전 Session Profile 비교 — 본문 조회 수단

### 무엇이 문제인가

지시서 §3에 **"이전 Session의 Profile과 현재 Profile 비교 화면을 구현한다"**(82행)가
있는데, 이전 Profile의 **본문을 가져올 방법이 없습니다.**

현재 계약(`src/schemas/api.py`):

```python
class SessionRestoreResponse(BaseModel):
    session_id: str
    user_id: str
    phase: str
    has_previous_completed_profile: bool    # 있다/없다 boolean 하나뿐
```

"있다"는 알 수 있지만 무엇이 있는지는 모릅니다. 비교 화면을 만들 수 없습니다.

### 요청

둘 중 편한 쪽이면 됩니다.

**(A안) 이전 세션 id 목록만 주기** — 기존 `GET /profile/{session_id}`를 재사용

```python
class SessionRestoreResponse(BaseModel):
    ...
    previous_completed_session_ids: list[str] = []   # 최신순
```

**(B안) 비교 전용 엔드포인트**

```
GET /profile/{session_id}/compare?with={previous_session_id}
```

**B는 A안을 권합니다.** 새 계산 로직이 필요 없고, 프론트가 `GET /profile/{id}`를 두 번
불러 나란히 놓기만 하면 됩니다.

### 함께 정해주셔야 할 것

**무엇을 "달라졌다"고 표시할지**는 화면이 정할 문제가 아닙니다.

- Highlight 문장은 매번 LLM이 새로 쓰므로 문자열 비교가 의미 없습니다
- 내부 점수 차이는 노출 금지입니다

그래서 지금 비교할 수 있는 건 `hashtags`, `detailed_evidence_by_dimension`의 관찰
개수 정도입니다. **A가 "이건 비교해도 된다"고 정해주시면 그 항목만 보여주겠습니다.**
정해지기 전에는 만들지 않겠습니다 — 잘못 비교하면 "너 예전보다 못해졌다"로 읽힙니다.

---

## 4. [P3] 성적 유사 범위 필터 — 입결 조회 엔드포인트

### 무엇이 문제인가

지시서 §3(76행)과 §8 E2E 목록(115행)에 **"성적 유사 범위 필터"**가 있는데,
`AdmissionReference`를 반환하는 엔드포인트가 없습니다.

```
$ grep -rn "AdmissionReference" src/api/main.py src/schemas/api.py
(결과 없음)
```

스키마(`src/schemas/major.py`)는 정의돼 있지만 API 표면에 나오지 않습니다.

### 요청

```
GET /departments/{major_id}/admissions?session_id=...
```

또는 기존 `DepartmentsResponse`의 각 학과에 선택 필드로:

```python
    admission: AdmissionReference | None = None
```

### 반드시 함께 주셔야 하는 것

`AdmissionReference`에 이미 `data_comparability_group`이 있습니다. 지시서에도
**"성적 유사 범위 필터를 Trait Matching과 분리해 표시한다"**고 되어 있고요.

**서로 다른 비교 그룹을 한 목록에 섞으면 안 된다는 규칙을 프론트가 알아야 합니다.**
정렬·필터를 화면에서 하면 그 규칙을 프론트가 다시 구현하는 셈이 되는데, 그건
"백엔드 내부 계산을 프론트에서 재구현하지 않는다"는 불변식 위반입니다.

그래서 **서버가 이미 걸러서 같은 그룹만 내려주는 형태**를 권합니다. 프론트는 받은
목록을 그대로 그리고, `data_comparability_group`을 안내 문구로만 표시하겠습니다.

### 우선순위를 낮게 둔 이유

`review_status: "verified"`인 입결 데이터가 실제로 얼마나 있는지 B는 모릅니다.
데이터가 시연 규모라면 이 화면은 발표에서 오히려 약점이 됩니다. **데이터 현황을
알려주시면 만들지 말지부터 다시 판단하겠습니다.**

---

## 참고 — 이미 해결된 건

**학과 "공식 출처" 링크**(지시서 §3, 77행)는 정리됐습니다.
`source_url`이 대학알리미 루트라 클릭 링크로 두면 근거를 증명하지 못해서,
비클릭 텍스트("대학알리미 {연도}년 공시 기준")로 바꾸고 `department_url`이 있을 때만
"학과 홈페이지 →" 링크를 답니다. (`3a36b5f`)

다만 지금 서버는 `department_url`이 **전부 null**입니다.
`origin/c/department-url-writeback`(32/35건 채움)이 아직 병합 전이라 그렇습니다.
병합되면 프론트 수정 없이 링크가 나타납니다.

---

## 요약

| # | 요청 | 없으면 | 우선순위 |
|---|---|---|---|
| 1 | `MajorRelevance`에 설명/키워드 | 전공 이름만 보임 | P1 |
| 2 | `GET /assessment/history/{session_id}` | 새로고침 시 지나온 질문 사라짐 | P2 |
| 3 | 이전 세션 id 목록 + 비교 항목 결정 | 비교 화면 구현 불가 | P2 |
| 4 | 입결 조회 + 데이터 현황 | 성적 필터 구현 불가 | P3 |

**1번만 있어도 결과 화면 완성도가 눈에 띄게 올라갑니다.** 나머지는 A의 판단에
따르겠습니다 — 안 만들기로 하시면 지시서 해당 항목을 "이번 범위 밖"으로 명시해
주시면 그대로 정리하겠습니다.
