/**
 * Obsidian Export — Subgraph API 결과를 Obsidian에서 열 수 있는 Markdown Vault로 바꾼다.
 *
 * 원칙:
 * - 입력은 오직 SubgraphResponse다. DB를 조회하거나 Edge를 새로 만들지 않는다.
 * - relevance_level 숫자는 문서에 쓰지 않는다(화면 원칙과 동일). 관계 성격만 남긴다.
 * - RELATED_TO는 "추론된 연관성"이라는 사실을 문서에도 남긴다 — 점선의 문서판이다.
 */
import type { SubgraphEdge, SubgraphNode, SubgraphResponse } from "@/api/contracts";
import { NODE_TYPE_LABEL, isInferredRelation } from "./layout";

const RELATION_LABEL: Record<SubgraphEdge["relation_type"], string> = {
  HAS_TRAIT: "관찰된 경향",
  RELATED_CONCEPT: "연관 개념(추론)",
  GROUPED_AS: "묶이는 영역",
  RELATED_TO: "연관성(추론)",
  HAS_DEPARTMENT: "개설 학과",
  BELONGS_TO: "소속 대학",
  RECOMMENDS: "추천 과목",
};

export interface ObsidianFile {
  /** Vault 안의 상대 경로. */
  path: string;
  content: string;
}

/** Obsidian [[링크]]와 파일명에서 문제를 일으키는 문자를 걷어낸다. */
export function toNoteName(node: SubgraphNode): string {
  const safe = node.label.replace(/[\\/:*?"<>|#^[\]]/g, " ").replace(/\s+/g, " ").trim();
  return safe || node.node_id;
}

function frontmatter(fields: Record<string, string | string[]>): string {
  const lines = ["---"];
  for (const [key, value] of Object.entries(fields)) {
    if (Array.isArray(value)) {
      if (value.length === 0) continue;
      lines.push(`${key}:`);
      for (const item of value) lines.push(`  - "${item.replace(/"/g, '\\"')}"`);
    } else {
      lines.push(`${key}: "${value.replace(/"/g, '\\"')}"`);
    }
  }
  lines.push("---", "");
  return lines.join("\n");
}

/** Node 하나당 노트 하나 + 전체 지도 노트 하나를 만든다. */
export function buildObsidianVault(subgraph: SubgraphResponse): ObsidianFile[] {
  const nameById = new Map(subgraph.nodes.map((node) => [node.node_id, toNoteName(node)]));
  const files: ObsidianFile[] = [];

  for (const node of subgraph.nodes) {
    const noteName = nameById.get(node.node_id) as string;
    const outgoing = subgraph.edges.filter((edge) => edge.source_node_id === node.node_id);
    const incoming = subgraph.edges.filter((edge) => edge.target_node_id === node.node_id);

    const body: string[] = [
      frontmatter({
        type: NODE_TYPE_LABEL[node.node_type],
        node_type: node.node_type,
        session: subgraph.session_id,
        tags: ["trail", node.node_type.toLowerCase()],
      }),
      `# ${node.label}`,
      "",
      `> ${NODE_TYPE_LABEL[node.node_type]}`,
      "",
    ];

    if (outgoing.length > 0) {
      body.push("## 여기서 이어지는 것", "");
      for (const edge of outgoing) {
        const target = nameById.get(edge.target_node_id);
        if (!target) continue;
        const suffix = isInferredRelation(edge) ? " _(추론된 연관성)_" : "";
        body.push(`- ${RELATION_LABEL[edge.relation_type]} → [[${target}]]${suffix}`);
        for (const source of edge.source_ids) body.push(`    - 근거: <${source}>`);
      }
      body.push("");
    }

    if (incoming.length > 0) {
      body.push("## 여기로 이어지는 것", "");
      for (const edge of incoming) {
        const source = nameById.get(edge.source_node_id);
        if (!source) continue;
        const suffix = isInferredRelation(edge) ? " _(추론된 연관성)_" : "";
        body.push(`- [[${source}]] → ${RELATION_LABEL[edge.relation_type]}${suffix}`);
      }
      body.push("");
    }

    files.push({ path: `${NODE_TYPE_LABEL[node.node_type]}/${noteName}.md`, content: body.join("\n") });
  }

  files.push({ path: "TRAIL 탐색 지도.md", content: buildIndexNote(subgraph, nameById) });
  return files;
}

function buildIndexNote(subgraph: SubgraphResponse, nameById: Map<string, string>): string {
  const grouped = new Map<SubgraphNode["node_type"], SubgraphNode[]>();
  for (const node of subgraph.nodes) {
    const bucket = grouped.get(node.node_type) ?? [];
    bucket.push(node);
    grouped.set(node.node_type, bucket);
  }

  const lines = [
    frontmatter({ type: "지도", session: subgraph.session_id, tags: ["trail", "index"] }),
    "# TRAIL 탐색 지도",
    "",
    "이 Vault는 TRAIL의 관계 그래프를 그대로 옮긴 것입니다.",
    "점선(추론된 연관성)으로 표시됐던 관계는 각 노트에 _(추론된 연관성)_ 으로 적혀 있습니다.",
    "",
  ];

  for (const [type, nodes] of grouped) {
    lines.push(`## ${NODE_TYPE_LABEL[type]}`, "");
    for (const node of [...nodes].sort((a, b) => a.label.localeCompare(b.label, "ko"))) {
      lines.push(`- [[${nameById.get(node.node_id) ?? node.label}]]`);
    }
    lines.push("");
  }

  return lines.join("\n");
}

/** Obsidian Canvas(.canvas) — 그래프 모양 그대로 열고 싶을 때 쓴다. */
export function buildObsidianCanvas(subgraph: SubgraphResponse, positions: Map<string, { x: number; y: number }>): string {
  const canvas = {
    nodes: subgraph.nodes.map((node) => {
      const position = positions.get(node.node_id) ?? { x: 0, y: 0 };
      return {
        id: node.node_id,
        type: "text" as const,
        text: `**${node.label}**\n${NODE_TYPE_LABEL[node.node_type]}`,
        x: Math.round(position.x * 2.4),
        y: Math.round(position.y * 2.4),
        width: 240,
        height: 90,
      };
    }),
    edges: subgraph.edges.map((edge, index) => ({
      id: `edge-${index}`,
      fromNode: edge.source_node_id,
      fromSide: "right" as const,
      toNode: edge.target_node_id,
      toSide: "left" as const,
      label: isInferredRelation(edge)
        ? `${RELATION_LABEL[edge.relation_type]}`
        : RELATION_LABEL[edge.relation_type],
    })),
  };
  return JSON.stringify(canvas, null, 2);
}

/** 파일 하나로 내려받을 수 있게 Vault 전체를 Markdown 한 장으로 합친다. */
export function buildSingleMarkdown(files: ObsidianFile[]): string {
  return files
    .map((file) => `<!-- ${file.path} -->\n\n${file.content}`)
    .join("\n\n---\n\n");
}
