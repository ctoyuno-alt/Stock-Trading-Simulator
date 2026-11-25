import React, { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { Bot, Play, Pause, Activity, Terminal, ShieldAlert } from 'lucide-react';

interface AutoTraderProps {
  market: 'IN' | 'US';
  timeframe: string;
}

export const AutoTraderTab: React.FC<AutoTraderProps> = ({ market, timeframe }) => {
  const [logs, setLogs] = useState<any[]>([]);
  const [running, setRunning] = useState(false);
  const [autoTickActive, setAutoTickActive] = useState(true);

  const fetchLogs = async () => {
    try {
      const res = await api.getDaemonLogs(30);
      if (res && Array.isArray(res.logs)) {
        setLogs(res.logs);
      }
    } catch (_) {}
  };

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleManualTick = async () => {
    setRunning(true);
    try {
      await api.runAutoTraderTick(market, timeframe);
      await fetchLogs();
    } catch (err) {
      console.error('Tick execution failed:', err);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* 1. Control Header */}
      <div className="bg-obsidian-900 border border-border-medium rounded-xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Bot className="w-5 h-5 text-neon-cyan" />
            <h3 className="text-base font-bold text-slate-100 font-sans">Autonomous AI Auto-Trader Daemon</h3>
          </div>
          <p className="text-xs text-slate-400 mt-0.5 font-mono">
            Continuous 24/7 background quant scanner evaluating 85+ confluence signals and auto-executing 1% risk trades.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={handleManualTick}
            disabled={running}
            className="px-3.5 py-2 bg-bloomberg-amber hover:bg-bloomberg-orange text-black font-bold text-xs rounded-lg flex items-center gap-1.5 transition shadow-sm disabled:opacity-50"
          >
            <Play className="w-3.5 h-3.5 fill-black" />
            {running ? 'Scanning Universe...' : 'Execute Manual Scan'}
          </button>
        </div>
      </div>

      {/* 2. Key Guardrail Policies */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="bg-obsidian-900 p-3.5 rounded-lg border border-border-medium font-mono text-xs space-y-1">
          <div className="text-slate-400">Position Risk Guardrail</div>
          <div className="text-base font-bold text-slate-100">0.5% - 1.0% Equity</div>
          <div className="text-[11px] text-neon-green">Strict 2 Max Concurrent Trades</div>
        </div>

        <div className="bg-obsidian-900 p-3.5 rounded-lg border border-border-medium font-mono text-xs space-y-1">
          <div className="text-slate-400">Minimum Confluence Filter</div>
          <div className="text-base font-bold text-slate-100">85+ / 100 Score</div>
          <div className="text-[11px] text-bloomberg-amber">Multi-Factor Confirmation Required</div>
        </div>

        <div className="bg-obsidian-900 p-3.5 rounded-lg border border-border-medium font-mono text-xs space-y-1">
          <div className="text-slate-400">Minimum Holding Period</div>
          <div className="text-base font-bold text-slate-100">4 Hours Lock</div>
          <div className="text-[11px] text-neon-cyan">Anti-Whipsaw Protection Enabled</div>
        </div>
      </div>

      {/* 3. Live Log Terminal */}
      <div className="bg-obsidian-950 border border-border-medium rounded-xl overflow-hidden shadow-2xl">
        <div className="px-4 py-2.5 bg-obsidian-900/80 border-b border-border-medium flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs font-mono font-semibold text-slate-300">
            <Terminal className="w-4 h-4 text-neon-green" />
            Real-Time Daemon Activity Log Stream
          </div>
          <span className="text-[10px] font-mono text-slate-500">Live Polling • 10s Stream</span>
        </div>

        <div className="p-4 font-mono text-xs space-y-2 max-h-96 overflow-y-auto">
          {logs.length === 0 ? (
            <div className="text-slate-500 italic">No automated trade activity logs recorded yet.</div>
          ) : (
            logs.map((log: any, idx: number) => {
              const text = typeof log === 'string' ? log : log.message || JSON.stringify(log);
              return (
                <div key={idx} className="flex items-start gap-2 text-slate-300">
                  <span className="text-slate-600 select-none">[{idx + 1}]</span>
                  <span className={text.includes('BUY') ? 'text-neon-green' : text.includes('SELL') ? 'text-neon-red' : 'text-slate-300'}>
                    {text}
                  </span>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
