# AI 진로·학업설계 Agent — 작업자 B 구현 지침 (`worker-b` 브랜치)

## 역할

이 브랜치에서 Claude Code는 작업자 B(프론트엔드)의 구현 도구다. `outputs/work_assignments/작업자_B_개발_지시서.md`에 정의된 범위 안에서 화면·상태관리·프론트엔드 테스트를 작성한다.

발표 자료와 PPT 제작은 이 지시서의 범위가 아니다. 관계 그래프와 Obsidian Export 실제 구현은 B의 담당 범위다.

## Source of Truth

1. 작업자 B 개발 지시서: `outputs/work_assignments/작업자_B_개발_지시서.md`
2. API 계약: `src/schemas/api.py`, `src/api/main.py`, `outputs/mock_api/*.json`
3. 사용법 요약: `README_B.md` (repo root)
4. `main` 브랜치가 계약의 최신 상태다. `main`이 바뀌면 이 브랜치로 `git merge main` 또는 `git rebase main`해서 따라간다.

## B가 소유하는 영역

- `frontend/`, `ui/` (아직 없음 — B가 새로 만든다)
- `src/graph/obsidian_exporter.py`
- `frontend tests/`

## B가 소유하지 않는 영역 (읽고 참고하되 수정하지 않는다)

```
src/schemas/     A 소유. 필드가 부족하면 직접 추가하지 말고 A에게 요청
src/api/         A 소유. Mock을 실제 로직으로 바꾸는 건 A가 함
src/memory/      A 소유
src/ids.py       A 소유
src/agents/, src/engines/, eval/, src/data/   A 소유, B와 무관
```

브랜치를 나눴다고 소유권 규칙이 바뀌지 않는다. 이 브랜치 안에서도 위 파일은 건드리지 않는다.

## 아키텍처 불변식

- 프론트엔드는 API JSON만 쓴다. LangGraph State나 DB에 직접 접근하지 않는다.
- 백엔드 내부 점수 계산(전공 관련도 등)을 프론트엔드에서 다시 구현하지 않는다.
- `MajorRelevance.relevance_label` 같은 정성 Label만 화면에 노출한다. 내부 숫자를 계산해서 보여주지 않는다.
- `/assessment/session`은 `user_id`를 받지 않는다 — 사용자가 이 값을 입력하게 만들지 않는다.

## 코드 작성 원칙

- Mock API와 실제 API 전환 지점을 환경설정으로 분리한다.
- 정상/빈 결과/부분 결과/오류 상태를 구분해서 렌더링한다(`outputs/mock_api/`의 `*__hand_crafted.json`이 각 상태의 형태 예시다).
- API 응답을 Schema에 맞춰 검증한다.
- 요구되지 않은 대규모 Refactor나 새 프레임워크 도입을 하지 않는다.

## 작업 흐름 (브랜치 기반)

- 이 브랜치(`worker-b`)에서 커밋한다. `main`에 직접 push하지 않는다.
- 작업이 어느 정도 쌓이면 `main`으로 PR을 올리거나 A에게 병합을 요청한다. `frontend/`, `ui/`, `src/graph/obsidian_exporter.py`, `frontend tests/` 외의 파일은 diff에 포함되지 않게 한다.
- 이 루트 `CLAUDE.md`는 작업 브랜치 전용이다. PR 직전에 삭제 커밋을 추가하거나 A가 구현 커밋만 Cherry-pick하며, 어떤 경우에도 `main`에 병합하지 않는다.
- PR 전 `python scripts/check_no_worker_claude.py`를 실행한다. 이 브랜치에서는 삭제 전까지 실패하는 것이 정상이며, 최종 PR 상태에서는 통과해야 한다.
- `main`의 계약(Schema/API)이 바뀌면 A가 알려준다. 그 전까지 이 브랜치가 최신이라고 가정하지 않는다 — 작업 시작 전 `git fetch origin && git log main..origin/main`으로 뒤처지지 않았는지 확인한다.
- 공통 Schema 변경이 필요하면 직접 고치지 말고 A에게 요청한다.

## 금지 사항

- 화면에 내부 점수(예: 84%, 0.67) 노출
- `src/schemas/`, `src/api/` 직접 수정
- Mock 응답 구조를 프론트엔드에서 임의로 확장해서 쓰기 (A와 계약 안 맞음)
- `main`에 직접 push
