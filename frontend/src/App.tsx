import React, { useEffect, useState } from 'react';
import { useAuth } from './context/AuthContext';
import { api } from './lib/api';
import { TickerMarquee } from './components/TickerMarquee';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { AuthModal } from './components/AuthModal';

import { MarketTab } from './tabs/MarketTab';
import { AiConfluenceTab } from './tabs/AiConfluenceTab';
import { AutoTraderTab } from './tabs/AutoTraderTab';
import { PositionsTab } from './tabs/PositionsTab';
import { LedgerTab } from './tabs/LedgerTab';
import { BacktestTab } from './tabs/BacktestTab';
import { HealthTab } from './tabs/HealthTab';
import { AdminTab } from './tabs/AdminTab';

import {
  TrendingUp,
  BrainCircuit,
  Bot,
  Briefcase,
  BookOpen,
  FlaskConical,
  ShieldCheck,
  ShieldAlert,
  Users,
} from 'lucide-react';

export const App: React.FC = () => {
  const { user, token, isAdmin } = useAuth();

  // Navigation State
  const [activeTab, setActiveTab] = useState<string>('market');

  // Workstation Parameters
  const [activeMarket, setActiveMarket] = useState<'IN' | 'US'>('IN');
  const [selectedSymbol, setSelectedSymbol] = useState<string>('RELIANCE');
  const [timeframe, setTimeframe] = useState<string>('1d');

  // Data State
  const [universe, setUniverse] = useState<any[]>([]);
  const [portfolio, setPortfolio] = useState<any>(null);
  const [positions, setPositions] = useState<any[]>([]);
  const [systemStatus, setSystemStatus] = useState<any>(null);
  const [killSwitchActive, setKillSwitchActive] = useState<boolean>(false);

  // Auto Refresh Polling
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);
  const [refreshRate, setRefreshRate] = useState<number>(10);

  const currencySymbol = activeMarket === 'IN' ? '₹' : '$';
  const currencyCode = activeMarket === 'IN' ? 'INR' : 'USD';

  // 1. Fetch Universe on Market Change
  useEffect(() => {
    let isMounted = true;
    const loadUniverse = async () => {
      try {
        const u = await api.getUniverse(activeMarket);
        if (isMounted && Array.isArray(u)) {
          setUniverse(u);
          if (u.length > 0) {
            setSelectedSymbol(activeMarket === 'IN' ? 'RELIANCE' : 'AAPL');
          }
        }
      } catch (err) {
        console.error('Failed to load universe:', err);
      }
    };
    loadUniverse();
    return () => { isMounted = false; };
  }, [activeMarket]);

  // 2. Fetch Portfolio, Positions & Status
  const refreshAccountData = async () => {
    try {
      const [portRes, posRes, statRes] = await Promise.all([
        api.getPortfolio(currencyCode),
        api.getPositions('OPEN', currencyCode),
        api.getSystemStatus(),
      ]);
      setPortfolio(portRes);
      setPositions(Array.isArray(posRes) ? posRes : []);
      setSystemStatus(statRes);
      setKillSwitchActive(statRes?.safety_guardrails?.kill_switch_active || false);
    } catch (_) {}
  };

  useEffect(() => {
    refreshAccountData();
    if (!autoRefresh) return;
    const interval = setInterval(refreshAccountData, refreshRate * 1000);
    return () => clearInterval(interval);
  }, [activeMarket, autoRefresh, refreshRate]);

  // Actions
  const handleToggleKillSwitch = async (activate: boolean) => {
    try {
      await api.toggleKillSwitch(activate, 'User toggle via React terminal');
      setKillSwitchActive(activate);
      refreshAccountData();
    } catch (err: any) {
      alert(`Kill switch toggle failed: ${err.message}`);
    }
  };

  const handleResetAccount = async () => {
    if (!confirm(`Are you sure you want to reset your virtual account to starting capital (${currencySymbol}100,000)?`)) return;
    try {
      await api.resetPaperAccount(currencyCode, activeMarket === 'IN' ? 100000 : 25000);
      refreshAccountData();
    } catch (err: any) {
      alert(`Reset failed: ${err.message}`);
    }
  };

  const tabs = [
    { id: 'market', label: 'Market & Technicals', icon: TrendingUp },
    { id: 'ai', label: 'AI Confluence Analysis', icon: BrainCircuit },
    { id: 'autotrader', label: 'Autonomous Auto-Trader', icon: Bot },
    { id: 'positions', label: 'Positions & Execution', icon: Briefcase },
    { id: 'ledger', label: 'Trade Ledger & Analytics', icon: BookOpen },
    { id: 'backtest', label: 'Historical Backtest', icon: FlaskConical },
    { id: 'health', label: 'System Health & Freshness', icon: ShieldCheck },
  ];

  if (isAdmin) {
    tabs.push({ id: 'admin', label: 'Admin User & Account Management', icon: Users });
  }

  const isMarketOpen = activeMarket === 'IN' ? systemStatus?.market_open : systemStatus?.us_market_open;
  const daemonActive = systemStatus?.safety_guardrails?.daemon_active ?? true;

  return (
    <div className="min-h-screen bg-obsidian-950 text-slate-100 flex flex-col font-sans select-none">
      {/* Auth Gate Modal when unauthenticated */}
      {!token && <AuthModal onSuccess={refreshAccountData} />}

      {/* Top 60fps Ticker Tape */}
      <TickerMarquee />

      {/* Main Terminal Header */}
      <Header
        activeMarket={activeMarket}
        currency={currencySymbol}
        isOpen={Boolean(isMarketOpen)}
        daemonActive={daemonActive}
        killSwitchActive={killSwitchActive}
        onToggleKillSwitch={handleToggleKillSwitch}
      />

      {/* Primary Workspace View */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Control Sidebar */}
        <Sidebar
          activeMarket={activeMarket}
          setActiveMarket={setActiveMarket}
          selectedSymbol={selectedSymbol}
          setSelectedSymbol={setSelectedSymbol}
          timeframe={timeframe}
          setTimeframe={setTimeframe}
          universe={universe}
          portfolio={portfolio}
          autoRefresh={autoRefresh}
          setAutoRefresh={setAutoRefresh}
          refreshRate={refreshRate}
          setRefreshRate={setRefreshRate}
          onResetAccount={handleResetAccount}
        />

        {/* Main Dashboard Canvas */}
        <main className="flex-1 flex flex-col h-[calc(100vh-6rem)] overflow-y-auto bg-obsidian-900">
          {/* Institutional Tab Navigation Bar */}
          <div className="bg-obsidian-950 border-b border-border-medium px-4 flex items-center gap-1 overflow-x-auto shrink-0 sticky top-0 z-20">
            {tabs.map(t => {
              const Icon = t.icon;
              const isActive = activeTab === t.id;
              return (
                <button
                  key={t.id}
                  onClick={() => setActiveTab(t.id)}
                  className={`px-3 py-2.5 text-xs font-semibold flex items-center gap-2 border-b-2 transition whitespace-nowrap ${
                    isActive
                      ? 'border-bloomberg-amber text-bloomberg-amber bg-obsidian-900 shadow-sm'
                      : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-white/[0.02]'
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-bloomberg-amber' : 'text-slate-500'}`} />
                  {t.label}
                </button>
              );
            })}
          </div>

          {/* Active Tab Content Area */}
          <div className="p-4 flex-1">
            {activeTab === 'market' && (
              <MarketTab
                symbol={selectedSymbol}
                timeframe={timeframe}
                market={activeMarket}
                currency={currencySymbol}
              />
            )}

            {activeTab === 'ai' && (
              <AiConfluenceTab
                symbol={selectedSymbol}
                timeframe={timeframe}
                currency={currencySymbol}
              />
            )}

            {activeTab === 'autotrader' && (
              <AutoTraderTab
                market={activeMarket}
                timeframe={timeframe}
              />
            )}

            {activeTab === 'positions' && (
              <PositionsTab
                symbol={selectedSymbol}
                currency={currencySymbol}
                portfolio={portfolio}
                positions={positions}
                onOrderPlaced={refreshAccountData}
              />
            )}

            {activeTab === 'ledger' && (
              <LedgerTab currency={currencySymbol} />
            )}

            {activeTab === 'backtest' && (
              <BacktestTab
                symbol={selectedSymbol}
                currency={currencySymbol}
              />
            )}

            {activeTab === 'health' && (
              <HealthTab />
            )}

            {activeTab === 'admin' && isAdmin && (
              <AdminTab />
            )}
          </div>
        </main>
      </div>
    </div>
  );
};
