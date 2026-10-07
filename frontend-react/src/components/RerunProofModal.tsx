import React from 'react';
import { X, RotateCcw, CheckCircle2, XCircle, ArrowRight } from 'lucide-react';
import { RerunResponse } from '../types';

interface RerunProofModalProps {
  isOpen: boolean;
  onClose: () => void;
  isLoading: boolean;
  result: RerunResponse | null;
  onTriggerRerun: () => void;
}

export const RerunProofModal: React.FC<RerunProofModalProps> = ({
  isOpen,
  onClose,
  isLoading,
  result,
  onTriggerRerun,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="w-full max-w-xl bg-zinc-950 border border-zinc-800 rounded-2xl overflow-hidden shadow-2xl flex flex-col">
        {/* Header */}
        <div className="p-5 border-b border-zinc-800 flex items-center justify-between bg-zinc-900/60">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <RotateCcw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white tracking-tight">
                DETERMINISTIC PROOF RE-EXECUTION
              </h2>
              <p className="text-xs text-zinc-400">
                Re-executing Python sandbox to verify reproducibility.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {isLoading ? (
            <div className="py-12 flex flex-col items-center justify-center text-center space-y-3">
              <div className="w-10 h-10 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
              <div className="text-sm font-semibold text-white">RE-RUNNING PROOF IN SANDBOX...</div>
              <p className="text-xs text-zinc-400 max-w-xs">
                Executing the exact Python AST in an isolated subprocess with fresh inputs.
              </p>
            </div>
          ) : result ? (
            <div className="space-y-6">
              {/* Verdict Header */}
              <div
                className={`p-4 rounded-xl border flex items-center gap-3 ${
                  result.matched
                    ? 'bg-emerald-950/30 border-emerald-500/40 text-emerald-300'
                    : 'bg-rose-950/30 border-rose-500/40 text-rose-300'
                }`}
              >
                {result.matched ? (
                  <CheckCircle2 className="w-6 h-6 text-emerald-400 shrink-0" />
                ) : (
                  <XCircle className="w-6 h-6 text-rose-400 shrink-0" />
                )}
                <div>
                  <div className="text-sm font-bold uppercase tracking-wider">
                    {result.matched ? 'PROOFS MATCH · PROOF REPRODUCED' : 'PROOF MISMATCH · RUN FAILED'}
                  </div>
                  <p className="text-xs opacity-90 mt-0.5">{result.message}</p>
                </div>
              </div>

              {/* Side-by-Side Comparison */}
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800">
                  <div className="text-[11px] font-mono text-zinc-400 uppercase tracking-wider mb-1">
                    Original Result
                  </div>
                  <div className="text-xl font-bold font-mono text-white">
                    {result.original_result?.value !== undefined
                      ? `₹${result.original_result.value.toLocaleString()}`
                      : result.original_result?.selected_entity || 'Recorded'}
                  </div>
                  <div className="text-xs text-zinc-500 mt-1">
                    {result.original_result?.selected_entity || 'Initial run'}
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800">
                  <div className="text-[11px] font-mono text-zinc-400 uppercase tracking-wider mb-1">
                    Re-run Result
                  </div>
                  <div className="text-xl font-bold font-mono text-emerald-400">
                    {result.rerun_result?.value !== undefined
                      ? `₹${result.rerun_result.value.toLocaleString()}`
                      : result.rerun_result?.selected_entity || 'Executed'}
                  </div>
                  <div className="text-xs text-zinc-500 mt-1">
                    {result.rerun_result?.selected_entity || 'Fresh child subprocess'}
                  </div>
                </div>
              </div>

              {/* Terminal stdout */}
              {result.stdout && (
                <div className="space-y-1.5">
                  <div className="text-[11px] font-mono uppercase text-zinc-400 tracking-wider">
                    Subprocess Standard Output
                  </div>
                  <pre className="p-3 rounded-lg bg-zinc-950 border border-zinc-850 font-mono text-xs text-zinc-300 overflow-x-auto max-h-36">
                    {result.stdout}
                  </pre>
                </div>
              )}
            </div>
          ) : (
            <div className="py-8 text-center space-y-4">
              <p className="text-xs text-zinc-400">
                Click below to trigger a deterministic re-run of this proof in a restricted subprocess.
              </p>
              <button
                onClick={onTriggerRerun}
                className="px-4 py-2 bg-emerald-500 hover:bg-emerald-400 text-black font-semibold text-xs rounded-lg transition-colors cursor-pointer"
              >
                Execute Re-run Now
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-zinc-800 bg-zinc-900/40 flex justify-between items-center text-xs">
          <span className="text-zinc-500 font-mono">Real-time Python execution</span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-zinc-800 text-zinc-300 hover:bg-zinc-700 text-xs font-medium cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
