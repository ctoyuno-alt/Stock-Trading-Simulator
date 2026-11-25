import React, { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { BookOpen, Download, TrendingUp, TrendingDown, DollarSign } from 'lucide-react';

interface LedgerTabProps {
  currency: string;
}

export const LedgerTab: React.FC<LedgerTabProps> = ({ currency }) => {
  const [orders, setOrders] = useState<any[]>([]);
  const [metrics, setMetrics] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    const fetchLedger = async () => {
      try {
        const [ordRes, metRes] = await Promise.all([
          api.getOrders(100),
          api.getMetrics(),
        ]);
        if (isMounted) {
          setOrders(Array.isArray(ordRes) ? ordRes : []);
          setMetrics(metRes || null);
        }
      } catch (err) {
        console.error('Failed to load ledger:', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchLedger();
    return () => { isMounted = false; };
  }, []);

  const exportCsv = () => {
    if (orders.length === 0) return;
    const headers = ['Order ID', 'Symbol', 'Side', 'Qty', 'Price', 'Status', 'Timestamp'];
    const rows = orders.map(o => [
      o.id,
      o.symbol,
      o.side,
      o.quantity,
      o.price,
      o.status,
      o.created_at,
    ]);
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map(e => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `trade_ledger_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const netRealized = metrics?.net_realized_pnl_inr ?? 0.0;
  const winRate = metrics?.win_rate_pct ?? 0.0;
  const profitFactor = metrics?.profit_factor ?? 0.0;
  const maxDrawdown = metrics?.max_drawdown_pct ?? 0.0;
  const chargesPaid = metrics?.total_charges_inr ?? 0.0;

  return (
    <div className="space-y-4">
      {/* 1. Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <div className="bg-obsidian-900 border border-border-medium rounded-xl p-3.5 font-mono">
          <div className="text-[10px] text-slate-400 uppercase">Net Realized P&L</div>
          <div className={`text-base font-bold mt-0.5 ${netRealized >= 0 ? 'text-neon-green' : 'text-neon-red'}`}>
            {netRealized >= 0 ? '+' : ''}{currency}{netRealized.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </div>
          <div className="text-[10px] text-slate-500 mt-1">Closed Trades</div>
        </div>

        <div className="bg-obsidian-900 border border-border-medium rounded-xl p-3.5 font-mono">
          <div className="text-[10px] text-slate-400 uppercase">Win Rate</div>
          <div className="text-base font-bold text-slate-100 mt-0.5">
            {winRate.toFixed(1)}%
          </div>
          <div className="text-[10px] text-neon-cyan mt-1">Institutional Strategy</div>
        </div>

        <div className="bg-obsidian-900 border border-border-medium rounded-xl p-3.5 font-mono">
          <div className="text-[10px] text-slate-400 uppercase">Profit Factor</div>
          <div className="text-base font-bold text-slate-100 mt-0.5">
            {profitFactor.toFixed(2)}
          </div>
          <div className="text-[10px] text-slate-500 mt-1">Gross Wins / Losses</div>
        </div>

        <div className="bg-obsidian-900 border border-border-medium rounded-xl p-3.5 font-mono">
          <div className="text-[10px] text-slate-400 uppercase">Max Drawdown</div>
          <div className="text-base font-bold text-rose-400 mt-0.5">
            {maxDrawdown.toFixed(2)}%
          </div>
          <div className="text-[10px] text-slate-500 mt-1">Peak-to-Trough</div>
        </div>

        <div className="bg-obsidian-900 border border-border-medium rounded-xl p-3.5 font-mono">
          <div className="text-[10px] text-slate-400 uppercase">Charges & Taxes Paid</div>
          <div className="text-base font-bold text-bloomberg-amber mt-0.5">
            {currency}{chargesPaid.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </div>
          <div className="text-[10px] text-slate-500 mt-1">STT / GST / Turnover</div>
        </div>
      </div>

      {/* 2. Trade Execution History Table */}
      <div className="bg-obsidian-900 border border-border-medium rounded-xl overflow-hidden shadow-xl">
        <div className="p-4 border-b border-border-medium flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm font-bold text-slate-100 font-sans">
            <BookOpen className="w-4 h-4 text-bloomberg-amber" />
            Execution Order History ({orders.length})
          </div>
          <button
            onClick={exportCsv}
            disabled={orders.length === 0}
            className="px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded text-xs font-mono font-medium text-slate-300 flex items-center gap-1.5 transition disabled:opacity-50"
          >
            <Download className="w-3.5 h-3.5" />
            Export CSV
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-xs">
            <thead className="bg-obsidian-950 text-slate-400 uppercase text-[10px] tracking-wider border-b border-border-medium">
              <tr>
                <th className="p-3">Order ID</th>
                <th className="p-3">Symbol</th>
                <th className="p-3">Side</th>
                <th className="p-3">Quantity</th>
                <th className="p-3">Price</th>
                <th className="p-3">Status</th>
                <th className="p-3">Timestamp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-medium text-slate-200">
              {orders.length === 0 ? (
                <tr>
                  <td colSpan={7} className="p-6 text-center text-slate-500 italic font-sans">
                    No executed orders found in trade ledger.
                  </td>
                </tr>
              ) : (
                orders.map(o => (
                  <tr key={o.id} className="hover:bg-white/[0.02] transition">
                    <td className="p-3 text-slate-400">#{o.id}</td>
                    <td className="p-3 font-bold text-slate-100">{o.symbol}</td>
                    <td className={`p-3 font-bold ${o.side === 'BUY' ? 'text-neon-green' : 'text-neon-red'}`}>
                      {o.side}
                    </td>
                    <td className="p-3">{o.quantity}</td>
                    <td className="p-3">{currency}{Number(o.price || 0).toFixed(2)}</td>
                    <td className="p-3">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-neon-green/10 text-neon-green border border-neon-green/20">
                        {o.status || 'FILLED'}
                      </span>
                    </td>
                    <td className="p-3 text-slate-400">
                      {o.created_at ? new Date(o.created_at).toLocaleString() : 'Just now'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
