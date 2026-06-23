// File: components/dashboard/dag-visualizer.tsx
import React from 'react';
import { Activity } from 'lucide-react';
import { Card } from '../ui/core';
import { DagData, NodeStatus } from '../../types/gridflow';

const getNodeColor = (status: NodeStatus) => {
  switch(status) {
    case 'running': return 'fill-amber-500 stroke-amber-200';
    case 'success': return 'fill-emerald-500 stroke-emerald-200';
    case 'error': return 'fill-red-500 stroke-red-200';
    default: return 'fill-zinc-800 stroke-zinc-600';
  }
};

export const DagVisualizer = ({ dag }: { dag: DagData }) => {
  return (
    <Card className="flex-1 min-h-[350px] relative overflow-hidden bg-zinc-950/50 flex items-center justify-center">
      <div className="absolute top-4 left-4 text-xs font-medium text-zinc-500 uppercase tracking-widest flex items-center">
         <Activity className="w-3 h-3 mr-2" /> Live Graph Analytics
      </div>
      
      {dag.nodes.length === 0 ? (
         <div className="text-zinc-600 text-sm">Awaiting DAG compilation payload...</div>
      ) : (
        <svg width="600" height="300" className="w-full h-full max-w-2xl">
          {dag.edges.map((edge, i) => {
            const fromNode = dag.nodes.find(n => n.id === edge.from);
            const toNode = dag.nodes.find(n => n.id === edge.to);
            if(!fromNode || !toNode) return null;
            return (
              <line 
                key={i}
                x1={fromNode.x} y1={fromNode.y}
                x2={toNode.x} y2={toNode.y}
                stroke={edge.stroke || "#3f3f46"}
                strokeWidth="2"
                strokeDasharray={edge.strokeDasharray || "none"}
                markerEnd="url(#arrowhead)"
              />
            );
          })}
          
          <defs>
            <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="25" refY="3.5" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#3f3f46" />
            </marker>
          </defs>

          {dag.nodes.map(node => (
            <g key={node.id} transform={`translate(${node.x}, ${node.y})`}>
              <circle 
                r="20" 
                className={`${getNodeColor(node.status)} transition-colors duration-500`}
                strokeWidth="3"
              />
              <text y="35" textAnchor="middle" className="text-xs font-medium fill-zinc-300">
                {node.label}
              </text>
              {node.status === 'running' && (
                <circle r="26" fill="none" className="stroke-amber-500/30 animate-ping" strokeWidth="2" />
              )}
            </g>
          ))}
        </svg>
      )}
    </Card>
  );
};