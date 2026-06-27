// File: hooks/use-engine-socket.ts
import { useState, useEffect, useCallback, useRef } from 'react';
import { DagData, SystemLog, EngineMetrics, LogLevel } from '../types/gridflow';

const DEFAULT_METRICS: EngineMetrics = {
  cpu: 0,
  memory: '0.0 GB',
  processMemory: '0.00 GB',
  activeThreads: 0,
  queuedTasks: 0,
  tasksCompleted: 0,
  totalTasks: 4,
  engineUtilization: 0,
  throughput: 0,
  elapsedSeconds: 0,
  stage: 'Idle',
  progress: 0,
  matrixSize: 0,
};

export const useEngineSocket = (url: string) => {
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [logs, setLogs] = useState<SystemLog[]>([]);
  const [dag, setDag] = useState<DagData>({ nodes: [], edges: [] });
  const [metrics, setMetrics] = useState<EngineMetrics>(DEFAULT_METRICS);

  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const addLog = useCallback((msg: string, type: LogLevel = 'info') => {
    setLogs(prev => [...prev, { time: new Date().toLocaleTimeString(), msg, type }]);
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      setSocket(ws);
      addLog("[System] Connected to GridFlow API Gateway.", "success");
    };

    ws.onclose = () => {
      setIsConnected(false);
      setSocket(null);
      wsRef.current = null;
      addLog("[System] Disconnected. Attempting to reconnect in 5s...", "warning");
      reconnectTimeout.current = setTimeout(connect, 5000);
    };

    ws.onerror = () => {
      ws.close();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        switch (data.type) {
          case 'LOG':
            addLog(data.payload.msg, data.payload.level);
            if (data.payload.msg.includes('Execution complete') || data.payload.msg.includes('Pipeline failed')) {
              setIsRunning(false);
            }
            break;
          case 'DAG_INIT': setDag(data.payload); break;
          case 'NODE_UPDATE':
            setDag(prev => ({
              ...prev,
              nodes: prev.nodes.map(n => n.id === data.payload.id ? { ...n, status: data.payload.status } : n)
            }));
            break;
          case 'METRICS': setMetrics(data.payload); break;
          case 'STATE_CHANGE': setIsRunning(data.payload.isRunning); break;
        }
      } catch (err) {
        console.error("Malformed WebSocket message", err);
      }
    };
  }, [url, addLog]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimeout.current);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [connect]);

  const sendMessage = useCallback((action: string, config?: Record<string, unknown>) => {
    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ action, config }));
    } else {
      addLog("[System] Cannot send: API Gateway offline.", "error");
    }
  }, [addLog]);

  const clearLogs = () => setLogs([]);

  return { isConnected, isRunning, logs, addLog, socket, setIsRunning, clearLogs, dag, metrics, sendMessage };
};
