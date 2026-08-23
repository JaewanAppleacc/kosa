/**
 * 관계 그래프 화면 — 서버가 준 Node·Edge만 그린다.
 *
 * 지켜야 할 것:
 * - relevance_level은 숫자로 표시하지 않고 선 굵기·투명도로만 쓴다.
 * - RELATED_TO는 점선(추론된 연관성), 나머지는 실선(확정된 구조적 관계).
 * - 과목 Node가 없는 부분 그래프는 오류가 아니라 정상 상태다.
 */
import { useMemo, useState } from "react";
import { fetchSubgraph } from "@/api/endpoints";
import type { SubgraphResponse } from "@/api/contracts";
import { ErrorView } from "@/components/ErrorView";
import { Badge, Button, Card, SectionTitle, Spinner } from "@/components/ui";
import { useAsync } from "@/hooks/useAsync";
import { useAppState } from "@/session/AppState";
import { NODE_STYLE, NODE_TYPE_LABEL, edgeEmphasis, isInferredRelation, layoutSubgraph } from "./layout";
import { ObsidianExportPanel } from "./ObsidianExportPanel";

export function SubgraphView() {
  const { state } = useAppState();
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const subgraph = useAsync(
    (signal) => {
      if (!state.sessionId) return Promise.reject(new Error("세션이 없습니다."));
      return fetchSubgraph(state.sessionId, signal);
    },
    [state.sessionId],
  );

  if (subgraph.status === "loading" || subgraph.status === "idle") {
    return (
      <div className="py-16 text-center">
        <Spinner label="관계를 그리는 중" />
      </div>
    );
  }
  if (subgraph.status === "error") return <ErrorView error={subgraph.error} onRetry={subgraph.reload} />;

  return (
    <div className="space-y-5">
      <SectionTitle hint="답변에서 관찰된 경향이 전공·학과·과목으로 어떻게 이어지는지 보여줘요.">
        관계 그래프
      </SectionTitle>

      <GraphCanvas
        subgraph={subgraph.data}
        selectedNodeId={selectedNodeId}
        onSelectNode={setSelectedNodeId}
      />

      <Legend />

      <EvidencePanel
        subgraph={subgraph.data}
        selectedNodeId={selectedNodeId}
        onClose={() => setSelectedNodeId(null)}
      />

      {subgraph.data.nodes.every((node) => node.node_type !== "HighSchoolSubject") ? (
        <p className="mut rounded-2xl px-5 py-4 text-[13.5px]" style={{ background: "var(--color-neutral-100)" }}>
          학교 편제표를 올리고 과목을 확정하면 과목까지 이어진 그래프를 볼 수 있어요.
        </p>
      ) : null}

      <ObsidianExportPanel subgraph={subgraph.data} />
    </div>
  );
}

function GraphCanvas({
  subgraph,
  selectedNodeId,
  onSelectNode,
}: {
  subgraph: SubgraphResponse;
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string | null) => void;
}) {
  const layout = useMemo(() => layoutSubgraph(subgraph.nodes), [subgraph.nodes]);

  const connectedNodeIds = useMemo(() => {
    if (!selectedNodeId) return null;
    const ids = new Set<string>([selectedNodeId]);
    for (const edge of subgraph.edges) {
      if (edge.source_node_id === selectedNodeId) ids.add(edge.target_node_id);
      if (edge.target_node_id === selectedNodeId) ids.add(edge.source_node_id);
    }
    return ids;
  }, [selectedNodeId, subgraph.edges]);

  if (subgraph.nodes.length === 0) {
    return (
      <Card>
        <p className="mut py-8 text-center text-[14px]">아직 그릴 관계가 없어요.</p>
      </Card>
    );
  }

  return (
    // 넓은 그래프는 페이지가 아니라 이 상자 안에서만 가로로 스크롤한다.
    <div className="overflow-x-auto rounded-[20px] bg-white" style={{ boxShadow: "inset 0 0 0 1.5px var(--line)" }}>
      <svg
        viewBox={`0 0 ${layout.width} ${layout.height}`}
        width={layout.width}
        height={layout.height}
        role="img"
        aria-label="답변에서 관찰된 경향과 전공·학과·과목의 관계 그래프"
        className="min-w-full"
      >
        <g>
          {subgraph.edges.map((edge, index) => {
            const from = layout.nodeById.get(edge.source_node_id);
            const to = layout.nodeById.get(edge.target_node_id);
            if (!from || !to) return null;

            const { width, opacity } = edgeEmphasis(edge.relevance_level);
            const dimmed =
              connectedNodeIds !== null &&
              !(connectedNodeIds.has(edge.source_node_id) && connectedNodeIds.has(edge.target_node_id));
            const midX = (from.x + to.x) / 2;

            return (
              <path
                key={`${edge.source_node_id}-${edge.target_node_id}-${index}`}
                d={`M ${from.x + 62} ${from.y} C ${midX} ${from.y}, ${midX} ${to.y}, ${to.x - 62} ${to.y}`}
                stroke="var(--color-neutral-500)"
                strokeWidth={width}
                strokeOpacity={dimmed ? 0.08 : opacity}
                // 추론된 연관성은 점선 — 확정 관찰과 시각적으로 구분한다.
                strokeDasharray={isInferredRelation(edge) ? "5 5" : undefined}
                fill="none"
              />
            );
          })}
        </g>

        <g>
          {layout.nodes.map((node) => {
            const style = NODE_STYLE[node.node_type];
            const dimmed = connectedNodeIds !== null && !connectedNodeIds.has(node.node_id);
            const isSelected = node.node_id === selectedNodeId;
            return (
              <g
                key={node.node_id}
                transform={`translate(${node.x}, ${node.y})`}
                opacity={dimmed ? 0.25 : 1}
                className="cursor-pointer"
                onClick={() => onSelectNode(isSelected ? null : node.node_id)}
              >
                <rect
                  x={-62}
                  y={-19}
                  width={124}
                  height={38}
                  rx={12}
                  fill={style.fill}
                  stroke={isSelected ? "var(--accent)" : "transparent"}
                  strokeWidth={2}
                />
                <text
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize={13}
                  fontWeight={600}
                  fill={style.text}
                >
                  {node.label.length > 9 ? `${node.label.slice(0, 8)}…` : node.label}
                </text>
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
}

function Legend() {
  return (
    <div className="mut flex flex-wrap items-center gap-4 text-[12px]">
      <span className="inline-flex items-center gap-2">
        <svg width="28" height="8" aria-hidden="true">
          <line x1="0" y1="4" x2="28" y2="4" stroke="var(--color-neutral-500)" strokeWidth="2.5" />
        </svg>
        확인된 관계
      </span>
      <span className="inline-flex items-center gap-2">
        <svg width="28" height="8" aria-hidden="true">
          <line
            x1="0"
            y1="4"
            x2="28"
            y2="4"
            stroke="var(--color-neutral-500)"
            strokeWidth="2.5"
            strokeDasharray="5 5"
          />
        </svg>
        함께 볼 만한 연관성
      </span>
      <span>선이 굵을수록 더 자주 관찰됐어요</span>
    </div>
  );
}

function EvidencePanel({
  subgraph,
  selectedNodeId,
  onClose,
}: {
  subgraph: SubgraphResponse;
  selectedNodeId: string | null;
  onClose: () => void;
}) {
  if (!selectedNodeId) {
    return <p className="mut text-[13.5px]">항목을 누르면 어떤 관계로 이어졌는지 볼 수 있어요.</p>;
  }

  const node = subgraph.nodes.find((n) => n.node_id === selectedNodeId);
  if (!node) return null;

  const related = subgraph.edges.filter(
    (edge) => edge.source_node_id === selectedNodeId || edge.target_node_id === selectedNodeId,
  );
  const sources = [...new Set(related.flatMap((edge) => edge.source_ids))];

  return (
    <Card>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-[17px]">{node.label}</h3>
          <Badge tone="quiet">{NODE_TYPE_LABEL[node.node_type]}</Badge>
        </div>
        <Button variant="ghost" size="sm" onClick={onClose}>
          닫기
        </Button>
      </div>

      <ul className="mut flex flex-col gap-1.5 text-[14px]">
        {related.map((edge, index) => {
          const otherId = edge.source_node_id === selectedNodeId ? edge.target_node_id : edge.source_node_id;
          const other = subgraph.nodes.find((n) => n.node_id === otherId);
          return (
            <li key={`${otherId}-${index}`}>
              · {other?.label ?? otherId}
              {isInferredRelation(edge) ? (
                <span className="mut ml-1 text-[12px]">(함께 볼 만한 연관성)</span>
              ) : null}
            </li>
          );
        })}
      </ul>

      {sources.length > 0 ? (
        <div className="mt-5 border-t pt-4" style={{ borderColor: "var(--line)" }}>
          <p className="gsec mb-2">참고한 공식 자료</p>
          <ul className="space-y-1">
            {sources.map((source) => (
              <li key={source}>
                <a
                  href={source}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="text-[12px] break-all underline underline-offset-2"
                  style={{ color: "var(--accent)" }}
                >
                  {source}
                </a>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </Card>
  );
}
