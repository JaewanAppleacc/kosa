"""C 스크립트 공용 콘솔 설정.

산출물·로그가 전부 한국어이고 대시(—) 같은 문자를 쓴다. Windows 기본 콘솔 인코딩은
cp949라, 이대로 출력하면 스크립트가 계산을 다 끝내 놓고 마지막 print에서
UnicodeEncodeError로 죽는다. 결과 파일은 이미 UTF-8로 잘 쓰이는데 화면 출력만 실패하는
거라 원인을 찾기도 어렵다.

`career_build_all.py`는 자식 프로세스에 PYTHONIOENCODING을 넘겨 이 문제를 피하지만,
스크립트를 하나씩 직접 실행할 때는 그 보호가 없다. 그래서 각 스크립트가 시작할 때
자기 표준 출력을 UTF-8로 바꾼다.
"""

from __future__ import annotations

import sys


def use_utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
