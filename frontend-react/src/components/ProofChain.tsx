import React from 'react';
import {
  CheckCircle2,
  CircleDashed,
  Sparkles,
  Database,
  FileCode,
  ShieldCheck,
  Terminal,
  FileSearch,
} from 'lucide-react';

interface ProofChainProps {
  stages: string[];
  currentStatus?: string;
  isAnalyzing: boolean;
}

const ALL_STAGES = [
  { id: 'Understanding question', label: 'Understanding', icon: Sparkles },
  { id: 'Finding data', label: 'Retrieval', icon: Database },
  { id: 'Generating code', label: 'Code Gen', icon: FileCode },
  { id: 'Executing code', label: 'Execution', icon: Terminal },
  { id: 'Verifying result', label: 'Verification', icon: ShieldCheck },
  { id: 'Proof Built', label: 'Proof', icon: FileSearch },
];

export const ProofChain: React.FC<ProofChainProps> = ({
  stages,
  currentStatus,
  isAnalyzing,
}) => {
  return (
    <div className="w-full bg-zinc-900/40 border border-zinc-800/80 rounded-xl p-4 backdrop-blur-md">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
            Deterministic Proof Chain
          </span>
        </div>
        <span className="text-[11px] font-mono text-zinc-500">
          {stages.length} of {ALL_STAGES.length - 1} steps completed
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
        {ALL_STAGES.map((s, idx) => {
          const Icon = s.icon;
          const isDone =
            stages.includes(s.id) ||
            (s.id === 'Proof Built' && currentStatus === 'VERIFIED');
          const isCurrent =
            isAnalyzing &&
            ((idx === 0 && stages.length === 0) ||
              stages[stages.length - 1] === ALL_STAGES[idx - 1]?.id);

          return (
            <div
              key={s.id}
              className={`flex items-center gap-2.5 p-2.5 rounded-lg border text-xs font-medium transition-all ${
                isDone
                  ? 'bg-emerald-950/20 border-emerald-500/30 text-emerald-300'
                  : isCurrent
                  ? 'bg-blue-950/20 border-blue-500/40 text-blue-300 animate-pulse'
                  : 'bg-zinc-950/30 border-zinc-800/50 text-zinc-500'
              }`}
            >
              <div
                className={`w-5 h-5 rounded-md flex items-center justify-center shrink-0 ${
                  isDone
                    ? 'bg-emerald-500/20 text-emerald-400'
                    : isCurrent
                    ? 'bg-blue-500/20 text-blue-400'
                    : 'bg-zinc-800/60 text-zinc-500'
                }`}
              >
                {isDone ? (
                  <CheckCircle2 className="w-3.5 h-3.5" />
                ) : isCurrent ? (
                  <CircleDashed className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Icon className="w-3.5 h-3.5" />
                )}
              </div>
              <span className="truncate">{s.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
