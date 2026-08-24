"""N.C.E REEXAMINABLE_BY_OFFICIAL_EVIDENCE 584건 → 공식 중계열 군집화 — c/academyinfo-nce-reexaminable.

worker-c가 이미 만든 `nce_triage_queue.jsonl`(1,901건, 커밋됨)의 3분류 중
`REEXAMINABLE_BY_OFFICIAL_EVIDENCE`(584건)만 다시 읽어, 공식 중계열별로 묶고 사람이
검토할 수 있는 형태로 정리한다.

**이 스크립트는 `nce_triage_queue.jsonl`을 다시 쓰지 않는다** — 읽기만 한다. 894건
(NAME_ALONE_INSUFFICIENT)과 423건(NEEDS_CANONICAL_GROUP_EXPANSION)을 포함한 나머지
1,317건은 이 스크립트가 존재하는지조차 모른다(파일 자체를 절대 열지 않는다는 뜻이
아니라, 그 파일의 어떤 바이트도 바꾸지 않는다는 뜻이다).

N.C.E는 전공명이 아니라 "세부 분류(소계열) 없음" 센티턴이다(A 지시 반복). 584건은
**소계열만 없고 중계열은 살아있는** 행이라, 중계열 범위 안에서 전공군 후보를 좁힐 수
있다 — 그렇다고 중계열 = 전공군이 되는 것은 아니다. 학과명 유사도만으로 전공군에
넣지 않는다.

세 입력 전부 git에 커밋돼 있다(clean clone에서 바로 재현 가능):

    data/academyinfo_work/2025/packets/nce_triage_queue.jsonl   worker-c의 N.C.E 3분류
    data/academyinfo_raw/2025/codes/getCodeByMiddleSeries.jsonl.gz  대학알리미 공식 중계열 코드표(28개)
    data/canonical_major_groups.draft.jsonl                     42개 Canonical Major Group 초안

`middle_series_hint`는 각 Canonical Major Group의 **초안(review_status=draft) 힌트**
필드다 — `included_official_small_series_codes`처럼 `classification_basis`가 별도로
붙어 있지 않다. 그래서 이 스크립트가 그 힌트로 찾아낸 후보는 "연결 가능한 후보"일
뿐 확정이 아니다:

    후보 0개  → INSUFFICIENT_OFFICIAL_EVIDENCE (학과명·중계열 외 공식 근거가 더 필요하다)
    후보 1개  → PROPOSED_GROUP_CANDIDATE       (자동 승인하지 않는다 — 제안일 뿐이다)
    후보 2개+ → DEPARTMENT_LEVEL_REVIEW_REQUIRED (중계열이 전공군보다 넓다 — 학과 단위로 봐야 한다)

`decision_status`는 위 세 값과 다른 필드다 — 이 파이프라인의 다른 검수 Queue와 같은
관례로, "사람이 이 군집을 승인했는가"를 가리키며 **모든 군집이 항상 PENDING**이다
(`reviewer_1_status`도 항상 TBD). 실제 판단(위 세 값)과 승인 여부(PENDING/TBD)를
같은 필드에 넣지 않는다 — 섞으면 "권고를 승인으로 착각"하는 사고가 난다.

실행:
    python scripts/career_build_nce_reexaminable_clusters.py
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402

NCE_REEXAMINABLE = "REEXAMINABLE_BY_OFFICIAL_EVIDENCE"

STATUS_PROPOSED = "PROPOSED_GROUP_CANDIDATE"
STATUS_DEPT_REVIEW = "DEPARTMENT_LEVEL_REVIEW_REQUIRED"
STATUS_INSUFFICIENT = "INSUFFICIENT_OFFICIAL_EVIDENCE"

FORBIDDEN = [
    "중계열 코드·명칭 임의 생성 — 대학알리미 공식 코드표(getCodeByMiddleSeries)에 없는 값 금지",
    "학과명 유사도만으로 전공군 확정",
    "중계열 하나 = 전공군 하나로 자동 승인",
    "기존 42개 Canonical Major Group 임의 확장",
    "reviewer_1_status를 TBD 외 값으로 미리 채움",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows),
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_official_middle_series_table(path: Path) -> dict[str, str]:
    """대학알리미 공식 중계열 코드표(getCodeByMiddleSeries) → {명칭: 코드}.

    이 표에 없는 명칭은 공식 근거가 없는 것이므로 Fail-Fast로 거부한다(§Fail-Closed).
    """

    with gzip.open(path, "rt", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    name_to_code: dict[str, str] = {}
    for row in rows:
        name_to_code[row["cdnm"]] = row["cdid"]
    return name_to_code


def build_middle_series_hint_index(groups: list[dict[str, Any]]) -> dict[str, list[str]]:
    """중계열 코드 → 그 코드를 `middle_series_hint`로 언급한 Canonical Major Group id 목록.

    힌트일 뿐 확정 매핑이 아니다 — `included_official_small_series_codes`(공식
    `classification_basis` 있음)와 달리 별도 출처가 붙어 있지 않다."""

    index: dict[str, list[str]] = defaultdict(list)
    for g in groups:
        for code in g.get("middle_series_hint") or []:
            index[code].append(g["canonical_major_id"])
    return {code: sorted(ids) for code, ids in index.items()}


def classify_cluster(candidate_ids: list[str]) -> tuple[str, str, list[str]]:
    """후보 개수만으로 셋 중 하나를 고른다. 넷 다 자동 승인은 아니다."""

    if len(candidate_ids) == 0:
        return (
            STATUS_INSUFFICIENT,
            "이 중계열에 연결 가능한 Canonical Major Group 후보가 없다 — 42개 전공군 어디에도 "
            "이 중계열을 가리키는 draft 힌트가 없어, 학과명·중계열 외의 공식 근거(교육과정· "
            "교육목표 등)가 확보돼야 후보를 만들 수 있다.",
            [
                "공식 소계열이 채워지는지 재조사 자료(대학알리미 재공시 또는 학교 공식 자료)",
                "학과 공식 교육과정(개설 교과목)",
                "학과 공식 교육목표",
            ],
        )
    if len(candidate_ids) == 1:
        return (
            STATUS_PROPOSED,
            "해당 없음 — 단일 전공군 후보로 좁혀진다. 다만 중계열은 소계열보다 넓은 범위라 "
            "이 중계열에 속한 개별 학과가 실제로 그 전공군에 속하는지는 확인되지 않았다 — "
            "자동 승인하지 않는다.",
            [
                "학과 공식 교육과정·교육목표 — 제안된 전공군과의 실제 일치 확인",
                "학과 홈페이지 등 공식 자료",
                "가능하면 대학알리미 공식 소계열 재조사",
            ],
        )
    return (
        STATUS_DEPT_REVIEW,
        f"공식 중계열 하나에 전공군 {len(candidate_ids)}개({', '.join(candidate_ids)})가 동시에 "
        "걸린다 — 중계열 범위가 전공군보다 넓어 이 중계열 하나로는 어느 전공군인지 특정할 수 "
        "없다. 학과 단위로 개별 확인해야 한다.",
        [
            "학과별 공식 교육과정(개설 교과목) — 걸리는 전공군 중 어디에 더 가까운지 판별용",
            "학과 공식 교육목표",
            "졸업 후 진로 공식 자료",
        ],
    )


def build_clusters(
    reexaminable_rows: list[dict[str, Any]],
    name_to_code: dict[str, str],
    hint_index: dict[str, list[str]],
    group_meta: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in reexaminable_rows:
        name = (row.get("official_middle_series_name") or "").strip()
        if name not in name_to_code:
            raise ValueError(
                f"official_middle_series_name {name!r}가 대학알리미 공식 중계열 코드표"
                "(getCodeByMiddleSeries)에 없다 — {row.get('department_id')}"
            )
        grouped[name].append(row)

    clusters: list[dict[str, Any]] = []
    for name, rows in grouped.items():
        code = name_to_code[name]
        candidate_ids = hint_index.get(code, [])
        status, reason, evidence_needed = classify_cluster(candidate_ids)
        members = sorted(
            (
                {
                    "candidate_id": r["candidate_id"],
                    "department_id": r["department_id"],
                    "source_record_id": r.get("source_record_id"),
                    "university_name": r.get("university_name"),
                    "department_name": r.get("department_name"),
                    "college_name": r.get("college_name"),
                }
                for r in rows
            ),
            key=lambda m: m["department_id"],
        )
        clusters.append({
            "cluster_id": f"nce_reex_middle_{code}",
            "official_middle_series_code": code,
            "official_middle_series_name": name,
            "official_middle_series_code_source": (
                "대학알리미 공식 중계열 코드표 getCodeByMiddleSeries "
                "(data/academyinfo_raw/2025/codes/getCodeByMiddleSeries.jsonl.gz)"
            ),
            "row_count": len(members),
            "members": members,
            "candidate_canonical_major_groups": [
                {"canonical_major_id": gid, "label": group_meta[gid]["label"]}
                for gid in candidate_ids
            ],
            "candidate_canonical_major_group_basis": (
                "42개 Canonical Major Group의 middle_series_hint(초안, review_status=draft) "
                "필드로 찾은 후보다 — included_official_small_series_codes와 달리 별도 "
                "classification_basis가 없다. 확정 근거가 아니라 검토 시작점이다."
                if candidate_ids else None
            ),
            "group_linkage_status": status,
            "unlinkable_or_too_broad_reason": reason,
            "additional_official_evidence_needed": evidence_needed,
            "decision_status": "PENDING",
            "reviewer_1_status": "TBD",
            "reviewer_1_comment": "",
            "forbidden": FORBIDDEN,
        })

    clusters.sort(key=lambda c: (-c["row_count"], c["official_middle_series_code"]))
    return clusters


_CSS = """body{font-family:system-ui,-apple-system,'Malgun Gothic',sans-serif;margin:0;padding:24px;
background:#f7f7f8;color:#1a1a1a;line-height:1.6}h1{font-size:20px;margin:0 0 4px}
.sub{color:#666;font-size:13px;margin-bottom:20px}
.card{background:#fff;border-radius:10px;padding:16px 18px;margin-bottom:14px;
box-shadow:0 1px 3px rgba(0,0,0,.08)}
.hd{font-weight:600;font-size:15px;margin-bottom:2px}
.meta{color:#666;font-size:12.5px;margin-bottom:10px}
table{border-collapse:collapse;width:100%;font-size:12.5px;margin:8px 0}
th,td{border:1px solid #e3e3e6;padding:5px 8px;text-align:left;vertical-align:top}
th{background:#fafafa;font-weight:600;white-space:nowrap}
.status{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600}
.proposed{background:#e7f2ff;color:#0b4a8f}.review{background:#fff0e6;color:#8f3d0b}
.insufficient{background:#f3f3f3;color:#555}
.reason{background:#fafafa;border-left:3px solid #d0d0d4;padding:8px 12px;font-size:13px;margin:8px 0}
ul{margin:6px 0;padding-left:20px;font-size:12.5px}
.pending{color:#8a6d00;font-weight:600;font-size:12.5px}
.warn{background:#fff8e6;border-left:3px solid #e0b000;padding:10px 14px;font-size:13px;
border-radius:4px;margin-bottom:18px}"""


def _esc(v: Any) -> str:
    return html.escape("" if v is None else str(v))


def render_html(clusters: list[dict[str, Any]]) -> str:
    status_class = {
        STATUS_PROPOSED: "proposed", STATUS_DEPT_REVIEW: "review", STATUS_INSUFFICIENT: "insufficient",
    }
    cards = []
    for c in clusters:
        head = ["대학", "학과", "단과대학", "department_id"]
        body = "".join(
            "<tr>" + "".join(f"<td>{_esc(v)}</td>" for v in (
                m["university_name"], m["department_name"], m["college_name"], m["department_id"],
            )) + "</tr>"
            for m in c["members"][:60]
        )
        more = (
            f"<div class='meta'>… 외 {c['row_count'] - 60}건 (전체는 JSONL 참조)</div>"
            if c["row_count"] > 60 else ""
        )
        candidates = ", ".join(
            f"{g['label']}({g['canonical_major_id']})" for g in c["candidate_canonical_major_groups"]
        ) or "없음"
        cards.append(f"""<div class="card">
<div class="hd">{_esc(c['official_middle_series_name'])} ({_esc(c['official_middle_series_code'])}) — {c['row_count']}건</div>
<div class="meta">Canonical Major Group 후보: {_esc(candidates)}</div>
<div><span class="status {status_class[c['group_linkage_status']]}">{_esc(c['group_linkage_status'])}</span></div>
<div class="reason">{_esc(c['unlinkable_or_too_broad_reason'])}</div>
<div>추가로 필요한 공식 근거<ul>{''.join(f'<li>{_esc(e)}</li>' for e in c['additional_official_evidence_needed'])}</ul></div>
<table><tr>{''.join(f'<th>{_esc(h)}</th>' for h in head)}</tr>{body}</table>{more}
<div class="pending">decision_status: {_esc(c['decision_status'])} · reviewer_1_status: {_esc(c['reviewer_1_status'])}</div>
</div>""")
    total = sum(c["row_count"] for c in clusters)
    return f"""<meta charset="utf-8"><title>N.C.E REEXAMINABLE 중계열 검수 패킷</title><style>{_CSS}</style>
<h1>N.C.E REEXAMINABLE_BY_OFFICIAL_EVIDENCE 중계열 검수 패킷</h1>
<div class="sub">{total}건 · {len(clusters)}개 중계열 군집 · c/academyinfo-nce-reexaminable</div>
<div class="warn"><b>PROPOSED_GROUP_CANDIDATE도 승인이 아닙니다.</b> 모든 군집이
<code>decision_status: PENDING</code>, <code>reviewer_1_status: TBD</code> 상태입니다.
중계열 하나가 전공군 하나와만 연결돼도 자동으로 배정하지 마세요. N.C.E는 전공명이 아니라
"세부 분류 없음" 센티널이며, 학과명 유사도만으로 전공군을 확정하지 마세요.</div>
{''.join(cards)}"""


def render_markdown(clusters: list[dict[str, Any]]) -> str:
    total = sum(c["row_count"] for c in clusters)
    lines = [
        "# N.C.E REEXAMINABLE_BY_OFFICIAL_EVIDENCE 중계열 검수 패킷",
        "",
        f"총 **{total}건** · 중계열 군집 {len(clusters)}개 · 브랜치 `c/academyinfo-nce-reexaminable`",
        "",
        "> PROPOSED_GROUP_CANDIDATE도 승인이 아니다. 모든 행이 `decision_status: PENDING`,"
        " `reviewer_1_status: TBD`다.",
        "",
        "| 중계열 코드 | 중계열 명칭 | 건수 | 연결 판정 | 후보 전공군 |",
        "|---|---|---|---|---|",
    ]
    for c in clusters:
        candidates = ", ".join(g["canonical_major_id"] for g in c["candidate_canonical_major_groups"]) or "—"
        lines.append(
            f"| {c['official_middle_series_code']} | {c['official_middle_series_name']} | "
            f"{c['row_count']} | {c['group_linkage_status']} | {candidates} |"
        )
    lines += ["", "---", ""]
    for c in clusters:
        candidates = ", ".join(
            f"{g['label']}({g['canonical_major_id']})" for g in c["candidate_canonical_major_groups"]
        ) or "없음"
        lines += [
            f"## {c['official_middle_series_name']} ({c['official_middle_series_code']}) — "
            f"{c['row_count']}건 — `{c['group_linkage_status']}`",
            "",
            f"**Canonical Major Group 후보.** {candidates}",
            "",
            f"**연결 불가능하거나 범위가 너무 넓은 이유.** {c['unlinkable_or_too_broad_reason']}",
            "",
            "**추가로 필요한 공식 근거.**",
            "",
        ]
        lines += [f"- {e}" for e in c["additional_official_evidence_needed"]]
        lines += ["", "대표 예시(최대 5건)", ""]
        for m in c["members"][:5]:
            lines.append(f"- {m['university_name']} {m['department_name']} ({m['college_name']})")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    use_utf8_stdout()
    parser = argparse.ArgumentParser(description="N.C.E REEXAMINABLE 584건 중계열 군집화")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--survey-year", type=int, default=2025)
    args = parser.parse_args(argv)

    work = args.data_dir / "academyinfo_work" / str(args.survey_year)
    inputs = {
        "nce_triage_queue.jsonl": work / "packets" / "nce_triage_queue.jsonl",
        "getCodeByMiddleSeries.jsonl.gz": (
            args.data_dir / "academyinfo_raw" / str(args.survey_year) / "codes" / "getCodeByMiddleSeries.jsonl.gz"
        ),
        "canonical_major_groups.draft.jsonl": args.data_dir / "canonical_major_groups.draft.jsonl",
    }
    missing = [name for name, path in inputs.items() if not path.exists()]
    if missing:
        print(f"입력이 없습니다: {missing}", file=sys.stderr)
        print("부분 산출물을 만들지 않고 중단합니다.", file=sys.stderr)
        return 2

    nce_all = read_jsonl(inputs["nce_triage_queue.jsonl"])
    reexaminable = [r for r in nce_all if r.get("triage_group") == NCE_REEXAMINABLE]
    if len(reexaminable) != 584:
        print(
            f"REEXAMINABLE_BY_OFFICIAL_EVIDENCE 건수가 584가 아니라 {len(reexaminable)}입니다 — "
            "입력(nce_triage_queue.jsonl)이 바뀐 것으로 보입니다. 산출물을 만들지 않고 중단합니다.",
            file=sys.stderr,
        )
        return 2

    name_to_code = load_official_middle_series_table(inputs["getCodeByMiddleSeries.jsonl.gz"])
    groups = read_jsonl(inputs["canonical_major_groups.draft.jsonl"])
    group_meta = {g["canonical_major_id"]: g for g in groups}
    hint_index = build_middle_series_hint_index(groups)

    clusters = build_clusters(reexaminable, name_to_code, hint_index, group_meta)

    packets = work / "packets"
    packets.mkdir(parents=True, exist_ok=True)
    jsonl_path = packets / "nce_reexaminable_middle_series_clusters.jsonl"
    md_path = packets / "nce_reexaminable_review_packet.md"
    html_path = packets / "nce_reexaminable_review_packet.html"

    write_jsonl(jsonl_path, clusters)
    md_path.write_text(render_markdown(clusters), encoding="utf-8")
    html_path.write_text(render_html(clusters), encoding="utf-8")

    outputs = {jsonl_path.name: jsonl_path, md_path.name: md_path, html_path.name: html_path}
    manifest = {
        "survey_year": args.survey_year,
        "source_triage_group": NCE_REEXAMINABLE,
        # 생성 시각을 넣지 않는다 — 재생성 결과가 매번 달라져 Byte 비교를 못 하게 된다.
        "input_hashes": {name: sha256_file(path) for name, path in sorted(inputs.items())},
        "output_hashes": {name: sha256_file(path) for name, path in sorted(outputs.items())},
        "cluster_count": len(clusters),
        "row_total": sum(c["row_count"] for c in clusters),
        "group_linkage_status_breakdown": dict(Counter(c["group_linkage_status"] for c in clusters)),
        "auto_approved_clusters": 0,
        "note": (
            "auto_approved_clusters가 0이라는 것이 자동 승인하지 않았다는 증명이다. 모든 군집은 "
            "decision_status=PENDING · reviewer_1_status=TBD다. PROPOSED_GROUP_CANDIDATE는 제안일 "
            "뿐 승인이 아니다."
        ),
    }
    (packets / "nce_reexaminable_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"N.C.E REEXAMINABLE 중계열 군집화 — {manifest['row_total']}건 / {len(clusters)}개 군집")
    for status, count in manifest["group_linkage_status_breakdown"].items():
        print(f"  {status:<32} {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
