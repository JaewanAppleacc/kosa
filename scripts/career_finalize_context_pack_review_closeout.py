"""ContextPack 검수 종결 — 2026-08-25 지시서(a/final-integration-master-promotion) §7.

사용자 최종 결정: "기존 코멘트로 수정 요청된 문항을 제외하고 수정 완료된 질문은 모두
통과." 실측 확인: 12개 Pack × 11개 검수 Key(Routing 1·Seed 5·Anchor Backup 5) = 132개
중 REVISE는 `business::routing::business_context_router_v1` 단 1건뿐이었다(science·
sports는 이미 11/11 APPROVE, 나머지 9개 Pack은 132개 중 99개가 TBD). 그 REVISE
코멘트가 지적한 두 문항(자원 배분 순간의 어색한 문구, 방향 결정 순간의 모호한 문구)을
`src/data/context_packs/business.py`의 현재 실제 문구와 대조했다:

    코멘트: "제한된 시간이나 예산을 어떻게 쓸지 정하는 순간,:제한된 시간안에가 더
             자연스러운것같아" / "여러 방향 중 하나를 결정하는 순간: 말이 너무 모호해"
    현재 문구: "정해진 시간이나 예산 안에서 무엇을 우선할지 정하는 순간"(자원 배분) /
              "아이디어를 어떤 방식으로 실제 진행할지 결정하는 순간"(방향 결정)

두 문항 모두 코멘트가 지적한 원문과 다른, 더 자연스럽고 구체적인 문구로 이미
바뀌어 있다 — "수정 완료된 질문"에 해당하므로 이 1건도 제외 대상이 아니라 통과
대상이다. 따라서 이번 라운드는 132개 Key 전부를 승인한다(TBD 99개 + REVISE 1개 →
APPROVE, 기존 APPROVE 32개는 재저장하지 않는다).

이 스크립트는 실제 Review UI Store(`update_context_pack_review`)만 쓴다 — Review
JSON을 문자열 치환으로 수정하지 않는다. reviewer_1_comment는 항상 기존 값을 그대로
넘겨 보존한다(이 Store 함수는 comment를 부분 갱신하지 않고 항상 덮어쓰므로, 이
스크립트가 명시적으로 기존 값을 다시 넣어야 한다)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.contexts.context_definitions import CONTEXT_IDS  # noqa: E402
from src.review_ui.context_pack_review_service import update_context_pack_review  # noqa: E402
from src.services.context_pack_registry import ContextPackRegistry, discover_context_packs  # noqa: E402
from src.services.context_pack_review_store import load_context_pack_review_entries  # noqa: E402

RESOLUTION_NOTE = "사용자 최종 일괄 검수 결정에 따라 기존 코멘트의 수정 요청이 이미 반영된 질문으로 판단해 승인"


def run_closeout(*, review_status_dir: Path | None = None) -> dict[str, dict]:
    packs, discovery_errors = discover_context_packs()
    if discovery_errors:
        raise RuntimeError(f"ContextPack 발견 중 오류: {discovery_errors}")

    registry = ContextPackRegistry(known_context_ids=frozenset(CONTEXT_IDS), review_status_dir=review_status_dir)

    results: dict[str, dict] = {}
    for context_id, pack in sorted(packs.items()):
        required_keys = sorted(registry.required_review_keys(pack))
        base_dir = registry.review_status_path_for(context_id).parent
        existing_by_key = {e.blueprint_id: e for e in load_context_pack_review_entries(context_id, base_dir)}

        updated_count, unchanged_count = 0, 0
        for key in required_keys:
            existing = existing_by_key.get(key)
            already_done = (
                existing is not None
                and existing.reviewer_1_status == "APPROVE"
                and existing.resolution_note == RESOLUTION_NOTE
            )
            if already_done:
                unchanged_count += 1
                continue
            existing_comment = existing.reviewer_1_comment if existing is not None else ""
            update_context_pack_review(
                registry, context_id, key, status="APPROVE", comment=existing_comment, resolution_note=RESOLUTION_NOTE,
            )
            updated_count += 1

        final_by_key = {e.blueprint_id: e for e in load_context_pack_review_entries(context_id, base_dir)}
        statuses = [final_by_key[k].reviewer_1_status if k in final_by_key else "TBD" for k in required_keys]
        results[context_id] = {
            "total_keys": len(required_keys),
            "updated_this_run": updated_count,
            "unchanged_this_run": unchanged_count,
            "approve_count": statuses.count("APPROVE"),
            "tbd_count": statuses.count("TBD"),
            "revise_count": statuses.count("REVISE"),
            "hold_count": statuses.count("HOLD"),
            "pack_review_approved": registry.is_pack_review_approved(context_id),
        }
    return results


def main() -> None:
    results = run_closeout()
    for context_id, result in results.items():
        print(f"=== {context_id} ===")
        for k, v in result.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
