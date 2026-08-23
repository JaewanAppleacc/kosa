/**
 * Obsidian Export UI — Markdown Vault(단일 파일) 또는 Canvas 파일을 내려받는다.
 */
import { useMemo, useState } from "react";
import type { SubgraphResponse } from "@/api/contracts";
import { Button, Card, SectionTitle } from "@/components/ui";
import { buildObsidianCanvas, buildObsidianVault, buildSingleMarkdown } from "./obsidianExport";
import { layoutSubgraph } from "./layout";

function download(filename: string, content: string, mimeType: string): void {
  const blob = new Blob([content], { type: `${mimeType};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function ObsidianExportPanel({ subgraph }: { subgraph: SubgraphResponse }) {
  const [preview, setPreview] = useState(false);
  const files = useMemo(() => buildObsidianVault(subgraph), [subgraph]);
  const markdown = useMemo(() => buildSingleMarkdown(files), [files]);

  const canvas = useMemo(() => {
    const layout = layoutSubgraph(subgraph.nodes);
    const positions = new Map(layout.nodes.map((node) => [node.node_id, { x: node.x, y: node.y }]));
    return buildObsidianCanvas(subgraph, positions);
  }, [subgraph]);

  if (subgraph.nodes.length === 0) return null;

  return (
    <Card>
      <SectionTitle hint="Obsidian에 넣으면 이 관계를 직접 넓혀가며 정리할 수 있어요.">
        내보내기
      </SectionTitle>

      <div className="flex flex-wrap gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => download("TRAIL 탐색 지도.md", markdown, "text/markdown")}
        >
          Markdown 내려받기
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => download("TRAIL 탐색 지도.canvas", canvas, "application/json")}
        >
          Canvas 내려받기
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setPreview((v) => !v)}
          aria-expanded={preview}
        >
          {preview ? "미리보기 닫기" : "미리보기"}
        </Button>
      </div>

      <p className="mut mt-4 text-[12px]">
        노트 {files.length}개 · Markdown 파일 하나로 합쳐서 내려받아요.
      </p>

      {preview ? (
        <pre className="mut mt-4 max-h-80 overflow-auto rounded-2xl p-4 text-[12px] leading-relaxed whitespace-pre-wrap"
          style={{ background: "var(--color-neutral-100)" }}>
          {markdown.slice(0, 4000)}
          {markdown.length > 4000 ? "\n\n… (이하 생략)" : ""}
        </pre>
      ) : null}
    </Card>
  );
}
