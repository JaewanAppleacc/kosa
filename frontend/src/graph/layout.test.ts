import { describe, expect, it } from "vitest";
import type { SubgraphEdge, SubgraphNode } from "@/api/contracts";
import { edgeEmphasis, isInferredRelation, layoutSubgraph } from "./layout";

const edge = (overrides: Partial<SubgraphEdge>): SubgraphEdge => ({
  source_node_id: "a",
  target_node_id: "b",
  relation_type: "HAS_TRAIT",
  relevance_level: 2,
  evidence_ids: [],
  source_ids: [],
  mapping_version: "v1",
  created_at: "2026-08-30T00:00:00Z",
  ...overrides,
});

describe("Edge 표현 규칙", () => {
  it("RELATED_TO와 RELATED_CONCEPT만 추론된 연관성(점선)이다", () => {
    expect(isInferredRelation(edge({ relation_type: "RELATED_TO" }))).toBe(true);
    expect(isInferredRelation(edge({ relation_type: "RELATED_CONCEPT" }))).toBe(true);
    for (const relation of ["HAS_TRAIT", "HAS_DEPARTMENT", "BELONGS_TO", "RECOMMENDS"] as const) {
      expect(isInferredRelation(edge({ relation_type: relation }))).toBe(false);
    }
  });

  it("relevance_level이 높을수록 굵고 진하다", () => {
    expect(edgeEmphasis(1).width).toBeLessThan(edgeEmphasis(3).width);
    expect(edgeEmphasis(1).opacity).toBeLessThan(edgeEmphasis(3).opacity);
  });

  it("범위를 벗어난 relevance_level에도 화면이 깨지지 않는다", () => {
    for (const level of [0, -3, 99, 2.4]) {
      const { width, opacity } = edgeEmphasis(level);
      expect(Number.isFinite(width)).toBe(true);
      expect(opacity).toBeGreaterThan(0);
    }
  });
});

describe("배치", () => {
  const node = (id: string, type: SubgraphNode["node_type"], label: string): SubgraphNode => ({
    node_id: id,
    node_type: type,
    label,
  });

  it("Student → Trait → 전공 → 학과 순으로 오른쪽에 놓인다", () => {
    const layout = layoutSubgraph([
      node("s", "Student", "학생"),
      node("t", "Trait", "원인 분석"),
      node("m", "CanonicalMajor", "산업공학"),
      node("d", "Department", "산업경영공학과"),
    ]);
    const x = (id: string) => layout.nodeById.get(id)?.x ?? 0;
    expect(x("s")).toBeLessThan(x("t"));
    expect(x("t")).toBeLessThan(x("m"));
    expect(x("m")).toBeLessThan(x("d"));
  });

  it("Node가 없어도 계산이 성립한다", () => {
    const layout = layoutSubgraph([]);
    expect(layout.nodes).toHaveLength(0);
    expect(layout.height).toBeGreaterThan(0);
  });
});
