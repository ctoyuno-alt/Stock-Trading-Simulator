import React, { useEffect, useRef } from 'react';
import { createChart, IChartApi, ISeriesApi, CandlestickData, LineData, HistogramData } from 'lightweight-charts';

interface CandleItem {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

interface ChartProps {
  candles: CandleItem[];
  indicators?: any;
  height?: number;
}

export const TradingViewChart: React.FC<ChartProps> = ({ candles, indicators, height = 500 }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Create TradingView Lightweight Chart
    const chart = createChart(containerRef.current, {
      height,
      layout: {
        background: { color: '#080B11' },
        textColor: '#8F9CAE',
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: 'rgba(255, 255, 255, 0.04)' },
        horzLines: { color: 'rgba(255, 255, 255, 0.04)' },
      },
      crosshair: {
        vertLine: { color: '#FF9900', width: 1, style: 2, labelBackgroundColor: '#1E2638' },
        horzLine: { color: '#FF9900', width: 1, style: 2, labelBackgroundColor: '#1E2638' },
      },
      rightPriceScale: {
        borderColor: '#1E2638',
        scaleMargins: { top: 0.1, bottom: 0.2 },
      },
      timeScale: {
        borderColor: '#1E2638',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    chartRef.current = chart;

    // 1. Candlestick Series
    const candleSeries = chart.addCandlestickSeries({
      upColor: '#00E676',
      downColor: '#FF3366',
      borderUpColor: '#00E676',
      borderDownColor: '#FF3366',
      wickUpColor: '#00E676',
      wickDownColor: '#FF3366',
    });

    // 2. Volume Series
    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });
    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    // 3. EMA 20 & EMA 50 Line Series
    const ema20Series = chart.addLineSeries({
      color: '#00F2FE',
      lineWidth: 1,
      title: 'EMA 20',
    });
    const ema50Series = chart.addLineSeries({
      color: '#FF9900',
      lineWidth: 1,
      title: 'EMA 50',
    });

    // Format & Populate Candle Data
    if (candles && candles.length > 0) {
      const formattedCandles: CandlestickData[] = [];
      const formattedVolume: HistogramData[] = [];

      candles.forEach(c => {
        // Parse timestamp into epoch seconds or date string
        let time: any = Math.floor(new Date(c.timestamp).getTime() / 1000);
        if (isNaN(time)) {
          time = c.timestamp.split('T')[0];
        }

        formattedCandles.push({
          time,
          open: Number(c.open),
          high: Number(c.high),
          low: Number(c.low),
          close: Number(c.close),
        });

        if (c.volume !== undefined) {
          formattedVolume.push({
            time,
            value: Number(c.volume),
            color: Number(c.close) >= Number(c.open) ? 'rgba(0, 230, 118, 0.25)' : 'rgba(255, 51, 102, 0.25)',
          });
        }
      });

      // Sort chronological
      formattedCandles.sort((a, b) => (Number(a.time) || 0) - (Number(b.time) || 0));
      formattedVolume.sort((a, b) => (Number(a.time) || 0) - (Number(b.time) || 0));

      candleSeries.setData(formattedCandles);
      volumeSeries.setData(formattedVolume);

      // Populate Indicators if available
      if (indicators) {
        if (indicators.ema_20_series && Array.isArray(indicators.ema_20_series)) {
          const ema20: LineData[] = indicators.ema_20_series.map((val: number, i: number) => ({
            time: formattedCandles[i]?.time || i,
            value: Number(val),
          })).filter((d: any) => !isNaN(d.value));
          ema20Series.setData(ema20);
        }
        if (indicators.ema_50_series && Array.isArray(indicators.ema_50_series)) {
          const ema50: LineData[] = indicators.ema_50_series.map((val: number, i: number) => ({
            time: formattedCandles[i]?.time || i,
            value: Number(val),
          })).filter((d: any) => !isNaN(d.value));
          ema50Series.setData(ema50);
        }
      }

      chart.timeScale().fitContent();
    }

    // Resize handler
    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [candles, indicators, height]);

  return (
    <div className="w-full relative bg-obsidian-900 border border-border-medium rounded-lg overflow-hidden shadow-xl">
      {/* Chart Legend Toolbar */}
      <div className="absolute top-2.5 left-3 z-10 flex items-center gap-3 bg-obsidian-950/80 backdrop-blur px-2.5 py-1 rounded border border-border-medium text-[11px] font-mono pointer-events-none">
        <span className="flex items-center gap-1.5 text-neon-cyan">
          <span className="w-2.5 h-0.5 bg-neon-cyan inline-block rounded" /> EMA 20
        </span>
        <span className="flex items-center gap-1.5 text-bloomberg-amber">
          <span className="w-2.5 h-0.5 bg-bloomberg-amber inline-block rounded" /> EMA 50
        </span>
        <span className="text-slate-400">Vol: Overlay</span>
      </div>
      <div ref={containerRef} className="w-full" style={{ height: `${height}px` }} />
    </div>
  );
};
