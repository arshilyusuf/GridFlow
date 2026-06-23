// File: components/dashboard/terminal.tsx
import React, { useEffect, useRef } from 'react';
import { TerminalSquare } from 'lucide-react';
import { Card } from '../ui/core';
import { SystemLog } from '../../types/gridflow';

export const TerminalLogs = ({ logs }: { logs: SystemLog[] }) => {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  return (
    <Card className="h-64 flex flex-col overflow-hidden bg-[#0c0c0e]">
      <div className="flex items-center justify-between px-4 py-2 border-b border-zinc-800/80 bg-zinc-950">
        <div className="flex items-center text-xs text-zinc-500 font-medium">
          <TerminalSquare className="w-4 h-4 mr-2" /> SYSTEM_OUT
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-4 font-mono text-[13px] leading-relaxed">
        {logs.length === 0 ? (
           <span className="text-zinc-600">Waiting for backend stream...</span>
        ) : (
          logs.map((log, i) => {
            let textColor = 'text-zinc-300';
            if (log.type === 'error') textColor = 'text-red-400';
            if (log.type === 'success') textColor = 'text-emerald-400';
            if (log.type === 'warning') textColor = 'text-amber-400';
            
            return (
              <div key={i} className={`mb-1 ${textColor}`}>
                <span className="text-zinc-600 mr-3">[{log.time}]</span>
                {log.msg}
              </div>
            );
          })
        )}
        <div ref={endRef} />
      </div>
    </Card>
  );
};