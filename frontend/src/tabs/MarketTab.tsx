import React, { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { TradingViewChart } from '../components/TradingViewChart';
import { TrendingUp, BarChart2, Activity, Zap } from 'lucide-react';

interface MarketTabProps {
  symbol: string;
  timeframe: string;
  market: 'IN' | 'US';
  currency: string;
}

export const MarketTab: React.FC<MarketTabProps> = ({ symbol, timeframe, market, currency }) => {
  const [candles, setCandles] = useState<any[]>([]);
  const [indicators, setIndicators] = useState<any>(null);
  const [signal, setSignal] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    const loadData = async () => {
      setLoading(true);
      try {
        const [cRes, indRes, sigRes] = await Promise.all([
          api.getCandles(symbol, timeframe, '6mo'),
          api.getIndicators(symbol, timeframe),
          api.getSignal(symbol, timeframe),
        ]);
        if (isMounted) {
          setCandles(cRes?.candles || []);
          setIndicators(indRes?.indicators || null);
          setSignal(sigRes || null);
        }
      } catch (err) {
        console.error('Failed to load market data:', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    loadData();
    return () => { isMounted = false; };
  }, [symbol, timeframe]);

  const lastCandle = candles[candles.length - 1];
  const prevCandle = candles.length >= 2 ? candles[candles.length - 2] : lastCandle;
  const currentPrice = lastCandle ? Number(lastCandle.close) : 0;
  const prevClose = prevCandle ? Number(prevCandle.close) : currentPrice;
  const delta = currentPrice - prevClose;
  const deltaPct = prevClose > 0 ? (delta / prevClose) * 100 : 0;

  const rsi = indicators?.rsi ?? 50.0;
  const macdVal = indicators?.macd_line ?? 0.0;
  const macdSig = indicators?.macd_signal ?? 0.0;
  const macdHist = indicators?.macd_histogram ?? 0.0;

  return (
    <div className="space-y-4">
      {/* 1. Market Telemetry Ribbon */}
      <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-2">
        <div className="bg-obsidian-900 border border-border-medium rounded-lg p-2.5">
          <div className="text-[10px] font-mono text-slate-400 uppercase">Last Price</div>
          <div className="text-base font-mono font-bold text-slate-100 mt-0.5">
            {currency}{currentPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className={`text-[11px] font-mono font-semibold ${delta >= 0 ? 'text-neon-green' : 'text-neon-red'}`}>
            {delta >= 0 ? '▲ +' : '▼ '}{delta.toFixed(2)} ({deltaPct.toFixed(2)}%)
          </div>
        </div>

        <div className="bg-obsidian-900 border border-border-medium rounded-lg p-2.5">
          <div className="text-[10px] font-mono text-slate-400 uppercase">Day Range</div>
          <div className="text-xs font-mono text-slate-300 mt-1">
            H: {currency}{lastCandle ? Number(lastCandle.high).toFixed(2) : '-'}
          </div>
          <div className="text-xs font-mono text-slate-400">
            L: {currency}{lastCandle ? Number(lastCandle.low).toFixed(2) : '-'}
          </div>
        </div>

        <div className="bg-obsidian-900 border border-border-medium rounded-lg p-2.5">
          <div className="text-[10px] font-mono text-slate-400 uppercase">RSI (14)</div>
          <div className="text-base font-mono font-bold text-slate-100 mt-0.5">
            {rsi.toFixed(1)}
          </div>
          <div className="text-[10px] font-mono text-slate-400">
            {rsi >= 70 ? 'Overbought' : rsi <= 30 ? 'Oversold' : 'Neutral'}
          </div>
        </div>

        <div className="bg-obsidian-900 border border-border-medium rounded-lg p-2.5">
          <div className="text-[10px] font-mono text-slate-400 uppercase">MACD Histogram</div>
          <div className={`text-base font-mono font-bold mt-0.5 ${macdHist >= 0 ? 'text-neon-green' : 'text-neon-red'}`}>
            {macdHist >= 0 ? '+' : ''}{macdHist.toFixed(2)}
          </div>
          <div className="text-[10px] font-mono text-slate-400">
            Sig: {macdSig.toFixed(2)}
          </div>
        </div>

        <div className="bg-obsidian-900 border border-border-medium rounded-lg p-2.5">
          <div className="text-[10px] font-mono text-slate-400 uppercase">Strategy Signal</div>
          <div className={`text-sm font-mono font-bold mt-0.5 uppercase ${
            signal?.signal === 'BUY' ? 'text-neon-green' : signal?.signal === 'SELL' ? 'text-neon-red' : 'text-slate-300'
          }`}>
            {signal?.signal || 'HOLD'}
          </div>
          <div className="text-[10px] font-mono text-slate-400">
            Confidence: {signal?.confidence ? `${Math.round(signal.confidence * 100)}%` : '65%'}
          </div>
        </div>

        <div className="bg-obsidian-900 border border-border-medium rounded-lg p-2.5">
          <div className="text-[10px] font-mono text-slate-400 uppercase">Candle Count</div>
          <div className="text-base font-mono font-bold text-slate-100 mt-0.5">
            {candles.length}
          </div>
          <div className="text-[10px] font-mono text-neon-cyan">
            Interval: {timeframe}
          </div>
        </div>
      </div>

      {/* 2. Interactive TradingView Chart */}
      <div className="relative">
        {loading && (
          <div className="absolute inset-0 bg-obsidian-950/60 backdrop-blur-sm z-20 flex items-center justify-center font-mono text-xs text-slate-300">
            Loading {symbol} high-frequency candlestick data...
          </div>
        )}
        <TradingViewChart candles={candles} indicators={indicators} height={520} />
      </div>
    </div>
  );
};
