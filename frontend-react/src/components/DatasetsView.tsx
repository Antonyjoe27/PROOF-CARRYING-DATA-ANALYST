import React, { useRef, useState } from 'react';
import {
  UploadCloud,
  FileSpreadsheet,
  CheckCircle2,
  AlertTriangle,
  ShieldAlert,
  Trash2,
  Table,
  Sparkles,
  Info,
} from 'lucide-react';
import { DatasetsResponse } from '../types';

interface DatasetsViewProps {
  datasetsData: DatasetsResponse | null;
  onUpload: (files: FileList) => Promise<void>;
  onLoadDemo: () => Promise<void>;
  onLoadMessyDemo: () => Promise<void>;
  onClear: () => Promise<void>;
  onInspectTable: (tableName: string) => void;
  isLoading: boolean;
}

export const DatasetsView: React.FC<DatasetsViewProps> = ({
  datasetsData,
  onUpload,
  onLoadDemo,
  onLoadMessyDemo,
  onClear,
  onInspectTable,
  isLoading,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onUpload(e.dataTransfer.files);
    }
  };

  const datasets = datasetsData?.datasets || [];
  const summary = datasetsData?.summary || {
    total_files: 0,
    total_rows: 0,
    total_columns: 0,
    total_warnings: 0,
  };

  return (
    <div className="space-y-8 animate-fade-in max-w-6xl mx-auto">
      {/* Header & Actions */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-zinc-800">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white">Datasets & Data Health</h2>
          <p className="text-xs text-zinc-400 mt-1">
            Ingest and inspect data. Clean profiling and data trap detection are computed automatically.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={onLoadDemo}
            disabled={isLoading}
            className="px-3 py-1.5 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 text-emerald-300 text-xs font-medium flex items-center gap-1.5 transition-all cursor-pointer"
          >
            <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
            <span>Load Demo Dataset</span>
          </button>

          <button
            onClick={onLoadMessyDemo}
            disabled={isLoading}
            className="px-3 py-1.5 rounded-lg bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 text-amber-300 text-xs font-medium flex items-center gap-1.5 transition-all cursor-pointer"
          >
            <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
            <span>Load Trap / Messy Dataset</span>
          </button>

          {datasets.length > 0 && (
            <button
              onClick={onClear}
              disabled={isLoading}
              className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-300 text-xs font-medium flex items-center gap-1.5 transition-all cursor-pointer"
            >
              <Trash2 className="w-3.5 h-3.5 text-rose-400" />
              <span>Clear</span>
            </button>
          )}
        </div>
      </div>

      {/* Drag & Drop Area */}
      <div
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-2xl p-8 text-center transition-all ${
          dragActive
            ? 'border-emerald-500 bg-emerald-500/5'
            : 'border-zinc-800 hover:border-zinc-700 bg-zinc-950/40'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".csv,.xlsx"
          className="hidden"
          onChange={(e) => {
            if (e.target.files && e.target.files.length > 0) {
              onUpload(e.target.files);
            }
          }}
        />

        <div className="flex flex-col items-center justify-center space-y-3">
          <div className="w-12 h-12 rounded-2xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-400">
            <UploadCloud className="w-6 h-6 text-emerald-400" />
          </div>
          <div>
            <div className="text-sm font-semibold text-white tracking-wide">
              DROP YOUR DATA HERE
            </div>
            <div className="text-xs text-zinc-400 mt-1">
              Supports <span className="text-zinc-200 font-mono">CSV</span> and{' '}
              <span className="text-zinc-200 font-mono">XLSX</span> multi-table workbooks
            </div>
          </div>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isLoading}
            className="mt-2 px-4 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-xs text-white font-medium cursor-pointer"
          >
            Browse files
          </button>
        </div>
      </div>

      {/* Dataset Health Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-5 rounded-xl bg-zinc-900/40 border border-zinc-800">
          <div className="text-[11px] font-mono text-zinc-400 uppercase tracking-wider">
            Total Rows
          </div>
          <div className="text-2xl font-bold font-mono text-white mt-1">
            {summary.total_rows.toLocaleString()}
          </div>
          <div className="text-[11px] text-zinc-500 mt-1">Across all tables</div>
        </div>

        <div className="p-5 rounded-xl bg-zinc-900/40 border border-zinc-800">
          <div className="text-[11px] font-mono text-zinc-400 uppercase tracking-wider">
            Total Columns
          </div>
          <div className="text-2xl font-bold font-mono text-white mt-1">
            {summary.total_columns}
          </div>
          <div className="text-[11px] text-zinc-500 mt-1">Dimensions profiled</div>
        </div>

        <div className="p-5 rounded-xl bg-zinc-900/40 border border-zinc-800">
          <div className="text-[11px] font-mono text-zinc-400 uppercase tracking-wider">
            Tables Loaded
          </div>
          <div className="text-2xl font-bold font-mono text-cyan-400 mt-1">
            {summary.total_files}
          </div>
          <div className="text-[11px] text-zinc-500 mt-1">Ready for retrieval</div>
        </div>

        <div className="p-5 rounded-xl bg-zinc-900/40 border border-zinc-800">
          <div className="text-[11px] font-mono text-zinc-400 uppercase tracking-wider">
            Integrity Warnings
          </div>
          <div
            className={`text-2xl font-bold font-mono mt-1 ${
              summary.total_warnings > 0 ? 'text-amber-400' : 'text-emerald-400'
            }`}
          >
            {summary.total_warnings}
          </div>
          <div className="text-[11px] text-zinc-500 mt-1">
            {summary.total_warnings > 0 ? 'Data traps flagged' : 'Clean schemas'}
          </div>
        </div>
      </div>

      {/* Cross Table Warnings */}
      {datasetsData?.cross_table_warnings && datasetsData.cross_table_warnings.length > 0 && (
        <div className="p-4 rounded-xl bg-amber-950/20 border border-amber-500/30 text-xs space-y-2">
          <div className="font-semibold text-amber-400 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            Cross-Table Integrity Warnings
          </div>
          <div className="space-y-1">
            {datasetsData.cross_table_warnings.map((w, i) => (
              <div key={i} className="text-amber-200/90 font-mono">
                • {w}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Dataset Cards */}
      <div className="space-y-4">
        <h3 className="text-sm font-bold text-white uppercase tracking-wider">
          Loaded Tables ({datasets.length})
        </h3>

        {datasets.length === 0 ? (
          <div className="p-12 text-center text-xs text-zinc-500 bg-zinc-900/20 border border-zinc-800/60 rounded-xl">
            No datasets uploaded yet. Click "Load Demo Dataset" or drop files above.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {datasets.map((d) => (
              <div
                key={d.name}
                className="p-5 rounded-xl bg-zinc-900/50 border border-zinc-800 space-y-4 hover:border-zinc-700/80 transition-all"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-zinc-800 border border-zinc-700 flex items-center justify-center text-cyan-400">
                      <FileSpreadsheet className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="font-semibold text-white text-sm font-mono">{d.name}</div>
                      <div className="text-[11px] text-zinc-400">
                        {d.rows.toLocaleString()} rows · {d.columns_count} columns
                        {d.sheet ? ` · Sheet: ${d.sheet}` : ''}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" />
                      Loaded
                    </span>
                    <button
                      onClick={() => onInspectTable(d.name)}
                      className="p-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs cursor-pointer"
                      title="Inspect rows"
                    >
                      <Table className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Column badges */}
                <div className="flex flex-wrap gap-1.5 pt-2 border-t border-zinc-800/80">
                  {d.columns.map((c) => (
                    <span
                      key={c.name}
                      className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800/80 border border-zinc-700/60 text-zinc-300"
                    >
                      {c.name} <span className="text-zinc-500">({c.dtype})</span>
                    </span>
                  ))}
                </div>

                {/* Warnings / Traps */}
                {d.warnings.length > 0 && (
                  <div className="p-2.5 rounded-lg bg-amber-950/20 border border-amber-500/20 text-[11px] text-amber-300 font-mono space-y-1">
                    {d.warnings.map((w, idx) => (
                      <div key={idx}>⚠ {w}</div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
