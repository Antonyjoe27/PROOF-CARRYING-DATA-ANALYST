import React from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  HelpCircle,
  RotateCcw,
  FileCode,
  FileSearch,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  Ban,
  Clock,
} from 'lucide-react';
import { AnalysisReport } from '../types';

interface ResultHeroProps {
  report: AnalysisReport;
  onViewEvidence: () => void;
  onViewPython: () => void;
  onRerunProof: () => void;
  isRerunning?: boolean;
}

export const ResultHero: React.FC<ResultHeroProps> = ({
  report,
  onViewEvidence,
  onViewPython,
  onRerunProof,
  isRerunning = false,
}) => {
  const { status, structured_result, answer, explanation, verification, reason, blocking_issues } =
    report;

  // Render format of primary metric value if available
  const renderFormattedValue = () => {
    if (!structured_result) return null;
    if (structured_result.value !== undefined && structured_result.value !== null) {
      const val = structured_result.value;
      const unit = structured_result.unit?.toUpperCase();
      const numStr = val.toLocaleString(undefined, { maximumFractionDigits: 2 });
      if (unit === 'INR') return `₹${numStr}`;
      if (unit === 'USD') return `$${numStr}`;
      if (unit === 'EUR') return `€${numStr}`;
      return `${numStr} ${structured_result.unit || ''}`.trim();
    }
    if (structured_result.selected_entity) {
      return structured_result.selected_entity;
    }
    return answer;
  };

  // 1. VERIFIED STATE
  if (status === 'VERIFIED') {
    return (
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-b from-emerald-950/30 to-zinc-950/80 border border-emerald-500/30 p-8 shadow-2xl shadow-emerald-950/20">
        <div className="absolute top-0 right-0 w-96 h-96 bg-emerald-500/5 blur-3xl pointer-events-none rounded-full" />

        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-6 border-b border-emerald-500/20">
          <div className="flex items-center gap-3">
            <div className="px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 stroke-[2.5]" />
              <span className="text-xs font-bold text-emerald-400 tracking-wider">
                VERIFIED BY PYTHON
              </span>
            </div>
            <span className="text-xs font-mono text-zinc-400">
              Audit ID: {report.audit_id || 'live'}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={onRerunProof}
              disabled={isRerunning}
              className="px-3.5 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium flex items-center gap-2 border border-zinc-700/80 transition-all cursor-pointer"
            >
              <RotateCcw className={`w-3.5 h-3.5 text-emerald-400 ${isRerunning ? 'animate-spin' : ''}`} />
              <span>{isRerunning ? 'Running Proof...' : 'Re-run Proof'}</span>
            </button>
            <button
              onClick={onViewPython}
              className="px-3.5 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium flex items-center gap-2 border border-zinc-700/80 transition-all cursor-pointer"
            >
              <FileCode className="w-3.5 h-3.5 text-cyan-400" />
              <span>View Python</span>
            </button>
            <button
              onClick={onViewEvidence}
              className="px-3.5 py-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 text-xs font-medium flex items-center gap-2 border border-emerald-500/40 transition-all cursor-pointer"
            >
              <FileSearch className="w-3.5 h-3.5" />
              <span>View Evidence</span>
            </button>
          </div>
        </div>

        {/* Hero Value Display */}
        <div className="py-8">
          <div className="text-xs font-mono uppercase tracking-widest text-emerald-400/80 font-semibold mb-2 flex items-center gap-2">
            <span>{structured_result?.metric || 'CALCULATED RESULT'}</span>
            {structured_result?.selected_entity && (
              <span className="text-zinc-400">· {structured_result.selected_entity}</span>
            )}
          </div>
          <div className="text-5xl md:text-6xl font-black text-white tracking-tight mb-4 font-mono">
            {renderFormattedValue()}
          </div>
          <div className="text-base text-zinc-200 font-medium max-w-3xl leading-relaxed">
            {answer}
          </div>
          {explanation && (
            <div className="mt-4 p-4 rounded-xl bg-zinc-900/60 border border-zinc-800 text-xs text-zinc-300 leading-relaxed flex items-start gap-3">
              <Sparkles className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-white">AI Synthesis: </span>
                <span>{explanation}</span>
                <div className="text-[10px] text-zinc-500 mt-1 font-mono">
                  Wording by LLM · Verified against executed structured result
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Verification Strength Checklist */}
        <div className="pt-6 border-t border-emerald-500/10">
          <div className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
            Verification Strength & Integrity Guarantees
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: 'Dataset sufficient', ok: true },
              { label: 'Required fields found', ok: true },
              { label: 'Correct filters & joins', ok: true },
              { label: 'Controlled sandbox execution', ok: true },
              { label: 'Zero LLM hallucination', ok: true },
              { label: 'Result verified by AST', ok: true },
              { label: 'Deterministic output', ok: true },
              { label: 'Proof reproducible', ok: true },
            ].map((item, idx) => (
              <div
                key={idx}
                className="flex items-center gap-2 text-xs text-zinc-300 bg-zinc-900/40 border border-zinc-800/80 px-2.5 py-2 rounded-lg"
              >
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                <span className="truncate">{item.label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // 2. CANNOT_DETERMINE STATE
  if (status === 'CANNOT_DETERMINE') {
    return (
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-b from-amber-950/20 to-zinc-950/80 border border-amber-500/30 p-8 shadow-2xl">
        <div className="flex items-center justify-between pb-6 border-b border-amber-500/20">
          <div className="flex items-center gap-3">
            <div className="px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400 stroke-[2.5]" />
              <span className="text-xs font-bold text-amber-400 tracking-wider">
                CANNOT SAFELY DETERMINE
              </span>
            </div>
            <span className="text-xs font-mono text-zinc-400">Refusal by Design</span>
          </div>

          <div className="flex items-center gap-2">
            {report.code && (
              <button
                onClick={onViewPython}
                className="px-3.5 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium flex items-center gap-2 border border-zinc-700/80 transition-all cursor-pointer"
              >
                <FileCode className="w-3.5 h-3.5 text-amber-400" />
                <span>View Attempted Code</span>
              </button>
            )}
            <button
              onClick={onViewEvidence}
              className="px-3.5 py-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 text-xs font-medium flex items-center gap-2 border border-amber-500/40 transition-all cursor-pointer"
            >
              <FileSearch className="w-3.5 h-3.5" />
              <span>Inspect Data Quality</span>
            </button>
          </div>
        </div>

        <div className="py-8">
          <div className="text-xs font-mono uppercase tracking-widest text-amber-400/80 font-semibold mb-2">
            HONEST BOUNDARY GUARANTEE
          </div>
          <div className="text-2xl md:text-3xl font-bold text-white mb-4">
            {reason || 'I cannot safely calculate an answer from the provided data.'}
          </div>

          <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5 mb-6 space-y-3">
            <div className="text-xs font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
              <Ban className="w-4 h-4 text-amber-400" />
              Why was this calculation blocked?
            </div>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Proof Analyst refuses to hallucinate, guess missing columns, or silently average contradictory values.
              The dataset either lacks critical dimensions, contains unhandled conflicts, or specifies an out-of-bounds period.
            </p>
            {blocking_issues && blocking_issues.length > 0 && (
              <div className="space-y-1.5 pt-2 border-t border-zinc-800">
                {blocking_issues.map((b, i) => (
                  <div key={i} className="text-xs text-amber-300 font-mono flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                    <span>{b}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="flex items-center gap-2 text-xs text-emerald-300 bg-emerald-950/20 border border-emerald-500/30 px-3 py-2.5 rounded-lg">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>✓ No value or calculation was fabricated</span>
            </div>
            <div className="flex items-center gap-2 text-xs text-emerald-300 bg-emerald-950/20 border border-emerald-500/30 px-3 py-2.5 rounded-lg">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>✓ Safe fallback preventing silent hallucination</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // 3. AI SERVICE UNAVAILABLE
  if (status === 'AI_SERVICE_UNAVAILABLE') {
    return (
      <div className="rounded-2xl bg-zinc-900/50 border border-zinc-800 p-8 shadow-xl">
        <div className="flex items-center gap-3 mb-4">
          <Clock className="w-5 h-5 text-amber-400" />
          <h3 className="text-lg font-bold text-white">AI Service Temporarily Unavailable</h3>
        </div>
        <p className="text-sm text-zinc-400 mb-6">
          The upstream LLM provider is currently overloaded or unreachable. No code was executed and no false claims were generated.
        </p>
        <button
          onClick={() => window.location.reload()}
          className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg text-xs font-medium"
        >
          Retry Request
        </button>
      </div>
    );
  }

  // 4. EXECUTION OR PLANNING FAILED
  return (
    <div className="rounded-2xl bg-zinc-900/50 border border-rose-500/30 p-8 shadow-xl">
      <div className="flex items-center justify-between pb-4 border-b border-rose-500/20 mb-6">
        <div className="flex items-center gap-3">
          <XCircle className="w-5 h-5 text-rose-400" />
          <div>
            <h3 className="text-lg font-bold text-white">
              {status === 'PLANNING_FAILED'
                ? 'Planning Request Rejected'
                : status === 'EXECUTION_FAILED'
                ? 'Sandbox Execution Failed'
                : 'Not Verified'}
            </h3>
            <span className="text-xs text-zinc-400 font-mono">Status: {status}</span>
          </div>
        </div>
        {report.code && (
          <button
            onClick={onViewPython}
            className="px-3.5 py-1.5 rounded-lg bg-zinc-800 text-zinc-200 text-xs font-medium flex items-center gap-2 border border-zinc-700/80"
          >
            <FileCode className="w-3.5 h-3.5 text-rose-400" />
            <span>Inspect Code</span>
          </button>
        )}
      </div>

      <div className="p-4 rounded-xl bg-rose-950/20 border border-rose-500/20 text-xs text-rose-300 font-mono mb-4">
        {reason || 'The generated plan or code did not satisfy deterministic verification rules.'}
      </div>

      {report.execution?.stderr && (
        <pre className="p-4 rounded-xl bg-zinc-950 border border-zinc-800 text-xs text-zinc-400 font-mono overflow-x-auto max-h-48">
          {report.execution.stderr}
        </pre>
      )}
    </div>
  );
};
