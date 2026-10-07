import React, { useState, useEffect } from 'react';
import {
  Sidebar,
} from './components/Sidebar';
import { ProofChain } from './components/ProofChain';
import { ResultHero } from './components/ResultHero';
import { EvidenceDrawer } from './components/EvidenceDrawer';
import { PythonProofModal } from './components/PythonProofModal';
import { RerunProofModal } from './components/RerunProofModal';
import { SourceRowViewerModal } from './components/SourceRowViewerModal';
import { DatasetsView } from './components/DatasetsView';
import { HistoryView } from './components/HistoryView';
import {
  fetchHealth,
  fetchDatasets,
  uploadDatasets,
  loadDemoDatasets,
  loadMessyDemoDatasets,
  clearDatasets,
  runAnalysis,
  rerunProof,
  fetchHistory,
  fetchAnalysisById,
} from './services/api';
import {
  HealthStatus,
  DatasetsResponse,
  AnalysisReport,
  RerunResponse,
  HistoryItem,
} from './types';
import {
  ArrowRight,
  Sparkles,
  ShieldCheck,
  Radio,
  FileCheck2,
  Database,
  History,
  AlertCircle,
  HelpCircle,
} from 'lucide-react';

export function App() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'datasets' | 'history' | 'proofs'>('dashboard');
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [datasetsData, setDatasetsData] = useState<DatasetsResponse | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);

  // Query & Analysis state
  const [question, setQuestion] = useState('Which product generated the highest profit?');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [currentReport, setCurrentReport] = useState<AnalysisReport | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  // Modals and Drawers
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [pythonModalOpen, setPythonModalOpen] = useState(false);
  const [rerunModalOpen, setRerunModalOpen] = useState(false);
  const [sourceRowModalOpen, setSourceRowModalOpen] = useState(false);
  const [inspectedTable, setInspectedTable] = useState('');

  // Rerun state
  const [isRerunning, setIsRerunning] = useState(false);
  const [rerunResult, setRerunResult] = useState<RerunResponse | null>(null);

  // Suggested Queries
  const suggestions = [
    { text: 'Which product generated the highest profit?', label: 'Profit Leader' },
    { text: 'Which region had the highest revenue?', label: 'Regional Revenue' },
    { text: 'What was the average revenue in Q3?', label: 'Q3 Average' },
    { text: 'What was the total profit in 2035?', label: 'Refusal Trap (2035)' },
  ];

  // Initial Data Load
  useEffect(() => {
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    try {
      const h = await fetchHealth().catch(() => null);
      setHealth(h);
      const ds = await fetchDatasets().catch(() => null);
      setDatasetsData(ds);
      const hist = await fetchHistory().catch(() => []);
      setHistory(hist);
    } catch (e) {
      console.error('Error loading initial data', e);
    }
  };

  const handleAnalyze = async (qToAnalyze?: string) => {
    const q = (qToAnalyze || question).trim();
    if (!q) return;

    setIsAnalyzing(true);
    setAnalysisError(null);
    try {
      const report = await runAnalysis(q);
      setCurrentReport(report);
      // Refresh history & datasets
      fetchHistory().then(setHistory).catch(() => {});
    } catch (err: any) {
      setAnalysisError(err.message || 'Analysis failed');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleUploadFiles = async (files: FileList) => {
    await uploadDatasets(files);
    await loadInitialData();
  };

  const handleLoadDemo = async () => {
    await loadDemoDatasets();
    await loadInitialData();
  };

  const handleLoadMessyDemo = async () => {
    await loadMessyDemoDatasets();
    await loadInitialData();
  };

  const handleClear = async () => {
    await clearDatasets();
    await loadInitialData();
  };

  const handleInspectTable = (tableName: string) => {
    setInspectedTable(tableName);
    setSourceRowModalOpen(true);
  };

  const handleRerunProof = async () => {
    if (!currentReport || !currentReport.code) return;
    setRerunModalOpen(true);
    setIsRerunning(true);
    try {
      const res = await rerunProof({
        code: currentReport.code,
        question: currentReport.question,
        original_value: currentReport.structured_result?.value,
        original_metric: currentReport.structured_result?.metric,
        original_entity: currentReport.structured_result?.selected_entity,
      });
      setRerunResult(res);
    } catch (e: any) {
      setRerunResult({
        matched: false,
        status: 'EXECUTION_FAILED',
        rerun_summary: '',
        stdout: '',
        stderr: e.message || 'Failed to rerun',
        message: e.message || 'Execution error',
      });
    } finally {
      setIsRerunning(false);
    }
  };

  const handleSelectAudit = async (auditId: string) => {
    try {
      const report = await fetchAnalysisById(auditId);
      setCurrentReport(report);
      setQuestion(report.question);
      setActiveTab('dashboard');
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="flex h-screen bg-[#090a0f] text-zinc-100 overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        health={health}
        datasetsCount={datasetsData?.summary.total_files || 0}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Top Header */}
        <header className="h-14 border-b border-zinc-800/80 px-6 flex items-center justify-between bg-[#0b0c13]/60 backdrop-blur-md shrink-0">
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold text-zinc-300">
              Proof-Carrying Data Analyst
            </span>
            <span className="text-zinc-600 font-mono text-xs">/</span>
            <span className="text-xs font-mono text-emerald-400 font-medium">
              Every answer comes with proof
            </span>
          </div>

          <div className="flex items-center gap-3">
            {datasetsData && datasetsData.summary.total_files > 0 ? (
              <span className="px-2.5 py-1 rounded-full bg-zinc-800/80 border border-zinc-700/80 text-[11px] font-mono text-zinc-300 flex items-center gap-1.5">
                <Database className="w-3 h-3 text-cyan-400" />
                {datasetsData.summary.total_files} active tables · {datasetsData.summary.total_rows.toLocaleString()} rows
              </span>
            ) : (
              <button
                onClick={handleLoadDemo}
                className="px-2.5 py-1 rounded-full bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 text-[11px] font-mono text-emerald-400 flex items-center gap-1.5 transition-colors cursor-pointer"
              >
                <Sparkles className="w-3 h-3" />
                Click to load demo data
              </button>
            )}

            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-950/30 border border-emerald-500/30 text-emerald-400 text-xs font-medium font-mono">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>System Ready</span>
            </div>
          </div>
        </header>

        {/* View Switcher */}
        <main className="flex-1 overflow-y-auto p-6 md:p-8">
          {activeTab === 'dashboard' && (
            <div className="max-w-5xl mx-auto space-y-8 animate-fade-in">
              {/* Hero Ask Box */}
              <div className="text-center space-y-2 pt-2">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-400 mb-2">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  <span>AI plans · Python computes · Verifier proves</span>
                </div>
                <h1 className="text-3xl md:text-5xl font-black text-white tracking-tight">
                  ASK YOUR DATA.
                </h1>
                <p className="text-sm text-zinc-400 max-w-xl mx-auto">
                  Get answers you can verify, reproduce, and inspect down to the exact row and line of code.
                </p>
              </div>

              {/* Search / Input Box */}
              <div className="relative max-w-3xl mx-auto">
                <div className="relative flex items-center shadow-2xl rounded-2xl bg-zinc-900/90 border border-zinc-700/80 focus-within:border-emerald-500/60 focus-within:ring-2 focus-within:ring-emerald-500/20 transition-all p-2">
                  <input
                    type="text"
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
                    placeholder="Ask a question about your datasets..."
                    className="w-full bg-transparent px-4 py-2.5 text-sm md:text-base text-white placeholder-zinc-500 focus:outline-none font-medium"
                  />
                  <button
                    onClick={() => handleAnalyze()}
                    disabled={isAnalyzing || !question.trim()}
                    className="px-5 py-2.5 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-black font-bold text-xs md:text-sm rounded-xl flex items-center gap-2 transition-all shrink-0 cursor-pointer shadow-lg shadow-emerald-500/20"
                  >
                    <span>{isAnalyzing ? 'ANALYZING...' : 'ANALYZE'}</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>

                {/* Suggestions */}
                <div className="flex flex-wrap items-center gap-2 mt-3 justify-center">
                  <span className="text-[11px] text-zinc-500 font-medium">Suggestions:</span>
                  {suggestions.map((s, idx) => (
                    <button
                      key={idx}
                      onClick={() => {
                        setQuestion(s.text);
                        handleAnalyze(s.text);
                      }}
                      className="px-2.5 py-1 rounded-lg bg-zinc-900/60 hover:bg-zinc-800 border border-zinc-800/80 text-[11px] text-zinc-400 hover:text-zinc-200 transition-colors font-mono cursor-pointer"
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Error banner if analyze failed */}
              {analysisError && (
                <div className="max-w-3xl mx-auto p-4 rounded-xl bg-rose-950/20 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2 font-mono">
                  <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
                  <span>{analysisError}</span>
                </div>
              )}

              {/* Proof Chain Pipeline */}
              {(isAnalyzing || currentReport) && (
                <div className="max-w-4xl mx-auto">
                  <ProofChain
                    stages={currentReport?.stages || []}
                    currentStatus={currentReport?.status}
                    isAnalyzing={isAnalyzing}
                  />
                </div>
              )}

              {/* Hero Result Section */}
              {currentReport && (
                <div className="max-w-4xl mx-auto">
                  <ResultHero
                    report={currentReport}
                    onViewEvidence={() => setEvidenceOpen(true)}
                    onViewPython={() => setPythonModalOpen(true)}
                    onRerunProof={handleRerunProof}
                    isRerunning={isRerunning}
                  />
                </div>
              )}
            </div>
          )}

          {activeTab === 'datasets' && (
            <DatasetsView
              datasetsData={datasetsData}
              onUpload={handleUploadFiles}
              onLoadDemo={handleLoadDemo}
              onLoadMessyDemo={handleLoadMessyDemo}
              onClear={handleClear}
              onInspectTable={handleInspectTable}
              isLoading={isAnalyzing}
            />
          )}

          {activeTab === 'history' && (
            <HistoryView
              history={history}
              onSelectAudit={handleSelectAudit}
              isLoading={false}
            />
          )}

          {activeTab === 'proofs' && (
            <div className="max-w-4xl mx-auto space-y-6">
              <h2 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
                <FileCheck2 className="w-6 h-6 text-emerald-400" />
                Active Proof Inspection
              </h2>
              {currentReport ? (
                <ResultHero
                  report={currentReport}
                  onViewEvidence={() => setEvidenceOpen(true)}
                  onViewPython={() => setPythonModalOpen(true)}
                  onRerunProof={handleRerunProof}
                  isRerunning={isRerunning}
                />
              ) : (
                <div className="p-12 text-center text-xs text-zinc-500 bg-zinc-900/20 border border-zinc-800 rounded-xl">
                  No active proof. Run an analysis on the dashboard first.
                </div>
              )}
            </div>
          )}
        </main>
      </div>

      {/* Slide-out Drawers & Modals */}
      <EvidenceDrawer
        isOpen={evidenceOpen}
        onClose={() => setEvidenceOpen(false)}
        evidence={currentReport?.evidence}
        onOpenSourceRows={(tbl) => {
          setEvidenceOpen(false);
          handleInspectTable(tbl);
        }}
      />

      <PythonProofModal
        isOpen={pythonModalOpen}
        onClose={() => setPythonModalOpen(false)}
        code={currentReport?.code || ''}
      />

      <RerunProofModal
        isOpen={rerunModalOpen}
        onClose={() => setRerunModalOpen(false)}
        isLoading={isRerunning}
        result={rerunResult}
        onTriggerRerun={handleRerunProof}
      />

      <SourceRowViewerModal
        isOpen={sourceRowModalOpen}
        onClose={() => setSourceRowModalOpen(false)}
        tableName={inspectedTable}
      />
    </div>
  );
}

export default App;
