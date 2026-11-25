import React from 'react';

interface GaugeProps {
  score: number; // 0 - 100
  title?: string;
  size?: number;
}

export const ConfluenceGauge: React.FC<GaugeProps> = ({ score, title = 'Confluence Score', size = 180 }) => {
  const clamped = Math.max(0, Math.min(100, Math.round(score)));
  const radius = size * 0.38;
  const strokeWidth = size * 0.08;
  const center = size / 2;
  const circumference = Math.PI * radius; // Half circle arc
  const strokeDashoffset = circumference - (clamped / 100) * circumference;

  let color = '#FF3366'; // Red
  let label = 'LOW CONFLUENCE';
  if (clamped >= 75) {
    color = '#00E676'; // Neon Green
    label = 'STRONG CONFLUENCE';
  } else if (clamped >= 50) {
    color = '#FF9900'; // Amber
    label = 'MODERATE';
  }

  return (
    <div className="flex flex-col items-center justify-center p-3 bg-obsidian-900 border border-border-medium rounded-xl shadow-lg">
      <div className="relative" style={{ width: size, height: size * 0.65 }}>
        <svg width={size} height={size * 0.65} className="overflow-visible">
          {/* Background Arc */}
          <path
            d={`M ${center - radius} ${center} A ${radius} ${radius} 0 0 1 ${center + radius} ${center}`}
            fill="none"
            stroke="rgba(255, 255, 255, 0.08)"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
          />
          {/* Active Score Arc */}
          <path
            d={`M ${center - radius} ${center} A ${radius} ${radius} 0 0 1 ${center + radius} ${center}`}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            className="transition-all duration-1000 ease-out"
          />
        </svg>

        {/* Center Score Display */}
        <div className="absolute inset-x-0 bottom-1 flex flex-col items-center justify-center">
          <span className="font-mono text-3xl font-bold tracking-tight" style={{ color }}>
            {clamped}
            <span className="text-xs text-slate-500 font-normal">/100</span>
          </span>
          <span className="text-[10px] font-mono font-semibold tracking-wider uppercase mt-0.5" style={{ color }}>
            {label}
          </span>
        </div>
      </div>
      <span className="text-xs font-mono text-slate-400 mt-2 tracking-wide font-medium">{title}</span>
    </div>
  );
};
