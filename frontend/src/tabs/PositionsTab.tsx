import React, { useState } from 'react';
import { api } from '../lib/api';
import { Briefcase, ArrowUpRight, Calculator, CheckCircle2, AlertOctagon } from 'lucide-react';

interface PositionsTabProps {
  symbol: string;
  currency: string;
  portfolio: any;
  positions: any[];
  onOrderPlaced: () => void;
}

export const PositionsTab: React.FC<PositionsTabProps> = ({
  symbol,
  currency,
  portfolio,
  positions,
  onOrderPlaced,
}) => {
  const [entryPrice, setEntryPrice] = useState<number>(2450.0);
  const [stopLoss, setStopLoss] = useState<number>(2380.0);
  const [takeProfit, setTakeProfit] = useState<number>(2600.0);
  const [manualQty, setManualQty] = useState<number>(10);
  const [isAutoSizing, setIsAutoSizing] = useState<boolean>(true);
  const [loading, setLoading] = useState<boolean>(false);
  const [orderFeedback, setOrderFeedback] = useState<string | null>(null);

  // 1% Risk Calculations
  const equity = portfolio?.equity_inr || (currency === '₹' ? 100000 : 25000);
  const riskBudget = equity * 0.01;
  const riskPerShare = Math.max(0.01, entryPrice - stopLoss);
  const calculatedQty = Math.max(1, Math.floor(riskBudget / riskPerShare));
  const effectiveQty = isAutoSizing ? calculatedQty : manualQty;
  const capitalRequired = effectiveQty * entryPrice;

  // Risk:Reward ratio
  const rewardPerShare = Math.max(0, takeProfit - entryPrice);
  const rrRatio = riskPerShare > 0 ? (rewardPerShare / riskPerShare).toFixed(2) : '0.00';

  // Indian Statutory Friction estimation
  const turnover = capitalRequired;
  const stt = turnover * 0.001; // 0.1% delivery
  const stampDuty = turnover * 0.00015;
  const gst = (turnover * 0.0000325) * 0.18;
  const totalFriction = stt + stampDuty + gst;

  const handleExecuteOrder = async () => {
    setLoading(true);
    setOrderFeedback(null);
    try {
      await api.placeBuyOrder({
        symbol,
        price: entryPrice,
        stop_loss_price: stopLoss,
        take_profit_price: takeProfit,
        quantity: effectiveQty,
        enforce_market_hours: false,
        reason: 'React Workstation Execution',
      });
      setOrderFeedback(`Order placed successfully for ${effectiveQty} shares of ${symbol}!`);
      onOrderPlaced();
    } catch (err: any) {
      setOrderFeedback(`Error: ${err.message || 'Execution failed'}`);
    } finally {
      setLoading(false);
    }
  };

  const handleClosePosition = async (id: number) => {
    try {
      await api.closePosition(id, 'Manual Close via React UI');
      onOrderPlaced();
    } catch (err: any) {
      alert(`Close failed: ${err.message}`);
    }
  };

  return (
    <div className="space-y-4">
      {/* 1. Virtual Order Execution Portal */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left 2 Cols: Order Sizing & Setup */}
        <div className="lg:col-span-2 bg-obsidian-900 border border-border-medium rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-border-medium pb-3">
            <div className="flex items-center gap-2 text-sm font-bold text-slate-100 font-sans">
              <Calculator className="w-4 h-4 text-bloomberg-amber" />
              1% Equity Risk-Budgeted Execution Portal
            </div>
            <span className="text-xs font-mono font-semibold text-neon-cyan">Target: {symbol}</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-[11px] font-mono text-slate-400 mb-1">Entry Price ({currency})</label>
              <input
                type="number"
                step="0.05"
                value={entryPrice}
                onChange={e => setEntryPrice(parseFloat(e.target.value) || 0)}
                className="w-full bg-obsidian-950 border border-border-medium rounded-lg p-2 text-sm font-mono text-slate-100 focus:outline-none focus:border-bloomberg-amber"
              />
            </div>

            <div>
              <label className="block text-[11px] font-mono text-slate-400 mb-1">Stop-Loss Price ({currency})</label>
              <input
                type="number"
                step="0.05"
                value={stopLoss}
                onChange={e => setStopLoss(parseFloat(e.target.value) || 0)}
                className="w-full bg-obsidian-950 border border-border-medium rounded-lg p-2 text-sm font-mono text-slate-100 focus:outline-none focus:border-bloomberg-amber"
              />
            </div>

            <div>
              <label className="block text-[11px] font-mono text-slate-400 mb-1">Take-Profit Price ({currency})</label>
              <input
                type="number"
                step="0.05"
                value={takeProfit}
                onChange={e => setTakeProfit(parseFloat(e.target.value) || 0)}
                className="w-full bg-obsidian-950 border border-border-medium rounded-lg p-2 text-sm font-mono text-slate-100 focus:outline-none focus:border-bloomberg-amber"
              />
            </div>
          </div>

          {/* Sizing Mode Toggle */}
          <div className="flex items-center justify-between p-3 bg-obsidian-950 rounded-lg border border-border-medium text-xs font-mono">
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="autoSize"
                checked={isAutoSizing}
                onChange={e => setIsAutoSizing(e.target.checked)}
                className="rounded text-bloomberg-amber focus:ring-0 cursor-pointer"
              />
              <label htmlFor="autoSize" className="cursor-pointer text-slate-200 font-semibold">
                Auto-Calculate 1% Risk Position Size ({calculatedQty} Qty)
              </label>
            </div>
            {!isAutoSizing && (
              <div className="flex items-center gap-2">
                <span className="text-slate-400">Manual Qty:</span>
                <input
                  type="number"
                  value={manualQty}
                  onChange={e => setManualQty(parseInt(e.target.value) || 1)}
                  className="w-20 bg-obsidian-900 border border-border-medium rounded px-2 py-1 text-slate-100 text-xs font-mono"
                />
              </div>
            )}
          </div>

          {/* Feedback & Place Button */}
          {orderFeedback && (
            <div className={`p-3 rounded-lg text-xs font-mono ${orderFeedback.includes('Error') ? 'bg-rose-500/10 border border-rose-500/20 text-rose-400' : 'bg-neon-green/10 border border-neon-green/20 text-neon-green'}`}>
              {orderFeedback}
            </div>
          )}

          <button
            onClick={handleExecuteOrder}
            disabled={loading}
            className="w-full py-2.5 rounded-lg bg-neon-green hover:bg-emerald-400 text-black font-extrabold text-sm tracking-wide transition shadow-lg disabled:opacity-50 flex items-center justify-center gap-2"
          >
            <ArrowUpRight className="w-4 h-4" />
            {loading ? 'Routing Order...' : `Execute Virtual BUY Order (${effectiveQty} shares)`}
          </button>
        </div>

        {/* Right Col: Mathematical Guardrail Preview */}
        <div className="bg-obsidian-900 border border-border-medium rounded-xl p-5 space-y-3">
          <div className="text-sm font-bold text-slate-100 font-sans border-b border-border-medium pb-2">
            Execution Guardrails & Friction
          </div>

          <div className="font-mono text-xs space-y-2">
            <div className="flex justify-between">
              <span className="text-slate-400">Risk per Share:</span>
              <span className="text-slate-200">{currency}{riskPerShare.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Total Capital Outlay:</span>
              <span className="text-slate-200">{currency}{capitalRequired.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Risk:Reward Ratio:</span>
              <span className="font-bold text-neon-green">1 : {rrRatio}</span>
            </div>
            <div className="flex justify-between border-t border-border-medium pt-2">
              <span className="text-slate-400">STT (0.1%):</span>
              <span className="text-slate-300">{currency}{stt.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Stamp Duty + GST:</span>
              <span className="text-slate-300">{currency}{(stampDuty + gst).toFixed(2)}</span>
            </div>
            <div className="flex justify-between border-t border-border-medium pt-2 font-bold">
              <span className="text-slate-200">Total Statutory Friction:</span>
              <span className="text-bloomberg-amber">{currency}{totalFriction.toFixed(2)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Active Positions Table */}
      <div className="bg-obsidian-900 border border-border-medium rounded-xl overflow-hidden shadow-xl">
        <div className="p-4 border-b border-border-medium flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm font-bold text-slate-100 font-sans">
            <Briefcase className="w-4 h-4 text-neon-cyan" />
            Active Open Paper Positions ({positions.length})
          </div>
          <span className="text-xs font-mono text-slate-400">Max: 2 concurrent</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-xs">
            <thead className="bg-obsidian-950 text-slate-400 uppercase text-[10px] tracking-wider border-b border-border-medium">
              <tr>
                <th className="p-3">Symbol</th>
                <th className="p-3">Side</th>
                <th className="p-3">Qty</th>
                <th className="p-3">Entry Price</th>
                <th className="p-3">Stop-Loss</th>
                <th className="p-3">Take-Profit</th>
                <th className="p-3">Unrealized P&L</th>
                <th className="p-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-medium text-slate-200">
              {positions.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-6 text-center text-slate-500 italic font-sans">
                    No active open positions. Virtual capital is safe in cash.
                  </td>
                </tr>
              ) : (
                positions.map(p => {
                  const pnl = Number(p.unrealized_pnl || 0);
                  return (
                    <tr key={p.id} className="hover:bg-white/[0.02] transition">
                      <td className="p-3 font-bold text-slate-100">{p.symbol}</td>
                      <td className="p-3 text-neon-green font-bold">BUY</td>
                      <td className="p-3">{p.quantity}</td>
                      <td className="p-3">{currency}{Number(p.entry_price).toFixed(2)}</td>
                      <td className="p-3 text-rose-400">{currency}{Number(p.stop_loss_price).toFixed(2)}</td>
                      <td className="p-3 text-neon-cyan">{p.take_profit_price ? `${currency}${Number(p.take_profit_price).toFixed(2)}` : '-'}</td>
                      <td className={`p-3 font-bold ${pnl >= 0 ? 'text-neon-green' : 'text-neon-red'}`}>
                        {pnl >= 0 ? '+' : ''}{currency}{pnl.toFixed(2)}
                      </td>
                      <td className="p-3 text-right">
                        <button
                          onClick={() => handleClosePosition(p.id)}
                          className="px-2.5 py-1 bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/30 text-rose-400 rounded text-[11px] font-semibold transition"
                        >
                          Close Pos
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
