// File: app/page.tsx
"use client";

import React, { useState } from 'react';
import { Play, Square, Activity, Cpu, Network, Settings2, Wifi, WifiOff, Gauge, Timer, Layers } from 'lucide-react';
import { Card, Button, Badge } from '../components/ui/core';
import { DagVisualizer } from '@/components/dashbaord/dag-visualizer';
import { TerminalLogs } from '@/components/dashbaord/terminal';
import { useEngineSocket } from '../hooks/use-engine-socket';
import { SCENARIOS, ScenarioType } from '../types/gridflow';

export default function GridFlowDashboard() {
  const [scenario, setScenario] = useState<ScenarioType>(SCENARIOS.OPTIMAL);
  const [targetCores, setTargetCores] = useState<number>(8);
  const [payloadSize, setPayloadSize] = useState<number>(14500);

  const { 
    socket, isConnected, isRunning, setIsRunning, 
    logs, clearLogs, dag, metrics, addLog 
  } = useEngineSocket(process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws/execution');

  const executePipeline = () => {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      addLog("Cannot deploy: Connection to backend is offline.", "error");
      return;
    }
    clearLogs();
    setIsRunning(true);
    addLog(`[Client] Requesting pipeline deployment: ${scenario}...`, "info");
    
    socket.send(JSON.stringify({
      action: 'START_PIPELINE',
      config: { scenario, targetCores, payloadSize }
    }));
  };

  const haltPipeline = () => {
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({ action: 'HALT_PIPELINE' }));
    setIsRunning(false);
    addLog("[Client] Transmitted emergency halt signal to Engine.", "warning");
  };

  return (
    <div className="min-h-screen bg-[#09090b] text-zinc-300 font-sans p-6">
      <header className="flex items-center justify-between mb-8 pb-4 border-b border-zinc-800/60">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded bg-zinc-100 flex items-center justify-center text-zinc-950 font-bold">GF</div>
          <div>
            <h1 className="text-xl font-semibold text-zinc-100 tracking-tight">GridFlow Monitor</h1>
            <p className="text-xs text-zinc-500">Distributed Execution Engine UI</p>
          </div>
        </div>
        <div className="flex items-center space-x-4">
          <div className="flex items-center text-xs text-zinc-400 mr-4">
            {isConnected ? <Wifi className="w-4 h-4 mr-2 text-emerald-500" /> : <WifiOff className="w-4 h-4 mr-2 text-red-500" />}
            {isConnected ? 'API Connected' : 'API Offline'}
          </div>
          <Badge variant={isRunning ? "warning" : "success"}>
            {isRunning ? "PROCESSING" : "SYSTEM IDLE"}
          </Badge>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-3 space-y-6">
          <Card className="p-5">
            <h2 className="text-sm font-semibold text-zinc-100 mb-4 flex items-center">
              <Settings2 className="w-4 h-4 mr-2" /> Pipeline Parameters
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1.5">Execution Profile</label>
                <select 
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-md text-sm text-zinc-300 py-2 px-3 focus:outline-none focus:ring-1 focus:ring-zinc-600 disabled:opacity-50"
                  value={scenario}
                  onChange={(e) => setScenario(e.target.value as ScenarioType)}
                  disabled={isRunning || !isConnected}
                >
                  {Object.values(SCENARIOS).map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1.5">Target Core Count</label>
                <input 
                  type="number" 
                  value={targetCores}
                  onChange={(e) => setTargetCores(Number(e.target.value))}
                  disabled={isRunning || !isConnected}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-md text-sm text-zinc-300 py-2 px-3 focus:outline-none disabled:opacity-50" 
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1.5">Matrix Scale (payload)</label>
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
                {isRunning ? 'Halt Execution' : 'Deploy Pipeline'}
              </Button>
            </div>
          </Card>

          <div className="grid grid-cols-2 gap-4">
            <Card className="p-4 flex flex-col justify-between">
              <div className="flex items-center text-zinc-500 mb-2">
                <Cpu className="w-4 h-4 mr-1.5" />
                <span className="text-xs font-medium">System CPU</span>
              </div>
              <span className="text-2xl font-semibold text-zinc-100">{metrics.cpu}%</span>
            </Card>
            <Card className="p-4 flex flex-col justify-between">
              <div className="flex items-center text-zinc-500 mb-2">
                <Activity className="w-4 h-4 mr-1.5" />
                <span className="text-xs font-medium">System Memory</span>
              </div>
              <span className="text-2xl font-semibold text-zinc-100">{metrics.memory}</span>
            </Card>
            <Card className="p-4 flex flex-col justify-between">
              <div className="flex items-center text-zinc-500 mb-2">
                <Gauge className="w-4 h-4 mr-1.5" />
                <span className="text-xs font-medium">Engine Utilization</span>
              </div>
              <span className="text-2xl font-semibold text-zinc-100">{metrics.engineUtilization}%</span>
            </Card>
            <Card className="p-4 flex flex-col justify-between">
              <div className="flex items-center text-zinc-500 mb-2">
                <Network className="w-4 h-4 mr-1.5" />
                <span className="text-xs font-medium">Active Workers</span>
              </div>
              <span className="text-2xl font-semibold text-zinc-100">{metrics.activeThreads} / {targetCores}</span>
            </Card>
            <Card className="col-span-2 p-4">
              <div className="flex items-center justify-between text-zinc-500 mb-2">
                <div className="flex items-center">
                  <Layers className="w-4 h-4 mr-1.5" />
                  <span className="text-xs font-medium">Pipeline Progress</span>
                </div>
                <span className="text-xs text-zinc-400">{metrics.tasksCompleted}/{metrics.totalTasks} tasks</span>
              </div>
              <div className="w-full h-2 bg-zinc-800 rounded-full overflow-hidden mb-2">
                <div
                  className="h-full bg-emerald-500 transition-all duration-300"
                  style={{ width: `${metrics.progress}%` }}
                />
              </div>
              <p className="text-xs text-zinc-400 truncate">{metrics.stage || 'Idle'}</p>
            </Card>
            <Card className="p-4 flex flex-col justify-between">
              <div className="flex items-center text-zinc-500 mb-2">
                <Timer className="w-4 h-4 mr-1.5" />
                <span className="text-xs font-medium">Elapsed</span>
              </div>
              <span className="text-2xl font-semibold text-zinc-100">{metrics.elapsedSeconds}s</span>
            </Card>
            <Card className="p-4 flex flex-col justify-between">
              <div className="flex items-center text-zinc-500 mb-2">
                <Activity className="w-4 h-4 mr-1.5" />
                <span className="text-xs font-medium">Throughput</span>
              </div>
              <span className="text-2xl font-semibold text-zinc-100">{metrics.throughput} t/s</span>
            </Card>
            <Card className="col-span-2 p-4 flex flex-col justify-between">
              <div className="flex items-center text-zinc-500 mb-2">
                <Cpu className="w-4 h-4 mr-1.5" />
                <span className="text-xs font-medium">Process Memory · Matrix · Queue</span>
              </div>
              <span className="text-sm font-semibold text-zinc-100">
                {metrics.processMemory} · {metrics.matrixSize > 0 ? `${metrics.matrixSize}×${metrics.matrixSize}` : '—'} · {metrics.queuedTasks} queued
              </span>
            </Card>
          </div>
        </div>

        <div className="lg:col-span-9 flex flex-col space-y-6">
          <DagVisualizer dag={dag} />
          <TerminalLogs logs={logs} />
        </div>
      </div>
    </div>
  );
}