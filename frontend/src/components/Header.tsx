import React from 'react';
import { useAuth } from '../context/AuthContext';
import { Shield, Activity, Power, LogOut, Radio } from 'lucide-react';

interface HeaderProps {
  activeMarket: 'IN' | 'US';
  currency: string;
  isOpen: boolean;
  daemonActive: boolean;
  killSwitchActive: boolean;
  onToggleKillSwitch: (active: boolean) => void;
}

export const Header: React.FC<HeaderProps> = ({
  activeMarket,
  currency,
  isOpen,
  daemonActive,
  killSwitchActive,
  onToggleKillSwitch,
}) => {
  const { user, logout, isAdmin } = useAuth();

  return (
    <header className="h-16 bg-obsidian-950/80 backdrop-blur border-b border-border-medium px-4 flex items-center justify-between sticky top-0 z-30">
      {/* Brand & Market Identity */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-bloomberg-amber/15 border border-bloomberg-amber/30 flex items-center justify-center font-bold text-bloomberg-amber shadow-sm">
            ⚡
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-base tracking-wider text-slate-100 font-sans">QUANTUM TRADER</span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-white/5 border border-white/10 text-slate-300">
                {activeMarket === 'IN' ? 'NSE/BSE (INR)' : 'NYSE/NASDAQ (USD)'}
              </span>
            </div>
            <div className="text-[11px] text-slate-400 hidden md:block">
              Institutional Quantitative Engine • Multi-Factor Confluence Strategy ({currency})
            </div>
          </div>
        </div>
      </div>

      {/* Telemetry Status Pills & Actions */}
      <div className="flex items-center gap-2.5">
        {/* Session Status */}
        <div className={`px-2.5 py-1 rounded-md text-xs font-mono font-semibold flex items-center gap-1.5 border ${
          isOpen
            ? 'bg-neon-green/10 border-neon-green/30 text-neon-green'
            : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
        }`}>
          <span className={`w-2 h-2 rounded-full ${isOpen ? 'bg-neon-green animate-pulse' : 'bg-rose-400'}`} />
          {activeMarket} SESSION: {isOpen ? 'OPEN' : 'CLOSED'}
        </div>

        {/* 24/7 Daemon Status */}
        <div className={`hidden sm:flex px-2.5 py-1 rounded-md text-xs font-mono font-semibold items-center gap-1.5 border ${
          daemonActive
            ? 'bg-neon-cyan/10 border-neon-cyan/30 text-neon-cyan'
            : 'bg-slate-800/40 border-slate-700 text-slate-400'
        }`}>
          <Radio className={`w-3 h-3 ${daemonActive ? 'animate-pulse text-neon-cyan' : ''}`} />
          DAEMON: {daemonActive ? 'ACTIVE' : 'STANDBY'}
        </div>

        {/* Emergency Kill Switch Button */}
        <button
          onClick={() => onToggleKillSwitch(!killSwitchActive)}
          className={`px-3 py-1 rounded-md text-xs font-mono font-bold flex items-center gap-1.5 transition-all shadow-sm ${
            killSwitchActive
              ? 'bg-rose-600 hover:bg-rose-500 text-white animate-pulse'
              : 'bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300'
          }`}
          title={killSwitchActive ? 'Click to deactivate kill switch' : 'Emergency kill switch: halts all trading'}
        >
          <Power className="w-3.5 h-3.5" />
          {killSwitchActive ? 'KILL SWITCH ACTIVE' : 'KILL SWITCH'}
        </button>

        {/* User Capsule */}
        {user && (
          <div className="flex items-center gap-2 pl-2 border-l border-white/10">
            <div className="text-right hidden sm:block">
              <div className="text-xs font-semibold text-slate-200">{user.username}</div>
              <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">{user.role}</div>
            </div>
            <button
              onClick={logout}
              className="p-1.5 rounded-md hover:bg-white/10 text-slate-400 hover:text-rose-400 transition"
              title="Sign Out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </header>
  );
};
