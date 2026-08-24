# B 작업자 핸드오프 — 2026-08-31 (갱신)

이 저장소(`kosa`)를 clone하면 바로 프론트엔드 개발을 시작할 수 있습니다. B 작업자는 별도 ZIP이나 `CLAUDE.md` 없이 이 문서를 시작점으로 사용합니다. 필요한 API 계약과 Mock 예시는 아래 경로에서 확인할 수 있습니다.

> **2026-08-24 갱신 내용 — `source_url`을 클릭 가능한 링크로 쓰지 않도록 수정 (22차,
> Schema 변경 없음)**:
> 1. **`source_url`은 학과마다 다른 값이 아니라 대학알리미 서비스의 같은 루트
>    URL을 거의 그대로 반복합니다.** 이걸 "공식 출처"라는 이름의 클릭 가능한
>    링크로 보여주면, 학생이 그 링크를 그 학과의 공식 홈페이지라고 오해할 수
>    있습니다 — 실제로는 대학알리미 서비스로 이동할 뿐입니다.
> 2. **그래서 `source_url`은 이제 화면 어디에도 `href`/`onClick`/`window.open`으로
>    쓰지 않습니다.** "대학알리미 {source_svy_year}년 공시 기준" 문구는 계속
>    보여주되(아래 형태 그대로, `source_svy_year`만으로 만들 수 있습니다),
>    일반 텍스트입니다 — `<a>` 태그가 아닙니다.
>    ```text
>    대학알리미 {source_svy_year}년 공시 기준
>    ```
> 3. **`department_url`이 학과 홈페이지로 클릭할 수 있는 유일한 URL입니다.**
>    있을 때만("학과 홈페이지 →" 같은) 링크를 보여주고, 없으면(`null`) 링크
>    자체를 완전히 숨기세요 — `source_url`을 대신 쓰지 마세요(Fallback 금지).
>    `DepartmentBrowser.tsx`가 실제 구현 지점입니다.
> 4. **단과대학(College) URL이 나중에 데이터에 들어와도 그걸 "학과 홈페이지"로
>    표시하지 마세요.** `department_url`은 검증된 "학과" 단위 공식 홈페이지만
>    가리켜야 합니다 — 학과보다 넓은 단위(단과대학·대학교 대표 홈페이지)를 그
>    자리에 채우면 학생이 잘못된 세부 정보를 학과 공식 정보로 오해합니다.
> 5. **API Schema는 이번에 변경되지 않았습니다** — `source_url: string`(필수),
>    `department_url: string | null`(21차에서 이미 추가됨) 둘 다 그대로입니다.
>    Mock/OpenAPI 재생성 결과도 이전과 byte-identical입니다.

> **2026-08-31 갱신 내용 — `Department.department_url` 필드 추가 (21차, 하위 호환 — 기존 필드 삭제·변경 없음)**:
> 1. **`GET /departments/{major_id}`가 반환하는 각 학과 객체에 `department_url:
>    string | null`이 새로 추가됐습니다.** 학과 **공식 홈페이지** URL입니다.
>    - `string`이면 "학과 홈페이지" 버튼을 표시하세요(새 탭으로 열어도 되는 값입니다).
>    - `null`이면 그 버튼을 숨기세요. **지금 저장소의 시연 데이터 35개는 전부
>      `null`입니다** — 검증된 홈페이지 URL 데이터가 아직 통합되지 않았습니다(다음
>      라운드에 채워질 예정). 화면에서 "URL이 없을 수 있다"를 기본 전제로 만들어
>      두세요.
> 2. **기존 `source_url` 필드는 역할이 다릅니다 — 학과 홈페이지 버튼으로 쓰지
>    마세요.** `source_url`은 대학알리미(academyinfo.go.kr) 공식 URL이고 **데이터
>    출처 표시 전용**입니다(2026-08-24 22차 갱신: 이제 클릭 링크로도 쓰지 않고
>    일반 텍스트로만 표시합니다 — 위 22차 항목을 확인하세요). 문구는 아래 형태를
>    그대로 쓰세요(`source_svy_year`와 조합):
>    ```text
>    대학알리미 {source_svy_year}년 공시 기준
>    ```
>    예: `source_svy_year: 2025` → "대학알리미 2025년 공시 기준". `source_dataset`
>    같은 별도 필드는 추가하지 않았습니다 — 이 문구는 `source_svy_year` 하나로
>    충분히 만들 수 있습니다.
> 3. **정리하면 학과 객체 하나에 URL이 두 개 있습니다** — `department_url`(있으면
>    "학과 홈페이지" 링크, 22차부터 유일한 클릭 가능 URL), `source_url`(항상 있음,
>    "대학알리미 {연도}년 공시 기준" 출처 문구를 만드는 데이터일 뿐 링크는 아님).
>    서로 바꿔 쓰지 마세요.
> 4. **API Request/Response Schema는 이 필드 하나만 추가됐습니다** — 기존 필드는
>    이름·타입 전부 그대로입니다. `outputs/mock_api/departments_normal.json`·
>    `openapi.json`을 재생성해 반영했습니다.

> **2026-08-30 갱신 내용 — Context 화면 API 정합성 (20차)**:
> 1. **`GET /contexts`가 새로 추가됐습니다(세션 불필요).** Context 15개 목록과 선택
>    개수 정책을 서버가 그대로 내려줍니다 — 화면에서 Context 목록이나 선택 개수를 상수로
>    복제하지 마세요. 아래 "4-3. Context 카탈로그" 절을 꼭 읽어주세요.
> 2. **`/assessment/context-select`의 선호 Context는 이제 "정확히 2개"만, 그것도
>    `game`/`media`/`school_life` 중에서만 허용됩니다.** 예전엔 등록된 15개 Context 중
>    아무거나 최소 2개만 통과시켜서, 화면이 실수로 `art_design` 같은 Context를 보내면
>    이 단계는 통과하고 `/assessment/next-question`에서야 뒤늦게 실패했습니다 — 이제
>    여기서 바로 422로 막습니다. 관심도 평가(`/assessment/interest-rating`)를 아직 안 한
>    Context도 선호 Context로 보낼 수 없습니다.
> 3. **`/assessment/context-confirm`의 최종 Context는 "2개 이상 3개 이하"입니다.**
>    예전엔 사실상 최소 1개만 검사해서 개수 제한이 없었습니다. **정확히 3개를 강제하지
>    않습니다** — 학생이 Contrast Context 제안을 받아들이지 않고 처음 고른 2개만으로
>    확정하는 기존 흐름은 그대로 유지됩니다.
> 4. **API Request/Response Schema 자체는 안 바뀌었습니다**(`GET /contexts` 신규
>    추가 제외) — 필드 이름·타입은 그대로고, 검증 범위만 정확해졌습니다.

> **2026-08-29 갱신 내용 — `GET /subgraph/{session_id}` 실제 계산으로 교체 (19차, API Request/Response Schema 변경 없음)**:
> 1. **더 이상 고정 5개 Node짜리 Mock이 아닙니다.** 이 세션의 실제 답변→Trait→대표
>    전공→실제 학과·대학, (확정했다면) →추천 과목까지 실제 근거로 계산한 그래프를
>    돌려줍니다. `SubgraphNode`/`SubgraphEdge` 필드 자체는 그대로입니다 — 값만
>    Mock에서 실제 계산으로 바뀌었습니다.
> 2. **아직 답변이 하나도 없으면 200 대신 422 `EVIDENCE_NOT_READY`입니다**(`/profile`과
>    동일한 기준). 답변은 있지만 아직 학교 개설과목을 확정하지 않았으면 200과 함께
>    Trait·전공·학과까지만 있는 **부분 그래프**를 정상 반환합니다(과목 Node가 없는 게
>    정상입니다 — 오류가 아닙니다).
> 3. **`POST /course/confirm`까지 마친 뒤에만 과목 Node(`HighSchoolSubject`)가
>    포함됩니다.** 그 전에는 아무리 다시 조회해도 과목 Node가 나오지 않습니다.
> 4. **`relation_type="RELATED_TO"`는 여전히 "추론된 연관성"입니다.** 학과·대학·과목
>    연결(`HAS_DEPARTMENT`/`BELONGS_TO`/`RECOMMENDS`)은 확정된 구조적 관계지만,
>    Trait↔전공·Trait↔과목을 잇는 `RELATED_TO`는 공식 근거 기반이어도 여전히
>    "확정 관찰"이 아니라 "연관성"이라 화면에서는 점선으로 표현해주세요(기존 Schema
>    문서 그대로).
> 5. **`relevance_level`(1~3)을 학생에게 숫자로 보여주지 마세요.** 화면 문구에는 절대
>    쓰지 말고, 선 굵기·투명도처럼 시각적 강조 정도로만 써주세요 — 다른 API의 정성
>    Label 원칙(§7)과 같은 이유입니다.
> 6. **B는 Node·Edge를 계산하지 않습니다.** `KnowledgeSubgraphService`(서버)가 전부
>    계산해서 내려줍니다 — 화면은 받은 그래프를 그대로 렌더링만 하면 됩니다. Obsidian
>    Export는 이번 라운드에서 건드리지 않았습니다(B 소유, 그대로).

> **2026-08-28 갱신 내용 — 편제표 열 제목 잡음 제거 (18차, API Request/Response Schema 변경 없음)**:
> 1. **`"교과(군)"` 같은 편제표 열 제목이 더 이상 `unmatched` 후보로 노출되지 않습니다.**
>    실제 과목이 아닌 표 부속물(열 제목·학년·학점·합계·비고 등)은 서버 Parser가 후보
>    단계에서 완전히 걸러냅니다 — `parsed_candidates`·`unresolved_candidates` 어디에도
>    나타나지 않습니다. `"정체불명 과목ABC"`처럼 실제로 확인이 필요한 미매칭 값은 그대로
>    남습니다. `outputs/mock_api/course_upload_normal.json`·`course_confirm_normal.json`이
>    갱신된 실제 예시입니다.
> 2. **화면 코드 변경은 필요 없습니다.** 필드·Schema가 안 바뀌었고, 순수하게 서버가
>    넘겨주는 후보 목록의 내용만 더 정확해졌습니다.

> **2026-08-27 갱신 내용 — POST_OFFERING 안정화 (17차, API Request/Response Schema 변경 없음)**:
> 1. **`unmatched` 후보가 Confirm 이후에도 사라지지 않습니다.** 예전에는 `POST
>    /course/confirm` 응답의 `course_profile.unresolved_candidates`가 항상 빈 배열이었는데,
>    이제 이번 업로드에서 `matched_subject_id`가 끝내 안 잡힌(=`"unmatched"`) 후보들이 그대로
>    담겨 옵니다. `GET /subjects`로 다시 조회해도 동일하게 유지됩니다 — 화면에서 이 목록을
>    "추가 확인 필요"(예: 직접 검색해서 등록) 영역으로 별도 표시해주세요.
> 2. **`high`/`low` 중 사용자가 `/course/confirm`으로 확정하지 않은 후보는 개설과목으로
>    쓰이지 않습니다.** (기존 규칙 그대로지만, 실수로 "high면 자동 반영"으로 오해하지
>    않도록 다시 강조합니다.)
> 3. **`POST /course/confirm`이 이제 완전히 원자적입니다.** 추천 계산이나 내부 검증 중
>    어디서든 실패하면 서버 상태는 확정 이전으로 그대로 남습니다 — "요청은 실패했는데
>    다음 조회에서는 어중간하게 확정된 것처럼 보이는" 상황이 생기지 않습니다. 화면에서는
>    `/course/confirm`이 실패(4xx)하면 안전하게 재시도할 수 있다고 가정해도 됩니다.
> 4. **업로드 용량 제한(10MB)이 더 앞단에서 걸립니다.** 동작은 그대로지만(10MB 초과 시
>    422 `VALIDATION_ERROR`), 이제 서버가 파일을 조금씩 읽으면서 상한을 넘는 즉시 멈춥니다
>    — 큰 파일을 올렸을 때 응답이 더 빨리 옵니다.
> 5. **같은 과목이 여러 번 추출됐을 때 더 확실한 쪽이 남습니다.** 예전엔 먼저 추출된
>    후보가 무조건 남았는데, 이제 `"high"`(정확 매칭) 후보가 있으면 그게 남고 `"low"`가
>    먼저 추출됐어도 사라지지 않습니다 — 화면 쪽 코드 변경은 필요 없습니다(순서 로직이라
>    서버 내부에서만 바뀝니다).

> **2026-08-26 갱신 내용 — POST_OFFERING(학교 실제 개설과목 기반 최종 추천) 구현 (`/course/upload`·`/course/confirm` 계약 변경, 하위 호환 아님)**:
> 1. **`POST /course/upload`가 이제 `selected_major_id`를 함께 받습니다.** `multipart/
>    form-data`로 `session_id`(Form) + `selected_major_id`(Form, `GET /subjects`와 동일한
>    규칙으로 검증됨) + `file`(File)을 보내세요. 더 이상 형식만 확인하는 Mock이 아니라
>    실제 Parser(과목명 추출·Alias 매칭)로 연결됩니다.
> 2. **지원 파일은 PDF와 XLSX뿐입니다. XLS(97-2003 이진 형식)는 명시적으로 거부됩니다**
>    (422 `VALIDATION_ERROR`, "XLSX로 다시 저장해 업로드해주세요" 안내). 파일 크기 상한은
>    10MB입니다. 빈 파일도 거부됩니다.
> 3. **문서를 읽지 못하면(이미지 스캔 PDF, 손상된 xlsx 등) 새 오류 코드 `PARSE_FAILED`
>    (422)가 옵니다.** "개설과목이 0개"(정상, 200 + 빈 목록)와 "문서를 못 읽었다"(422)는
>    다른 상황이니 화면에서도 다르게 안내해주세요.
> 4. **`CourseUploadResponse`에 `selected_major_id`·`parse_warnings`가 추가됐습니다.**
>    `parse_warnings`는 `{stage, message}` 형태의 안전한 경고 목록입니다(로컬 파일 경로나
>    Stack Trace는 절대 안 옵니다).
> 5. **`ParsedSubjectCandidate.confidence`가 `"high"`/`"low"`/`"unmatched"` 중 하나로 옵니다.**
>    `"high"`도 자동으로 개설과목이 되는 게 아닙니다 — 세 등급 전부 사용자가 확인 화면에서
>    보고, `POST /course/confirm`을 호출해야만 확정됩니다. `"unmatched"`는 `matched_
>    subject_id`가 없어서 애초에 확정 대상이 될 수 없습니다(화면에서 선택 불가로
>    표시하세요).
> 6. **`POST /course/confirm`이 이제 실제로 검증합니다.** 어떤 ID든 받아주던 Mock이
>    아닙니다 — (a) 이 세션이 먼저 업로드를 거쳤는지(404 `COURSE_UPLOAD_NOT_FOUND`),
>    (b) 보낸 `confirmed_subject_ids`가 이번 업로드의 실제 후보에서 나온 값인지, 정본
>    과목 목록에 있는지(422 `VALIDATION_ERROR`)를 확인합니다. 빈 목록(`[]`)은 "이번 업로드
>    에서 하나도 확정 안 함"이라는 뜻으로 정상 허용됩니다. 중복 ID는 서버가 자동으로
>    하나로 정리합니다.
> 7. **`CourseConfirmResponse`에 `course_profile`이 추가됐습니다.** 확정 직후 바로
>    POST_OFFERING 최종 추천을 함께 받습니다 — 별도로 `GET /subjects`를 다시 호출할
>    필요가 없습니다(호출해도 같은 결과가 옵니다, 아래 10번 참고).
> 8. **`CourseProfile`에 `unavailable_subjects`가 추가됐고, `CourseRecommendationItem`에
>    `replaces_subject_id`가 추가됐습니다.** PRE_SURVEY에서는 항상 각각 빈 리스트/`null`
>    입니다. POST_OFFERING에서: 원래 희망했지만 실제로 개설 안 된 과목은
>    `recommendations`가 아니라 `unavailable_subjects`에 `{subject_id, label, reason}`
>    으로 옵니다. 그 대신 제안하는 대체 과목은 `recommendations`에
>    `category="alternative"`로 들어오고, `replaces_subject_id`에 어떤 미개설 과목을
>    대신하는지가 담깁니다. 대체 과목을 못 찾으면 `unavailable_subjects`에만 남고
>    `recommendations`에는 아무것도 추가되지 않습니다(억지 대체 없음).
> 9. **`GET /subjects/{session_id}?selected_major_id=...`는 그대로지만 동작이 똑똑해졌습니다.**
>    이 세션·전공 조합으로 `/course/confirm`까지 마쳤으면 POST_OFFERING 결과를, 아직
>    안 마쳤으면(또는 다른 전공으로 확정했으면) 기존 PRE_SURVEY 결과를 반환합니다 —
>    화면에서 "지금 PRE_SURVEY인지 POST_OFFERING인지"는 응답의 `source` 필드로
>    판단하세요.
> 10. **시연용 학교 개설과목 파일**: `data/fixtures/course_offerings/demo_school_offerings.xlsx`
>    — 업로드 UI를 테스트할 실제 예시 파일입니다(고정 텍스트 3개 과목 + low confidence
>    1개 + unmatched 1개 + 표 잡음 포함). `outputs/mock_api/course_upload_normal.json`·
>    `course_confirm_normal.json`이 이 파일로 만든 실제 예시 응답입니다.

> **2026-08-25 갱신 내용 — 14차(2026-08-24) PRE_SURVEY 구현의 검수 후속 수정 (`GET /subjects` 응답 필드 추가, 하위 호환)**:
> 1. **`CourseRecommendationItem`에 `label: str`이 추가됐습니다.** 예전엔 `subject_id`
>    (예: `subj_fd2661b74f5517b17f5f9d9e`)만 와서 화면에 과목명을 표시할 방법이
>    없었습니다 — 이제 정본 `SubjectProfile.label`(예: "화법과 언어")을 그대로
>    함께 내려줍니다. `subject_id`는 여전히 식별자로만 쓰고 화면 표시에는 `label`을
>    쓰세요. 기존 필드(`category`/`is_actually_offered`/`reason`)는 그대로입니다.
> 2. **`reason` 문구가 바뀌었습니다.** "선택한 전공과 공식적으로 연결된 과목입니다"라는
>    표현은 Subject–Major/Subject–Trait 근거가 아직 `review_status="draft"`(2인 검토
>    전)라는 사실보다 과장돼 있었습니다 — 이제 "공식 교육과정 자료를 바탕으로 {전공명}
>    탐색과 연결한 시연 과목입니다"처럼 더 정직한 수위로 표현하고, 그 과목의 공식
>    교육과정 근거에서 뽑은 **구체적인 학습 활동**(예: "확률과 통계에서 자료를 수집·
>    처리해 합리적으로 의사 결정하는 활동을 경험할 수 있으며...")과 학생 답변에서
>    확인된 Trait를 함께 문장으로 담습니다. `reason`은 여전히 자유 문자열이라 Schema
>    타입은 안 바뀌었지만, 화면에 하드코딩된 문구 매칭이 있다면 다시 확인하세요.
> 3. **오류 코드 분류가 더 정확해졌습니다.** `selected_major_id`가 등록된 대표 전공이긴
>    하지만 답변 근거상 이 학생에게 전혀 추천되지 않은 상황(`MAJOR_NOT_SELECTABLE`)과,
>    애초에 어느 대표 전공도 판단할 만큼 Evidence가 안 쌓인 상황(`EVIDENCE_NOT_READY`)
>    을 이제 정확히 구분합니다 — 오류 코드 자체는 이미 있던 두 값 그대로라 화면 처리
>    로직을 바꿀 필요는 없지만, 실제로 어느 쪽이 오는지가 이전보다 더 신뢰할 수
>    있어졌습니다.
> 4. **UX 흐름 참고**: `/majors/{session_id}`는 여전히 대표 전공명과 정성적 관련도만
>    반환하고 대학명·실제 학과 목록을 절대 합치지 않습니다. 학과 상세(대학명·학과명·
>    지역·공식 출처)는 사용자가 "자세히 보기"를 눌렀을 때만 별도로 `/departments/
>    {major_id}`를 호출하세요. "자세히 보기"와 "이 전공으로 과목 추천받기"는 서로 다른
>    사용자 행동입니다 — 학생이 과목 추천 버튼을 명시적으로 누른 뒤에만
>    `selected_major_id`를 `/subjects`에 전달하세요(서버는 화면이 어떤 전공을
>    "선택 확정"으로 보냈는지 알 방법이 없으므로, 이 구분은 전적으로 화면 책임입니다).

> **2026-08-24 갱신 내용 — `GET /subjects/{session_id}` API 계약 변경 (하위 호환 아님)**:
> 1. **`selected_major_id` Query Parameter가 필수로 추가됐습니다.** 학생이 전공 추천
>    화면에서 대표 전공 하나를 고른 뒤 과목 추천 화면으로 넘어가는 흐름을 그대로
>    반영합니다. 예: `GET /subjects/{session_id}?selected_major_id=industrial_engineering`.
>    이 값은 서버 어디에도 저장되지 않습니다 — 화면이 매번 쿼리 파라미터로 다시
>    보내야 합니다(무상태 GET).
> 2. **더 이상 고정 Mock이 아닙니다.** 이 세션의 실제 Trait 근거 + 선택한 전공과
>    공식적으로 연결된 과목(현재 시연 데이터 18개 과목 한정)을 조합해 실제로 계산한
>    "PRE_SURVEY 과목 추천"을 반환합니다. 학교가 실제로 이 과목을 개설하는지는
>    이 단계에서 아직 확인되지 않습니다 — 다음 3번 항목을 꼭 읽어주세요.
> 3. **`CourseRecommendationItem.is_actually_offered`가 `bool`에서 `bool | None`으로
>    바뀌었습니다.** PRE_SURVEY 응답에서는 항상 `null`입니다(개설 여부 미확정 — 아직
>    "미개설 확정"이 아니라는 뜻입니다. `false`로 해석하지 마세요). 이때 `category:
>    "core"`는 "학교가 실제 개설을 확인한 핵심 과목"이 아니라 **"학생 Trait 근거가
>    충분한 희망 우선과목"**이라는 뜻입니다 — 화면 문구도 "핵심 과목"보다는 "우선
>    희망 과목" 계열로 표현하는 걸 권장합니다. `true`/`false`는 다음 단계
>    (POST_OFFERING, 학교가 실제 개설과목을 업로드한 뒤)에서만 나옵니다.
> 4. **새 오류 코드 `MAJOR_NOT_SELECTABLE`이 추가됐습니다.** `selected_major_id`가
>    다음 중 하나면 422로 거부됩니다 — (a) Vertical Slice 대표 전공 3개
>    (`media_communication`/`hci_ux`/`industrial_engineering`)에 없는 값(`design` 등
>    추천 제외 전공 포함), (b) 이 세션이 실제로 추천받은 전공 목록(`/majors/{session_id}`
>    의 `relevant_majors`+`explore_together_majors`)에 없는 값. Evidence 자체가 부족하면
>    기존과 같은 `EVIDENCE_NOT_READY`(422)입니다.
> 5. **과목 Trait/전공 연결 근거는 아직 `draft`입니다.** 2022 개정 교육과정 공식
>    성취기준을 근거로 삼았지만 아직 2인 교차검토를 거치지 않았습니다 —
>    "검증된 진학 지침"처럼 표현하지 마세요(`outputs/reviews/` 참고, 다음 라운드에
>    Subject 버전이 추가될 예정입니다).

> **2026-08-22 갱신 내용 (4건)**:
> 1. C의 Repository·RAG·MCP·데이터 구현이 병합된 뒤 첫 통합 단계로 `GET /departments/
>    {major_id}`가 고정 Mock에서 실제 `JsonlDepartmentRepository` 조회로 바뀌었습니다.
>    Response Schema는 동일합니다. Subjects/Subgraph, 입결·안정/적정/상향 추천은 아직
>    연결되지 않았습니다.
> 2. 이어서 `/majors/{session_id}`가 실제로 추천하는 대표 전공 3개(`media_communication`/
>    `hci_ux`/`industrial_engineering`)에 실제 학과를 연결했습니다.
> 3. **(2번 직후 정정) 예체능 계열 학과 추천 제외 정책이 새로 확정됐습니다.** 2번에서
>    `hci_ux`에 연결했던 서울여자대학교 산업디자인학과는 실제 UX 교육과정이 있어도
>    학과 자체가 예체능(디자인) 계열이라 **추천 대상에서 제외**했습니다 — 그래서
>    `hci_ux`는 지금 학과 1개(이화여자대학교 융합콘텐츠학과, 비예체능·공학+인문+디자인
>    융합 학과로 재확인됨)만 나옵니다. `design` Canonical Major 자체도 통째로 추천에서
>    뺐습니다(`/departments/design`은 200 + 빈 목록 — 학과 데이터 자체는 남아 있지만
>    노출하지 않습니다). 아래 2번 표를 확인하세요.
> 4. **(3번 보완) 학과 단위 추천 적격성 정책(Fail-Closed)을 추가했습니다.** `design`
>    major_id를 막는 것만으로는 "다른 major_id로 잘못 Mapping된 예체능 학과"까지는
>    못 막습니다(major_id 검사만 통과하면 그대로 노출됨). 그래서 대표 전공 3개에
>    연결된 학과는 이제 학과 하나하나가 공식 자료(단과대학 분류·입학전형·교육과정)로
>    검토돼 명시적으로 "승인"이라고 기록된 것만 노출합니다 — 검토 기록이 없으면
>    무조건 제외합니다(승인 여부를 확인할 수 없으면 안전하게 막는 쪽으로 동작).
>    이 검토는 지금 추천 가능한 3개 전공(`media_communication`/`hci_ux`/
>    `industrial_engineering`)에 연결된 학과 8개에만 적용돼 있고, 그 외 `major_id`
>    (예: `computer_science`)는 이 검토 대상이 아닙니다 — 전국 학과 전체의 예체능
>    분류는 아직 안 돼 있습니다(후속 확장 과제). B 쪽 API 응답에는 이 내부 검토
>    필드(계열·검토 상태·검토자 등)가 전혀 노출되지 않습니다 — Response는 이전과
>    똑같은 `Department[]`만 돌려줍니다.

> **2026-08-21 갱신 내용**: 질문 생성(§10)·Career Profile(§14)·전공 Matching(§16)이 전부
> Mock에서 실제 계산으로 바뀌었습니다. 아래 2번 표와 4번 상태값 목록이 크게 달라졌으니
> 이전에 이 문서를 보신 적 있어도 다시 한번 읽어주세요. Response의 필드 이름·타입은
> 기존과 호환되고(`insufficient_evidence_message` 필드 하나만 새로 추가됨), 값의 내용만
> Mock에서 실제 계산 결과로 바뀌었습니다.

## 1. 빠른 시작

```bash
git clone https://github.com/JaewanAppleacc/kosa.git
cd kosa
python3 -m venv .venv
./.venv/bin/pip install -r requirements-lock.txt
./.venv/bin/uvicorn src.api.main:app --reload
```

- `http://127.0.0.1:8000/docs` — 실제 동작하는 API 문서(Swagger UI). 여기서 바로 요청 날려볼 수 있습니다.
- 서버 안 띄우고 정적 파일만 보고 싶으면 `outputs/mock_api/`를 참고하세요.

## 2. 지금 뭐가 진짜로 되고, 뭐가 Mock인지

| 단계 | 실제 동작 여부 |
|---|---|
| 세션 생성 / 관심도 평가 / Context 선택·확정 | ✅ 실제 상태 저장·조회 (단, In-Memory — 서버 재시작하면 날아감, DB 아님) |
| Seed 질문(각 Context의 첫 질문) | ✅ 실제 고정 문항(§7-1) |
| 꼬리질문(2번째 질문부터) 생성 | ✅ 실제 LLM 생성(§10) — **단, `.env`에 `ENABLE_LLM_QUESTION_GENERATION=true` + API Key가 있을 때만.** 안 켜져 있으면 자동으로 이전과 같은 Mock 문구로 동작합니다(서버가 알아서 판단 — B가 신경 쓸 필요 없음). |
| 답변 제출 → Evidence·Trait 판정 | ✅ 실제 계산(§12/§13). LLM 연동 여부와 무관하게 항상 실제로 동작합니다. |
| Profile 조회 (`/profile/{session_id}`) | ✅ 실제 계산(§14) — LLM을 쓸 수 있으면 실제 Evidence를 바탕으로 LLM이 문장을 생성하고, LLM이 꺼져 있거나 호출에 실패하면 **같은 학생의 같은 실제 Evidence**를 바탕으로 결정론적 Fallback 문장을 생성합니다(다른 학생의 Mock Profile을 대신 보여주지 않습니다). 어느 경로든 Trait·근거 구조는 항상 이 세션의 실제 답변에서 나옵니다. 답변이 아예 없으면 200이 아니라 `EVIDENCE_NOT_READY`입니다(아래 참고). `highlights` 5~8개·`detailed_evidence_by_dimension`은 항상 실제 Evidence 구조입니다. |
| Majors 조회 (`/majors/{session_id}`) | ✅ 실제 계산(§16) — **LLM 연동 여부와 무관하게 항상 실제 값입니다.** 답변이 아직 부족하면 목록이 비고 `insufficient_evidence_message`가 채워집니다(아래 4번 참고). |
| Departments 조회 (`/departments/{major_id}`) | ✅ 실제 Repository 조회(§18) — **단, 대학 13개·학과 35개 시연 데이터 기준입니다. 전국 학과 DB가 아닙니다.** `/majors/{session_id}`가 실제로 추천할 수 있는 대표 전공 3개 중 `media_communication`(학과 4개)·`industrial_engineering`(학과 3개)은 실제 학과가 연결돼 있습니다. `hci_ux`는 **비예체능 공학·정보·융합 학과만** 연결하는 원칙으로 재검토해 지금은 학과 1개(이화여자대학교 융합콘텐츠학과)뿐입니다 — 예체능 계열 학과(음악·미술·회화·조소, 시각/산업/커뮤니케이션 디자인, 실기 중심 패션디자인, 연극·영화·무용, 체육 실기 계열 및 예술대학·미술대학·디자인대학·체육대학 소속 학과)는 교육과정에 UX 등 관련 근거가 있어도 추천 대상에서 제외한다는 정책이 확정됐기 때문입니다. `design` Canonical Major는 통째로 추천에서 제외돼 `/departments/design`은 200 + 빈 목록을 반환합니다(학과 데이터 자체는 남아 있지만 노출하지 않음). **관심 Context(미술·디자인/스포츠/미디어/패션·뷰티 등)는 이 정책과 무관하게 그대로 유지되고 Trait 탐색에 계속 쓰입니다** — 관심 Context와 추천 학과 범위는 별개입니다. 그 외 `major_id`(예: `computer_science`)도 데이터상 매핑돼 있어 조회는 되지만 실제 매칭 엔진이 추천하지는 않습니다. 매핑 안 된(또는 제외된) `major_id`는 200 + 빈 목록입니다. 입결·안정/적정/상향 추천은 아직 연결 안 됨(아래 참고). **`department_url`(2026-08-31, 21차)은 지금 전부 `null`입니다** — 위 21차 갱신 내용을 확인하세요. |
| Subjects 조회 (`/subjects/{session_id}`) | ✅ 실제 PRE_SURVEY + POST_OFFERING 추천(§20) — `selected_major_id` Query Parameter 필수. `/course/confirm`을 마쳤으면 자동으로 POST_OFFERING 결과가 나옵니다(응답의 `source` 필드로 구분). 위 2026-08-26 갱신 내용을 꼭 읽어주세요. |
| 과목 업로드·확정 (`/course/upload`, `/course/confirm`) | ✅ 실제 Parser 연결 + 실제 확정 검증(§20). PDF/XLSX만 지원(XLS 제외). 위 2026-08-26 갱신 내용을 꼭 읽어주세요. |
| Subgraph 조회 (`/subgraph/{session_id}`) | ✅ 실제 계산(§23) — 답변이 하나도 없으면 `EVIDENCE_NOT_READY`, 과목 미확정이면 Trait·전공·학과까지만(부분 그래프), `/course/confirm` 완료 후에는 과목 Node까지 포함한 전체 그래프. 위 2026-08-29 갱신 내용을 꼭 읽어주세요. |
| 전국 학과 Master, 입결 필터·정렬 | ⚠️ 아직 미완성 (`schl_id`/`department_id` 일부가 대학알리미 API Key 발급 전 임시값 — 장기 저장 대상 아님) |

**질문 생성과 Profile 문장 생성만 로컬 LLM 설정에 따라 달라지고, 그 외 계산(Evidence·Trait·Matching)은 전부 실제로 동작합니다.** 화면에서 "LLM 켜짐/꺼짐"을 구분할 필요는 없습니다 — 응답 Schema(필드 이름·타입)가 동일해서 화면 코드는 그대로 씁니다.

**실제 생성된 질문·선택지가 어떤 톤인지 미리 보고 싶으면**: https://claude.ai/code/artifact/f9a0df5f-8bcf-4ea5-b904-62b8e855f6b5 (A가 LLM 검수용으로 만든 페이지 — 게임/미디어/학교생활 3개 Context 실제 생성 결과 전량). 비공개 링크라 안 보이면 A에게 공유 요청하세요. 정식 검수 기록은 `outputs/evaluation/question_generator_live_review.md`에도 있습니다.

## 3. Endpoint 목록

| Method | Path | 용도 |
|---|---|---|
| GET | `/contexts` | Context 카탈로그 + 선택 개수 정책 (세션 불필요 — 화면 로딩 시 한 번 불러와 쓰세요) |
| POST | `/assessment/session` | 세션 생성 (user_id는 서버가 자동으로 demo_user_01로 고정, 클라이언트가 지정 못 함) |
| POST | `/assessment/interest-rating` | 15개 Context 관심도(1~5) 제출 |
| POST | `/assessment/context-select` | 선호 Context **정확히 2개**(`game`/`media`/`school_life` 중, 관심도 평가를 마친 것만) 제출 → Contrast Context 1개 제안받음 |
| POST | `/assessment/context-confirm` | 최종 Context 확정 (**2개 이상 3개 이하**, `game`/`media`/`school_life` 중 — 정확히 3개를 강제하지 않음) |
| POST | `/assessment/next-question` | 다음 질문 받기 |
| POST | `/assessment/answer` | 답변 제출 |
| GET | `/profile/{session_id}` | Career Profile 결과 카드 |
| GET | `/majors/{session_id}` | 전공 관련도 목록 |
| GET | `/departments/{major_id}` | 실제 학과 목록(35개 시연 데이터 기준, 위 2번 표 참고) |
| GET | `/subjects/{session_id}?selected_major_id={major_id}` | PRE_SURVEY 또는 POST_OFFERING(확정 여부에 따라 자동 분기) 과목 추천 결과. `selected_major_id` 필수 |
| POST | `/course/upload` | 학교 PDF·XLSX 업로드 — `multipart/form-data`, `session_id`(Form) + `selected_major_id`(Form) + `file`(File). PDF/XLSX 외 형식(XLS 포함)은 422 `VALIDATION_ERROR`, 문서를 못 읽으면 422 `PARSE_FAILED` |
| POST | `/course/confirm` | 파싱된 과목 후보 확인·확정 — 성공하면 POST_OFFERING `course_profile`을 함께 반환 |
| GET | `/subgraph/{session_id}` | 실제 근거 그래프 (학생–Trait–전공–학과·대학–과목). 답변 없으면 422 `EVIDENCE_NOT_READY`, 과목 미확정이면 부분 그래프(아래 4-2 참고) |
| GET | `/session/{session_id}` | Session 복원 |

## 4. 화면에서 써야 하는 상태값 (하드코딩하지 말고 이 목록을 그대로 쓰세요)

**질문 로딩/Fallback 상태** (`NextQuestionResponse.status`):
`GENERATED` / `REGENERATING` / `CACHE_USED` / `BACKUP_USED` / `CONTEXT_EARLY_TERMINATED`

**오류 코드** (`APIError.error_code`, 404 등에서 `detail`에 담겨 옴):
`VALIDATION_ERROR` / `SESSION_NOT_FOUND` / `LLM_UNAVAILABLE` / `LANGSMITH_UNAVAILABLE` / `INTERNAL_ERROR` / `EVIDENCE_NOT_READY`(`GET /profile`·`GET /subjects`·`POST /course/upload`·`GET /subgraph` 공통 — 2026-08-29: `/subgraph`도 답변이 하나도 없으면 이 코드를 반환합니다, 새 코드가 아니라 기존 코드를 재사용) / `MAJOR_NOT_SELECTABLE`(`GET /subjects`·`POST /course/upload` 공통) / `PARSE_FAILED`(`POST /course/upload` 전용 — 문서를 읽지 못함) / `COURSE_UPLOAD_NOT_FOUND`(`POST /course/confirm` 전용, 404 — 이 세션이 아직 업로드를 안 거쳤음)

> ⚠️ **`/profile/{session_id}` 하위 호환 아닌 변경**: 답변을 하나도 제출하지 않은 세션에서
> `/profile`을 호출하면 이제 200 대신 **422 + `EVIDENCE_NOT_READY`**를 반환합니다(예전엔
> 무관한 고정 Mock Profile을 200으로 줬습니다 — 실제 계산이 가능해진 뒤로는 그게 다른
> 학생 결과를 보여주는 셈이라 없앴습니다). 화면에서 "적어도 질문 1개는 답한 뒤에 Profile
> 탭을 활성화"하는 흐름이면 원래 안 마주칠 상황이지만, 혹시 세션 생성 직후 Profile을
> 미리 호출하는 코드가 있다면 이 오류를 처리해야 합니다. 예시: `outputs/mock_api/error_evidence_not_ready__hand_crafted.json`

> ⚠️ **`/assessment/context-select`·`/assessment/context-confirm` 검증 규칙(2026-08-30, 20차 최신)**:
> 필드 이름·타입은 그대로지만, 서버가 입력을 실제로 검증합니다.
> - `context-select`의 `selected_preferred_context_ids`는 **정확히 2개**여야 하고, 그
>   2개는 반드시 `game`/`media`/`school_life`(`GET /contexts`의 `assessment_supported:
>   true` 3개) 안에서만 골라야 합니다. 빈 목록·중복·미등록 Context id·1개나 3개 이상·
>   미지원 Context(예: `art_design` — 등록은 됐지만 아직 질문 흐름이 없음)는 전부 422
>   `VALIDATION_ERROR`입니다. **관심도 평가를 아직 안 한 Context도 선호로 보낼 수
>   없습니다** — 먼저 `/assessment/interest-rating`으로 그 Context의 점수를 제출해야
>   합니다.
> - `context-confirm`의 `final_context_ids`는 **2개 이상 3개 이하**여야 하고, 역시
>   `game`/`media`/`school_life` 안에서만 고를 수 있습니다(빈 목록·중복·미등록·미지원·
>   1개·4개 이상은 422). **정확히 3개를 강제하지 않습니다** — 학생이 Contrast 제안을
>   받아들이지 않고 원래 선호 2개만으로 확정해도 정상입니다. 제안받은 Contrast 후보를
>   그대로 안 써도 되고, 학생이 처음에 고르지 않았던 지원 Context로 자유롭게 바꿔서
>   확정할 수도 있습니다 — "제안한 것만 가능"으로 강제하지 않습니다.
> - 개수 제한·지원 Context 목록을 화면에 하드코딩하지 말고 `GET /contexts`의
>   `selection_policy`/`assessment_supported`를 그대로 쓰세요(아래 "4-3" 절 참고).

> ⚠️ **`MajorRelevance.description` 신규 필수 필드(2026-08-24, Additive 변경)**:
> 전공 카드마다 그 전공이 무엇을 배우는 분야인지 설명하는 1~2문장이 추가됐습니다.
> ```text
> MajorRelevance.description:
> - 전공이 무엇을 배우는 분야인지 설명하는 1~2문장
> - 관련도 근거 문장이 아님
> - 학생 Trait 분석 문장이 아님
> - 전공 카드의 전공명 아래에 표시
> - 프론트에서 keywords를 조합해 설명을 만들지 않음
> ```
> 권장 표시:
> ```text
> 미디어·커뮤니케이션
> 미디어 콘텐츠가 만들어지고 전달되는 과정과 사람·사회에 미치는 영향을 탐구하는 전공 분야입니다.
> 관련성 높음
> ```
> `relevant_majors`·`explore_together_majors` 양쪽 모두 이 필드가 채워집니다(Optional
> 아님). 서버 정본(`data/master/canonical_majors.jsonl`)에서 결정론적으로 가져온
> 값이라 LLM이 매번 다른 문구를 만들지 않습니다 — 같은 major_id는 항상 같은 문구입니다.

**전공 관련도 정성 Label** (`MajorRelevance.relevance_label` — 절대 숫자 아님, 숫자 필드 자체가 없음):
`"관련성 높음"` / `"함께 탐색해볼 분야"` / `"비교해볼 만한 분야"`

**Evidence 충분성** (`MajorRelevance.evidence_sufficiency`):
`"충분"` / `"보통"` / `"제한적"`

**전공 목록이 아예 빈 경우** (`MajorsResponse.insufficient_evidence_message`, 신규 필드):
답변이 아직 충분하지 않아 전공 순위를 계산할 수 없을 때 `relevant_majors`·`explore_together_majors`가
둘 다 빈 배열로 오고, 이 필드에 "아직 관련도를 계산하기에 답변이 부족합니다. 추가 탐색이
필요합니다." 문구가 채워집니다. 정상 계산됐으면 이 필드는 `null`입니다 — **화면에서 반드시
이 필드를 먼저 확인하고, `null`이 아니면 목록 UI 대신 이 안내 문구를 보여주세요.**
(`outputs/mock_api/majors_normal.json`이 채워진 예시, 이 필드가 비게 되는 경우는 세션을
얼마 안 진행했을 때 재현됩니다.)

## 4-1. 학교 개설과목 업로드·확정 흐름 (실제 예시)

**1) 업로드** — `outputs/mock_api/course_upload_normal.json`이 실제 예시입니다:

```
POST /course/upload
Content-Type: multipart/form-data

session_id=sess_...
selected_major_id=industrial_engineering
file=<PDF 또는 XLSX>
```

응답의 `parsed_candidates[]` 각 항목은 `confidence`가 `"high"`(Alias와 정확히 일치)/
`"low"`(비슷하지만 확인 필요)/`"unmatched"`(전혀 못 찾음) 중 하나입니다. **셋 다
`/course/confirm`을 호출하기 전까지는 확정된 개설과목이 아닙니다** — `"high"`를 화면에서
기본 선택 상태로 보여주는 건 괜찮지만, 서버가 자동으로 확정 처리하지는 않습니다.
`"unmatched"`는 `matched_subject_id`가 `null`이라 애초에 확정에 쓸 수 없습니다(선택
불가로 표시하세요).

**2) 확인 후 확정** — 사용자가 체크한 과목들의 `matched_subject_id`만 모아서 보냅니다:

```json
POST /course/confirm
{
  "session_id": "sess_...",
  "confirmed_subject_ids": ["subj_fde7a436237d8af94c11515e", "subj_a668a359a7a11a7fbcbbc447"]
}
```

빈 배열(`[]`)도 유효합니다 — "이번 업로드에서 확정할 과목이 없음"이라는 뜻으로 정상
처리됩니다. `data/master/subjects.jsonl`에 없는 값이나 이번 업로드 후보에 없는 값을
보내면 422 `VALIDATION_ERROR`입니다.

**3) POST_OFFERING 결과** — `outputs/mock_api/course_confirm_normal.json`이 실제 예시입니다.
`confirmed_subject_ids`로 보낸 과목 중 학생 Trait 근거와 맞는 것들이 `recommendations`에
`category="core"`/`"explore"`로 옵니다. 원래 PRE_SURVEY 희망과목이었지만 이번에 개설 안 된
과목은 `unavailable_subjects`로 옮겨지고, 그 대신 제안하는 실제 개설과목이 있으면
`recommendations`에 `category="alternative"`로 오며 `replaces_subject_id`에 어떤 과목을
대신하는지 담깁니다:

```json
{
  "subject_id": "subj_a668a359a7a11a7fbcbbc447",
  "label": "정보",
  "category": "alternative",
  "is_actually_offered": true,
  "reason": "원래 희망했던 데이터 과학은 이 학교에서 실제로 개설되지 않았습니다. 대신 ...",
  "replaces_subject_id": "subj_486f78700e4a5981582a75e1"
}
```

대체 과목을 못 찾으면 `unavailable_subjects`에만 남고 `recommendations`에는 아무것도
추가되지 않습니다 — 화면에서 "대체 과목 없음"을 정직하게 보여주세요(억지로 아무 과목이나
채워 넣지 않습니다).

**4) 확인 안 된 후보(`unresolved_candidates`)** — 2026-08-27(17차) 추가. 업로드에서
`"unmatched"`로 나왔던 후보(canonical 과목을 아예 못 찾은 것들)는 Confirm을 마친 뒤에도
`course_profile.unresolved_candidates`에 그대로 남아 있습니다(`/course/confirm` 응답과
그 뒤 `GET /subjects` 재조회 응답 둘 다):

```json
"unresolved_candidates": [
  {
    "raw_text": "정체불명 과목ABC",
    "matched_subject_id": null,
    "confidence": "unmatched",
    "requires_user_confirmation": true
  }
]
```

이 후보들은 `matched_subject_id`가 없어서 `/course/confirm`으로 확정할 방법이 구조적으로
없습니다(임의의 과목에 갖다 붙이지 않습니다) — 화면에서는 "자동으로 인식하지 못한 과목"
같은 별도 영역에 `raw_text`를 그대로 보여주고, 필요하면 사용자가 직접 검색해서 수동으로
등록하는 흐름(향후 과제)을 안내하는 정도로 처리해주세요. `recommendations`에는 절대 섞여
들어오지 않습니다.

> **`unresolved_candidates`에 뭐가 오고 뭐가 안 오는지 (2026-08-28, 18차)**: 이 목록은
> "실제로 과목일 가능성이 있지만 정본 과목 목록과 매칭이 안 된 값"만 담습니다.
> 편제표의 열 제목("교과(군)", "이수 단위" 등)·학년·학점·합계·비고 같은 표 부속물은
> 서버 Parser가 애초에 후보 단계에서 걸러내서 `parsed_candidates`/`unresolved_candidates`
> 어디에도 나타나지 않습니다 — 화면에서 이런 값을 별도로 필터링할 필요는 없습니다.
> 반대로 `unmatched`는 사용자가 직접 확인해야 하는 값이라는 뜻이고, 현재는 이 값을
> 수동으로 canonical `subject_id`에 연결하는 API가 아직 없습니다(위 문단의 "향후 과제").

## 4-2. Subgraph 조회 흐름 (실제 예시, 2026-08-29)

```
GET /subgraph/{session_id}
```

`outputs/mock_api/subgraph_normal.json`이 실제 예시입니다(과목 확정까지 마친 세션 기준
— 전체 그래프). 응답 형태는 기존 `SubgraphResponse` 그대로입니다:

```json
{
  "session_id": "sess_...",
  "nodes": [
    {"node_id": "student_1", "node_type": "Student", "label": "학생"},
    {"node_id": "trait_causal_analysis", "node_type": "Trait", "label": "원인 분석"},
    {"node_id": "major_industrial_engineering", "node_type": "CanonicalMajor", "label": "산업공학"},
    {"node_id": "dept_...", "node_type": "Department", "label": "산업경영공학과"},
    {"node_id": "univ_...", "node_type": "University", "label": "경희대학교"},
    {"node_id": "subj_...", "node_type": "HighSchoolSubject", "label": "정보"}
  ],
  "edges": [
    {"source_node_id": "student_1", "target_node_id": "trait_causal_analysis", "relation_type": "HAS_TRAIT", "relevance_level": 3, "evidence_ids": ["ev_..."], "source_ids": [], "mapping_version": "v1", "created_at": "..."},
    {"source_node_id": "trait_causal_analysis", "target_node_id": "major_industrial_engineering", "relation_type": "RELATED_TO", "relevance_level": 3, "evidence_ids": ["major_trait:..."], "source_ids": ["https://..."], "mapping_version": "major_trait_mapping_v1", "created_at": "..."},
    {"source_node_id": "major_industrial_engineering", "target_node_id": "dept_...", "relation_type": "HAS_DEPARTMENT", "relevance_level": 3, "mapping_version": "v1", "created_at": "..."},
    {"source_node_id": "dept_...", "target_node_id": "univ_...", "relation_type": "BELONGS_TO", "relevance_level": 3, "mapping_version": "v1", "created_at": "..."},
    {"source_node_id": "major_industrial_engineering", "target_node_id": "subj_...", "relation_type": "RECOMMENDS", "relevance_level": 3, "mapping_version": "v1", "created_at": "..."}
  ]
}
```

읽는 법:

- **호출 시점에 따라 그래프 범위가 다릅니다.** 답변이 하나도 없으면 이 API 자체가 422
  `EVIDENCE_NOT_READY`입니다. 답변은 있지만 아직 `/course/confirm`을 안 거쳤으면
  `HighSchoolSubject` Node·`RECOMMENDS` Edge가 아예 없는 부분 그래프가 200으로 옵니다
  — 이건 오류가 아니라 "아직 과목 단계까지 안 왔다"는 정상 상태입니다. 화면에서
  과목 영역을 빈 상태(또는 "학교 편제표를 업로드하면 과목까지 표시됩니다" 안내)로
  보여주세요.
- **`relation_type`으로 실선/점선을 구분해주세요.** `HAS_TRAIT`/`HAS_DEPARTMENT`/
  `BELONGS_TO`/`RECOMMENDS`는 확정된 구조적 관계(실선). `RELATED_TO`(Trait↔전공,
  Trait↔과목)는 공식 근거가 있어도 여전히 "추론된 연관성"이라 점선으로 표현해주세요
  (기존 `src/schemas/graph.py` docstring 그대로, 이번에 안 바뀜).
- **`relevance_level`(1~3)은 학생에게 숫자로 보여주지 마세요.** 선 굵기·투명도 같은
  시각적 강조에만 쓰세요 — 다른 API의 정성 Label 원칙과 같습니다.
- **`evidence_ids`/`source_ids`는 내부 추적용 값입니다.** `evidence_ids`는
  `HAS_TRAIT`에서는 실제 Evidence 식별자, `RELATED_TO`에서는 Mapping 식별 문자열이고,
  `source_ids`는 공식 근거 URL입니다 — 화면에 그대로 노출해도 되지만("근거 보기" 같은
  보조 UI에 적합) 학생용 핵심 문구로 가공해서 보여줄 필요는 없습니다.
- **B는 이 Node·Edge를 다시 계산하지 않습니다.** 서버(`KnowledgeSubgraphService`)가
  전부 계산해서 내려주므로, 화면은 받은 그래프를 그대로 그리기만 하면 됩니다. Obsidian
  Export 변환은 B 소유 그대로이고 이번 라운드에서 A가 건드리지 않았습니다.

## 4-3. Context 카탈로그와 선택 규칙 (실제 예시, 2026-08-30)

```
GET /contexts
```

세션과 무관합니다 — 화면 로딩 시(또는 앱 시작 시) 한 번 불러와 두고 재사용하세요.
`outputs/mock_api/contexts_normal.json`이 실제 예시입니다:

```json
{
  "contexts": [
    {
      "context_id": "game",
      "label": "게임",
      "description": "게임을 하거나 게임의 구조·전략·시스템에 관심을 갖는 것",
      "example_activities": ["전략 게임 공략", "게임 시스템 분석", "커뮤니티 공략 공유"],
      "interest_rating_prompt": "게임을 하거나 게임의 시스템·전략을 분석하는 것에 관심이 있나요?",
      "is_core": true,
      "assessment_supported": true
    },
    {
      "context_id": "art_design",
      "label": "미술·디자인",
      "...": "...",
      "is_core": false,
      "assessment_supported": false
    }
  ],
  "selection_policy": {
    "preferred_context_min_count": 2,
    "preferred_context_max_count": 2,
    "contrast_context_count": 1,
    "final_context_min_count": 2,
    "final_context_max_count": 3,
    "coverage_replacement_enabled": false
  }
}
```

읽는 법:

- **`contexts`는 항상 15개, `CONTEXT_DEFINITIONS`(서버 정본)와 같은 순서로 옵니다.**
  관심도 평가 화면(15개 전부 보여주기)은 이 배열을 그대로 순회하면 됩니다.
- **`assessment_supported: true`인 Context(현재 3개: game/media/school_life)만
  `/assessment/context-select`에서 선호 Context로 고를 수 있습니다.** 나머지 12개는
  관심도는 매길 수 있지만(`/assessment/interest-rating`), 선호 Context 선택 화면에서는
  선택 불가로 표시하거나 아예 숨기세요 — 골라도 서버가 422로 거부합니다.
- **`selection_policy`의 숫자를 그대로 쓰세요.** 선호 Context 선택 UI는
  `preferred_context_min_count`~`preferred_context_max_count`(현재 둘 다 2 — "정확히
  2개")개를 고르게 만들고, 최종 확정 UI는 `final_context_min_count`~
  `final_context_max_count`(현재 2~3) 범위로 만드세요. **이 값들을 화면에 상수로
  하드코딩하지 마세요** — 다음 라운드에 Full Mode로 전환되면 이 정책 값 자체가
  바뀔 수 있고, 그때 이 API 응답만 바뀌면 화면 코드는 그대로 동작해야 합니다.
- **`coverage_replacement_enabled: false`는 "지금은 이 기능이 꺼져 있다"는 뜻입니다.**
  `ContextSelectResponse.coverage_replacement_offered`가 항상 빈 배열인 이유와 같은
  사실입니다 — 배열이 비어 있으면 교체 제안 UI를 아예 숨기세요(실제 Coverage
  Replacement 계산은 Context 확장 이후 별도 작업입니다).

## 5. Mock JSON (서버 안 띄워도 되는 정적 파일)

`outputs/mock_api/`에 정상·오류·빈 결과 예시와 `openapi.json`이 있습니다. Schema가 바뀌면 아래 명령으로 재생성됩니다(재생성됐는지 커밋 로그로 확인하세요):

```bash
PYTHONPATH=. ./.venv/bin/python scripts/generate_mock_json.py
```

## 6. Schema 원본 위치 (타입 확인하고 싶을 때)

- `src/schemas/api.py` — 모든 Endpoint의 Request/Response(`ContextCatalogItem`/`ContextCatalogResponse`/`ContextSelectionPolicyResponse` 포함)
- `src/data/contexts/context_definitions.py` — `GET /contexts`가 그대로 옮겨 담는 Context 15개 정본(A 소유, B는 참고만)
- `src/schemas/profile.py` — CareerProfile
- `src/schemas/major.py` — MajorProfile, Department, MajorRelevance
- `src/schemas/course.py` — CourseProfile(`unavailable_subjects` 포함), CourseRecommendationItem(`label: str`, `is_actually_offered: bool | None`, `replaces_subject_id: str | None`), UnavailableSubjectItem, ParsedSubjectCandidate, CourseParseWarning
- `src/schemas/graph.py` — SubgraphNode/SubgraphEdge

## 7. 알아둘 것

- Session은 In-Memory라 서버 재시작하면 다 날아갑니다. 새로고침 후 복원 UI는 만들어도 되지만, 서버 재시작까지 버티는 지속성은 아직 없습니다.
- **업로드·확정 상태(`CoursePlanningSessionState`)도 별도의 In-Memory Store입니다.** Assessment Session Store와 완전히 분리돼 있고(전공 관련 정보는 Assessment 쪽에 전혀 저장되지 않습니다), 이쪽도 서버 재시작하면 날아갑니다 — 업로드→확정까지 한 서버 프로세스 안에서 끝내야 합니다.
- **POST_OFFERING 결과는 `/course/confirm`이 완전히 성공한 뒤에만 저장됩니다(2026-08-27, 17차).** 검증이나 추천 계산 중 어디서든 실패하면 서버 상태는 요청 이전 그대로 유지됩니다 — 화면에서 실패 응답을 받으면 "일부만 반영됐을 수도 있다"고 걱정하지 않아도 됩니다.
- **업로드 용량 제한은 10MB이고, 넘으면 문서를 파싱하기 전에 거부됩니다.** 큰 파일을 올려도 서버가 끝까지 다 읽고 나서 뒤늦게 거부하지 않습니다.
- B는 UI만 구현합니다. 과목명 유사도 매칭이나 POST_OFFERING 재추천 로직을 화면 쪽에서 다시 계산하지 마세요 — 전부 서버가 계산해서 내려줍니다. 화면은 받은 `confidence`(high/low/unmatched)에 따라 확인 UI를 다르게 보여주고, 사용자가 고른 `confirmed_subject_ids`만 그대로 `/course/confirm`에 전달하면 됩니다.
- `/assessment/session`은 `user_id`를 받지 않습니다(보안상 서버가 고정) — 화면에서 이 값을 사용자가 입력하게 만들지 마세요.
- 화면에 내부 점수(예: 84%, 0.67 같은 숫자)를 노출하는 API는 애초에 없습니다. 정성 Label만 옵니다.
- `/subjects/{session_id}` 과목 추천은 **현재 시연용으로 등록된 과목 18개**(`data/master/subjects.jsonl`) 범위 안에서만 나옵니다. 전국 고교 편제표 전체를 다루는 게 아닙니다 — "이 학교엔 왜 이 과목이 없나요?" 같은 문의가 예상된다면, 시연 범위임을 화면에 짧게 안내하는 걸 권장합니다.
- `CareerProfile.title`은 "~형", "~유형", "~타입", "꼼꼼한 탐색자" 같은 성격 유형 검사식 고정
  라벨이 나오지 않도록 서버에서 강제합니다(기획 원칙 "학생을 유형으로 규정하지 않는다"). 항상
  "~보여요", "~나타났어요" 같은 관찰 서술 문장으로 옵니다 — 화면에 "유형 카드"나 "타입 뱃지"
  같은 고정 라벨 UI를 전제로 디자인하지 마세요.
- **질문 진행률(2026-08-30, 20차): 정확한 전체 문항 수와 퍼센트 진행률을 표시하지
  않습니다.** `NextQuestionResponse`에 그런 필드가 없습니다 — Adaptive 질문 수는 꼬리질문
  4~6개·Evidence 충족 여부·Conflict 확인 질문·Context 조기 종료(`CONTEXT_EARLY_
  TERMINATED`) 때문에 사전에 확정할 수 없습니다. 화면에서는 `current_context_id`와
  `questions_asked_in_current_context`로 "학교생활 탐색 중 · 완료한 답변 3개"처럼
  "진행 중인 Context + 답변한 개수"만 보여주세요. **`questions_asked_in_current_context`
  를 "이 Context의 전체 목표 문항 수"로 해석하지 마세요** — 그냥 지금까지 답한 개수입니다.
- **이전 Profile 비교(2026-08-30, 20차): `SessionRestoreResponse.has_previous_completed_
  profile`은 지금 항상 `false`입니다.** 이전 Profile을 조회하는 API와 영속 Profile
  Store가 아직 없습니다 — 이번 MVP에서는 "이전 결과와 비교" 화면을 숨겨주세요.
- **성적·입결 필터(2026-08-30, 20차): 학과 목록에 성적 필터·정렬 UI를 아직 넣지
  마세요.** Admission Repository 초안은 있지만 사용자 API·검증된 필터가 아직 연결되지
  않았습니다(위 §2 표의 "전국 학과 Master, 입결 필터·정렬" 행 참고). `/departments/
  {major_id}`가 반환하는 순서를 그대로 표시하세요.
- **LangSmith `trace_id`(2026-08-30, 20차): 서버 내부 전용입니다.** `AssessmentState.
  trace_id`는 어떤 API 응답에도 노출되지 않습니다 — 화면은 `session_id`만 API 호출
  동안 유지하면 되고, `trace_id`를 화면에 표시하거나 요청 파라미터로 보낼 필요가
  전혀 없습니다.

## 8. 문제 발견 시

데이터 표현이 이상하면 A의 파일을 직접 고치지 말고, 재현 가능한 API 요청/응답과 함께 전달해주세요.

## 브랜치 전용 `CLAUDE.md` 처리

`worker-b`의 루트 `CLAUDE.md`는 B 작업 중에만 사용하는 브랜치 전용 파일입니다. `main` PR에는 포함하지 않습니다.

- PR을 만들기 직전에 `worker-b`에서 루트 `CLAUDE.md`를 삭제하는 마무리 커밋을 추가하거나, A가 구현 커밋만 선택적으로 Cherry-pick합니다.
- PR 전 `python scripts/check_no_worker_claude.py`를 실행해 루트 `CLAUDE.md`가 최종 변경에 남지 않았는지 확인합니다.

## 참고 문서

- `outputs/work_assignments/작업자_B_개발_지시서.md` — 원래 담당 범위 전체
- `outputs/context_definition_table_draft.md`, `outputs/trait_ontology_draft.md` — Context 15개·Trait 12개 정의 (아직 검토 확정 전 초안 상태)
