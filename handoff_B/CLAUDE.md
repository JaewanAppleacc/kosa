# AI 진로·학업설계 Agent — 작업자 B 구현 지침

## 역할

이 폴더에서 Claude Code는 작업자 B(프론트엔드)의 구현 도구다. `작업자_B_개발_지시서.md`에
정의된 범위 안에서 화면·상태관리·프론트엔드 테스트를 작성한다.

발표 자료, PPT, Obsidian 실제 구현은 이 지시서의 범위가 아니다.

## Source of Truth

1. 작업자 B 개발 지시서: `작업자_B_개발_지시서.md` (이 폴더에 포함됨)
2. 이 폴더의 API 계약: `src/schemas/api.py`, `src/api/main.py`, `mock_api/*.json`
3. 최신 설계안 (필요 시 A에게 요청하거나 본 저장소 `https://github.com/JaewanAppleacc/kosa.git` 참고)

이 폴더는 **base commit `0110f07`(2026-08-21) 기준 스냅샷**이다. 이후 API 계약이 바뀌면 A가
새 Mock JSON과 함께 변경 내용을 알려준다 — 이 폴더의 `src/schemas/`, `src/api/`를 직접 고쳐서
임의로 계약을 바꾸지 않는다.

## B가 소유하는 영역

- `frontend/`, `ui/` (아직 이 폴더엔 없음 — B가 새로 만든다)
- `src/graph/obsidian_exporter.py`
- `frontend tests/`

## B가 소유하지 않는 영역 (이 폴더에 참고용으로 들어있는 것들)

```
src/schemas/          A 소유. 필드가 부족하면 직접 추가하지 말고 A에게 요청
src/api/               A 소유. Mock을 실제 로직으로 바꾸는 건 A가 함
src/memory/            A 소유
src/ids.py             A 소유
```

이 파일들은 **읽고 참고하되 수정하지 않는다.** 화면에 필요한 필드가 없으면 A에게 Schema
변경을 요청한다.

## 아키텍처 불변식

- 프론트엔드는 API JSON만 쓴다. LangGraph State나 DB에 직접 접근하지 않는다.
- 백엔드 내부 점수 계산(전공 관련도 등)을 프론트엔드에서 다시 구현하지 않는다.
- `MajorRelevance.relevance_label` 같은 정성 Label만 화면에 노출한다. 내부 숫자를 계산해서
  보여주지 않는다.
- `/assessment/session`은 `user_id`를 받지 않는다 — 사용자가 이 값을 입력하게 만들지 않는다.

## 코드 작성 원칙

- Mock API와 실제 API 전환 지점을 환경설정으로 분리한다.
- 정상/빈 결과/부분 결과/오류 상태를 구분해서 렌더링한다(`mock_api/`의 `__hand_crafted` 파일들이
  각 상태의 형태 예시다).
- API 응답을 Schema에 맞춰 검증한다.
- 요구되지 않은 대규모 Refactor나 새 프레임워크 도입을 하지 않는다.

## 작업 반환 시

- 이 폴더 기준으로 B가 만든 `frontend/`, `ui/`, `src/graph/obsidian_exporter.py`,
  `frontend tests/`만 반환한다. `src/schemas/`, `src/api/` 등 참고용 파일은 수정했더라도
  반환하지 않는다(A가 이미 최신 버전을 갖고 있음).
- 공통 Schema 변경이 필요하면 직접 고치지 말고 A에게 요청한다.
- 데이터 표현이 이상하면 재현 가능한 API 요청/응답과 함께 A에게 전달한다.

## 금지 사항

- 화면에 내부 점수(예: 84%, 0.67) 노출
- `src/schemas/`, `src/api/` 직접 수정
- Mock 응답 구조를 프론트엔드에서 임의로 확장해서 쓰기 (A와 계약 안 맞음)
