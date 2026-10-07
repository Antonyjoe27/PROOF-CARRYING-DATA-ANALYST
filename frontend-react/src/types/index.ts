export interface HealthStatus {
  status: string;
  openrouter_configured: boolean;
  model: string;
  tables_loaded: number;
  uptime_seconds: number;
}

export interface ColumnInfo {
  name: string;
  dtype: string;
  missing: number;
  unique: number;
  likely_numeric: boolean;
  likely_date: boolean;
  ambiguous_date: boolean;
  unit_hints: string[];
}

export interface DatasetInfo {
  name: string;
  variable: string;
  source_file: string;
  sheet: string | null;
  rows: number;
  columns_count: number;
  duplicate_rows: number;
  warnings: string[];
  columns: ColumnInfo[];
  sample_rows: Record<string, any>[];
}

export interface DatasetsResponse {
  datasets: DatasetInfo[];
  cross_table_warnings: string[];
  summary: {
    total_files: number;
    total_rows: number;
    total_columns: number;
    total_warnings: number;
  };
}

export interface StructuredResult {
  result_type: 'ranking' | 'aggregate' | 'comparison';
  metric: string;
  value?: number;
  unit?: string;
  selected_entity?: string;
  direction?: 'highest' | 'lowest';
  operation?: string;
  entities?: string[];
  values?: Record<string, number>;
  rows_used?: number;
}

export interface DataQualityRecord {
  table: string;
  original_rows: number;
  duplicate_rows_detected: number;
  duplicate_rows_removed: number;
  missing: Record<string, { missing: number; rows_excluded: number }>;
  rows_used: number;
  note: string;
}

export interface Evidence {
  question: string;
  timestamp: string;
  files_used: string[];
  tables_used: string[];
  sheets_used: string[];
  columns_used: Record<string, string[]>;
  retrieval: string[];
  planned_operations: string[];
  filters: string[];
  joins: string[];
  transformations: string[];
  data_quality_warnings: string[];
  data_quality_actions: string[];
  data_quality_records: DataQualityRecord[];
  structured_result?: StructuredResult;
  result_summary: string;
  llm_calls: number;
  code: string;
  code_sha256: string;
  execution_status: string;
  execution_output: string;
  verification_status: string;
  data_fingerprints: Record<string, string>;
}

export interface DataIssue {
  severity: 'SAFE' | 'WARNING' | 'BLOCKING';
  kind: string;
  message: string;
  table?: string;
  column?: string;
}

export interface AnalysisReport {
  question: string;
  status:
    | 'VERIFIED'
    | 'CANNOT_DETERMINE'
    | 'NOT_VERIFIED'
    | 'EXECUTION_FAILED'
    | 'AI_SERVICE_UNAVAILABLE'
    | 'PLANNING_FAILED'
    | 'CODE_GENERATION_FAILED';
  answer: string;
  reason?: string;
  explanation: string;
  plan?: {
    answerable: boolean;
    reason: string;
    required_sources: string[];
    required_columns: string[];
    derived_columns: string[];
    operation: string;
    operations: string[];
    code: string;
  };
  code: string;
  execution?: {
    success: boolean;
    stdout: string;
    stderr: string;
    returncode?: number;
    timed_out: boolean;
    blocked_reasons: string[];
  };
  verification?: {
    status: string;
    checks: Record<string, boolean>;
    reasons: string[];
    blocking_issues: string[];
    warnings: string[];
    structured_result?: StructuredResult;
    issues: DataIssue[];
  };
  evidence?: Evidence;
  quality_notes: string[];
  blocking_issues: string[];
  rejected_answer?: string;
  issues: DataIssue[];
  llm_calls: number;
  structured_result?: StructuredResult;
  stages: string[];
  audit_id?: string;
}

export interface RerunResponse {
  matched: boolean;
  status: string;
  original_result?: Record<string, any>;
  rerun_result?: Record<string, any>;
  rerun_summary: string;
  stdout: string;
  stderr: string;
  message: string;
}

export interface HistoryItem {
  audit_id: string;
  question: string;
  status: string;
  answer: string;
  created_at: string;
  llm_calls: number;
  files_used: string[];
  metric: string;
  value?: number;
}
