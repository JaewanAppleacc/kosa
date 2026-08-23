# B 인계 — 학과 "공식 출처" 링크 정정

작성: 2026-08-23 (worker-c)
근거: `rationale_c/07-academyinfo-collection.md` §7-6

## 문제

`frontend/src/screens/MajorsScreen.tsx`의 학과 카드가 이렇게 그린다.

```tsx
{department.source_svy_year}년 기준 ·{" "}
<a href={department.source_url} ...>공식 출처</a>
```

`source_url`이 `https://www.academyinfo.go.kr/` **루트 도메인**이라, 학생이 "공식 출처"를
누르면 대학알리미 첫 화면이 뜨고 자기 학과 근거는 직접 검색해야 한다. **링크가 근거를
뒷받침하는 것처럼 보이지만 실제로는 아무것도 증명하지 않는다.**

대학알리미는 조회 폼 기반이라 **학과별 고정 링크가 존재하지 않는다.** API 응답 전체를
확인했지만 학과 홈페이지는커녕 대학 홈페이지 필드도 없다. 즉 "API를 붙이면 해결된다"는
기대는 성립하지 않는다 — 링크 자체를 없애고 표기를 바꾸는 게 맞다.

## 백엔드에서 이미 끝난 것 (worker-c)

`GET /departments/{major_id}` 응답에 **선택 필드 2개가 추가**됐다. 기존 필드는 그대로라
지금 코드도 계속 동작한다.

```jsonc
{
  "source_url": "https://www.data.go.kr/data/15158963/openapi.do",  // 루트 도메인 → 데이터셋 URL
  "source_dataset": "한국대학교육협의회 대학알리미 대학 기본 정보 (data.go.kr B340014)",  // 신규
  "department_url": null   // 신규. 확인된 학과 홈페이지만, 없으면 null
}
```

`source_url`이 이제 **검증 가능한 데이터셋 페이지**를 가리킨다. 다만 이건 여전히 "이 데이터가
어느 데이터셋의 몇 년도 공시인지"를 말할 뿐, 특정 학과를 증명하지는 않는다. 그래서 화면에서는
**링크가 아니라 표기**로 쓰는 게 맞다.

## 프론트에서 해야 할 것

### 1. `contracts.ts` — 스키마에 두 필드 추가

```ts
export const departmentSchema = z.object({
  // ... 기존 필드 그대로 ...
  source_url: z.string(),
  source_dataset: z.string().nullable().default(null),
  department_url: z.string().nullable().default(null),
  canonical_major_id: z.string().nullable().default(null),
});
```

`.default(null)`을 붙이면 **구버전 서버(필드 없음)와도 호환**된다 — 배포 순서를 신경 쓰지
않아도 된다.

### 2. `MajorsScreen.tsx` — 링크를 표기로 바꾸고, 학과 홈페이지만 링크로

`DepartmentList` 안의 출처 줄을 이렇게 바꾼다.

```tsx
<p className="mut mt-1.5 text-[12px]">
  대학알리미 {department.source_svy_year}년 공시 기준
  {department.department_url ? (
    <>
      {" · "}
      <a
        href={department.department_url}
        target="_blank"
        rel="noreferrer noopener"
        className="underline underline-offset-2"
        style={{ color: "var(--accent)" }}
      >
        학과 홈페이지 →
      </a>
    </>
  ) : null}
</p>
```

지켜야 하는 것:

- **`source_url`을 `href`에 쓰지 않는다.** 데이터 출처는 표기로만.
- **`department_url`이 `null`이면 링크를 아예 그리지 않는다.** "출처 없음" 같은 문구도 넣지
  않는다 — 학생에게 의미 없는 정보다.
- 대학 대표 홈페이지로 대체하지 않는다. 그러면 다시 "눌러도 그 학과가 없는 링크"가 된다.

### 3. 화면 결과

```
서울대학교 컴퓨터공학부
공과대학 · 서울
대학알리미 2025년 공시 기준
```

`department_url`이 채워진 학과만:

```
대학알리미 2025년 공시 기준 · 학과 홈페이지 →
                              ^^^^^^^^^^^^ 여기만 링크
```

## 참고 — 지금은 전부 `null`이다

`department_url`은 API가 주지 않으므로 사람이 확인한 학과만 채운다. 현재 시연 데이터 35건은
전부 `null`이라 **화면상 링크가 사라지는 것이 정상**이다. 링크가 안 보인다고 버그가 아니다.

전국 규모(수천 건)로 채우는 것은 현실적이지 않아, 시연 대상 학과에만 채울 예정이다.

## 확인 방법

```bash
# 백엔드 띄우고
./.venv/bin/uvicorn src.api.main:app --reload
curl -s localhost:8000/departments/computer_science | python -m json.tool | head -20
```

`source_dataset`이 문자열, `department_url`이 `null`로 오면 정상이다.
