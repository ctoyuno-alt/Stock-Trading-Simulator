import React from 'react';
import { useAuth } from '../context/AuthContext';
import { Globe, Search, RefreshCw, AlertTriangle, RotateCcw } from 'lucide-react';

interface SidebarProps {
  activeMarket: 'IN' | 'US';
  setActiveMarket: (market: 'IN' | 'US') => void;
  selectedSymbol: string;
  setSelectedSymbol: (sym: string) => void;
  timeframe: string;
  setTimeframe: (tf: string) => void;
  universe: any[];
  portfolio: any;
  autoRefresh: boolean;
  setAutoRefresh: (val: boolean) => void;
  refreshRate: number;
  setRefreshRate: (rate: number) => void;
  onResetAccount: () => void;
}

const TIMEFRAMES = ['1m', '5m', '15m', '1h', '1d'];

export const Sidebar: React.FC<SidebarProps> = ({
  activeMarket,
  setActiveMarket,
  selectedSymbol,
  setSelectedSymbol,
  timeframe,
  setTimeframe,
  universe,
  portfolio,
  autoRefresh,
  setAutoRefresh,
  refreshRate,
  setRefreshRate,
  onResetAccount,
}) => {
  const { user, isAdmin } = useAuth();
  const [searchTerm, setSearchTerm] = React.useState('');

  const currSymbol = activeMarket === 'IN' ? '₹' : '$';
  const filteredSymbols = universe.filter(u =>
    u.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (u.name && u.name.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const equity = portfolio?.equity_inr || (activeMarket === 'IN' ? 100000 : 25000);
  const cash = portfolio?.cash_balance_inr || equity;
  const totalPnl = portfolio?.total_pnl_inr || 0;
  const openCount = portfolio?.open_positions_count || 0;
  const retPct = portfolio?.return_on_initial_capital_pct || 0;

  return (
    <aside className="w-72 bg-obsidian-950 border-r border-border-medium flex flex-col h-[calc(100vh-6rem)] shrink-0 overflow-y-auto">
      {/* 1. Market Selection */}
      <div className="p-3.5 border-b border-border-medium">
        <label className="text-[11px] font-mono text-slate-400 uppercase tracking-wider block mb-2 font-semibold">
          Active Exchange / Market
        </label>
        <div className="grid grid-cols-2 gap-1.5 bg-obsidian-900 p-1 rounded-lg border border-border-medium">
          <button
            onClick={() => setActiveMarket('IN')}
            className={`py-1.5 px-2 rounded-md text-xs font-semibold flex items-center justify-center gap-1.5 transition ${
              activeMarket === 'IN'
                ? 'bg-bloomberg-amber/20 border border-bloomberg-amber/40 text-bloomberg-amber shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            🇮🇳 India (NSE)
          </button>
          <button
            onClick={() => setActiveMarket('US')}
            className={`py-1.5 px-2 rounded-md text-xs font-semibold flex items-center justify-center gap-1.5 transition ${
              activeMarket === 'US'
                ? 'bg-bloomberg-amber/20 border border-bloomberg-amber/40 text-bloomberg-amber shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            🇺🇸 US Mega-Caps
          </button>
        </div>
      </div>

      {/* 2. Instrument Selection */}
      <div className="p-3.5 border-b border-border-medium space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-[11px] font-mono text-slate-400 uppercase tracking-wider font-semibold">
            Instrument Universe ({universe.length})
          </label>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-500" />
          <input
            type="text"
            placeholder="Search ticker or company..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            className="w-full bg-obsidian-900 border border-border-medium rounded-md py-1.5 pl-8 pr-3 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-bloomberg-amber/50"
          />
        </div>

        {/* Dropdown / Selector */}
        <select
          value={selectedSymbol}
          onChange={e => setSelectedSymbol(e.target.value)}
          className="w-full bg-obsidian-900 border border-border-medium rounded-md py-1.5 px-2.5 text-xs text-slate-100 font-mono focus:outline-none focus:border-bloomberg-amber/50"
        >
          {filteredSymbols.map(u => (
            <option key={u.symbol} value={u.symbol}>
              {u.symbol} — {u.name || u.sector || 'Equities'}
            </option>
          ))}
        </select>

        {/* Timeframe Buttons */}
        <div>
          <label className="text-[10px] font-mono text-slate-400 uppercase tracking-wider block mb-1">
            Chart Interval
          </label>
          <div className="flex items-center gap-1">
            {TIMEFRAMES.map(tf => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={`flex-1 py-1 rounded text-xs font-mono font-medium border transition ${
                  timeframe === tf
                    ? 'bg-neon-cyan/15 border-neon-cyan/40 text-neon-cyan'
                    : 'bg-obsidian-900 border-border-medium text-slate-400 hover:text-slate-200'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 3. Live Auto-Refresh Polling */}
      <div className="p-3.5 border-b border-border-medium space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
            <RefreshCw className={`w-3 h-3 ${autoRefresh ? 'animate-spin text-neon-cyan' : 'text-slate-500'}`} />
            Live Stream Polling
          </span>
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={e => setAutoRefresh(e.target.checked)}
            className="rounded bg-obsidian-900 border-border-medium text-bloomberg-amber focus:ring-0 cursor-pointer"
          />
        </div>
        {autoRefresh && (
          <div className="flex items-center justify-between text-xs">
            <span className="text-[11px] text-slate-400 font-mono">Interval:</span>
            <div className="flex gap-1">
              {[5, 10, 15, 30].map(s => (
                <button
                  key={s}
                  onClick={() => setRefreshRate(s)}
                  className={`px-1.5 py-0.5 rounded text-[10px] font-mono border ${
                    refreshRate === s
                      ? 'bg-white/10 border-white/20 text-white font-bold'
                      : 'border-transparent text-slate-500 hover:text-slate-300'
                  }`}
                >
                  {s}s
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 4. Portfolio Snapshot Card */}
      <div className="p-3.5 border-b border-border-medium space-y-2.5">
        <div className="flex items-center justify-between">
          <span className="text-xs font-mono font-semibold text-slate-300 tracking-wider uppercase">
            Portfolio ({currSymbol})
          </span>
          <span className="text-[10px] font-mono text-slate-500">
            {openCount}/2 POS
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="bg-obsidian-900 p-2 rounded border border-border-medium">
            <div className="text-[10px] font-mono text-slate-400 uppercase">Equity</div>
            <div className="text-sm font-mono font-bold text-slate-100">
              {currSymbol}{equity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          </div>
          <div className="bg-obsidian-900 p-2 rounded border border-border-medium">
            <div className="text-[10px] font-mono text-slate-400 uppercase">Cash</div>
            <div className="text-sm font-mono font-bold text-slate-100">
              {currSymbol}{cash.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          </div>
        </div>

        <div className="bg-obsidian-900 p-2 rounded border border-border-medium flex items-center justify-between">
          <div>
            <div className="text-[10px] font-mono text-slate-400 uppercase">Total P&L</div>
            <div className={`text-sm font-mono font-bold ${totalPnl >= 0 ? 'text-neon-green' : 'text-neon-red'}`}>
              {totalPnl >= 0 ? '+' : ''}{currSymbol}{totalPnl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          </div>
          <span className={`text-xs font-mono font-bold px-1.5 py-0.5 rounded ${
            retPct >= 0 ? 'bg-neon-green/10 text-neon-green' : 'bg-rose-500/10 text-rose-400'
          }`}>
            {retPct >= 0 ? '+' : ''}{retPct.toFixed(2)}%
          </span>
        </div>
      </div>

      {/* 5. Account Reset (Clean Slate) */}
      <div className="p-3.5 mt-auto">
        <button
          onClick={onResetAccount}
          className="w-full py-2 px-3 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 hover:text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition"
        >
          <RotateCcw className="w-3.5 h-3.5 text-bloomberg-amber" />
          Reset Virtual Account
        </button>
      </div>
    </aside>
  );
};
