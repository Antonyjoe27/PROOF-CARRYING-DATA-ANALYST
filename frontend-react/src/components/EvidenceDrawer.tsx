import React, { useState } from 'react';
import {
  X,
  FileSpreadsheet,
  Columns,
  Filter,
  GitMerge,
  ArrowRightLeft,
  AlertTriangle,
  CheckCircle2,
  Table,
} from 'lucide-react';
import { Evidence } from '../types';

interface EvidenceDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  evidence?: Evidence;
  onOpenSourceRows?: (tableName: string) => void;
}

export const EvidenceDrawer: React.FC<EvidenceDrawerProps> = ({
  isOpen,
  onClose,
  evidence,
  onOpenSourceRows,
}) => {
  if (!isOpen || !evidence) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-xl bg-zinc-950 border-l border-zinc-800 h-full overflow-y-auto flex flex-col shadow-2xl">
        {/* Header */}
        <div className="p-6 border-b border-zinc-800/80 flex items-center justify-between sticky top-0 bg-zinc-950/90 backdrop-blur-md z-10">
          <div>
            <div className="text-[11px] font-mono uppercase tracking-wider text-emerald-400 font-semibold mb-1">
              Deterministic Provenance
            </div>
            <h2 className="text-lg font-bold text-white tracking-tight">
              PROOF EVIDENCE
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6 flex-1">
          {/* Metadata */}
          <div className="p-4 rounded-xl bg-zinc-900/40 border border-zinc-800 text-xs space-y-1.5 font-mono">
            <div className="flex justify-between text-zinc-400">
              <span>Timestamp:</span>
              <span className="text-zinc-200">{evidence.timestamp}</span>
            </div>
            <div className="flex justify-between text-zinc-400">
              <span>Code SHA256:</span>
              <span className="text-zinc-200">{evidence.code_sha256?.slice(0, 16)}…</span>
            </div>
            <div className="flex justify-between text-zinc-400">
              <span>LLM Calls:</span>
              <span className="text-zinc-200">{evidence.llm_calls} / 3 hard cap</span>
            </div>
          </div>

          {/* Source Files */}
          <div className="space-y-3">
            <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
              <FileSpreadsheet className="w-4 h-4 text-cyan-400" />
              Source Files & Tables Used
            </h3>
            <div className="space-y-2">
              {evidence.tables_used.map((tbl, i) => (
                <div
                  key={i}
                  className="p-3 rounded-lg bg-zinc-900/60 border border-zinc-800 flex items-center justify-between text-xs"
                >
                  <div>
                    <span className="font-semibold text-white font-mono">{tbl}</span>
                    <div className="text-[11px] text-zinc-400 mt-0.5">
                      Columns: {evidence.columns_used[tbl]?.join(', ') || 'None'}
                    </div>
                  </div>
                  {onOpenSourceRows && (
                    <button
                      onClick={() => onOpenSourceRows(tbl)}
                      className="px-2.5 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded text-[11px] font-medium flex items-center gap-1 border border-zinc-700"
                    >
                      <Table className="w-3 h-3" />
                      <span>Inspect</span>
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Joins & Filters */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
                <GitMerge className="w-4 h-4 text-violet-400" />
                Table Joins
              </h3>
              <div className="p-3 rounded-lg bg-zinc-900/60 border border-zinc-800 text-xs text-zinc-300 font-mono min-h-[48px]">
                {evidence.joins.length > 0 ? evidence.joins.join(', ') : 'No joins required'}
              </div>
            </div>

            <div className="space-y-2">
              <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
                <Filter className="w-4 h-4 text-amber-400" />
                Applied Filters
              </h3>
              <div className="p-3 rounded-lg bg-zinc-900/60 border border-zinc-800 text-xs text-zinc-300 font-mono min-h-[48px]">
                {evidence.filters.length > 0 ? evidence.filters.join(', ') : 'No row filters'}
              </div>
            </div>
          </div>

          {/* Transformations */}
          <div className="space-y-2">
            <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
              <ArrowRightLeft className="w-4 h-4 text-emerald-400" />
              AST Transformations & Formulas
            </h3>
            <div className="p-3 rounded-lg bg-zinc-900/60 border border-zinc-800 text-xs space-y-1 font-mono text-zinc-300">
              {evidence.transformations.length > 0 ? (
                evidence.transformations.map((t, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="text-emerald-400">→</span>
                    <span>{t}</span>
                  </div>
                ))
              ) : (
                <div className="text-zinc-500">None extracted</div>
              )}
            </div>
          </div>

          {/* Data Quality Accounting */}
          {evidence.data_quality_records && evidence.data_quality_records.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-cyan-400" />
                Row Accounting & Data Integrity
              </h3>
              <div className="space-y-2">
                {evidence.data_quality_records.map((dq, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-lg bg-zinc-900/60 border border-zinc-800 text-xs space-y-1.5"
                  >
                    <div className="flex justify-between font-mono font-semibold text-zinc-200">
                      <span>{dq.table}</span>
                      <span className="text-emerald-400">{dq.rows_used.toLocaleString()} rows used</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-[11px] text-zinc-400 font-mono">
                      <div>Original: {dq.original_rows.toLocaleString()}</div>
                      <div>Duplicates removed: {dq.duplicate_rows_removed.toLocaleString()}</div>
                    </div>
                    {dq.note && <div className="text-[11px] text-amber-300">{dq.note}</div>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
