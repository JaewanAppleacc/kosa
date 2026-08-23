/**
 * "어디에서 나타났나요" 지도 — Career Dimension × Context 격자.
 *
 * 이 화면이 보여주는 건 **관찰된 답변의 개수**뿐이다. 점수가 아니다.
 *
 * · 점 하나 = 그 영역으로 분류된 답변 하나. 서버가 준
 *   `detailed_evidence_by_dimension`의 항목을 그대로 센 값이다.
 * · 그래서 색 농도(Heatmap)나 막대 길이를 쓰지 않는다 — 그렇게 그리면 "많다"가
 *   "잘한다/강하다"로 읽히는데, 그건 계약에 없는 해석이다.
 * · 칸을 누르면 그 칸에 실제로 들어간 답변 설명을 그대로 펼친다. 요약하지 않는다.
 */
import { useMemo, useState } from "react";
import type { CareerProfile } from "@/api/contracts";
import { contextEmoji } from "@/domain/contextEmoji";

type Evidence = CareerProfile["detailed_evidence_by_dimension"][string][number];

interface Cell {
  contextId: string;
  items: Evidence[];
}

export function TraitMap({
  evidenceByDimension,
  labelOf,
}: {
  evidenceByDimension: CareerProfile["detailed_evidence_by_dimension"];
  /** context_id를 사람이 읽는 이름으로. 목록을 못 받았으면 id를 그대로 돌려준다. */
  labelOf: (contextId: string) => string;
}) {
  const [openCell, setOpenCell] = useState<{ dimension: string; contextId: string } | null>(null);

  const dimensions = useMemo(() => Object.keys(evidenceByDimension), [evidenceByDimension]);

  // 열 순서는 답변에 처음 나타난 순서를 따른다 — 임의로 재정렬하지 않는다.
  const contextIds = useMemo(() => {
    const seen: string[] = [];
    for (const items of Object.values(evidenceByDimension)) {
      for (const item of items) {
        if (!seen.includes(item.context_id)) seen.push(item.context_id);
      }
    }
    return seen;
  }, [evidenceByDimension]);

  const grid = useMemo(() => {
    const map = new Map<string, Cell[]>();
    for (const [dimension, items] of Object.entries(evidenceByDimension)) {
      map.set(
        dimension,
        contextIds.map((contextId) => ({
          contextId,
          items: items.filter((item) => item.context_id === contextId),
        })),
      );
    }
    return map;
  }, [evidenceByDimension, contextIds]);

  if (dimensions.length === 0 || contextIds.length === 0) return null;

  const opened =
    openCell === null
      ? null
      : (grid.get(openCell.dimension) ?? []).find((cell) => cell.contextId === openCell.contextId);

  return (
    <div>
      <div className="tmap-scroll">
        <table className="tmap">
          <caption className="sr-only">
            영역별로, 어떤 이야기에서 몇 개의 답변이 나타났는지 보여주는 표
          </caption>
          <thead>
            <tr>
              <th scope="col" className="tmap-corner">
                <span className="sr-only">영역</span>
              </th>
              {contextIds.map((contextId) => (
                <th key={contextId} scope="col">
                  <span aria-hidden="true" className="block text-[19px] leading-none">
                    {contextEmoji(contextId)}
                  </span>
                  <span className="mt-1.5 block">{labelOf(contextId)}</span>
                </th>
              ))}
              <th scope="col" className="tmap-sum">
                나타난
                <br />
                이야기
              </th>
            </tr>
          </thead>
          <tbody>
            {dimensions.map((dimension) => (
              <tr key={dimension}>
                <th scope="row">{dimension}</th>
                {(grid.get(dimension) ?? []).map((cell) => {
                  const count = cell.items.length;
                  const isOpen =
                    openCell?.dimension === dimension && openCell.contextId === cell.contextId;
                  return (
                    <td key={cell.contextId}>
                      <button
                        type="button"
                        className={`tcell${count === 0 ? " none" : ""}${isOpen ? " on" : ""}`}
                        disabled={count === 0}
                        aria-pressed={isOpen}
                        aria-label={`${dimension} · ${labelOf(cell.contextId)} · 답변 ${count}개`}
                        onClick={() =>
                          setOpenCell(isOpen ? null : { dimension, contextId: cell.contextId })
                        }
                      >
                        {count === 0 ? (
                          <span className="tdash" aria-hidden="true" />
                        ) : (
                          Array.from({ length: count }, (_, index) => (
                            <i
                              key={index}
                              aria-hidden="true"
                              style={{ animationDelay: `${index * 60}ms` }}
                            />
                          ))
                        )}
                      </button>
                    </td>
                  );
                })}
                <td className="tmap-sum">
                  <span className="tspread">
                    {(grid.get(dimension) ?? []).filter((cell) => cell.items.length > 0).length}
                    <span className="tspread-unit">/{contextIds.length}</span>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mut mt-3 text-[12.5px] leading-relaxed">
        점 하나가 그렇게 답한 문항 하나예요. 점이 많다고 더 잘한다는 뜻은 아니고, 여러 이야기에
        걸쳐 나타났는지를 보는 표예요.
      </p>

      {opened !== undefined && opened !== null && openCell !== null ? (
        <div className="tdetail reveal">
          <p className="gsec mb-2">
            {openCell.dimension} · {labelOf(openCell.contextId)}
          </p>
          <ul className="flex flex-col gap-1.5">
            {opened.items.map((item, index) => (
              <li key={index} className="text-[14px] leading-relaxed">
                · {item.description}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
