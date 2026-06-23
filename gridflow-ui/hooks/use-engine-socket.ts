// File: hooks/use-engine-socket.ts
import { useState, useEffect, useCallback, useRef } from 'react';
import { DagData, SystemLog, EngineMetrics, LogLevel } from '../types/gridflow';

export const useEngineSocket = (url: string) => {
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [logs, setLogs] = useState<SystemLog[]>([]);
  const [dag, setDag] = useState<DagData>({ nodes: [], edges: [] });
  const [metrics, setMetrics] = useState<EngineMetrics>({ cpu: 0, memory: '0.0 GB', activeThreads: 0 });
  
  // Use a ref to track reconnection attempts
  const reconnectTimeout = useRef<NodeJS.Timeout | null>(null);
  const addLog = useCallback((msg: string, type: LogLevel = 'info') => {
    setLogs(prev => [...prev, { time: new Date().toLocaleTimeString(), msg, type }]);
  }, []);

  const connect = useCallback(() => {
    const ws = new WebSocket(url);

    ws.onopen = () => {
      setIsConnected(true);
      addLog("[System] Connected to GridFlow API Gateway.", "success");
    };

    ws.onclose = () => {
      setIsConnected(false);
      addLog("[System] Disconnected. Attempting to reconnect in 5s...", "warning");
      // Auto-reconnect logic
      reconnectTimeout.current = setTimeout(connect, 5000);
    };

    ws.onerror = () => {
      // Errors are handled by onclose, but we can log specific failures here
      ws.close();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        switch (data.type) {
          case 'LOG': addLog(data.payload.msg, data.payload.level); break;
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

    setSocket(ws);
  }, [url, addLog]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimeout.current);
      if (socket) socket.close();
    };
  }, [connect]);

  // Exposed helper to send data
  const sendMessage = useCallback((action: string, config?: any) => {
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ action, config }));
    } else {
      addLog("[System] Cannot send: API Gateway offline.", "error");
    }
  }, [socket, addLog]);

  const clearLogs = () => setLogs([]);

  return { isConnected, isRunning, logs, addLog, socket, setIsRunning, clearLogs, dag, metrics, sendMessage };
};