// File: types/gridflow.ts

export type NodeStatus = 'idle' | 'running' | 'success' | 'error';
export type LogLevel = 'info' | 'error' | 'success' | 'warning';

export interface DagNode {
  id: string;
  label: string;
  x: number;
  y: number;
  status: NodeStatus;
}

export interface DagEdge {
  from: string;
  to: string;
  stroke?: string;
  strokeDasharray?: string;
}

export interface DagData {
  nodes: DagNode[];
  edges: DagEdge[];
}

export interface SystemLog {
  time: string;
  msg: string;
  type: LogLevel;
}

export interface EngineMetrics {
  cpu: number;
  memory: string;
  activeThreads: number;
}

export const SCENARIOS = {
  OPTIMAL: 'Optimal Execution Path',
  CYCLE: 'Graph Cycle Detected',
  FUSION: 'Linear Chain Fusion',
  NETWORK_FAIL: 'Network Worker Failure'
} as const;

export type ScenarioType = typeof SCENARIOS[keyof typeof SCENARIOS];