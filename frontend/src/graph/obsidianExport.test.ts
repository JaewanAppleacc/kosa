import { describe, expect, it } from "vitest";
import type { SubgraphResponse } from "@/api/contracts";
import { buildObsidianCanvas, buildObsidianVault, buildSingleMarkdown, toNoteName } from "./obsidianExport";
import { layoutSubgraph } from "./layout";
import subgraphFixture from "@mock/subgraph_normal.json";

const subgraph = subgraphFixture as SubgraphResponse;

describe("Obsidian Export", () => {
  it("Node마다 노트 하나와 지도 노트 하나를 만든다", () => {
    const files = buildObsidianVault(subgraph);
    expect(files).toHaveLength(subgraph.nodes.length + 1);
    expect(files.at(-1)?.path).toBe("TRAIL 탐색 지도.md");
  });

  it("추론된 연관성(RELATED_TO)을 문서에도 표시한다", () => {
    const markdown = buildSingleMarkdown(buildObsidianVault(subgraph));
    expect(markdown).toContain("_(추론된 연관성)_");
  });

  it("relevance_level 숫자를 문서에 쓰지 않는다", () => {
    const markdown = buildSingleMarkdown(buildObsidianVault(subgraph));
    expect(markdown).not.toMatch(/relevance[_ ]?level/i);
  });

  it("공식 근거 URL은 남긴다", () => {
    const withSource = subgraph.edges.find((edge) => edge.source_ids.length > 0);
    if (!withSource) return;
    const markdown = buildSingleMarkdown(buildObsidianVault(subgraph));
    expect(markdown).toContain(withSource.source_ids[0] as string);
  });

  it("Obsidian 링크에서 문제가 되는 문자를 걷어낸다", () => {
    const name = toNoteName({ node_id: "x", node_type: "Trait", label: "a/b:c#d[e]" });
    expect(name).not.toMatch(/[\\/:#[\]]/);
  });

  it("Canvas는 모든 Node·Edge를 담고 JSON으로 파싱된다", () => {
    const layout = layoutSubgraph(subgraph.nodes);
    const positions = new Map(layout.nodes.map((n) => [n.node_id, { x: n.x, y: n.y }]));
    const parsed = JSON.parse(buildObsidianCanvas(subgraph, positions));
    expect(parsed.nodes).toHaveLength(subgraph.nodes.length);
    expect(parsed.edges).toHaveLength(subgraph.edges.length);
  });
});
