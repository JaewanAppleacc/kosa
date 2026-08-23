"""V2 Direct Probe 로컬 전용 검수 UI 실행 — 2026-08-23 Trait Ontology v2(2.4단계) §2.

`src/review_ui/app.py`(공개 서비스 API와 완전히 분리된 내부 App)를 127.0.0.1에만
바인딩해서 띄운다. 외부 네트워크에 노출하지 않는다 — `host`를 바꾸지 마라.

실행:
    PYTHONPATH=. ./.venv/bin/python scripts/run_v2_direct_probe_review_ui.py

기본 접속 주소: http://127.0.0.1:8765
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # noqa: E402

import uvicorn  # noqa: E402

HOST = "127.0.0.1"
PORT = 8765


def main() -> None:
    print(f"V2 Direct Probe Review UI — http://{HOST}:{PORT} (로컬 전용, 외부 노출 안 됨)")
    uvicorn.run("src.review_ui.app:app", host=HOST, port=PORT, reload=False, log_level="warning")


if __name__ == "__main__":
    main()
