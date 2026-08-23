"""V2 Direct Probe LLM 생성 품질 평가(opt-in, 실제 네트워크 호출) — 2026-08-23
Trait Ontology v2(2.1단계 §12, 2.2단계 §16, 2.4단계 §1).

2.4단계 §1: `main()`/`_write_report()`가 `output_path`를 주입받을 수 있다 — 실제 CLI
실행(`python scripts/evaluate_v2_direct_probe_llm_quality.py`)은 인자 없이 호출되므로
계속 커밋된 실제 `OUTPUT_PATH`를 쓰고, `tests/test_v2_direct_probe_llm_quality_script.py`는
`TemporaryDirectory` 안의 경로를 넘겨 커밋된 보고서를 절대 건드리지 않는다.

기본 테스트 실행(`unittest discover`)에서는 이 스크립트를 부르지 않는다 — 실제 API Key로
실제 요금이 발생하는 네트워크 호출을 한다. 명시적으로 opt-in해야만 실행된다.

실행:
    RUN_V2_DIRECT_PROBE_LLM_REVIEW=1 \\
    ./.venv/bin/python scripts/evaluate_v2_direct_probe_llm_quality.py

규칙(§12):
- Blueprint당 최대 2개 Sample(14 Blueprint × 2 = 28).
- 재시도(재생성)까지 포함한 실제 API 호출 총합이 28회를 넘지 않는다 — Sample 수가
  아니라 "실제 호출 횟수" 자체를 상한으로 강제한다(아래 `_CallBudgetedLLMClient`).
- 학생 데이터를 전혀 쓰지 않는다 — 고정 Context/Blueprint만 사용한다.
- LLM은 문장 표현만 생성한다(Trait/Role/Signal/weight는 절대 LLM이 정하지 않는다 —
  `generate_v2_direct_probe_question()`이 이미 강제한다, 이 스크립트는 그 함수를
  그대로 재사용할 뿐 별도 로직을 추가하지 않는다).
- API Key·응답 원문 어디에도 비용·Key 자체를 로그/출력 파일에 남기지 않는다(집계
  수치만 보고서에 남긴다).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # noqa: E402

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

MAX_TOTAL_LLM_CALLS = 28
MAX_SAMPLES_PER_BLUEPRINT = 2

OUTPUT_PATH = (
    Path(__file__).resolve().parents[1] / "outputs" / "evaluation" / "v2_direct_probe_llm_quality_report.md"
)


class _CallBudgetGate(Exception):
    """예산을 다 썼을 때 더 이상 실제 네트워크 호출을 하지 않기 위한 내부 신호."""


class _CallBudgetedLLMClient:
    """실제 `ChatLLMClient`를 감싸서 총 호출 횟수를 센다 — 재생성(regeneration)까지
    포함한 실제 API 호출 수가 `MAX_TOTAL_LLM_CALLS`를 넘으면 그 이후로는 실제 호출을
    하지 않고 `LLMCallError`를 던져 호출자가 Fallback으로 넘어가게 한다(§12 "실패
    재시도 포함 총호출 상한 적용")."""

    def __init__(self, inner) -> None:  # noqa: ANN001
        self._inner = inner
        self.call_count = 0

    def complete_structured(self, *, system_prompt, user_prompt, response_model):
        from src.llm.protocols import LLMCallError

        if self.call_count >= MAX_TOTAL_LLM_CALLS:
            raise LLMCallError("V2 Direct Probe LLM 품질 평가 — 호출 예산(28회) 소진")
        self.call_count += 1
        return self._inner.complete_structured(
            system_prompt=system_prompt, user_prompt=user_prompt, response_model=response_model
        )


def _write_report(
    samples: list[dict] | None, *, total_calls: int, skipped_reason: str | None,
    output_path: Path = OUTPUT_PATH,
) -> None:
    """2.4단계 §1: `output_path`를 주입할 수 있게 한다 — 실제 CLI 실행은 기존
    `OUTPUT_PATH`(커밋된 실제 보고서)를 그대로 쓰고, 테스트는 `TemporaryDirectory` 안의
    경로를 넘겨서 커밋된 파일을 절대 건드리지 않는다."""

    lines = [
        "# V2 Direct Probe LLM 생성 품질 평가 보고서",
        "",
        "2026-08-23 Trait Ontology v2(2.1단계 §12, 2.2단계 §16). 학생 데이터는 전혀 쓰지 않는다 — "
        "고정 Context·Blueprint만 사용한다. API Key·요청/응답 원문은 이 보고서에 남기지 않는다.",
        "",
    ]
    if skipped_reason is not None:
        lines.extend([
            "## 실행 여부",
            "",
            f"**실검증 미실행** — {skipped_reason}",
            "",
            "이 문단 아래에는 FakeLLM 결과를 '실제 검증'이라고 표현하지 않는다 — 이",
            "스크립트를 실제로 opt-in 실행하기 전까지는 실제 LLM 생성 품질에 대한",
            "근거가 없다는 뜻이다.",
            "",
        ])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # §1: 마지막에 빈 줄이 겹치지 않게(EOF 빈 줄 경고 방지) 끝 공백을 정리한 뒤
        # 파일 끝에 개행 하나만 남긴다.
        output_path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
        print(f"wrote {output_path} (실검증 미실행)")
        return

    assert samples is not None
    lines.extend([
        "## 실행 여부",
        "",
        f"**실제 opt-in 실행함.** 총 API 호출 수: {total_calls}(예산 {MAX_TOTAL_LLM_CALLS}회) — "
        f"Sample {len(samples)}개(Blueprint당 최대 {MAX_SAMPLES_PER_BLUEPRINT}개).",
        "",
        "NO_SIGNAL Role은 LLM이 문구를 어떻게 바꿔도 Evidence 분류(`primary_trait_delta`)가 "
        "절대 바뀌지 않는다 — `finalize_v2_probe_question()`이 그 값을 Blueprint의 "
        "mapping_type에서만 가져오고 LLM 출력 텍스트를 참고하지 않는 구조적 보장이다. "
        "문장이 실제로 다른 Trait처럼 읽히는지는 이 스크립트가 자동으로 판단하지 않는다.",
        "",
        "| trait_id | blueprint_id | sample_number | question_text | options(role:type:text) | "
        "Quality Gate | Fallback 여부 | Trait Label 노출 | Role 순서 일치 | Target 길이 이상치 | "
        "문장 자연스러움 검토 | 인접 Trait 혼동 가능성 | 사람 검토 상태 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ])
    for s in samples:
        options_text = " / ".join(f"{r}:{t}:{txt}" for r, txt, t in s["options"])
        lines.append(
            f"| {s['trait_id']} | {s['blueprint_id']} | {s['sample_number']} | "
            f"{s['question_text'].replace('|', chr(92) + '|')} | {options_text.replace('|', chr(92) + '|')} | "
            f"{s['quality_gate']} | {s['fallback']} | {s['trait_label_exposed']} | "
            f"{s['role_order_match']} | {s['target_length_outlier']} | TBD | TBD | TBD |"
        )

    llm_sourced = sum(1 for s in samples if s["fallback"] == "아니오")
    lines.extend([
        "",
        "## 요약",
        "",
        f"- 실제 LLM 경로로 생성됨: {llm_sourced}/{len(samples)}",
        f"- Fallback(base_question)으로 넘어감: {len(samples) - llm_sourced}/{len(samples)}",
        f"- Trait Label 노출 발견: {sum(1 for s in samples if s['trait_label_exposed'] == '예')}건",
        f"- Role 순서 불일치 발견: {sum(1 for s in samples if s['role_order_match'] == '아니오')}건",
        f"- Target 길이 이상치(다른 선택지 평균보다 10자 이상 김) 발견: "
        f"{sum(1 for s in samples if s['target_length_outlier'] == '예')}건",
        "",
        "'문장 자연스러움 검토'/'인접 Trait 혼동 가능성'/'사람 검토 상태'는 항상 TBD다 — "
        "이 스크립트가 자동으로 채우지 않는다(§12 자동 검사는 검토 후보 표시 용도). "
        "Target 길이 이상치도 '편향 없음'을 확정하는 게 아니라 검토 후보 표시일 뿐이다.",
        "",
        "재요청 시 LLM 호출이 늘지 않는지(멱등성)는 이 스크립트가 아니라 "
        "`tests/test_v2_direct_probe.py`의 FakeLLM 기반 단위 테스트로 검증한다 — 멱등성은 "
        "코드 경로의 성질이라 실제 LLM 백엔드와 무관하고, 반복 검증에 실제 요금이 드는 "
        "네트워크 호출을 쓸 이유가 없다.",
    ])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    print(f"wrote {output_path} ({len(samples)} samples, {total_calls} LLM calls)")


def main(output_path: Path = OUTPUT_PATH) -> None:
    if os.environ.get("RUN_V2_DIRECT_PROBE_LLM_REVIEW", "").strip().lower() not in {"1", "true", "yes"}:
        _write_report(
            None, total_calls=0,
            skipped_reason=(
                "RUN_V2_DIRECT_PROBE_LLM_REVIEW 환경변수가 설정되지 않았다(opt-in 안 됨) — "
                "기본 실행에서는 네트워크를 호출하지 않는다."
            ),
            output_path=output_path,
        )
        return

    from src.llm.settings import LLMSettingsError, load_chat_llm_settings

    try:
        settings = load_chat_llm_settings()
    except LLMSettingsError as exc:
        _write_report(None, total_calls=0, skipped_reason=f"LLM 설정이 불완전하다: {exc}", output_path=output_path)
        return

    from src.agents.assessment.v2_direct_probe_generator import generate_v2_direct_probe_question
    from src.data.contexts.context_definitions import CONTEXT_DEFINITIONS
    from src.data.questions.trait_v2_direct_probe_blueprints import V2_DIRECT_PROBE_BLUEPRINTS
    from src.engines.question_quality_gate import V2_DIRECT_PROBE_TRAIT_LABEL_PHRASES, run_quality_gate
    from src.llm.openai_client import OpenAIChatClient

    real_client = OpenAIChatClient(settings)
    budgeted_client = _CallBudgetedLLMClient(real_client)
    context_by_id = {c.context_id: c for c in CONTEXT_DEFINITIONS}

    samples: list[dict] = []
    for blueprint in V2_DIRECT_PROBE_BLUEPRINTS:
        if budgeted_client.call_count >= MAX_TOTAL_LLM_CALLS:
            break
        context_id = blueprint.base_question.context
        for sample_number in range(1, MAX_SAMPLES_PER_BLUEPRINT + 1):
            if budgeted_client.call_count >= MAX_TOTAL_LLM_CALLS:
                break
            question_id = f"{blueprint.blueprint_id}_llmreview_{sample_number:02d}"
            outcome = generate_v2_direct_probe_question(
                question_id=question_id,
                context_definition=context_by_id[context_id],
                blueprint=blueprint,
                llm_client=budgeted_client,
                max_regenerations=1,
            )
            question = outcome.question
            gate = run_quality_gate(question, forbidden_trait_label_phrases=V2_DIRECT_PROBE_TRAIT_LABEL_PHRASES)
            blueprint_role_ids = [m.role_id for m in blueprint.option_mappings]
            question_role_ids = [o.role_id for o in question.options]
            # §16: NO_SIGNAL Role은 LLM이 문구를 바꿔도 Evidence 분류가 절대 바뀌지 않는다
            # — `finalize_v2_probe_question()`이 primary_trait_delta를 Blueprint의
            # mapping_type에서만 가져오고 LLM 출력 텍스트는 참고하지 않기 때문이다
            # (구조적 보장). 문장이 실제로 다른 Trait처럼 "읽히는가"는 사람이 봐야 한다.
            no_signal_role_ids = {
                m.role_id for m in blueprint.option_mappings if m.mapping_type == "NO_SIGNAL"
            }
            target_option = next(
                (o for o in question.options if o.role_id == next(
                    m.role_id for m in blueprint.option_mappings
                    if m.mapping_type == "TRAIT_SIGNAL" and m.primary_trait_id == blueprint.trait_id
                )), None,
            )
            other_lengths = [len(o.text) for o in question.options if o is not target_option]
            target_length_outlier = bool(
                target_option is not None and other_lengths
                and len(target_option.text) > (sum(other_lengths) / len(other_lengths)) + 10
            )
            samples.append({
                "trait_id": blueprint.trait_id,
                "blueprint_id": blueprint.blueprint_id,
                "sample_number": sample_number,
                "question_text": question.question_text,
                "options": [
                    (o.role_id, o.text, "NO_SIGNAL" if o.role_id in no_signal_role_ids else "TRAIT_SIGNAL")
                    for o in question.options
                ],
                "quality_gate": "통과" if gate.passed else f"실패({'; '.join(gate.failures)})",
                "fallback": "예" if outcome.source == "backup" else "아니오",
                "trait_label_exposed": "예" if not gate.passed and any(
                    "Trait Label" in f for f in gate.failures
                ) else "아니오",
                "role_order_match": "예" if blueprint_role_ids == question_role_ids else "아니오",
                "target_length_outlier": "예" if target_length_outlier else "아니오",
            })

    _write_report(samples, total_calls=budgeted_client.call_count, skipped_reason=None, output_path=output_path)


if __name__ == "__main__":
    main()
