"""AcademyInfo 분류 REVIEW_REQUIRED — P1(추천 노출 직접 영향) 사람 검수 패킷 생성
— 2026-08-24 지시서(c/academyinfo-classification-p1-review).

분류 REVIEW_REQUIRED 1,936건 전체 중, 추천 노출에 직접 영향을 주는 P1 374건
(콘텐츠·미디어 275 + 디자인/HCI/UX 99)만 사람이 빠르게 판단할 수 있는 검수 패킷
으로 정리한다. P1 선별 기준은 `career_build_academyinfo_review_packets.py`가 이미
쓰고 있는 `cluster_of()`(학과명·단과대학명 키워드 군집)를 그대로 재사용한다 —
이 스크립트가 새 키워드 목록을 만들면 기존 군집 정의와 어긋날 위험이 있다.

**Claude가 확정하지 않는다.** `judgment_candidate`는 사람이 볼 "판단 후보"일
뿐이고, 6개 값 중 실제로 공식 필드(`candidate_canonical_major_ids` — 대학알리미
공식 소계열 코드로 이미 계산된 후보 전공군)에 근거해 확정적으로 매길 수 있는 건
DESIGN_ARTS_EXCLUDED/PERFORMING_MEDIA_ARTS_EXCLUDED/MEDIA_COMMUNICATION_CANDIDATE
뿐이다. HCI_UX_CANDIDATE는 대학알리미 158개 공식 소계열 어디에도 "HCI/UX"에
대응하는 코드가 없어(이미 canonical_major_group_bridge 검토에서 확인된 사실) 학과·
단과대학명의 HCI/UX 관련 키워드로 "검토 후보"만 표시하고, 이 근거만으로는 확정
버킷으로 보지 않는다. 공식 근거가 없으면 추측하지 말고 NEEDS_OFFICIAL_CURRICULUM
으로 유지한다.

만드는 것(전부 `data/academyinfo_work/2025/packets/` 아래):

    p1_classification_review.jsonl        374행 검수 패킷(JSONL)
    p1_classification_review_packet.html  사람이 읽는 검수 패킷(콘텐츠·미디어/
                                           디자인·HCI·UX 별도 필터)
    p1_classification_review_manifest.json 입력·출력 Hash, 통계

실행:
    python scripts/career_build_academyinfo_p1_classification_review.py --survey-year 2025
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_build_academyinfo_review_packets import cluster_of, read_jsonl  # noqa: E402
from scripts.career_console import use_utf8_stdout  # noqa: E402

# ── P1 선별(기존 군집 정의 재사용) ────────────────────────────────────────
P1_CLUSTER_CODES = ("CONTENT_MEDIA", "DESIGN_HCI_UX")

# ── §1 판단 후보 6종 ──────────────────────────────────────────────────────
MEDIA_COMMUNICATION_CANDIDATE = "MEDIA_COMMUNICATION_CANDIDATE"
HCI_UX_CANDIDATE = "HCI_UX_CANDIDATE"
DESIGN_ARTS_EXCLUDED = "DESIGN_ARTS_EXCLUDED"
PERFORMING_MEDIA_ARTS_EXCLUDED = "PERFORMING_MEDIA_ARTS_EXCLUDED"
NEEDS_OFFICIAL_CURRICULUM = "NEEDS_OFFICIAL_CURRICULUM"
UNMAPPED = "UNMAPPED"

# 예체능 4개 전공군(canonical_major_group_bridge_loader.ARTS_EXCLUDED_GROUP_IDS와
# 정확히 같은 4개). music/performing_media_arts/sports_dance는 fine_arts_design과
# 구분해서 PERFORMING_MEDIA_ARTS_EXCLUDED로 분리한다 — "디자인" 경계 사례와
# "공연·영상·체육" 경계 사례는 사람이 확인해야 하는 공식 근거가 다르다.
_DESIGN_ARTS_GROUP = "fine_arts_design"
_PERFORMING_MEDIA_ARTS_GROUPS = frozenset({"music", "performing_media_arts", "sports_dance"})
_MEDIA_COMMUNICATION_GROUP = "media_communication"

# HCI·UX는 대학알리미 158개 공식 소계열 어디에도 정확히 대응하는 코드가 없다
# (a/canonical-major-bridge-scope 지시서에서 이미 확인한 사실 — computer_science
# -> hci_ux Bridge 행도 이 이유로 DEPARTMENT_REVIEW_REQUIRED다). 그래서 공식
# 전공군 코드만으로는 HCI_UX_CANDIDATE를 확정할 수 없고, 학과·단과대학명의
# 명확한 HCI/UX 키워드만 "검토 후보 표시"로 쓴다 — 이것으로 확정하지 않는다
# (아래 judgment_evidence_sufficient=False로 항상 표시).
_HCI_UX_KEYWORDS = ("HCI", "UX", "UI", "인터랙션", "인터렉션")


def _judgment_candidate(row: dict[str, Any]) -> tuple[str, str, bool]:
    """(judgment_candidate, reason, evidence_sufficient)를 돌려준다.

    evidence_sufficient=True는 "이 판단이 확정됐다"는 뜻이 아니다 — 오직 "공식
    필드(candidate_canonical_major_ids, 대학알리미 공식 소계열 코드로 이미 계산된
    값)에 근거해 이 버킷으로 분류했다"는 뜻이다. reviewer_1_status는 어떤 경우에도
    TBD로 남는다(이 함수가 건드리지 않는다)."""

    groups = set(row.get("candidate_canonical_major_ids") or [])

    if _DESIGN_ARTS_GROUP in groups:
        return (
            DESIGN_ARTS_EXCLUDED,
            f"공식 소계열 분류상 전공군 후보에 '{_DESIGN_ARTS_GROUP}'(미술·디자인, 예체능 제외 "
            "정책 대상)이 포함된다 — canonical_major_group_bridge.draft.jsonl에서 이 전공군은 "
            "이미 EXCLUDED_RECOMMENDATION이다.",
            True,
        )

    hit = groups & _PERFORMING_MEDIA_ARTS_GROUPS
    if hit:
        return (
            PERFORMING_MEDIA_ARTS_EXCLUDED,
            f"공식 소계열 분류상 전공군 후보에 {sorted(hit)}(공연·영상·체육 예체능 계열, "
            "예체능 제외 정책 대상)이 포함된다.",
            True,
        )

    if _MEDIA_COMMUNICATION_GROUP in groups:
        return (
            MEDIA_COMMUNICATION_CANDIDATE,
            f"공식 소계열 분류상 전공군 후보가 '{_MEDIA_COMMUNICATION_GROUP}' 하나다 — "
            f"공식 소계열 '{row.get('official_small_series_name')}' 기준.",
            True,
        )

    text = f"{row.get('department_name') or ''} {row.get('college_name') or ''}"
    if any(k in text for k in _HCI_UX_KEYWORDS):
        return (
            HCI_UX_CANDIDATE,
            "학과·단과대학명에 HCI/UX 관련 키워드가 있어 검토 후보로 표시한다. 대학알리미 "
            "158개 공식 소계열에는 HCI·UX에 정확히 대응하는 코드가 없어(공식 계열 코드로는 "
            "확정 불가) 공식 교육과정 확인 전까지는 후보일 뿐이다.",
            False,
        )

    if not groups:
        return (
            UNMAPPED,
            "공식 소계열 분류상 대응하는 전공군 후보가 없다(candidate_canonical_major_ids 비어 있음).",
            False,
        )

    return (
        NEEDS_OFFICIAL_CURRICULUM,
        f"공식 전공군 후보는 있지만({sorted(groups)}) 콘텐츠·미디어/디자인·HCI·UX 여부를 "
        "그 후보만으로 판단할 근거가 부족하다 — 공식 교육과정·교육목표 확인이 필요하다.",
        False,
    )


def candidate_id(*parts: str) -> str:
    """결정론적 검수 행 id. 생성 시각을 쓰지 않는다 — 재생성해도 같아야 한다."""
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"p1cls_{digest}"


def build_p1_rows(queue: list[dict[str, Any]]) -> list[dict[str, Any]]:
    p1: list[dict[str, Any]] = []
    for row in queue:
        cluster_code = cluster_of(row)[0]
        if cluster_code not in P1_CLUSTER_CODES:
            continue
        judgment, reason, sufficient = _judgment_candidate(row)
        p1.append({
            "candidate_id": candidate_id(row["department_id"], row["source_record_id"]),
            "source_record_id": row["source_record_id"],
            "department_id": row["department_id"],
            "university_name": row.get("university_name"),
            "department_name": row.get("department_name"),
            "college_name": row.get("college_name"),
            "official_large_series_name": row.get("official_large_series_name"),
            "official_middle_series_name": row.get("official_middle_series_name"),
            "official_small_series_name": row.get("official_small_series_name"),
            "candidate_canonical_major_ids": row.get("candidate_canonical_major_ids") or [],
            "arts_sports_possibility": row.get("arts_sports_possibility"),
            # 이 파이프라인 단계에는 학과별 공식 교육목표 원문이 수집돼 있지 않다 — 지어내지
            # 않고 정직하게 없다고 표시한다(§4 "추측하지 말고 NEEDS_OFFICIAL_CURRICULUM으로 유지").
            "official_curriculum_summary": None,
            "official_curriculum_available": False,
            "official_evidence_needed": row.get("official_evidence_needed") or [],
            "p1_cluster": cluster_code,
            "judgment_candidate": judgment,
            "judgment_candidate_reason": reason,
            "judgment_evidence_sufficient": sufficient,
            "reviewer_1_status": "TBD",
            "resolution_status": "PENDING",
            "reviewer_comment": None,
        })
    # source_record_id 기준 정렬 — 원본 Queue의 등장 순서(비결정적일 수 있는 사전 처리 결과)에
    # 기대지 않고, 이 스크립트가 스스로 결정론적 순서를 고정한다.
    p1.sort(key=lambda r: r["source_record_id"])
    return p1


# ── HTML 검수 패킷 ────────────────────────────────────────────────────────

_CSS = """body{font-family:system-ui,-apple-system,'Malgun Gothic',sans-serif;margin:0;padding:24px;
background:#f7f7f8;color:#1a1a1a;line-height:1.6}h1{font-size:20px;margin:0 0 4px}
.sub{color:#666;font-size:13px;margin-bottom:14px}
.warn{background:#fff8e6;border-left:3px solid #e0b000;padding:10px 14px;font-size:13px;
border-radius:4px;margin-bottom:18px}
.filters{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px;position:sticky;top:0;
background:#f7f7f8;padding:10px 0;z-index:1}
.filters button{border:1px solid #d8d8dc;background:#fff;border-radius:999px;padding:6px 14px;
font-size:12.5px;cursor:pointer}
.filters button.active{background:#0b4a8f;color:#fff;border-color:#0b4a8f}
.count{color:#666;font-size:12.5px;margin-bottom:12px}
.card{background:#fff;border-radius:10px;padding:14px 16px;margin-bottom:10px;
box-shadow:0 1px 3px rgba(0,0,0,.08)}
.card.hidden{display:none}
.hd{font-weight:600;font-size:14.5px;margin-bottom:2px}
.meta{color:#666;font-size:12px;margin-bottom:8px}
.badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11.5px;font-weight:600;
margin-right:4px}
.b-media{background:#e7f2ff;color:#0b4a8f}.b-hci{background:#f0e7ff;color:#5a0b8f}
.b-design-x{background:#ffe7ea;color:#8f0b1f}.b-perf-x{background:#ffe7ea;color:#8f0b1f}
.b-needs{background:#fff0e6;color:#8f3d0b}.b-unmapped{background:#f0f0f0;color:#555}
table{border-collapse:collapse;width:100%;font-size:12px;margin:6px 0}
th,td{border:1px solid #e3e3e6;padding:4px 7px;text-align:left;vertical-align:top}
th{background:#fafafa;font-weight:600;white-space:nowrap}
.reason{background:#fafafa;border-left:3px solid #d0d0d4;padding:7px 11px;font-size:12.5px;margin:6px 0}
.pending{color:#8a6d00;font-weight:600;font-size:12px}"""

_JS = """function p1Filter(kind, value){
  document.querySelectorAll('.filters[data-kind="'+kind+'"] button').forEach(function(b){
    b.classList.toggle('active', b.dataset.value===value);
  });
  window.__p1state = window.__p1state || {cluster:'ALL', judgment:'ALL'};
  window.__p1state[kind] = value;
  var cards = document.querySelectorAll('.card');
  var shown = 0;
  cards.forEach(function(c){
    var okCluster = window.__p1state.cluster==='ALL' || c.dataset.cluster===window.__p1state.cluster;
    var okJudgment = window.__p1state.judgment==='ALL' || c.dataset.judgment===window.__p1state.judgment;
    var visible = okCluster && okJudgment;
    c.classList.toggle('hidden', !visible);
    if (visible) shown++;
  });
  document.getElementById('shown-count').textContent = shown;
}"""

_BADGE_CLASS = {
    MEDIA_COMMUNICATION_CANDIDATE: "b-media",
    HCI_UX_CANDIDATE: "b-hci",
    DESIGN_ARTS_EXCLUDED: "b-design-x",
    PERFORMING_MEDIA_ARTS_EXCLUDED: "b-perf-x",
    NEEDS_OFFICIAL_CURRICULUM: "b-needs",
    UNMAPPED: "b-unmapped",
}


def _esc(v: Any) -> str:
    return html.escape("" if v is None else str(v))


def render_html(rows: list[dict[str, Any]], survey_year: int) -> str:
    judgment_counts = Counter(r["judgment_candidate"] for r in rows)
    cluster_counts = Counter(r["p1_cluster"] for r in rows)

    cards = []
    for r in rows:
        badge_cls = _BADGE_CLASS[r["judgment_candidate"]]
        evidence_needed = "".join(f"<li>{_esc(e)}</li>" for e in r["official_evidence_needed"]) or "<li>(없음)</li>"
        cards.append(f"""<div class="card" data-cluster="{_esc(r['p1_cluster'])}" data-judgment="{_esc(r['judgment_candidate'])}">
<div class="hd">{_esc(r['university_name'])} · {_esc(r['department_name'])}</div>
<div class="meta">{_esc(r['college_name'])} · department_id <code>{_esc(r['department_id'])}</code>
 · source_record_id <code>{_esc(r['source_record_id'])}</code></div>
<table><tr><th>공식 대계열</th><th>공식 중계열</th><th>공식 소계열</th><th>공식 후보 전공군</th><th>예체능 가능성</th></tr>
<tr><td>{_esc(r['official_large_series_name'])}</td><td>{_esc(r['official_middle_series_name'])}</td>
<td>{_esc(r['official_small_series_name'])}</td><td>{_esc(', '.join(r['candidate_canonical_major_ids']) or '(없음)')}</td>
<td>{_esc(r['arts_sports_possibility'])}</td></tr></table>
<div><span class="badge {badge_cls}">{_esc(r['judgment_candidate'])}</span>
<span class="badge {'b-media' if r['judgment_evidence_sufficient'] else 'b-needs'}">
근거 {'충분' if r['judgment_evidence_sufficient'] else '부족'}</span></div>
<div class="reason">{_esc(r['judgment_candidate_reason'])}</div>
<div>공식 교육목표 요약: {_esc(r['official_curriculum_summary']) or '(이 단계에는 수집되지 않음 — 추측하지 않음)'}</div>
<div>판단에 필요한 추가 공식 자료<ul>{evidence_needed}</ul></div>
<div class="pending">reviewer_1_status: {_esc(r['reviewer_1_status'])} ·
 resolution_status: {_esc(r['resolution_status'])}</div>
</div>""")

    cluster_buttons = "".join(
        f'<button data-value="{_esc(code)}" onclick="p1Filter(\'cluster\',\'{_esc(code)}\')">'
        f"{_esc(label)} ({cluster_counts.get(code, 0)})</button>"
        for code, label in (("ALL", "전체"), ("CONTENT_MEDIA", "콘텐츠·미디어"), ("DESIGN_HCI_UX", "디자인/HCI/UX"))
    )
    judgment_buttons = "".join(
        f'<button data-value="{_esc(code)}" onclick="p1Filter(\'judgment\',\'{_esc(code)}\')">'
        f"{_esc(code)} ({judgment_counts.get(code, 0)})</button>"
        for code in (
            "ALL", MEDIA_COMMUNICATION_CANDIDATE, HCI_UX_CANDIDATE, DESIGN_ARTS_EXCLUDED,
            PERFORMING_MEDIA_ARTS_EXCLUDED, NEEDS_OFFICIAL_CURRICULUM, UNMAPPED,
        )
    )

    return f"""<meta charset="utf-8"><title>분류 REVIEW P1 검수 패킷 {survey_year}</title>
<style>{_CSS}</style>
<h1>분류 REVIEW_REQUIRED — P1(추천 노출 직접 영향) 검수 패킷</h1>
<div class="sub">조사연도 {survey_year} · 총 {len(rows)}건(콘텐츠·미디어 {cluster_counts.get('CONTENT_MEDIA', 0)} +
 디자인/HCI/UX {cluster_counts.get('DESIGN_HCI_UX', 0)}) · worker-c 분류 Queue 기반, A 검수 패킷</div>
<div class="warn"><b>judgment_candidate는 확정이 아닙니다.</b> 모든 행이
<code>reviewer_1_status: TBD</code>, <code>resolution_status: PENDING</code> 상태입니다.
학과명 문자열만으로 Canonical Major를 확정하지 마세요. 예체능을 HCI·UX나 미디어 전공으로
자동 연결하지 마세요. 공식 교육목표·교육과정 근거가 없는 행(<code>judgment_evidence_sufficient:
false</code>)은 근거가 생기기 전까지 NEEDS_OFFICIAL_CURRICULUM/HCI_UX_CANDIDATE(검토 후보)로
남습니다.</div>
<div class="filters" data-kind="cluster">{cluster_buttons}</div>
<div class="filters" data-kind="judgment">{judgment_buttons}</div>
<div class="count"><span id="shown-count">{len(rows)}</span> / {len(rows)}건 표시 중</div>
{''.join(cards)}
<script>{_JS}</script>"""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    use_utf8_stdout()
    parser = argparse.ArgumentParser(description="분류 REVIEW P1 검수 패킷 생성")
    parser.add_argument("--survey-year", type=int, default=2025)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args(argv)

    work = args.data_dir / "academyinfo_work" / str(args.survey_year)
    queue_path = work / "classification_review_queue.jsonl"
    if not queue_path.exists():
        print(f"입력이 없습니다: {queue_path}", file=sys.stderr)
        print("기존 패킷을 부분 덮어쓰지 않고 중단합니다.", file=sys.stderr)
        return 2

    queue = read_jsonl(queue_path)
    p1_rows = build_p1_rows(queue)

    packets = work / "packets"
    packets.mkdir(parents=True, exist_ok=True)

    jsonl_path = packets / "p1_classification_review.jsonl"
    jsonl_path.write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in p1_rows),
        encoding="utf-8",
    )

    html_path = packets / "p1_classification_review_packet.html"
    html_path.write_text(render_html(p1_rows, args.survey_year), encoding="utf-8")

    judgment_breakdown = dict(Counter(r["judgment_candidate"] for r in p1_rows))
    cluster_breakdown = dict(Counter(r["p1_cluster"] for r in p1_rows))
    arts_breakdown = dict(Counter(r["arts_sports_possibility"] for r in p1_rows))
    sufficient_count = sum(1 for r in p1_rows if r["judgment_evidence_sufficient"])

    manifest = {
        "survey_year": args.survey_year,
        # 생성 시각을 넣지 않는다 — 재생성 결과가 매번 달라져 Byte 비교를 못 하게 된다.
        "input_hashes": {"classification_review_queue.jsonl": sha256_file(queue_path)},
        "output_hashes": {
            jsonl_path.name: sha256_file(jsonl_path),
            html_path.name: sha256_file(html_path),
        },
        "source_queue_total": len(queue),
        "p1_total": len(p1_rows),
        "p1_cluster_breakdown": cluster_breakdown,
        "judgment_candidate_breakdown": judgment_breakdown,
        "official_evidence_sufficient_count": sufficient_count,
        "official_evidence_insufficient_count": len(p1_rows) - sufficient_count,
        "arts_sports_possibility_breakdown": arts_breakdown,
        "auto_approved_rows": 0,
        "note": (
            "auto_approved_rows가 0이라는 것이 자동 승인하지 않았다는 증명이다. 모든 행은 "
            "reviewer_1_status=TBD · resolution_status=PENDING이다. "
            "official_evidence_sufficient_count는 '자동 처리 가능한 건수'가 아니라 "
            "'공식 필드(candidate_canonical_major_ids)만으로 판단 후보를 매길 근거가 있는 건수'다 "
            "— 사람 승인 여부와 무관하다."
        ),
    }
    manifest_path = packets / "p1_classification_review_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"P1 분류 REVIEW 검수 패킷 생성 — 조사연도 {args.survey_year}")
    print(f"  총 {len(p1_rows)}건 (콘텐츠·미디어 {cluster_breakdown.get('CONTENT_MEDIA', 0)} + "
          f"디자인/HCI/UX {cluster_breakdown.get('DESIGN_HCI_UX', 0)})")
    for code, count in sorted(judgment_breakdown.items(), key=lambda kv: -kv[1]):
        print(f"    {code:<32} {count}")
    print(f"  공식 근거 충분 {sufficient_count} / 부족 {len(p1_rows) - sufficient_count} · 자동 승인 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
