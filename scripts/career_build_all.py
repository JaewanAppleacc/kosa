"""C 산출 데이터를 처음부터 다시 만든다.

`data/raw/`와 각 빌드 스크립트 안의 표만 원본이고, `data/master/`·`data/drafts/`·
`data/eval_fixtures/`·`data/rag/`·`data/audit/`는 전부 이 명령 하나로 재생성된다.
순서가 있다 — 학과 Master가 있어야 입결·RAG가 학과를 참조할 수 있고, 질문 초안이 있어야
Coverage 표를 만들 수 있다.

실행:
    python scripts/career_build_all.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

STEPS: list[tuple[str, str]] = [
    ("career_build_department_master.py", "대학·학과 Master 정제 + Canonical Mapping"),
    ("career_build_major_profiles.py", "대표 전공 Profile + Major-Trait Mapping 초안"),
    ("career_build_subject_profiles.py", "고교 과목 Master + Subject-Trait Mapping 초안"),
    ("career_build_admission_references.py", "AdmissionReference 골격"),
    ("career_build_rag_corpus.py", "RAG 수집 목록·원문·색인·Manifest"),
    ("career_build_question_blueprints.py", "비핵심 Context Seed Question 초안"),
    ("career_build_context_trait_review.py", "Context × Trait Coverage 검토표"),
    ("career_build_persona_fixtures.py", "Persona + Hand-Calculated Fixture"),
    ("career_build_eval_fixtures.py", "RAG·Mapping 기대값, 질문 Cache"),
    ("career_measure_thresholds.py", "임계값 근거 재측정"),
    ("career_audit_data_quality.py", "데이터 품질 검사"),
]


def main() -> int:
    # 산출물·로그가 전부 한글이라 Windows 기본 콘솔 인코딩(cp949)에서는 출력이 깨지거나
    # UnicodeEncodeError로 죽는다. 자식 프로세스 출력만 UTF-8로 고정한다.
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    for script, description in STEPS:
        print(f"\n=== {description} ({script}) ===")
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script)], cwd=ROOT, check=False, env=env
        )
        if completed.returncode != 0:
            print(f"실패: {script} (종료 코드 {completed.returncode})")
            return completed.returncode
    print("\n전체 재생성 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
