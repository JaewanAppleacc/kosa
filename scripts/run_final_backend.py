"""최종 Runtime Backend 실행 — 2026-08-25 지시서(a/final-runtime-v2-primary) §2.

최종 로컬·시연 환경은 다음 네 Flag가 항상 함께 켜져 있어야 한다 — 하나라도 빠지면
`/profile`·`/majors`·`/subjects`가 조용히 Legacy Trait 요약 경로로 되돌아가 검사
완료 후에도 `insufficient_evidence_message`가 반환될 수 있다(실측 재현 결과는
지시서 §1 참고).

    ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES=true
    ENABLE_TRAIT_VECTOR_V2_PRIMARY=true
    ENABLE_CONTEXT_PACK_RUNTIME=true
    ENABLE_CONTEXT_SELECTION_4_PLUS_1=true

이 스크립트는 그 네 Flag가 전부 켜져 있는지 서버를 띄우기 전에 검사하고, 하나라도
빠지면 **어떤 Flag가 빠졌는지 이름만** 출력하고(값·다른 환경변수는 절대 출력하지
않는다) 종료 코드 2로 즉시 실패한다 — 기존 Feature Flag들의 기본값 OFF는 그대로
유지한다(이 스크립트가 실행 환경에 값을 대신 채워 넣지 않는다 — 실제 실행 명령이나
`.env`가 이미 네 값을 설정해 뒀는지만 확인한다). `.env` 자체는 이 스크립트도, 이
Repository의 다른 어떤 파일도 커밋하지 않는다.

일반 `unittest` 스위트는 이 스크립트를 import하는 것만으로 서버가 뜨거나 검사
로직이 자동 실행되지 않는다 — `validate_final_runtime_flags()`만 순수 함수로
따로 테스트할 수 있다(§2 "테스트 환경에서는 실제 서버 Process를 띄우지 않고 설정
검증 함수만 테스트 가능").

실행:
    PYTHONPATH=. ./.venv/bin/python scripts/run_final_backend.py
    PYTHONPATH=. ./.venv/bin/python scripts/run_final_backend.py --port 8123
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # noqa: E402

from scripts.career_console import use_utf8_stdout  # noqa: E402

# 기존 project 관례(uvicorn CLI 기본값, README_B의 "실행: uvicorn src.api.main:app")를
# 그대로 따른다 — 이 스크립트가 새 기본 포트를 정하지 않는다.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000

# src/services/feature_flags.py의 실제 로더 4개와 정확히 같은 이름·같은 값
# 판정 방식을 쓴다 — 새 판정 규칙을 여기서 다시 만들지 않는다(단일 정본 원칙).
REQUIRED_FLAG_NAMES = (
    "ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES",
    "ENABLE_TRAIT_VECTOR_V2_PRIMARY",
    "ENABLE_CONTEXT_PACK_RUNTIME",
    "ENABLE_CONTEXT_SELECTION_4_PLUS_1",
)


def _flag_on(name: str, env: dict[str, str]) -> bool:
    # src.services.feature_flags._flag_on과 동일한 판정 — 이 스크립트는 src.api.main을
    # import하기 전에 검사해야 하므로(그래야 Import 부작용 전에 Fail-Fast한다) 그
    # 모듈에 의존하지 않고 같은 규칙만 그대로 복제한다.
    return env.get(name, "").strip().lower() in {"1", "true", "yes"}


def validate_final_runtime_flags(env: dict[str, str] | None = None) -> list[str]:
    """네 Flag 중 켜지지 않은 것의 이름 목록을 돌려준다(전부 켜져 있으면 빈 목록).

    순수 함수다 — 아무것도 출력하지 않고, 프로세스를 띄우거나 종료하지 않는다.
    `env`를 생략하면 `os.environ`을 읽는다."""

    source = env if env is not None else os.environ
    return [name for name in REQUIRED_FLAG_NAMES if not _flag_on(name, source)]


def main(argv: list[str] | None = None) -> int:
    use_utf8_stdout()

    parser = argparse.ArgumentParser(description="최종 Runtime Backend 실행(4개 Flag 전부 ON 필수)")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--reload", action="store_true", help="개발용 자동 재시작(uvicorn --reload)")
    args = parser.parse_args(argv)

    missing = validate_final_runtime_flags()
    if missing:
        print("최종 Runtime Backend를 시작할 수 없습니다 — 다음 Flag가 꺼져 있습니다:", file=sys.stderr)
        for name in missing:
            print(f"  - {name}", file=sys.stderr)
        print(
            "네 Flag를 전부 true로 설정한 뒤 다시 실행하세요("
            "ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES/ENABLE_TRAIT_VECTOR_V2_PRIMARY/"
            "ENABLE_CONTEXT_PACK_RUNTIME/ENABLE_CONTEXT_SELECTION_4_PLUS_1).",
            file=sys.stderr,
        )
        return 2

    print("최종 Runtime Backend — 4개 Flag 전부 ON 확인 완료:")
    for name in REQUIRED_FLAG_NAMES:
        print(f"  - {name}=true")
    print(f"http://{args.host}:{args.port} 에서 src.api.main:app 실행")

    import uvicorn

    uvicorn.run("src.api.main:app", host=args.host, port=args.port, reload=args.reload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
