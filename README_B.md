# B 작업자 핸드오프 — 2026-08-22 (갱신)

이 저장소(`kosa`)를 clone하면 바로 프론트엔드 개발을 시작할 수 있습니다. B 작업자는 별도 ZIP이나 `CLAUDE.md` 없이 이 문서를 시작점으로 사용합니다. 필요한 API 계약과 Mock 예시는 아래 경로에서 확인할 수 있습니다.

> **2026-08-22 갱신 내용**: C의 Repository·RAG·MCP·데이터 구현이 병합된 뒤 첫 통합 단계로
> `GET /departments/{major_id}`가 고정 Mock에서 실제 `JsonlDepartmentRepository` 조회로
> 바뀌었습니다. Response Schema는 동일하지만, **지금 연결된 데이터는 대학 10개·학과 30개
> 시연 데이터**입니다(전국 학과 DB 아님) — 아래 2번 표를 확인하세요. Subjects/Subgraph,
> 입결·안정/적정/상향 추천은 아직 연결되지 않았습니다.

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
| Profile 조회 (`/profile/{session_id}`) | ✅ 실제 계산(§14) — LLM 켜져 있으면 실제 문장, 꺼져 있으면 Mock 문장. `highlights` 5~8개·`detailed_evidence_by_dimension`은 항상 실제 Evidence 구조입니다. |
| Majors 조회 (`/majors/{session_id}`) | ✅ 실제 계산(§16) — **LLM 연동 여부와 무관하게 항상 실제 값입니다.** 답변이 아직 부족하면 목록이 비고 `insufficient_evidence_message`가 채워집니다(아래 4번 참고). |
| Departments 조회 (`/departments/{major_id}`) | ✅ 실제 Repository 조회(§18) — **단, C가 구축한 대학 10개·학과 30개 시연 데이터 기준입니다. 전국 학과 DB가 아닙니다.** 매핑된 대표 전공(`computer_science` 등 8개)만 학과가 나오고, 그 외 `major_id`는 200 + 빈 목록입니다. 입결·안정/적정/상향 추천은 아직 연결 안 됨(아래 참고). |
| Subjects / Subgraph 조회 | ⚠️ 아직 고정 Mock (A의 Subject Planning 미완료) |
| 전국 학과 Master, 입결 필터·정렬 | ⚠️ 아직 미완성 (`schl_id`/`department_id` 일부가 대학알리미 API Key 발급 전 임시값 — 장기 저장 대상 아님) |

**질문 생성과 Profile 문장 생성만 로컬 LLM 설정에 따라 달라지고, 그 외 계산(Evidence·Trait·Matching)은 전부 실제로 동작합니다.** 화면에서 "LLM 켜짐/꺼짐"을 구분할 필요는 없습니다 — 응답 Schema(필드 이름·타입)가 동일해서 화면 코드는 그대로 씁니다.

**실제 생성된 질문·선택지가 어떤 톤인지 미리 보고 싶으면**: https://claude.ai/code/artifact/f9a0df5f-8bcf-4ea5-b904-62b8e855f6b5 (A가 LLM 검수용으로 만든 페이지 — 게임/미디어/학교생활 3개 Context 실제 생성 결과 전량). 비공개 링크라 안 보이면 A에게 공유 요청하세요. 정식 검수 기록은 `outputs/evaluation/question_generator_live_review.md`에도 있습니다.

## 3. Endpoint 목록

| Method | Path | 용도 |
|---|---|---|
| POST | `/assessment/session` | 세션 생성 (user_id는 서버가 자동으로 demo_user_01로 고정, 클라이언트가 지정 못 함) |
| POST | `/assessment/interest-rating` | 15개 Context 관심도(1~5) 제출 |
| POST | `/assessment/context-select` | 선호 Context 4개 제출 → Contrast Context 1개 제안받음 |
| POST | `/assessment/context-confirm` | 최종 Context 확정 (Vertical Slice는 3개: game/media/school_life) |
| POST | `/assessment/next-question` | 다음 질문 받기 |
| POST | `/assessment/answer` | 답변 제출 |
| GET | `/profile/{session_id}` | Career Profile 결과 카드 |
| GET | `/majors/{session_id}` | 전공 관련도 목록 |
| GET | `/departments/{major_id}` | 실제 학과 목록(30개 시연 데이터 기준, 위 2번 표 참고) |
| GET | `/subjects/{session_id}` | 과목 추천 결과 |
| POST | `/course/upload` | 학교 PDF·Excel 업로드 — `multipart/form-data`, `session_id`(Form) + `file`(File). PDF/Excel 외 형식은 422 `VALIDATION_ERROR` |
| POST | `/course/confirm` | 파싱된 과목 후보 확인·확정 |
| GET | `/subgraph/{session_id}` | 관계 그래프 (Trait–전공–학과–과목) |
| GET | `/session/{session_id}` | Session 복원 |

## 4. 화면에서 써야 하는 상태값 (하드코딩하지 말고 이 목록을 그대로 쓰세요)

**질문 로딩/Fallback 상태** (`NextQuestionResponse.status`):
`GENERATED` / `REGENERATING` / `CACHE_USED` / `BACKUP_USED` / `CONTEXT_EARLY_TERMINATED`

**오류 코드** (`APIError.error_code`, 404 등에서 `detail`에 담겨 옴):
`VALIDATION_ERROR` / `SESSION_NOT_FOUND` / `LLM_UNAVAILABLE` / `LANGSMITH_UNAVAILABLE` / `INTERNAL_ERROR` / `EVIDENCE_NOT_READY`(신규)

> ⚠️ **`/profile/{session_id}` 하위 호환 아닌 변경**: 답변을 하나도 제출하지 않은 세션에서
> `/profile`을 호출하면 이제 200 대신 **422 + `EVIDENCE_NOT_READY`**를 반환합니다(예전엔
> 무관한 고정 Mock Profile을 200으로 줬습니다 — 실제 계산이 가능해진 뒤로는 그게 다른
> 학생 결과를 보여주는 셈이라 없앴습니다). 화면에서 "적어도 질문 1개는 답한 뒤에 Profile
> 탭을 활성화"하는 흐름이면 원래 안 마주칠 상황이지만, 혹시 세션 생성 직후 Profile을
> 미리 호출하는 코드가 있다면 이 오류를 처리해야 합니다. 예시: `outputs/mock_api/error_evidence_not_ready__hand_crafted.json`

> ⚠️ **`/assessment/context-select`·`/assessment/context-confirm` 검증 강화(2026-08-22)**:
> 필드 이름·타입은 그대로지만, 이제 서버가 입력을 실제로 검증합니다.
> - `context-select`의 `selected_preferred_context_ids`가 비어 있거나, 중복이 있거나,
>   알 수 없는 Context id를 포함하면 422 `VALIDATION_ERROR`.
> - `context-confirm`의 `final_context_ids`도 동일하게 검증하고, 추가로 **아직 실제
>   질문 흐름을 지원하는 Context가 game/media/school_life 3개뿐이라** 그 외 Context id는
>   거부합니다(알려진 Context라도). 제안받은 Contrast 후보를 그대로 안 써도 되고, 학생이
>   다른 유효한 조합으로 자유롭게 바꿔서 확정할 수 있습니다 — "제안한 것만 가능"으로
>   강제하지 않습니다.

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

## 5. Mock JSON (서버 안 띄워도 되는 정적 파일)

`outputs/mock_api/`에 정상·오류·빈 결과 예시와 `openapi.json`이 있습니다. Schema가 바뀌면 아래 명령으로 재생성됩니다(재생성됐는지 커밋 로그로 확인하세요):

```bash
PYTHONPATH=. ./.venv/bin/python scripts/generate_mock_json.py
```

## 6. Schema 원본 위치 (타입 확인하고 싶을 때)

- `src/schemas/api.py` — 모든 Endpoint의 Request/Response
- `src/schemas/profile.py` — CareerProfile
- `src/schemas/major.py` — MajorProfile, Department, MajorRelevance
- `src/schemas/course.py` — CourseProfile, ParsedSubjectCandidate
- `src/schemas/graph.py` — SubgraphNode/SubgraphEdge

## 7. 알아둘 것

- Session은 In-Memory라 서버 재시작하면 다 날아갑니다. 새로고침 후 복원 UI는 만들어도 되지만, 서버 재시작까지 버티는 지속성은 아직 없습니다.
- `/assessment/session`은 `user_id`를 받지 않습니다(보안상 서버가 고정) — 화면에서 이 값을 사용자가 입력하게 만들지 마세요.
- 화면에 내부 점수(예: 84%, 0.67 같은 숫자)를 노출하는 API는 애초에 없습니다. 정성 Label만 옵니다.
- `CareerProfile.title`은 "~형", "~유형", "~타입", "꼼꼼한 탐색자" 같은 성격 유형 검사식 고정
  라벨이 나오지 않도록 서버에서 강제합니다(기획 원칙 "학생을 유형으로 규정하지 않는다"). 항상
  "~보여요", "~나타났어요" 같은 관찰 서술 문장으로 옵니다 — 화면에 "유형 카드"나 "타입 뱃지"
  같은 고정 라벨 UI를 전제로 디자인하지 마세요.

## 8. 문제 발견 시

데이터 표현이 이상하면 A의 파일을 직접 고치지 말고, 재현 가능한 API 요청/응답과 함께 전달해주세요.

## 브랜치 전용 `CLAUDE.md` 처리

`worker-b`의 루트 `CLAUDE.md`는 B 작업 중에만 사용하는 브랜치 전용 파일입니다. `main` PR에는 포함하지 않습니다.

- PR을 만들기 직전에 `worker-b`에서 루트 `CLAUDE.md`를 삭제하는 마무리 커밋을 추가하거나, A가 구현 커밋만 선택적으로 Cherry-pick합니다.
- PR 전 `python scripts/check_no_worker_claude.py`를 실행해 루트 `CLAUDE.md`가 최종 변경에 남지 않았는지 확인합니다.

## 참고 문서

- `outputs/work_assignments/작업자_B_개발_지시서.md` — 원래 담당 범위 전체
- `outputs/context_definition_table_draft.md`, `outputs/trait_ontology_draft.md` — Context 15개·Trait 12개 정의 (아직 검토 확정 전 초안 상태)
