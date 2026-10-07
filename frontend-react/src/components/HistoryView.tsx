import React from 'react';
import { HistoryItem } from '../types';
import { History, CheckCircle2, AlertTriangle, XCircle, ArrowRight, Clock, FileSpreadsheet } from 'lucide-react';

interface HistoryViewProps {
  history: HistoryItem[];
  onSelectAudit: (auditId: string) => void;
  isLoading: boolean;
}

export const HistoryView: React.FC<HistoryViewProps> = ({
  history,
  onSelectAudit,
  isLoading,
}) => {
  return (
    <div className="space-y-6 max-w-5xl mx-auto animate-fade-in">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
          <History className="w-6 h-6 text-violet-400" />
          Analysis History & Proof Archive
        </h2>
        <p className="text-xs text-zinc-400 mt-1">
          Every query generates a persistent, cryptographically fingerprinted audit log and reproducible proof.
        </p>
      </div>

      {isLoading ? (
        <div className="p-12 text-center text-xs text-zinc-400 font-mono">
          Loading audit logs...
        </div>
      ) : history.length === 0 ? (
        <div className="p-12 text-center text-xs text-zinc-500 bg-zinc-900/20 border border-zinc-800 rounded-xl">
          No audit records found yet. Run an analysis on the dashboard to generate your first proof.
        </div>
      ) : (
        <div className="space-y-3">
          {history.map((item) => {
            const isVerified = item.status === 'VERIFIED';
            const isCannot = item.status === 'CANNOT_DETERMINE';

            return (
              <div
                key={item.audit_id}
                onClick={() => onSelectAudit(item.audit_id)}
                className="p-5 rounded-xl bg-zinc-900/40 hover:bg-zinc-900/80 border border-zinc-800 hover:border-zinc-700 transition-all cursor-pointer flex flex-col md:flex-row md:items-center justify-between gap-4 group"
              >
                <div className="space-y-1.5 flex-1">
                  <div className="flex items-center gap-3">
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded-full border flex items-center gap-1 font-bold ${
                        isVerified
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                          : isCannot
                          ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                          : 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                      }`}
                    >
                      {isVerified ? (
                        <CheckCircle2 className="w-3 h-3" />
                      ) : isCannot ? (
                        <AlertTriangle className="w-3 h-3" />
                      ) : (
                        <XCircle className="w-3 h-3" />
                      )}
                      {item.status}
                    </span>

                    <span className="text-xs font-mono text-zinc-500 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {item.created_at || item.audit_id}
                    </span>
                  </div>

                  <h3 className="text-sm font-semibold text-white group-hover:text-emerald-400 transition-colors">
                    {item.question}
                  </h3>

                  {item.answer && (
                    <p className="text-xs text-zinc-400 line-clamp-1 font-mono">
                      {item.answer}
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-4 text-xs font-mono text-zinc-400 shrink-0">
                  {item.files_used && item.files_used.length > 0 && (
                    <div className="flex items-center gap-1 text-[11px] text-zinc-500">
                      <FileSpreadsheet className="w-3.5 h-3.5" />
                      <span>{item.files_used.join(', ')}</span>
                    </div>
                  )}

                  <div className="p-2 rounded-lg bg-zinc-800 group-hover:bg-emerald-500 group-hover:text-black text-zinc-400 transition-colors">
                    <ArrowRight className="w-4 h-4" />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
