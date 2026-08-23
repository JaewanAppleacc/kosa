/**
 * Subgraph 배치 계산 — 서버가 준 Node·Edge를 화면 좌표로 옮기기만 한다.
 *
 * 여기서 Edge를 새로 만들거나 관계를 추론하지 않는다. 그건 KnowledgeSubgraphService의 일이다.
 */
import type { SubgraphEdge, SubgraphNode, SubgraphNodeType } from "@/api/contracts";

/** 왼쪽(학생)에서 오른쪽(구체적인 선택지)으로 흐르도록 Node 종류마다 열을 정한다. */
const COLUMN_OF: Record<SubgraphNodeType, number> = {
  Student: 0,
  Trait: 1,
  RelatedConcept: 1,
  CareerDimension: 1,
  CanonicalMajor: 2,
  Department: 3,
  HighSchoolSubject: 3,
  University: 4,
  Occupation: 4,
};

export const NODE_STYLE: Record<SubgraphNodeType, { fill: string; text: string }> = {
  Student: { fill: "oklch(0.93 0.11 95)", text: "oklch(0.35 0.08 95)" },
  Trait: { fill: "oklch(0.92 0.06 300)", text: "oklch(0.38 0.12 300)" },
  RelatedConcept: { fill: "oklch(0.94 0.005 250)", text: "oklch(0.45 0.01 250)" },
  CareerDimension: { fill: "oklch(0.93 0.05 350)", text: "oklch(0.40 0.11 350)" },
  CanonicalMajor: { fill: "oklch(0.90 0.07 250)", text: "oklch(0.38 0.15 250)" },
  Department: { fill: "oklch(0.92 0.07 155)", text: "oklch(0.36 0.10 155)" },
  University: { fill: "oklch(0.95 0.04 155)", text: "oklch(0.40 0.08 155)" },
  HighSchoolSubject: { fill: "oklch(0.93 0.07 65)", text: "oklch(0.38 0.10 65)" },
  Occupation: { fill: "oklch(0.92 0.07 25)", text: "oklch(0.38 0.12 25)" },
};

/** 화면에 보여줄 Node 종류 이름. node_type을 영어 그대로 노출하지 않는다. */
export const NODE_TYPE_LABEL: Record<SubgraphNodeType, string> = {
  Student: "나",
  Trait: "관찰된 경향",
  RelatedConcept: "연관 개념",
  CareerDimension: "영역",
  CanonicalMajor: "전공",
  Department: "학과",
  University: "대학",
  HighSchoolSubject: "과목",
  Occupation: "직업",
};

/**
 * 확정된 구조적 관계는 실선, 추론된 연관성은 점선으로 그린다.
 * (README_B 2026-08-29: RELATED_TO는 공식 근거가 있어도 "확정 관찰"이 아니다.)
 */
export function isInferredRelation(edge: SubgraphEdge): boolean {
  return edge.relation_type === "RELATED_TO" || edge.relation_type === "RELATED_CONCEPT";
}

/**
 * relevance_level(1~3)은 숫자로 표시하지 않고 선 굵기·투명도로만 쓴다.
 * 범위를 벗어난 값이 와도 화면이 깨지지 않도록 clamp한다.
 */
export function edgeEmphasis(level: number): { width: number; opacity: number } {
  const clamped = Math.min(3, Math.max(1, Math.round(level)));
  return { width: [1.2, 2, 3][clamped - 1] ?? 2, opacity: [0.4, 0.62, 0.85][clamped - 1] ?? 0.62 };
}

export interface PositionedNode extends SubgraphNode {
  x: number;
  y: number;
}

export interface GraphLayout {
  nodes: PositionedNode[];
  nodeById: Map<string, PositionedNode>;
  width: number;
  height: number;
}

const COLUMN_WIDTH = 210;
const ROW_HEIGHT = 62;
const MARGIN_X = 90;
const MARGIN_Y = 44;

/** 같은 열 안에서는 label 기준으로 정렬해 매번 같은 그림이 나오게 한다. */
export function layoutSubgraph(nodes: SubgraphNode[]): GraphLayout {
  const columns = new Map<number, SubgraphNode[]>();
  for (const node of nodes) {
    const column = COLUMN_OF[node.node_type] ?? 1;
    const bucket = columns.get(column) ?? [];
    bucket.push(node);
    columns.set(column, bucket);
  }

  const positioned: PositionedNode[] = [];
  const tallest = Math.max(1, ...[...columns.values()].map((bucket) => bucket.length));

  for (const [column, bucket] of [...columns.entries()].sort((a, b) => a[0] - b[0])) {
    const sorted = [...bucket].sort((a, b) => a.label.localeCompare(b.label, "ko"));
    // 열마다 개수가 달라도 세로 중앙에 모이도록 배치한다.
    const offset = (tallest - sorted.length) / 2;
    sorted.forEach((node, index) => {
      positioned.push({
        ...node,
        x: MARGIN_X + column * COLUMN_WIDTH,
        y: MARGIN_Y + (offset + index) * ROW_HEIGHT,
      });
    });
  }

  const maxColumn = Math.max(0, ...[...columns.keys()]);
  return {
    nodes: positioned,
    nodeById: new Map(positioned.map((node) => [node.node_id, node])),
    width: MARGIN_X * 2 + maxColumn * COLUMN_WIDTH,
    height: MARGIN_Y * 2 + tallest * ROW_HEIGHT,
  };
}
