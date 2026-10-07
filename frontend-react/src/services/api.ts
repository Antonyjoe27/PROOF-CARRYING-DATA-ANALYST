import {
  AnalysisReport,
  DatasetsResponse,
  HealthStatus,
  HistoryItem,
  RerunResponse,
} from '../types';

const API_BASE = '/api';

export async function fetchHealth(): Promise<HealthStatus> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.statusText}`);
  return res.json();
}

export async function fetchDatasets(): Promise<DatasetsResponse> {
  const res = await fetch(`${API_BASE}/datasets`);
  if (!res.ok) throw new Error(`Failed to load datasets: ${res.statusText}`);
  return res.json();
}

export async function uploadDatasets(files: FileList | File[]): Promise<any> {
  const formData = new FormData();
  Array.from(files).forEach((file) => formData.append('files', file));
  const res = await fetch(`${API_BASE}/datasets/upload`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to upload datasets');
  }
  return res.json();
}

export async function loadDemoDatasets(): Promise<any> {
  const res = await fetch(`${API_BASE}/datasets/demo`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to load demo datasets');
  return res.json();
}

export async function loadMessyDemoDatasets(): Promise<any> {
  const res = await fetch(`${API_BASE}/datasets/demo/messy`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to load messy demo datasets');
  return res.json();
}

export async function clearDatasets(): Promise<any> {
  const res = await fetch(`${API_BASE}/datasets`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to clear datasets');
  return res.json();
}

export async function fetchTableRows(
  tableName: string,
  limit: number = 50,
  offset: number = 0
): Promise<{ table: string; total_rows: number; columns: string[]; rows: Record<string, any>[] }> {
  const res = await fetch(`${API_BASE}/datasets/${encodeURIComponent(tableName)}/rows?limit=${limit}&offset=${offset}`);
  if (!res.ok) throw new Error('Failed to fetch table rows');
  return res.json();
}

export async function runAnalysis(question: string): Promise<AnalysisReport> {
  const res = await fetch(`${API_BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Analysis failed (${res.status})`);
  }
  return res.json();
}

export async function rerunProof(payload: {
  code: string;
  question: string;
  original_value?: number;
  original_metric?: string;
  original_entity?: string;
}): Promise<RerunResponse> {
  const res = await fetch(`${API_BASE}/proof/rerun`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Re-run proof failed');
  }
  return res.json();
}

export async function fetchHistory(): Promise<HistoryItem[]> {
  const res = await fetch(`${API_BASE}/history`);
  if (!res.ok) throw new Error('Failed to fetch history');
  return res.json();
}

export async function fetchAnalysisById(auditId: string): Promise<AnalysisReport> {
  const res = await fetch(`${API_BASE}/analysis/${encodeURIComponent(auditId)}`);
  if (!res.ok) throw new Error('Failed to fetch analysis report');
  return res.json();
}
