// File: app/page.tsx
"use client";

import React, { useState } from "react";
import {
  Play,
  Square,
  Activity,
  Cpu,
  Network,
  Settings2,
  Wifi,
  WifiOff,
  Gauge,
  Timer,
  Layers,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { Card, Button, Badge } from "../components/ui/core";
import { DagVisualizer } from "@/components/dashbaord/dag-visualizer";
import { TerminalLogs } from "@/components/dashbaord/terminal";
import { useEngineSocket } from "../hooks/use-engine-socket";
import { SCENARIOS, ScenarioType } from "../types/gridflow";

// ─── tiny stat pill used in the hero ───
function StatPill({ value, label }: { value: string; label: string }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        padding: "10px 20px",
        background: "rgba(255,255,255,0.04)",
        border: "1px solid rgba(255,255,255,0.08)",
        borderRadius: 10,
        minWidth: 90,
      }}
    >
      <span
        style={{
          fontSize: 20,
          fontWeight: 600,
          color: "#f4f4f5",
          lineHeight: 1.2,
        }}
      >
        {value}
      </span>
      <span style={{ fontSize: 11, color: "#71717a", marginTop: 3 }}>
        {label}
      </span>
    </div>
  );
}

// ─── scenario description map ───
const SCENARIO_INFO: Record<string, { what: string; demonstrates: string }> = {
  "Optimal Execution Path": {
    what: "Allocates two matrices, transforms them in parallel, then splits the dot product across N worker threads — each handling a row chunk simultaneously.",
    demonstrates:
      "Work-stealing scheduler · GIL release · parallel C++ math kernels",
  },
  "Graph Cycle Detected": {
    what: "Builds a DAG where Task B depends on Task C and Task C depends back on Task B — an illegal cycle. The C++ compiler catches it before any thread fires.",
    demonstrates:
      "Kahn's topological sort · DFS cycle tracer · compiler error reporting",
  },
  "Linear Chain Fusion": {
    what: "Submits four tasks in a strict sequence (A→B→C→D). The optimizer detects the linear chain and fuses them into a single task, reducing scheduler overhead.",
    demonstrates:
      "DAGOptimizer · linear chain fusion · task dispatch reduction",
  },
  "Network Worker Failure": {
    what: "Dispatches a DAG across two simulated TCP worker nodes. Midway through, one node goes offline. The registry marks it dead and reroutes remaining tasks.",
    demonstrates: "NodeRegistry · TCP serializer · failover routing",
  },
};

// ─── collapsible hero panel ───
function HeroPanel({ scenario }: { scenario: string }) {
  const [open, setOpen] = useState(true);
  const info =
    SCENARIO_INFO[scenario] ?? SCENARIO_INFO["Optimal Execution Path"];

  return (
    <div
      style={{
        background:
          "linear-gradient(135deg, rgba(16,16,20,0.95) 0%, rgba(24,24,32,0.95) 100%)",
        border: "1px solid rgba(255,255,255,0.07)",
        borderRadius: 14,
        marginBottom: 24,
        overflow: "hidden",
      }}
    >
      {/* Top bar — always visible */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "14px 20px",
          cursor: "pointer",
          userSelect: "none",
        }}
        onClick={() => setOpen((o) => !o)}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {/* Logo mark */}
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: 8,
              background: "rgba(255,255,255,0.07)",
              border: "1px solid rgba(255,255,255,0.1)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 13,
              fontWeight: 700,
              color: "#e4e4e7",
              letterSpacing: "-0.5px",
            }}
          >
            GF
          </div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 600, color: "#f4f4f5" }}>
              GridFlow
            </div>
            <div style={{ fontSize: 11, color: "#71717a" }}>
              C++ parallel task scheduler · pybind11 · work-stealing
            </div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {/* Stat pills — always visible */}
          <StatPill value="O(1)" label="alloc" />
          <StatPill value="Lock-free" label="deque" />
          <StatPill value="GIL-safe" label="bindings" />
          <div style={{ color: "#52525b", marginLeft: 8 }}>
            {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </div>
        </div>
      </div>

      {/* Expandable body */}
      {open && (
        <div
          style={{
            padding: "0 20px 18px",
            borderTop: "1px solid rgba(255,255,255,0.05)",
          }}
        >
          {/* Architecture badges */}
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 8,
              marginTop: 14,
              marginBottom: 16,
            }}
          >
            {[
              "Chase-Lev work-stealing deque",
              "Kahn's topo sort + cycle detection",
              "Linear chain fusion optimizer",
              "Critical path priority scheduler",
              "Thread-local O(1) slab allocator",
              "HFT spin-wait backoff",
              "pybind11 GIL acquire/release",
              "FastAPI WebSocket telemetry",
            ].map((badge) => (
              <span
                key={badge}
                style={{
                  fontSize: 11,
                  padding: "3px 10px",
                  background: "rgba(255,255,255,0.05)",
                  border: "1px solid rgba(255,255,255,0.09)",
                  borderRadius: 20,
                  color: "#a1a1aa",
                }}
              >
                {badge}
              </span>
            ))}
          </div>

          {/* Two-col: what this scenario does + stack */}
          <div
            style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}
          >
            <div
              style={{
                background: "rgba(255,255,255,0.03)",
                borderRadius: 10,
                border: "1px solid rgba(255,255,255,0.06)",
                padding: "12px 14px",
              }}
            >
              <div
                style={{
                  fontSize: 10,
                  fontWeight: 600,
                  color: "#52525b",
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  marginBottom: 6,
                }}
              >
                Active scenario
              </div>
              <div style={{ fontSize: 12, color: "#a1a1aa", lineHeight: 1.6 }}>
                {info.what}
              </div>
            </div>
            <div
              style={{
                background: "rgba(255,255,255,0.03)",
                borderRadius: 10,
                border: "1px solid rgba(255,255,255,0.06)",
                padding: "12px 14px",
              }}
            >
              <div
                style={{
                  fontSize: 10,
                  fontWeight: 600,
                  color: "#52525b",
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  marginBottom: 6,
                }}
              >
                Demonstrates
              </div>
              <div style={{ fontSize: 12, color: "#34d399", lineHeight: 1.6 }}>
                {info.demonstrates}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function GridFlowDashboard() {
  const [scenario, setScenario] = useState<ScenarioType>(SCENARIOS.OPTIMAL);
  const [targetCores, setTargetCores] = useState<number>(8);
  const [payloadSize, setPayloadSize] = useState<number>(14500);

  const {
    socket,
    isConnected,
    isRunning,
    setIsRunning,
    logs,
    clearLogs,
    dag,
    metrics,
    addLog,
  } = useEngineSocket(
    process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws/execution",
  );

  const executePipeline = () => {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      addLog("Cannot deploy: Connection to backend is offline.", "error");
      return;
    }
    clearLogs();
    setIsRunning(true);
    addLog(`[Client] Requesting pipeline deployment: ${scenario}...`, "info");
    socket.send(
      JSON.stringify({
        action: "START_PIPELINE",
        config: { scenario, targetCores, payloadSize },
      }),
    );
  };

  const haltPipeline = () => {
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({ action: "HALT_PIPELINE" }));
    setIsRunning(false);
    addLog("[Client] Transmitted emergency halt signal to Engine.", "warning");
  };

  return (
    <div className="min-h-screen bg-[#09090b] text-zinc-300 font-sans p-6">
      {/* ── HEADER ── */}
      <header className="flex items-center justify-between mb-6 pb-4 border-b border-zinc-800/60">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded bg-zinc-100 flex items-center justify-center text-zinc-950 font-bold text-sm">
            GF
          </div>
          <div>
            <h1 className="text-xl font-semibold text-zinc-100 tracking-tight">
              GridFlow Monitor
            </h1>
            <p className="text-xs text-zinc-500">
              Distributed Execution Engine · Live Dashboard
            </p>
          </div>
        </div>
        <div className="flex items-center space-x-4">
          <div className="flex items-center text-xs text-zinc-400 mr-4">
            {isConnected ? (
              <Wifi className="w-4 h-4 mr-2 text-emerald-500" />
            ) : (
              <WifiOff className="w-4 h-4 mr-2 text-red-500" />
            )}
            {isConnected ? "API Connected" : "API Offline"}
          </div>
          <Badge variant={isRunning ? "warning" : "success"}>
            {isRunning ? "PROCESSING" : "SYSTEM IDLE"}
          </Badge>
        </div>
      </header>

      {/* ── HERO PANEL ── */}
      <HeroPanel scenario={scenario} />

      {/* ── MAIN GRID ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* LEFT COLUMN — controls + metrics */}
        <div className="lg:col-span-3 space-y-6">
          <Card className="p-5">
            <h2 className="text-sm font-semibold text-zinc-100 mb-4 flex items-center">
              <Settings2 className="w-4 h-4 mr-2" /> Pipeline Parameters
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1.5">
                  Execution Profile
                </label>
                <select
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-md text-sm text-zinc-300 py-2 px-3 focus:outline-none focus:ring-1 focus:ring-zinc-600 disabled:opacity-50"
                  value={scenario}
                  onChange={(e) => setScenario(e.target.value as ScenarioType)}
                  disabled={isRunning || !isConnected}
                >
                  {Object.values(SCENARIOS).map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1.5">
                  Target Core Count
                </label>
                <input
                  type="number"
                  value={targetCores}
                  onChange={(e) => setTargetCores(Number(e.target.value))}
                  disabled={isRunning || !isConnected}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-md text-sm text-zinc-300 py-2 px-3 focus:outline-none disabled:opacity-50"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1.5">
                  Matrix Scale (payload)
                </label>
                <input
                  type="number"
                  value={payloadSize}
                  onChange={(e) => setPayloadSize(Number(e.target.value))}
                  disabled={isRunning || !isConnected}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-md text-sm text-zinc-300 py-2 px-3 focus:outline-none disabled:opacity-50"
                />
              </div>
            </div>
            <div className="mt-6">
              <Button
                onClick={isRunning ? haltPipeline : executePipeline}
                disabled={!isConnected}
                variant={isRunning ? "danger" : "primary"}
                className="w-full"
                icon={isRunning ? Square : Play}
              >
                {isRunning ? "Halt Execution" : "Deploy Pipeline"}
              </Button>
            </div>
          </Card>

          {/* Metric cards */}
          <div className="grid grid-cols-2 gap-4">
            <Card className="p-4 flex flex-col justify-between">
              <div className="flex items-center text-zinc-500 mb-2">
                <Cpu className="w-4 h-4 mr-1.5" />
                <span className="text-xs font-medium">System CPU</span>
              </div>
              <span className="text-2xl font-semibold text-zinc-100">
                {metrics.cpu}%
              </span>
            </Card>
            <Card className="p-4 flex flex-col justify-between">
              <div className="flex items-center text-zinc-500 mb-2">
                <Activity className="w-4 h-4 mr-1.5" />
                <span className="text-xs font-medium">Process Memory</span>
              </div>
              <span className="text-2xl font-semibold text-zinc-100">
                {metrics.memory}
              </span>
            </Card>
            <Card className="p-4 flex flex-col justify-between">
              <div className="flex items-center text-zinc-500 mb-2">
                <Gauge className="w-4 h-4 mr-1.5" />
                <span className="text-xs font-medium">Engine Util.</span>
              </div>
              <span className="text-2xl font-semibold text-zinc-100">
                {metrics.engineUtilization}%
              </span>
            </Card>
            <Card className="p-4 flex flex-col justify-between">
              <div className="flex items-center text-zinc-500 mb-2">
                <Network className="w-4 h-4 mr-1.5" />
                <span className="text-xs font-medium">Active Workers</span>
              </div>
              <span className="text-2xl font-semibold text-zinc-100">
                {metrics.activeThreads} / {targetCores}
              </span>
            </Card>

            {/* Progress bar */}
            <Card className="col-span-2 p-4">
              <div className="flex items-center justify-between text-zinc-500 mb-2">
                <div className="flex items-center">
                  <Layers className="w-4 h-4 mr-1.5" />
                  <span className="text-xs font-medium">Pipeline Progress</span>
                </div>
                <span className="text-xs text-zinc-400">
                  {metrics.tasksCompleted}/{metrics.totalTasks} tasks
                </span>
              </div>
              <div className="w-full h-2 bg-zinc-800 rounded-full overflow-hidden mb-2">
                <div
                  className="h-full bg-emerald-500 transition-all duration-300"
                  style={{ width: `${metrics.progress}%` }}
                />
              </div>
              <p className="text-xs text-zinc-400 truncate">
                {metrics.stage || "Idle"}
              </p>
            </Card>

            <Card className="p-4 flex flex-col justify-between">
              <div className="flex items-center text-zinc-500 mb-2">
                <Timer className="w-4 h-4 mr-1.5" />
                <span className="text-xs font-medium">Elapsed</span>
              </div>
              <span className="text-2xl font-semibold text-zinc-100">
                {metrics.elapsedSeconds}s
              </span>
            </Card>
            <Card className="p-4 flex flex-col justify-between">
              <div className="flex items-center text-zinc-500 mb-2">
                <Activity className="w-4 h-4 mr-1.5" />
                <span className="text-xs font-medium">Throughput</span>
              </div>
              <span className="text-2xl font-semibold text-zinc-100">
                {metrics.throughput} t/s
              </span>
            </Card>

            <Card className="col-span-2 p-4 flex flex-col justify-between">
              <div className="flex items-center text-zinc-500 mb-2">
                <Cpu className="w-4 h-4 mr-1.5" />
                <span className="text-xs font-medium">
                  Process Memory · Matrix · Queue
                </span>
              </div>
              <span className="text-sm font-semibold text-zinc-100">
                {metrics.processMemory} ·{" "}
                {metrics.matrixSize > 0
                  ? `${metrics.matrixSize}×${metrics.matrixSize}`
                  : "—"}{" "}
                · {metrics.queuedTasks} queued
              </span>
            </Card>
          </div>
        </div>

        {/* RIGHT COLUMN — DAG + terminal */}
        <div className="lg:col-span-9 flex flex-col space-y-6">
          <DagVisualizer dag={dag} />
          <TerminalLogs logs={logs} />
        </div>
      </div>
    </div>
  );
}
