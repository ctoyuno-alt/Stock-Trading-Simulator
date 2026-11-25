import React, { useEffect, useState } from 'react';
import { api } from '../lib/api';

interface TickerQuote {
  symbol: string;
  price: number;
  delta_pct: number;
  currency: string;
  is_index?: boolean;
}

const DEFAULT_QUOTES: TickerQuote[] = [
  { symbol: 'NIFTY 50', price: 24180.80, delta_pct: 0.42, currency: '₹', is_index: true },
  { symbol: 'SENSEX', price: 79402.29, delta_pct: 0.38, currency: '₹', is_index: true },
  { symbol: 'RELIANCE', price: 1285.50, delta_pct: 1.15, currency: '₹' },
  { symbol: 'TCS', price: 4120.00, delta_pct: -0.45, currency: '₹' },
  { symbol: 'HDFCBANK', price: 1745.20, delta_pct: 0.82, currency: '₹' },
  { symbol: 'AAPL', price: 228.50, delta_pct: 0.65, currency: '$' },
  { symbol: 'NVDA', price: 142.80, delta_pct: 2.34, currency: '$' },
  { symbol: 'MSFT', price: 425.20, delta_pct: -0.22, currency: '$' },
  { symbol: 'TSLA', price: 345.60, delta_pct: 3.85, currency: '$' },
];

export const TickerMarquee: React.FC = () => {
  const [quotes, setQuotes] = useState<TickerQuote[]>(DEFAULT_QUOTES);

  useEffect(() => {
    let isMounted = true;
    const fetchLive = async () => {
      try {
        const updated = [...DEFAULT_QUOTES];
        for (const item of updated) {
          if (item.is_index) continue;
          try {
            const res = await api.getCandles(item.symbol, '1d', '5d');
            if (res && res.candles && res.candles.length >= 1) {
              const c = res.candles;
              const last = parseFloat(c[c.length - 1].close);
              const prev = c.length >= 2 ? parseFloat(c[c.length - 2].close) : parseFloat(c[c.length - 1].open);
              const pct = prev > 0 ? ((last - prev) / prev) * 100 : 0;
              item.price = last;
              item.delta_pct = pct;
            }
          } catch (_) {}
        }
        if (isMounted) setQuotes(updated);
      } catch (_) {}
    };

    fetchLive();
    const interval = setInterval(fetchLive, 60000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const marqueeContent = [...quotes, ...quotes];

  return (
    <div className="w-full overflow-hidden bg-obsidian-950 border-b border-border-medium py-1.5 px-0 select-none shadow-inner">
      <div className="animate-ticker flex items-center">
        {marqueeContent.map((q, idx) => {
          const isPos = q.delta_pct >= 0;
          return (
            <div
              key={`${q.symbol}-${idx}`}
              className="inline-flex items-center gap-2 px-4 border-r border-white/10 font-mono text-xs whitespace-nowrap"
            >
              <span className="font-bold text-slate-200 tracking-wider">{q.symbol}</span>
              <span className="text-slate-100 font-medium">
                {q.currency}{q.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <span className={`font-semibold flex items-center gap-0.5 ${isPos ? 'text-neon-green' : 'text-neon-red'}`}>
                {isPos ? '▲ +' : '▼ '}{q.delta_pct.toFixed(2)}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
