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
  processMemory: string;
  activeThreads: number;
  queuedTasks: number;
  tasksCompleted: number;
  totalTasks: number;
  engineUtilization: number;
  throughput: number;
  elapsedSeconds: number;
  stage: string;
  progress: number;
  matrixSize: number;
}

export const SCENARIOS = {
  OPTIMAL: 'Optimal Execution Path',
  CYCLE: 'Graph Cycle Detected',
  FUSION: 'Linear Chain Fusion',
  NETWORK_FAIL: 'Network Worker Failure'
} as const;

export type ScenarioType = typeof SCENARIOS[keyof typeof SCENARIOS];