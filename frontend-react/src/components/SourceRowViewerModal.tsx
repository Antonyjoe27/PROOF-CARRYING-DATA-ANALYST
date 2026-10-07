import React, { useState, useEffect } from 'react';
import { X, Search, ChevronLeft, ChevronRight, Table, ArrowUpDown } from 'lucide-react';
import { fetchTableRows } from '../services/api';

interface SourceRowViewerModalProps {
  isOpen: boolean;
  onClose: () => void;
  tableName: string;
}

export const SourceRowViewerModal: React.FC<SourceRowViewerModalProps> = ({
  isOpen,
  onClose,
  tableName,
}) => {
  const [rows, setRows] = useState<Record<string, any>[]>([]);
  const [columns, setColumns] = useState<string[]>([]);
  const [totalRows, setTotalRows] = useState(0);
  const [limit] = useState(50);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (isOpen && tableName) {
      loadData(0);
    }
  }, [isOpen, tableName]);

  const loadData = async (newOffset: number) => {
    setIsLoading(true);
    try {
      const data = await fetchTableRows(tableName, limit, newOffset);
      setRows(data.rows);
      setColumns(data.columns);
      setTotalRows(data.total_rows);
      setOffset(newOffset);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  const filteredRows = rows.filter((r) =>
    search ? JSON.stringify(r).toLowerCase().includes(search.toLowerCase()) : true
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="w-full max-w-5xl bg-zinc-950 border border-zinc-800 rounded-2xl overflow-hidden shadow-2xl flex flex-col h-[85vh]">
        {/* Header */}
        <div className="p-5 border-b border-zinc-800 flex items-center justify-between bg-zinc-900/60">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <Table className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white tracking-tight flex items-center gap-2">
                <span>SOURCE ROW VIEWER</span>
                <span className="font-mono text-xs text-zinc-400 font-normal">({tableName})</span>
              </h2>
              <p className="text-xs text-zinc-400">
                Inspect authentic underlying data rows used to produce proofs.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Search Input */}
            <div className="relative w-64">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
              <input
                type="text"
                placeholder="Filter rows..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-800 rounded-lg pl-9 pr-3 py-1.5 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-700"
              />
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Table Content */}
        <div className="flex-1 overflow-auto bg-zinc-950">
          {isLoading ? (
            <div className="h-full flex items-center justify-center text-xs text-zinc-400">
              Loading rows...
            </div>
          ) : (
            <table className="w-full text-left border-collapse text-xs">
              <thead className="sticky top-0 bg-zinc-900/90 backdrop-blur-sm border-b border-zinc-800 text-zinc-400 font-mono">
                <tr>
                  <th className="p-3 w-12 text-zinc-600 border-r border-zinc-850">#</th>
                  {columns.map((col) => (
                    <th key={col} className="p-3 border-r border-zinc-850 whitespace-nowrap">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-900 font-mono">
                {filteredRows.map((row, idx) => (
                  <tr key={idx} className="hover:bg-zinc-900/50 transition-colors">
                    <td className="p-3 text-zinc-600 border-r border-zinc-900">
                      {offset + idx + 1}
                    </td>
                    {columns.map((col) => (
                      <td
                        key={col}
                        className="p-3 text-zinc-300 border-r border-zinc-900 whitespace-nowrap max-w-xs truncate"
                      >
                        {row[col] !== null && row[col] !== undefined ? String(row[col]) : '—'}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination Footer */}
        <div className="p-4 border-t border-zinc-800 bg-zinc-900/50 flex items-center justify-between text-xs text-zinc-400 font-mono">
          <div>
            Showing {Math.min(offset + 1, totalRows)} - {Math.min(offset + limit, totalRows)} of{' '}
            {totalRows} rows
          </div>
          <div className="flex items-center gap-2">
            <button
              disabled={offset <= 0 || isLoading}
              onClick={() => loadData(Math.max(0, offset - limit))}
              className="p-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 disabled:opacity-40 text-zinc-200 cursor-pointer"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              disabled={offset + limit >= totalRows || isLoading}
              onClick={() => loadData(offset + limit)}
              className="p-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 disabled:opacity-40 text-zinc-200 cursor-pointer"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
