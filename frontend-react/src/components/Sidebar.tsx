import React from 'react';
import {
  LayoutDashboard,
  Database,
  History,
  ShieldCheck,
  Radio,
  FileCheck2,
} from 'lucide-react';
import { HealthStatus } from '../types';

interface SidebarProps {
  activeTab: 'dashboard' | 'datasets' | 'history' | 'proofs';
  setActiveTab: (tab: 'dashboard' | 'datasets' | 'history' | 'proofs') => void;
  health: HealthStatus | null;
  datasetsCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  setActiveTab,
  health,
  datasetsCount,
}) => {
  return (
    <aside className="w-64 border-r border-zinc-800 bg-[#0d0e15]/80 backdrop-blur-xl flex flex-col justify-between select-none">
      <div>
        {/* Brand Header */}
        <div className="p-6 border-b border-zinc-800/80">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-400 to-teal-600 flex items-center justify-center shadow-lg shadow-emerald-500/20 text-black">
              <ShieldCheck className="w-5 h-5 stroke-[2.5]" />
            </div>
            <div>
              <h1 className="font-bold tracking-tight text-white text-base leading-tight">
                PROOF ANALYST
              </h1>
              <p className="text-[11px] text-zinc-400 font-medium">
                Every answer comes with proof
              </p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="p-3 space-y-1">
          <button
            onClick={() => setActiveTab('dashboard')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'dashboard'
                ? 'bg-zinc-800/90 text-white shadow-sm border border-zinc-700/50'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/60'
            }`}
          >
            <LayoutDashboard className="w-4 h-4 text-emerald-400" />
            <span>Dashboard</span>
          </button>

          <button
            onClick={() => setActiveTab('datasets')}
            className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'datasets'
                ? 'bg-zinc-800/90 text-white shadow-sm border border-zinc-700/50'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/60'
            }`}
          >
            <div className="flex items-center gap-3">
              <Database className="w-4 h-4 text-cyan-400" />
              <span>Datasets</span>
            </div>
            {datasetsCount > 0 && (
              <span className="text-[11px] px-1.5 py-0.5 rounded-full bg-zinc-800 border border-zinc-700 text-zinc-300 font-mono">
                {datasetsCount}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('history')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'history'
                ? 'bg-zinc-800/90 text-white shadow-sm border border-zinc-700/50'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/60'
            }`}
          >
            <History className="w-4 h-4 text-violet-400" />
            <span>Analysis History</span>
          </button>

          <button
            onClick={() => setActiveTab('proofs')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'proofs'
                ? 'bg-zinc-800/90 text-white shadow-sm border border-zinc-700/50'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/60'
            }`}
          >
            <FileCheck2 className="w-4 h-4 text-amber-400" />
            <span>Proofs & Evidence</span>
          </button>
        </nav>
      </div>

      {/* Footer System Status */}
      <div className="p-4 border-t border-zinc-800/80 bg-zinc-950/40 space-y-3">
        <div className="flex items-center justify-between text-xs">
          <span className="text-zinc-400 font-medium flex items-center gap-1.5">
            <Radio className="w-3.5 h-3.5 text-zinc-500 animate-pulse" />
            System Status
          </span>
          <span
            className={`flex items-center gap-1.5 font-medium ${
              health?.status === 'healthy' ? 'text-emerald-400' : 'text-rose-400'
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                health?.status === 'healthy'
                  ? 'bg-emerald-400 ring-2 ring-emerald-400/20'
                  : 'bg-rose-400 ring-2 ring-rose-400/20'
              }`}
            />
            {health?.status === 'healthy' ? 'Connected' : 'Offline'}
          </span>
        </div>

        <div className="text-[11px] text-zinc-500 font-mono flex flex-col gap-0.5 border-t border-zinc-900 pt-2">
          <div className="flex justify-between">
            <span>Model:</span>
            <span className="text-zinc-400 truncate max-w-[120px]" title={health?.model}>
              {health?.model?.split('/')[1] || health?.model || 'Configured'}
            </span>
          </div>
          <div className="flex justify-between">
            <span>OpenRouter:</span>
            <span className={health?.openrouter_configured ? 'text-emerald-400' : 'text-amber-400'}>
              {health?.openrouter_configured ? 'Ready' : 'Mock/Offline'}
            </span>
          </div>
        </div>
      </div>
    </aside>
  );
};
