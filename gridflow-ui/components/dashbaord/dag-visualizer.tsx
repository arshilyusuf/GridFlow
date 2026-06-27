// File: components/dashboard/dag-visualizer.tsx
"use client";

import React, { useMemo } from "react";
import { Activity } from "lucide-react";
import { Card } from "../ui/core";
import { DagData, DagNode, NodeStatus } from "../../types/gridflow";

const STATUS_COLORS: Record<
  NodeStatus,
  { fill: string; stroke: string; ping: string }
> = {
  idle: { fill: "#27272a", stroke: "#52525b", ping: "" },
  running: { fill: "#92400e", stroke: "#fbbf24", ping: "#f59e0b" },
  success: { fill: "#064e3b", stroke: "#34d399", ping: "" },
  error: { fill: "#7f1d1d", stroke: "#f87171", ping: "#ef4444" },
};

// Layout engine: positions nodes based on their ids and relationships
// For the Optimal scenario the backend sends fixed x/y — we respect those.
// For chunk nodes (id prefixed "chunk_") we auto-layout them in a fan.
function useLayoutedDag(dag: DagData): DagData {
  return useMemo(() => {
    if (dag.nodes.length === 0) return dag;

    // Detect if this dag already has explicit positions set by the backend
    // (non-zero x values mean the backend positioned them)
    const hasPositions = dag.nodes.every((n) => n.x !== 0 || n.y !== 0);
    if (hasPositions) return dag;

    // Auto-layout fallback (shouldn't be needed but keeps it safe)
    const positioned = dag.nodes.map((n, i) => ({
      ...n,
      x: 60 + i * 130,
      y: 150,
    }));
    return { ...dag, nodes: positioned };
  }, [dag]);
}

// Compute viewBox to fit all nodes with padding
function computeViewBox(nodes: DagNode[]): string {
  if (nodes.length === 0) return "0 0 600 300";
  const xs = nodes.map((n) => n.x);
  const ys = nodes.map((n) => n.y);
  const minX = Math.min(...xs) - 60;
  const minY = Math.min(...ys) - 60;
  const maxX = Math.max(...xs) + 60;
  const maxY = Math.max(...ys) + 80;
  return `${minX} ${minY} ${maxX - minX} ${maxY - minY}`;
}

function NodeCircle({ node }: { node: DagNode }) {
  const colors = STATUS_COLORS[node.status] ?? STATUS_COLORS.idle;
  const isChunk = node.id.startsWith("chunk_");
  const r = isChunk ? 14 : 22;

  return (
    <g>
      {/* Ping ring for running/error */}
      {colors.ping && (
        <circle
          cx={node.x}
          cy={node.y}
          r={r + 8}
          fill="none"
          stroke={colors.ping}
          strokeWidth="2"
          opacity="0.3"
          style={{ animation: "ping 1.4s ease-out infinite" }}
        />
      )}
      <circle
        cx={node.x}
        cy={node.y}
        r={r}
        fill={colors.fill}
        stroke={colors.stroke}
        strokeWidth={isChunk ? 1.5 : 2.5}
        style={{ transition: "fill 0.4s, stroke 0.4s" }}
      />
      {/* Status icon inside node */}
      {node.status === "success" && (
        <text
          x={node.x}
          y={node.y}
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={isChunk ? 10 : 13}
          fill="#34d399"
        >
          ✓
        </text>
      )}
      {node.status === "error" && (
        <text
          x={node.x}
          y={node.y}
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={isChunk ? 10 : 13}
          fill="#f87171"
        >
          ✕
        </text>
      )}
      {node.status === "running" && (
        <text
          x={node.x}
          y={node.y}
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={isChunk ? 8 : 11}
          fill="#fbbf24"
        >
          ●
        </text>
      )}
      {/* Label below node */}
      <text
        x={node.x}
        y={node.y + r + 14}
        textAnchor="middle"
        fontSize={isChunk ? 9 : 11}
        fontFamily="ui-monospace, monospace"
        fill="#a1a1aa"
      >
        {node.label}
      </text>
    </g>
  );
}

function EdgeLine({
  from,
  to,
  stroke,
  strokeDasharray,
}: {
  from: DagNode;
  to: DagNode;
  stroke?: string;
  strokeDasharray?: string;
}) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const len = Math.sqrt(dx * dx + dy * dy);
  if (len === 0) return null;

  const fromR = from.id.startsWith("chunk_") ? 14 : 22;
  const toR = to.id.startsWith("chunk_") ? 14 : 22;

  const sx = from.x + (dx / len) * fromR;
  const sy = from.y + (dy / len) * fromR;
  const ex = to.x - (dx / len) * (toR + 6);
  const ey = to.y - (dy / len) * (toR + 6);

  return (
    <line
      x1={sx}
      y1={sy}
      x2={ex}
      y2={ey}
      stroke={stroke ?? "#52525b"}
      strokeWidth="1.5"
      strokeDasharray={strokeDasharray}
      markerEnd="url(#dag-arrow)"
      style={{ transition: "stroke 0.3s" }}
    />
  );
}

// Legend pill
function LegendPill({ color, label }: { color: string; label: string }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 5,
        fontSize: 11,
        color: "#71717a",
      }}
    >
      <div
        style={{
          width: 10,
          height: 10,
          borderRadius: "50%",
          background: color,
          border: `1.5px solid ${color}`,
          opacity: 0.8,
        }}
      />
      {label}
    </div>
  );
}

export const DagVisualizer = ({ dag }: { dag: DagData }) => {
  const layouted = useLayoutedDag(dag);
  const viewBox = computeViewBox(layouted.nodes);

  const chunkNodes = layouted.nodes.filter((n) => n.id.startsWith("chunk_"));
  const hasChunks = chunkNodes.length > 0;

  return (
    <Card className="flex-1 min-h-[380px] relative overflow-hidden bg-zinc-950/50 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <div className="text-xs font-medium text-zinc-500 uppercase tracking-widest flex items-center">
          <Activity className="w-3 h-3 mr-2" /> Live Graph Analytics
        </div>
        {/* Legend */}
        <div style={{ display: "flex", gap: 12 }}>
          <LegendPill color="#52525b" label="idle" />
          <LegendPill color="#fbbf24" label="running" />
          <LegendPill color="#34d399" label="done" />
          <LegendPill color="#f87171" label="error" />
        </div>
      </div>

      {/* Parallel chunk badge */}
      {hasChunks && (
        <div className="px-4 pb-1">
          <span className="text-xs text-amber-400 bg-amber-950/50 border border-amber-800/50 rounded px-2 py-0.5">
            {chunkNodes.length} parallel compute chunks active
          </span>
        </div>
      )}

      {/* SVG canvas */}
      <div className="flex-1 flex items-center justify-center p-2">
        {layouted.nodes.length === 0 ? (
          <div className="text-zinc-600 text-sm">
            Awaiting DAG compilation payload...
          </div>
        ) : (
          <>
            <style>{`
              @keyframes ping {
                0%   { transform: scale(1);   opacity: 0.6; }
                80%  { transform: scale(1.6); opacity: 0; }
                100% { transform: scale(1.6); opacity: 0; }
              }
            `}</style>
            <svg
              viewBox={viewBox}
              style={{
                width: "100%",
                height: "100%",
                maxHeight: 340,
                overflow: "visible",
              }}
            >
              <defs>
                <marker
                  id="dag-arrow"
                  viewBox="0 0 10 10"
                  refX="8"
                  refY="5"
                  markerWidth="5"
                  markerHeight="5"
                  orient="auto-start-reverse"
                >
                  <path
                    d="M2 1L8 5L2 9"
                    fill="none"
                    stroke="#52525b"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </marker>
              </defs>

              {/* Edges first (behind nodes) */}
              {layouted.edges.map((edge, i) => {
                const from = layouted.nodes.find((n) => n.id === edge.from);
                const to = layouted.nodes.find((n) => n.id === edge.to);
                if (!from || !to) return null;
                return (
                  <EdgeLine
                    key={i}
                    from={from}
                    to={to}
                    stroke={edge.stroke}
                    strokeDasharray={edge.strokeDasharray}
                  />
                );
              })}

              {/* Nodes */}
              {layouted.nodes.map((node) => (
                <NodeCircle key={node.id} node={node} />
              ))}
            </svg>
          </>
        )}
      </div>
    </Card>
  );
};
